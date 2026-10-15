#!/bin/bash
# Idle auto-stop for the pt-research GCE machine. Installed by gcp_provision.sh
# as /usr/local/bin/pt-idle-stop and run by root's cron every 5 minutes.
#
# BUSY  = any process running from the research venv (~/Pair_Trading/.venv:
#         VIRTUAL_ENV in its environment, or the venv python as argv[0]), or the
#         1-minute load average >= 0.5.
# IDLE  = neither. The first idle check writes its time to $STATE; when idle has
#         lasted >= 30 minutes the machine runs `shutdown -h now`, which on GCE
#         STOPS the instance (TERMINATED state, disk kept, no compute billing).
#         Any busy check clears $STATE.
# Every decision is one line in /var/log/pt-idle.log.
set -u
VENV=/home/${PT_USER:-elvisobondo}/Pair_Trading/.venv
VENV_PY=$VENV/bin/python
STATE=/var/lib/pt-idle/since
LOG=/var/log/pt-idle.log
IDLE_MIN=30
mkdir -p "$(dirname "$STATE")"
now=$(date -u +%s)
load=$(cut -d' ' -f1 /proc/loadavg)
# a process "runs from the research venv" when its environment carries
# VIRTUAL_ENV=<venv> (set by activate, and by gcp_run.sh for every command), or
# its argv[0] is the venv's python. Root can read every /proc/PID/environ.
procs=0
for e in /proc/[0-9]*/environ; do
  pid=${e#/proc/}; pid=${pid%/environ}
  [ "$pid" = "$$" ] && continue
  if tr '\0' '\n' < "$e" 2>/dev/null | grep -qx "VIRTUAL_ENV=$VENV"; then procs=$((procs+1)); continue; fi
  a0=$(tr '\0' '\n' < /proc/$pid/cmdline 2>/dev/null | head -1)
  [ "$a0" = "$VENV_PY" ] && procs=$((procs+1))
done
busy_load=$(awk -v l="$load" 'BEGIN{print (l >= 0.5) ? 1 : 0}')
stamp=$(date -u +%FT%TZ)
if [ "$procs" -gt 0 ] || [ "$busy_load" -eq 1 ]; then
  rm -f "$STATE"
  echo "$stamp BUSY venv_procs=$procs load1=$load" >> "$LOG"
  exit 0
fi
if [ ! -f "$STATE" ]; then
  echo "$now" > "$STATE"
  echo "$stamp IDLE-START venv_procs=0 load1=$load" >> "$LOG"
  exit 0
fi
since=$(cat "$STATE"); idle=$(( (now - since) / 60 ))
if [ "$idle" -ge "$IDLE_MIN" ]; then
  echo "$stamp STOP idle ${idle}min venv_procs=0 load1=$load -> shutdown -h now" >> "$LOG"
  rm -f "$STATE"
  /sbin/shutdown -h now
else
  echo "$stamp IDLE ${idle}min venv_procs=0 load1=$load" >> "$LOG"
fi
