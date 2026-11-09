"""User-requested pre-NUMBERS sanity check (2026-11-09): where did the money go? Reads the trade logs
only -- no rerun, no rule change. Prints, per run: totals and per-trade means of gross P&L, fees,
slippage and funding; for q=0.01/stop=none/fee=taker, the 5 worst trades by net with a full cost
breakdown; and the min_order skip mechanics at q=0.001.

    python -u research/model/logs/profit1/diagnostics/cost_breakdown.py
"""
import glob
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PROFIT_DIR = os.path.dirname(HERE)

print("=== Per-run totals and per-trade means ===")
rows = []
for f in sorted(glob.glob(os.path.join(PROFIT_DIR, "trades_*.parquet"))):
    name = os.path.basename(f)[len("trades_"):-len(".parquet")]
    d = pd.read_parquet(f)
    n = len(d)
    if n == 0:
        continue
    gross = d["gross_pnl"].sum()
    fee = (d["entry_fee"] + d["exit_fee"]).sum()
    slip = (d["entry_slip"] + d["exit_slip"]).sum()
    fund_net = (d["funding_paid"] - d["funding_received"]).sum()
    net = d["net"].sum()
    rows.append(dict(run=name, n_trades=n, gross_total=gross, fee_total=fee, slip_total=slip,
                      funding_net_total=fund_net, net_total=net,
                      gross_per_trade=gross / n, fee_per_trade=fee / n, slip_per_trade=slip / n,
                      funding_per_trade=fund_net / n, net_per_trade=net / n))
summary = pd.DataFrame(rows)
with pd.option_context("display.width", 200, "display.max_columns", None, "display.float_format",
                        lambda x: f"{x:,.4f}"):
    print(summary.to_string(index=False))

print("\n=== Share of |net_total| by cost category, pooled over all 24 runs ===")
pooled_gross = summary["gross_total"].sum()
pooled_fee = summary["fee_total"].sum()
pooled_slip = summary["slip_total"].sum()
pooled_fund = summary["funding_net_total"].sum()
pooled_net = summary["net_total"].sum()
pooled_n = summary["n_trades"].sum()
print(f"pooled n_trades={pooled_n:,}")
print(f"pooled gross_pnl={pooled_gross:,.2f}  fee={pooled_fee:,.2f}  slip={pooled_slip:,.2f}  "
      f"funding_net={pooled_fund:,.2f}  net={pooled_net:,.2f}")
print(f"check: gross - fee - slip - funding_net = {pooled_gross - pooled_fee - pooled_slip - pooled_fund:,.2f} "
      f"(should equal net={pooled_net:,.2f})")

print("\n=== 5 worst trades, q=0.01 stop=none fee=taker, by net ===")
f = os.path.join(PROFIT_DIR, "trades_q0.01_stopnone_feetaker.parquet")
d = pd.read_parquet(f)
worst = d.sort_values("net").head(5)
cols = ["event_id", "ticker_a", "ticker_b", "t0", "exit_time", "exit_reason", "holding_minutes",
        "notional", "leverage", "gross_pnl", "entry_fee", "exit_fee", "entry_slip", "exit_slip",
        "funding_paid", "funding_received", "net"]
with pd.option_context("display.width", 250, "display.max_columns", None, "display.float_format",
                        lambda x: f"{x:,.4f}"):
    print(worst[cols].to_string(index=False))

print("\n=== min_order skip mechanics, q=0.001 ===")
for stop, fee in [("1p0", "feemaker")]:
    sk_path = os.path.join(PROFIT_DIR, f"skips_q0.001_stop{stop}_{fee}.parquet")
    me_path = os.path.join(PROFIT_DIR, f"minute_equity_q0.001_stop{stop}_{fee}.parquet")
    sk = pd.read_parquet(sk_path)
    me = pd.read_parquet(me_path)
    n_total = len(sk)
    by_reason = sk["reason"].value_counts()
    print(f"q=0.001 stop={stop} fee={fee}: total skip rows={n_total:,}")
    print(by_reason.to_string())
    min_order_sk = sk[sk["reason"] == "min_order"]
    me = me.set_index("time").sort_index()
    # account value just before each min_order skip (asof)
    av_at_skip = me["account_value"].reindex(min_order_sk["t0"].to_numpy(), method="ffill")
    print(f"\naccount_value at the time of a min_order skip: "
          f"min={av_at_skip.min():.2f} median={av_at_skip.median():.2f} max={av_at_skip.max():.2f}")
    # with margin_frac=0.05, leverage up to 10, min_order_usd=10: notional = margin_frac*av*lev
    margin_frac, lev_cap, min_order_usd = 0.05, 10.0, 10.0
    implied_notional = margin_frac * av_at_skip * lev_cap
    print(f"implied notional (margin_frac=0.05 x account_value x leverage<=10): "
          f"min={implied_notional.min():.2f} median={implied_notional.median():.2f} "
          f"max={implied_notional.max():.2f}")
    print(f"a leg below min_order_usd={min_order_usd} needs notional/(1+|beta|) or "
          f"notional*|beta|/(1+|beta|) < {min_order_usd} -- at median implied notional "
          f"{implied_notional.median():.2f}, any |beta| outside roughly "
          f"[{min_order_usd/(implied_notional.median()-min_order_usd) if implied_notional.median()>min_order_usd else float('nan'):.3f}, "
          f"{(implied_notional.median()-min_order_usd)/min_order_usd if implied_notional.median()>min_order_usd else float('nan'):.3f}] "
          f"fails the $10 minimum on one leg.")
