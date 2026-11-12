"""HL-MODEL1 S1: proximal Newton (IRLS + coordinate descent) solver for the penalised discrete-time
hazard objective -- the planner's ruling, S1 review round 6, after the AWS probe showed L-BFGS-B needs
2+ machines to clear the 24h gate while Newton can clear it on ONE machine in its best case.

OUTER LOOP (one per call to `fit_hazard_elastic_net_newton`'s iteration body): at the current (w, b),
build the exact objective's weighted Gram H_ww = X^T diag(d_i) X (d_i = sum over at-risk steps of
p_ik(1-p_ik), the SAME per-event aggregation pattern hazard_nll_grad's gradient already uses), the cross
block H_wb (features x step-intercepts) and the diagonal H_bb (step-intercepts only) -- together the exact
Hessian of the UNPENALISED NLL at (w, b). `b` is unpenalised, so it has a closed form given w via the
block's Schur complement: eliminating b turns the (w, b) quadratic into a w-only quadratic with an
EFFECTIVE Hessian H_eff = H_ww - H_wb diag(1/H_bb) H_wb^T and gradient g_eff = grad_w - H_wb (grad_b /
H_bb). This w-only quadratic plus the elastic-net penalty is solved by cyclic COORDINATE DESCENT (cheap
at p ~ 2.4k -- each coordinate's own Hessian diagonal gives its own Newton step size, and the elastic-net
proximal operator is the SAME one `s1_model.py`'s FISTA already uses, scaled per-coordinate instead of
uniformly). A backtracking LINE SEARCH on the EXACT objective (not the quadratic model) then scales the
full (w, b) step -- standard proximal-Newton safeguard against a quadratic model that overshoots.

`hazard_nll_grad` (the proven, unmodified B5/S1 core) supplies nll/grad_w/grad_b; this module only adds
the second-order pieces, in the SAME chunked, serial-Python/threaded-BLAS style as s1_gram_timing.py's
build_gram_ww (checker's "one parallel layer" principle, S1 review round 6).
"""
import time

import numpy as np
import threadpoolctl

from hazard_logistic import hazard_nll_grad, sigmoid

GRAM_BLAS_THREADS = 64   # measured on the r7i.16xlarge probe: 1.51s/chunk at 64 BLAS threads
GRAM_BUILD_BUDGET_S = 120.0   # 2x the probe's ~60s/outer-iteration -- checker's tripwire
_threadpool_info_logged = False
_first_gram_checked = False


class GramBuildTooSlow(RuntimeError):
    """Raised once, on the very first Gram build of the process, if it took more than
    GRAM_BUILD_BUDGET_S -- the checker's tripwire: the 24h/2-machine sizing assumed BLAS actually
    multithreads inside this scope (the r7i probe's measured ~60s/outer-iteration); if the machine isn't
    giving BLAS that speed (wrong instance type, BLAS not actually threaded, thermal throttling, ...),
    stop here rather than burn hours finding out fold by fold."""


def elastic_net_penalty(w, lam, l1_ratio):
    return lam * (l1_ratio * np.sum(np.abs(w)) + 0.5 * (1 - l1_ratio) * np.sum(w ** 2))


def _prox(z, step, lam, l1_ratio):
    thresh = step * lam * l1_ratio
    shrunk = np.sign(z) * np.maximum(np.abs(z) - thresh, 0.0)
    return shrunk / (1.0 + step * lam * (1 - l1_ratio))


