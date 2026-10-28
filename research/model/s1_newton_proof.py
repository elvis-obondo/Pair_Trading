"""HL-MODEL1 S1: proximal Newton proof against TIGHT exact L-BFGS-B (planner's ruling, S1 review round 6:
"Proof on the smoke data against the exact L-BFGS-B driven tight: exact objective within 1e-6 relative,
KKT within the agreed bound, predictions within 1e-3 at the middle and lowest penalties, plus a failing
variant"). L-BFGS-B here is run to the SAME tight settings B5's own proof used (ftol=1e-15, maxiter=
15000) specifically to find the TRUE optimum Newton is checked against -- this is a different job from
the real S1 run's own settings, same distinction s1_model_proof.py/s1_hazard_fast_proof.py already drew.

    python -u research/model/s1_newton_proof.py > research/model/logs/s1_newton_proof.log

On real standardised smoke data, at the MIDDLE (grid[4]) and LOWEST (grid[7]) penalties: fits with
s1_newton.fit_hazard_elastic_net_newton (cold start, R6's own stopping rule, tol=1e-7, max_outer=50) and
separately with s1_model.fit_hazard_elastic_net_lbfgsb driven tight (the true optimum). Both solutions are
scored under the EXACT objective (hazard_nll_grad + the elastic-net penalty). PASS requires: rel|obj
diff| < 1e-6, Newton's exact-gradient KKT <= max(10 x the tight L-BFGS-B's own KKT, 1e-4), and
max|p_10h diff| <= 1e-3 with top-10% overlap >= 99% on the smoke events. w diff is reported, never gated
(flat L1 directions don't identify coefficients -- S1 review round 5's own finding). A FAILING VARIANT
(Newton's own break_grad=True, negating grad_w into an ascent direction the line search cannot rescue)
must make the check FAIL. break_cross=True (zeroing the w/b cross-Hessian block) is ALSO run and reported
but not gated on -- the checker found it changes the trajectory (14 outer iterations instead of 7) without
changing the final answer on real data, so it is not a reliable failing variant here even though it is a
genuine code difference; kept as a reported finding, not the proof's failing case.

fit_hazard_elastic_net_lbfgsb lives HERE, not in s1_model.py (planner's ruling, S1 review round 6,
after Newton was proven): it is retired from the real run path and kept only as this proof's own tight
reference optimiser, so the real-run code has a single solver path (Newton).
"""
import os
import sys
import time

import numpy as np
import scipy.optimize as opt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402
from hazard_logistic import hazard_nll_grad  # noqa: E402
from s1_preprocess import fit_preprocessing, apply_preprocessing  # noqa: E402
from s1_model import lambda_max, build_grid, kkt_violation  # noqa: E402
from s1_newton import fit_hazard_elastic_net_newton, elastic_net_penalty  # noqa: E402


def fit_hazard_elastic_net_lbfgsb(X, row_event_pos, row_step, row_label, n_events, lam, l1_ratio,
                                   w0=None, b0=None, n_steps=20, max_iter=2000, tol=1e-7):
    """Split-weight (w = u - v, u,v >= 0) L-BFGS-B fit of the SAME penalised objective as the proven
    Newton solver -- this proof's TIGHT reference optimiser only, retired from the real run path. L1 term
    lambda*l1_ratio*|w_j| becomes the LINEAR lambda*l1_ratio*(u_j+v_j) (exact at any optimum, since u_j
    and v_j are never both positive there); the L2 term stays the smooth quadratic. Reuses hazard_nll_grad
    (the proven core) unchanged, only the wrapping differs."""
    n_feat = X.shape[1]
    w_start = np.zeros(n_feat) if w0 is None else np.asarray(w0, dtype=np.float64)
    b_start = np.zeros(n_steps) if b0 is None else np.asarray(b0, dtype=np.float64)
    u0 = np.maximum(w_start, 0.0)
    v0 = np.maximum(-w_start, 0.0)
    theta0 = np.concatenate([u0, v0, b_start])
    bounds = [(0, None)] * (2 * n_feat) + [(None, None)] * n_steps

    def obj_grad(theta):
        u, v, b = theta[:n_feat], theta[n_feat:2 * n_feat], theta[2 * n_feat:]
        w = u - v
        nll, gw, gb = hazard_nll_grad(w, b, X, row_event_pos, row_step, row_label, n_events)
        obj = nll + lam * l1_ratio * np.sum(u + v) + 0.5 * lam * (1 - l1_ratio) * np.sum(w ** 2)
        l2_term = lam * (1 - l1_ratio) * w
        g_u = gw + lam * l1_ratio + l2_term
        g_v = -gw + lam * l1_ratio - l2_term
        return obj, np.concatenate([g_u, g_v, gb])

    res = opt.minimize(obj_grad, theta0, jac=True, method="L-BFGS-B", bounds=bounds,
                        options={"maxiter": max_iter, "maxfun": max_iter * 4, "ftol": tol, "gtol": 1e-10})
    u, v, b = res.x[:n_feat], res.x[n_feat:2 * n_feat], res.x[2 * n_feat:]
    w = u - v
    converged = bool(res.success) and res.nit < max_iter
    return {"w": w, "b": b, "n_iter": int(res.nit), "converged": converged, "obj_final": float(res.fun)}

