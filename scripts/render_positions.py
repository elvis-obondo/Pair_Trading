"""Render the monitor's open-position snapshot. Run inside the container."""
import json, os, sys, datetime

p = os.environ.get("PAIRS_DATA_DIR", "/app/trading_data") + "/open_positions.json"
if not os.path.exists(p):
    raise SystemExit("  no snapshot yet — the monitor writes it on each heartbeat (10s)")
s = json.load(open(p))

age = (datetime.datetime.now(datetime.timezone.utc)
       - datetime.datetime.fromisoformat(s["as_of"])).total_seconds()
print(f"as of {s['as_of']}  ({age:.0f}s ago)   feed={s['feed_state']}")
print(f"equity {s['equity']:.2f}   margin used {s['used_margin']:.2f}   "
      f"free {s['available_margin']:.2f}   open {s['open']}/{s['max_slots']}")
print()

if not s["positions"]:
    raise SystemExit("  book is flat")

hdr = (f"{'#':>3} {'pair':<16}{'side':<7}{'held':>6}{'beta':>7}{'r2':>6}"
       f"{'z now':>7}{'->stop':>8}{'P&L $':>9}{'R':>7}{'net exp':>9}")
print(hdr)
print("-" * len(hdr))
win = loss = 0
for r in s["positions"]:
    pair = f"{r['ticker_a']}/{r['ticker_b']}"
    side = "SHORT" if r["side"].startswith("short") else "LONG"
    pnl, rr = r.get("unrealized_pnl"), r.get("unrealized_r")
    if pnl is None:
        mark = "   (blind — no mark)"
        print(f"{r['trade_num']:>3} {pair:<16}{side:<7}{r['hours_held']:>5.1f}h"
              f"{r['beta']:>7.2f}{(r['r2'] or float('nan')):>6.2f}{mark}")
        continue
    win += pnl > 0; loss += pnl <= 0
    flag = " *" if r.get("progress_to_stop", 0) and r["progress_to_stop"] > 0.75 else ""
    print(f"{r['trade_num']:>3} {pair:<16}{side:<7}{r['hours_held']:>5.1f}h"
          f"{r['beta']:>7.2f}{(r['r2'] if r['r2'] is not None else float('nan')):>6.2f}"
          f"{r['z_now']:>7.2f}{r['progress_to_stop']:>7.0%}{flag:<1}"
          f"{pnl:>+9.2f}{rr:>+7.2f}{r['net_exposure']:>+9.0f}")

print("-" * len(hdr))
print(f"{win} up, {loss} down   unrealized {s['unrealized_total']:>+.2f}")
print()
print(f"book net exposure {s['book_net_exposure']:>+9.2f} on gross "
      f"{s['book_gross_exposure']:.2f}  =  {s['book_net_frac']:+.1%} directional")
print(f"                  {s['book_net_exposure']/s['equity']:>+9.2f}x equity")
print()
print("  ->stop is progress toward the stop level; * marks past 75%.")
print("  net exp is one-way market exposure: 0 = hedged, +/- = directional.")
