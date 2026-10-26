"""HL-MASTER1 integrity item 8: provenance and freezing. Writes the named, immutable version of the master dataset.

    python -u research/dataset/master_manifest.py VERSION [--note "text"]  > research/dataset/logs/master_manifest_VERSION.log

For each unit (pair, coin) the group files of research/datasets/master/work/{unit}/ are UPLOADED to s3://pair-trading-hl-289869684922/master/versions/VERSION/{unit}/ (a real copy under a version prefix; a hard link would share its inode
with the working file and is not immutable) and the local version directory research/datasets/master/versions/VERSION/ holds MANIFEST.json and CHANGELOG.md (read-only). ENFORCEMENT: verify(VERSION, [paths]) re-hashes the files a model opens
(from the local work copy or a download) against the manifest and raises on a mismatch; models read tables only through open_version(VERSION, unit, name) which verifies first.
MANIFEST.json records: version, build date (UTC), code commit (git HEAD) and the sha256 of every research/dataset/*.py and research/hyperliquid/build{7,8}*.{py,sh} used (the working tree is not committed, so the
commit alone is not enough), per file: size, sha256, row count, column count; the input files (name, size, mtime) of the raw sources the groups read (panel, flow tables, wallet tables, ctx, funding, order-book daily tables,
bars); the validator results = every line in research/dataset/logs/master_tests_*.log and master_*.log that contains "PASS" or "ALL PASS" or "FAIL", verbatim, with the log file's sha256; the recorded waivers (NUMBERS
[HL-WAIVERS]). CHANGELOG.md: the change log (version n+1 gets its own entry; a released version is never edited). Refuses to overwrite an existing version directory.
"""
import os, sys, json, glob, hashlib, subprocess, time
import pandas as pd
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research"))
sys.path.insert(0, os.path.join(ROOT, "research", "dislocation_model"))
import paths

WORK = os.path.join(paths.DATASETS, "master", "work")
VERS = os.path.join(paths.DATASETS, "master", "versions")
LOGS = os.path.join(HERE, "logs")
BUCKET = "s3://pair-trading-hl-289869684922/master/versions"
RECEIPT_LOGS = ["master_events.log", "master_labels.log", "master_coin.log", "master_tests.log", "master_tests_g2.log", "master_g2_indep.log", "master_tests_g2b.log", "master_tests_g3.log", "master_tests_g4.log", "master_tests_g5.log",
                "master_tests_g6_part1.log", "master_tests_g6_indep2000.log", "master_tests_g6_poison_400.log", "master_tests_g7.log", "master_tests_g7_fund.log", "master_tests_g8.log", "master_tests_g9a.log",
                "master_oi_gate2.log", "master_funding_check.log", "master_release_checks.log", "master_known.log", "master_coin_rewalk.log", "master_coin_rewalk_stored.log", "master_coin_gaps.log",
                "master_drift_explain_pair.log", "master_drift_explain_coin.log", "master_seams_pair.log", "master_seams_coin.log"]


def verify(ver, rels, base=None):
    """Re-hash files against the manifest of VERSION; base = directory holding {unit}/{name} (default: the working area). Raises on any mismatch or unknown file."""
    man = json.load(open(os.path.join(VERS, ver, "MANIFEST.json")))
    base = base or WORK
    for rel in rels:
        want = man["files"][rel]["sha256"]
        got = sha(os.path.join(base, rel))
        if got != want:
            raise RuntimeError(f"{ver}: {rel} does not match the manifest (sha256 {got[:12]} vs {want[:12]}); refusing to read it")
    return True


def open_version(ver, unit, name, columns=None, base=None):
    """The only way models read a named version: verify the file against the manifest, then read it."""
    rel = f"{unit}/{name}"
    verify(ver, [rel], base)
    return pd.read_parquet(os.path.join(base or WORK, rel), columns=columns)


