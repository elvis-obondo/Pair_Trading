"""HL-BUILD2 diagnostic: where do block numbers repeat across days? (analysis only)

Stage 2 stopped on `duplicate block numbers across days`. Each day's npz holds
the blocks read from that day's own 24 hour files, and stage 1 found no
duplicate WITHIN any day. This lists every repeated block number, the days that
hold it, and whether the copies carry the same block_time, so the cause can be
named before any fix is proposed.
Usage: python build2_blockdup_check.py DAYDIR
"""
import glob, os, sys
import numpy as np, pandas as pd

src = sys.argv[1]
files = sorted(glob.glob(os.path.join(src, "*_blocks.npz")))
N, T, D = [], [], []
for f in files:
    z = np.load(f)
    if not len(z["number"]): continue
    d = int(os.path.basename(f)[:8])
    N.append(z["number"]); T.append(z["time_ns"]); D.append(np.full(len(z["number"]), d, np.int32))
n = np.concatenate(N); t = np.concatenate(T); d = np.concatenate(D)
o = np.argsort(n, kind="stable"); n, t, d = n[o], t[o], d[o]
dup = np.flatnonzero(np.diff(n) == 0)
print(f"[INFO] {len(files)} block files, {len(n):,} blocks, {len(dup):,} repeated adjacent pairs")
if len(dup):
    R = pd.DataFrame({"block": n[dup], "day_a": d[dup], "day_b": d[dup + 1],
                      "time_a": pd.to_datetime(t[dup], utc=True), "time_b": pd.to_datetime(t[dup + 1], utc=True)})
    R["same_time"] = R.time_a == R.time_b
    R["same_day"] = R.day_a == R.day_b
    print("same block_time on both copies:", int(R.same_time.sum()), "of", len(R))
    print("both copies in the same day file set:", int(R.same_day.sum()))
    print("\nby (day_a, day_b):")
    print(R.groupby(["day_a", "day_b"]).agg(n=("block", "size"), first=("block", "min"), last=("block", "max"),
                                             t_first=("time_a", "min"), t_last=("time_a", "max")).to_string())
    print("\nfirst 10:"); print(R.head(10).to_string(index=False))
    R.to_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "build2_blockdup.csv"), index=False)
# continuity of the deduplicated sequence, for context
u = np.unique(n); st = np.diff(u)
print(f"\nunique blocks {len(u):,}; gaps (step > 1): {int((st > 1).sum())}, missing blocks {int((st[st > 1] - 1).sum()):,}")
