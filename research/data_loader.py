import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import pandas as pd
from pathlib import Path

from adapters.hyperliquid_futures import sync_normalized_store as _sync_hl_futures

NORMALIZED_DIR = Path(__file__).parent.parent / "user_data" / "normalized"


def _parse_timeframe_minutes(timeframe: str) -> int:
    """Parse a "30m"/"1h"-style timeframe string into minutes.

    Only minute ("m") and hour ("h") suffixes are supported, matching the
    only units used anywhere in this pipeline (BAR_LENGTH is minutes; bar
    filenames use "1m"/"30m").
    """
    if timeframe.endswith("m"):
        return int(timeframe[:-1])
    if timeframe.endswith("h"):
        return int(timeframe[:-1]) * 60
    raise ValueError(f"Unsupported timeframe format: {timeframe!r} (expected e.g. '30m' or '1h')")


def _snap_to_grid(series: pd.Series, bar_minutes: int) -> pd.Series:
    """Snap one instrument's series onto the common target-frequency grid.

    Rule -- bar-open-time floor: each observation's timestamp is floored to
    the nearest bar_minutes-aligned grid point. E.g. on a 30-minute grid, a
    bar timestamped HH:05 is treated as the HH:00 bar. An hourly source's
    bars are already exact multiples of 30 and land unchanged; the
    in-between :30 grid points for that instrument stay genuinely missing
    (not fabricated -- they simply don't exist in the source, and are left
    for the caller's gap policy, e.g. _align_drop_any_gap, to handle).

    This corrects PHASE (two sources off-grid from each other, e.g. :00/:30
    vs :05/:35) and FREQUENCY (a coarser source lands on whichever grid
    points it naturally floors to) using only real, already-observed
    prices -- no value is invented or interpolated here.

    Collision rule: if flooring causes two or more source bars to land on
    the same grid timestamp (only possible when the source is FINER than
    the target grid, e.g. 15-minute bars snapped to a 30-minute grid), the
    LAST bar within that interval (by original timestamp) is kept and the
    earlier one(s) are dropped -- the latest observation in an interval is
    the most current closing price for that slot. Requires `series` to
    already be sorted ascending by its original timestamp (the caller
    guarantees this via `sort_values("date")` before construction).

    No-op when every timestamp already lands exactly on the grid and no two
    observations share a grid slot -- true for the Hyperliquid bars, which are
    built on a uniform, phase-aligned grid.
    """
    grid_index = series.index.floor(f"{bar_minutes}min")
    snapped = pd.Series(series.values, index=grid_index, name=series.name)
    snapped = snapped[~snapped.index.duplicated(keep="last")]
    return snapped.sort_index()


def _align_drop_any_gap(df: pd.DataFrame) -> pd.DataFrame:
    """Drop any row (timestamp) where ANY loaded instrument is missing a value.

    Runs on the already grid-snapped frame (see _snap_to_grid), which is
    built as an outer join across all currently-loaded instruments
    (whichever sources/adapters contributed columns). Two sources with
    different observation calendars -- different start times, venue-specific
    gaps -- show up as NaN holes at timestamps where not every instrument
    has a bar. Forward-filling those holes is prohibited (a known source of
    spurious cointegration results): instead the whole row is dropped, for
    every instrument, so every remaining timestamp is backed by a real
    observation for everything currently loaded.

    This runs unconditionally whenever the caller asks for it (see the
    `align` parameter on get_price_levels), because two 24/7 sources can still
    drift out of alignment with each other. On the Hyperliquid bars it is NOT a
    no-op: archive gaps are NaN closes, and staggered listings leave NaN before
    each coin's first trade, so align=True drops every such row for all coins.

    Trade-off, stated plainly: this is frame-wide, not per-pair. One
    short-lived or gappy instrument shrinks the retained history for every
    pair in the frame, including pairs that don't involve it. That is the
    deliberate, conservative default -- correctness over data retention --
    for callers that want one rectangular frame across the whole universe.
    Callers that need genuine per-pair joint coverage (e.g. pair_analysis.py)
    should call get_price_levels(align=False) instead and compute their own
    per-pair dropna(); see that parameter's docstring for why.
    """
    return df.dropna(how="any")


def get_price_levels(
    start_date: str = None,
    end_date: str = None,
    timeframe: str = "30m",
    align: bool = True,
) -> pd.DataFrame:
    """Returns DataFrame of log prices: datetime index, ticker columns (e.g. BTC, SOL), values are ln(close).

    Source-blind: syncs the normalized per-instrument store (user_data/normalized/)
    from every active data-source adapter, then builds the frame from it. All
    source-specific knowledge (paths, filenames, ticker encoding) lives in each
    adapter, not here.

    Every instrument's timestamps are snapped onto a common `timeframe` grid
    first (see _snap_to_grid), so phase-misaligned or differently-frequenced
    sources still line up correctly instead of silently failing to join.

    align : bool, default True
        If True (default), also apply the frame-wide drop-any-gap policy
        (see _align_drop_any_gap): any timestamp missing a value for ANY
        currently-loaded instrument is dropped for ALL instruments. This is
        the safe default for callers that want one fully rectangular,
        gap-free frame across the whole loaded universe.
        If False, skip that step and return the raw (per-instrument-gappy)
        grid-snapped frame. Callers that need genuine PER-PAIR joint
        coverage (e.g. pair_analysis.py's per-pair min-overlap gate) must
        use align=False: with align=True, every pair's own dropna() length
        is identical to the whole frame's length (already gap-free), so it
        can no longer distinguish a thin pair from a well-covered one.
    """
    # One source since 2026-10-14 (HL-BUILD2): Hyperliquid perps, bars built
    # from the trade archive. OKX and the LST adapter are in attic/. Archive
    # gaps are NaN closes inside a coin's life; align=False keeps them.
    tickers = _sync_hl_futures(NORMALIZED_DIR, timeframe=timeframe)
    bar_minutes = _parse_timeframe_minutes(timeframe)

    series = {}
    for ticker in tickers:
        df_raw = pd.read_feather(NORMALIZED_DIR / f"{ticker}.feather")
        if df_raw.empty:
            continue
        df_raw = df_raw.sort_values("date")
        idx = pd.to_datetime(df_raw["date"], utc=True).dt.tz_localize(None)
        raw_series = pd.Series(np.log(df_raw["close"].values), index=idx, name=ticker)
        series[ticker] = _snap_to_grid(raw_series, bar_minutes)

    df = pd.DataFrame(series).sort_index()
    if align:
        df = _align_drop_any_gap(df)

    if start_date is not None:
        df = df[df.index >= start_date]
    if end_date is not None:
        df = df[df.index <= end_date]

    return df


if __name__ == "__main__":
    df = get_price_levels()
    print(df.shape)
    print(df.head())
