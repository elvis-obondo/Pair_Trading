"""HL-MODEL1 S1: time ONE weighted Gram matrix build on fold 7's full train set (planner's ruling, S1
review round 6: threading the exact gradient only got 2.6x on the VM with steep diminishing returns past
4 threads, and the old probe's own numbers showed the problem is ITERATION COUNT (90 first-order
iterations, gradient still 3-6e4), not per-evaluation speed -- numba would at best halve the step time.
Direction: switch to a second-order (proximal Newton / IRLS + coordinate descent, the glmnet method) solver
on the SAME objective, which needs far fewer outer iterations but each one needs the weighted Gram
X^T D X. Before writing the whole method: time ONE Gram build and project the full cost.

    python -u research/model/s1_gram_timing.py > research/model/logs/s1_gram_timing.log

H_ww = X^T diag(d_i) X, d_i = sum over k <= n_i (the steps event i survived) of p_ik(1-p_ik) -- same
per-event aggregation pattern as hazard_nll_grad's gradient (a bincount over hazard rows), evaluated at
the null model (w=0, b=the closed-form step-intercept MLE -- s1_model.null_step_intercepts, the same
starting point lambda_max is measured from) as a representative first-outer-iteration point.

ONE parallel layer only (checker's finding, S1 review round 6, BLOCKING): chunks are processed in a
SERIAL Python loop, each chunk's (X_chunk * d_chunk).T @ X_chunk left to BLAS's OWN internal threading
(OPENBLAS_NUM_THREADS=8, set by the launcher) -- a Python-level ThreadPoolExecutor around a GEMM that is
itself 8-way threaded would run 64 threads on 8 cores, making the measured time meaningless. A single
large dgemm already parallelises well across cores on its own. Each chunk casts to float64 ONCE (`Xc`),
reused for both the elementwise scale and the matmul -- not two separate casts of the same chunk.
"""
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402
from s1_preprocess import fit_preprocessing, apply_preprocessing  # noqa: E402
from s1_model import null_step_intercepts  # noqa: E402
from hazard_logistic import sigmoid  # noqa: E402
from b5_profile import rss_gb, clear_peak_rss  # noqa: E402

CHUNK_SIZE = 100_000
N_FOLDS = 8
FITS_PER_FOLD = 17   # 16 grid fits + 1 refit, R3
HOURS_GATE = 24.0


def build_gram_ww(X, d, chunk_size=CHUNK_SIZE, log_chunks=False):
    """Serial over chunks -- BLAS's own OPENBLAS_NUM_THREADS=8 threads each chunk's GEMM; a Python-level
    ThreadPoolExecutor around that would be 64 threads on 8 cores (checker's finding, S1 review round 6).
    Each chunk casts to float64 ONCE (`Xc`), reused for both the elementwise scale and the matmul."""
    n_events, n_feat = X.shape
    gram = np.zeros((n_feat, n_feat), dtype=np.float64)
    chunks = [(s, min(s + chunk_size, n_events)) for s in range(0, n_events, chunk_size)]
    for i, (s, e) in enumerate(chunks):
        t0 = time.time()
        Xc = X[s:e].astype(np.float64, copy=False)
        gram += (Xc * d[s:e, None]).T @ Xc
        if log_chunks:
            print(f"[S1-GRAM]   chunk {i+1}/{len(chunks)} ({s}:{e}): {time.time()-t0:.2f}s", flush=True)
    return gram


