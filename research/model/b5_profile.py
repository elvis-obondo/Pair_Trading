"""HL-MODEL1 B5 Step 1: measure first, no optimisation here.

    python -u research/model/b5_profile.py > research/model/logs/b5_profile.log

Profiles the CURRENT (unmodified) harness.py on fold 7 (the largest fold) and fold 0 (the smallest),
stage by stage, as the brief asks: manifest verification, the per-file row-order assert, the column
reads, the take/cast, train/val/test loading, hazard-row build, scoring. Nothing in harness.py is
changed or copied -- every number comes from calling H.load_features, H.build_hazard_rows, H.score_fold
and H.day_block_bootstrap exactly as they exist on disk today. The only instrumentation is monkeypatching
LIBRARY/module entry points harness.py calls by module-level name (MF.verify, pyarrow.parquet.read_table,
pyarrow.compute.cast) and two harness.py module FUNCTIONS it calls by bare name from within load_features
(check_inputs, _assert_positional_row_order) -- replacing a module attribute with a timing wrapper that
calls the original and returns its exact result, so load_features's own behaviour and return value are
unchanged; this is not an edit to the file, and the "no optimisation before Step 1 is reported" rule is
not touched by it. MF.verify, check_inputs and _assert_positional_row_order are patched for the whole
process (confirmed by reading harness.py: they are called ONLY from inside load_features, with a stable
signature everywhere). pq.read_table and pc.cast are NOT: pandas' own pd.read_parquet (used by
MF.open_version, which load_search_events calls once at startup, well before any profiled block) also
calls pq.read_table, but hands it an already-open file object instead of a path string. The first VM run
crashed exactly there (os.path.basename() on a BufferedReader) -- fixed by patching pq.read_table/pc.cast
ONLY for the duration of each H.load_features call (load_features_patched), restoring the originals
immediately after, so they can never see any pyarrow activity outside the thing Step 1 actually profiles.

Checker round-1 fixes (2026-10-27), applied here:
  1. Peak RSS: ru_maxrss is a LIFETIME high-water mark (never per-block). Replaced with
     /proc/self/clear_refs ("5" resets the kernel's own VmHWM tracker for THIS process, no root needed)
     before each measured block, then VmRSS and VmHWM read from /proc/self/status after. VmRSS is also
     read again after `del X; gc.collect()`, to separate "memory still in use" from "freed but held by
     the allocator" (one of B4's candidate causes for the 52.9 vs 23.4 GB gap). If /proc is unavailable
     (non-Linux), falls back to ru_maxrss with a loud warning rather than silently lying.
  2. The previous matrix is dropped (del + gc.collect) inside timed_load before it returns, and
     timed_load returns ONLY the summary dict (not X) so a caller cannot accidentally keep it alive the
     way `_, s = timed_load(...)` did before. Each fold's COMBINED load now runs FIRST (the B4-comparable
     figure, measured before earlier loads leave the allocator/page cache in a different state), then the
     3 separate loads. Each block prints its own starting VmRSS as an explicit baseline.
  3. Nested double-counting: _assert_positional_row_order itself calls pq.read_table (harness.py:125) for
     the event_id column. A global depth counter marks that inner read as nested; nested calls are tagged
     with a distinct stage name (column_read.in_row_order) so they never pollute the real feature-column
     read stats, and are excluded from "instrumented_total" (their time is already inside their parent's
     own recorded elapsed, so adding it again would double-count wall-clock time that only happened once).
  4. Provenance path fixed (was dirname(dirname(HERE)), the repo root; GIT_STATE.json lives at
     research/dataset/GIT_STATE.json, i.e. dirname(HERE)/dataset/GIT_STATE.json). Added sha256 of
     inputs_v1_pair.csv and master_manifest.py to the header. (B4's own "git_head unavailable" line had
     the same bug -- reported to the planner separately; B4's receipt stands on its file shas regardless.)
  5. cast wrapper guards len(arr) for inputs without __len__ (e.g. a Scalar), so an internal pyarrow cast
     that doesn't go through an Array never crashes the run.
  6. The "uninstrumented remainder" is now described accurately (to_pandas/factorize or to_numpy, and the
     strided per-column write into the preallocated (n_events x 1,093) matrix -- not just take()). Every
     manifest_verify call now also logs MB/s (bytes verified / elapsed), so page-cache state (warm vs
     cold) is visible in the numbers themselves rather than assumed; the separate-vs-combined verify
     comparison is reported alongside that throughput, not attributed to call count alone.

Two separate 3-separate-calls vs 1-combined-call load_features comparisons are run (fold 7, fold 0) to
quantify the brief's named concern directly: "load_features calls MF.verify per file on every call, which
re-hashes the group files each time train, val and test are loaded."

Arrow pool bytes (pa.default_memory_pool().bytes_allocated()/max_memory()/backend_name) are sampled
around every read_table/cast call and around every load_features block, to confirm or rule out the
candidate causes for the 52.9 GB RSS vs 23.4 GB matrix gap found in B4 (not to assume one): pool retention
across the ~1,093 sequential per-column reads; full-column decompression before take (the read_table
wrapper records the FULL row count of every column read, which is the file's total event count, not
len(event_ids) -- this is a structural fact about load_features's current code, not an inference);
double-copy in cast + to_numpy. Hazard-row build and scoring (score_fold, day_block_bootstrap) are timed
with RANDOM dummy scores -- TIMING ONLY, not a scored prediction, exactly as B4's own preprocessing note.

SAFETY: launched under `timeout` in run_b5_profile.sh, not relied on to self-interrupt (same reasoning as
B4: most of the time is inside compiled pyarrow/pandas code, not pure Python bytecode).
"""
import csv
import functools
import gc
import os
import resource
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

