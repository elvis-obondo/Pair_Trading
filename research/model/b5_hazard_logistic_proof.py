"""HL-MODEL1 B5 Step 2: hazard rows without copying features -- the logistic core.

    python -u research/model/b5_hazard_logistic_proof.py > research/model/logs/b5_hazard_logistic_proof.log

Brief: "keep hazard rows as (event position, step, label) only. Features are looked up by event
position at fit time, never replicated 20 times. Logistic: compute the linear predictor once per event
(X_event @ w), add the step intercept per hazard row, and accumulate gradients back per event. Same
likelihood as the expanded design." Equivalence rule for model code not yet written: "prove it against
the naive version on a labelled smoke-test subset: same objective value and coefficients within stated
float tolerance."

Proves research/model/hazard_logistic.py's hazard_nll_grad -- the SHIPPED function S1 (docs/prompts/
HL_MODEL1_S1_LOGISTIC.md) imports and fits against ("the B5-proved per-event logistic core") -- checker's
round-1 finding: a copy defined inside this script would prove nothing about what S1 actually runs.
hazard_logistic.py's own docstring says this proof must be rerun if that file changes.

NOT the S1 scoring build (that is a separate, already-approved brief with its own regularisation,
standardisation and preprocessing rules). This script proves ONLY the computational trick: that skipping
the (event x step) row expansion computes the IDENTICAL discrete-time hazard log-likelihood and gradient
as the naive expanded design, at arbitrary weights, and converges to the same optimum under the same
unregularised fit. No penalty, no standardisation here -- those are S1's job on top of a core already
proven correct.

NAIVE (the explicit, wasteful baseline -- what the brief says NOT to ship, and the ONLY thing defined in
this script, independent of hazard_logistic.py): materialises X_rows, one row per HAZARD ROW, by indexing
X at each row's event position (REPLICATES a 20-step event's feature vector up to 20 times) plus a
one-hot step design S_rows (n_rows x 20). z = X_rows @ w + S_rows @ b.

PROOF 1: NLL and BOTH gradients (w, b) from hazard_nll_grad match the naive version EXACTLY (not a
tolerance -- this is an algebraic identity, not an approximation) at several random (w, b), on a labelled
smoke subset.
PROOF 2: optimising both (scipy.optimize.minimize, L-BFGS-B, identical start point and settings) reaches
the same NLL and the same coefficients within the STATED tolerance (checker's round-1 finding: the first
version checked coef_diff against TOL_FIT*10 while claiming TOL_FIT -- fixed to check the stated value
directly). Both fits must converge (res.success) with nit < maxiter, logged explicitly -- two runs that
both merely hit maxiter would "match" without either having found the real optimum.

ROUND 2 (planner ruling, option (a), after this proof's first real run genuinely FAILED PROOF 2 on real
data: |nll diff|=5.75e-04, max|coef diff|=5.41e-03, both over TOL_FIT=1e-4, even though PROOF 1 already
showed the two objectives identical to 1e-10-1e-13 at arbitrary points -- kept as
b5_hazard_logistic_proof_fail1.log). The checker traced it to L-BFGS-B's DEFAULT stop criteria (ftol
~2.2e-9 relative, gtol ~1e-5) letting an unstandardised, real-scale fit quit about 6e-4 above the true
optimum -- the test was asking for a closer match than the default solver settings actually reach, not
evidence of a wrong objective. Fix (same TOL_FIT=1e-4, same unstandardised columns, per the ruling): both
fits now use tight solver settings (ftol 1e-15, gtol 1e-10, maxiter/maxfun 15,000) to drive them to the
TRUE optimum instead of the solver's default early stop. Each solution's max-abs gradient and res.message
are logged, plus a cross-check evaluating each solution's NLL under BOTH naive_nll_grad and
hazard_nll_grad (a free check that the two objectives still agree AT the optimum, not only along the
path). If PROOF 2 still fails under these settings, the script stops and reports it -- per the ruling, no
further tolerance or solver adjustment happens in this script.
BROKEN VARIANT: hazard_nll_grad's own break_intercept=True flag (exercising the SHIPPED function, not a
reimplementation) skips the step-intercept add -- PROOF 1's exact-match check must then FAIL.
"""
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402
from hazard_logistic import hazard_nll_grad, sigmoid  # noqa: E402 -- the SHIPPED function, not a copy

SEED = 20261027
N_SMOKE_EVENTS = 3000
SMOKE_COLS = ["z", "threshold", "beta", "beta_stab", "r2"]  # a handful of real IN numeric columns
N_STEPS = H.N_STEPS  # 20
RTOL_EXACT = 1e-9   # PROOF 1: an algebraic identity, near machine precision, not a loose tolerance
TOL_FIT = 1e-4       # PROOF 2: stated tolerance for the optimised coefficients and NLL -- checked directly

