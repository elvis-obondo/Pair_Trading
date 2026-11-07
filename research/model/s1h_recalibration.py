"""HL-MODEL1 S1-H: recalibrating the logistic model's probabilities (brief, 2026-11-07,
docs/prompts/HL_MODEL1_S1_RECALIBRATION.md). Descriptive only -- the S1 gate verdict (FAIL, NUMBERS
[HL-MODEL1-S1]) does not change. No refit of the S1 model, no vault, no fees/profit. Picks are never
re-selected: Rule A on the RAW p_10h, exactly as S1-G, cross-checked (assert) against S1-G's own saved
per-fold n (research/model/logs/s1/s1g_report.json).

    python -u research/model/s1h_recalibration.py > research/model/logs/s1/s1h_recalibration.log

Fit set for month k (folds 1-7): all test events of folds 0..k-1 pooled (expanding), fold 0 fit-only.
Look-ahead guard (planner ruling 2026-11-07, on the checker's finding): for horizon h, a fit event is
used only if t0 + h <= the start of test block k, so its outcome was known before month k began --
this drops at most the last h hours of block k-1's events (the only block close enough in time to be
affected; every earlier block's t0 is already well before the cutoff). Rule A's own cut-off needs no
guard (predictions only, known at t0).

Every number this prints is one this session's NUMBERS.md write-up may cite (CLAUDE.md rule, 2026-11-07
standing rule): nothing is typed by hand.
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import sklearn
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402

LOG_DIR = os.path.join(HERE, "logs", "s1")
N_FOLDS = 8
HORIZONS = (2, 5, 10)
QS = (0.01, 0.005, 0.001)
P_EPS = 1e-6          # Platt's logit clip, per the brief
LL_EPS = 1e-12        # log-loss clip (avoid log(0))
SEED = 20261107       # R7: one seed, logged (used nowhere stochastic here, but kept for the convention)


def pick_col(q):
    return f"pick_{q}"


# ---------------------------------------------------------------------------
# Data loading and the pick cross-check
# ---------------------------------------------------------------------------

def load_data():
    frames = [pd.read_csv(os.path.join(LOG_DIR, f"fold{k}_test_predictions.csv")) for k in range(N_FOLDS)]
    df = pd.concat(frames, ignore_index=True)
    event_ids = df["event_id"].to_numpy()
    events = H.load_search_events(columns=["reach_2h", "reach_5h"])
    sub = events.loc[event_ids]
    for c in ("reach_2h", "reach_5h", "reach_10h", "t0"):
        df[c] = sub[c].to_numpy()
    return df, events


def compute_picks(df, s1g_report):
    """Rule A on RAW p_10h, q in QS, folds 1-7 -- identical rule to S1-G. Cross-checked (assert) against
    S1-G's own saved per-fold n in s1g_report.json's g7_tighter_cutoffs.cutoff_table (not just recomputed
    independently -- this IS the same selection, never re-derived from scratch without the check)."""
    df = df.copy()
    for q in QS:
        df[pick_col(q)] = False
    cutoff_table = s1g_report["g7_tighter_cutoffs"]["cutoff_table"]
    per_fold_c = {q: {} for q in QS}
    for k in range(1, N_FOLDS):
        prev = df.loc[df["fold"] == k - 1, "p_10h"].to_numpy()
        blk = df["fold"] == k
        blk_p10h = df.loc[blk, "p_10h"].to_numpy()
        for q in QS:
            c_k = float(np.quantile(prev, 1 - q))
            mask = blk_p10h >= c_k
            df.loc[blk, pick_col(q)] = mask
            per_fold_c[q][k] = c_k
            saved_n = cutoff_table[str(q)]["per_fold"][str(k)]["n"]
            assert int(mask.sum()) == saved_n, (
                f"fold {k} q={q}: recomputed n={int(mask.sum())} != S1-G's saved n={saved_n}")
    block_df = df[df["fold"].between(1, N_FOLDS - 1)].copy()
    print(f"[S1H] picks cross-checked against S1-G's saved per-fold n, every (fold,q): OK", flush=True)
    for q in QS:
        n_q = int(block_df[pick_col(q)].sum())
        print(f"[S1H] q={q}: n={n_q:,}", flush=True)
    return block_df, per_fold_c


# ---------------------------------------------------------------------------
# Platt and isotonic fitting
# ---------------------------------------------------------------------------

def _logit(p):
    p = np.clip(p, P_EPS, 1 - P_EPS)
    return np.log(p / (1 - p))


def fit_platt(p_fit, y_fit):
    """Checker's fix 1: penalty=None is deprecated in sklearn 1.8+ (removed in 1.10, errors before 1.2).
    C=np.inf gives the same unpenalised fit (verified against statsmodels to 1e-4 on this sklearn
    version) without relying on a deprecated/version-sensitive argument."""
    logit_fit = _logit(p_fit)
    clf = LogisticRegression(C=np.inf, solver="lbfgs", max_iter=1000)
    clf.fit(logit_fit.reshape(-1, 1), y_fit)
    assert clf.n_iter_[0] < 1000, f"Platt fit did not converge in {clf.n_iter_[0]} iterations"
    intercept, slope = float(clf.intercept_[0]), float(clf.coef_[0, 0])
    return intercept, slope


def platt_predict(intercept, slope, p):
    eta = intercept + slope * _logit(p)
    return 1.0 / (1.0 + np.exp(-eta))


def fit_isotonic(p_fit, y_fit):
    iso = IsotonicRegression(increasing=True, out_of_bounds="clip", y_min=0, y_max=1)
    iso.fit(p_fit, y_fit)
    return iso


def isotonic_tied_groups(iso, p_fit):
    """Number of tied groups the fit creates: runs of >1 distinct raw p-value (from the fit set) that
    the step function maps to the same output level."""
    unique_p = np.unique(p_fit)
    preds = iso.predict(unique_p)
    groups = 0
    i = 0
    n = len(preds)
    while i < n:
        j = i
        while j + 1 < n and preds[j + 1] == preds[i]:
            j += 1
        if j > i:
            groups += 1
        i = j + 1
    return groups


def log_loss(p, y):
    p = np.clip(p, LL_EPS, 1 - LL_EPS)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def brier(p, y):
    return float(np.mean((p - y) ** 2))


# ---------------------------------------------------------------------------
# Per-(fold, horizon) fit + apply
# ---------------------------------------------------------------------------

def fit_and_apply(df, folds, k, h):
    test_start_k = folds[k]["test_start"]
    p_col, r_col = f"p_{h}h", f"reach_{h}h"
    fit_pool = df[df["fold"] < k]
    n_before = len(fit_pool)
    guard = (fit_pool["t0"] + pd.Timedelta(hours=h)) <= test_start_k
    fit_h = fit_pool[guard]
    n_dropped = n_before - len(fit_h)

    p_fit = fit_h[p_col].to_numpy()
    y_fit = fit_h[r_col].to_numpy()
    intercept, slope = fit_platt(p_fit, y_fit)
    platt_valid = slope > 0
    iso = fit_isotonic(p_fit, y_fit)
    tied_groups = isotonic_tied_groups(iso, p_fit)

    test_mask = df["fold"] == k
    test_p = df.loc[test_mask, p_col].to_numpy()
    test_y = df.loc[test_mask, r_col].to_numpy()
    platt_pred = platt_predict(intercept, slope, test_p) if platt_valid else np.full(len(test_p), np.nan)
    iso_pred = iso.predict(test_p)

    print(f"[S1H] fold {k} h={h}h: n_fit_pool={n_before:,} n_dropped(guard)={n_dropped:,} "
          f"n_fit_used={len(fit_h):,} platt_intercept={intercept:.6f} platt_slope={slope:.6f} "
          f"platt_valid={platt_valid} iso_tied_groups={tied_groups}", flush=True)

    if h == 10 and platt_valid:
        rho, _ = spearmanr(test_p, platt_pred)
        print(f"[S1H] fold {k} h=10h: Spearman(raw p_10h, platt p_10h)={rho:.12f}", flush=True)
        assert abs(rho - 1.0) < 1e-9, f"fold {k}: Platt broke the ranking of p_10h (spearman={rho})"

    iso_at_grid = {g: float(iso.predict([g / 10.0])[0]) for g in range(1, 10)}
    print(f"[S1H] fold {k} h={h}h: iso_at_grid (raw p=0.1..0.9) = " +
          ", ".join(f"{g/10:.1f}:{iso_at_grid[g]:.4f}" for g in range(1, 10)), flush=True)

    # Checker's fix 3: isotonic can output exactly 0 or 1 on the test block (out_of_bounds="clip" and
    # the step function itself both saturate); the log-loss clip (LL_EPS) then charges ~27.6 nats for
    # any one of those that contradicts its label. Count both, per fold/horizon, rather than let it
    # hide inside a pooled average.
    n_iso_saturated = int(np.sum((iso_pred == 0.0) | (iso_pred == 1.0)))
    n_iso_contradicted = int(np.sum(((iso_pred == 0.0) & (test_y == 1)) | ((iso_pred == 1.0) & (test_y == 0))))
    n_iso_levels_test = int(len(np.unique(iso_pred)))
    print(f"[S1H] fold {k} h={h}h: iso saturated (0 or 1) on test={n_iso_saturated}, of which "
          f"contradicted by the label={n_iso_contradicted}; distinct iso levels on this test block="
          f"{n_iso_levels_test}", flush=True)

    return {"n_fit_pool": n_before, "n_dropped": n_dropped, "n_fit_used": len(fit_h),
            "intercept": intercept, "slope": slope, "platt_valid": platt_valid,
            "tied_groups": tied_groups, "iso_at_grid": iso_at_grid,
            "n_iso_saturated": n_iso_saturated, "n_iso_contradicted": n_iso_contradicted,
            "n_iso_levels_test": n_iso_levels_test,
            "test_p": test_p, "platt_pred": platt_pred, "iso_pred": iso_pred}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    t0 = time.time()
    import master_manifest as MF
    for name in ("s1h_recalibration.py", "harness.py"):
        print(f"[S1H] sha256 {name}: {MF.sha(os.path.join(HERE, name))}", flush=True)
    print(f"[S1H] sklearn.__version__={sklearn.__version__}", flush=True)
    gs = os.path.join(os.path.dirname(HERE), "dataset", "GIT_STATE.json")
    git_head, git_dirty = ("unavailable", "unavailable")
    if os.path.exists(gs):
        G = MF.json.load(open(gs))
        git_head, git_dirty = G.get("head", "unavailable"), len(G.get("porcelain", []))
    print(f"[S1H] git_head {git_head} ({git_dirty} uncommitted paths); "
          f"start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC; pid {os.getpid()}; "
          f"seed={SEED}", flush=True)

    df, events = load_data()
    folds = H.build_folds(events)
    print(f"[S1H] loaded {len(df):,} test-predictions rows across {N_FOLDS} folds  [{time.time()-t0:.0f}s]",
          flush=True)
    s1g_report = json.load(open(os.path.join(LOG_DIR, "s1g_report.json")))
    block_df, per_fold_c = compute_picks(df, s1g_report)

    # ---- R1/R2/R6 raw material: fit + apply per (fold, horizon) ----
    fits = {}   # (k, h) -> result dict
    for k in range(1, N_FOLDS):
        for h in HORIZONS:
            fits[(k, h)] = fit_and_apply(df, folds, k, h)
    print(f"[S1H] all fits done  [{time.time()-t0:.0f}s]", flush=True)

    # Attach corrected predictions back onto df (per-fold, per-horizon correction -- each test row gets
    # the correction fitted on ITS OWN fold's expanding fit pool, never another fold's).
    for h in HORIZONS:
        df[f"platt_{h}h"] = np.nan
        df[f"iso_{h}h"] = np.nan
        for k in range(1, N_FOLDS):
            m = df["fold"] == k
            df.loc[m, f"platt_{h}h"] = fits[(k, h)]["platt_pred"]
            df.loc[m, f"iso_{h}h"] = fits[(k, h)]["iso_pred"]
    scored = df[df["fold"].between(1, N_FOLDS - 1)].copy()
    # Bug fix (found when the first run crashed): compute_picks adds pick_{q} columns to its OWN
    # internal copy of df and returns that as block_df -- it never mutates the caller's df, so `scored`
    # (built from the caller's df) never had them. block_df and scored are filtered from the same df on
    # the identical mask (fold between 1 and N_FOLDS-1), so their indices are the same set; carry the
    # columns over by index, not by a second recomputation.
    assert scored.index.equals(block_df.index), (
        "scored and block_df were expected to share the identical index (same df, same fold-1..7 "
        "filter) -- they don't, so the column carry-over below would silently misalign")
    for q in QS:
        scored[pick_col(q)] = block_df.loc[scored.index, pick_col(q)]

    # ---- R2: error scores, per fold and pooled, all events ----
    r2 = {}
    for h in HORIZONS:
        p_col, r_col = f"p_{h}h", f"reach_{h}h"
        per_fold = {}
        for k in range(1, N_FOLDS):
            sub = scored[scored["fold"] == k]
            y = sub[r_col].to_numpy()
            row = {"n": len(sub),
                   "logloss_raw": log_loss(sub[p_col].to_numpy(), y), "brier_raw": brier(sub[p_col].to_numpy(), y),
                   "logloss_iso": log_loss(sub[f"iso_{h}h"].to_numpy(), y), "brier_iso": brier(sub[f"iso_{h}h"].to_numpy(), y)}
            if fits[(k, h)]["platt_valid"]:
                row["logloss_platt"] = log_loss(sub[f"platt_{h}h"].to_numpy(), y)
                row["brier_platt"] = brier(sub[f"platt_{h}h"].to_numpy(), y)
            else:
                row["logloss_platt"] = row["brier_platt"] = None
            per_fold[k] = row
            print(f"[S1H] R2 h={h}h fold {k}: n={row['n']:,} logloss raw/platt/iso="
                  f"{row['logloss_raw']:.4f}/{row['logloss_platt']}/{row['logloss_iso']:.4f} "
                  f"brier raw/platt/iso={row['brier_raw']:.4f}/{row['brier_platt']}/{row['brier_iso']:.4f}",
                  flush=True)
        y_all = scored[r_col].to_numpy()
        valid_folds = [k for k in range(1, N_FOLDS) if fits[(k, h)]["platt_valid"]]
        platt_mask = scored["fold"].isin(valid_folds).to_numpy()
        pooled = {"n": len(scored),
                  "logloss_raw": log_loss(scored[p_col].to_numpy(), y_all),
                  "brier_raw": brier(scored[p_col].to_numpy(), y_all),
                  "logloss_iso": log_loss(scored[f"iso_{h}h"].to_numpy(), y_all),
                  "brier_iso": brier(scored[f"iso_{h}h"].to_numpy(), y_all),
                  "n_platt_valid_folds": len(valid_folds),
                  "logloss_platt": (log_loss(scored.loc[platt_mask, f"platt_{h}h"].to_numpy(),
                                              scored.loc[platt_mask, r_col].to_numpy())
                                     if platt_mask.any() else None),
                  "brier_platt": (brier(scored.loc[platt_mask, f"platt_{h}h"].to_numpy(),
                                         scored.loc[platt_mask, r_col].to_numpy())
                                   if platt_mask.any() else None)}
        print(f"[S1H] R2 h={h}h POOLED (months 2-8, ALL events): n={pooled['n']:,} n_platt_valid_folds="
              f"{pooled['n_platt_valid_folds']}/7 logloss raw/platt/iso={pooled['logloss_raw']:.4f}/"
              f"{pooled['logloss_platt']}/{pooled['logloss_iso']:.4f} brier raw/platt/iso="
              f"{pooled['brier_raw']:.4f}/{pooled['brier_platt']}/{pooled['brier_iso']:.4f}", flush=True)
        # Checker's fix 2: when Platt is invalid in some fold, the pooled Platt figure above is on a
        # DIFFERENT (smaller) set of rows than pooled raw/iso -- not a fair comparison. When that
        # happens, also compute raw and isotonic on the SAME valid-fold-only rows, so all three are on
        # one baseline.
        if len(valid_folds) < 7:
            pooled["logloss_raw_matched"] = log_loss(scored.loc[platt_mask, p_col].to_numpy(),
                                                       scored.loc[platt_mask, r_col].to_numpy())
            pooled["brier_raw_matched"] = brier(scored.loc[platt_mask, p_col].to_numpy(),
                                                  scored.loc[platt_mask, r_col].to_numpy())
            pooled["logloss_iso_matched"] = log_loss(scored.loc[platt_mask, f"iso_{h}h"].to_numpy(),
                                                       scored.loc[platt_mask, r_col].to_numpy())
            pooled["brier_iso_matched"] = brier(scored.loc[platt_mask, f"iso_{h}h"].to_numpy(),
                                                  scored.loc[platt_mask, r_col].to_numpy())
            print(f"[S1H] R2 h={h}h POOLED (months 2-8, MATCHED to Platt's {len(valid_folds)}/7 valid "
                  f"folds, n={int(platt_mask.sum()):,}): logloss raw/iso={pooled['logloss_raw_matched']:.4f}/"
                  f"{pooled['logloss_iso_matched']:.4f} brier raw/iso={pooled['brier_raw_matched']:.4f}/"
                  f"{pooled['brier_iso_matched']:.4f}", flush=True)
        else:
            print(f"[S1H] R2 h={h}h: all 7 folds had a valid Platt fit -- the ALL-events and MATCHED "
                  f"baselines are identical, nothing further to print.", flush=True)
        r2[h] = {"per_fold": per_fold, "pooled": pooled}

    # ---- R3: calibration by decile, pooled, per horizon ----
    r3 = {}
    for h in HORIZONS:
        p_col, r_col = f"p_{h}h", f"reach_{h}h"
        p_all = scored[p_col].to_numpy()
        cuts = np.quantile(p_all, np.arange(1, 10) / 10.0)
        bin_idx = np.digitize(p_all, cuts)
        bins = {}
        for b in range(10):
            m = bin_idx == b
            n = int(m.sum())
            platt_vals = scored.loc[m, f"platt_{h}h"].to_numpy()
            n_platt_nan = int(np.isnan(platt_vals).sum())
            bins[b] = {"n": n, "mean_raw": float(p_all[m].mean()),
                       "mean_platt": float(np.nanmean(platt_vals)) if n else None,
                       "n_platt_nan": n_platt_nan,
                       "mean_iso": float(scored.loc[m, f"iso_{h}h"].to_numpy().mean()),
                       "actual_reach": float(scored.loc[m, r_col].to_numpy().mean())}
            # Checker's fix 2: mean_raw/mean_iso above are over ALL n events in the bin, mean_platt is
            # over only the non-NaN ones -- a mismatched baseline whenever n_platt_nan>0. Add the
            # matched-to-platt versions of raw/iso in that case.
            if n_platt_nan > 0:
                not_nan = ~np.isnan(platt_vals)
                bins[b]["mean_raw_matched"] = float(p_all[m][not_nan].mean())
                bins[b]["mean_iso_matched"] = float(scored.loc[m, f"iso_{h}h"].to_numpy()[not_nan].mean())
            print(f"[S1H] R3 h={h}h bin {b}: n={bins[b]['n']} mean_raw={bins[b]['mean_raw']:.4f} "
                  f"mean_platt={bins[b]['mean_platt']} (nan={bins[b]['n_platt_nan']}) "
                  f"mean_iso={bins[b]['mean_iso']:.4f} actual_reach={bins[b]['actual_reach']:.4f}" +
                  (f" | MATCHED to platt's non-nan rows: mean_raw={bins[b]['mean_raw_matched']:.4f} "
                   f"mean_iso={bins[b]['mean_iso_matched']:.4f}" if n_platt_nan > 0 else ""), flush=True)
        r3[h] = {"cuts": cuts.tolist(), "bins": bins}

    # ---- R4: the picks, per q, per month + pooled, all 3 horizons ----
    r4 = {}
    for q in QS:
        col = pick_col(q)
        picks = scored[scored[col]]
        per_month = {}
        for k in range(1, N_FOLDS):
            sub = picks[picks["fold"] == k]
            row = {"n": len(sub)}
            for h in HORIZONS:
                p_col, r_col = f"p_{h}h", f"reach_{h}h"
                if len(sub):
                    row[f"mean_raw_{h}h"] = float(sub[p_col].mean())
                    pv = sub[f"platt_{h}h"].to_numpy()
                    row[f"mean_platt_{h}h"] = float(np.nanmean(pv)) if not np.all(np.isnan(pv)) else None
                    row[f"mean_iso_{h}h"] = float(sub[f"iso_{h}h"].mean())
                    row[f"actual_{h}h"] = float(sub[r_col].mean())
                else:
                    for suf in (f"mean_raw_{h}h", f"mean_platt_{h}h", f"mean_iso_{h}h", f"actual_{h}h"):
                        row[suf] = None
            per_month[k] = row
            print(f"[S1H] R4 q={q} fold {k}: n={row['n']} " +
                  ", ".join(f"{h}h: raw={row[f'mean_raw_{h}h']} platt={row[f'mean_platt_{h}h']} "
                            f"iso={row[f'mean_iso_{h}h']} actual={row[f'actual_{h}h']}" for h in HORIZONS),
                  flush=True)
        pooled_row = {"n": len(picks)}
        for h in HORIZONS:
            p_col, r_col = f"p_{h}h", f"reach_{h}h"
            pooled_row[f"mean_raw_{h}h"] = float(picks[p_col].mean())
            pv = picks[f"platt_{h}h"].to_numpy()
            n_nan = int(np.isnan(pv).sum())
            pooled_row[f"mean_platt_{h}h"] = float(np.nanmean(pv))
            pooled_row[f"n_platt_nan_{h}h"] = n_nan
            pooled_row[f"mean_iso_{h}h"] = float(picks[f"iso_{h}h"].mean())
            pooled_row[f"actual_{h}h"] = float(picks[r_col].mean())
            # Checker's fix 2: same mismatched-baseline issue as R2/R3 -- add matched raw/iso/actual
            # when some picks' fold had no valid Platt fit for this horizon.
            if n_nan > 0:
                not_nan = ~np.isnan(pv)
                pooled_row[f"mean_raw_matched_{h}h"] = float(picks[p_col].to_numpy()[not_nan].mean())
                pooled_row[f"mean_iso_matched_{h}h"] = float(picks[f"iso_{h}h"].to_numpy()[not_nan].mean())
                pooled_row[f"actual_matched_{h}h"] = float(picks[r_col].to_numpy()[not_nan].mean())
        print(f"[S1H] R4 q={q} POOLED (ALL picks): n={pooled_row['n']} " +
              ", ".join(f"{h}h: raw={pooled_row[f'mean_raw_{h}h']:.4f} platt={pooled_row[f'mean_platt_{h}h']:.4f} "
                        f"iso={pooled_row[f'mean_iso_{h}h']:.4f} actual={pooled_row[f'actual_{h}h']:.4f}"
                        for h in HORIZONS), flush=True)
        for h in HORIZONS:
            if pooled_row[f"n_platt_nan_{h}h"] > 0:
                print(f"[S1H] R4 q={q} POOLED h={h}h MATCHED to platt's non-nan picks "
                      f"(n_nan={pooled_row[f'n_platt_nan_{h}h']}): raw={pooled_row[f'mean_raw_matched_{h}h']:.4f} "
                      f"iso={pooled_row[f'mean_iso_matched_{h}h']:.4f} actual={pooled_row[f'actual_matched_{h}h']:.4f}",
                      flush=True)
        r4[q] = {"per_month": per_month, "pooled": pooled_row}

    # ---- R5: the cut-off in real terms (q=1%, 10h) ----
    # Isotonic needs the fitted IsotonicRegression object itself to evaluate at the exact c_k (the
    # iso_at_grid above only has the 0.1..0.9 grid) -- refit inline per fold on the same guarded h=10h
    # fit pool fit_and_apply already built (cheap: IsotonicRegression is O(n log n), no re-grid-search).
    r5 = {}
    for k in range(1, N_FOLDS):
        c_k = per_fold_c[0.01][k]
        fit = fits[(k, 10)]
        platt_c = platt_predict(fit["intercept"], fit["slope"], np.array([c_k]))[0] if fit["platt_valid"] else None

        fit_pool = df[df["fold"] < k]
        test_start_k = folds[k]["test_start"]
        guard = (fit_pool["t0"] + pd.Timedelta(hours=10)) <= test_start_k
        fit_h = fit_pool[guard]
        iso = fit_isotonic(fit_h["p_10h"].to_numpy(), fit_h["reach_10h"].to_numpy())
        iso_c = float(iso.predict([c_k])[0])

        r5[k] = {"c_k_raw": c_k, "c_k_platt": platt_c, "c_k_isotonic": iso_c}
        print(f"[S1H] R5 fold {k}: c_k(raw)={c_k:.6f} c_k(Platt)={platt_c} c_k(isotonic)={iso_c:.6f}",
              flush=True)

    # ---- R6: horizon order breaks, per method, pooled over months 2-8 ----
    r6 = {}
    for method, cols in (("raw", ("p_2h", "p_5h", "p_10h")),
                          ("platt", ("platt_2h", "platt_5h", "platt_10h")),
                          ("isotonic", ("iso_2h", "iso_5h", "iso_10h"))):
        c2, c5, c10 = cols
        valid = ~(scored[c2].isna() | scored[c5].isna() | scored[c10].isna())
        sub = scored[valid]
        n_excluded = len(scored) - len(sub)
        n_2gt5 = int((sub[c2] > sub[c5]).sum())
        n_5gt10 = int((sub[c5] > sub[c10]).sum())
        r6[method] = {"n_scored": len(sub), "n_excluded_nan": n_excluded,
                      "n_p2h_gt_p5h": n_2gt5, "n_p5h_gt_p10h": n_5gt10}
        print(f"[S1H] R6 method={method}: n_scored={len(sub):,} n_excluded(nan)={n_excluded} "
              f"n(p2h>p5h)={n_2gt5} n(p5h>p10h)={n_5gt10}", flush=True)

    # ---- R1: fitted maps (print consolidated, data already printed per-fold above) ----
    r1 = {str(k): {str(h): {"intercept": fits[(k, h)]["intercept"], "slope": fits[(k, h)]["slope"],
                            "platt_valid": fits[(k, h)]["platt_valid"],
                            "iso_at_grid": fits[(k, h)]["iso_at_grid"],
                            "n_dropped_guard": fits[(k, h)]["n_dropped"],
                            "n_fit_pool": fits[(k, h)]["n_fit_pool"],
                            "n_fit_used": fits[(k, h)]["n_fit_used"],
                            "tied_groups": fits[(k, h)]["tied_groups"],
                            "n_iso_saturated": fits[(k, h)]["n_iso_saturated"],
                            "n_iso_contradicted": fits[(k, h)]["n_iso_contradicted"],
                            "n_iso_levels_test": fits[(k, h)]["n_iso_levels_test"]}
                   for h in HORIZONS}
          for k in range(1, N_FOLDS)}

    out = {"r1_fitted_maps": r1, "r2_error_scores": r2, "r3_calibration_deciles": r3,
           "r4_picks": r4, "r5_cutoff": r5, "r6_horizon_order": r6}
    with open(os.path.join(LOG_DIR, "s1h_report.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)

    print("\n[S1H] === 10-LINE SUMMARY ===", flush=True)
    n_invalid = sum(1 for k in range(1, N_FOLDS) for h in HORIZONS if not fits[(k, h)]["platt_valid"])
    print(f"1. Platt fits: {n_invalid} of {7*3} (fold,horizon) pairs had slope<=0 (reported, not used).",
          flush=True)
    print(f"2. Look-ahead guard dropped at most {max(fits[(k,h)]['n_dropped'] for k in range(1,N_FOLDS) for h in HORIZONS)} "
          f"events from any one (fold,horizon) fit pool.", flush=True)
    for h in HORIZONS:
        p = r2[h]["pooled"]
        print(f"3. R2 h={h}h pooled: logloss raw={p['logloss_raw']:.4f} platt={p['logloss_platt']} "
              f"iso={p['logloss_iso']:.4f}; brier raw={p['brier_raw']:.4f} platt={p['brier_platt']} "
              f"iso={p['brier_iso']:.4f}.", flush=True)
    for q in QS:
        pr = r4[q]["pooled"]
        print(f"4. R4 q={q} pooled n={pr['n']}: 10h raw={pr['mean_raw_10h']:.4f} platt={pr['mean_platt_10h']:.4f} "
              f"iso={pr['mean_iso_10h']:.4f} actual={pr['actual_10h']:.4f}.", flush=True)
    print(f"5. R6: n(p2h>p5h) raw={r6['raw']['n_p2h_gt_p5h']} platt={r6['platt']['n_p2h_gt_p5h']} "
          f"iso={r6['isotonic']['n_p2h_gt_p5h']}; n(p5h>p10h) raw={r6['raw']['n_p5h_gt_p10h']} "
          f"platt={r6['platt']['n_p5h_gt_p10h']} iso={r6['isotonic']['n_p5h_gt_p10h']}.", flush=True)
    print("6. Picks are never re-selected -- Rule A per-fold n matches S1-G's saved values exactly in "
          "every (fold,q).", flush=True)
    print("7. Spearman(raw p_10h, Platt p_10h)=1 asserted and held in every fold with a valid Platt fit.",
          flush=True)
    print("8. Descriptive only -- no S1 refit, no vault, no fees/profit.", flush=True)
    print("9. Gate verdict is still FAIL (NUMBERS [HL-MODEL1-S1]); no cause claimed beyond the tables.",
          flush=True)
    print("10. Full fitted maps, decile tables, picks tables and cut-offs are in s1h_report.json and "
          "the per-fold/per-bin log lines above.", flush=True)
    print(f"[S1H] ALL DONE  [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
