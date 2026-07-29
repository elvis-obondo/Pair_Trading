"""
LST-token adapter — second data source feeding the shared normalized store.

Pulls each LST (liquid-staking-token) as 24/7 MARKET PRICE IN USDT (an OHLCV
`close`, exactly like any other token) — NOT as an exchange rate to the
underlying asset (e.g. NOT "stETH per ETH"). A rate-to-underlying series is a
non-OHLCV feed and is explicitly out of scope for this adapter; that belongs
to a separate, later source. Because this adapter only ever hands
get_price_levels() a market-price `close`, no change to the ln(close) model
is needed anywhere downstream.

FIXTURE FORMAT (what the operator must supply)
------------------------------------------------
This environment has no live LST price feed configured, so this adapter
reads from a local, operator-populated directory instead of calling an
exchange/API directly:

    user_data/data/lst/{TICKER}.csv

One file per LST token. TICKER is the canonical symbol it will appear under
in the normalized store and in pair_analysis (e.g. WSTETH, RETH, MSOL,
JITOSOL) — pick something that will not collide with an existing
OKX-futures ticker for a different underlying asset.

Required columns:
    date   -- timestamp, any pandas-parseable format; parsed with
              pd.to_datetime(..., utc=True). Must be the 24/7 USDT
              market-price bar's timestamp, at the SAME bar frequency as
              the rest of the pipeline (30-minute bars by default) and
              phase-aligned to the same :00/:30 grid as the OKX data --
              this adapter does not resample or snap timestamps, so bars
              on an offset grid will simply fail to align with OKX bars
              (see the module docstring warning in data_loader.py).
    close  -- float, the token's USDT market price at that bar (a market
              price, NOT a ratio/rate to an underlying asset).

Optional columns (open, high, low, volume) are accepted and ignored.

OPERATOR ACTION REQUIRED: populate user_data/data/lst/*.csv with real LST
market-price data before this adapter contributes real instruments. Until
then, sync_normalized_store() finds no files and returns an empty list --
this is not an error, since the OKX-futures source operates fine alone.
"""
import json
from pathlib import Path

import pandas as pd

LST_SOURCE_DIR = Path(__file__).parent.parent.parent / "user_data" / "data" / "lst"

REQUIRED_COLUMNS = {"date", "close"}


def _load_manifest(manifest_path: Path) -> dict:
    if manifest_path.exists():
        with open(manifest_path) as f:
            return json.load(f)
    return {}


def sync_normalized_store(normalized_dir: Path, timeframe: str = "30m") -> list[str]:
    """Read operator-supplied LST CSV fixtures and write normalized per-instrument
    (date, close) files into normalized_dir, plus update manifest.json.

    `timeframe` is accepted for interface symmetry with the OKX adapter but is
    NOT used to select files -- LST fixtures are not named by timeframe. It is
    the operator's responsibility to supply data at the pipeline's bar
    frequency.

    Parameters
    ----------
    normalized_dir : Path
        Destination directory for the normalized per-instrument store
        (shared with other adapters, e.g. okx_futures).
    timeframe : str, default "30m"
        Unused; present for interface symmetry with other adapters.

    Returns
    -------
    list[str]
        Tickers written, sorted alphabetically by ticker (this source has no
        prior baseline to preserve ordering against, unlike okx_futures).
        Returns [] if user_data/data/lst/ does not exist or contains no
        *.csv fixture files -- this is not an error.

    Raises
    ------
    ValueError
        If a fixture file is missing the required `date` or `close` column.
    """
    if not LST_SOURCE_DIR.exists():
        return []

    files = sorted(LST_SOURCE_DIR.glob("*.csv"))
    if not files:
        return []

    normalized_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = normalized_dir / "manifest.json"
    manifest = _load_manifest(manifest_path)

    tickers = []
    for path in files:
        ticker = path.stem
        df_raw = pd.read_csv(path)
        missing = REQUIRED_COLUMNS - set(df_raw.columns)
        if missing:
            raise ValueError(
                f"LST fixture {path} is missing required column(s) {sorted(missing)}. "
                f"Expected at least: {sorted(REQUIRED_COLUMNS)}."
            )
        if df_raw.empty:
            continue

        df_raw["date"] = pd.to_datetime(df_raw["date"], utc=True)
        df_raw["close"] = df_raw["close"].astype(float)
        df_raw[["date", "close"]].to_feather(normalized_dir / f"{ticker}.feather")

        manifest[ticker] = {"source": "lst_token", "quote": "USDT"}
        tickers.append(ticker)

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)

    return tickers