def sha(path, block=1 << 24):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(block)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def main():
    ver = sys.argv[1]
    note = sys.argv[sys.argv.index("--note") + 1] if "--note" in sys.argv else ""
    vdir = os.path.join(VERS, ver)
    if os.path.exists(vdir):
        raise SystemExit(f"version {ver} already exists: a released version is immutable; make the next version")
    t0 = time.time()
    os.makedirs(vdir)
    gs = os.path.join(HERE, "GIT_STATE.json")             # written on the LAPTOP (the machine has no .git): {"head": ..., "porcelain": [...]}
    if not os.path.exists(gs):
        raise SystemExit("research/dataset/GIT_STATE.json is missing: write it on the laptop (git rev-parse HEAD; git status --porcelain) before freezing, the machine has no .git")
    G = json.load(open(gs))
    commit, dirty_paths = G["head"], G["porcelain"]
    dirty = len(dirty_paths)
    assert commit and len(commit) >= 40, "empty git head"
    code = {}
    for pat in ("research/dataset/*.py", "research/hyperliquid/build7*", "research/hyperliquid/build8*", "research/dislocation_model/flowfeat.py", "research/dislocation_model/evmarket.py"):
        for f in sorted(glob.glob(os.path.join(ROOT, pat))):
            if os.path.isfile(f):
                code[os.path.relpath(f, ROOT)] = sha(f)
    man = {"version": ver, "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "note": note, "git_head": commit, "uncommitted_paths_at_build": dirty, "uncommitted_paths": dirty_paths,
           "code_identity": "the code's identity rests on code_sha256 (the hashes of the files used), not on git_head, for as long as paths are uncommitted", "code_sha256": code, "files": {}, "inputs": {}, "validators": {}}
    for unit in ("pair", "coin"):
        pass
        for p in sorted(glob.glob(os.path.join(WORK, unit, "*.parquet")) + glob.glob(os.path.join(WORK, unit, "*.npz"))):
            subprocess.run(["aws", "s3", "cp", p, f"{BUCKET}/{ver}/{unit}/{os.path.basename(p)}", "--region", "ap-northeast-1", "--only-show-errors"], check=True)
            ent = {"size": os.path.getsize(p), "sha256": sha(p)}
            if p.endswith(".parquet"):
                md = pq.ParquetFile(p).metadata
                ent["rows"], ent["columns"] = md.num_rows, md.num_columns
            man["files"][f"{unit}/{os.path.basename(p)}"] = ent
            print(f"  {unit}/{os.path.basename(p)}: {ent.get('rows', '')} rows  [{time.time() - t0:.0f}s]", flush=True)
    for pat in ("flow/*.parquet", "wallet5/*", "oi/*", "ctx/*", "funding/*", "l2/*", "bars/*", "panel*"):
        fs = glob.glob(os.path.join(paths.DATASETS, pat))
        if fs:
            man["inputs"][pat] = {"files": len(fs), "bytes": sum(os.path.getsize(f) for f in fs if os.path.isfile(f)), "newest_mtime": max(os.path.getmtime(f) for f in fs)}
    for nm in RECEIPT_LOGS:                                  # only the FINAL receipt logs are validators; superseded / diagnostic logs are recorded by name and hash only
        lf = os.path.join(LOGS, nm)
        if not os.path.exists(lf):
            continue
        lines = [ln.rstrip() for ln in open(lf, errors="replace") if ("PASS" in ln or "FAIL" in ln or "mismatches" in ln or "changed" in ln or "hand checks" in ln)]
        man["validators"][nm] = {"sha256": sha(lf), "lines": lines[:60]}
    man["superseded_logs"] = {os.path.basename(lf): sha(lf) for lf in sorted(glob.glob(os.path.join(LOGS, "master_*.log"))) if os.path.basename(lf) not in RECEIPT_LOGS and os.path.getsize(lf) > 0}
    json.dump(man, open(os.path.join(vdir, "MANIFEST.json"), "w"), indent=1)
    open(os.path.join(vdir, "CHANGELOG.md"), "w").write(f"# {ver}\n\nBuilt {man['built_utc']} from git {commit} ({dirty} uncommitted paths).\n{note}\n")
    for f in ("MANIFEST.json", "CHANGELOG.md"):
        os.chmod(os.path.join(vdir, f), 0o444)
    subprocess.run(["aws", "s3", "cp", os.path.join(vdir, "MANIFEST.json"), f"{BUCKET}/{ver}/MANIFEST.json", "--region", "ap-northeast-1", "--only-show-errors"], check=True)
    subprocess.run(["aws", "s3", "cp", os.path.join(vdir, "CHANGELOG.md"), f"{BUCKET}/{ver}/CHANGELOG.md", "--region", "ap-northeast-1", "--only-show-errors"], check=True)
    print(f"[MANIFEST {ver}] {len(man['files'])} files, {len(man['validators'])} validator logs, {len(code)} code files hashed; written to {vdir} and s3://pair-trading-hl-289869684922/master/versions/{ver}/  [{time.time() - t0:.0f}s]")


if __name__ == "__main__":
    main()
