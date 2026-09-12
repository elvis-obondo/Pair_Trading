#!/usr/bin/env bash
# Move the live paper system to the VM: resize, deploy, start, schedule.
#
# RUN THIS YOURSELF, IN YOUR OWN TERMINAL. It resizes a running instance off the
# free tier and stops a process that has been up three weeks. Each destructive
# step asks first, and every step is idempotent, so a Ctrl-C and a re-run costs
# nothing.
#
#   scripts/vm_migrate.sh            # all steps, with prompts
#   scripts/vm_migrate.sh 3          # just step 3
#   scripts/vm_migrate.sh 3 4 5      # a range
#   scripts/vm_migrate.sh status     # what is true right now
#
# WHAT CHANGES
#   e2-micro (1GB, free)  ->  e2-medium (4GB, ~$25/month)
#   nautilus single-pair  ->  stop-monitor service + 30-min scanner cron
#
# WHY THE RESIZE. Measured 2026-09-12: scanner peak RSS 531MB, stop monitor
# 174MB, VM OS+docker 258MB. The download and the scan run sequentially so they
# never stack, putting peak near 1GB. e2-micro has 958MB total and 297MB free.
set -uo pipefail

PROJECT="project-0671be06-e22a-44d8-83c"
ZONE="us-central1-a"
INSTANCE="pairs-trading"
MACHINE="e2-medium"
REMOTE="/home/elvisobondo/Pair_Trading"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
G="--project=$PROJECT --zone=$ZONE"
GLIST="--project=$PROJECT --zones=$ZONE"

bold() { printf "\n\033[1m%s\033[0m\n" "$*"; }
ok()   { printf "  \033[32mok\033[0m   %s\n" "$*"; }
warn() { printf "  \033[33mwarn\033[0m %s\n" "$*"; }
die()  { printf "  \033[31mfail\033[0m %s\n" "$*"; exit 1; }

ssh_vm() { gcloud compute ssh "$INSTANCE" $G --command="$1"; }
scp_vm() { gcloud compute scp $G "$@"; }

confirm() {
    printf "\n\033[1m%s\033[0m\n" "$1"
    read -r -p "  type yes to continue: " a
    [ "$a" = "yes" ] || { echo "  skipped."; return 1; }
    return 0
}

machine_type() {
    gcloud compute instances describe "$INSTANCE" $G \
        --format="value(machineType)" 2>/dev/null | sed 's|.*/||'
}

# ---------------------------------------------------------------------------

step_status() {
    bold "Current state"
    gcloud compute instances list $GLIST --filter="name=$INSTANCE"
    echo
    ssh_vm "free -m | head -2; echo; df -h / | tail -1; echo; docker ps --format 'table {{.Names}}\t{{.Status}}'; echo; echo 'cron:'; crontab -l 2>/dev/null | grep vm_scan_cycle || echo '  (none)'"
}

step_1_resize() {
    bold "STEP 1 — resize to $MACHINE"
    local cur; cur="$(machine_type)"
    if [ "$cur" = "$MACHINE" ]; then ok "already $MACHINE"; return 0; fi
    echo "  currently: $cur"
    echo
    echo "  This stops the instance, which stops the retired nautilus paper"
    echo "  process. Its ledger is already archived locally at"
    echo "  research/retired_nautilus_paper/ — nothing is lost."
    echo
    echo "  It also ENDS THE FREE TIER. e2-micro is free in us-central1;"
    echo "  $MACHINE is roughly \$25/month on demand, less with sustained use."
    confirm "Resize $INSTANCE from $cur to $MACHINE?" || return 0

    gcloud compute instances stop  "$INSTANCE" $G || die "stop failed"
    gcloud compute instances set-machine-type "$INSTANCE" $G --machine-type="$MACHINE" \
        || die "set-machine-type failed"
    gcloud compute instances start "$INSTANCE" $G || die "start failed"

    echo "  waiting for ssh..."
    until ssh_vm "true" >/dev/null 2>&1; do sleep 5; done
    ok "resized and back up: $(machine_type)"
    ssh_vm "free -m | head -2"
}

