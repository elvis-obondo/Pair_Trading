"""HL-MODEL1 B5 Step 3: before/after table per stage on fold 7, MATCHED cache states.

    python -u research/model/b5_step3_matched_comparison.py > research/model/logs/b5_step3_matched_comparison.log

Every prior timing comparison in B5 was cache-biased and said so explicitly: Step 2 (i)'s equivalence
proof ran OLD first (cold) then NEW immediately after (warm) on fold 7, and the build-cache script never
instrumented NEW's internals stage by stage at all (it only timed load_features as a black box). Neither
gives a fair, stage-level before/after on fold 7, which the checker asked for by name.

This script: ONE throwaway warm-up call (NEW.load_features on fold 7's combined ids, result discarded)
pulls every group file into the OS page cache. Then OLD (the committed pre-B5-Step-2 harness, a `git
show 955469b` snapshot, sha256 c06484599c879d050f30af898aaf078f754266208f29f3a82c2580f51c75548a --
deleted after this script runs, never committed as a parallel file, same discipline as Step 2 (i)'s own
frozen snapshot) and NEW are each timed ONCE on fold 7's combined ids, back to back, on that SAME now-warm
cache. Both get the SAME stage-level instrumentation (manifest verify, row-order assert, column read,
cast), by monkeypatching each module's own entry points by name (no harness.py edit; OLD's own file is
never touched either).

MATCHED, not just warm (checker's round-1 finding): the warm-up call above also populates NEW's own
_VERIFIED_FILES cache -- without a fix, NEW's timed call would skip manifest_verify entirely while OLD
still pays it, making the speed-up look bigger than it really is. timed_call() clears NEW._VERIFIED_FILES
(and both modules' _ROW_ORDER_CHECKED, which already existed pre-B5 and would cache across calls too)
immediately before EVERY timed call, so OLD and NEW both pay manifest_verify once on the same warm page
cache -- the real per-process cost a fresh process (e.g. S1) would see on its first load. A THIRD call,
NEW again with clear_verify_cache=False, measures NEW's own within-process cached benefit as its own row,
not compared against OLD (which has no such cache to begin with).

NEW's column_read/cast run in a thread pool, so their summed-per-stage seconds can exceed wall time
(several threads' CPU-seconds added together) -- labelled explicitly; OLD vs NEW is compared on wall= only,
never on the per-stage sums.
"""
import functools
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as NEW  # noqa: E402
import _frozen_harness_step3 as OLD  # noqa: E402
from b5_profile import rss_gb, clear_peak_rss  # noqa: E402 -- checker-approved memory helpers, reused

CALLS = []
_DEPTH = 0


def _record(stage, t0, nested, **extra):
    CALLS.append({"stage": stage, "elapsed_s": time.time() - t0, "nested": nested, **extra})


