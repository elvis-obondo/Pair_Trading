"""The universe: 212 instruments on one clock, and the pairs they form.

WHY align=False IS NOT OPTIONAL HERE

`get_price_levels(align=True)` drops any timestamp missing a value for ANY
loaded instrument. On a two-ticker frame that is harmless. On the full 212 it is
catastrophic: the newest listing sets the intersection for everything, and one
71-day-old ticker (VVV, first bar 2026-07-03) collapses the panel from 731 days
to 71 -- 90% of the history gone, including for pairs that do not involve it.

So the panel is loaded unaligned and every pair does its own dropna(), exactly
the way exit_sweep.run() and pair_analysis.analyze_top_pairs already do it.

WHY THE PANEL IS MEMOIZED

get_price_levels() re-reads all 212 raw feathers and rewrites 212 normalized
feathers plus a manifest on EVERY call (adapters/okx_futures.py). A 30-minute
scan loop must not pay that twice a cycle. `load_panel` caches by argument and
`refresh()` drops the cache when new bars have landed.

Measured on this universe: the unaligned panel is 35,091 x 212 and 60MB, and
loads in ~2s. Memory is not the constraint people expected -- the constraint was
always the per-pair RESULT rows in the offline dataset jobs, not the prices.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import itertools

import numpy as np
import pandas as pd

from data_loader import get_price_levels
from pair_analysis import _base_symbol
from rolling_spread import min_bars_required

_PANEL = None


def load_panel(tail_bars: int | None = None, force: bool = False) -> pd.DataFrame:
    """Log-price panel, one column per ticker, unaligned.

    tail_bars trims to the most recent N rows AFTER loading -- the live scanner
    only ever needs min_bars_required(bar_hours) of history, and trimming keeps
    the per-pair rolling work proportional to what is actually read.

    force=True bypasses the cache; use it when new bars have been downloaded.
    """
    global _PANEL
    if _PANEL is None or force:
        _PANEL = get_price_levels(align=False)
    return _PANEL if tail_bars is None else _PANEL.tail(tail_bars)


def drop_forming_bars(panel: pd.DataFrame, lookback: int = 20,
                      min_coverage: float = 0.95) -> pd.DataFrame:
    """Drop trailing bars that have not closed yet.

    THIS IS NOT COSMETIC. A 30-minute bar stamped 14:00 closes at 14:30. Download
    at 14:27 and the exchange returns that bar for whichever instruments have
    ticked into it so far -- 75 of 212, measured -- and omits it for the rest.
    Two things then go wrong at once:

      1. `usable_tickers` requires a complete 671-bar tail, so the 137 tickers
         without the partial bar are dropped. The universe fell from 22,366
         pairs to 2,775 that way, silently, and the scan still reported success.
      2. Worse, the 75 that survived were screened on a CLOSE PRICE THAT IS NOT
         THE CLOSE. Every rolling statistic and every z-score for those pairs was
         computed off a few minutes of a half-hour bar.

    The first symptom is loud once you look at the pair count. The second is not
    visible at all.

    A row counts as closed when its coverage is within min_coverage of the recent
    norm. Comparing against neighbours rather than against the column count is
    deliberate: instruments legitimately come and go from the universe, and a
    fixed threshold would start trimming real bars the moment one delisted.
    """
    if len(panel) < 2:
        return panel
    counts = panel.notna().sum(axis=1)
    window = counts.iloc[-(lookback + 1):-1]
    if not len(window):
        return panel
    norm = float(window.max())
    if norm <= 0:
        return panel
    keep = len(panel)
    while keep > 1 and counts.iloc[keep - 1] < min_coverage * norm:
        keep -= 1
    return panel.iloc[:keep]


def refresh() -> pd.DataFrame:
    """Drop the cache and reload. Call after a data download, not per scan."""
    return load_panel(force=True)


def tradeable_pairs(tickers) -> list[tuple[str, str]]:
    """Every unordered pair of distinct underlyings.

    The _base_symbol check excludes a spot ticker paired against its own
    futures ticker ("ARB_SPOT"/"ARB") -- trading an asset against itself is not
    a spread. It selects nothing today (the spot adapter is off, so every
    ticker is a futures ticker) and is dormant insurance for when it is on.

    This idiom was copy-pasted in four places -- pair_analysis.py:336-339,
    exit_sweep.py:191-192, reversion_dataset.py:249-250, coint_survival.py:146.
    This is the one definition.

    212 tickers -> 22,366 pairs.
    """
    return [(a, b) for a, b in itertools.combinations(tickers, 2)
            if _base_symbol(a) != _base_symbol(b)]


def usable_tickers(panel: pd.DataFrame, bar_hours: float = 0.5) -> list[str]:
    """Tickers with a complete, finite price history across the panel given.

    A pair is only scannable if BOTH legs are complete over the window, because
    rolling_spread_stats rejects a whole pair when any single price is
    non-finite -- it returns all-NaN, which is indistinguishable from "not
    dislocated". Screening the tickers up front turns a silent skip into a
    countable one.
    """
    need = min_bars_required(bar_hours)
    if len(panel) < need:
        return []
    return [c for c in panel.columns
            if panel[c].notna().sum() == len(panel)
            and np.isfinite(panel[c].to_numpy(dtype=float)).all()]


def price_precision(min_price: float) -> tuple[int, float]:
    """Decimal places and tick size for an instrument, from its price magnitude.

    WHY THIS EXISTS

    nautilus/run_backtest.py's make_instrument hardcodes price_precision=4 for
    every ticker. Across this universe that is not a rounding nuisance, it is
    silent data destruction: BONK, PEPE, SHIB, FLOKI and NEIRO all trade below
    0.0001, so their ENTIRE price series rounds to 0.0000. Six more (HMSTR, NOT,
    BOME, MEME, ONE, TURBO) are left with one or two significant digits. This is
    the root cause of the "FLOKI pairs showed exactly 0 trades" and the
    "rounded to zero due to size increment" bugs already logged in docs/HANDOFF.md.

    The rule: enough decimals to give the SMALLEST observed price five
    significant figures, clamped to a sane range. BNB at ~1367 gets 2; SHIB at
    4e-06 gets 10.
    """
    if not np.isfinite(min_price) or min_price <= 0:
        return 8, 1e-8
    exponent = int(np.floor(np.log10(min_price)))
    precision = int(np.clip(5 - 1 - exponent, 2, 12))
    return precision, float(10.0 ** -precision)


def panel_precisions(panel: pd.DataFrame) -> dict[str, tuple[int, float]]:
    """price_precision for every column. Panel holds LOG prices, so exponentiate."""
    out = {}
    for c in panel.columns:
        v = panel[c].to_numpy(dtype=float)
        v = v[np.isfinite(v)]
        out[c] = price_precision(float(np.exp(v.min())) if len(v) else np.nan)
    return out
