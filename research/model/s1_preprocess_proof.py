"""HL-MODEL1 S1: proves s1_preprocess.drop_degenerate_numpy matches harness.drop_degenerate_for_fold
exactly, on a small synthetic frame (local, seconds -- not a VM job). Needed because
drop_degenerate_numpy is a column-wise reimplementation of the harness rule, not a call to the harness
function itself (s1_preprocess.py's docstring explains why: avoiding a second full-size pandas copy of a
fold's train slice). Covers every case the rule distinguishes: all-NaN, one distinct finite value
(degenerate), two distinct finite values (kept), and a normal varied column.

    python -u research/model/s1_preprocess_proof.py > research/model/logs/s1_preprocess_proof.log
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402
from s1_preprocess import drop_degenerate_numpy  # noqa: E402

SEED = 20261028
PASS = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    PASS.append(cond)
    print(f"[S1-PREPROCESS-PROOF] {name}: {status}" + (f" -- {detail}" if detail else ""), flush=True)
    return cond


def main():
    import master_manifest as MF
    print(f"[S1-PREPROCESS-PROOF] sha256 {os.path.basename(__file__)}: {MF.sha(os.path.abspath(__file__))}",
          flush=True)
    print(f"[S1-PREPROCESS-PROOF] sha256 s1_preprocess.py: {MF.sha(os.path.join(HERE, 's1_preprocess.py'))}",
          flush=True)
    print(f"[S1-PREPROCESS-PROOF] sha256 harness.py: {MF.sha(os.path.join(HERE, 'harness.py'))}", flush=True)

    rng = np.random.default_rng(SEED)
    n = 500
    cols = ["all_nan", "one_value", "one_value_plus_nan", "two_values", "varied", "varied_with_nan"]
    X = np.empty((n, len(cols)), dtype=np.float64)
    X[:, 0] = np.nan
    X[:, 1] = 7.0
    X[:, 2] = 7.0
    X[: n // 3, 2] = np.nan
    X[:, 3] = np.where(rng.random(n) < 0.5, 1.0, 2.0)
    X[:, 4] = rng.normal(size=n)
    X[:, 5] = rng.normal(size=n)
    X[: n // 5, 5] = np.nan

    kept_np, dropped_np = drop_degenerate_numpy(X, cols)

    df = pd.DataFrame(X, columns=cols)
    kept_df, dropped_df = H.drop_degenerate_for_fold(df, cols)

    check("same dropped set", set(dropped_np) == set(dropped_df),
          f"numpy={sorted(dropped_np)} harness={sorted(dropped_df)}")
    check("same kept set, same order", kept_np == kept_df, f"numpy={kept_np} harness={kept_df}")
    check("dropped is exactly {all_nan, one_value, one_value_plus_nan}",
          set(dropped_np) == {"all_nan", "one_value", "one_value_plus_nan"})
    check("kept is exactly {two_values, varied, varied_with_nan}",
          set(kept_np) == {"two_values", "varied", "varied_with_nan"})

    print(f"[S1-PREPROCESS-PROOF] all done: {sum(PASS)}/{len(PASS)} checks PASS", flush=True)
    if not all(PASS):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