def build_hessian_blocks(X, w, b, row_event_pos, row_step, row_label, n_events, n_steps=20,
                          chunk_size=100_000, gram_blas_threads=GRAM_BLAS_THREADS, log_prefix=""):
    """Returns (nll, grad_w, grad_b, H_ww, H_wb, H_bb) at the given (w, b). nll/grad_w/grad_b come
    straight from the proven hazard_nll_grad -- this function adds ONLY H_ww (n_feat x n_feat), H_wb
    (n_feat x n_steps) and H_bb (n_steps,), the exact Hessian of the unpenalised NLL. d_row = p_row(1-
    p_row) per hazard row; H_ww's per-event weight is the SAME per-event aggregation as the gradient's
    own per_event_resid_sum, just with d_row instead of resid as the bincount weight.

    Checker's finding (S1 review, launch-script round): hazard_nll_grad above is its OWN parallel layer
    (a Python ThreadPoolExecutor over chunks, expecting BLAS pinned to 1 thread by the process-wide env
    vars) -- that call stays OUTSIDE any BLAS thread-count override, or the two layers nest. The H_ww/H_wb
    loop below is the OTHER established pattern (serial Python chunks, BLAS itself threaded) -- same as
    s1_gram_timing.py's build_gram_ww and s1_aws_thread_timing.py's Gram-chunk sample -- so ONLY that loop
    is scoped up to `gram_blas_threads` via threadpoolctl, overriding the env-var baseline just for this
    block."""
    global _threadpool_info_logged, _first_gram_checked
    nll, grad_w, grad_b = hazard_nll_grad(w, b, X, row_event_pos, row_step, row_label, n_events)

    n_feat = X.shape[1]
    w64 = np.asarray(w, dtype=np.float64)
    eta = np.empty(n_events, dtype=np.float64)
    for s in range(0, n_events, chunk_size):
        e = min(s + chunk_size, n_events)
        eta[s:e] = X[s:e].astype(np.float64, copy=False) @ w64
    z = eta[row_event_pos] + b[row_step - 1]
    p_row = sigmoid(z)
    d_row = p_row * (1 - p_row)

    d_event = np.bincount(row_event_pos, weights=d_row, minlength=n_events)
    H_bb = np.bincount(row_step - 1, weights=d_row, minlength=n_steps)

    # D_step[event, step] = d_row for that (event, step) pair, 0 elsewhere -- each (event, step) appears
    # at most once among the hazard rows (B2's own invariant), so this scatter assignment is safe.
    D_step = np.zeros((n_events, n_steps), dtype=np.float64)
    D_step[row_event_pos, row_step - 1] = d_row

    H_ww = np.zeros((n_feat, n_feat), dtype=np.float64)
    H_wb = np.zeros((n_feat, n_steps), dtype=np.float64)
    t_gram0 = time.time()
    with threadpoolctl.threadpool_limits(limits=gram_blas_threads, user_api="blas"):
        if not _threadpool_info_logged:
            for info in threadpoolctl.threadpool_info():
                print(f"{log_prefix} threadpool_info (inside the Gram scope): {info}", flush=True)
            _threadpool_info_logged = True
        for s in range(0, n_events, chunk_size):
            e = min(s + chunk_size, n_events)
            Xc = X[s:e].astype(np.float64, copy=False)
            H_ww += (Xc * d_event[s:e, None]).T @ Xc
            H_wb += Xc.T @ D_step[s:e]
    gram_s = time.time() - t_gram0
    print(f"{log_prefix} Gram build: {gram_s:.2f}s", flush=True)
    if not _first_gram_checked:
        _first_gram_checked = True
        if gram_s > GRAM_BUILD_BUDGET_S:
            raise GramBuildTooSlow(
                f"first Gram build took {gram_s:.1f}s, over the {GRAM_BUILD_BUDGET_S:.0f}s budget "
                f"(2x the r7i probe's ~60s/outer-iteration) -- stopping before the remaining folds "
                f"burn hours on a machine that isn't delivering the sized BLAS speed")

    return nll, grad_w, grad_b, H_ww, H_wb, H_bb


def coordinate_descent(H_eff, g_eff, w_center, lam, l1_ratio, max_sweeps=200, tol=1e-10):
    """Minimises g_eff.(w-w_center) + 0.5(w-w_center).H_eff.(w-w_center) + the elastic-net penalty on w
    (NOT on w-w_center -- the penalty is always on the actual coefficient), via cyclic coordinate descent.
    Each coordinate's own Hessian diagonal gives its Newton step size; the proximal operator is the SAME
    elastic-net shrinkage s1_model.py's FISTA uses, just per-coordinate instead of a uniform step. Returns
    (w, n_sweeps)."""
    n = len(w_center)
    w = w_center.copy()
    diagH = np.diag(H_eff).copy()
    diagH[diagH <= 1e-12] = 1e-12   # a coordinate the Hessian is flat in still gets a (large) finite step
    r = g_eff.copy()   # gradient of the quadratic at the CURRENT w (starts at w_center, so r = g_eff)
    n_sweeps = 0
    for sweep in range(1, max_sweeps + 1):
        max_change = 0.0
        for j in range(n):
            step_j = 1.0 / diagH[j]
            z_j = w[j] - step_j * r[j]
            w_new_j = _prox(z_j, step_j, lam, l1_ratio)
            delta = w_new_j - w[j]
            if delta != 0.0:
                r += H_eff[:, j] * delta
                w[j] = w_new_j
                if abs(delta) > max_change:
                    max_change = abs(delta)
        n_sweeps = sweep
        if max_change < tol:
            break
    return w, n_sweeps


