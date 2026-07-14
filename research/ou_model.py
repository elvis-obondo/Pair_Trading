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


class OUParams(NamedTuple):
    theta: float  # mean reversion speed (per hour)
    mu: float     # long-run mean of the spread
    sigma: float  # volatility of the spread


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


def fit_ou(price_a: np.ndarray, price_b: np.ndarray) -> OUParams:
    """Fit an Ornstein-Uhlenbeck model to the spread implied by price_a and price_b.

    Computes the spread via OLS (price_a - alpha - beta * price_b), then estimates
    the three OU parameters from the discretised process dS = -theta*(S - mu)*dt + sigma*dW
    using OLS on consecutive spread values.

    Parameters
    ----------
    price_a, price_b:
        1-D float arrays of hourly prices, equal length.

    Returns
    -------
    OUParams with:
        theta -- mean-reversion speed (per hour); larger values mean faster pull toward mu.
        mu    -- long-run mean of the spread (spread units: price_a - beta * price_b).
        sigma -- spread volatility (spread units per sqrt(hour)).

    Returns OUParams(nan, nan, nan) if:
        - Fewer than 3 finite spread values remain after stripping non-finite entries, or
        - The fitted theta is <= 0, meaning the spread does not mean-revert.
    """
    spread, _beta, _alpha = compute_spread(price_a, price_b)

    S = np.asarray(spread, dtype=float)
    S = S[np.isfinite(S)]
    if len(S) < 3:
        return OUParams(np.nan, np.nan, np.nan)

    internals = _fit_ou_internals(S)
    if internals is None:
        return OUParams(np.nan, np.nan, np.nan)

    lam, c = internals["lam"], internals["c"]

    theta = -lam
    if theta <= 0:
        return OUParams(np.nan, np.nan, np.nan)

    mu    = c / theta
    sigma = float(np.std(internals["residuals"]))

    return OUParams(theta=theta, mu=mu, sigma=sigma)


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


def ou_reversion_probability(
    S0: float, theta: float, mu: float, sigma: float, tau: float
) -> float:
    """Compute the probability that the spread crosses mu at least once within tau hours.

    Uses the reflection principle approximation:
        P = 2 * norm.cdf(-abs(S0 - mu) * exp(-theta * tau) / std)

    where std = ou_spread_std(theta, sigma, tau).

    Parameters
    ----------
    S0    : current spread value
    theta : mean-reversion speed (per hour); must be > 0
    mu    : long-run mean of the spread
    sigma : spread volatility (spread units per sqrt(hour))
    tau   : forecast horizon in hours

    Returns
    -------
    float in [0, 1].
    1.0 if S0 == mu.
    0.0 if tau == 0 and S0 != mu.
    np.nan if theta <= 0.
    np.nan if std == 0.
    """
    if S0 == mu:
        return 1.0
    if tau == 0:
        return 0.0
    if theta <= 0:
        return np.nan
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
