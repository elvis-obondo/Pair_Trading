"""HL-MODEL1 S1-G: why the live top 1% works and where it fails (brief, 2026-11-06,
docs/prompts/HL_MODEL1_S1_TOP1_DEEP.md). Descriptive only -- the S1 gate verdict (FAIL, NUMBERS
[HL-MODEL1-S1]) does not change. No refit of the model, no vault, no fees/profit. Run on the GCP VM
(G3 needs the cached IN-matrix, same reason S1-F's shift check did).

    python -u research/model/s1g_top1_deep.py > research/model/logs/s1/s1g_top1_deep.log

Pick set (brief's own definition): S1-F Rule A, folds 1-7 -- in test block k, events with p_10h >= the
(1-q) quantile of block k-1's p_10h (fold 0 has no history, not scored). q=1% is the main pick set used
throughout G1-G6 (35,629 picks, cross-checked against S1-F's own saved per-fold n and c_k --
research/model/logs/s1/s1f_report.json -- not just the total). q=0.5% and q=0.1% are G7's tighter
cut-offs (user, 2026-11-06), computed the same way but with no prior saved value to cross-check against
(same code path already proven against q=1%). "Rest" = that block's other usable events. Block events =
folds 1-7's test rows, pooled where noted.

G3's proof (amended by the planner 2026-11-06, see the brief): the refit's step intercepts `b` were
never saved by s1_run.py (checked directly -- not in fold*_coefs.csv, fold*_grid.json, fold*_done.json,
or anywhere else), so p_10h cannot be rebuilt exactly. p_10h = 1 - prod_k(1 - sigmoid(eta + b_k)) is
strictly increasing in eta = X.w within a fold (same b's for every row), so the RANKING needs no b. The
proof here is: the rebuilt eta separates picks from rest perfectly (min eta over picks > max eta over
rest, in every fold -- true by construction if eta orders events exactly as the saved p_10h did, since
picks = {p_10h >= c_k}), and Spearman(eta, saved p_10h) >= 0.999999 over the block. Either failing
stops the script (assert) -- no solving for b. G3 only runs for the main q=1% pick set (the brief's
amendment did not extend it to G7's tighter cut-offs).
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402
from s1_preprocess import fit_preprocessing, apply_preprocessing  # noqa: E402

LOG_DIR = os.path.join(HERE, "logs", "s1")
N_FOLDS = 8
SEED = 20261106   # R7: one seed, logged, for every tie-break/resample in this script
N_RESAMPLES = 2000
LEVEL = 0.9875
MAIN_Q = 0.01                    # G1-G6's pick set
TIGHT_QS = (0.01, 0.005, 0.001)  # G7's cut-offs, q=1% repeated alongside for comparison

EVENT_COLS = ["ticker_a", "ticker_b", "z", "threshold", "sigma", "r2", "beta_stab", "vol_48",
              "mins_since_trade_a", "mins_since_trade_b", "bars_into_segment", "depth_10h", "mae_sigma",
              "reach_2h", "chance_2h", "reach_5h", "chance_5h"]
ITEM3_COLS = ("z", "abs_z_minus_thresh", "sigma", "vol_48", "r2", "beta_stab",
              "mins_since_trade_a", "mins_since_trade_b", "bars_into_segment", "chance_10h")


def pick_col(q):
    return f"pick_{q}"


# ---------------------------------------------------------------------------
# Data loading and the pick set
# ---------------------------------------------------------------------------

def load_data():
    frames = [pd.read_csv(os.path.join(LOG_DIR, f"fold{k}_test_predictions.csv")) for k in range(N_FOLDS)]
    df = pd.concat(frames, ignore_index=True)
    event_ids = df["event_id"].to_numpy()
    events = H.load_search_events(columns=EVENT_COLS)
    sub = events.loc[event_ids]
    for c in EVENT_COLS + ["reach_10h", "chance_10h", "minutes_to_mu", "t0", "entry_time"]:
        df[c] = sub[c].to_numpy()
    df["abs_z_minus_thresh"] = np.abs(df["z"]) - df["threshold"]
    df["day"] = pd.to_datetime(df["t0"]).dt.floor("D")
    et = pd.to_datetime(df["entry_time"], utc=True)
    df["utc_hour"] = et.dt.hour
    df["weekday"] = et.dt.weekday
    return df, events


def compute_picks(df, s1f_report):
    """Rule A for every q in TIGHT_QS, folds 1-7. q=0.01 is cross-checked against S1-F's own saved
    per-fold n and c_k (not just the 35,629 total) before use; q=0.005/0.001 have no prior saved value
    (new cut-offs, same formula, same code path already proven against q=0.01)."""
    df = df.copy()
    for q in TIGHT_QS:
        df[pick_col(q)] = False
    saved = s1f_report["f1_fixed_cutoff"]["ruleA"][str(MAIN_Q)]["per_fold"]
    per_fold_c = {q: {} for q in TIGHT_QS}
    for k in range(1, N_FOLDS):
        prev = df.loc[df["fold"] == k - 1, "p_10h"].to_numpy()
        blk = df["fold"] == k
        blk_p10h = df.loc[blk, "p_10h"].to_numpy()
        for q in TIGHT_QS:
            c_k = float(np.quantile(prev, 1 - q))
            mask = blk_p10h >= c_k
            df.loc[blk, pick_col(q)] = mask
            per_fold_c[q][k] = c_k
            if q == MAIN_Q:
                saved_row = saved[str(k)]
                assert abs(c_k - saved_row["c_k"]) < 1e-9, (
                    f"fold {k}: recomputed c_k={c_k:.10f} disagrees with S1-F's saved c_k="
                    f"{saved_row['c_k']:.10f}")
                assert int(mask.sum()) == saved_row["n"], (
                    f"fold {k}: recomputed n={int(mask.sum())} disagrees with S1-F's saved n="
                    f"{saved_row['n']}")
    block_df = df[df["fold"].between(1, N_FOLDS - 1)].copy()
    n_picks = {q: int(block_df[pick_col(q)].sum()) for q in TIGHT_QS}
    print(f"[S1G] pick sets, folds 1-7: " + ", ".join(f"q={q}: n={n_picks[q]:,}" for q in TIGHT_QS) +
          " (q=0.01 matches S1-F's saved per-fold n and c_k exactly)", flush=True)
    assert n_picks[MAIN_Q] == 35629, f"expected 35,629 picks at q={MAIN_Q} per the brief, got {n_picks[MAIN_Q]:,}"
    return block_df, per_fold_c


# ---------------------------------------------------------------------------
# G1: trade count
# ---------------------------------------------------------------------------

def _day_count_stats(counts):
    counts = np.asarray(counts, dtype=np.float64)
    return {"median": float(np.median(counts)), "mean": float(np.mean(counts)),
            "p10": float(np.quantile(counts, 0.10)), "p90": float(np.quantile(counts, 0.90)),
            "max": float(np.max(counts)), "n_days": int(len(counts))}


def _picks_per_day(block_df, col, fold=None):
    sub = block_df if fold is None else block_df[block_df["fold"] == fold]
    days = np.sort(sub["day"].unique())
    pick_counts = sub[sub[col]].groupby("day").size()
    counts = pick_counts.reindex(days, fill_value=0).to_numpy()
    return _day_count_stats(counts)


def _open_intervals(picks):
    """Hold each pick from t0 until minutes_to_mu (if it reached), else for 10h (600 min)."""
    hold_min = np.where(picks["reach_10h"].to_numpy() == 1, picks["minutes_to_mu"].to_numpy(), 600.0)
    starts = pd.to_datetime(picks["t0"]).to_numpy()
    ends = (pd.to_datetime(picks["t0"]) + pd.to_timedelta(hold_min, unit="m")).to_numpy()
    return starts, ends


def _time_weighted_open_stats(starts, ends):
    """Time-weighted peak/median/90th percentile of the number of positions open at once, over the span
    from the first pick's open to the last pick's close (the window the system was actually holding
    something, not the full calendar -- days with zero picks are outside this span by construction).
    End is exclusive (a close and an open at the identical instant do not count as overlapping)."""
    if len(starts) == 0:
        return {"peak": 0, "median": 0.0, "p90": 0.0}
    times = np.concatenate([starts, ends])
    deltas = np.concatenate([np.ones(len(starts), dtype=np.int64), -np.ones(len(ends), dtype=np.int64)])
    order = np.lexsort((deltas, times))   # ties: close (-1) applied before open (+1) at the same instant
    ev = pd.Series(deltas[order]).groupby(times[order]).sum()
    cum = ev.cumsum()
    seg_times = cum.index.to_numpy()
    seg_counts = cum.to_numpy()
    peak = int(seg_counts.max())
    if len(seg_times) < 2:
        return {"peak": peak, "median": float(seg_counts[0]), "p90": float(seg_counts[0])}
    durations = np.diff(seg_times).astype("timedelta64[s]").astype(np.float64)
    vals = seg_counts[:-1]
    order2 = np.argsort(vals)
    vals_sorted, w_sorted = vals[order2], durations[order2]
    cumw = np.cumsum(w_sorted)
    total = cumw[-1]

    def wq(q):
        if total <= 0:
            return float(vals_sorted[-1])
        idx = min(int(np.searchsorted(cumw, q * total)), len(vals_sorted) - 1)
        return float(vals_sorted[idx])

    return {"peak": peak, "median": wq(0.5), "p90": wq(0.9)}


def g1_trade_count(block_df, col):
    per_fold_day = {k: _picks_per_day(block_df, col, k) for k in range(1, N_FOLDS)}
    pooled_day = _picks_per_day(block_df, col)

    picks = block_df[block_df[col]]
    per_fold_open = {}
    for k in range(1, N_FOLDS):
        starts, ends = _open_intervals(picks[picks["fold"] == k])
        per_fold_open[k] = _time_weighted_open_stats(starts, ends)
    starts_all, ends_all = _open_intervals(picks)
    pooled_open = _time_weighted_open_stats(starts_all, ends_all)

    coins = pd.concat([picks["ticker_a"], picks["ticker_b"]]).unique()
    coin_peaks = {}
    for coin in coins:
        m = (picks["ticker_a"] == coin) | (picks["ticker_b"] == coin)
        s, e = _open_intervals(picks[m])
        coin_peaks[coin] = _time_weighted_open_stats(s, e)["peak"]
    top_coin = max(coin_peaks, key=coin_peaks.get) if coin_peaks else None
    print(f"[S1G] G1 ({col}): pooled picks/day median={pooled_day['median']:.1f} mean={pooled_day['mean']:.1f} "
          f"p10={pooled_day['p10']:.1f} p90={pooled_day['p90']:.1f} max={pooled_day['max']:.0f}", flush=True)
    print(f"[S1G] G1 ({col}): pooled open-at-once peak={pooled_open['peak']} median={pooled_open['median']:.2f} "
          f"p90={pooled_open['p90']:.2f}; peak per single coin: {top_coin}="
          f"{coin_peaks.get(top_coin)}", flush=True)
    return {"per_fold_day": per_fold_day, "pooled_day": pooled_day,
            "per_fold_open": per_fold_open, "pooled_open": pooled_open,
            "peak_per_coin_top": {"coin": top_coin, "peak": coin_peaks.get(top_coin)},
            "n_coins": len(coins)}


# ---------------------------------------------------------------------------
# G2: same-chance comparison (main q only, per the brief)
# ---------------------------------------------------------------------------

def g2_same_chance(block_df, col):
    chance = block_df["chance_10h"].to_numpy()
    cuts = np.quantile(chance, np.arange(1, 10) / 10.0)
    bin_idx = np.digitize(chance, cuts)   # 0..9
    out = {}
    for b in range(10):
        m = bin_idx == b
        picks_m = m & block_df[col].to_numpy()
        rest_m = m & ~block_df[col].to_numpy()
        reach = block_df["reach_10h"].to_numpy()
        row = {"n_picks": int(picks_m.sum()), "n_rest": int(rest_m.sum()),
               "reach_10h_picks": float(reach[picks_m].mean()) if picks_m.any() else None,
               "reach_10h_rest": float(reach[rest_m].mean()) if rest_m.any() else None,
               "chance_10h_bin_range": (float(chance[m].min()), float(chance[m].max())) if m.any() else None}
        if row["reach_10h_picks"] is not None and row["reach_10h_rest"] is not None:
            row["diff"] = row["reach_10h_picks"] - row["reach_10h_rest"]
        else:
            row["diff"] = None
        out[b] = row
    print("[S1G] G2: " + "; ".join(f"bin{b}=diff{out[b]['diff']:.3f}" if out[b]["diff"] is not None
                                    else f"bin{b}=n/a" for b in range(10)), flush=True)
    return out


# ---------------------------------------------------------------------------
# G3: exact linear contributions (main q only, per the brief -- not extended to G7)
# ---------------------------------------------------------------------------

def _raw_group_map():
    import csv
    rows = list(csv.DictReader(open(os.path.join(HERE, "inputs_v1_pair.csv"))))
    col_file = {r["column"]: r["file"] for r in rows if r["in_out"] == "IN"}

    def group(file):
        name = file.replace(".parquet", "")
        if name == "events":
            return "events"
        for g in ("g2", "g3", "g4", "g5", "g6", "g7", "g8", "g9"):
            if name.startswith(g):
                return g.upper()
        return name.upper()

    return {c: group(f) for c, f in col_file.items()}


def _output_column_groups(stats, out_cols, raw_group):
    groups = []
    for c in stats["final_numeric"]:
        groups.append(raw_group.get(c, "UNKNOWN"))
    for _ in stats["nan_indicator_cols"]:
        groups.append("missing_indicator")
    n_a = len(stats["ticker_levels"]["ticker_a"])
    n_b = len(stats["ticker_levels"]["ticker_b"])
    groups += ["coin_one_hot"] * (n_a + n_b)
    assert len(groups) == len(out_cols), f"group list length {len(groups)} != out_cols length {len(out_cols)}"
    assert "UNKNOWN" not in groups, "a raw column did not map to a known group (events/G2..G9) -- fix _raw_group_map"
    return groups


def g3_contributions(folds, in_cols, block_df, col):
    raw_group = _raw_group_map()
    df_idx = block_df.set_index("event_id")
    results = {}
    for k in range(1, N_FOLDS):
        t0 = time.time()
        fold = folds[k]
        all_ids = np.concatenate([fold["train_ids"], fold["val_ids"]])
        stats_refit = fit_preprocessing(all_ids, in_cols)
        test_ids = fold["test_ids"]
        X_test, out_cols = apply_preprocessing(test_ids, in_cols, stats_refit)
        coefs = pd.read_csv(os.path.join(LOG_DIR, f"fold{k}_coefs.csv"))
        assert coefs["column"].tolist() == out_cols, f"fold {k}: coefs column order != rebuilt out_cols order"
        w = coefs["coef"].to_numpy(dtype=np.float64)
        eta = X_test.astype(np.float64) @ w

        is_pick = df_idx.loc[test_ids, col].to_numpy()
        p10h_saved = df_idx.loc[test_ids, "p_10h"].to_numpy()

        min_eta_picks = float(eta[is_pick].min())
        max_eta_rest = float(eta[~is_pick].max())
        separated = min_eta_picks > max_eta_rest
        rho, _ = spearmanr(eta, p10h_saved)
        print(f"[S1G] G3 fold {k} PROOF: min_eta_picks={min_eta_picks:.6f} max_eta_rest={max_eta_rest:.6f} "
              f"separated={separated} spearman={rho:.8f}  [{time.time()-t0:.0f}s]", flush=True)
        assert separated, f"fold {k}: rebuilt eta does NOT separate picks from rest -- STOP (see brief's G3 proof)"
        assert rho >= 0.999999, f"fold {k}: Spearman(eta, saved p_10h)={rho:.8f} < 0.999999 -- STOP"

        mean_picks = X_test[is_pick].mean(axis=0, dtype=np.float64) * w
        mean_rest = X_test[~is_pick].mean(axis=0, dtype=np.float64) * w
        diff = mean_picks - mean_rest
        groups = _output_column_groups(stats_refit, out_cols, raw_group)

        group_picks, group_rest = {}, {}
        for g, p, r in zip(groups, mean_picks, mean_rest):
            group_picks[g] = group_picks.get(g, 0.0) + float(p)
            group_rest[g] = group_rest.get(g, 0.0) + float(r)

        top20_idx = np.argsort(-np.abs(diff))[:20]
        top20 = [{"column": out_cols[j], "group": groups[j], "picks": float(mean_picks[j]),
                  "rest": float(mean_rest[j]), "diff": float(diff[j])} for j in top20_idx]

        results[k] = {"n_test": len(test_ids), "n_picks": int(is_pick.sum()),
                      "separated": separated, "spearman": float(rho),
                      "group_mean_contrib_picks": group_picks, "group_mean_contrib_rest": group_rest,
                      "top20_columns": top20}
        print(f"[S1G] G3 fold {k}: top 3 by |diff|: " +
              ", ".join(f"{t['column']}({t['group']}):{t['diff']:+.4f}" for t in top20[:3]) +
              f"  [{time.time()-t0:.0f}s]", flush=True)
        del X_test, stats_refit
    return results


# ---------------------------------------------------------------------------
# G4: fixed slices
# ---------------------------------------------------------------------------

def _bootstrap_interval(day_of_event, mask, reach, chance, rng):
    """Wraps H.day_block_bootstrap: a resample that draws no pick day gives 0/0 -> NaN in that resample's
    lift, which np.quantile propagates into lo/hi. Checker's finding: don't touch the shared harness
    function (bitwise rule) or switch to nanquantile (would quietly condition on picks being present) --
    just report the interval as undefined when this happens. The point lift is unaffected (it uses the
    full, unresampled picks/rest split, no 0/0 risk there)."""
    point, lo, hi = H.day_block_bootstrap(day_of_event, mask, reach, chance, N_RESAMPLES, LEVEL, rng)
    if not (np.isfinite(lo) and np.isfinite(hi)):
        return {"point": point, "lo": None, "hi": None,
                "note": "interval undefined: at least one resample drew no pick day"}
    return {"point": point, "lo": lo, "hi": hi}


def _slice_row(block_df, mask_slice, rng, col):
    sub = block_df[mask_slice]
    n_slice = len(sub)
    picks = sub[col].to_numpy()
    n_picks = int(picks.sum())
    reach = sub["reach_10h"].to_numpy()
    chance = sub["chance_10h"].to_numpy()
    row = {"n_slice": n_slice, "n_picks": n_picks,
           "share": (n_picks / n_slice) if n_slice else None}
    if n_picks > 0:
        row["reach_10h"] = float(reach[picks].mean())
        row["chance_10h"] = float(chance[picks].mean())
        row["lift"] = H.lift(reach[picks], chance[picks], reach, chance)
        day_of_event = sub["day"].to_numpy()
        row["lift_bootstrap"] = _bootstrap_interval(day_of_event, picks, reach, chance, rng)
    else:
        row["reach_10h"] = row["chance_10h"] = row["lift"] = row["lift_bootstrap"] = None
    return row


def g4_slices(block_df, rng, col):
    out = {}
    out["side_z_pos"] = _slice_row(block_df, block_df["z"].to_numpy() > 0, rng, col)
    out["side_z_neg"] = _slice_row(block_df, block_df["z"].to_numpy() < 0, rng, col)

    is_yzy = ((block_df["ticker_a"] == "YZY") | (block_df["ticker_b"] == "YZY")).to_numpy()
    out["yzy_in_leg"] = _slice_row(block_df, is_yzy, rng, col)
    out["yzy_not"] = _slice_row(block_df, ~is_yzy, rng, col)

    for c in ("vol_48", "r2", "sigma", "abs_z_minus_thresh"):
        vals = block_df[c].to_numpy()
        lo_c, hi_c = np.quantile(vals, [1 / 3, 2 / 3])
        out[f"{c}_low"] = _slice_row(block_df, vals <= lo_c, rng, col)
        out[f"{c}_mid"] = _slice_row(block_df, (vals > lo_c) & (vals <= hi_c), rng, col)
        out[f"{c}_high"] = _slice_row(block_df, vals > hi_c, rng, col)
        out[f"{c}_tercile_cuts"] = (float(lo_c), float(hi_c))

    hour = block_df["utc_hour"].to_numpy()
    for lo_h, hi_h, name in ((0, 6, "hour_00_06"), (6, 12, "hour_06_12"),
                              (12, 18, "hour_12_18"), (18, 24, "hour_18_24")):
        out[name] = _slice_row(block_df, (hour >= lo_h) & (hour < hi_h), rng, col)

    weekend = block_df["weekday"].to_numpy() >= 5
    out["weekend"] = _slice_row(block_df, weekend, rng, col)
    out["weekday"] = _slice_row(block_df, ~weekend, rng, col)

    for k in range(1, N_FOLDS):
        out[f"fold_{k}"] = _slice_row(block_df, (block_df["fold"] == k).to_numpy(), rng, col)

    print(f"[S1G] G4 ({col}): " + "; ".join(
        f"{name}=lift{out[name]['lift']:.3f}" if out[name].get("lift") is not None else f"{name}=n/a"
        for name in ("side_z_pos", "side_z_neg", "yzy_in_leg", "yzy_not")), flush=True)
    return out


# ---------------------------------------------------------------------------
# G5: anatomy of the misses
# ---------------------------------------------------------------------------

def g5_misses(block_df, col):
    picks = block_df[block_df[col]]
    reached = picks[picks["reach_10h"] == 1]
    missed = picks[picks["reach_10h"] == 0]
    medians = {c: {"reached": float(reached[c].median()) if len(reached) else None,
                   "missed": float(missed[c].median()) if len(missed) else None}
               for c in ITEM3_COLS}

    rest = block_df[~block_df[col]]
    rest_missed = rest[rest["reach_10h"] == 0]

    def quartiles(sub, c):
        vals = sub[c].to_numpy()
        if len(vals) == 0:
            return {"q25": None, "median": None, "q75": None, "n": 0}
        q25, q50, q75 = np.percentile(vals, [25, 50, 75])
        return {"q25": float(q25), "median": float(q50), "q75": float(q75), "n": len(vals)}

    miss_profile = {c: {"picks_miss": quartiles(missed, c), "rest_miss": quartiles(rest_missed, c)}
                    for c in ("depth_10h", "mae_sigma")}
    print(f"[S1G] G5 ({col}): reached n={len(reached)} missed n={len(missed)} rest_missed n={len(rest_missed)}; "
          f"depth_10h median picks_miss={miss_profile['depth_10h']['picks_miss']['median']} "
          f"rest_miss={miss_profile['depth_10h']['rest_miss']['median']}", flush=True)
    return {"medians_reached_vs_missed": medians, "miss_profile": miss_profile}


# ---------------------------------------------------------------------------
# G6: calibration
# ---------------------------------------------------------------------------

def g6_calibration(block_df, col):
    picks = block_df[block_df[col]]
    by_fold = {}
    for k in range(1, N_FOLDS):
        sub = picks[picks["fold"] == k]
        by_fold[k] = {"mean_p10h": float(sub["p_10h"].mean()) if len(sub) else None,
                      "actual_reach_10h": float(sub["reach_10h"].mean()) if len(sub) else None,
                      "n": len(sub)}

    p = picks["p_10h"].to_numpy()
    pooled_bins = {}
    if len(p) >= 5:
        edges = np.quantile(p, [0.2, 0.4, 0.6, 0.8])
        bin_idx = np.digitize(p, edges)
        for b in range(5):
            m = bin_idx == b
            pooled_bins[b] = {"n": int(m.sum()),
                              "mean_p10h": float(p[m].mean()) if m.any() else None,
                              "actual_reach_10h": float(picks["reach_10h"].to_numpy()[m].mean()) if m.any() else None}
    print(f"[S1G] G6 ({col}) by fold: " + ", ".join(
        f"f{k}=p{by_fold[k]['mean_p10h']}/r{by_fold[k]['actual_reach_10h']}" for k in range(1, N_FOLDS)),
        flush=True)
    return {"by_fold": by_fold, "pooled_quintiles": pooled_bins}


# ---------------------------------------------------------------------------
# G7: tighter cut-offs (top 0.5% and top 0.1%, q=1% alongside)
# ---------------------------------------------------------------------------

def _outcomes_block(sub):
    if len(sub) == 0:
        return {"reach_2h": None, "chance_2h": None, "reach_5h": None, "chance_5h": None,
                "reach_10h": None, "chance_10h": None, "median_minutes_to_mu": None,
                "share_within_30min": None, "share_within_60min": None, "n": 0}
    reach = sub["reach_10h"].to_numpy()
    mtm = sub["minutes_to_mu"].to_numpy()
    reachers = sub[reach == 1]
    within = lambda mins: float(((reach == 1) & (mtm <= mins)).mean())
    return {"reach_2h": float(sub["reach_2h"].mean()), "chance_2h": float(sub["chance_2h"].mean()),
            "reach_5h": float(sub["reach_5h"].mean()), "chance_5h": float(sub["chance_5h"].mean()),
            "reach_10h": float(sub["reach_10h"].mean()), "chance_10h": float(sub["chance_10h"].mean()),
            "median_minutes_to_mu": float(reachers["minutes_to_mu"].median()) if len(reachers) else None,
            "share_within_30min": within(30), "share_within_60min": within(60), "n": len(sub)}


def _quartiles(vals):
    q25, q50, q75 = np.percentile(vals, [25, 50, 75])
    return {"median": float(q50), "q25": float(q25), "q75": float(q75)}


def _distance_to_mu(sub):
    """Size, in sigma (user, 2026-11-07, brief amendment): |z| and |z|-threshold, median+quartiles --
    these are the report. |z| x sigma (price-percent distance) is kept for the JSON only, not the report."""
    if len(sub) == 0:
        empty = {"median": None, "q25": None, "q75": None}
        return {"abs_z": empty, "abs_z_minus_threshold": empty, "abs_z_times_sigma_json_only": empty, "n": 0}
    abs_z = np.abs(sub["z"].to_numpy())
    abs_z_minus_thresh = abs_z - sub["threshold"].to_numpy()
    dist_sigma = abs_z * sub["sigma"].to_numpy()
    return {"abs_z": _quartiles(abs_z), "abs_z_minus_threshold": _quartiles(abs_z_minus_thresh),
            "abs_z_times_sigma_json_only": _quartiles(dist_sigma), "n": len(sub)}


def g7_cutoff_table(block_df, rng):
    results = {}
    for q in TIGHT_QS:
        col = pick_col(q)
        per_fold = {}
        parts_reach, parts_chance, parts_day, parts_mask = [], [], [], []
        for k in range(1, N_FOLDS):
            blk = block_df[block_df["fold"] == k]
            mask = blk[col].to_numpy()
            reach, chance = blk["reach_10h"].to_numpy(), blk["chance_10h"].to_numpy()
            n_active_days = blk["day"].nunique()
            n = int(mask.sum())
            row = {"n": n, "picks_per_active_day": (n / n_active_days) if n_active_days else None,
                   "share": (n / len(blk)) if len(blk) else None}
            if n > 0:
                row["reach_10h"] = float(reach[mask].mean())
                row["chance_10h"] = float(chance[mask].mean())
                row["gap"] = H.gap(reach[mask], chance[mask])
                row["lift"] = H.lift(reach[mask], chance[mask], reach, chance)
            else:
                row["reach_10h"] = row["chance_10h"] = row["gap"] = row["lift"] = None
            per_fold[k] = row
            parts_reach.append(reach); parts_chance.append(chance)
            parts_day.append(blk["day"].to_numpy()); parts_mask.append(mask)
        reach_cat, chance_cat = np.concatenate(parts_reach), np.concatenate(parts_chance)
        day_cat, mask_cat = np.concatenate(parts_day), np.concatenate(parts_mask)
        interval = _bootstrap_interval(day_cat, mask_cat, reach_cat, chance_cat, rng)
        results[q] = {"per_fold": per_fold, "pooled_point": interval["point"],
                      "pooled_lo": interval["lo"], "pooled_hi": interval["hi"]}
        if "note" in interval:
            results[q]["pooled_interval_note"] = interval["note"]
        print(f"[S1G] G7 cutoff table q={q}: pooled lift={interval['point']:.4f} "
              f"({interval['lo']},{interval['hi']})" + (f" -- {interval['note']}" if "note" in interval else ""),
              flush=True)
    return results


def g7_tighter_cutoffs(block_df, rng):
    cutoff_table = g7_cutoff_table(block_df, rng)
    g1_by_q, outcomes_by_q, distance_by_q, g5_by_q, g6_by_q, g4_by_q = {}, {}, {}, {}, {}, {}
    for q in TIGHT_QS:
        col = pick_col(q)
        picks = block_df[block_df[col]]
        rest = block_df[~block_df[col]]
        g1_by_q[q] = g1_trade_count(block_df, col)
        outcomes_by_q[q] = {"picks": _outcomes_block(picks), "rest": _outcomes_block(rest)}
        distance_by_q[q] = {"picks": _distance_to_mu(picks), "rest": _distance_to_mu(rest)}
        g5_by_q[q] = g5_misses(block_df, col)
        g6_by_q[q] = g6_calibration(block_df, col)
        g4_by_q[q] = g4_slices(block_df, rng, col)
        print(f"[S1G] G7 (q={q}): n_picks={len(picks):,} "
              f"median_abs_z={distance_by_q[q]['picks']['abs_z']['median']} "
              f"median_abs_z_minus_thresh={distance_by_q[q]['picks']['abs_z_minus_threshold']['median']} "
              f"reach_10h={outcomes_by_q[q]['picks']['reach_10h']}", flush=True)
    return {"cutoff_table": cutoff_table, "g1_by_q": g1_by_q, "outcomes_by_q": outcomes_by_q,
            "distance_by_q": distance_by_q, "g5_by_q": g5_by_q, "g6_by_q": g6_by_q, "g4_by_q": g4_by_q}


# ---------------------------------------------------------------------------
# G8: distance from mu against predicted and actual reversion (user, 2026-11-07)
# ---------------------------------------------------------------------------

def g8_distance_vs_probability(block_df):
    """Bins ALL block events (folds 1-7 pooled) into 10 |z| deciles (edges from all block events,
    printed). Headline per bin: n and the model's p_10h (mean, median, q25, q75) -- for all events and,
    on the SAME edges, for Rule A picks at each q in TIGHT_QS. Side column only: actual reach_10h's
    mean, beside the mean p_10h (not chance_10h, not a picks-minus-rest diff -- dropped per the user's
    2026-11-07 correction: this item is distance vs the model's probability, not vs reversion). Thin or
    empty bins report None, not an error."""
    absz = np.abs(block_df["z"].to_numpy())
    edges = np.quantile(absz, np.arange(1, 10) / 10.0)
    bin_idx = np.digitize(absz, edges)   # 0..9
    p10h = block_df["p_10h"].to_numpy()
    reach = block_df["reach_10h"].to_numpy()

    def bin_row(mask):
        n = int(mask.sum())
        if n == 0:
            return {"n": 0, "mean_p10h": None, "median_p10h": None, "q25_p10h": None, "q75_p10h": None,
                    "actual_reach_10h": None}
        p = p10h[mask]
        q25, q50, q75 = np.percentile(p, [25, 50, 75])
        return {"n": n, "mean_p10h": float(p.mean()), "median_p10h": float(q50),
                "q25_p10h": float(q25), "q75_p10h": float(q75), "actual_reach_10h": float(reach[mask].mean())}

    all_bins = {b: bin_row(bin_idx == b) for b in range(10)}
    picks_by_q = {q: {b: bin_row((bin_idx == b) & block_df[pick_col(q)].to_numpy()) for b in range(10)}
                  for q in TIGHT_QS}

    print(f"[S1G] G8: |z| decile edges = {[round(e, 4) for e in edges]}", flush=True)
    for b in range(10):
        r = all_bins[b]
        print(f"[S1G] G8 bin {b}: n={r['n']} mean_p10h={r['mean_p10h']} median_p10h={r['median_p10h']} "
              f"q25={r['q25_p10h']} q75={r['q75_p10h']} actual_reach_10h={r['actual_reach_10h']}", flush=True)
    return {"edges": edges.tolist(), "all_bins": all_bins, "picks_by_q": picks_by_q}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    t0 = time.time()
    import master_manifest as MF
    for name in ("s1g_top1_deep.py", "harness.py", "s1_preprocess.py", "s1_run.py", "inputs_v1_pair.csv"):
        print(f"[S1G] sha256 {name}: {MF.sha(os.path.join(HERE, name))}", flush=True)
    cache_info = H._cache_info()
    cache_sha = cache_info.get("cache_sha256", "NO VALID CACHE") if cache_info else "NO VALID CACHE"
    print(f"[S1G] cache manifest cache_sha256: {cache_sha} "
          f"(must be bd5dc2549374d0a80c8b042425e34119289b17b753a49213ac28c1831c6ca544)", flush=True)
    gs = os.path.join(os.path.dirname(HERE), "dataset", "GIT_STATE.json")
    git_head, git_dirty = ("unavailable", "unavailable")
    if os.path.exists(gs):
        G = MF.json.load(open(gs))
        git_head, git_dirty = G.get("head", "unavailable"), len(G.get("porcelain", []))
    print(f"[S1G] git_head {git_head} ({git_dirty} uncommitted paths); "
          f"start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC; pid {os.getpid()}; "
          f"seed={SEED}", flush=True)

    rng = np.random.default_rng(SEED)
    df, events = load_data()
    print(f"[S1G] loaded {len(df):,} test-predictions rows across {N_FOLDS} folds  [{time.time()-t0:.0f}s]",
          flush=True)
    s1f_report = json.load(open(os.path.join(LOG_DIR, "s1f_report.json")))
    block_df, per_fold_c = compute_picks(df, s1f_report)
    main_col = pick_col(MAIN_Q)

    folds = H.build_folds(events)
    cache_info_full = H._cache_info()
    in_cols = cache_info_full["columns"]
    assert len(in_cols) == 1091, f"expected 1,091 IN columns, cache has {len(in_cols)}"

    g1 = g1_trade_count(block_df, main_col)
    print(f"[S1G] G1 done  [{time.time()-t0:.0f}s]", flush=True)
    g2 = g2_same_chance(block_df, main_col)
    print(f"[S1G] G2 done  [{time.time()-t0:.0f}s]", flush=True)
    g3 = g3_contributions(folds, in_cols, block_df, main_col)
    print(f"[S1G] G3 done  [{time.time()-t0:.0f}s]", flush=True)
    g4 = g4_slices(block_df, rng, main_col)
    print(f"[S1G] G4 done  [{time.time()-t0:.0f}s]", flush=True)
    g5 = g5_misses(block_df, main_col)
    print(f"[S1G] G5 done  [{time.time()-t0:.0f}s]", flush=True)
    g6 = g6_calibration(block_df, main_col)
    print(f"[S1G] G6 done  [{time.time()-t0:.0f}s]", flush=True)
    g7 = g7_tighter_cutoffs(block_df, rng)
    print(f"[S1G] G7 done  [{time.time()-t0:.0f}s]", flush=True)

    out = {"g1_trade_count": g1, "g2_same_chance": g2, "g3_contributions": g3,
           "g4_slices": g4, "g5_misses": g5, "g6_calibration": g6, "g7_tighter_cutoffs": g7}
    with open(os.path.join(LOG_DIR, "s1g_report.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)

    print("\n[S1G] === 10-LINE SUMMARY ===", flush=True)
    print(f"1. Pick set (q=1%): folds 1-7, n={len(block_df[block_df[main_col]]):,} (matches S1-F exactly); "
          f"q=0.5%/0.1% in G7.", flush=True)
    print(f"2. G1 pooled picks/day: median={g1['pooled_day']['median']:.1f}, max={g1['pooled_day']['max']:.0f}; "
          f"open at once: peak={g1['pooled_open']['peak']}, median={g1['pooled_open']['median']:.2f}, "
          f"peak per coin: {g1['peak_per_coin_top']['coin']}={g1['peak_per_coin_top']['peak']}.", flush=True)
    print("3. G2 (same starting chance, different result): reach_10h difference (picks-rest) by "
          "chance_10h decile -- see table.", flush=True)
    for k in range(1, N_FOLDS):
        print(f"4. G3 fold {k}: proof separated={g3[k]['separated']} spearman={g3[k]['spearman']:.6f}.",
              flush=True)
    print("5. G3 top contributors: see per-fold top-20 tables.", flush=True)
    print("6. G4 fixed slices: side of spread, YZY, vol_48/r2/sigma/(|z|-threshold) terciles, hour, "
          "weekend, fold -- lift within each slice, see table.", flush=True)
    print(f"7. G5: reached-vs-missed medians and miss-depth/mae_sigma quartiles (picks' misses vs "
          f"rest's misses) -- see table.", flush=True)
    print("8. G6: mean p_10h vs actual reach_10h, by fold and pooled by p_10h quintile -- see table.",
          flush=True)
    print(f"9. G7 (q=0.5%/0.1%): pooled lift q=0.005={g7['cutoff_table'][0.005]['pooled_point']:.4f}, "
          f"q=0.001={g7['cutoff_table'][0.001]['pooled_point']:.4f} -- small n reported as is.", flush=True)
    print("10. Descriptive only, every slice chosen after seeing results; gate verdict is still FAIL "
          "(NUMBERS [HL-MODEL1-S1]); no cause is claimed beyond what these tables show.", flush=True)
    print(f"[S1G] ALL DONE  [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