SEED = 20261027  # fixed, logged; profiling-only RNG (no model result depends on this)
N_RESAMPLES = 2000  # A5 bootstrap resample count, used for the scoring timing only

_PROC_STATUS = "/proc/self/status"
_PROC_CLEAR_REFS = "/proc/self/clear_refs"
_HAS_PROC = os.path.exists(_PROC_STATUS)
if not _HAS_PROC:
    print("[B5-PROFILE] WARN: /proc/self/status not available on this platform -- falling back to "
          "ru_maxrss (a LIFETIME high-water mark, NOT per-block; later blocks' 'peak' figures will be "
          "unusable and are labelled as such)", flush=True)


def clear_peak_rss():
    if not _HAS_PROC:
        return
    try:
        with open(_PROC_CLEAR_REFS, "w") as f:
            f.write("5")
    except OSError as e:
        print(f"[B5-PROFILE] WARN: could not write {_PROC_CLEAR_REFS} ({e}); VmHWM will not reset per-block",
              flush=True)


def rss_gb():
    """Returns (VmRSS, VmHWM) in GB from /proc/self/status, or (ru_maxrss, ru_maxrss) as a labelled
    fallback. VmHWM is only a true per-block peak if clear_peak_rss() was called at the top of the block."""
    if not _HAS_PROC:
        v = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6
        return v, v
    d = {}
    with open(_PROC_STATUS) as f:
        for line in f:
            if line.startswith(("VmRSS:", "VmHWM:")):
                k, v = line.split(":")
                d[k.strip()] = int(v.strip().split()[0]) / 1e6  # kB -> GB
    return d.get("VmRSS", float("nan")), d.get("VmHWM", float("nan"))


def pool_stats():
    pool = pa.default_memory_pool()
    return pool.bytes_allocated() / 1e9, pool.max_memory() / 1e9, pool.backend_name


# ---------------------------------------------------------------------------
# Instrumentation: wrap library/module functions by NAME, call the original,
# return its exact result. No harness.py file is touched; load_features's
# return value is byte-identical to calling it unwrapped. A global depth
# counter + context stack flags NESTED calls (e.g. the event_id read inside
# _assert_positional_row_order) so they are never double-counted against the
# outer call that already includes their time, and are tagged distinctly so
# they don't pollute genuine feature-column read/cast stats.
# ---------------------------------------------------------------------------
CALLS = []  # list of dict(stage=..., elapsed_s=..., nested=..., **extra), reset per measured block
_DEPTH = 0
_CTX_STACK = []


