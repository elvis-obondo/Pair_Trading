"""HL-FLOW1 Part 1, the split, from the dislocation meta's `day` column ONLY.

Run before any target or model is touched. CUT = 2026-05-25 is the 70/30 day split
mkdisloc printed (41,941 fit / 18,063 held out). Validation = the last 20% of the
fit days (harness.Split). HO1 / HO2 = the first / second half of the held-out
DAYS by dislocation count: HO1 is every held-out day up to and including the day
on which the running count first reaches half the held-out total; HO2 is the rest.
The printed boundary is the first HO2 day and goes into envelope.HO_BOUNDARY.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
import harness, paths

meta = pd.read_parquet(paths.META, columns=["day"])
day = meta.day.to_numpy()
fit = day < harness.CUT
fd = np.sort(np.unique(day[fit]))
vcut = fd[int(harness.VAL_FRAC * len(fd))]
te_days, cnt = np.unique(day[~fit], return_counts=True)
cum = np.cumsum(cnt)
k = int(np.searchsorted(cum, 0.5 * cum[-1], side="left"))
last_ho1 = te_days[k]
ho2_first = te_days[k + 1]
print(f"rows {len(day):,}; CUT {pd.Timestamp(harness.CUT).date()}: fit {int(fit.sum()):,} ({len(fd)} days), held out {int((~fit).sum()):,} ({len(te_days)} days)")
print(f"validation cut (last 20% of fit days) {pd.Timestamp(vcut).date()}: train {int((fit & (day < vcut)).sum()):,}, val {int((fit & (day >= vcut)).sum()):,}")
h1 = (~fit) & (day <= last_ho1)
print(f"HO1 = held-out days <= {pd.Timestamp(last_ho1).date()}: {int(h1.sum()):,} rows, {int((te_days <= last_ho1).sum())} days")
print(f"HO2 = days >= {pd.Timestamp(ho2_first).date()} (HO_BOUNDARY): {int(((~fit) & (day > last_ho1)).sum()):,} rows, {int((te_days > last_ho1).sum())} days")
