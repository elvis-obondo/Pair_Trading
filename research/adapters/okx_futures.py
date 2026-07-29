import json
from pathlib import Path

import pandas as pd

OKX_FUTURES_DIR = Path(__file__).parent.parent.parent / "user_data" / "data" / "okx" / "futures"


def _load_manifest(manifest_path: Path) -> dict:
    if manifest_path.exists():
        with open(manifest_path) as f:
            return json.load(f)
    return {}


def sync_normalized_store(normalized_dir: Path, timeframe: str = "30m") -> list[str]:
    """Read OKX futures feather files for `timeframe` and materialize a source-agnostic
    normalized store: one two-column (date, close) feather file per instrument at
    normalized_dir/{TICKER}.feather, plus a manifest.json sidecar recording each
    instrument's source and quote currency.

    All OKX-specific knowledge (directory layout, glob pattern, filename encoding,
    ticker extraction) lives in this function; nothing downstream needs it.

    Parameters
    ----------
    normalized_dir : Path
        Destination directory for the normalized per-instrument store.
    timeframe : str, default "30m"
        Bar timeframe to select from OKX futures filenames
        (BTC_USDT_USDT-30m-futures.feather).

    Returns
    -------
    list[str]
        Tickers written, in OKX source-file discovery order (i.e. sorted by the
        raw OKX filename, exactly as the original data_loader.py ordered columns).
        This order does not match a plain alphabetical sort of the ticker strings
        themselves whenever one ticker is a prefix of another (e.g. AR/ARB,
        ETH/ETHFI) — "_USDT_USDT..." sorts differently than the bare ticker does.
        Callers that need the historical column order must use this returned
        list rather than re-deriving order from the normalized directory listing.

    Raises
    ------
    FileNotFoundError
        If no OKX futures files for `timeframe` are found.
    """
    files = sorted(OKX_FUTURES_DIR.glob(f"*_USDT_USDT-{timeframe}-futures.feather"))
    if not files:
        raise FileNotFoundError(
            f"No futures {timeframe} data files found in {OKX_FUTURES_DIR}. "
            f"Download data first with: freqtrade download-data --trading-mode futures --timeframes {timeframe}"
        )

    normalized_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = normalized_dir / "manifest.json"
    manifest = _load_manifest(manifest_path)

    tickers = []
    for path in files:
        ticker = path.name.split("_")[0]
        df_raw = pd.read_feather(path)
        if df_raw.empty:
            continue
        df_raw[["date", "close"]].to_feather(normalized_dir / f"{ticker}.feather")
        manifest[ticker] = {"source": "okx_futures", "quote": "USDT"}
        tickers.append(ticker)

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)

    return tickers
