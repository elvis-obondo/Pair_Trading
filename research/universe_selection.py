"""
Top-N-by-volume universe selection for the OKX spot instrument universe.

Structural (data-driven) selection, NOT a hardcoded token list: ranks
candidate OKX spot USDT instruments by their trailing-window AVERAGE DAILY
USDT-notional volume (default 30 days) -- not a 24h snapshot, which is
noisier and more gameable by a single volume spike -- and returns the top
N, after removing two categories of candidate that are structurally unfit
to be a cointegration leg (see the two exclusion rules below).

This is a planning/discovery utility, separate from the data-loading
pipeline: it tells the operator WHICH tickers to download (via
`freqtrade download-data --trading-mode spot`) so that
research/adapters/okx_spot.py has something to pick up. It is not wired
into get_price_levels() and does not affect any existing behavior.

TWO EXCLUSION RULES, KEPT SEPARATE (different rationale each)
------------------------------------------------------------------
1. Market-factor exclusion (exclude_symbols, default {"BTC", "ETH"}):
   by SYMBOL. BTC/ETH aren't excluded for being pegged -- they're not --
   they're excluded because nearly everything in crypto correlates with
   them; they're the market factor, not a candidate "protocol token" for
   pair discovery. A hardcoded, tiny, auditable list is appropriate here
   because there are exactly two chain-native majors this applies to and
   the rationale is symbol-specific, not behavioral.

2. Peg exclusion (peg_cv_threshold): BEHAVIORAL, not a name list. A
   pegged instrument (USD stablecoin, gold-pegged token like XAUT, or any
   future unknown peg) has near-zero price variability over any real
   window -- that's what "pegged" means. A real token's price random-walks
   and does not. This is detected via the coefficient of variation (CV)
   of raw close price (std/mean) over the selection window, NOT a
   hardcoded stablecoin list (new pegs launch constantly; a hand list is
   both incomplete and a maintenance/contamination risk). See
   DEFAULT_PEG_CV_THRESHOLD below for how the cutoff was chosen.
"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from adapters.okx_spot import OKX_SPOT_DIR  # noqa: E402 -- reuses the adapter's own path/glob knowledge (see list_downloaded_spot_tickers) instead of re-deriving it here

# Chain-native majors excluded by symbol: they represent the market factor
# itself (nearly everything correlates with BTC/ETH), not a "protocol
# token" candidate for pair discovery. Documented here so the exclusion
# is auditable rather than implicit in some hardcoded pairlist. This is
# NOT the peg-exclusion mechanism -- see module docstring.
DEFAULT_EXCLUDED_SYMBOLS = {"BTC", "ETH"}

# Empirically chosen -- and deliberately CONSERVATIVE, because the real
# distribution does NOT have one clean gap all the way from "pegged" to
# "real token". Computed CV (std/mean of the 30-day daily close) for all
# ~300 real OKX spot/USDT candidates with sufficient history (see the
# accompanying task report for the full sorted distribution). What was
# actually found:
#
#   - A tight, unambiguous near-zero cluster of 8 tickers (AUDF, USDS,
#     USDG, RLUSD, PYUSD, USDC, USD1, USAT), all CV in [~3e-16, ~3.3e-4],
#     with consecutive gaps of ~1e-6 to ~1e-4 within the cluster.
#   - Then a genuinely large, clean jump: USAT (3.28e-4) -> AUDM (4.98e-3),
#     a >10x relative jump, far bigger (in log space) than any other
#     nearby gap. This is the ONE robust, defensible boundary found.
#   - Above that point, CV increases in a SMOOTH CONTINUUM with no further
#     clean separation. Critically, legitimate gold-pegged tokens (XAUT
#     cv=0.0130, PAXG cv=0.0135) sit IMMEDIATELY ADJACENT to genuine,
#     non-pegged, real cryptocurrencies with naturally low 30-day
#     volatility (TRX cv=0.0137, ASTER cv=0.0145, BNB cv=0.0150,
#     ELF cv=0.0168, WLFI cv=0.0189) -- there is NO gap separating them.
#     A threshold anywhere in this region either lets gold-pegs through
#     (too low) or wrongly excludes BNB/TRX as "pegged" (too high, e.g.
#     the previous 0.02 default used before this was actually checked
#     against real data -- an error, corrected here). See the task report
#     for the full discussion; this ambiguity is a judgment call, not
#     something this function can resolve on its own.
#
# Given that, this default is set at the ONE gap that's actually clean and
# defensible (0.002, comfortably between USAT and AUDM) -- catching only
# the unambiguous USD/AUD stablecoin cluster. It will NOT catch XAUT,
# PAXG, AUDM, BRL1, or NFT (also low-CV, cv=0.0085, likely peg-adjacent
# but unconfirmed) by default. Raise `peg_cv_threshold` toward ~0.014-0.02
# to also catch those, but that trades in a real risk of excluding
# legitimate low-volatility majors (TRX, BNB) as false positives -- there
# is no threshold that gets both right on this window. This is a DEFAULT,
# not a hardcoded final answer -- override `peg_cv_threshold` explicitly;
# the full distribution is reported alongside every use of the default so
# it can be checked and vetoed.
DEFAULT_PEG_CV_THRESHOLD = 0.002


def _default_fetch_daily_bars(symbols: list[str], window_days: int) -> dict[str, dict]:
    """Live OKX spot data via ccxt: `window_days` of daily OHLCV bars per symbol.

    Returns {symbol: {"close": [...], "volume": [...]}} using the last
    window_days daily bars (close and base-asset volume respectively). A
    symbol is omitted if: it fails to fetch (delisted, too new, API
    error); it returns fewer than `window_days` bars; or it has ZERO
    total volume across the whole window. A dead/inactive listing with a
    stale carried-forward price and no real trading has no genuine price
    discovery happening at all -- its CV would reflect "nothing traded",
    not "this is pegged", and would corrupt peg-vs-real classification
    (found empirically: one such symbol, AUDF, produced a degenerate
    near-zero CV that dominated the gap-detection analysis until this
    filter was added -- see the accompanying task report).

    Fetches both series from ONE ccxt call per symbol (not two) so that
    volume ranking and peg detection share the same network round-trip.
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
        bars = ohlcv[-window_days:]
        # ccxt OHLCV row: [timestamp, open, high, low, close, volume(base)]
        volumes = [row[5] for row in bars]
        if sum(volumes) <= 0:
            continue
        result[symbol] = {
            "close": [row[4] for row in bars],
            "volume": volumes,
        }
    return result


