#!/usr/bin/env bash
# Move the live paper system to the VM: resize, deploy, start, schedule.
#
# RUN THIS YOURSELF, IN YOUR OWN TERMINAL. It resizes a running instance off the
# free tier and stops a process that has been up three weeks. Each destructive
# step asks first, and every step is idempotent, so a Ctrl-C and a re-run costs
# nothing.
#
#   scripts/vm_migrate.sh              # MICRO mode (default) — free tier
#   scripts/vm_migrate.sh full         # FULL mode — resize, everything on the VM
#   scripts/vm_migrate.sh status       # what is true right now
#   scripts/vm_migrate.sh micro build  # one named step
#
# TWO MODES.
#
#   MICRO (default, free). The stop monitor runs on the existing e2-micro; the
#   scanner stays on the laptop and ships its candidates over. Costs nothing and
#   tests the thing that actually needs testing -- the monitor runs 24/7 and
#   every open position's stop is watched whether the laptop is up or not.
#   The trade: while the laptop sleeps no new candidates arrive, so nothing new
#   OPENS. Positions already open keep being watched. The monitor's 60-minute
#   staleness guard handles it with no configuration.
#
#   FULL (~$25/month). Resizes to e2-medium and runs both halves on the VM, so
#   entries continue with the laptop closed. Do this once micro has shown the
#   strategy and the code hold up.
#
# WHY MICRO FITS. Measured 2026-09-12: the monitor is 174MB RSS. The VM has
# 958MB, of which the retired nautilus container was holding 255MB -- removing
# it (step `retire`) frees more than the monitor needs. What does NOT fit is the
# scanner: 531MB peak plus a freqtrade download. That is why it stays local.
#
# Step `swap` adds 2GB of swap regardless of mode. It no longer protects a build
# -- the VM does not build anything, see step `build` -- but it turns a transient
# memory spike into slowness rather than a dead monitor, and an unwatched stop is
# the failure this whole system exists to prevent.
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

# stdin from /dev/null: gcloud compute ssh reads stdin, so an ssh call sitting
# just before a confirm() would swallow the answer the user already typed -- and
# silently "skip" a step they meant to run.
ssh_vm() { gcloud compute ssh "$INSTANCE" $G --command="$1" < /dev/null; }
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

step_swap() {
    bold "STEP swap — 2GB swapfile"
    if ssh_vm "swapon --show | grep -q /swapfile" 2>/dev/null; then
        ok "already present"
        ssh_vm "free -m | tail -1"
        return 0
    fi
    # A 1GB instance with no swap OOM-kills the image build partway through pip.
    # Worth having on e2-medium too: it turns a transient spike into slowness
    # rather than a dead monitor, and an unwatched stop is the failure this whole
    # system exists to prevent.
    ssh_vm "sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile >/dev/null && sudo swapon /swapfile && grep -q /swapfile /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null" \
        && ok "2GB swap on, and persisted in /etc/fstab"
    ssh_vm "free -m"
}

