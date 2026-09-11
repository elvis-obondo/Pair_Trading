"""Does a signal move in a precursor pattern before detection?

Two independent questions, deliberately kept separate because they can
disagree and the disagreement is informative:

  1. MARGINAL: does this signal move in a consistent direction in the days
     before a detection, more often than chance? This is the question the
     earlier exploratory pass asked, and the one that found theta beating
     chance and beta_cv moving opposite the naive hypothesis. Reported as the
     fraction of events whose trajectory slope is negative, with a two-sided
     binomial test against 0.5.

     A signal can pass this and still be useless: "beta_cv rises before 80% of
     detections" is only tradeable if detections are distinguishable from
     non-detections, and every row here IS a detection. This test has no
     negative class. It measures consistency, not discriminative power. Read
     it as a description of what happens before detections, never as evidence
     that the signal predicts them.

  2. DISCRIMINATIVE: does this signal help separate detections that STICK from
     detections that die immediately? This one has a real negative class and a
     real out-of-sample test, so it is the question with an actionable answer.
     Label is raw-gate survival, which is the strict definition -- the smoothed
     gate is self-referential (an event is detected and killed by the same
     rule) and would leak.

Both are reported against a null built by shuffling, not against a textbook
p-value alone: with 400+ events and ~24 signals, some marginal test clears
0.05 by construction. The shuffled null shows what "significant" looks like
when nothing is there.

Chronological split, never random: events are autocorrelated in time (the same
market regime produces many detections at once), so a random split leaks
regime information across the boundary and inflates out-of-sample scores.

Usage:
    python research/precursor_pattern_test.py ENRICHED.parquet [--label-days 3]
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

PROJECT_ROOT = Path(__file__).parent.parent
EVENTS_PATH = PROJECT_ROOT / "research" / "coint_survival_events.parquet"

# Trajectory columns are summarised by slope before testing. Slope rather than
# (last - first): a two-point difference throws away the interior of the
# trajectory and is far noisier, and these trajectories are short enough
# (2-8 points) that a least-squares slope is still cheap.
MIN_TRAJ_POINTS = 3


def trajectory_slope(v) -> float:
    """Least-squares slope per day over a trajectory, NaN-tolerant.

    Returns NaN rather than 0.0 when a trajectory is too short or too sparse:
    0.0 is a real, meaningful value here ("flat"), so using it as a
    missing-data sentinel would silently pull every degenerate row toward the
    'no movement' conclusion.
    """
    if not isinstance(v, (np.ndarray, list)) or len(v) < MIN_TRAJ_POINTS:
        return np.nan
    y = np.asarray(v, dtype=float)
    mask = np.isfinite(y)
    if mask.sum() < MIN_TRAJ_POINTS:
        return np.nan
    x = np.arange(len(y), dtype=float)[mask]
    y = y[mask]
    if np.ptp(x) == 0:
        return np.nan
    return float(np.polyfit(x, y, 1)[0])


def trajectory_last(v) -> float:
    """Last finite value of a trajectory -- the reading closest to detection."""
    if not isinstance(v, (np.ndarray, list)) or len(v) == 0:
        return np.nan
    y = np.asarray(v, dtype=float)
    y = y[np.isfinite(y)]
    return float(y[-1]) if len(y) else np.nan


def embargo(v, days: int):
    """Drop the final `days` readings of a trajectory.

    Every trajectory in the precursor file runs up to and INCLUDING
    detection_date, which makes the tail of the trajectory the very data that
    triggered the detection. That is fatal for p_value in particular: the
    smoothed gate fires when the trailing 3-day mean p-value crosses
    RECENT_P_THRESHOLD, so the last three p-values are mechanically bound to
    the detection, and a survival label derived from the same p-value series
    is then partly readable straight off the feature. Measured: without an
    embargo the stick/die classifier scores AUC 0.99 with
    pvalue_trajectory_14d__last carrying 45% of permutation importance -- a
    leak, not a finding.

    Embargoing 3 days (SMOOTHED_LOOKBACK_WINDOWS) removes the whole window
    that participates in triggering detection, so what remains is genuinely
    information available BEFORE the gate could have fired. The cost is real:
    the 4-day lookback retains almost nothing after a 3-day embargo, which is
    why the longer lookbacks carry the analysis once this is on.
    """
    if not isinstance(v, (np.ndarray, list)) or days <= 0:
        return v
    y = np.asarray(v, dtype=float)
    return y[:-days] if len(y) > days else np.array([])


def build_features(df: pd.DataFrame, embargo_days: int = 0) -> tuple[pd.DataFrame, list[str]]:
    """Slope + last-value features for every trajectory column, plus any
    scalar columns already present. Returns (feature_frame, trajectory_names)."""
    traj_cols = [c for c in df.columns if "trajectory" in c]
    feats = {}
    for c in traj_cols:
        col = df[c].map(lambda v: embargo(v, embargo_days)) if embargo_days else df[c]
        feats[f"{c}__slope"] = col.map(trajectory_slope)
        feats[f"{c}__last"] = col.map(trajectory_last)
    # scalars that are already one number per event
    for c in ["eventual_stationary_sigma", "prior_detection_count",
              "days_since_prior_detection", "prior_survival_days_raw"]:
        if c in df.columns:
            feats[c] = pd.to_numeric(df[c], errors="coerce")
    return pd.DataFrame(feats, index=df.index), traj_cols


def marginal_test(feat: pd.DataFrame, traj_cols: list[str], rng) -> pd.DataFrame:
    """Per-signal: what fraction of events show a falling trajectory, and is
    that fraction distinguishable from a coin flip."""
    rows = []
    for c in traj_cols:
        s = feat[f"{c}__slope"].dropna()
        s = s[s != 0]
        n = len(s)
        if n < 30:
            rows.append({"signal": c, "n": n, "frac_falling": np.nan,
                         "p_binom": np.nan, "verdict": "too few events"})
            continue
        n_down = int((s < 0).sum())
        frac = n_down / n
        p = stats.binomtest(n_down, n, 0.5).pvalue
        rows.append({"signal": c, "n": n, "frac_falling": frac, "p_binom": p,
                     "verdict": ""})
    out = pd.DataFrame(rows)
    # Shuffled null: how extreme does frac_falling get when direction is random?
    # Gives a concrete "this is what noise looks like at this n" reference.
    if len(out):
        n_ref = int(out["n"].median())
        if n_ref >= 30:
            null = [abs(rng.binomial(n_ref, 0.5) / n_ref - 0.5) for _ in range(2000)]
            thresh = np.percentile(null, 95)
            out["exceeds_null95"] = (out["frac_falling"] - 0.5).abs() > thresh
            out.attrs["null_threshold"] = thresh
            out.attrs["null_n"] = n_ref
    return out


def make_label(df: pd.DataFrame, events_path: Path, label_days: int,
               exclude_doa: bool = False) -> pd.Series:
    """1 = the detection stuck (raw gate survived >= label_days), 0 = it died.

    Right-censoring is handled by only ever letting censoring create a
    positive, never a negative: an event still alive with fewer than
    label_days observed is dropped (we cannot know), while one already past
    label_days is a 1 regardless of whether it later dies.

    exclude_doa: drop events flagged raw_already_failing_at_detection -- the
    ones where the strict gate had ALREADY been failing for three consecutive
    days at the moment the smoothed gate declared a detection. These are 77%
    of all events in the current data. Including them means the model is
    mostly being asked to predict an artifact of gate disagreement rather than
    anything about the pair, so the more meaningful question -- among
    detections that were at least alive at birth, which ones stick -- needs
    them removed.
    """
    ev = pd.read_parquet(events_path)
    ev["detection_date"] = pd.to_datetime(ev["detection_date"]).dt.normalize()
    key = ["ticker_a", "ticker_b", "detection_date"]
    d = df[key].copy()
    d["detection_date"] = pd.to_datetime(d["detection_date"]).dt.normalize()
    cols = ["survival_days_raw", "raw_still_alive", "raw_already_failing_at_detection"]
    m = d.merge(ev[key + cols], on=key, how="left")
    label = pd.Series(np.nan, index=df.index, dtype="float64")
    stuck = m["survival_days_raw"] >= label_days
    died = (m["survival_days_raw"] < label_days) & (~m["raw_still_alive"].fillna(False))
    label[stuck.values] = 1.0
    label[died.values] = 0.0
    doa = m["raw_already_failing_at_detection"].fillna(False).values
    print(f"  dead-on-arrival (raw gate already failing at detection): "
          f"{int(doa.sum())}/{len(doa)} ({doa.mean() * 100:.1f}%)")
    if exclude_doa:
        label[doa] = np.nan
        print(f"  excluded them -> {int(label.notna().sum())} labelled events remain")
    return label


def discriminative_test(feat: pd.DataFrame, label: pd.Series, dates: pd.Series,
                        rng, n_null: int = 20) -> dict:
    """Chronological 70/30 split, gradient-boosted trees, out-of-sample AUC,
    against a label-shuffled null distribution."""
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score

    ok = label.notna()
    X = feat[ok]
    y = label[ok].astype(int)
    d = pd.to_datetime(dates[ok])
    order = np.argsort(d.values)
    X, y = X.iloc[order], y.iloc[order]

    # Drop degenerate feature columns. A column that is all-NaN, or constant,
    # carries no information and breaks HistGradientBoostingClassifier's
    # binning outright (it cannot form a single bin edge). Dropping is done on
    # the TRAIN split only and applied to both, so the test split cannot
    # influence which features the model is allowed to see.
    cut = int(len(X) * 0.7)
    train_mask = np.zeros(len(X), dtype=bool)
    train_mask[:cut] = True
    tr_view = X[train_mask]
    keep = [c for c in X.columns
            if tr_view[c].notna().sum() >= 2 and tr_view[c].nunique(dropna=True) >= 2]
    dropped = [c for c in X.columns if c not in keep]
    X = X[keep]
    Xtr, Xte = X.iloc[:cut], X.iloc[cut:]
    ytr, yte = y.iloc[:cut], y.iloc[cut:]

    result = {"n_train": len(Xtr), "n_test": len(Xte),
              "base_rate_train": float(ytr.mean()) if len(ytr) else np.nan,
              "base_rate_test": float(yte.mean()) if len(yte) else np.nan,
              "n_features": X.shape[1], "n_features_dropped_degenerate": len(dropped)}
    # Refuse to report a number rather than reporting a meaningless one: with a
    # handful of positives in the test split, AUC swings wildly on single
    # events and would read as signal when it is sampling noise.
    n_pos_test, n_pos_train = int(yte.sum()), int(ytr.sum())
    if len(Xte) < 30 or yte.nunique() < 2 or ytr.nunique() < 2:
        result["auc"] = np.nan
        result["note"] = "insufficient test data or single-class split"
        return result
    if n_pos_test < 10 or n_pos_train < 10:
        result["auc"] = np.nan
        result["note"] = (f"too few positives to trust an AUC "
                          f"(train={n_pos_train}, test={n_pos_test}; need >=10 each)")
        return result

    def fit_auc(y_train):
        m = HistGradientBoostingClassifier(max_iter=200, random_state=0)
        m.fit(Xtr, y_train)
        return roc_auc_score(yte, m.predict_proba(Xte)[:, 1]), m

    auc, model = fit_auc(ytr)
    null_aucs = []
    for _ in range(n_null):
        y_shuf = pd.Series(rng.permutation(ytr.values), index=ytr.index)
        if y_shuf.nunique() < 2:
            continue
        null_aucs.append(fit_auc(y_shuf)[0])
    result["auc"] = float(auc)
    result["null_auc_mean"] = float(np.mean(null_aucs)) if null_aucs else np.nan
    result["null_auc_p95"] = float(np.percentile(null_aucs, 95)) if null_aucs else np.nan
    result["beats_null"] = bool(auc > result["null_auc_p95"]) if null_aucs else False

    # Permutation importance on the test split -- which features carry the AUC.
    from sklearn.inspection import permutation_importance
    pi = permutation_importance(model, Xte, yte, n_repeats=5, random_state=0,
                                scoring="roc_auc")
    imp = (pd.Series(pi.importances_mean, index=X.columns)
           .sort_values(ascending=False).head(12))
    result["top_features"] = imp
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--label-days", type=int, default=1,
                    help="raw-gate survival days for a positive label (default 1; "
                         "only 3.6%% of events reach 3 days, so higher values "
                         "starve the positive class)")
    ap.add_argument("--embargo-days", type=int, default=3,
                    help="drop the final N days of every trajectory before building "
                         "features (default 3 = the smoothed gate's trailing window, "
                         "which mechanically triggers the detection; 0 disables and "
                         "will leak)")
    ap.add_argument("--exclude-doa", action="store_true",
                    help="drop events whose raw gate was already failing at detection")
    ap.add_argument("--events", default=str(EVENTS_PATH))
    args = ap.parse_args()

    rng = np.random.default_rng(0)
    df = pd.read_parquet(args.path)
    print(f"loaded {args.path}: {df.shape}\n")

    feat, traj_cols = build_features(df, embargo_days=args.embargo_days)
    print(f"{len(traj_cols)} trajectory columns -> {feat.shape[1]} features")
    print(f"embargo: last {args.embargo_days} day(s) of every trajectory dropped before features\n")

    print("=" * 78)
    print("1. MARGINAL -- direction consistency before detection (no negative class)")
    print("=" * 78)
    mt = marginal_test(feat, traj_cols, rng)
    if "null_threshold" in mt.attrs:
        print(f"shuffled null: |frac-0.5| exceeds {mt.attrs['null_threshold']:.4f} "
              f"only 5% of the time at n={mt.attrs['null_n']}\n")
    with pd.option_context("display.width", 200, "display.max_rows", 100):
        print(mt.sort_values("frac_falling", na_position="last").to_string(index=False))
    print()

    print("=" * 78)
    print(f"2. DISCRIMINATIVE -- does it separate stick (raw survival >= {args.label_days}d) from death")
    print("=" * 78)
    label = make_label(df, Path(args.events), args.label_days, args.exclude_doa)
    print(f"label: {int((label == 1).sum())} stuck, {int((label == 0).sum())} died, "
          f"{int(label.isna().sum())} unusable (censored short or excluded)")
    res = discriminative_test(feat, label, df["detection_date"], rng)
    for k, v in res.items():
        if k == "top_features":
            continue
        print(f"  {k}: {v}")
    if "top_features" in res:
        print("\n  top features by permutation importance (test split):")
        for name, val in res["top_features"].items():
            print(f"    {val:+.4f}  {name}")


if __name__ == "__main__":
    main()
