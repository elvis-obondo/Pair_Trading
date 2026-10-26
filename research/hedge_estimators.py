"""Three rolling hedge-ratio estimators, and why the labelling one is arbitrary.

THE PROBLEM THIS MODULE EXISTS FOR

`rolling_spread.rolling_beta_alpha` is OLS of A on B. OLS has a left-hand side,
and which coin is the left-hand side is decided by `itertools.combinations` in
`universe_panel.tradeable_pairs` -- alphabetical order. Randomising that choice
moves end equity across a $626 band on a 35-day window, which is larger than
any parameter effect ever measured on this system. The reason is exact:

    beta(A|B) * beta(B|A) = r2

so the two labellings agree only as far as the fit is good, and the median fit
here is r2 = 0.31. Flipping does not re-scale a hedge on the same positions; it
selects a different strategy.

A SYMMETRIC ESTIMATOR REMOVES THE CHOICE RATHER THAN FILTERING FOR PAIRS WHERE
IT HAPPENS NOT TO MATTER. For both symmetric estimators here

    beta(A|B) * beta(B|A) = 1

identically, so the pair is genuinely unordered and the noise band collapses.
That is a methodological gain, not an edge -- see MEASURED, below.

THE THREE

  ols    beta = cov(a,b)/var(b). The current rule. Asymmetric, and biased toward
         zero by errors-in-variables: it assumes B is measured without error,
         which for the log price of a crypto perp is false.

  tls    Total least squares / orthogonal regression -- the principal
         eigenvector of the 2x2 covariance. Symmetric. Corrects the attenuation,
         which makes |beta| much LARGER (median 2.63 against OLS's 0.41).
         Assumes equal error variance in both legs, which is questionable when
         two coins have very different volatilities.

  ratio  beta = sd(a)/sd(b), signed by the covariance. Symmetric, scale-free,
         and it does not try to estimate a relationship at all -- it equalises
         each leg's volatility contribution. That is the point: with a median
         r2 of 0.31 there is little relationship to estimate, and this
         estimator does not pretend otherwise. The spread becomes a vol-matched
         difference whose variance is 2*var(a)*(1-corr), so its sigma encodes
         the correlation directly.

MEASURED (1200-1500 pairs, 35 days to 2026-09-21, 1-minute exit checking, costs
charged per episode as FRAC*(1+|beta|), liquidation at (1+|beta|)/leverage
enforced, day-clustered 95% CI over 35 day-blocks). Paired against OLS at the
same stop width:

    stop 0.5 sigma   ratio +0.133 R [+0.023, +0.228]   tls +0.023 [-0.110, +0.128]
    stop 1.0 sigma   ratio +0.112 R [+0.017, +0.183]   tls +0.082 [-0.027, +0.155]
    stop 2.0 sigma   ratio +0.075 R [+0.004, +0.130]   tls +0.065 [-0.029, +0.136]
    stop 3.0 sigma   ratio +0.060 R [+0.008, +0.104]   tls +0.059 [-0.019, +0.119]

`ratio` separates at every width; `tls` at none. TLS wins on gross barrier odds
and loses it all to costs: cost scales with (1+|beta|) and its beta is ~6x OLS,
so it pays 0.349 R per trade against ratio's 0.166 and OLS's 0.138.

NONE OF THE THREE IS PROFITABLE. The best cell measured is ratio at a 3.0-sigma
stop, -0.083 R [-0.229, +0.059], and at that width liquidation binds on 35% of
episodes. At the live-relevant 1.0 sigma, ratio is -0.178 R [-0.345, -0.008] --
better than OLS and still losing. Read this as "OLS is actively harmful", not
as "ratio is an edge".

NOT WIRED INTO THE TRADING PATH. Switching estimators changes beta, hence the
spread, hence sigma, hence which pairs clear the entry threshold -- and it
decalibrates the 3.0 and 0.5 constants, which came from a rolling 7-day OLS fit
in exit_sweep.py. rolling_spread.py exists because those thresholds were once
applied to a ruler 2.17x away. Re-derive before wiring.
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

ESTIMATORS = ("ols", "tls", "ratio")
SYMMETRIC = ("tls", "ratio")


def rolling_moments(a: np.ndarray, b: np.ndarray, window: int):
    """(var_a, var_b, cov, mean_a, mean_b) over the window ENDING at each index.

    ddof=1 throughout, matching rolling_spread's sigma -- a ddof mismatch shifts
    every z-score by sqrt(w/(w-1)) and quietly decalibrates the entry threshold.
    """
    sa, sb = pd.Series(a), pd.Series(b)
    return (sa.rolling(window).var().to_numpy(),
            sb.rolling(window).var().to_numpy(),
            sa.rolling(window).cov(sb).to_numpy(),
            sa.rolling(window).mean().to_numpy(),
            sb.rolling(window).mean().to_numpy())


def rolling_beta(a: np.ndarray, b: np.ndarray, window: int,
                 estimator: str = "ols") -> np.ndarray:
    """Rolling hedge ratio of a against b, by the named estimator.

    Nothing looks forward: index i uses bars (i-window, i] only, so an array
    computed over a whole history can be sliced anywhere and still equals what
    was computable live at that bar. Positions before the first full window are
    NaN rather than fitted on partial data.
    """
    if estimator not in ESTIMATORS:
        raise ValueError(f"estimator must be one of {ESTIMATORS}, got {estimator!r}")
    vaa, vbb, vab, _, _ = rolling_moments(a, b, window)
    with np.errstate(invalid="ignore", divide="ignore"):
        if estimator == "ols":
            return vab / vbb
        if estimator == "tls":
            # Principal eigenvector slope of [[vaa, vab], [vab, vbb]]. The sign
            # of vab carries through, so a negatively correlated pair still
            # returns a negative beta -- symmetry does NOT rescue the 25% of
            # episodes where both legs end up on the same side.
            #
            # TWO ALGEBRAICALLY IDENTICAL FORMS, AND THE CHOICE IS NOT COSMETIC.
            # With d = vaa - vbb and disc = sqrt(d^2 + 4*vab^2),
            #
            #     (d + disc) / (2*vab)   ==   2*vab / (disc - d)
            #
            # The left form cancels catastrophically when d < 0 and |vab| is
            # small: it subtracts two nearly equal positive numbers. The right
            # form cancels when d > 0. Taking each on the branch where its terms
            # share a sign keeps full precision, and the difference is visible --
            # the naive left form alone breaks the exact symmetry this estimator
            # exists for, by ~3e-06 on real pairs. The validator checks the
            # identity beta(a,b)*beta(b,a) == 1 to 1e-9 for exactly this reason.
            d = vaa - vbb
            disc = np.sqrt(d ** 2 + 4.0 * vab ** 2)
            return np.where(d >= 0.0,
                            (d + disc) / (2.0 * vab),
                            2.0 * vab / (disc - d))
        return np.sqrt(vaa / vbb) * np.sign(vab)


def rolling_beta_alpha(a: np.ndarray, b: np.ndarray, window: int,
                       estimator: str = "ols"):
    """(beta, alpha). alpha centres the spread the same way for every estimator."""
    beta = rolling_beta(a, b, window, estimator)
    _, _, _, ma, mb = rolling_moments(a, b, window)
    return beta, ma - beta * mb


def cost_in_spread_units(beta, cost_frac: float) -> np.ndarray:
    """Round-trip cost as a spread distance, which is what R must be net of.

    The dollar cost is cost_frac * GROSS while P&L is spread_move * leg_a, and
    gross/leg_a = 1 + |beta|. So the cost is cost_frac*(1+|beta|) in spread
    units -- it grows with |beta|, which is exactly the tax that cancels TLS's
    advantage.

    This is also the bug in Position.pnl: net_pct subtracts cost_frac alone,
    charging the round trip on leg A's notional while the constant is defined on
    gross. Every historical R is flattered by cost_frac*|beta|.
    """
    return cost_frac * (1.0 + np.abs(np.asarray(beta, dtype=float)))


def liquidation_distance(beta, leverage: float) -> np.ndarray:
    """Spread move that wipes the posted margin, in spread units.

    gross = leverage * margin and P&L = move * leg_a, so the margin is gone at
    move = gross/(leverage*leg_a) = (1+|beta|)/leverage. A stop placed further
    away than this never fills: the exchange closes the position first.

    Note the direction: a LARGER |beta| means a smaller leg A, so a given spread
    move costs less relative to gross and there is MORE headroom. Measured
    medians: OLS 2.96 sigma, ratio 3.65, TLS 4.91.
    """
    return (1.0 + np.abs(np.asarray(beta, dtype=float))) / float(leverage)
