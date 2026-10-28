"""HL-MODEL1 S1 Step 1: ONE fit, in isolation, timed with per-iteration logging (planner's ruling, S1
review round 5, after the full mid->lowest chain ran 7,200s and produced zero completed fits).

    python -u research/model/s1_one_fit_probe.py > research/model/logs/s1_one_fit_probe.log

Fold 7 (largest), full train set, full IN-column set (1,091 columns, no subsampling), the column-block
streaming preprocessing (checker-approved, S1 review round 4), ONE split-weight L-BFGS-B fit at the middle
grid penalty (index 4 of 8, l1_ratio 0.5), COLD START, under R6's own stopping rule (ftol=1e-7 relative
objective change, maxiter=2,000 -- NOT the equivalence proof's tight settings, ftol=1e-15/maxiter=15,000;
confirmed by the literal `tol`/`max_iter` values passed below, logged).

Logs every 10 iterations (wall, objective, max|grad|) via s1_model.fit_hazard_elastic_net_lbfgsb's
callback, so a run that is killed by the launch timeout still tells us iterations x seconds -- the
previous chain run gave nothing after 1.5h of silence between its last print and the kill.

Reports, but does NOT change: the actual BLAS/thread configuration this process is running under, and
hazard_logistic.py's own per-chunk float64 cast of X (its design, re-proven 4/4 PASS after the chunking
fix -- S1 review round 1). Per the checker's ruling: speeding this up (float32 matmuls, fewer iterations,
more threads) trades precision or completeness for speed and is the user's call, not made here.
"""
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402
from s1_preprocess import fit_preprocessing, apply_preprocessing  # noqa: E402
from s1_model import lambda_max, build_grid, fit_hazard_elastic_net_lbfgsb, kkt_violation  # noqa: E402
from b5_profile import rss_gb, clear_peak_rss  # noqa: E402 -- checker-approved memory helpers, reused

L1_RATIO_SIZED = 0.5
N_GRID = 8
MID_INDEX = N_GRID // 2
MAX_ITER = 2000
TOL = 1e-7
N_FOLDS = 8
FITS_PER_FOLD = 16
HOURS_GATE = 24.0


