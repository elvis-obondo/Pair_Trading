"""HL-MODEL1 B3: the five required proofs (proof 2, shuffled labels, is REMOVED per the user, 2026-10-27).
Every proof must be able to fail: each has a deliberately-broken variant that the proof's own check must
catch, so a proof that silently always passes is itself caught.

    python -u research/model/proofs_v1_pair.py > research/model/logs/proofs_v1_pair.log

NOT RUN YET. Sent to the checker before anything here touches the VM. All five were rewritten after the
checker's first review found three could not actually fail as first written (proofs 1, 3, 5) -- see each
proof's docstring for what was wrong and how it was fixed; re-tested against synthetic data before this
second send, same as the first.

1. LEAK CHECK (planted future column). A column built from reach_10h plus noise is checked two ways: (a)
   harness.check_inputs([real columns + the planted name]) must raise (the real gate a model-fitting script
   is required to call); (b) a BROKEN VARIANT that skips check_inputs and scores the planted column through
   the real fold-0 test block via harness.score_fold must show a lift >= 0.5 -- large enough that size alone
   catches it. Both must hold: (a) proves the gate rejects the leak before any model sees it; (b) proves
   that if the gate were skipped, the leak would be visible by its size, not by assumption.
3. PLANTED REAL SIGNAL of known size, run through the REAL 8-fold path (checker, 2026-10-27: the first
   version used a ranking column, vol_48, that already predicts chance_10h on its own (Part Z: raw AUC
   0.628), and generated a signal independent of chance -- so the measured "lift" was biased by vol_48's own
   relation to chance, and a null run with no planted effect would not sit at 0). Fixed: synthetic
   reach_i ~ Bernoulli(clip(chance_i - 0.11 + delta * 1[i in top decile of ITS OWN fold's test block], 0, 1)).
   Subtracting chance_i (not a constant) and ranking by the SAME column removes the chance-correlation bias
   by construction -- the gap formula's own chance term cancels it. delta is solved from the REAL pooled
   top-decile fraction across all 8 folds (not assumed to be exactly 0.10), and the REALISED expected lift
   (after clipping reach_i to [0, 1]) is computed analytically and logged next to the target, since clipping
   can move the achieved lift away from the pre-clipping target. Scored through harness.build_folds +
   harness.score_fold on every fold, pooled exactly as the real scoring will be, with
   harness.day_block_bootstrap at 2,000 resamples and the real 98.75% level (not 500 resamples on an
   arbitrary single pool, which the first version used).
4. HAZARD ROUND TRIP. The true step labels, fed back through 1 - prod_k (1 - h_k) with h_k in {0, 1}, must
   give exactly reach_10h on EVERY search event -- 0 mismatches. 2,000 events sampled and checked by hand
   with a DIFFERENT formula from the harness's own (step = 1 + (mtm - 1) // 30 on integer minutes, not
   ceil(mtm / 30) -- the same formula would not be an independent check), plus an assert that minutes_to_mu
   is an integer in [1, 600] for every reacher sampled. The hazard frame is indexed by event_id before the
   2,000-event loop (checker: filtering ~100M rows by boolean mask 2,000 times is very slow).
5. VAULT AND BOUNDARY ASSERTS. A vault-dated row (t0 = 2026-07-13) is injected into the REAL events frame
   and passed to harness.build_folds and harness.build_hazard_rows directly -- both must raise (via
   harness.assert_search_only, checked at each function's entry). The BROKEN VARIANT monkeypatches
   harness.assert_search_only to a no-op and re-runs the same calls, which must NOT raise, proving it is
   that specific check -- not an accident of date-range filtering -- that catches the row (checker,
   2026-10-27: the first version only showed the row got excluded by ordinary date filtering, which proved
   nothing about whether any real check would fire if the filtering were ever wrong).
6. INDEPENDENT RECOMPUTE. Fold 0's dates, embargo drops and lift are recomputed by a deliberately SEPARATE,
   short, from-scratch implementation (no harness.py calls) ranking by vol_48 (checker: the first version
   picked "the first numeric column," which can be event_id) and compared to harness.py's own numbers, plus
   both sides' embargo-drop counts (B3 explicitly lists "embargo drops").

OUTPUT: printed PASS/FAIL per proof with the numbers; research/model/logs/proofs_v1_pair.log.
"""
import csv
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "research", "dataset"))
import harness as H  # noqa: E402
import master_manifest as MF  # noqa: E402

