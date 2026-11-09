"""Checker-requested manifest/guard before the max_open=20 run (task A, 2026-11-09): sha256 every
max_open=10 output -- research/model/logs/profit1/*.parquet (top level: trades/minute_equity/skips/
liquidations), research/model/logs/profit1/cleaned/**/*.parquet (the price/impact series
save_cleaned_series_local rewrites on every run -- shared/untagged by design, task A's run touches
these files too, so they must be proven byte-identical afterward, not just untouched), plus
s1_profit1_report.json and s1_profit1.log -- so a re-check after A can prove nothing under those names
was overwritten or changed. cleaned/manifest.json is expected to differ (it carries its own
generated_utc timestamp, rewritten every run even when the underlying data is identical) -- flagged
explicitly as EXPECTED_DIFF, not counted as a problem.

    python -u research/model/diagnostics/manifest_profit1_outputs.py write   # before A
    python -u research/model/diagnostics/manifest_profit1_outputs.py check   # after A
"""
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PROFIT_DIR = os.path.join(ROOT, "research", "model", "logs", "profit1")
CLEANED_DIR = os.path.join(PROFIT_DIR, "cleaned")
LOG_DIR = os.path.join(ROOT, "research", "model", "logs", "s1")
MANIFEST_PATH = os.path.join(ROOT, "research", "model", "diagnostics", "profit1_outputs_manifest.json")
EXPECTED_DIFF_SUFFIXES = ("cleaned/manifest.json",)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def file_list():
    files = sorted(f for f in os.listdir(PROFIT_DIR) if f.endswith(".parquet"))
    paths = [os.path.join(PROFIT_DIR, f) for f in files]
    for sub in ("price", "impact"):
        d = os.path.join(CLEANED_DIR, sub)
        if os.path.isdir(d):
            paths += [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.endswith(".parquet")]
    manifest_json = os.path.join(CLEANED_DIR, "manifest.json")
    if os.path.exists(manifest_json):
        paths.append(manifest_json)
    paths.append(os.path.join(LOG_DIR, "s1_profit1_report.json"))
    paths.append(os.path.join(LOG_DIR, "s1_profit1.log"))
    return paths


def write():
    paths = file_list()
    manifest = {os.path.relpath(p, ROOT): sha(p) for p in paths}
    json.dump(manifest, open(MANIFEST_PATH, "w"), indent=2)
    print(f"[MANIFEST] wrote {len(manifest)} entries to {MANIFEST_PATH}")


def check():
    manifest = json.load(open(MANIFEST_PATH))
    n_total = len(manifest)
    n_unchanged, n_expected_diff = 0, 0
    changed = []
    for rel, want in manifest.items():
        p = os.path.join(ROOT, rel)
        is_expected_diff = rel.endswith(EXPECTED_DIFF_SUFFIXES)
        if not os.path.exists(p):
            changed.append((rel, "MISSING"))
            continue
        got = sha(p)
        if got == want:
            n_unchanged += 1
        elif is_expected_diff:
            n_expected_diff += 1
            print(f"[MANIFEST] EXPECTED_DIFF (generated_utc only): {rel}")
        else:
            changed.append((rel, "CHANGED"))
    print(f"[MANIFEST] {n_unchanged}/{n_total} unchanged "
          f"({n_expected_diff} expected-diff, not counted as a problem)")
    if changed:
        print("[MANIFEST] problems:")
        for rel, why in changed:
            print(f"  {why}: {rel}")
    return n_unchanged + n_expected_diff == n_total


if __name__ == "__main__":
    if sys.argv[1] == "write":
        write()
    elif sys.argv[1] == "check":
        ok = check()
        sys.exit(0 if ok else 1)
    else:
        raise SystemExit("usage: manifest_profit1_outputs.py write|check")
