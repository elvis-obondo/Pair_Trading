"""HL-VAULT1 step 5 gate (checker, 2026-11-12): sha256 of every cleaned_vault/price and impact parquet.
    python research/model/diagnostics/manifest_cleaned_vault.py write   # after vault_open10
    python research/model/diagnostics/manifest_cleaned_vault.py check   # after vault_open20 (rebuilds the same series)
manifest.json carries a generated_utc that changes every run (the one expected difference). Any other change
means a transient corruption (like the flat-10x run's) and the run does not count."""
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
D = os.path.join(ROOT, "research", "model", "logs", "profit1", "cleaned_vault")
OUT = os.path.join(ROOT, "research", "model", "diagnostics", "cleaned_vault_manifest.json")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def files():
    out = []
    for sub in ("price", "impact"):
        d = os.path.join(D, sub)
        out += [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.endswith(".parquet")]
    return out


if sys.argv[1] == "write":
    m = {os.path.relpath(p, ROOT): sha(p) for p in files()}
    json.dump(m, open(OUT, "w"), indent=1)
    print(f"[CVMANIFEST] wrote {len(m)} entries to {OUT}")
else:
    m = json.load(open(OUT))
    now = {os.path.relpath(p, ROOT): sha(p) for p in files()}
    bad = [k for k in m if now.get(k) != m[k]]
    extra = [k for k in now if k not in m]
    print(f"[CVMANIFEST] {len(m) - len(bad)}/{len(m)} unchanged; changed/missing {len(bad)}; new files {len(extra)}")
    for k in bad[:20]:
        print("  CHANGED/MISSING:", k)
    sys.exit(1 if bad or extra else 0)
