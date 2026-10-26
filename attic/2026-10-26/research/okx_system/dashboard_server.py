"""Serve the dashboard. Read-only, allowlisted, and it owns nothing.

WHY IT IS ITS OWN PROCESS

The monitor is the only writer of the book and the only thing whose latency
matters -- a stop that fires late is the failure this project exists to prevent.
Serving HTTP from inside it would put request handling on the same event loop as
tick evaluation. So this runs beside it and only ever reads files.

WHAT IT WILL SERVE

An explicit allowlist, nothing else. No directory listing, no path traversal, no
writes, no query parameters that reach the filesystem. The page and three data
files, all of which the monitor produces anyway.

AUTH

Basic auth over TLS, and ONLY because the chosen transport is Tailscale Funnel,
which publishes to the whole internet and does not authenticate anyone itself.
Funnel terminates real HTTPS, so the credential is encrypted in transit -- that
is the whole reason basic auth is acceptable here and would not have been over
plain HTTP.

The password is never stored. PAIRS_DASH_SHA256 holds a salted SHA-256 of it and
comparison is constant-time. If that variable is unset the server REFUSES to
serve anything except /healthz, rather than falling open -- a dashboard that
silently drops its own auth is worse than one that will not start.

Behind an SSH tunnel there is nothing to authenticate, so PAIRS_DASH_OPEN=1
disables the check for that case only.

Usage:
    python research/dashboard_server.py --port 8080
"""
# Annotations as strings: macOS ships Python 3.9 as /usr/bin/python3, which
# cannot evaluate `str | None` at import time. `--hash` has to run under
# whatever interpreter the user happens to have.
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
import base64
import hashlib
import hmac
import http.server
import socketserver
from datetime import datetime, timezone


# book_state pulls in pandas. Deferred so `--hash` -- which needs nothing but
# hashlib -- works in any interpreter, including one without the project's
# dependencies installed. Hashing a password should not require a dataframe
# library, and it failed in exactly that way the first time it was run.
_cfg = None


def cfg():
    global _cfg
    if _cfg is None:
        import book_state
        _cfg = book_state
    return _cfg

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DASHBOARD_DIR = os.environ.get(
    "PAIRS_DASHBOARD_DIR", os.path.join(PROJECT_ROOT, "dashboard"))

# Salted so the stored digest is useless against a rainbow table, and so the
# same password on two deployments does not produce the same hash.
SALT = os.environ.get("PAIRS_DASH_SALT", "pairs-dashboard-v1")
EXPECT = os.environ.get("PAIRS_DASH_SHA256", "").strip().lower()
OPEN = os.environ.get("PAIRS_DASH_OPEN", "") == "1"


def password_digest(password: str, salt: str = SALT) -> str:
    return hashlib.sha256((salt + ":" + password).encode()).hexdigest()


def check_auth(header: str | None) -> bool:
    """Constant-time compare. Any username is accepted; only the password counts."""
    if not header or not header.startswith("Basic "):
        return False
    try:
        raw = base64.b64decode(header[6:]).decode("utf-8", "replace")
    except Exception:                                   # noqa: BLE001
        return False
    _, _, password = raw.partition(":")
    return hmac.compare_digest(password_digest(password), EXPECT)


# url path -> (file on disk, content type, download filename or None)
def routes() -> dict:
    return {
        "/": (os.path.join(DASHBOARD_DIR, "index.html"), "text/html; charset=utf-8", None),
        "/index.html": (os.path.join(DASHBOARD_DIR, "index.html"), "text/html; charset=utf-8", None),
        "/open_positions.json": (cfg().POSITIONS_PATH, "application/json", None),
        "/equity_curve.csv": (cfg().EQUITY_PATH, "text/csv", "equity_curve.csv"),
        "/ledger.csv": (cfg().LEDGER_PATH, "text/csv", "scanner_trades.csv"),
        "/healthz": (None, "text/plain", None),
    }


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "pairs-dashboard"
    sys_version = ""

    def _send(self, code, body: bytes, ctype: str, download=None, cache=False):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        # The book changes every ten seconds; a cached snapshot is a wrong one.
        self.send_header("Cache-Control",
                         "public, max-age=300" if cache else "no-store, must-revalidate")
        if download:
            self.send_header("Content-Disposition", f'attachment; filename="{download}"')
        # Cheap hardening that costs nothing even behind Access.
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = self.path.split("?", 1)[0].split("#", 1)[0]

        # /healthz stays open: the funnel and any uptime check need to see the
        # process is alive without holding a credential, and it reveals nothing.
        if path != "/healthz" and not OPEN:
            if not EXPECT:
                # Fail CLOSED. An unset password must never mean "no password".
                self._send(503, b"dashboard has no password configured\n", "text/plain")
                return
            if not check_auth(self.headers.get("Authorization")):
                self.send_response(401)
                self.send_header("WWW-Authenticate", 'Basic realm="book", charset="UTF-8"')
                self.send_header("Content-Length", "0")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                return

        route = routes().get(path)
        if route is None:
            self._send(404, b"not found\n", "text/plain")
            return
        disk, ctype, download = route

        if path == "/healthz":
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            ok = os.path.exists(cfg().POSITIONS_PATH)
            self._send(200 if ok else 503,
                       f"{'ok' if ok else 'no snapshot'} {now}\n".encode(), "text/plain")
            return

        try:
            with open(disk, "rb") as fh:
                body = fh.read()
        except OSError:
            # A missing equity curve or an empty ledger is normal on a fresh
            # deployment, and the page copes. Say so rather than 500.
            self._send(404, b"not written yet\n", "text/plain")
            return
        # Only the page itself is worth caching, and only briefly.
        self._send(200, body, ctype, download, cache=(path in ("/", "/index.html")))

    def log_message(self, fmt, *args):
        # One line per request, to stdout, which docker captures with the same
        # json-file caps as everything else. Silence would make a broken tunnel
        # indistinguishable from a quiet one.
        sys.stdout.write("%s %s %s\n" % (
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            self.address_string(), fmt % args))
        sys.stdout.flush()


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    # Binds to localhost by default: the tunnel connects outbound from the same
    # host, so nothing needs to listen on a public interface. Overriding this to
    # 0.0.0.0 puts an UNAUTHENTICATED dashboard on the internet.
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--hash", metavar="PASSWORD",
                    help="print the salted digest for a password and exit; the "
                         "password itself is never stored anywhere")
    a = ap.parse_args()
    if a.hash:
        print(password_digest(a.hash))
        return
    if OPEN:
        print("AUTH DISABLED (PAIRS_DASH_OPEN=1) — only safe behind an SSH tunnel",
              flush=True)
    elif not EXPECT:
        print("NO PASSWORD SET — serving 503 until PAIRS_DASH_SHA256 is provided",
              flush=True)
    print(f"dashboard on http://{a.host}:{a.port}  serving {DASHBOARD_DIR}", flush=True)
    print(f"  positions {cfg().POSITIONS_PATH}", flush=True)
    print(f"  equity    {cfg().EQUITY_PATH}", flush=True)
    print(f"  ledger    {cfg().LEDGER_PATH}", flush=True)
    with Server((a.host, a.port), Handler) as srv:
        srv.serve_forever()


if __name__ == "__main__":
    main()
