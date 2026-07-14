import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
from ou_model import (
    fit_ou,
    ou_residual_diagnostics,
    ou_reversion_probability,
)
from trade_diagnostics import (
    pre_entry_coint_check,
    spread_volatility_regime,
)
from pair_analysis import compute_spread


def generate_entry_signal(
    price_a: np.ndarray,
    price_b: np.ndarray,
    coint_p_threshold: float = 0.10,
    regime_threshold: float = 1.1,
    prob_threshold: float = 0.67,
    theta_p_threshold: float = 0.05,
    take_profit_pct: float = 0.80,
    f: float = 0.20,
    min_deviation_sigma: float = 1.0,
) -> dict | None:
    """
    Run a gated OU-model entry check and return a signal dict if all gates pass.

    Applies five sequential gates to price_a and price_b; if any gate fails the
    function returns None immediately. If all pass, it returns a dict describing
    the entry conditions and derived targets.

    Parameters
    ----------
    price_a : np.ndarray
        1-D float array of hourly log-prices for asset A.
    price_b : np.ndarray
        1-D float array of hourly log-prices for asset B, equal length to price_a.
    coint_p_threshold : float, default 0.10
        Gate 1 — maximum acceptable Engle-Granger cointegration p-value on the
        last 168 bars. Higher p-value means cointegration is not supported.
    regime_threshold : float, default 1.1
        Gate 4 — maximum acceptable log volatility ratio log(recent_std / sigma).
        Default 1.1 corresponds to roughly 3x sigma in recent spread std; above
        this the model assumptions are strained.
    prob_threshold : float, default 0.67
        Gate 5 — minimum analytical reversion probability to generate a signal.
        Default 0.67 targets a true probability of ~0.60 after accounting for the
        ~6-7% overestimate introduced by the reflection-principle approximation on
        hourly-discrete paths.
    theta_p_threshold : float, default 0.05
        Gate 3 — maximum acceptable p-value for the theta significance test.
        If exceeded, mean reversion is not statistically reliable enough to trade.
    take_profit_pct : float, default 0.80
        Fraction of the deviation from entry spread to mu that defines the
        take-profit target. Default 0.80 captures 80% of the expected move.
    f : float, default 0.20
        Fraction of the initial deviation remaining at the end of the holding
        horizon. The holding horizon (tau) is derived as tau = ln(1/f) / theta,
        so f=0.20 means the horizon targets 80% decay of the deviation.
    min_deviation_sigma : float, default 1.0
        Gate 3 — minimum distance of the current spread from mu, in units
        of sigma_stationary = sigma / sqrt(2*theta). Entries closer to mu
        than this are rejected. Default 1.0 (one stationary std dev) chosen
        as the natural unit; flagged for empirical sweep. Set to 0.0 to
        disable the gate.

    Returns
    -------
    dict or None
        None if any gate fails. Otherwise a dict with keys:

        entry_spread            -- spread value at signal time (float, spread units)
        reversion_probability   -- analytical P(cross mu within tau) (float, [0,1])
        expected_reversion_time -- 1.5 * ln(1/f) / theta in hours (float);
                                 1.5x empirical correction applied so the
                                 time-stop horizon matches observed reversion
                                 (probe showed 1.3x-1.9x under-prediction).
        mu_at_entry             -- fitted OU long-run mean (float, spread units)
        sigma_at_entry          -- fitted OU noise parameter (float, spread units)
        take_profit_level       -- S0 - take_profit_pct * (S0 - mu) (float, spread units)
        regime_log_ratio        -- log(recent_std / sigma) at entry (float, dimensionless)
        deviation_sigma         -- how many sigma_stationary from mu at entry (float, dimensionless)
        min_deviation_sigma     -- the min_deviation_sigma threshold in force (float, dimensionless)

    Gate order (execution order)
    ----------
    Gate 1 : Cointegration — pre_entry_coint_check p-value <= coint_p_threshold
    Gate 2 : OU fit — fit_ou must return finite theta (theta > 0)
    Gate 3 : Minimum deviation — abs(S0 - mu) >= min_deviation_sigma * sigma_stationary
    Gate 4 : Theta significance — ou_residual_diagnostics theta_p <= theta_p_threshold
    Gate 5 : Volatility regime — spread_volatility_regime <= regime_threshold
    Gate 6 : Reversion probability — ou_reversion_probability >= prob_threshold
    """
    # Step 1 — input preparation
    spread_arr, beta, alpha = compute_spread(price_a, price_b)
    S = np.asarray(spread_arr, dtype=float)
    S = S[np.isfinite(S)]
    if len(S) < 3:
        return None
    S0 = float(S[-1])

    # Step 2 — Gate 1: cointegration check
    coint_p = pre_entry_coint_check(price_a, price_b)
    if np.isnan(coint_p) or coint_p > coint_p_threshold:
        return None

    # Step 3 — Gate 2: fit OU parameters
    params = fit_ou(price_a, price_b)
    if np.isnan(params.theta):
        return None

    # Step 3b — Gate 3: minimum deviation from mu
    # Require the current spread to sit at least min_deviation_sigma
    # stationary std devs from mu. sigma_stationary = sigma / sqrt(2*theta)
    # is the long-run OU spread volatility, the same unit used by the
    # position sizer and the adverse-move exit stop.
    sigma_stationary = params.sigma / np.sqrt(2.0 * params.theta)
    deviation = abs(S0 - params.mu)
    if deviation < min_deviation_sigma * sigma_stationary:
        return None

    # Step 4 — Gate 3: theta significance
    diag = ou_residual_diagnostics(price_a, price_b)
    if np.isnan(diag.theta_p) or diag.theta_p > theta_p_threshold:
        return None

    # Step 5 — Gate 4: volatility regime
    regime = spread_volatility_regime(S, params.sigma)
    if np.isnan(regime) or regime > regime_threshold:
        return None

    # Step 6 — Gate 5: reversion probability
    tau  = np.log(1.0 / f) / params.theta
    prob = ou_reversion_probability(
        S0, params.theta, params.mu, params.sigma, tau
    )
    if np.isnan(prob) or prob < prob_threshold:
        return None

    # Step 7 — signal construction
    # 1.5x empirical correction: OU tau = ln(1/f)/theta systematically
    # under-predicts realized reversion time. Step 6 reversion-timing
    # probe showed reverting trades reached take-profit at 1.3x-1.9x
    # predicted tau. The time stop reads this field as its horizon, so
    # this lengthens the holding window to match observed reversion.
    # NOTE: the probability-gate tau above is deliberately NOT corrected.
    expected_reversion_time = 1.5 * np.log(1.0 / f) / params.theta
    take_profit_level = S0 - take_profit_pct * (S0 - params.mu)

    return {
        "entry_spread":            float(S0),
        "reversion_probability":   float(prob),
        "expected_reversion_time": float(expected_reversion_time),
        "mu_at_entry":             float(params.mu),
        "sigma_at_entry":          float(params.sigma),
        "take_profit_level":       float(take_profit_level),
        "regime_log_ratio":        float(regime),
        "beta_at_entry":           float(beta),
        "alpha_at_entry":          float(alpha),
        "theta_at_entry":          float(params.theta),
        "deviation_sigma":         float(deviation / sigma_stationary),
        "min_deviation_sigma":     float(min_deviation_sigma),
    }


