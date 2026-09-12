"""Entry and exit signals, measured in 7-day rolling sigma.

WHAT CHANGED AND WHY

This module used to run six entry gates and measure every distance in the OU
stationary sigma (`sigma / sqrt(2*theta)`). Both are gone.

The gates went because they were tested. All 31 combinations of the five boolean
entry gates were scored at a 3-sigma entry: no combination beats no gates, and 25
of the 31 collapse the account to 6-14% of starting equity. They raise the win
rate (15.7% to 21.6%) and lose money anyway, by filtering out the rare large
winners the edge depends on. The cointegration gate is among the ones that hurt.
Removing them also removes the Monte Carlo reversion probability, which was ~85%
of this path's compute -- the saving the universe scanner needs.

The sigma basis changed because the parameters were always calibrated in rolling
sigma. `research/exit_sweep.py` built every candidate trade on a rolling 7-day
fit and divided its adverse excursions by the rolling std; entry at 3.0, stop at
0.5 beyond entry, take-profit at full reversion to mu are all in those units.
Applying them to a stationary sigma roughly 2.17x smaller was measuring the right
thresholds against the wrong ruler. `research/rolling_spread.py` is now the one
definition of that geometry, and research/validate_rolling_spread.py checks it
against exit_sweep's own inline code.

WHAT THE OU FIT IS STILL FOR

theta only, and it is a RANKING key, never a gate. The scanner orders candidates
fastest-reverting first and fills its ten slots from the top.

A NaN theta does NOT decline the trade. It used to, and that was wrong: the
two-year walk-forward found only 40.8% of 3-sigma candidates fit a positive theta
(against 93.6% on the original 89-day window), so declining the rest silently
discarded nearly six candidates in ten. Ranking and filtering are different
rules and only the first is settled -- unranked candidates sort last and fill
whatever slots the ranked ones leave.

Ranking on theta measured dead even against random on the two-year panel (+0.417
vs +0.420 per unit risked, equal-weighted across 12 folds); it raises the win
rate in 11 of 12 folds but wins shrink to match. The alternatives are worse, not
better: spread volatility looks best per-trade (+3.40% vs +0.30%) purely because
payoff scales with sigma, and carries 32% ruin; cointegration p-value correlates
-0.223 with outcome. See docs/SCANNER_SESSION_HANDOFF.md section 6c.

ORDERING MATTERS. The z-screen runs before the OU fit, not after. Only ~322 of
22,366 pairs a day clear 3 sigma, so fitting after screening is what keeps the
scanner tractable (<1s z-screen plus ~0.5s of fits per 30-minute bar, versus
fitting every pair every bar).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np

from ou_model import fit_ou_ewma
from rolling_spread import last_bar, entry_window_bars, min_bars_required


def generate_entry_signal(
    price_a: np.ndarray,
    price_b: np.ndarray,
    min_deviation_sigma: float = 3.0,
    take_profit_pct: float = 1.0,
    bar_hours: float = 0.5,
) -> dict | None:
    """Return an entry signal if the spread has stretched far enough, else None.

    Parameters
    ----------
    price_a, price_b : np.ndarray
        1-D float arrays of LOG prices, equal length, sampled every bar_hours.
        Must be at least rolling_spread.min_bars_required(bar_hours) long --
        671 bars at 30 minutes, i.e. TWO 7-day windows, not one. See that
        function for why one window silently yields no signal, ever.
    min_deviation_sigma : float, default 3.0
        Entry threshold: how far the spread must sit from its rolling mean, in
        7-day rolling standard deviations. 3.0 is the settled value. 0.0
        disables the check.
    take_profit_pct : float, default 1.0
        Fraction of the entry gap to capture. 1.0 puts the target at mu itself
        -- full reversion, the settled value.
    bar_hours : float, default 0.5
        Real hours between consecutive samples. Sets the rolling window length
        and makes theta come back genuinely per-hour.

    Returns
    -------
    dict or None
        None if the rolling geometry is undetermined or the spread is inside
        the entry threshold. A failed OU fit does NOT return None. Otherwise:

        entry_spread      -- spread at signal time, under this bar's rolling fit
        mu_at_entry       -- 7-day rolling mean of the spread
        sigma_at_entry    -- 7-day rolling std. THE unit for the stop and for
                             sizing. Not the OU noise parameter.
        z_at_entry        -- (entry_spread - mu) / sigma, signed
        beta_at_entry     -- rolling hedge ratio, frozen here for the trade's life
        alpha_at_entry    -- rolling intercept, likewise frozen
        theta_at_entry    -- OU mean-reversion speed, per hour. The RANKING key,
                             and NaN when the fit fails. Not a gate -- see Step 3.
        take_profit_level -- entry_spread - take_profit_pct * (entry_spread - mu)
    """
    a = np.asarray(price_a, dtype=float)
    b = np.asarray(price_b, dtype=float)

    # Step 1 -- rolling geometry at the current bar. Cheap, and it rejects the
    # overwhelming majority of candidates before anything expensive runs.
    pt = last_bar(a, b, bar_hours=bar_hours)
    if pt is None:
        return None

    # Step 2 -- the only entry condition: has it moved far enough?
    if abs(pt.z) < min_deviation_sigma:
        return None

    # Step 3 -- OU fit, for theta. Fitted on the spread this trade will actually
    # live in: beta/alpha frozen at this bar, over the same 7-day window the
    # z-score was measured on. Fitting compute_spread's static full-window OLS
    # instead would return a theta describing a different series.
    #
    # A failed fit yields NaN theta and does NOT decline the trade. Theta is the
    # RANKING key, not a gate: on the two-year panel only 40.8% of 3-sigma
    # candidates fit a positive theta, so declining the rest would discard nearly
    # six candidates in ten -- a filter nobody asked for, applied silently. At
    # 3 sigma many spreads are trending rather than stretched, and that is a
    # statement about the fit, not about whether the dislocation is tradeable.
    # The scanner ranks NaN-theta candidates last; they fill only the slots the
    # ranked ones did not want.
    #
    # fit_df=False: the Student-t tail parameter is ~95% of this call's cost and
    # nothing here reads it.
    window = entry_window_bars(bar_hours)
    spread_frozen = a[-window:] - pt.beta * b[-window:] - pt.alpha
    params = fit_ou_ewma(a[-window:], b[-window:], bar_hours=bar_hours,
                         spread=spread_frozen, fit_df=False)
    theta = (float(params.theta)
             if np.isfinite(params.theta) and params.theta > 0 else float("nan"))

    # Step 4 -- signal
    take_profit_level = pt.spread - take_profit_pct * (pt.spread - pt.mu)

    return {
        "entry_spread":      float(pt.spread),
        "mu_at_entry":       float(pt.mu),
        "sigma_at_entry":    float(pt.sigma),
        "z_at_entry":        float(pt.z),
        "beta_at_entry":     float(pt.beta),
        "alpha_at_entry":    float(pt.alpha),
        "theta_at_entry":    theta,
        "take_profit_level": float(take_profit_level),
    }


def generate_exit_signal(
    current_price_a: float,
    current_price_b: float,
    entry_signal: dict,
    hours_elapsed: float,
    stop_sigma: float = 0.5,
    max_hold_hours: float = 72.0,
) -> dict | None:
    """Evaluate exit conditions for an open pair trade, or None to keep holding.

    Parameters
    ----------
    current_price_a, current_price_b : float
        Scalar LOG prices at the current bar. Not arrays.
    entry_signal : dict
        The dict generate_entry_signal returned. Never modified. Reads
        entry_spread, mu_at_entry, sigma_at_entry, take_profit_level,
        beta_at_entry, alpha_at_entry.
    hours_elapsed : float
        Hours since entry, tracked by the caller.
    stop_sigma : float, default 0.5
        Adverse move from the ENTRY SPREAD that closes the trade, in 7-day
        rolling sigma. With a 3.0-sigma entry this puts the stop at 3.5 from mu.
    max_hold_hours : float, default 72.0
        Flat time cap. Previously this was min(a per-trade OU estimate, a 24h
        ceiling), which meant raising the ceiling did nothing -- the model
        estimate bound first, so a 72h holding rule could not be expressed at
        all. It is now just the number.

    Returns
    -------
    dict or None
        None if nothing fires. Otherwise exit_reason ("take_profit",
        "time_stop" or "adverse_move"), current_spread, entry_spread, pnl_pct
        and stop_sigma.

    Notes
    -----
    The spread is reconstructed with the coefficients frozen at entry, not
    re-estimated. Re-fitting the hedge ratio mid-trade would shift the spread
    baseline and make P&L accounting inconsistent.

    THE STOP IS A DISTANCE TRAVELLED FROM entry_spread, not a fixed level
    measured from mu. This is deliberate and load-bearing. An earlier version
    placed it at a fixed level, which made the stop closer the further from mu
    you entered and manufactured a huge spurious relationship between entry z
    and win rate -- 38.9% at z~1.1 decaying to 1.7% above z=2.3, almost entirely
    an artifact of entries starting beyond their own stop. It also matches how
    exit_sweep.py measured adverse excursions, which is where stop_sigma=0.5
    came from.

    Gate order: time stop, then adverse move, then take profit. A trade that has
    both stopped out and exceeded max_hold_hours reports "time_stop".
    """
    # Step 1 -- reconstruct the current spread under frozen entry coefficients
    current_spread = (current_price_a
                      - entry_signal["alpha_at_entry"]
                      - entry_signal["beta_at_entry"] * current_price_b)

    # Step 2 -- entry state
    entry_spread = entry_signal["entry_spread"]
    mu           = entry_signal["mu_at_entry"]
    take_profit  = entry_signal["take_profit_level"]

    # Step 3 -- fraction of the available move captured so far
    pnl_pct = abs(current_spread - entry_spread) / abs(entry_spread - mu)

    def _exit(reason: str) -> dict:
        return {
            "exit_reason":    reason,
            "current_spread": float(current_spread),
            "entry_spread":   float(entry_spread),
            "pnl_pct":        float(pnl_pct),
            "stop_sigma":     float(stop_sigma),
        }

    # Step 4 -- stop distance, in the same rolling sigma the entry was measured in
    stop_distance = stop_sigma * entry_signal["sigma_at_entry"]

    # Step 5 -- time stop, unconditional, checked first
    if hours_elapsed >= max_hold_hours:
        return _exit("time_stop")

    # Step 6 -- adverse move, measured from entry_spread
    if entry_spread > mu:
        if current_spread >= entry_spread + stop_distance:
            return _exit("adverse_move")
    else:
        if current_spread <= entry_spread - stop_distance:
            return _exit("adverse_move")

    # Step 7 -- take profit, direction derived from entry
    if entry_spread > mu:
        if current_spread <= take_profit:
            return _exit("take_profit")
    else:
        if current_spread >= take_profit:
            return _exit("take_profit")

    return None
