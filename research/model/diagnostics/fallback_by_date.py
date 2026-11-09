"""Checker's finding: slip_stats' fallback_median counts (14 total across q0.01_stopnone_feemaker=2,
q0.005_stopnone_feetaker=4, q0.005_stopnone_feemaker=8) don't match the 12 slippage_frac calls (6
fills x 2 legs) expected from the single known gap day, 2026-07-08. This script recomputes, from the
trade logs and the saved cleaned impact series (the SAME data the engine read), which individual
entry/exit leg lookups were direct vs fallback, by date and by run -- no rerun, no rule change.

    python -u research/model/logs/profit1/diagnostics/fallback_by_date.py
"""
import glob
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PROFIT_DIR = os.path.dirname(HERE)
IMPACT_DIR = os.path.join(PROFIT_DIR, "cleaned", "impact")

_impact_cache = {}


def load_impact(coin):
    if coin not in _impact_cache:
        p = os.path.join(IMPACT_DIR, f"{coin}.parquet")
        if not os.path.exists(p):
            _impact_cache[coin] = None
        else:
            df = pd.read_parquet(p)
            df["label"] = pd.to_datetime(df["label"], utc=True)
            _impact_cache[coin] = df.set_index("label")["impact_frac"]
    return _impact_cache[coin]


def is_direct(coin, fill_minute):
    s = load_impact(coin)
    if s is None:
        return False
    label = pd.Timestamp(fill_minute) - pd.Timedelta(minutes=1)
    return label in s.index and pd.notna(s.loc[label])


rows = []
for f in sorted(glob.glob(os.path.join(PROFIT_DIR, "trades_*.parquet"))):
    run = os.path.basename(f)[len("trades_"):-len(".parquet")]
    d = pd.read_parquet(f, columns=["ticker_a", "ticker_b", "t0", "exit_time"])
    for _, r in d.iterrows():
        for leg_coin in (r["ticker_a"], r["ticker_b"]):
            for kind, ts in (("entry", r["t0"]), ("exit", r["exit_time"])):
                direct = is_direct(leg_coin, ts)
                rows.append(dict(run=run, date=pd.Timestamp(ts).date(), kind=kind, coin=leg_coin,
                                  direct=direct))

tab = pd.DataFrame(rows)
fb = tab[~tab["direct"]]
print(f"total slippage lookups checked: {len(tab):,}")
print(f"total fallback lookups (recomputed): {len(fb):,}")

print("\n=== fallback lookups by date (all runs pooled) ===")
print(fb.groupby("date").size().to_string())

print("\n=== fallback lookups by run ===")
print(fb.groupby("run").size().to_string())

print("\n=== fallback lookups by run x date (only runs/dates with >0) ===")
print(fb.groupby(["run", "date"]).size().to_string())
