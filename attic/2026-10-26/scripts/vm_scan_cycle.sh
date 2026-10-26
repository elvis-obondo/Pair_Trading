#!/usr/bin/env bash
# One scanner cycle on the VM. The cron equivalent of the laptop's LaunchAgent.
#
#   */30 * * * * /home/elvisobondo/Pair_Trading/scripts/vm_scan_cycle.sh >> /home/elvisobondo/Pair_Trading/logs/cron.log 2>&1
#
# TWO STEPS, DELIBERATELY. The download runs in the freqtrade container and the
# scan runs in the pairs-trading container, driven from the host. Doing the
# download from inside the scanner container would mean handing it the host
# Docker socket, which is not a trade worth making for a cron line.
#
# The stop monitor is NOT here. It is a long-lived service under
# docker-compose.trading.yml and stays up between these cycles — that is the
# whole point of the split.
#
# Only 30 days of 30m candles are pulled. min_bars_required is 671 bars = 14
# days, so 30 leaves a fortnight of slack. The laptop keeps two years because
# the research needs it; the VM does not, and that difference is most of why
# this fits on a small instance.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) scan cycle start ==="

docker compose run --rm freqtrade download-data \
    --config user_data/config.json --exchange okx \
    --trading-mode futures --timeframes 30m --days 30

docker compose -f docker-compose.trading.yml run --rm scanner

echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) scan cycle done ==="
