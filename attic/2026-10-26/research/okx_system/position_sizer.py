"""Position sizing: a fixed fraction of equity, deployed at a fixed leverage.

THE RULE

    gross_notional = leverage * capital_frac * equity
    margin         = gross_notional / leverage   ==  capital_frac * equity

So each position commits `capital_frac` of the account as margin and controls
`leverage` times that in notional. At the settled 5% / 20x this is one account's
worth of gross notional per position, and ten concurrent positions commit half
the account as margin -- inside the 20x venue ceiling with room to spare.

WHY A FRACTION OF EQUITY RATHER THAN A DOLLAR CONSTANT

The previous rule was `target_leverage * TRADE_CAPITAL`, a hardcoded $300 that
never moved with the account: a winning run stayed at $300 and a losing one kept
betting $300 of a shrinking balance. Sizing off equity compounds in both
directions and needs no manual adjustment as the balance changes.

WHAT THIS RULE DOES NOT DO

It is volatility-blind. Because gross notional is the same fraction of equity on
every pair, the dollar loss at the stop still scales with that pair's rolling
sigma -- roughly 0.65% of equity on the median pair and 3.4% at the 99th
percentile. research/risk_sim.py measures the alternative (size off the stop
distance so every stop-out costs the same) and finds it materially lower-ruin.
Recorded here because the difference is real and measured, not to argue it.

THE LEG SPLIT

The pair is two notionals, not one. leg A gets gross/(1+|beta|) and leg B gets
beta times that, so leg_a + abs(leg_b) == gross_notional exactly for either sign
of beta. leg_b_notional carries beta's sign: negative means leg B is short while
leg A is long. Callers derive direction separately (side_a/side_b) and take
abs() when converting to a quantity.

MARGIN IS CHARGED ON GROSS, both legs, because that is what the venue charges.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np


def compute_position_size(
    entry_signal: dict,
    equity: float,
    capital_frac: float = 0.05,
    leverage: float = 20.0,
    available_margin: float | None = None,
    max_notional: float | None = None,
) -> dict | None:
    """Size one pair position as a fixed fraction of account equity.

    Parameters
    ----------
    entry_signal : dict
        Dict returned by generate_entry_signal. Exactly one field is read:
            beta_at_entry (float) -- rolling hedge ratio (dimensionless); must be
                                     finite; may be negative, which reverses leg B.
    equity : float
        Account equity in dollars. Must be finite and strictly positive. This is
        the real balance, not a per-trade slice -- the whole point of the rule is
        that size tracks the account.
    capital_frac : float, default 0.05
        Fraction of equity committed as margin by this position. The settled
        configuration runs 10 concurrent positions at 0.05, so a full book posts
        50% of equity as margin.
    leverage : float, default 20.0
        Notional multiple on the committed margin. 20x is the venue ceiling.
    max_notional : float or None, default None
        Hard ceiling on gross notional, in dollars. A percentage-of-equity rule
        compounds without bound, and a position eventually exceeds the depth of
        the pair it is trading -- an uncapped run of this spec reported
        $36.5M from $300 with 70% of its trades sized past any plausible book.
        The ceiling makes the account curve physically meaningful; it binds only
        once equity reaches max_notional / (leverage * capital_frac). None
        leaves size uncapped.
    available_margin : float or None, default None
        Margin still free across the whole book. None means the full `equity` is
        available, which is correct for a single-position strategy. The portfolio
        manager passes `equity - used_margin` once more than one position can be
        open at a time; nothing else about this function changes then.

    Returns
    -------
    dict with keys:
        leg_a_notional (float, dollars) -- always positive when inputs are valid.
        leg_b_notional (float, dollars) -- carries beta's sign. Do not take abs()
                                           for interpretation; callers take it
                                           only when converting to a quantity.
        gross_notional (float, dollars) -- leg_a + abs(leg_b), the margined base.
        margin         (float, dollars) -- gross_notional / leverage.
        leverage       (float)          -- echoed back for logging/traceability.
        rejected       (bool)           -- True if margin exceeds available_margin.
        reject_reason  (str or None)    -- "margin", or None.
    None
        Only for unusable inputs: non-finite beta, or non-finite/non-positive
        equity, capital_frac or leverage. A margin rejection is NOT None -- it
        returns the dict with rejected=True, so the caller can log the actual
        numbers instead of a bare "sizer returned None".
    """
    # Step 1 -- extract
    beta = entry_signal["beta_at_entry"]

    # Step 2 -- validate everything before returning, so one bad field does not
    # mask another behind short-circuit evaluation.
    invalid = (
        not np.isfinite(beta)
        or not np.isfinite(equity)       or equity <= 0
        or not np.isfinite(capital_frac) or capital_frac <= 0
        or not np.isfinite(leverage)     or leverage <= 0
    )
    if available_margin is not None:
        invalid = invalid or not np.isfinite(available_margin)
    if max_notional is not None:
        invalid = invalid or not np.isfinite(max_notional) or max_notional <= 0
    if invalid:
        return None

    # Step 3 -- notional and margin
    gross_notional = leverage * capital_frac * equity
    if max_notional is not None:
        gross_notional = min(gross_notional, max_notional)
    # Margin follows the CAPPED notional, so a capped position posts less margin
    # and frees room for another. Deriving margin from the uncapped figure would
    # silently hold capital against size that is not deployed.
    margin = gross_notional / leverage

    # Step 4 -- split across legs by |beta|
    leg_a_notional = gross_notional / (1.0 + abs(beta))
    leg_b_notional = beta * leg_a_notional

    # Step 5 -- margin check against what is actually free
    available = equity if available_margin is None else available_margin
    rejected = margin > available

    return {
        "leg_a_notional": float(leg_a_notional),
        "leg_b_notional": float(leg_b_notional),
        "gross_notional": float(gross_notional),
        "margin":         float(margin),
        "leverage":       float(leverage),
        "notional_capped": bool(max_notional is not None
                                and gross_notional >= max_notional - 1e-9),
        "rejected":       bool(rejected),
        "reject_reason":  "margin" if rejected else None,
    }
