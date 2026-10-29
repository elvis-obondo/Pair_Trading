"""HL-MODEL1 S1-D: the top 1% of picks, examined (user, 2026-10-29). Descriptive only -- the gate verdict
(FAIL, NUMBERS [HL-MODEL1-S1]) does not change. Reads the 8 folds' saved test predictions plus v1
events/labels for the same event_ids. No refit, no vault, no profit/fee/stop metrics (A1).

    python -u research/model/s1d_top1pct.py > research/model/logs/s1d_top1pct.log

Top X% = per test block (same rule as M2/the gate): per-fold top_k_mask, concatenated -- never a single
rank across all 8 folds' pooled rows. "The rest" = that same block's other (100-X)%.
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
SEED = 20261029  # R7: one seed, logged, for every tie-break/resample in this script
N_RESAMPLES = 2000
LEVEL = 0.9875

EVENT_COLS = ["ticker_a", "ticker_b", "z", "threshold", "sigma", "r2", "beta_stab", "vol_48",
              "mins_since_trade_a", "mins_since_trade_b", "bars_into_segment",
              "reach_2h", "chance_2h", "reach_5h", "chance_5h"]


def top_k_mask(scores, frac, rng):
    n = len(scores)
    n_top = max(1, int(np.ceil(frac * n)))
    tie_key = rng.random(n)
    order = np.lexsort((tie_key, -np.asarray(scores)))
    mask = np.zeros(n, dtype=bool)
    mask[order[:n_top]] = True
    return mask


def pooled_top_mask(df, frac, rng):
    return np.concatenate([top_k_mask(df[df["fold"] == k]["p_10h"].to_numpy(), frac, rng)
                            for k in range(N_FOLDS)])


def top10_driver_columns():
    """Item 5's input list: sum each column's validation permutation importance (log_loss_increase)
    across the 8 folds' already-saved files, no event data needed for this part."""
    imp_total = None
    for k in range(N_FOLDS):
        imp = pd.read_csv(os.path.join(LOG_DIR, f"fold{k}_val_permutation_importance.csv")) \
            .set_index("column")["log_loss_increase"]
        imp_total = imp if imp_total is None else imp_total.add(imp, fill_value=0.0)
    return imp_total.sort_values(ascending=False).head(10).index.tolist()


def load_data(extra_cols):
    """extra_cols: item 5's top-10 driver columns not already in EVENT_COLS. Most S1-D columns (z,
    threshold, sigma, r2, beta_stab, vol_48, mins_since_trade_a/b, bars_into_segment) live in
    events.parquet directly (checked against its schema), so load_search_events covers them. Any driver
    column from the g2-g9a group files does NOT -- those need the cached IN-matrix (load_features_cached),
    which only exists on a machine that built it (the GCP VM / AWS, never the laptop -- this is why the
    brief says "run on the GCP VM, the data is there")."""
    frames = [pd.read_csv(os.path.join(LOG_DIR, f"fold{k}_test_predictions.csv")) for k in range(N_FOLDS)]
    df = pd.concat(frames, ignore_index=True)
    event_ids = df["event_id"].to_numpy()

    events = H.load_search_events(columns=EVENT_COLS)
    sub = events.loc[event_ids]
    for c in EVENT_COLS + ["reach_10h", "chance_10h", "minutes_to_mu", "t0", "entry_time"]:
        df[c] = sub[c].to_numpy()

    missing = [c for c in extra_cols if c not in df.columns]
    if missing:
        print(f"[S1D] load_data: {len(missing)} driver column(s) not in events.parquet, "
              f"pulling from the cached IN-matrix: {missing}")
        X, _ = H.load_features_cached(event_ids, missing)
        for j, c in enumerate(missing):
            df[c] = X[:, j]

    df["abs_z_minus_thresh"] = np.abs(df["z"]) - df["threshold"]
    df["pair"] = df["ticker_a"] + "-" + df["ticker_b"]
    df["day"] = df["t0"].dt.floor("D")
    et = pd.to_datetime(df["entry_time"], utc=True)
    df["utc_hour"] = et.dt.hour
    df["weekday"] = et.dt.weekday
    return df