step_2_retire() {
    bold "STEP 2 — retire the old container"
    if ! ssh_vm "docker ps -a --format '{{.Names}}' | grep -qx pairs-trading" 2>/dev/null; then
        ok "already gone"
        return 0
    fi
    echo "  The container 'pairs-trading' runs the deleted nautilus process."
    ssh_vm "docker ps --format '{{.Names}} {{.Status}}' | grep pairs-trading || true"
    confirm "Stop and remove it?" || return 0
    ssh_vm "docker rm -f pairs-trading" && ok "removed"
    # The image is rebuilt from the new Dockerfile in step 5; drop the old tag so
    # a stale layer cannot be started by accident in between.
    ssh_vm "docker image rm -f pairs-trading:latest 2>/dev/null || true"
}

step_3_push() {
    bold "STEP 3 — push source"
    # Source only. trading_data/ on the VM is the book and is never overwritten.
    ssh_vm "mkdir -p $REMOTE/user_data" || die "mkdir failed"

    echo "  research/ ..."
    scp_vm --recurse "$ROOT/research" "$INSTANCE:$REMOTE/" || die "research push failed"
    echo "  scripts/ ..."
    scp_vm --recurse "$ROOT/scripts"  "$INSTANCE:$REMOTE/" || die "scripts push failed"
    for f in Dockerfile.trading docker-compose.trading.yml docker-compose.yml requirements.txt README.md; do
        echo "  $f ..."
        scp_vm "$ROOT/$f" "$INSTANCE:$REMOTE/$f" || die "$f push failed"
    done
    # Download-only config: exchange key, secret and password are all empty, so
    # nothing secret crosses the wire. It carries the 212-pair whitelist that
    # drives the download.
    echo "  user_data/config.json (no credentials in it) ..."
    scp_vm "$ROOT/user_data/config.json" "$INSTANCE:$REMOTE/user_data/config.json" \
        || die "config push failed"
    echo "  user_data/normalized/manifest.json ..."
    ssh_vm "mkdir -p $REMOTE/user_data/normalized"
    scp_vm "$ROOT/user_data/normalized/manifest.json" \
        "$INSTANCE:$REMOTE/user_data/normalized/manifest.json" || true

    # The deleted package must not survive as stale bytes on the VM.
    ssh_vm "rm -rf $REMOTE/nautilus $REMOTE/diagnostics" && ok "removed retired source"
    ok "pushed"
}

step_4_dirs() {
    bold "STEP 4 — one-time runtime directories"
    # Docker bind-mounts a missing FILE path as an empty DIRECTORY rather than
    # erroring. Pre-creating the ledger as a real file avoids that footgun; the
    # rest are genuinely directories.
    ssh_vm "cd $REMOTE && mkdir -p trading_data/scan_history trading_data/monitor_ticks logs user_data/data && touch trading_data/scanner_trades.csv && ls -la trading_data/" \
        && ok "created"
}

step_5_build() {
    bold "STEP 5 — build the image and start the monitor"
    echo "  First build pulls python:3.12-slim and installs pandas/numpy/scipy/"
    echo "  statsmodels/websockets/ccxt. Expect a few minutes."
    ssh_vm "cd $REMOTE && docker compose -f docker-compose.trading.yml up -d --build stop-monitor" \
        || die "build/start failed"
    echo "  waiting for first log lines..."
    sleep 8
    ssh_vm "docker logs --tail 20 pairs-stop-monitor"
    echo
    echo "  Expect: 'resumed: 0 open' then 'websocket connected'."
    echo "  'candidates ... old — the scanner is down' is CORRECT here; step 6"
    echo "  produces the first candidates."
}

step_6_firstscan() {
    bold "STEP 6 — first data download and scan"
    echo "  Pulls the freqtrade image (~1.4GB) and 30 days of 30m candles for"
    echo "  212 tickers, then runs one scan. Several minutes."
    echo
    echo "  30 days, not 60: min_bars_required is 671 bars = 14 days, so this"
    echo "  leaves a fortnight of slack. The laptop keeps two years because the"
    echo "  research needs it; the VM does not."
    confirm "Run the first cycle now?" || return 0
    ssh_vm "cd $REMOTE && bash scripts/vm_scan_cycle.sh" || warn "cycle returned non-zero — read the output above"
    ssh_vm "cd $REMOTE && python3 -c \"
import json
p = json.load(open('trading_data/scanner_candidates.json'))
print(p['n_candidates'], 'candidates,', len(p['candidates']), 'published, bar', p['bar_time'])
\"" || warn "no candidates file — the scan did not complete"
}

