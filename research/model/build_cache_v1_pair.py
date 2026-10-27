"""HL-MODEL1 B5 Step 2 (iii): build the cached IN-matrix once, on the revised 1,091-column list.

    python -u research/model/build_cache_v1_pair.py > research/model/logs/build_cache_v1_pair.log

Builds a float32 matrix of ALL 6,697,756 pair-unit events x every current IN column (full dataset, no
subsampling -- standing rule) by calling harness.load_features EXACTLY ONCE on event_ids =
np.arange(6_697_756, dtype=np.int64) (every row, in row-position order; event_id IS row position, so this
reads the whole dataset through the SAME code path B5 Step 2 (i) already proved, not a parallel
reimplementation). The result is written with np.save (a standard .npy file, readable later with
np.load(path, mmap_mode="r") for positional row/column indexing without loading the whole 29 GB into RAM).

Lives under research/datasets/ (the DATA directory, excluded from scripts/gcp_run.sh's sync in both
directions -- this file never touches the laptop, same as the rest of the master dataset).

MANIFEST (written alongside the .npy): this cache's own sha256, the v1 MANIFEST.json sha256 (via
harness._manifest_sha()), inputs_v1_pair.csv's sha256, coins.csv's sha256 (checker's round-1 finding: the
ticker codes depend on it, so a coins.csv change must also invalidate the cache, not just a v1 or
input-list change), harness.CACHE_FORMAT (bumped whenever the cast/encoding rules change independently of
those three), the exact column order, shape and dtype. harness._cache_info() checks all of these before
ever trusting the cache -- any mismatch makes it refuse the cache and fall back to the parquet path.

NaN is kept exactly as load_features returns it -- no fill, nothing inferred. The two ticker columns are
NOT re-factorised here: load_features (as of B5 Step 2 (i)) already writes the fixed sorted(coins.csv)
code for them, so this cache is simply what load_features produces, persisted.

EQUIVALENCE CHECK (the brief's own requirement: "must be byte-identical to load_features output for the
same rows, assert on fold 7 and fold 0"): harness.load_features_cached (the NEW, separate entry point that
reads from the cache -- NOT load_features itself, which stays the plain parquet path unchanged, so the two
can never be ambiguously conflated) is compared against an independent harness.load_features call (the
parquet path, proven in Step 2 (i)) on fold 7's and fold 0's train+val+test ids -- not a self-comparison
against the one big build call that wrote the cache. A broken variant (checker's round-1 finding: there
was none) corrupts one cell of a copy and shows the SAME shared comparison function catches it.

CHUNKED, not all-at-once (round 2, post-mortem of a real OOM kill -- see the comment at the equivalence
loop itself): the comparison runs CHUNK_SIZE rows at a time, never holding more than about 2 x CHUNK_SIZE
x 1,091 x 4 bytes of the two arrays at once, instead of fold 7's full 23.3 GB EACH (46.6 GB together) --
the first attempt at this script held both full arrays and was killed by the kernel's OOM killer (dmesg
confirmed, anon-rss 64.97 GB, past even that 46.6 GB estimate; the likely gap is that del X; gc.collect()
on the 29.2 GB build array was never actually confirmed freed, since the only check printed a VmHWM that
cannot drop once set -- fixed separately, but chunking removes the risk regardless of the exact cause).

BROKEN VARIANTS on _cache_info() run against a TEMPORARY CACHE_DIR (checker's round-1 finding: the first
version tampered the REAL manifest on disk -- a crash mid-window would leave the just-built cache marked
stale or tampered, forcing a 29 GB rebuild for no reason). The temp dir holds a copied, tampered manifest
and a symlink to the real .npy (never copies the 29 GB file); harness.CACHE_DIR points there only for the
duration of the check, restored in `finally` even on an exception.
"""
import os
import shutil
import sys
import tempfile
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402
from b5_profile import rss_gb, clear_peak_rss  # noqa: E402 -- checker-approved memory helpers, reused

ROOT = os.path.dirname(os.path.dirname(HERE))
CACHE_DIR = os.path.join(ROOT, "research", "datasets", "model_cache")
N_ROWS = 6_697_756
MIN_FREE_BYTES_MARGIN = 5 * 1024**3  # 5 GB headroom beyond the ~29.2 GB file itself


