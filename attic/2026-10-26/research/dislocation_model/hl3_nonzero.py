"""HL-FLOW1 receipt for the direction check: how many rows actually carry each H1 feature.

Backstop and ADL shares are zero on almost every row (they happen in cascades), so a
correlation with the residual rests on the few nonzero rows. Counts per period, from
flowfeat.npz on the matched population. Report only.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import paths
from hl3_common import Pop

P = Pop()
Z = np.load(os.path.join(paths.DATASETS, "flowfeat.npz"), allow_pickle=False)
names = [str(x) for x in Z["names"]]
X = Z["X"][P.rows].astype(float)
per = {"train": P.tr, "val": P.va, "HO1": np.isin(np.arange(P.n), P.halves["HO1"]), "HO2": np.isin(np.arange(P.n), P.halves["HO2"])}
print(f"{'feature':<24}" + "".join(f"{k:>26}" for k in per))
for nm in ("h1_forced_share_60", "h1_backstop_share_60", "h1_adl_share_60", "h1_backstop_share_30", "h1_adl_share_30"):
    j = names.index(nm)
    print(f"{nm:<24}" + "".join(f"{f'{int((np.nan_to_num(X[m, j]) > 0).sum()):,} of {int(m.sum()):,} ({100 * (np.nan_to_num(X[m, j]) > 0).mean():.1f}%)':>26}" for m in per.values()))
