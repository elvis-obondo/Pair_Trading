"""Rolling 7-day hedge ratio and spread statistics — the live entry geometry.

WHY THIS EXISTS

The settled configuration measures every distance in the 7-day ROLLING standard
deviation of the spread, not in the OU stationary sigma
(`sigma / sqrt(2*theta)`) the live path used before. Entry fires at 3.0 rolling
sigma from mu, the adverse stop sits 0.5 rolling sigma beyond the entry spread,
and the take-profit is full reversion to mu.

Those numbers come from `research/exit_sweep.py`, which built every candidate
trade on a rolling 7-day fit. Reproducing them live means reproducing that fit
exactly, not approximating it with a full-window OLS (`pair_analysis.compute_spread`)
and a different volatility unit. This module is the single definition both sides
use, so research and live cannot drift apart.

Note `exit_sweep.py`'s STOP_GRID comment calls its stops "stationary sigma". The
code on the same page divides by the rolling std. The code is what produced the
results; the comment was wrong.

WHY THE ARRAY FORM

`rolling_spread_stats` returns full arrays even though the live single-pair path
only ever reads the last bar. The scanner (build-order item 3) has to z-screen
22,366 pairs per bar and can only do that vectorised — a scalar-at-a-time helper
would have to be thrown away and rewritten. `last_bar` is a thin wrapper over the
array form for the single-pair callers.

DEGENERATE INPUT returns NaN rather than raising, following compute_spread's
precedent: every consumer on the hot path already screens for NaN, so a bad
window declines to trade while the run continues. Raising would throw away every
remaining bar for that pair.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typing import NamedTuple

import numpy as np
import pandas as pd

# 7 days matches rolling_coint's default and the window every research dataset
# was built on. Expressed in days, not bars, so it survives a timeframe change.
ENTRY_WINDOW_DAYS = 7


def entry_window_bars(bar_hours: float) -> int:
    """Bars covering ENTRY_WINDOW_DAYS of real time at this bar frequency.

    336 at 30-minute bars, which is what every research dataset used.
    """
    return int(round(ENTRY_WINDOW_DAYS * 24 / bar_hours))


def min_bars_required(bar_hours: float) -> int:
    """Shortest history that yields ONE finite bar of rolling geometry.

    TWO windows, not one, and the reason is easy to miss. The spread is built
    from a rolling hedge ratio, so `spread` is itself NaN for the first
    window-1 bars. Taking a rolling mean/std OF that series therefore needs
    another full window of finite spread values on top -- the first finite mu
    and sigma land at index 2*window - 2, so 2*window - 1 bars are needed.

    Hand a caller exactly one window and every statistic comes back NaN, the
    entry signal declines on every bar, and the run looks like "the threshold
    was never crossed" rather than "the window was too short". That failure is
    silent by construction, which is why this is a named, exported requirement
    and not a comment: min_bars on both trading paths is derived from it.

    exit_sweep.py never hit this because it runs on years of history and
    explicitly skips bars whose mu/sigma are not finite.
    """
    return 2 * entry_window_bars(bar_hours) - 1


def rolling_beta_alpha(a: np.ndarray, b: np.ndarray, window: int):
    """Rolling OLS of a on b over `window` bars, vectorised.

    beta = cov(a,b)/var(b), alpha = mean(a) - beta*mean(b), both computed from
    the window ENDING at each index -- so index i uses bars (i-window, i], and
    never anything after i. Positions before the first full window are NaN
    rather than fitted on partial data: a hedge ratio from three bars is not a
    hedge ratio, and letting those through would put fake rows at the start of
    every pair's history.
    """
    sa = pd.Series(a)
    sb = pd.Series(b)
    mean_a = sa.rolling(window).mean()
    mean_b = sb.rolling(window).mean()
    cov = sa.rolling(window).cov(sb)
    var_b = sb.rolling(window).var()
    beta = cov / var_b
    alpha = mean_a - beta * mean_b
    return beta.to_numpy(), alpha.to_numpy()


class RollingSpread(NamedTuple):
    """Per-bar rolling spread geometry. All arrays share the input's length."""
    spread: np.ndarray   # a - beta*b - alpha, under that bar's own fit
    beta:   np.ndarray   # rolling hedge ratio
    alpha:  np.ndarray   # rolling intercept
    mu:     np.ndarray   # rolling mean of the spread
    sigma:  np.ndarray   # rolling std of the spread -- THE unit for entry/stop/sizing
    z:      np.ndarray   # (spread - mu) / sigma


class SpreadPoint(NamedTuple):
    """One bar's geometry, for the single-pair live/backtest path."""
    spread: float
    beta:   float
    alpha:  float
    mu:     float
    sigma:  float
    z:      float


def rolling_spread_stats(price_a: np.ndarray,
                         price_b: np.ndarray,
                         bar_hours: float = 0.5) -> RollingSpread:
    """Rolling hedge ratio and spread statistics over a 7-day trailing window.

    price_a/price_b are LOG prices (what data_loader.get_price_levels returns),
    so the spread is already a return and a spread move of x is a fractional
    P&L of x on the leg-A notional. That is why `sigma` can be read directly as
    a percent-of-notional stop distance with no conversion.

    Every statistic at index i uses only bars (i-window, i]. Nothing looks
    forward, so an array computed over a whole history can be sliced at any
    point and still equals what would have been computable live at that bar.

    Returns all-NaN arrays (not an exception) if the inputs are too short,
    mismatched, or non-finite.
    """
    a = np.asarray(price_a, dtype=float)
    b = np.asarray(price_b, dtype=float)
    n = len(a)
    nan = np.full(n, np.nan)
    blank = RollingSpread(nan, nan.copy(), nan.copy(), nan.copy(), nan.copy(), nan.copy())

    window = entry_window_bars(bar_hours)
    if n != len(b) or n < min_bars_required(bar_hours):
        return blank
    if not (np.isfinite(a).all() and np.isfinite(b).all()):
        return blank

    beta, alpha = rolling_beta_alpha(a, b, window)
    spread = a - beta * b - alpha
    s = pd.Series(spread)
    mu = s.rolling(window).mean().to_numpy()
    # ddof=1, pandas' default -- exit_sweep.py built its `sigma` column the same
    # way. A ddof mismatch would shift every z-score by sqrt(336/335) and quietly
    # decalibrate the 3.0 entry threshold against the grid it was scored on.
    sigma = s.rolling(window).std().to_numpy()

    with np.errstate(divide="ignore", invalid="ignore"):
        z = np.where(sigma > 0, (spread - mu) / sigma, np.nan)

    return RollingSpread(spread, beta, alpha, mu, sigma, z)


def last_bar(price_a: np.ndarray,
             price_b: np.ndarray,
             bar_hours: float = 0.5) -> SpreadPoint | None:
    """Geometry at the most recent bar, or None if it is not fully determined.

    None rather than a NaN-filled tuple because the single-pair callers treat
    "cannot compute" as "do not trade", and an explicit None is harder to
    accidentally arithmetic with than a NaN.
    """
    r = rolling_spread_stats(price_a, price_b, bar_hours)
    vals = (r.spread[-1], r.beta[-1], r.alpha[-1], r.mu[-1], r.sigma[-1], r.z[-1])
    if not all(np.isfinite(v) for v in vals):
        return None
    if r.sigma[-1] <= 0:
        return None
    return SpreadPoint(*(float(v) for v in vals))
