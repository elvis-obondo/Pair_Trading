import numpy as np
from statsmodels.tsa.stattools import coint


def measure_approach_speeds(
    zscore: np.ndarray,
    signal_indices: list[int],
    threshold: float,
) -> list[tuple[int, float]]:
    """
    For each signal index, measure how many hours elapsed from the first bar of the
    current threshold excursion to the signal bar.

    Inputs:
        zscore          : 1-D array of z-score values (hourly bars)
        signal_indices  : bar indices at which signals fired
        threshold       : positive float; long signals are below -threshold,
                          short signals are above +threshold

    Outputs:
        List of (signal_index, hours) tuples.
        hours = float(idx - (j + 1)) where j is the last bar not beyond the threshold
                before the excursion started.
        Returns np.inf  if the excursion was already underway at bar 0
                        (cannot measure the approach start).
        Returns np.nan  if zscore[idx] is not beyond ±threshold (invalid index).

    Units: hours (1 bar == 1 hour).
    """
    z = np.asarray(zscore, dtype=float)
    if len(z) == 0:
        return [(idx, np.nan) for idx in signal_indices]
    result = []

    for idx in signal_indices:
        if z[idx] < -threshold:
            beyond = lambda v: v < -threshold  # noqa: E731
        elif z[idx] > threshold:
            beyond = lambda v: v > threshold   # noqa: E731
        else:
            result.append((idx, np.nan))
            continue

        if idx < 2:
            result.append((idx, np.inf))
            continue

        j = idx - 2
        while j >= 0 and beyond(z[j]):
            j -= 1

        if j < 0:
            result.append((idx, np.inf))
        else:
            result.append((idx, float(idx - (j + 1))))

    return result


def conditional_half_life(zscore: np.ndarray, threshold: float) -> float:
    """
    Mean duration of threshold excursions, measured from the first bar above
    |threshold| to the first bar back below |threshold|.

    Only counts fresh excursions (first bar of a new event). Unresolved events
    (still beyond threshold at end of array) are excluded. Returns np.nan if
    fewer than 2 resolved events are found.

    Inputs:
        zscore    : 1-D array of z-score values (hourly bars)
        threshold : positive float; excursions are bars where |zscore| >= threshold

    Outputs:
        Mean excursion duration in days (float), or np.nan.

    Units: output in days (input bars assumed hourly, divided by 24).
    """
    z = np.asarray(zscore, dtype=float)
    z = z[np.isfinite(z)]

    durations = []
    i = 1
    while i < len(z):
        if abs(z[i]) >= threshold and abs(z[i - 1]) < threshold:
            j = i + 1
            while j < len(z) and abs(z[j]) >= threshold:
                j += 1
            if j < len(z):
                durations.append(j - i)
            i = j
        else:
            i += 1

    if len(durations) < 2:
        return np.nan
    return float(np.mean(durations)) / 24.0


def pre_entry_coint_check(
    price_a: np.ndarray,
    price_b: np.ndarray,
    window: int = 168,
) -> float:
    """
    Engle-Granger cointegration p-value on the most recent window bars.

    Inputs:
        price_a : 1-D array of log-prices for asset A (hourly bars)
        price_b : 1-D array of log-prices for asset B (hourly bars)
        window  : number of trailing bars to test (default 168 = 7 days)

    Outputs:
        p-value (float in [0, 1]), or np.nan if either array is shorter than
        window or contains non-finite values in the window.

    Units: p-value is dimensionless.
    """
    a = np.asarray(price_a, dtype=float)
    b = np.asarray(price_b, dtype=float)

    if len(a) < window or len(b) < window:
        return np.nan

    chunk_a = a[-window:]
    chunk_b = b[-window:]

    if not (np.isfinite(chunk_a).all() and np.isfinite(chunk_b).all()):
        return np.nan

    _, pval, _ = coint(chunk_a, chunk_b)
    return float(pval)


def spread_volatility_regime(
    spread: np.ndarray,
    sigma: float,
    window: int = 168,
) -> float:
    """
    Log ratio of recent spread volatility to the fitted OU noise parameter sigma.

    Inputs:
        spread : 1-D array of raw spread values (spread units, not z-scores)
        sigma  : fitted OU volatility parameter from fit_ou() (spread units);
                 must be finite and positive
        window : number of trailing bars defining "recent" (default 168 = 7 days)

    Outputs:
        log(recent_std / sigma) as a float, or np.nan under the conditions below.

        Sign and magnitude:
          0.0   recent std == sigma  (model accurate, neutral regime)
          > 0   recent std > sigma   (more volatile than model expects)
          < 0   recent std < sigma   (quieter than model expects)

          ~+0.4  moderately elevated    (recent std ~1.5x sigma)
          ~+0.7  significantly elevated (recent std ~2x sigma)
          ~+1.1  severely elevated      (recent std ~3x sigma)
          ~-0.7  significantly quiet    (recent std ~0.5x sigma)

        Returns np.nan when:
          - len(s) < window          (too few finite observations)
          - not np.isfinite(sigma)   (sigma is nan or inf)
          - sigma <= 0               (sigma must be strictly positive)
          - current_std == 0         (degenerate window, no variation)

        where s is spread after stripping non-finite values.

    Units: dimensionless log ratio.
    """
    s = np.asarray(spread, dtype=float)
    s = s[np.isfinite(s)]

    if len(s) < window:
        return np.nan
    if not np.isfinite(sigma):
        return np.nan
    if sigma <= 0:
        return np.nan

    current_std = float(np.std(s[-window:]))

    if current_std == 0:
        return np.nan

    return float(np.log(current_std / sigma))