def _enter(label):
    global _DEPTH
    _DEPTH += 1
    _CTX_STACK.append(label)


def _exit():
    global _DEPTH
    _DEPTH -= 1
    _CTX_STACK.pop()


def _record(stage, t0, nested, **extra):
    CALLS.append({"stage": stage, "elapsed_s": time.time() - t0, "nested": nested, **extra})


def _wrap_verify(orig):
    @functools.wraps(orig)
    def wrapped(ver, rels, base=None):
        nested = _DEPTH > 0
        sizes = []
        for rel in rels:
            p = os.path.join(H.MF.WORK, rel)
            if os.path.exists(p):
                sizes.append(os.path.getsize(p))
        total_bytes = sum(sizes)
        _enter("verify")
        t0 = time.time()
        try:
            r = orig(ver, rels, base)
        finally:
            _exit()
        dt = time.time() - t0
        mb_s = (total_bytes / 1e6) / dt if dt > 0 else float("inf")
        _record("manifest_verify", t0, nested, rels=list(rels), bytes=total_bytes, mb_per_s=mb_s)
        return r
    return wrapped


def _wrap_row_order(orig):
    @functools.wraps(orig)
    def wrapped(file):
        nested = _DEPTH > 0
        was_cached = file in H._ROW_ORDER_CHECKED
        _enter("row_order")
        t0 = time.time()
        try:
            r = orig(file)
        finally:
            _exit()
        _record("row_order_assert", t0, nested, file=file, was_cached=was_cached)
        return r
    return wrapped


def _wrap_check_inputs(orig):
    @functools.wraps(orig)
    def wrapped(columns):
        nested = _DEPTH > 0
        _enter("check_inputs")
        t0 = time.time()
        try:
            r = orig(columns)
        finally:
            _exit()
        _record("check_inputs", t0, nested, n_columns=len(columns))
        return r
    return wrapped


def _wrap_read_table(orig):
    @functools.wraps(orig)
    def wrapped(path, columns=None, **kw):
        nested = _DEPTH > 0
        ctx = _CTX_STACK[-1] if _CTX_STACK else None
        stage = f"column_read.in_{ctx}" if ctx else "column_read"
        b_before, _, _ = pool_stats()
        _enter("read_table")
        t0 = time.time()
        try:
            tbl = orig(path, columns=columns, **kw)
        finally:
            _exit()
        b_after, m_after, _ = pool_stats()
        _record(stage, t0, nested, path=os.path.basename(path), column=columns[0] if columns else None,
                rows_returned=tbl.num_rows, dtype=str(tbl.column(0).type) if tbl.num_columns else None,
                pool_delta_gb=b_after - b_before, pool_after_gb=b_after, pool_max_gb=m_after)
        return tbl
    return wrapped


def _wrap_cast(orig):
    @functools.wraps(orig)
    def wrapped(arr, target_type, **kw):
        nested = _DEPTH > 0
        n = len(arr) if hasattr(arr, "__len__") else None
        b_before, _, _ = pool_stats()
        _enter("cast")
        t0 = time.time()
        try:
            r = orig(arr, target_type, **kw)
        finally:
            _exit()
        b_after, _, _ = pool_stats()
        _record("cast", t0, nested, n=n, pool_delta_gb=b_after - b_before)
        return r
    return wrapped


