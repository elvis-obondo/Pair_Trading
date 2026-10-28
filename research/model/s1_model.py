"""HL-MODEL1 S1: penalised discrete-time hazard logistic -- elastic-net fit via FISTA.

R6 fixes the objective (hazard_logistic.hazard_nll_grad, the B5-proved core: no row expansion, eta = X@w
computed once per event) and the convergence rule (relative objective change < 1e-7, or at most 2,000
iterations), but not the optimiser. L-BFGS-B -- used for B5's unpenalised proof -- cannot be used here: the
elastic net's L1 term is non-differentiable at zero, so a smooth-gradient method has no valid gradient at
a coefficient that should shrink to exactly zero. FISTA (accelerated proximal gradient, Beck & Teboulle
2009, with backtracking since this design's Lipschitz constant has no simple closed form) is the standard
choice for L1/elastic-net penalised GLMs for exactly this reason. Only `w` (the standardised inputs, one-
hot coins, missing indicators) is penalised and goes through the proximal (shrinkage) step; the 20 step
intercepts `b` are unpenalised and move by a plain gradient step in the same loop (R6). Warm-starting the
next penalty's FISTA from the previous penalty's (w, b) is R3's "warm-started along the path" -- the
caller passes w0/b0, this module does not manage the path itself.

SPLIT-WEIGHT L-BFGS-B (checker/planner ruling, S1 review round 1): FISTA is only acceptable if it is shown
to reach the optimum, and a fallback is needed for any grid point where it does not within the 2,000-iter
cap. `fit_hazard_elastic_net_lbfgsb` reparameterises w = u - v with u, v >= 0: the L1 term lambda*l1_ratio*
|w_j| becomes the LINEAR lambda*l1_ratio*(u_j+v_j) (exact at any optimum, since u_j and v_j are never both
positive there), and the L2 term stays the smooth quadratic lambda*(1-l1_ratio)*0.5*(u_j-v_j)^2. The whole
objective is then smooth everywhere with simple box constraints (u,v >= 0, b free) -- exactly what L-BFGS-B
needs, and it reuses hazard_nll_grad (the proven core) unchanged, only the wrapping around it differs.
`kkt_violation` checks any candidate solution (from either optimiser) against the exact KKT stationarity
conditions of the SAME penalised objective, independent of how it was reached.

A float32 "fast path" (hazard_nll_grad_fast) was tried after the one-fit probe measured ~67s per function
evaluation, and REJECTED by the planner, S1 review round 5: it matched the exact objective and KKT on real
smoke data, but individual event-level predictions (p_10h) diverged beyond the stated tolerance at both
grid points tested. Deleted, not left behind as a parallel path -- both optimisers call the EXACT
hazard_nll_grad again, which is now itself threaded across event-row chunks (see hazard_logistic.py's
module docstring) to remove the real bottleneck (the unthreaded float64 cast) without changing any number.
"""
import time

import numpy as np
import scipy.optimize as opt

from hazard_logistic import hazard_nll_grad


def elastic_net_penalty(w, lam, l1_ratio):
    return lam * (l1_ratio * np.sum(np.abs(w)) + 0.5 * (1 - l1_ratio) * np.sum(w ** 2))


def _prox(w, step, lam, l1_ratio):
    thresh = step * lam * l1_ratio
    shrunk = np.sign(w) * np.maximum(np.abs(w) - thresh, 0.0)
    return shrunk / (1.0 + step * lam * (1 - l1_ratio))


def null_step_intercepts(row_step, row_label, n_steps=20):
    """Closed-form unpenalised MLE of the step intercepts alone (w=0): with no features, z_ik = b_k for
    every row of step k, so each step's rows are iid Bernoulli(sigmoid(b_k)) and b_k = logit(mean label
    at step k). Used only to build the null model lambda_max is measured against."""
    label1 = np.bincount(row_step - 1, weights=row_label.astype(np.float64), minlength=n_steps)
    n = np.bincount(row_step - 1, minlength=n_steps).astype(np.float64)
    eps = 1e-10
    p = np.clip(label1 / n, eps, 1 - eps)
    return np.log(p / (1 - p))