SEED = 20261028
N_SMOKE_EVENTS = 20_000
SMOKE_COLS = ["z", "threshold", "beta", "beta_stab", "r2", "ticker_a", "ticker_b"]
N_STEPS = H.N_STEPS
L1_RATIO = 0.5
TOL_OBJ = 1e-6
PASS = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    PASS.append(cond)
    print(f"[S1-NEWTON-PROOF] {name}: {status}" + (f" -- {detail}" if detail else ""), flush=True)
    return cond


def exact_obj(w, b, lam, l1_ratio, X, row_event_pos, row_step, row_label, n_events):
    nll, _, _ = hazard_nll_grad(w, b, X, row_event_pos, row_step, row_label, n_events)
    return nll + elastic_net_penalty(w, lam, l1_ratio)


def compute_p10h(w, b, X, n_steps=20):
    eta = X.astype(np.float64) @ np.asarray(w, dtype=np.float64)
    h = 1.0 / (1.0 + np.exp(-(eta[:, None] + np.asarray(b, dtype=np.float64)[None, :])))
    return 1.0 - np.prod(1.0 - h, axis=1)


def top10_overlap(p_a, p_b):
    n = len(p_a)
    n_top = max(1, int(np.ceil(0.10 * n)))
    top_a = set(np.argsort(-p_a)[:n_top].tolist())
    top_b = set(np.argsort(-p_b)[:n_top].tolist())
    return len(top_a & top_b) / n_top


def end_to_end_check(label, lam, X_fit, row_event_pos, row_step, row_label, n_events,
                      break_cross=False, break_grad=False, gate=True):
    t0 = time.time()
    r_newton = fit_hazard_elastic_net_newton(X_fit, row_event_pos, row_step, row_label, n_events,
                                              lam=lam, l1_ratio=L1_RATIO, tol=1e-7, max_outer=50,
                                              break_cross=break_cross, break_grad=break_grad)
    t_newton = time.time() - t0
    t0 = time.time()
    r_tight = fit_hazard_elastic_net_lbfgsb(X_fit, row_event_pos, row_step, row_label, n_events,
                                             lam=lam, l1_ratio=L1_RATIO, max_iter=15000, tol=1e-15)
    t_tight = time.time() - t0

    obj_newton = exact_obj(r_newton["w"], r_newton["b"], lam, L1_RATIO, X_fit, row_event_pos, row_step,
                            row_label, n_events)
    obj_tight = exact_obj(r_tight["w"], r_tight["b"], lam, L1_RATIO, X_fit, row_event_pos, row_step,
                           row_label, n_events)
    rel_obj_diff = abs(obj_newton - obj_tight) / max(abs(obj_tight), 1e-12)
    w_diff = float(np.max(np.abs(r_newton["w"] - r_tight["w"])))

    kkt_newton = kkt_violation(r_newton["w"], r_newton["b"], lam, L1_RATIO, X_fit, row_event_pos, row_step,
                                row_label, n_events)
    kkt_tight = kkt_violation(r_tight["w"], r_tight["b"], lam, L1_RATIO, X_fit, row_event_pos, row_step,
                               row_label, n_events)
    kkt_bound = max(10 * kkt_tight["max_violation"], 1e-4)

    p_newton = compute_p10h(r_newton["w"], r_newton["b"], X_fit)
    p_tight = compute_p10h(r_tight["w"], r_tight["b"], X_fit)
    max_p_diff = float(np.max(np.abs(p_newton - p_tight)))
    overlap = top10_overlap(p_newton, p_tight)

    print(f"[S1-NEWTON-PROOF] {label} (lam={lam:.6g}, break_cross={break_cross}, break_grad={break_grad}): "
          f"newton: n_outer={r_newton['n_iter']} converged={r_newton['converged']} time={t_newton:.2f}s | "
          f"tight L-BFGS-B: converged={r_tight['converged']} time={t_tight:.2f}s", flush=True)
    print(f"[S1-NEWTON-PROOF] {label}: exact-obj(newton)={obj_newton:.6f} exact-obj(tight)={obj_tight:.6f} "
          f"rel|diff|={rel_obj_diff:.3e}", flush=True)
    print(f"[S1-NEWTON-PROOF] {label}: KKT (exact gradient) newton={kkt_newton['max_violation']:.3e} "
          f"tight={kkt_tight['max_violation']:.3e} bound=max(10xtight,1e-4)={kkt_bound:.3e}", flush=True)
    print(f"[S1-NEWTON-PROOF] {label}: predictions max|p_10h diff|={max_p_diff:.3e} "
          f"top-10% overlap={overlap:.4f}", flush=True)
    print(f"[S1-NEWTON-PROOF] {label}: max|w diff|={w_diff:.3e} (REPORTED ONLY, not gated)", flush=True)

    gate1 = rel_obj_diff < TOL_OBJ
    gate2 = kkt_newton["max_violation"] <= kkt_bound
    gate3 = max_p_diff <= 1e-3 and overlap >= 0.99
    passed = gate1 and gate2 and gate3
    label_full = (f"{label} (break_cross={break_cross}, break_grad={break_grad}) -- "
                  f"objective rel|diff|<{TOL_OBJ:.0e} [{gate1}], KKT bound [{gate2}], "
                  f"predictions [{gate3}]")
    if gate:
        check(label_full, passed)
    else:
        print(f"[S1-NEWTON-PROOF] (not gated, reported only) {label_full}: "
              f"{'would PASS' if passed else 'would FAIL'}", flush=True)
    return passed


