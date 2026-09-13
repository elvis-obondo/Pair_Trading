"""Validate the slot manager: caps, margin, ranking, occupancy, equity.

Run: python research/validate_portfolio.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from portfolio import Portfolio, Position, ROUND_TRIP_COST_FRAC

n_pass = n_fail = 0
T0 = datetime(2026, 9, 1, 0, 0)


def check(name, ok, detail=""):
    global n_pass, n_fail
    ok = bool(ok)
    n_pass, n_fail = n_pass + ok, n_fail + (not ok)
    print(f"{name + ':':60s} {str(detail)[:26]:28s} {'PASS' if ok else 'FAIL'}")


def cand(a, b, theta, z=3.5, sigma=0.02, mu=0.0, beta=1.0):
    """One candidate row, as scanner.scan() emits it."""
    entry = mu + z * sigma
    return {"ticker_a": a, "ticker_b": b, "entry_spread": entry,
            "mu_at_entry": mu, "sigma_at_entry": sigma, "z_at_entry": z,
            "beta_at_entry": beta, "alpha_at_entry": 0.0,
            "theta_at_entry": theta, "take_profit_level": mu}


def frame(rows):
    """Ranked the way scan() ranks: theta descending, NaN last."""
    return (pd.DataFrame(rows)
            .sort_values("theta_at_entry", ascending=False, na_position="last")
            .reset_index(drop=True))


# --------------------------------------------------------------------------
print("=" * 104)
print("1. Slot cap")
print("=" * 104)
p = Portfolio(equity=300.0, max_slots=10)
many = frame([cand(f"A{i}", f"B{i}", 0.2 - i * 0.001) for i in range(40)])
opened = p.fill_slots(many, T0)
check("never exceeds max_slots", len(p.open_positions) == 10, f"{len(p.open_positions)} open")
check("returns exactly what it opened", len(opened) == 10, f"{len(opened)}")
check("free_slots hits zero", p.free_slots == 0)
check("a second fill on a full book takes nothing",
      len(p.fill_slots(many, T0)) == 0)

print()
print("=" * 104)
print("2. Taken best-theta-first, deterministically")
print("=" * 104)
p2 = Portfolio(equity=300.0, max_slots=3)
p2.fill_slots(many, T0)
took = [(q.ticker_a, q.signal["theta_at_entry"]) for q in p2.open_positions]
check("took the three fastest", [t[0] for t in took] == ["A0", "A1", "A2"], str([t[0] for t in took]))
check("in descending theta order",
      all(took[i][1] >= took[i + 1][1] for i in range(len(took) - 1)))
p2b = Portfolio(equity=300.0, max_slots=3)
p2b.fill_slots(many, T0)
check("deterministic across runs",
      [q.pair for q in p2b.open_positions] == [q.pair for q in p2.open_positions])

print()
print("=" * 104)
print("3. NaN-theta candidates are taken LAST, not dropped")
print("=" * 104)
mixed = frame([cand("FAST", "X", 0.20), cand("SLOW", "Y", 0.01),
               cand("NONE", "Z", float("nan"))])
p3 = Portfolio(equity=300.0, max_slots=3)
p3.fill_slots(mixed, T0)
order = [q.ticker_a for q in p3.open_positions]
check("all three taken, including the unranked", len(order) == 3, str(order))
check("unranked is last", order == ["FAST", "SLOW", "NONE"], str(order))
p3b = Portfolio(equity=300.0, max_slots=2)
p3b.fill_slots(mixed, T0)
check("with fewer slots the unranked one misses out",
      [q.ticker_a for q in p3b.open_positions] == ["FAST", "SLOW"])

print()
print("=" * 104)
print("4. Margin never exceeds equity")
print("=" * 104)
# 5% margin per position, so 20 positions would need 100% of equity.
p4 = Portfolio(equity=300.0, max_slots=40, capital_frac=0.05)
p4.fill_slots(many, T0)
check("total margin <= equity", p4.used_margin <= p4.equity + 1e-9,
      f"{p4.used_margin:.2f} of {p4.equity:.2f}")
check("stopped where margin ran out, not at the slot cap",
      len(p4.open_positions) == 20, f"{len(p4.open_positions)} open")
check("available_margin is exhausted", abs(p4.available_margin) < 1e-9,
      f"{p4.available_margin:.6f}")
# A rejection must not stop consideration of later candidates.
p4b = Portfolio(equity=100.0, max_slots=40, capital_frac=0.30)
p4b.fill_slots(many, T0)
check("a book at 30%/position fits exactly 3", len(p4b.open_positions) == 3,
      f"{len(p4b.open_positions)}")
check("margin still bounded", p4b.used_margin <= p4b.equity + 1e-9,
      f"{p4b.used_margin:.2f}")

print()
print("=" * 104)
print("5. One position per pair; re-entry after a close is allowed")
print("=" * 104)
dupes = frame([cand("A", "B", 0.2), cand("A", "B", 0.1), cand("C", "D", 0.05)])
p5 = Portfolio(equity=300.0, max_slots=10)
p5.fill_slots(dupes, T0)
check("the same pair is not opened twice", len(p5.open_positions) == 2,
      str([q.pair for q in p5.open_positions]))
# Force A/B out via the time stop, then offer it again.
closed = p5.evaluate_exits({"A": 0.07, "B": 0.0, "C": 0.07, "D": 0.0},
                           T0 + timedelta(hours=100))
check("time stop closes both at the 72h cap", len(closed) == 2,
      str([c["exit_reason"] for c in closed]))
reopened = p5.fill_slots(dupes, T0 + timedelta(hours=101))
check("re-entry on the same pair is allowed after a close",
      any(q.pair == ("A", "B") for q in p5.open_positions), str(len(reopened)))

print()
print("=" * 104)
print("6. Closing frees exactly one slot and exactly its margin")
print("=" * 104)
p6 = Portfolio(equity=300.0, max_slots=10)
p6.fill_slots(frame([cand(f"A{i}", f"B{i}", 0.2 - i * 0.01) for i in range(4)]), T0)
before_m, before_n = p6.used_margin, len(p6.open_positions)
one = p6.open_positions[0]
one_margin = one.margin
# Hold every pair AT its entry spread (no exit), then move only the first
# one back to mu so exactly one take-profit fires.
prices = {}
for q in p6.open_positions:
    prices[q.ticker_a] = q.signal["entry_spread"]
    prices[q.ticker_b] = 0.0
prices[one.ticker_a] = 0.0
out = p6.evaluate_exits(prices, T0 + timedelta(hours=1))
check("exactly one position closed", len(out) == 1, str(len(out)))
check("slot count drops by one", len(p6.open_positions) == before_n - 1)
check("margin drops by exactly that position's margin",
      abs((before_m - p6.used_margin) - one_margin) < 1e-9,
      f"{before_m - p6.used_margin:.4f} vs {one_margin:.4f}")
check("exit reason is take_profit", out[0]["exit_reason"] == "take_profit",
      out[0]["exit_reason"])

print()
print("=" * 104)
print("7. Occupancy: a slot stays taken until its own exit fires")
print("=" * 104)
p7 = Portfolio(equity=300.0, max_slots=2)
p7.fill_slots(frame([cand("A", "B", 0.2), cand("C", "D", 0.1)]), T0)
# Nothing has moved: no exit, so no slot frees and nothing new is taken.
held = p7.evaluate_exits({"A": 0.07, "B": 0.0, "C": 0.07, "D": 0.0},
                         T0 + timedelta(hours=1))
check("nothing closes when nothing has moved", len(held) == 0)
check("a fresh candidate cannot jump in",
      len(p7.fill_slots(frame([cand("E", "F", 0.99)]), T0 + timedelta(hours=1))) == 0,
      "book full")
check("still two open", len(p7.open_positions) == 2)

print()
print("=" * 104)
print("8. Equity compounds and P&L signs are right")
print("=" * 104)
p8 = Portfolio(equity=300.0, max_slots=1)
p8.fill_slots(frame([cand("A", "B", 0.2, z=3.5, sigma=0.02)]), T0)
size_first = p8.open_positions[0].sizing["gross_notional"]
# Entry above mu -> short the spread -> spread falling to mu is a WIN.
w = p8.evaluate_exits({"A": 0.0, "B": 0.0}, T0 + timedelta(hours=2))
check("reverting to mu from above is a win", w[0]["realized_pnl_net"] > 0,
      f"{w[0]['realized_pnl_net']:+.2f}")
check("equity rose", p8.equity > 300.0, f"{p8.equity:.2f}")
p8.fill_slots(frame([cand("C", "D", 0.2, z=3.5, sigma=0.02)]), T0 + timedelta(hours=3))
check("next position is larger on the larger equity",
      p8.open_positions[0].sizing["gross_notional"] > size_first,
      f"{size_first:.2f} -> {p8.open_positions[0].sizing['gross_notional']:.2f}")

# Losing side: spread moves further away -> adverse move -> loss.
p8b = Portfolio(equity=300.0, max_slots=1)
p8b.fill_slots(frame([cand("A", "B", 0.2, z=3.5, sigma=0.02)]), T0)
l = p8b.evaluate_exits({"A": 0.07 + 0.5 * 0.02, "B": 0.0}, T0 + timedelta(hours=1))
check("moving further from mu stops out", l[0]["exit_reason"] == "adverse_move",
      l[0]["exit_reason"])
check("and it is a loss", l[0]["realized_pnl_net"] < 0, f"{l[0]['realized_pnl_net']:+.2f}")
check("equity fell", p8b.equity < 300.0, f"{p8b.equity:.2f}")
check("R at a full stop-out is about -1",
      -1.25 < l[0]["r"] < -0.9, f"R={l[0]['r']:.3f}")

print()
print("=" * 104)
print("9. Costs are charged, and equity never drifts")
print("=" * 104)
p9 = Portfolio(equity=300.0, max_slots=1)
p9.fill_slots(frame([cand("A", "B", 0.2, z=3.5, sigma=0.02)]), T0)
pos = p9.open_positions[0]
flat = p9.evaluate_exits({"A": pos.signal["entry_spread"], "B": 0.0},
                         T0 + timedelta(hours=100))
check("an unchanged spread still costs the round trip",
      flat[0]["realized_pnl_net"] < 0, f"{flat[0]['realized_pnl_net']:+.4f}")
check("the cost is ROUND_TRIP_COST_FRAC of gross",
      abs(flat[0]["realized_pnl_net"]
          + ROUND_TRIP_COST_FRAC * pos.sizing["gross_notional"]) < 1e-9)
check("equity == start + sum(realized), not an accumulator",
      abs(p9.equity - (300.0 + sum(c["realized_pnl_net"] for c in p9.closed))) < 1e-12,
      f"{p9.equity:.6f}")

print()
print("=" * 104)
print("10. stop_fill_overshoot: adverse exits book at a MEASURED multiple")
print("=" * 104)
import book_state as _bs
SG, SS = 0.02, 0.5
MEAS = _bs.MEASURED_STOP_OVERSHOOT
for label, z in (("entered ABOVE mu (short spread)", 3.5),
                 ("entered BELOW mu (long spread)", -3.5)):
    real = Portfolio(equity=300.0, max_slots=1, stop_sigma=SS)
    meas = Portfolio(equity=300.0, max_slots=1, stop_sigma=SS,
                     stop_fill_overshoot=MEAS)
    perf = Portfolio(equity=300.0, max_slots=1, stop_sigma=SS,
                     stop_fill_overshoot=1.0)
    c = frame([cand("A", "B", 0.2, z=z, sigma=SG)])
    for pf_ in (real, meas, perf):
        pf_.fill_slots(c, T0)
    entry = z * SG
    # Blow well past the stop so the unmodelled book fills far out.
    far = entry + (3.0 * SS * SG if z > 0 else -3.0 * SS * SG)
    when = T0 + timedelta(hours=1)
    r_out = real.evaluate_exits({"A": far, "B": 0.0}, when)[0]
    m_out = meas.evaluate_exits({"A": far, "B": 0.0}, when)[0]
    p_out = perf.evaluate_exits({"A": far, "B": 0.0}, when)[0]
    print(f"  {label}")
    check("   all three stop out",
          r_out["exit_reason"] == m_out["exit_reason"] == p_out["exit_reason"] == "adverse_move")
    check("   None books where the spread WAS", abs(r_out["r"]) > 2.5, f"R={r_out['r']:.2f}")
    check("   1.00x books at the level (R ~ -1)", -1.2 < p_out["r"] < -1.0,
          f"R={p_out['r']:.3f}")
    check(f"   {MEAS}x is slightly worse than 1.00x",
          m_out["r"] < p_out["r"], f"{m_out['r']:.3f} < {p_out['r']:.3f}")
    check("   ... and much better than the unmodelled fill",
          m_out["r"] > r_out["r"], f"{r_out['r']:.2f} -> {m_out['r']:.2f}")
    # The fill must land exactly `overshoot` stop-distances past entry.
    want = entry - (-1.0 if z > 0 else 1.0) * SS * SG * MEAS
    check("   fill lands exactly overshoot*distance past entry",
          abs(m_out["exit_spread"] - want) < 1e-12, f"{m_out['exit_spread']:.6f}")
    check("   the row records the multiple it used",
          abs(m_out["stop_fill_overshoot"] - MEAS) < 1e-12
          and np.isnan(r_out["stop_fill_overshoot"]), f"{m_out['stop_fill_overshoot']}")

# Non-stop exits must be untouched.
real = Portfolio(equity=300.0, max_slots=1, stop_sigma=SS)
meas = Portfolio(equity=300.0, max_slots=1, stop_sigma=SS, stop_fill_overshoot=MEAS)
c = frame([cand("A", "B", 0.2, z=3.5, sigma=SG)])
real.fill_slots(c, T0); meas.fill_slots(c, T0)
rt = real.evaluate_exits({"A": 0.0, "B": 0.0}, T0 + timedelta(hours=2))[0]
ft = meas.evaluate_exits({"A": 0.0, "B": 0.0}, T0 + timedelta(hours=2))[0]
check("take_profit is identical under the setting",
      abs(rt["realized_pnl_net"] - ft["realized_pnl_net"]) < 1e-12, "unchanged")
check("take_profit records no overshoot", np.isnan(ft["stop_fill_overshoot"]))

# THE LIVE FOOTGUN: a Portfolio built with no argument must book real fills.
check("default Portfolio books ACTUAL fills (live safety)",
      Portfolio(equity=300.0).stop_fill_overshoot is None, "None")
import book_state as _bs2
check("load_portfolio does not model fills either",
      "stop_fill_overshoot" not in open(
          os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "book_state.py")).read().split("def load_portfolio")[1]
      .split("def save_portfolio")[0], "not passed")

print()
print("=" * 104)
print("11. Optional per-ticker concentration limit")
print("=" * 104)
hot = frame([cand("BILL", f"X{i}", 0.2 - i * 0.01) for i in range(6)])
p10 = Portfolio(equity=300.0, max_slots=10)
p10.fill_slots(hot, T0)
check("default (spec) allows one ticker to take the book",
      len(p10.open_positions) == 6, f"BILL in {p10.concentration().get('BILL', 0)}")
p10b = Portfolio(equity=300.0, max_slots=10, max_per_ticker=2)
p10b.fill_slots(hot, T0)
check("max_per_ticker=2 caps it", len(p10b.open_positions) == 2,
      f"BILL in {p10b.concentration().get('BILL', 0)}")

print()
print("=" * 104)
print("12. Net exposure — how market-neutral a 'market-neutral' position is")
print("=" * 104)
from position_sizer import compute_position_size


def pos_with(beta, z=3.5, sigma=0.02, mu=0.0):
    sig = cand("A", "B", 0.1, z=z, sigma=sigma, mu=mu, beta=beta)
    szg = compute_position_size(sig, equity=300.0, capital_frac=0.05, leverage=20.0)
    return Position(1, "A", "B", sig, szg, T0, 0.5)


# beta == 1 is the only value that is actually dollar-neutral.
p1 = pos_with(beta=1.0)
check("beta=1 is dollar-neutral", abs(p1.net_exposure) < 1e-9, f"{p1.net_exposure:+.2f}")
ea, eb = p1.exposure
check("  ... and the legs are on opposite sides", ea * eb < 0, f"{ea:+.1f} / {eb:+.1f}")

# beta == 0: leg B is nothing. This is a naked single-coin bet.
p0 = pos_with(beta=0.0)
check("beta=0 is fully directional",
      abs(abs(p0.net_exposure_frac) - 1.0) < 1e-9, f"{p0.net_exposure_frac:+.2f}")
check("  ... net exposure is the whole leg-A notional",
      abs(abs(p0.net_exposure) - p0.sizing["leg_a_notional"]) < 1e-9,
      f"{p0.net_exposure:+.2f}")

# beta < 0: both legs the SAME way, so net exceeds either leg. This is the case
# that reads as a hedge and is a doubling.
pn = pos_with(beta=-1.0)
ea, eb = pn.exposure
check("beta=-1 puts both legs on the same side", ea * eb > 0, f"{ea:+.1f} / {eb:+.1f}")
check("  ... net exposure exceeds either leg",
      abs(pn.net_exposure) > max(abs(ea), abs(eb)) + 1e-9, f"{pn.net_exposure:+.2f}")

# Direction flips every sign, and nothing else.
short = pos_with(beta=0.5, z=+3.5)
long_ = pos_with(beta=0.5, z=-3.5)
check("shorting the spread reverses both legs",
      all(abs(x + y) < 1e-9 for x, y in zip(short.exposure, long_.exposure)),
      f"{short.net_exposure:+.1f} vs {long_.net_exposure:+.1f}")

# THE invariant: exposure must be what pnl() actually implies, or the two drift
# apart and the ledger's exposure column becomes decoration.
for beta in (1.0, 0.5, 0.0, -0.8, 1.7):
    q = pos_with(beta=beta)
    d_log_a, d_log_b = 0.011, -0.004          # independent moves in each leg
    entry = q.signal["entry_spread"]
    exit_spread = entry + (d_log_a - beta * d_log_b)
    gross_pnl = q.pnl(exit_spread)[0] + ROUND_TRIP_COST_FRAC * q.sizing["gross_notional"]
    ea, eb = q.exposure
    implied = ea * d_log_a + eb * d_log_b
    check(f"exposure reproduces pnl at beta={beta:+.1f}",
          abs(gross_pnl - implied) < 1e-9, f"{gross_pnl:+.4f} vs {implied:+.4f}")

# And the ledger carries it, so this is answerable after the fact.
import book_state as _cfg
for col in ("r2_at_entry", "net_exposure", "net_exposure_frac"):
    check(f"ledger records {col}", col in _cfg.LEDGER_COLUMNS, "present")

print()
print("=" * 104)
print(f"{n_pass}/{n_pass + n_fail} assertions PASS")
print("=" * 104)
sys.exit(1 if n_fail else 0)
