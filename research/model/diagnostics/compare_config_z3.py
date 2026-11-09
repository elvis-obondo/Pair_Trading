"""Task C diff (2026-11-09): compares CONFIG in s1_profit1_report.json (max_open=10 baseline) against
s1_profit1_report_z3_open10.json and s1_profit1_report_z3_open20.json, and prints the keys that differ
for each. z3_open10 should differ from baseline ONLY in min_abs_z; z3_open20 should differ ONLY in
min_abs_z and max_open.

    python -u research/model/diagnostics/compare_config_z3.py
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
LOG_DIR = os.path.join(ROOT, "research", "model", "logs", "s1")

base = json.load(open(os.path.join(LOG_DIR, "s1_profit1_report.json")))["config"]


def compare(tag, expected_diff_keys):
    other = json.load(open(os.path.join(LOG_DIR, f"s1_profit1_report_{tag}.json")))["config"]
    all_keys = sorted(set(base) | set(other))
    diffs = [(k, base.get(k), other.get(k)) for k in all_keys if base.get(k) != other.get(k)]
    print(f"CONFIG keys that differ (baseline -> {tag}):")
    for k, a, b in diffs:
        print(f"  {k}: {a} -> {b}")
    only_expected = sorted(k for k, _, _ in diffs) == sorted(expected_diff_keys)
    print(f"ONLY {expected_diff_keys} differ: {only_expected}")
    return only_expected


ok10 = compare("z3_open10", ["min_abs_z"])
ok20 = compare("z3_open20", ["min_abs_z", "max_open"])
print(f"\nz3_open10 OK: {ok10}")
print(f"z3_open20 OK: {ok20}")