def lambda_max(X, row_event_pos, row_step, row_label, n_events, l1_ratio, n_steps=20):
    """R3: 'lambda_max computed on the fold's train rows.' Standard elastic-net definition: the smallest
    lambda whose L1 subgradient test keeps every w_j at exactly 0 from the null model (w=0, b=the closed-
    form step-intercept MLE) -- max_j|grad_w_j| / l1_ratio."""
    b0 = null_step_intercepts(row_step, row_label, n_steps)
    w0 = np.zeros(X.shape[1])
    _, gw, _ = hazard_nll_grad(w0, b0, X, row_event_pos, row_step, row_label, n_events)
    return float(np.max(np.abs(gw)) / l1_ratio)


def build_grid(lam_max, n=8, hi_frac=0.5, lo_frac=1e-3):
    """R3: 8 penalties log-spaced from 0.5 x lambda_max down to 1e-3 x lambda_max."""
    return np.geomspace(hi_frac * lam_max, lo_frac * lam_max, n)


def fit_hazard_elastic_net(X, row_event_pos, row_step, row_label, n_events, lam, l1_ratio,
                            w0=None, b0=None, n_steps=20, max_iter=2000, tol=1e-7, step_init=1.0):
    """FISTA with backtracking. Returns a dict: w, b, n_iter, converged (relative objective change < tol
    before max_iter), obj_final. `w0`/`b0` (default: zeros) are the warm start -- the caller supplies the
    previous penalty's solution to implement R3's warm-started path; this function does not know about the
    grid or the path, only about one fit."""
    n_feat = X.shape[1]
    w = np.zeros(n_feat) if w0 is None else np.asarray(w0, dtype=np.float64).copy()
    b = np.zeros(n_steps) if b0 is None else np.asarray(b0, dtype=np.float64).copy()
    step = step_init
    y_w = w.copy()
    t_prev = 1.0

    def full_obj(w_, b_):
        nll, _, _ = hazard_nll_grad(w_, b_, X, row_event_pos, row_step, row_label, n_events)
        return nll + elastic_net_penalty(w_, lam, l1_ratio)

    obj_prev = full_obj(w, b)
    converged = False
    n_iter = 0
    for it in range(1, max_iter + 1):
        nll_y, gw, gb = hazard_nll_grad(y_w, b, X, row_event_pos, row_step, row_label, n_events)
        while True:
            w_new = _prox(y_w - step * gw, step, lam, l1_ratio)
            b_new = b - step * gb
            nll_new, _, _ = hazard_nll_grad(w_new, b_new, X, row_event_pos, row_step, row_label, n_events)
            diff = w_new - y_w
            quad = nll_y + gw @ diff + (1.0 / (2 * step)) * np.sum(diff ** 2)
            if nll_new <= quad + 1e-12 or step < 1e-12:
                break
            step *= 0.5
        t_new = (1 + np.sqrt(1 + 4 * t_prev ** 2)) / 2
        y_w = w_new + ((t_prev - 1) / t_new) * (w_new - w)
        w, b, t_prev = w_new, b_new, t_new
        obj_new = full_obj(w, b)
        n_iter = it
        rel_change = abs(obj_prev - obj_new) / max(abs(obj_prev), 1e-12)
        obj_prev = obj_new
        if rel_change < tol:
            converged = True
            break
        step = min(step * 1.5, step_init)
    return {"w": w, "b": b, "n_iter": n_iter, "converged": converged, "obj_final": obj_prev}


