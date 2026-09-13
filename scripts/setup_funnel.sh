#!/usr/bin/env bash
# Put the dashboard on the internet over Tailscale Funnel, behind a password.
#
#   scripts/setup_funnel.sh          full setup (prompts for the password)
#   scripts/setup_funnel.sh password change only the password
#   scripts/setup_funnel.sh status   what is running and at what URL
#   scripts/setup_funnel.sh down     take it off the internet
#
# WHY FUNNEL AND NOT A PORT
#
# The VM's external IP is EPHEMERAL and has already changed once (35.238.142.118
# -> 104.155.130.144 during the e2-medium resize). Funnel gives a STABLE
# https://<host>.<tailnet>.ts.net hostname that survives every restart, needs no
# domain, costs nothing, and needs no inbound firewall rule -- tailscaled dials
# out, exactly like cloudflared would have.
#
# WHY THERE IS A PASSWORD AT ALL
#
# Funnel publishes to the WHOLE INTERNET and authenticates nobody. (Its sibling
# `tailscale serve` is private to your tailnet and needs no password, but then
# every device needs the Tailscale app -- which is not "open a URL anywhere".)
# So the server checks basic auth itself. That is only acceptable because Funnel
# terminates real TLS: the credential is encrypted in transit. Over plain HTTP
# it would not be.
#
# THE PASSWORD IS NEVER TRANSMITTED TO ANYONE BUT YOU
#
# Read here with `read -s` (no echo, never in shell history), hashed LOCALLY, and
# only the salted SHA-256 digest is sent to the VM. The plaintext never leaves
# this terminal, is never written to a file, and is not recoverable from the VM.
#
# The server FAILS CLOSED: with no digest configured it serves 503, not content.
set -uo pipefail

PROJECT="project-0671be06-e22a-44d8-83c"
ZONE="us-central1-a"
INSTANCE="pairs-trading"
REMOTE="/home/elvisobondo/Pair_Trading"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
G="--project=$PROJECT --zone=$ZONE"
C="docker compose -f docker-compose.trading.yml"

ssh_vm() { gcloud compute ssh "$INSTANCE" $G --command="$1" < /dev/null; }
bold() { printf "\n\033[1m%s\033[0m\n" "$*"; }
ok()   { printf "  \033[32mok\033[0m   %s\n" "$*"; }
warn() { printf "  \033[33mwarn\033[0m %s\n" "$*"; }
die()  { printf "  \033[31mfail\033[0m %s\n" "$*"; exit 1; }

read_password() {
    # Never echoed, never in history, never written down.
    local p1 p2
    printf "\n  Choose the dashboard password (not shown as you type).\n"
    printf "  Use one you use NOWHERE else.\n\n"
    read -r -s -p "  password: " p1; echo
    read -r -s -p "  again:    " p2; echo
    [ -n "$p1" ] || die "empty password"
    [ "$p1" = "$p2" ] || die "they do not match"
    [ ${#p1} -ge 10 ] || die "use at least 10 characters — this is on the public internet"
    DIGEST="$(python3 "$ROOT/research/dashboard_server.py" --hash "$p1")"
    unset p1 p2
    [ -n "$DIGEST" ] || die "could not hash the password"
}

push_digest() {
    # Appended to the same .env the compose file reads. umask 077 so it is not
    # world-readable; only the digest crosses the wire.
    ssh_vm "cd $REMOTE && umask 077 && touch .env \
        && grep -v '^PAIRS_DASH_SHA256=' .env > .env.new 2>/dev/null; \
        printf 'PAIRS_DASH_SHA256=%s\n' '$DIGEST' >> .env.new \
        && mv .env.new .env && chmod 600 .env && echo '  .env updated'" \
        || die "could not write .env"
}

case "${1:-setup}" in
  status)
    bold "Funnel status"
    ssh_vm "tailscale status 2>&1 | head -3; echo;
            echo 'funnel:'; tailscale funnel status 2>&1 | sed 's/^/  /';
            echo; cd $REMOTE && $C ps dashboard;
            curl -s -o /dev/null -w '  local dashboard (no auth path): %{http_code}\n' localhost:8080/healthz"
    exit 0 ;;

  password)
    read_password
    push_digest
    bold "Restarting the dashboard with the new password"
    ssh_vm "cd $REMOTE && $C up -d --force-recreate dashboard && sleep 2 && $C ps dashboard"
    ok "password changed"
    exit 0 ;;

  down)
    bold "Taking the dashboard off the internet"
    ssh_vm "sudo tailscale funnel --https=443 off 2>&1 | sed 's/^/  /'; tailscale funnel status 2>&1 | sed 's/^/  /'"
    ok "funnel off — the dashboard is only reachable over SSH tunnel now"
    exit 0 ;;
esac

# ── full setup ──────────────────────────────────────────────────────────────
bold "1/4  Tailscale login"
if ssh_vm "tailscale status >/dev/null 2>&1"; then
    ok "already logged in"
    ssh_vm "tailscale status | head -2 | sed 's/^/  /'"
else
    cat <<'EOF'

  The VM needs to join your tailnet. This prints a URL — open it in a browser,
  sign in (Google/GitHub/email, free personal account), approve the machine.
  One click, once. Everything after this is terminal-only.

EOF
    ssh_vm "sudo tailscale up --ssh=false --hostname=pairs-trading 2>&1 | sed 's/^/  /'" \
        || warn "if that printed a URL, open it, then re-run this script"
    ssh_vm "tailscale status >/dev/null 2>&1" || die "not logged in yet — open the URL above and re-run"
    ok "joined"
fi

bold "2/4  Dashboard password"
read_password
push_digest

bold "3/4  Restarting the dashboard with auth enabled"
ssh_vm "cd $REMOTE && $C up -d --force-recreate dashboard && sleep 3 \
    && $C ps dashboard \
    && curl -s -o /dev/null -w '  unauthenticated request -> %{http_code} (expect 401)\n' localhost:8080/"

bold "4/4  Opening the funnel"
# Funnel needs to be enabled for the tailnet once, in the admin console. The
# command says so plainly if it is not.
ssh_vm "sudo tailscale funnel --bg --https=443 8080 2>&1 | sed 's/^/  /'" \
    || warn "if that asked you to enable Funnel, follow the link, then re-run"
ssh_vm "tailscale funnel status 2>&1 | sed 's/^/  /'"

bold "Your URL"
ssh_vm "echo -n '  https://'; tailscale status --json 2>/dev/null | python3 -c \"
import json,sys
d=json.load(sys.stdin)
print(d['Self']['DNSName'].rstrip('.'))
\" 2>/dev/null || echo '  (run: scripts/setup_funnel.sh status)'"

cat <<'EOF'

  Open that URL from anywhere. Any username; the password is the one you chose.

  scripts/setup_funnel.sh status     what is running
  scripts/setup_funnel.sh password   change the password
  scripts/setup_funnel.sh down       take it off the internet

  The server fails CLOSED: if the digest is ever missing it serves 503, not the
  book.
EOF