def generate_exit_signal(
    current_price_a: float,
    current_price_b: float,
    entry_signal: dict,
    hours_elapsed: float,
    stop_sigma: float = 2.5,
) -> dict | None:
    """
    Evaluate exit conditions for an open pairs trade and return an exit dict or None.

    Checks three exit gates in order — time stop first (unconditional), then adverse
    move, then take profit — and returns None if none fires.

    Parameters
    ----------
    current_price_a : float
        Scalar log-price for asset A at the current bar. Not an array.
    current_price_b : float
        Scalar log-price for asset B at the current bar. Not an array.
    entry_signal : dict
        Dict returned by generate_entry_signal. Must contain:
            entry_spread, mu_at_entry, take_profit_level,
            expected_reversion_time, beta_at_entry, alpha_at_entry,
            sigma_at_entry, theta_at_entry.
        This dict is never modified.
    hours_elapsed : float
        Number of hours since trade entry, tracked by the caller.
    stop_sigma : float, default 2.5
        Number of stationary standard deviations of adverse move from entry
        that triggers an immediate exit. Scaled by
        sigma_stationary = sigma / sqrt(2 * theta), not by raw sigma, because
        sigma_stationary reflects the long-run spread volatility and is a more
        meaningful unit for detecting model failure. Default 2.5 chosen to avoid
        stopping out on normal OU noise while still protecting against genuine
        model breakdown. Fat tails in crypto spreads (excess kurtosis ~2.6) mean
        2.0 would fire too frequently on normal noise. Flagged for empirical
        calibration in Step 6.

    Returns
    -------
    dict or None
        None if no exit condition is met. Otherwise a dict with keys:
            exit_reason    : str   — "take_profit", "time_stop", or "adverse_move"
            current_spread : float — spread value at decision time
            entry_spread   : float — carried from entry_signal unchanged
            pnl_pct        : float — fraction of available move captured,
                             abs(current_spread - entry_spread) /
                             abs(entry_spread - mu_at_entry)
            stop_sigma     : float — stop_sigma parameter active for this trade;
                             included in all exits for backtest traceability

    Notes
    -----
    The spread is reconstructed using the coefficients frozen at entry
    (beta_at_entry, alpha_at_entry), not re-estimated OLS. The hedge ratio
    is fixed at entry; re-estimating it mid-trade would shift the spread
    baseline and make P&L accounting inconsistent.

    Gate order: time stop → adverse move → take profit. Time stop is checked
    first, unconditionally. A trade that has both triggered the adverse move
    stop and exceeded max_hours will be reported as "time_stop".

    Direction is derived from the sign of (entry_spread - mu_at_entry):
        entry_spread > mu  →  spread above long-run mean, expecting downward
                               reversion; adverse move fires if spread rises
                               above entry_spread + stop_distance; take profit
                               fires when spread falls to or below take_profit_level.
        entry_spread <= mu →  spread below long-run mean, expecting upward
                               reversion; adverse move fires if spread falls
                               below entry_spread - stop_distance; take profit
                               fires when spread rises to or above take_profit_level.

    pnl_pct formula: abs(current_spread - entry_spread) / abs(entry_spread - mu_at_entry)

    sigma_stationary = sigma / sqrt(2 * theta) is the long-run OU spread volatility,
    a more meaningful stop unit than per-hour sigma. Fat tails in crypto spreads
    (excess kurtosis ~2.6) informed the 2.5 default — 2.0 would fire too frequently
    on normal OU noise. The stop_sigma parameter is flagged for empirical calibration.

    stop_sigma is included in all exit dicts (not just adverse_move) so the backtest
    always knows what stop was active for that trade.
    """
    # Step 1 — reconstruct current spread using frozen entry coefficients
    current_spread = (current_price_a
                      - entry_signal["alpha_at_entry"]
                      - entry_signal["beta_at_entry"] * current_price_b)

    # Step 2 — extract entry state
    entry_spread = entry_signal["entry_spread"]
    mu           = entry_signal["mu_at_entry"]
    take_profit  = entry_signal["take_profit_level"]
    max_hours    = entry_signal["expected_reversion_time"]

    # Step 3 — compute pnl_pct
    pnl_pct = abs(current_spread - entry_spread) / abs(entry_spread - mu)

    # Step 4 — build exit dict helper
    def _exit(reason: str) -> dict:
        return {
            "exit_reason":    reason,
            "current_spread": float(current_spread),
            "entry_spread":   float(entry_spread),
            "pnl_pct":        float(pnl_pct),
            "stop_sigma":     float(stop_sigma),
        }

    # Step 5 — compute adverse move stop level
    sigma_stationary = (entry_signal["sigma_at_entry"] /
                        np.sqrt(2.0 * entry_signal["theta_at_entry"]))
    stop_distance    = stop_sigma * sigma_stationary

    # Step 6 — Gate 1: time stop (unconditional, checked first)
    if hours_elapsed >= max_hours:
        return _exit("time_stop")

    # Step 7 — Gate 2: adverse move stop
    if entry_spread > mu:
        if current_spread >= entry_spread + stop_distance:
            return _exit("adverse_move")
    else:
        if current_spread <= entry_spread - stop_distance:
            return _exit("adverse_move")

    # Step 8 — Gate 3: take profit (direction derived from entry)
    if entry_spread > mu:
        # spread above mu, expecting downward reversion
        if current_spread <= take_profit:
            return _exit("take_profit")
    else:
        # spread below mu, expecting upward reversion
        if current_spread >= take_profit:
            return _exit("take_profit")

    # Step 9 — no exit condition met
    return None
