"""HL-MODEL1 B1: mask-equality check for single-value-plus-NaN columns (planner ruling 2026-10-27).

    python -u research/model/check_crossed_mask_v1_pair.py > research/model/logs/check_crossed_mask_v1_pair.log

A column with one value on every finite row and NaN elsewhere is OUT (degenerate) only if its NaN mask
equals the NaN mask of ANOTHER IN column in the same file, and that other column itself stays IN (a match
against another single-value column does not count). research/model/degenerate_v1_pair.csv (the full
1,097-column scan) found exactly two columns of this shape: g8/a_crossed and g8/b_crossed (the other two
rows there, a_listing_src and net_max_abs_imb_5m_bin, have zero NaN or zero finite rows respectively, so
they need no mask check). This checks both against every other IN g8 column for the same leg.

Read-only, small (9 columns from one file); re-verifies the v1 hash first.
OUTPUT: printed evidence only (no CSV; the result folds into inputs_v1_pair.csv by hand).
"""
import csv
import os
import sys
import time

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research", "dataset"))
import master_manifest as MF  # noqa: E402

WORK = MF.WORK
PAIR_DIR = os.path.join(WORK, "pair")


def arrow_to_f64(arr):
    return pc.cast(arr, pa.float64()).to_numpy(zero_copy_only=False)


def main():
    t0 = time.time()
    gs = os.path.join(ROOT, "research", "dataset", "GIT_STATE.json")
    git_head, git_dirty = ("unavailable", "unavailable")
    if os.path.exists(gs):
        G = MF.json.load(open(gs))
        git_head, git_dirty = G.get("head", "unavailable"), len(G.get("porcelain", []))
    print(f"[CROSSMASK] sha256 {os.path.basename(__file__)}: {MF.sha(os.path.abspath(__file__))}", flush=True)
    print(f"[CROSSMASK] sha256 inputs_v1_pair.csv: {MF.sha(os.path.join(HERE, 'inputs_v1_pair.csv'))}", flush=True)
    print(f"[CROSSMASK] git_head {git_head} ({git_dirty} uncommitted paths); "
          f"start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC; pid {os.getpid()}", flush=True)

    rows = list(csv.DictReader(open(os.path.join(HERE, "inputs_v1_pair.csv"))))
    in_g8 = {r["column"] for r in rows if r["in_out"] == "IN" and r["file"] == "g8.parquet"}
    print(f"[CROSSMASK] {len(in_g8)} current IN columns in g8.parquet")

    man = MF.json.load(open(os.path.join(MF.VERS, "v1", "MANIFEST.json")))
    MF.verify("v1", ["pair/g8.parquet"], base=WORK)
    print(f"[CROSSMASK] pair/g8.parquet re-hashed against MANIFEST.json: match  [{time.time()-t0:.0f}s]")

    cands = [c for c in sorted(in_g8) if c not in ("a_crossed", "b_crossed")]
    tbl = pq.read_table(os.path.join(PAIR_DIR, "g8.parquet"), columns=["a_crossed", "b_crossed"] + cands)
    masks = {c: np.isnan(arrow_to_f64(tbl.column(c))) for c in tbl.column_names}
    n_finite = {c: int((~masks[c]).sum()) for c in tbl.column_names}

    for leg in ("a", "b"):
        mc = masks[f"{leg}_crossed"]
        print(f"[CROSSMASK] {leg}_crossed: n_finite {n_finite[f'{leg}_crossed']:,} of 6,697,756 "
              f"(NaN {int(mc.sum()):,})")
        matches = [c for c in cands if c.startswith(leg + "_") and np.array_equal(masks[c], mc)]
        if matches:
            for c in matches:
                print(f"   MATCH {c} (IN, stays IN): n_finite {n_finite[c]:,} -- identical NaN mask to {leg}_crossed")
        else:
            print(f"   no IN column in g8.parquet shares {leg}_crossed's NaN mask")
    print(f"[CROSSMASK] done  [{time.time()-t0:.0f}s]")


if __name__ == "__main__":
    main()
