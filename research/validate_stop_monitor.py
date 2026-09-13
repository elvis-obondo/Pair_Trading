"""Validate the tick-speed stop: where it fires, and where it refuses to.

Run: python research/validate_stop_monitor.py

The whole build exists because the 30-minute stop overshoots its level by a
median 1.53x. The test that matters is section 5: an exact-touch price path must
book an overshoot of essentially zero. Everything else guards the ways a fast
stop goes wrong -- firing on one bad print, firing on a stale price, or firing on
a price nobody could have traded.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import math
import tempfile
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import book_state as cfg

# EVERY path is redirected into a scratch directory BEFORE anything that could
# write is imported. This is not tidiness: an earlier version of this file
# redirected only LEDGER_PATH, and running it overwrote the live
# scanner_state.json and wiped the open paper book. A validator must not be able
# to touch the thing it validates.
TMP = tempfile.mkdtemp(prefix="validate_stop_monitor_")
cfg.DATA_DIR         = TMP
cfg.LOG_DIR          = os.path.join(TMP, "logs")
cfg.STATE_PATH       = os.path.join(TMP, "scanner_state.json")
cfg.LEDGER_PATH      = os.path.join(TMP, "scanner_trades.csv")
cfg.CANDIDATES_PATH  = os.path.join(TMP, "scanner_candidates.json")
cfg.SCAN_HISTORY_DIR = os.path.join(TMP, "scan_history")
cfg.TICKS_DIR        = os.path.join(TMP, "monitor_ticks")
cfg.LOCK_PATH        = os.path.join(TMP, "stop_monitor.lock")
cfg.MONITOR_LOG      = os.path.join(cfg.LOG_DIR, "stop_monitor.log")
cfg.HEARTBEAT_PATH   = os.path.join(cfg.LOG_DIR, "heartbeat.log")

_REAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scanner_state.json")
assert cfg.STATE_PATH != _REAL, "refusing to run against the live book"

from portfolio import Portfolio, Position    # noqa: E402 — after the redirect
from stop_monitor import StopMonitor, instrument_id   # noqa: E402

n_pass = n_fail = 0

# Epoch seconds for a fixed wall time, so hours_elapsed is deterministic.
T0_EPOCH = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc).timestamp()
T0_WALL = datetime(2026, 9, 1, 0, 0)


def check(name, ok, detail=""):
    global n_pass, n_fail
    ok = bool(ok)
    n_pass, n_fail = n_pass + ok, n_fail + (not ok)
    print(f"{name + ':':64s} {str(detail)[:24]:26s} {'PASS' if ok else 'FAIL'}")


def make_monitor(z=3.5, sigma=0.02, mu=0.0, beta=1.0, alpha=0.0,
                 confirm_ticks=1, stale=30.0, equity=300.0):
    """One open position on A/B, entered z sigma above (or below) mu."""
    pf = Portfolio(equity=equity, max_slots=10, stop_sigma=cfg.STOP_SIGMA,
                   max_hold_hours=cfg.MAX_HOLD_HOURS)
    entry = mu + z * sigma
    signal = {"entry_spread": entry, "mu_at_entry": mu, "sigma_at_entry": sigma,
              "z_at_entry": z, "beta_at_entry": beta, "alpha_at_entry": alpha,
              "theta_at_entry": 0.2, "take_profit_level": mu}
    sizing = {"leg_a_notional": 150.0, "leg_b_notional": 150.0,
              "gross_notional": 300.0, "margin": 15.0, "leverage": 20.0,
              "rejected": False, "reject_reason": None, "notional_capped": False}
    pf.open_positions.append(Position(1, "AAA", "BBB", signal, sizing, T0_WALL,
                                      cfg.STOP_SIGMA))
    m = StopMonitor(pf, dry_run=True, confirm_ticks=confirm_ticks,
                    stale_seconds=stale, record_ticks=False)
    return m


def push(m, spread, t, beta=1.0, alpha=0.0, pb=100.0):
    """Move leg A to produce exactly `spread`, holding leg B still.

    spread = log(pa) - beta*log(pb) - alpha, so pa follows from the rest.

    Leg B's quote is refreshed in the cache DIRECTLY rather than through on_tick,
    because B is not moving -- only its staleness clock is. Ticking it would
    trigger an evaluation against A's previous price, which is a real thing the
    monitor must handle but not what these tests are measuring.
    """
    from stop_monitor import Quote
    pa = math.exp(spread + beta * math.log(pb) + alpha)
    m.quotes[instrument_id("BBB")] = Quote(pb, pb, pb, t)
    return m.on_tick(instrument_id("AAA"), pa, pa, pa, now=t)


# --------------------------------------------------------------------------
print("=" * 118)
print("1. The monitor adds no geometry — it reconstructs the same spread as the book")
print("=" * 118)
m = make_monitor(beta=1.7, alpha=-0.4)
pos = m.pf.open_positions[0]
target = 0.0731
pa = math.exp(target + 1.7 * math.log(100.0) + (-0.4))
m.on_tick(instrument_id("AAA"), pa, pa, pa, now=T0_EPOCH)
m.on_tick(instrument_id("BBB"), 100.0, 100.0, 100.0, now=T0_EPOCH)
la, lb = m._log_prices(pos)
check("monitor spread == Position.current_spread",
      abs(pos.current_spread(la, lb) - target) < 1e-12,
      f"{pos.current_spread(la, lb):.10f}")

# --------------------------------------------------------------------------
print()
print("=" * 118)
print("2. The stop fires just past its level and not just short of it")
print("=" * 118)
sigma, z = 0.02, 3.5
entry = z * sigma
dist = cfg.STOP_SIGMA * sigma       # 0.5 sigma BEYOND entry, i.e. 4.0 from mu

m = make_monitor(z=z, sigma=sigma)
push(m, entry + dist * 0.999, T0_EPOCH + 1)
check("0.001 sigma SHORT of the stop does not fire", not m.closed_this_session,
      f"{len(m.closed_this_session)} closed")

m = make_monitor(z=z, sigma=sigma)
out = push(m, entry + dist * 1.001, T0_EPOCH + 1)
check("0.001 sigma PAST the stop fires", len(out) == 1 and
      out[0]["exit_reason"] == "adverse_move",
      out[0]["exit_reason"] if out else "none")

# --------------------------------------------------------------------------
print()
print("=" * 118)
print("3. Direction — a short-spread and a long-spread position stop opposite ways")
print("=" * 118)
m = make_monitor(z=+3.5, sigma=sigma)
check("entered above mu is SHORT the spread", m.pf.open_positions[0].direction == -1.0,
      m.pf.open_positions[0].direction)
out = push(m, entry + dist * 1.1, T0_EPOCH + 1)
check("  ... stops when the spread RISES", len(out) == 1 and
      out[0]["exit_reason"] == "adverse_move", "rose")

m = make_monitor(z=-3.5, sigma=sigma)
check("entered below mu is LONG the spread", m.pf.open_positions[0].direction == +1.0,
      m.pf.open_positions[0].direction)
out = push(m, -entry - dist * 1.1, T0_EPOCH + 1)
check("  ... stops when the spread FALLS", len(out) == 1 and
      out[0]["exit_reason"] == "adverse_move", "fell")
m = make_monitor(z=-3.5, sigma=sigma)
out = push(m, -entry + dist * 1.1, T0_EPOCH + 1)
check("  ... and NOT when it rises toward mu", not out, f"{len(out)} closed")

# --------------------------------------------------------------------------
print()
print("=" * 118)
print("4. Take profit fires at mu, in both directions")
print("=" * 118)
m = make_monitor(z=+3.5, sigma=sigma)
out = push(m, 0.0 - 1e-9, T0_EPOCH + 1)
check("short spread takes profit at mu", len(out) == 1 and
      out[0]["exit_reason"] == "take_profit", out[0]["exit_reason"] if out else "none")
m = make_monitor(z=+3.5, sigma=sigma)
out = push(m, entry * 0.5, T0_EPOCH + 1)
check("  ... but not half way there", not out, f"{len(out)} closed")
m = make_monitor(z=-3.5, sigma=sigma)
out = push(m, 0.0 + 1e-9, T0_EPOCH + 1)
check("long spread takes profit at mu", len(out) == 1 and
      out[0]["exit_reason"] == "take_profit", out[0]["exit_reason"] if out else "none")

# --------------------------------------------------------------------------
print()
print("=" * 118)
print("5. THE POINT OF THE BUILD — overshoot on an exact-touch path is ~0")
print("=" * 118)
print("   Baseline, 9,704 backtested stop-outs at 30-minute bar close:")
print("   median overshoot 1.53x, mean 2.07x, p90 3.26x. NONE inside the level.")
print()
m = make_monitor(z=z, sigma=sigma)
# Walk in 0.02-sigma steps, the fine-grained path a tick feed actually gives,
# instead of the 0.11-sigma median jump between 30-minute bars.
t = T0_EPOCH
booked = []
for i in range(1, 400):
    t += 1.0
    booked = push(m, entry + dist * (i * 0.04), t)
    if booked:
        break
over = booked[0]["overshoot_ratio"]
# entry sits at 3.5 sigma, the stop 0.5 beyond it, so an exact touch is 4.0/0.5.
check("overshoot_ratio at first breach", abs(over - 1.04) < 0.05, f"{over:.4f}x")
check("  ... vs the 1.53x median it replaces", over < 1.53, f"{over:.3f} < 1.53")

# A 30-minute bar that jumps the whole distance shows the failure being fixed.
m2 = make_monitor(z=z, sigma=sigma)
out2 = push(m2, entry + dist * 3.0, T0_EPOCH + 1800)
check("one 30-min-sized jump overshoots badly", out2[0]["overshoot_ratio"] > 2.9,
      f"{out2[0]['overshoot_ratio']:.2f}x")

# --------------------------------------------------------------------------
print()
print("=" * 118)
print("6. Confirmation — one bad print does not fire the stop")
print("=" * 118)
m = make_monitor(z=z, sigma=sigma, confirm_ticks=2)
out = push(m, entry + dist * 1.5, T0_EPOCH + 1)
check("first breach tick books nothing", not out, f"{len(out)} closed")
out = push(m, entry + dist * 0.2, T0_EPOCH + 2)
check("  ... a revert clears the breach", not out and not m._breach, "cleared")
out = push(m, entry + dist * 1.5, T0_EPOCH + 3)
check("  ... one breach again books nothing", not out, f"{len(out)} closed")
out = push(m, entry + dist * 1.5, T0_EPOCH + 4)
check("  ... two consecutive breaches book it", len(out) == 1, "closed")
check("  ... and confirm_delay_ms records the cost",
      abs(out[0]["confirm_delay_ms"] - 1000.0) < 1.0,
      f"{out[0]['confirm_delay_ms']:.0f}ms")

# --------------------------------------------------------------------------
print()
print("=" * 118)
print("7. Staleness — a blind position is never exited on an old price")
print("=" * 118)
m = make_monitor(z=z, sigma=sigma, stale=30.0)
pos = m.pf.open_positions[0]
push(m, entry, T0_EPOCH)          # both legs quoted at T0
check("both legs fresh -> not blind", not m.is_blind(pos, T0_EPOCH + 1), "fresh")
pa = math.exp(entry + dist * 2.0 + math.log(100.0))
out = m.on_tick(instrument_id("AAA"), pa, pa, pa, now=T0_EPOCH + 100)
check("a leg 100s stale -> BLIND, no exit booked", not out and
      m.is_blind(pos, T0_EPOCH + 100), "held")
check("  ... position still open", len(m.pf.open_positions) == 1,
      f"{len(m.pf.open_positions)} open")

# --------------------------------------------------------------------------
print()
print("=" * 118)
print("8. A feed outage is recorded, not hidden")
print("=" * 118)
m = make_monitor(z=z, sigma=sigma, stale=30.0)
push(m, entry, T0_EPOCH)                       # establishes last_eval
out = push(m, entry + dist * 2.5, T0_EPOCH + 7200)   # 2h gap, then past the stop
check("exit after a 2h gap is still booked", len(out) == 1, "closed")
check("  ... blind_gap_seconds ~ 7200",
      abs(out[0]["blind_gap_seconds"] - 7200) < 2, f"{out[0]['blind_gap_seconds']:.0f}s")
check("  ... feed_state flags it", out[0]["feed_state"] == "recovered_from_blind",
      out[0]["feed_state"])
m = make_monitor(z=z, sigma=sigma)
push(m, entry, T0_EPOCH)
out = push(m, entry + dist * 2.5, T0_EPOCH + 2)
check("a watched exit has no gap and reads 'live'",
      out[0]["blind_gap_seconds"] == 0.0 and out[0]["feed_state"] == "live",
      out[0]["feed_state"])

# --------------------------------------------------------------------------
print()
print("=" * 118)
print("9. The time stop belongs to the slow timer, not to ticks")
print("=" * 118)
m = make_monitor(z=z, sigma=sigma)
late = T0_EPOCH + cfg.MAX_HOLD_HOURS * 3600 + 60
out = push(m, entry, late)
check("a tick past max_hold does NOT fire the time stop", not out, f"{len(out)}")
closed = m.evaluate_positions(late, touched=None, check_time_stop=True)
check("the 60s sweep does", len(closed) == 1 and
      closed[0]["exit_reason"] == "time_stop",
      closed[0]["exit_reason"] if closed else "none")

# --------------------------------------------------------------------------
print()
print("=" * 118)
print("10. Entries are re-anchored to the price actually filled")
print("=" * 118)
sigma = 0.02
base = {"ticker_a": "AAA", "ticker_b": "BBB", "mu_at_entry": 0.0,
        "sigma_at_entry": sigma, "beta_at_entry": 1.0, "alpha_at_entry": 0.0,
        "theta_at_entry": 0.2, "entry_spread": 3.2 * sigma,
        "z_at_entry": 3.2, "take_profit_level": 0.0}

def fresh_monitor():
    pf = Portfolio(equity=300.0, max_slots=10, stop_sigma=cfg.STOP_SIGMA,
                   max_notional=cfg.MAX_NOTIONAL)
    # confirm_ticks=1: these sections test WHERE the stop sits, not the debounce
    # (section 6 owns that), and a 2-tick default would hide the boundary.
    return StopMonitor(pf, dry_run=True, confirm_ticks=1, record_ticks=False)

# Spread still at 3.2 sigma when we get the fill -> take it.
m = fresh_monitor()
pa = math.exp(3.2 * sigma + math.log(100.0))
m.on_tick(instrument_id("AAA"), pa, pa, pa, now=T0_EPOCH)
m.on_tick(instrument_id("BBB"), 100.0, 100.0, 100.0, now=T0_EPOCH)
opened = m.try_open([dict(base)], T0_EPOCH)
check("candidate still beyond 3 sigma is taken", len(opened) == 1, f"{len(opened)}")
if opened:
    p = opened[0]
    check("  ... entry_spread is the FILL, not the bar",
          abs(p.signal["entry_spread"] - 3.2 * sigma) < 1e-9,
          f"{p.signal['entry_spread']:.6f}")
    check("  ... bar z and fill z both recorded",
          p.entry_bar_z == 3.2 and abs(p.signal["z_at_entry"] - 3.2) < 1e-9,
          f"{p.entry_bar_z} / {p.signal['z_at_entry']:.3f}")

# Reverted to 2.4 sigma between the bar and the fill -> decline.
m = fresh_monitor()
pa = math.exp(2.4 * sigma + math.log(100.0))
m.on_tick(instrument_id("AAA"), pa, pa, pa, now=T0_EPOCH)
m.on_tick(instrument_id("BBB"), 100.0, 100.0, 100.0, now=T0_EPOCH)
check("candidate that reverted inside 3 sigma is skipped",
      not m.try_open([dict(base)], T0_EPOCH), "skipped")

# Flipped to the other side of mu -> decline.
m = fresh_monitor()
pa = math.exp(-3.4 * sigma + math.log(100.0))
m.on_tick(instrument_id("AAA"), pa, pa, pa, now=T0_EPOCH)
m.on_tick(instrument_id("BBB"), 100.0, 100.0, 100.0, now=T0_EPOCH)
check("candidate that crossed mu is skipped",
      not m.try_open([dict(base)], T0_EPOCH), "skipped")

# A stale quote must not be used to open, either.
m = fresh_monitor()
pa = math.exp(3.2 * sigma + math.log(100.0))
m.on_tick(instrument_id("AAA"), pa, pa, pa, now=T0_EPOCH - 600)
m.on_tick(instrument_id("BBB"), 100.0, 100.0, 100.0, now=T0_EPOCH - 600)
check("a stale quote cannot open a position",
      not m.try_open([dict(base)], T0_EPOCH), "skipped")

# --------------------------------------------------------------------------
print()
print("=" * 118)
print("11. The stop is measured from ENTRY, so re-anchoring keeps it correct")
print("=" * 118)
m = fresh_monitor()
pa = math.exp(3.2 * sigma + math.log(100.0))
m.on_tick(instrument_id("AAA"), pa, pa, pa, now=T0_EPOCH)
m.on_tick(instrument_id("BBB"), 100.0, 100.0, 100.0, now=T0_EPOCH)
m.try_open([dict(base)], T0_EPOCH)
p = m.pf.open_positions[0]
fill_entry = p.signal["entry_spread"]
d = cfg.STOP_SIGMA * sigma
out = push(m, fill_entry + d * 0.99, T0_EPOCH + 1)
check("just inside the stop from the FILL does not fire", not out, "held")
out = push(m, fill_entry + d * 1.01, T0_EPOCH + 2)
check("just past it does", len(out) == 1, "fired")
check("  ... overshoot measured from the fill", abs(out[0]["overshoot_ratio"] - 1.01) < 0.02,
      f"{out[0]['overshoot_ratio']:.3f}x")

# --------------------------------------------------------------------------
print()
print("=" * 118)
print("12. Ledger schema — an open and a close cannot cross columns")
print("=" * 118)
try:
    m = make_monitor(z=3.5, sigma=0.02)
    m.dry_run = False
    p = m.pf.open_positions[0]
    p.entry_bar_z = 3.5
    m.persist([p], [])
    out = push(m, entry + dist * 1.2, T0_EPOCH + 1)
    m.persist([], out)
    d = pd.read_csv(cfg.LEDGER_PATH)
    check("columns match LEDGER_COLUMNS exactly",
          list(d.columns) == cfg.LEDGER_COLUMNS, f"{len(d.columns)} cols")
    check("one open row and one close row", set(d.event) == {"open", "close"},
          sorted(set(d.event)))
    close = d[d.event == "close"].iloc[0]
    check("close row's exit_reason is in the exit_reason column",
          close.exit_reason == "adverse_move", close.exit_reason)
    check("close row carries the overshoot diagnostics",
          np.isfinite(close.overshoot_ratio) and np.isfinite(close.confirm_delay_ms),
          f"{close.overshoot_ratio:.2f}x")
    check("open row has no exit fields", pd.isna(close.opened_at) is False and
          pd.isna(d[d.event == "open"].iloc[0].exit_reason), "clean")
finally:
    pass

# --------------------------------------------------------------------------
print()
print("=" * 118)
print("13. Single writer — the scanner never touches the book")
print("=" * 118)
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "live_scanner.py")).read()
for banned in ("save_portfolio", "append_ledger", "fill_slots", "evaluate_exits"):
    check(f"live_scanner.py does not call {banned}", banned not in src, "absent")
mon_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "stop_monitor.py")).read()
check("stop_monitor.py never writes scan_history",
      "SCAN_HISTORY_DIR" not in mon_src, "absent")
check("the monitor holds an exclusive lock path", "LOCK_PATH" in mon_src, "present")

# --------------------------------------------------------------------------
print()
print("=" * 118)
print("13. Equity survives a restart — losses booked before it are not erased")
print("=" * 118)
# The bug this guards: load_portfolio set pf.equity from the ledger but left
# pf.starting_equity at ACCOUNT_EQUITY and pf.closed empty. _close() recomputes
# equity as starting_equity + sum(closed), so the FIRST close after any restart
# dropped every earlier loss. Live on the VM: 7 closes totalling -20.31 reported
# equity 290.93 instead of 279.69. Equity drifted UP across restarts, and
# position size is a function of equity.
import csv as _csv

with open(cfg.LEDGER_PATH, "w", newline="") as fh:
    w = _csv.DictWriter(fh, fieldnames=cfg.LEDGER_COLUMNS)
    w.writeheader()
    for i, pnl in enumerate([-2.36, -2.18, -3.33, -3.38], start=1):
        w.writerow({"event": "close", "trade_num": i, "realized_pnl_net": pnl})
if os.path.exists(cfg.STATE_PATH):
    os.remove(cfg.STATE_PATH)

pf = cfg.load_portfolio(equity=300.0)
check("equity re-summed from the ledger on load", abs(pf.equity - 288.75) < 0.01,
      f"{pf.equity:.2f}")
check("starting_equity re-based to match", abs(pf.starting_equity - pf.equity) < 1e-9,
      f"{pf.starting_equity:.2f}")

# Book one more loss the way _close does and confirm it compounds, not replaces.
pf.closed.append({"realized_pnl_net": -2.27})
pf.equity = pf.starting_equity + sum(c["realized_pnl_net"] for c in pf.closed)
check("a close after the restart subtracts from the restored equity",
      abs(pf.equity - 286.48) < 0.01, f"{pf.equity:.2f} (bug gave 297.73)")

# --------------------------------------------------------------------------
print()
print("=" * 118)
print("14. Live position snapshot — marked to the monitor's own quotes")
print("=" * 118)
m = make_monitor(z=3.5, sigma=0.02, beta=1.0)
pos = m.pf.open_positions[0]
entry = pos.signal["entry_spread"]
dist = cfg.STOP_SIGMA * pos.signal["sigma_at_entry"]

# Halfway to the stop.
push(m, entry + dist * 0.5, T0_EPOCH + 1)
snap = m.positions_snapshot()
r = snap["positions"][0]
check("one position reported", snap["open"] == 1, snap["open"])
check("progress_to_stop is 0.5 halfway there",
      abs(r["progress_to_stop"] - 0.5) < 1e-6, f"{r['progress_to_stop']:.3f}")
check("a short spread moving up is losing", r["unrealized_pnl"] < 0,
      f"{r['unrealized_pnl']:+.2f}")
check("unrealized R is about -0.5 at half the stop",
      -0.65 < r["unrealized_r"] < -0.45, f"{r['unrealized_r']:+.2f}")

# Moving toward mu is a gain, and progress runs negative.
push(m, entry - dist * 0.5, T0_EPOCH + 2)
r = m.positions_snapshot()["positions"][0]
check("moving toward mu shows a gain", r["unrealized_pnl"] > 0, f"{r['unrealized_pnl']:+.2f}")
check("  ... and progress_to_stop goes negative", r["progress_to_stop"] < 0,
      f"{r['progress_to_stop']:.2f}")

# The mark must agree with what the stop itself computes -- one geometry.
r = m.positions_snapshot()["positions"][0]
la, lb = m._log_prices(pos)
check("snapshot spread == Position.current_spread",
      abs(r["spread"] - pos.current_spread(la, lb)) < 1e-12, "exact")

# A stale leg is reported as blind with NO mark, never a stale number.
m2 = make_monitor(z=3.5, sigma=0.02, stale=30.0)
r2 = m2.positions_snapshot()["positions"][0]
check("no quotes yet -> blind, and no mark at all",
      r2["blind"] and r2["unrealized_pnl"] is None, "blank")

# Book-level exposure aggregates.
m3 = make_monitor(z=3.5, sigma=0.02, beta=1.0)
push(m3, entry, T0_EPOCH + 1)
s3 = m3.positions_snapshot()
check("beta=1 book reports zero net exposure",
      abs(s3["book_net_exposure"]) < 1e-9, f"{s3['book_net_exposure']:+.2f}")
check("margin accounting: used + free == equity",
      abs(s3["used_margin"] + s3["available_margin"] - s3["equity"]) < 1e-9,
      f"{s3['used_margin']:.2f} + {s3['available_margin']:.2f}")

# It is a read-only view: writing it must not touch the book.
m4 = make_monitor(z=3.5, sigma=0.02)
m4.dry_run = False
push(m4, entry, T0_EPOCH + 1)
before = (os.path.exists(cfg.LEDGER_PATH) and os.path.getmtime(cfg.LEDGER_PATH),
          os.path.exists(cfg.STATE_PATH) and os.path.getmtime(cfg.STATE_PATH))
m4.write_positions_snapshot()
after = (os.path.exists(cfg.LEDGER_PATH) and os.path.getmtime(cfg.LEDGER_PATH),
         os.path.exists(cfg.STATE_PATH) and os.path.getmtime(cfg.STATE_PATH))
check("writing the snapshot does not touch ledger or state", before == after, "untouched")
check("snapshot file is valid json", isinstance(
    json.load(open(cfg.POSITIONS_PATH)), dict), "ok")

# --------------------------------------------------------------------------
print()
print("=" * 118)
print("15. Adding a ledger column must not corrupt the existing file")
print("=" * 118)
# What happened live on 2026-09-13: three columns were added to LEDGER_COLUMNS,
# append_ledger kept appending under the header written before that, and the
# ledger became rows of 39 fields under a 36-field header. pandas refuses to
# parse it -- "Expected 36 fields in line 26, saw 39" -- so the monitor
# crash-looped on restart and could not load the book at all.
import csv as _csv2

real_cols = cfg.LEDGER_COLUMNS
try:
    # A ledger written under an older, narrower schema.
    old_cols = [c for c in real_cols if c not in
                ("r2_at_entry", "net_exposure", "net_exposure_frac")]
    with open(cfg.LEDGER_PATH, "w", newline="") as fh:
        w = _csv2.DictWriter(fh, fieldnames=old_cols)
        w.writeheader()
        w.writerow({"event": "close", "trade_num": 1, "realized_pnl_net": -5.0})
        w.writerow({"event": "close", "trade_num": 2, "realized_pnl_net": -3.0})

    # Now append under the CURRENT, wider schema.
    cfg.append_ledger([{"event": "close", "trade_num": 3,
                        "realized_pnl_net": -2.0, "net_exposure": -120.0}])

    d = pd.read_csv(cfg.LEDGER_PATH)          # this is what used to raise
    check("a widened ledger still parses", len(d) == 3, f"{len(d)} rows")
    check("  ... header matches LEDGER_COLUMNS",
          list(d.columns) == real_cols, f"{len(d.columns)} cols")
    check("  ... pre-migration rows are preserved",
          abs(d.realized_pnl_net.sum() + 10.0) < 1e-9, f"{d.realized_pnl_net.sum():.1f}")
    check("  ... and the new column is populated on the new row",
          abs(d[d.trade_num == 3].net_exposure.iloc[0] + 120.0) < 1e-9, "-120")
    check("  ... old rows get the new column as NaN",
          pd.isna(d[d.trade_num == 1].net_exposure.iloc[0]), "NaN")
    check("equity still re-sums correctly after a migration",
          abs(cfg.load_portfolio(equity=300.0).equity - 290.0) < 1e-9, "290.00")

    # A column that LEFT the schema must not be deleted -- it is history.
    with open(cfg.LEDGER_PATH, "w", newline="") as fh:
        w = _csv2.DictWriter(fh, fieldnames=real_cols + ["retired_field"])
        w.writeheader()
        w.writerow({"event": "close", "trade_num": 9, "realized_pnl_net": -1.0,
                    "retired_field": "keepme"})
    cfg.append_ledger([{"event": "close", "trade_num": 10, "realized_pnl_net": -1.0}])
    d = pd.read_csv(cfg.LEDGER_PATH)
    check("a column dropped from the schema is KEPT, not destroyed",
          "retired_field" in d.columns and
          d[d.trade_num == 9].retired_field.iloc[0] == "keepme", "kept")

    # Idempotent: a ledger already on the current schema is left alone.
    before = open(cfg.LEDGER_PATH).read()
    cfg.migrate_ledger_schema()
    check("migrating an up-to-date ledger changes nothing",
          open(cfg.LEDGER_PATH).read() == before, "unchanged")
finally:
    if os.path.exists(cfg.LEDGER_PATH):
        os.remove(cfg.LEDGER_PATH)

import shutil
shutil.rmtree(TMP, ignore_errors=True)

print()
print("=" * 118)
print(f"{n_pass}/{n_pass + n_fail} assertions PASS")
print("=" * 118)
sys.exit(1 if n_fail else 0)
