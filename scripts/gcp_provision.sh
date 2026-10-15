#!/bin/bash
# One-time setup ON the pt-research machine (Ubuntu 22.04). Run by
# `scripts/gcp_run.sh provision` after the first code sync. Idempotent.
#   - Python 3.12.2 (the laptop's version) via uv, venv at ~/Pair_Trading/.venv
#     from requirements-research.txt (torch from the CPU wheel index)
#   - awscli for the read-only S3 pulls (credentials put in ~/.aws by gcp_run.sh)
#   - the idle auto-stop: /usr/local/bin/pt-idle-stop every 5 min from root's
#     cron, plus a boot-time reset of its idle clock
set -euo pipefail
cd ~/Pair_Trading
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq rsync zstd lz4 awscli >/dev/null
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv python install 3.12.2
[ -x .venv/bin/python ] || uv venv --python 3.12.2 .venv
grep -v -E '^#|^torch==' requirements-research.txt > /tmp/req.txt
VIRTUAL_ENV=$PWD/.venv uv pip install -q -r /tmp/req.txt
VIRTUAL_ENV=$PWD/.venv uv pip install -q "$(grep '^torch==' requirements-research.txt)" --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python --version
sudo install -m 755 scripts/gcp_idle_stop.sh /usr/local/bin/pt-idle-stop
sudo tee /etc/cron.d/pt-idle >/dev/null <<EOF
SHELL=/bin/bash
PT_USER=$USER
*/5 * * * * root /usr/local/bin/pt-idle-stop
@reboot root rm -f /var/lib/pt-idle/since; echo "\$(date -u +\%FT\%TZ) BOOT idle clock reset" >> /var/log/pt-idle.log
EOF
sudo chmod 644 /etc/cron.d/pt-idle
echo "provisioned: $(.venv/bin/python --version), idle-stop installed"