def _notional_volume(closes: list[float], volumes: list[float]) -> float:
    """Average daily USDT-notional turnover: mean(close * base_volume).

    ccxt's OHLCV `volume` field is base-asset volume (a token count), not
    comparable across instruments with wildly different unit prices -- a
    sub-cent memecoin with a huge supply can show an enormous raw token
    count while moving a modest amount of actual USDT. Multiplying by
    close price converts to comparable USDT-notional turnover, which is
    what "average daily volume" should mean for a liquidity-based ranking.
    """
    closes = np.asarray(closes, dtype=float)
    volumes = np.asarray(volumes, dtype=float)
    return float(np.mean(closes * volumes))


def find_natural_gap(cv_values: list[float], min_gap_ratio: float = 3.0, log_epsilon: float = 1e-8) -> dict:
    """Inspect a set of CV values for a natural gap separating a near-constant
    (pegged) cluster from the rest, so a threshold can be chosen IN that gap
    rather than guessed.

    Works in LOG10 space (values floored at `log_epsilon` first), NOT linear
    space, because real CV distributions for this universe span several
    orders of magnitude: true pegs sit around 1e-4, real tokens range from
    ~0.01 to 0.5+. A linear "biggest absolute gap" search is dominated by
    the sparse, spread-out high-CV tail -- e.g. a 0.05 absolute gap between
    two unrelated volatile tokens far out in the tail is numerically bigger
    than, but far LESS meaningful than, a 0.0003 -> 0.005 jump right after
    the peg cluster, which is only a tiny absolute gap but a >10x relative
    jump. This was found empirically: an earlier linear-gap version of this
    function picked out a meaningless gap in the sparse tail of the real
    OKX universe and missed the real peg/non-peg boundary entirely (see the
    accompanying task report). Log-space gaps correctly weight relative,
    not absolute, jumps.

    Method: sort ascending, log10-transform (floored), compute every
    consecutive gap in log space, take the largest one. That gap is
    "clean" only if it is at least `min_gap_ratio` times the median of all
    the OTHER consecutive log-space gaps -- i.e. a genuinely anomalous
    jump, not just the largest of many similarly-sized gaps in a smooth
    continuum (which would mean there's no real cluster boundary, just
    noise -- see the no-clean-gap case this is designed to report
    honestly rather than paper over).

    Parameters
    ----------
    cv_values : list[float]
        CV values across the candidate universe (see _coefficient_of_variation).
    min_gap_ratio : float, default 3.0
        How much larger the largest log-space gap must be than the median
        of the other log-space gaps to count as a genuine cluster boundary
        rather than noise in a continuum.
    log_epsilon : float, default 1e-8
        Floor applied before the log10 transform, so an exact-zero CV
        (a perfectly flat series) doesn't blow up to -inf.

    Returns
    -------
    dict with:
        has_clean_gap : bool -- False (with no suggested_threshold) if
            fewer than 2 distinct values, or the largest gap isn't
            anomalous relative to the rest.
        gap_start, gap_end : the two RAW (linear, un-floored) CV values
            bounding the largest gap (None if has_clean_gap is False or
            too few values).
        suggested_threshold : geometric mean of the (floored) gap bounds
            if has_clean_gap, else None -- the natural "midpoint" in log
            space. Deliberately NOT auto-applied anywhere; this is a
            report for a human to act on, not a silent auto-cutoff.
        largest_gap, median_other_gap : the LOG10-space gap sizes behind
            the has_clean_gap verdict (not the same units as the CV
            values themselves), so the call can be checked, not just
            trusted.
    """
    values = sorted(cv_values)
    empty_result = {
        "has_clean_gap": False, "gap_start": None, "gap_end": None,
        "suggested_threshold": None, "largest_gap": None, "median_other_gap": None,
    }
    if len(values) < 2:
        return empty_result

    log_values = [np.log10(max(v, log_epsilon)) for v in values]
    gaps = [log_values[i + 1] - log_values[i] for i in range(len(log_values) - 1)]
    max_gap = max(gaps)
    max_idx = gaps.index(max_gap)
    other_gaps = gaps[:max_idx] + gaps[max_idx + 1:]

    if not other_gaps:
        # Exactly two values total: one gap, nothing to compare it against.
        return empty_result

    median_other = float(np.median(other_gaps))
    has_clean_gap = bool(
        max_gap > 0
        and (median_other == 0 or max_gap >= min_gap_ratio * median_other)
        and max_gap > 1e-9
    )

    suggested_threshold = None
    if has_clean_gap:
        log_mid = (log_values[max_idx] + log_values[max_idx + 1]) / 2.0
        suggested_threshold = float(10 ** log_mid)

    return {
        "has_clean_gap": has_clean_gap,
        "gap_start": values[max_idx] if has_clean_gap else None,
        "gap_end": values[max_idx + 1] if has_clean_gap else None,
        "suggested_threshold": suggested_threshold,
        "largest_gap": max_gap,
        "median_other_gap": median_other,
    }