def install_instrumentation():
    """check_inputs and _assert_positional_row_order are called ONLY from inside load_features
    (confirmed by reading harness.py). MF.verify is called from inside load_features too, but ALSO from
    MF.open_version (master_manifest.py:48, a bare-name call resolved via the same module dict), which
    load_search_events uses at startup -- that's fine: the signature is identical at every call site, it
    ran without error in the crashed run, and CALLS is reset at the start of each timed_load block, so
    the extra pre-profiling entries are just discarded, never reported. pq.read_table and pc.cast are NOT
    safe to patch globally in the same way:
    pandas' own pd.read_parquet (used by MF.open_version, which load_search_events calls before any
    profiling block even starts) also calls pq.read_table, but passes it an already-open file object,
    not a path string -- the first VM run crashed exactly here (os.path.basename() on a BufferedReader).
    So those two are patched/restored ONLY around each H.load_features call (see load_features_patched),
    never globally -- this also means they can never pick up any pyarrow activity outside the thing
    Step 1 is actually asked to profile."""
    H.check_inputs = _wrap_check_inputs(H.check_inputs)
    H._assert_positional_row_order = _wrap_row_order(H._assert_positional_row_order)
    H.MF.verify = _wrap_verify(H.MF.verify)


def load_features_patched(event_ids, in_cols):
    """H.load_features, with pq.read_table/pc.cast patched ONLY for the duration of this call (see
    install_instrumentation's docstring for why they can't be global patches)."""
    orig_read_table, orig_cast = pq.read_table, pc.cast
    pq.read_table = _wrap_read_table(orig_read_table)
    pc.cast = _wrap_cast(orig_cast)
    try:
        return H.load_features(event_ids, in_cols)
    finally:
        pq.read_table, pc.cast = orig_read_table, orig_cast


def summarize_calls(label):
    by_stage = {}
    for c in CALLS:
        by_stage.setdefault(c["stage"], []).append(c)
    top_level_total = sum(c["elapsed_s"] for c in CALLS if not c["nested"])
    print(f"[B5-PROFILE] {label}: {len(CALLS)} instrumented calls, {top_level_total:.2f}s top-level "
          f"instrumented total (nested calls excluded from this sum -- their time is already inside "
          f"their parent's own elapsed)", flush=True)
    for stage, items in by_stage.items():
        s_top = sum(c["elapsed_s"] for c in items if not c["nested"])
        s_nested = sum(c["elapsed_s"] for c in items if c["nested"])
        print(f"[B5-PROFILE]   {stage}: n={len(items)} top_level_sum={s_top:.2f}s nested_sum={s_nested:.2f}s "
              f"mean={((s_top+s_nested)/len(items))*1000:.1f}ms", flush=True)
    if "column_read" in by_stage:
        reads = by_stage["column_read"]  # genuine feature-column reads only; event_id reads are tagged
        full_rows = [c["rows_returned"] for c in reads]
        print(f"[B5-PROFILE]   column_read rows_returned: min={min(full_rows):,} max={max(full_rows):,} "
              f"(the file's full row count is read before any take-by-position, every single call)", flush=True)
        pool_deltas = [c["pool_delta_gb"] for c in reads]
        print(f"[B5-PROFILE]   column_read pool_delta_gb: sum={sum(pool_deltas):.3f} "
              f"min={min(pool_deltas):.4f} max={max(pool_deltas):.4f} "
              f"pool_after_gb trajectory: start={reads[0]['pool_after_gb']:.3f} end={reads[-1]['pool_after_gb']:.3f} "
              f"pool_max_gb={max(c['pool_max_gb'] for c in reads):.3f}", flush=True)
    if "cast" in by_stage:
        casts = by_stage["cast"]
        n_top, n_nested = sum(1 for c in casts if not c["nested"]), sum(1 for c in casts if c["nested"])
        print(f"[B5-PROFILE]   cast pool_delta_gb: sum={sum(c['pool_delta_gb'] for c in casts):.3f} "
              f"(covers all {len(casts)} pc.cast calls, {n_top} top-level + {n_nested} nested/"
              f"pyarrow-internal -- the sum is not restricted to top-level only, unlike the time totals)",
              flush=True)
    verify_calls = by_stage.get("manifest_verify", [])
    for c in verify_calls:
        print(f"[B5-PROFILE]   manifest_verify: {c['rels']} {c['bytes']/1e9:.2f}GB in {c['elapsed_s']:.2f}s "
              f"({c['mb_per_s']:.0f} MB/s -- low means cold page cache, high means warm)", flush=True)
    row_order_calls = by_stage.get("row_order_assert", [])
    if row_order_calls:
        print(f"[B5-PROFILE]   row_order_assert cached hits: "
              f"{sum(1 for c in row_order_calls if c['was_cached'])}/{len(row_order_calls)}", flush=True)
    return {"label": label, "top_level_total_s": top_level_total,
            "by_stage_top_s": {k: sum(c["elapsed_s"] for c in v if not c["nested"]) for k, v in by_stage.items()},
            "verify_mb_per_s": [c["mb_per_s"] for c in verify_calls]}


