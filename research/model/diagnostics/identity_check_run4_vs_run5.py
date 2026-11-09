"""Checker-requested identity check: run5 (coverage-fix only) vs run4_ref (saved aside before the fix).
Prints whether every report.json field except the coverage figures is identical, and whether every
trades_*.parquet matches, row for row. Both runs use the same seed, so any other difference means
something besides the one-line coverage fix changed.

    python -u research/model/logs/profit1/diagnostics/identity_check_run4_vs_run5.py
"""
import json
import os
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PROFIT_DIR = os.path.dirname(HERE)
REF_DIR = os.path.join(PROFIT_DIR, "run4_ref")
LOG_DIR = os.path.join(os.path.dirname(PROFIT_DIR), "s1")

ref = json.load(open(os.path.join(REF_DIR, "report.json")))
new = json.load(open(os.path.join(LOG_DIR, "s1_profit1_report.json")))

print("=== report.json: everything except coverage_by_fold ===")
all_same = True
for key in sorted(set(ref.keys()) | set(new.keys())):
    if key == "coverage_by_fold":
        continue
    rv, nv = ref.get(key), new.get(key)
    same = rv == nv
    all_same &= same
    print(f"  {key}: {'SAME' if same else 'DIFFERENT'}")
print(f"ALL NON-COVERAGE FIELDS SAME: {all_same}")

print("\n=== coverage_by_fold: ref (bug) vs new (fixed) ===")
for fold in sorted(ref["coverage_by_fold"].keys(), key=int):
    r = ref["coverage_by_fold"][fold]
    n = new["coverage_by_fold"][fold]
    print(f"  fold {fold}: covered {r['covered']}->{n['covered']}, total {r['total']}->{n['total']}, "
          f"share {r['share']:.6f}->{n['share']:.6f}")

print("\n=== trades_*.parquet: row-for-row match ===")
all_trades_match = True
for f in sorted(os.listdir(REF_DIR)):
    if not f.startswith("trades_") or not f.endswith(".parquet"):
        continue
    ref_df = pd.read_parquet(os.path.join(REF_DIR, f))
    new_df = pd.read_parquet(os.path.join(PROFIT_DIR, f))
    match = ref_df.equals(new_df)
    all_trades_match &= match
    print(f"  {f}: {'MATCH' if match else 'MISMATCH'} (ref n={len(ref_df)}, new n={len(new_df)})")
print(f"ALL TRADES PARQUETS MATCH: {all_trades_match}")
