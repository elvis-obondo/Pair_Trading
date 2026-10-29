"""HL-MODEL1 S1 Step 3: the report. Reads the 8 folds' saved outputs (research/model/logs/s1/, pulled
from S3 via `aws s3 sync s3://pair-trading-hl-289869684922/s1_run/logs/{A,B}/outputs/ research/model/logs/s1/`
for each machine -- no wrapper script, just those two sync calls), computes Part A's gate through harness
functions and nothing else, then the M1-M6 use-case metrics (descriptive only, never a gate, never used
to pick settings -- R2/R8e already fixed the settings at training time).

    python -u research/model/s1_report.py > research/model/logs/s1_report.log

Vault safety: imports only `harness` (never `vault_loader`); every event used here comes from the 8 test
blocks already restricted to the search period by `build_folds`/`assert_search_only` at TRAINING time, and
this script's own `load_search_events` call re-applies the same filter.

Design choices beyond the brief's own wording (flagged for the checker, not buried):
  - Report-time scoring (the gate's per-fold/pooled lift, the bootstrap, and every top-k% ranking in
    M1/M2/M4/M5) uses ITS OWN seed (REPORT_SEED below), not a replay of training-time rng state. Training
    time already used its own per-fold seed (R7) for the grid search's tie-breaks and M6's permutation
    importance; reproducing that exact draw sequence here would mean replaying every grid-point and
    permutation-importance rng draw in order, which is fragile and not what R7 asks for. One report-time
    seed, logged once, governs every tie-break and resample in this script -- consistent methodology
    across the gate and all six M-metrics, not a bit-exact replay of the training run.
  - M6's group rollup: inputs_v1_pair.csv's `file` column names 15 raw group files (g2, g2b, g3, g4,
    g5_a/g5_b/g5_net/g5_shape, g6_a/g6_b/g6_net, g7, g8, g9a) plus events.parquet. Rolled up to the
    brief's "events, G2..G9" naming by canonical prefix: g5_* -> G5, g6_* -> G6, everything else maps
    1:1 (g2b stays its own group, not folded into G2 -- it is a distinct raw file, not a direction split
    of g2).
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402

LOG_DIR = os.path.join(HERE, "logs", "s1")
N_FOLDS = 8
REPORT_SEED = 20261029   # R7: one seed, logged, for every tie-break/resample in THIS script
N_RESAMPLES = 2000
LEVEL = 0.9875
DRIFT_CSV = os.path.join(os.path.dirname(os.path.dirname(HERE)), "docs", "release_v1",
                          "drift_explained_pair.csv")
INPUTS_CSV = os.path.join(HERE, "inputs_v1_pair.csv")

GROUP_PREFIX_MAP = {
    "g5_a": "G5", "g5_b": "G5", "g5_net": "G5", "g5_shape": "G5",
    "g6_a": "G6", "g6_b": "G6", "g6_net": "G6",
}


def canonical_group(file_name):
    stem = file_name.replace(".parquet", "")
    if stem == "events":
        return "events"
    return GROUP_PREFIX_MAP.get(stem, stem.upper())


def load_column_group_map():
    """column name -> canonical group (events, G2, G2B, G3, G4, G5, G6, G7, G8, G9), IN columns only."""
    import csv
    rows = list(csv.DictReader(open(INPUTS_CSV)))
    return {r["column"]: canonical_group(r["file"]) for r in rows if r["in_out"] == "IN"}


def load_unexplained_drift_columns():
    import csv
    rows = list(csv.DictReader(open(DRIFT_CSV)))
    unexplained = {r["column"] for r in rows if r["cause"] == "unexplained"}
    in_cols = set(load_column_group_map().keys())
    cols = sorted(unexplained & in_cols)
    print(f"[S1-REPORT] unexplained-drift IN columns: {len(cols)} (brief says 95)")
    return set(cols)


def top_k_mask(scores, frac, rng):
    """Same tie-break convention as harness.score_fold: rank by `scores` descending, ties broken by a
    seeded random key (not row order), so a tied model's earliest events don't always win the top slice."""
    n = len(scores)
    n_top = max(1, int(np.ceil(frac * n)))
    tie_key = rng.random(n)
    order = np.lexsort((tie_key, -np.asarray(scores)))
    mask = np.zeros(n, dtype=bool)
    mask[order[:n_top]] = True
    return mask


def pooled_top_mask(df, score_col, frac, rng):
    """Checker's finding: A5's own pooling takes each test BLOCK's own top-k% (score_fold ranks within a
    fold, never across them), then concatenates -- a single top_k_mask over the whole pooled df ranks
    across fold boundaries instead, which is a different (and wrong) population. `df` must be ordered by
    fold (load_all_folds already concatenates fold0..fold7 in order), so concatenating each fold's own
    mask in that same order realigns with df's own row order."""
    masks = [top_k_mask(df[df["fold"] == k][score_col].to_numpy(), frac, rng) for k in range(N_FOLDS)]
    return np.concatenate(masks)