PLANTED_COL = "__planted_leak_column__"


def _in_columns():
    rows = list(csv.DictReader(open(os.path.join(HERE, "inputs_v1_pair.csv"))))
    return sorted(r["column"] for r in rows if r["in_out"] == "IN")


def proof1_leak_check(events, seed=1):
    print("[PROOF 1] leak check by planted future column")
    rng = np.random.default_rng(seed)
    real_in = _in_columns()
    try:
        H.check_inputs(real_in + [PLANTED_COL])
        ok_gate_raised = False
        print("   BUG: check_inputs did NOT raise with the planted column included")
    except ValueError as e:
        ok_gate_raised = True
        print(f"   (a) check_inputs correctly raised with the planted column included: {e}")

    print("   (b) broken variant: skip check_inputs, score the planted column through the real fold-0 path")
    planted = events["reach_10h"].to_numpy() + rng.normal(0, 0.01, len(events))
    folds = H.build_folds(events)
    test0 = events.loc[folds[0]["test_ids"]]
    planted_test = planted[np.isin(events.index.to_numpy(), folds[0]["test_ids"])]
    lift_val, _ = H.score_fold(planted_test, test0, np.random.default_rng(seed + 1))
    print(f"   broken-variant lift on fold 0's test block: {lift_val:.4f} (must be >= 0.5)")
    ok_leak_visible = lift_val >= 0.5

    passed = ok_gate_raised and ok_leak_visible
    print(f"[PROOF 1] {'PASS' if passed else 'FAIL'}")
    return passed