def fit_hazard_elastic_net_lbfgsb(X, row_event_pos, row_step, row_label, n_events, lam, l1_ratio,
                                   w0=None, b0=None, n_steps=20, max_iter=2000, tol=1e-7,
                                   log_every=None, log_prefix=""):
    """Split-weight (w = u - v, u,v >= 0) L-BFGS-B fit of the SAME penalised objective as
    fit_hazard_elastic_net -- see the module docstring. Returns the same dict shape (w, b, n_iter,
    converged, obj_final), plus n_calls (the number of obj_grad evaluations -- line search inside one
    L-BFGS-B iteration can call it more than once, so this can exceed n_iter; checker's ruling, S1 review
    round 5, to tell seconds-per-iteration apart from seconds-per-evaluation on a slow fit). `tol` maps to
    L-BFGS-B's `ftol` (relative objective reduction), matching R6's 'relative objective change < tol' as
    closely as scipy's own stopping rule allows; `max_iter` maps to both `maxiter` and `maxfun` (a tight
    cap can otherwise stop on function evaluations before iterations, silently).

    `log_every`, if set, prints wall time / objective / max|grad| every that many ITERATIONS (via scipy's
    own callback, called once per accepted step, not per line-search evaluation) -- planner's ruling, S1
    review round 5: a run that gets killed before finishing must still say how many iterations happened
    in how much time, which the previous (log-nothing-until-return) version could not."""
    n_feat = X.shape[1]
    w_start = np.zeros(n_feat) if w0 is None else np.asarray(w0, dtype=np.float64)
    b_start = np.zeros(n_steps) if b0 is None else np.asarray(b0, dtype=np.float64)
    u0 = np.maximum(w_start, 0.0)
    v0 = np.maximum(-w_start, 0.0)
    theta0 = np.concatenate([u0, v0, b_start])
    bounds = [(0, None)] * (2 * n_feat) + [(None, None)] * n_steps

    state = {"obj": None, "grad": None, "n_calls": 0}

    def obj_grad(theta):
        u, v, b = theta[:n_feat], theta[n_feat:2 * n_feat], theta[2 * n_feat:]
        w = u - v
        nll, gw, gb = hazard_nll_grad(w, b, X, row_event_pos, row_step, row_label, n_events)
        obj = nll + lam * l1_ratio * np.sum(u + v) + 0.5 * lam * (1 - l1_ratio) * np.sum(w ** 2)
        l2_term = lam * (1 - l1_ratio) * w
        g_u = gw + lam * l1_ratio + l2_term
        g_v = -gw + lam * l1_ratio - l2_term
        state["obj"], state["grad"], state["n_calls"] = obj, (g_u, g_v, gb), state["n_calls"] + 1
        return obj, np.concatenate([g_u, g_v, gb])

    t_start = time.time()
    iter_count = [0]

    def callback(xk):
        iter_count[0] += 1
        if log_every and iter_count[0] % log_every == 0:
            gnorm = float(np.max(np.abs(np.concatenate(state["grad"])))) if state["grad"] is not None \
                else float("nan")
            print(f"{log_prefix} iter={iter_count[0]} n_calls={state['n_calls']} "
                  f"wall={time.time()-t_start:.2f}s obj={state['obj']:.6f} "
                  f"max|grad|={gnorm:.3e}", flush=True)

    res = opt.minimize(obj_grad, theta0, jac=True, method="L-BFGS-B", bounds=bounds,
                        options={"maxiter": max_iter, "maxfun": max_iter * 4, "ftol": tol, "gtol": 1e-10},
                        callback=callback if log_every else None)
    u, v, b = res.x[:n_feat], res.x[n_feat:2 * n_feat], res.x[2 * n_feat:]
    w = u - v
    converged = bool(res.success) and res.nit < max_iter
    return {"w": w, "b": b, "n_iter": int(res.nit), "n_calls": state["n_calls"], "converged": converged,
            "obj_final": float(res.fun)}


def kkt_violation(w, b, lam, l1_ratio, X, row_event_pos, row_step, row_label, n_events):
    """Checker's spec: the exact KKT stationarity conditions of the elastic-net objective, independent of
    which optimiser produced (w, b) -- grad_b ~ 0 (b unpenalised); for w_j != 0, |g_j + lambda*(1-l1_ratio)
    *w_j + lambda*l1_ratio*sign(w_j)| small; for w_j == 0, |g_j| <= lambda*l1_ratio. Each violation is
    scaled by n_rows (the hazard-row count), since the raw gradients are sums over that many rows and would
    otherwise not be comparable across fits of different sizes. Returns the max violation on each side and
    overall."""
    n_rows = len(row_step)
    _, gw, gb = hazard_nll_grad(w, b, X, row_event_pos, row_step, row_label, n_events)
    b_violation = float(np.max(np.abs(gb))) / n_rows if len(gb) else 0.0
    nonzero = w != 0
    w_viol_nonzero = 0.0
    if nonzero.any():
        stat = gw[nonzero] + lam * (1 - l1_ratio) * w[nonzero] + lam * l1_ratio * np.sign(w[nonzero])
        w_viol_nonzero = float(np.max(np.abs(stat)))
    zero = ~nonzero
    w_viol_zero = 0.0
    if zero.any():
        excess = np.abs(gw[zero]) - lam * l1_ratio
        w_viol_zero = float(max(0.0, np.max(excess)))
    w_violation = max(w_viol_nonzero, w_viol_zero) / n_rows
    return {"b_violation": b_violation, "w_violation_nonzero": w_viol_nonzero / n_rows,
            "w_violation_zero": w_viol_zero / n_rows, "max_violation": max(b_violation, w_violation)}
