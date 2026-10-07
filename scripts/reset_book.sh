#!/usr/bin/env bash
# Archive the live book and start a new one flat at ACCOUNT_EQUITY.
#
#   scripts/reset_book.sh            do it (asks first)
#   scripts/reset_book.sh --dry-run  show what would happen
#
# WHY YOU WOULD EVER DO THIS
#
# When the rules change, a ledger that spans both sets of rules cannot answer
# anything. Every win rate, hold time and R figure becomes a blend of two
# regimes with no column to separate them. Archive at the boundary instead.
#
# NOTHING IS DELETED. The ledger, the state file and the equity curve are copied
# to trading_data/archive/<timestamp>/ first. This repo has lost a book to a
# ledger bug once already (see attic/docs/HANDOFF.md); archives are cheap.
#
# WHAT IS KEPT ACROSS THE RESET
#
# monitor_ticks/ stays. Raw prices are regime-independent, and they are what
# makes the new equity curve backfillable from its first position.
#
# The overshoot statistic also pools across a reset: it measures how far past
# its level a fill lands, which is an EXIT-side property and has nothing to do
# with entry rules. MEASURED_STOP_OVERSHOOT is derived from it, so binning those
# rows would knock the basis out from under the backtest default.
#
# OPEN POSITIONS are booked closed at the current mark with
# exit_reason="book_reset". Dangling open rows would reconcile as unfinished
# trades forever; a distinct reason keeps them complete AND trivially
# excludable, so a reset can never be mistaken for a take-profit.
set -uo pipefail

PROJECT="project-0671be06-e22a-44d8-83c"
ZONE="us-central1-a"
INSTANCE="pairs-trading"
REMOTE="/home/elvisobondo/Pair_Trading"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
G="--project=$PROJECT --zone=$ZONE"
C="docker compose -f docker-compose.trading.yml"

DRY=""
[ "${1:-}" = "--dry-run" ] && DRY="--dry-run"

ssh_vm() { gcloud compute ssh "$INSTANCE" $G --command="$1" < /dev/null; }
bold() { printf "\n\033[1m%s\033[0m\n" "$*"; }
die()  { printf "  \033[31mfail\033[0m %s\n" "$*"; exit 1; }

bold "Current book"
ssh_vm "docker exec pairs-stop-monitor python /app/research/reset_book.py --report" \
    || die "could not read the book"

if [ -z "$DRY" ]; then
    printf "\n\033[1mArchive this book and start flat?\033[0m\n"
    printf "  Everything is copied to trading_data/archive/ first. Nothing is deleted.\n"
    read -r -p "  type yes to continue: " a
    [ "$a" = "yes" ] || { echo "  skipped."; exit 0; }
fi

bold "Stopping the monitor"
# It must not be writing while the ledger is moved. It is the only writer, so
# stopping it is sufficient -- no lock dance needed.
ssh_vm "cd $REMOTE && $C stop stop-monitor" || die "could not stop the monitor"

bold "Archiving and resetting"
ssh_vm "cd $REMOTE && docker compose -f docker-compose.trading.yml run --rm \
    --entrypoint python stop-monitor /app/research/reset_book.py $DRY" \
    || { ssh_vm "cd $REMOTE && $C start stop-monitor"; die "reset failed — monitor restarted, book untouched"; }

bold "Starting the monitor on the new book"
ssh_vm "cd $REMOTE && $C start stop-monitor && sleep 4 && tail -3 logs/stop_monitor.log"

bold "Done"
echo "  scripts/check_vm.sh positions    the new book"
echo "  scripts/check_vm.sh overshoot    still pools across the reset"
