"""HL-MODEL1 S1-F: two descriptive follow-up checks on the saved S1 logistic results (brief, 2026-10-31,
docs/prompts/HL_MODEL1_S1_FOLLOWUPS.md). The S1 gate verdict (FAIL, NUMBERS [HL-MODEL1-S1]) does not
change. No refit, no vault, no profit/fee/stop metrics. Reads the 8 folds' saved test predictions,
report.json and val_permutation_importance.csv, plus v1 events/labels and the cached IN-matrix for the
same event_ids. Run on the GCP VM (F2's shift check needs the cached IN-matrix, which only exists there).

    python -u research/model/s1f_followups.py > research/model/logs/s1f_followups.log

F1 (fixed cut-off): the cut-off is set from EARLIER test blocks only (Rule A = the immediately previous
block; Rule B = all earlier blocks pooled), then applied forward to block k -- what a live system would
actually have available, unlike S1's own in-block top-q% ranking (which needs the whole block's scores
at once, impossible live). Scored folds 1-7; fold 0 has no earlier block and is not scored.

F2 (why folds 5-7 are weaker): per-fold lift/drift-share table, reading what report.json and the saved
permutation-importance CSVs already have, computing only the vol_48-vs-other-94-drift split (report.json
only saves the combined drift share) and gap(all) = reach_10h_all - chance_10h_all. The shift check reads
RAW event-level column values (harness.load_fold_features_cached, same fold split S1 trained on) for each
fold's saved top-20 columns -- the fold's REFIT rows (train+val, same as S1's R1) vs its TEST block.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402
from s1_report import load_unexplained_drift_columns, top_k_mask  # noqa: E402

LOG_DIR = os.path.join(HERE, "logs", "s1")
N_FOLDS = 8
SEED = 20261031   # R7: one seed, logged, for every tie-break/resample in this script
N_RESAMPLES = 2000
LEVEL = 0.9875


def load_predictions():
    frames = [pd.read_csv(os.path.join(LOG_DIR, f"fold{k}_test_predictions.csv")) for k in range(N_FOLDS)]
    df = pd.concat(frames, ignore_index=True)
    event_ids = df["event_id"].to_numpy()
    events = H.load_search_events()
    sub = events.loc[event_ids]
    df["reach_10h"] = sub["reach_10h"].to_numpy()
    df["chance_10h"] = sub["chance_10h"].to_numpy()
    df["day"] = pd.to_datetime(sub["t0"].to_numpy()).floor("D")
    return df, events


def f1_fixed_cutoff(df, rng, report):
    """`report`: S1's saved report.json, used ONLY to cross-check the in-block (S1-way) mask against the
    already-scored values it saved at training time (checker's fix round 1, minor 2) -- with continuous
    p_10h scores the mask doesn't depend on this script's RNG, so the two must match exactly."""
    results = {"ruleA": {}, "ruleB": {}, "inblock": {}}
    for q in (0.01, 0.10):
        per_fold_A, per_fold_B, per_fold_inblock = {}, {}, {}
        reach_parts, chance_parts, day_parts = [], [], []
        maskA_parts, maskB_parts, maskIn_parts = [], [], []
        max_abs_diff = 0.0

        for k in range(1, N_FOLDS):
            block = df[df["fold"] == k]
            n_block = len(block)
            reach = block["reach_10h"].to_numpy()
            chance = block["chance_10h"].to_numpy()
            p10h = block["p_10h"].to_numpy()
            day = block["day"].to_numpy()
            n_active_days = block["day"].nunique()   # days with >=1 event in the block, not calendar days

            def scored_row(mask, c_k=None):
                row = {"n": int(mask.sum())}
                if c_k is not None:
                    row["c_k"] = c_k
                row["picks_per_active_day"] = row["n"] / n_active_days if n_active_days else None
                row["share"] = row["n"] / n_block if n_block else None
                if row["n"] > 0:
                    row["reach_10h"] = float(reach[mask].mean())
                    row["chance_10h"] = float(chance[mask].mean())
                    row["gap"] = H.gap(reach[mask], chance[mask])
                    row["lift"] = H.lift(reach[mask], chance[mask], reach, chance)
                else:
                    row["reach_10h"] = row["chance_10h"] = row["gap"] = row["lift"] = None
                return row

            # Rule A: previous block (k-1) only
            prev = df[df["fold"] == k - 1]["p_10h"].to_numpy()
            c_A = float(np.quantile(prev, 1 - q))
            mask_A = p10h >= c_A
            per_fold_A[k] = scored_row(mask_A, c_A)

            # Rule B: all earlier blocks pooled (0..k-1)
            earlier = df[df["fold"] < k]["p_10h"].to_numpy()
            c_B = float(np.quantile(earlier, 1 - q))
            mask_B = p10h >= c_B
            per_fold_B[k] = scored_row(mask_B, c_B)

            # In-block top-q% (the S1 way), same fold -- for comparison over the same months
            mask_in = top_k_mask(p10h, q, rng)
            row_in = scored_row(mask_in)
            per_fold_inblock[k] = row_in

            # Cross-check against S1's own saved value (checker's fix round 1, minor 2)
            saved = (report["gate"]["per_fold_lift"][str(k)] if q == 0.10
                     else report["m2_selectivity"]["0.01"]["per_fold"][str(k)])
            diff = abs(row_in["lift"] - saved) if row_in["lift"] is not None else float("nan")
            max_abs_diff = max(max_abs_diff, diff)
            if diff >= 1e-9:
                n_at_cutoff = int(np.sum(p10h == p10h[np.argsort(-p10h)[row_in["n"] - 1]])) if row_in["n"] else 0
                print(f"[S1F] WARNING fold {k} q={q}: in-block lift {row_in['lift']:.6f} != saved "
                      f"{saved:.6f} (diff {diff:.2e}); {n_at_cutoff} tied score(s) sit at the cut", flush=True)

            reach_parts.append(reach); chance_parts.append(chance); day_parts.append(day)
            maskA_parts.append(mask_A); maskB_parts.append(mask_B); maskIn_parts.append(mask_in)
        print(f"[S1F] F1 q={q}: in-block lift vs S1's saved value, max |diff| across folds 1-7 = "
              f"{max_abs_diff:.2e}", flush=True)
        assert max_abs_diff < 1e-9, (
            f"in-block lift at q={q} disagrees with S1's own saved value by {max_abs_diff:.2e} "
            f"(>= 1e-9) -- the continuous-score mask should be identical regardless of RNG")

        reach_cat = np.concatenate(reach_parts)
        chance_cat = np.concatenate(chance_parts)
        day_cat = np.concatenate(day_parts)
        maskA_cat = np.concatenate(maskA_parts)
        maskB_cat = np.concatenate(maskB_parts)
        maskIn_cat = np.concatenate(maskIn_parts)

        pA, loA, hiA = H.day_block_bootstrap(day_cat, maskA_cat, reach_cat, chance_cat, N_RESAMPLES, LEVEL, rng)
        pB, loB, hiB = H.day_block_bootstrap(day_cat, maskB_cat, reach_cat, chance_cat, N_RESAMPLES, LEVEL, rng)
        pIn, loIn, hiIn = H.day_block_bootstrap(day_cat, maskIn_cat, reach_cat, chance_cat, N_RESAMPLES, LEVEL, rng)

        results["ruleA"][q] = {"per_fold": per_fold_A, "pooled_point": pA, "pooled_lo": loA, "pooled_hi": hiA}
        results["ruleB"][q] = {"per_fold": per_fold_B, "pooled_point": pB, "pooled_lo": loB, "pooled_hi": hiB}
        results["inblock"][q] = {"per_fold": per_fold_inblock, "pooled_point": pIn, "pooled_lo": loIn, "pooled_hi": hiIn}
        print(f"[S1F] F1 q={q}: folds 1-7 pooled -- RuleA lift={pA:.4f} ({loA:.4f},{hiA:.4f}); "
              f"RuleB lift={pB:.4f} ({loB:.4f},{hiB:.4f}); in-block (S1 way) lift={pIn:.4f} "
              f"({loIn:.4f},{hiIn:.4f})", flush=True)
    return results


def f2_weaker_folds(folds, report, df):
    """`df`: F1's loaded test predictions, used only for the n_block cross-check (fix 3) -- F2's own
    n_block comes from `folds` (harness.build_folds), F1's comes from the saved CSVs; they must agree."""
    drift_cols = load_unexplained_drift_columns()
    other_drift_cols = drift_cols - {"vol_48"}
    assert len(other_drift_cols) == 94, (
        f"expected 94 drift columns excluding vol_48 (95 total per the brief), got {len(other_drift_cols)}")

    main_table = {}
    shift_table = {}
    for k in range(N_FOLDS):
        top20 = report["m6_drivers"]["per_fold_top20"][str(k)]
        top20_cols = [c["column"] for c in top20]
        top_col = top20[0]["column"]

        # READ from report.json (already computed at training time)
        lift10 = report["gate"]["per_fold_lift"][str(k)]
        lift1 = report["m2_selectivity"]["0.01"]["per_fold"][str(k)]
        m1 = report["m1_hit_rate"]["10h"]["per_fold"][str(k)]
        reach_all, chance_all = m1["all_reach"], m1["all_chance"]
        top_col_share = report["m6_drivers"]["top_col_share_by_fold"][str(k)]
        drift_share_total_saved = report["m6_drivers"]["drift_share_by_fold"][str(k)]

        # COMPUTED here: gap(all), and the vol_48-vs-other-94 drift split (report.json only has the
        # combined total) -- same positive-importance-only, same-total convention as s1_report.py's own
        # drift_share_by_fold, so the two numbers are comparable.
        gap_all = reach_all - chance_all
        imp = pd.read_csv(os.path.join(LOG_DIR, f"fold{k}_val_permutation_importance.csv")) \
            .set_index("column")["log_loss_increase"]
        imp = imp[imp > 0]
        total = imp.sum()
        if total > 0:
            vol48_share = float(imp.get("vol_48", 0.0) / total)
            other94_share = float(imp[imp.index.isin(other_drift_cols)].sum() / total)
        else:
            vol48_share = other94_share = 0.0
        drift_share_check = abs((vol48_share + other94_share) - drift_share_total_saved) < 1e-9

        n_block = len(folds[k]["test_ids"])
        n_block_csv = int((df["fold"] == k).sum())
        assert n_block == n_block_csv, (
            f"fold {k}: harness.build_folds test_ids count ({n_block}) != the saved "
            f"fold{k}_test_predictions.csv row count ({n_block_csv})")
        main_table[k] = {"lift_top10": lift10, "lift_top1": lift1, "drift_share_vol48": vol48_share,
                          "drift_share_other94": other94_share, "drift_share_total_check_ok": drift_share_check,
                          "top_col": top_col, "top_col_share": top_col_share, "n_block": n_block,
                          "reach_10h_all": reach_all, "chance_10h_all": chance_all, "gap_all": gap_all}

        # COMPUTED: event-level shift for every fold's top-20 column. refit = train+val (R1), test = the
        # fold's own test block.
        X_train, X_val, X_test, cols = H.load_fold_features_cached(folds[k], top20_cols)
        X_refit = np.vstack([X_train, X_val])
        shifts = []
        for j, col in enumerate(top20_cols):
            refit_col = X_refit[:, j]
            test_col = X_test[:, j]
            refit_col = refit_col[np.isfinite(refit_col)]
            test_col = test_col[np.isfinite(test_col)]
            refit_median = float(np.median(refit_col)) if len(refit_col) else None
            test_median = float(np.median(test_col)) if len(test_col) else None
            q25, q75 = np.percentile(refit_col, [25, 75]) if len(refit_col) else (None, None)
            iqr = (q75 - q25) if q25 is not None else None
            shift = ((test_median - refit_median) / iqr) if (iqr and iqr > 0) else None
            shifts.append({"column": col, "is_drift": col in drift_cols, "refit_median": refit_median,
                            "test_median": test_median, "refit_iqr": iqr, "shift": shift})
        drift_abs = [abs(s["shift"]) for s in shifts if s["is_drift"] and s["shift"] is not None]
        nondrift_abs = [abs(s["shift"]) for s in shifts if not s["is_drift"] and s["shift"] is not None]
        n_none = sum(1 for s in shifts if s["shift"] is None)
        shift_table[k] = {"columns": shifts, "n_shift_none": n_none,
                           "mean_abs_shift_drift": float(np.mean(drift_abs)) if drift_abs else None,
                           "mean_abs_shift_nondrift": float(np.mean(nondrift_abs)) if nondrift_abs else None}
        print(f"[S1F] F2 fold {k}: lift10={lift10:.4f} lift1={lift1:.4f} gap_all={gap_all:.4f} "
              f"drift_share vol48={vol48_share:.4f} other94={other94_share:.4f} (check_ok={drift_share_check}) "
              f"top_col={top_col}({top_col_share:.4f}) {n_none}/20 top-20 columns had shift=None "
              f"mean|shift| drift={shift_table[k]['mean_abs_shift_drift']} "
              f"nondrift={shift_table[k]['mean_abs_shift_nondrift']}", flush=True)
    return {"main_table": main_table, "shift_table": shift_table}


def main():
    import time
    t0 = time.time()
    import master_manifest as MF
    for name in ("s1f_followups.py", "harness.py", "s1_report.py", "inputs_v1_pair.csv"):
        print(f"[S1F] sha256 {name}: {MF.sha(os.path.join(HERE, name))}", flush=True)
    cache_info = H._cache_info()
    cache_sha = cache_info.get("cache_sha256", "NO VALID CACHE") if cache_info else "NO VALID CACHE"
    print(f"[S1F] cache manifest cache_sha256: {cache_sha} "
          f"(must be bd5dc2549374d0a80c8b042425e34119289b17b753a49213ac28c1831c6ca544)", flush=True)
    gs = os.path.join(os.path.dirname(HERE), "dataset", "GIT_STATE.json")
    git_head, git_dirty = ("unavailable", "unavailable")
    if os.path.exists(gs):
        G = MF.json.load(open(gs))
        git_head, git_dirty = G.get("head", "unavailable"), len(G.get("porcelain", []))
    print(f"[S1F] git_head {git_head} ({git_dirty} uncommitted paths); "
          f"start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC; pid {os.getpid()}; "
          f"seed={SEED}", flush=True)

    rng = np.random.default_rng(SEED)
    df, events = load_predictions()
    folds = H.build_folds(events)
    print(f"[S1F] loaded {len(df):,} test-predictions rows across {N_FOLDS} folds  [{time.time()-t0:.0f}s]",
          flush=True)

    report = json.load(open(os.path.join(LOG_DIR, "report.json")))
    f1 = f1_fixed_cutoff(df, rng, report)
    f2 = f2_weaker_folds(folds, report, df)

    out = {"f1_fixed_cutoff": f1, "f2_weaker_folds": f2}
    with open(os.path.join(LOG_DIR, "s1f_report.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)

    print("\n[S1F] === 10-LINE SUMMARY ===", flush=True)
    a1, b1, in1 = f1["ruleA"][0.01], f1["ruleB"][0.01], f1["inblock"][0.01]
    a10, b10, in10 = f1["ruleA"][0.10], f1["ruleB"][0.10], f1["inblock"][0.10]
    print(f"1. F1 top 1%, folds 1-7 pooled: Rule A (previous block) lift={a1['pooled_point']:.4f} "
          f"({a1['pooled_lo']:.4f},{a1['pooled_hi']:.4f}); Rule B (all earlier) lift={b1['pooled_point']:.4f} "
          f"({b1['pooled_lo']:.4f},{b1['pooled_hi']:.4f}); in-block (S1 way) lift={in1['pooled_point']:.4f} "
          f"({in1['pooled_lo']:.4f},{in1['pooled_hi']:.4f}).", flush=True)
    print(f"2. F1 top 10%, folds 1-7 pooled: Rule A lift={a10['pooled_point']:.4f} "
          f"({a10['pooled_lo']:.4f},{a10['pooled_hi']:.4f}); Rule B lift={b10['pooled_point']:.4f} "
          f"({b10['pooled_lo']:.4f},{b10['pooled_hi']:.4f}); in-block lift={in10['pooled_point']:.4f} "
          f"({in10['pooled_lo']:.4f},{in10['pooled_hi']:.4f}).", flush=True)
    n_zero_picks = sum(1 for rule in (a1, b1, a10, b10) for row in rule["per_fold"].values() if row["n"] == 0)
    print(f"3. {n_zero_picks} (rule,fold) cell(s) across both targets had 0 picks (reported as n=0, not dropped).",
          flush=True)
    mt = f2["main_table"]
    print(f"4. F2 per-fold lift@10%: " + ", ".join(f"f{k}={mt[k]['lift_top10']:.4f}" for k in range(N_FOLDS)) + ".",
          flush=True)
    print(f"5. F2 per-fold lift@1%: " + ", ".join(f"f{k}={mt[k]['lift_top1']:.4f}" for k in range(N_FOLDS)) + ".",
          flush=True)
    print(f"6. F2 per-fold total drift share: " +
          ", ".join(f"f{k}={mt[k]['drift_share_vol48']+mt[k]['drift_share_other94']:.4f}" for k in range(N_FOLDS)) +
          " (vol_48 alone vs the other 94 -- see the table).", flush=True)
    print(f"7. F2 per-fold top-column share: " + ", ".join(f"f{k}={mt[k]['top_col_share']:.4f}" for k in range(N_FOLDS))
          + ".", flush=True)
    st = f2["shift_table"]
    print(f"8. F2 mean |shift| (drift columns) by fold: " +
          ", ".join(f"f{k}={st[k]['mean_abs_shift_drift']}" for k in range(N_FOLDS)) + ".", flush=True)
    print(f"9. F2 mean |shift| (non-drift columns) by fold: " +
          ", ".join(f"f{k}={st[k]['mean_abs_shift_nondrift']}" for k in range(N_FOLDS)) + ".", flush=True)
    print("10. Descriptive only -- the gate verdict stays FAIL (NUMBERS [HL-MODEL1-S1]); no cause is "
          "claimed beyond what these tables show.", flush=True)
    print(f"[S1F] ALL DONE  [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