def proof3_planted_signal(events, target_lift=0.08, seed=3):
    """Checker, 2026-10-27, round 2: the first version used p = clip(chance - 0.11 + delta*top, 0, 1). The
    -0.11 offset buys nothing (a constant cancels in lift by construction) and is actively harmful: for any
    event with chance_10h < 0.11 (most of decile 0), clipping sets p = 0 instead of -0.11, so the gap
    becomes -chance instead of -0.11 -- an error that is NOT the same for the top 10% (which correlates
    with chance via the ranking column) as for the whole block, biasing even the delta=0 null away from 0.
    Fixed: p = clip(chance + delta*top, 0, 1). At delta=0 this is exactly chance, so the null's expected
    lift is EXACTLY 0 (no clipping possible, chance_10h is already in [0,1]) -- asserted, not just hoped.
    The top set is determined ONCE per fold with a fixed, reusable seed and reused for BOTH planting the
    signal and scoring it through H.score_fold with that same seed, so planting and scoring cannot disagree
    on a tied score's side of the cut."""
    print(f"[PROOF 3] planted real signal of known size (target lift {target_lift}), run through the real 8-fold path")
    ranking_col = "vol_48" if "vol_48" in events.columns else events.select_dtypes("number").columns[0]
    x_full = events[ranking_col].to_numpy(dtype=float)
    finite = np.isfinite(x_full)
    x_full = np.where(finite, x_full, np.nanmedian(x_full[finite]))
    chance_full = events["chance_10h"].to_numpy(dtype=float)
    event_id_full = events.index.to_numpy()
    assert np.all((chance_full >= 0) & (chance_full <= 1)), "chance_10h outside [0, 1] -- a data problem, not this proof's"

    folds = H.build_folds(events)
    fold_info = []
    for f in folds:
        if not len(f["test_ids"]):
            fold_info.append(None)
            continue
        test_mask = np.isin(event_id_full, f["test_ids"])
        sub_x = x_full[test_mask]
        sub_chance = chance_full[test_mask]
        n_sub = len(sub_x)
        tie_seed = seed + 1000 + f["k"]
        n_top_f = max(1, int(np.ceil(0.10 * n_sub)))
        tie_key = np.random.default_rng(tie_seed).random(n_sub)   # mirrors score_fold's own tie-break exactly
        order = np.lexsort((tie_key, -sub_x))
        top_mask_f = np.zeros(n_sub, dtype=bool)
        top_mask_f[order[:n_top_f]] = True
        fold_info.append(dict(k=f["k"], sub_x=sub_x, sub_chance=sub_chance, top_mask_f=top_mask_f,
                               tie_seed=tie_seed, test_index=events.index[test_mask]))

    live = [fi for fi in fold_info if fi]
    n_top_total = sum(int(fi["top_mask_f"].sum()) for fi in live)
    n_test_total = sum(len(fi["sub_x"]) for fi in live)
    frac_top_pooled = n_top_total / n_test_total if n_test_total else 0.10

    def realised_lift_for_delta(delta_):
        """Analytical expected lift over the pooled TEST rows only (not all search events), given delta."""
        p_all, chance_all, p_top, chance_top = [], [], [], []
        for fi in live:
            p = np.clip(fi["sub_chance"] + delta_ * fi["top_mask_f"], 0, 1)
            p_all.append(p); chance_all.append(fi["sub_chance"])
            p_top.append(p[fi["top_mask_f"]]); chance_top.append(fi["sub_chance"][fi["top_mask_f"]])
        p_all, chance_all = np.concatenate(p_all), np.concatenate(chance_all)
        p_top, chance_top = np.concatenate(p_top), np.concatenate(chance_top)
        return float(np.mean(p_top) - np.mean(chance_top) - (np.mean(p_all) - np.mean(chance_all)))

    delta = target_lift / (1 - frac_top_pooled)
    for _ in range(5):
        realised = realised_lift_for_delta(delta)
        if abs(realised - target_lift) <= 0.005 or realised == 0:
            break
        delta *= target_lift / realised
    print(f"   pooled top fraction across all 8 folds' test blocks: {frac_top_pooled:.4f} ({n_top_total:,} of {n_test_total:,})")
    print(f"   solved delta = {delta:.4f}; realised expected lift over TEST rows only (target {target_lift}): {realised:.4f}")
    ok_realised_close = abs(realised - target_lift) <= 0.005

    realised0 = realised_lift_for_delta(0.0)
    print(f"   null (delta=0) realised expected lift: {realised0:.9f} (must be exactly 0 -- p = chance exactly, no clipping possible)")
    ok_null_exact = abs(realised0) < 1e-9

    def run(delta_, tag):
        rng_draw = np.random.default_rng(seed + 50)
        reach_all, chance_all, top_mask_all, day_all = [], [], [], []
        per_fold_lift = []
        for fi in live:
            p = np.clip(fi["sub_chance"] + delta_ * fi["top_mask_f"], 0, 1)
            synth_reach_f = (rng_draw.random(len(p)) < p).astype(float)
            test_sub = events.loc[fi["test_index"]].copy()
            test_sub["reach_10h"] = synth_reach_f
            lift_f, top_mask_check = H.score_fold(fi["sub_x"], test_sub, np.random.default_rng(fi["tie_seed"]))
            assert np.array_equal(top_mask_check, fi["top_mask_f"]), \
                f"fold {fi['k']}: scoring's top_mask disagreed with planting's despite the same tie seed"
            per_fold_lift.append(lift_f)
            reach_all.append(synth_reach_f)
            chance_all.append(fi["sub_chance"])
            top_mask_all.append(fi["top_mask_f"])
            day_all.append(test_sub["t0"].dt.floor("D").to_numpy())
        reach_all, chance_all = np.concatenate(reach_all), np.concatenate(chance_all)
        top_mask_all, day_all = np.concatenate(top_mask_all), np.concatenate(day_all)
        pooled = H.pooled_lift(reach_all, chance_all, top_mask_all)
        point, lo, hi = H.day_block_bootstrap(day_all, top_mask_all, reach_all, chance_all,
                                               n_resamples=2000, level=0.9875, rng=np.random.default_rng(seed + 100))
        print(f"   [{tag}] measured pooled lift {pooled:.4f}, 98.75% interval [{lo:.4f}, {hi:.4f}], "
              f"positive folds {sum(1 for l in per_fold_lift if l > 0)}/{len(per_fold_lift)}")
        return pooled, lo, hi

    pooled, lo, hi = run(delta, "planted")
    ok_recovered = lo <= target_lift <= hi
    print(f"   target {target_lift} inside interval: {ok_recovered}")

    pooled0, lo0, hi0 = run(0.0, "null")
    ok_null_interval = lo0 <= 0 <= hi0
    print(f"   null interval contains 0: {ok_null_interval}")

    passed = ok_realised_close and ok_null_exact and ok_recovered and ok_null_interval
    print(f"[PROOF 3] {'PASS' if passed else 'FAIL'}")
    return passed


