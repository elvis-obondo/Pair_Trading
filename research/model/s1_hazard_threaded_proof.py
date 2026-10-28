"""HL-MODEL1 S1: pointwise proof that the threaded hazard_nll_grad (current hazard_logistic.py) matches
the pre-threading, serial, B5-committed version EXACTLY -- this is the SAME arithmetic (same chunk
boundaries, same float64 cast per chunk, same summation order for grad_w), only parallelised across
threads, not an approximation. Checker's requirement, S1 review round 6: must run and be committed
BEFORE any real S1 fit uses the threaded kernel.

    python -u research/model/s1_hazard_threaded_proof.py > research/model/logs/s1_hazard_threaded_proof.log

OLD = the B5-committed hazard_logistic.py (git show bdddaf1:research/model/hazard_logistic.py --
EXTRACTED ON THE LAPTOP, where git is available, not inside this script: the VM this proof runs on has
no .git directory, same established pattern as b5_equivalence_step2.py's own OLD snapshot). The frozen
file is a plain sibling, research/model/_frozen_hazard_logistic_s1_threaded_proof.py -- synced to the VM
like any other file, its sha256 verified against the expected value below before use, deleted after this
script runs, never committed as a parallel file. NEW = the current, threaded hazard_logistic.hazard_nll_grad.

PROOF: on a real smoke subset (reuses s1_model_proof.py's own loader -- 20,000 events, the same 7
columns), at 5 random (w, b) points, NLL and both gradients match within 1e-10 relative (not an
approximation's tolerance -- an algebraic identity, same as b5_hazard_logistic_proof.py's own PROOF 1).
BROKEN VARIANT: NEW's own break_intercept=True (the shipped function's existing flag, not a
reimplementation) must make the match FAIL, proving this check can catch a real break.
"""
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402
from s1_preprocess import fit_preprocessing, apply_preprocessing  # noqa: E402
import hazard_logistic as NEW  # noqa: E402

OLD_COMMIT = "bdddaf1"
OLD_EXPECTED_SHA = "be657a4ca3d33ec94ae29a1a9132b61ea47966a46f5adedfddc2d34fdd028e58"
SEED = 20261028
N_SMOKE_EVENTS = 20_000
SMOKE_COLS = ["z", "threshold", "beta", "beta_stab", "r2", "ticker_a", "ticker_b"]
N_STEPS = H.N_STEPS
RTOL_EXACT = 1e-10
PASS = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    PASS.append(cond)
    print(f"[S1-THREADED-PROOF] {name}: {status}" + (f" -- {detail}" if detail else ""), flush=True)
    return cond


def load_old_module():
    import master_manifest as MF
    frozen_path = os.path.join(HERE, "_frozen_hazard_logistic_s1_threaded_proof.py")
    assert os.path.exists(frozen_path), (
        f"{frozen_path} is missing -- extract it on the LAPTOP first: "
        f"git show {OLD_COMMIT}:research/model/hazard_logistic.py > {frozen_path}")
    got = MF.sha(frozen_path)
    assert got == OLD_EXPECTED_SHA, (
        f"{frozen_path} sha {got[:12]}... does not match the expected OLD snapshot "
        f"{OLD_EXPECTED_SHA[:12]}... -- refusing to trust a stale or wrong frozen file")
    import importlib.util
    spec = importlib.util.spec_from_file_location("_frozen_hazard_logistic_s1_threaded_proof", frozen_path)
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    return old, frozen_path


