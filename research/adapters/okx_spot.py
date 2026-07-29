"""
OKX spot adapter — third data source feeding the shared normalized store.

Reads OKX SPOT market OHLCV feathers downloaded via freqtrade
(`freqtrade download-data --trading-mode spot`) and writes normalized
(date, close) files into the shared store, tagged instrument_type="spot".

FILENAME CONVENTION -- VERIFIED, NOT ASSUMED
----------------------------------------------
Spot data does NOT follow the futures naming pattern and does NOT live in
a "spot" subdirectory. This was verified directly against freqtrade's own
source (no freqtrade installation or real downloaded spot data was
available in this environment to check against directly):

    freqtrade/misc.py::pair_to_filename() replaces "/", ":", and a few
    other characters with "_". A spot ccxt symbol has no settle-currency
    suffix, e.g. "BTC/USDT" -> "BTC_USDT" (ONE underscore group). A
    futures symbol "BTC/USDT:USDT" -> "BTC_USDT_USDT" (TWO groups) --
    which is why the existing futures files are named
    BTC_USDT_USDT-30m-futures.feather.

    freqtrade/data/history/datahandlers/idatahandler.py::_pair_data_filename()
    only adds a "futures" subdirectory AND a "-{candle_type}" filename
    suffix when candle_type != SPOT. For candle_type == SPOT specifically,
    BOTH are skipped: no subdirectory, no suffix (spot is the unmarked
    default candle type in freqtrade's convention -- futures/mark/
    funding_rate are the ones that get an explicit label).

    Net result: a spot 30-minute file for BTC/USDT lands at

        user_data/data/okx/BTC_USDT-30m.feather

    directly in the exchange's base data directory -- a SIBLING of the
    existing user_data/data/okx/futures/ directory, NOT a subdirectory
    inside it, and with NO "-spot" suffix.

    OPERATOR ACTION: run one real `freqtrade download-data --trading-mode
    spot` and confirm the resulting filename matches
    {TICKER}_USDT-{timeframe}.feather directly under user_data/data/okx/
    before trusting this adapter against live data.

TICKER-COLLISION HANDLING
----------------------------------------------
Unlike the LST adapter (which trusts the operator to pick non-colliding
ticker names), the spot universe here is selected structurally (top-N by
volume, see research/universe_selection.py) rather than hand-curated, so
it can legitimately select a symbol that's also an existing OKX futures
ticker (e.g. SOL trades both spot and perp). Existing futures/LST column
names must not change (that would break the byte-identity invariance
established in earlier tasks), so on collision the SPOT ticker is the one
disambiguated: it is stored as "{TICKER}_SPOT" instead of "{TICKER}", and
recorded under that key in the manifest and the returned ticker list.
No collision handling is needed the other direction (spot syncs after
futures, so futures always claims the plain name first).

All OKX-spot-specific knowledge (directory, glob pattern, ticker
extraction, collision handling) lives in this function; nothing
downstream needs it.
"""
import json
from pathlib import Path

import pandas as pd

# Base OKX data directory (sibling of .../okx/futures/) -- NOT a "spot"
# subdirectory. See module docstring for the verified reasoning.
OKX_SPOT_DIR = Path(__file__).parent.parent.parent / "user_data" / "data" / "okx"


def _load_manifest(manifest_path: Path) -> dict:
    if manifest_path.exists():
        with open(manifest_path) as f:
            return json.load(f)
    return {}


def sync_normalized_store(normalized_dir: Path, timeframe: str = "30m") -> list[str]:
    """Read OKX spot feather files for `timeframe` and materialize normalized
    (date, close) per-instrument files into normalized_dir, plus update
    manifest.json with instrument_type="spot".

    Parameters
    ----------
    normalized_dir : Path
        Destination directory for the normalized per-instrument store
        (shared with the other adapters).
    timeframe : str, default "30m"
        Bar timeframe to select from OKX spot filenames
        (BTC_USDT-30m.feather).

    Returns
    -------
    list[str]
        Tickers written, sorted by filename. A ticker colliding with an
        existing non-spot manifest entry is returned (and stored) as
        "{TICKER}_SPOT" instead of "{TICKER}" -- see module docstring.
        Returns [] if no OKX spot files are found for `timeframe` -- this
        is NOT an error: futures-only / futures+LST operation must be
        completely unaffected by the absence of spot data.
    """
    files = sorted(OKX_SPOT_DIR.glob(f"*_USDT-{timeframe}.feather"))
    if not files:
        return []

    normalized_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = normalized_dir / "manifest.json"
    manifest = _load_manifest(manifest_path)

    tickers = []
    for path in files:
        ticker = path.name.split("_")[0]
        df_raw = pd.read_feather(path)
        if df_raw.empty:
            continue

        store_ticker = ticker
        if ticker in manifest and manifest[ticker].get("source") != "okx_spot":
            store_ticker = f"{ticker}_SPOT"

        df_raw[["date", "close"]].to_feather(normalized_dir / f"{store_ticker}.feather")
        manifest[store_ticker] = {"source": "okx_spot", "quote": "USDT", "instrument_type": "spot"}
        tickers.append(store_ticker)

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)

    return tickers
