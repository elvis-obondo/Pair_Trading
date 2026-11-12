"""HL-VAULT1 launch preflight (planner's requirement, 2026-11-11, after round 2's missing coins.csv):
before ANY AWS launch, from a CLEAN extract of the exact payload tarball, list every file each step opens
and assert each exists. Read-only; spends nothing; reads no vault row.

    python research/model/vault_preflight.py PAYLOAD.tar.gz research/model/aws_vault_userdata.sh

Four checks, all printed, any failure -> exit 1:
  1. PAYLOAD vs USERDATA: the userdata's own sha256-print file list and its fold7_done.json requirement are
     all present in the extract; the tarball's sha256 equals the userdata's PAYLOAD_SHA256.
  2. S3 SOURCES: every s3:// source the userdata copies/syncs (payload, MANIFEST.json, CHANGELOG.md, pair/
     data) exists (aws s3 ls, read-only).
  3. IMPORT + PATH AUDIT: in a subprocess whose cwd/sys.path are ONLY the clean extract (python -I), import
     the modules the steps run (harness, master_manifest, s1_run, s1_vault_prevault_refit,
     build_cache_v1_pair as a module without running main) with an audit hook on open(); every path opened
     for reading that lies inside the extract must exist. Then the path constants the steps read at run
     time (harness.COINS_CSV, inputs_v1_pair.csv, fold7_done.json, OUT_DIR for writes) are resolved and
     checked.
  4. LITERAL PATHS: every string literal ending in .csv/.json/.parquet/.npy/.sh in the four step scripts
     is listed with one of: IN PAYLOAD / BUILT AT RUNTIME / OUTPUT / NOT FOUND -- NOT FOUND fails.
"""
import ast
import hashlib
import os
import re
import subprocess
import sys
import tarfile
import tempfile

# usage: vault_preflight.py PAYLOAD USERDATA [ENTRY_SCRIPT_BASENAME]  (default entry: s1_vault_prevault_refit.py)
ENTRY = sys.argv[3] if len(sys.argv) > 3 else "s1_vault_prevault_refit.py"
STEP_SCRIPTS = ("research/model/harness.py", "research/model/build_cache_v1_pair.py",
                "research/model/s1_run.py", "research/model/" + ENTRY)