def _coefficient_of_variation(closes: list[float]) -> float:
    """CV = std(price) / mean(price) (population std, ddof=0) over the window.

    Near zero for a pegged/near-constant price series (USD stablecoins,
    gold-pegs like XAUT, or any future unknown peg target) since a peg's
    whole purpose is near-zero price variability; materially larger for a
    real, price-discovering token. Deliberately behavioral (looks only at
    price variability), not a name list -- see module docstring.
    """
    closes = np.asarray(closes, dtype=float)
    mean = closes.mean()
    if mean == 0:
        return float("inf")
    return float(closes.std() / mean)


def build_candidate_table(
    window_days: int = 30,
    exclude_symbols: set[str] | None = None,
    peg_cv_threshold: float | None = DEFAULT_PEG_CV_THRESHOLD,
    candidate_symbols: list[str] | None = None,
    fetch_daily_bars: Callable[[list[str], int], dict[str, dict]] | None = None,
) -> pd.DataFrame:
    """Build the FULL auditable candidate table: every candidate considered,
    its avg_daily_volume, its price CV, and why it was excluded (if it was).

    This is the metadata record the operator can inspect to see exactly
    what was dropped and why -- select_top_n_by_volume() is a thin filter
    on top of this table's `excluded_reason is None` rows.

    Parameters
    ----------
    window_days : int, default 30
        Number of trailing daily bars to use for both the volume ranking
        and the peg CV statistic.
    exclude_symbols : set[str], optional
        Ticker symbols always excluded, reason="excluded_market_factor"
        (default: {"BTC", "ETH"} -- see DEFAULT_EXCLUDED_SYMBOLS).
    peg_cv_threshold : float or None, default DEFAULT_PEG_CV_THRESHOLD
        Instruments with price CV strictly below this are excluded,
        reason="excluded_peg". Pass None to disable peg filtering entirely
        (e.g. to inspect the raw, unfiltered CV distribution before
        choosing a threshold -- this is how DEFAULT_PEG_CV_THRESHOLD
        itself was chosen; see module docstring).
    candidate_symbols : list[str], optional
        Candidate ccxt spot symbols (e.g. ["SOL/USDT", "JUP/USDT"]). If
        None, live OKX spot USDT markets are discovered via ccxt (excludes
        anything with a settle-currency suffix, i.e. futures).
    fetch_daily_bars : callable, optional
        (symbols, window_days) -> {symbol: {"close": [...], "volume": [...]}}.
        Injectable so this is testable against fixtures without live
        network access; defaults to _default_fetch_daily_bars (real OKX
        data via ccxt).

    Returns
    -------
    pd.DataFrame with columns [ticker, symbol, avg_daily_volume, cv,
    excluded_reason], one row per candidate that had enough history to
    fetch. excluded_reason is one of {None, "excluded_market_factor",
    "excluded_peg"}. NOT sorted or truncated -- see select_top_n_by_volume
    for that.
    """
    exclude_symbols = exclude_symbols if exclude_symbols is not None else DEFAULT_EXCLUDED_SYMBOLS
    fetch_daily_bars = fetch_daily_bars or _default_fetch_daily_bars

    if candidate_symbols is None:
        import ccxt

        exchange = ccxt.okx({"options": {"defaultType": "spot"}})
        markets = exchange.fetch_tickers()
        candidate_symbols = [s for s in markets if s.endswith("/USDT") and ":" not in s]

    candidate_symbols = sorted(set(candidate_symbols))  # deterministic tie-break order
    symbol_ticker = {s: s.split("/")[0] for s in candidate_symbols}

    bars = fetch_daily_bars(candidate_symbols, window_days)

    rows = []
    for symbol in candidate_symbols:  # preserves the alphabetical tie-break order
        if symbol not in bars:
            continue
        ticker = symbol_ticker[symbol]
        closes, volumes = bars[symbol]["close"], bars[symbol]["volume"]
        avg_daily_volume = _notional_volume(closes, volumes)
        cv = _coefficient_of_variation(closes)

        if ticker in exclude_symbols:
            reason = "excluded_market_factor"
        elif peg_cv_threshold is not None and cv < peg_cv_threshold:
            reason = "excluded_peg"
        else:
            reason = None

        rows.append({
            "ticker": ticker,
            "symbol": symbol,
            "avg_daily_volume": avg_daily_volume,
            "cv": cv,
            "excluded_reason": reason,
        })

    return pd.DataFrame(rows, columns=["ticker", "symbol", "avg_daily_volume", "cv", "excluded_reason"])