def instrument(mod, pq_mod, pc_mod):
    """Wraps mod's own entry points by module-attribute name (same technique as b5_profile.py /
    b5_equivalence_step2.py) and pq_mod.read_table / pc_mod.cast. Returns an uninstall() callback.

    Nesting (checker's finding on b5_profile.py, applied here too): _assert_positional_row_order itself
    calls pq.read_table internally (for the event_id column) -- a global depth counter marks that inner
    call as nested so it is never double-counted against row_order_assert's own elapsed, which already
    includes it."""
    global _DEPTH
    orig_verify = mod.MF.verify
    orig_row_order = mod._assert_positional_row_order
    orig_read_table = pq_mod.read_table
    orig_cast = pc_mod.cast

    @functools.wraps(orig_verify)
    def verify_w(ver, rels, base=None):
        global _DEPTH
        nested = _DEPTH > 0
        _DEPTH += 1
        t0 = time.time()
        try:
            r = orig_verify(ver, rels, base)
        finally:
            _DEPTH -= 1
        _record("manifest_verify", t0, nested)
        return r

    @functools.wraps(orig_row_order)
    def row_order_w(file):
        global _DEPTH
        nested = _DEPTH > 0
        _DEPTH += 1
        t0 = time.time()
        try:
            r = orig_row_order(file)
        finally:
            _DEPTH -= 1
        _record("row_order_assert", t0, nested)
        return r

    @functools.wraps(orig_read_table)
    def read_w(path, columns=None, **kw):
        global _DEPTH
        nested = _DEPTH > 0
        _DEPTH += 1
        t0 = time.time()
        try:
            r = orig_read_table(path, columns=columns, **kw)
        finally:
            _DEPTH -= 1
        _record("column_read", t0, nested)
        return r

    @functools.wraps(orig_cast)
    def cast_w(arr, target_type, **kw):
        global _DEPTH
        nested = _DEPTH > 0
        _DEPTH += 1
        t0 = time.time()
        try:
            r = orig_cast(arr, target_type, **kw)
        finally:
            _DEPTH -= 1
        _record("cast", t0, nested)
        return r

    mod.MF.verify = verify_w
    mod._assert_positional_row_order = row_order_w
    pq_mod.read_table = read_w
    pc_mod.cast = cast_w

    def uninstall():
        mod.MF.verify = orig_verify
        mod._assert_positional_row_order = orig_row_order
        pq_mod.read_table = orig_read_table
        pc_mod.cast = orig_cast

    return uninstall


def timed_call(label, fn, event_ids, in_cols, pq_mod, pc_mod, mod, row_order_cache_attr,
               clear_verify_cache=True, threaded=False):
    """checker's finding 1: clear mod's row-order cache AND (for NEW) its verify-cache before every timed
    call, so both OLD and NEW pay manifest_verify once on the same warm page cache -- matched, and the
    real per-process cost a fresh process (e.g. S1) would see. Pass clear_verify_cache=False for a
    deliberate SECOND NEW call that measures the within-process cached benefit as its own row, per the
    checker's suggestion."""
    global CALLS
    CALLS = []
    getattr(mod, row_order_cache_attr).clear()
    if hasattr(mod, "_VERIFIED_FILES") and clear_verify_cache:
        mod._VERIFIED_FILES.clear()
    clear_peak_rss()
    rss_before, _ = rss_gb()
    uninstall = instrument(mod, pq_mod, pc_mod)
    try:
        t0 = time.time()
        X, cols = fn(event_ids, in_cols)
        wall_s = time.time() - t0
    finally:
        uninstall()
    _, hwm = rss_gb()
    by_stage = {}
    for c in CALLS:
        if c["nested"]:
            continue  # already counted inside its parent's own elapsed (row_order_assert's inner read)
        by_stage.setdefault(c["stage"], []).append(c["elapsed_s"])
    stage_sums = {k: sum(v) for k, v in by_stage.items()}
    instrumented_s = sum(stage_sums.values())
    remainder_s = wall_s - instrumented_s
    nbytes = X.nbytes
    del X, cols
    import gc
    gc.collect()
    thread_note = " (column_read/cast SUMMED ACROSS THREADS -- can exceed wall time, checker's finding 2; " \
                  "compare OLD vs NEW on wall= only)" if threaded else ""
    print(f"[B5-STEP3] {label}: wall={wall_s:.2f}s manifest_verify={stage_sums.get('manifest_verify',0):.2f}s "
          f"row_order_assert={stage_sums.get('row_order_assert',0):.2f}s "
          f"column_read={stage_sums.get('column_read',0):.2f}s cast={stage_sums.get('cast',0):.2f}s "
          f"remainder={remainder_s:.2f}s rss_before={rss_before:.2f}GB VmHWM_this_block={hwm:.2f}GB "
          f"X.nbytes={nbytes/1e9:.2f}GB{thread_note}", flush=True)
    return {"wall_s": wall_s, **stage_sums, "remainder_s": remainder_s, "hwm_gb": hwm}