PASS = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    PASS.append(cond)
    print(f"[B5-LOGISTIC] {name}: {status}" + (f" -- {detail}" if detail else ""), flush=True)
    return cond


def naive_nll_grad(w, b, X, row_event_pos, row_step, row_label):
    """The explicit, wasteful baseline: replicates each event's feature row once per its hazard rows via
    X_rows = X[row_event_pos] (exactly what the brief says not to ship), one-hot step design S_rows.
    Deliberately independent of hazard_logistic.py -- defined only here, never imported by it."""
    X_rows = X[row_event_pos]                       # (n_rows, n_features) -- REPLICATED, this is the cost
    S_rows = np.zeros((len(row_step), N_STEPS))
    S_rows[np.arange(len(row_step)), row_step - 1] = 1.0
    z = X_rows @ w + S_rows @ b
    p = sigmoid(z)
    y = row_label.astype(np.float64)
    eps = 1e-12
    nll = -np.sum(y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps))
    resid = p - y
    grad_w = X_rows.T @ resid
    grad_b = S_rows.T @ resid
    return nll, grad_w, grad_b


def load_smoke_subset():
    events = H.load_search_events()
    folds = H.build_folds(events)
    test_ids = folds[0]["test_ids"]
    rng = np.random.default_rng(SEED)
    chosen = rng.choice(test_ids, size=min(N_SMOKE_EVENTS, len(test_ids)), replace=False)
    chosen = np.sort(chosen)
    X, cols = H.load_features_cached(chosen, SMOKE_COLS)
    n_nan_per_col = {c: int(np.isnan(X[:, j]).sum()) for j, c in enumerate(cols)}
    print(f"[B5-LOGISTIC] NaN count per smoke column BEFORE fill: {n_nan_per_col}", flush=True)
    X = np.nan_to_num(X, nan=0.0).astype(np.float64)  # NaN handling is S1's job; this proof needs a clean X
    hazard = H.build_hazard_rows(events.loc[chosen])
    event_pos = {eid: i for i, eid in enumerate(chosen)}
    row_event_pos = hazard["event_id"].map(event_pos).to_numpy()
    row_step = hazard["step"].to_numpy()
    row_label = hazard["label"].to_numpy()
    return X, cols, chosen, row_event_pos, row_step, row_label


def proof_1_exact_match(X, row_event_pos, row_step, row_label, n_events):
    n_feat = X.shape[1]
    rng = np.random.default_rng(SEED + 1)
    all_ok = True
    for trial in range(5):
        w = rng.normal(scale=0.3, size=n_feat)
        b = rng.normal(scale=0.3, size=N_STEPS)
        nll_n, gw_n, gb_n = naive_nll_grad(w, b, X, row_event_pos, row_step, row_label)
        nll_e, gw_e, gb_e = hazard_nll_grad(w, b, X, row_event_pos, row_step, row_label, n_events)
        ok = (np.isclose(nll_n, nll_e, rtol=RTOL_EXACT)
              and np.allclose(gw_n, gw_e, rtol=RTOL_EXACT, atol=1e-9)
              and np.allclose(gb_n, gb_e, rtol=RTOL_EXACT, atol=1e-9))
        print(f"[B5-LOGISTIC]   trial {trial}: nll naive={nll_n:.6f} shipped={nll_e:.6f} "
              f"max|grad_w diff|={np.max(np.abs(gw_n-gw_e)):.2e} max|grad_b diff|={np.max(np.abs(gb_n-gb_e)):.2e}: "
              f"{'OK' if ok else 'MISMATCH'}", flush=True)
        all_ok = all_ok and ok
    check("PROOF 1 -- NLL and both gradients match the naive expanded design EXACTLY at 5 random (w,b)",
          all_ok)


def broken_variant(X, row_event_pos, row_step, row_label, n_events):
    rng = np.random.default_rng(SEED + 2)
    w = rng.normal(scale=0.3, size=X.shape[1])
    b = rng.normal(scale=0.3, size=N_STEPS)
    nll_n, gw_n, gb_n = naive_nll_grad(w, b, X, row_event_pos, row_step, row_label)
    nll_bad, gw_bad, gb_bad = hazard_nll_grad(w, b, X, row_event_pos, row_step, row_label, n_events,
                                               break_intercept=True)
    mismatch = not (np.isclose(nll_n, nll_bad, rtol=RTOL_EXACT)
                     and np.allclose(gw_n, gw_bad, rtol=RTOL_EXACT, atol=1e-9))
    check("BROKEN VARIANT -- hazard_nll_grad's own break_intercept=True (the SHIPPED function, not a "
          "reimplementation) makes PROOF 1's exact-match check FAIL",
          mismatch, f"nll naive={nll_n:.4f} broken={nll_bad:.4f}")


