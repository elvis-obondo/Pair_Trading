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
#   scripts/check_vm.sh oi             # copy new open-interest days down, merge, report gaps
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

  oi)
    # Open interest, collected on the VM every 5 minutes by collect_oi.py and
    # pulled down here. It is collected forward rather than downloaded because
    # OKX keeps no usable archive -- see the header of scripts/collect_oi.py.
    #
    # Pull is by MISSING DAY, not by date range, so a week offline self-heals on
    # the next run. Today's file is always re-pulled because it is still growing.
    # Lands in research/datasets/ (gitignored) -- at 13.5MB/day raw this must
    # never go near git.
    OI_LOCAL="$PROJECT_ROOT/research/datasets/oi"
    mkdir -p "$OI_LOCAL"
    today="$(date -u +%F)"
    remote_days="$(run "ls -1 $REMOTE/trading_data/oi/ 2>/dev/null" | tr -d '\r' \
                   | grep -E '^[0-9-]+\.csv(\.gz)?$' || true)"
    if [ -z "$remote_days" ]; then echo "no open-interest files on the VM yet"; exit 0; fi

    want=""
    for f in $remote_days; do
        day="${f%%.*}"
        # Re-pull today, which is still growing. Otherwise pull only what we lack
        # in EITHER form, since VM housekeeping gzips yesterday's file in place.
        if [ "$day" = "$today" ] \
           || { [ ! -f "$OI_LOCAL/$day.csv" ] && [ ! -f "$OI_LOCAL/$day.csv.gz" ]; }; then
            want="$want $f"
        fi
    done
    if [ -z "${want// /}" ]; then
        echo "nothing new -- $(ls -1 "$OI_LOCAL" | wc -l | tr -d ' ') day file(s) already local"
    else
        for f in $want; do
            gcloud compute scp "$INSTANCE:$REMOTE/trading_data/oi/$f" "$OI_LOCAL/" \
              --project="$PROJECT" --zone="$ZONE" -q
        done
        echo "pulled:$want"
        # A day that arrives gzipped supersedes any plain copy we still hold.
        for f in $want; do
            case "$f" in *.gz) rm -f "$OI_LOCAL/${f%.gz}";; esac
        done
    fi

    python3 - "$OI_LOCAL" <<'OIMERGE'
import glob, os, sys
import pandas as pd

d = sys.argv[1]
files = sorted(glob.glob(os.path.join(d, "*.csv")) + glob.glob(os.path.join(d, "*.csv.gz")))
if not files:
    print("no local day files"); raise SystemExit(0)

frames = []
for f in files:
    x = pd.read_csv(f)
    x["poll_ts"] = pd.to_datetime(x.poll_ts, utc=True, format="ISO8601")
    frames.append(x)
oi = pd.concat(frames, ignore_index=True)
# A re-pulled growing file alongside an earlier partial copy duplicates rows.
oi = oi.drop_duplicates(["poll_ts", "inst_id"]).sort_values(["poll_ts", "inst_id"])

out = os.path.join(os.path.dirname(d), "open_interest.feather")
oi.reset_index(drop=True).to_feather(out)

polls = oi.poll_ts.drop_duplicates().sort_values().reset_index(drop=True)
print(f"\n{len(oi):,} rows  {oi.inst_id.nunique()} instruments  "
      f"{len(polls):,} polls  {polls.min()} -> {polls.max()}")
print(f"-> {os.path.relpath(out)}  ({os.path.getsize(out)/1e6:.1f}MB)")

# GAPS MUST BE LOUD. A VM outage leaves holes in a series whose whole value is
# that it is continuous, and a silent merge would hide them.
PER_HOUR = 12  # the 5-minute grid
now = pd.Timestamp.now(tz="UTC")
per_day = polls.dt.date.value_counts().sort_index()
for day, n in per_day.items():
    # Today is still in progress, so expect only the polls that could have run.
    # A fixed 288 would scream on every pull and train us to ignore the one
    # time it means something.
    if day == now.date():
        expect = max(1, int((now - now.normalize()).total_seconds() // 300))
        label = f"{expect} so far"
    else:
        expect = 24 * PER_HOUR
        label = str(expect)
    flag = "" if n >= expect - 2 else f"   <-- {expect - n} MISSING"
    print(f"  {day}  {n:3d}/{label} polls{flag}")
gaps = polls.diff()
gaps = gaps[gaps > pd.Timedelta(minutes=11)]
if len(gaps):
    print(f"\n{len(gaps)} gap(s) longer than two polls:")
    for i, g in gaps.items():
        print(f"  {g} ending {polls[i]}")
OIMERGE
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
    sed -n '19,31p' "${BASH_SOURCE[0]}"
    exit 1
    ;;
esac
