"""HL-MODEL1 B5 Step 1 (user-approved follow-up, 2026-10-27): peak RSS of the startup step ALONE.

    python -u research/model/b5_profile_startup.py > research/model/logs/b5_profile_startup.log

Scope, as approved by the user through the planner: ONE measurement of H.load_search_events() +
H.build_folds(events) -- the only two calls that ran before B4's 52.9 GB peak-RSS print, and the only
thing b5_profile.py's Step 1 run did NOT measure (its first clear_refs() call happens after both of
these already ran). Nothing else: no optimisation, no AWS, no further runs chained off this result.
Fresh process, nothing else runs here -- no load_features, no fit.

Three reset-then-read points, each isolating ONE step's own peak (checker's spec): (1) right after
imports, (2) reset immediately before load_search_events, read immediately after, (3) reset immediately
before build_folds, read immediately after. ru_maxrss (B4's own measure, the lifetime high-water mark) is
also printed at the end, to tie this result directly to B4's 52.9 GB figure. harness.py is used UNCHANGED
(sha256 c06484599c879d050f30af898aaf078f754266208f29f3a82c2580f51c75548a) with no instrumentation/
monkeypatching of any kind -- this script only calls the two functions directly and reads
/proc/self/status around them, reusing the already-approved rss_gb/clear_peak_rss/pool_stats helpers from
b5_profile.py rather than redefining the same methodology twice. If the peak turns out to be inside
load_search_events, it is reported at the function level, per the checker's instruction -- no sub-step
breakdown inside it unless the user asks for one.
"""
import os
import socket
import sys
import time

import resource

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402
from b5_profile import rss_gb, clear_peak_rss, pool_stats, _HAS_PROC  # noqa: E402


def main():
    t_main0 = time.time()
    import master_manifest as MF
    print(f"[B5-STARTUP] sha256 {os.path.basename(__file__)}: {MF.sha(os.path.abspath(__file__))}",
          flush=True)
    print(f"[B5-STARTUP] sha256 harness.py: {MF.sha(os.path.join(HERE, 'harness.py'))}", flush=True)
    print(f"[B5-STARTUP] sha256 master_manifest.py: {MF.sha(os.path.abspath(MF.__file__))}", flush=True)
    print(f"[B5-STARTUP] sha256 inputs_v1_pair.csv: {MF.sha(os.path.join(HERE, 'inputs_v1_pair.csv'))}",
          flush=True)
    print(f"[B5-STARTUP] sha256 b5_profile.py: {MF.sha(os.path.join(HERE, 'b5_profile.py'))}", flush=True)
    gs = os.path.join(os.path.dirname(HERE), "dataset", "GIT_STATE.json")
    git_head, git_dirty = ("unavailable", "unavailable")
    if os.path.exists(gs):
        G = MF.json.load(open(gs))
        git_head, git_dirty = G.get("head", "unavailable"), len(G.get("porcelain", []))
    print(f"[B5-STARTUP] git_head {git_head} ({git_dirty} uncommitted paths); "
          f"start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC; pid {os.getpid()}; "
          f"host {socket.gethostname()}; has_proc_status={_HAS_PROC}", flush=True)
    print("[B5-STARTUP] NOTE: no instrumentation/monkeypatching anywhere in this script; "
          "H.load_search_events and H.build_folds are called directly, unmodified. No optimisation, "
          "no AWS, no further runs chained off this result (B5 Step 1 follow-up, user-approved scope).",
          flush=True)

    # Point 1: right after imports.
    clear_peak_rss()
    rss0, hwm0 = rss_gb()
    pool0, pool0_max, backend = pool_stats()
    print(f"[B5-STARTUP] (1) after imports: VmRSS={rss0:.2f}GB VmHWM={hwm0:.2f}GB (since this reset) "
          f"pool={pool0:.3f}GB pool_backend={backend}  [{time.time()-t_main0:.0f}s]", flush=True)

    # Point 2: reset immediately before load_search_events, read immediately after.
    clear_peak_rss()
    rss_before_events, _ = rss_gb()
    t0 = time.time()
    events = H.load_search_events()
    t_events = time.time() - t0
    rss_after_events, hwm_events = rss_gb()
    pool_after_events, pool_max_events, _ = pool_stats()
    print(f"[B5-STARTUP] (2) load_search_events: {t_events:.2f}s, {len(events):,} events; "
          f"VmRSS {rss_before_events:.2f}GB -> {rss_after_events:.2f}GB; "
          f"VmHWM (this call's own peak, reset just before it) = {hwm_events:.2f}GB; "
          f"pool_after={pool_after_events:.3f}GB pool_max={pool_max_events:.3f}GB  "
          f"[{time.time()-t_main0:.0f}s]", flush=True)

    # Point 3: reset immediately before build_folds, read immediately after.
    clear_peak_rss()
    rss_before_folds, _ = rss_gb()
    t0 = time.time()
    folds = H.build_folds(events)
    t_folds = time.time() - t0
    rss_after_folds, hwm_folds = rss_gb()
    pool_after_folds, pool_max_folds, _ = pool_stats()
    print(f"[B5-STARTUP] (3) build_folds: {t_folds:.2f}s, {len(folds)} folds; "
          f"VmRSS {rss_before_folds:.2f}GB -> {rss_after_folds:.2f}GB; "
          f"VmHWM (this call's own peak, reset just before it) = {hwm_folds:.2f}GB; "
          f"pool_after={pool_after_folds:.3f}GB pool_max={pool_max_folds:.3f}GB  "
          f"[{time.time()-t_main0:.0f}s]", flush=True)

    lifetime_ru_maxrss_gb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6  # KB on Linux
    print(f"[B5-STARTUP] TOTAL startup (load_search_events + build_folds): "
          f"{t_events + t_folds:.2f}s; VmRSS {rss0:.2f}GB -> {rss_after_folds:.2f}GB; "
          f"max(VmHWM_events, VmHWM_folds) = {max(hwm_events, hwm_folds):.2f}GB; "
          f"ru_maxrss (B4's own lifetime-high-water-mark measure, for direct comparison to its "
          f"52.9 GB figure) = {lifetime_ru_maxrss_gb:.2f}GB  [{time.time()-t_main0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
