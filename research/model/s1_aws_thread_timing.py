"""HL-MODEL1 S1: AWS r7i.16xlarge timing probe (user-approved, 2026-10-28: one spot instance, ~1h,
under $10, self-terminating). The GCP VM is an 8-vCPU slice of a larger host with a slice of its memory
bandwidth, which is why threading hazard_nll_grad stopped scaling past 4 threads there (~26s/eval). A
64-vCPU r7i.16xlarge gets a full socket's memory channels; this times the SAME exact, bit-identical
threaded kernel (hazard_logistic.hazard_nll_grad -- no code change, no new precision trade) at 16, 32 and
64 threads on fold 7's full train set, to see whether it scales further there.

    python -u research/model/s1_aws_thread_timing.py > /tmp/s1_timing.log 2>&1

Runs against the v1 data pulled fresh from S3 onto this throwaway instance (research/datasets/master/work
and .../versions/v1, populated by the launch script before this runs) and a cache built fresh by
build_cache_v1_pair.py (also run by the launch script, before this). Reports s/eval and peak RSS at each
thread count, then projects the full S1 run (150h baseline at the GCP VM's 26s/eval, R3's 136 fit-units)
for 1, 2 and 4 machines at whichever thread count is fastest here.

Also times a SAMPLE of weighted-Gram chunks (planner's ruling, S1 review round 6, within the same 90-
minute cap): the current solver ruling is proximal Newton, whose cost is dominated by the Gram build
(~23 min on the GCP VM). A few chunks, same math as s1_gram_timing.py's build_gram_ww (serial Python loop,
BLAS itself threaded via threadpoolctl -- ONE parallel layer, not nested with hazard_nll_grad's own
Python-level threading, which is pinned to 1 BLAS thread for its own section above), scaled up to a full
fold-7-sized build, gives BOTH solvers' projections from the SAME machine.
"""
import os
import sys
import time

import numpy as np
import threadpoolctl

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402
from s1_preprocess import fit_preprocessing, apply_preprocessing  # noqa: E402
from hazard_logistic import hazard_nll_grad  # noqa: E402
from b5_profile import rss_gb, clear_peak_rss  # noqa: E402

N_EVALS = 10
THREAD_COUNTS = (16, 32, 64)
BASELINE_S_PER_EVAL = 26.0     # GCP VM, 8 threads, measured (S1 review round 5)
BASELINE_TOTAL_HOURS = 150.0   # checker's corrected realistic projection at that s/eval
N_FOLDS = 8
GRAM_CHUNK_SIZE = 100_000
N_GRAM_CHUNKS_SAMPLE = 5
GRAM_BLAS_THREADS = 64


def null_step_intercepts(row_step, row_label, n_steps=20):
    """Inlined from s1_model.py (not shipped to this throwaway instance to keep the embedded user-data
    payload small -- this probe never fits a model, so the optimiser code isn't needed). Identical to
    s1_model.null_step_intercepts: closed-form unpenalised MLE of the step intercepts alone (w=0)."""
    label1 = np.bincount(row_step - 1, weights=row_label.astype(np.float64), minlength=n_steps)
    n = np.bincount(row_step - 1, minlength=n_steps).astype(np.float64)
    eps = 1e-10
    p = np.clip(label1 / n, eps, 1 - eps)
    return np.log(p / (1 - p))