def timed_load(label, event_ids, in_cols):
    """One H.load_features call, unmodified, with CALLS reset first and a wall-clock total around it.
    Drops X (del + gc.collect) before returning, and returns ONLY the summary dict -- the caller cannot
    accidentally keep the matrix alive across the next block (checker round-1 finding 2)."""
    global CALLS
    CALLS = []
    clear_peak_rss()
    rss_before, hwm_before = rss_gb()
    pool_before, _, backend = pool_stats()
    t_wall0 = time.time()
    X, cols = load_features_patched(event_ids, in_cols)
    wall_s = time.time() - t_wall0
    rss_after, hwm_after = rss_gb()
    pool_after, pool_max, _ = pool_stats()
    x_nbytes_gb = X.nbytes / 1e9
    top_level_s = sum(c["elapsed_s"] for c in CALLS if not c["nested"])
    del X, cols
    gc.collect()
    rss_after_gc, _ = rss_gb()
    retained_gb = rss_after_gc - rss_before  # checker round-2: the real "freed but held" signal is this
                                              # staying well above 0 while pool_after (Arrow bytes) is
                                              # near 0 -- rss_after_gc < rss_after on its own just means X
                                              # (a large numpy array, not Arrow-managed) was freed to the OS
                                              # as expected, not evidence of retention.
    print(f"[B5-PROFILE] {label}: n_events={len(event_ids):,} n_cols={len(in_cols)} wall={wall_s:.2f}s "
          f"top_level_instrumented={top_level_s:.2f}s uninstrumented_remainder={wall_s - top_level_s:.2f}s "
          f"(remainder = to_pandas/factorize or to_numpy, plus the strided per-column write into the "
          f"preallocated n_events x {len(in_cols)} matrix -- pyarrow's Array.take is a compiled method, "
          f"not independently hookable, and is part of this remainder too) "
          f"rss_before={rss_before:.2f}GB rss_after={rss_after:.2f}GB rss_after_gc={rss_after_gc:.2f}GB "
          f"retained_gb={retained_gb:.2f}GB (retained_gb well above 0 while pool_after is near 0 is the "
          f"signal that memory is held by something other than Arrow's own pool after X and cols are "
          f"freed; rss_after_gc alone dropping below rss_after is just X being freed to the OS as normal) "
          f"hwm_before={hwm_before:.2f}GB hwm_this_block={hwm_after:.2f}GB "
          f"pool_before={pool_before:.3f}GB pool_after={pool_after:.3f}GB pool_max={pool_max:.3f}GB "
          f"pool_backend={backend} X.nbytes={x_nbytes_gb:.2f}GB", flush=True)
    summary = summarize_calls(label)
    summary.update(wall_s=wall_s, rss_before_gb=rss_before, rss_after_gb=rss_after,
                    rss_after_gc_gb=rss_after_gc, retained_gb=retained_gb,
                    hwm_before_gb=hwm_before, hwm_block_gb=hwm_after,
                    pool_before_gb=pool_before, pool_after_gb=pool_after, pool_max_gb=pool_max,
                    x_nbytes_gb=x_nbytes_gb, n_events=len(event_ids))
    return summary