def select_top_n_by_volume(
    n: int = 50,
    window_days: int = 30,
    exclude_symbols: set[str] | None = None,
    peg_cv_threshold: float | None = DEFAULT_PEG_CV_THRESHOLD,
    candidate_symbols: list[str] | None = None,
    fetch_daily_bars: Callable[[list[str], int], dict[str, dict]] | None = None,
) -> pd.DataFrame:
    """Select the top N OKX spot USDT instruments by window_days-average daily
    USDT-notional volume (turnover), after removing market-factor symbols and
    behaviorally-detected pegs.

    Exclusion is applied BEFORE the top-N truncation (via build_candidate_table,
    on the full candidate set), so an excluded peg or market-factor symbol
    does NOT consume one of the N slots -- the result is always up to N
    non-excluded instruments (fewer only if fewer than N candidates survive
    exclusion and have enough history).

    Parameters
    ----------
    n : int, default 50
        Number of instruments to select.
    window_days : int, default 30
        Number of trailing daily bars for both volume ranking and peg CV.
    exclude_symbols : set[str], optional
        See build_candidate_table.
    peg_cv_threshold : float or None, default DEFAULT_PEG_CV_THRESHOLD
        See build_candidate_table. Pass None to disable peg filtering.
    candidate_symbols : list[str], optional
        See build_candidate_table.
    fetch_daily_bars : callable, optional
        See build_candidate_table.

    Returns
    -------
    pd.DataFrame with columns [rank, ticker, symbol, avg_daily_volume, cv],
    rank 1 = highest volume, length <= n, ZERO excluded (market-factor or
    peg) instruments among them.

    Tie-break rule (documented, not implicit): candidates are sorted
    alphabetically by symbol BEFORE ranking by volume, and the volume sort
    uses a stable sort. So if two candidates have EXACTLY equal
    avg_daily_volume, the alphabetically-earlier symbol gets the lower
    (better) rank number.
    """
    table = build_candidate_table(
        window_days=window_days,
        exclude_symbols=exclude_symbols,
        peg_cv_threshold=peg_cv_threshold,
        candidate_symbols=candidate_symbols,
        fetch_daily_bars=fetch_daily_bars,
    )

    survivors = table[table["excluded_reason"].isna()].drop(columns=["excluded_reason"])
    if survivors.empty:
        return pd.DataFrame(columns=["rank", "ticker", "symbol", "avg_daily_volume", "cv"])

    df = (
        survivors
        .sort_values("avg_daily_volume", ascending=False, kind="stable")
        .reset_index(drop=True)
        .head(n)
    )
    df.insert(0, "rank", df.index + 1)
    return df