def main():
    t0 = time.time()
    import master_manifest as MF
    for name in ("s1_aws_thread_timing.py", "s1_preprocess.py", "hazard_logistic.py", "harness.py"):
        print(f"[S1-AWS] sha256 {name}: {MF.sha(os.path.join(HERE, name))}", flush=True)
    cache_info = H._cache_info()
    cache_sha = cache_info.get("cache_sha256", "NO VALID CACHE") if cache_info else "NO VALID CACHE"
    print(f"[S1-AWS] cache manifest cache_sha256: {cache_sha} "
          f"(must be bd5dc2549374d0a80c8b042425e34119289b17b753a49213ac28c1831c6ca544)", flush=True)
    print(f"[S1-AWS] cpu_count={os.cpu_count()}; start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} "
          f"UTC; pid {os.getpid()}", flush=True)

    clear_peak_rss()
    events = H.load_search_events()
    folds = H.build_folds(events)
    fold = folds[7]
    train_ids = fold["train_ids"]
    in_cols = cache_info["columns"]
    assert len(in_cols) == 1091, f"expected 1,091 IN columns, cache has {len(in_cols)}"
    print(f"[S1-AWS] fold 7: n_train={len(train_ids):,}  [{time.time()-t0:.0f}s]", flush=True)

    t_prep0 = time.time()
    stats = fit_preprocessing(train_ids, in_cols)
    X_fit, out_cols = apply_preprocessing(train_ids, in_cols, stats)
    t_prep = time.time() - t_prep0
    import gc
    gc.collect()
    _, hwm_prep = rss_gb()
    print(f"[S1-AWS] preprocessed TRAIN in {t_prep:.2f}s: n_features={len(out_cols)} "
          f"VmHWM={hwm_prep:.2f}GB  [{time.time()-t0:.0f}s]", flush=True)

    train_events = events.loc[train_ids]
    hazard = H.build_hazard_rows(train_events)
    pos = {eid: i for i, eid in enumerate(train_ids)}
    row_event_pos = hazard["event_id"].map(pos).to_numpy()
    row_step = hazard["step"].to_numpy()
    row_label = hazard["label"].to_numpy()
    n_events = len(train_ids)
    print(f"[S1-AWS] hazard rows: {len(row_event_pos):,} over {n_events:,} train events "
          f"[{time.time()-t0:.0f}s]", flush=True)

    b0 = null_step_intercepts(row_step, row_label, n_steps=H.N_STEPS)
    w0 = np.zeros(X_fit.shape[1])

    best_s_per_eval = None
    for n_threads in THREAD_COUNTS:
        clear_peak_rss()
        times = []
        for i in range(N_EVALS):
            t_e0 = time.time()
            nll, gw, gb = hazard_nll_grad(w0, b0, X_fit, row_event_pos, row_step, row_label, n_events,
                                           n_threads=n_threads)
            times.append(time.time() - t_e0)
        _, hwm = rss_gb()
        mean_s = float(np.mean(times))
        print(f"[S1-AWS] n_threads={n_threads}: times={[f'{x:.2f}' for x in times]} "
              f"mean={mean_s:.3f}s VmHWM={hwm:.2f}GB  [{time.time()-t0:.0f}s]", flush=True)
        if best_s_per_eval is None or mean_s < best_s_per_eval:
            best_s_per_eval = mean_s

    scale = best_s_per_eval / BASELINE_S_PER_EVAL
    total_hours_lbfgsb = BASELINE_TOTAL_HOURS * scale
    print(f"[S1-AWS] best s/eval here: {best_s_per_eval:.3f}s (GCP baseline {BASELINE_S_PER_EVAL}s, "
          f"scale {scale:.3f}x)", flush=True)
    print(f"[S1-AWS] PROJECTED full-run total compute (exact L-BFGS-B): {total_hours_lbfgsb:.1f}h "
          f"(scaled from the GCP-measured {BASELINE_TOTAL_HOURS}h at {BASELINE_S_PER_EVAL}s/eval)",
          flush=True)
    for n_machines in (1, 2, 4):
        print(f"[S1-AWS]   L-BFGS-B, {n_machines} machine(s): wall time ~{total_hours_lbfgsb/n_machines:.1f}h",
              flush=True)

    # Gram-chunk sample: ONE parallel layer (BLAS at GRAM_BLAS_THREADS via threadpoolctl, serial Python
    # loop over chunks -- checker's round-6 principle, same as s1_gram_timing.py's build_gram_ww).
    p_row = 1.0 / (1.0 + np.exp(-np.clip(b0[row_step - 1], -30, 30)))   # w=0 -> eta=0 for every event
    d = np.bincount(row_event_pos, weights=p_row * (1 - p_row), minlength=n_events)
    n_feat = X_fit.shape[1]
    n_chunks_total = (n_events + GRAM_CHUNK_SIZE - 1) // GRAM_CHUNK_SIZE
    clear_peak_rss()
    gram_times = []
    with threadpoolctl.threadpool_limits(limits=GRAM_BLAS_THREADS, user_api="blas"):
        for info in threadpoolctl.threadpool_info():
            print(f"[S1-AWS] threadpool_info (inside the Gram section, process started with "
                  f"OMP_NUM_THREADS=1): {info}", flush=True)
        for i in range(min(N_GRAM_CHUNKS_SAMPLE, n_chunks_total)):
            s = i * GRAM_CHUNK_SIZE
            e = min(s + GRAM_CHUNK_SIZE, n_events)
            t_g0 = time.time()
            Xc = X_fit[s:e].astype(np.float64, copy=False)
            _ = (Xc * d[s:e, None]).T @ Xc
            gram_times.append(time.time() - t_g0)
    _, hwm_gram = rss_gb()
    mean_chunk_s = float(np.mean(gram_times))
    full_gram_s = mean_chunk_s * n_chunks_total
    print(f"[S1-AWS] Gram chunk sample ({len(gram_times)}/{n_chunks_total} chunks, "
          f"BLAS at {GRAM_BLAS_THREADS} threads): times={[f'{x:.2f}' for x in gram_times]} "
          f"mean={mean_chunk_s:.3f}s/chunk VmHWM={hwm_gram:.2f}GB  [{time.time()-t0:.0f}s]", flush=True)
    print(f"[S1-AWS] full fold-7 H_ww build, scaled: {full_gram_s:.1f}s ({n_chunks_total} chunks x "
          f"{mean_chunk_s:.3f}s/chunk)", flush=True)

    for cold_iters, warm_iters, label in ((30, 5, "worst case: 30 cold, 5 warm"),
                                           (10, 2, "best case: 10 cold, 2 warm")):
        per_fold_s = t_prep + (2 * (cold_iters + 7 * warm_iters) + cold_iters) * full_gram_s
        total_hours_newton = (N_FOLDS * per_fold_s) / 3600.0
        print(f"[S1-AWS] PROJECTED full-run total compute (proximal Newton, {label}): "
              f"{total_hours_newton:.1f}h", flush=True)
        for n_machines in (1, 2, 4):
            print(f"[S1-AWS]   Newton ({label}), {n_machines} machine(s): "
                  f"wall time ~{total_hours_newton/n_machines:.1f}h", flush=True)

    print(f"[S1-AWS] all done  [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
