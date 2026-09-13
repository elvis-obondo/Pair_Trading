#!/usr/bin/env bash
# Build the image here, push it to Artifact Registry, tell the VM to pull it.
#
# THE VM NEVER BUILDS. It has 2 shared vCPU and 1GB of RAM and one job: watch
# every open position's stop without missing one. Building there cost 4.6GB of
# build cache against 8GB free, seven minutes of pip, and OOM risk on exactly
# the wrong machine.
#
#   scripts/release.sh            build, push, deploy, verify
#   scripts/release.sh --build    build and push only
#   scripts/release.sh --deploy   deploy the image already in the registry
#
# CROSS-BUILD. This Mac is arm64 and the VM is x86_64, so --platform
# linux/amd64 is not optional -- a native build produces an image the VM cannot
# run. It builds under emulation, which is still faster than the e2-micro.
#
# SOURCE-ONLY CHANGES DO NOT NEED THIS. The .py files are baked into the image,
# so a code change does mean a rebuild -- but the pip layer is cached, so it is
# the fast kind. Only a requirements.txt change pays the full cost.
set -euo pipefail
cd "$(dirname "$0")/.."

PROJECT="project-0671be06-e22a-44d8-83c"
ZONE="us-central1-a"
INSTANCE="pairs-trading"
REGION="us-central1"
IMG="$REGION-docker.pkg.dev/$PROJECT/pairs-trading/stop-monitor"
REMOTE="/home/elvisobondo/Pair_Trading"
G="--project=$PROJECT --zone=$ZONE"

bold() { printf "\n\033[1m%s\033[0m\n" "$*"; }
ssh_vm() { gcloud compute ssh "$INSTANCE" $G --command="$1" < /dev/null; }

MODE="${1:-all}"
SHA="$(git rev-parse --short HEAD)"
DIRTY=""
git diff --quiet || DIRTY="-dirty"

if [ "$MODE" = "all" ] || [ "$MODE" = "--build" ]; then
    bold "Build $IMG:$SHA$DIRTY (linux/amd64)"
    # Tagged with the commit as well as :latest, so `docker images` on the VM
    # answers "which code is actually running" without guessing.
    docker buildx build --platform linux/amd64 -f Dockerfile.trading \
        -t "$IMG:latest" -t "$IMG:$SHA$DIRTY" --push .
    echo "  pushed $SHA$DIRTY"
fi

if [ "$MODE" = "all" ] || [ "$MODE" = "--deploy" ]; then
    bold "Deploy to $INSTANCE"
    # Source that lives outside the image: the compose file and the host scripts.
    gcloud compute scp docker-compose.trading.yml "$INSTANCE:$REMOTE/" $G --quiet
    # COPYFILE_DISABLE: macOS tars an xattr per file, and GNU tar on the VM
    # prints a warning for each one -- 18 lines of noise per deploy.
    # dashboard/ rides along: it is bind-mounted read-only, not baked into the
    # image, so an HTML change ships without a rebuild.
    COPYFILE_DISABLE=1 tar -czf - scripts dashboard | gcloud compute ssh "$INSTANCE" $G \
        --command="tar -C $REMOTE -xzf - && chmod +x $REMOTE/scripts/*.sh"

    # Idempotent, and cheap. Without it the pull fails with a bare 401 that
    # reads like a missing image rather than a missing credential helper.
    ssh_vm "gcloud auth configure-docker us-central1-docker.pkg.dev --quiet"
    # The dashboard runs the same image, so one pull covers both. cloudflared is
    # only started if a TUNNEL_TOKEN exists -- see scripts/setup_tunnel.sh.
    ssh_vm "cd $REMOTE && docker compose -f docker-compose.trading.yml pull stop-monitor \
        && docker compose -f docker-compose.trading.yml up -d stop-monitor dashboard \
        && if grep -qs TUNNEL_TOKEN .env; then \
             docker compose -f docker-compose.trading.yml up -d cloudflared; \
           else echo '  (no TUNNEL_TOKEN yet — tunnel not started)'; fi"
    sleep 6
    bold "Running"
    ssh_vm "docker ps --format '{{.Names}} | {{.Image}} | {{.Status}}'; echo; tail -12 $REMOTE/logs/stop_monitor.log 2>/dev/null || echo '  no log yet'"
fi