def profile_fold(fold, in_cols):
    k = fold["k"]
    print(f"[B5-PROFILE] ===== fold {k}: train={len(fold['train_ids']):,} val={len(fold['val_ids']):,} "
          f"test={len(fold['test_ids']):,} =====", flush=True)
    rss_baseline, _ = rss_gb()
    print(f"[B5-PROFILE] fold {k} baseline VmRSS before any load this fold: {rss_baseline:.2f}GB", flush=True)

    # COMBINED first (checker round-1, finding 2): this is the B4-comparable figure (52.9 GB there), run
    # before any of this fold's separate loads can leave the allocator/page cache in a different state.
    print(f"[B5-PROFILE] --- fold {k}: ONE COMBINED load_features call (train+val+test ids), FIRST ---",
          flush=True)
    H._ROW_ORDER_CHECKED.clear()
    all_ids = np.concatenate([fold["train_ids"], fold["val_ids"], fold["test_ids"]])
    s_combined = timed_load(f"fold{k}.combined", all_ids, in_cols)

    print(f"[B5-PROFILE] --- fold {k}: THREE SEPARATE load_features calls (train, val, test) ---", flush=True)
    H._ROW_ORDER_CHECKED.clear()
    s_train = timed_load(f"fold{k}.separate.train", fold["train_ids"], in_cols)
    s_val = timed_load(f"fold{k}.separate.val", fold["val_ids"], in_cols)
    s_test = timed_load(f"fold{k}.separate.test", fold["test_ids"], in_cols)
    separate_total_wall = s_train["wall_s"] + s_val["wall_s"] + s_test["wall_s"]
    separate_total_verify = (s_train["by_stage_top_s"].get("manifest_verify", 0)
                              + s_val["by_stage_top_s"].get("manifest_verify", 0)
                              + s_test["by_stage_top_s"].get("manifest_verify", 0))
    print(f"[B5-PROFILE] fold {k} separate-calls total: wall={separate_total_wall:.2f}s "
          f"manifest_verify={separate_total_verify:.2f}s", flush=True)
    combined_verify = s_combined["by_stage_top_s"].get("manifest_verify", 0)
    print(f"[B5-PROFILE] fold {k} SEPARATE vs COMBINED: wall {separate_total_wall:.2f}s vs "
          f"{s_combined['wall_s']:.2f}s ({separate_total_wall/max(s_combined['wall_s'],1e-9):.2f}x); "
          f"manifest_verify {separate_total_verify:.2f}s vs {combined_verify:.2f}s "
          f"({separate_total_verify/max(combined_verify,1e-9):.2f}x) -- NOTE: throughput (MB/s, logged per "
          f"call above) can differ between these because of page-cache warmth, not just call count; read "
          f"the MB/s lines before attributing the ratio to the extra calls alone.", flush=True)
    return {"k": k, "combined": s_combined,
            "separate": {"train": s_train, "val": s_val, "test": s_test,
                          "total_wall_s": separate_total_wall, "total_verify_s": separate_total_verify}}


def profile_hazard_and_scoring(events, fold):
    print("[B5-PROFILE] --- hazard-row build (full search set) ---", flush=True)
    clear_peak_rss()
    rss0, _ = rss_gb()
    t0 = time.time()
    hazard = H.build_hazard_rows(events)
    dt = time.time() - t0
    rss1, hwm1 = rss_gb()
    print(f"[B5-PROFILE] build_hazard_rows: {len(events):,} events -> {len(hazard):,} rows in {dt:.2f}s; "
          f"VmRSS {rss0:.2f}GB -> {rss1:.2f}GB (block VmHWM {hwm1:.2f}GB)", flush=True)

    print("[B5-PROFILE] --- scoring timing (RANDOM dummy scores -- TIMING ONLY, not a real result) ---",
          flush=True)
    rng = np.random.default_rng(SEED)
    test_ids = fold["test_ids"]
    events_test = events.loc[test_ids]
    dummy_scores = rng.random(len(test_ids))
    t0 = time.time()
    lift_val, top_mask = H.score_fold(dummy_scores, events_test, rng)
    dt_score = time.time() - t0
    print(f"[B5-PROFILE] score_fold: n={len(test_ids):,} in {dt_score*1000:.1f}ms "
          f"(dummy lift={lift_val:.4f}, meaningless -- random scores)", flush=True)

    day_of_event = events_test["t0"].dt.floor("D").to_numpy()
    reach = events_test["reach_10h"].to_numpy()
    chance = events_test["chance_10h"].to_numpy()
    t0 = time.time()
    point, lo, hi = H.day_block_bootstrap(day_of_event, top_mask, reach, chance, N_RESAMPLES, 0.9875, rng)
    dt_boot = time.time() - t0
    print(f"[B5-PROFILE] day_block_bootstrap: n_resamples={N_RESAMPLES} in {dt_boot:.2f}s "
          f"(dummy point={point:.4f} CI=[{lo:.4f},{hi:.4f}], meaningless -- random scores)", flush=True)
    return {"hazard_build_s": dt, "hazard_rows": len(hazard), "score_fold_s": dt_score,
            "bootstrap_s": dt_boot}


