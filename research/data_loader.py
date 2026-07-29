import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import pandas as pd
from pathlib import Path

from adapters.okx_futures import sync_normalized_store as _sync_okx_futures
from adapters.lst_tokens import sync_normalized_store as _sync_lst_tokens

NORMALIZED_DIR = Path(__file__).parent.parent / "user_data" / "normalized"


def _align_drop_any_gap(df: pd.DataFrame) -> pd.DataFrame:
    """Drop any row (timestamp) where ANY loaded instrument is missing a value.

    The wide frame is built as an outer join across all currently-loaded
    instruments (whichever sources/adapters contributed columns), so two
    sources with different observation calendars -- different start times,
    venue-specific gaps -- show up as NaN holes at timestamps where not every
    instrument has a bar. Forward-filling those holes is prohibited (a known
    source of spurious cointegration results): instead the whole row is
    dropped, for every instrument, so every remaining timestamp is backed by
    a real observation for everything currently loaded.

    This runs unconditionally for every call, not only when a non-OKX source
    is present, because two 24/7 sources can still drift out of alignment
    with each other. It is a no-op on already-aligned single-source data
    (verified: current OKX-futures-only data has zero NaNs and a uniform
    30-minute grid).

    Trade-off, stated plainly: this is frame-wide, not per-pair. One
    short-lived or gappy instrument shrinks the retained history for every
    pair in the frame, including pairs that don't involve it. That is the
    deliberate, conservative choice here -- correctness over data retention.
    pair_analysis.py's existing per-pair `dropna()` + `min_bars` check is the
    second line of defense: it catches the case where the aligned overlap is
    too short to trust, and skips those pairs rather than trading on it.
    """
    return df.dropna(how="any")


def get_price_levels(start_date: str = None, end_date: str = None, timeframe: str = "30m") -> pd.DataFrame:
    """Returns DataFrame of log prices: datetime index, ticker columns (e.g. BTC, SOL), values are ln(close).

    Source-blind: syncs the normalized per-instrument store (user_data/normalized/)
    from every active data-source adapter, then builds the frame from it. All
    source-specific knowledge (paths, filenames, ticker encoding) lives in each
    adapter, not here. The resulting frame is gap-aligned (see
    _align_drop_any_gap) before being returned.
    """
    okx_tickers = _sync_okx_futures(NORMALIZED_DIR, timeframe=timeframe)
    lst_tickers = _sync_lst_tokens(NORMALIZED_DIR, timeframe=timeframe)
    tickers = okx_tickers + lst_tickers

    series = {}
    for ticker in tickers:
        df_raw = pd.read_feather(NORMALIZED_DIR / f"{ticker}.feather")
        if df_raw.empty:
            continue
        df_raw = df_raw.sort_values("date")
        idx = pd.to_datetime(df_raw["date"], utc=True).dt.tz_localize(None)
        series[ticker] = pd.Series(np.log(df_raw["close"].values), index=idx, name=ticker)

    df = pd.DataFrame(series).sort_index()
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
