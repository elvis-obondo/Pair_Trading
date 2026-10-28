"""HL-MODEL1 S1 Step 1: logistic sizing (the B4 spec, on the B5 code).

    python -u research/model/s1_sizing.py > research/model/logs/s1_sizing.log

On fold 7 (largest), at full data, full IN-column set (1,091 columns, no subsampling -- standing project
rule): times a CHAIN of warm-started fits from the middle grid penalty (index 4 of 8, l1_ratio 0.5) down
to the lowest (index 7, the hardest -- planner/checker ruling, S1 review round 1: timing only the middle
point gives an optimistic projection).

SOLVER (checker's ruling, S1 review round 2): split-weight L-BFGS-B ONLY, at full fold-7 scale -- not
FISTA. s1_model_proof.py already showed, on real (if smaller) smoke data, that L-BFGS-B reaches the same
optimum as FISTA (within 1e-4 relative at both the middle and lowest grid points) while running 6-14x
faster; running FISTA's chain at full fold-7 scale too would cost hours on top of this run and risks this
script's own 7200s launch timeout before the L-BFGS-B chain it actually needs even starts. FISTA
(s1_model.fit_hazard_elastic_net) stays in s1_model.py for that smoke proof only -- not called here.
Every fit's KKT violation (s1_model.kkt_violation) is logged for every fit, per the checker's rule and its
own note for the record: at the smoke proof's lowest penalty, L-BFGS-B's R6-style stopping rule (ftol=
1e-7) stopped at an objective 1.28 higher than FISTA's -- a real fit may stop slightly short of the true
optimum too, which is exactly what the logged KKT number is for. Peak RSS is reported. The extrapolation
uses the WORST-CASE (slowest) per-step time in the chain, not the middle point alone.

The refit (train+val) is approximated as: worst_case_fit_time x (n_train+n_val)/n_train [the row-count
ratio -- about 1.27x for fold 7] + a SEPARATELY TIMED preprocessing re-fit on train+val (checker's ruling,
round 1: not the mid-penalty cold time, and preprocessing itself is re-timed, not just scaled).

Scoring and the use-case metrics (M1-M6) are NOT timed here -- they run once per fold on test-sized data
(much smaller than a fit) and are not the dominant cost; the brief's Step 1 asks for fit timing only.
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
MID_INDEX = N_GRID // 2        # the "middle penalty" -- index 4 of 8
CHAIN_INDICES = list(range(MID_INDEX, N_GRID))   # 4,5,6,7 -- mid down to the lowest (hardest)
MAX_ITER = 2000
TOL = 1e-7
N_FOLDS = 8
FITS_PER_FOLD = 16             # R3: 2 l1_ratios x 8 penalties
HOURS_GATE = 24.0


def run_chain(fit_fn, X_fit, row_event_pos, row_step, row_label, n_events, grid, solver_name, **fit_kwargs):
    """Runs `fit_fn` warm-started along CHAIN_INDICES (mid -> lowest), timing each step and logging its
    KKT violation. Returns (results_list, all_converged)."""
    results = []
    w_prev, b_prev = None, None
    all_converged = True
    for idx in CHAIN_INDICES:
        lam = grid[idx]
        t0 = time.time()
        r = fit_fn(X_fit, row_event_pos, row_step, row_label, n_events, lam=lam, l1_ratio=L1_RATIO_SIZED,
                   w0=w_prev, b0=b_prev, max_iter=MAX_ITER, **fit_kwargs)
        wall = time.time() - t0
        kkt = kkt_violation(r["w"], r["b"], lam, L1_RATIO_SIZED, X_fit, row_event_pos, row_step,
                             row_label, n_events)
        print(f"[S1-SIZING] {solver_name} grid[{idx}] (lam={lam:.6g}, {'cold' if idx == MID_INDEX else 'warm'}): "
              f"wall={wall:.2f}s n_iter={r['n_iter']}/{MAX_ITER} converged={r['converged']} "
              f"obj_final={r['obj_final']:.4f} n_nonzero_w={int(np.sum(r['w'] != 0))} "
              f"kkt_max={kkt['max_violation']:.3e}", flush=True)
        results.append({"idx": idx, "lam": lam, "wall_s": wall, **r, "kkt": kkt})
        all_converged = all_converged and r["converged"]
        w_prev, b_prev = r["w"], r["b"]
    return results, all_converged


def main():
    t0 = time.time()
    import master_manifest as MF
    for name in ("s1_sizing.py", "s1_preprocess.py", "s1_model.py", "hazard_logistic.py", "harness.py"):
        print(f"[S1-SIZING] sha256 {name}: {MF.sha(os.path.join(HERE, name))}", flush=True)
    cache_info = H._cache_info()
    cache_sha = cache_info.get("cache_sha256", "NO VALID CACHE") if cache_info else "NO VALID CACHE"
    print(f"[S1-SIZING] cache manifest cache_sha256: {cache_sha} "
          f"(must be bd5dc2549374d0a80c8b042425e34119289b17b753a49213ac28c1831c6ca544)", flush=True)
    gs = os.path.join(os.path.dirname(HERE), "dataset", "GIT_STATE.json")
    git_head, git_dirty = ("unavailable", "unavailable")
    if os.path.exists(gs):
        G = MF.json.load(open(gs))
        git_head, git_dirty = G.get("head", "unavailable"), len(G.get("porcelain", []))
    print(f"[S1-SIZING] git_head {git_head} ({git_dirty} uncommitted paths); "
          f"start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC; pid {os.getpid()}", flush=True)

    clear_peak_rss()
    rss0, _ = rss_gb()
    events = H.load_search_events()
    folds = H.build_folds(events)
    fold = folds[7]
    train_ids, val_ids = fold["train_ids"], fold["val_ids"]
    in_cols = cache_info["columns"]
    assert len(in_cols) == 1091, f"expected 1,091 IN columns, cache has {len(in_cols)}"
    print(f"[S1-SIZING] fold 7: n_train={len(train_ids):,} n_val={len(val_ids):,}  "
          f"[{time.time()-t0:.0f}s]", flush=True)

    # --- Phase 1: grid selection fit, on TRAIN rows only (R1) ---
    # Planner's ruling, S1 review round 3: fit_preprocessing/apply_preprocessing now stream one raw
    # column at a time straight from the cache (harness.load_features_cached) by event_ids -- no
    # (n x 1,091) raw matrix is ever materialised here, which is what pushed peak RSS to 55.25 GB on
    # train alone in the prior run (see s1_preprocess.py's module docstring for the full accounting).
    cols = in_cols
    import gc
    t_prep0 = time.time()
    stats = fit_preprocessing(train_ids, cols)
    X_fit, out_cols = apply_preprocessing(train_ids, cols, stats)
    t_prep_train = time.time() - t_prep0
    gc.collect()
    rss_after_prep, hwm_after_prep = rss_gb()
    print(f"[S1-SIZING] preprocessed TRAIN in {t_prep_train:.2f}s: n_features={len(out_cols)} "
          f"(ticker_a_levels={len(stats['ticker_levels']['ticker_a'])} "
          f"ticker_b_levels={len(stats['ticker_levels']['ticker_b'])}) "
          f"rss={rss_after_prep:.2f}GB VmHWM={hwm_after_prep:.2f}GB  [{time.time()-t0:.0f}s]", flush=True)

    train_events = events.loc[train_ids]
    hazard = H.build_hazard_rows(train_events)
    pos = {eid: i for i, eid in enumerate(train_ids)}
    row_event_pos = hazard["event_id"].map(pos).to_numpy()
    row_step = hazard["step"].to_numpy()
    row_label = hazard["label"].to_numpy()
    n_events = len(train_ids)
    pos_per_step = np.bincount(row_step - 1, weights=row_label.astype(np.float64), minlength=H.N_STEPS)
    print(f"[S1-SIZING] hazard rows: {len(row_event_pos):,} over {n_events:,} train events; "
          f"label=1 rows per step: {pos_per_step.astype(int).tolist()}  [{time.time()-t0:.0f}s]", flush=True)

    lam_max = lambda_max(X_fit, row_event_pos, row_step, row_label, n_events, L1_RATIO_SIZED)
    grid = build_grid(lam_max, n=N_GRID)
    print(f"[S1-SIZING] lambda_max={lam_max:.6g} grid={np.array2string(grid, precision=4)} "
          f"chain indices (mid->lowest)={CHAIN_INDICES}  [{time.time()-t0:.0f}s]", flush=True)

    clear_peak_rss()
    # Checker's ruling, S1 review round 2: split-weight L-BFGS-B only, at full fold-7 scale, under R6's own
    # stopping rule (ftol=1e-7 relative objective change, maxiter=2,000) -- not an artificially tight
    # comparison setting, since this chain's times ARE the extrapolation. FISTA is not run here at all
    # (s1_model_proof.py already showed the two reach the same real-data optimum, at much smaller scale;
    # running FISTA's chain here too risks hours more wall time and this script's own launch timeout).
    chosen_name = "LBFGSB"
    chosen_results, lbfgsb_all_converged = run_chain(fit_hazard_elastic_net_lbfgsb, X_fit, row_event_pos,
                                                       row_step, row_label, n_events, grid, "LBFGSB", tol=TOL)
    _, hwm_lbfgsb = rss_gb()
    print(f"[S1-SIZING] LBFGSB chain done, all_converged={lbfgsb_all_converged} "
          f"(non-converged fits are flagged above, per R6, not dropped), "
          f"VmHWM_this_block={hwm_lbfgsb:.2f}GB  [{time.time()-t0:.0f}s]", flush=True)

    cold_s = chosen_results[0]["wall_s"]          # grid[MID_INDEX], cold start
    warm_times = [r["wall_s"] for r in chosen_results[1:]]   # grid[MID_INDEX+1 .. lowest], warm-started
    worst_case_s = max(r["wall_s"] for r in chosen_results)
    print(f"[S1-SIZING] {chosen_name} per-step times: cold(idx={MID_INDEX})={cold_s:.2f}s "
          f"warm(idx={CHAIN_INDICES[1:]})={[f'{w:.2f}s' for w in warm_times]} "
          f"worst_case={worst_case_s:.2f}s", flush=True)

    del X_fit
    gc.collect()

    # --- Phase 2: preprocessing re-fit timing on TRAIN+VAL (checker's ruling, round 1) ---
    # Times BOTH fit_preprocessing and apply_preprocessing (same as Phase 1's t_prep_train), not just the
    # stats pass -- the real refit needs the transformed train+val matrix too, and the planner's memory
    # fix (streaming columns, no raw matrix held alongside the output) is what makes it SAFE to actually
    # build that output here and measure its real peak RSS, instead of only estimating it.
    all_ids = np.concatenate([train_ids, val_ids])
    clear_peak_rss()
    t_prep0 = time.time()
    stats_tv = fit_preprocessing(all_ids, cols)
    X_trainval_fit, _ = apply_preprocessing(all_ids, cols, stats_tv)
    t_prep_trainval = time.time() - t_prep0
    _, hwm_trainval_prep = rss_gb()
    print(f"[S1-SIZING] preprocessing re-fit on TRAIN+VAL ({len(all_ids):,} events, "
          f"n_features={X_trainval_fit.shape[1]}): {t_prep_trainval:.2f}s "
          f"VmHWM_this_block={hwm_trainval_prep:.2f}GB  [{time.time()-t0:.0f}s]", flush=True)
    del X_trainval_fit, stats_tv
    gc.collect()

    _, hwm_overall = rss_gb()
    print(f"[S1-SIZING] overall peak RSS this run (VmHWM, process start to now): {hwm_overall:.2f}GB "
          f"(rss at process start: {rss0:.2f}GB)", flush=True)

    # Extrapolation (A: arithmetic on the measured numbers above).
    row_ratio = (len(train_ids) + len(val_ids)) / len(train_ids)
    refit_s = t_prep_trainval + worst_case_s * row_ratio
    warm_steps_per_l1ratio = (FITS_PER_FOLD // 2) - 1   # 7 warm steps per l1_ratio path, R3
    # cold + (warm_steps - measured_warm_steps) extra warm steps at the WORST-CASE warm time (conservative:
    # this chain measured 3 warm steps toward the hardest end; any unmeasured warm step is assumed to cost
    # at least as much as the worst one actually measured, not the average).
    worst_warm_s = max(warm_times) if warm_times else cold_s
    extra_warm_steps = warm_steps_per_l1ratio - len(warm_times)
    per_l1ratio_s = cold_s + sum(warm_times) + max(0, extra_warm_steps) * worst_warm_s
    # Planner's ruling, S1 review round 3: preprocessing is fit TWICE per fold, not once per fit -- once
    # on train (t_prep_train, reused for all 16 grid fits in that fold) and once on train+val for the
    # refit (t_prep_trainval, inside refit_s above). The first version of this script measured
    # t_prep_train but never added it to the total -- fixed here.
    per_fold_fit_s = t_prep_train + 2 * per_l1ratio_s + refit_s
    total_fit_s = N_FOLDS * per_fold_fit_s
    total_hours = total_fit_s / 3600.0
    print(f"[S1-SIZING] EXTRAPOLATION (A, arithmetic on {chosen_name}'s measured times; worst-case/conservative "
          f"where a grid point was not directly measured): per-l1_ratio = cold[{cold_s:.2f}s] + "
          f"{len(warm_times)} measured warm {[f'{w:.2f}s' for w in warm_times]} + {max(0,extra_warm_steps)} "
          f"unmeasured warm steps @ worst-case[{worst_warm_s:.2f}s] = {per_l1ratio_s:.1f}s; "
          f"refit = prep[{t_prep_trainval:.2f}s] + worst_case_fit[{worst_case_s:.2f}s] x "
          f"row_ratio[{row_ratio:.3f}] = {refit_s:.1f}s; "
          f"per_fold = train_prep[{t_prep_train:.2f}s] + 2 x {per_l1ratio_s:.1f}s + {refit_s:.1f}s "
          f"= {per_fold_fit_s:.1f}s; "
          f"x {N_FOLDS} folds = {total_fit_s:.0f}s = {total_hours:.2f}h "
          f"(fits + both preprocessing passes per fold; scoring and M1-M6 metrics are NOT included, not "
          f"measured here, expected small relative to {N_FOLDS * FITS_PER_FOLD} fits' total)", flush=True)
    if total_hours > HOURS_GATE:
        print(f"[S1-SIZING] PROJECTION OVER {HOURS_GATE}h GATE -- per the brief, STOP here; "
              f"do not shrink the grid or subsample. Report the options to the planner.", flush=True)
    else:
        print(f"[S1-SIZING] projection is under the {HOURS_GATE}h gate.", flush=True)

    print(f"[S1-SIZING] all done  [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
