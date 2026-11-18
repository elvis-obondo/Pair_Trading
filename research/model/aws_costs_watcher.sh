#!/bin/bash
# COSTS1 watcher (standing rule: every AWS launch gets a background watcher). Read-only: ec2 describe-instances every 60 s from the builder's session; prints a line on each state change
# and on a terminal state. Does not launch, modify or terminate anything.
#   INSTANCE_ID=i-xxxx [REGION=ap-northeast-1] [RESULTS=costs1/g8] research/model/aws_costs_watcher.sh &
#   the Tokyo G8 job used the defaults; the 20-file validation uses REGION=us-east-2 RESULTS=costs1/l2test
set -uo pipefail
: "${INSTANCE_ID:?set INSTANCE_ID=i-xxxx}"
REGION="${REGION:-ap-northeast-1}"
RESULTS="${RESULTS:-costs1/g8}"            # prefix under s3://pair-trading-hl-<acct>/ named in the terminal message
AWS_BIN="${AWS_BIN:-$HOME/.local/bin/aws}"
last=""; unknown=0; START=$(date +%s)
echo "[COSTS-WATCHER] watching $INSTANCE_ID in $REGION every 60s"
while true; do
  st=$("$AWS_BIN" ec2 describe-instances --instance-ids "$INSTANCE_ID" --region "$REGION" --query 'Reservations[0].Instances[0].State.Name' --output text 2>/dev/null || echo unknown)
  [ "$st" = None ] && st=unknown        # an empty reservation is treated like a failed describe
  if [ $(( $(date +%s) - START )) -gt 5400 ]; then echo "[COSTS-WATCHER] $(date -u +%FT%TZ) 90-minute cap reached, last state '${last:-none}'; the instance's own shutdown timer is 30 to 40 minutes. Check it by hand."; exit 0; fi
  if [ "$st" = unknown ]; then unknown=$((unknown+1)); echo "[COSTS-WATCHER] $(date -u +%FT%TZ) describe failed ($unknown of 5)"; [ "$unknown" -lt 5 ] && { sleep 60; continue; }; else unknown=0; fi
  if [ "$st" != "$last" ]; then echo "[COSTS-WATCHER] $(date -u +%FT%TZ) state: ${last:-none} -> $st"; last=$st; fi
  if [ "$st" = stopped ] || [ "$st" = terminated ] || [ "$st" = unknown ]; then echo "[COSTS-WATCHER] terminal state '$st': results under s3://pair-trading-hl-289869684922/$RESULTS/ (ec2.log and the job's outputs)"; exit 0; fi
  sleep 60
done