def format_download_command(
    symbols: list[str],
    timeframe: str = "30m",
    days: int = 60,
    trading_mode: str = "futures",
    exchange: str = "okx",
    config_path: str = "user_data/config.json",
) -> str:
    """Build the `freqtrade download-data` command for a list of ccxt symbols
    (e.g. select_top_n_by_volume()'s `symbol` column), so the operator can
    copy-paste one command instead of hand-typing --pairs for N tickers.

    Runs via `docker compose run --rm freqtrade ...` rather than a bare
    `freqtrade` binary, matching this repo's documented setup (README:
    Freqtrade runs via the Docker image in docker-compose.yml). `run` (not
    `up`) is used so this one-off command overrides docker-compose.yml's
    default `trade` command instead of launching the live-trading service.

    `days`, default 60 (~2 months), is passed explicitly via `--days` rather
    than left to freqtrade's own default (30 days) -- see the existing
    futures feathers in user_data/data/okx/futures/, which were themselves
    downloaded with that 30-day default and are on the thin side for a
    stable cointegration/half-life estimate.

    Returns an empty-pairs-safe string; callers should check for an empty
    `symbols` list themselves (nothing to download) rather than relying on
    this function to detect it.
    """
    pairs = " ".join(symbols)
    return (
        f"docker compose run --rm freqtrade download-data "
        f"--config {config_path} --exchange {exchange} "
        f"--trading-mode {trading_mode} --timeframes {timeframe} "
        f"--days {days} --pairs {pairs}"
    )


def list_downloaded_spot_tickers(timeframe: str = "30m") -> dict[str, Path]:
    """Currently-downloaded OKX spot tickers and their raw feather paths.

    Mirrors adapters/okx_spot.py's own file discovery exactly -- same
    directory (OKX_SPOT_DIR, imported from that module rather than
    re-hardcoded here), same glob pattern, same ticker-extraction rule
    (filename split on "_") -- so this report can never drift from what the
    adapter itself would actually pick up on its next sync.

    Returns {} if OKX_SPOT_DIR doesn't exist yet (nothing downloaded) --
    not an error, same convention as the adapter itself.
    """
    if not OKX_SPOT_DIR.exists():
        return {}
    files = sorted(OKX_SPOT_DIR.glob(f"*_USDT-{timeframe}.feather"))
    return {path.name.split("_")[0]: path for path in files}