def item1_robustness(df, rng):
    out = {}
    for frac in (0.01, 0.02, 0.05):
        per_fold = {}
        for k in range(N_FOLDS):
            sub = df[df["fold"] == k]
            mask = top_k_mask(sub["p_10h"].to_numpy(), frac, rng)
            per_fold[k] = {"n": int(mask.sum()),
                           "lift": H.lift(sub["reach_10h"].to_numpy()[mask], sub["chance_10h"].to_numpy()[mask],
                                          sub["reach_10h"].to_numpy(), sub["chance_10h"].to_numpy())}
        n_positive = sum(1 for v in per_fold.values() if v["lift"] > 0)
        mask_pooled = pooled_top_mask(df, frac, rng)
        day_of_event = df["t0"].dt.floor("D").to_numpy()
        point, lo, hi = H.day_block_bootstrap(day_of_event, mask_pooled, df["reach_10h"].to_numpy(),
                                               df["chance_10h"].to_numpy(), N_RESAMPLES, LEVEL, rng)
        out[frac] = {"per_fold": per_fold, "n_positive": n_positive,
                     "pooled_point": point, "pooled_lo": lo, "pooled_hi": hi}
        print(f"[S1D] item1 top{frac*100:g}%: n_positive={n_positive}/{N_FOLDS} "
              f"pooled_lift={point:.4f} ({lo:.4f},{hi:.4f})")
    return out


def item2_concentration(df, mask1):
    top = df[mask1]
    rest = df[~mask1]
    n_pairs = top["pair"].nunique()
    n_coins = pd.concat([top["ticker_a"], top["ticker_b"]]).nunique()
    n_days = top["day"].nunique()

    day_counts = top["day"].value_counts()
    busiest10 = set(day_counts.head(10).index)
    share_busiest10 = float(day_counts.head(10).sum() / len(top))
    # Checker's note: same convention as the vol_48 check below -- only the TOP-1% PICKS side drops the
    # busiest-day events; the "all events" baseline is left unchanged. This asks "does the top-1%'s own
    # edge survive if we simply hadn't picked its busiest-day events", not "what if those days never
    # existed at all" (which would also shrink the baseline).
    not_busiest = ~df["day"].isin(busiest10)
    mask1_excl = mask1 & not_busiest
    lift_excl_busiest = H.lift(df["reach_10h"].to_numpy()[mask1_excl], df["chance_10h"].to_numpy()[mask1_excl],
                                df["reach_10h"].to_numpy(), df["chance_10h"].to_numpy())

    top10_pairs = []
    for pair, cnt in top["pair"].value_counts().head(10).items():
        m = df["pair"] == pair
        top10_pairs.append({"pair": pair, "n": int(cnt),
                            "gap": H.gap(df["reach_10h"].to_numpy()[mask1 & m], df["chance_10h"].to_numpy()[mask1 & m])})
    coin_counts = pd.concat([top["ticker_a"], top["ticker_b"]]).value_counts()
    top10_coins = []
    for coin, cnt in coin_counts.head(10).items():
        m = (df["ticker_a"] == coin) | (df["ticker_b"] == coin)
        top10_coins.append({"coin": coin, "n": int(cnt),
                            "gap": H.gap(df["reach_10h"].to_numpy()[mask1 & m], df["chance_10h"].to_numpy()[mask1 & m])})
    print(f"[S1D] item2: distinct pairs={n_pairs} coins={n_coins} days={n_days} "
          f"share_busiest10days={share_busiest10:.4f} lift_excl_busiest10={lift_excl_busiest:.4f}")
    return {"n_pairs": n_pairs, "n_coins": n_coins, "n_days": n_days,
            "share_busiest10days": share_busiest10, "lift_excl_busiest10days": lift_excl_busiest,
            "top10_pairs": top10_pairs, "top10_coins": top10_coins}


