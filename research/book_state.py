"""The settled configuration, and the only code that reads or writes the book.

WHY THIS FILE EXISTS

Two processes now share the strategy: `live_scanner.py` finds dislocations every 30
minutes, and `stop_monitor.py` holds the positions and watches their stops tick by
tick. They must agree exactly on the parameters and they must NOT both write the
state. Both of those are enforced here rather than by convention.

SINGLE WRITER, AND WHY IT MATTERS

`stop_monitor.py` is the only process that calls `save_portfolio` or `append_ledger`.
The scanner imports the config and the paths, reads state read-only, and writes its
own separate `scan_history` — never the book.

This is not fastidiousness. `docs/HANDOFF.md` records a ledger corruption whose root
cause was never identified, and the two mechanisms that produce one are both live
here: two processes appending to the same CSV, and `to_csv(mode="a")` writing
whatever columns a frame happens to carry under a header written once from the first
batch. The fixed `LEDGER_COLUMNS` + `reindex` below closes the second. One writer
closes the first.

WHERE THE FILES LIVE

Everything resolves from PAIRS_DATA_DIR, defaulting to `research/`. On the VM that
env var points at the bind-mounted `trading_data/` so the book survives a container
rebuild. Nothing here hardcodes an absolute path.
"""
import os

import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("PAIRS_DATA_DIR",
                          os.path.join(PROJECT_ROOT, "research"))
LOG_DIR = os.environ.get("PAIRS_LOG_DIR", os.path.join(PROJECT_ROOT, "logs"))

STATE_PATH      = os.path.join(DATA_DIR, "scanner_state.json")
LEDGER_PATH     = os.path.join(DATA_DIR, "scanner_trades.csv")
CANDIDATES_PATH = os.path.join(DATA_DIR, "scanner_candidates.json")
SCAN_HISTORY_DIR = os.path.join(DATA_DIR, "scan_history")
TICKS_DIR       = os.path.join(DATA_DIR, "monitor_ticks")
LOCK_PATH       = os.path.join(DATA_DIR, "stop_monitor.lock")

SCANNER_LOG   = os.path.join(LOG_DIR, "scanner.log")
MONITOR_LOG   = os.path.join(LOG_DIR, "stop_monitor.log")
HEARTBEAT_PATH = os.path.join(LOG_DIR, "stop_monitor_heartbeat.log")

# ---------------------------------------------------------------------------
# The settled configuration. One definition, both processes.
# ---------------------------------------------------------------------------

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

# Inert below $5,000 of equity, because gross notional is
# leverage * capital_frac * equity = 1.0 * equity under the settled parameters.
# Above that it pins position size flat. Without it, percentage-of-equity sizing
# grows notional without bound and the equity curve stops meaning anything -- the
# full-spec walk-forward produced 1.1e11x that way, arithmetically correct and
# physically impossible.
MAX_NOTIONAL = 5000.0

# How stale the candidates file may be before the monitor refuses to open from it.
# Past this the 30-minute scanner is down and the numbers describe a market that
# has moved on.
CANDIDATES_MAX_AGE_MIN = 60.0

# ---------------------------------------------------------------------------
# FIXED ledger schema. Open rows and close rows conform to the SAME columns, and
# every row is reindexed onto them before writing. See the module docstring.
# ---------------------------------------------------------------------------

LEDGER_COLUMNS = [
    "event", "trade_num", "ticker_a", "ticker_b", "time",
    "opened_at", "closed_at", "hours_held", "exit_reason",
    "entry_spread", "exit_spread", "mu_at_entry", "sigma_at_entry",
    "z_at_entry", "beta_at_entry", "alpha_at_entry", "theta_at_entry",
    "take_profit_level",
    "leg_a_notional", "leg_b_notional", "gross_notional", "margin", "leverage",
    "notional_capped",
    "realized_pnl_net", "net_pct", "r",

    # -- what this build exists to measure ------------------------------------
    # The stop is a bar-close detector today and it has never once filled at its
    # level: 0 of 9,704 stop-outs, median overshoot 1.53x. These columns make the
    # same number fall out of the live ledger automatically, so "did watching it
    # every second help" is a groupby, not another study.
    "exit_detected_at",     # when the breach was FIRST seen, not when booked
    "exit_level_spread",    # where the stop was placed
    "overshoot_ratio",      # |fill - entry| / stop_distance   <- THE number
    "confirm_delay_ms",     # first breach -> fill, the cost of debouncing
    "blind_gap_seconds",    # feed outage immediately before this exit, 0 if none
    "feed_state",           # live | rest_fallback | recovered_from_blind
    "entry_bar_z",          # z at the bar close that produced the candidate
    "entry_fill_z",         # z at the actual fill -- the two differ, on purpose
    "exec_spread_at_exit",  # executable-side spread, diagnostic only
]

