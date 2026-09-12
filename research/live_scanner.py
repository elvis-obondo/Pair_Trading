"""One scan cycle: refresh data, screen the universe, manage the paper book.

DESIGNED TO BE RUN REPEATEDLY, NOT TO RUN FOREVER

This is single-shot by design. A LaunchAgent fires it every 30 minutes and it
exits. A long-lived process would have to survive sleep, network drops and
memory creep for weeks; a process that starts, does one cycle from persisted
state and exits cannot leak, and a crash costs one cycle rather than the run.
All state lives on disk between cycles.

IT SUBMITS NO ORDERS. It maintains a real book against live prices using the
production sizer and exit logic -- everything except execution.

CYCLE COST, measured on this laptop:
    refresh 30m futures     ~80s   (the four-timeframe update_data.sh is 5m21s)
    load panel               ~2s
    scan 22,366 pairs        ~9s
    ------------------------------
    total                  ~100s   on a 30-minute clock, a 5% duty cycle

Usage:
    python research/live_scanner.py              # refresh data, then scan
    python research/live_scanner.py --no-refresh # scan whatever is on disk
    python research/live_scanner.py --dry-run    # scan and report, persist nothing
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from universe_panel import load_panel, usable_tickers, tradeable_pairs
from rolling_spread import min_bars_required
from scanner import scan, scan_summary
from portfolio import Portfolio, Position

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(PROJECT_ROOT, "research", "scanner_state.json")
LEDGER_PATH = os.path.join(PROJECT_ROOT, "research", "scanner_trades.csv")
CANDIDATES_PATH = os.path.join(PROJECT_ROOT, "research", "scanner_candidates.json")
LOG_PATH = os.path.join(PROJECT_ROOT, "logs", "scanner.log")

# The settled configuration. Mirrors nautilus/run_trading.py so the scanner and
# the single-pair live process cannot silently disagree about the rules.
ACCOUNT_EQUITY = 300.0
CAPITAL_FRAC = 0.05
LEVERAGE = 20.0
MAX_SLOTS = 10
MIN_DEVIATION_SIGMA = 3.0
TAKE_PROFIT_PCT = 1.0
STOP_SIGMA = 0.5
MAX_HOLD_HOURS = 72.0
BAR_HOURS = 0.5
MAX_PER_TICKER = None      # None = the spec: one token may take the whole book
TOP_N_REPORTED = 25

# FIXED ledger schema, open rows and close rows conforming to the same columns.
# This is not tidiness. pandas' to_csv(mode="a") writes whatever columns the
# frame happens to have, in its own order, under a header written once from the
# FIRST batch -- so an open-row header followed by a close-row append silently
# files every close value under the wrong column name. docs/HANDOFF.md records
# an earlier ledger corruption whose root cause was never identified; this is
# how you get one. Every row is reindexed onto these columns before writing.
LEDGER_COLUMNS = [
    "event", "trade_num", "ticker_a", "ticker_b", "time",
    "opened_at", "closed_at", "hours_held", "exit_reason",
    "entry_spread", "exit_spread", "mu_at_entry", "sigma_at_entry",
    "z_at_entry", "beta_at_entry", "alpha_at_entry", "theta_at_entry",
    "take_profit_level",
    "leg_a_notional", "leg_b_notional", "gross_notional", "margin", "leverage",
    "realized_pnl_net", "net_pct", "r",
]


def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')}  {msg}"
    print(line, flush=True)
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a") as fh:
        fh.write(line + "\n")


def refresh_data(timeout_s: int = 900) -> bool:
    """Pull only the 30m futures candles.

    update_data.sh downloads four timeframes per ticker (30m futures, 1h
    futures, 1h mark, 1h funding_rate) and takes 5m21s. The scanner reads only
    30m futures, so asking for just that is roughly a quarter of the work. That
    difference is what makes a 30-minute cycle comfortable instead of tight.
    """
    cmd = ["docker", "compose", "run", "--rm", "freqtrade", "download-data",
           "--config", "user_data/config.json", "--exchange", "okx",
           "--trading-mode", "futures", "--timeframes", "30m", "--days", "60"]
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True,
                           text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        log(f"data refresh TIMED OUT after {timeout_s}s — scanning stale data")
        return False
    except FileNotFoundError:
        log("docker not found — scanning whatever is already on disk")
        return False
    if r.returncode != 0:
        log(f"data refresh FAILED rc={r.returncode} — scanning stale data: "
            f"{r.stderr.strip().splitlines()[-1] if r.stderr.strip() else ''}")
        return False
    log(f"data refreshed in {time.time()-t0:.0f}s")
    return True


# ---------------------------------------------------------------------------
# State. Open positions are persisted whole -- the frozen entry signal IS the
# state an exit needs, so there is nothing to recompute and nothing to drift.
# ---------------------------------------------------------------------------

def load_portfolio() -> Portfolio:
    pf = Portfolio(equity=ACCOUNT_EQUITY, max_slots=MAX_SLOTS,
                   capital_frac=CAPITAL_FRAC, leverage=LEVERAGE,
                   stop_sigma=STOP_SIGMA, max_hold_hours=MAX_HOLD_HOURS,
                   max_per_ticker=MAX_PER_TICKER)
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH) as fh:
            st = json.load(fh)
        for p in st.get("open_positions", []):
            pf.open_positions.append(Position(
                p["trade_num"], p["ticker_a"], p["ticker_b"],
                p["signal"], p["sizing"],
                datetime.fromisoformat(p["opened_at"]), STOP_SIGMA))
        pf.next_trade_num = st.get("next_trade_num", 1)

    # Equity is re-summed from the ledger, never carried in the state file --
    # the same discipline PairsTradingActor._recompute_equity uses, so a state
    # file that goes stale cannot silently corrupt position sizing.
    if os.path.exists(LEDGER_PATH):
        d = pd.read_csv(LEDGER_PATH)
        realized = 0.0
        if "event" in d.columns and "realized_pnl_net" in d.columns:
            closes = d[d["event"] == "close"]
            realized = float(pd.to_numeric(closes["realized_pnl_net"],
                                           errors="coerce").fillna(0.0).sum())
        pf.equity = ACCOUNT_EQUITY + realized
    return pf


def save_portfolio(pf: Portfolio) -> None:
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w") as fh:
        json.dump({
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "equity": pf.equity,
            "next_trade_num": pf.next_trade_num,
            "open_positions": [{
                "trade_num": p.trade_num, "ticker_a": p.ticker_a,
                "ticker_b": p.ticker_b, "opened_at": p.opened_at.isoformat(),
                "signal": p.signal, "sizing": p.sizing,
            } for p in pf.open_positions],
        }, fh, indent=2, default=str)
    os.replace(tmp, STATE_PATH)   # atomic: a kill mid-write cannot truncate it


def append_ledger(rows: list[dict]) -> None:
    """Append rows onto the FIXED schema, dropping anything not in it.

    reindex(columns=...) is the whole point: it fills missing fields with NaN
    and puts every column in the same order regardless of whether the row is an
    open or a close, so an appended close can never land under an open's header.
    """
    if not rows:
        return
    d = pd.DataFrame(rows).reindex(columns=LEDGER_COLUMNS)
    d.to_csv(LEDGER_PATH, mode="a", header=not os.path.exists(LEDGER_PATH),
             index=False)


def write_candidates(cands: pd.DataFrame, pf: Portfolio, bar_time) -> None:
    top = cands.head(TOP_N_REPORTED).copy()
    if len(top):
        top["half_life_hours"] = np.log(2.0) / top["theta_at_entry"]
    held = {p.pair for p in pf.open_positions}
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bar_time": str(bar_time),
        "n_candidates": int(len(cands)),
        "n_ranked": int(cands["theta_at_entry"].notna().sum()) if len(cands) else 0,
        "equity": round(pf.equity, 4),
        "open_positions": [{
            "trade_num": p.trade_num, "pair": f"{p.ticker_a}/{p.ticker_b}",
            "opened_at": p.opened_at.isoformat(),
            "z_at_entry": round(p.signal["z_at_entry"], 3),
            "gross_notional": round(p.sizing["gross_notional"], 2),
        } for p in pf.open_positions],
        "top_candidates": [{
            "pair": f"{r.ticker_a}/{r.ticker_b}",
            "z": round(float(r.z_at_entry), 3),
            "theta": None if pd.isna(r.theta_at_entry) else round(float(r.theta_at_entry), 5),
            "half_life_hours": None if pd.isna(r.half_life_hours) else round(float(r.half_life_hours), 2),
            "sigma": round(float(r.sigma_at_entry), 6),
            "already_open": (r.ticker_a, r.ticker_b) in held,
        } for r in top.itertuples(index=False)],
    }
    tmp = CANDIDATES_PATH + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(payload, fh, indent=2)
    os.replace(tmp, CANDIDATES_PATH)


# ---------------------------------------------------------------------------

def cycle(refresh: bool = True, dry_run: bool = False) -> Portfolio:
    t0 = time.time()
    log("=== cycle start ===")
    if refresh:
        refresh_data()

    need = min_bars_required(BAR_HOURS)
    panel = load_panel(force=refresh).tail(need)
    bar_time = panel.index[-1]
    age_min = (pd.Timestamp.utcnow().tz_localize(None) - bar_time).total_seconds() / 60
    log(f"panel {panel.shape[0]}x{panel.shape[1]} | last bar {bar_time} "
        f"({age_min:.0f} min old)")
    if age_min > 120:
        log(f"WARNING: data is {age_min:.0f} minutes stale — candidates may be wrong")

    tickers = usable_tickers(panel, BAR_HOURS)
    pairs = tradeable_pairs(tickers)
    pf = load_portfolio()
    log(f"resumed: {len(pf.open_positions)} open, equity {pf.equity:.2f}, "
        f"next trade {pf.next_trade_num}")

    prices = {t: panel.iloc[-1][t] for t in tickers}
    now = bar_time.to_pydatetime()

    closed = pf.evaluate_exits(prices, now)
    for c in closed:
        log(f"CLOSE #{c['trade_num']} {c['ticker_a']}/{c['ticker_b']} "
            f"{c['exit_reason']} after {c['hours_held']:.1f}h "
            f"pnl {c['realized_pnl_net']:+.2f} R {c['r']:+.2f}")

    t1 = time.time()
    cands = scan(panel, pairs, min_deviation_sigma=MIN_DEVIATION_SIGMA,
                 take_profit_pct=TAKE_PROFIT_PCT, bar_hours=BAR_HOURS)
    log(f"scan {len(pairs):,} pairs in {time.time()-t1:.1f}s — {scan_summary(cands)}")

    opened = pf.fill_slots(cands, now) if pf.free_slots > 0 else []
    for p in opened:
        hl = np.log(2.0) / p.signal["theta_at_entry"] if np.isfinite(p.signal["theta_at_entry"]) else float("nan")
        log(f"OPEN  #{p.trade_num} {p.ticker_a}/{p.ticker_b} "
            f"z {p.signal['z_at_entry']:+.2f} half-life {hl:.1f}h "
            f"gross {p.sizing['gross_notional']:.2f} margin {p.sizing['margin']:.2f}")

    if not dry_run:
        rows = []
        for p in opened:
            rows.append({"event": "open", "trade_num": p.trade_num,
                         "ticker_a": p.ticker_a, "ticker_b": p.ticker_b,
                         "time": now, **p.signal, **p.sizing})
        for c in closed:
            rows.append({"event": "close", "time": c["closed_at"], **c})
        append_ledger(rows)
        save_portfolio(pf)
        write_candidates(cands, pf, bar_time)

    conc = pf.concentration()
    hot = conc[conc >= 3]
    if len(hot):
        log(f"CONCENTRATION: {dict(hot)} — one token in 3+ open positions")

    log(f"book: {len(pf.open_positions)}/{MAX_SLOTS} open | "
        f"margin {pf.used_margin:.2f}/{pf.equity:.2f} | {pf.summary()}")
    log(f"=== cycle done in {time.time()-t0:.0f}s ===")
    return pf


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-refresh", action="store_true",
                    help="skip the data download and scan what is on disk")
    ap.add_argument("--dry-run", action="store_true",
                    help="scan and report, but persist nothing")
    a = ap.parse_args()
    cycle(refresh=not a.no_refresh, dry_run=a.dry_run)