def load_in_cols():
    import csv
    rows = list(csv.DictReader(open(os.path.join(HERE, "inputs_v1_pair.csv"))))
    return [r["column"] for r in rows if r["in_out"] == "IN"]


PASS = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    PASS.append(cond)
    print(f"[B5-CACHE] {name}: {status}" + (f" -- {detail}" if detail else ""), flush=True)
    return cond


def arrays_match(X_a, X_b):
    """Shared by the real equivalence checks and their broken variant (checker's round-1 finding: PROOF
    had none)."""
    return X_a.dtype == X_b.dtype and np.array_equal(X_a, X_b, equal_nan=True)


def broken_variant_arrays_match():
    X = np.array([[1.0, 2.0], [3.0, np.nan]], dtype=np.float32)
    X_bad = X.copy()
    X_bad[1, 0] += 1.0
    check("BROKEN VARIANT -- arrays_match (shared by the real fold checks) catches one changed cell",
          not arrays_match(X, X_bad))


def broken_variants_cache_info(manifest_path, npy_path):
    """checker's round-1 finding: run against a TEMP CACHE_DIR (copied manifest, SYMLINKED .npy -- never
    copies the 29 GB file), so a crash mid-check can never leave the real, just-built cache marked stale
    or tampered."""
    import json
    real_man = json.load(open(manifest_path))
    tmp_dir = tempfile.mkdtemp(prefix="b5_cache_broken_variant_")
    real_cache_dir = H.CACHE_DIR
    try:
        # n_in must be derived the SAME way _cache_info() derives it (from the current inputs_v1_pair.csv,
        # not from the manifest's own "columns" length) -- found by this script's own local testing: a
        # mismatch here silently points _cache_info() at a filename it was never going to look for, and
        # every check below passes for the wrong reason (no cache found at all, not a validity check).
        in_cols = load_in_cols()
        n_in = len(in_cols)
        tmp_manifest = os.path.join(tmp_dir, f"ivq_pair_v1_{n_in}.manifest.json")
        tmp_npy = os.path.join(tmp_dir, f"ivq_pair_v1_{n_in}.npy")
        os.symlink(npy_path, tmp_npy)

        # (a) stale inputs sha -> invalid, not raising
        H.CACHE_DIR = tmp_dir
        H._CACHE_FILE_SHA = None
        stale = dict(real_man)
        stale["inputs_sha256"] = "0" * 64
        json.dump(stale, open(tmp_manifest, "w"))
        info = H._cache_info()
        check("BROKEN VARIANT (a) -- a stale inputs_sha256 makes _cache_info() report invalid (not raise)",
              info is False)

        # (b) tampered cache_sha256 -> raise
        tampered = dict(real_man)
        tampered["cache_sha256"] = "0" * 64
        json.dump(tampered, open(tmp_manifest, "w"))
        H._CACHE_FILE_SHA = None
        raised = False
        try:
            H._cache_info()
        except RuntimeError as e:
            raised = "tampered or corrupted" in str(e)
        check("BROKEN VARIANT (b) -- a tampered cache_sha256 makes _cache_info() RAISE (not silently trust it)",
              raised)
    finally:
        H.CACHE_DIR = real_cache_dir
        H._CACHE_FILE_SHA = None
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main():
    t0 = time.time()
    import master_manifest as MF
    print(f"[B5-CACHE] sha256 {os.path.basename(__file__)}: {MF.sha(os.path.abspath(__file__))}", flush=True)
    print(f"[B5-CACHE] sha256 harness.py: {MF.sha(os.path.join(HERE, 'harness.py'))}", flush=True)
    print(f"[B5-CACHE] sha256 b5_profile.py: {MF.sha(os.path.join(HERE, 'b5_profile.py'))}", flush=True)
    print(f"[B5-CACHE] sha256 master_manifest.py: {MF.sha(os.path.abspath(MF.__file__))}", flush=True)
    inputs_sha = MF.sha(os.path.join(HERE, "inputs_v1_pair.csv"))
    print(f"[B5-CACHE] sha256 inputs_v1_pair.csv: {inputs_sha} (must be 91cb311c74a2970144e9e2656faf71acce75c422dcf0c404512eb0560a2c0bcf)", flush=True)
    coins_sha = MF.sha(H.COINS_CSV)
    print(f"[B5-CACHE] sha256 coins.csv: {coins_sha}", flush=True)
    v1_manifest_sha = H._manifest_sha()
    print(f"[B5-CACHE] sha256 v1 MANIFEST.json: {v1_manifest_sha}", flush=True)
    gs = os.path.join(os.path.dirname(HERE), "dataset", "GIT_STATE.json")
    git_head, git_dirty = ("unavailable", "unavailable")
    if os.path.exists(gs):
        G = MF.json.load(open(gs))
        git_head, git_dirty = G.get("head", "unavailable"), len(G.get("porcelain", []))
    print(f"[B5-CACHE] git_head {git_head} ({git_dirty} uncommitted paths); "
          f"start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC; pid {os.getpid()}", flush=True)

    broken_variant_arrays_match()

    in_cols = load_in_cols()
    print(f"[B5-CACHE] {len(in_cols)} IN columns (expected 1,091)", flush=True)
    assert len(in_cols) == 1091, f"expected 1,091 IN columns on the revised list, got {len(in_cols)}"

    os.makedirs(CACHE_DIR, exist_ok=True)
    npy_path = os.path.join(CACHE_DIR, f"ivq_pair_v1_{len(in_cols)}.npy")
    manifest_path = os.path.join(CACHE_DIR, f"ivq_pair_v1_{len(in_cols)}.manifest.json")

    clear_peak_rss()
    rss_before, _ = rss_gb()
    event_ids = np.arange(N_ROWS, dtype=np.int64)
    t_load0 = time.time()
    X, cols = H.load_features(event_ids, in_cols)
    t_load = time.time() - t_load0
    _, hwm_load = rss_gb()
    print(f"[B5-CACHE] full load_features call: {N_ROWS:,} rows x {len(in_cols)} cols, {t_load:.1f}s, "
          f"X.nbytes={X.nbytes/1e9:.2f}GB, rss_before={rss_before:.2f}GB VmHWM={hwm_load:.2f}GB  "
          f"[{time.time()-t0:.0f}s]", flush=True)

    free_bytes = shutil.disk_usage(CACHE_DIR).free
    needed = X.nbytes + MIN_FREE_BYTES_MARGIN
    print(f"[B5-CACHE] disk free at {CACHE_DIR}: {free_bytes/1e9:.1f}GB; need {needed/1e9:.1f}GB "
          f"({X.nbytes/1e9:.1f}GB file + {MIN_FREE_BYTES_MARGIN/1e9:.0f}GB margin)", flush=True)
    assert free_bytes >= needed, f"not enough free disk at {CACHE_DIR}: {free_bytes/1e9:.1f}GB < {needed/1e9:.1f}GB needed"

    t_save0 = time.time()
    np.save(npy_path, X)
    t_save = time.time() - t_save0
    print(f"[B5-CACHE] saved {npy_path} in {t_save:.1f}s  [{time.time()-t0:.0f}s]", flush=True)

    del X
    import gc
    gc.collect()
    clear_peak_rss()  # reset so the NEXT reading is this instant's own current RSS, not the still-30.61GB
                       # high-water mark from the load above (an OOM post-mortem found this exact gap: the
                       # first version only ever printed VmHWM here, which cannot drop once set, so "should
                       # drop close to baseline" was asserted in a comment and never actually verified)
    rss_after_del, _ = rss_gb()
    print(f"[B5-CACHE] after del X + gc.collect: VmRSS (current, not a high-water mark) {rss_after_del:.2f}GB",
          flush=True)

    cache_sha = MF.sha(npy_path)
    import json
    manifest = {
        "cache_sha256": cache_sha,
        "v1_manifest_sha256": v1_manifest_sha,
        "inputs_sha256": inputs_sha,
        "coins_sha256": coins_sha,
        "cache_format": H.CACHE_FORMAT,
        "columns": cols,
        "n_rows": N_ROWS,
        "dtype": "float32",
        "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    json.dump(manifest, open(manifest_path, "w"), indent=1)
    print(f"[B5-CACHE] manifest {manifest_path}: cache_sha256={cache_sha}", flush=True)

    # EQUIVALENCE CHECK: load_features_cached (reads the cache just built) vs load_features (the plain
    # parquet path, unchanged, proven in Step 2 (i)) -- two distinct functions, never conflated.
    #
    # POST-MORTEM (this is the SECOND attempt at this section -- the first run was OOM-killed here):
    # holding X_cache and X_fresh for fold 7's full combined ids (23.3 GB EACH, ~46.6 GB together) was
    # supposed to fit under the VM's 62 GB with room to spare, matching Step 2 (i)'s own 48.5 GB peak on
    # the same fold. It didn't: dmesg on the VM showed a genuine kernel OOM kill (not a timeout -- exit
    # code 137), with anon-rss 64.97 GB at the moment of the kill, PAST the two-array estimate. The likely
    # cause (not fully pinned down, see the del/gc fix above): the full 29.2 GB build array's memory may
    # not have been confirmed freed before this section started -- the only line that checked it printed
    # VmHWM (a high-water mark that cannot drop once set), not current VmRSS, so "should drop close to
    # baseline" was never actually verified by a number. Rather than re-run the same 46.6 GB-at-once
    # comparison and hope the real cause is fixed, this section now compares in CHUNKS of CHUNK_SIZE rows:
    # never holds more than roughly 2 x CHUNK_SIZE x 1,091 x 4 bytes of these two arrays at once (about
    # 4.4 GB at the current CHUNK_SIZE), removing the risk with a large margin regardless of what exactly
    # caused the 18 GB overshoot.
    H._CACHE_FILE_SHA = None  # force a fresh file-hash check against the cache just written
    events = H.load_search_events()
    folds = H.build_folds(events)
    CHUNK_SIZE = 500_000
    for k in (7, 0):
        f = folds[k]
        ids = np.concatenate([f["train_ids"], f["val_ids"], f["test_ids"]])

        clear_peak_rss()
        rss_before_k, _ = rss_gb()
        n = len(ids)
        bad_ranges = []
        for start in range(0, n, CHUNK_SIZE):
            chunk_ids = ids[start:start + CHUNK_SIZE]
            X_c, cols_c = H.load_features_cached(chunk_ids, in_cols)
            X_f, cols_f = H.load_features(chunk_ids, in_cols)
            if not (cols_c == cols_f == in_cols and arrays_match(X_c, X_f)):
                bad_ranges.append((start, start + len(chunk_ids)))
            del X_c, X_f
            gc.collect()
        _, hwm_k = rss_gb()
        check(f"fold {k} equivalence -- load_features_cached vs load_features "
              f"(n={n:,}, {CHUNK_SIZE:,} rows/chunk, {(n + CHUNK_SIZE - 1)//CHUNK_SIZE} chunks)",
              len(bad_ranges) == 0, f"bad ranges: {bad_ranges}" if bad_ranges else "")
        print(f"[B5-CACHE] fold {k} memory: rss_before={rss_before_k:.2f}GB VmHWM_this_block={hwm_k:.2f}GB",
              flush=True)

        # load_fold_features_cached vs load_fold_features: the split (train/val/test boundaries) is pure
        # position arithmetic, already proven correct for the identical parquet-side split in Step 2 (i)
        # PROOF 3 -- what's left to check here is only that load_fold_features_cached's SHAPES match,
        # which is free (no large arrays). Full-content equivalence of load_features_cached itself is
        # exactly what the chunked check above already proves, on these same ids.
        Xt_c, Xv_c, Xs_c, _ = H.load_fold_features_cached(f, in_cols)
        shapes_cached = (Xt_c.shape, Xv_c.shape, Xs_c.shape)
        del Xt_c, Xv_c, Xs_c
        gc.collect()
        expected_shapes = (f["train_ids"].shape[0], len(in_cols)), (f["val_ids"].shape[0], len(in_cols)), \
            (f["test_ids"].shape[0], len(in_cols))
        check(f"fold {k} -- load_fold_features_cached shapes match the fold's train/val/test sizes",
              shapes_cached == expected_shapes, f"{shapes_cached} vs {expected_shapes}")

    broken_variants_cache_info(manifest_path, npy_path)

    print(f"[B5-CACHE] all done [{time.time()-t0:.0f}s]: {sum(PASS)}/{len(PASS)} checks PASS", flush=True)
    if not all(PASS):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
