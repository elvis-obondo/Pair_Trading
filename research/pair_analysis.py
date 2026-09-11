import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from data_loader import get_price_levels
from statsmodels.tsa.stattools import coint
import itertools
import numpy as np
import pandas as pd
from pathlib import Path

BAR_LENGTH = 30  # minutes per bar
BARS_PER_DAY = (24 * 60) // BAR_LENGTH  # 48 at 30-min

# Raised from the conventional 0.05 to 0.01 after checking directly against
# this project's own data: at 268 tickers (35,778 pairs/week), a flat 0.05
# bar lets through ~5% false positives BY CONSTRUCTION before any real
# relationship exists (~27 of 536 pair-weeks checked were expected from noise
# alone; ~94 were observed -- real signal, but visibly diluted by noise at
# 0.05). Tightening to 0.01 roughly doubled the week-to-week persistence
# ratio in the same check (22.2%/18.1% -> 16.7%/7.1%), though not yet at
# significance given only 62 days / 8 weekly windows of history -- treat this
# as a data-informed adjustment, not a proven-optimal cutoff.
COINT_PVALUE_THRESHOLD = 0.01

# Recency gate for get_tradeable_pairs, separate from COINT_PVALUE_THRESHOLD above.
# Looser deliberately -- this isn't a second multiple-comparison-corrected
# significance test, it's asking "how close is the most recent relationship to
# the boundary," using a continuous p-value signal instead of a binary pass/fail
# on 1-2 non-overlapping weekly chunks (see recent_cointegrated's computation in
# analyze_top_pairs for why the old binary version was too coarse: shifting the
# selection anchor by 12h could flip it, because it was counting 2-of-4-ish
# non-overlapping windows rather than reading a trend). Calibrated against one
# fold, n=5 known-outcome pairs (holdout backtest 2026-08-09->16): the mean
# p-value of the last 3 daily-stride windows was 0.10 for the one pair that lost
# money (JTO/SYRUP) and <0.06 for all four that won -- 0.2 sits comfortably above
# that gap. One fold, five pairs -- a data-informed starting point, not a proven
# cutoff; revisit once more folds exist.
RECENT_P_THRESHOLD = 0.2

# Window size for the recent-only half-life/Hurst estimates in get_tradeable_pairs
# (half_life_hours_recent, hurst_recent). Unlike RECENT_P_THRESHOLD above, this one
# is NOT backed by a discriminating result -- prototyped against the same n=5
# known-outcome pairs and found no separation: the pair that lost money and the
# four that won all had recent half-life/Hurst values inside the same range as
# each other, and neither metric would have flipped any pass/fail verdict at the
# existing thresholds either way. Added anyway on the reasoning that a 14-day
# estimate is more representative of the pair's CURRENT behavior than a 30-day
# blend, not because this sample proved it helps -- unlike recent_cointegrated,
# treat this one as unvalidated.
RECENT_WINDOW_DAYS = 14

# Both legs of a pair must individually clear this to be tradeable -- a
# 50x-leveraged position can move a thin market itself. Checked directly
# against this project's own recent holdout backtests, using real turnover
# computed from the downloaded feather data: RLS/ZK (the original live pair)
# and IOST/UMA (a recent fold's best performer at +21.82%) both fail this
# floor on BOTH legs; only 1 of 7 candidate pairs in the most recent fold
# would have survived it at $1M. Lowered from an originally-discussed $1M to
# $500k, then to $450k, after review of the actual turnover distribution
# (101 of 268 whitelisted tickers fall under $1M; 62 fall under $500k; 57
# fall under $450k).
MIN_AVG_DAILY_TURNOVER_USD = 450_000

_TURNOVER_CACHE: dict[str, float] = {}


