import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
from typing import NamedTuple
from scipy.stats import jarque_bera
from scipy.stats import t as t_dist
from scipy.stats import norm
from statsmodels.stats.diagnostic import acorr_ljungbox
from pair_analysis import compute_spread


# Bounds for the Student-t degrees-of-freedom fit in _fit_student_t_df.
# Lower bound: below df=2 the t-distribution's population variance is
# undefined/explosive, so keeping a margin above that avoids the MLE
# optimizer landing in a region where the scale estimate is unstable.
# Upper bound: a t with df=60 is visually indistinguishable from Gaussian,
# so there's nothing gained by letting the optimizer wander further out.
STUDENT_T_DF_BOUNDS = (2.5, 60.0)


class OUParams(NamedTuple):
    theta:     float      # mean reversion speed (per hour)
    mu:        float      # long-run mean of the spread (log-price units, per compute_spread)
    sigma:     float      # volatility of the spread (log-price units, per compute_spread)
    df:        float      # Student-t degrees of freedom fit to the OLS residuals (tail
                           # heaviness; large values ~ Gaussian, small values ~ fat tails).
                           # Does not redefine sigma -- sigma stays the empirical residual
                           # std regardless of df. See _fit_student_t_df.
    residuals: np.ndarray  # raw per-bar OLS residuals (dS - fitted) the fit was estimated
                           # from, in the same raw (pre bar_hours-rescale) units as the AR(1)
                           # regression. Threaded through so callers can bootstrap-resample
                           # them for Monte Carlo reversion-probability estimation instead of
                           # assuming a parametric residual shape (see ou_reversion_probability).


class OUResidualDiagnostics(NamedTuple):
    jb_stat:         float
    jb_p:            float
    lb_stat:         float
    lb_p:            float
    skewness:        float
    excess_kurtosis: float
    theta_tstat:     float
    theta_p:         float


def _fit_ou_internals(S: np.ndarray) -> dict | None:
    dS    = S[1:] - S[:-1]
    S_lag = S[:-1]

    lam, c    = np.polyfit(S_lag, dS, 1)
    residuals = dS - (c + lam * S_lag)

    n      = len(S_lag)
    sigma2 = np.sum(residuals ** 2) / (n - 2)
    SS_lag = np.sum((S_lag - np.mean(S_lag)) ** 2)
    if SS_lag == 0:
        return None

    lam_se = float(np.sqrt(sigma2 / SS_lag))
    return {"lam": float(lam), "c": float(c), "residuals": residuals, "lam_se": lam_se}


def _fit_student_t_df(
    residuals: np.ndarray, df_bounds: tuple[float, float] = STUDENT_T_DF_BOUNDS
) -> float:
    """MLE-fit the Student-t degrees of freedom (tail shape) of OU residuals.

    Fits (df, scale) jointly via scipy.stats.t.fit with loc fixed at 0 -- OLS
    residuals are already centered by construction. This only supplies the
    tail-shape parameter; sigma (used everywhere else in this module) stays
    the empirical np.std(residuals) and is not redefined by this fit.

    Falls back to df_bounds[1] (~Gaussian) if the optimizer fails to converge
    or returns a non-finite value, so a bad fit degrades to the old Gaussian
    assumption rather than propagating NaN into every downstream caller.
    """
    try:
        df_fit, _loc, _scale = t_dist.fit(residuals, floc=0.0)
    except Exception:
        return float(df_bounds[1])
    if not np.isfinite(df_fit):
        return float(df_bounds[1])
    return float(np.clip(df_fit, df_bounds[0], df_bounds[1]))