def proof_2_fit_match(X, row_event_pos, row_step, row_label, n_events):
    import scipy.optimize as opt
    n_feat = X.shape[1]
    theta0 = np.zeros(n_feat + N_STEPS)

    def naive_obj(theta):
        w, b = theta[:n_feat], theta[n_feat:]
        nll, gw, gb = naive_nll_grad(w, b, X, row_event_pos, row_step, row_label)
        return nll, np.concatenate([gw, gb])

    def shipped_obj(theta):
        w, b = theta[:n_feat], theta[n_feat:]
        nll, gw, gb = hazard_nll_grad(w, b, X, row_event_pos, row_step, row_label, n_events)
        return nll, np.concatenate([gw, gb])

    # Planner ruling 2026-10-27 (option (a), after the checker traced the first FAIL to L-BFGS-B's default
    # stop criteria letting an unstandardised fit quit ~6e-4 above the true optimum): same proof, same
    # TOL_FIT=1e-4, but drive BOTH fits to the true optimum with tight solver settings instead of the
    # earlier maxiter-doubling retry (dropped, no longer needed at this maxiter).
    maxiter = 15000
    opts = {"maxiter": maxiter, "maxfun": maxiter, "ftol": 1e-15, "gtol": 1e-10}
    t0 = time.time()
    res_n = opt.minimize(naive_obj, theta0, jac=True, method="L-BFGS-B", options=opts)
    t_naive = time.time() - t0
    t0 = time.time()
    res_e = opt.minimize(shipped_obj, theta0, jac=True, method="L-BFGS-B", options=opts)
    t_shipped = time.time() - t0
    both_converged = res_n.success and res_e.success and res_n.nit < maxiter and res_e.nit < maxiter

    pg_n = np.max(np.abs(res_n.jac))
    pg_e = np.max(np.abs(res_e.jac))
    print(f"[B5-LOGISTIC]   naive: nll={res_n.fun:.8f} iters={res_n.nit}/{maxiter} converged={res_n.success} "
          f"message={res_n.message!r} max|grad|={pg_n:.3e} time={t_naive:.2f}s", flush=True)
    print(f"[B5-LOGISTIC]   shipped: nll={res_e.fun:.8f} iters={res_e.nit}/{maxiter} converged={res_e.success} "
          f"message={res_e.message!r} max|grad|={pg_e:.3e} time={t_shipped:.2f}s", flush=True)

    # Cross-check (checker's spec): each solution's NLL evaluated by BOTH objectives -- a free check that
    # the two formulations still agree AT the optimum, not just that each solver thinks it converged.
    w_n, b_n = res_n.x[:n_feat], res_n.x[n_feat:]
    w_e, b_e = res_e.x[:n_feat], res_e.x[n_feat:]
    nll_n_by_naive, _, _ = naive_nll_grad(w_n, b_n, X, row_event_pos, row_step, row_label)
    nll_n_by_shipped, _, _ = hazard_nll_grad(w_n, b_n, X, row_event_pos, row_step, row_label, n_events)
    nll_e_by_naive, _, _ = naive_nll_grad(w_e, b_e, X, row_event_pos, row_step, row_label)
    nll_e_by_shipped, _, _ = hazard_nll_grad(w_e, b_e, X, row_event_pos, row_step, row_label, n_events)
    print(f"[B5-LOGISTIC]   cross-check at naive's solution: naive_obj={nll_n_by_naive:.8f} "
          f"shipped_obj={nll_n_by_shipped:.8f} (diff {abs(nll_n_by_naive-nll_n_by_shipped):.2e})", flush=True)
    print(f"[B5-LOGISTIC]   cross-check at shipped's solution: naive_obj={nll_e_by_naive:.8f} "
          f"shipped_obj={nll_e_by_shipped:.8f} (diff {abs(nll_e_by_naive-nll_e_by_shipped):.2e})", flush=True)

    # Checker's finding: possible separation (a step with ~0 label-1 rows, whose unpenalised intercept has
    # no finite optimum and drifts toward -inf, so two runs can stop at different very negative b_k with
    # the SAME NLL -- that is separation, not a code fault). These two lines report, not decide; no check
    # changes as a result of them.
    w_diff = np.max(np.abs(w_n - w_e))
    b_diff = np.max(np.abs(b_n - b_e))
    print(f"[B5-LOGISTIC]   max|w diff|={w_diff:.3e} max|b diff|={b_diff:.3e}", flush=True)
    print(f"[B5-LOGISTIC]   naive b:   {np.array2string(b_n, precision=4, max_line_width=200)}", flush=True)
    print(f"[B5-LOGISTIC]   shipped b: {np.array2string(b_e, precision=4, max_line_width=200)}", flush=True)
    rows_per_step = np.bincount(row_step - 1, minlength=N_STEPS)
    label1_per_step = np.bincount(row_step - 1, weights=row_label.astype(np.float64), minlength=N_STEPS)
    print(f"[B5-LOGISTIC]   hazard rows per step:  {rows_per_step.tolist()}", flush=True)
    print(f"[B5-LOGISTIC]   label=1 rows per step: {label1_per_step.astype(int).tolist()}", flush=True)

    check("PROOF 2 pre-check -- both fits converged below maxiter (not two runs both stopped at the cap)",
          both_converged, f"naive nit={res_n.nit}/{maxiter} success={res_n.success}; "
                           f"shipped nit={res_e.nit}/{maxiter} success={res_e.success}")

    nll_diff = abs(res_n.fun - res_e.fun)
    coef_diff = np.max(np.abs(res_n.x - res_e.x))
    ok2 = check(f"PROOF 2 -- optimised NLL and coefficients match within the STATED tolerance "
                f"(|nll diff|={nll_diff:.2e} < {TOL_FIT:.0e}, max|coef diff|={coef_diff:.2e} < {TOL_FIT:.0e})",
                nll_diff < TOL_FIT and coef_diff < TOL_FIT)
    if not ok2:
        print("[B5-LOGISTIC]   PROOF 2 FAILED under tight solver settings -- per the planner's ruling, "
              "STOP here, report to the planner, no further adjustment in this script.", flush=True)


