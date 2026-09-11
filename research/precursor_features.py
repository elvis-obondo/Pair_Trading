"""Tier-A precursor signals: derived from the survival tables, not from prices.

Why this is a separate module rather than more columns inside
coint_precursors.py's per-event loop:

  Every signal in coint_precursors.py needs the raw price series, so it pays
  the per-event cost of slicing prices and re-fitting models -- that is what
  makes a full run multi-hour. The signals here need none of that. They are
  functions of coint_survival_pvalues.parquet and coint_survival_events.parquet,
  both of which are already computed. Adding them as a post-hoc enrichment
  means (a) they cost seconds instead of hours, (b) they can be re-derived or
  redefined without re-running the price extraction at all, and (c) they are
  structurally incapable of perturbing the price-derived trajectories, since
  this module only ever adds columns to a frame it does not otherwise touch.

Signals added (all four share one pass over the p-value table):

  pvalue_trajectory_{L}d
      The raw daily Engle-Granger p-value for the L days ending at
      detection_date. No windowing concept applies -- each stored p-value is
      already one 7-day-window reading at daily stride, so a day IS a reading,
      the same convention funding_convergence uses in coint_precursors.py.
      This is the one signal prior analysis found to genuinely lead theta
      (leads by 1 day, r=-0.594 lagged vs -0.370 contemporaneous), so it is
      the highest-prior addition of the set.

  breadth_a_trajectory_{L}d / breadth_b_trajectory_{L}d
      For each leg separately: how many DISTINCT other tickers that leg is
      simultaneously passing the smoothed cointegration gate with, on each of
      the L days before detection. Targets the spurious-detection mode where
      one asset makes a large move and "cointegrates" with most of the
      universe at once -- visible in the live screen as LUNA occupying 6 of 13
      tradeable slots on a single day. A pair whose legs are each cointegrating
      with one or two things is a different object from a pair whose leg is
      cointegrating with forty.
      Kept as two columns rather than one combined statistic on purpose:
      whether the asymmetry between legs matters is a question for the feature
      -engineering stage, and combining here would destroy the information
      needed to answer it.

  universe_detections_trajectory_{L}d
      Total pairs passing the smoothed gate universe-wide on each of the L
      days -- a market-regime covariate rather than a pair-specific one. Falls
      out of the same computation as breadth. Lets a later model ask whether a
      detection arriving during a market-wide burst of detections behaves
      differently from one arriving in a quiet stretch.

  prior_detection_count / days_since_prior_detection / prior_survival_days_raw
      Scalars, from the events table: how many times this pair has been
      detected BEFORE this event, how long since the last one, and how long
      that last one survived on the raw gate. 65,015 repeat-detection events
      across 21,592 pairs exist in the data, so most events are not a pair's
      first. A pair on its fourth detection in a month is a different
      proposition from a pair detected once, and nothing in the existing
      feature set expresses that.
      Strictly backward-looking: only events strictly before this one are
      counted, so these carry no information from the future of the event
      being described.

Gate convention is imported, not redefined: the smoothed pass rule here is
coint_survival.py's (trailing SMOOTHED_LOOKBACK_WINDOWS daily p-values,
mean < RECENT_P_THRESHOLD), which is itself pair_analysis.py's live
recent_cointegrated rule. If those move, this moves with them.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from pathlib import Path

import numpy as np
import pandas as pd

from pair_analysis import RECENT_P_THRESHOLD
from coint_survival import SMOOTHED_LOOKBACK_WINDOWS

PROJECT_ROOT = Path(__file__).parent.parent
PVALUES_PATH = PROJECT_ROOT / "research" / "coint_survival_pvalues.parquet"
EVENTS_PATH = PROJECT_ROOT / "research" / "coint_survival_events.parquet"
PRECURSORS_PATH = PROJECT_ROOT / "research" / "coint_precursors.parquet"
OUTPUT_PATH = PROJECT_ROOT / "research" / "coint_precursors_enriched.parquet"

LOOKBACKS = [14, 10, 7, 4]


# ---------------------------------------------------------------------------
# Shared pass-matrix computation (one pass, feeds three of the four signals)
# ---------------------------------------------------------------------------

def build_smoothed_pass_table(pvalues: pd.DataFrame) -> pd.DataFrame:
    """Per (pair, date): the smoothed gate's pass/fail, using the same
    trailing-mean rule as coint_survival.derive_events.

    Returns the input frame with `date` normalized to midnight and a boolean
    `smoothed_pass` column. Dates are normalized because the p-value table
    stores the last BAR timestamp of each window (e.g. 23:30), while every
    consumer here reasons in whole days.
    """
    df = pvalues.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df = df.sort_values(["ticker_a", "ticker_b", "date"])
    # Trailing mean of the last SMOOTHED_LOOKBACK_WINDOWS readings, per pair.
    # min_periods matches derive_events' "fails closed until enough readings
    # exist" behaviour: fewer than the full lookback -> NaN -> not a pass.
    df["smoothed_p"] = (
        df.groupby(["ticker_a", "ticker_b"])["p_value"]
        .transform(lambda s: s.rolling(SMOOTHED_LOOKBACK_WINDOWS, min_periods=SMOOTHED_LOOKBACK_WINDOWS).mean())
    )
    df["smoothed_pass"] = df["smoothed_p"] < RECENT_P_THRESHOLD
    return df


def build_breadth_series(pass_table: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """From the pass table, derive:
      - per-(ticker, date) breadth: number of distinct partners that ticker is
        passing with on that date. A pair contributes to BOTH its legs' counts.
      - per-date universe total: number of passing pairs that day.
    """
    passing = pass_table[pass_table["smoothed_pass"]]
    # Each passing pair contributes one partner to each of its two legs.
    left = passing[["date", "ticker_a"]].rename(columns={"ticker_a": "ticker"})
    right = passing[["date", "ticker_b"]].rename(columns={"ticker_b": "ticker"})
    stacked = pd.concat([left, right], ignore_index=True)
    breadth = (
        stacked.groupby(["ticker", "date"]).size()
        .rename("breadth").reset_index()
    )
    breadth_lookup = breadth.set_index(["ticker", "date"])["breadth"]
    universe = passing.groupby("date").size().rename("universe_detections")
    return breadth_lookup, universe


# ---------------------------------------------------------------------------
# Per-event trajectory extraction
# ---------------------------------------------------------------------------

def _daily_index(detection_date: pd.Timestamp, L: int) -> pd.DatetimeIndex:
    """The L whole days ending at (and including) detection_date."""
    end = pd.Timestamp(detection_date).normalize()
    return pd.date_range(end - pd.Timedelta(days=L - 1), end, freq="D")


def _pvalue_trajectory(pair_pvals: pd.Series, detection_date: pd.Timestamp, L: int) -> np.ndarray:
    """Raw daily p-values over the L-day window. Missing days come back NaN
    rather than being dropped, so position in the array always means the same
    number of days before detection."""
    if pair_pvals is None or pair_pvals.empty:
        return np.array([])
    return pair_pvals.reindex(_daily_index(detection_date, L)).to_numpy(dtype=float)


def _breadth_trajectory(
    breadth_lookup: pd.Series, ticker: str, detection_date: pd.Timestamp, L: int
) -> np.ndarray:
    """Breadth for one leg over the L-day window. A ticker with no passing
    partners on a day is genuinely 0, not missing -- absence from the lookup
    means zero partners, so reindex fills with 0 rather than NaN."""
    idx = _daily_index(detection_date, L)
    try:
        series = breadth_lookup.loc[ticker]
    except KeyError:
        return np.zeros(len(idx), dtype=float)
    return series.reindex(idx).fillna(0.0).to_numpy(dtype=float)


def _universe_trajectory(universe: pd.Series, detection_date: pd.Timestamp, L: int) -> np.ndarray:
    """Universe-wide passing-pair count over the L-day window. Same zero-vs-
    missing reasoning as breadth."""
    return universe.reindex(_daily_index(detection_date, L)).fillna(0.0).to_numpy(dtype=float)


def build_detection_history(events: pd.DataFrame) -> pd.DataFrame:
    """Strictly backward-looking repeat-detection scalars, per event.

    For each event: how many detections this pair had strictly BEFORE it, how
    many days since the previous one, and the raw-gate survival of that
    previous one. First detections get count 0 and NaN for the other two --
    NaN rather than a sentinel like -1, so a model treats "no prior detection"
    as missing rather than as an extreme numeric value.
    """
    ev = events.copy()
    ev["detection_date"] = pd.to_datetime(ev["detection_date"]).dt.normalize()
    ev = ev.sort_values(["ticker_a", "ticker_b", "detection_date"]).reset_index(drop=True)
    grp = ev.groupby(["ticker_a", "ticker_b"], sort=False)
    ev["prior_detection_count"] = grp.cumcount()
    prev_date = grp["detection_date"].shift(1)
    ev["days_since_prior_detection"] = (ev["detection_date"] - prev_date).dt.days.astype("float64")
    ev["prior_survival_days_raw"] = grp["survival_days_raw"].shift(1).astype("float64")
    return ev[["ticker_a", "ticker_b", "detection_date",
               "prior_detection_count", "days_since_prior_detection", "prior_survival_days_raw"]]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def enrich(
    precursors_path: Path = PRECURSORS_PATH,
    pvalues_path: Path = PVALUES_PATH,
    events_path: Path = EVENTS_PATH,
    output_path: Path | None = OUTPUT_PATH,
    lookbacks: list[int] = LOOKBACKS,
) -> pd.DataFrame:
    """Add the Tier-A columns to an existing precursor frame.

    The input frame's own columns are never read for computation and never
    written to -- only new columns are attached -- so this cannot perturb the
    price-derived trajectories it sits alongside.
    """
    print(f"[INFO] Loading precursors: {precursors_path.name}")
    pre = pd.read_parquet(precursors_path)
    pre["detection_date"] = pd.to_datetime(pre["detection_date"]).dt.normalize()
    print(f"[INFO] {len(pre)} precursor rows")

    print(f"[INFO] Loading p-values: {pvalues_path.name}")
    pvalues = pd.read_parquet(pvalues_path)
    print(f"[INFO] {len(pvalues)} p-value rows -- building smoothed pass table...")
    pass_table = build_smoothed_pass_table(pvalues)
    n_pass = int(pass_table["smoothed_pass"].sum())
    print(f"[INFO] {n_pass} passing (pair, date) readings")

    print("[INFO] Building breadth + universe series...")
    breadth_lookup, universe = build_breadth_series(pass_table)
    print(f"[INFO] breadth covers {breadth_lookup.index.get_level_values(0).nunique()} tickers, "
          f"universe series spans {len(universe)} days")

    # p-value lookup: one Series per pair, indexed by date, for cheap reindexing
    pv_idx = pass_table.set_index(["ticker_a", "ticker_b", "date"])["p_value"].sort_index()

    print("[INFO] Extracting per-event trajectories...")
    new_cols: dict[str, list] = {}
    for L in lookbacks:
        new_cols[f"pvalue_trajectory_{L}d"] = []
        new_cols[f"breadth_a_trajectory_{L}d"] = []
        new_cols[f"breadth_b_trajectory_{L}d"] = []
        new_cols[f"universe_detections_trajectory_{L}d"] = []

    for i, (a, b, d) in enumerate(zip(pre["ticker_a"], pre["ticker_b"], pre["detection_date"])):
        try:
            pair_pvals = pv_idx.loc[(a, b)]
        except KeyError:
            pair_pvals = None
        for L in lookbacks:
            new_cols[f"pvalue_trajectory_{L}d"].append(_pvalue_trajectory(pair_pvals, d, L))
            new_cols[f"breadth_a_trajectory_{L}d"].append(_breadth_trajectory(breadth_lookup, a, d, L))
            new_cols[f"breadth_b_trajectory_{L}d"].append(_breadth_trajectory(breadth_lookup, b, d, L))
            new_cols[f"universe_detections_trajectory_{L}d"].append(_universe_trajectory(universe, d, L))
        if (i + 1) % 5000 == 0:
            print(f"  [{i + 1}/{len(pre)}]")

    out = pre.copy()
    for col, vals in new_cols.items():
        out[col] = vals

    print("[INFO] Building detection-history scalars...")
    events = pd.read_parquet(events_path)
    hist = build_detection_history(events)
    before = len(out)
    out = out.merge(hist, on=["ticker_a", "ticker_b", "detection_date"], how="left")
    assert len(out) == before, f"merge changed row count {before} -> {len(out)}"

    if output_path is not None:
        out.to_parquet(output_path, index=False)
        print(f"[INFO] Wrote {len(out)} rows, {len(out.columns)} columns to {output_path}")
    return out


if __name__ == "__main__":
    enrich()