def fit_ou(price_a: np.ndarray, price_b: np.ndarray, bar_hours: float = 1.0) -> OUParams:
    """Fit an Ornstein-Uhlenbeck model to the spread implied by price_a and price_b.

    Computes the spread via OLS (price_a - alpha - beta * price_b), then estimates
    the three OU parameters from the discretised process dS = -theta*(S - mu)*dt + sigma*dW
    using OLS on consecutive spread values.

    Parameters
    ----------
    price_a, price_b:
        1-D float arrays of log-prices sampled every `bar_hours` hours, equal length.
    bar_hours : float, default 1.0
        Real time, in hours, between consecutive samples in price_a/price_b. The
        raw AR(1) regression is fit in bar units (dt=1 bar); theta and sigma are
        then rescaled by bar_hours so they're genuinely per-hour/per-sqrt-hour
        regardless of the sampling frequency. Default 1.0 preserves prior
        behavior for callers passing hourly bars.

    Returns
    -------
    OUParams with:
        theta -- mean-reversion speed (per hour); larger values mean faster pull toward mu.
        mu    -- long-run mean of the spread (spread units: price_a - beta * price_b).
                 In practice price_a/price_b are log prices (see compute_spread),
                 so mu/sigma read as log-ratio units, not raw price differences.
        sigma -- spread volatility (spread units per sqrt(hour)).
        df    -- Student-t degrees of freedom fit to the OLS residuals (tail
                 heaviness). See _fit_student_t_df.
        residuals -- raw per-bar OLS residuals the fit was estimated from, in
                 pre-rescale (dt=1 bar) units. For bootstrap-resampling in
                 ou_reversion_probability's Monte Carlo path.

    Returns OUParams(nan, nan, nan, nan, empty array) if:
        - Fewer than 3 finite spread values remain after stripping non-finite entries, or
        - The fitted theta is <= 0, meaning the spread does not mean-revert.
    """
    spread, _beta, _alpha = compute_spread(price_a, price_b)

    S = np.asarray(spread, dtype=float)
    S = S[np.isfinite(S)]
    if len(S) < 3:
        return OUParams(np.nan, np.nan, np.nan, np.nan, np.array([]))

    internals = _fit_ou_internals(S)
    if internals is None:
        return OUParams(np.nan, np.nan, np.nan, np.nan, np.array([]))

    lam, c = internals["lam"], internals["c"]

    theta_raw = -lam
    if theta_raw <= 0:
        return OUParams(np.nan, np.nan, np.nan, np.nan, np.array([]))

    mu        = c / theta_raw  # time-unit invariant, computed before rescaling
    residuals = internals["residuals"]
    sigma_raw = float(np.std(residuals))
    df        = _fit_student_t_df(residuals)

    theta = theta_raw / bar_hours
    sigma = sigma_raw / np.sqrt(bar_hours)

    return OUParams(theta=theta, mu=mu, sigma=sigma, df=df, residuals=residuals)


# EWMA half-life multiplier: how many multiples of the pair's OWN reference
# half-life (see fit_ou_ewma) the exponential decay's memory should span.
# 2.0x -- swept 1.0-5.0x in a single-window, 7-pair, 8-config backtest sweep
# on 2026-08-20 (research/ab_sweep3_logs, research/ab_sweep3_results.csv):
# net P&L peaked at 1.0-2.0x and degraded steadily above 3.0x, going negative
# (worse than not using EWMA at all) by 5.0x -- a bigger multiplier means
# slower decay, which drags the estimate back toward the static full-window
# fit's own weaknesses. 2.0x was picked from that range (not 1.0x, the
# single best point in that one sweep) as a small margin against overfitting
# the exact peak of one window's noise; re-validate if this stops looking
# stable across other windows -- see fit_ou_ewma's own backtest validation.
EWMA_HALFLIFE_MULTIPLIER = 2.0


