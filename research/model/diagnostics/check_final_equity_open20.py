"""Task A close-out (2026-11-09): cross-checks the open20 numbers-generator report against the
open20 engine report.json -- same final_equity assert the generator already does internally
(per_run_report in s1_profit1_numbers_gen.py), re-run standalone here so there's a saved script+log
receipt for the 24/24-match claim sent to the checker.

    python -u research/model/diagnostics/check_final_equity_open20.py
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
LOG_DIR = os.path.join(ROOT, "research", "model", "logs", "s1")

engine = json.load(open(os.path.join(LOG_DIR, "s1_profit1_report_open20.json")))
numgen = json.load(open(os.path.join(LOG_DIR, "s1_profit1_numbers_report_open20.json")))

mismatches = 0
for key, r in numgen["runs"].items():
    eng_fe = engine["runs"][key]["final_equity"]
    gen_fe = r["final_equity"]
    ok = abs(eng_fe - gen_fe) < 1e-6
    if not ok:
        mismatches += 1
        print(f"MISMATCH {key}: engine={eng_fe} numgen={gen_fe}")
    print(f"{key}: engine_final_equity={eng_fe:.2f} numgen_final_equity={gen_fe:.2f} match={ok}")
print(f"\n{len(numgen['runs'])} runs checked, {mismatches} mismatches")
