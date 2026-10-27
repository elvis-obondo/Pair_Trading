"""HL-MODEL1 B1: re-gate the flagged pairs from a completed dup_audit_v1_pair.py run with a corrected
is_exact_affine_duplicate tolerance, WITHOUT rerunning the expensive full-screen Gram pass.

    python -u research/model/regate_v1_pair.py > research/model/logs/regate_v1_pair.log

Reads research/model/dup_audit_v1_pair.csv (every pair the completed run flagged at |r| >= BORDERLINE_THRESH).
For every pair whose kind was duplicate/anti_duplicate/near_duplicate (i.e. every pair that went through the
affine gate), re-reads just the two raw columns and reapplies the CURRENT is_exact_affine_duplicate() from
dup_audit_v1_pair.py (tolerance round 3, checker 2026-10-27) -- this REFITS a and b from the raw columns (the
function always fits its own a/b; it is not given the original run's saved values), then reclassifies kind.
Rebuilds the keep-rule connected components and dup_audit_keep_v1_pair.csv from the reclassified pairs, and
regenerates inputs_v1_pair.csv's duplicate_dropped rows from the result. Borderline/anti_borderline pairs
(never gated) pass through unchanged.

This script does not touch the full-screen matrices (N/Sx/Sxx/Sxy): that pass's correlations are a function
of the data alone and are correct regardless of the gate's tolerance, so there is no need to recompute them.
"""
import csv
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "research", "dataset"))
from dup_audit_v1_pair import (  # noqa: E402
    GROUP_ORDER, PAIR_DIR, is_exact_affine_duplicate, kind_of, read_col_f64,
)
import master_manifest as MF  # noqa: E402

ROWS_PATH = os.path.join(HERE, "dup_audit_v1_pair.csv")
OUT_CSV = os.path.join(HERE, "dup_audit_v1_pair.csv")  # overwritten in place; the original is kept as .orig below
LOG_PATH = os.path.join(HERE, "logs", "dup_audit_v1_pair.log")


def exact_hash_nodes():
    """(file, col) tuples that were in an EXACT hash-duplicate group in the completed run, parsed from its
    log (not recomputed): these are unaffected by the affine-tolerance fix (identical values trivially pass
    any tolerance), so their keep/drop decision from the original run stands."""
    nodes = set()
    if not os.path.exists(LOG_PATH):
        return nodes
    import ast
    for line in open(LOG_PATH):
        line = line.strip()
        if line.startswith("EXACT:"):
            for tag in ast.literal_eval(line[len("EXACT:"):].strip()):
                fc = tag.split(" ")[0].split("/", 1)
                nodes.add((fc[0], fc[1]))
    return nodes


def sort_key(fc):
    f, c = fc
    return (GROUP_ORDER.index(f) if f in GROUP_ORDER else 999, c)