def load_all_folds():
    """Loads every fold's test predictions, grid log, coefficients and permutation importance. Returns
    (test_df, grid_selected, coefs_by_fold, perm_imp_by_fold)."""
    test_frames = []
    grid_selected = {}
    coefs_by_fold = {}
    perm_imp_by_fold = {}
    for k in range(N_FOLDS):
        prefix = os.path.join(LOG_DIR, f"fold{k}")
        done = json.load(open(f"{prefix}_done.json"))
        assert done["fold"] == k
        test_frames.append(pd.read_csv(f"{prefix}_test_predictions.csv"))
        grid = json.load(open(f"{prefix}_grid.json"))
        grid_selected[k] = grid["selected"]
        coefs_by_fold[k] = pd.read_csv(f"{prefix}_coefs.csv")
        perm_imp_by_fold[k] = pd.read_csv(f"{prefix}_val_permutation_importance.csv")
        print(f"[S1-REPORT] fold {k}: n_test={len(test_frames[-1]):,} "
              f"selected l1_ratio={grid_selected[k]['l1_ratio']} lam={grid_selected[k]['lam']:.6g} "
              f"refit_converged={done['refit_converged']} refit_rel_change={done.get('refit_rel_change')} "
              f"KKT={done.get('refit_kkt', {}).get('max_violation')}")
    test_df = pd.concat(test_frames, ignore_index=True)
    return test_df, grid_selected, coefs_by_fold, perm_imp_by_fold


def attach_labels(test_df):
    """Joins each test row's own event-level labels. One load_search_events call for every event used
    anywhere in the report (test labels only -- the search filter already applies)."""
    ids = test_df["event_id"].to_numpy()
    events = H.load_search_events(columns=["ticker_a", "ticker_b", "reach_2h", "chance_2h",
                                            "reach_5h", "chance_5h"])
    sub = events.loc[ids]
    out = test_df.copy()
    for c in ("reach_2h", "chance_2h", "reach_5h", "chance_5h", "reach_10h", "chance_10h",
              "minutes_to_mu", "ticker_a", "ticker_b", "t0"):
        out[c] = sub[c].to_numpy()
    return out


def part_a_gate(df, rng):
    """A5's own gate, computed with harness.score_fold/pooled_lift/day_block_bootstrap/pass_search and
    nothing else. Each fold's own top-10% mask comes from a FRESH score_fold call on just that fold's
    test rows (report-time seed, not a replay of the training run's draws -- see module docstring)."""
    reach_all, chance_all, top_mask_all = [], [], []
    per_fold_lift = {}
    for k in range(N_FOLDS):
        sub = df[df["fold"] == k]
        lift_k, top_mask_k = H.score_fold(sub["p_10h"].to_numpy(), sub, rng)
        per_fold_lift[k] = lift_k
        reach_all.append(sub["reach_10h"].to_numpy())
        chance_all.append(sub["chance_10h"].to_numpy())
        top_mask_all.append(top_mask_k)
        print(f"[S1-REPORT] gate: fold {k} lift={lift_k:.4f}")
    reach_all = np.concatenate(reach_all)
    chance_all = np.concatenate(chance_all)
    top_mask_all = np.concatenate(top_mask_all)
    pooled = H.pooled_lift(reach_all, chance_all, top_mask_all)
    day_of_event = df["t0"].dt.floor("D").to_numpy()
    point, lo, hi = H.day_block_bootstrap(day_of_event, top_mask_all, df["reach_10h"].to_numpy(),
                                           df["chance_10h"].to_numpy(), N_RESAMPLES, LEVEL, rng)
    n_positive = sum(1 for v in per_fold_lift.values() if v > 0)
    verdict, reason = H.pass_search(pooled, lo, n_positive, n_folds=N_FOLDS)
    print(f"[S1-REPORT] gate: pooled_lift={pooled:.4f} bootstrap=({point:.4f},{lo:.4f},{hi:.4f}) "
          f"n_positive={n_positive}/{N_FOLDS} verdict={verdict} ({reason})")
    return {"per_fold_lift": per_fold_lift, "pooled_lift": pooled, "bootstrap_point": point,
            "bootstrap_lo": lo, "bootstrap_hi": hi, "n_positive": n_positive, "verdict": verdict,
            "reason": reason}


