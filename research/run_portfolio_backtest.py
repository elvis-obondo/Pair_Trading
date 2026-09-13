"""Walk the scanner and the portfolio bar by bar over historical prices.

WHAT THIS IS FOR

The live scanner should not be trusted before its behaviour has been measured.
This runs the same Portfolio and the same entry/exit geometry the live scanner
uses, so the thing that is measured is the thing that will run. The z-screen is
the one part computed differently -- in bulk rather than per bar -- and
validate_backtest_screen.py asserts the two produce identical candidates.
No nautilus: a 212-instrument engine would materialise ~5.3M Bar objects, and
this laptop has 8GB.

WHAT IT REPORTS, AND WHAT IT DELIBERATELY DOES NOT

Per-trade net_pct and R (profit per unit risked). Both are immune to compounding.

It does NOT report a compounded return multiple. Percentage-of-equity sizing with
no liquidity ceiling grows notional without bound -- the full-spec walk-forward
produced 1.1e11x that way, arithmetically correct and physically impossible once
a position exceeds the depth of the pair it trades. The equity curve is written
to the ledger because the sizer genuinely uses it, but it is not a result.

COST

The z-screen runs ONCE PER PAIR over the whole window, not once per bar. Calling
the live scanner per bar re-derives each pair's entire rolling history 8,640
times for a 6-month run -- measured at 20.4 hours against 30 seconds for the
bulk pass. See research/backtest_screen.py; the two are mathematically identical
because the rolling statistics never look forward, and validate_backtest_screen.py
asserts that equality against generate_entry_signal directly.

theta is still fitted one candidate at a time, lazily, only at bars where a slot
is actually free. That is the remaining cost and it is proportional to how often
the book has room.

Usage:
    python research/run_portfolio_backtest.py --days 180
    python research/run_portfolio_backtest.py --days 180 --end-date 2026-06-13
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
import time

import numpy as np
import pandas as pd

from universe_panel import load_panel, usable_tickers, tradeable_pairs
from rolling_spread import min_bars_required
from backtest_screen import build_screen, rank_bar
from portfolio import Portfolio
import book_state as cfg

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(PROJECT_ROOT, "research", "portfolio_backtest_trades.csv")


def run(days=30, stride=1, bar_hours=0.5, equity=300.0, slots=10, end_date=None,
        min_deviation_sigma=3.0, take_profit_pct=1.0, stop_sigma=0.5,
        max_hold_hours=72.0, capital_frac=0.05, leverage=20.0,
        max_per_ticker=None, stop_fill_overshoot=None, max_notional=None,
        rank_by="theta", exit_check_minutes=None, debounce_minutes=0.0,
        grace_minutes=0.0, out_path=OUT):
    need = min_bars_required(bar_hours)
    bars_per_day = int(round(24 / bar_hours))

    full = load_panel()
    # end_date anchors the window so a fold can be placed OUT OF SAMPLE. Without
    # it the window is always the most recent `days`, which for this project sits
    # 95% inside the period the settled parameters were fitted on (2026-06-14 to
    # 2026-09-11) -- an in-sample result that says nothing about forward
    # performance. 641 days of never-fitted history precede that window.
    if end_date is not None:
        full = full.loc[:pd.Timestamp(end_date)]

    # Warm-up first, then the evaluated window. The warm-up is NOT part of the
    # window: every evaluated bar must have a complete history behind it.
    n_eval = days * bars_per_day
    panel = full.tail(need + n_eval)
    if len(panel) < need + stride:
        raise SystemExit(f"need > {need} bars of history, have {len(panel)}")

    tickers = usable_tickers(panel, bar_hours)
    # A SINGLE partial trailing bar guts the universe. usable_tickers demands a
    # complete history, so every ticker that has not yet printed the forming bar
    # is dropped -- measured once at 17 tickers out of 212, with the run carrying
    # on and reporting numbers as though nothing were wrong.
    if len(tickers) < 0.5 * panel.shape[1]:
        raise SystemExit(
            f"[FAIL] only {len(tickers)} of {panel.shape[1]} tickers have a complete "
            f"history here. The last bar ({panel.index[-1]}) is missing "
            f"{panel.tail(1).isna().sum(axis=1).iloc[0]} tickers — it is probably still "
            f"forming. Re-run with --end-date '{panel.index[-2]}'")
    pairs = tradeable_pairs(tickers)
    eval_idx = list(range(need, len(panel), stride))
    print(f"[INFO] {len(tickers)} tickers, {len(pairs):,} pairs")
    print(f"[INFO] {len(eval_idx):,} bars to evaluate "
          f"({panel.index[need]} -> {panel.index[-1]}), stride {stride}")
    for name, live, used in (("max_per_ticker", cfg.MAX_PER_TICKER, max_per_ticker),
                             ("max_notional", cfg.MAX_NOTIONAL, max_notional),
                             ("stop_sigma", cfg.STOP_SIGMA, stop_sigma),
                             ("max_hold_hours", cfg.MAX_HOLD_HOURS, max_hold_hours),
                             ("min_deviation_sigma", cfg.MIN_DEVIATION_SIGMA, min_deviation_sigma)):
        if live != used:
            print(f"[WARN] {name}={used} but the LIVE book runs {live} — "
                  f"this run does not describe the live strategy")
    print(f"[INFO] entry {min_deviation_sigma} sigma | tp {take_profit_pct} | "
          f"stop {stop_sigma} | hold {max_hold_hours}h | {slots} slots | "
          f"{capital_frac*100:.0f}% margin at {leverage:.0f}x"
          + (f" | max {max_per_ticker}/ticker" if max_per_ticker else "")
          + f" | rank by {rank_by}" + "\n")

    # Fine-grained exit checking. bar_hours*60 (the default) means "check only
    # at bar closes", which is what this engine has always done. Anything smaller
    # loads a finer price grid and checks the FROZEN stop and take-profit levels
    # between bar closes as well -- no rolling statistic is recomputed, because
    # none of them change once a position is open.
    bar_minutes = int(round(bar_hours * 60))
    exit_check_minutes = bar_minutes if exit_check_minutes is None else int(exit_check_minutes)
    fine = None
    if exit_check_minutes < bar_minutes:
        import intrabar
        print(f"[INFO] loading {exit_check_minutes}m prices for intrabar exit checks...")
        fine = intrabar.load_panel(tickers, start=panel.index[need], end=panel.index[-1],
                                   timeframe=f"{exit_check_minutes}m")
        # The 30m panel is tz-naive UTC; intrabar returns tz-aware UTC. Both are
        # UTC — only the label differs — so reconcile once, here, at the boundary.
        if panel.index.tz is None and fine.index.tz is not None:
            fine.index = fine.index.tz_convert("UTC").tz_localize(None)
        fine.index = fine.index.as_unit(panel.index.unit)
        missing = [t for t in tickers if t not in fine.columns]
        if missing:
            # Silently checking only SOME positions intrabar would make the
            # comparison meaningless in a way nothing downstream could detect.
            raise SystemExit(
                f"[FAIL] {len(missing)} of {len(tickers)} tickers have no "
                f"{exit_check_minutes}m data ({', '.join(missing[:6])}...). "
                f"Download it before running, or the two arms are not comparable.")
        print(f"[INFO] {len(fine):,} {exit_check_minutes}m bars x {len(fine.columns)} tickers "
              f"({fine.index[0]} -> {fine.index[-1]})\n")

    print("[INFO] screening the whole window, once per pair...")
    ts = time.time()
    screen = build_screen(panel, pairs, need, min_deviation_sigma, bar_hours)
    by_bar = {b: g for b, g in screen.groupby("bar", sort=False)} if len(screen) else {}
    print(f"[INFO] {len(screen):,} candidate rows across {len(by_bar):,} bars "
          f"in {time.time()-ts:.0f}s\n")
    arrays = {t: panel[t].to_numpy(dtype=float) for t in tickers}

    pf = Portfolio(equity=equity, max_slots=slots, capital_frac=capital_frac,
                   leverage=leverage, stop_sigma=stop_sigma,
                   max_hold_hours=max_hold_hours, max_per_ticker=max_per_ticker,
                   stop_fill_overshoot=stop_fill_overshoot, max_notional=max_notional,
                   debounce_minutes=debounce_minutes, grace_minutes=grace_minutes)
    if stop_fill_overshoot is not None:
        print(f"[INFO] adverse exits booked at {stop_fill_overshoot:.2f}x the stop "
              f"distance, not at the bar-close spread.")
        if abs(stop_fill_overshoot - cfg.MEASURED_STOP_OVERSHOOT) < 1e-9:
            print("[INFO] that is the MEASURED live figure (tick-watched monitor, "
                  "median 1.042x).")
        elif stop_fill_overshoot <= 1.0:
            print("[WARN] 1.00x is perfect execution and has NEVER been observed. "
                  "This is an upper bound on the edge, not a result.\n")
        else:
            print(f"[WARN] {stop_fill_overshoot:.2f}x is not the measured figure "
                  f"({cfg.MEASURED_STOP_OVERSHOOT:.2f}x). Say why when quoting it.\n")
    else:
        print("[WARN] booking adverse exits at the BAR-CLOSE spread. That is the "
              "30-minute checking this system replaced;")
        print("[WARN] it measured 1.53x median overshoot. Pass --stop-fill-overshoot "
              f"{cfg.MEASURED_STOP_OVERSHOOT} for the live figure.\n")

    t0 = time.time()
    n_open = 0
    for k, i in enumerate(eval_idx, 1):
        now = panel.index[i]
        row = panel.iloc[i]
        prices = {t: row[t] for t in tickers}

        # Exits first, so a slot freed this bar is reusable this bar -- which is
        # what the live loop does.
        pf.evaluate_exits(prices, now)
        if pf.free_slots > 0 and i in by_bar:
            cands = rank_bar(by_bar[i], arrays, take_profit_pct, bar_hours,
                             rank_by=rank_by)
            n_open += len(pf.fill_slots(cands, now))

        # Walk the minutes BETWEEN this bar close and the next, checking exits
        # against the frozen levels. Entries are untouched: they still happen
        # only at bar closes, from that bar's candidates, so the two arms open
        # exactly the same trades and any difference in results is the exit
        # timing alone. validate_intrabar asserts that equality.
        if fine is not None and i + 1 < len(panel):
            lo, hi = panel.index[i], panel.index[i + 1]
            window = fine.loc[(fine.index > lo) & (fine.index < hi)]
            for ts, frow in window.iterrows():
                if not pf.open_positions:
                    break
                held = {t for p_ in pf.open_positions for t in p_.pair}
                fp = {t: frow[t] for t in held if t in frow.index}
                # A NaN price is a minute the instrument did not trade. Skip the
                # position rather than mark it -- same rule the live monitor
                # applies when a leg goes stale.
                fp = {t: v for t, v in fp.items() if np.isfinite(v)}
                if fp:
                    pf.evaluate_exits(fp, ts)

        if k % 200 == 0 or k == len(eval_idx):
            el = time.time() - t0
            print(f"  bar {k}/{len(eval_idx)}  {now}  "
                  f"open {len(pf.open_positions)}  closed {len(pf.closed)}  "
                  f"{el:.0f}s eta {el/k*(len(eval_idx)-k):.0f}s", flush=True)

    print(f"\n[INFO] opened {n_open}, closed {len(pf.closed)}, "
          f"still open {len(pf.open_positions)} in {time.time()-t0:.0f}s")
    report(pf, out_path)
    return pf


def report(pf: Portfolio, out_path: str = OUT) -> None:
    if not pf.closed:
        print("\nNo completed trades.")
        return
    d = pd.DataFrame(pf.closed)
    d.to_csv(out_path, index=False)

    print("\n" + "=" * 100)
    print("PER-TRADE RESULTS  (the compounded multiple is deliberately not quoted)")
    print("=" * 100)
    print(f"  trades closed        : {len(d)}")
    print(f"  mean net_pct         : {d.net_pct.mean():+.4f}%  "
          f"(median {d.net_pct.median():+.4f}%)")
    print(f"  mean R               : {d.r.mean():+.4f}   (median {d.r.median():+.4f})")
    print(f"  win rate             : {(d.realized_pnl_net > 0).mean()*100:.1f}%")
    print(f"  mean hours held      : {d.hours_held.mean():.1f}  (max {d.hours_held.max():.1f})")

    print("\n  by exit reason:")
    for reason, g in d.groupby("exit_reason"):
        print(f"    {reason:14s} {len(g):5d} ({len(g)/len(d)*100:5.1f}%)  "
              f"mean R {g.r.mean():+.3f}  mean hrs {g.hours_held.mean():6.1f}")

    ranked = d[d.theta_at_entry.notna()]
    unranked = d[d.theta_at_entry.isna()]
    print(f"\n  ranked (had a theta) : {len(ranked):5d}  mean R {ranked.r.mean():+.4f}"
          if len(ranked) else "\n  ranked: none")
    if len(unranked):
        print(f"  unranked (no theta)  : {len(unranked):5d}  mean R {unranked.r.mean():+.4f}")

    print("\n  invariants:")
    print(f"    max concurrent open  : {int(max_concurrent(d))} (cap {pf.max_slots})")
    print(f"    duplicate pair open  : {'none' if no_overlap(d) else 'FOUND — BUG'}")
    print(f"    all |z| >= entry     : {bool((d.z_at_entry.abs() >= 3.0 - 1e-9).all())}")
    print(f"    all holds <= cap     : {bool((d.hours_held <= pf.max_hold_hours + 1e-9).all())}")

    conc = pd.concat([d.ticker_a, d.ticker_b]).value_counts()
    print(f"\n  most-traded tickers  : "
          + ", ".join(f"{t}({n})" for t, n in conc.head(5).items()))
    print(f"\n[INFO] ledger written to {out_path}")
    print("=" * 100)


def max_concurrent(d: pd.DataFrame) -> int:
    """Peak simultaneous positions, from the open/close timestamps."""
    ev = ([(t, 1) for t in d.opened_at] + [(t, -1) for t in d.closed_at])
    ev.sort()
    cur = peak = 0
    for _, delta in ev:
        cur += delta
        peak = max(peak, cur)
    return peak


def no_overlap(d: pd.DataFrame) -> bool:
    """No pair ever held two positions at the same time."""
    for _, g in d.groupby(["ticker_a", "ticker_b"]):
        g = g.sort_values("opened_at")
        if (g.opened_at.values[1:] < g.closed_at.values[:-1]).any():
            return False
    return True


def _overshoot(v):
    """'none' books the actual bar-close spread; anything else is a multiple."""
    return None if str(v).strip().lower() in ("none", "off", "") else float(v)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=180)
    ap.add_argument("--stride", type=int, default=1)
    ap.add_argument("--slots", type=int, default=10)
    ap.add_argument("--equity", type=float, default=300.0)
    ap.add_argument("--entry", type=float, default=3.0)
    ap.add_argument("--stop", type=float, default=0.5)
    ap.add_argument("--hold", type=float, default=72.0)
    # Defaults come from book_state, NOT from a literal here. These were None
    # while the live book ran with MAX_PER_TICKER=1 and MAX_NOTIONAL=5000, so
    # every result the backtest produced described a more concentrated,
    # unbounded strategy than the one actually running. A backtest whose
    # defaults can drift from the live config is measuring the wrong thing.
    ap.add_argument("--max-per-ticker", type=int, default=cfg.MAX_PER_TICKER)
    ap.add_argument("--end-date", type=str, default=None,
                    help="anchor the window, e.g. 2026-06-13. Omit for the most "
                         "recent `days`, which is IN SAMPLE for this project.")
    ap.add_argument("--stop-fill-overshoot", default=str(cfg.MEASURED_STOP_OVERSHOOT),
                    help="how far past its level an adverse exit fills, as a "
                         "multiple of the stop distance. Default is the MEASURED "
                         f"live figure ({cfg.MEASURED_STOP_OVERSHOOT}). Pass 'none' "
                         "to book the bar-close spread instead, which is the "
                         "30-minute checking this system replaced (1.53x).")
    ap.add_argument("--max-notional", type=float, default=cfg.MAX_NOTIONAL,
                    help="hard dollar ceiling on gross notional per position; "
                         f"defaults to the live setting ({cfg.MAX_NOTIONAL:,.0f})")
    ap.add_argument("--grace-minutes", type=float, default=0.0,
                    help="the stop cannot fire this soon after ENTRY (the lever)")
    ap.add_argument("--debounce-minutes", type=float, default=0.0,
                    help="a breach must STILL hold this many minutes later to fire")
    ap.add_argument("--exit-check-minutes", type=int, default=None,
                    help="how often to check the stop and take-profit, in "
                         "minutes. Default is the bar length (30), which checks "
                         "only at bar closes -- what this engine has always done. "
                         "1 checks every minute, which is far closer to what the "
                         "live tick monitor does. Entries are unaffected either "
                         "way; only exits move.")
    ap.add_argument("--rank-by", type=str, default="theta",
                    choices=("theta", "neutrality", "both"),
                    help="which key orders candidates for the ten slots. "
                         "Only the ORDER changes; the candidate set and the "
                         "geometry are identical across modes.")
    ap.add_argument("--out", type=str, default=OUT)
    a = ap.parse_args()
    run(days=a.days, stride=a.stride, slots=a.slots, equity=a.equity,
        min_deviation_sigma=a.entry, stop_sigma=a.stop, max_hold_hours=a.hold,
        max_per_ticker=a.max_per_ticker, end_date=a.end_date,
        stop_fill_overshoot=_overshoot(a.stop_fill_overshoot),
        max_notional=a.max_notional,
        rank_by=a.rank_by, exit_check_minutes=a.exit_check_minutes,
        debounce_minutes=a.debounce_minutes, grace_minutes=a.grace_minutes,
        out_path=a.out)