def fit_hazard_elastic_net_newton(X, row_event_pos, row_step, row_label, n_events, lam, l1_ratio,
                                   w0=None, b0=None, n_steps=20, max_outer=50, tol=1e-7,
                                   cd_max_sweeps=200, cd_tol=1e-10, chunk_size=100_000,
                                   log_every=None, log_prefix="", break_cross=False, break_grad=False):
    """Proximal Newton: see the module docstring. `max_outer` defaults to 50, not R6's 2,000 -- that cap
    is sized for a FIRST-ORDER method; Newton needs far fewer outer iterations (the planner's own
    estimate: 10-30 cold, a handful warm), and each one costs a full Gram build, so a 2,000 cap would be
    nonsensical here. Returns the same dict shape as s1_model's fitters, plus n_calls = n_outer (one
    Hessian-block build per outer iteration -- there is no separate "evaluation" count the way line
    search gives FISTA/L-BFGS-B extra calls, since the line search here only evaluates the cheap exact
    objective, not the expensive Hessian)."""
    n_feat = X.shape[1]
    w = np.zeros(n_feat) if w0 is None else np.asarray(w0, dtype=np.float64).copy()
    b = np.zeros(n_steps) if b0 is None else np.asarray(b0, dtype=np.float64).copy()

    def full_obj(w_, b_):
        nll, _, _ = hazard_nll_grad(w_, b_, X, row_event_pos, row_step, row_label, n_events)
        return nll + elastic_net_penalty(w_, lam, l1_ratio)

    obj_prev = full_obj(w, b)
    converged = False
    n_outer = 0
    n_cd_capped = 0
    for it in range(1, max_outer + 1):
        nll, grad_w, grad_b, H_ww, H_wb, H_bb = build_hessian_blocks(
            X, w, b, row_event_pos, row_step, row_label, n_events, n_steps, chunk_size,
            log_prefix=f"{log_prefix} outer={it}")
        if break_cross:
            # FAILING VARIANT candidate, S1 review round 6 (checker's finding): zeroing H_wb turned out
            # NOT to be decisive on real smoke data -- the line search's own safeguard and the fresh
            # re-linearisation each outer iteration let the fit self-correct to the SAME answer, just in
            # more outer iterations (14 vs 7). Kept here for the record (it genuinely changes the
            # trajectory, just not the final answer); `break_grad` below is the variant actually used as
            # the proof's failing case.
            H_wb = np.zeros_like(H_wb)
        if break_grad:
            # FAILING VARIANT (s1_newton_proof.py): negates grad_w, turning the Newton step into an
            # ASCENT direction. The backtracking line search can only shrink step_ls toward its floor
            # (1e-6) every outer iteration -- it cannot turn an uphill direction into a downhill one -- so
            # this must make the fit stall near its start point, far from the true optimum. Must never be
            # set True by any real caller.
            grad_w = -grad_w
        inv_hbb = 1.0 / np.maximum(H_bb, 1e-12)
        H_eff = H_ww - (H_wb * inv_hbb[None, :]) @ H_wb.T
        g_eff = grad_w - H_wb @ (grad_b * inv_hbb)

        w_full, n_sweeps = coordinate_descent(H_eff, g_eff, w, lam, l1_ratio,
                                               max_sweeps=cd_max_sweeps, tol=cd_tol)
        b_full = b - inv_hbb * (grad_b + H_wb.T @ (w_full - w))

        step_ls = 1.0
        while True:
            w_cand = w + step_ls * (w_full - w)
            b_cand = b + step_ls * (b_full - b)
            obj_cand = full_obj(w_cand, b_cand)
            if obj_cand <= obj_prev or step_ls < 1e-6:
                break
            step_ls *= 0.5
        w, b = w_cand, b_cand
        n_outer = it
        rel_change = abs(obj_prev - obj_cand) / max(abs(obj_prev), 1e-12)
        cd_capped = n_sweeps >= cd_max_sweeps
        n_cd_capped += int(cd_capped)
        # Checker's ruling, S1 review round 6: CD's sweep count and whether it hit the cap are logged for
        # EVERY outer iteration (not just every `log_every`) -- a capped sweep means the step may not be
        # a true Newton step, and that must always be visible, not only on the periodic detail line.
        print(f"{log_prefix} outer={it} cd_sweeps={n_sweeps}/{cd_max_sweeps}"
              + (" CD-CAPPED" if cd_capped else ""), flush=True)
        if log_every and it % log_every == 0:
            print(f"{log_prefix} outer={it} obj={obj_cand:.6f} rel_change={rel_change:.2e} "
                  f"cd_sweeps={n_sweeps} step_ls={step_ls:.3g}", flush=True)
        obj_prev = obj_cand
        if rel_change < tol:
            converged = True
            break
    return {"w": w, "b": b, "n_iter": n_outer, "n_calls": n_outer, "converged": converged,
            "obj_final": obj_prev, "rel_change": rel_change,
            "n_cd_capped": n_cd_capped, "n_cd_calls": n_outer}
