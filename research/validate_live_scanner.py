"""Validate the live scanner's persistence: ledger schema, state, equity.

The ledger check is the point. docs/HANDOFF.md records a ledger corruption
incident whose root cause was never identified; pandas' to_csv(mode="a") writing
a close row under an open row's header is exactly how you produce one.

Run: python research/validate_live_scanner.py
"""
import sys, os, json, shutil, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

import live_scanner as ls
from portfolio import Portfolio

n_pass = n_fail = 0
T0 = datetime(2026, 9, 1, 0, 0)


def check(name, ok, detail=""):
    global n_pass, n_fail
    ok = bool(ok)
    n_pass, n_fail = n_pass + ok, n_fail + (not ok)
    print(f"{name + ':':60s} {str(detail)[:26]:28s} {'PASS' if ok else 'FAIL'}")


def cand(a, b, theta, z=3.5, sigma=0.02):
    return {"ticker_a": a, "ticker_b": b, "entry_spread": z * sigma,
            "mu_at_entry": 0.0, "sigma_at_entry": sigma, "z_at_entry": z,
            "beta_at_entry": 1.0, "alpha_at_entry": 0.0,
            "theta_at_entry": theta, "take_profit_level": 0.0}


tmp = tempfile.mkdtemp()
ls.LEDGER_PATH = os.path.join(tmp, "trades.csv")
ls.STATE_PATH = os.path.join(tmp, "state.json")
ls.CANDIDATES_PATH = os.path.join(tmp, "candidates.json")

print("=" * 104)
print("1. Ledger: open rows then close rows land on the SAME fixed schema")
print("=" * 104)
pf = Portfolio(equity=300.0, max_slots=3)
frame = pd.DataFrame([cand("A", "B", 0.2), cand("C", "D", 0.1), cand("E", "F", 0.05)])
opened = pf.fill_slots(frame, T0)

ls.append_ledger([{"event": "open", "trade_num": p.trade_num,
                   "ticker_a": p.ticker_a, "ticker_b": p.ticker_b,
                   "time": T0, **p.signal, **p.sizing} for p in opened])
after_open = pd.read_csv(ls.LEDGER_PATH)
check("open batch written", len(after_open) == 3, f"{len(after_open)} rows")
check("header is the full fixed schema",
      list(after_open.columns) == ls.LEDGER_COLUMNS, f"{len(after_open.columns)} cols")

closed = pf.evaluate_exits({"A": 0.0, "B": 0.0, "C": 0.07, "D": 0.0,
                            "E": 0.07, "F": 0.0}, T0 + timedelta(hours=2))
ls.append_ledger([{"event": "close", "time": c["closed_at"], **c} for c in closed])
d = pd.read_csv(ls.LEDGER_PATH)
check("close batch appended", len(d) == 3 + len(closed), f"{len(d)} rows")
check("schema unchanged after appending a close",
      list(d.columns) == ls.LEDGER_COLUMNS, f"{len(d.columns)} cols")

# The corruption tell: values filed under the wrong column name.
op, cl = d[d.event == "open"], d[d.event == "close"]
check("open rows carry entry fields, not exit ones",
      bool(op.z_at_entry.notna().all() and op.exit_reason.isna().all()))
check("close rows carry exit fields AND entry fields",
      bool(cl.exit_reason.notna().all() and cl.realized_pnl_net.notna().all()
           and cl.z_at_entry.notna().all()))
check("no unnamed/overflow columns",
      not any(str(c).startswith("Unnamed") for c in d.columns))
check("trade_num is a clean integer throughout",
      bool(pd.to_numeric(d.trade_num, errors="coerce").notna().all()))

print()
print("=" * 104)
print("2. A row with extra keys cannot widen or shift the schema")
print("=" * 104)
ls.append_ledger([{"event": "close", "time": T0, "trade_num": 99,
                   "ticker_a": "Z", "ticker_b": "Y", "realized_pnl_net": 1.0,
                   "some_new_field": "should be dropped", "another": 123}])
d2 = pd.read_csv(ls.LEDGER_PATH)
check("unknown keys dropped", "some_new_field" not in d2.columns)
check("schema still exactly the fixed list",
      list(d2.columns) == ls.LEDGER_COLUMNS, f"{len(d2.columns)} cols")
check("the row still landed", int(d2.trade_num.max()) == 99)

print()
print("=" * 104)
print("3. State round-trips: positions resume identically")
print("=" * 104)
pf2 = Portfolio(equity=300.0, max_slots=3)
pf2.fill_slots(frame, T0)
ls.save_portfolio(pf2)
check("state file written", os.path.exists(ls.STATE_PATH))
check("written atomically (no .tmp left behind)",
      not os.path.exists(ls.STATE_PATH + ".tmp"))

restored = ls.load_portfolio()
check("same number of open positions",
      len(restored.open_positions) == len(pf2.open_positions),
      f"{len(restored.open_positions)}")
check("same pairs, same order",
      [p.pair for p in restored.open_positions] == [p.pair for p in pf2.open_positions])
check("next_trade_num carried", restored.next_trade_num == pf2.next_trade_num,
      f"{restored.next_trade_num}")
a, b = restored.open_positions[0], pf2.open_positions[0]
check("frozen entry signal identical",
      all(np.isclose(a.signal[k], b.signal[k]) for k in a.signal
          if isinstance(b.signal[k], float)))
check("sizing identical", np.isclose(a.sizing["gross_notional"], b.sizing["gross_notional"]))
check("direction preserved", a.direction == b.direction, f"{a.direction}")
check("opened_at preserved", a.opened_at == b.opened_at, str(a.opened_at))

print()
print("=" * 104)
print("4. Equity is re-summed from the ledger, never trusted from state")
print("=" * 104)
realized = float(pd.to_numeric(pd.read_csv(ls.LEDGER_PATH)
                               .query("event == 'close'")["realized_pnl_net"],
                               errors="coerce").fillna(0).sum())
check("equity == ACCOUNT_EQUITY + sum(realized)",
      abs(restored.equity - (ls.ACCOUNT_EQUITY + realized)) < 1e-9,
      f"{restored.equity:.4f}")
# Corrupt the state file's equity; the ledger must still win.
st = json.load(open(ls.STATE_PATH)); st["equity"] = 999999.0
json.dump(st, open(ls.STATE_PATH, "w"), default=str)
check("a wrong equity in the state file is ignored",
      abs(ls.load_portfolio().equity - (ls.ACCOUNT_EQUITY + realized)) < 1e-9,
      "ledger wins")

print()
print("=" * 104)
print("5. Missing / empty files start clean rather than crashing")
print("=" * 104)
os.remove(ls.LEDGER_PATH); os.remove(ls.STATE_PATH)
fresh = ls.load_portfolio()
check("no state, no ledger -> flat book at starting equity",
      len(fresh.open_positions) == 0 and fresh.equity == ls.ACCOUNT_EQUITY,
      f"equity {fresh.equity}")
# A ledger holding only open rows has no realized_pnl_net values at all.
ls.append_ledger([{"event": "open", "trade_num": 1, "ticker_a": "A",
                   "ticker_b": "B", "time": T0, **cand("A", "B", 0.2)}])
check("a ledger with only open rows does not crash equity recompute",
      ls.load_portfolio().equity == ls.ACCOUNT_EQUITY, "300.0")

shutil.rmtree(tmp, ignore_errors=True)
print()
print("=" * 104)
print(f"{n_pass}/{n_pass + n_fail} assertions PASS")
print("=" * 104)
sys.exit(1 if n_fail else 0)
