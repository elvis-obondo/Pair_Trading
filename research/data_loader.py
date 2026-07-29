import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import pandas as pd
from pathlib import Path

from adapters.okx_futures import sync_normalized_store

NORMALIZED_DIR = Path(__file__).parent.parent / "user_data" / "normalized"


def get_price_levels(start_date: str = None, end_date: str = None, timeframe: str = "30m") -> pd.DataFrame:
    """Returns DataFrame of log prices: datetime index, ticker columns (e.g. BTC, SOL), values are ln(close).

    Source-blind: syncs the normalized per-instrument store (user_data/normalized/)
    from the active data-source adapter, then builds the frame from it. All
    source-specific knowledge (paths, filenames, ticker encoding) lives in the
    adapter, not here.
    """
    tickers = sync_normalized_store(NORMALIZED_DIR, timeframe=timeframe)

    series = {}
    for ticker in tickers:
        df_raw = pd.read_feather(NORMALIZED_DIR / f"{ticker}.feather")
        if df_raw.empty:
            continue
        df_raw = df_raw.sort_values("date")
        idx = pd.to_datetime(df_raw["date"], utc=True).dt.tz_localize(None)
        series[ticker] = pd.Series(np.log(df_raw["close"].values), index=idx, name=ticker)

    df = pd.DataFrame(series).sort_index()

    if start_date is not None:
        df = df[df.index >= start_date]
    if end_date is not None:
        df = df[df.index <= end_date]

    return df


if __name__ == "__main__":
    df = get_price_levels()
    print(df.shape)
    print(df.head())
