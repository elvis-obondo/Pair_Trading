#!/bin/bash
# Quick status checks against the pairs-trading cloud VM (see
# docs/CLOUD_DEPLOY.md for the full deployment record). Wraps the repetitive
# gcloud --project/--zone flags into short subcommands.
#
#
# Usage:
#   scripts/check_vm.sh status      # is it running, last 20 log lines
#   scripts/check_vm.sh logs [N]    # last N log lines (default 50)
#   scripts/check_vm.sh follow      # live-tail the logs (Ctrl-C to stop)
#   scripts/check_vm.sh ledger [N]  # last N ledger rows (default 5)
#   scripts/check_vm.sh heartbeat [N]  # last N heartbeat lines (default 10)
#   scripts/check_vm.sh pull        # copy the live ledger CSV to
#                                    #   research/paper_trades_from_vm.csv
#   scripts/check_vm.sh ssh         # open an interactive shell on the VM
#   scripts/check_vm.sh switch TICKER_A TICKER_B [stats string...]
#                                    # rotate the live pair: checks for an
#                                    # open position first (asks before
#                                    # abandoning one), validates both
#                                    # tickers are futures in manifest.json,
#                                    # edits nautilus/run_trading.py locally,
#                                    # seeds the VM with full local bar
#                                    # history for the new pair (see
#                                    # docs/CLOUD_DEPLOY.md "MIN_BARS cold
#                                    # start gap" -- without this a fresh
#                                    # pair sits ~8 days before it has enough
#                                    # history to evaluate a signal), pushes
#                                    # the code, rebuilds+restarts the
#                                    # container, prints the startup log so
#                                    # you can confirm it came up clean.
#                                    # e.g.: scripts/check_vm.sh switch QTUM SUSHI \
#                                    #   "walk-forward selected as-of 2026-08-15, coint_stability=0.50"

set -euo pipefail

PROJECT="project-0671be06-e22a-44d8-83c"
ZONE="us-central1-a"
INSTANCE="pairs-trading"
REMOTE_DIR="~/Pair_Trading/trading_data"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

gssh() {
  gcloud compute ssh "$INSTANCE" --project="$PROJECT" --zone="$ZONE" --command="$1"
}

cmd="${1:-status}"
shift || true

case "$cmd" in
  status)
    gssh "docker ps && echo --- && docker logs --tail 20 pairs-trading"
    ;;
  logs)
    n="${1:-50}"
    gssh "docker logs --tail $n pairs-trading"
    ;;
  follow)
    echo "Live-tailing pairs-trading logs — Ctrl-C to stop."
    gcloud compute ssh "$INSTANCE" --project="$PROJECT" --zone="$ZONE" \
      --command="docker logs -f --tail 20 pairs-trading"
    ;;
  ledger)
    n="${1:-5}"
    gssh "tail -n $n $REMOTE_DIR/paper_trades.csv"
    ;;
  heartbeat)
    n="${1:-10}"
    gssh "tail -n $n $REMOTE_DIR/paper_trade_heartbeat.log"
    ;;
  pull)
    dest="$PROJECT_ROOT/research/paper_trades_from_vm.csv"
    gcloud compute scp "$INSTANCE:$REMOTE_DIR/paper_trades.csv" "$dest" \
      --project="$PROJECT" --zone="$ZONE"
    echo "Saved to $dest"
    ;;
  ssh)
    gcloud compute ssh "$INSTANCE" --project="$PROJECT" --zone="$ZONE"
    ;;
  switch)
    new_a="${1:-}"
    new_b="${2:-}"
    shift 2 || true
    stats="${*:-no stats recorded — edit LAST_SELECTED_STATS in nautilus/run_trading.py manually}"

    if [[ -z "$new_a" || -z "$new_b" ]]; then
      echo "Usage: $0 switch TICKER_A TICKER_B [stats string...]" >&2
      exit 1
    fi

    run_trading_file="$PROJECT_ROOT/nautilus/run_trading.py"

    echo "== 1/6: checking manifest.json for $new_a / $new_b =="
    python3 -c "
import json, sys
m = json.load(open('$PROJECT_ROOT/user_data/normalized/manifest.json'))
bad = [t for t in ('$new_a', '$new_b') if m.get(t, {}).get('instrument_type') != 'futures']
if bad:
    print(f'ERROR: not a futures instrument in manifest.json: {bad}', file=sys.stderr)
    sys.exit(1)
