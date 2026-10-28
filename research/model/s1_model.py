"""HL-MODEL1 S1: regularisation-path and KKT helpers shared by the real run (s1_newton.py, proximal
Newton -- the user-approved solver, S1 review round 6) and its proof (s1_newton_proof.py, which keeps the
split-weight L-BFGS-B fit as its OWN reference tool only -- see that file's module docstring).

FISTA (fit_hazard_elastic_net) and the split-weight L-BFGS-B fit (fit_hazard_elastic_net_lbfgsb) that used
to live here are RETIRED from the real run path: FISTA needed far too many outer iterations (90+, still
not converged, on the real fold-7 probe) and L-BFGS-B needed 2+ machines to clear the 24h gate; the user
chose proximal Newton instead (9.5-23.2h on ONE machine depending on the real outer-iteration count).
fit_hazard_elastic_net is deleted outright (git keeps it); fit_hazard_elastic_net_lbfgsb moved into
s1_newton_proof.py, the only place it is still used, as the proof's tight reference optimiser.

`lambda_max`/`build_grid` (R3's regularisation path) and `kkt_violation` (the exact KKT stationarity
check, independent of which optimiser produced a candidate solution) apply to EITHER optimiser and stay
here, imported by both the real run and the proof.
"""
import numpy as np

from hazard_logistic import hazard_nll_grad


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
