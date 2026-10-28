"""HL-MODEL1 S1 Step 2: the full run. One fold at a time, restart-safe (a finished fold is never redone),
unattended -- the launcher (a separate bash script, not this file) is what loops/sleeps/syncs logs; this
script does exactly one invocation's worth of folds and exits.

    python -u research/model/s1_run.py --folds 0,1,2,3

Per fold (R1, R3, R4, R8): for each l1_ratio in {1.0, 0.5} (R3), builds the regularisation grid (8 points,
lambda_max down to 1e-3*lambda_max) on TRAIN rows only, chains s1_newton.fit_hazard_elastic_net_newton
warm-started along the path, and scores each grid point's VALIDATION lift (A5's lift formula, via
harness.score_fold -- "the model's P(reach within 10h)", i.e. p_10h from the SAME fit, computed on
validation). The best (lift, R2 tie-break: l1_ratio=1.0 first, then the larger penalty) is REFIT on
train+val (R1 -- "refit on the whole search period", A5's own vault rule, mirrored here); the step
intercepts warm-start from the selection fit (always length n_steps=20), but w starts cold -- train-only
and train+val preprocessing can drop different degenerate/sd0 columns, so the two fits' w are not
guaranteed to be the same width (found by this script's own dry run on real data). Test predictions
(p_2h, p_5h, p_10h) and the refit's coefficients are saved, plus
M6's raw per-column validation permutation importance (for columns with a non-zero coefficient in the
SELECTION fit, per the brief).

Vault safety: imports only `harness` (never `vault_loader`) and calls `assert_search_only`-protected
functions throughout (load_search_events/build_folds/build_hazard_rows/score_fold each assert their own
input internally). No vault-dated row can reach this script by construction.
"""
import argparse
import gc
import json
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402
from s1_preprocess import fit_preprocessing, apply_preprocessing  # noqa: E402
from s1_model import lambda_max, build_grid, kkt_violation  # noqa: E402
from s1_newton import fit_hazard_elastic_net_newton  # noqa: E402


def _vm_field(name):
    """One /proc/self/status field in MB (Linux only -- every real run is on GCP/AWS; returns None
    off-Linux so a laptop import/syntax check never breaks on this)."""
    try:
        for line in open("/proc/self/status"):
            if line.startswith(f"{name}:"):
                return int(line.split()[1]) // 1024
    except Exception:
        return None
    return None


def vm_hwm_mb():
    """Peak resident set EVER REACHED so far -- a high-water mark, so it never drops even after freeing
    memory (checker's finding). Use vm_rss_mb() to show a free actually took effect."""
    return _vm_field("VmHWM")


def vm_rss_mb():
    """CURRENT resident set -- drops after a real free, unlike VmHWM."""
    return _vm_field("VmRSS")


L1_RATIOS = (1.0, 0.5)          # R3, tried in this order for R2's tie-break (1.0 first)
N_GRID = 8
MAX_OUTER = 50                   # R6 amendment, user-approved (S1 review round 6)
TOL = 1e-7                       # R6
N_STEPS = H.N_STEPS
OUT_DIR = os.path.join(HERE, "logs", "s1")
SEED = 20261028                  # R7: one seed, logged, for score_fold's tie-break and permutation importance


def fold_hazard(events, ids):
    """Hazard rows for exactly these event ids, with a positional (event_id -> row index in `ids`) map --
    same pattern s1_newton_proof.py/s1_aws_thread_timing.py already use."""
    hazard = H.build_hazard_rows(events.loc[ids])
    pos = {eid: i for i, eid in enumerate(ids)}
    row_event_pos = hazard["event_id"].map(pos).to_numpy()
    row_step = hazard["step"].to_numpy()
    row_label = hazard["label"].to_numpy()
    return row_event_pos, row_step, row_label


def compute_p_h(w, b, X, h_steps):
    """p_h = 1 - prod over steps k <= h_steps of (1 - sigmoid(eta_event + b_k)) -- A3's own definition."""
    eta = X.astype(np.float64) @ np.asarray(w, dtype=np.float64)
    h = 1.0 / (1.0 + np.exp(-(eta[:, None] + np.asarray(b, dtype=np.float64)[None, :h_steps])))
    return 1.0 - np.prod(1.0 - h, axis=1)