def m1_hit_rate(df, rng):
    """For 2h/5h/10h, each ranked by its OWN p_h: reach rate and chance rate of the top 10%, and of all
    events, per fold and pooled."""
    out = {}
    for h, p_col, reach_col, chance_col in (("2h", "p_2h", "reach_2h", "chance_2h"),
                                             ("5h", "p_5h", "reach_5h", "chance_5h"),
                                             ("10h", "p_10h", "reach_10h", "chance_10h")):
        per_fold = {}
        for k in range(N_FOLDS):
            sub = df[df["fold"] == k]
            mask = top_k_mask(sub[p_col].to_numpy(), 0.10, rng)
            per_fold[k] = {"top_reach": float(sub[reach_col].to_numpy()[mask].mean()),
                           "top_chance": float(sub[chance_col].to_numpy()[mask].mean()),
                           "all_reach": float(sub[reach_col].mean()),
                           "all_chance": float(sub[chance_col].mean())}
        mask_pooled = pooled_top_mask(df, p_col, 0.10, rng)
        pooled = {"top_reach": float(df[reach_col].to_numpy()[mask_pooled].mean()),
                  "top_chance": float(df[chance_col].to_numpy()[mask_pooled].mean()),
                  "all_reach": float(df[reach_col].mean()), "all_chance": float(df[chance_col].mean())}
        out[h] = {"per_fold": per_fold, "pooled": pooled}
        print(f"[S1-REPORT] M1 {h}: pooled top10 reach={pooled['top_reach']:.4f} "
              f"chance={pooled['top_chance']:.4f} all reach={pooled['all_reach']:.4f} "
              f"chance={pooled['all_chance']:.4f}")
    return out


def m2_selectivity(df, rng):
    """Lift(10h) at top 1/5/10/20%, per fold and pooled, with a pooled 98.75% day-bootstrap CI each."""
    fracs = (0.01, 0.05, 0.10, 0.20)
    out = {}
    for frac in fracs:
        per_fold = {}
        for k in range(N_FOLDS):
            sub = df[df["fold"] == k]
            mask = top_k_mask(sub["p_10h"].to_numpy(), frac, rng)
            per_fold[k] = H.lift(sub["reach_10h"].to_numpy()[mask], sub["chance_10h"].to_numpy()[mask],
                                  sub["reach_10h"].to_numpy(), sub["chance_10h"].to_numpy())
        mask_pooled = pooled_top_mask(df, "p_10h", frac, rng)
        day_of_event = df["t0"].dt.floor("D").to_numpy()
        point, lo, hi = H.day_block_bootstrap(day_of_event, mask_pooled, df["reach_10h"].to_numpy(),
                                               df["chance_10h"].to_numpy(), N_RESAMPLES, LEVEL, rng)
        out[frac] = {"per_fold": per_fold, "pooled_point": point, "pooled_lo": lo, "pooled_hi": hi}
        print(f"[S1-REPORT] M2 top{int(frac*100)}%: pooled lift={point:.4f} ({lo:.4f}, {hi:.4f})")
    return out


