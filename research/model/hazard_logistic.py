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

CHUNKED AND THREADED BY EVENT ROWS (checker's finding, S1 review round 1, and planner's ruling, S1 review
round 5, after a float32 "fast path" was tried and REJECTED -- see git history for hazard_nll_grad_fast,
deleted, not left behind as a parallel path): `X` is float32; `X @ w64` and `X.T @ resid64` with a
float64 `w`/`resid` make numpy upcast each chunk of `X` to a float64 temporary. The one-fit probe (S1
review round 5) measured ~67s per function evaluation on fold 7's full train set; a local profile traced
~99% of that to this cast, not to the matmul FLOPs themselves or to sigmoid/NLL/bincount (negligible).

The planner's diagnosis: "the cost is the unthreaded astype(float64) copy per chunk, not float64 itself."
This keeps the EXACT same arithmetic (float64 throughout, same chunk boundaries, same summation order) but
runs the per-chunk cast+matmul for DIFFERENT chunks on DIFFERENT threads (concurrent.futures.ThreadPoolExecutor)
-- numpy's astype and matmul both release the GIL during their C-level work, so this is real parallelism
across cores, not just concurrency (the same reasoning B5's load_features already used for parallel file
reads). grad_w's per-chunk partial sums are collected into a list (one per chunk, in chunk order -- pool.map
preserves input order regardless of which thread finishes first) and then summed in that same order with a
plain loop, not np.sum's pairwise algorithm, to stay as close as possible to the un-threaded version's exact
summation -- s1_hazard_threaded_proof.py checks the result against the pre-threading version within 1e-10
relative (a pointwise check only, since this is the SAME arithmetic, not an approximation).
"""
import concurrent.futures

import numpy as np

N_THREADS = 8  # R7: "a fixed thread count, logged" -- logged by callers, not here


def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


def hazard_nll_grad(w, b, X, row_event_pos, row_step, row_label, n_events, break_intercept=False,
                     chunk_size=100_000, n_threads=N_THREADS):
    """Returns (nll, grad_w, grad_b). `break_intercept` exists ONLY so b5_hazard_logistic_proof.py's
    broken variant can exercise this exact shipped function (not a reimplementation) with the step-
    intercept add disabled -- it must never be set True by any real caller."""
    n_feat = X.shape[1]
    w64 = np.asarray(w, dtype=np.float64)
    chunks = [(s, min(s + chunk_size, n_events)) for s in range(0, n_events, chunk_size)]
    eta = np.empty(n_events, dtype=np.float64)

    def eta_chunk(se):
        s, e = se
        eta[s:e] = X[s:e].astype(np.float64, copy=False) @ w64

    with concurrent.futures.ThreadPoolExecutor(max_workers=n_threads) as pool:
        list(pool.map(eta_chunk, chunks))

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

    def gradw_chunk(se):
        s, e = se
        return X[s:e].astype(np.float64, copy=False).T @ per_event_resid_sum[s:e]

    with concurrent.futures.ThreadPoolExecutor(max_workers=n_threads) as pool:
        partials = list(pool.map(gradw_chunk, chunks))   # pool.map: same order as `chunks`, always
    grad_w = np.zeros(n_feat, dtype=np.float64)
    for part in partials:                                 # plain sequential sum, same order/method the
        grad_w += part                                    # un-threaded version used -- not np.sum's
                                                            # pairwise algorithm, to stay numerically close
    grad_b = np.bincount(row_step - 1, weights=resid, minlength=len(b))
    return nll, grad_w, grad_b
