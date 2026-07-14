import numpy as np
import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "user_data" / "data" / "okx" / "futures"


def get_price_levels(start_date: str = None, end_date: str = None, timeframe: str = "30m") -> pd.DataFrame:
    """Returns DataFrame of log prices: datetime index, ticker columns (e.g. BTC, SOL), values are ln(close).

    Reads all futures feather files for the given timeframe from user_data/data/okx/futures/.
    Futures files are named BTC_USDT_USDT-30m-futures.feather (BTC/USDT:USDT encoding).
    """
    files = sorted(DATA_DIR.glob(f"*_USDT_USDT-{timeframe}-futures.feather"))
    if not files:
        raise FileNotFoundError(
            f"No futures {timeframe} data files found in {DATA_DIR}. "
            f"Download data first with: freqtrade download-data --trading-mode futures --timeframes {timeframe}"
        )

    series = {}
    for path in files:
        ticker = path.name.split("_")[0]
        df_raw = pd.read_feather(path)
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