# names that are produced at run time on the instance (or are outputs), not shipped: matched by basename
RUNTIME_OK = ("MANIFEST.json", "CHANGELOG.md", "GIT_STATE.json")
OUTPUT_PAT = re.compile(r"(fold\d_|s1_prevault_model|\.manifest\.json|_grid|_coefs|_done|_test_predictions|_cache|_val_permutation|_predictions)")
# data files the steps read from the v1 dataset, which the userdata syncs from S3 (checked against the listing)
S3_DATA = ("events.parquet", "labels.parquet")


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def main(payload, userdata):
    fails = []
    ud = open(userdata).read()
    want_sha = re.search(r'^PAYLOAD_SHA256="([0-9a-f]{64})"', ud, re.M).group(1)
    got_sha = sha256_file(payload)
    print(f"[PREFLIGHT 1] tarball sha256 {got_sha} userdata PAYLOAD_SHA256 {want_sha} -> "
          f"{'OK' if got_sha == want_sha else 'MISMATCH'}")
    if got_sha != want_sha:
        fails.append("payload sha != userdata PAYLOAD_SHA256")

    tmp = tempfile.mkdtemp(prefix="vault_preflight_")
    with tarfile.open(payload) as t:
        t.extractall(tmp, filter="data")
    print(f"[PREFLIGHT 1] clean extract: {tmp}")

    loop = re.search(r"for f in (.*?); do", ud, re.S).group(1)
    listed = [x for x in loop.replace("\\", " ").split() if "/" in x]
    needed = listed + (["research/model/logs/s1/fold7_done.json"] if ENTRY == "s1_vault_prevault_refit.py" else [])
    for f in needed:
        ok = os.path.isfile(os.path.join(tmp, f))
        print(f"[PREFLIGHT 1] {'OK     ' if ok else 'MISSING'} {f}")
        if not ok:
            fails.append(f"missing in extract: {f}")

    # 2. S3 sources named in the userdata
    srcs = set(re.findall(r"s3://pair-trading-hl-289869684922/[^\s\"'<)]+", ud))
    srcs = {s.replace("${PAYLOAD_SHA256}", want_sha) for s in srcs}
    for s in sorted(srcs):
        if "s1_vault/logs" in s or "s1_vault/score_logs" in s:
            continue  # write targets (log sync), not inputs
        r = subprocess.run(["aws", "s3", "ls", s, "--region", "ap-northeast-1"], capture_output=True, text=True)
        ok = r.returncode == 0 and r.stdout.strip() != ""
        print(f"[PREFLIGHT 2] {'OK     ' if ok else 'MISSING'} {s}")
        if not ok:
            fails.append(f"S3 source missing: {s}")

    # 3. import + path audit inside the clean extract
    probe = r'''
import sys, os, runpy
root = os.getcwd()
opened = []
def hook(ev, args):
    if ev == "open" and isinstance(args[0], (str, bytes)) and args[1] in (None, "r", "rb", "rt"):
        p = args[0] if isinstance(args[0], str) else args[0].decode()
        ap = os.path.abspath(p)
        if ap.startswith(root):
            opened.append(ap)
sys.addaudithook(hook)
sys.path[:0] = [os.path.join(root, "research", "model")]
import importlib, harness as H, master_manifest as MF, s1_run as S1R
V = importlib.import_module(os.environ["PREFLIGHT_ENTRY"])
import importlib.util
spec = importlib.util.spec_from_file_location("bc", os.path.join(root, "research/model/build_cache_v1_pair.py"))
bc = importlib.util.module_from_spec(spec); spec.loader.exec_module(bc)   # module level only; main() not called
consts = [H.COINS_CSV, os.path.join(H.HERE, "inputs_v1_pair.csv")] + [
    os.path.join(S1R.OUT_DIR, f) for f in getattr(V, "REQUIRED_FILES", ())]
for p in sorted(set(opened) | set(consts)):
    print("OPEN", p, os.path.exists(p))
print("OUTDIR", S1R.OUT_DIR, os.path.isdir(S1R.OUT_DIR))
'''
    r = subprocess.run([sys.executable, "-I", "-c", probe], cwd=tmp, capture_output=True, text=True,
                       env={**os.environ, "PREFLIGHT_ENTRY": ENTRY[:-3]})
    if r.returncode != 0:
        print(r.stdout, r.stderr)
        fails.append("import/audit subprocess crashed")
    for line in r.stdout.splitlines():
        if line.startswith("OPEN"):
            _, p, ex = line.split(" ", 2)
            p = p.replace(tmp, "<extract>")
            if p.endswith(".pyc") or "__pycache__" in p:
                continue
            print(f"[PREFLIGHT 3] {'OK     ' if ex == 'True' else 'MISSING'} {p}")
            if ex != "True":
                fails.append(f"audit: opened but missing: {p}")
        elif line.startswith("OUTDIR"):
            ok = line.endswith("True")
            print(f"[PREFLIGHT 3] {'OK     ' if ok else 'MISSING'} output dir: {line.split(' ')[1].replace(tmp, '<extract>')}")
            if not ok:
                fails.append("OUT_DIR missing in extract")

    # 4. string-literal file names in the step scripts
    in_payload = {os.path.basename(os.path.join(dp, f)) for dp, _, fs in os.walk(tmp) for f in fs}
    for rel in STEP_SCRIPTS:
        tree = ast.parse(open(os.path.join(tmp, rel)).read())
        lits = sorted({n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
                       and re.search(r"\.(csv|json|parquet|npy|sh)$", n.value) and "{" not in n.value
                       and " " not in n.value and len(n.value) < 120})
        for lit in lits:
            base = os.path.basename(lit)
            if base in in_payload:
                kind = "IN PAYLOAD"
            elif lit.startswith((".", "_")):
                kind = "BUILT AT RUNTIME / OUTPUT"   # a name suffix (e.g. ".npy", "_x.csv"), not a whole file
            elif base in S3_DATA:
                r2 = subprocess.run(["aws", "s3", "ls", "s3://pair-trading-hl-289869684922/master/versions/v1/pair/"
                                     + base, "--region", "ap-northeast-1"], capture_output=True, text=True)
                kind = "IN S3 v1 pair/ SYNC" if r2.returncode == 0 and r2.stdout.strip() else "NOT FOUND"
                if kind == "NOT FOUND":
                    fails.append(f"S3 v1 pair data missing: {base}")
                    continue
            elif base in RUNTIME_OK or OUTPUT_PAT.search(base):
                kind = "BUILT AT RUNTIME / OUTPUT"
            else:
                kind = "NOT FOUND"
                fails.append(f"literal not accounted for: {lit} in {rel}")
            print(f"[PREFLIGHT 4] {kind:26s} {lit}   ({rel})")

    print(f"[PREFLIGHT] {'PASSED' if not fails else 'FAILED'}: {len(fails)} problem(s)")
    for f in fails:
        print(f"[PREFLIGHT]   - {f}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
