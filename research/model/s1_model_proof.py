"""HL-MODEL1 S1: proves FISTA (s1_model.fit_hazard_elastic_net) and the split-weight L-BFGS-B fallback
(s1_model.fit_hazard_elastic_net_lbfgsb) reach the SAME optimum of the SAME penalised hazard objective, on
real standardised smoke data, at the MIDDLE and LOWEST grid penalties (checker's round-1 finding: FISTA is
only acceptable if shown to reach the optimum; a fallback must be proven equivalent before it can be used
for real). Also logs each fit's KKT violation (s1_model.kkt_violation) -- a check on the solution itself,
independent of which optimiser produced it.

    python -u research/model/s1_model_proof.py > research/model/logs/s1_model_proof.log

SEPARATION, checked and avoided (checker's finding on this session's first toy-data smoke test, which used
uniformly random minutes_to_mu unconditional on reach -- a real risk on a small sample): a step with zero
label=1 rows has no finite unpenalised MLE for its intercept and can make an optimiser's path look
"not converged" for reasons that have nothing to do with the optimiser. This script's smoke subset is
sized up from B5's 3,000-event proof (to N_SMOKE_EVENTS below) and explicitly ASSERTS every one of the 20
steps has at least one label=1 row before any fit runs; if real data at this size does not clear that bar,
the script raises rather than silently proceeding into a separation-confounded comparison.

Real preprocessing (s1_preprocess.fit_preprocessing/apply_preprocessing, R4/R8) runs on this smoke subset
first ('on the standardised smoke data' -- checker's wording), including ticker_a/ticker_b one-hot, so the
comparison exercises the actual S1 design, not a hand-picked clean subset of numeric columns only.
"""
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402
from s1_preprocess import fit_preprocessing, apply_preprocessing  # noqa: E402
from s1_model import (lambda_max, build_grid, fit_hazard_elastic_net,  # noqa: E402
                       fit_hazard_elastic_net_lbfgsb, kkt_violation)

SEED = 20261028
N_SMOKE_EVENTS = 20_000
SMOKE_COLS = ["z", "threshold", "beta", "beta_stab", "r2", "ticker_a", "ticker_b"]
N_STEPS = H.N_STEPS
L1_RATIO = 0.5
MAX_ITER = 2000
TOL_FIT = 1e-3   # looser than B5's unpenalised TOL_FIT=1e-4: this compares two DIFFERENT optimisers on a
                 # penalised, non-strictly-convex-in-general objective, not the same algorithm's own
                 # repeatability
PASS = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    PASS.append(cond)
    print(f"[S1-MODEL-PROOF] {name}: {status}" + (f" -- {detail}" if detail else ""), flush=True)
    return cond


def load_smoke_subset():
    events = H.load_search_events()
    folds = H.build_folds(events)
    test_ids = folds[0]["test_ids"]
    rng = np.random.default_rng(SEED)
    chosen = rng.choice(test_ids, size=min(N_SMOKE_EVENTS, len(test_ids)), replace=False)
    chosen = np.sort(chosen)
    hazard = H.build_hazard_rows(events.loc[chosen])
    event_pos = {eid: i for i, eid in enumerate(chosen)}
    row_event_pos = hazard["event_id"].map(event_pos).to_numpy()
    row_step = hazard["step"].to_numpy()
    row_label = hazard["label"].to_numpy()
    return chosen, row_event_pos, row_step, row_label