def main():
    t0 = time.time()
    import master_manifest as MF
    for name in ("s1_newton_proof.py", "s1_newton.py", "s1_model.py", "s1_preprocess.py",
                 "hazard_logistic.py", "harness.py"):
        print(f"[S1-NEWTON-PROOF] sha256 {name}: {MF.sha(os.path.join(HERE, name))}", flush=True)
    gs = os.path.join(os.path.dirname(HERE), "dataset", "GIT_STATE.json")
    git_head, git_dirty = ("unavailable", "unavailable")
    if os.path.exists(gs):
        G = MF.json.load(open(gs))
        git_head, git_dirty = G.get("head", "unavailable"), len(G.get("porcelain", []))
    print(f"[S1-NEWTON-PROOF] git_head {git_head} ({git_dirty} uncommitted paths); "
          f"start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC; pid {os.getpid()}", flush=True)

    events = H.load_search_events()
    folds = H.build_folds(events)
    test_ids = folds[0]["test_ids"]
    rng = np.random.default_rng(SEED)
    chosen = np.sort(rng.choice(test_ids, size=min(N_SMOKE_EVENTS, len(test_ids)), replace=False))
    hazard = H.build_hazard_rows(events.loc[chosen])
    event_pos = {eid: i for i, eid in enumerate(chosen)}
    row_event_pos = hazard["event_id"].map(event_pos).to_numpy()
    row_step = hazard["step"].to_numpy()
    row_label = hazard["label"].to_numpy()
    n_events = len(chosen)
    pos_per_step = np.bincount(row_step - 1, weights=row_label.astype(np.float64), minlength=N_STEPS)
    print(f"[S1-NEWTON-PROOF] smoke subset: {n_events} events (seed {SEED}), {len(row_event_pos):,} "
          f"hazard rows  [{time.time()-t0:.0f}s]", flush=True)
    print(f"[S1-NEWTON-PROOF] label=1 rows per step: {pos_per_step.astype(int).tolist()}", flush=True)
    assert (pos_per_step > 0).all(), "a step has zero label=1 rows -- separation risk"

    stats = fit_preprocessing(chosen, SMOKE_COLS)
    X_fit, out_cols = apply_preprocessing(chosen, SMOKE_COLS, stats)
    print(f"[S1-NEWTON-PROOF] preprocessed: n_features={len(out_cols)}  [{time.time()-t0:.0f}s]",
          flush=True)

    lam_max = lambda_max(X_fit, row_event_pos, row_step, row_label, n_events, L1_RATIO)
    grid = build_grid(lam_max, n=8)
    print(f"[S1-NEWTON-PROOF] lambda_max={lam_max:.6g} grid={np.array2string(grid, precision=4)}",
          flush=True)

    for idx, label in ((4, "MIDDLE"), (7, "LOWEST")):
        end_to_end_check(f"{label} penalty idx={idx}", grid[idx], X_fit, row_event_pos, row_step,
                          row_label, n_events, break_cross=False, break_grad=False)

    # break_cross: reported only, not gated -- see the module docstring's note (changes the trajectory,
    # not the final answer, on real data; not a reliable failing variant for THIS algorithm's design).
    end_to_end_check("MIDDLE penalty idx=4 (break_cross, informational)", grid[4], X_fit, row_event_pos,
                      row_step, row_label, n_events, break_cross=True, break_grad=False, gate=False)

    # break_grad: the proof's actual failing variant -- negates grad_w into an ascent direction the line
    # search cannot rescue.
    # gate=False here too (same reason as break_cross above): the raw match/mismatch is not itself one of
    # the proof's real checks -- only the META check below (did it correctly FAIL) is registered, same
    # precedent as b5_hazard_logistic_proof.py's own broken-variant check.
    broken_ok = end_to_end_check("MIDDLE penalty idx=4 (BROKEN VARIANT, break_grad)", grid[4], X_fit,
                                  row_event_pos, row_step, row_label, n_events,
                                  break_cross=False, break_grad=True, gate=False)
    check("BROKEN VARIANT -- Newton with break_grad=True correctly FAILS the check", not broken_ok)

    print(f"[S1-NEWTON-PROOF] all done [{time.time()-t0:.0f}s]: {sum(PASS)}/{len(PASS)} checks PASS",
          flush=True)
    if not all(PASS):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