step_resize() {
    bold "STEP resize — resize to $MACHINE"
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

step_retire() {
    bold "STEP retire — retire the old container"
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

step_push() {
    bold "STEP push — push source"
    # Source only. trading_data/ on the VM is the book and is never overwritten.
    ssh_vm "mkdir -p $REMOTE/user_data" || die "mkdir failed"

    # SOURCE ONLY. `scp --recurse research/` would ship exit_sweep_paths.parquet
    # (342MB) and the rest of the research artifacts -- 442MB the VM has no use
    # for, over scp, onto an 11GB margin. Tar just the .py files instead: one
    # stream, a few hundred KB, and no chance of dragging data along.
    echo "  research/*.py ..."
    tar -C "$ROOT" -czf - research/*.py research/adapters/*.py \
        | gcloud compute ssh "$INSTANCE" $G --command="rm -f $REMOTE/research/*.py && tar -C $REMOTE -xzf -" \
        || die "research push failed"
    echo "  scripts/ ..."
    tar -C "$ROOT" -czf - scripts \
        | gcloud compute ssh "$INSTANCE" $G --command="tar -C $REMOTE -xzf - && chmod +x $REMOTE/scripts/*.sh" \
        || die "scripts push failed"
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

step_dirs() {
    bold "STEP dirs — one-time runtime directories"
    # Docker bind-mounts a missing FILE path as an empty DIRECTORY rather than
    # erroring. Pre-creating the ledger as a real file avoids that footgun; the
    # rest are genuinely directories.
    ssh_vm "cd $REMOTE && mkdir -p trading_data/scan_history trading_data/monitor_ticks logs user_data/data && touch trading_data/scanner_trades.csv && ls -la trading_data/" \
        && ok "created"
}

step_build() {
    bold "STEP build — authorise the registry and pull the image"
    # The VM does not build. Images are built on the laptop for linux/amd64 and
    # pushed to Artifact Registry; building here cost 4.6GB of build cache
    # against 8GB free, seven minutes of pip on 2 shared vCPU, and OOM risk on
    # the one machine whose job is to never miss a stop.
    #
    # Run scripts/release.sh --build first if the image is not in the registry.
    ssh_vm "gcloud auth configure-docker us-central1-docker.pkg.dev --quiet" \
        && ok "registry authorised"
    ssh_vm "cd $REMOTE && docker compose -f docker-compose.trading.yml pull stop-monitor && docker compose -f docker-compose.trading.yml up -d stop-monitor" \
        || die "pull/start failed — is the image pushed? scripts/release.sh --build"
    echo "  waiting for first log lines..."
    sleep 8
    ssh_vm "docker ps --format '{{.Names}} | {{.Image}} | {{.Status}}'; echo; tail -15 $REMOTE/logs/stop_monitor.log 2>/dev/null || echo '  no log yet'"
    echo
    echo "  Expect: 'resumed: 0 open' then 'websocket connected'."
}

step_firstscan() {
    bold "STEP firstscan — first data download and scan"
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

step_cron() {
    bold "STEP cron — schedule what runs on the VM"
    # The monitor is NOT in cron. It is a long-lived service under
    # docker-compose.trading.yml with restart: unless-stopped, which is the
    # whole point of the split.
    if [ "$MODE" = "full" ]; then
        if ! ssh_vm "crontab -l 2>/dev/null | grep -q vm_scan_cycle"; then
            ssh_vm "(crontab -l 2>/dev/null; echo '*/30 * * * * $REMOTE/scripts/vm_scan_cycle.sh >> $REMOTE/logs/cron.log 2>&1') | crontab -" \
                && ok "scanner scheduled every 30 min"
        else
            ok "scanner already scheduled"
        fi
    else
        # In micro mode the scanner runs on the laptop; scheduling it here would
        # try a 531MB scan plus a freqtrade download on a 1GB box.
        if ssh_vm "crontab -l 2>/dev/null | grep -q vm_scan_cycle"; then
            warn "a scanner cron exists but this is MICRO mode — removing it"
            ssh_vm "crontab -l | grep -v vm_scan_cycle | crontab -"
        fi
        ok "scanner stays on the laptop (micro mode)"
    fi
    # Tick capture is ~18.5MB/day measured, and Docker leaves dangling layers on
    # every rebuild. Those are the only two things here that can fill the disk.
    if ! ssh_vm "crontab -l 2>/dev/null | grep -q vm_housekeeping"; then
        ssh_vm "(crontab -l 2>/dev/null; echo '15 4 * * * $REMOTE/scripts/vm_housekeeping.sh >> $REMOTE/logs/cron.log 2>&1') | crontab -" \
            && ok "housekeeping scheduled daily at 04:15 UTC"
    else
        ok "housekeeping already scheduled"
    fi
    ssh_vm "crontab -l"
}

step_laptop() {
    bold "STEP laptop — turn on the candidate push from here"
    # Opt-in by sentinel rather than an env var, because the LaunchAgent would
    # otherwise need a plist edit to carry one.
    if [ -f "$ROOT/.push_to_vm" ]; then
        ok ".push_to_vm already present"
    else
        touch "$ROOT/.push_to_vm" && ok "created .push_to_vm — run_scanner.sh now ships candidates"
    fi
    echo
    echo "  Test it now:"
    echo "    scripts/push_candidates.sh"
    echo
    echo "  Schedule the scanner here if it is not already:"
    echo "    cp scripts/com.pairtrading.scanner.plist ~/Library/LaunchAgents/"
    echo "    launchctl bootstrap gui/\$(id -u) ~/Library/LaunchAgents/com.pairtrading.scanner.plist"
    echo
    echo "  To stop pushing:  rm .push_to_vm"
}

step_verify() {
    bold "STEP verify"
    echo
    echo "-- machine type --"
    machine_type
    echo
    echo "-- disk (ticks retain 14d, scan history 90d, logs rotate at 32MB) --"
    ssh_vm "df -h / | tail -1; du -sh $REMOTE/trading_data 2>/dev/null || true"
    echo
    echo "-- memory (monitor measured at 174MB) --"
    ssh_vm "free -m | head -3; echo; docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}'"
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
  scripts/check_vm.sh overshoot    THE number, once stop-outs accumulate

  Baseline to beat: median overshoot 1.53x at 30-minute bar close, 0 of 9,704
  inside the level. Rows with blind_gap_seconds > 0 are excluded — those exits
  were not watched.
TXT
    if [ "$MODE" = "micro" ]; then
        cat <<'TXT'

  MICRO mode, so be clear about what is and is not being tested:
    tested      the stop, 24/7, on every position that is open
    not tested  entries while the laptop is asleep — none happen then
    costs       nothing

  Move to full when the monitor has been stable for a week or two and the
  overshoot number says whether it worked:  scripts/vm_migrate.sh full
TXT
    fi
}

# ---------------------------------------------------------------------------

MODE="micro"
case "${1:-}" in
  status) step_status; exit 0 ;;
  micro)  MODE="micro"; shift ;;
  full)   MODE="full";  shift ;;
esac

# Written out rather than clever: macOS ships bash 3.2, where an empty array
# under `set -u` is an unbound-variable error.
if [ $# -eq 0 ]; then
  if [ "$MODE" = "full" ]; then
    STEPS="swap resize retire push dirs build firstscan cron verify"
  else
    STEPS="swap retire push dirs build cron laptop verify"
  fi
else
  STEPS="$*"
fi

bold "MODE: $MODE"
if [ "$MODE" = "micro" ]; then
  echo "  monitor on the e2-micro (free), scanner stays on this laptop"
else
  echo "  both halves on the VM, resized to $MACHINE (~\$25/month)"
fi
echo "  steps: $STEPS"

for s in $STEPS; do
  case "$s" in
    swap)      step_swap ;;
    resize)    step_resize ;;
    retire)    step_retire ;;
    push)      step_push ;;
    dirs)      step_dirs ;;
    build)     step_build ;;
    firstscan) step_firstscan ;;
    cron)      step_cron ;;
    laptop)    step_laptop ;;
    verify)    step_verify ;;
    *) die "unknown step: $s (swap resize retire push dirs build firstscan cron laptop verify, or 'status')" ;;
  esac
done
