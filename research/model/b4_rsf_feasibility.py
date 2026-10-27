"""HL-MODEL1 B4: Random survival forest feasibility (report, then STOP; no real-model scoring here).

    python -u research/model/b4_rsf_feasibility.py > research/model/logs/b4_rsf_feasibility.log

"Random survival forest feasibility: time one fold at full data with a fixed small number of trees and
extrapolate. If the full rolling run cannot finish in 24 h on the largest allowed machine, STOP and report
the options. Do not subsample (standing rule: full dataset always)." Times fold 7's FULL train set (no row
subsampling, the largest fold) with a FIXED SMALL n_estimators, at TWO depth settings (checker, 2026-10-27,
round 2: max_depth drives cost and a real RSF would not use max_depth=8 alone), and times PREDICTION too
(on fold 7's val and test sets -- prediction over ~600 unique times is not free and happens every fold).
Extrapolates with the grid size as a parameter (1, 4, 9 settings), not a single 8-folds-times-one-fit
guess, since the brief fixes no RSF hyperparameter grid.

RSF is fit on (minutes_to_mu capped at 600, reached flag) directly at the EVENT level (A3 model 3), not the
hazard-row level the logistic/boosted-tree models use -- fold 7's row count here is its train EVENT count
(3,979,894), not its hazard-row count.

This is NOT a scored model run (no lift, no pass bar): a timing measurement only, so B4's "no real-model
scoring" rule is not violated. Preprocessing here (NaN -> 0, factorised tickers, done inside
harness.load_features) is for TIMING REALISM ONLY -- the real preprocessing (imputation fitted on the
fold's TRAIN rows, per A4) is UNTIMED by this script and is not claimed to be what a real fit would use.
For the real scoring build (not this script): load_features factorises ticker_a/ticker_b on whatever id
set it is given, so codes differ between separate calls -- this script loads train+val+test in one call so
it doesn't hit that, but a real fold must fit the encoding on TRAIN only and apply it to val/test with an
explicit "unseen" level (A6).

TIMING, not wall-clock arithmetic (checker, round 2): with n_jobs=-1, N_TREES_TEST trees fit in parallel
across all cores, so fit_s is NOT "N_TREES_TEST trees' worth of time" -- it is close to one tree's wall
time when N_TREES_TEST == core count. Extrapolation below works in CORE-SECONDS PER TREE
(fit_s * ncores / N_TREES_TEST), then converts to wall time for n trees on c cores as
core_seconds_per_tree * n / c, reported for both the VM's core count and a named AWS core count, since
that's the number the B4 machine proposal needs.

SAFETY: run under `timeout` in the launching shell script, not relied on to self-interrupt (checker,
round 2: signal.alarm only fires between Python bytecode instructions, and the RSF fit spends almost all
its time inside sklearn/sksurv's compiled code, so an in-process alarm may not fire until the fit already
returned). The in-script alarm is kept ONLY as a backup for the parts that are pure Python (loading,
matrix building), not for the fit/predict calls themselves.
"""
import csv
import os
import resource
import signal
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402

NCORES = os.cpu_count() or 1
N_TREES_TEST = NCORES                  # one tree per core, so fit_s stays close to wall time for ONE tree
                                        # (checker, round 2: N_TREES_TEST=3 on 8 cores made fit_s look like
                                        # 3 trees' worth of serial work when it was really ~1 tree's worth)
DEPTH_SETTINGS = [
    {"max_depth": 8, "min_samples_leaf": 1},
    {"max_depth": None, "min_samples_leaf": 1000},   # unrestricted depth, leaf size as in a plausible validation grid
]
PY_ALARM_BUDGET_S = 20 * 60            # backup alarm for the pure-Python parts only (loading, matrix build)
TARGET_TREES_FOR_EXTRAPOLATION = [50, 100, 200]
GRID_SIZES_TO_REPORT = [1, 4, 9]
TARGET_HOURS_LIMIT = 24
MACHINES_TO_REPORT = {"this VM": NCORES, "AWS (named core count)": 64}
PREDICT_HORIZON_MINUTES = 600.0


class TimeoutError_(Exception):
    pass


def _alarm_handler(signum, frame):
    raise TimeoutError_(f"exceeded the {PY_ALARM_BUDGET_S}s backup budget for the pure-Python part")


def peak_rss_gb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6   # ru_maxrss is KB on Linux