def nonzero_raw_columns(w, out_cols, stats):
    """Groups s1_preprocess.py's OUTPUT columns back to their LOGICAL raw input column (a numeric
    column's own value + its missing indicator, if any, are the SAME raw column; ticker_a/ticker_b's
    one-hot columns are each one raw column -- R8d). A raw column is "non-zero" (M6: permute only
    non-zero-coefficient columns) if ANY of its output columns has a non-zero coefficient in `w`."""
    groups = {}   # raw column name -> list of output positions
    for j, c in enumerate(stats["final_numeric"]):
        groups.setdefault(c, []).append(j)
    ind_start = len(stats["final_numeric"])
    for i, c in enumerate(stats["nan_indicator_cols"]):
        groups.setdefault(c, []).append(ind_start + i)
    base = len(stats["final_numeric"]) + len(stats["nan_indicator_cols"])
    for tcol, levels in (("ticker_a", stats["ticker_levels"]["ticker_a"]),
                         ("ticker_b", stats["ticker_levels"]["ticker_b"])):
        idx = list(range(base, base + len(levels)))
        groups[tcol] = idx
        base += len(levels)
    return {raw_col: idx for raw_col, idx in groups.items() if np.any(w[idx] != 0)}


def permutation_importance(w, b, X_val, out_cols, stats, val_events, rng):
    """M6: one seeded permutation per RAW column (not per output column -- R8d, a numeric column's own
    value and its missing indicator move TOGETHER, ticker_a/ticker_b's one-hot columns move together as
    one unit), for columns with a non-zero coefficient in `w` (the SELECTION fit). Permuting the group of
    OUTPUT columns that all derive from one raw column by the SAME row permutation is mathematically
    IDENTICAL to permuting the raw column before preprocessing: every one of s1_preprocess.py's per-row
    transforms (clip, standardise, isnan) is a function of that row's own raw value alone, so permuting
    rows commutes with applying the transform. Scored as the INCREASE in validation log-loss (A5/A3's own
    reach_10h as the label, p_10h as the prediction) versus the unpermuted baseline.

    The model is linear in X (eta = X@w), so a permuted column's eta is just the baseline eta plus the
    CHANGE from permuting that one group: eta_perm = eta_base + (X_val[perm][:, idx] - X_val[:, idx]) @
    w[idx] -- O(n x |idx|) per column, never a copy of the full X_val or a float64 cast of it (checker's
    finding: the original full-matrix-copy version was O(n_cols) full-matrix casts, hours per fold on a
    ~10 GB val slice). Returns {raw_col: log_loss_increase}."""
    groups = nonzero_raw_columns(w, out_cols, stats)
    reach_10h = val_events["reach_10h"].to_numpy()
    eps = 1e-12

    def log_loss_from_eta(eta):
        h = 1.0 / (1.0 + np.exp(-(eta[:, None] + np.asarray(b, dtype=np.float64)[None, :N_STEPS])))
        p = 1.0 - np.prod(1.0 - h, axis=1)
        p = np.clip(p, eps, 1 - eps)
        return float(-np.mean(reach_10h * np.log(p) + (1 - reach_10h) * np.log(1 - p)))

    eta_base = X_val.astype(np.float64) @ np.asarray(w, dtype=np.float64)
    base_loss = log_loss_from_eta(eta_base)

    n = X_val.shape[0]
    importance = {}
    for raw_col, idx in groups.items():
        perm = rng.permutation(n)
        w_idx = np.asarray(w, dtype=np.float64)[idx]
        delta = (X_val[perm][:, idx].astype(np.float64) - X_val[:, idx].astype(np.float64)) @ w_idx
        eta_perm = eta_base + delta
        importance[raw_col] = log_loss_from_eta(eta_perm) - base_loss
    return importance, base_loss


