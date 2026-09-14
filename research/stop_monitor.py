"""Watch the book tick by tick and close positions when their level is crossed.

THE PROBLEM THIS SOLVES

The stop has never once worked. Across 12,597 backtested trades in three
independent 6-month windows, ZERO of 9,704 stop-outs filled at or inside the
0.5-sigma stop: median overshoot 1.53x, mean 2.07x, p90 3.26x. That costs 0.83R
per trade and turns a +0.74R edge into -0.083R.

It is not the stop width. Sweeping 0.5 -> 2.5 sigma moves mean R from -0.201 to
-0.024 and converges on zero without ever crossing it. It is how often we look.
The spread moves a median 0.11 sigma per 30-minute bar and 5.3% of single bars
clear the whole stop distance alone, so a bar-close check is not a stop -- it is
a report that the stop was passed some time in the last half hour.

No exchange can fix this. The stop is on a synthetic, log(A) - beta*log(B) -
alpha, and no venue has an order type that watches a spread across two arbitrary
instruments. Per-leg stops are worse: one firing leaves the other naked. So it
is a monitoring problem and the only lever is frequency.

WHY THAT IS CHEAP

The stop level is fully determined at entry. entry_spread, sigma_at_entry,
beta_at_entry and alpha_at_entry are frozen and never re-estimated, so checking
the stop is two logs, a multiply, a subtract and a compare. No panel, no rolling
window, no OU fit. It runs on anything, every second.

WHAT THIS OWNS

Everything about the book: opening, closing, sizing, the state file and the
ledger. `live_scanner.py` is a stateless candidate producer that writes a file.
One writer, because two processes appending to one CSV is how you get the ledger
corruption docs/HANDOFF.md never explained.

IT SUBMITS NO ORDERS. `_submit_close` is a stub. This maintains a paper book
against live prices with the production sizer and exit logic; execution is
deliberately not wired.

Usage:
    python research/stop_monitor.py                 # live, books trades
    python research/stop_monitor.py --dry-run       # live, persists nothing
    python research/stop_monitor.py --replay f.csv  # no socket; drive from a file
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
import asyncio
import fcntl
import json
import math
import time
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd

import book_state as cfg
from portfolio import Position, cooldown_key
from position_sizer import compute_position_size
from signal_generator import generate_exit_signal

OKX_WS_PUBLIC = "wss://ws.okx.com:8443/ws/v5/public"

# How long a leg may go without a tick before its position is BLIND. A blind
# position is never exited on the stale price -- booking a fill against a price
# from ten minutes ago is worse than the 30-minute bar close this replaces.
STALE_SECONDS = 30.0

# Consecutive evaluations beyond the level before the exit is booked. One bad
# print on a thin altcoin book must not fire a stop; two consecutive pushes is
# typically well under a second. 1 disables the check. confirm_delay_ms records
# what it actually cost, per trade.
CONFIRM_TICKS = 2

PING_SECONDS = 20.0
RECONNECT_MAX_BACKOFF = 30.0
REST_FALLBACK_AFTER_FAILURES = 4
REST_POLL_SECONDS = 5.0
HEARTBEAT_SECONDS = 10.0
SLOW_TIMER_SECONDS = 60.0
HOUSEKEEPING_SECONDS = 3600.0
TICK_RECORD_HZ = 1.0


def instrument_id(ticker: str) -> str:
    return f"{ticker}-USDT-SWAP"


def ticker_of(inst_id: str) -> str:
    return inst_id.split("-")[0]


def log(msg: str, path: str = cfg.MONITOR_LOG) -> None:
    line = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')}  {msg}"
    print(line, flush=True)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as fh:
        fh.write(line + "\n")


class Quote:
    """Top of book for one instrument, plus when we last heard from it."""

    __slots__ = ("bid", "ask", "last", "ts")

    def __init__(self, bid, ask, last, ts):
        self.bid, self.ask, self.last, self.ts = bid, ask, last, ts

    @property
    def mid(self) -> float:
        if self.bid and self.ask and self.bid > 0 and self.ask > 0:
            return 0.5 * (self.bid + self.ask)
        return self.last


class StopMonitor:
    """The book, and the rules for getting out of it.

    Deliberately synchronous and socket-free. The asyncio layer below feeds
    `on_tick`; `--replay` feeds the same method from a CSV; the validator calls
    it directly. Nothing about the exit logic depends on how prices arrived.
    """

    def __init__(self, portfolio, dry_run: bool = False,
                 confirm_ticks: int = CONFIRM_TICKS,
                 stale_seconds: float = STALE_SECONDS,
                 record_ticks: bool = True):
        self.pf = portfolio
        self.dry_run = dry_run
        self.confirm_ticks = max(1, int(confirm_ticks))
        self.stale_seconds = float(stale_seconds)
        self.record_ticks = record_ticks

        self.quotes: dict[str, Quote] = {}
        self.feed_state = "live"
        self.subscribed: set[str] = set()
        self.candidate_instruments: set[str] = set()

        # Per-position breach bookkeeping, keyed by trade_num. Reset whenever the
        # spread comes back inside the level or the firing reason changes.
        self._breach: dict[int, dict] = {}
        # Last evaluation time per position, so the length of a feed outage is
        # measurable rather than inferred.
        self._last_eval: dict[int, float] = {}

        self._tick_buffer: list[dict] = []
        self._tick_last_recorded: dict[str, float] = {}
        # SHADOW WINDOW: {inst_id: unix ts to keep recording until}. Populated
        # when a position closes so the spread's behaviour AFTER the exit is
        # still captured. See book_state.SHADOW_WINDOW_MINUTES for why.
        self._shadow_until: dict[str, float] = {}
        self.closed_this_session: list[dict] = []
        self.opened_this_session: list[Position] = []

    # -- what we need prices for ----------------------------------------- #

    def desired_instruments(self) -> set[str]:
        """Open legs plus current candidate legs.

        Candidates are included so an entry can be filled at a live price the
        moment the scanner names it, instead of waiting a subscribe round trip
        while the dislocation decays.
        """
        want = set()
        for p in self.pf.open_positions:
            want.add(instrument_id(p.ticker_a))
            want.add(instrument_id(p.ticker_b))
        return want | self.candidate_instruments | self.shadow_instruments()

    def held_instruments(self) -> set[str]:
        want = set()
        for p in self.pf.open_positions:
            want.add(instrument_id(p.ticker_a))
            want.add(instrument_id(p.ticker_b))
        return want

    def shadow_instruments(self, now: float | None = None) -> set[str]:
        """Legs of recently-closed positions, still inside the shadow window.

        Expired entries are dropped here rather than on a timer, so the set is
        always correct at the moment it is asked for. A shadowed instrument is
        recorded and stays subscribed; it holds no position, so nothing in the
        exit path can ever see it.
        """
        now = time.time() if now is None else now
        self._shadow_until = {i: t for i, t in self._shadow_until.items() if t > now}
        return set(self._shadow_until)

    def recording_instruments(self, now: float | None = None) -> set[str]:
        """Everything whose ticks we want on disk: open legs plus shadowed ones."""
        return self.held_instruments() | self.shadow_instruments(now)

    # -- prices in ------------------------------------------------------- #

    def on_tick(self, inst_id: str, bid, ask, last, now: float | None = None):
        """One quote update. Returns the exits it booked, usually none."""
        now = time.time() if now is None else now
        self.quotes[inst_id] = Quote(bid, ask, last, now)
        self._maybe_record(inst_id, now)
        return self.evaluate_positions(now, touched=inst_id)

    def _maybe_record(self, inst_id: str, now: float) -> None:
        """Throttled tick capture, open positions only.

        This is the intraday data the backtest could not have. After a few weeks
        it is enough to replay our own book at one-second resolution and measure
        directly what 30-minute checking was costing.

        Covers the shadow window too -- a closed position's legs keep recording
        for SHADOW_WINDOW_MINUTES, which is what makes "did the spread come back
        after we were stopped" a countable question instead of a guess.
        """
        if not self.record_ticks or inst_id not in self.recording_instruments(now):
            return
        prev = self._tick_last_recorded.get(inst_id, 0.0)
        if now - prev < 1.0 / TICK_RECORD_HZ:
            return
        self._tick_last_recorded[inst_id] = now
        q = self.quotes[inst_id]
        self._tick_buffer.append({
            "ts": now, "inst_id": inst_id,
            "bid": q.bid, "ask": q.ask, "last": q.last,
        })

    # -- exits ------------------------------------------------------------ #

    def _log_prices(self, pos) -> tuple[float, float] | None:
        qa = self.quotes.get(instrument_id(pos.ticker_a))
        qb = self.quotes.get(instrument_id(pos.ticker_b))
        if qa is None or qb is None:
            return None
        ma, mb = qa.mid, qb.mid
        if not (ma and mb and ma > 0 and mb > 0):
            return None
        return math.log(ma), math.log(mb)

    def _exec_spread(self, pos) -> float:
        """Spread at the side of book we would actually have to cross.

        Diagnostic only -- the trigger and the booked fill both use mid. beta can
        be negative, which flips which leg is short, so the side is taken from
        the signed position in each leg rather than assumed from direction.
        """
        qa = self.quotes.get(instrument_id(pos.ticker_a))
        qb = self.quotes.get(instrument_id(pos.ticker_b))
        if qa is None or qb is None:
            return float("nan")
        # Leg B's sign is the OPPOSITE of leg A's -- see Position.exposure. This
        # read +direction until 2026-09-13, which picked the wrong side of book
        # for leg B on every exit. Diagnostic column only; no fill used it.
        pos_a, pos_b = pos.exposure
        # Closing a short means buying: cross the ask. Closing a long: the bid.
        px_a = (qa.ask if pos_a < 0 else qa.bid) or qa.last
        px_b = (qb.ask if pos_b < 0 else qb.bid) or qb.last
        if not (px_a and px_b and px_a > 0 and px_b > 0):
            return float("nan")
        return (math.log(px_a)
                - pos.signal["alpha_at_entry"]
                - pos.signal["beta_at_entry"] * math.log(px_b))

    def is_blind(self, pos, now: float) -> bool:
        for t in (pos.ticker_a, pos.ticker_b):
            q = self.quotes.get(instrument_id(t))
            if q is None or (now - q.ts) > self.stale_seconds:
                return True
        return False

    def evaluate_positions(self, now: float, touched: str | None = None,
                           check_time_stop: bool = False) -> list[dict]:
        """Evaluate every position that this tick could have moved.

        `touched` limits the work to positions holding that leg; the 60-second
        slow timer passes None and check_time_stop=True to sweep everything.
        """
        booked = []
        for pos in list(self.pf.open_positions):
            if touched is not None and touched not in (
                    instrument_id(pos.ticker_a), instrument_id(pos.ticker_b)):
                continue

            # A stale leg cannot be marked or closed. Hold rather than guess.
            if self.is_blind(pos, now):
                continue

            prices = self._log_prices(pos)
            if prices is None:
                continue
            la, lb = prices

            # How long we were unable to see this position. Attached to whatever
            # exit fires now, so a trade booked after an outage is never mistaken
            # for one that was watched the whole way.
            prev_eval = self._last_eval.get(pos.trade_num)
            gap = 0.0 if prev_eval is None else max(0.0, now - prev_eval)
            self._last_eval[pos.trade_num] = now

            wall_now = datetime.fromtimestamp(now, tz=timezone.utc).replace(tzinfo=None)
            hours = (wall_now - pos.opened_at).total_seconds() / 3600.0

            ex = generate_exit_signal(
                current_price_a=la, current_price_b=lb,
                entry_signal=pos.signal, hours_elapsed=hours,
                stop_sigma=self.pf.stop_sigma,
                # The time stop is not latency sensitive and must not fire off a
                # tick that merely happens to arrive late. The slow timer owns it.
                max_hold_hours=(self.pf.max_hold_hours if check_time_stop
                                else float("inf")),
            )
            if ex is None:
                self._breach.pop(pos.trade_num, None)
                continue

            reason = ex["exit_reason"]
            if reason == "time_stop":
                booked.append(self._book(pos, ex, now, hours, gap, 0.0))
                continue

            # Confirmation counts distinct PRICE OBSERVATIONS, not evaluations.
            # Legs tick independently, so a position is re-evaluated every time
            # either one updates. Counting evaluations would let a chatty leg B
            # confirm a breach that only leg A's (unchanged) quote implies --
            # ten ticks on B would satisfy a two-tick debounce without any new
            # information about the spread at all.
            qts = (self.quotes[instrument_id(pos.ticker_a)].ts,
                   self.quotes[instrument_id(pos.ticker_b)].ts)
            st = self._breach.get(pos.trade_num)
            if st is None or st["reason"] != reason:
                st = {"reason": reason, "count": 0, "first_ts": now, "qts": None}
                self._breach[pos.trade_num] = st
            if st["qts"] != qts:
                st["qts"] = qts
                st["count"] += 1
            if st["count"] < self.confirm_ticks:
                continue

            confirm_ms = (now - st["first_ts"]) * 1000.0
            self._breach.pop(pos.trade_num, None)
            booked.append(self._book(pos, ex, now, hours, gap, confirm_ms))
        return booked

    def _book(self, pos, ex: dict, now: float, hours: float,
              blind_gap: float, confirm_ms: float) -> dict:
        """Close the position and write the diagnostics this build exists for."""
        stop_distance = self.pf.stop_sigma * pos.signal["sigma_at_entry"]
        # The stop sits at entry - direction*distance in both directions:
        # direction is -1 when short the spread, where adverse means it rises.
        level = pos.signal["entry_spread"] - pos.direction * stop_distance
        fill = ex["current_spread"]

        self._submit_close(pos, ex["exit_reason"], fill)

        detected = datetime.fromtimestamp(now - confirm_ms / 1000.0, tz=timezone.utc)
        wall_now = datetime.fromtimestamp(now, tz=timezone.utc).replace(tzinfo=None)
        rec = self.pf._close(pos, ex, wall_now, hours)
        self.pf.open_positions = [p for p in self.pf.open_positions
                                  if p.trade_num != pos.trade_num]
        self._last_eval.pop(pos.trade_num, None)

        overshoot = (abs(fill - pos.signal["entry_spread"]) / stop_distance
                     if stop_distance > 0 else float("nan"))
        state = ("recovered_from_blind" if blind_gap > self.stale_seconds
                 else self.feed_state)
        rec.update({
            "exit_detected_at": detected.isoformat(timespec="milliseconds"),
            "exit_level_spread": level,
            # Meaningful for adverse_move; for a take-profit or time stop it is
            # just how far the spread travelled, in stop units.
            "overshoot_ratio": overshoot,
            "confirm_delay_ms": confirm_ms,
            "blind_gap_seconds": blind_gap if blind_gap > self.stale_seconds else 0.0,
            "feed_state": state,
            "entry_bar_z": getattr(pos, "entry_bar_z", None),
            "entry_fill_z": pos.signal["z_at_entry"],
            "exec_spread_at_exit": self._exec_spread(pos),
        })
        self.closed_this_session.append(rec)
        # Keep watching both legs. Recording only -- the position is already out
        # of pf.open_positions above, so nothing here can re-enter the exit path.
        until = now + cfg.SHADOW_WINDOW_MINUTES * 60.0
        for t in pos.pair:
            inst = instrument_id(t)
            self._shadow_until[inst] = max(self._shadow_until.get(inst, 0.0), until)
        log(f"CLOSE #{rec['trade_num']} {rec['ticker_a']}/{rec['ticker_b']} "
            f"{rec['exit_reason']} after {hours:.1f}h "
            f"pnl {rec['realized_pnl_net']:+.2f} R {rec['r']:+.2f} "
            f"overshoot {overshoot:.2f}x confirm {confirm_ms:.0f}ms "
            f"feed={state}")
        return rec

    def _submit_close(self, pos, reason: str, fill_spread: float) -> None:
        """PAPER ONLY. The one function a live adapter replaces.

        Live would send reduce-only market orders on both legs here and reconcile
        what actually filled. That needs API keys, a kill switch, and an answer to
        one leg filling while the other does not -- none of which belong in a
        paper run.
        """
        return None

    # -- entries ---------------------------------------------------------- #

    def load_candidates(self, path: str = cfg.CANDIDATES_PATH) -> list[dict]:
        if not os.path.exists(path):
            return []
        try:
            with open(path) as fh:
                payload = json.load(fh)
        except (json.JSONDecodeError, OSError) as e:
            log(f"candidates unreadable ({e}) — opening nothing this cycle")
            return []
        gen = payload.get("generated_at")
        if gen:
            age_min = (datetime.now(timezone.utc)
                       - datetime.fromisoformat(gen)).total_seconds() / 60.0
            if age_min > cfg.CANDIDATES_MAX_AGE_MIN:
                log(f"candidates are {age_min:.0f} min old (max "
                    f"{cfg.CANDIDATES_MAX_AGE_MIN:.0f}) — the scanner is down, "
                    f"opening nothing")
                return []
        rows = payload.get("candidates", [])
        self.candidate_instruments = set()
        for r in rows:
            self.candidate_instruments.add(instrument_id(r["ticker_a"]))
            self.candidate_instruments.add(instrument_id(r["ticker_b"]))
        return rows

    def try_open(self, candidates: list[dict], now: float) -> list[Position]:
        """Fill free slots at LIVE prices, re-anchoring each entry to its fill.

        The candidate's mu, sigma, beta, alpha and theta come from the 30-minute
        bar and are kept. entry_spread does not: it is recomputed from the price
        we actually get, and the trade is skipped if the spread reverted back
        inside 3 sigma in the meantime.

        This matters because the stop is defined as a DISTANCE FROM ENTRY. Anchor
        it to a bar-close spread we did not trade at and the stop sits the wrong
        distance from the real position, which is the same class of error that
        once manufactured a spurious 38.9% -> 1.7% win-rate curve.
        """
        opened = []
        if not candidates:
            return opened
        held = {p.pair for p in self.pf.open_positions}
        counts = self.pf._ticker_counts()
        wall_now = datetime.fromtimestamp(now, tz=timezone.utc).replace(tzinfo=None)
        # Same wall clock the ledger's closed_at is written in, so the ages come
        # out right. Computed once: the set cannot change inside one cycle.
        cooling = self.pf.cooling_pairs(wall_now)

        for row in candidates:
            if self.pf.free_slots <= 0:
                break
            pair = (row["ticker_a"], row["ticker_b"])
            if pair in held:
                continue
            if cooling and cooldown_key(row["ticker_a"], row["ticker_b"]) in cooling:
                continue
            if self.pf.max_per_ticker is not None and (
                    counts.get(row["ticker_a"], 0) >= self.pf.max_per_ticker
                    or counts.get(row["ticker_b"], 0) >= self.pf.max_per_ticker):
                continue

            qa = self.quotes.get(instrument_id(row["ticker_a"]))
            qb = self.quotes.get(instrument_id(row["ticker_b"]))
            if qa is None or qb is None:
                continue
            if (now - qa.ts) > self.stale_seconds or (now - qb.ts) > self.stale_seconds:
                continue
            ma, mb = qa.mid, qb.mid
            if not (ma and mb and ma > 0 and mb > 0):
                continue

            mu    = float(row["mu_at_entry"])
            sigma = float(row["sigma_at_entry"])
            beta  = float(row["beta_at_entry"])
            alpha = float(row["alpha_at_entry"])
            if not (sigma > 0 and np.isfinite(sigma)):
                continue

            entry_spread = math.log(ma) - beta * math.log(mb) - alpha
            fill_z = (entry_spread - mu) / sigma
            bar_z = float(row["z_at_entry"])
            if abs(fill_z) < cfg.MIN_DEVIATION_SIGMA or (fill_z * bar_z) <= 0:
                # Reverted, or flipped sign, between the bar close and the fill.
                # It no longer qualifies; taking it would be entering a trade the
                # rules decline.
                continue

            signal = {
                "entry_spread": entry_spread,
                "mu_at_entry": mu,
                "sigma_at_entry": sigma,
                "z_at_entry": fill_z,
                "beta_at_entry": beta,
                "alpha_at_entry": alpha,
                "theta_at_entry": float(row.get("theta_at_entry") or float("nan")),
                "take_profit_level": entry_spread - cfg.TAKE_PROFIT_PCT * (entry_spread - mu),
            }
            sizing = compute_position_size(
                entry_signal=signal, equity=self.pf.equity,
                capital_frac=self.pf.capital_frac, leverage=self.pf.leverage,
                available_margin=self.pf.available_margin,
                max_notional=self.pf.max_notional,
            )
            if sizing is None or sizing["rejected"]:
                continue

            pos = Position(self.pf.next_trade_num, row["ticker_a"], row["ticker_b"],
                           signal, sizing, wall_now, self.pf.stop_sigma)
            pos.entry_bar_z = bar_z
            self.pf.next_trade_num += 1
            self.pf.open_positions.append(pos)
            held.add(pair)
            counts[row["ticker_a"]] = counts.get(row["ticker_a"], 0) + 1
            counts[row["ticker_b"]] = counts.get(row["ticker_b"], 0) + 1
            opened.append(pos)
            self.opened_this_session.append(pos)
            log(f"OPEN  #{pos.trade_num} {pos.ticker_a}/{pos.ticker_b} "
                f"bar z {bar_z:+.2f} -> fill z {fill_z:+.2f} "
                f"gross {sizing['gross_notional']:.2f} margin {sizing['margin']:.2f}")
        return opened

    # -- persistence ------------------------------------------------------ #

    def persist(self, opened: list, closed: list) -> None:
        if self.dry_run:
            return
        rows = []
        for p in opened:
            rows.append({"event": "open", "trade_num": p.trade_num,
                         "ticker_a": p.ticker_a, "ticker_b": p.ticker_b,
                         "time": p.opened_at, "entry_bar_z": getattr(p, "entry_bar_z", None),
                         "entry_fill_z": p.signal["z_at_entry"],
                         "net_exposure": p.net_exposure,
                         "net_exposure_frac": p.net_exposure_frac,
                         **p.signal, **p.sizing})
        for c in closed:
            rows.append({"event": "close", "time": c["closed_at"], **c})
        cfg.append_ledger(rows)
        cfg.save_portfolio(self.pf)

    def flush_ticks(self) -> None:
        """Append one part file per flush. Never rewrite what is already down.

        The obvious version -- read the day's parquet, concat, write it back --
        is quadratic: by late afternoon it re-reads and re-writes ~20MB every
        sixty seconds, on a shared vCPU. Part files make each flush cost only
        what it actually adds. Read them back with
        pd.read_parquet(TICKS_DIR/'<day>') -- pandas globs a directory of parts.
        """
        if self.dry_run or not self._tick_buffer:
            return
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        day_dir = os.path.join(cfg.TICKS_DIR, day)
        os.makedirs(day_dir, exist_ok=True)
        d = pd.DataFrame(self._tick_buffer)
        self._tick_buffer = []
        d.to_parquet(os.path.join(day_dir, f"part-{int(time.time())}.parquet"),
                     index=False)

    def housekeeping(self) -> None:
        """Drop expired tick days and rotate the logs.

        Tick capture is ~20 instruments at 1 Hz, roughly 20-25MB/day, which is
        7-9GB/year against 11GB free on the VM. It is the one thing this system
        writes that can fill the disk on its own. The ledger is never touched:
        it is small, and equity is re-summed from it on every start.
        """
        if self.dry_run:
            return
        gone = cfg.prune_dated(cfg.TICKS_DIR, cfg.RETAIN_TICK_DAYS)
        if gone:
            log(f"pruned {len(gone)} tick day(s) older than "
                f"{cfg.RETAIN_TICK_DAYS}d: {', '.join(sorted(gone))}")
        rotated = cfg.rotate_logs_in()
        if rotated:
            log(f"rotated at {cfg.LOG_MAX_BYTES // 1024 // 1024}MB: "
                f"{', '.join(rotated)}")

    def positions_snapshot(self) -> dict:
        """Every open position marked to the SAME quotes the stop is watching.

        Deliberately not a fresh REST call. A status view that fetches its own
        prices can disagree with the process that owns the book, and then a
        position reads green on the dashboard while the monitor is closing it.
        This reports exactly what the stop sees, including staleness.
        """
        now = time.time()
        rows = []
        for pos in self.pf.open_positions:
            sig = pos.signal
            entry, sigma = sig["entry_spread"], sig["sigma_at_entry"]
            stop_dist = self.pf.stop_sigma * sigma
            level = entry - pos.direction * stop_dist
            ea, eb = pos.exposure
            row = {
                "trade_num": pos.trade_num,
                "ticker_a": pos.ticker_a, "ticker_b": pos.ticker_b,
                "side": "short spread" if pos.direction < 0 else "long spread",
                "opened_at": pos.opened_at.isoformat(),
                "hours_held": (datetime.now(timezone.utc).replace(tzinfo=None)
                               - pos.opened_at).total_seconds() / 3600.0,
                "beta": sig["beta_at_entry"],
                "r2": sig.get("r2_at_entry"),
                "z_at_entry": sig["z_at_entry"],
                "entry_spread": entry,
                "stop_level": level,
                "take_profit_level": sig["take_profit_level"],
                "gross_notional": pos.sizing["gross_notional"],
                "margin": pos.margin,
                "exposure_a": ea, "exposure_b": eb,
                "net_exposure": pos.net_exposure,
                "net_exposure_frac": pos.net_exposure_frac,
                "blind": self.is_blind(pos, now),
                "tick_age_s": max(
                    (now - q.ts) for q in
                    (self.quotes.get(instrument_id(t)) for t in pos.pair)
                    if q is not None) if all(
                        self.quotes.get(instrument_id(t)) for t in pos.pair) else None,
            }
            # BLIND MEANS NO MARK. _log_prices only asks whether quotes exist,
            # not whether they are recent -- so without the row["blind"] test a
            # position whose legs stopped ticking ten minutes ago would be
            # marked at ten-minute-old prices and read as current. That is the
            # same stale-price mistake evaluate_positions refuses to make when
            # it decides whether to EXIT; the view must not make it either.
            prices = None if row["blind"] else self._log_prices(pos)
            if prices is None:
                # No mark rather than a stale one. A blank is honest; a number
                # from ten minutes ago reads as current and is not.
                row.update(spread=None, z_now=None, unrealized_pnl=None,
                           unrealized_r=None, progress_to_stop=None)
            else:
                spread = pos.current_spread(*prices)
                net, net_pct, r = pos.pnl(spread)
                row.update(
                    spread=spread,
                    z_now=(spread - sig["mu_at_entry"]) / sigma if sigma else None,
                    unrealized_pnl=net, unrealized_pct=net_pct, unrealized_r=r,
                    # How far of the way to the stop this has travelled. 1.0 is
                    # the level; the monitor fires at the first tick past it.
                    progress_to_stop=(pos.direction * (entry - spread)) / stop_dist
                    if stop_dist else None,
                )
            rows.append(row)
        rows.sort(key=lambda x: (x["unrealized_r"] is None, x["unrealized_r"] or 0))
        open_net = sum(r["net_exposure"] for r in rows)
        open_gross = sum(abs(r["exposure_a"]) + abs(r["exposure_b"]) for r in rows)
        return {
            "as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "equity": self.pf.equity,
            "used_margin": self.pf.used_margin,
            "available_margin": self.pf.available_margin,
            "feed_state": self.feed_state,
            "open": len(rows), "max_slots": self.pf.max_slots,
            "unrealized_total": sum(r["unrealized_pnl"] or 0.0 for r in rows),
            "book_net_exposure": open_net,
            "book_gross_exposure": open_gross,
            "book_net_frac": open_net / open_gross if open_gross else 0.0,
            "positions": rows,
        }

    def record_equity(self) -> dict:
        """One row of the equity curve, from the snapshot's own numbers.

        BLIND POSITIONS MAKE unrealized NaN, for the whole book, deliberately.
        A blind leg cannot be marked; carrying its last known value forward
        draws a flat line through an outage, which reads as "nothing happened"
        when the truth is "we could not see". A gap in the chart is a prompt to
        go and look. That is the same reasoning that stops the monitor exiting
        on a stale price.
        """
        snap = self.positions_snapshot()
        blind_n = sum(1 for p in snap["positions"] if p["blind"])
        unmarked = any(p["unrealized_pnl"] is None for p in snap["positions"])
        unreal = float("nan") if unmarked else snap["unrealized_total"]
        row = {
            "ts": snap["as_of"],
            "realized": round(snap["equity"], 6),
            "unrealized": "" if unmarked else round(unreal, 6),
            "total": "" if unmarked else round(snap["equity"] + unreal, 6),
            "open_n": snap["open"], "blind_n": blind_n,
            "feed_state": snap["feed_state"],
        }
        if not self.dry_run:
            cfg.append_equity(row)
        return row

    def write_positions_snapshot(self) -> None:
        if self.dry_run:
            return
        os.makedirs(os.path.dirname(cfg.POSITIONS_PATH), exist_ok=True)
        tmp = cfg.POSITIONS_PATH + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(self.positions_snapshot(), fh, indent=1, default=str)
        os.replace(tmp, cfg.POSITIONS_PATH)

    def heartbeat(self) -> str:
        now = time.time()
        ages = [now - q.ts for q in self.quotes.values()]
        blind = [p.trade_num for p in self.pf.open_positions if self.is_blind(p, now)]
        line = (f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} "
                f"feed={self.feed_state} subs={len(self.subscribed)} "
                f"open={len(self.pf.open_positions)}/{self.pf.max_slots} "
                f"equity={self.pf.equity:.4f} "
                f"max_tick_age={max(ages) if ages else -1:.1f}s "
                f"blind={blind}")
        if not self.dry_run:
            os.makedirs(os.path.dirname(cfg.HEARTBEAT_PATH), exist_ok=True)
            with open(cfg.HEARTBEAT_PATH, "a") as fh:
                fh.write(line + "\n")
            self.write_positions_snapshot()
            self.record_equity()
        return line


# ---------------------------------------------------------------------------
# The live feed. Everything above is socket-free on purpose; this layer only
# turns messages into on_tick calls and keeps the subscription set honest.
# ---------------------------------------------------------------------------

def _f(v):
    """OKX sends numbers as strings, and empty string for 'no quote'."""
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


async def ws_loop(mon: StopMonitor, stop_event: asyncio.Event) -> None:
    import websockets

    failures = 0
    backoff = 1.0
    while not stop_event.is_set():
        try:
            async with websockets.connect(OKX_WS_PUBLIC,
                                          ping_interval=PING_SECONDS,
                                          ping_timeout=PING_SECONDS,
                                          max_queue=4096) as ws:
                failures = 0
                backoff = 1.0
                mon.feed_state = "live"
                mon.subscribed = set()
                log(f"websocket connected — {len(mon.desired_instruments())} "
                    f"instruments wanted")

                while not stop_event.is_set():
                    await _reconcile_subs(ws, mon)
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    except asyncio.TimeoutError:
                        continue        # idle tick, so housekeeping still runs
                    _handle_message(mon, raw)

        except asyncio.CancelledError:
            raise
        except Exception as e:                      # noqa: BLE001 - any drop
            failures += 1
            mon.subscribed = set()
            if failures >= REST_FALLBACK_AFTER_FAILURES:
                # Degrade rather than disappear. A slow stop beats a blind one.
                mon.feed_state = "rest_fallback"
                log(f"websocket failed {failures}x ({e}) — falling back to REST "
                    f"polling every {REST_POLL_SECONDS:.0f}s")
                await _rest_poll_once(mon)
            else:
                log(f"websocket dropped ({e}) — reconnecting in {backoff:.0f}s")
            await asyncio.sleep(backoff)
            backoff = min(RECONNECT_MAX_BACKOFF, backoff * 2)


async def _reconcile_subs(ws, mon: StopMonitor) -> None:
    """Send subscribe/unsubscribe deltas. Never tears the connection down."""
    want = mon.desired_instruments()
    add = want - mon.subscribed
    drop = mon.subscribed - want
    for op, ids in (("subscribe", add), ("unsubscribe", drop)):
        if not ids:
            continue
        args = [{"channel": "tickers", "instId": i} for i in sorted(ids)]
        for i in range(0, len(args), 100):
            await ws.send(json.dumps({"op": op, "args": args[i:i + 100]}))
    mon.subscribed = want


def _handle_message(mon: StopMonitor, raw: str) -> None:
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        return
    if msg.get("event") == "error":
        # A failed subscribe means a position's leg has no feed. Say so loudly:
        # silently treating it as "nothing to report" is the failure mode that
        # leaves a stop unwatched.
        log(f"OKX SUBSCRIBE ERROR {msg.get('code')} {msg.get('msg')} "
            f"— a leg may be unwatched: {msg.get('arg')}")
        return
    if msg.get("arg", {}).get("channel") != "tickers":
        return
    for d in msg.get("data", []):
        inst = d.get("instId")
        if not inst:
            continue
        closed = mon.on_tick(inst, _f(d.get("bidPx")), _f(d.get("askPx")),
                             _f(d.get("last")))
        if closed:
            mon.persist([], closed)


async def _rest_poll_once(mon: StopMonitor) -> None:
    """One ccxt sweep, used only while the socket is down."""
    try:
        import ccxt
        ex = ccxt.okx({"enableRateLimit": True})
        want = {i for i in mon.desired_instruments()}
        tickers = ex.fetch_tickers()
        now = time.time()
        for sym, t in tickers.items():
            inst = sym.replace("/", "-").replace(":USDT", "-SWAP")
            if inst not in want:
                continue
            closed = mon.on_tick(inst, t.get("bid"), t.get("ask"),
                                 t.get("last"), now=now)
            if closed:
                mon.persist([], closed)
    except Exception as e:                          # noqa: BLE001
        log(f"REST fallback also failed ({e}) — the book is BLIND")


async def timer_loop(mon: StopMonitor, stop_event: asyncio.Event) -> None:
    """Slow work: the time stop, the heartbeat, entries, and tick flushes."""
    last_slow = 0.0
    last_beat = 0.0
    last_entry_check = 0.0
    # Starts at now, not 0, so the first pass does not prune before the process
    # has even connected.
    last_housekeeping = time.time()
    while not stop_event.is_set():
        await asyncio.sleep(1.0)
        now = time.time()

        if now - last_slow >= SLOW_TIMER_SECONDS:
            last_slow = now
            closed = mon.evaluate_positions(now, touched=None, check_time_stop=True)
            if closed:
                mon.persist([], closed)
            mon.flush_ticks()

        if now - last_housekeeping >= HOUSEKEEPING_SECONDS:
            last_housekeeping = now
            mon.housekeeping()

        if now - last_beat >= HEARTBEAT_SECONDS:
            last_beat = now
            mon.heartbeat()

        # Entries are driven by the candidates file's mtime, not by a clock, so a
        # late or early scanner cycle is picked up when it actually lands.
        if now - last_entry_check >= 20.0:
            last_entry_check = now
            # Integer nanoseconds, persisted to disk. A float mtime through a
            # 6-decimal format truncates, which made this comparison never match
            # and re-opened the same file every 20 seconds. See
            # book_state.candidates_consumed_ns.
            mtime_ns = cfg.candidates_mtime_ns()
            if mtime_ns == 0 or mtime_ns <= cfg.candidates_consumed_ns():
                continue
            cfg.mark_candidates_consumed(mtime_ns)
            cands = mon.load_candidates()
            if not cands:
                continue
            # Give fresh subscriptions a moment to deliver a first quote before
            # trying to price an entry off them.
            await asyncio.sleep(3.0)
            opened = mon.try_open(cands, time.time())
            if opened:
                mon.persist(opened, [])


def run_replay(mon: StopMonitor, path: str) -> None:
    """Drive the whole exit path from a CSV. No socket, no clock.

    Columns: ts (epoch seconds), inst_id or ticker, bid, ask, last.
    This is how the validator feeds price paths, and how recorded ticks get
    re-run once monitor_ticks/ has accumulated.
    """
    d = pd.read_csv(path)
    if "inst_id" not in d.columns:
        d["inst_id"] = d["ticker"].map(instrument_id)
    for r in d.itertuples(index=False):
        closed = mon.on_tick(r.inst_id, _f(r.bid), _f(r.ask), _f(r.last),
                             now=float(r.ts))
        if closed:
            mon.persist([], closed)
    log(f"replay done — {len(mon.closed_this_session)} closed")


def acquire_lock():
    """One writer per deployment, enforced rather than documented.

    Two monitors against one ledger produce two books that each believe they own
    the equity, and the sizing of every subsequent trade is wrong in both.
    """
    os.makedirs(cfg.DATA_DIR, exist_ok=True)
    fh = open(cfg.LOCK_PATH, "w")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fh.close()
        return None
    fh.write(f"{os.getpid()}\n")
    fh.flush()
    return fh


async def _main_async(mon: StopMonitor) -> None:
    stop_event = asyncio.Event()
    tasks = [asyncio.create_task(ws_loop(mon, stop_event)),
             asyncio.create_task(timer_loop(mon, stop_event))]
    try:
        await asyncio.gather(*tasks)
    except (KeyboardInterrupt, asyncio.CancelledError):
        stop_event.set()
    finally:
        for t in tasks:
            t.cancel()
        mon.flush_ticks()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="watch and report, but persist nothing")
    ap.add_argument("--replay", metavar="CSV",
                    help="drive from a tick file instead of the live socket")
    ap.add_argument("--candidates-path", default=cfg.CANDIDATES_PATH,
                    help="read candidates from here (lets the scanner run elsewhere)")
    ap.add_argument("--confirm-ticks", type=int, default=CONFIRM_TICKS)
    ap.add_argument("--stale-seconds", type=float, default=STALE_SECONDS)
    a = ap.parse_args()

    cfg.CANDIDATES_PATH = a.candidates_path

    lock = None
    if not a.dry_run:
        lock = acquire_lock()
        if lock is None:
            print(f"another stop_monitor holds {cfg.LOCK_PATH} — refusing to start. "
                  f"Two monitors on one ledger produce two books.", file=sys.stderr)
            sys.exit(1)

    pf = cfg.load_portfolio()
    monitor = StopMonitor(pf, dry_run=a.dry_run, confirm_ticks=a.confirm_ticks,
                          stale_seconds=a.stale_seconds)
    log(f"resumed: {len(pf.open_positions)} open, equity {pf.equity:.2f}, "
        f"next trade {pf.next_trade_num}, dry_run={a.dry_run}")

    if a.replay:
        run_replay(monitor, a.replay)
    else:
        try:
            asyncio.run(_main_async(monitor))
        except KeyboardInterrupt:
            log("interrupted — flushing")
            monitor.flush_ticks()