def item3_profile(df, mask1):
    top, rest = df[mask1], df[~mask1]
    medians = {}
    for c in ("z", "abs_z_minus_thresh", "sigma", "vol_48", "r2", "beta_stab",
              "mins_since_trade_a", "mins_since_trade_b", "bars_into_segment", "chance_10h"):
        medians[c] = {"top1": float(top[c].median()), "rest": float(rest[c].median())}
    hour_counts = top["utc_hour"].value_counts().sort_index().to_dict()
    weekday_counts = top["weekday"].value_counts().sort_index().to_dict()
    print(f"[S1D] item3: medians computed for {len(medians)} columns (top1% vs rest)")
    return {"medians": medians, "utc_hour_counts": {int(k): int(v) for k, v in hour_counts.items()},
            "weekday_counts": {int(k): int(v) for k, v in weekday_counts.items()}}


def item4_outcomes(df, mask1):
    def block(sub):
        reach = sub["reach_10h"].to_numpy().astype(bool)
        reachers = sub[reach]
        within = lambda mins: float(((sub["reach_10h"].to_numpy() == 1) &
                                      (sub["minutes_to_mu"].to_numpy() <= mins)).mean())
        return {"reach_2h": float(sub["reach_2h"].mean()), "chance_2h": float(sub["chance_2h"].mean()),
                "reach_5h": float(sub["reach_5h"].mean()), "chance_5h": float(sub["chance_5h"].mean()),
                "reach_10h": float(sub["reach_10h"].mean()), "chance_10h": float(sub["chance_10h"].mean()),
                "median_minutes_to_mu": float(reachers["minutes_to_mu"].median()) if len(reachers) else None,
                "share_within_30min": within(30), "share_within_60min": within(60)}
    out = {"top1": block(df[mask1]), "rest": block(df[~mask1])}
    print(f"[S1D] item4: top1 reach_10h={out['top1']['reach_10h']:.4f} rest={out['rest']['reach_10h']:.4f}")
    return out


def item5_drivers(df, mask1, top10_cols, rng):
    top, rest = df[mask1], df[~mask1]
    medians = {col: {"top1": float(top[col].median()), "rest": float(rest[col].median())}
               for col in top10_cols}

    vol48_q90 = df["vol_48"].quantile(0.90)
    original_lift = H.lift(top["reach_10h"].to_numpy(), top["chance_10h"].to_numpy(),
                            df["reach_10h"].to_numpy(), df["chance_10h"].to_numpy())
    is_high_vol48 = df["vol_48"].to_numpy() >= vol48_q90
    mask1_novol = mask1 & ~is_high_vol48
    mask1_highvol = mask1 & is_high_vol48
    n_top1 = int(mask1.sum())
    n_removed = int(mask1_highvol.sum())
    n_remaining = int(mask1_novol.sum())
    # Checker's finding: 87% of the top 1% IS top-decile vol_48 -- report that share up front, the
    # removed set's own lift on the SAME baseline, and a bootstrap interval for the small remainder
    # (likely wide at this n), rather than a bare "share left" number that reads the wrong way.
    share_removed = float(n_removed / n_top1) if n_top1 else None
    lift_removed = H.lift(df["reach_10h"].to_numpy()[mask1_highvol], df["chance_10h"].to_numpy()[mask1_highvol],
                           df["reach_10h"].to_numpy(), df["chance_10h"].to_numpy())
    lift_remaining = H.lift(df["reach_10h"].to_numpy()[mask1_novol], df["chance_10h"].to_numpy()[mask1_novol],
                             df["reach_10h"].to_numpy(), df["chance_10h"].to_numpy())
    day_of_event = df["t0"].dt.floor("D").to_numpy()
    remaining_point, remaining_lo, remaining_hi = H.day_block_bootstrap(
        day_of_event, mask1_novol, df["reach_10h"].to_numpy(), df["chance_10h"].to_numpy(),
        N_RESAMPLES, LEVEL, rng)
    print(f"[S1D] item5: top10 driver columns {top10_cols}")
    print(f"[S1D] item5: top1% n={n_top1}, top-decile-vol_48 share={share_removed:.4f} (n={n_removed}), "
          f"remaining n={n_remaining}")
    print(f"[S1D] item5: lift -- full top1%={original_lift:.4f}, removed (top-decile vol_48) set="
          f"{lift_removed:.4f}, remaining set={lift_remaining:.4f} bootstrap=({remaining_point:.4f},"
          f"{remaining_lo:.4f},{remaining_hi:.4f})")
    return {"top10_driver_columns": top10_cols, "medians": medians,
            "original_lift": original_lift, "n_top1": n_top1,
            "share_top_decile_vol48": share_removed, "n_removed": n_removed, "n_remaining": n_remaining,
            "lift_removed_set": lift_removed, "lift_remaining_set": lift_remaining,
            "remaining_bootstrap_point": remaining_point, "remaining_bootstrap_lo": remaining_lo,
            "remaining_bootstrap_hi": remaining_hi, "vol48_q90_threshold": float(vol48_q90)}


