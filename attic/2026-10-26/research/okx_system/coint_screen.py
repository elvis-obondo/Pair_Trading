"""THE SCREENED UNIVERSE: which pairs are actually related enough to trade.

WHY THIS EXISTS. The trading path has never screened anything.
`universe_panel.tradeable_pairs` is `itertools.combinations` -- all 22,366 pairs
of 212 tickers, filtered for nothing -- and `scanner.py`, `live_scanner.py` and
`run_portfolio_backtest.py` all call it. `pair_analysis.get_tradeable_pairs`,
which does test whether two coins are related, is called only from inside
`pair_analysis.py` itself and has never gated a trade. Every result this project
has ever produced was measured on arbitrary pairs.

That matters because of what the 2026-09-27 measurements showed: the win rate is
28.2% against a 23.3% breakeven for the barriers, so gross expectancy is +0.211
sigma, and the OKX taker round trip costs 0.208 sigma. The bet is exactly at
breakeven, and NOTHING moved the win rate -- not 7 lookbacks, 6 stop widths, 3
ranking keys or 149 threshold combinations. If the pairs have no relationship,
the spread being a driftless walk is the expected result rather than a discovery.
This tests the premise the strategy was built on and never checked.

EVERY TEST HERE IS ORDER-FREE, and that is the substantive change from
pair_analysis. Engle-Granger regresses A on B, so `coint(a,b) != coint(b,a)`.
Measured on 400 random pairs over one 7-day window at p<0.01: 13 pairs pass as
(A,B), 15 as (B,A), and only 8 pass BOTH. Of the 20 that pass either ordering,
60% are decided by alphabetical order -- because `itertools.combinations` picks
the left-hand side and nothing else does. RIVER/ZEC reads p=0.0069 one way and
p=0.7955 the other. Spearman between the two orderings is only +0.65.

That is the same defect as the $626 hedge-ratio band the symmetric estimator was
shipped to kill (see rolling_spread.py), reappearing in the one component meant
to fix the universe -- and worse here, because selection compounds. So:

  cointegration   run BOTH orderings, take the WORSE p-value. A pair must be
                  cointegrated whichever way round you write it.
  beta_cv         from the symmetric ratio beta, not np.polyfit. pair_analysis'
                  rolling_hedge_ratio is OLS of A on B.
  hurst           on a spread built with the symmetric beta. pair_analysis uses
                  compute_spread, a full-window OLS, so its Hurst inherits the
                  asymmetry too.

GATES, and which were dropped. half_life_hours and half_life_hours_recent are
GONE: the OU half-life is fitted at a median 1.09h against dislocations that
widen from 3.30 to 7.09 sigma over 72h, only 16% of trades halve by their own
predicted half-life, and ranking on it is mildly anti-predictive. Four of the
nine original gates were half-life/Hurst; Hurst is kept because it is a separate
estimator that tests trending-versus-reverting directly rather than through
theta.

    hurst < 0.5              full window, on the symmetric spread
    hurst_recent < 0.5       last RECENT_WINDOW_DAYS
    coint_stability >= 0.5   fraction of chunks with worse-p < 0.01
    recent_cointegrated      the most recent chunk's worse-p < 0.2
    beta_cv < 0.6            symmetric rolling beta
    turnover >= $450k/day    BOTH legs

THRESHOLDS ARE NOT RE-DERIVED and most were never validated. pair_analysis says
so itself: COINT_PVALUE_THRESHOLD 0.01 is "not yet at significance given only 62
days / 8 weekly windows"; RECENT_P_THRESHOLD 0.2 came from "one fold, five
pairs"; RECENT_WINDOW_DAYS 14 is "NOT backed by a discriminating result... found
no separation". They are inherited so this run measures the SCREEN, not a fresh
calibration. Re-deriving them on the same 35 days that will score them would be
the fitting mistake this project keeps making.

THE RECENCY GATE IS COARSER THAN pair_analysis'. That one built a separate
daily-stride p-value series because a weekly-stride series has only ~4 windows
and its last entry flips when the slice boundary moves 12h. This uses the last
chunk of the same series. The cost is that boundary sensitivity; the benefit is
that one chunked series serves both gates and the whole screen fits in minutes.
Worth revisiting if the screen survives at all.

CHUNK LENGTH IS THE OPEN QUESTION. 7 days is what pair_analysis used. But the
screen judges on a weekly timescale while the trades it would gate last a median
1.15 hours, and nothing has ever tested whether that mismatch matters. Run both
with --chunk-days and compare the universes and what they trade like.

NO PREFILTER, deliberately. pair_analysis funnels on a single full-window
Engle-Granger and keeps the 3,000 lowest p-values, but its own docstring warns a
raw full-window p-value "is easily dominated by whichever single asset had the
biggest trending move over the window". Testing every pair with the chunked
statistic directly costs LESS (13.8 min against 19.7 for the funnel's stage one,
measured) and carries no prefilter bias. The cheap gates run first instead --
turnover, then Hurst, then beta_cv -- and only survivors pay for cointegration.

Usage:
    python research/coint_screen.py --chunk-days 7 --out research/screen_7d.csv
    python research/coint_screen.py --chunk-days 2 --out research/screen_2d.csv
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
import itertools
import time

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import coint

from universe_panel import load_panel, usable_tickers
from rolling_spread import min_bars_required
import hedge_estimators as he

BARS_PER_DAY = 48
COINT_PVALUE_THRESHOLD = 0.01     # pair_analysis' value, not re-derived
RECENT_P_THRESHOLD = 0.2          # ditto
RECENT_WINDOW_DAYS = 14           # ditto
MIN_AVG_DAILY_TURNOVER_USD = 450_000
HURST_MAX = 0.5
BETA_CV_MAX = 0.6
STABILITY_MIN = 0.5
HURST_LAGS = (2, 4, 8, 16, 32, 64, 128, 256)


def hurst_exponent(spread: np.ndarray) -> float:
    """Variance-ratio Hurst. <0.5 mean-reverting, 0.5 random walk, >0.5 trending.

    Same estimator as pair_analysis.hurst_exponent. Needs 2*max(lag) = 512 bars
    (10.7 days at 30m), and returns NaN rather than raising below that so a short
    pair declines rather than killing the run.
    """
    S = np.asarray(spread, dtype=float)
    S = S[np.isfinite(S)]
    if len(S) < 2 * max(HURST_LAGS):
        return float("nan")
    v = [np.var(S[lag:] - S[:-lag]) for lag in HURST_LAGS]
    if not all(x > 0 for x in v):
        return float("nan")
    slope, _ = np.polyfit(np.log(HURST_LAGS), np.log(v), 1)
    return slope / 2.0


def symmetric_spread(pa: np.ndarray, pb: np.ndarray):
    """Spread under the SHIPPED symmetric hedge, fitted on the whole window.

    The ratio estimator is sd(a)/sd(b) signed by the covariance, so
    beta(A|B)*beta(B|A) == 1 exactly and the spread does not depend on which coin
    was written first. alpha centres it.

    hedge_estimators only exposes ROLLING forms, so the full-window beta is taken
    as the last value of a rolling fit whose window is the whole series -- one
    value, identical arithmetic, and no second definition of the estimator.
    """
    n = len(pa)
    if n < 10:
        return None, np.nan
    beta = float(he.rolling_beta(pa, pb, n, "ratio")[-1])
    if not np.isfinite(beta):
        return None, np.nan
    alpha = float(np.mean(pa) - beta * np.mean(pb))
    return pa - beta * pb - alpha, float(beta)


def rolling_beta_cv(pa: np.ndarray, pb: np.ndarray, window: int) -> float:
    """Coefficient of variation of the SYMMETRIC rolling beta.

    pair_analysis uses np.polyfit(price_b, price_a, 1) -- OLS of A on B -- so its
    beta_cv depends on the argument order. The ratio estimator does not: it is
    sd_a/sd_b, and swapping the legs inverts it, which leaves the CV of the
    inverse rather than a different strategy. Computed with pandas rolling so it
    is one vectorised pass instead of a fit per bar.
    """
    sa = pd.Series(pa).rolling(window).std()
    sb = pd.Series(pb).rolling(window).std()
    with np.errstate(divide="ignore", invalid="ignore"):
        b = (sa / sb).to_numpy()
    b = b[np.isfinite(b)]
    if len(b) < 10 or abs(np.mean(b)) < 1e-12:
        return float("nan")
    return float(np.std(b) / abs(np.mean(b)))


def worse_p(a: np.ndarray, b: np.ndarray) -> float:
    """Engle-Granger both ways, WORSE p-value. Order-free by construction."""
    try:
        _, p1, _ = coint(a, b)
        _, p2, _ = coint(b, a)
    except Exception:
        return float("nan")
    if not (np.isfinite(p1) and np.isfinite(p2)):
        return float("nan")
    return float(max(p1, p2))


def chunked_coint(pa: np.ndarray, pb: np.ndarray, chunk: int):
    """Non-overlapping chunks, worse-p each. Returns (stability, last_p, n)."""
    ps = []
    for i in range(0, len(pa) - chunk + 1, chunk):
        ca, cb = pa[i:i + chunk], pb[i:i + chunk]
        if not (np.isfinite(ca).all() and np.isfinite(cb).all()):
            continue
        p = worse_p(ca, cb)
        if np.isfinite(p):
            ps.append(p)
    if not ps:
        return float("nan"), float("nan"), 0
    ps = np.asarray(ps)
    return float((ps < COINT_PVALUE_THRESHOLD).mean()), float(ps[-1]), len(ps)


def daily_turnover(tickers, start, end) -> pd.Series:
    """Average USD/day from the raw feather store: sum(close*volume)/days."""
    out = {}
    for t in tickers:
        p = f"user_data/data/okx/futures/{t}_USDT_USDT-30m-futures.feather"
        if not os.path.exists(p):
            continue
        d = pd.read_feather(p)[["date", "close", "volume"]]
        d["date"] = pd.to_datetime(d.date).dt.tz_localize(None)
        d = d[(d.date >= start) & (d.date <= end)]
        if len(d) < BARS_PER_DAY:
            continue
        span = max((d.date.max() - d.date.min()).total_seconds() / 86400.0, 1.0)
        out[t] = float((d.close * d.volume).sum() / span)
    return pd.Series(out)


def run(chunk_days=7, days=35, bar_hours=0.5, end_date=None, out_path=None,
        entry_window_days=2.0):
    import rolling_spread as rs
    rs.ENTRY_WINDOW_DAYS = float(entry_window_days)
    need = min_bars_required(bar_hours)
    full = load_panel()
    if end_date:
        full = full.loc[:end_date]
    else:
        print("[WARN] no --end-date. One partially formed trailing 30m bar cuts "
              "the universe from 212 tickers to 17. Pass it.")
    panel = full.tail(need + int(days * 24 / bar_hours))
    tickers = usable_tickers(panel, bar_hours)
    chunk = int(round(chunk_days * 24 / bar_hours))
    rec_bars = int(round(RECENT_WINDOW_DAYS * 24 / bar_hours))
    beta_win = int(round(7 * 24 / bar_hours))
    print(f"[INFO] {len(tickers)} tickers, window {panel.index[0]} -> {panel.index[-1]}")
    # chunked_coint walks the WHOLE panel, warm-up included -- the warm-up is
    # only needed by the rolling geometry, not by a cointegration test on raw
    # levels. So the chunk count is over len(panel), not len(panel)-need. Getting
    # this wrong once made every coint_stability read as k/17 when it was k/19,
    # which mis-stated the null comparison. n_chunks is written per pair; read it
    # from the output rather than recomputing it.
    n_chunks = len(range(0, len(panel) - chunk + 1, chunk))
    print(f"[INFO] chunk {chunk_days}d = {chunk} bars; "
          f"{n_chunks} chunks per pair over {len(panel)} bars")

    print("[INFO] turnover...", flush=True)
    tov = daily_turnover(tickers, panel.index[0], panel.index[-1])
    liquid = sorted(t for t in tickers if tov.get(t, 0.0) >= MIN_AVG_DAILY_TURNOVER_USD)
    print(f"[INFO] turnover >= ${MIN_AVG_DAILY_TURNOVER_USD:,}/day: "
          f"{len(liquid)} of {len(tickers)} tickers")

    arr = {t: panel[t].to_numpy(dtype=float) for t in liquid}
    pairs = list(itertools.combinations(liquid, 2))
    print(f"[INFO] {len(pairs):,} pairs to screen\n", flush=True)

    n_hurst = n_beta = n_coint = 0
    rows = []
    t0 = time.time()
    for k, (a, b) in enumerate(pairs, 1):
        pa, pb = arr[a], arr[b]
        if not (np.isfinite(pa).all() and np.isfinite(pb).all()):
            continue
        sp, beta = symmetric_spread(pa, pb)
        if sp is None:
            continue
        H = hurst_exponent(sp)
        if not (np.isfinite(H) and H < HURST_MAX):
            continue
        sp_r, _ = symmetric_spread(pa[-rec_bars:], pb[-rec_bars:])
        Hr = hurst_exponent(sp_r) if sp_r is not None else float("nan")
        if not (np.isfinite(Hr) and Hr < HURST_MAX):
            continue
        n_hurst += 1
        cv = rolling_beta_cv(pa, pb, beta_win)
        if not (np.isfinite(cv) and cv < BETA_CV_MAX):
            continue
        n_beta += 1
        stab, last_p, nch = chunked_coint(pa, pb, chunk)
        if not np.isfinite(stab):
            continue
        n_coint += 1
        rows.append(dict(ticker_a=a, ticker_b=b, beta=beta, hurst=H,
                         hurst_recent=Hr, beta_cv=cv, coint_stability=stab,
                         last_chunk_p=last_p, n_chunks=nch,
                         turnover_a=tov[a], turnover_b=tov[b]))
        if k % 2000 == 0:
            el = time.time() - t0
            print(f"  {k:,}/{len(pairs):,}  hurst-ok {n_hurst:,}  beta-ok {n_beta:,}  "
                  f"scored {n_coint:,}  {el:.0f}s eta {el/k*(len(pairs)-k):.0f}s",
                  flush=True)

    D = pd.DataFrame(rows)
    print(f"\n[INFO] scored {len(D):,} pairs in {time.time()-t0:.0f}s")
    if D.empty:
        print("[WARN] nothing survived the cheap gates.")
        return D
    D["recent_cointegrated"] = D.last_chunk_p < RECENT_P_THRESHOLD
    D["tradeable"] = (D.coint_stability >= STABILITY_MIN) & D.recent_cointegrated

    print("\n" + "=" * 92)
    print(f"THE FUNNEL  (chunk {chunk_days}d, order-free tests)")
    print("=" * 92)
    n_all = len(tickers) * (len(tickers) - 1) // 2
    print(f"  all pairs of the traded universe            {n_all:>8,}")
    print(f"  both legs >= ${MIN_AVG_DAILY_TURNOVER_USD:,}/day        {len(pairs):>8,}"
          f"   ({100*len(pairs)/n_all:.1f}%)")
    print(f"  hurst < {HURST_MAX} and hurst_recent < {HURST_MAX}        {n_hurst:>8,}"
          f"   ({100*n_hurst/n_all:.1f}%)")
    print(f"  beta_cv < {BETA_CV_MAX} (symmetric beta)             {n_beta:>8,}"
          f"   ({100*n_beta/n_all:.1f}%)")
    print(f"  coint_stability >= {STABILITY_MIN}                     "
          f"{int((D.coint_stability>=STABILITY_MIN).sum()):>8,}"
          f"   ({100*(D.coint_stability>=STABILITY_MIN).sum()/n_all:.1f}%)")
    print(f"  ... AND recent_cointegrated (p<{RECENT_P_THRESHOLD})      "
          f"{int(D.tradeable.sum()):>8,}   ({100*D.tradeable.sum()/n_all:.2f}%)")
    T = D[D.tradeable]
    print(f"\n  TRADEABLE: {len(T):,} pairs across "
          f"{len(set(T.ticker_a) | set(T.ticker_b)) if len(T) else 0} tickers")
    if len(T):
        print(f"    median coint_stability {T.coint_stability.median():.2f}   "
              f"median hurst {T.hurst.median():.3f}   median |beta| "
              f"{T.beta.abs().median():.3f}   median beta_cv {T.beta_cv.median():.3f}")
        print(f"    most frequent tickers: "
              f"{pd.concat([T.ticker_a, T.ticker_b]).value_counts().head(8).to_dict()}")
        print(f"\n  CAN IT FILL TEN SLOTS? {len(T):,} pairs is "
              f"{'plenty' if len(T) >= 200 else 'THIN -- check the trigger rate' if len(T) >= 30 else 'almost certainly too few'}")
    if out_path:
        D.to_csv(out_path, index=False)
        print(f"\n[INFO] all {len(D):,} scored pairs written to {out_path}")
        print(f"       filter on `tradeable` for the allow-list")
    print("=" * 92)
    return D


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunk-days", type=float, default=7.0)
    ap.add_argument("--days", type=int, default=35)
    ap.add_argument("--end-date", type=str, default=None)
    ap.add_argument("--entry-window-days", type=float, default=2.0)
    ap.add_argument("--out", type=str, default=None)
    a = ap.parse_args()
    run(chunk_days=a.chunk_days, days=a.days, end_date=a.end_date,
        out_path=a.out, entry_window_days=a.entry_window_days)
