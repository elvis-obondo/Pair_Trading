"""
Survival-curve infrastructure for cointegration detection events.

Independent of trade_pool.parquet / trade_pool_gap.parquet -- never reads,
writes, or modifies either pool. Uses research/pair_analysis.py's existing
price-loading and constants (get_price_levels, _base_symbol,
COINT_PVALUE_THRESHOLD, RECENT_P_THRESHOLD, BARS_PER_DAY) without changing
any of that code. The rolling-cointegration window/stride semantics here
(7-day window, daily stride) are reimplemented locally rather than calling
pair_analysis.rolling_coint() directly, because this module needs to resume
from an arbitrary window position for incremental re-runs -- see
update_pvalue_series()'s docstring. The window CONTENTS and math are
identical to rolling_coint(price_a, price_b, window=7*BARS_PER_DAY,
stride=BARS_PER_DAY): same 336-bar window, same 48-bar stride, same
Engle-Granger coint() call per window.

Why re-run discovery independently instead of reading the trade pools: the
trade pools only contain pairs that were selected as a batch run's candidate
AND fired >=1 trade -- a small, biased subset of everything that ever passed
cointegration screening. This tracks ALL pairs that ever crossed into
"passing" territory, not just the ones that happened to trade.

Two output tables, deliberately different storage lifecycles (confirmed with
the user before building):

  coint_survival_pvalues.parquet -- raw material. Append-only. One row per
  (pair, date) daily-stride rolling-window Engle-Granger p-value. `date` is
  the LAST bar's timestamp in that window -- "as of this date, using the
  trailing 7 days, is this pair cointegrated." A later run only computes
  NEW dates for pairs already tracked (see update_pvalue_series), which is
  what makes periodic re-runs cheap instead of a full ~86-minute rescan
  every time.

  coint_survival_events.parquet -- derived. Regenerated in FULL every run,
  never append-only. One row per detection event (see derive_events). This
  is intentionally NOT append-only, unlike trade_pool.parquet: a trade's
  P&L is a fixed historical fact once closed, but a "still alive" survival
  event is a censored estimate that needs to be able to UPDATE in place
  (not accumulate a new row) once more data reveals whether it died.
  Cheap to fully rebuild -- no coint() calls, pure pandas over already-
  computed p-values -- so full regeneration is not a cost problem.

Detection event definition (confirmed with the user before building):
  - Anchored on the SMOOTHED/live-gate definition -- mean of the trailing 3
    daily-stride p-values < RECENT_P_THRESHOLD -- exactly matching
    pair_analysis.py's recent_cointegrated logic in analyze_top_pairs. An
    event starts the first day this flips False/undefined -> True.
  - A later re-qualification (fail, then pass again) is a SEPARATE, new
    event, not a continuation. Matches the live system's own behavior:
    once excluded, re-inclusion is a fresh decision on fresh evidence.

Two survival curves are computed for every event, from the SAME
detection_date:
  - survival_days_smoothed: days until the SAME smoothed gate that
    triggered detection first flips back False. Self-referential by
    construction (start and end use the same rule).
  - survival_days_raw: days until the raw, unsmoothed daily p-value
    (< COINT_PVALUE_THRESHOLD) has failed for RAW_CONSECUTIVE_FAIL_DAYS
    consecutive days. Proposed and confirmed as 3 -- matching the magnitude
    of pair_analysis.py's own tail(3) convention for the smoothed gate, but
    NOT empirically re-derived for this run-length use (that "3" was chosen
    for a mean-based smoother, not a consecutive-failure counter) -- a
    reasonable default by precedent, not a proven-optimal one.
  If the raw gate is ALREADY mid-failure-streak exactly at detection_date,
  raw_already_failing_at_detection is set and survival_days_raw is forced
  to 0, rather than reporting a small positive number that looks like a
  short-but-real survival.

Right-censoring (confirmed accounted for): an event with no observed
"death" by the end of available data gets *_still_alive=True and
survival_days_* measured up to last_data_date, not silently treated as a
short-lived or excluded event.

Left-truncation (a related, unasked-about issue, flagged rather than
silently ignored): a pair whose smoothed gate is ALREADY passing the very
first moment it's evaluable (its first 3 valid daily p-values) might have
been cointegrated for a while before our own history begins -- we can't
know. Flagged via left_truncated, not corrected for.

Candidate universe (confirmed with the user before building): full
brute-force, every valid pair in the current universe (22,366 pairs as of
2026-08-24, C(212,2) minus same-underlying pairs) -- no pre-filter, no bias
risk of missing a short-lived relationship. Benchmarked at ~86 minutes for
a full first run against the full 71-day history available at build time.
This is O(pairs) = O(tickers^2); revisit with a pre-filtered candidate set
(e.g. reusing analyze_top_pairs' own cheap stage-1 scan, run per-week
across history to avoid diluting short-lived relationships into a weak
whole-history p-value) if the ticker universe grows much larger.

Threshold note: derive_events() uses the CURRENT values of
pair_analysis.COINT_PVALUE_THRESHOLD / RECENT_P_THRESHOLD at call time. If
those change, the next regeneration reinterprets the ENTIRE historical
p-value series under the new thresholds -- intentional, given the events
table is "current best read," not frozen to whatever was active at first
detection. This means detection_date boundaries can shift between runs if
the thresholds themselves change.

Time resolution: daily, matching rolling_coint's and recent_cointegrated's
existing daily-stride convention. Not built at bar-level resolution.

Incremental-resume assumption, stated explicitly: bars, once observed, are
never revised or removed from the underlying feather files. If a pair's
last-stored p-value date is no longer found at all in its current joint
price index, that assumption is treated as violated for that pair and its
entire series is recomputed from scratch (logged, not silently trusted).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import itertools
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import coint

from data_loader import get_price_levels
from pair_analysis import _base_symbol, BARS_PER_DAY, COINT_PVALUE_THRESHOLD, RECENT_P_THRESHOLD

PROJECT_ROOT = Path(__file__).parent.parent
PVALUES_PATH = PROJECT_ROOT / "research" / "coint_survival_pvalues.parquet"
EVENTS_PATH = PROJECT_ROOT / "research" / "coint_survival_events.parquet"

WINDOW_BARS = 7 * BARS_PER_DAY   # 336 bars -- same 7-day window as rolling_coint's default
STRIDE_BARS = BARS_PER_DAY       # 48 bars -- daily stride, same as recent_cointegrated's roll_p_fine

# Confirmed with the user (see module docstring) -- not independently derived.
RAW_CONSECUTIVE_FAIL_DAYS = 3
# Matches pair_analysis.py's hardcoded `roll_p_fine.tail(3).mean()` in
# analyze_top_pairs -- no named constant exists there to import, so this is
# a local literal kept in sync by comment, not by shared reference.
SMOOTHED_LOOKBACK_WINDOWS = 3


# ---------------------------------------------------------------------------
# Step 1 (expensive): raw daily-stride p-value series, append-only
# ---------------------------------------------------------------------------

def _all_valid_pairs(tickers: list[str]) -> list[tuple[str, str]]:
    """Every ticker combination except same-underlying pairs (e.g. a spot/
    futures pair for the same asset) -- same exclusion rule as
    pair_analysis.analyze_top_pairs, via the same _base_symbol function."""
    return [(a, b) for a, b in itertools.combinations(tickers, 2) if _base_symbol(a) != _base_symbol(b)]


def update_pvalue_series(
    end_date: str | None = None,
    pvalues_path: Path = PVALUES_PATH,
) -> pd.DataFrame:
    """The expensive step. Computes daily-stride rolling-window
    Engle-Granger p-values for every valid pair's full available joint
    history, appending only genuinely new (pair, date) rows to
    `pvalues_path`.

    Incremental resume: for a pair with existing rows, the next window to
    compute is found by looking up its last-stored date's exact position in
    the pair's CURRENT joint price index, then resuming one stride past it
    -- not by counting existing rows (which would silently misalign if any
    window were ever skipped for non-finite data). If that date can't be
    found (see module docstring's stated assumption), the pair's entire
    series is recomputed from scratch instead of trusting a possibly-stale
    position. Pairs with no new data since the last run cost one dict
    lookup and a `range()` that's immediately empty -- not a coint() call.

    end_date: passed through to get_price_levels -- None (default) uses all
    available data (today's real "now"), matching analyze_top_pairs' own
    convention. Exists so a specific historical cutoff can be reproduced.
    """
    print(f"[INFO] Loading price data (end_date={end_date or 'latest'})...")
    df = get_price_levels(align=False, end_date=end_date)
    tickers = df.columns.tolist()
    pairs = _all_valid_pairs(tickers)
    print(f"[INFO] {len(tickers)} tickers, {len(pairs)} valid pairs, data through {df.index.max()}")

    if pvalues_path.exists():
        existing = pd.read_parquet(pvalues_path)
    else:
        existing = pd.DataFrame(columns=["ticker_a", "ticker_b", "date", "p_value", "computed_run_id"])

    existing_by_pair = (
        {key: sub for key, sub in existing.groupby(["ticker_a", "ticker_b"])}
        if not existing.empty else {}
    )

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    new_rows: list[dict] = []
    n_skipped_no_new_data = 0
    n_skipped_too_short = 0
    n_full_recompute_fallback = 0
    t_start = time.time()
    progress_step = max(1, len(pairs) // 20)

    for idx, (a, b) in enumerate(pairs):
        pair_clean = df[[a, b]].dropna()
        if len(pair_clean) < WINDOW_BARS:
            n_skipped_too_short += 1
            continue

        pa, pb = pair_clean[a].values, pair_clean[b].values
        dates = pair_clean.index
        n = len(pa)

        start_i = 0
        prior = existing_by_pair.get((a, b))
        if prior is not None and len(prior):
            last_date = prior["date"].max()
            try:
                loc = dates.get_loc(last_date)
                # last_date == dates[i_last + WINDOW_BARS - 1] for the window
                # that produced it -- solve for i_last, then resume one stride later.
                i_last = loc - WINDOW_BARS + 1
                start_i = max(0, i_last + STRIDE_BARS)
            except KeyError:
                start_i = 0
                n_full_recompute_fallback += 1

        if start_i >= n - WINDOW_BARS:
            n_skipped_no_new_data += 1
            continue

        for i in range(start_i, n - WINDOW_BARS, STRIDE_BARS):
            chunk_a = pa[i:i + WINDOW_BARS]
            chunk_b = pb[i:i + WINDOW_BARS]
            if not (np.isfinite(chunk_a).all() and np.isfinite(chunk_b).all()):
                continue
            _, pval, _ = coint(chunk_a, chunk_b)
            new_rows.append({
                "ticker_a": a, "ticker_b": b,
                "date": dates[i + WINDOW_BARS - 1],
                "p_value": float(pval),
                "computed_run_id": run_id,
            })

        if (idx + 1) % progress_step == 0 or (idx + 1) == len(pairs):
            elapsed = time.time() - t_start
            print(f"  [{idx + 1}/{len(pairs)}] {elapsed:.0f}s elapsed, {len(new_rows)} new rows so far")

    elapsed = time.time() - t_start
    print(
        f"[INFO] Done in {elapsed:.0f}s: {len(new_rows)} new p-value rows. "
        f"{n_skipped_no_new_data} pairs had no new data, "
        f"{n_skipped_too_short} pairs had insufficient joint history, "
        f"{n_full_recompute_fallback} pairs fell back to a full recompute "
        f"(last-stored date not found in current price index)."
    )

    if new_rows:
        new_df = pd.DataFrame(new_rows)
        combined = pd.concat([existing, new_df], ignore_index=True) if not existing.empty else new_df
        pvalues_path.parent.mkdir(parents=True, exist_ok=True)
        combined.to_parquet(pvalues_path, index=False)
        print(f"[INFO] Wrote {len(combined)} total rows to {pvalues_path}")
        return combined

    print("[INFO] No new rows -- pvalues file unchanged.")
    return existing


# ---------------------------------------------------------------------------
# Step 2 (cheap): detection events + survival outcomes, full regeneration
# ---------------------------------------------------------------------------

def derive_events(
    pvalues_df: pd.DataFrame | None = None,
    pvalues_path: Path = PVALUES_PATH,
    events_path: Path = EVENTS_PATH,
    raw_consecutive_fail_days: int = RAW_CONSECUTIVE_FAIL_DAYS,
    smoothed_lookback_windows: int = SMOOTHED_LOOKBACK_WINDOWS,
    write: bool = True,
) -> pd.DataFrame:
    """The cheap step -- pure pandas, zero coint() calls. Regenerates the
    full detection-events-and-survival-outcomes table from the raw p-value
    series. Always a full rebuild -- see module docstring."""
    if pvalues_df is None:
        if not pvalues_path.exists():
            raise FileNotFoundError(f"{pvalues_path} does not exist -- run update_pvalue_series() first.")
        pvalues_df = pd.read_parquet(pvalues_path)

    if pvalues_df.empty:
        return pd.DataFrame()

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    events: list[dict] = []

    for (a, b), sub in pvalues_df.groupby(["ticker_a", "ticker_b"]):
        sub = sub.sort_values("date").reset_index(drop=True)
        dates = sub["date"].tolist()
        pvals = sub["p_value"].to_numpy()
        n = len(sub)
        if n == 0:
            continue
        last_data_date = dates[-1]

        # Smoothed/live-gate series -- mean of the trailing smoothed_lookback_windows
        # readings (inclusive of the current one), matching analyze_top_pairs'
        # recent_p_signal = roll_p_fine.tail(3).mean() exactly. Fails closed
        # (not-passing) until enough readings exist.
        smoothed_pass = np.zeros(n, dtype=bool)
        for t in range(n):
            if t + 1 >= smoothed_lookback_windows:
                window_mean = pvals[t - smoothed_lookback_windows + 1: t + 1].mean()
                smoothed_pass[t] = window_mean < RECENT_P_THRESHOLD
        first_evaluable_idx = smoothed_lookback_windows - 1

        raw_pass = pvals < COINT_PVALUE_THRESHOLD

        t = 0
        while t < n:
            if smoothed_pass[t] and (t == 0 or not smoothed_pass[t - 1]):
                detection_idx = t
                detection_date = dates[t]

                # --- smoothed survival: first day the SAME gate flips back False ---
                end_idx = None
                for u in range(t + 1, n):
                    if not smoothed_pass[u]:
                        end_idx = u
                        break
                if end_idx is None:
                    smoothed_still_alive = True
                    survival_days_smoothed = (last_data_date - detection_date).days
                else:
                    smoothed_still_alive = False
                    survival_days_smoothed = (dates[end_idx] - detection_date).days

                # --- was the raw gate already mid-failure-streak at detection? ---
                raw_already_failing = False
                run_len = 0
                for u in range(detection_idx, -1, -1):
                    if not raw_pass[u]:
                        run_len += 1
                        if run_len >= raw_consecutive_fail_days:
                            raw_already_failing = True
                            break
                    else:
                        break

                # --- raw survival: first day starting a run_len-day fail streak, from detection forward ---
                raw_end_idx = None
                run_len = 0
                for u in range(detection_idx, n):
                    if not raw_pass[u]:
                        run_len += 1
                        if run_len >= raw_consecutive_fail_days:
                            raw_end_idx = u - raw_consecutive_fail_days + 1
                            break
                    else:
                        run_len = 0
                if raw_end_idx is None:
                    raw_still_alive = True
                    survival_days_raw = (last_data_date - detection_date).days
                else:
                    raw_still_alive = False
                    survival_days_raw = (dates[raw_end_idx] - detection_date).days
                if raw_already_failing:
                    survival_days_raw = 0  # already dead at the moment of detection, not a short survival

                events.append({
                    "ticker_a": a, "ticker_b": b,
                    "detection_date": detection_date,
                    "survival_days_smoothed": survival_days_smoothed,
                    "smoothed_still_alive": smoothed_still_alive,
                    "survival_days_raw": survival_days_raw,
                    "raw_still_alive": raw_still_alive,
                    "raw_already_failing_at_detection": raw_already_failing,
                    "left_truncated": detection_idx == first_evaluable_idx,
                    "last_data_date": last_data_date,
                    "computed_run_id": run_id,
                })

                t = end_idx if end_idx is not None else n
            else:
                t += 1

    events_df = pd.DataFrame(events)
    if write and not events_df.empty:
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_df.to_parquet(events_path, index=False)
        print(f"[INFO] Wrote {len(events_df)} detection events to {events_path}")
    return events_df


if __name__ == "__main__":
    _end_date = os.environ.get("SURVIVAL_END_DATE")  # None -> latest available data
    pvalues_df = update_pvalue_series(end_date=_end_date)
    derive_events(pvalues_df=pvalues_df)
