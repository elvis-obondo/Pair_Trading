"""HL-MODEL1 B1: full scan for degenerate columns (planner ruling 2026-10-27, relayed by Research Partner).

    python -u research/model/scan_degenerate_v1_pair.py > research/model/logs/scan_degenerate_v1_pair.log

Constant-on-every-row or all-NaN-on-every-row columns, over the WHOLE pair unit, carry no information and
are dropped outright -- including the one column each duplicate-audit component kept as its representative.
(A column that is constant or all-NaN only inside SOME folds stays IN; that is the harness's job, per fold,
logged there, not this script's.)

This re-reads every CURRENT IN column of research/model/inputs_v1_pair.csv once (not the dup-audit's cached
stats, which were never written to disk) and checks, over the full 6,697,756 rows: n_finite == 0 (all-NaN) or
all finite values identical (constant). Re-verifies the v1 hash first. Cheap: no hashing, no correlation, a
single pass per column, same order of cost as the dup-audit's pass 1 without the sha256.

OUTPUT: research/model/degenerate_v1_pair.csv (file, column, kind [all_nan|constant], n_finite, value_if_constant).
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


def load_in_columns():
    rows = list(csv.DictReader(open(os.path.join(HERE, "inputs_v1_pair.csv"))))
    return [(r["file"], r["column"]) for r in rows if r["in_out"] == "IN"]


def main():
    t0 = time.time()
    gs = os.path.join(ROOT, "research", "dataset", "GIT_STATE.json")
    git_head, git_dirty = ("unavailable", "unavailable")
    if os.path.exists(gs):
        G = MF.json.load(open(gs))
        git_head, git_dirty = G.get("head", "unavailable"), len(G.get("porcelain", []))
    print(f"[DEGEN] sha256 {os.path.basename(__file__)}: {MF.sha(os.path.abspath(__file__))}", flush=True)
    print(f"[DEGEN] sha256 inputs_v1_pair.csv: {MF.sha(os.path.join(HERE, 'inputs_v1_pair.csv'))}", flush=True)
    print(f"[DEGEN] git_head {git_head} ({git_dirty} uncommitted paths); "
          f"start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC; pid {os.getpid()}", flush=True)

    cols = load_in_columns()
    print(f"[DEGEN] scanning {len(cols)} current IN columns (string columns checked for a single distinct "
          f"non-null value)  [{time.time()-t0:.0f}s]")

    man = MF.json.load(open(os.path.join(MF.VERS, "v1", "MANIFEST.json")))
    rels = sorted({f"pair/{f}" for f, _ in cols})
    MF.verify("v1", rels, base=WORK)
    print(f"[DEGEN] {len(rels)} v1 pair files re-hashed against MANIFEST.json: all match  [{time.time()-t0:.0f}s]")

    file_cols = {}
    for f, c in cols:
        file_cols.setdefault(f, []).append(c)

    degenerate = []
    done = 0
    for f, cs in file_cols.items():
        tbl = pq.read_table(os.path.join(PAIR_DIR, f), columns=cs)
        for c in cs:
            arr = tbl.column(c)
            n_finite = int(pc.count(arr, mode="only_valid").as_py())
            if n_finite == 0:
                degenerate.append((f, c, "all_nan", 0, ""))
            else:
                n_distinct = pc.count_distinct(arr.drop_null()).as_py()
                if n_distinct == 1:
                    val = arr.drop_null()[0].as_py()
                    degenerate.append((f, c, "constant", n_finite, val))
            done += 1
            if done % 200 == 0:
                print(f"   {done}/{len(cols)}  [{time.time()-t0:.0f}s]", flush=True)

    print(f"[DEGEN] {len(degenerate)} degenerate columns found of {len(cols)}  [{time.time()-t0:.0f}s]")
    for f, c, kind, n_finite, val in degenerate:
        print(f"   {kind.upper():9} {f}/{c}  n_finite={n_finite}  value={val!r}")

    with open(os.path.join(HERE, "degenerate_v1_pair.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["file", "column", "kind", "n_finite", "value_if_constant"])
        w.writerows(degenerate)
    print(f"[DEGEN] wrote {len(degenerate)} rows to degenerate_v1_pair.csv  [{time.time()-t0:.0f}s]")


if __name__ == "__main__":
    main()