def m3_calibration(df):
    """Pooled test events in 10 bins by p_10h decile: mean p_10h vs actual reach_10h. Per-fold log-loss
    and Brier score."""
    eps = 1e-12
    p = df["p_10h"].to_numpy()
    y = df["reach_10h"].to_numpy()
    bin_idx = pd.qcut(p, 10, labels=False, duplicates="drop")
    bins = []
    for b in sorted(pd.unique(bin_idx)):
        m = bin_idx == b
        bins.append({"bin": int(b), "n": int(m.sum()), "mean_p": float(p[m].mean()),
                     "actual_reach": float(y[m].mean())})
    per_fold = {}
    for k in range(N_FOLDS):
        sub = df[df["fold"] == k]
        pk = np.clip(sub["p_10h"].to_numpy(), eps, 1 - eps)
        yk = sub["reach_10h"].to_numpy()
        log_loss = float(-np.mean(yk * np.log(pk) + (1 - yk) * np.log(1 - pk)))
        brier = float(np.mean((pk - yk) ** 2))
        per_fold[k] = {"log_loss": log_loss, "brier": brier}
    print(f"[S1-REPORT] M3 calibration: {len(bins)} bins; fold log-loss/Brier logged per fold")
    return {"bins": bins, "per_fold": per_fold}


def m4_speed(df, rng):
    """Top 10% vs the rest: reach_10h rate, median minutes_to_mu among REACHERS, share reaching within 2h."""
    mask_pooled = pooled_top_mask(df, "p_10h", 0.10, rng)

    def block(sub):
        reach = sub["reach_10h"].to_numpy().astype(bool)
        reachers = sub[reach]
        return {"reach_10h_rate": float(reach.mean()),
                "median_minutes_to_mu": float(reachers["minutes_to_mu"].median()) if len(reachers) else None,
                "share_within_2h": float(sub["reach_2h"].to_numpy().mean())}

    out = {"top10": block(df[mask_pooled]), "rest": block(df[~mask_pooled])}
    print(f"[S1-REPORT] M4: top10 reach_10h_rate={out['top10']['reach_10h_rate']:.4f} "
          f"rest={out['rest']['reach_10h_rate']:.4f}")
    return out


def m5_breadth(df, rng):
    """By coin (either leg, pooled, lift restricted to that coin's own events, >=200 top-10% picks only);
    the share of all top-10% picks held by the 10 most-picked coins; by test block (per-fold table)."""
    mask_pooled = pooled_top_mask(df, "p_10h", 0.10, rng)
    coin_of_row = np.concatenate([df["ticker_a"].to_numpy(), df["ticker_b"].to_numpy()])
    top_mask_dup = np.concatenate([mask_pooled, mask_pooled])
    reach_dup = np.concatenate([df["reach_10h"].to_numpy(), df["reach_10h"].to_numpy()])
    chance_dup = np.concatenate([df["chance_10h"].to_numpy(), df["chance_10h"].to_numpy()])

    picks_by_coin = pd.Series(coin_of_row[top_mask_dup]).value_counts()
    by_coin = {}
    for coin, n_picks in picks_by_coin.items():
        if n_picks < 200:
            continue
        coin_mask = coin_of_row == coin
        by_coin[coin] = {"n_top10_picks": int(n_picks),
                          "lift": H.lift(reach_dup[coin_mask & top_mask_dup], chance_dup[coin_mask & top_mask_dup],
                                         reach_dup[coin_mask], chance_dup[coin_mask])}
    top10_coins_share = float(picks_by_coin.head(10).sum() / picks_by_coin.sum()) if len(picks_by_coin) else 0.0

    by_block = {}
    for k in range(N_FOLDS):
        sub = df[df["fold"] == k]
        mask_k = top_k_mask(sub["p_10h"].to_numpy(), 0.10, rng)
        by_block[k] = H.lift(sub["reach_10h"].to_numpy()[mask_k], sub["chance_10h"].to_numpy()[mask_k],
                              sub["reach_10h"].to_numpy(), sub["chance_10h"].to_numpy())
    print(f"[S1-REPORT] M5: {len(by_coin)} coins with >=200 top-10% picks; "
          f"top-10-coins share={top10_coins_share:.4f}")
    return {"by_coin": by_coin, "top10_coins_share": top10_coins_share, "by_block": by_block}


