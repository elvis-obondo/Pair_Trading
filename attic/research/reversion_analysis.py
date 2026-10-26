"""Three questions the reversion dataset can answer that the precursor data could not.

  Q1  Does the current detector actually pick reverting spreads?
      Compare take-profit rate on rows the detector passed against rows it did
      not. This is the question the old setup could never ask: there, the
      detector defined correctness, so it scored 100% by construction. Here it
      is graded against what prices did, and it is allowed to lose.

  Q2  Can a model beat it?
      Same rows, same price-derived label, chronological split. The detector's
      own reading is available to the model as one input among many rather
      than as the target, so "beat the detector" is a measurable claim.

  Q3  Does the model fire EARLIER?
      For pairs the detector eventually flagged, compare the first day the
      model would have entered with the first day the detector did -- and
      check whether those earlier entries actually won. Earliness is only
      worth anything if the early trades pay; firing sooner and being wrong is
      not an improvement.

Every comparison is restricted to rows that were candidate trades at all
(|z| >= MIN_ENTRY_SIGMA). Rows with no dislocation are not opportunities the
detector missed -- there was no position to take -- and including them would
inflate every rate with trivially-correct abstentions.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

FEATURE_BLOCKLIST = {
    # Direct components of the label or its construction -- including any of
    # these would leak the outcome into the prediction.
    "label_tp", "outcome", "reversion_frac", "bars_to_exit",
    "ticker_a", "ticker_b", "date",
}


def load(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    return df


def q1_detector_skill(cand: pd.DataFrame) -> None:
    print("=" * 76)
    print("Q1 -- does the detector pick reverting spreads?")
    print("=" * 76)
    if "detector_pass" not in cand.columns:
        print("  no detector columns present")
        return
    g = cand.groupby("detector_pass").agg(
        n=("label_tp", "size"),
        take_profit_rate=("label_tp", "mean"),
        mean_reversion_frac=("reversion_frac", "mean"),
    )
    g["take_profit_rate"] = (g["take_profit_rate"] * 100).round(2)
    g["mean_reversion_frac"] = g["mean_reversion_frac"].round(3)
    print(g.to_string())
    if len(g) == 2:
        lift = g.loc[True, "take_profit_rate"] - g.loc[False, "take_profit_rate"]
        print(f"\n  detector edge: {lift:+.2f} percentage points")
        if abs(lift) < 1.0:
            print("  -> the detector is not separating winners from losers here")

    # Strict raw p-value, for contrast with the loose smoothed gate.
    if "detector_raw_p" in cand.columns:
        sub = cand[cand["detector_raw_p"].notna()].copy()
        if len(sub):
            sub["p_bucket"] = pd.cut(sub["detector_raw_p"],
                                     [0, 0.01, 0.05, 0.2, 0.5, 1.0])
            gb = sub.groupby("p_bucket", observed=True).agg(
                n=("label_tp", "size"), take_profit_rate=("label_tp", "mean"))
            gb["take_profit_rate"] = (gb["take_profit_rate"] * 100).round(2)
            print("\n  by raw (unsmoothed) p-value:")
            print(gb.to_string())
    print()


def q2_model_vs_detector(cand: pd.DataFrame, n_null: int = 10) -> tuple:
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score

    print("=" * 76)
    print("Q2 -- can a model beat it, on the same rows and the same label?")
    print("=" * 76)
    feats = [c for c in cand.columns
             if c not in FEATURE_BLOCKLIST and pd.api.types.is_numeric_dtype(cand[c])]
    # detector_pass is boolean -- keep it, as an input rather than the answer
    if "detector_pass" in cand.columns:
        cand = cand.copy()
        cand["detector_pass"] = cand["detector_pass"].astype(float)
        if "detector_pass" not in feats:
            feats.append("detector_pass")
    d = cand.sort_values("date")
    X, y = d[feats], d["label_tp"].astype(int)
    cut = int(len(d) * 0.7)
    Xtr, Xte, ytr, yte = X.iloc[:cut], X.iloc[cut:], y.iloc[:cut], y.iloc[cut:]
    split_date = d["date"].iloc[cut]
    print(f"  features: {len(feats)}")
    print(f"  train {len(Xtr)} rows (to {split_date.date()}), test {len(Xte)} rows")
    print(f"  base take-profit rate: train {ytr.mean():.3f}, test {yte.mean():.3f}")
    if yte.nunique() < 2 or len(Xte) < 100:
        print("  insufficient test data")
        return None, None, None

    m = HistGradientBoostingClassifier(max_iter=300, random_state=0)
    m.fit(Xtr, ytr)
    p = m.predict_proba(Xte)[:, 1]
    auc = roc_auc_score(yte, p)

    rng = np.random.default_rng(0)
    nulls = []
    for _ in range(n_null):
        ys = pd.Series(rng.permutation(ytr.values), index=ytr.index)
        mm = HistGradientBoostingClassifier(max_iter=300, random_state=0)
        mm.fit(Xtr, ys)
        nulls.append(roc_auc_score(yte, mm.predict_proba(Xte)[:, 1]))
    print(f"  model AUC: {auc:.4f}   shuffled-null mean {np.mean(nulls):.4f}, "
          f"p95 {np.percentile(nulls, 95):.4f}")
    print(f"  beats null: {auc > np.percentile(nulls, 95)}")

    # Detector as a standalone classifier on the same test rows.
    if "detector_pass" in Xte.columns and Xte["detector_pass"].nunique() > 1:
        det_auc = roc_auc_score(yte, Xte["detector_pass"])
        print(f"  detector-alone AUC on the same rows: {det_auc:.4f}")

    # What a model actually buys you: win rate in the top decile of its score.
    te = d.iloc[cut:].copy()
    te["score"] = p
    top = te.nlargest(max(1, len(te) // 10), "score")
    print(f"\n  top-decile by model score: {len(top)} trades, "
          f"take-profit {top['label_tp'].mean() * 100:.2f}% "
          f"(vs {yte.mean() * 100:.2f}% overall)")
    if "detector_pass" in te.columns:
        dsel = te[te["detector_pass"] > 0.5]
        if len(dsel):
            print(f"  detector-selected on same test window: {len(dsel)} trades, "
                  f"take-profit {dsel['label_tp'].mean() * 100:.2f}%")
    return m, feats, te


def q3_earliness(te: pd.DataFrame, quantile: float = 0.9) -> None:
    """Per pair, first model entry vs first detector entry, and whether the
    early window actually paid."""
    print()
    print("=" * 76)
    print("Q3 -- does the model fire earlier, and do the early trades win?")
    print("=" * 76)
    if te is None or "detector_pass" not in te.columns:
        print("  unavailable")
        return
    thresh = te["score"].quantile(quantile)
    te = te.copy()
    te["model_fire"] = te["score"] >= thresh
    rows = []
    for (a, b), sub in te.groupby(["ticker_a", "ticker_b"]):
        sub = sub.sort_values("date")
        mf = sub.loc[sub["model_fire"], "date"]
        df_ = sub.loc[sub["detector_pass"] > 0.5, "date"]
        if mf.empty or df_.empty:
            continue
        rows.append({"pair": f"{a}/{b}", "first_model": mf.iloc[0],
                     "first_detector": df_.iloc[0],
                     "days_earlier": (df_.iloc[0] - mf.iloc[0]).days})
    if not rows:
        print("  no pairs where both fired in the test window")
        return
    e = pd.DataFrame(rows)
    print(f"  pairs where both fired: {len(e)}")
    print(f"  model earlier: {(e['days_earlier'] > 0).sum()} | "
          f"same day: {(e['days_earlier'] == 0).sum()} | "
          f"later: {(e['days_earlier'] < 0).sum()}")
    print(f"  median days earlier: {e['days_earlier'].median():.1f}")

    early = te[te["model_fire"] & (te["detector_pass"] <= 0.5)]
    both = te[te["model_fire"] & (te["detector_pass"] > 0.5)]
    print(f"\n  model fires, detector silent: {len(early)} trades, "
          f"take-profit {early['label_tp'].mean() * 100:.2f}%"
          if len(early) else "\n  no model-only trades")
    print(f"  both agree               : {len(both)} trades, "
          f"take-profit {both['label_tp'].mean() * 100:.2f}%"
          if len(both) else "  no agreed trades")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    args = ap.parse_args()
    df = load(Path(args.path))
    print(f"loaded {df.shape} rows\n")
    print("outcome mix (all rows):")
    print(df["outcome"].value_counts().to_string())
    cand = df[df["label_tp"].notna()].copy()
    print(f"\ncandidate trades (|z| >= entry threshold): {len(cand)} "
          f"({len(cand) / len(df) * 100:.1f}% of rows)")
    print(f"overall take-profit rate: {cand['label_tp'].mean() * 100:.2f}%\n")

    q1_detector_skill(cand)
    _, _, te = q2_model_vs_detector(cand)
    q3_earliness(te)


if __name__ == "__main__":
    main()
