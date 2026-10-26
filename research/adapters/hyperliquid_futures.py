import json
from pathlib import Path

import pandas as pd

HL_FUTURES_DIR = Path(__file__).parent.parent.parent / "user_data" / "data" / "hyperliquid" / "futures"
HL_CTX_DIR = Path(__file__).parent.parent.parent / "user_data" / "data" / "hyperliquid" / "ctx"


def bar_file(coin: str, timeframe: str) -> Path:
    """The one place the Hyperliquid bar filename is defined: {COIN}-{tf}.feather.

    Coins keep Hyperliquid's own names (kPEPE, kBONK, ...): a log-price spread
    is unchanged by the 1000x scale, so nothing is renamed.
    """
    return HL_FUTURES_DIR / f"{coin}-{timeframe}.feather"


def ctx_file(coin: str) -> Path:
    return HL_CTX_DIR / f"{coin}-1m-ctx.feather"


def coin_from_file(path: Path, timeframe: str) -> str:
    return path.name[: -len(f"-{timeframe}.feather")]


def _load_manifest(manifest_path: Path) -> dict:
    if manifest_path.exists():
        with open(manifest_path) as f:
            return json.load(f)
    return {}


def sync_normalized_store(normalized_dir: Path, timeframe: str = "30m") -> list[str]:
    """Read Hyperliquid perp bar files for `timeframe` and materialize the
    source-agnostic normalized store: one two-column (date, close) feather per
    instrument at normalized_dir/{TICKER}.feather, plus a manifest.json sidecar
    recording each instrument's source and quote currency.

    All Hyperliquid-specific knowledge (directory layout, filename encoding,
    ticker extraction) lives in this module; nothing downstream needs it.

    The bars are built from Hyperliquid's trade archive (HL-BUILD2,
    research/hyperliquid/build2_*.py): on-book taker trades only, label = bar
    OPEN, columns date, open, high, low, close, volume, notional,
    mins_since_trade. Archive gaps are NaN closes. Only `date` and `close` are
    copied here, which is all the store ever held.

    Returns
    -------
    list[str]
        Tickers written, sorted by Hyperliquid coin name.

    Raises
    ------
    FileNotFoundError
        If no Hyperliquid bar files for `timeframe` are found.
    """
    files = sorted(HL_FUTURES_DIR.glob(f"*-{timeframe}.feather"))
    if not files:
        raise FileNotFoundError(
            f"No Hyperliquid {timeframe} bar files found in {HL_FUTURES_DIR}. "
            f"Build them with research/hyperliquid/build2_fills.py + build2_assemble.py"
        )

    normalized_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = normalized_dir / "manifest.json"
    manifest = _load_manifest(manifest_path)

    tickers = []
    for path in files:
        ticker = coin_from_file(path, timeframe)
        df_raw = pd.read_feather(path, columns=["date", "close"])
        if df_raw.empty:
            continue
        df_raw.to_feather(normalized_dir / f"{ticker}.feather")
        manifest[ticker] = {"source": "hyperliquid_futures", "quote": "USDC", "instrument_type": "futures"}
        tickers.append(ticker)

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)

    return tickers