def fit_ou_ewma(
    price_a: np.ndarray, price_b: np.ndarray,
    bar_hours: float = 1.0,
    halflife_multiplier: float = EWMA_HALFLIFE_MULTIPLIER,
    min_bars: int = 20,
    fit_df: bool = True,
) -> OUParams:
    """Exponentially-weighted alternative to fit_ou(): re-estimates the AR(1)
    coefficients (c, lam) bar-by-bar, weighting recent observations more than
    old ones via exponential decay, instead of fit_ou's single OLS fit over
    the whole window.

    Pair-adaptive half-life: the EWMA decay constant is NOT a fixed number of
    days -- it's set to halflife_multiplier times a REFERENCE half-life
    derived from a one-off static fit_ou()-style OLS fit on the same window
    (used only to set the decay rate, not returned). A fast-reverting pair
    gets a fast-updating EWMA; a slow pair gets a slower one, rather than one
    global constant applied to every pair regardless of its own timescale.
    halflife_multiplier=2.0 (EWMA_HALFLIFE_MULTIPLIER's default -- see its
    comment for the backtest sweep behind this value) sits where P&L peaked
    across a 1.0-5.0x sweep: long enough that the estimator isn't just
    noise-chasing bar to bar, short enough that it actually adapts within a
    pair's own reversion timescale instead of drifting back toward the
    static fit's own weaknesses (which is what happened at the high end of
    that sweep).

    Residuals are one-step-ahead PREDICTION residuals (dS[t] minus the
    prediction made from the EWMA state as of t-1, i.e. before that bar's
    observation updates it) -- not the final converged coefficients applied
    retroactively to the whole series (which would be look-ahead: judging
    bar 5's fit quality using information from bar 500). This is the same
    convention exp2_kalman.py's Kalman filter innovations used for its own
    convergence experiment.

    Parameters
    ----------
    price_a, price_b : as fit_ou.
    bar_hours : as fit_ou.
    halflife_multiplier : float, default 2.0
        EWMA half-life (in bars) = halflife_multiplier * reference_half_life_bars.
    min_bars : int, default 20
        Minimum bars of EWMA history before (c, lam) are considered defined;
        also the floor on the EWMA half-life itself, so a pair with a very
        short or noisy reference half-life doesn't get an unstably-fast decay.

    Returns
    -------
    OUParams, same shape and units as fit_ou -- a drop-in alternative, not a
    different interface. theta/mu are the FINAL (most recent) EWMA state;
    sigma/df are fit from the one-step prediction-residual series above.

    Returns OUParams(nan, nan, nan, nan, empty array) if there's not enough
    data, the reference fit's theta isn't positive (no half-life to scale
    the decay by), or the EWMA state never becomes finite (e.g. a
    degenerate/near-constant spread).
    """
    spread, _beta, _alpha = compute_spread(price_a, price_b)
    S = np.asarray(spread, dtype=float)
    S = S[np.isfinite(S)]
    if len(S) < max(3, 2 * min_bars):
        return OUParams(np.nan, np.nan, np.nan, np.nan, np.array([]))

    # Reference half-life: a static full-window fit, used ONLY to scale the
    # EWMA decay -- not returned, not the estimate this function reports.
    internals = _fit_ou_internals(S)
    if internals is None:
        return OUParams(np.nan, np.nan, np.nan, np.nan, np.array([]))
    theta_static_raw = -internals["lam"]
    if theta_static_raw <= 0:
        return OUParams(np.nan, np.nan, np.nan, np.nan, np.array([]))

    reference_halflife_bars = np.log(2.0) / theta_static_raw
    halflife_bars = max(float(min_bars), halflife_multiplier * reference_halflife_bars)
    decay = 0.5 ** (1.0 / halflife_bars)

    dS, S_lag = S[1:] - S[:-1], S[:-1]
    n = len(dS)

    Sw = Sx = Sxx = Sy = Sxy = 0.0
    lam_t = c_t = np.nan
    pred_residuals = []

    for t in range(n):
        x_t, y_t = S_lag[t], dS[t]

        # One-step-ahead prediction BEFORE this bar updates the state --
        # the honest, non-look-ahead residual.
        if np.isfinite(lam_t):
            pred_residuals.append(y_t - (c_t + lam_t * x_t))

        Sw = decay * Sw + 1.0
        Sx = decay * Sx + x_t
        Sxx = decay * Sxx + x_t * x_t
        Sy = decay * Sy + y_t
        Sxy = decay * Sxy + x_t * y_t

        if t + 1 >= min_bars:
            denom = Sw * Sxx - Sx * Sx
            if abs(denom) > 1e-300:
                lam_t = (Sw * Sxy - Sx * Sy) / denom
                c_t = (Sy - lam_t * Sx) / Sw

    if not np.isfinite(lam_t):
        return OUParams(np.nan, np.nan, np.nan, np.nan, np.array([]))

    theta_raw = -lam_t
    if theta_raw <= 0:
        return OUParams(np.nan, np.nan, np.nan, np.nan, np.array([]))

    mu = c_t / theta_raw
    residuals = np.array(pred_residuals, dtype=float)
    if len(residuals) < 3:
        return OUParams(np.nan, np.nan, np.nan, np.nan, np.array([]))
    sigma_raw = float(np.std(residuals))
    # The Student-t df fit is a Nelder-Mead optimisation and costs ~95% of this
    # function's runtime (2.0s of 2.1s per 60 calls, profiled). It is reported
    # for diagnostics only -- theta, mu, sigma and the residual series are all
    # computed without it, and ou_reversion_probability block-bootstraps the
    # residuals rather than drawing from a fitted t. Callers that need a fit
    # but not the tail-heaviness number can pass fit_df=False and go ~5x
    # faster; the default keeps every existing caller bit-identical.
    df = _fit_student_t_df(residuals) if fit_df else np.nan

    theta = theta_raw / bar_hours
    sigma = sigma_raw / np.sqrt(bar_hours)

    return OUParams(theta=theta, mu=mu, sigma=sigma, df=df, residuals=residuals)


