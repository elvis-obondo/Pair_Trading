#!/bin/bash
# Run research on the Google Cloud machine pt-research, from the laptop.
#
#   scripts/gcp_run.sh "<command>" [--log research/<dir>/logs/<name>.log]
#       Starts the machine if it is stopped, rsyncs the repo up, and runs
#       <command> in ~/Pair_Trading under nohup with the research venv active.
#       Its output goes to the --log path (default
#       research/hyperliquid/logs/gcp_run_<UTC stamp>.log, always under
#       research/**/logs/). Returns at once; the machine stops itself 30 min
#       after the command ends (idle auto-stop, scripts/gcp_idle_stop.sh).
#   scripts/gcp_run.sh pull
#       rsyncs back every research/**/logs/ file, small outputs (*.csv, *.json,
#       *.png under 50 MB anywhere in research/, never overwriting a newer
#       laptop copy), and the machine's NUMBERS.md to
#       research/.gcp_pull/NUMBERS.md with a diff against the laptop's.
#   scripts/gcp_run.sh status       instance state + the last idle-stop lines
#   scripts/gcp_run.sh provision    one-time: sync, then scripts/gcp_provision.sh
#
# The sync sends nothing gitignored (so no .env, no user_data/config*.json: the
# OKX keys never leave the laptop), and explicitly excludes .env*,
# user_data/config*.json, .venv, attic/, user_data/data/, research/datasets/,
# research/hyperliquid/flow/, __pycache__, .git/. Data lives on the machine,
# pulled from S3 (see docs/HYPERLIQUID_HANDOFF.md). A second pass deletes .py
# files that no longer exist on the laptop, so moved or retired code cannot be
# imported there. ssh goes through `gcloud compute ssh` only.
#
# RULES. Never `source .venv/bin/activate` in an interactive shell on the
# machine: VIRTUAL_ENV keeps the idle-stop from ever firing. Run every job,
# including long non-Python ones (aws s3 pulls, uploads), through
# `gcp_run.sh "<cmd>"`, which marks it busy; a bare-ssh job can be stopped
# mid-transfer. NUMBERS.md receipts are written on the LAPTOP only; machine
# runs write logs, and `pull` shows any machine-side NUMBERS.md diff.
set -euo pipefail
PROJECT=project-0671be06-e22a-44d8-83c
ZONE=us-central1-a
VM=pt-research
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
G="gcloud compute --project=$PROJECT"
HOST="$VM.$ZONE.$PROJECT"            # the alias `gcloud compute config-ssh` writes

state() { $G instances describe $VM --zone=$ZONE --format='value(status)'; }
ensure_up() {
  s=$(state)
  while [ "$s" = STOPPING ] || [ "$s" = SUSPENDING ]; do sleep 10; s=$(state); done
  if [ "$s" != RUNNING ]; then
    echo "starting $VM (was $s)"; $G instances start $VM --zone=$ZONE --quiet >/dev/null
  fi
  $G config-ssh --quiet >/dev/null                   # refresh the host alias (IP changes on start)
  # one gcloud ssh pushes this laptop's key if the instance lacks it (config-ssh does not)
  for i in $(seq 1 12); do $G ssh $VM --zone=$ZONE --command=true --quiet >/dev/null 2>&1 && break; sleep 5; done
  for i in $(seq 1 30); do ssh -o ConnectTimeout=5 -o BatchMode=yes "$HOST" true 2>/dev/null && return; sleep 5; done
  echo "ssh to $VM not ready"; exit 1
}
sync_up() {
  # no --delete: files the machine made (logs, outputs) are never removed by a sync.
  # NUMBERS.md goes up only when the laptop copy is newer (--update), so a run's
  # receipts on the machine are not overwritten before `pull`.
  local EX=(--exclude .env --exclude '.env.*' --exclude 'user_data/config*.json'
            --exclude .venv/ --exclude attic/ --exclude user_data/data/ --exclude research/datasets/
            --exclude research/hyperliquid/flow/ --exclude __pycache__/ --exclude .git/ --exclude .gcp_pull/)
  rsync -az "${EX[@]}" --filter=':- .gitignore' \
    --exclude research/dislocation_model/NUMBERS.md \
    -e ssh "$ROOT/" "$HOST:Pair_Trading/"
  # code-only delete pass: remove machine .py files the laptop no longer has
  rsync -az --delete "${EX[@]}" --include '*/' --include '*.py' --exclude '*' \
    -e ssh "$ROOT/" "$HOST:Pair_Trading/"
  rsync -az --update -e ssh "$ROOT/research/dislocation_model/NUMBERS.md" "$HOST:Pair_Trading/research/dislocation_model/NUMBERS.md"
}

case "${1:-}" in
pull)
  ensure_up
  rsync -az --update -e ssh --prune-empty-dirs --max-size=50m \
    --exclude 'research/datasets/' --exclude 'research/hyperliquid/flow/' --exclude '.venv/' \
    --exclude 'user_data/' --exclude 'attic/' \
    --include '*/' --include 'research/**/logs/**' --include 'research/**.csv' \
    --include 'research/**.json' --include 'research/**.png' --exclude '*' \
    "$HOST:Pair_Trading/" "$ROOT/"
  mkdir -p "$ROOT/research/.gcp_pull"
  rsync -az -e ssh "$HOST:Pair_Trading/research/dislocation_model/NUMBERS.md" "$ROOT/research/.gcp_pull/NUMBERS.md"
  diff -u "$ROOT/research/dislocation_model/NUMBERS.md" "$ROOT/research/.gcp_pull/NUMBERS.md" || true
  ;;
status)
  echo "$VM: $(state)"
  [ "$(state)" = RUNNING ] && ssh "$HOST" 'tail -5 /var/log/pt-idle.log' || true
  ;;
provision)
  ensure_up; sync_up
  ssh "$HOST" 'bash ~/Pair_Trading/scripts/gcp_provision.sh'
  ;;
""|-h|--help)
  sed -n '2,25p' "$0"; exit 1 ;;
*)
  CMD=$1; shift
  LOG="research/hyperliquid/logs/gcp_run_$(date -u +%Y%m%dT%H%M%SZ).log"
  if [ "${1:-}" = --log ]; then LOG=$2; fi
  case "$LOG" in research/*/logs/*|research/logs/*) ;; *) echo "--log must be under research/**/logs/"; exit 1;; esac
  [[ "$LOG" =~ ^[A-Za-z0-9_./-]+$ ]] || { echo "--log may only contain [A-Za-z0-9_./-]"; exit 1; }
  ensure_up; sync_up
  Q=$(printf '%q' "$CMD")
  ssh "$HOST" "cd ~/Pair_Trading && mkdir -p \$(dirname $LOG) && \
    nohup env VIRTUAL_ENV=\$HOME/Pair_Trading/.venv PATH=\$HOME/Pair_Trading/.venv/bin:\$PATH \
      OMP_NUM_THREADS=1 PYTHONUNBUFFERED=1 bash -c $Q > $LOG 2>&1 < /dev/null & echo \"started pid \$! -> $LOG\""
  ;;
esac
