#!/usr/bin/env bash
# One live-scanner cycle: refresh 30m data, screen 22,366 pairs, manage the
# paper book. Exits when done -- it is not a daemon.
#
# Fired every 30 minutes by the com.pairtrading.scanner LaunchAgent (see
# scripts/com.pairtrading.scanner.plist for the install command). Safe to run by
# hand at any time; all state lives on disk and a cycle is idempotent in the
# sense that a crash costs one cycle, not the run.
#
# Measured cycle cost: ~80s data refresh + ~2s panel load + ~9s scan.
# Note it pulls ONLY the 30m futures timeframe. scripts/update_data.sh pulls
# four timeframes per ticker and takes 5m21s; the scanner reads only 30m, and
# that difference is what makes a 30-minute cycle comfortable.
#
# NO ORDERS ARE SUBMITTED. This maintains a paper book with the production
# sizer and exit logic; execution is deliberately not wired up.
#
# Outputs:
#   research/scanner_candidates.json  what is dislocated right now (top 25)
#   research/scanner_trades.csv       the ledger, open/close rows
#   research/scanner_state.json       open positions, for the next cycle
#   logs/scanner.log                  one block per cycle
#
# Useful:
#   cat research/scanner_candidates.json | python3 -m json.tool | head -40
#   tail -f logs/scanner.log
#   scripts/run_scanner.sh --no-refresh     # scan without downloading
set -euo pipefail
cd "$(dirname "$0")/.."
python3 research/live_scanner.py "$@"

# Split deployment: the monitor runs on the VM and reads candidates from a file.
# No-ops unless .push_to_vm exists, and never fails the cycle.
scripts/push_candidates.sh