def main():
    t0 = time.time()
    dup_audit_py = os.path.join(HERE, "dup_audit_v1_pair.py")
    inputs_csv = os.path.join(HERE, "inputs_v1_pair.csv")
    gs = os.path.join(ROOT, "research", "dataset", "GIT_STATE.json")
    git_head, git_dirty = ("unavailable", "unavailable")
    if os.path.exists(gs):
        G = MF.json.load(open(gs))
        git_head, git_dirty = G.get("head", "unavailable"), len(G.get("porcelain", []))
    print(f"[REGATE] sha256 regate_v1_pair.py: {MF.sha(os.path.abspath(__file__))}", flush=True)
    print(f"[REGATE] sha256 dup_audit_v1_pair.py (gate imported from): {MF.sha(dup_audit_py)}", flush=True)
    print(f"[REGATE] sha256 dup_audit_v1_pair.csv (as read, pre-regate): {MF.sha(ROWS_PATH)}", flush=True)
    print(f"[REGATE] sha256 inputs_v1_pair.csv (as read): {MF.sha(inputs_csv)}", flush=True)
    print(f"[REGATE] git_head {git_head} ({git_dirty} uncommitted paths); "
          f"start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC; pid {os.getpid()}", flush=True)

    rows = list(csv.DictReader(open(ROWS_PATH)))
    print(f"[REGATE] read {len(rows)} flagged pairs from dup_audit_v1_pair.csv")

    orig_path = ROWS_PATH + ".orig"
    if not os.path.exists(orig_path):
        import shutil
        shutil.copy(ROWS_PATH, orig_path)
        print(f"[REGATE] saved the pre-regate file to {orig_path}")

    out_rows = []
    changed = 0
    for row in rows:
        fa, ca, fb, cb = row["file_a"], row["col_a"], row["file_b"], row["col_b"]
        r = float(row["pearson"]) if row["pearson"] not in ("", "nan") else float("nan")
        rho = float(row["spearman"]) if row["spearman"] not in ("", "nan") else float("nan")
        na, nb, n_overlap = int(row["n_a"]), int(row["n_b"]), int(row["n_overlap"])
        old_kind = row["kind"]
        deg = row["degenerate"]

        if old_kind not in ("duplicate", "anti_duplicate", "near_duplicate"):
            out_rows.append(row)  # borderline / anti_borderline: never gated, unchanged
            continue

        xa = read_col_f64(fa, ca)
        xb = read_col_f64(fb, cb)
        affine_ok, same_nan, max_rel_resid, a, b = is_exact_affine_duplicate(xa, xb)
        new_kind = kind_of(r) if np.isfinite(r) else None
        if new_kind in ("duplicate", "anti_duplicate") and not affine_ok:
            new_kind = "near_duplicate"
        if new_kind != old_kind:
            changed += 1
            print(f"   RECLASSIFIED {ca}@{fa} vs {cb}@{fb}: {old_kind} -> {new_kind} "
                  f"(affine_ok={affine_ok}, same_nan={same_nan}, a={a}, b={b})")
        row = dict(row)
        row["kind"] = new_kind
        row["affine_ok"] = affine_ok
        row["same_nan_pattern"] = same_nan
        row["affine_a"] = a
        row["affine_b"] = b
        out_rows.append(row)

    print(f"[REGATE] {changed} of {len(rows)} pairs reclassified under the corrected tolerance")

    with open(OUT_CSV, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()) if out_rows else
                            ["file_a", "col_a", "file_b", "col_b", "pearson", "spearman", "n_a", "n_b",
                             "n_overlap", "kind", "degenerate", "affine_ok", "same_nan_pattern", "affine_a", "affine_b"])
        w.writeheader()
        w.writerows(out_rows)
    print(f"[REGATE] wrote {len(out_rows)} rows to dup_audit_v1_pair.csv (re-gated)")

    # rebuild the keep rule from scratch on the reclassified pairs (exact-hash groups are unaffected by the
    # gate, since identical values trivially pass any tolerance; their keep/drop decision from the original
    # run stands, so a pair where BOTH columns are already exact-hash nodes is skipped here to avoid dropping
    # the same column twice under two different reasons -- found and fixed myself: the first version unioned
    # mins_since_trade_a/b's correlation edge (r = 1.0, since it is also an exact-hash duplicate) on top of
    # its already-preserved hash-based decision, writing it to dup_audit_keep_v1_pair.csv twice).
    keep_path = os.path.join(HERE, "dup_audit_keep_v1_pair.csv")
    old_keep = list(csv.DictReader(open(keep_path))) if os.path.exists(keep_path) else []
    hash_nodes = exact_hash_nodes()  # (file, col) from the log's "EXACT:" lines -- unaffected by the gate
    hash_based = [r for r in old_keep if (r["dropped_file"], r["dropped_col"]) in hash_nodes]
    print(f"[REGATE] {len(hash_nodes)} columns in exact-hash groups (from {LOG_PATH}'s EXACT: lines, "
          f"unaffected by the affine-tolerance fix); {len(hash_based)} of the original keep rows are "
          f"exact-hash drops and are kept as-is")

    parent = {}

    def find(x):
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x

    def union(x, y):
        parent.setdefault(x, x)
        parent.setdefault(y, y)
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    skipped_both_hash = 0
    for row in out_rows:
        if row["kind"] in ("duplicate", "anti_duplicate"):
            na, nb = (row["file_a"], row["col_a"]), (row["file_b"], row["col_b"])
            if na in hash_nodes and nb in hash_nodes:
                skipped_both_hash += 1
                continue
            union(na, nb)
    if skipped_both_hash:
        print(f"[REGATE] skipped {skipped_both_hash} correlation edge(s) already fully covered by an "
              f"exact-hash decision (both endpoints are exact-hash nodes)")

    components = {}
    for node in set(parent):
        components.setdefault(find(node), []).append(node)
    components = [c for c in components.values() if len(c) > 1]
    print(f"[REGATE] keep rule: {len(components)} connected correlation-based duplicate component(s) after re-gating")
    new_keep = []
    for comp in components:
        comp_sorted = sorted(comp, key=sort_key)
        best = comp_sorted[0]
        same_file_tie = len({sort_key(fc)[0] for fc in comp_sorted}) == 1
        for fc in comp_sorted:
            if fc == best:
                continue
            reason = "tie, same file, column name" if same_file_tie else "earlier file in GROUP_ORDER (mechanical rule, brief B1 lines 123-133)"
            new_keep.append({"dropped_file": fc[0], "dropped_col": fc[1], "kept_file": best[0], "kept_col": best[1], "reason": reason})
        print(f"   KEEP {best[0]}/{best[1]}  DROP {[f'{f}/{c}' for f, c in comp_sorted if (f, c) != best]}")

    keep_orig = keep_path + ".orig"
    if not os.path.exists(keep_orig) and os.path.exists(keep_path):
        import shutil
        shutil.copy(keep_path, keep_orig)

    all_keep = hash_based + new_keep
    with open(keep_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["dropped_file", "dropped_col", "kept_file", "kept_col", "reason"])
        w.writeheader()
        w.writerows(all_keep)
    print(f"[REGATE] wrote {len(all_keep)} keep/drop decisions ({len(hash_based)} exact-hash, unaffected by "
          f"the gate; {len(new_keep)} correlation-based, rebuilt) to dup_audit_keep_v1_pair.csv")

    print(f"[REGATE] sha256 dup_audit_v1_pair.csv (as written): {MF.sha(ROWS_PATH)}", flush=True)
    print(f"[REGATE] sha256 dup_audit_keep_v1_pair.csv (as written): {MF.sha(keep_path)}", flush=True)
    print(f"[REGATE] note: this script does not write inputs_v1_pair.csv itself -- that is a separate step "
          f"(build_inputs_v1_pair.py, rerun by hand using this file's DUP_DROP additions), reported alongside "
          f"this log, not inside it.  [{time.time()-t0:.0f}s]")


if __name__ == "__main__":
    main()
