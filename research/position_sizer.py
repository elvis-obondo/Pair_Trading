import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np


def compute_position_size(
    entry_signal: dict,
    capital: float,
    risk_budget_pct: float = 0.01,
    stop_sigma: float = 2.5,
) -> dict | None:
    """
    Size a pairs trade so that a worst-case stop-out costs exactly risk_budget_pct
    of capital, using the OU stationary distribution as the unit of risk measurement.

    The function derives the spread's stationary standard deviation (sigma_stationary)
    from the OU parameters frozen at entry, then computes leg notionals such that a
    stop_sigma-unit adverse move in the spread costs exactly risk_budget_pct * capital.

    Parameters
    ----------
    entry_signal : dict
        Dict returned by generate_entry_signal. Exactly three fields are read:
            sigma_at_entry (float) -- OU noise parameter in spread units per sqrt(hour);
                                      must be finite and strictly positive.
            theta_at_entry (float) -- OU mean-reversion speed in per-hour units;
                                      must be finite and strictly positive.
            beta_at_entry  (float) -- OLS hedge ratio (dimensionless); must be finite;
                                      may be negative, which reverses the leg B direction.
        All other fields in the dict are ignored.
    capital : float
        Total capital in dollars. Must be finite and strictly positive.
    risk_budget_pct : float, default 0.01
        Fraction of capital to risk per trade (e.g. 0.01 = 1%). A full stop-out
        on leg A will cost exactly risk_budget_pct * capital dollars. Must be
        finite and strictly positive.
    stop_sigma : float, default 2.5
        Number of sigma_stationary units defining the adverse-move stop distance.
        Must be finite and strictly positive. IMPORTANT: this value must match the
        stop_sigma passed to generate_exit_signal for the same trade. If they
        differ, the position is sized to a stop level that is not where the exit
        fires — the sizing is internally inconsistent. This function does not
        enforce the match; the caller is responsible.

    Returns
    -------
    dict with keys:
        leg_a_notional   (float, dollars) -- notional to deploy on leg A (long leg).
                                             Always positive when inputs are valid.
        leg_b_notional   (float, dollars) -- notional to deploy on leg B, scaled by
                                             beta. Positive when beta > 0 (same-direction
                                             leg), negative when beta < 0 (reversed
                                             direction). A negative value is correct and
                                             intentional — it means leg B is short while
                                             leg A is long (or vice versa). Do not take
                                             abs(leg_b_notional).
        total_deployed   (float, dollars) -- leg_a_notional + leg_b_notional. May be
                                             less than leg_a_notional alone when beta < 0.
        fraction         (float, dimensionless) -- fraction of capital deployed on leg A.
                                             Equals risk_budget_pct / risk_unit.
        sigma_stationary (float, spread units) -- stationary standard deviation of the
                                             spread's OU distribution: sigma / sqrt(2*theta).
    None
        Returned if any of the following hold:
            - sigma_at_entry is not finite or <= 0
            - theta_at_entry is not finite or <= 0
            - beta_at_entry is not finite
            - capital is not finite or <= 0
            - risk_budget_pct is not finite or <= 0
            - stop_sigma is not finite or <= 0
            - risk_unit <= 0 (safety guard; should not occur given the above)
    """
    # Step 1 — extract fields from entry_signal
    sigma = entry_signal["sigma_at_entry"]
    theta = entry_signal["theta_at_entry"]
    beta  = entry_signal["beta_at_entry"]

    # Step 2 — validate all inputs; evaluate all conditions before returning
    invalid = (
        not np.isfinite(sigma)           or sigma <= 0
        or not np.isfinite(theta)        or theta <= 0
        or not np.isfinite(beta)
        or not np.isfinite(capital)      or capital <= 0
        or not np.isfinite(risk_budget_pct) or risk_budget_pct <= 0
        or not np.isfinite(stop_sigma)   or stop_sigma <= 0
    )
    if invalid:
        return None

    # Step 3 — stationary standard deviation of the spread's OU distribution
    sigma_stationary = sigma / np.sqrt(2.0 * theta)

    # Step 4 — adverse-move stop distance in spread units
    risk_unit = stop_sigma * sigma_stationary

    # Step 5 — safety guard
    if risk_unit <= 0:
        return None

    # Step 6 — fraction of capital on leg A such that a full stop-out = risk_budget_pct
    fraction = risk_budget_pct / risk_unit

    # Step 7 — leg notionals
    leg_a_notional = fraction * capital
    leg_b_notional = beta * fraction * capital
    total_deployed = leg_a_notional + leg_b_notional

    # Step 8 — return
    return {
        "leg_a_notional":   float(leg_a_notional),
        "leg_b_notional":   float(leg_b_notional),
        "total_deployed":   float(total_deployed),
        "fraction":         float(fraction),
        "sigma_stationary": float(sigma_stationary),
    }
