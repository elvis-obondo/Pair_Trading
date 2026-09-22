"""What separates a dislocation that reverts from one that does not.

WHAT A ROW IS

One DISLOCATION EPISODE: the first bar at which a pair crosses |z| >= 3, with
the geometry frozen there exactly as generate_entry_signal freezes it, and the
outcome of walking forward under generate_exit_signal's rules.

The unit matters. The backtest screen emits one row per (bar, pair) the pair
stays dislocated, so a single episode that lasts twenty bars appears twenty
times -- 917,856 screen rows over 35 days collapse to far fewer episodes. Any
per-row statistic over the screen is really a statistic over episode LENGTH,
weighted by how long each dislocation persisted, which is itself an outcome.

WHAT THIS CAN AND CANNOT CONCLUDE

Every dislocation is walked forward independently. There are no ten slots, no
theta ranking, no per-ticker cap and no cooldown, so this measures the
POPULATION of dislocations rather than the strategy. Removing slot contention
has twice made a change look good here that the engine then refused (grace,
cooldown). So: use this to rule a feature OUT, never to rule one IN. A feature
that does not separate outcomes here cannot separate them in the engine either,
and that is worth knowing cheaply.

WHY EXPECTED R AND NOT THE REVERSION RATE

At a 3-sigma entry and a 0.5-sigma stop, a full reversion to mu earns about
|z|/0.5 = 6R and a stop costs 1R. So a 14% reversion rate is already
break-even, and a feature that lifts the reversion rate by discarding the far
tail of |z| can raise the rate while lowering the expectation. That is the exact
signature every gate tested in e5f494e showed: win rate 15.7% -> 21.6%, money
lost. Every table here reports mean R alongside the rate, and the rate alone is
never the answer.

COST. One rolling pass per pair, the same call build_screen makes (~25s for
22,366 pairs), plus a forward walk per episode. theta is NOT fitted by default:
it costs ~1.4ms per episode and is available on the live scan history already.
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
import time

import numpy as np
import pandas as pd

from universe_panel import load_panel, usable_tickers, tradeable_pairs
from rolling_spread import rolling_spread_stats, min_bars_required

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(PROJECT_ROOT, "research", "dislocations.parquet")

# Attribution window: how far back to look when asking which leg moved. Six
# 30-minute bars is three hours -- long enough to contain the move that caused
# the dislocation, short enough not to average it away.
ATTRIB_BARS = 6


def episodes_for_pair(a: str, b: str, pa: np.ndarray, pb: np.ndarray,
                      first_eval: int, entry: float, stop_sigma: float,
                      max_hold_bars: int, bar_hours: float,
                      fine: tuple | None = None) -> list[dict]:
    """Every |z| >= entry crossing for one pair, with its forward outcome.

    The forward spread is reconstructed with alpha and beta FROZEN at the
    crossing bar, which is what an open position actually holds -- refitting
    mid-trade would move the baseline the P&L is measured against.

    `fine`, when given, is (fa, fb, pos) -- 1-minute log prices for the two legs
    and, for each 30-minute bar, the index of the first minute after that bar
    closes. The exit gates are then checked every minute instead of every
    thirty, which is the whole question: a spread that crosses the stop intrabar
    and recovers is NEVER stopped at bar close, so bar-close checking converts
    intrabar stop-outs into take-profits. Measured at 32% of the backtest's
    winners. Nothing about the signal moves -- beta, alpha, mu and sigma stay
    30-minute rolling statistics, because the entry threshold and the stop
    distance are defined in those terms. Only "has the frozen level been
    crossed yet" moves to a finer grid.
    """
    r = rolling_spread_stats(pa, pb, bar_hours)
    z, spread, mu, sigma = r.z, r.spread, r.mu, r.sigma
    n = len(z)

    ok = np.isfinite(z)
    hot = ok & (np.abs(z) >= entry)
    if not hot[first_eval:].any():
        return []
    # An episode STARTS where the pair is dislocated and was not on the previous
    # bar. A NaN z counts as not dislocated, so a gap in the data opens a new
    # episode rather than extending one across it.
    prev = np.concatenate(([False], hot[:-1]))
    starts = np.flatnonzero(hot & ~prev)
    starts = starts[starts >= first_eval]
    if not len(starts):
        return []

    out = []
    for si, i in enumerate(starts):
        es, m, sg = spread[i], mu[i], sigma[i]
        if not (np.isfinite(es) and np.isfinite(m) and np.isfinite(sg)) or sg <= 0:
            continue
        beta, alpha = r.beta[i], r.alpha[i]
        # direction: +1 means the spread must FALL to revert (entered above mu)
        above = es > m
        stop_distance = stop_sigma * sg
        stop_level = es + stop_distance if above else es - stop_distance
        tp_level = m                      # take_profit_pct = 1.0, full reversion

        hi = min(i + max_hold_bars, n - 1)
        if hi <= i:
            continue
        if fine is None:
            fwd = pa[i + 1:hi + 1] - alpha - beta * pb[i + 1:hi + 1]
            bars_per_step = 1.0
        else:
            fa, fb, pos = fine
            p0, p1 = pos[i], pos[hi]
            if p0 < 0 or p1 <= p0:
                continue
            fwd = fa[p0:p1] - alpha - beta * fb[p0:p1]
            # A step is now a minute, but bars_held stays in 30-minute bars so
            # the coarse and fine arms are read on the same axis.
            bars_per_step = 1.0 / (bar_hours * 60.0)
        good = np.isfinite(fwd)
        if not good.any():
            continue

        # Gate order is generate_exit_signal's: time stop, adverse, take profit.
        # A bar that both stops and takes profit books the ADVERSE outcome,
        # because the stop is checked first -- and at 30m resolution that
        # ambiguity is real, which is what the intrabar work measured.
        if above:
            hit_stop = good & (fwd >= stop_level)
            hit_tp = good & (fwd <= tp_level)
        else:
            hit_stop = good & (fwd <= stop_level)
            hit_tp = good & (fwd >= tp_level)

        js = np.flatnonzero(hit_stop)
        jt = np.flatnonzero(hit_tp)
        j_stop = js[0] if len(js) else np.inf
        j_tp = jt[0] if len(jt) else np.inf
        if j_stop == np.inf and j_tp == np.inf:
            reason, jj = "time_stop", len(fwd) - 1
        elif j_stop <= j_tp:
            reason, jj = "adverse_move", int(j_stop)
        else:
            reason, jj = "take_profit", int(j_tp)

        # R, in units of the stop distance actually risked. A take profit banks
        # the whole entry-to-mu move; a time stop banks wherever it ended.
        if good[jj]:
            exit_spread = fwd[jj]
        else:
            # a minute the instrument did not trade. Book the last price that
            # existed rather than a forward-filled one nobody traded at.
            seen_ok = np.flatnonzero(good[:jj + 1])
            exit_spread = fwd[seen_ok[-1]] if len(seen_ok) else es
        travelled = (es - exit_spread) if above else (exit_spread - es)
        r_mult = travelled / stop_distance

        # Excursions over the SAME window the trade was alive for, so they
        # describe the path taken rather than the whole 72 hours.
        seen = fwd[:jj + 1][good[:jj + 1]]
        if len(seen):
            mv = (es - seen) if above else (seen - es)
            max_fav, max_adv = float(mv.max()), float(-mv.min())
        else:
            max_fav = max_adv = 0.0

        # Which leg moved. The spread change over the attribution window splits
        # into a leg-A part and a beta-scaled leg-B part; the share tells you
        # whether this is a pair dislocating or one coin running on its own.
        lo = max(i - ATTRIB_BARS, 0)
        da, db = pa[i] - pa[lo], beta * (pb[i] - pb[lo])
        denom = abs(da) + abs(db)
        leg_a_share = float(abs(da) / denom) if denom > 0 else np.nan

        # How long the dislocation lasted, and how far it went, regardless of
        # when the trade closed -- the episode is a property of the market.
        end = i
        while end + 1 < n and hot[end + 1]:
            end += 1
        run = end - i + 1
        zseg = z[i:end + 1]

        out.append(dict(
            ticker_a=a, ticker_b=b, bar=int(i),
            z=float(z[i]), absz=float(abs(z[i])),
            entry_spread=float(es), mu=float(m), sigma=float(sg),
            beta=float(beta), alpha=float(alpha), r2=float(r.r2[i]),
            neutrality=float(abs(1.0 - beta) / (1.0 + abs(beta))),
            above_mu=bool(above), leg_a_share=leg_a_share,
            run_bars=int(run), max_absz_in_run=float(np.nanmax(np.abs(zseg))),
            episode_num=int(si),
            exit_reason=reason, bars_held=(jj + 1) * bars_per_step,
            r=float(r_mult),
            max_fav_sigma=max_fav / sg, max_adv_sigma=max_adv / sg,
        ))
    return out


def add_breadth(d: pd.DataFrame) -> pd.DataFrame:
    """How many dislocated pairs each leg sits in, at the bar it dislocated.

    WHY IT IS WORTH A COLUMN

    With 212 tickers each one has 211 possible partners, so one coin moving on
    its own dislocates up to 211 pairs at once. Breadth separates "this pair
    diverged" from "this coin ran and the pair is along for the ride". The
    median dislocation's busier leg sits in ~50 other dislocated pairs, which
    says most of them are the second thing.

    Counted over EPISODE STARTS in this frame, not over every dislocated bar.
    The two differ -- a pair that stays dislocated for twenty bars contributes
    one episode and twenty bar-rows -- and the episode count is the right one
    here because it asks how many pairs newly dislocated alongside this one.
    """
    z = d[["bar", "ticker_a", "ticker_b"]].copy()
    for c in ("ticker_a", "ticker_b"):
        z[c] = z[c].astype(str)
    long = pd.concat([z[["bar", "ticker_a"]].rename(columns={"ticker_a": "t"}),
                      z[["bar", "ticker_b"]].rename(columns={"ticker_b": "t"})])
    br = long.groupby(["bar", "t"]).size().rename("n").reset_index()
    tot = z.groupby("bar").size().rename("n_dislocated").reset_index()

    d = d.copy()
    for c in ("ticker_a", "ticker_b"):
        d[c] = d[c].astype(str)
    d = d.merge(br.rename(columns={"t": "ticker_a", "n": "breadth_a"}),
                on=["bar", "ticker_a"], how="left")
    d = d.merge(br.rename(columns={"t": "ticker_b", "n": "breadth_b"}),
                on=["bar", "ticker_b"], how="left")
    d = d.merge(tot, on="bar", how="left")
    d["breadth_a"] = d.breadth_a.fillna(1)
    d["breadth_b"] = d.breadth_b.fillna(1)
    d["breadth_max"] = d[["breadth_a", "breadth_b"]].max(axis=1)
    d["breadth_min"] = d[["breadth_a", "breadth_b"]].min(axis=1)
    return d


def build(days=35, end_date=None, entry=3.0, stop_sigma=0.5,
          max_hold_hours=72.0, bar_hours=0.5, out_path=OUT,
          limit_pairs=None, exit_check_minutes=None) -> pd.DataFrame:
    need = min_bars_required(bar_hours)
    bars_per_day = int(round(24 / bar_hours))
    full = load_panel()
    if end_date is not None:
        full = full.loc[:pd.Timestamp(end_date)]
    panel = full.tail(need + days * bars_per_day)

    tickers = usable_tickers(panel, bar_hours)
    # A single partially-formed trailing bar cuts the universe from 212 to 17
    # and the run carries on reporting numbers. Refuse instead.
    if len(tickers) < 0.5 * panel.shape[1]:
        raise SystemExit(
            f"[FAIL] only {len(tickers)} of {panel.shape[1]} tickers have a complete "
            f"history. The last bar ({panel.index[-1]}) is probably still forming. "
            f"Re-run with --end-date '{panel.index[-2]}'")
    pairs = tradeable_pairs(tickers)
    if limit_pairs:
        pairs = pairs[:limit_pairs]
    print(f"[INFO] {len(tickers)} tickers, {len(pairs):,} pairs, "
          f"{panel.index[need]} -> {panel.index[-1]}")
    print(f"[INFO] entry {entry} sigma | stop {stop_sigma} | hold {max_hold_hours}h")

    arrays = {t: panel[t].to_numpy(dtype=float) for t in tickers}
    max_hold_bars = int(round(max_hold_hours / bar_hours))

    # Fine-resolution exit checking. The whole 1m panel is held in memory once
    # (212 tickers x ~50k minutes is ~85MB) rather than re-read per pair, and
    # `pos` maps each 30-minute bar to the first minute AFTER it closes, so a
    # forward walk is a slice rather than a search.
    fine_arrays = pos = None
    if exit_check_minutes is not None:
        import intrabar
        print(f"[INFO] loading {exit_check_minutes}m prices...")
        f = intrabar.load_panel(tickers, start=panel.index[need],
                               end=panel.index[-1],
                               timeframe=f"{exit_check_minutes}m")
        if panel.index.tz is None and f.index.tz is not None:
            f.index = f.index.tz_convert("UTC").tz_localize(None)
        f.index = f.index.as_unit(panel.index.unit)
        missing = [t for t in tickers if t not in f.columns]
        if missing:
            # Checking only SOME pairs finely would make the comparison
            # meaningless in a way nothing downstream could detect.
            raise SystemExit(
                f"[FAIL] {len(missing)} of {len(tickers)} tickers have no "
                f"{exit_check_minutes}m data ({', '.join(missing[:6])}...).")
        fine_arrays = {t: f[t].to_numpy(dtype=float) for t in tickers}
        # ALIGNMENT, and it has bitten this repo before (ac3ac48, "the 29-minute
        # misalignment that invalidated the earlier surface"). Bars are labelled
        # by OPEN time, so the 30-minute bar labelled 03:00 closes at the same
        # instant as the 1-minute bar labelled 03:29 -- verified by exact float
        # equality. A position entered on bar i therefore begins its life at the
        # 1-minute bar labelled i + 30min, NOT i + 1min. Starting a minute after
        # the LABEL walks the 29 minutes inside the entry bar, checking exits
        # against prices from before the position existed, which can take profit
        # or stop out before entry. The invariant that catches it: a 30-minute
        # stop-out must still be a stop-out at 1 minute, because finer checking
        # can only ADD breaches.
        step = pd.Timedelta(hours=bar_hours)
        pos = np.searchsorted(f.index.to_numpy(),
                              (panel.index + step).to_numpy(), side="left")
        print(f"[INFO] {len(f):,} fine bars x {len(f.columns)} tickers "
              f"({f.index[0]} -> {f.index[-1]})\n")
        del f

    rows, t0 = [], time.time()
    for k, (a, b) in enumerate(pairs, 1):
        fine = ((fine_arrays[a], fine_arrays[b], pos)
                if fine_arrays is not None else None)
        rows.extend(episodes_for_pair(a, b, arrays[a], arrays[b], need, entry,
                                      stop_sigma, max_hold_bars, bar_hours,
                                      fine=fine))
        if k % 4000 == 0:
            el = time.time() - t0
            print(f"  {k:,}/{len(pairs):,} pairs  {len(rows):,} episodes  "
                  f"{el:.0f}s eta {el/k*(len(pairs)-k):.0f}s", flush=True)

    d = pd.DataFrame(rows)
    d["date"] = panel.index[d.bar.to_numpy()]
    d = add_breadth(d)
    d.to_parquet(out_path)
    print(f"\n[INFO] {len(d):,} episodes in {time.time()-t0:.0f}s -> {out_path}")
    return d


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=35)
    ap.add_argument("--end-date", type=str, default=None,
                    help="REQUIRED in practice: omitting it lets a partially "
                         "formed trailing bar gut the universe")
    ap.add_argument("--entry", type=float, default=3.0)
    ap.add_argument("--stop", type=float, default=0.5)
    ap.add_argument("--hold", type=float, default=72.0)
    ap.add_argument("--limit-pairs", type=int, default=None)
    ap.add_argument("--exit-check-minutes", type=int, default=None,
                    help="check the stop and take profit every N minutes "
                         "instead of only at 30-minute bar closes. 1 is the "
                         "honest comparison: bar-close checking cannot see a "
                         "spread that crosses the stop intrabar and recovers, "
                         "and converts those into take-profits.")
    ap.add_argument("--out", type=str, default=OUT)
    a = ap.parse_args()
    build(days=a.days, end_date=a.end_date, entry=a.entry, stop_sigma=a.stop,
          max_hold_hours=a.hold, out_path=a.out, limit_pairs=a.limit_pairs,
          exit_check_minutes=a.exit_check_minutes)
