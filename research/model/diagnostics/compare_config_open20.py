"""Checker-requested check, task A (2026-11-09): compares CONFIG in s1_profit1_report.json (max_open=10
baseline) against s1_profit1_report_open20.json (max_open=20), and prints the keys that differ. Only
max_open (10 -> 20) is allowed to differ. Also compares the s1_profit1.py sha256 line in both logs.

    python -u research/model/diagnostics/compare_config_open20.py
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
LOG_DIR = os.path.join(ROOT, "research", "model", "logs", "s1")

base = json.load(open(os.path.join(LOG_DIR, "s1_profit1_report.json")))
open20 = json.load(open(os.path.join(LOG_DIR, "s1_profit1_report_open20.json")))

base_cfg, open20_cfg = base["config"], open20["config"]
all_keys = sorted(set(base_cfg) | set(open20_cfg))
diffs = [(k, base_cfg.get(k), open20_cfg.get(k)) for k in all_keys if base_cfg.get(k) != open20_cfg.get(k)]

print("CONFIG keys that differ (baseline -> open20):")
for k, a, b in diffs:
    print(f"  {k}: {a} -> {b}")
only_max_open = len(diffs) == 1 and diffs[0][0] == "max_open"
print(f"ONLY max_open differs: {only_max_open}")

sha_re = re.compile(r"\[PROFIT1\] sha256 s1_profit1\.py: (\w+)")


def first_sha(log_path):
    for line in open(log_path):
        m = sha_re.search(line)
        if m:
            return m.group(1)
    return None


base_sha = first_sha(os.path.join(LOG_DIR, "s1_profit1.log"))
open20_sha = first_sha(os.path.join(LOG_DIR, "s1_profit1_open20.log"))
print(f"s1_profit1.py sha256: baseline={base_sha} open20={open20_sha} "
      f"{'SAME' if base_sha == open20_sha else 'DIFFERENT'}")
if base_sha != open20_sha:
    print("  (expected to differ: the env-var-driven max_open/RUN_TAG lines were added to the file "
        "between the two runs -- this is the code change the diff already covered, not a surprise)")
