import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import math
import numpy as np
import pandas as pd
from data_loader import get_price_levels

# --- Step 1: Load price data (same 30-day filter as run_backtest) ---
df = get_price_levels()
cutoff = df.index.max() - pd.Timedelta(days=30)
df = df[df.index >= cutoff]
pair = df[["AVAX", "LINK"]].dropna()

first_val = pair["AVAX"].iloc[0]
if 1.0 < first_val < 5.0:
    print(f"[CHECK] pair['AVAX'].iloc[0] = {first_val:.4f} — already log (expected ~3)")
else:
    print(f"[CHECK] pair['AVAX'].iloc[0] = {first_val:.4f} — REAL PRICE — applying np.log")
    pair = np.log(pair)

# --- Step 2: Load trade log, filter to time_stop ---
dump_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trade_log_dump.json")
with open(dump_path) as fh:
    trade_log = json.load(fh)

time_stopped = [t for t in trade_log if t["exit_reason"] == "time_stop"]
print(f"[INFO] Total trades in log: {len(trade_log)} | time_stop: {len(time_stopped)}\n")

# --- Steps 3–6: Per-trade probe ---
results = []

for trade in time_stopped:
    trade_num = trade["trade_num"]
    entry_time = trade["entry_time"]
    entry_spread = trade["entry_spread"]
    mu_at_entry = trade["mu_at_entry"]
    beta_at_entry = trade["beta_at_entry"]
    alpha_at_entry = trade["alpha_at_entry"]
    predicted_tau = trade["hours_held"]

    # Step 3: locate entry bar (tz-naive to match pair.index)
    entry_ts = pd.Timestamp(entry_time)
    locs = pair.index.get_indexer([entry_ts], method="nearest")
    entry_pos = locs[0]
    matched_ts = pair.index[entry_pos]
    offset_hrs = abs((matched_ts - entry_ts).total_seconds()) / 3600.0

    print(f"Trade #{trade_num}  entry={entry_time}")

    if offset_hrs > 1.0:
        print(f"  ** entry bar not found (nearest is {offset_hrs:.2f}h off) — SKIPPED\n")
        results.append({"trade_num": trade_num, "skipped": True})
        continue

    # Step 4: forward window
    window_size = math.ceil(3 * predicted_tau)
    available_forward = len(pair) - entry_pos - 1
    end_pos = min(entry_pos + window_size, len(pair))
    actual_forward_hrs = end_pos - entry_pos
    insufficient = actual_forward_hrs < window_size

    # Step 5: take-profit level and direction
    tp_level = entry_spread - 0.80 * (entry_spread - mu_at_entry)
    going_down = entry_spread > mu_at_entry  # reversion is downward

    # Step 6: walk forward window
    entry_dev = abs(entry_spread - mu_at_entry)
    min_remaining_dev = entry_dev
    hrs_to_tp = None
    hrs_to_tp_in_tau = None

    for offset in range(1, actual_forward_hrs):
        i = entry_pos + offset
        spread_i = (pair["AVAX"].iloc[i]
                    - alpha_at_entry
                    - beta_at_entry * pair["LINK"].iloc[i])
        remaining_dev = abs(spread_i - mu_at_entry)
        if remaining_dev < min_remaining_dev:
            min_remaining_dev = remaining_dev

        reached = (spread_i <= tp_level) if going_down else (spread_i >= tp_level)
        if reached and hrs_to_tp is None:
            hrs_to_tp = offset
            if offset <= predicted_tau:
                hrs_to_tp_in_tau = offset

    closeness = (entry_dev - min_remaining_dev) / entry_dev if entry_dev > 0 else float("nan")

    # --- Output for this trade ---
    print(f"  predicted_tau (hrs):        {predicted_tau:.2f}  (= hours_held, +0-1h bar rounding)")
    print(f"  forward window (hrs):       {window_size}")
    print(f"  forward data available:     {actual_forward_hrs}"
          + ("  ** INSUFFICIENT FORWARD DATA" if insufficient else ""))
    print(f"  entry_spread:               {entry_spread:.6f}")
    print(f"  mu_at_entry:                {mu_at_entry:.6f}")
    print(f"  take_profit_level:          {tp_level:.6f}")
    if hrs_to_tp is not None:
        print(f"  reached TP within window?   YES at hr={hrs_to_tp}")
    else:
        print(f"  reached TP within window?   NO")
    if hrs_to_tp_in_tau is not None:
        print(f"  reached TP within tau?      YES at hr={hrs_to_tp_in_tau}")
    else:
        if hrs_to_tp is not None:
            beyond = hrs_to_tp - predicted_tau
            print(f"  reached TP within tau?      NO (reached at hr={hrs_to_tp}, {beyond:.1f}h beyond tau)")
        else:
            print(f"  reached TP within tau?      NO")
    print(f"  max closeness to mu:        {closeness:.4f}  (1.0=mu, 0.80=TP level, <=0 diverged)")
    print()

    results.append({
        "trade_num":       trade_num,
        "skipped":         False,
        "predicted_tau":   predicted_tau,
        "window_size":     window_size,
        "actual_forward":  actual_forward_hrs,
        "insufficient":    insufficient,
        "hrs_to_tp":       hrs_to_tp,
        "hrs_to_tp_in_tau": hrs_to_tp_in_tau,
        "closeness":       closeness,
    })

# --- Summary ---
probed = [r for r in results if not r.get("skipped")]
n = len(probed)
reached_window = [r for r in probed if r["hrs_to_tp"] is not None]
reached_in_tau = [r for r in probed if r["hrs_to_tp_in_tau"] is not None]
never_reached = [r for r in probed if r["hrs_to_tp"] is None and not r["insufficient"]]
insufficient_list = [r for r in probed if r["insufficient"]]
beyond_tau = [r["hrs_to_tp"] - r["predicted_tau"]
              for r in reached_window if r["hrs_to_tp_in_tau"] is None]
closeness_vals = [r["closeness"] for r in probed if not math.isnan(r["closeness"])]

print("=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"Time-stopped trades probed:     {n}")
print(f"Reached TP eventually (3x tau): {len(reached_window)} of {n}")
if beyond_tau:
    print(f"  of those, hours beyond tau:   {[round(x, 1) for x in beyond_tau]}")
print(f"Reached TP within tau:          {len(reached_in_tau)} of {n}   "
      f"(these should be ~0 — they time-stopped)")
print(f"Never reached TP in 3x window:  {len(never_reached)} of {n}")
print(f"Trades with insufficient data:  {len(insufficient_list)} of {n}")
if closeness_vals:
    print(f"Median closeness to mu:         {float(np.median(closeness_vals)):.4f}")