def main():
    t0 = time.time()
    import master_manifest as MF
    print(f"[S1-MODEL-PROOF] sha256 {os.path.basename(__file__)}: {MF.sha(os.path.abspath(__file__))}",
          flush=True)
    for name in ("s1_model.py", "s1_preprocess.py", "hazard_logistic.py", "harness.py"):
        print(f"[S1-MODEL-PROOF] sha256 {name}: {MF.sha(os.path.join(HERE, name))}", flush=True)
    gs = os.path.join(os.path.dirname(HERE), "dataset", "GIT_STATE.json")
    git_head, git_dirty = ("unavailable", "unavailable")
    if os.path.exists(gs):
        G = MF.json.load(open(gs))
        git_head, git_dirty = G.get("head", "unavailable"), len(G.get("porcelain", []))
    print(f"[S1-MODEL-PROOF] git_head {git_head} ({git_dirty} uncommitted paths); "
          f"start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC; pid {os.getpid()}", flush=True)

    chosen, row_event_pos, row_step, row_label = load_smoke_subset()
    n_events = len(chosen)
    pos_per_step = np.bincount(row_step - 1, weights=row_label.astype(np.float64), minlength=N_STEPS)
    print(f"[S1-MODEL-PROOF] smoke subset: {n_events} events (seed {SEED}), columns {SMOKE_COLS}, "
          f"{len(row_event_pos):,} hazard rows  [{time.time()-t0:.0f}s]", flush=True)
    print(f"[S1-MODEL-PROOF] label=1 rows per step: {pos_per_step.astype(int).tolist()}", flush=True)
    assert (pos_per_step > 0).all(), (
        "a step has zero label=1 rows in this smoke subset -- separation risk, raise N_SMOKE_EVENTS or "
        "change SEED rather than compare optimisers on a confounded objective")

    stats = fit_preprocessing(chosen, SMOKE_COLS)
    X_fit, out_cols = apply_preprocessing(chosen, SMOKE_COLS, stats)
    print(f"[S1-MODEL-PROOF] preprocessed: n_features={len(out_cols)} "
          f"degenerate_dropped={len(stats['degenerate_dropped'])} sd0_dropped={len(stats['sd0_dropped'])} "
          f"ticker_a_levels={len(stats['ticker_levels']['ticker_a'])} "
          f"ticker_b_levels={len(stats['ticker_levels']['ticker_b'])}  [{time.time()-t0:.0f}s]", flush=True)

    lam_max = lambda_max(X_fit, row_event_pos, row_step, row_label, n_events, L1_RATIO)
    grid = build_grid(lam_max, n=8)
    print(f"[S1-MODEL-PROOF] lambda_max={lam_max:.6g} grid={np.array2string(grid, precision=4)}", flush=True)

    all_ok = True
    for idx, label in ((4, "MIDDLE"), (7, "LOWEST")):
        lam = grid[idx]
        t_f0 = time.time()
        r_f = fit_hazard_elastic_net(X_fit, row_event_pos, row_step, row_label, n_events,
                                      lam=lam, l1_ratio=L1_RATIO, max_iter=MAX_ITER, tol=1e-7)
        t_fista = time.time() - t_f0
        t_l0 = time.time()
        r_l = fit_hazard_elastic_net_lbfgsb(X_fit, row_event_pos, row_step, row_label, n_events,
                                             lam=lam, l1_ratio=L1_RATIO, max_iter=MAX_ITER, tol=1e-12)
        t_lbfgsb = time.time() - t_l0
        kkt_f = kkt_violation(r_f["w"], r_f["b"], lam, L1_RATIO, X_fit, row_event_pos, row_step,
                               row_label, n_events)
        kkt_l = kkt_violation(r_l["w"], r_l["b"], lam, L1_RATIO, X_fit, row_event_pos, row_step,
                               row_label, n_events)
        obj_diff = abs(r_f["obj_final"] - r_l["obj_final"])
        rel_obj_diff = obj_diff / max(abs(r_l["obj_final"]), 1e-12)
        w_diff = float(np.max(np.abs(r_f["w"] - r_l["w"])))
        print(f"[S1-MODEL-PROOF] {label} penalty (idx={idx}, lam={lam:.6g}):", flush=True)
        print(f"   FISTA:  n_iter={r_f['n_iter']}/{MAX_ITER} converged={r_f['converged']} "
              f"obj={r_f['obj_final']:.6f} kkt_max={kkt_f['max_violation']:.3e} time={t_fista:.2f}s",
              flush=True)
        print(f"   LBFGSB: n_iter={r_l['n_iter']}/{MAX_ITER} converged={r_l['converged']} "
              f"obj={r_l['obj_final']:.6f} kkt_max={kkt_l['max_violation']:.3e} time={t_lbfgsb:.2f}s",
              flush=True)
        print(f"   rel|obj diff|={rel_obj_diff:.3e}  max|w diff|={w_diff:.3e}", flush=True)
        ok = check(f"{label} penalty -- FISTA and LBFGSB reach the same optimum "
                   f"(rel|obj diff|={rel_obj_diff:.2e} < {TOL_FIT:.0e})", rel_obj_diff < TOL_FIT)
        all_ok = all_ok and ok
        check(f"{label} penalty -- LBFGSB's own KKT violation is small (<=1e-4)", kkt_l["max_violation"] <= 1e-4)

    print(f"[S1-MODEL-PROOF] all done [{time.time()-t0:.0f}s]: {sum(PASS)}/{len(PASS)} checks PASS",
          flush=True)
    if not all(PASS):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