def _avg_daily_turnover_usd(ticker: str, window_days: int = 30) -> float:
    """Average daily USDT-notional turnover (close * volume) for `ticker`,
    read directly from the raw OKX futures feather file.

    NOT from get_price_levels()/the normalized store (user_data/normalized/)
    -- that store strips volume entirely during sync, keeping only date/close
    (see data_loader.py). This reads user_data/data/okx/futures/ directly,
    the same raw files nautilus/run_backtest.py loads.

    Same method as universe_selection.py's _notional_volume: a trailing
    window_days average, not a single 24h snapshot, which is noisier and
    more gameable by a single volume spike.

    Cached per ticker (module-level dict) -- the stage-2 loop in
    analyze_top_pairs would otherwise re-read the same file once per
    candidate pair a ticker appears in, rather than once per ticker.

    Returns np.nan if the raw feather file doesn't exist or has no usable
    rows -- fails closed in get_tradeable_pairs' mask (NaN < threshold is
    False), same convention as every other gate in this module.
    """
    ticker = _base_symbol(ticker)
    if ticker in _TURNOVER_CACHE:
        return _TURNOVER_CACHE[ticker]

    path = (
        Path(__file__).parent.parent / "user_data" / "data" / "okx" / "futures"
        / f"{ticker}_USDT_USDT-30m-futures.feather"
    )
    if not path.exists():
        _TURNOVER_CACHE[ticker] = np.nan
        return np.nan

    raw = pd.read_feather(path)
    raw = raw[raw["close"].notna() & (raw["close"] > 0)]
    if raw.empty:
        _TURNOVER_CACHE[ticker] = np.nan
        return np.nan

    raw = raw.assign(date=pd.to_datetime(raw["date"]))
    cutoff = raw["date"].max() - pd.Timedelta(days=window_days)
    recent = raw[raw["date"] >= cutoff]
    daily = (
        recent.assign(turnover=recent["close"] * recent["volume"])
        .set_index("date")["turnover"]
        .resample("1D").sum()
    )
    daily = daily[daily.index < daily.index.max()]  # drop partial last day
    turnover = float(daily.mean()) if len(daily) else np.nan

    _TURNOVER_CACHE[ticker] = turnover
    return turnover


def _base_symbol(ticker: str) -> str:
    """Maps a ticker to its underlying symbol, e.g. "ARB_SPOT" -> "ARB".

    Mirrors the collision-disambiguation convention in adapters/okx_spot.py:
    a spot ticker only gets the "_SPOT" suffix when it collides with a
    futures ticker for the same underlying asset.
    """
    return ticker.removesuffix("_SPOT")


def compute_spread(price_a: np.ndarray, price_b: np.ndarray):
    """OLS spread of price_a on price_b: spread = price_a - alpha - beta*price_b.

    price_a, price_b are expected to already be log prices (this is what
    get_price_levels() in data_loader.py returns), so beta is a log-log
    elasticity / approximate dollar-notional hedge ratio, not a raw share-count
    ratio, and alpha is the log-space intercept that lines up the two series'
    levels.

    Degenerate input returns (all-NaN spread, NaN, NaN) rather than raising.

    Sub-penny instruments quantise hard enough to break the fit: SHIB prints at
    ~$0.000005, so inside one window the log-price series can collapse to a
    handful of distinct values (or one), and np.polyfit's underlying SVD then
    fails with LinAlgError("SVD did not converge in Linear Least Squares").
    Because compute_spread runs in generate_entry_signal's very first step --
    before any gate -- that exception escapes Strategy.on_bar and terminates
    the whole backtest for that pair. Measured: MANA/SHIB and NEIRO/PNUT, 2 of
    6 pairs in a live batch, produced no result at all, so every pooled
    statistic from that batch silently described only the pairs that happened
    not to crash.

    NaN is the right failure value because every consumer on the hot path
    already screens for it -- generate_entry_signal filters to finite values
    and bails at `len(S) < 3`, half_life and hurst_exponent do the same and
    return inf/NaN -- so a bad window declines to trade while the run
    continues and the pair's other windows still get evaluated. Raising, by
    contrast, throws away every remaining bar for that pair.
    """
    price_a = np.asarray(price_a, dtype=float)
    price_b = np.asarray(price_b, dtype=float)
    nan_result = (np.full(len(price_a), np.nan), np.nan, np.nan)

    if len(price_a) < 2 or len(price_b) < 2:
        return nan_result
    if not (np.isfinite(price_a).all() and np.isfinite(price_b).all()):
        return nan_result
    # A constant regressor has no slope to fit; caught explicitly so the common
    # case does not depend on the except below firing.
    if np.ptp(price_b) == 0.0:
        return nan_result

    try:
        beta, alpha = np.polyfit(price_b, price_a, 1)
    except np.linalg.LinAlgError:
        return nan_result
    if not (np.isfinite(beta) and np.isfinite(alpha)):
        return nan_result

    spread = price_a - alpha - beta * price_b
    return spread, beta, alpha