def main():
    t0 = time.time()
    import master_manifest as MF
    print(f"[S1-THREADED-PROOF] sha256 {os.path.basename(__file__)}: {MF.sha(os.path.abspath(__file__))}",
          flush=True)
    print(f"[S1-THREADED-PROOF] sha256 hazard_logistic.py (NEW, threaded): "
          f"{MF.sha(os.path.join(HERE, 'hazard_logistic.py'))}", flush=True)
    gs = os.path.join(os.path.dirname(HERE), "dataset", "GIT_STATE.json")
    git_head, git_dirty = ("unavailable", "unavailable")
    if os.path.exists(gs):
        G = MF.json.load(open(gs))
        git_head, git_dirty = G.get("head", "unavailable"), len(G.get("porcelain", []))
    print(f"[S1-THREADED-PROOF] git_head {git_head} ({git_dirty} uncommitted paths); "
          f"start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC; pid {os.getpid()}", flush=True)

    old, frozen_path = load_old_module()
    print(f"[S1-THREADED-PROOF] sha256 OLD (git show {OLD_COMMIT}:research/model/hazard_logistic.py): "
          f"{MF.sha(frozen_path)}", flush=True)

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
    print(f"[S1-THREADED-PROOF] smoke subset: {n_events} events (seed {SEED}), {len(row_event_pos):,} "
          f"hazard rows  [{time.time()-t0:.0f}s]", flush=True)

    stats = fit_preprocessing(chosen, SMOKE_COLS)
    X_fit, out_cols = apply_preprocessing(chosen, SMOKE_COLS, stats)
    print(f"[S1-THREADED-PROOF] preprocessed: n_features={len(out_cols)}  [{time.time()-t0:.0f}s]",
          flush=True)

    rng2 = np.random.default_rng(SEED + 1)
    all_ok = True
    for trial in range(5):
        w = rng2.normal(scale=0.3, size=X_fit.shape[1])
        b = rng2.normal(scale=0.3, size=N_STEPS)
        nll_o, gw_o, gb_o = old.hazard_nll_grad(w, b, X_fit, row_event_pos, row_step, row_label, n_events)
        nll_n, gw_n, gb_n = NEW.hazard_nll_grad(w, b, X_fit, row_event_pos, row_step, row_label, n_events)
        ok = (np.isclose(nll_o, nll_n, rtol=RTOL_EXACT)
              and np.allclose(gw_o, gw_n, rtol=RTOL_EXACT, atol=1e-9)
              and np.allclose(gb_o, gb_n, rtol=RTOL_EXACT, atol=1e-9))
        print(f"[S1-THREADED-PROOF]   trial {trial}: nll_old={nll_o:.6f} nll_new={nll_n:.6f} "
              f"max|gw diff|={np.max(np.abs(gw_o-gw_n)):.2e} max|gb diff|={np.max(np.abs(gb_o-gb_n)):.2e}: "
              f"{'OK' if ok else 'MISMATCH'}", flush=True)
        all_ok = all_ok and ok
    check(f"threaded NEW matches serial OLD (git {OLD_COMMIT}) exactly at 5 random (w,b), "
          f"rtol={RTOL_EXACT:.0e}", all_ok)

    # BROKEN VARIANT: NEW's own break_intercept=True must make the match FAIL.
    w = rng2.normal(scale=0.3, size=X_fit.shape[1])
    b = rng2.normal(scale=0.3, size=N_STEPS)
    nll_o, gw_o, gb_o = old.hazard_nll_grad(w, b, X_fit, row_event_pos, row_step, row_label, n_events)
    nll_bad, gw_bad, gb_bad = NEW.hazard_nll_grad(w, b, X_fit, row_event_pos, row_step, row_label, n_events,
                                                   break_intercept=True)
    mismatch = not (np.isclose(nll_o, nll_bad, rtol=RTOL_EXACT)
                     and np.allclose(gw_o, gw_bad, rtol=RTOL_EXACT, atol=1e-9))
    check("BROKEN VARIANT -- NEW's own break_intercept=True correctly FAILS the match",
          mismatch, f"nll_old={nll_o:.4f} nll_broken={nll_bad:.4f}")

    os.remove(frozen_path)
    print(f"[S1-THREADED-PROOF] all done [{time.time()-t0:.0f}s]: {sum(PASS)}/{len(PASS)} checks PASS",
          flush=True)
    if not all(PASS):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