def m6_drivers(coefs_by_fold, perm_imp_by_fold):
    """Validation permutation importance aggregation (already run on the selection fit, per fold, at
    training time -- this just rolls it up): per-fold top 20 columns with their standardised refit
    coefficient and sign; group shares; the top-column share; the 95 unexplained-drift columns' share;
    any drift column in a top 20 is named (A6 watch rule). No pruning (HL-MODEL1 rule)."""
    group_map = load_column_group_map()
    drift_cols = load_unexplained_drift_columns()

    per_fold_top20 = {}
    group_share_by_fold = {}
    top_col_share_by_fold = {}
    drift_share_by_fold = {}
    drift_watch_hits = []
    for k, perm_imp in perm_imp_by_fold.items():
        imp = perm_imp.set_index("column")["log_loss_increase"]
        imp = imp[imp > 0]   # a column that DECREASED val log-loss when permuted carries no driver share
        total = imp.sum()
        coefs = coefs_by_fold[k].set_index("column")["coef"]

        top20_cols = imp.sort_values(ascending=False).head(20)
        top20 = []
        for col, score in top20_cols.items():
            coef = float(coefs.get(col, coefs.get(f"{col}__isnan", float("nan"))))
            top20.append({"column": col, "importance": float(score), "coef": coef,
                          "sign": "+" if coef > 0 else ("-" if coef < 0 else "0")})
            if col in drift_cols:
                drift_watch_hits.append((k, col))
        per_fold_top20[k] = top20

        if total > 0:
            shares = {}
            for col, score in imp.items():
                g = group_map.get(col, group_map.get(col.replace("__isnan", ""), "unknown"))
                shares[g] = shares.get(g, 0.0) + float(score) / total
            group_share_by_fold[k] = shares
            top_col_share_by_fold[k] = float(imp.max() / total)
            drift_share_by_fold[k] = float(imp[imp.index.isin(drift_cols)].sum() / total)
        else:
            group_share_by_fold[k] = {}
            top_col_share_by_fold[k] = 0.0
            drift_share_by_fold[k] = 0.0

    print(f"[S1-REPORT] M6: drift-column watch hits in a top-20 (A6): {drift_watch_hits}")
    return {"per_fold_top20": per_fold_top20, "group_share_by_fold": group_share_by_fold,
            "top_col_share_by_fold": top_col_share_by_fold, "drift_share_by_fold": drift_share_by_fold,
            "drift_watch_hits": drift_watch_hits}


def main():
    rng = np.random.default_rng(REPORT_SEED)
    print(f"[S1-REPORT] seed={REPORT_SEED}")
    test_df, grid_selected, coefs_by_fold, perm_imp_by_fold = load_all_folds()
    test_df = attach_labels(test_df)
    print(f"[S1-REPORT] total test events across 8 folds: {len(test_df):,}")

    gate = part_a_gate(test_df, rng)
    m1 = m1_hit_rate(test_df, rng)
    m2 = m2_selectivity(test_df, rng)
    # Checker's own check: M2's pooled top-10% point is the SAME quantity as the gate's pooled lift
    # (per-fold top-10% masks concatenated, same population) -- they must agree. The tie-break draw
    # differs (separate rng calls), but with continuous p_10h scores a tie is never actually hit, so this
    # is an exact-population check, not a tolerance-on-randomness check.
    assert abs(m2[0.10]["pooled_point"] - gate["pooled_lift"]) < 1e-9, (
        f"M2's pooled top-10% lift ({m2[0.10]['pooled_point']}) does not match the gate's pooled lift "
        f"({gate['pooled_lift']}) -- they are the same quantity and must agree exactly")
    print(f"[S1-REPORT] cross-check: M2 top10% pooled ({m2[0.10]['pooled_point']:.6f}) == "
          f"gate pooled_lift ({gate['pooled_lift']:.6f})")
    m3 = m3_calibration(test_df)
    m4 = m4_speed(test_df, rng)
    m5 = m5_breadth(test_df, rng)
    m6 = m6_drivers(coefs_by_fold, perm_imp_by_fold)

    out = {"gate": gate, "m1_hit_rate": m1, "m2_selectivity": m2, "m3_calibration": m3,
           "m4_speed": m4, "m5_breadth": m5, "m6_drivers": m6}
    with open(os.path.join(LOG_DIR, "report.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    print("[S1-REPORT] ALL DONE")


if __name__ == "__main__":
    main()