def half_life(spread: np.ndarray) -> float:
    S = np.asarray(spread, dtype=float)
    S = S[np.isfinite(S)]
    if len(S) < 3:
        return np.inf
    lam, _ = np.polyfit(S[:-1], np.diff(S), 1)
    if lam >= 0:
        return np.inf
    return -np.log(2) / lam  # bars


def hurst_exponent(spread: np.ndarray) -> float:
    S = np.asarray(spread, dtype=float)
    S = S[np.isfinite(S)]
    lags = [2, 4, 8, 16, 32, 64, 128, 256]
    if len(S) < 2 * max(lags):
        return np.nan
    variances = [np.var(S[lag:] - S[:-lag]) for lag in lags]
    slope, _ = np.polyfit(np.log(lags), np.log(variances), 1)
    return slope / 2


def rolling_coint(price_a: np.ndarray, price_b: np.ndarray, window: int = 7 * BARS_PER_DAY, stride: int = 7 * BARS_PER_DAY) -> pd.Series:
    pvalues = []
    for i in range(0, len(price_a) - window, stride):
        chunk_a = price_a[i:i + window]
        chunk_b = price_b[i:i + window]
        if not (np.isfinite(chunk_a).all() and np.isfinite(chunk_b).all()):
            continue
        _, pval, _ = coint(chunk_a, chunk_b)
        pvalues.append(pval)
    return pd.Series(pvalues)


def rolling_hedge_ratio(price_a: np.ndarray, price_b: np.ndarray, window: int = 7 * BARS_PER_DAY) -> pd.Series:
    betas = []
    for i in range(len(price_a) - window):
        beta, _ = np.polyfit(price_b[i:i + window], price_a[i:i + window], 1)
        betas.append(beta)
    return pd.Series(betas)


def get_tradeable_pairs(summary: pd.DataFrame) -> pd.DataFrame:
    """coint_stability alone is order-blind: 3-of-4 weeks passing scores the
    same 0.75 whether the failing week is the OLDEST or the MOST RECENT one,
    even though only the former is still a live relationship. recent_cointegrated
    (see analyze_top_pairs) is an AND-ed recency gate on top of it, not a
    replacement -- coint_stability still rewards a pair with a longer track
    record over one that only just scraped by, but a pair that's dead in the
    last two weekly windows is excluded regardless of how good its historical
    score looks.

    half_life_hours_recent/hurst_recent are the same idea applied to the
    other two diagnostics -- gates on top of the full-history half_life_hours/
    hurst, not replacements. Unlike recent_cointegrated, these two aren't
    backed by a discriminating result yet (see RECENT_WINDOW_DAYS' docstring
    in analyze_top_pairs); included on the reasoning that a recent estimate
    should be more representative of current behavior, not because it's been
    shown to improve outcomes."""
    mask = (
          summary["half_life_hours"].between(1, 120) &
        (summary["hurst"] < 0.5) &
        (summary["half_life_hours_recent"].between(1, 120)) &
        (summary["hurst_recent"] < 0.5) &
        (summary["coint_stability"] >= 0.5) &
        (summary["beta_cv"] < 0.6) &
        (summary["recent_cointegrated"]) &
        (summary["turnover_a_usd"] >= MIN_AVG_DAILY_TURNOVER_USD) &
        (summary["turnover_b_usd"] >= MIN_AVG_DAILY_TURNOVER_USD)
    )
    return summary[mask].reset_index(drop=True)