def run_one_fold(k, events, fold, in_cols, rng):
    t0 = time.time()
    train_ids, val_ids, test_ids = fold["train_ids"], fold["val_ids"], fold["test_ids"]
    print(f"[S1-RUN] fold {k}: n_train={len(train_ids):,} n_val={len(val_ids):,} n_test={len(test_ids):,} "
          f"[{time.time()-t0:.0f}s]", flush=True)

    # --- selection: fit on TRAIN, score on VAL (R1, R4) ---
    stats_train = fit_preprocessing(train_ids, in_cols)
    X_train, out_cols = apply_preprocessing(train_ids, in_cols, stats_train)
    X_val, _ = apply_preprocessing(val_ids, in_cols, stats_train)
    print(f"[S1-RUN] fold {k}: preprocessed train+val, n_features={len(out_cols)} "
          f"degenerate={len(stats_train['degenerate_dropped'])} sd0={len(stats_train['sd0_dropped'])} "
          f"[{time.time()-t0:.0f}s]", flush=True)

    row_event_pos_tr, row_step_tr, row_label_tr = fold_hazard(events, train_ids)
    n_train = len(train_ids)
    val_events = events.loc[val_ids]
    print(f"[S1-RUN] fold {k}: VmRSS={vm_rss_mb()}MB VmHWM={vm_hwm_mb()}MB after train+val preprocessing "
          f"[{time.time()-t0:.0f}s]", flush=True)

    grid_log = []
    best = None   # dict: l1_ratio, lam_idx, lam, val_lift, w, b, n_iter, converged, rel_change
    for l1_ratio in L1_RATIOS:
        lam_max_v = lambda_max(X_train, row_event_pos_tr, row_step_tr, row_label_tr, n_train, l1_ratio)
        grid = build_grid(lam_max_v, n=N_GRID)
        w_warm, b_warm = None, None
        for lam_idx, lam in enumerate(grid):
            r = fit_hazard_elastic_net_newton(X_train, row_event_pos_tr, row_step_tr, row_label_tr,
                                               n_train, lam=lam, l1_ratio=l1_ratio, w0=w_warm, b0=b_warm,
                                               max_outer=MAX_OUTER, tol=TOL)
            w_warm, b_warm = r["w"], r["b"]
            p_val = compute_p_h(r["w"], r["b"], X_val, N_STEPS)
            val_lift, _ = H.score_fold(p_val, val_events, rng)
            entry = {"l1_ratio": l1_ratio, "lam_idx": lam_idx, "lam": float(lam), "val_lift": val_lift,
                     "n_iter": r["n_iter"], "converged": r["converged"], "rel_change": r["rel_change"],
                     "w": r["w"], "b": r["b"]}
            grid_log.append({k2: v for k2, v in entry.items() if k2 not in ("w", "b")})
            print(f"[S1-RUN] fold {k}: l1_ratio={l1_ratio} lam_idx={lam_idx} lam={lam:.6g} "
                  f"val_lift={val_lift:.4f} n_iter={r['n_iter']} converged={r['converged']} "
                  f"rel_change={r['rel_change']:.2e} [{time.time()-t0:.0f}s]", flush=True)
            if (best is None or val_lift > best["val_lift"]
                    or (val_lift == best["val_lift"] and _better_tie(entry, best))):
                best = entry
    print(f"[S1-RUN] fold {k}: SELECTED l1_ratio={best['l1_ratio']} lam_idx={best['lam_idx']} "
          f"lam={best['lam']:.6g} val_lift={best['val_lift']:.4f}  [{time.time()-t0:.0f}s]", flush=True)

    # Planner's requirement: the selected fit's exact KKT violation (on the TRAIN rows it was fit on) and
    # its final relative objective change, reported for the chosen setting, not just the convergence flag.
    kkt_selected = kkt_violation(best["w"], best["b"], best["lam"], best["l1_ratio"], X_train,
                                  row_event_pos_tr, row_step_tr, row_label_tr, n_train)
    print(f"[S1-RUN] fold {k}: SELECTED KKT max_violation={kkt_selected['max_violation']:.3e} "
          f"rel_change={best['rel_change']:.2e}  [{time.time()-t0:.0f}s]", flush=True)

    # M6 permutation importance on the SELECTION fit (not the refit), per the brief.
    perm_importance, base_val_loss = permutation_importance(
        best["w"], best["b"], X_val, out_cols, stats_train, val_events, rng)
    print(f"[S1-RUN] fold {k}: permutation importance on {len(perm_importance)} non-zero raw columns, "
          f"base val log-loss={base_val_loss:.6f}  [{time.time()-t0:.0f}s]", flush=True)

    # Checker's finding: free the selection-phase matrices before building the refit's (train+val is
    # bigger than train alone, and holding both at once is pure waste on a paid machine).
    del X_train, X_val
    gc.collect()
    print(f"[S1-RUN] fold {k}: VmRSS={vm_rss_mb()}MB (VmHWM={vm_hwm_mb()}MB) after freeing selection-phase X "
          f"[{time.time()-t0:.0f}s]", flush=True)

    # --- refit on TRAIN+VAL (R1), warm-started from the selection fit ---
    all_ids = np.concatenate([train_ids, val_ids])
    stats_refit = fit_preprocessing(all_ids, in_cols)
    X_refit, out_cols_refit = apply_preprocessing(all_ids, in_cols, stats_refit)
    row_event_pos_rf, row_step_rf, row_label_rf = fold_hazard(events, all_ids)
    print(f"[S1-RUN] fold {k}: VmRSS={vm_rss_mb()}MB VmHWM={vm_hwm_mb()}MB after refit preprocessing "
          f"[{time.time()-t0:.0f}s]", flush=True)
    # w0 is cold (not best["w"]): train-only vs train+val preprocessing can drop different degenerate/sd0
    # columns, so the selection fit's w and the refit's X can have different widths (found by the dry
    # run: 184 vs 186 on a real small subset). b0 is still warm -- step intercepts are always length
    # n_steps=20 regardless of which numeric columns survived preprocessing.
    r_refit = fit_hazard_elastic_net_newton(X_refit, row_event_pos_rf, row_step_rf, row_label_rf,
                                             len(all_ids), lam=best["lam"], l1_ratio=best["l1_ratio"],
                                             w0=None, b0=best["b"], max_outer=MAX_OUTER, tol=TOL)
    kkt_refit = kkt_violation(r_refit["w"], r_refit["b"], best["lam"], best["l1_ratio"], X_refit,
                               row_event_pos_rf, row_step_rf, row_label_rf, len(all_ids))
    print(f"[S1-RUN] fold {k}: REFIT n_iter={r_refit['n_iter']} converged={r_refit['converged']} "
          f"rel_change={r_refit['rel_change']:.2e} KKT max_violation={kkt_refit['max_violation']:.3e} "
          f"n_nonzero_w={int(np.sum(r_refit['w'] != 0))} VmRSS={vm_rss_mb()}MB VmHWM={vm_hwm_mb()}MB "
          f"[{time.time()-t0:.0f}s]", flush=True)

    # --- test predictions, using the REFIT's own (train+val) preprocessing stats ---
    X_test, _ = apply_preprocessing(test_ids, in_cols, stats_refit)
    p_2h = compute_p_h(r_refit["w"], r_refit["b"], X_test, 4)    # 2h = 4 steps of 30 min
    p_5h = compute_p_h(r_refit["w"], r_refit["b"], X_test, 10)   # 5h = 10 steps
    p_10h = compute_p_h(r_refit["w"], r_refit["b"], X_test, N_STEPS)
    test_events = events.loc[test_ids]
    test_lift, _ = H.score_fold(p_10h, test_events, rng)
    print(f"[S1-RUN] fold {k}: TEST lift={test_lift:.4f}  [{time.time()-t0:.0f}s]", flush=True)

    os.makedirs(OUT_DIR, exist_ok=True)
    fold_prefix = os.path.join(OUT_DIR, f"fold{k}")
    selected_out = {k2: v for k2, v in best.items() if k2 not in ("w", "b")}
    selected_out["kkt"] = kkt_selected
    with open(f"{fold_prefix}_grid.json", "w") as f:
        json.dump({"grid_log": grid_log, "selected": selected_out}, f, indent=1)
    pd.DataFrame({"column": out_cols_refit, "coef": r_refit["w"]}
                 ).to_csv(f"{fold_prefix}_coefs.csv", index=False)
    pd.DataFrame({"event_id": test_ids, "fold": k, "p_2h": p_2h, "p_5h": p_5h, "p_10h": p_10h}
                 ).to_csv(f"{fold_prefix}_test_predictions.csv", index=False)
    pd.DataFrame({"column": list(perm_importance.keys()),
                  "log_loss_increase": list(perm_importance.values())}
                 ).to_csv(f"{fold_prefix}_val_permutation_importance.csv", index=False)
    with open(f"{fold_prefix}_done.json", "w") as f:
        json.dump({"fold": k, "selected_l1_ratio": best["l1_ratio"], "selected_lam": best["lam"],
                   "selected_rel_change": best["rel_change"], "selected_kkt": kkt_selected,
                   "refit_n_iter": r_refit["n_iter"], "refit_converged": r_refit["converged"],
                   "refit_rel_change": r_refit["rel_change"], "refit_kkt": kkt_refit,
                   "test_lift": test_lift, "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                   }, f, indent=1)
    print(f"[S1-RUN] fold {k} DONE  [{time.time()-t0:.0f}s]", flush=True)


def _better_tie(candidate, current):
    """R2: a tie goes to the larger penalty (smaller model), and R8e: among those, l1_ratio=1.0 first."""
    if candidate["l1_ratio"] != current["l1_ratio"]:
        return candidate["l1_ratio"] == 1.0
    return candidate["lam_idx"] < current["lam_idx"]   # lower lam_idx = LARGER penalty (grid descends)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", required=True, help="comma-separated fold indices this invocation handles, e.g. 0,1,2,3")
    args = ap.parse_args()
    fold_indices = [int(x) for x in args.folds.split(",")]

    t0 = time.time()
    import master_manifest as MF
    for name in ("s1_run.py", "s1_newton.py", "s1_preprocess.py", "s1_model.py", "hazard_logistic.py",
                 "harness.py"):
        print(f"[S1-RUN] sha256 {name}: {MF.sha(os.path.join(HERE, name))}", flush=True)
    cache_info = H._cache_info()
    cache_sha = cache_info.get("cache_sha256", "NO VALID CACHE -- load_features_cached would raise") \
        if cache_info else "NO VALID CACHE -- load_features_cached would raise"
    print(f"[S1-RUN] cache manifest cache_sha256: {cache_sha} "
          f"(must be bd5dc2549374d0a80c8b042425e34119289b17b753a49213ac28c1831c6ca544)", flush=True)
    gs = os.path.join(os.path.dirname(HERE), "dataset", "GIT_STATE.json")
    git_head, git_dirty = ("unavailable", "unavailable")
    if os.path.exists(gs):
        G = MF.json.load(open(gs))
        git_head, git_dirty = G.get("head", "unavailable"), len(G.get("porcelain", []))
    print(f"[S1-RUN] git_head {git_head} ({git_dirty} uncommitted paths); "
          f"seed={SEED} folds={fold_indices}; "
          f"start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC; pid {os.getpid()}", flush=True)

    events = H.load_search_events()
    folds = H.build_folds(events)
    in_cols = cache_info["columns"]
    assert len(in_cols) == 1091, f"expected 1,091 IN columns, cache has {len(in_cols)}"

    for k in fold_indices:
        done_path = os.path.join(OUT_DIR, f"fold{k}_done.json")
        if os.path.exists(done_path):
            print(f"[S1-RUN] fold {k}: done marker already present, skipping (restart-safe)", flush=True)
            continue
        fold_seed = SEED + k   # R7: one base seed, logged, per-fold derived so no two folds share a stream
        print(f"[S1-RUN] fold {k}: seed={fold_seed}", flush=True)
        rng = np.random.default_rng(fold_seed)
        run_one_fold(k, events, folds[k], in_cols, rng)

    print(f"[S1-RUN] all assigned folds done  [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
