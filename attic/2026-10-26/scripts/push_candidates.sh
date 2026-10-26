#!/usr/bin/env bash
# Ship the local scan's candidates to the VM's monitor.
#
# For the split deployment: the scanner runs here (it needs 531MB and a 60MB
# panel), the stop monitor runs on the VM (it needs 174MB and never sleeps).
# The monitor reads candidates from a file, so this is the whole integration.
#
# OPT-IN. Does nothing unless the sentinel file .push_to_vm exists in the repo
# root. scripts/vm_migrate.sh creates it; `rm .push_to_vm` turns it off.
#
# ALWAYS EXITS 0. A failed push must not fail the scan cycle -- the laptop is
# often offline, and a stale candidates file is already handled: the monitor
# refuses to open from anything older than 60 minutes.
#
# WHAT IT MEANS WHEN THE LAPTOP IS ASLEEP: no new candidates reach the VM, so no
# new positions open. Every position ALREADY open keeps being watched, which is
# the part under test. Entries are intermittent; the stop is not.
set -uo pipefail
cd "$(dirname "$0")/.."

[ -f .push_to_vm ] || exit 0

PROJECT="${PAIRS_VM_PROJECT:-project-0671be06-e22a-44d8-83c}"
ZONE="${PAIRS_VM_ZONE:-us-central1-a}"
INSTANCE="${PAIRS_VM_INSTANCE:-pairs-trading}"
SRC="research/scanner_candidates.json"
DST="/home/elvisobondo/Pair_Trading/trading_data/scanner_candidates.json"

[ -f "$SRC" ] || { echo "push_candidates: no $SRC yet"; exit 0; }

# Land it under a temp name and move it into place on the VM, so the monitor can
# never read a half-written file. It polls the mtime and reads immediately.
if gcloud compute scp "$SRC" "$INSTANCE:$DST.tmp" \
      --project="$PROJECT" --zone="$ZONE" --quiet 2>&1 | tail -2; then
    gcloud compute ssh "$INSTANCE" --project="$PROJECT" --zone="$ZONE" --quiet \
        --command="mv $DST.tmp $DST" 2>&1 | tail -1
    echo "push_candidates: delivered $(date -u +%H:%M:%SZ)"
else
    echo "push_candidates: FAILED — the VM will keep watching open positions but open nothing new"
fi
exit 0
