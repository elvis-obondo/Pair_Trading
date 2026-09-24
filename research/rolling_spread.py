"""Rolling 7-day hedge ratio and spread statistics — the live entry geometry.

THE HEDGE RATIO IS SYMMETRIC (changed 2026-09-24). Read this first.

This module used to fit OLS of A on B. OLS has a left-hand side, and which coin
is the left-hand side was decided by `itertools.combinations` in
`universe_panel.tradeable_pairs` — alphabetical order, and nothing else.

That was not a detail. `beta(A|B) * beta(B|A) = r2` exactly, and the median r2
here is 0.31, so the two labellings do not describe one hedge at two scales —
they select different strategies. Randomising the choice moved end equity across
a $626 band on a 35-day window, larger than any parameter effect ever measured
on this system, and only 56 of ~1000 trades were common to the two arms.

The ratio estimator, `beta = sd(a)/sd(b)` signed by the covariance, satisfies
`beta(A|B) * beta(B|A) = 1` exactly. The pair is genuinely unordered, so the
band collapses to nothing rather than being filtered down. See
`research/hedge_estimators.py` for the other two estimators, the identities and
the measurement; `validate_hedge_estimators.py` checks the identity to 2.22e-16.

WHY THIS ESTIMATOR AND NOT TOTAL LEAST SQUARES. TLS is also exactly symmetric
and wins on gross barrier odds, then hands it all back in fees: the round-trip
cost is charged on GROSS, so in spread units it is frac*(1+|beta|), and TLS beta
is ~6x OLS. It pays 0.349 R per trade against ratio's 0.166 and OLS's 0.138.
Paired against OLS at the same stop width, 1-minute exits, costs charged per
episode and liquidation enforced, day-clustered over 35 day-blocks:

    stop 0.5   ratio +0.133 [+0.023, +0.228]   tls +0.023 [-0.110, +0.128]
    stop 1.0   ratio +0.112 [+0.017, +0.183]   tls +0.082 [-0.027, +0.155]
    stop 2.0   ratio +0.075 [+0.004, +0.130]   tls +0.065 [-0.029, +0.136]
    stop 3.0   ratio +0.060 [+0.008, +0.104]   tls +0.059 [-0.019, +0.119]

ratio separates at every width; tls at none. OLS is not merely neutral either —
it reverts 3.70pp BELOW the driftless two-barrier rate for its own |z|
[-5.43, -1.69], so it was actively harmful.

WHAT THIS DOES NOT CLAIM. It is not an edge. The best cell measured is ratio at
a 3.0-sigma stop, -0.083 R [-0.229, +0.059], and liquidation binds on 35% of
those episodes. At the live 1.0 sigma, ratio is -0.178 R [-0.345, -0.008]:
better than OLS and still losing. The change was made because OLS is worse and
because it makes the system MEASURABLE, not because it is profitable.

WHAT ELSE MOVED, mechanically, with no code change of its own. median |beta|
0.413 -> 1.262, so sizing shifts (`leg_a = gross/(1+|beta|)`: 71% of gross ->
44%); median sigma 0.0245 -> 0.0326; dollar-neutrality improves (|1-beta|
/(1+|beta|) median 0.583 -> 0.368) because vol-matching lands beta near 1; and
liquidation moves further away (2.96 -> 3.65 median sigma of headroom).

THE THRESHOLDS WERE NOT RE-DERIVED, deliberately. 3.0 and 0.5 were scored on
exit_sweep's rolling 7-day OLS fit, so this geometry is no longer the one they
were calibrated against — the failure mode this module was written to prevent.
It is accepted here for one reason: the comparison above is PAIRED at each stop
width, and ratio wins at 0.5 and 1.0 as well as wide. The thresholds are still
worth re-deriving; the switch does not depend on it.

NO STORED R IS COMPARABLE ACROSS THIS CHANGE. beta, the spread, sigma and which
pairs clear the entry threshold all move, so the backtest needs a fresh
baseline. `MEASURED_STOP_OVERSHOOT = 1.04` was derived on OLS geometry at 0.5
sigma and must be re-derived from the live ledger.

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

import hedge_estimators as he

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


# The shipped hedge ratio. Named rather than inlined so it is greppable and so
# there is exactly one place that decides it. hedge_estimators also defines
# "ols" and "tls"; they exist to reproduce the measurement in this module's
# docstring and are NOT alternate trading paths.
HEDGE_ESTIMATOR = "ratio"


def rolling_beta_alpha(a: np.ndarray, b: np.ndarray, window: int):
    """Rolling SYMMETRIC hedge ratio of a against b, vectorised.

    beta = sd(a)/sd(b) signed by the covariance, alpha = mean(a) - beta*mean(b),
    both from the window ENDING at each index -- so index i uses bars
    (i-window, i] and never anything after i. Positions before the first full
    window are NaN rather than fitted on partial data: a hedge ratio from three
    bars is not a hedge ratio, and letting those through would put fake rows at
    the start of every pair's history.

    WHAT THE ESTIMATOR DOES AND DOES NOT ASSUME. It does not try to estimate a
    relationship; it equalises each leg's volatility contribution. With a median
    r2 of 0.31 there is little relationship to estimate, and pretending
    otherwise is what OLS did. The spread becomes a vol-matched difference whose
    variance is 2*var(a)*(1-corr), so its sigma encodes the correlation directly.

    TWO CONSEQUENCES WORTH NAMING, both improvements on OLS:

      A near-zero beta is now unreachable. OLS returned a tiny beta whenever the
      covariance was small -- and beta ~ 0 means leg B is nothing and the
      position is a naked bet on A, which was the worst-performing decile of the
      whole dislocation study (-0.663 R). sd(a)/sd(b) can only reach zero at
      exactly zero covariance, which is measure-zero.

      A negative beta is NOT fixed. The sign comes from the covariance, so a
      negatively correlated pair still puts both legs on the same side -- 25% of
      episodes, -0.535 R. Symmetry does not rescue that; nothing here does.

    Delegates to hedge_estimators so the estimator has one definition and its
    identities are checked in one validator.
    """
    return he.rolling_beta_alpha(a, b, window, HEDGE_ESTIMATOR)


def rolling_r2(a: np.ndarray, b: np.ndarray, window: int) -> np.ndarray:
    """Rolling squared correlation of a and b -- the fit quality of the hedge.

    corr(a,b)**2, computed from the moments in one pass. IT IS ALREADY
    SYMMETRIC: swapping a and b leaves cov**2/(var_a*var_b) unchanged, so this
    needed no change when the hedge ratio became symmetric and it is directly
    comparable across the switch.

    WHAT IT NO LONGER IS. Under the old OLS hedge this number was also the
    regression's R-squared, and the identity `beta(A|B)*beta(B|A) = r2` held --
    which is exactly why the arbitrary A/B labelling moved end equity across a
    $626 band. The shipped estimator satisfies `beta(A|B)*beta(B|A) = 1`
    instead, so r2 is now a fit diagnostic and nothing more. Do not read it as
    an attenuation factor any more.

    WHY IT IS RECORDED

    beta alone does not say whether B hedges A. The vol-matched beta is near 1
    by construction for similar-volatility coins, so it looks like a hedge
    whether or not the two move together; r2 is what distinguishes those. A
    beta near 1 with an r2 near 0 is two unrelated coins in equal size.
    Recorded, not gated -- see generate_entry_signal Step 4.

    Measured on 206,935 dislocation episodes: median r2 0.309, and R rises
    monotonically across all ten r2 deciles (-0.572 to +0.111 at 1-minute
    exits). It is a real discriminator and it was never enough on its own.
    """
    sa = pd.Series(a)
    sb = pd.Series(b)
    cov = sa.rolling(window).cov(sb)
    var_a = sa.rolling(window).var()
    var_b = sb.rolling(window).var()
    with np.errstate(divide="ignore", invalid="ignore"):
        r2 = (cov ** 2) / (var_a * var_b)
    return r2.to_numpy()


class RollingSpread(NamedTuple):
    """Per-bar rolling spread geometry. All arrays share the input's length."""
    spread: np.ndarray   # a - beta*b - alpha, under that bar's own fit
    beta:   np.ndarray   # rolling hedge ratio
    alpha:  np.ndarray   # rolling intercept
    mu:     np.ndarray   # rolling mean of the spread
    sigma:  np.ndarray   # rolling std of the spread -- THE unit for entry/stop/sizing
    z:      np.ndarray   # (spread - mu) / sigma
    r2:     np.ndarray   # fit quality of the hedge; recorded, never a gate


class SpreadPoint(NamedTuple):
    """One bar's geometry, for the single-pair live/backtest path."""
    spread: float
    beta:   float
    alpha:  float
    mu:     float
    sigma:  float
    z:      float
    r2:     float


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
    blank = RollingSpread(nan, nan.copy(), nan.copy(), nan.copy(), nan.copy(),
                          nan.copy(), nan.copy())

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

    r2 = rolling_r2(a, b, window)

    return RollingSpread(spread, beta, alpha, mu, sigma, z, r2)


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
    # r2 is deliberately OUTSIDE the finite check above. It is a diagnostic, not
    # a gate, and letting a NaN R-squared decline an otherwise well-determined
    # bar would silently change which trades the strategy takes.
    return SpreadPoint(*(float(v) for v in vals), float(r.r2[-1]))