def _hand_check_hazard(hz, sample):
    """Independent hand-check, deliberately using a DIFFERENT formula from harness.build_hazard_rows's
    ceil(mtm/30): step = 1 + (mtm-1)//30 on integer minutes. Returns (bad_boundaries, bad_integer_mtm)."""
    hz_by_event = hz.set_index("event_id")  # indexed once, not re-filtered per sampled event (checker: speed)
    bad_boundaries = 0
    bad_integer_mtm = 0
    for eid, row in sample.iterrows():
        mtm = row["minutes_to_mu"]
        rows = hz_by_event.loc[[eid]] if eid in hz_by_event.index else hz_by_event.iloc[0:0]
        if np.isfinite(mtm):
            if mtm != round(mtm) or mtm < 1 or mtm > 600:
                bad_integer_mtm += 1
                continue
            expected_step = 1 + (int(mtm) - 1) // 30
            got = rows.loc[rows["label"] == 1, "step"]
            if len(got) != 1 or int(got.iloc[0]) != expected_step or len(rows) != expected_step:
                bad_boundaries += 1
        else:
            if len(rows) != 20 or rows["label"].sum() != 0:
                bad_boundaries += 1
    return bad_boundaries, bad_integer_mtm


def _build_hazard_rows_broken(events):
    """Deliberately WRONG hazard-row builder (checker, 2026-10-27): step = floor(mtm/30) + 1 instead of
    ceil(mtm/30). These agree only when mtm is not an exact multiple of 30 (e.g. mtm=31 -> floor(31/30)+1=2,
    matches; mtm=30 -> floor(30/30)+1=2, WRONG, should be 1), so this must be caught by the hand-check."""
    mtm = events["minutes_to_mu"].to_numpy(dtype=float)
    reach = events["reach_10h"].to_numpy(dtype=float)
    reached = np.isfinite(mtm)
    step_reach = np.floor(mtm / H.STEP_MINUTES) + 1   # the deliberate bug
    n_rows = np.where(reached, step_reach, H.N_STEPS).astype(np.int64)
    event_ids = events.index.to_numpy()
    total = int(n_rows.sum())
    offsets = np.concatenate([[0], np.cumsum(n_rows)[:-1]])
    row_event = np.repeat(event_ids, n_rows)
    row_within = np.arange(total) - np.repeat(offsets, n_rows)
    steps = row_within + 1
    is_last_row = steps == np.repeat(n_rows, n_rows)
    labels = (is_last_row & np.repeat(reached, n_rows)).astype(np.int8)
    return pd.DataFrame({"event_id": row_event, "step": steps, "label": labels})


