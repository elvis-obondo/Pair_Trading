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
# Open positions marked to the monitor's own live quotes, rewritten every
# heartbeat. A read-only view: nothing reads it back into the book.
POSITIONS_PATH  = os.path.join(DATA_DIR, "open_positions.json")

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
# One open position per ticker. portfolio.py calls None "the settled spec", but
# every measured result was produced with 1: the 12,597-trade study, the +0.74R
# assumed-fill edge, the stop-width sweep, all of it. Running None live would be
# testing a configuration nothing was measured under.
#
# It is not a theoretical concern. The first live book filled with BERA in 4 of
# 10 positions, AGLD in 2, ATOM in 2, DOT in 2 -- ten trades, about five
# independent bets, and four stops that would fire together if BERA kept
# trending. See the 01:42 block in logs/stop_monitor.log.
MAX_PER_TICKER = 1

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

# How far past its level an adverse exit actually fills, as a multiple of the
# stop distance. THE BACKTEST BOOKS STOPS HERE.
#
# 1.00 would be perfect execution and has never once happened. 1.53 is what a
# 30-minute bar-close check produced across 9,704 backtested stop-outs, and was
# the default for exactly as long as bar-close checking was the only mechanism.
# Neither is what the system does now.
#
# 1.04 is MEASURED, from the live tick-watching monitor:
#     13 stop-outs, median 1.042x, mean 1.075x, confirm delays 100-255ms
#
# It is a small sample and it should be re-derived as the ledger grows --
# scripts/check_vm.sh overshoot prints the current figure. Raise this the day
# the live median disagrees with it; a backtest booking fills better than the
# live system achieves is a backtest that lies.
MEASURED_STOP_OVERSHOOT = 1.04

# ---------------------------------------------------------------------------
# RETENTION. Everything this system writes on a schedule grows without bound
# unless something deletes it, and the VM has an 11GB margin, not 11TB.
#
# Measured rates: tick capture is ~20 instruments at 1 Hz, roughly 20-25MB/day,
# which is 7-9GB/year -- the only one big enough to fill the disk on its own.
# Scan history is ~4,800 rows/day and the logs are ~1MB/day.
#
# The ledger is NEVER pruned. It is the record of what the account did, it is
# small, and equity is re-summed from it on every start.
# ---------------------------------------------------------------------------

RETAIN_TICK_DAYS = 14          # enough to re-walk any trade still in memory
RETAIN_SCAN_HISTORY_DAYS = 90  # a quarter of "what was dislocated, and when"
LOG_MAX_BYTES = 32 * 1024 * 1024


def prune_dated(directory: str, keep_days: int) -> list:
    """Delete YYYY-MM-DD-named files and directories older than keep_days.

    Named by date rather than checked by mtime on purpose: a file's mtime moves
    when it is rewritten, so an mtime rule would keep re-dating the same day and
    never expire it. The name is what the data actually is.
    """
    import datetime as _dt
    import re
    import shutil

    if not os.path.isdir(directory):
        return []
    cutoff = _dt.date.today() - _dt.timedelta(days=keep_days)
    removed = []
    for name in os.listdir(directory):
        m = re.match(r"^(\d{4}-\d{2}-\d{2})(\.parquet)?$", name)
        if not m:
            continue
        try:
            day = _dt.date.fromisoformat(m.group(1))
        except ValueError:
            continue
        if day >= cutoff:
            continue
        path = os.path.join(directory, name)
        shutil.rmtree(path, ignore_errors=True) if os.path.isdir(path) else os.remove(path)
        removed.append(name)
    return removed


def rotate_log(path: str, max_bytes: int = LOG_MAX_BYTES) -> bool:
    """Keep one previous generation. Crude on purpose -- no dependency, and a
    log that rotates is better than one that quietly eats the disk.

    os.replace overwrites the existing .1, so a log is bounded at 2 * max_bytes
    rather than growing a numbered tail forever.
    """
    try:
        if os.path.getsize(path) < max_bytes:
            return False
    except OSError:
        return False
    os.replace(path, path + ".1")
    return True