print('OK — both are futures instruments')
"

    echo "== 2/6: checking for an open position on the current pair =="
    # Must filter to the CURRENTLY-configured pair's rows specifically, not
    # just the ledger's last line -- if the current pair never opened a
    # trade, the file's last line is stale history from whatever pair was
    # live before it (bit us on the first real run: RLS/ZK never opened,
    # so the last line was still the old abandoned GALA/SAND row).
    cur_a="$(grep -m1 '^TICKER_A = ' "$run_trading_file" | sed -E 's/^TICKER_A = "(.*)"/\1/')"
    cur_b="$(grep -m1 '^TICKER_B = ' "$run_trading_file" | sed -E 's/^TICKER_B = "(.*)"/\1/')"
    cur_inst_a="${cur_a}-USDT-SWAP.OKX"
    last_row="$(gssh "grep ',${cur_inst_a},' $REMOTE_DIR/paper_trades.csv | tail -1 || true")"
    if [[ -z "$last_row" ]]; then
      echo "OK — current pair ($cur_a/$cur_b) has no trades in the ledger yet."
    else
      echo "$last_row"
      if [[ "$(echo "$last_row" | cut -d',' -f2)" == "open" ]]; then
        echo
        echo "WARNING: the row above is an 'open' with no matching close for the" \
             "CURRENT pair ($cur_a/$cur_b) — there is a live position. Switching" \
             "abandons it (frozen, never resolves)."
        read -r -p "Continue anyway? [y/N] " confirm
        if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
          echo "Aborted — no changes made."
          exit 1
        fi
      else
        echo "OK — current pair's last row is a 'close', nothing open."
      fi
    fi

    echo "== 3/6: editing nautilus/run_trading.py locally =="
    today="$(date +%F)"
    sed -i '' \
      -e "s/^TICKER_A = .*/TICKER_A = \"$new_a\"/" \
      -e "s/^TICKER_B = .*/TICKER_B = \"$new_b\"/" \
      -e "s/^LAST_SELECTED_DATE = .*/LAST_SELECTED_DATE = \"$today\"/" \
      "$run_trading_file"
    sed -i '' \
      -e "s|^LAST_SELECTED_STATS = .*|LAST_SELECTED_STATS = \"$stats\"|" \
      "$run_trading_file"
    grep -n "^TICKER_A\|^TICKER_B\|^LAST_SELECTED" "$run_trading_file"

    echo "== 4/6: seeding full local bar history for $new_a / $new_b on the VM =="
    # Without this, DataObserver falls back to an OKX historical backfill
    # that caps at 300 candles (no pagination), leaving the new pair ~420
    # bars short of MIN_BARS=720 -- it would then sit for ~8 days
    # accumulating the rest one bar at a time before evaluating any signal.
    # See docs/CLOUD_DEPLOY.md "MIN_BARS cold start gap" for the full story.
    merge_tmpdir="$(mktemp -d)"
    for t in "$new_a" "$new_b"; do
      canonical="$PROJECT_ROOT/user_data/data/okx/futures/${t}_USDT_USDT-30m-futures.feather"
      vm_pulled="$merge_tmpdir/${t}_vm_existing.feather"
      gcloud compute scp "$INSTANCE:$REMOTE_DIR/paper_live/${t}_USDT_USDT-30m-paper.feather" \
        "$vm_pulled" --project="$PROJECT" --zone="$ZONE" 2>/dev/null || true
      [[ -f "$vm_pulled" ]] || vm_pulled=""

      merged="$merge_tmpdir/${t}_merged.feather"
      if python3 "$PROJECT_ROOT/scripts/merge_bar_history.py" "$t" "$canonical" "$vm_pulled" "$merged"; then
        gcloud compute scp "$merged" "$INSTANCE:~/${t}_merged.feather" \
          --project="$PROJECT" --zone="$ZONE"
        gssh "sudo mv ~/${t}_merged.feather $REMOTE_DIR/paper_live/${t}_USDT_USDT-30m-paper.feather && \
              sudo chown \$(id -u):\$(id -g) $REMOTE_DIR/paper_live/${t}_USDT_USDT-30m-paper.feather"
      fi
    done
    rm -rf "$merge_tmpdir"

    echo "== 5/6: pushing code to the VM and rebuilding =="
    gcloud compute scp "$run_trading_file" "$INSTANCE:~/Pair_Trading/nautilus/run_trading.py" \
      --project="$PROJECT" --zone="$ZONE"
    gssh "cd ~/Pair_Trading && docker compose -f docker-compose.trading.yml up -d --build"

    echo "== 6/6: startup log — confirm 'no unresolved open position' and a bar count near/above 720 =="
    sleep 5
    gssh "docker logs --tail 30 pairs-trading" | grep -i "Seeded\|PairsTradingActor\|ERROR\|Traceback" || true
    ;;
  *)
    echo "Unknown subcommand: $cmd" >&2
    echo "Usage: $0 {status|logs [N]|follow|ledger [N]|heartbeat [N]|pull|ssh|switch TICKER_A TICKER_B [stats...]}" >&2
    exit 1
    ;;
esac
