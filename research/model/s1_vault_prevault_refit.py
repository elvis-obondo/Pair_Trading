"""HL-VAULT1 step 2b ONLY (brief docs/prompts/HL_VAULT1_RUN.md): the AWS pre-vault refit.

  Round 3 (instance i-095394542d9f95783, log research/model/logs/s1/vault_pull/vault-refit_i-095394542d9f95783.log)
  ran this script's former step 2a, a fold 0 reproduction check, and it failed its original tolerance
  (derived from fold0_done.json). The planner relayed the user's decision (2026-11-11; the user's own yes to the launch is still taken in the builder session) to ACCEPT 2a as
  solver-level agreement and to launch 2b ONLY, with the same 2b code the checker passed. The 2a code was
  therefore removed from this file (git/the round-3 log's printed script sha keep the record); nothing
  in 2b itself changed except: (1) the Newton fit now also reports how many outer steps hit the inner
  coordinate-descent sweep cap (200), printed and saved in the model JSON's fit_result, because 2a hit
  that cap at every outer step (see its log) and 2b must state whether it does too.

  2b: calls fit_prevault on EVERY search event with t0 < VAULT_START - EMBARGO (asserted equal to
      len(events), the full load_search_events() output -- the vault coverage check already found
      VAULT_START - EMBARGO == SEARCH_END for this data), with fold 7's own selected lam/l1_ratio (no
      grid search), one cold-started fit (w0=None, b0=None). Saves the COMPLETE model: w, b (20 step
      intercepts), every s1_preprocess.py statistic, ticker one-hot levels, settings, input sha256s,
      the lam/row-count-ratio known-gap line. Reloads it and asserts BIT-IDENTICAL predictions on a sample.

Vault safety: imports only `harness` (via s1_preprocess, s1_model, s1_newton, and borrows a few small
helpers from s1_run -- vm_rss_mb/vm_hwm_mb/fold_hazard/compute_p_h/SEED/MAX_OUTER/TOL/OUT_DIR -- but never
calls s1_run.run_one_fold) for 2b. `vault_loader` is never imported here -- step 2 never
reads a vault row; the pre-vault model is fit on search-period data only.

    python -u research/model/s1_vault_prevault_refit.py > research/model/logs/s1/s1_vault_prevault_refit.log

Expected to run on an AWS instance with enough RAM for 2b's full-data refit; not runnable on this laptop
(8 GB RAM, 2b's refit needs on the order of 75-80 GB, scaled from fold 7's own measured peak of 55-58 GB
at 3,979,894 rows: 5,378,429/3,979,894 = 1.3514x).
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402
import s1_run as S1R  # noqa: E402 -- only its small helpers are reused (see module docstring); its
                       # run_one_fold (the grid search) is never called by this script
from s1_preprocess import fit_preprocessing, apply_preprocessing  # noqa: E402
from s1_model import kkt_violation  # noqa: E402
from s1_newton import fit_hazard_elastic_net_newton  # noqa: E402

OUT_DIR = S1R.OUT_DIR
MODEL_OUT = os.path.join(OUT_DIR, "s1_prevault_model.json")
MODEL_W_OUT = os.path.join(OUT_DIR, "s1_prevault_model_w.npy")

REQUIRED_FILES = ("fold7_done.json",)
# the round-3 2a record, parsed from that run's log by diagnostics/vault_2a_maxdiff.py (numbers read, never typed)
MAXDIFF_JSON = os.path.join(HERE, "diagnostics", "vault_2a_maxdiff.json")


def log(msg):
    print(msg, flush=True)


def fit_prevault(events, ids, in_cols, lam, l1_ratio):
    """fit_preprocessing on `ids`, apply, hazard rows, a single cold-started (w0=None, b0=None) Newton fit
    at the given (lam, l1_ratio) -- no grid search. Returns (r, stats, out_cols, kkt)."""
    t0 = time.time()
    n = len(ids)
    stats = fit_preprocessing(ids, in_cols)
    X, out_cols = apply_preprocessing(ids, in_cols, stats)
    log(f"[FITPREVAULT] n={n:,} n_features={len(out_cols)} degenerate={len(stats['degenerate_dropped'])} "
        f"sd0={len(stats['sd0_dropped'])} VmRSS={S1R.vm_rss_mb()}MB VmHWM={S1R.vm_hwm_mb()}MB "
        f"[{time.time()-t0:.0f}s]")
    row_event_pos, row_step, row_label = S1R.fold_hazard(events, ids)
    r = fit_hazard_elastic_net_newton(X, row_event_pos, row_step, row_label, n, lam=lam, l1_ratio=l1_ratio,
                                       w0=None, b0=None, max_outer=S1R.MAX_OUTER, tol=S1R.TOL)
    kkt = kkt_violation(r["w"], r["b"], lam, l1_ratio, X, row_event_pos, row_step, row_label, n)
    log(f"[FITPREVAULT] fit: n_iter={r['n_iter']} converged={r['converged']} rel_change={r['rel_change']:.2e} "
        f"KKT max_violation={kkt['max_violation']:.3e} n_nonzero_w={int(np.sum(r['w'] != 0))} "
        f"VmRSS={S1R.vm_rss_mb()}MB VmHWM={S1R.vm_hwm_mb()}MB  [{time.time()-t0:.0f}s]")
    log(f"[FITPREVAULT] inner CD sweep cap (200): hit at {r['n_cd_capped']} of {r['n_cd_calls']} outer steps "
        f"(round 3's 2a log shows CD-CAPPED on every outer step; compare with this count)")
    return r, stats, out_cols, kkt


def step_2b_prevault_fit(events, in_cols, fold7_lam, fold7_l1_ratio, fold7_train_n, fold7_val_n):
    """Fits the pre-vault model with fit_prevault (the same function round 3's 2a ran) on every search
    event with t0 < VAULT_START - EMBARGO, using fold 7's own selected lam/l1_ratio. Saves the complete
    model and reloads it to assert identical predictions on a sample.

    Planner's point (2026-11-09): the loss is SUMMED, not averaged (hazard_logistic.py:72 and
    s1_newton.py:44 both skip any /n), and s1_run.py:229 carries lam from the selection fit (train) to
    the refit (train+val, ~1.27x rows for fold 7) with NO rescaling -- the established rule in this
    codebase is to reuse the lam number verbatim across a row-count change, not to rescale it. 2b
    follows that same rule on a bigger row-count change (fold 7's train rows -> every search event).
    Both ratios are computed below, never typed."""
    log("[VAULT2B] start: pre-vault refit, lam from fold 7 (2a skipped by the user's 2026-11-11 decision, see docstring)")
    cutoff = H.VAULT_START - H.EMBARGO
    all_ids = events.index[events["t0"] < cutoff].to_numpy()
    assert len(all_ids) == len(events), (
        f"expected every search event to satisfy t0 < VAULT_START - EMBARGO ({len(all_ids)} of "
        f"{len(events)} did) -- the vault coverage check found these are the same set; a mismatch here "
        f"means that has changed and must be investigated before fitting")
    n = len(all_ids)
    lam_row_ratio_2b = n / fold7_train_n
    fold7_refit_ratio = (fold7_train_n + fold7_val_n) / fold7_train_n
    log(f"[VAULT2B] n_events={n:,} fold7_train_n={fold7_train_n:,} fold7_val_n={fold7_val_n:,} "
        f"lam_row_ratio_2b={lam_row_ratio_2b:.4f} fold7_refit_ratio={fold7_refit_ratio:.4f} "
        f"lam={fold7_lam:.6g} l1_ratio={fold7_l1_ratio}")

    md = json.load(open(MAXDIFF_JSON))
    d = md["max_abs_diff"]
    gap_2a = (f"2a (fold 0 refit-only reproduction, round 3) FAILED its pre-set tolerance "
              f"{md['pred_abs_tol']:.3e} (outside it: p_2h {md['counts']['p_2h']['outside']:,}, "
              f"p_5h {md['counts']['p_5h']['outside']:,}, p_10h {md['counts']['p_10h']['outside']:,} of "
              f"{md['counts']['p_10h']['compared']:,} fold 0 test events) and was ACCEPTED on the user's explicit "
              f"yes as solver-level agreement; max |delta p| per horizon: p_2h {d['p_2h']:.6f}, "
              f"p_5h {d['p_5h']:.6f}, p_10h {d['p_10h']:.6f}. Attributed to the unsaved warm-start intercepts "
              f"b0 (s1_run.py refit starts b from the selection fit) plus the lasso's non-strict convexity "
              f"(unproven). Source: {md['log']} via diagnostics/vault_2a_maxdiff.py.")
    log(f"[VAULT2B] known gap recorded: {gap_2a}")

    t0 = time.time()
    r, stats, out_cols, kkt = fit_prevault(events, all_ids, in_cols, fold7_lam, fold7_l1_ratio)

    # sample predictions BEFORE saving, to compare against the reload
    rng_sample = np.random.default_rng(S1R.SEED)
    sample_pos = rng_sample.choice(n, size=min(2000, n), replace=False)
    sample_ids = all_ids[sample_pos]
    X_sample, _ = apply_preprocessing(sample_ids, in_cols, stats)
    p_2h_live = S1R.compute_p_h(r["w"], r["b"], X_sample, 4)
    p_5h_live = S1R.compute_p_h(r["w"], r["b"], X_sample, 10)
    p_10h_live = S1R.compute_p_h(r["w"], r["b"], X_sample, H.N_STEPS)

    import master_manifest as MF
    input_sha256 = {name: MF.sha(os.path.join(HERE, name)) for name in
                     ("s1_vault_prevault_refit.py", "s1_run.py", "s1_newton.py", "s1_preprocess.py",
                      "s1_model.py", "hazard_logistic.py", "harness.py")}

    model = dict(
        out_cols=out_cols,
        b=list(r["b"]),
        fit_cols=stats["fit_cols"], final_numeric=stats["final_numeric"],
        clip_lo=list(stats["clip_lo"]), clip_hi=list(stats["clip_hi"]),
        mean=list(stats["mean"]), sd=list(stats["sd"]),
        nan_indicator_cols=stats["nan_indicator_cols"],
        degenerate_dropped=stats["degenerate_dropped"], sd0_dropped=stats["sd0_dropped"],
        ticker_levels=stats["ticker_levels"],
        settings=dict(lam=fold7_lam, l1_ratio=fold7_l1_ratio, seed=S1R.SEED, max_outer=S1R.MAX_OUTER,
                      tol=S1R.TOL, reused_fold="fold7", n_events=n, n_steps=H.N_STEPS,
                      fold7_train_n=fold7_train_n, fold7_val_n=fold7_val_n,
                      lam_row_ratio_2b=lam_row_ratio_2b, fold7_refit_ratio=fold7_refit_ratio),
        fit_result=dict(n_iter=r["n_iter"], converged=bool(r["converged"]), rel_change=r["rel_change"],
                        kkt_max_violation=kkt["max_violation"],
                        n_cd_capped=r["n_cd_capped"], n_cd_calls=r["n_cd_calls"]),
        input_sha256=input_sha256,
        sample_event_ids=[int(x) for x in sample_ids],
        known_gaps=[
            f"pre-vault model reuses fold 7's lam on {lam_row_ratio_2b:.2f}x its train rows (summed "
            f"loss, see s1_newton.py/hazard_logistic.py), so the relative penalty is slightly weaker; "
            f"same rule as every fold's refit ({fold7_refit_ratio:.2f}x, fold 7's own train+val vs "
            f"train).",
            gap_2a,
        ],
    )
    os.makedirs(OUT_DIR, exist_ok=True)
    np.save(MODEL_W_OUT, r["w"])
    json.dump(model, open(MODEL_OUT, "w"), indent=1)
    log(f"[VAULT2B] model saved: {MODEL_OUT} + {MODEL_W_OUT}  [{time.time()-t0:.0f}s]")

    # --- reload and assert identical predictions on the SAME sample ---
    w_reload = np.load(MODEL_W_OUT)
    model_reload = json.load(open(MODEL_OUT))
    stats_reload = dict(
        fit_cols=model_reload["fit_cols"], final_numeric=model_reload["final_numeric"],
        clip_lo=np.array(model_reload["clip_lo"]), clip_hi=np.array(model_reload["clip_hi"]),
        mean=np.array(model_reload["mean"]), sd=np.array(model_reload["sd"]),
        nan_indicator_cols=model_reload["nan_indicator_cols"],
        ticker_levels=model_reload["ticker_levels"],
    )
    b_reload = np.array(model_reload["b"])
    sample_ids_reload = np.array(model_reload["sample_event_ids"])
    assert np.array_equal(sample_ids_reload, sample_ids), "reloaded sample_event_ids do not match"

    X_sample_reload, out_cols_reload = apply_preprocessing(sample_ids_reload, in_cols, stats_reload)
    assert out_cols_reload == model_reload["out_cols"], "reloaded out_cols do not match the saved ones"
    p_2h_reload = S1R.compute_p_h(w_reload, b_reload, X_sample_reload, 4)
    p_5h_reload = S1R.compute_p_h(w_reload, b_reload, X_sample_reload, 10)
    p_10h_reload = S1R.compute_p_h(w_reload, b_reload, X_sample_reload, H.N_STEPS)

    assert np.array_equal(p_2h_live, p_2h_reload), "reload mismatch: p_2h"
    assert np.array_equal(p_5h_live, p_5h_reload), "reload mismatch: p_5h"
    assert np.array_equal(p_10h_live, p_10h_reload), "reload mismatch: p_10h"
    log(f"[VAULT2B] reload check PASSED: {len(sample_ids)} sampled events, "
        f"p_2h/p_5h/p_10h bit-identical between the live fit and the reloaded model")
    return model


def main():
    t0 = time.time()
    import master_manifest as MF
    for name in ("s1_vault_prevault_refit.py", "s1_run.py", "s1_newton.py", "s1_preprocess.py",
                 "s1_model.py", "hazard_logistic.py", "harness.py"):
        log(f"[VAULTREFIT] sha256 {name}: {MF.sha(os.path.join(HERE, name))}")
    log(f"[VAULTREFIT] start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC; pid {os.getpid()}")

    # checker's V3: assert the required file(s) exist up front, before any compute is spent.
    missing = [f for f in REQUIRED_FILES if not os.path.exists(os.path.join(OUT_DIR, f))]
    assert not missing, f"missing required file(s) in {OUT_DIR}: {missing}"
    assert os.path.exists(MAXDIFF_JSON), f"missing {MAXDIFF_JSON} (run diagnostics/vault_2a_maxdiff.py)"
    log(f"[VAULTREFIT] required files present: {REQUIRED_FILES}")

    fold7_done = json.load(open(os.path.join(OUT_DIR, "fold7_done.json")))
    log(f"[VAULTREFIT] fold7_done.json: lam={fold7_done['selected_lam']:.6g} "
        f"l1_ratio={fold7_done['selected_l1_ratio']}")

    events = H.load_search_events()
    folds = H.build_folds(events)
    cache_info = H._cache_info()
    in_cols = cache_info["columns"]
    assert len(in_cols) == 1091, f"expected 1,091 IN columns, cache has {len(in_cols)}"

    fold7_train_n, fold7_val_n = len(folds[7]["train_ids"]), len(folds[7]["val_ids"])
    step_2b_prevault_fit(events, in_cols, fold7_done["selected_lam"], fold7_done["selected_l1_ratio"],
                         fold7_train_n, fold7_val_n)
    log(f"[VAULTREFIT] all done  [{time.time()-t0:.0f}s]")


if __name__ == "__main__":
    main()
