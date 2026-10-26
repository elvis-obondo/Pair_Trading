"""Validate compute_position_size: equity-fraction sizing at fixed leverage.

Run: python research/validate_position_sizer.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

from position_sizer import compute_position_size

n_pass = n_fail = 0


def check(name, got, exp, tol=1e-9):
    global n_pass, n_fail
    if isinstance(exp, (bool, str, type(None))):
        ok = got == exp
        detail = f"got={got!r} expected={exp!r}"
    else:
        ok = got is not None and abs(got - exp) <= tol
        detail = f"got={got!r} expected={exp!r}"
    n_pass, n_fail = n_pass + ok, n_fail + (not ok)
    print(f"{name + ':':44s} {detail:44s} {'PASS' if ok else 'FAIL'}")


EQUITY = 300.0
FRAC = 0.05
LEV = 20.0

# --------------------------------------------------------------------------
print("=" * 96)
print("1. The rule: gross = leverage * capital_frac * equity, margin = capital_frac * equity")
print("=" * 96)
r = compute_position_size({"beta_at_entry": 1.0}, equity=EQUITY,
                          capital_frac=FRAC, leverage=LEV)
check("gross_notional == 20 * 0.05 * 300", r["gross_notional"], 300.0)
check("margin == 5% of equity", r["margin"], 15.0)
check("margin == gross / leverage", r["margin"], r["gross_notional"] / LEV)
check("leverage echoed", r["leverage"], LEV)
check("not rejected", r["rejected"], False)
check("reject_reason None", r["reject_reason"], None)

# --------------------------------------------------------------------------
print()
print("=" * 96)
print("2. Leg split by |beta| -- leg_a + abs(leg_b) == gross for either sign")
print("=" * 96)
check("beta=1  -> leg_a", r["leg_a_notional"], 150.0)
check("beta=1  -> leg_b", r["leg_b_notional"], 150.0)

r2 = compute_position_size({"beta_at_entry": -2.0}, equity=EQUITY,
                           capital_frac=FRAC, leverage=LEV)
check("beta=-2 -> leg_a", r2["leg_a_notional"], 100.0)
check("beta=-2 -> leg_b (signed)", r2["leg_b_notional"], -200.0)
check("beta=-2 -> gross unchanged", r2["leg_a_notional"] + abs(r2["leg_b_notional"]), 300.0)
check("beta=-2 -> margin unchanged", r2["margin"], 15.0)

r3 = compute_position_size({"beta_at_entry": 0.0}, equity=EQUITY,
                           capital_frac=FRAC, leverage=LEV)
check("beta=0  -> whole notional on leg A", r3["leg_a_notional"], 300.0)
check("beta=0  -> leg_b zero", r3["leg_b_notional"], 0.0)

# --------------------------------------------------------------------------
print()
print("=" * 96)
print("3. Sizing compounds with equity, and is blind to the pair")
print("=" * 96)
r_up = compute_position_size({"beta_at_entry": 1.0}, equity=600.0,
                             capital_frac=FRAC, leverage=LEV)
check("equity doubles -> gross doubles", r_up["gross_notional"], 600.0)
check("equity doubles -> margin doubles", r_up["margin"], 30.0)
r_dn = compute_position_size({"beta_at_entry": 1.0}, equity=150.0,
                             capital_frac=FRAC, leverage=LEV)
check("equity halves -> gross halves", r_dn["gross_notional"], 150.0)

# A ten-slot book at 5% posts half the account as margin.
check("10 slots post 50% of equity", 10 * r["margin"] / EQUITY, 0.5)

# --------------------------------------------------------------------------
print()
print("=" * 96)
print("4. Margin rejection returns the dict, not None")
print("=" * 96)
r_rej = compute_position_size({"beta_at_entry": 1.0}, equity=EQUITY,
                              capital_frac=FRAC, leverage=LEV,
                              available_margin=10.0)
check("available 10 < margin 15 -> rejected", r_rej["rejected"], True)
check("reject_reason == 'margin'", r_rej["reject_reason"], "margin")
check("is a dict, not None", r_rej is not None, True)
check("numbers still reported for logging", r_rej["margin"], 15.0)

r_ok = compute_position_size({"beta_at_entry": 1.0}, equity=EQUITY,
                             capital_frac=FRAC, leverage=LEV,
                             available_margin=15.0)
check("available exactly equals margin -> allowed", r_ok["rejected"], False)

# --------------------------------------------------------------------------
print()
print("=" * 96)
print("5. max_notional caps gross AND the margin it posts")
print("=" * 96)
# Below the cap: no effect at all.
small = compute_position_size({"beta_at_entry": 1.0}, equity=EQUITY,
                              capital_frac=FRAC, leverage=LEV, max_notional=5000.0)
check("uncapped while equity is small", small["gross_notional"], 300.0)
check("not flagged as capped", small["notional_capped"], False)

# The cap binds at equity = max_notional / (leverage * capital_frac) = 5000.
big = compute_position_size({"beta_at_entry": 1.0}, equity=50_000.0,
                            capital_frac=FRAC, leverage=LEV, max_notional=5000.0)
check("gross clamped to the ceiling", big["gross_notional"], 5000.0)
check("flagged as capped", big["notional_capped"], True)
check("margin follows the CAPPED notional", big["margin"], 250.0)
check("legs still sum to the capped gross",
      big["leg_a_notional"] + abs(big["leg_b_notional"]), 5000.0)
check("binds exactly at equity = cap/(lev*frac)",
      compute_position_size({"beta_at_entry": 1.0}, equity=5000.0,
                            capital_frac=FRAC, leverage=LEV,
                            max_notional=5000.0)["gross_notional"], 5000.0)
check("just below that it does not bind",
      compute_position_size({"beta_at_entry": 1.0}, equity=4999.0,
                            capital_frac=FRAC, leverage=LEV,
                            max_notional=5000.0)["notional_capped"], False)
check("a capped position leaves margin free for others",
      big["margin"] < FRAC * 50_000.0, True)

print()
print("=" * 96)
print("6. Unusable inputs return None")
print("=" * 96)
cases = [
    ("beta NaN",          {"beta_at_entry": np.nan}, dict(equity=EQUITY)),
    ("beta inf",          {"beta_at_entry": np.inf}, dict(equity=EQUITY)),
    ("equity zero",       {"beta_at_entry": 1.0},    dict(equity=0.0)),
    ("equity negative",   {"beta_at_entry": 1.0},    dict(equity=-300.0)),
    ("equity NaN",        {"beta_at_entry": 1.0},    dict(equity=np.nan)),
    ("capital_frac zero", {"beta_at_entry": 1.0},    dict(equity=EQUITY, capital_frac=0.0)),
    ("capital_frac neg",  {"beta_at_entry": 1.0},    dict(equity=EQUITY, capital_frac=-0.05)),
    ("leverage zero",     {"beta_at_entry": 1.0},    dict(equity=EQUITY, leverage=0.0)),
    ("available NaN",     {"beta_at_entry": 1.0},    dict(equity=EQUITY, available_margin=np.nan)),
    ("max_notional zero",  {"beta_at_entry": 1.0},    dict(equity=EQUITY, max_notional=0.0)),
    ("max_notional neg",   {"beta_at_entry": 1.0},    dict(equity=EQUITY, max_notional=-100.0)),
    ("max_notional NaN",   {"beta_at_entry": 1.0},    dict(equity=EQUITY, max_notional=np.nan)),
]
for label, sig, kw in cases:
    out = compute_position_size(sig, **kw)
    ok = out is None
    n_pass, n_fail = n_pass + ok, n_fail + (not ok)
    print(f"{label + ':':44s} {'got ' + repr(out)[:38]:44s} {'PASS' if ok else 'FAIL'}")

print()
print("=" * 96)
print(f"{n_pass}/{n_pass + n_fail} assertions PASS")
print("=" * 96)
sys.exit(1 if n_fail else 0)