def rotate_logs_in(directory: str = None, max_bytes: int = LOG_MAX_BYTES) -> list:
    """Rotate EVERY *.log in a directory, not a hand-maintained list.

    The hand-maintained list missed the ones that matter most. Both LaunchAgents
    and both cron jobs redirect stdout and stderr into this directory --
    scanner.out.log, stop_monitor.out.log and their .err siblings -- and the
    monitor prints every line it logs, so stop_monitor.out.log is a full
    duplicate of stop_monitor.log that nothing was capping. Anything added later
    is covered by construction.
    """
    directory = LOG_DIR if directory is None else directory
    if not os.path.isdir(directory):
        return []
    return [f for f in sorted(os.listdir(directory))
            if f.endswith(".log") and rotate_log(os.path.join(directory, f), max_bytes)]

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

    # -- is it actually a pair trade? -----------------------------------------
    # The screen is |z| >= 3 and nothing else: no cointegration test, no bound
    # on beta, no fit quality. Measured over 3.6M candidate observations, only
    # 18.4% have beta in [0.8, 1.2] and 17.4% have beta < 0, which puts BOTH
    # legs on the same side. The median position carries 34.6% of its gross as
    # one-way market exposure. These columns record that per trade so the cost
    # can be measured before any filter is chosen.
    "r2_at_entry",          # fit quality of the hedge over the entry window
    "net_exposure",         # signed dollars of one-way exposure, leg A + leg B
    "net_exposure_frac",    # the same over gross: 0 neutral, +/-1 directional
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

    # getsize, not just exists. docker-compose.trading.yml's setup deliberately
    # pre-creates this as an EMPTY file, because Docker bind-mounts a missing
    # file path as a directory instead of erroring -- so on a fresh deployment
    # the ledger exists and is zero bytes, and pd.read_csv raises
    # EmptyDataError("No columns to parse from file"). That crash-looped the
    # monitor on the VM the first time it started with no trades.
    try:
        if os.path.getsize(LEDGER_PATH) > 0:
            # Self-heal a ledger written under an older LEDGER_COLUMNS before
            # trying to parse it. Without this, adding a column makes every
            # restart crash-loop on a ParserError and the book cannot be loaded
            # at all -- see migrate_ledger_schema. A residual parse error is
            # deliberately NOT swallowed: crash-looping loudly beats resuming
            # with equity silently reset to ACCOUNT_EQUITY.
            migrate_ledger_schema()
            d = pd.read_csv(LEDGER_PATH)
            realized = 0.0
            if "event" in d.columns and "realized_pnl_net" in d.columns:
                closes = d[d["event"] == "close"]
                realized = float(pd.to_numeric(closes["realized_pnl_net"],
                                               errors="coerce").fillna(0.0).sum())
            pf.equity = equity + realized
            # Re-base starting_equity too. _close() recomputes equity as
            # `starting_equity + sum(self.closed)`, and self.closed is empty
            # after a restart -- so leaving starting_equity at the original
            # ACCOUNT_EQUITY makes the FIRST close after any restart silently
            # erase every loss booked before it. Caught live on the VM: seven
            # closes totalling -20.31 showed equity 290.93 instead of 279.69,
            # because a restart landed between close 4 and close 5. Equity
            # drifts UP across restarts, and size is a function of equity.
            pf.starting_equity = pf.equity
    except (OSError, pd.errors.EmptyDataError):
        # No ledger yet, or a header-only one. Starting equity is correct.
        pass
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
    # getsize, not exists. docker-compose.trading.yml's setup pre-creates the
    # ledger as an EMPTY file on purpose -- Docker bind-mounts a missing file
    # path as a directory rather than erroring -- so `exists` is True on a fresh
    # deployment and the header was never written. The result is a ledger full
    # of rows that pandas cannot parse: every column name is wrong, equity
    # re-sums to garbage on restart, and nothing complains.
    try:
        need_header = os.path.getsize(LEDGER_PATH) == 0
    except OSError:
        need_header = True

    # The header on disk was written once, by the first append this file ever
    # saw. Reindexing every row onto the CURRENT LEDGER_COLUMNS keeps opens and
    # closes aligned with each other -- but says nothing about whether they are
    # aligned with that header. Add a column to LEDGER_COLUMNS and every
    # subsequent row is silently wider than the header above it, which is not a
    # warning, it is a file pandas refuses to parse at all:
    #
    #     ParserError: Expected 36 fields in line 26, saw 39
    #
    # and the monitor crash-loops on its next restart, unable to load the book.
    # That happened live on 2026-09-13 when r2_at_entry, net_exposure and
    # net_exposure_frac were added. Migrate instead: widen the existing rows to
    # the current schema and rewrite the file once.
    if not need_header:
        migrate_ledger_schema()

    d.to_csv(LEDGER_PATH, mode="a", header=need_header, index=False)


def migrate_ledger_schema() -> bool:
    """Rewrite the ledger onto the current LEDGER_COLUMNS if it is behind.

    Returns True if it rewrote. Cheap: reads the header line only unless a
    migration is actually needed, so the common path costs one small read.

    Columns present on disk but gone from LEDGER_COLUMNS are KEPT, appended
    after the known ones. A ledger is the record of what the account did, and
    dropping a column because the code moved on destroys history that cannot be
    recovered.
    """
    import csv

    try:
        with open(LEDGER_PATH, newline="") as fh:
            header = next(csv.reader(fh), None)
    except (OSError, StopIteration):
        return False
    if header is None or header == LEDGER_COLUMNS:
        return False

    target = LEDGER_COLUMNS + [c for c in header if c not in LEDGER_COLUMNS]
    if header == target:
        return False

    with open(LEDGER_PATH, newline="") as fh:
        d = pd.read_csv(fh, names=header, skiprows=1, dtype=str,
                        keep_default_na=False)
    # Written to a temp file and moved into place: a kill partway through a
    # rewrite of the account's only ledger must not leave a truncated one.
    tmp = LEDGER_PATH + ".migrating"
    d.reindex(columns=target).to_csv(tmp, index=False)
    os.replace(tmp, LEDGER_PATH)
    return True
