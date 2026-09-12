"""Did the spread actually revert? A price-only dataset, not conditioned on detection.

WHY THIS EXISTS -- the circularity it is built to escape:

The precursor dataset (coint_precursors.py) has one row per DETECTION EVENT and
a label derived from rolling Engle-Granger survival. Both halves of that are
the detector's own output, which makes it impossible to use for the thing we
actually want:

  1. Sample selection. A row exists only where the detector fired. If a pair
     was cleanly tradeable for a week before the detector noticed, those days
     are simply absent from the data -- so no model trained on it can ever
     learn to fire earlier, because it has never been shown an example of a
     good day the detector missed.

  2. Circular target. "survival_days_raw" is defined by the same rolling
     p-value the detector thresholds. A model that predicts it perfectly has
     learned to imitate the current system, not to improve on it, and a model
     that DISAGREES with the detector is automatically scored wrong even when
     the spread went on to revert and pay.

This module inverts both. Rows are (pair, day) over the whole universe
regardless of what the detector thought, and the label is measured from prices
alone -- no cointegration test, no p-value, nothing from the detection path
appears in the definition of a good outcome.

THE LABEL, precisely:

  At each day T, using ONLY bars at or before T:
    - fit the hedge ratio beta/alpha on the trailing ENTRY_WINDOW_DAYS
    - build the spread, take its trailing mean (mu) and standard deviation
    - z = (spread_T - mu) / sigma

  A row is a candidate trade only if |z| >= MIN_ENTRY_SIGMA. Rows below that
  are recorded with outcome "no_dislocation" and a null label: there was
  nothing to trade, and scoring them as failures would drown the real signal
  in rows where no position would ever have been opened.

  For candidates, beta/alpha/mu are FROZEN at T (matching pairs_strategy.py's
  live convention -- re-estimating mid-trade shifts the spread baseline under
  the position) and the next HORIZON_HOURS of bars are replayed forward:
    take_profit -- spread retraced TAKE_PROFIT_FRAC of the way to mu
    adverse     -- spread first moved ADVERSE_SIGMA further from mu
    timeout     -- neither, within the horizon

  label_tp = 1 for take_profit, 0 for adverse or timeout. The thresholds
  deliberately mirror signal_generator.py's live exits (80% capture, ~2.3
  sigma abort, 24h cap) so a positive label means "a trade under the rules you
  actually run would have won", not an abstract statistical event.

  reversion_frac is also stored -- the fraction of the initial gap that had
  closed by horizon end -- so the same rows support a continuous target
  without recomputing.

LOOK-AHEAD: the entry side uses df.loc[:T] exclusively; the outcome side uses
bars strictly after T. The frozen beta is the only thing that crosses the
boundary, and it crosses backward-to-forward, which is the correct direction.

COMPARISON COLUMNS: the detector's own state at T (raw p-value, smoothed-gate
pass) is joined on where available, not to define the label but so "model vs
detector" can be scored on identical rows. This is the column that makes the
earliness question answerable: for a pair, the first day the model would fire
versus the first day the detector did, with both judged by what prices did.
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

from data_loader import get_price_levels
from pair_analysis import _base_symbol, BARS_PER_DAY
# Re-exported: exit_sweep.py imports rolling_beta_alpha from this module, and the
# live entry path needs the same fit. One definition, in rolling_spread.py.
from rolling_spread import rolling_beta_alpha  # noqa: F401

PROJECT_ROOT = Path(__file__).parent.parent
PVALUES_PATH = PROJECT_ROOT / "research" / "coint_survival_pvalues.parquet"
OUTPUT_PATH = PROJECT_ROOT / "research" / "reversion_dataset.parquet"

# Entry-side window. 7 days matches rolling_coint's default and the live
# entry gate's lookback, so the hedge ratio and z-score a row sees are the
# same vintage the live system would have had at that moment.
ENTRY_WINDOW_DAYS = 7
ENTRY_WINDOW_BARS = ENTRY_WINDOW_DAYS * BARS_PER_DAY

# Trade rules, mirroring signal_generator.py / pairs_strategy.py.
MIN_ENTRY_SIGMA = 1.0      # signal_generator's min_deviation_sigma
TAKE_PROFIT_FRAC = 0.80    # signal_generator's take_profit_pct
# generate_exit_signal's stop_sigma default. Critically this is a distance
# travelled FROM THE ENTRY SPREAD, not an absolute level measured from mu:
#   adverse if current_spread >= entry_spread + stop_sigma * sigma_stationary
# An earlier version of this file placed the stop at a fixed level (mu +
# 2.3 sigma) instead, which made the stop closer the further from mu you
# entered, and manufactured a huge spurious relationship between entry z and
# win rate (38.9% at z~1.1 decaying to 1.7% above z=2.3 -- almost entirely an
# artifact of entries starting beyond their own stop). With the live
# definition the stop distance is constant regardless of entry z.
ADVERSE_SIGMA = 2.5
HORIZON_HOURS = 24.0       # MAX_TIME_STOP_HOURS
HORIZON_BARS = int(HORIZON_HOURS * 60 / 30)

MIN_JOINT_BARS = ENTRY_WINDOW_BARS + HORIZON_BARS + BARS_PER_DAY


def _forward_outcome(spread_fwd: np.ndarray, s0: float, mu: float, sigma: float):
    """Replay the horizon bar by bar under frozen beta/alpha/mu.

    Returns (outcome, bars_to_exit, reversion_frac_at_horizon).

    Both barriers are checked on every bar in order, and whichever is touched
    first wins -- checking take-profit for the whole horizon before checking
    the adverse barrier would let a trade that blew through the stop on bar 2
    be recorded as a winner because it happened to come back on bar 40.
    """
    gap = s0 - mu
    if gap == 0 or not np.isfinite(gap):
        return "degenerate", np.nan, np.nan
    tp_level = s0 - TAKE_PROFIT_FRAC * gap
    # Distance from ENTRY, matching generate_exit_signal, so the stop sits the
    # same distance away regardless of how far from mu the entry was.
    stop_distance = ADVERSE_SIGMA * sigma
    adverse_level = s0 + np.sign(gap) * stop_distance

    for i, s in enumerate(spread_fwd):
        if not np.isfinite(s):
            continue
        # Adverse is checked BEFORE take-profit within a bar, matching
        # generate_exit_signal's gate order (time -> adverse -> take profit).
        # Order matters on a bar that crosses both.
        if gap > 0:
            if s >= adverse_level:
                return "adverse", i + 1, float((s0 - s) / gap)
            if s <= tp_level:
                return "take_profit", i + 1, float((s0 - s) / gap)
        else:
            if s <= adverse_level:
                return "adverse", i + 1, float((s0 - s) / gap)
            if s >= tp_level:
                return "take_profit", i + 1, float((s0 - s) / gap)

    finite = spread_fwd[np.isfinite(spread_fwd)]
    last = finite[-1] if len(finite) else np.nan
    frac = float((s0 - last) / gap) if np.isfinite(last) else np.nan
    return "timeout", np.nan, frac


def build_pair_rows(a: str, b: str, pair_df: pd.DataFrame) -> list[dict]:
    """All daily candidate rows for one pair.

    Sampled once per day at the last bar of each calendar day, matching the
    daily-stride convention the p-value table already uses, so detector state
    joins onto these rows without resampling either side.
    """
    pa = pair_df[a].to_numpy()
    pb = pair_df[b].to_numpy()
    idx = pair_df.index
    n = len(pa)
    if n < MIN_JOINT_BARS:
        return []

    beta, alpha = rolling_beta_alpha(pa, pb, ENTRY_WINDOW_BARS)
    spread_roll = pa - beta * pb - alpha
    s_roll = pd.Series(spread_roll)
    mu_roll = s_roll.rolling(ENTRY_WINDOW_BARS).mean().to_numpy()
    sigma_roll = s_roll.rolling(ENTRY_WINDOW_BARS).std().to_numpy()

    # One entry candidate per calendar day: the last bar of that day.
    day_end_pos = (
        pd.Series(np.arange(n), index=idx)
        .groupby(idx.normalize()).last()
    )

    rows = []
    for day, t in day_end_pos.items():
        t = int(t)
        if t < ENTRY_WINDOW_BARS or t + HORIZON_BARS >= n:
            continue
        bt, at_, mu, sg = beta[t], alpha[t], mu_roll[t], sigma_roll[t]
        if not (np.isfinite(bt) and np.isfinite(mu) and np.isfinite(sg)) or sg <= 0:
            continue
        s0 = pa[t] - bt * pb[t] - at_
        z = (s0 - mu) / sg

        row = {
            "ticker_a": a, "ticker_b": b, "date": pd.Timestamp(day),
            "beta": float(bt), "mu": float(mu), "sigma": float(sg),
            "spread": float(s0), "z": float(z),
        }
        if abs(z) < MIN_ENTRY_SIGMA:
            row.update({"outcome": "no_dislocation", "label_tp": np.nan,
                        "bars_to_exit": np.nan, "reversion_frac": np.nan})
            rows.append(row)
            continue

        # Frozen beta/alpha forward -- the position's spread definition does
        # not move once the trade is on.
        fwd = pa[t + 1: t + 1 + HORIZON_BARS] - bt * pb[t + 1: t + 1 + HORIZON_BARS] - at_
        outcome, bars, frac = _forward_outcome(fwd, s0, mu, sg)
        row.update({"outcome": outcome,
                    "label_tp": 1.0 if outcome == "take_profit" else (
                        np.nan if outcome == "degenerate" else 0.0),
                    "bars_to_exit": bars, "reversion_frac": frac})
        rows.append(row)
    return rows


def attach_detector_state(df: pd.DataFrame, pvalues_path: Path = PVALUES_PATH) -> pd.DataFrame:
    """Join the detector's own reading at T onto each row.

    Never used to build the label -- only so the same rows can score
    "what the detector said" against "what prices did", which is the whole
    point of the comparison.
    """
    if not pvalues_path.exists():
        print(f"[WARN] {pvalues_path} missing -- detector columns skipped")
        return df
    pv = pd.read_parquet(pvalues_path)
    pv["date"] = pd.to_datetime(pv["date"]).dt.normalize()
    pv = pv.sort_values(["ticker_a", "ticker_b", "date"])
    from pair_analysis import RECENT_P_THRESHOLD
    from coint_survival import SMOOTHED_LOOKBACK_WINDOWS
    pv["smoothed_p"] = (
        pv.groupby(["ticker_a", "ticker_b"])["p_value"]
        .transform(lambda s: s.rolling(SMOOTHED_LOOKBACK_WINDOWS,
                                       min_periods=SMOOTHED_LOOKBACK_WINDOWS).mean())
    )
    pv["detector_pass"] = pv["smoothed_p"] < RECENT_P_THRESHOLD
    out = df.merge(
        pv[["ticker_a", "ticker_b", "date", "p_value", "smoothed_p", "detector_pass"]]
        .rename(columns={"p_value": "detector_raw_p"}),
        on=["ticker_a", "ticker_b", "date"], how="left",
    )
    out["detector_pass"] = out["detector_pass"].fillna(False)
    return out


def run(max_pairs: int | None = None, output_path: Path | None = OUTPUT_PATH,
        seed: int = 42) -> pd.DataFrame:
    print("[INFO] Loading price universe...")
    df = get_price_levels(align=False)
    tickers = df.columns.tolist()
    pairs = [(a, b) for a, b in itertools.combinations(tickers, 2)
             if _base_symbol(a) != _base_symbol(b)]
    if max_pairs is not None and max_pairs < len(pairs):
        rng = np.random.default_rng(seed)
        sel = rng.choice(len(pairs), size=max_pairs, replace=False)
        pairs = [pairs[i] for i in sorted(sel)]
    print(f"[INFO] {len(tickers)} tickers, {len(pairs)} pairs, data through {df.index.max()}")

    all_rows = []
    t0 = time.time()
    step = max(1, len(pairs) // 20)
    n_short = 0
    for i, (a, b) in enumerate(pairs):
        pair_df = df[[a, b]].dropna()
        if len(pair_df) < MIN_JOINT_BARS:
            n_short += 1
            continue
        all_rows.extend(build_pair_rows(a, b, pair_df))
        if (i + 1) % step == 0 or (i + 1) == len(pairs):
            el = time.time() - t0
            print(f"  [{i+1}/{len(pairs)}] {el:.0f}s, {len(all_rows)} rows, "
                  f"ETA {(len(pairs)-i-1)/max((i+1)/el, 1e-9)/60:.1f} min")

    out = pd.DataFrame(all_rows)
    print(f"[INFO] {len(out)} rows from {len(pairs)-n_short} pairs "
          f"({n_short} skipped for short joint history)")
    if len(out):
        out = attach_detector_state(out)
        if output_path is not None:
            out.to_parquet(output_path, index=False)
            print(f"[INFO] Wrote {output_path}")
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-pairs", type=int, default=None)
    ap.add_argument("--out", default=str(OUTPUT_PATH))
    args = ap.parse_args()
    run(max_pairs=args.max_pairs, output_path=Path(args.out))