def main():
    rng = np.random.default_rng(SEED)
    print(f"[S1D] seed={SEED}")
    top10_cols = top10_driver_columns()
    df = load_data(top10_cols)
    print(f"[S1D] total test events across 8 folds: {len(df):,}")

    item1 = item1_robustness(df, rng)
    mask1 = pooled_top_mask(df, 0.01, rng)
    item2 = item2_concentration(df, mask1)
    item3 = item3_profile(df, mask1)
    item4 = item4_outcomes(df, mask1)
    item5 = item5_drivers(df, mask1, top10_cols, rng)

    out = {"item1_robustness": item1, "item2_concentration": item2, "item3_profile": item3,
           "item4_outcomes": item4, "item5_drivers": item5}
    with open(os.path.join(LOG_DIR, "s1d_report.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)

    print("\n[S1D] === 10-LINE SUMMARY ===")
    print(f"1. Top 1% pooled lift={item1[0.01]['pooled_point']:.4f} "
          f"({item1[0.01]['pooled_lo']:.4f},{item1[0.01]['pooled_hi']:.4f}), "
          f"{item1[0.01]['n_positive']}/8 folds positive.")
    print(f"2. Top 2%={item1[0.02]['pooled_point']:.4f}, top 5%={item1[0.05]['pooled_point']:.4f} "
          f"-- edge {'rises' if item1[0.01]['pooled_point'] > item1[0.05]['pooled_point'] else 'flattens'} "
          f"as the slice narrows.")
    print(f"3. {item2['n_pairs']} distinct pairs, {item2['n_coins']} coins, {item2['n_days']} days in the top 1%.")
    print(f"4. {item2['share_busiest10days']*100:.1f}% of top-1% picks fall on its 10 busiest days; "
          f"lift excluding those days = {item2['lift_excl_busiest10days']:.4f}.")
    print(f"5. Busiest pair: {item2['top10_pairs'][0]['pair']} (n={item2['top10_pairs'][0]['n']}, "
          f"gap={item2['top10_pairs'][0]['gap']:.4f}).")
    print(f"6. Top-1% outcomes: reach_10h={item4['top1']['reach_10h']:.4f} vs rest "
          f"{item4['rest']['reach_10h']:.4f}; median minutes-to-mu={item4['top1']['median_minutes_to_mu']}.")
    print(f"7. Share reaching within 30/60 min (top1%): {item4['top1']['share_within_30min']:.4f} / "
          f"{item4['top1']['share_within_60min']:.4f}.")
    print(f"8. Top driver columns (M6, summed across folds): {item5['top10_driver_columns'][:5]}...")
    print(f"9. The top 1% is mostly top-decile vol_48 events ({item5['share_top_decile_vol48']*100:.0f}% "
          f"of n={item5['n_top1']}, lift {item5['lift_removed_set']:.4f}); the small remainder "
          f"(n={item5['n_remaining']}) shows a similar point lift {item5['lift_remaining_set']:.4f} "
          f"(bootstrap {item5['remaining_bootstrap_point']:.4f}, {item5['remaining_bootstrap_lo']:.4f} to "
          f"{item5['remaining_bootstrap_hi']:.4f}).")
    print(f"10. Gate verdict is still FAIL (NUMBERS [HL-MODEL1-S1]) -- descriptive only, not a pass.")
    print("[S1D] ALL DONE")


if __name__ == "__main__":
    main()