def log_blas_threads():
    import os as _os
    env_threads = {k: _os.environ.get(k) for k in
                   ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")}
    print(f"[S1-ONEFIT] cpu_count={_os.cpu_count()} thread env vars={env_threads}", flush=True)
    try:
        import threadpoolctl
        for info in threadpoolctl.threadpool_info():
            print(f"[S1-ONEFIT] threadpool: {info}", flush=True)
    except ImportError:
        print("[S1-ONEFIT] threadpoolctl not installed -- BLAS's actual runtime thread count is not "
              "directly queryable here; the env vars above are what was set at process launch.",
              flush=True)
    print("[S1-ONEFIT] hazard_logistic.hazard_nll_grad casts EACH event-row chunk of X "
          "(float32) to float64 before X@w / X.T@resid (its own design, re-proven 4/4 PASS after this "
          "chunking -- S1 review round 1) -- this is NOT a float32 BLAS path; reported here as fact, not "
          "changed.", flush=True)


def main():
    t0 = time.time()
    import master_manifest as MF
    for name in ("s1_one_fit_probe.py", "s1_preprocess.py", "s1_model.py", "hazard_logistic.py", "harness.py"):
        print(f"[S1-ONEFIT] sha256 {name}: {MF.sha(os.path.join(HERE, name))}", flush=True)
    cache_info = H._cache_info()
    cache_sha = cache_info.get("cache_sha256", "NO VALID CACHE") if cache_info else "NO VALID CACHE"
    print(f"[S1-ONEFIT] cache manifest cache_sha256: {cache_sha} "
          f"(must be bd5dc2549374d0a80c8b042425e34119289b17b753a49213ac28c1831c6ca544)", flush=True)
    gs = os.path.join(os.path.dirname(HERE), "dataset", "GIT_STATE.json")
    git_head, git_dirty = ("unavailable", "unavailable")
    if os.path.exists(gs):
        G = MF.json.load(open(gs))
        git_head, git_dirty = G.get("head", "unavailable"), len(G.get("porcelain", []))
    print(f"[S1-ONEFIT] git_head {git_head} ({git_dirty} uncommitted paths); "
          f"start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC; pid {os.getpid()}", flush=True)
    print(f"[S1-ONEFIT] solver settings: ftol={TOL:.0e} maxiter={MAX_ITER} maxfun={MAX_ITER*4} "
          f"(R6's own stopping rule -- NOT the equivalence proof's tight ftol=1e-15/maxiter=15000)",
          flush=True)
    log_blas_threads()

    clear_peak_rss()
    rss0, _ = rss_gb()
    events = H.load_search_events()
    folds = H.build_folds(events)
    fold = folds[7]
    train_ids = fold["train_ids"]
    in_cols = cache_info["columns"]
    assert len(in_cols) == 1091, f"expected 1,091 IN columns, cache has {len(in_cols)}"
    print(f"[S1-ONEFIT] fold 7: n_train={len(train_ids):,}  [{time.time()-t0:.0f}s]", flush=True)

    t_prep0 = time.time()
    stats = fit_preprocessing(train_ids, in_cols)
    X_fit, out_cols = apply_preprocessing(train_ids, in_cols, stats)
    t_prep_train = time.time() - t_prep0
    import gc
    gc.collect()
    rss_after_prep, hwm_after_prep = rss_gb()
    print(f"[S1-ONEFIT] preprocessed TRAIN (block-streamed) in {t_prep_train:.2f}s: "
          f"n_features={len(out_cols)} rss={rss_after_prep:.2f}GB VmHWM={hwm_after_prep:.2f}GB "
          f"[{time.time()-t0:.0f}s]", flush=True)

    train_events = events.loc[train_ids]
    hazard = H.build_hazard_rows(train_events)
    pos = {eid: i for i, eid in enumerate(train_ids)}
    row_event_pos = hazard["event_id"].map(pos).to_numpy()
    row_step = hazard["step"].to_numpy()
    row_label = hazard["label"].to_numpy()
    n_events = len(train_ids)
    print(f"[S1-ONEFIT] hazard rows: {len(row_event_pos):,} over {n_events:,} train events "
          f"[{time.time()-t0:.0f}s]", flush=True)

    lam_max = lambda_max(X_fit, row_event_pos, row_step, row_label, n_events, L1_RATIO_SIZED)
    grid = build_grid(lam_max, n=N_GRID)
    print(f"[S1-ONEFIT] lambda_max={lam_max:.6g} grid={np.array2string(grid, precision=4)} "
          f"fitting grid[{MID_INDEX}]={grid[MID_INDEX]:.6g}  [{time.time()-t0:.0f}s]", flush=True)

    clear_peak_rss()
    t_fit0 = time.time()
    r = fit_hazard_elastic_net_lbfgsb(X_fit, row_event_pos, row_step, row_label, n_events,
                                       lam=grid[MID_INDEX], l1_ratio=L1_RATIO_SIZED,
                                       max_iter=MAX_ITER, tol=TOL, log_every=10, log_prefix="[S1-ONEFIT]")
    wall = time.time() - t_fit0
    _, hwm_fit = rss_gb()
    kkt = kkt_violation(r["w"], r["b"], grid[MID_INDEX], L1_RATIO_SIZED, X_fit, row_event_pos, row_step,
                         row_label, n_events)
    s_per_eval = wall / max(r["n_calls"], 1)
    print(f"[S1-ONEFIT] FIT DONE: wall={wall:.2f}s n_iter={r['n_iter']}/{MAX_ITER} n_calls={r['n_calls']} "
          f"s_per_eval={s_per_eval:.3f}s converged={r['converged']} obj_final={r['obj_final']:.4f} "
          f"n_nonzero_w={int(np.sum(r['w'] != 0))} kkt_max={kkt['max_violation']:.3e} "
          f"VmHWM_this_fit={hwm_fit:.2f}GB  [{time.time()-t0:.0f}s]", flush=True)

    _, hwm_overall = rss_gb()
    print(f"[S1-ONEFIT] overall peak RSS this run (VmHWM, process start to now): {hwm_overall:.2f}GB "
          f"(rss at process start: {rss0:.2f}GB)", flush=True)

    # Rough projection (A: a SINGLE measured fit, not a chain -- every other grid point is ASSUMED to cost
    # the same as this one, which is conservative for warm-started steps but is the only data point this
    # probe has; preprocessing is assumed to repeat at ~this same train-set cost for the refit too, which
    # under-states the refit's real row count by about 1.27x). FITS_PER_FOLD (16) + 1 refit = 17 "fit
    # units" per fold, plus 2 preprocessing passes per fold.
    per_fold_s = 2 * t_prep_train + (FITS_PER_FOLD + 1) * wall
    total_s = N_FOLDS * per_fold_s
    total_hours = total_s / 3600.0
    print(f"[S1-ONEFIT] ROUGH PROJECTION (A, one measured fit treated as representative of all "
          f"{FITS_PER_FOLD}+1 fits per fold -- conservative, not the multi-point chain the full sizing "
          f"script would give): per_fold = 2 x prep[{t_prep_train:.1f}s] + {FITS_PER_FOLD+1} x "
          f"fit[{wall:.1f}s] = {per_fold_s:.0f}s; x {N_FOLDS} folds = {total_s:.0f}s = {total_hours:.2f}h "
          f"(fits + preprocessing only; scoring/M1-M6 not included)", flush=True)
    if total_hours > HOURS_GATE:
        print(f"[S1-ONEFIT] PROJECTION OVER {HOURS_GATE}h GATE -- per the brief, STOP here; "
              f"report the options to the planner. Do not shrink the grid or subsample.", flush=True)
    else:
        print(f"[S1-ONEFIT] projection is under the {HOURS_GATE}h gate.", flush=True)

    print(f"[S1-ONEFIT] all done  [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