def build_refresh_report(result: pd.DataFrame, timeframe: str = "30m", days: int = 60) -> str:
    """Markdown report: which currently-downloaded spot tickers fell out of
    the fresh top-N selection (delete these first) and the ready-to-paste
    download command for the current selection (run second).

    Read-only / report-only -- deletes nothing, downloads nothing. Scoped
    to OKX SPOT only (see list_downloaded_spot_tickers): deliberately does
    not enumerate or mention user_data/data/okx/futures/ or
    user_data/data/lst/, neither of which this selection process touches.

    Parameters
    ----------
    result : pd.DataFrame
        Output of select_top_n_by_volume() -- the fresh selection to diff
        the current disk state against.
    timeframe, days
        Forwarded to format_download_command() for section 2 of the report.
    """
    selected_tickers = set(result["ticker"]) if not result.empty else set()
    downloaded = list_downloaded_spot_tickers(timeframe=timeframe)
    stale = sorted(t for t in downloaded if t not in selected_tickers)

    lines = [
        "# Spot universe refresh",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"Timeframe: `{timeframe}` | Fresh selection: {len(selected_tickers)} tickers | "
        f"Currently downloaded (spot): {len(downloaded)} tickers",
        "",
        "Scope: OKX **spot** files only "
        f"(`{OKX_SPOT_DIR}`). Do not touch `user_data/data/okx/futures/` or "
        "`user_data/data/lst/` based on this report -- neither is part of "
        "this selection.",
        "",
        "## 1. Delete these first (no longer in the fresh top-N)",
        "",
    ]
    if stale:
        lines.append(f"{len(stale)} currently-downloaded ticker(s) fell out of the selection:")
        lines.append("")
        for ticker in stale:
            lines.append(f"- [ ] `{ticker}` -> `{downloaded[ticker]}`")
    else:
        lines.append("None -- every currently-downloaded spot ticker is still in the selection.")
    lines += [
        "",
        "## 2. Then run this to (re)download the fresh selection",
        "",
        "```bash",
        format_download_command(result["symbol"].tolist(), timeframe=timeframe, days=days)
        if not result.empty else "# no surviving candidates -- nothing to download",
        "```",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    table = build_candidate_table(peg_cv_threshold=None)  # unfiltered, to show the full CV distribution
    print(f"Fetched {len(table)} candidates with sufficient history.\n")

    print("--- CV distribution (sorted ascending, lowest 20) ---")
    print(table.sort_values("cv")[["ticker", "cv", "avg_daily_volume"]].head(20).to_string(index=False))
    print()

    peg_candidates = table[~table["ticker"].isin(DEFAULT_EXCLUDED_SYMBOLS)].sort_values("cv")
    gap = find_natural_gap(peg_candidates["cv"].tolist())
    print("--- Natural-gap analysis (excludes BTC/ETH, which are removed by symbol not CV) ---")
    if gap["has_clean_gap"]:
        print(f"Clean gap found: {gap['gap_start']:.5f} -> {gap['gap_end']:.5f} "
              f"(largest_gap={gap['largest_gap']:.5f}, median_other_gap={gap['median_other_gap']:.5f}); "
              f"suggested_threshold={gap['suggested_threshold']:.5f}")
    else:
        print(f"NO clean gap detected (largest_gap={gap['largest_gap']}, median_other_gap={gap['median_other_gap']}) "
              f"-- do not force a cutoff; this is a judgment call for the operator.")
    print()

    print(f"--- Applying DEFAULT_PEG_CV_THRESHOLD = {DEFAULT_PEG_CV_THRESHOLD} ---")
    below = peg_candidates[peg_candidates["cv"] < DEFAULT_PEG_CV_THRESHOLD]
    above = peg_candidates[peg_candidates["cv"] >= DEFAULT_PEG_CV_THRESHOLD]
    print(f"Excluded as pegged ({len(below)}): {sorted(below['ticker'].tolist())}")
    if not above.empty:
        print(f"Lowest-CV surviving (real) token: {above.iloc[0]['ticker']} (cv={above.iloc[0]['cv']:.5f})")
    print()

    print("--- Final top-N selection (pegs + BTC/ETH excluded) ---")
    result = select_top_n_by_volume()
    print(result.to_string(index=False))
    print()

    if result.empty:
        print("--- Download command --- (skipped: no surviving candidates)")
    else:
        print("--- Download command (paste into terminal) ---")
        print(format_download_command(result["symbol"].tolist()))
    print()

    report_path = Path(__file__).parent / "SPOT_UNIVERSE_REFRESH.md"
    report_path.write_text(build_refresh_report(result))
    print(f"--- Wrote {report_path} -- read it (and delete what it lists) before pasting the download command above ---")