def main():
    t0 = time.time()
    import master_manifest as MF
    for name in ("s1_gram_timing.py", "s1_preprocess.py", "s1_model.py", "hazard_logistic.py", "harness.py"):
        print(f"[S1-GRAM] sha256 {name}: {MF.sha(os.path.join(HERE, name))}", flush=True)
    cache_info = H._cache_info()
    cache_sha = cache_info.get("cache_sha256", "NO VALID CACHE") if cache_info else "NO VALID CACHE"
    print(f"[S1-GRAM] cache manifest cache_sha256: {cache_sha} "
          f"(must be bd5dc2549374d0a80c8b042425e34119289b17b753a49213ac28c1831c6ca544)", flush=True)
    gs = os.path.join(os.path.dirname(HERE), "dataset", "GIT_STATE.json")
    git_head, git_dirty = ("unavailable", "unavailable")
    if os.path.exists(gs):
        G = MF.json.load(open(gs))
        git_head, git_dirty = G.get("head", "unavailable"), len(G.get("porcelain", []))
    print(f"[S1-GRAM] git_head {git_head} ({git_dirty} uncommitted paths); "
          f"start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC; pid {os.getpid()}", flush=True)

    clear_peak_rss()
    rss0, _ = rss_gb()
    events = H.load_search_events()
    folds = H.build_folds(events)
    fold = folds[7]
    train_ids = fold["train_ids"]
    in_cols = cache_info["columns"]
    assert len(in_cols) == 1091, f"expected 1,091 IN columns, cache has {len(in_cols)}"
    print(f"[S1-GRAM] fold 7: n_train={len(train_ids):,}  [{time.time()-t0:.0f}s]", flush=True)

    t_prep0 = time.time()
    stats = fit_preprocessing(train_ids, in_cols)
    X_fit, out_cols = apply_preprocessing(train_ids, in_cols, stats)
    t_prep_train = time.time() - t_prep0
    import gc
    gc.collect()
    rss_after_prep, hwm_after_prep = rss_gb()
    n_feat = len(out_cols)
    print(f"[S1-GRAM] preprocessed TRAIN in {t_prep_train:.2f}s: n_features={n_feat} "
          f"rss={rss_after_prep:.2f}GB VmHWM={hwm_after_prep:.2f}GB  [{time.time()-t0:.0f}s]", flush=True)

    train_events = events.loc[train_ids]
    hazard = H.build_hazard_rows(train_events)
    pos = {eid: i for i, eid in enumerate(train_ids)}
    row_event_pos = hazard["event_id"].map(pos).to_numpy()
    row_step = hazard["step"].to_numpy()
    row_label = hazard["label"].to_numpy()
    n_events = len(train_ids)
    print(f"[S1-GRAM] hazard rows: {len(row_event_pos):,} over {n_events:,} train events "
          f"[{time.time()-t0:.0f}s]", flush=True)

    # Representative point: the null model (w=0, b=closed-form step-intercept MLE) -- the same point
    # lambda_max is measured from, and a plausible first-outer-iteration state.
    b0 = null_step_intercepts(row_step, row_label, n_steps=H.N_STEPS)
    p_row = sigmoid(b0[row_step - 1])   # w=0 -> eta=0 for every event
    d = np.bincount(row_event_pos, weights=p_row * (1 - p_row), minlength=n_events)
    print(f"[S1-GRAM] built per-event weights d_i (null model, w=0): min={d.min():.4g} "
          f"max={d.max():.4g} mean={d.mean():.4g}  [{time.time()-t0:.0f}s]", flush=True)

    clear_peak_rss()
    t_gram0 = time.time()
    gram = build_gram_ww(X_fit, d, chunk_size=CHUNK_SIZE, log_chunks=True)
    t_gram = time.time() - t_gram0
    _, hwm_gram = rss_gb()
    print(f"[S1-GRAM] H_ww build: shape={gram.shape} wall={t_gram:.2f}s "
          f"VmHWM_this_block={hwm_gram:.2f}GB  [{time.time()-t0:.0f}s]", flush=True)

    _, hwm_overall = rss_gb()
    print(f"[S1-GRAM] overall peak RSS this run (VmHWM): {hwm_overall:.2f}GB "
          f"(rss at process start: {rss0:.2f}GB)", flush=True)

    # Projection (A: arithmetic on ONE measured Gram build; outer-iteration count is the planner's own
    # stated expectation, 10-30 cold / "a handful" warm -- not measured here, since the inner coordinate
    # descent and the rest of the method are not written yet).
    for cold_iters, warm_iters, label in ((30, 5, "planner's stated range (worst case: 30 cold, 5 warm)"),
                                           (10, 2, "planner's stated range (best case: 10 cold, 2 warm)")):
        # 2 l1_ratios x (1 cold + 7 warm) per fold (R3) + 1 refit (approximated as another cold fit, same
        # as earlier sizing scripts' convention).
        per_fold_s = t_prep_train + (2 * (cold_iters + 7 * warm_iters) + cold_iters) * t_gram
        total_s = N_FOLDS * per_fold_s
        total_hours = total_s / 3600.0
        print(f"[S1-GRAM] PROJECTION ({label}): per_fold = prep[{t_prep_train:.1f}s] + "
              f"(2 x ({cold_iters} cold + 7 x {warm_iters} warm) + {cold_iters} refit) x "
              f"gram[{t_gram:.2f}s] = {per_fold_s:.0f}s; x {N_FOLDS} folds = {total_s:.0f}s = "
              f"{total_hours:.2f}h (Gram builds only -- the inner coordinate descent, line search and "
              f"H_wb/H_bb blocks are NOT included, not written yet, expected much cheaper than H_ww)",
              flush=True)

    print(f"[S1-GRAM] all done  [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
