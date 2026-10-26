"""Rebuild the equity curve from ticks and the ledger, for time already elapsed.

WHY THIS EXISTS

`equity_curve.csv` only starts the moment the monitor began writing it. But the
history to reconstruct it was already on disk: the ledger says which positions
were open when and on what geometry, and `monitor_ticks/` holds 1 Hz bid/ask for
both legs of every open position. Between them, mark-to-market equity at any past
second is computable exactly -- not estimated.

    MTM(t) = ACCOUNT_EQUITY
           + realized P&L of every close before t          (ledger)
           + unrealized of every position open at t         (ticks -> spread)

The arithmetic is Position.pnl, unchanged. This does not re-derive it.

THE WINDOW CLOSES

Tick retention is RETAIN_TICK_DAYS. Past that the raw prices are gone and this
can no longer reach back. That is precisely why the monitor records the curve
going forward rather than relying on being able to rebuild it later.

Rows this writes carry feed_state="backfill" so they are never mistaken for
something the monitor observed live.

Usage:
    python research/backfill_equity.py --step 10
    python research/backfill_equity.py --step 10 --out /tmp/curve.csv --dry-run
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
import glob
import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import book_state as cfg
from portfolio import Position
from stop_monitor import instrument_id


def load_ticks() -> pd.DataFrame:
    files = sorted(glob.glob(os.path.join(cfg.TICKS_DIR, "*", "*.parquet")))
    if not files:
        raise SystemExit(f"no tick files under {cfg.TICKS_DIR}")
    d = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    d["mid"] = np.where(
        d.bid.notna() & d.ask.notna() & (d.bid > 0) & (d.ask > 0),
        (d.bid + d.ask) / 2.0, d.last)
    return d[d.mid.notna() & (d.mid > 0)].sort_values("ts").reset_index(drop=True)


def mid_series(ticks: pd.DataFrame) -> dict:
    """{inst_id: (ts array, mid array)} for as-of lookup."""
    out = {}
    for inst, g in ticks.groupby("inst_id", sort=False):
        out[inst] = (g.ts.to_numpy(), g.mid.to_numpy())
    return out


def as_of(series: tuple, t: float, max_age: float) -> float | None:
    """Most recent mid at or before t, or None if the last one is too old.

    `max_age` is the same staleness rule the monitor applies live. Without it a
    backfilled curve would happily mark a position against a price from before
    an outage -- the exact stale-price mark this project refuses to make.
    """
    ts, mids = series
    i = int(np.searchsorted(ts, t, side="right")) - 1
    if i < 0 or (t - ts[i]) > max_age:
        return None
    return float(mids[i])


def build(step: float, max_age: float) -> pd.DataFrame:
    led = pd.read_csv(cfg.LEDGER_PATH)
    opens = led[led.event.eq("open")].set_index("trade_num")
    closes = led[led.event.eq("close")].set_index("trade_num")
    if not len(opens):
        raise SystemExit("  ledger has no open rows — nothing to reconstruct")

    ticks = load_ticks()
    series = mid_series(ticks)
    t1 = float(ticks.ts.max())
    # Start at the book's FIRST POSITION, not at the first recorded tick. The
    # tick store outlives a book reset by design (raw prices are regime
    # independent), so after a reset it reaches back hours before the new book
    # existed -- and padding that with a flat line asserts the account was open
    # and doing nothing, which is not what happened.
    if len(opens):
        first = pd.Timestamp(opens.time.min(), tz="UTC").timestamp()
        t0 = max(float(ticks.ts.min()), first)
    else:
        t0 = float(ticks.ts.min())

    # One Position per trade, so current_spread and pnl are the real ones.
    live = {}
    for tn, r in opens.iterrows():
        sig = {k: r[k] for k in
               ("entry_spread", "mu_at_entry", "sigma_at_entry", "z_at_entry",
                "beta_at_entry", "alpha_at_entry", "theta_at_entry",
                "take_profit_level")}
        szg = {k: r[k] for k in
               ("leg_a_notional", "leg_b_notional", "gross_notional", "margin")}
        live[tn] = (Position(tn, r.ticker_a, r.ticker_b, sig, szg,
                             pd.Timestamp(r.time).to_pydatetime(), cfg.STOP_SIGMA),
                    pd.Timestamp(r.time, tz="UTC").timestamp(),
                    (pd.Timestamp(closes.loc[tn].closed_at, tz="UTC").timestamp()
                     if tn in closes.index else math.inf),
                    (float(closes.loc[tn].realized_pnl_net)
                     if tn in closes.index else float("nan")))

    rows = []
    t = t0
    while t <= t1:
        realized = cfg.ACCOUNT_EQUITY
        unreal = 0.0
        open_n = blind_n = 0
        unmarked = False
        for tn, (pos, opened, closed, pnl) in live.items():
            if t >= closed:
                realized += pnl
                continue
            if t < opened:
                continue
            open_n += 1
            ma = as_of(series.get(instrument_id(pos.ticker_a), (np.array([]), np.array([]))), t, max_age)
            mb = as_of(series.get(instrument_id(pos.ticker_b), (np.array([]), np.array([]))), t, max_age)
            if ma is None or mb is None:
                # Blind. NaN for the whole book, exactly as record_equity does --
                # see its docstring for why a carried-forward value is worse.
                blind_n += 1
                unmarked = True
                continue
            unreal += pos.pnl(pos.current_spread(math.log(ma), math.log(mb)))[0]
        rows.append({
            "ts": datetime.fromtimestamp(t, tz=timezone.utc).isoformat(timespec="seconds"),
            "realized": round(realized, 6),
            "unrealized": "" if unmarked else round(unreal, 6),
            "total": "" if unmarked else round(realized + unreal, 6),
            "open_n": open_n, "blind_n": blind_n,
            "feed_state": "backfill",
        })
        t += step
    return pd.DataFrame(rows, columns=cfg.EQUITY_COLUMNS)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", type=float, default=10.0,
                    help="seconds between rows (default 10, the heartbeat rate)")
    ap.add_argument("--max-age", type=float, default=None,
                    help="staleness cap in seconds; default is the monitor's own")
    ap.add_argument("--out", default=None,
                    help="default: prepend to EQUITY_PATH, keeping live rows")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    max_age = a.max_age if a.max_age is not None else 30.0
    d = build(a.step, max_age)
    marked = d.unrealized.astype(str).ne("").sum()
    print(f"{len(d):,} rows  {d.ts.iloc[0]} -> {d.ts.iloc[-1]}")
    print(f"  marked {marked:,}  blind {len(d)-marked:,}")
    fin = pd.to_numeric(d.total, errors="coerce")
    print(f"  total equity {fin.min():.2f} .. {fin.max():.2f}, last {fin.dropna().iloc[-1]:.2f}")

    if a.dry_run:
        print("  dry run, nothing written")
        return

    out = a.out or cfg.EQUITY_PATH
    if a.out is None and os.path.exists(cfg.EQUITY_PATH) and os.path.getsize(cfg.EQUITY_PATH):
        # The live rows are authoritative wherever the two overlap: they were
        # observed, these were reconstructed. Keep backfill strictly before them.
        live_rows = pd.read_csv(cfg.EQUITY_PATH, dtype=str, keep_default_na=False)
        cut = live_rows.ts.min()
        d = d[d.ts < cut]
        d = pd.concat([d, live_rows], ignore_index=True)
        print(f"  live rows start {cut}; backfill truncated to {len(d)-len(live_rows):,} rows")
    d.to_csv(out, index=False)
    print(f"  -> {out}")


if __name__ == "__main__":
    main()
