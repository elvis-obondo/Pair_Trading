"""
Top-N-by-volume universe selection for the OKX spot instrument universe.

Structural (data-driven) selection, NOT a hardcoded token list: ranks
candidate OKX spot USDT instruments by their trailing-window AVERAGE DAILY
volume (default 30 days) -- not a 24h snapshot, which is noisier and more
gameable by a single volume spike -- and returns the top N.

This is a planning/discovery utility, separate from the data-loading
pipeline: it tells the operator WHICH tickers to download (via
`freqtrade download-data --trading-mode spot`) so that
research/adapters/okx_spot.py has something to pick up. It is not wired
into get_price_levels() and does not affect any existing behavior.
"""
from typing import Callable

import numpy as np
import pandas as pd

# Chain-native majors excluded by symbol: they represent the market factor
# itself (nearly everything correlates with BTC/ETH), not a "protocol
# token" candidate for pair discovery. Documented here so the exclusion
# is auditable rather than implicit in some hardcoded pairlist.
DEFAULT_EXCLUDED_SYMBOLS = {"BTC", "ETH"}


def _default_fetch_daily_volumes(symbols: list[str], window_days: int) -> dict[str, list[float]]:
    """Live OKX spot data via ccxt: `window_days` of daily USDT NOTIONAL volume
    bars per symbol (close * base-asset volume, i.e. turnover), NOT raw
    base-asset volume.

    This distinction matters: ccxt's OHLCV `volume` field is base-asset
    volume (a count of tokens traded), which is not comparable across
    instruments with wildly different unit prices -- a sub-cent memecoin
    with a huge supply can show an enormous raw token count while moving
    a modest number of actual USDT, drowning out genuinely liquid,
    higher-unit-price instruments in a raw-volume ranking. Multiplying by
    close price converts to a comparable USDT-notional turnover figure,
    which is what "average daily volume" should mean for a liquidity-based
    selection.

    Returns {symbol: [daily_notional_volume, ...]}. A symbol that fails to
    fetch (delisted, too new, API error) or returns fewer than
    `window_days` bars is simply omitted -- a candidate without a full,
    reliable volume history should not be rankable against ones that have
    it.
    """
    import ccxt

    exchange = ccxt.okx({"options": {"defaultType": "spot"}})
    result = {}
    for symbol in symbols:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe="1d", limit=window_days)
        except Exception:
            continue
        if len(ohlcv) < window_days:
            continue
        # ccxt OHLCV row: [timestamp, open, high, low, close, volume(base)]
        result[symbol] = [row[4] * row[5] for row in ohlcv[-window_days:]]
    return result


def select_top_n_by_volume(
    n: int = 50,
    window_days: int = 30,
    exclude_symbols: set[str] | None = None,
    candidate_symbols: list[str] | None = None,
    fetch_daily_volumes: Callable[[list[str], int], dict[str, list[float]]] | None = None,
) -> pd.DataFrame:
    """Select the top N OKX spot USDT instruments by window_days-average daily
    USDT-notional volume (turnover), NOT raw base-asset volume -- see
    _default_fetch_daily_volumes for why that distinction matters.

    Parameters
    ----------
    n : int, default 50
        Number of instruments to select.
    window_days : int, default 30
        Number of trailing daily bars to average for the volume ranking.
    exclude_symbols : set[str], optional
        Ticker symbols excluded regardless of volume rank (default:
        {"BTC", "ETH"} -- see DEFAULT_EXCLUDED_SYMBOLS).
    candidate_symbols : list[str], optional
        Candidate ccxt spot symbols to rank (e.g. ["SOL/USDT", "JUP/USDT"]).
        If None, live OKX spot USDT markets are discovered via ccxt
        (excludes anything with a settle-currency suffix, i.e. futures).
    fetch_daily_volumes : callable, optional
        (symbols, window_days) -> {symbol: [daily_volume, ...]}. Injectable
        so this function is testable against fixtures without live network
        access; defaults to _default_fetch_daily_volumes (real OKX data via
        ccxt).

    Returns
    -------
    pd.DataFrame with columns [rank, ticker, symbol, avg_daily_volume],
    rank 1 = highest volume, length <= n.

    Tie-break rule (documented, not implicit): candidates are sorted
    alphabetically by symbol BEFORE ranking by volume, and the volume sort
    uses a stable sort. So if two candidates have EXACTLY equal
    avg_daily_volume, the alphabetically-earlier symbol gets the lower
    (better) rank number.
    """
    exclude_symbols = exclude_symbols if exclude_symbols is not None else DEFAULT_EXCLUDED_SYMBOLS
    fetch_daily_volumes = fetch_daily_volumes or _default_fetch_daily_volumes

    if candidate_symbols is None:
        import ccxt

        exchange = ccxt.okx({"options": {"defaultType": "spot"}})
        markets = exchange.fetch_tickers()
        candidate_symbols = [s for s in markets if s.endswith("/USDT") and ":" not in s]

    candidate_symbols = sorted(set(candidate_symbols))  # deterministic tie-break order
    symbol_ticker = {s: s.split("/")[0] for s in candidate_symbols}
    candidate_symbols = [s for s in candidate_symbols if symbol_ticker[s] not in exclude_symbols]

    volumes = fetch_daily_volumes(candidate_symbols, window_days)

    rows = [
        {
            "ticker": symbol_ticker[symbol],
            "symbol": symbol,
            "avg_daily_volume": float(np.mean(daily_volumes)),
        }
        for symbol in candidate_symbols  # preserves the alphabetical tie-break order
        if symbol in volumes
        for daily_volumes in [volumes[symbol]]
    ]

    if not rows:
        return pd.DataFrame(columns=["rank", "ticker", "symbol", "avg_daily_volume"])

    df = (
        pd.DataFrame(rows)
        .sort_values("avg_daily_volume", ascending=False, kind="stable")
        .reset_index(drop=True)
        .head(n)
    )
    df.insert(0, "rank", df.index + 1)
    return df


if __name__ == "__main__":
    result = select_top_n_by_volume()
    print(result.to_string(index=False))
