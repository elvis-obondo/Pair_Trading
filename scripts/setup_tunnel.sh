#!/usr/bin/env bash
# Put the dashboard on the internet without opening a port.
#
#   scripts/setup_tunnel.sh <TUNNEL_TOKEN>
#   scripts/setup_tunnel.sh status
#   scripts/setup_tunnel.sh logs
#
# WHY A TUNNEL AND NOT A PORT
#
# The VM's external IP is EPHEMERAL and has already changed once (35.238.142.118
# -> 104.155.130.144 during the e2-medium resize). Any bookmark against an IP
# dies on the next restart, and there is another restart coming when the trial
# ends. A tunnel gives a stable hostname that does not care.
#
# It also means nothing listens on a public interface. cloudflared connects
# OUTBOUND from the VM; the firewall stays closed; there is no port to scan.
#
# WHY THERE IS NO PASSWORD IN THIS FILE
#
# Auth is Cloudflare Access, in front of the tunnel, and it authenticates PEOPLE
# rather than checking a shared secret: a whitelisted address requests a one-time
# code by email. Nothing to leak, reuse, or rotate, and an unauthenticated
# request never reaches dashboard_server.py -- which has no login of its own, on
# purpose. A second weaker check there would only tempt someone to expose the
# port directly and rely on it.
#
# ── WHAT YOU DO IN THE BROWSER, ONCE ───────────────────────────────────────────
#
#  1. one.dash.cloudflare.com  ->  Networks  ->  Tunnels  ->  Create a tunnel
#       type: Cloudflared.  Name it e.g. "pairs-dashboard".
#       Copy the token it shows (a long string starting "ey...").
#
#  2. On the tunnel's Public Hostname tab, add a hostname:
#       Service:  HTTP  ->  localhost:8080
#       If you have no domain on Cloudflare, use the free *.cfargotunnel.com
#       hostname it offers instead.
#
#  3. Run this script with that token. It writes .env on the VM and starts
#     cloudflared. The token is a credential: it is stored 0600 and never
#     committed.
#
#  4. THEN LOCK IT DOWN, or the dashboard is public:
#       Zero Trust -> Access -> Applications -> Add an application -> Self-hosted
#       Point it at the same hostname.
#       Policy: Action Allow, Include -> Emails -> your addresses.
#       Authentication method: One-time PIN.
#
#     Until step 4 exists, anyone with the URL can read the book. It is paper
#     with no keys and no money, but do not leave it that way.
set -uo pipefail

PROJECT="project-0671be06-e22a-44d8-83c"
ZONE="us-central1-a"
INSTANCE="pairs-trading"
REMOTE="/home/elvisobondo/Pair_Trading"
G="--project=$PROJECT --zone=$ZONE"
C="docker compose -f docker-compose.trading.yml"

ssh_vm() { gcloud compute ssh "$INSTANCE" $G --command="$1" < /dev/null; }
bold() { printf "\n\033[1m%s\033[0m\n" "$*"; }
die()  { printf "  \033[31mfail\033[0m %s\n" "$*"; exit 1; }

case "${1:-}" in
  status)
    bold "Tunnel status"
    ssh_vm "cd $REMOTE && $C ps cloudflared dashboard; echo;
            curl -s -o /dev/null -w 'local dashboard: %{http_code}\n' localhost:8080/;
            echo; docker logs --tail 12 pairs-tunnel 2>&1 | sed 's/^/  /'"
    exit 0 ;;
  logs)
    ssh_vm "docker logs --tail ${2:-60} -f pairs-tunnel"
    exit 0 ;;
  down)
    ssh_vm "cd $REMOTE && $C stop cloudflared && $C rm -f cloudflared" \
      && echo "  tunnel stopped; the dashboard is no longer reachable from outside"
    exit 0 ;;
esac

TOKEN="${1:-}"
[ -n "$TOKEN" ] || die "usage: scripts/setup_tunnel.sh <TUNNEL_TOKEN>   (see the header)"
case "$TOKEN" in
  ey*) : ;;
  *) die "that does not look like a tunnel token — they start with 'ey'" ;;
esac

bold "Installing the tunnel token"
# Written with printf over ssh rather than scp'd: the token never lands in a
# file on the laptop, and 0600 keeps it off other accounts on the VM.
ssh_vm "cd $REMOTE && umask 077 && printf 'TUNNEL_TOKEN=%s\n' '$TOKEN' > .env && ls -l .env" \
  || die "could not write .env"

bold "Starting cloudflared"
ssh_vm "cd $REMOTE && $C up -d dashboard cloudflared && sleep 4 && $C ps dashboard cloudflared" \
  || die "compose up failed"

bold "Checking it registered"
ssh_vm "docker logs --tail 20 pairs-tunnel 2>&1 | sed 's/^/  /'"

cat <<'EOF'

  Next, and this is the part that matters:

    Zero Trust -> Access -> Applications -> Add an application -> Self-hosted
      Application domain: the hostname you bound to localhost:8080
      Policy: Allow, Include -> Emails -> the addresses you want
      Authentication: One-time PIN

  Until that policy exists the URL is readable by anyone who has it.

  scripts/setup_tunnel.sh status    what the tunnel is doing
  scripts/setup_tunnel.sh down      take it off the internet
EOF