def main():
    t0 = time.time()
    import master_manifest as MF
    print(f"[B5-STEP3] sha256 {os.path.basename(__file__)}: {MF.sha(os.path.abspath(__file__))}", flush=True)
    print(f"[B5-STEP3] sha256 harness.py (NEW): {MF.sha(os.path.join(HERE, 'harness.py'))}", flush=True)
    print(f"[B5-STEP3] sha256 _frozen_harness_step3.py (OLD): "
          f"{MF.sha(os.path.join(HERE, '_frozen_harness_step3.py'))} "
          f"(must equal c06484599c879d050f30af898aaf078f754266208f29f3a82c2580f51c75548a)", flush=True)
    gs = os.path.join(os.path.dirname(HERE), "dataset", "GIT_STATE.json")
    git_head, git_dirty = ("unavailable", "unavailable")
    if os.path.exists(gs):
        G = MF.json.load(open(gs))
        git_head, git_dirty = G.get("head", "unavailable"), len(G.get("porcelain", []))
    print(f"[B5-STEP3] git_head {git_head} ({git_dirty} uncommitted paths); "
          f"start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC; pid {os.getpid()}", flush=True)

    import csv
    rows = list(csv.DictReader(open(os.path.join(HERE, "inputs_v1_pair.csv"))))
    in_cols = [r["column"] for r in rows if r["in_out"] == "IN"]
    print(f"[B5-STEP3] {len(in_cols)} IN columns", flush=True)

    events = NEW.load_search_events()
    folds = NEW.build_folds(events)
    f = folds[7]
    all_ids = np.concatenate([f["train_ids"], f["val_ids"], f["test_ids"]])
    print(f"[B5-STEP3] fold 7: n={len(all_ids):,}  [{time.time()-t0:.0f}s]", flush=True)

    # ONE throwaway warm-up call -- pulls every file into the OS page cache. Result discarded immediately.
    print("[B5-STEP3] warm-up call (result discarded, warms the page cache for both OLD and NEW)",
          flush=True)
    import pyarrow.parquet as pq
    import pyarrow.compute as pc
    X_warm, _ = NEW.load_features(all_ids, in_cols)
    del X_warm
    import gc
    gc.collect()
    print(f"[B5-STEP3] warm-up done  [{time.time()-t0:.0f}s]", flush=True)

    # MATCHED: both pay manifest_verify once on the same warm page cache (checker's finding 1 -- the
    # warm-up call above also populated NEW's own verify-cache, so clear_verify_cache=True, the default,
    # wipes that before NEW's timed call runs).
    r_old = timed_call("OLD (fold 7, warm page cache, fresh verify)", OLD.load_features, all_ids, in_cols,
                        pq, pc, OLD, "_ROW_ORDER_CHECKED")
    r_new = timed_call("NEW (fold 7, warm page cache, fresh verify)", NEW.load_features, all_ids, in_cols,
                        pq, pc, NEW, "_ROW_ORDER_CHECKED", threaded=True)

    # checker's optional suggestion: a SECOND NEW call, verify-cache left populated from the one above --
    # the within-process cached benefit NEW specifically provides (not matched against OLD, which has no
    # such cache; reported as its own row).
    r_new_cached = timed_call("NEW (fold 7, warm page cache, OWN verify-cache already warm -- "
                               "within-process repeat, not matched against OLD)",
                               NEW.load_features, all_ids, in_cols, pq, pc, NEW, "_ROW_ORDER_CHECKED",
                               clear_verify_cache=False, threaded=True)

    print(f"[B5-STEP3] speedup (matched warm page cache, fresh verify for both): "
          f"wall {r_old['wall_s']/max(r_new['wall_s'],1e-9):.2f}x, "
          f"manifest_verify {r_old.get('manifest_verify',0)/max(r_new.get('manifest_verify',1e-9),1e-9):.2f}x",
          flush=True)
    print(f"[B5-STEP3] NEW's own within-process verify-cache benefit: wall "
          f"{r_new['wall_s']/max(r_new_cached['wall_s'],1e-9):.2f}x vs its own prior call "
          f"(not compared to OLD, which has no such cache)", flush=True)
    print(f"[B5-STEP3] all done  [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
