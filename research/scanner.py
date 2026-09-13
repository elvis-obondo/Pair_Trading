"""Screen the whole universe for dislocated spreads, ranked by reversion speed.

WHAT THIS IS

The strategy is no longer "watch one cointegrated pair". It is: look at all
22,366 pairs every bar, take the ones that have stretched 3 rolling sigma from
their own mean, and rank them by how fast that spread has been reverting.

WHY IT IS CHEAP ENOUGH TO RUN LIVE

Measured on this laptop, single-threaded: 0.378 ms per pair, 8.5 s for the full
universe. The whole cycle including a data refresh is ~100 s, on a 30-minute
clock -- a 5% duty cycle.

That works because generate_entry_signal short-circuits in the right order:
the rolling z-score is computed first and costs almost nothing, and the OU fit
runs ONLY on what clears the threshold. Around 84 pairs clear 3 sigma at any
instant, so the model is fitted 84 times, not 22,366. Reverse that order and the
scan takes an hour.

WHY IT CALLS generate_entry_signal RATHER THAN REIMPLEMENTING IT

The single-pair strategy calls the same function. If the scanner had its own
copy of the geometry the two could disagree about what an entry is, silently,
and the disagreement would only show up as a discrepancy between backtest and
live months later. One definition, both callers.

RANKING

By theta descending, fastest reverter first. NaN-theta candidates sort LAST but
are kept -- see generate_entry_signal's Step 3 for why dropping them would throw
away most of the pool. Ranking is settled; filtering on theta is not the same
rule and is not applied.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

from signal_generator import generate_entry_signal
from rolling_spread import min_bars_required
from universe_panel import tradeable_pairs, usable_tickers

SIGNAL_FIELDS = [
    "entry_spread", "mu_at_entry", "sigma_at_entry", "z_at_entry",
    "beta_at_entry", "alpha_at_entry", "theta_at_entry", "take_profit_level",
    "r2_at_entry",
]


def scan(panel: pd.DataFrame,
         pairs: list[tuple[str, str]] | None = None,
         min_deviation_sigma: float = 3.0,
         take_profit_pct: float = 1.0,
         bar_hours: float = 0.5) -> pd.DataFrame:
    """Every pair that is dislocated at the panel's LAST bar, best theta first.

    Parameters
    ----------
    panel : DataFrame
        Log prices, ticker columns. Must hold at least
        min_bars_required(bar_hours) rows -- 671 at 30m, two 7-day windows. Pass
        the trailing slice; nothing here reads further back.
    pairs : list of (ticker_a, ticker_b), optional
        Defaults to every tradeable pair among the panel's usable tickers.
    min_deviation_sigma, take_profit_pct, bar_hours
        Passed straight through to generate_entry_signal.

    Returns
    -------
    DataFrame with ticker_a, ticker_b and every entry-signal field, sorted by
    theta_at_entry descending with NaN theta last. Empty (with the right
    columns) when nothing is dislocated, so callers can treat it uniformly.
    """
    need = min_bars_required(bar_hours)
    cols = ["ticker_a", "ticker_b"] + SIGNAL_FIELDS
    if len(panel) < need:
        return pd.DataFrame(columns=cols)

    tickers = usable_tickers(panel, bar_hours)
    if pairs is None:
        pairs = tradeable_pairs(tickers)

    # Pull each column out once. Indexing a DataFrame per pair would dominate
    # the runtime -- 22,366 pairs means 44,732 column lookups per scan.
    usable = set(tickers)
    arrays = {t: panel[t].to_numpy(dtype=float) for t in usable}

    rows = []
    for a, b in pairs:
        if a not in usable or b not in usable:
            continue
        sig = generate_entry_signal(
            arrays[a], arrays[b],
            min_deviation_sigma=min_deviation_sigma,
            take_profit_pct=take_profit_pct,
            bar_hours=bar_hours,
        )
        if sig is None:
            continue
        rows.append({"ticker_a": a, "ticker_b": b, **sig})

    if not rows:
        return pd.DataFrame(columns=cols)

    out = pd.DataFrame(rows)
    # na_position="last": an unranked candidate is still tradeable, it just does
    # not get to jump the queue.
    return (out.sort_values("theta_at_entry", ascending=False, na_position="last")
               .reset_index(drop=True))


def scan_summary(candidates: pd.DataFrame) -> str:
    """One log line describing a scan result."""
    if not len(candidates):
        return "0 candidates"
    ranked = int(candidates["theta_at_entry"].notna().sum())
    z = candidates["z_at_entry"].abs()
    return (f"{len(candidates)} candidates | {ranked} ranked "
            f"({ranked / len(candidates) * 100:.0f}% fit a theta) | "
            f"|z| max {z.max():.2f} median {z.median():.2f}")
