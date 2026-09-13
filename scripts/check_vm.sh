#!/bin/bash
# Status checks against the pairs-trading cloud VM. Wraps the repetitive
# gcloud --project/--zone flags into short subcommands.
#
# WHAT RUNS THERE NOW. Two things, and the split is the point:
#   stop-monitor   long-lived. Watches every open position's stop over a
#                  websocket and closes it within about a second of the level
#                  being crossed. Owns the book -- it is the only writer of
#                  scanner_trades.csv and scanner_state.json.
#   scanner        single-shot, cron every 30 minutes via vm_scan_cycle.sh.
#                  Screens 22,366 pairs and publishes candidates. Touches no
#                  state.
#
# This replaced a single-pair nautilus process on 2026-09-12. That one checked
# its stop at 30-minute bar closes, which is the thing that was costing the
# edge -- see research/stop_monitor.py.
#
# Usage:
#   scripts/check_vm.sh status         # instance, containers, resources
#   scripts/check_vm.sh logs [N]       # last N stop-monitor log lines (50)
#   scripts/check_vm.sh follow         # live-tail the monitor (Ctrl-C to stop)
#   scripts/check_vm.sh scanner [N]    # last N scanner cycle lines (50)
#   scripts/check_vm.sh heartbeat [N]  # feed state, tick ages, blind positions
#   scripts/check_vm.sh positions      # open positions, marked live, P&L and exposure
#   scripts/check_vm.sh ledger [N]     # last N ledger rows (5)
#   scripts/check_vm.sh overshoot      # THE number: how far past the stop fills land
#   scripts/check_vm.sh pull           # copy ledger + scan history down
#   scripts/check_vm.sh deploy         # build here, push to the registry, VM pulls
#   scripts/check_vm.sh ssh            # interactive shell
#   scripts/check_vm.sh positions      # check the live positions


set -euo pipefail

PROJECT="project-0671be06-e22a-44d8-83c"
ZONE="us-central1-a"
INSTANCE="pairs-trading"
REMOTE="~/Pair_Trading"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

run() { gcloud compute ssh "$INSTANCE" --project="$PROJECT" --zone="$ZONE" --command="$1"; }

cmd="${1:-status}"
shift || true

case "$cmd" in
  status)
    gcloud compute instances list --project="$PROJECT" --filter="name=$INSTANCE"
    echo
    run "free -m; echo; df -h / | tail -1; echo; docker ps --format 'table {{.Names}}\t{{.Status}}'; echo; docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}'"
    ;;

  logs)
    run "tail -${1:-50} $REMOTE/logs/stop_monitor.log"
    ;;

  follow)
    run "tail -f $REMOTE/logs/stop_monitor.log"
    ;;

  scanner)
    run "tail -${1:-50} $REMOTE/logs/scanner.log"
    ;;

  heartbeat)
    # feed=live is what you want. rest_fallback means the socket is down and the
    # stop is degraded; a non-empty blind=[] means positions are unwatched.
    run "tail -${1:-10} $REMOTE/logs/stop_monitor_heartbeat.log"
    ;;

  ledger)
    # The ledger is empty until the first position opens, and an empty file
    # printed silently looks identical to a broken command.
    run "f=$REMOTE/trading_data/scanner_trades.csv
         if [ ! -s \$f ]; then
           echo '  ledger is empty — no positions have opened yet'
           echo '  the monitor opens on the first candidates file it sees'
         else
           head -1 \$f; tail -${1:-5} \$f
         fi"
    ;;

  overshoot)
    # The whole reason the monitor exists. Baseline from 9,704 backtested
    # stop-outs at 30-minute bar close: median 1.53x, mean 2.07x, NONE inside
    # the level. Rows with a feed outage are excluded -- they were not watched.
    run "docker exec pairs-stop-monitor python3 -c \"
import pandas as pd, os
p = '/app/trading_data/scanner_trades.csv'
if not os.path.exists(p) or os.path.getsize(p) == 0:
    raise SystemExit('  ledger is empty — no positions have closed yet')
d = pd.read_csv(p)
c = d[(d.event=='close') & (d.exit_reason=='adverse_move')]
c = c[c.blind_gap_seconds.fillna(0) == 0]
if not len(c):
    print('no watched stop-outs yet')
else:
    o = c.overshoot_ratio
    print(f'{len(c)} watched stop-outs')
    print(f'  median {o.median():.3f}x   mean {o.mean():.3f}x   p90 {o.quantile(0.9):.3f}x')
    print(f'  inside the level: {(o <= 1.0).sum()} of {len(c)}')
    print(f'  baseline at 30-min bar close: median 1.53x, mean 2.07x, 0 inside')
\""
    ;;

  positions)
    # Marked to the monitor's OWN quotes, not a fresh fetch -- a status view
    # that prices itself can disagree with the process holding the book.
    gcloud compute scp "$PROJECT_ROOT/scripts/render_positions.py" \
      "$INSTANCE:/tmp/render_positions.py" --project="$PROJECT" --zone="$ZONE" -q >/dev/null
    run "docker cp /tmp/render_positions.py pairs-stop-monitor:/tmp/ >/dev/null && \
         docker exec pairs-stop-monitor python /tmp/render_positions.py"
    ;;

  pull)
    mkdir -p "$PROJECT_ROOT/research/from_vm"
    gcloud compute scp "$INSTANCE:$REMOTE/trading_data/scanner_trades.csv" \
      "$PROJECT_ROOT/research/from_vm/" --project="$PROJECT" --zone="$ZONE"
    gcloud compute scp --recurse "$INSTANCE:$REMOTE/trading_data/scan_history" \
      "$PROJECT_ROOT/research/from_vm/" --project="$PROJECT" --zone="$ZONE" || true
    echo "-> research/from_vm/"
    ;;

  deploy)
    # Deploying means building on the laptop and pushing to Artifact Registry.
    # The VM never builds. See scripts/release.sh.
    exec "$PROJECT_ROOT/scripts/release.sh"
    ;;

  ssh)
    gcloud compute ssh "$INSTANCE" --project="$PROJECT" --zone="$ZONE"
    ;;

  *)
    sed -n '19,30p' "${BASH_SOURCE[0]}"
    exit 1
    ;;
esac
