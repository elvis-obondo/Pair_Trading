"""Per-ticker history coverage. Reports what is actually on disk, not what was asked for.

Many of the 212 whitelisted tokens did not exist two years ago, so a backfill
that "succeeds" still leaves a ragged panel. Cointegration needs both legs
present on the same bars, so the number that matters for pair research is not
the deepest ticker but how many tickers share a given start date.
"""
import glob
import os

import pandas as pd

files = sorted(glob.glob("user_data/data/okx/futures/*_USDT_USDT-30m-futures.feather"))
if not files:
    print("  no 30m futures files found")
    raise SystemExit(0)

rows = []
for f in files:
    try:
        df = pd.read_feather(f, columns=["date"])
    except Exception as e:                       # a truncated file is data loss, say so
        print(f"  UNREADABLE {os.path.basename(f)}: {e}")
        continue
    if not len(df):
        continue
    rows.append((os.path.basename(f).split("_")[0], len(df), df.date.min(), df.date.max()))

d = pd.DataFrame(rows, columns=["ticker", "bars", "start", "end"])
span = (d.end.max() - d.start.min()).days
print(f"  {len(d)} tickers | {d.bars.sum():,} bars | earliest {d.start.min().date()} "
      f"| latest {d.end.max().date()} | span {span} days")
print(f"  bars per ticker: median {d.bars.median():,.0f}  min {d.bars.min():,}  max {d.bars.max():,}")
print("  tickers with at least N days of history:")
for days in [90, 180, 365, 547, 730]:
    cutoff = d.end.max() - pd.Timedelta(days=days)
    n = (d.start <= cutoff).sum()
    print(f"    {days:>4}d ({days/365:.1f}y): {n:>4} of {len(d)}  "
          f"-> {n*(n-1)//2:,} pairs")
