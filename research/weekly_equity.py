"""Week-by-week account level from a backtest ledger.

WHY THE CAP MATTERS HERE

run_portfolio_backtest deliberately refuses to quote a compounded multiple,
because percentage-of-equity sizing with no liquidity ceiling grows notional
without bound -- the 700-day uncapped run ended at $1.5 quadrillion, which is
arithmetically correct and physically impossible once a position exceeds the
depth of the pair it trades.

So an equity curve is only worth reading from a ledger produced with
--max-notional. Without one this prints the number anyway and says loudly that
it is meaningless, rather than quietly formatting nonsense into a table.

Equity is re-summed from realized_pnl_net ordered by closed_at -- the same rule
load_portfolio uses on the live book, so the two are directly comparable.

Usage:
    python research/weekly_equity.py research/rank_experiment/d180_theta.csv
    python research/weekly_equity.py <ledger> --equity 300 --freq W
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse

import numpy as np
import pandas as pd


def weekly(path: str, equity: float = 300.0, freq: str = "W") -> pd.DataFrame:
    d = pd.read_csv(path, parse_dates=["opened_at", "closed_at"])
    d = d.sort_values("closed_at").reset_index(drop=True)
    d["equity"] = equity + d.realized_pnl_net.cumsum()

    g = d.set_index("closed_at").resample(freq)
    out = pd.DataFrame({
        "trades": g.size(),
        "pnl": g.realized_pnl_net.sum(),
        "mean_R": g.r.mean(),
        "win%": g.realized_pnl_net.apply(lambda s: (s > 0).mean() * 100 if len(s) else np.nan),
        "equity": g.equity.last(),
    })
    # Weeks with no closes carry the previous balance rather than a gap: the
    # account still existed, it just did not transact.
    out["equity"] = out.equity.ffill().fillna(equity)
    out["ret%"] = out.equity.pct_change().fillna(out.equity / equity - 1) * 100
    peak = out.equity.cummax()
    out["dd%"] = (out.equity / peak - 1) * 100
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("ledger")
    ap.add_argument("--equity", type=float, default=300.0)
    ap.add_argument("--freq", default="W", help="W weekly, ME monthly, D daily")
    a = ap.parse_args()

    d = pd.read_csv(a.ledger)
    capped = "notional_capped" in d.columns and bool(d.notional_capped.any())
    w = weekly(a.ledger, a.equity, a.freq)

    print(f"{a.ledger}  —  {len(d):,} trades")
    if not capped:
        print("\n  *** NO NOTIONAL CAP IN THIS LEDGER ***")
        print("  Sizing compounded without a liquidity ceiling, so the equity")
        print("  column below is arithmetic, not an account. Re-run the backtest")
        print("  with --max-notional 5000 before quoting any of it.\n")

    pd.set_option("display.width", 200)
    print(w.to_string(float_format=lambda x: f"{x:,.2f}"))

    fin = w.equity.iloc[-1]
    print(f"\n  start {a.equity:,.2f} -> end {fin:,.2f}   "
          f"({fin / a.equity:,.2f}x over {len(w)} periods)")
    print(f"  worst drawdown {w['dd%'].min():.1f}%   "
          f"best period {w['ret%'].max():+.1f}%   worst {w['ret%'].min():+.1f}%")
    up = (w["ret%"] > 0).sum()
    print(f"  {up}/{len(w)} periods up ({up / len(w) * 100:.0f}%)")


if __name__ == "__main__":
    main()