def proof4_hazard_round_trip(events, n_sample=2000, seed=4):
    print("[PROOF 4] hazard round trip")
    try:
        hz = H.build_hazard_rows(events)
    except AssertionError as e:
        print(f"[PROOF 4] FAIL: harness.build_hazard_rows raised: {e}")
        return False

    recon = hz.groupby("event_id")["label"].max().reindex(events.index, fill_value=0).to_numpy()
    reach = events["reach_10h"].to_numpy()
    mismatches = int((recon.astype(float) != reach.astype(float)).sum())
    print(f"   reach_10h vs reconstructed-from-true-labels mismatches: {mismatches} of {len(events):,}")

    sample = events.sample(n=min(n_sample, len(events)), random_state=seed)
    bad_boundaries, bad_integer_mtm = _hand_check_hazard(hz, sample)
    print(f"   step-boundary hand-check on {len(sample):,} events (independent formula 1+(mtm-1)//30): "
          f"{bad_boundaries} bad boundaries, {bad_integer_mtm} non-integer/out-of-range minutes_to_mu")
    ok_real = mismatches == 0 and bad_boundaries == 0 and bad_integer_mtm == 0

    # the proof must be able to fail: a deliberately broken hazard frame must trip the SAME hand-check
    broken_sample = sample[np.isfinite(sample["minutes_to_mu"]) & (sample["minutes_to_mu"] % 30 == 0)]
    if len(broken_sample) == 0:
        broken_sample = sample[np.isfinite(sample["minutes_to_mu"])].copy()
        broken_sample["minutes_to_mu"] = (broken_sample["minutes_to_mu"] // 30) * 30
        broken_sample = broken_sample[broken_sample["minutes_to_mu"] >= 30]
    hz_broken = _build_hazard_rows_broken(events)
    broken_bad, broken_bad_int = _hand_check_hazard(hz_broken, broken_sample)
    print(f"   broken-variant check on {len(broken_sample):,} exact-multiple-of-30 events: "
          f"{broken_bad} bad boundaries (must be > 0, proving the hand-check can fail)")
    ok_can_fail = broken_bad > 0

    passed = ok_real and ok_can_fail
    print(f"[PROOF 4] {'PASS' if passed else 'FAIL'}")
    return passed


def proof5_vault_boundary_assert(events):
    print("[PROOF 5] vault and boundary asserts")
    bad = events.copy()
    injected_id = -999999
    bad_row = bad.iloc[[0]].copy()
    bad_row.index = [injected_id]
    bad_row["event_id"] = injected_id
    bad_row["t0"] = pd.Timestamp("2026-07-13T00:00:00Z")
    bad2 = pd.concat([bad, bad_row])

    score_fold_scores = bad2["chance_10h"].fillna(0.3).to_numpy() if "chance_10h" in bad2.columns else np.zeros(len(bad2))
    calls = {
        "build_folds": lambda: H.build_folds(bad2),
        "build_hazard_rows": lambda: H.build_hazard_rows(bad2),
        "score_fold": lambda: H.score_fold(score_fold_scores, bad2, np.random.default_rng(5)),
    }

    results = {}
    for fn_name, fn in calls.items():
        try:
            fn()
            results[fn_name] = False
            print(f"   {fn_name}: BUG, did not raise with a vault-dated row injected directly")
        except AssertionError as e:
            results[fn_name] = True
            print(f"   {fn_name}: correctly raised ({e})")
    ok_intact = all(results.values())

    orig = H.assert_search_only
    H.assert_search_only = lambda df, where: None
    broken_results = {}
    try:
        for fn_name, fn in calls.items():
            try:
                fn()
                broken_results[fn_name] = True   # did NOT raise -- expected for the broken variant
            except AssertionError:
                broken_results[fn_name] = False  # still raised despite the patch -- means some OTHER check caught it
    finally:
        H.assert_search_only = orig
    ok_broken_did_not_raise = all(broken_results.values())
    print(f"   with assert_search_only monkeypatched off: {list(calls)} raised = "
          f"{ {k: not broken_results.get(k) for k in calls} } (all should be False, proving assert_search_only "
          f"was the thing catching it)")

    passed = ok_intact and ok_broken_did_not_raise
    print(f"[PROOF 5] {'PASS' if passed else 'FAIL'}")
    return passed


def proof6_independent_recompute(events):
    print("[PROOF 6] independent recompute (fold 0, from scratch, no harness.py calls)")
    test_start = pd.Timestamp("2025-11-21T00:00:00Z")
    test_end = pd.Timestamp("2025-12-21T00:00:00Z")
    fit_cutoff = test_start - pd.Timedelta(days=1)
    n_before_test_embargo_indep = int(((events["t0"] >= fit_cutoff) & (events["t0"] < test_start)).sum())
    fit = events[events["t0"] < fit_cutoff]
    fit_days = sorted(fit["t0"].dt.floor("D").unique())
    n_val_days = max(1, int(np.ceil(0.2 * len(fit_days))))
    val_days = set(fit_days[-n_val_days:])
    val_start = min(val_days)
    embargo_day = val_start - pd.Timedelta(days=1)
    n_before_val_embargo_indep = int((fit["t0"].dt.floor("D") == embargo_day).sum())
    train = fit[fit["t0"].dt.floor("D") < embargo_day]
    val = fit[fit["t0"].dt.floor("D").isin(val_days)]
    test = events[(events["t0"] >= test_start) & (events["t0"] < test_end)]

    reach, chance = test["reach_10h"].to_numpy(), test["chance_10h"].to_numpy()
    ranking_col = "vol_48" if "vol_48" in events.columns else events.select_dtypes("number").columns[0]
    x = test[ranking_col].to_numpy(dtype=float) if len(test) else np.array([])
    n = len(test)
    n_top = max(1, int(np.ceil(0.10 * n))) if n else 0
    tie_seed = 6
    # checker, 2026-10-27: x can tie at the top-10% cut, and an unseeded argsort on one side vs score_fold's
    # seeded lexsort on the other could then disagree on which tied row lands in the top decile for a
    # harmless reason. Detect ties at the cut and, if any, use the SAME seeded tie-break on both sides.
    if n:
        x_filled = np.nan_to_num(x, nan=-1e18)
        sorted_desc = np.sort(x_filled)[::-1]
        cut_value = sorted_desc[n_top - 1]
        n_ties_at_cut = int(np.sum(x_filled == cut_value))
        print(f"   rows tied at the top-10% cut value ({cut_value:.6g}): {n_ties_at_cut}"
              + (" -- using the same seeded tie-break on both sides" if n_ties_at_cut > 1 else ""))
        tie_key = np.random.default_rng(tie_seed).random(n)
        order = np.lexsort((tie_key, -x_filled))
    else:
        n_ties_at_cut = 0
        order = np.array([], dtype=int)
    top = order[:n_top]
    indep_lift = (float(np.mean(reach[top]) - np.mean(chance[top])) - float(np.mean(reach) - np.mean(chance))) if n else float("nan")

    folds = H.build_folds(events)
    f0 = folds[0]
    ids_match = (set(train.index) == set(f0["train_ids"])) and (set(val.index) == set(f0["val_ids"])) and (set(test.index) == set(f0["test_ids"]))
    hs_lift, hs_top = H.score_fold(x, events.loc[f0["test_ids"]], np.random.default_rng(tie_seed)) if len(f0["test_ids"]) else (float("nan"), np.array([]))

    print(f"   train/val/test id sets equal: {ids_match}")
    print(f"   embargo drops before test: independent {n_before_test_embargo_indep:,} vs harness "
          f"{f0['n_dropped_before_test_embargo']:,}, equal: {n_before_test_embargo_indep == f0['n_dropped_before_test_embargo']}")
    print(f"   embargo drops before val: independent {n_before_val_embargo_indep:,} vs harness "
          f"{f0['n_dropped_before_val_embargo']:,}, equal: {n_before_val_embargo_indep == f0['n_dropped_before_val_embargo']}")
    lift_equal = abs(indep_lift - hs_lift) < 1e-9 if np.isfinite(indep_lift) and np.isfinite(hs_lift) else len(test) == 0
    print(f"   lift: independent {indep_lift:.6f} vs harness {hs_lift:.6f}, equal (1e-9): {lift_equal}")

    passed = (ids_match and lift_equal
              and n_before_test_embargo_indep == f0["n_dropped_before_test_embargo"]
              and n_before_val_embargo_indep == f0["n_dropped_before_val_embargo"])
    print(f"[PROOF 6] {'PASS' if passed else 'FAIL'}")
    return passed


def main():
    t0 = time.time()
    gs = os.path.join(ROOT, "research", "dataset", "GIT_STATE.json")
    git_head, git_dirty = ("unavailable", "unavailable")
    if os.path.exists(gs):
        G = MF.json.load(open(gs))
        git_head, git_dirty = G.get("head", "unavailable"), len(G.get("porcelain", []))
    for f in (os.path.abspath(__file__), os.path.join(HERE, "harness.py"), os.path.join(HERE, "inputs_v1_pair.csv"),
              os.path.join(ROOT, "research", "dataset", "master_manifest.py")):
        print(f"[PROOFS] sha256 {os.path.relpath(f, ROOT)}: {MF.sha(f)}", flush=True)
    print(f"[PROOFS] git_head {git_head} ({git_dirty} uncommitted paths); "
          f"start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC; pid {os.getpid()}", flush=True)
    print("[PROOFS] seeds used: proof1=1 (and +1 for score_fold's tie-break); proof3=3 (and +100 for the "
          "bootstrap, +k per fold's score_fold tie-break); proof4=4 (sample selection); proof5=none (no "
          "randomness); proof6=6 (score_fold tie-break, irrelevant when scores are distinct)", flush=True)

    events = H.load_search_events(columns=["vol_48"])
    print(f"[PROOFS] loaded {len(events):,} search events  [{time.time()-t0:.0f}s]")

    results = {
        "proof1_leak_check": proof1_leak_check(events),
        "proof3_planted_signal": proof3_planted_signal(events),
        "proof4_hazard_round_trip": proof4_hazard_round_trip(events),
        "proof5_vault_boundary_assert": proof5_vault_boundary_assert(events),
        "proof6_independent_recompute": proof6_independent_recompute(events),
    }
    print(f"[PROOFS] summary: {results}")
    print(f"[PROOFS] ALL PASS: {all(results.values())}  [{time.time()-t0:.0f}s]")


if __name__ == "__main__":
    main()