def main():
    t0 = time.time()
    import master_manifest as MF
    print(f"[B5-LOGISTIC] sha256 {os.path.basename(__file__)}: {MF.sha(os.path.abspath(__file__))}", flush=True)
    print(f"[B5-LOGISTIC] sha256 hazard_logistic.py: {MF.sha(os.path.join(HERE, 'hazard_logistic.py'))}",
          flush=True)
    print(f"[B5-LOGISTIC] sha256 harness.py: {MF.sha(os.path.join(HERE, 'harness.py'))}", flush=True)
    print(f"[B5-LOGISTIC] sha256 inputs_v1_pair.csv: {MF.sha(os.path.join(HERE, 'inputs_v1_pair.csv'))} "
          f"(must be 91cb311c74a2970144e9e2656faf71acce75c422dcf0c404512eb0560a2c0bcf)", flush=True)
    print(f"[B5-LOGISTIC] sha256 coins.csv: {MF.sha(H.COINS_CSV)}", flush=True)
    cache_info = H._cache_info()
    cache_sha = cache_info.get("cache_sha256", "NO VALID CACHE -- load_features_cached would raise") \
        if cache_info else "NO VALID CACHE -- load_features_cached would raise"
    print(f"[B5-LOGISTIC] cache manifest cache_sha256: {cache_sha} "
          f"(must be bd5dc2549374d0a80c8b042425e34119289b17b753a49213ac28c1831c6ca544)", flush=True)
    gs = os.path.join(os.path.dirname(HERE), "dataset", "GIT_STATE.json")
    git_head, git_dirty = ("unavailable", "unavailable")
    if os.path.exists(gs):
        G = MF.json.load(open(gs))
        git_head, git_dirty = G.get("head", "unavailable"), len(G.get("porcelain", []))
    print(f"[B5-LOGISTIC] git_head {git_head} ({git_dirty} uncommitted paths); "
          f"start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC; pid {os.getpid()}", flush=True)
    print(f"[B5-LOGISTIC] smoke subset: {N_SMOKE_EVENTS} events (seed {SEED}), columns {SMOKE_COLS}, "
          f"{N_STEPS} steps. NOT the S1 scoring build -- proves only the no-row-copy computational trick, "
          f"unpenalised, no standardisation.", flush=True)

    X, cols, chosen, row_event_pos, row_step, row_label = load_smoke_subset()
    n_events = len(chosen)
    print(f"[B5-LOGISTIC] loaded {n_events} events x {len(cols)} cols, {len(row_event_pos):,} hazard rows "
          f"[{time.time()-t0:.0f}s]", flush=True)

    proof_1_exact_match(X, row_event_pos, row_step, row_label, n_events)
    broken_variant(X, row_event_pos, row_step, row_label, n_events)
    proof_2_fit_match(X, row_event_pos, row_step, row_label, n_events)

    print(f"[B5-LOGISTIC] all done [{time.time()-t0:.0f}s]: {sum(PASS)}/{len(PASS)} checks PASS", flush=True)
    if not all(PASS):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
