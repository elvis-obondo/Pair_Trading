"""Validate the scanner as a stateless candidate producer, and book_state's IO.

Run: python research/validate_live_scanner.py

The scanner used to hold the book. It does not any more -- stop_monitor.py owns
opening, closing and the ledger, because a stop has to be watched between bars.
So the tests here changed shape: what the scanner PUBLISHES, and what it must
never touch. The exit-side ledger tests live in validate_stop_monitor.py.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import shutil
import tempfile
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd

import book_state as cfg

n_pass = n_fail = 0


def check(name, ok, detail=""):
    global n_pass, n_fail
    ok = bool(ok)
    n_pass, n_fail = n_pass + ok, n_fail + (not ok)
    print(f"{name + ':':64s} {str(detail)[:24]:26s} {'PASS' if ok else 'FAIL'}")


def cands_frame(n=105):
    """What scan() returns: ranked theta descending, NaN last.

    n=105 with the last 10 unranked, so five NaN-theta rows land INSIDE the
    published top 100. A fixture where every unranked row falls off the end
    silently stops testing that they survive publication.
    """
    rows = []
    for i in range(n):
        theta = np.nan if i >= n - 10 else 0.5 - i * 0.001
        rows.append({
            "ticker_a": f"A{i}", "ticker_b": f"B{i}",
            "entry_spread": 0.0612345678901234 + i * 1e-9,
            "mu_at_entry": -0.0012345678901234,
            "sigma_at_entry": 0.0203456789012345,
            "z_at_entry": 3.0 + i * 0.0001,
            "beta_at_entry": 1.2345678901234567,
            "alpha_at_entry": -4.9876543210987654,
            "theta_at_entry": theta,
            "take_profit_level": -0.0012345678901234,
        })
    return pd.DataFrame(rows)


# Redirect every path into a scratch dir BEFORE importing live_scanner, so a
# validation run can never write the real book or the real scan history.
TMP = tempfile.mkdtemp(prefix="validate_scanner_")
cfg.DATA_DIR = TMP
cfg.LOG_DIR = os.path.join(TMP, "logs")
cfg.STATE_PATH = os.path.join(TMP, "scanner_state.json")
cfg.LEDGER_PATH = os.path.join(TMP, "scanner_trades.csv")
cfg.CANDIDATES_PATH = os.path.join(TMP, "scanner_candidates.json")
cfg.SCAN_HISTORY_DIR = os.path.join(TMP, "scan_history")
cfg.SCANNER_LOG = os.path.join(cfg.LOG_DIR, "scanner.log")

import live_scanner as ls          # noqa: E402 — must follow the redirect above
from portfolio import Portfolio, Position   # noqa: E402

BAR = pd.Timestamp("2026-09-12 01:00:00")

try:
    # ----------------------------------------------------------------------
    print("=" * 118)
    print("1. Candidates are published at FULL precision — the monitor stops off these")
    print("=" * 118)
    cands = cands_frame()
    ls.write_candidates(cands, BAR)
    payload = json.load(open(cfg.CANDIDATES_PATH))

    check("machine block is present and separate from the display block",
          "candidates" in payload and "top_candidates" in payload,
          f"{len(payload.get('candidates', []))} / {len(payload.get('top_candidates', []))}")
    check("publishes TOP_N_PUBLISHED rows", len(payload["candidates"]) == ls.TOP_N_PUBLISHED,
          len(payload["candidates"]))
    check("display block is the shorter one",
          len(payload["top_candidates"]) == ls.TOP_N_DISPLAYED,
          len(payload["top_candidates"]))

    first = payload["candidates"][0]
    src = cands.iloc[0]
    for f in ("entry_spread", "mu_at_entry", "sigma_at_entry", "beta_at_entry",
              "alpha_at_entry", "take_profit_level"):
        check(f"  {f} round-trips bit-exact", first[f] == float(src[f]),
              f"{first[f]!r}")
    check("the display block IS rounded (so it is never mistaken for the other)",
          payload["top_candidates"][0]["sigma"] != float(src.sigma_at_entry),
          payload["top_candidates"][0]["sigma"])

    check("every field the monitor needs is present",
          all(k in first for k in ("ticker_a", "ticker_b", "entry_spread",
                                   "mu_at_entry", "sigma_at_entry", "z_at_entry",
                                   "beta_at_entry", "alpha_at_entry",
                                   "theta_at_entry", "take_profit_level")),
          f"{len(first)} keys")
    check("NaN theta serialises as null, not NaN (JSON has no NaN)",
          payload["candidates"][-1]["theta_at_entry"] is None,
          payload["candidates"][-1]["theta_at_entry"])
    check("written atomically — no .tmp left behind",
          not os.path.exists(cfg.CANDIDATES_PATH + ".tmp"), "clean")
    check("generated_at is timezone-aware, so staleness is computable",
          datetime.fromisoformat(payload["generated_at"]).tzinfo is not None,
          payload["generated_at"][-6:])

    # ----------------------------------------------------------------------
    print()
    print("=" * 118)
    print("2. Ranking order survives publication")
    print("=" * 118)
    thetas = [c["theta_at_entry"] for c in payload["candidates"]]
    ranked = [t for t in thetas if t is not None]
    check("ranked candidates are theta descending",
          ranked == sorted(ranked, reverse=True), f"{len(ranked)} ranked")
    check("unranked ones sort last, and are KEPT not dropped",
          all(t is None for t in thetas[len(ranked):]) and len(ranked) < len(thetas),
          f"{len(thetas) - len(ranked)} unranked")

    # ----------------------------------------------------------------------
    print()
    print("=" * 118)
    print("3. Scan history accumulates — what the scanner saw outlives the cycle")
    print("=" * 118)
    ls.append_scan_history(cands, BAR)
    day = BAR.strftime("%Y-%m-%d")
    path = os.path.join(cfg.SCAN_HISTORY_DIR, f"{day}.parquet")
    check("a day file is written", os.path.exists(path), day)
    h1 = pd.read_parquet(path)
    check("one row per published candidate", len(h1) == ls.TOP_N_PUBLISHED, len(h1))
    check("bar_time and rank are recorded",
          "bar_time" in h1.columns and "rank" in h1.columns and h1["rank"].iloc[0] == 1,
          "present")

    ls.append_scan_history(cands, BAR + timedelta(minutes=30))
    h2 = pd.read_parquet(path)
    check("a second cycle APPENDS, never overwrites",
          len(h2) == 2 * ls.TOP_N_PUBLISHED, len(h2))
    check("both cycles are distinguishable by bar_time",
          h2["bar_time"].nunique() == 2, h2["bar_time"].nunique())

    ls.append_scan_history(cands, BAR + timedelta(days=1))
    check("a new day starts a new file",
          os.path.exists(os.path.join(cfg.SCAN_HISTORY_DIR,
                                      f"{(BAR + timedelta(days=1)).strftime('%Y-%m-%d')}.parquet")),
          "partitioned")
    check("an empty scan writes nothing rather than an empty file",
          (ls.append_scan_history(pd.DataFrame(), BAR) is None
           and len(pd.read_parquet(path)) == 2 * ls.TOP_N_PUBLISHED), "no-op")

    # ----------------------------------------------------------------------
    print()
    print("=" * 118)
    print("4. SINGLE WRITER — the scanner never touches the book")
    print("=" * 118)
    check("no state file was created", not os.path.exists(cfg.STATE_PATH), "absent")
    check("no ledger was created", not os.path.exists(cfg.LEDGER_PATH), "absent")

    # Now plant a book and confirm publishing still does not disturb it.
    pf = Portfolio(equity=300.0, max_slots=10)
    sig = {"entry_spread": 0.06, "mu_at_entry": 0.0, "sigma_at_entry": 0.02,
           "z_at_entry": 3.0, "beta_at_entry": 1.0, "alpha_at_entry": 0.0,
           "theta_at_entry": 0.2, "take_profit_level": 0.0}
    szg = {"leg_a_notional": 150.0, "leg_b_notional": 150.0,
           "gross_notional": 300.0, "margin": 15.0, "leverage": 20.0,
           "rejected": False, "reject_reason": None, "notional_capped": False}
    pf.open_positions.append(Position(1, "A0", "B0", sig, szg,
                                      datetime(2026, 9, 12, 1, 0), 0.5))
    cfg.save_portfolio(pf)
    before = os.path.getmtime(cfg.STATE_PATH)
    ls.write_candidates(cands, BAR)
    ls.append_scan_history(cands, BAR)
    check("state file untouched by a publish",
          os.path.getmtime(cfg.STATE_PATH) == before, "unchanged")
    check("still no ledger", not os.path.exists(cfg.LEDGER_PATH), "absent")
    payload = json.load(open(cfg.CANDIDATES_PATH))
    check("the scanner CAN read state for display only",
          payload["top_candidates"][0]["already_open"] is True, "annotated")

    # ----------------------------------------------------------------------
    print()
    print("=" * 118)
    print("5. book_state round-trips a position exactly")
    print("=" * 118)
    restored = cfg.load_portfolio()
    check("written atomically — no .tmp left behind",
          not os.path.exists(cfg.STATE_PATH + ".tmp"), "clean")
    check("same number of open positions",
          len(restored.open_positions) == len(pf.open_positions),
          len(restored.open_positions))
    a, b = restored.open_positions[0], pf.open_positions[0]
    check("same pair", a.pair == b.pair, f"{a.pair}")
    check("frozen entry signal identical",
          all(np.isclose(a.signal[k], b.signal[k]) for k in b.signal), "identical")
    check("sizing identical",
          np.isclose(a.sizing["gross_notional"], b.sizing["gross_notional"]), "identical")
    check("direction recomputed correctly on load", a.direction == b.direction,
          a.direction)
    check("equity comes from the ledger, not the state file",
          restored.equity == cfg.ACCOUNT_EQUITY,
          f"{restored.equity:.2f} (no ledger yet)")

    # A ledger with realised PnL must override whatever the state file claimed.
    cfg.append_ledger([{"event": "close", "trade_num": 1, "realized_pnl_net": -12.5}])
    check("a realised close moves equity off the starting value",
          np.isclose(cfg.load_portfolio().equity, cfg.ACCOUNT_EQUITY - 12.5),
          f"{cfg.load_portfolio().equity:.2f}")

    # A FRESH DEPLOYMENT has a zero-byte ledger, on purpose: Docker bind-mounts a
    # missing file path as a directory instead of erroring, so the compose setup
    # pre-creates it empty. pd.read_csv raises EmptyDataError on that, which
    # crash-looped the monitor on the VM the first time it started with no trades.
    import os as _os
    _os.remove(cfg.LEDGER_PATH)
    open(cfg.LEDGER_PATH, "w").close()
    check("a zero-byte ledger loads at starting equity",
          cfg.load_portfolio().equity == cfg.ACCOUNT_EQUITY,
          f"{cfg.load_portfolio().equity:.2f}")
    open(cfg.LEDGER_PATH, "w").write(",".join(cfg.LEDGER_COLUMNS) + "\n")
    check("a header-only ledger loads at starting equity",
          cfg.load_portfolio().equity == cfg.ACCOUNT_EQUITY,
          f"{cfg.load_portfolio().equity:.2f}")
    _os.remove(cfg.LEDGER_PATH)
    check("a missing ledger loads at starting equity",
          cfg.load_portfolio().equity == cfg.ACCOUNT_EQUITY,
          f"{cfg.load_portfolio().equity:.2f}")

    # Writing into a PRE-CREATED EMPTY ledger must still write the header. It did
    # not: `header=not exists` was False for the zero-byte file the deploy
    # creates, so the first ten live positions landed with no column names and
    # pandas could not read the file back at all.
    open(cfg.LEDGER_PATH, "w").close()
    cfg.append_ledger([{"event": "open", "trade_num": 1, "ticker_a": "A",
                        "ticker_b": "B", "gross_notional": 300.0}])
    back = pd.read_csv(cfg.LEDGER_PATH)
    check("appending to a zero-byte ledger writes the header",
          list(back.columns) == cfg.LEDGER_COLUMNS, f"{len(back.columns)} cols")
    check("  ... and the row is readable by name",
          back.event.iloc[0] == "open" and back.ticker_a.iloc[0] == "A", "readable")
    cfg.append_ledger([{"event": "close", "trade_num": 1, "realized_pnl_net": -5.0}])
    back = pd.read_csv(cfg.LEDGER_PATH)
    check("  ... and a second append does NOT repeat it",
          len(back) == 2 and list(back.columns) == cfg.LEDGER_COLUMNS, f"{len(back)} rows")

    # ----------------------------------------------------------------------
    print()
    print("=" * 118)
    print("6. The cycle imports its parameters, it does not redefine them")
    print("=" * 118)
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "live_scanner.py")).read()
    for const in ("STOP_SIGMA", "MAX_SLOTS", "CAPITAL_FRAC", "LEVERAGE",
                  "ACCOUNT_EQUITY", "MIN_DEVIATION_SIGMA"):
        check(f"{const} is not redefined locally", f"\n{const} = " not in src,
              "imported")

    print()
    print("=" * 118)
    print(f"{n_pass}/{n_pass + n_fail} assertions PASS")
    print("=" * 118)
finally:
    shutil.rmtree(TMP, ignore_errors=True)

sys.exit(1 if n_fail else 0)
