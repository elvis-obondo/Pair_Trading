#!/bin/bash
# HL-VAULT1 step 2 watcher (memory: "every AWS launch gets a background watcher"). Run from the builder's
# OWN session (not on the instance) via: INSTANCE_ID=i-xxxx ./research/model/aws_vault_watcher.sh &
# Polls instance state every 60s and prints a line on every state change, so the session notices a stop
# (normal finalize() shutdown) or an unexpected termination without having to poll manually. Does not
# launch, modify or terminate anything -- read-only (ec2 describe-instances) the whole time.
set -euo pipefail
: "${INSTANCE_ID:?set INSTANCE_ID=i-xxxx before running}"
REGION="${REGION:-ap-northeast-1}"
AWS_BIN="${AWS_BIN:-aws}"

last_state=""
unknown_streak=0   # checker's fix (2026-11-11): one failed describe call is not a terminal state
echo "[VAULT-WATCHER] watching $INSTANCE_ID in $REGION, polling every 60s"
while true; do
  state=$("$AWS_BIN" ec2 describe-instances --instance-ids "$INSTANCE_ID" --region "$REGION" \
          --query 'Reservations[0].Instances[0].State.Name' --output text 2>/dev/null || echo "unknown")
  if [ "$state" = "unknown" ]; then
    unknown_streak=$((unknown_streak + 1))
    echo "[VAULT-WATCHER] $(date -u +%Y-%m-%dT%H:%M:%SZ) describe-instances failed ($unknown_streak of 5 allowed in a row)"
    if [ "$unknown_streak" -lt 5 ]; then sleep 60; continue; fi
  else
    unknown_streak=0
  fi
  if [ "$state" != "$last_state" ]; then
    echo "[VAULT-WATCHER] $(date -u +%Y-%m-%dT%H:%M:%SZ) state change: ${last_state:-<none>} -> $state"
    last_state="$state"
  fi
  if [ "$state" = "stopped" ] || [ "$state" = "terminated" ] || [ "$state" = "unknown" ]; then
    echo "[VAULT-WATCHER] instance reached terminal state '$state' -- pull logs from s3://pair-trading-hl-289869684922/s1_vault/logs/ and check vault-refit_${INSTANCE_ID}.log's exit_code line"
    # Checker's fix (round 2): an early failure (before AWS_BIN is ready inside the instance) never
    # reaches S3 at all -- aws ec2 get-console-output is the only record in that case. Fetched and saved
    # on every terminal state, not just when S3 comes up empty, so there's always a local copy.
    CONSOLE_OUT="$(dirname "$0")/logs/s1/vault_console_${INSTANCE_ID}.log"
    mkdir -p "$(dirname "$CONSOLE_OUT")"
    if "$AWS_BIN" ec2 get-console-output --instance-id "$INSTANCE_ID" --region "$REGION" \
          --output text > "$CONSOLE_OUT" 2>&1; then
      echo "[VAULT-WATCHER] console output saved: $CONSOLE_OUT"
    else
      echo "[VAULT-WATCHER] WARNING: could not fetch console output (may not be available yet/anymore)"
    fi
    break
  fi
  sleep 60
done