def main():
    t0 = time.time()
    import master_manifest as MF
    gs = os.path.join(os.path.dirname(os.path.dirname(HERE)), "dataset", "GIT_STATE.json")
    git_head, git_dirty = ("unavailable", "unavailable")
    if os.path.exists(gs):
        G = MF.json.load(open(gs))
        git_head, git_dirty = G.get("head", "unavailable"), len(G.get("porcelain", []))
    print(f"[B4-RSF] sha256 {os.path.basename(__file__)}: {MF.sha(os.path.abspath(__file__))}", flush=True)
    print(f"[B4-RSF] sha256 harness.py: {MF.sha(os.path.join(HERE, 'harness.py'))}", flush=True)
    print(f"[B4-RSF] sha256 inputs_v1_pair.csv: {MF.sha(os.path.join(HERE, 'inputs_v1_pair.csv'))}", flush=True)
    print(f"[B4-RSF] git_head {git_head} ({git_dirty} uncommitted paths); "
          f"start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC; pid {os.getpid()}", flush=True)
    print(f"[B4-RSF] N_TREES_TEST={N_TREES_TEST} (= this machine's core count, one tree per core so fit_s "
          f"approximates one tree's wall time), depth settings={DEPTH_SETTINGS}, nproc={NCORES}, "
          f"launched under shell `timeout` (see run_b4_rsf.sh), in-script alarm {PY_ALARM_BUDGET_S}s for "
          f"the loading/matrix-build steps only", flush=True)
    print("[B4-RSF] NOTE: NaN->0 and factorised ticker columns (done inside harness.load_features) are for "
          "TIMING REALISM ONLY. The real preprocessing -- imputation fitted on the fold's TRAIN rows, per "
          "A4 -- is UNTIMED here and is not claimed to match this.", flush=True)

    signal.signal(signal.SIGALRM, _alarm_handler)
    signal.alarm(PY_ALARM_BUDGET_S)
    events = H.load_search_events()
    folds = H.build_folds(events)
    f = folds[-1]   # fold 7: the largest, closest to the eventual full-search refit's size
    print(f"[B4-RSF] fold {f['k']}: train={len(f['train_ids']):,} val={len(f['val_ids']):,} "
          f"test={len(f['test_ids']):,} events (FULL, no subsampling)  [{time.time()-t0:.0f}s]", flush=True)

    rows = list(csv.DictReader(open(os.path.join(HERE, "inputs_v1_pair.csv"))))
    in_cols = [r["column"] for r in rows if r["in_out"] == "IN"]
    print(f"[B4-RSF] loading {len(in_cols)} IN columns for train+val+test ({len(f['train_ids'])+len(f['val_ids'])+len(f['test_ids']):,} events)  "
          f"[{time.time()-t0:.0f}s]", flush=True)
    t_load = time.time()
    # one load_features call, not three: each call re-reads every one of the 15 group files' columns in
    # full (load time is dominated by that read, not by how many ids are kept), so loading train/val/test
    # separately would triple the file-read cost for no reason -- load the combined id set once, then
    # slice the resulting matrix by position (cheap, pure numpy).
    all_ids = np.concatenate([f["train_ids"], f["val_ids"], f["test_ids"]])
    n_train, n_val = len(f["train_ids"]), len(f["val_ids"])
    X_all, _ = H.load_features(all_ids, in_cols)
    np.nan_to_num(X_all, copy=False, nan=0.0)
    X_train = X_all[:n_train]
    X_val = X_all[n_train:n_train + n_val]
    X_test = X_all[n_train + n_val:]
    load_s = time.time() - t_load
    print(f"[B4-RSF] loaded train {X_train.shape}, val {X_val.shape}, test {X_test.shape} in {load_s:.0f}s "
          f"(float32, {X_train.nbytes/1e9:.1f}+{X_val.nbytes/1e9:.1f}+{X_test.nbytes/1e9:.1f} GB); "
          f"peak RSS so far {peak_rss_gb():.1f} GB  [{time.time()-t0:.0f}s]", flush=True)

    def surv_y(ids):
        mtm = events.loc[ids, "minutes_to_mu"].to_numpy(dtype=float)
        reached = np.isfinite(mtm)
        time_col = np.where(reached, mtm, 600.0)
        y = np.empty(len(ids), dtype=[("event", bool), ("time", float)])
        y["event"] = reached
        y["time"] = time_col
        return y

    y_train = surv_y(f["train_ids"])
    signal.alarm(0)   # the rest is the real fit/predict work; rely on the shell `timeout`, not this alarm

    from sksurv.ensemble import RandomSurvivalForest
    results = []
    for depth_setting in DEPTH_SETTINGS:
        tag = f"max_depth={depth_setting['max_depth']},min_samples_leaf={depth_setting['min_samples_leaf']}"
        print(f"[B4-RSF] fitting RandomSurvivalForest(n_estimators={N_TREES_TEST}, {tag}, n_jobs=-1) "
              f"on {X_train.shape[0]:,} x {X_train.shape[1]} ...  [{time.time()-t0:.0f}s]", flush=True)
        rsf = RandomSurvivalForest(n_estimators=N_TREES_TEST, n_jobs=-1, random_state=0, **depth_setting)
        t_fit = time.time()
        rsf.fit(X_train, y_train)
        fit_s = time.time() - t_fit
        print(f"[B4-RSF]   fit done: {fit_s:.1f}s for {N_TREES_TEST} trees; peak RSS {peak_rss_gb():.1f} GB  "
              f"[{time.time()-t0:.0f}s]", flush=True)

        t_pred_val = time.time()
        surv_arr_val = rsf.predict_survival_function(X_val, return_array=True)
        times = rsf.unique_times_
        horizon_idx = int(np.searchsorted(times, PREDICT_HORIZON_MINUTES, side="right") - 1)
        horizon_idx = max(horizon_idx, 0)
        horizon_time = times[horizon_idx]
        p_reach_val = 1.0 - surv_arr_val[:, horizon_idx]
        pred_val_s = time.time() - t_pred_val
        t_pred_test = time.time()
        surv_arr_test = rsf.predict_survival_function(X_test, return_array=True)
        p_reach_test = 1.0 - surv_arr_test[:, horizon_idx]
        pred_test_s = time.time() - t_pred_test
        print(f"[B4-RSF]   predict(val, {len(f['val_ids']):,} events): {pred_val_s:.1f}s; "
              f"predict(test, {len(f['test_ids']):,} events): {pred_test_s:.1f}s; "
              f"horizon time used = {horizon_time:.1f} min (last of {len(times)} unique train event times "
              f"<= {PREDICT_HORIZON_MINUTES:.0f}); peak RSS {peak_rss_gb():.1f} GB  [{time.time()-t0:.0f}s]",
              flush=True)
        print(f"[B4-RSF]   p_reach sanity: val mean {p_reach_val.mean():.4f}, test mean {p_reach_test.mean():.4f} "
              f"(timing-only preprocessing, not a scored prediction)")

        # core-seconds per tree, not per-tree wall time: fit_s is ~N_TREES_TEST trees run in PARALLEL
        # across NCORES cores (n_jobs=-1), so the serial cost of one tree is fit_s * NCORES / N_TREES_TEST.
        core_s_per_tree = fit_s * NCORES / N_TREES_TEST
        pred_per_1000_val = pred_val_s / (len(f["val_ids"]) / 1000)
        pred_per_1000_test = pred_test_s / (len(f["test_ids"]) / 1000)
        results.append(dict(tag=tag, fit_s=fit_s, core_s_per_tree=core_s_per_tree,
                             pred_val_s=pred_val_s, pred_test_s=pred_test_s,
                             pred_per_1000_val=pred_per_1000_val, pred_per_1000_test=pred_per_1000_test))

    refit_ratio = (n_train + n_val) / n_train   # the chosen-setting refit trains on train+val, not train alone
    print(f"[B4-RSF] extrapolation (fold 7's sizes as a conservative per-fold upper bound; "
          f"prediction scales with val/test size, not train size; refit-on-train+val scaled by "
          f"{refit_ratio:.3f}x the train-only fit)  [{time.time()-t0:.0f}s]")
    for r in results:
        print(f"[B4-RSF]   --- {r['tag']} ---")
        for n_trees in TARGET_TREES_FOR_EXTRAPOLATION:
            for machine, ncores_target in MACHINES_TO_REPORT.items():
                wall_s_per_n_trees = r["core_s_per_tree"] * n_trees / ncores_target
                est_fit_grid_h = wall_s_per_n_trees / 3600
                est_fit_refit_h = est_fit_grid_h * refit_ratio
                # one fold's TOTAL real cost = (grid_size x (fit on train + predict on val)) + (one refit
                # on train+val for the chosen setting + predict on test); predict cost uses this depth
                # setting's measured per-1000-event rate, assumed independent of which grid point it
                # belongs to and independent of target machine (predict timing was only measured here).
                for grid_size in GRID_SIZES_TO_REPORT:
                    est_pred_val_h = (r["pred_per_1000_val"] * len(f["val_ids"]) / 1000) / 3600
                    est_pred_test_h = (r["pred_per_1000_test"] * len(f["test_ids"]) / 1000) / 3600
                    one_fold_h = grid_size * (est_fit_grid_h + est_pred_val_h) + est_fit_refit_h + est_pred_test_h
                    all_folds_h = one_fold_h * 8   # 8 folds, fold 7's size as the per-fold upper bound
                    feasible = all_folds_h <= TARGET_HOURS_LIMIT
                    print(f"[B4-RSF]     {n_trees} trees, grid size {grid_size}, {machine} "
                          f"({ncores_target} cores): ~{one_fold_h:.2f}h/fold, "
                          f"~{all_folds_h:.2f}h for all 8 folds at this upper bound -- "
                          f"{'FEASIBLE' if feasible else 'STOP: exceeds 24h'} within {TARGET_HOURS_LIMIT}h")
    print(f"[B4-RSF] done  [{time.time()-t0:.0f}s]; final peak RSS {peak_rss_gb():.1f} GB")


if __name__ == "__main__":
    main()