step_7_cron() {
    bold "STEP 7 — schedule the scanner and the daily housekeeping"
    # The monitor is NOT in cron. It is a long-lived service under
    # docker-compose.trading.yml with restart: unless-stopped, which is the
    # whole point of the split.
    if ! ssh_vm "crontab -l 2>/dev/null | grep -q vm_scan_cycle"; then
        ssh_vm "(crontab -l 2>/dev/null; echo '*/30 * * * * $REMOTE/scripts/vm_scan_cycle.sh >> $REMOTE/logs/cron.log 2>&1') | crontab -" \
            && ok "scanner scheduled every 30 min"
    else
        ok "scanner already scheduled"
    fi
    # Tick capture is ~20-25MB/day and Docker leaves dangling layers on every
    # rebuild. Those are the only two things here that can fill an 11GB margin.
    if ! ssh_vm "crontab -l 2>/dev/null | grep -q vm_housekeeping"; then
        ssh_vm "(crontab -l 2>/dev/null; echo '15 4 * * * $REMOTE/scripts/vm_housekeeping.sh >> $REMOTE/logs/cron.log 2>&1') | crontab -" \
            && ok "housekeeping scheduled daily at 04:15 UTC"
    else
        ok "housekeeping already scheduled"
    fi
    ssh_vm "crontab -l"
}

step_8_verify() {
    bold "STEP 8 — verify"
    echo
    echo "-- machine type (want $MACHINE) --"
    machine_type
    echo
    echo "-- disk (ticks retain 14d, scan history 90d, logs rotate at 32MB) --"
    ssh_vm "df -h / | tail -1; du -sh $REMOTE/trading_data 2>/dev/null || true"
    echo
    echo "-- memory under load --"
    ssh_vm "free -m | head -2; echo; docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}'"
    echo
    echo "-- heartbeat: want feed=live, blind=[], max_tick_age under a second --"
    ssh_vm "tail -3 $REMOTE/logs/stop_monitor_heartbeat.log 2>/dev/null || echo '  none yet'"
    echo
    echo "-- the book --"
    ssh_vm "tail -3 $REMOTE/logs/stop_monitor.log 2>/dev/null || echo '  none yet'"
    echo
    bold "From here"
    cat <<'TXT'
  scripts/check_vm.sh status       instance, containers, resources
  scripts/check_vm.sh heartbeat    feed state, tick ages, blind positions
  scripts/check_vm.sh logs         the monitor
  scripts/check_vm.sh scanner      the 30-minute cycles
  scripts/check_vm.sh overshoot    THE number, once stop-outs accumulate

  Baseline to beat: median overshoot 1.53x at 30-minute bar close, 0 of 9,704
  inside the level. Rows with blind_gap_seconds > 0 are excluded — those exits
  were not watched.

  Then close the laptop. That was the point.
TXT
}

# ---------------------------------------------------------------------------

case "${1:-all}" in
  status) step_status; exit 0 ;;
esac

# Written out rather than clever: macOS ships bash 3.2, where an empty array
# under `set -u` is an unbound-variable error.
if [ $# -eq 0 ] || [ "${1:-}" = "all" ]; then
  STEPS="1 2 3 4 5 6 7 8"
else
  STEPS="$*"
fi

for s in $STEPS; do
  case "$s" in
    1) step_1_resize ;;
    2) step_2_retire ;;
    3) step_3_push ;;
    4) step_4_dirs ;;
    5) step_5_build ;;
    6) step_6_firstscan ;;
    7) step_7_cron ;;
    8) step_8_verify ;;
    *) die "unknown step: $s (use 1-8, or 'status')" ;;
  esac
done