def analyze_top_pairs(top_n: int = 140, candidate_pool: int | None = 3000, window: int = 7 * BARS_PER_DAY, days: int = 40, end_date: str | None = None):
    """Two-stage funnel: cheap p_value pre-filter, then rank by coint_stability.

    Stage 1 (cheap): every pair gets one full-sample Engle-Granger test;
    the `candidate_pool` lowest p-values move on to stage 2. This is a
    pre-filter only, not the final ranking -- a raw p_value is easily
    dominated by whichever single asset had the biggest trending move over
    the window (it "cointegrates" with almost everything, spuriously), so
    sorting the FINAL list by p_value crowds out genuinely mean-reverting
    pairs that just don't happen to involve that week's trending asset.
    `candidate_pool` needs to be wide enough that those genuine pairs are
    still in the pool -- 150 was picked empirically after a real pair
    (SNX/WLD, tradeable on every diagnostic) ranked #29 by raw p_value
    while a single trending asset (DYDX that week, MORPHO the week before)
    occupied the entire top 10. `candidate_pool=None` (current default)
    skips the truncation entirely -- every pair with enough history goes
    to stage 2, so nothing can be cut before it's actually diagnosed. This
    costs real time (stage 2 scales with candidate count, unlike stage 1
    which scales with the whole universe regardless), but removes the one
    remaining way a genuine pair could get excluded before ever being
    scored on coint_stability/recent_cointegrated/beta_cv.

    Stage 2 (expensive): full diagnostics -- half-life, Hurst,
    rolling-window coint_stability, recent_cointegrated, beta stability --
    computed for every pair in the pool, which is then re-sorted by
    coint_stability descending. coint_stability (fraction of rolling
    windows that stayed cointegrated) is the metric that actually reflects
    a stable, tradeable relationship, unlike the single full-sample
    p_value, so it drives both the printed ranking and (alongside
    recent_cointegrated -- see get_tradeable_pairs) the tradeable-candidate
    filter. coint_stability alone is order-blind, though: it can't tell "3
    of the last 4 weeks passed, including this one" from "3 of the last 4
    weeks passed, but not this one" -- recent_cointegrated (both of the
    last two weekly windows, specifically) exists to catch the second case,
    a relationship that looks fine on the aggregate score but is actually
    already dead.

    The tradeable filter (get_tradeable_pairs) is applied to the WHOLE
    diagnosed pool, not just the printed top `top_n` rows -- a pair that
    passes every threshold but isn't in the top `top_n` by coint_stability
    should still show up as tradeable, not get silently dropped by the
    display truncation.

    end_date : str, optional
        Truncates the price data to this timestamp BEFORE the `days` window
        is computed, so `days` counts back from `end_date` instead of from
        real "now" (today's latest bar). Exists for walk-forward validation:
        run selection as if standing at some point in the past (end_date),
        so a subsequent backtest over the days AFTER end_date is evaluating
        the pair on data selection never saw, instead of the same window
        twice (see conversation -- the default screening window and the
        default backtest window turned out to be nearly identical 30-day
        spans anchored to the same "now", which is close to circular).
        None (default): use all available data, i.e. today's real "now".
    """
    print("Fetching price data...")
    # align=False: keep each instrument's own gaps intact so the per-pair
    # `dropna()` + `min_bars` check below reflects genuine joint coverage
    # for THAT pair, not the frame-wide worst case across every loaded
    # instrument (see get_price_levels' align docstring).
    df = get_price_levels(align=False, end_date=end_date)

    cutoff = df.index.max() - pd.Timedelta(days=days)
    df = df[df.index >= cutoff]
    print(f"Using last {days} days of data ({cutoff.date()} → {df.index.max().date()}), {len(df)} bars per pair.")

    spacings = df.index.to_series().diff().dropna().dt.total_seconds() / 60
    median_spacing = spacings.median()
    if abs(median_spacing - BAR_LENGTH) > 1:
        raise RuntimeError(
            f"Loaded data has median bar spacing {median_spacing:.1f}m, expected {BAR_LENGTH}m. "
            f"Check feather files or BAR_LENGTH constant."
        )

    tickers = df.columns.tolist()
    min_bars = days * BARS_PER_DAY // 2  # require at least half the expected bars

    pairs = [
        (a, b) for a, b in itertools.combinations(tickers, 2)
        if _base_symbol(a) != _base_symbol(b)
    ]
    n_pairs = len(pairs)
    print(f"Running cointegration scan on {n_pairs} pairs (min {min_bars} bars required)...")
    progress_step = max(1, n_pairs // 20)  # ~20 updates regardless of ticker count
    coint_results = []
    for i, (a, b) in enumerate(pairs):
        pair = df[[a,b]].dropna()
        if len(pair) < min_bars:
            continue
        _, pval, _ = coint(pair[a].values, pair[b].values)
        coint_results.append((a, b, pval))
        if (i + 1) % progress_step == 0 or (i + 1) == n_pairs:
            print(f"  scanned {i + 1}/{n_pairs} pairs ({(i + 1) / n_pairs:.0%})")

    coint_df = (
        pd.DataFrame(coint_results, columns=["ticker_a", "ticker_b", "p_value"])
        .sort_values("p_value")
        .head(candidate_pool)
        .reset_index(drop=True)
    )
    n_candidates = len(coint_df)

    print(f"\nRunning diagnostics on {n_candidates} p_value-prefiltered candidates "
          f"(rolling window = {window} bars = {window // BARS_PER_DAY}d)...")
    diag_progress_step = max(1, n_candidates // 20)  # ~20 updates, same convention as the scan step above
    rows = []
    for i, row in coint_df.iterrows():
        a, b, pval = row.ticker_a, row.ticker_b, row.p_value
        if (i + 1) % diag_progress_step == 0 or (i + 1) == n_candidates:
            print(f"  diagnosed {i + 1}/{n_candidates} candidates ({(i + 1) / n_candidates:.0%})")
        pair_clean = df[[a, b]].dropna()
        pa, pb = pair_clean[a].values, pair_clean[b].values

        spread, _beta, _alpha = compute_spread(pa, pb)
        hl_bars = half_life(spread)
        H = hurst_exponent(spread)

        # Recent-window companions to the full-history half-life/Hurst above --
        # same idea as recent_cointegrated (full-history stat can hide a recent
        # regime change), but see RECENT_WINDOW_DAYS' docstring: unlike the
        # cointegration case, this one isn't shown to discriminate on the one
        # sample we've checked it against.
        recent_cutoff = pair_clean.index.max() - pd.Timedelta(days=RECENT_WINDOW_DAYS)
        pair_recent = pair_clean[pair_clean.index >= recent_cutoff]
        pa_recent, pb_recent = pair_recent[a].values, pair_recent[b].values
        spread_recent, _, _ = compute_spread(pa_recent, pb_recent)
        hl_bars_recent = half_life(spread_recent)
        H_recent = hurst_exponent(spread_recent)

        roll_beta = rolling_hedge_ratio(pa, pb, window)
        beta_mean = roll_beta.mean()
        beta_std = roll_beta.std()
        beta_cv = beta_std / abs(beta_mean) if beta_mean != 0 else np.inf

        roll_p = rolling_coint(pa, pb, window)
        coint_stability = (roll_p < COINT_PVALUE_THRESHOLD).mean()  # fraction of windows that are cointegrated

        # Recency gate on top of the (order-blind) fraction above -- a pair
        # that cointegrated weeks 1-3 but died in week 4 must NOT read as
        # tradeable just because 3/4 clears the coint_stability bar. Uses a
        # SEPARATE, daily-stride (overlapping) p-value series rather than
        # roll_p's weekly-stride one: roll_p only has ~4 non-overlapping
        # windows over 30 days, so its last 1-2 entries are extremely
        # sensitive to exactly where the 30-day slice's boundary falls --
        # shifting "now" by 12h can flip which calendar days land in which
        # chunk, flipping the verdict on data that barely changed. Daily
        # stride (~24 overlapping windows, same 7-day window size, so no
        # loss of per-test statistical power) gives a real trend to read
        # instead of a coin flip. Mean of the last 3 (not just the latest
        # single window) smooths one-day noise without hiding a genuine
        # multi-day breakdown. Needs >=3 windows to make the claim at all;
        # fewer than that can't confirm a "recent" trend, so it fails
        # closed (np.inf -> False), not open.
        roll_p_fine = rolling_coint(pa, pb, window, stride=BARS_PER_DAY)
        recent_p_signal = roll_p_fine.tail(3).mean() if len(roll_p_fine) >= 3 else np.inf
        recent_cointegrated = bool(recent_p_signal < RECENT_P_THRESHOLD)

        # Liquidity: both legs' own metric, not a pair-level one -- a thin
        # leg makes the PAIR untradeable regardless of how liquid the other
        # side is. Cached per ticker, so this is a cheap lookup after the
        # first candidate involving that ticker.
        turnover_a = _avg_daily_turnover_usd(a)
        turnover_b = _avg_daily_turnover_usd(b)

        rows.append({
            "ticker_a": a,
            "ticker_b": b,
            "p_value": round(pval, 4),
            "half_life_hours": round(hl_bars * BAR_LENGTH / 60, 1) if np.isfinite(hl_bars) else np.inf,
            "hurst": round(H, 3),
            "half_life_hours_recent": round(hl_bars_recent * BAR_LENGTH / 60, 1) if np.isfinite(hl_bars_recent) else np.inf,
            "hurst_recent": round(H_recent, 3) if np.isfinite(H_recent) else np.nan,
            "coint_stability": round(coint_stability, 2),
            "recent_cointegrated": recent_cointegrated,
            "beta_mean": round(beta_mean, 3),
            "beta_cv": round(beta_cv, 3),
            "turnover_a_usd": round(turnover_a) if np.isfinite(turnover_a) else np.nan,
            "turnover_b_usd": round(turnover_b) if np.isfinite(turnover_b) else np.nan,
        })

    # Rank the whole diagnosed pool by coint_stability, not the p_value order
    # it arrived in -- see the module docstring for why p_value is only a
    # pre-filter here, not the metric that should decide "top".
    summary = pd.DataFrame(rows).sort_values(
        "coint_stability", ascending=False, kind="stable"
    ).reset_index(drop=True)

    print(f"\n--- Pair Diagnostics (top {top_n} of {n_candidates}, ranked by coint_stability) ---")
    print(summary.head(top_n).to_string(index=False))

    # Filtered against the FULL diagnosed pool, not just the printed
    # top `top_n` -- a pair passing every threshold shouldn't disappear
    # just because coint_stability ranking put it 11th.
    tradeable = get_tradeable_pairs(summary)
    print()
    if not tradeable.empty:
        print(f"Tradeable candidates (1-120h half-life, H<0.5, coint_stability>=0.3, "
              f"last 2 weekly windows both cointegrated, β_cv<0.6, "
              f"both legs >=${MIN_AVG_DAILY_TURNOVER_USD:,} avg daily turnover), "
              f"{len(tradeable)} of {n_candidates} diagnosed:")
        print(tradeable[["ticker_a", "ticker_b", "half_life_hours", "hurst",
                          "half_life_hours_recent", "hurst_recent", "coint_stability",
                          "recent_cointegrated", "beta_cv", "turnover_a_usd",
                          "turnover_b_usd"]].to_string(index=False))
    else:
        print("No pairs pass all tradeable filters.")

    return summary


if __name__ == "__main__":
    analyze_top_pairs(days=30)