def main():
    t_main0 = time.time()
    import master_manifest as MF
    print(f"[B5-PROFILE] sha256 {os.path.basename(__file__)}: {MF.sha(os.path.abspath(__file__))}", flush=True)
    print(f"[B5-PROFILE] sha256 harness.py: {MF.sha(os.path.join(HERE, 'harness.py'))}", flush=True)
    print(f"[B5-PROFILE] sha256 inputs_v1_pair.csv: {MF.sha(os.path.join(HERE, 'inputs_v1_pair.csv'))}",
          flush=True)
    print(f"[B5-PROFILE] sha256 master_manifest.py: {MF.sha(os.path.abspath(MF.__file__))}", flush=True)
    gs = os.path.join(os.path.dirname(HERE), "dataset", "GIT_STATE.json")  # research/dataset/GIT_STATE.json
    git_head, git_dirty = ("unavailable", "unavailable")
    if os.path.exists(gs):
        G = MF.json.load(open(gs))
        git_head, git_dirty = G.get("head", "unavailable"), len(G.get("porcelain", []))
    print(f"[B5-PROFILE] git_head {git_head} ({git_dirty} uncommitted paths); "
          f"start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC; pid {os.getpid()}; "
          f"pyarrow {pa.__version__}; pool_backend={pa.default_memory_pool().backend_name}; "
          f"has_proc_status={_HAS_PROC}", flush=True)
    print("[B5-PROFILE] NOTE: this script does not modify harness.py. It monkeypatches, by module-attribute "
          "name only, master_manifest.verify, pyarrow.parquet.read_table, pyarrow.compute.cast, "
          "harness.check_inputs and harness._assert_positional_row_order with timing wrappers that call "
          "the original and return its exact result -- load_features's behaviour and output are unchanged. "
          "No optimisation of any kind happens in this script (B5 Step 1 rule).", flush=True)

    install_instrumentation()

    rows = list(csv.DictReader(open(os.path.join(HERE, "inputs_v1_pair.csv"))))
    in_cols = [r["column"] for r in rows if r["in_out"] == "IN"]
    print(f"[B5-PROFILE] {len(in_cols)} IN columns  [{time.time()-t_main0:.0f}s]", flush=True)

    events = H.load_search_events()
    folds = H.build_folds(events)
    results = {}
    for k in (7, 0):
        results[k] = profile_fold(folds[k], in_cols)
        print(f"[B5-PROFILE] fold {k} done  [{time.time()-t_main0:.0f}s]", flush=True)

    results["hazard_and_scoring"] = profile_hazard_and_scoring(events, folds[7])
    final_rss, final_hwm = rss_gb()
    print(f"[B5-PROFILE] all done  [{time.time()-t_main0:.0f}s]; final VmRSS {final_rss:.2f}GB "
          f"VmHWM since last reset (hazard/scoring block) {final_hwm:.2f}GB", flush=True)


if __name__ == "__main__":
    main()
