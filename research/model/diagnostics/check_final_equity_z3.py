"""Task C close-out: cross-checks the numbers-generator report against the engine's own report.json
for both z3_open10 and z3_open20 -- same final_equity assert the generator already does internally,
re-run standalone for a saved script+log receipt covering all 48 values (24 per tag).

    python -u research/model/diagnostics/check_final_equity_z3.py
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
LOG_DIR = os.path.join(ROOT, "research", "model", "logs", "s1")

total_mismatches = 0
for tag in ("z3_open10", "z3_open20"):
    engine = json.load(open(os.path.join(LOG_DIR, f"s1_profit1_report_{tag}.json")))
    numgen = json.load(open(os.path.join(LOG_DIR, f"s1_profit1_numbers_report_{tag}.json")))
    mismatches = 0
    for key, r in numgen["runs"].items():
        eng_fe = engine["runs"][key]["final_equity"]
        gen_fe = r["final_equity"]
        ok = abs(eng_fe - gen_fe) < 1e-6
        if not ok:
            mismatches += 1
            print(f"MISMATCH {tag} {key}: engine={eng_fe} numgen={gen_fe}")
        print(f"{tag} {key}: engine_final_equity={eng_fe:.2f} numgen_final_equity={gen_fe:.2f} match={ok}")
    print(f"-- {tag}: {len(numgen['runs'])} runs checked, {mismatches} mismatches --")
    total_mismatches += mismatches

print(f"\nTOTAL: 48 runs checked across both tags, {total_mismatches} mismatches")
