"""HL-MODEL1 B5 Step 2 / S1: the shipped per-event discrete-time hazard logistic core.

This is the function S1 (docs/prompts/HL_MODEL1_S1_LOGISTIC.md) imports and fits against -- "the
B5-proved per-event logistic core". research/model/b5_hazard_logistic_proof.py imports THIS module (does
not redefine it) and proves it matches a naive, wasteful expanded-design baseline exactly; if this file
changes, that proof must be rerun.

MODEL (A2, A3): hazard row (event i, step k, label y_ik), z_ik = X_i . w + b_k (b_k a per-step intercept,
20 steps). p_ik = sigmoid(z_ik). NLL = -sum_rows [y log p + (1-y) log(1-p)] -- no penalty here; L1/elastic
net is added on top by the caller (S1's job), not inside this core.

Avoids the (event x step) row expansion the brief says not to ship: eta = X @ w is computed ONCE PER
EVENT (length n_events, never replicated to n_rows). z is built by indexing eta at each row's event
position and adding that row's step intercept -- no per-row feature vector is ever materialised. The
gradient w.r.t. w accumulates the PER-EVENT sum of residuals first (one bincount over n_events), then
multiplies by X ONCE PER EVENT, not once per hazard row. grad_b is a plain bincount by step, independent
of event count.
"""
import numpy as np


def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


def hazard_nll_grad(w, b, X, row_event_pos, row_step, row_label, n_events, break_intercept=False):
    """Returns (nll, grad_w, grad_b). `break_intercept` exists ONLY so b5_hazard_logistic_proof.py's
    broken variant can exercise this exact shipped function (not a reimplementation) with the step-
    intercept add disabled -- it must never be set True by any real caller."""
    eta = X @ w
    if break_intercept:
        z = eta[row_event_pos]
    else:
        z = eta[row_event_pos] + b[row_step - 1]
    p = sigmoid(z)
    y = row_label.astype(np.float64)
    eps = 1e-12
    nll = -np.sum(y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps))
    resid = p - y
    per_event_resid_sum = np.bincount(row_event_pos, weights=resid, minlength=n_events)
    grad_w = X.T @ per_event_resid_sum
    grad_b = np.bincount(row_step - 1, weights=resid, minlength=len(b))
    return nll, grad_w, grad_b