def ou_residual_diagnostics(
    price_a: np.ndarray,
    price_b: np.ndarray,
    lb_lags: int = 48,
) -> OUResidualDiagnostics:
    """Compute residual diagnostics for the OU AR(1) regression on the spread.

    Tests whether the OLS residuals from the OU fit behave like white noise,
    which is required for the OU parameter estimates to be reliable.

    Parameters
    ----------
    price_a, price_b:
        1-D float arrays of hourly prices, equal length.
    lb_lags:
        Number of lags for the Ljung-Box autocorrelation test. Capped at
        len(residuals) // 2 to keep the test well-defined.

    Returns
    -------
    OUResidualDiagnostics with:
        jb_stat         -- Jarque-Bera test statistic (normality of residuals).
        jb_p            -- Jarque-Bera p-value; small values reject normality.
        lb_stat         -- Ljung-Box test statistic at lb_lags (autocorrelation).
        lb_p            -- Ljung-Box p-value; small values indicate autocorrelation.
        skewness        -- Third standardised moment of residuals (0 = symmetric).
        excess_kurtosis -- Fourth standardised moment minus 3 (0 = Gaussian tails).
        theta_tstat     -- t-statistic for H0: theta == 0 (no mean reversion).
        theta_p         -- Two-sided p-value for the theta t-test.

    Returns OUResidualDiagnostics with all fields as np.nan if:
        - Fewer than 3 finite spread values remain after stripping non-finite entries, or
        - The spread is degenerate (zero variance in lagged values).
    """
    spread, _beta, _alpha = compute_spread(price_a, price_b)

    S = np.asarray(spread, dtype=float)
    S = S[np.isfinite(S)]
    if len(S) < 3:
        return OUResidualDiagnostics(*(np.nan,) * 8)

    internals = _fit_ou_internals(S)
    if internals is None:
        return OUResidualDiagnostics(*(np.nan,) * 8)

    lam       = internals["lam"]
    lam_se    = internals["lam_se"]
    residuals = internals["residuals"]
    n         = len(residuals)

    jb_stat, jb_p = jarque_bera(residuals)

    lb_lags_actual = min(lb_lags, n // 2)
    result  = acorr_ljungbox(residuals, lags=[lb_lags_actual], return_df=True)
    lb_stat = float(result["lb_stat"].iloc[-1])
    lb_p    = float(result["lb_pvalue"].iloc[-1])

    mean            = np.mean(residuals)
    std             = np.std(residuals)
    z               = (residuals - mean) / std
    skewness        = float(np.mean(z ** 3))
    excess_kurtosis = float(np.mean(z ** 4) - 3)

    theta_tstat = float(-lam / lam_se)
    df_         = n - 2
    theta_p     = float(2 * t_dist.sf(abs(theta_tstat), df_))

    return OUResidualDiagnostics(
        jb_stat=float(jb_stat),
        jb_p=float(jb_p),
        lb_stat=lb_stat,
        lb_p=lb_p,
        skewness=skewness,
        excess_kurtosis=excess_kurtosis,
        theta_tstat=theta_tstat,
        theta_p=theta_p,
    )


def ou_expected_spread(S0: float, theta: float, mu: float, tau: float) -> float:
    """Compute the conditional mean of the OU process tau hours from now.

    Formula: E[S_{t+tau} | S0] = mu + (S0 - mu) * exp(-theta * tau)

    Parameters
    ----------
    S0    : current spread value
    theta : mean-reversion speed (per hour); must be > 0
    mu    : long-run mean of the spread
    tau   : forecast horizon in hours; must be >= 0

    Returns
    -------
    float — expected spread in tau hours.
    float(S0) exactly when tau == 0.
    np.nan if theta <= 0.
    """
    if theta <= 0:
        return np.nan
    if tau == 0:
        return float(S0)
    return float(mu + (S0 - mu) * np.exp(-theta * tau))


def ou_spread_std(theta: float, sigma: float, tau: float) -> float:
    """Compute the conditional standard deviation of the OU process tau hours from now.

    Formula: std[S_{t+tau}] = sigma * sqrt((1 - exp(-2*theta*tau)) / (2*theta))

    Parameters
    ----------
    theta : mean-reversion speed (per hour); must be > 0
    sigma : spread volatility (spread units per sqrt(hour))
    tau   : forecast horizon in hours; must be >= 0

    Returns
    -------
    float — standard deviation of spread in tau hours.
    0.0 exactly when tau == 0.
    Approaches sigma / sqrt(2*theta) as tau -> infinity.
    np.nan if theta <= 0.
    """
    if theta <= 0:
        return np.nan
    if tau == 0:
        return 0.0
    return float(sigma * np.sqrt((1.0 - np.exp(-2.0 * theta * tau)) / (2.0 * theta)))


def ou_confidence_interval(
    S0: float, theta: float, mu: float, sigma: float,
    tau: float, alpha: float = 0.95
) -> tuple[float, float]:
    """Compute the (lower, upper) confidence interval for the spread at tau hours.

    Formula:
        z     = norm.ppf(1 - (1 - alpha) / 2)
        lower = E[S_{t+tau}] - z * std
        upper = E[S_{t+tau}] + z * std

    Parameters
    ----------
    S0    : current spread value
    theta : mean-reversion speed (per hour); must be > 0
    mu    : long-run mean of the spread
    sigma : spread volatility (spread units per sqrt(hour))
    tau   : forecast horizon in hours
    alpha : confidence level (default 0.95)

    Returns
    -------
    (lower, upper) tuple of floats.
    (np.nan, np.nan) if ou_expected_spread or ou_spread_std returns nan.
    """
    m = ou_expected_spread(S0, theta, mu, tau)
    s = ou_spread_std(theta, sigma, tau)
    if np.isnan(m) or np.isnan(s):
        return (np.nan, np.nan)
    z = norm.ppf(1.0 - (1.0 - alpha) / 2.0)
    return (float(m - z * s), float(m + z * s))


# Minimum residual count for the Monte Carlo path in ou_reversion_probability.
# Below this, a block bootstrap is resampling from too few points to be
# meaningfully "empirical" (with the default 16-bar block, 24 residuals is
# only 1.5 blocks of raw material) -- fall back to the analytic formula
# instead of dressing up a thin sample as a distribution fit.
_MC_MIN_RESIDUALS = 24


# Bounds for _mc_reversion_probability's forward simulation. See the comment
# inside that function: tau is unbounded when theta approaches zero, and the
# old full-array allocation turned one pathological pair into a 26 GB request.
# _MC_CHUNK_STEPS is chosen so that any fit needing fewer steps than this draws
# its innovations in exactly one chunk, preserving the previous draw order and
# therefore the previous result exactly.
_MC_CHUNK_STEPS = 4096
_MC_MAX_STEPS   = 200_000


def _mc_reversion_probability(
    S0: float, theta: float, mu: float, tau: float, residuals: np.ndarray,
    *, bar_hours: float, n_paths: int, block_hours: float,
    rng: np.random.Generator | None,
) -> float:
    """Estimate P(spread crosses mu within tau) by simulating forward paths.

    Simulates n_paths discrete trajectories at bar_hours spacing using the
    same AR(1) recursion the OU fit was estimated from:
        S_next = c_raw + phi * S,   phi = 1 - theta*bar_hours,   c_raw = mu*theta*bar_hours
    with innovations drawn by circular block bootstrap from `residuals` (the
    fitted OU residuals) rather than an assumed parametric shape -- this is
    what removes the reflection principle's Gaussian-tails bias at the
    source instead of patching the probability threshold after the fact.

    block_hours converts to a bar count via block_bars = round(block_hours /
    bar_hours), clipped to [1, len(residuals)]. Resampling in contiguous
    blocks (default: 16 bars = one 8h funding cycle at 30m bars) rather than
    single bars preserves any short-range dependence in the residuals an iid
    bar-by-bar draw would erase.

    Crossing is checked at bar resolution: a path counts as "crossed" if
    (S - mu) changes sign, or hits exactly mu, at any simulated bar within
    tau. Returns the fraction of paths that crossed.
    """
    if rng is None:
        rng = np.random.default_rng()

    residuals = np.asarray(residuals, dtype=float)
    n_res      = len(residuals)
    block_bars = max(1, min(n_res, int(round(block_hours / bar_hours))))

    # tau = ln(1/f)/theta, so a near-zero theta asks for an unbounded horizon.
    # The innovation array used to be allocated in full as n_paths x n_steps:
    # a spread that fits theta=1e-6 requests 1.6 million hours, 3.2 million
    # bars, and a 26 GB allocation. On an 8GB machine that is not a slow path,
    # it is a hard kill -- it took this laptop down three times before the
    # cause was found, because the pair that triggers it is roughly 1 in
    # 100,000 and never the same one twice.
    #
    # Two bounds, neither of which changes a normal result:
    #   _MC_CHUNK_STEPS  innovations are drawn a chunk at a time instead of all
    #                    at once, so peak memory is n_paths x chunk regardless
    #                    of tau. For n_steps <= _MC_CHUNK_STEPS (tau <= 2048h
    #                    at 30m bars, which is over 99% of real fits) the draw
    #                    order is unchanged and the result is bit-identical.
    #   _MC_MAX_STEPS    a ceiling on simulated bars. Reaching it returns the
    #                    fraction crossed SO FAR, which is a lower bound on the
    #                    true probability -- more time can only add crossings.
    #                    Gate 6 is a minimum-probability test, so a lower bound
    #                    can only make it stricter, never let a trade through
    #                    that should have been blocked.
    n_steps_full = max(1, int(np.ceil(tau / bar_hours)))
    n_steps      = min(n_steps_full, _MC_MAX_STEPS)

    phi   = 1.0 - theta * bar_hours
    c_raw = mu * theta * bar_hours

    offsets = np.arange(block_bars)
    S       = np.full(n_paths, S0, dtype=float)
    sign0   = np.sign(S0 - mu)
    crossed = np.zeros(n_paths, dtype=bool)

    done = 0
    while done < n_steps:
        m        = min(_MC_CHUNK_STEPS, n_steps - done)
        n_blocks = int(np.ceil(m / block_bars))
        starts   = rng.integers(0, n_res, size=(n_paths, n_blocks))
        idx      = (starts[:, :, None] + offsets[None, None, :]) % n_res
        eps      = residuals[idx].reshape(n_paths, n_blocks * block_bars)[:, :m]
        for k in range(m):
            S = c_raw + phi * S + eps[:, k]
            crossed |= (np.sign(S - mu) != sign0) | (S == mu)
        done += m
        # Once every path has crossed the answer is 1.0 and cannot change;
        # continuing is the difference between 0.1s and an hour on a spread
        # that is effectively a random walk.
        if crossed.all():
            break

    return float(np.mean(crossed))


def ou_reversion_probability(
    S0: float, theta: float, mu: float, sigma: float, tau: float,
    residuals: np.ndarray | None = None,
    *,
    bar_hours: float = 1.0,
    n_paths: int = 5000,
    block_hours: float = 8.0,
    rng: np.random.Generator | None = None,
) -> float:
    """Compute the probability that the spread crosses mu at least once within tau hours.

    Two estimation paths:

    - residuals given (and len(residuals) >= _MC_MIN_RESIDUALS): Monte Carlo.
      Simulates n_paths forward paths under the fitted OU dynamics, with
      innovations block-bootstrapped from the fitted residuals -- see
      _mc_reversion_probability. This is the accurate path: it doesn't
      assume Gaussian noise, so it isn't subject to the reflection
      principle's known bias on the fat-tailed (excess kurtosis ~2.6)
      spreads this model is fit to.
    - residuals not given (or too few): falls back to the closed-form
      reflection principle approximation,
          P = 2 * norm.cdf(-abs(S0 - mu) * exp(-theta * tau) / std),
      where std = ou_spread_std(theta, sigma, tau). This is a Gaussian
      approximation and is known to be biased on fat-tailed residuals;
      kept for callers that only have scalar OU params (no fitted
      residuals available) and for analytic/monotonicity sanity checks.

    Parameters
    ----------
    S0        : current spread value
    theta     : mean-reversion speed (per hour); must be > 0
    mu        : long-run mean of the spread
    sigma     : spread volatility (spread units per sqrt(hour)); only used
                on the analytic fallback path
    tau       : forecast horizon in hours
    residuals : fitted OU residuals (OUParams.residuals) to bootstrap from;
                None selects the analytic fallback
    bar_hours : real time between bars in `residuals`; must match what
                fit_ou was called with, since it sets both the simulation
                step size and the block-bootstrap bar count
    n_paths   : number of Monte Carlo paths (MC path only)
    block_hours : bootstrap block length in hours (MC path only); default
                8.0 matches the OKX perpetual funding cycle
    rng       : numpy Generator for the simulation draws (MC path only).
                None creates a fresh unseeded Generator each call --
                callers that need reproducible backtests should pass a
                shared seeded Generator instead of leaving this None.

    Returns
    -------
    float in [0, 1].
    1.0 if S0 == mu.
    0.0 if tau == 0 and S0 != mu.
    np.nan if theta <= 0.
    np.nan if std == 0 on the analytic fallback path.
    """
    if S0 == mu:
        return 1.0
    if tau == 0:
        return 0.0
    if theta <= 0:
        return np.nan

    if residuals is not None and len(residuals) >= _MC_MIN_RESIDUALS:
        return _mc_reversion_probability(
            S0, theta, mu, tau, residuals,
            bar_hours=bar_hours, n_paths=n_paths, block_hours=block_hours, rng=rng,
        )

    s = ou_spread_std(theta, sigma, tau)
    if np.isnan(s) or s == 0.0:
        return np.nan
    arg = -abs(S0 - mu) * np.exp(-theta * tau) / s
    return float(2.0 * norm.cdf(arg))


def ou_expected_reversion_time(
    S0: float, theta: float, mu: float, epsilon: float = 1e-4
) -> float:
    """Compute the expected time in hours for the spread to reach within epsilon of mu.

    Formula: E[time to mu] = (1/theta) * ln(|S0 - mu| / epsilon)

    Parameters
    ----------
    S0      : current spread value
    theta   : mean-reversion speed (per hour); must be > 0
    mu      : long-run mean of the spread
    epsilon : tolerance band around mu (default 1e-4)

    Returns
    -------
    float — expected hours until |S - mu| <= epsilon.
    0.0 if abs(S0 - mu) <= epsilon (already within tolerance).
    0.0 if ln(|S0 - mu| / epsilon) is negative (|S0 - mu| < epsilon).
    np.nan if theta <= 0.
    """
    if theta <= 0:
        return np.nan
    if abs(S0 - mu) <= epsilon:
        return 0.0
    log_val = np.log(abs(S0 - mu) / epsilon)
    if log_val < 0:
        return 0.0
    return float(log_val / theta)