# Rows carrying any of these mean the exit was not observed live and must be
# excluded before quoting an overshoot statistic.
BLIND_EXCLUDE = ("recovered_from_blind",)


def _ensure_dirs() -> None:
    for d in (DATA_DIR, LOG_DIR):
        os.makedirs(d, exist_ok=True)


# ---------------------------------------------------------------------------
# State. Open positions are persisted whole -- the frozen entry signal IS the
# state an exit needs, so there is nothing to recompute and nothing to drift.
# ---------------------------------------------------------------------------

def load_portfolio(equity: float = ACCOUNT_EQUITY):
    """Rebuild the book from disk: positions from state, equity from the ledger.

    Equity is re-summed from the ledger rather than read from the state file. A
    state file can go stale; the ledger is the record of what actually happened,
    and position size is a function of equity, so a wrong equity silently
    mis-sizes every subsequent trade.
    """
    # Imported here, not at module scope: `live_scanner` imports this module for
    # its config alone and must not pay for pandas-heavy portfolio machinery.
    import json
    from datetime import datetime

    from portfolio import Portfolio, Position

    pf = Portfolio(equity=equity, max_slots=MAX_SLOTS,
                   capital_frac=CAPITAL_FRAC, leverage=LEVERAGE,
                   stop_sigma=STOP_SIGMA, max_hold_hours=MAX_HOLD_HOURS,
                   max_per_ticker=MAX_PER_TICKER, max_notional=MAX_NOTIONAL)

    if os.path.exists(STATE_PATH):
        with open(STATE_PATH) as fh:
            st = json.load(fh)
        for p in st.get("open_positions", []):
            pos = Position(p["trade_num"], p["ticker_a"], p["ticker_b"],
                           p["signal"], p["sizing"],
                           datetime.fromisoformat(p["opened_at"]), STOP_SIGMA)
            pos.entry_bar_z = p.get("entry_bar_z")
            pf.open_positions.append(pos)
        pf.next_trade_num = st.get("next_trade_num", 1)

    if os.path.exists(LEDGER_PATH):
        d = pd.read_csv(LEDGER_PATH)
        realized = 0.0
        if "event" in d.columns and "realized_pnl_net" in d.columns:
            closes = d[d["event"] == "close"]
            realized = float(pd.to_numeric(closes["realized_pnl_net"],
                                           errors="coerce").fillna(0.0).sum())
        pf.equity = equity + realized
    return pf


def save_portfolio(pf) -> None:
    """Atomic write. A kill mid-write cannot leave a truncated state file."""
    import json

    _ensure_dirs()
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w") as fh:
        json.dump({
            "saved_at": pd.Timestamp.now(tz="UTC").isoformat(),
            "equity": pf.equity,
            "next_trade_num": pf.next_trade_num,
            "open_positions": [{
                "trade_num": p.trade_num, "ticker_a": p.ticker_a,
                "ticker_b": p.ticker_b, "opened_at": p.opened_at.isoformat(),
                "signal": p.signal, "sizing": p.sizing,
                "entry_bar_z": getattr(p, "entry_bar_z", None),
            } for p in pf.open_positions],
        }, fh, indent=2, default=str)
    os.replace(tmp, STATE_PATH)


def append_ledger(rows: list) -> None:
    """Append onto the FIXED schema, dropping anything not in it.

    `reindex(columns=...)` is the whole point: it fills missing fields with NaN
    and puts every column in the same order regardless of whether the row is an
    open or a close, so an appended close can never land under an open's header.
    """
    if not rows:
        return
    _ensure_dirs()
    d = pd.DataFrame(rows).reindex(columns=LEDGER_COLUMNS)
    d.to_csv(LEDGER_PATH, mode="a", header=not os.path.exists(LEDGER_PATH),
             index=False)
