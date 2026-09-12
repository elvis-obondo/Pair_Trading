#!/usr/bin/env bash
# The stop monitor: watches every open position's stop tick by tick and closes
# it when the level is crossed.
#
# UNLIKE run_scanner.sh THIS IS A DAEMON. It stays up. The scanner is single-shot
# every 30 minutes; the whole point of this process is that 30 minutes is far too
# long to go without looking. See research/stop_monitor.py for the measurement
# that says so.
#
# It takes an exclusive lock on research/stop_monitor.lock and refuses to start
# if another copy holds it. Two monitors against one ledger produce two books
# that each believe they own the equity, and every subsequent position is then
# mis-sized in both.
#
# NO ORDERS ARE SUBMITTED. Paper book, production sizer and exit logic, live
# prices — execution deliberately not wired.
#
# Outputs:
#   research/scanner_trades.csv     the ledger; overshoot_ratio is the column
#                                   this whole build exists to move
#   research/scanner_state.json     open positions, for a restart
#   research/monitor_ticks/         1 Hz quotes for held legs, by day
#   logs/stop_monitor.log           opens, closes, reconnects, subscribe errors
#   logs/stop_monitor_heartbeat.log one line every 10s: feed, tick ages, blind
#
# Useful:
#   tail -f logs/stop_monitor.log
#   tail -5 logs/stop_monitor_heartbeat.log
#   scripts/run_stop_monitor.sh --dry-run     # watch, book nothing, no lock
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 research/stop_monitor.py "$@"
