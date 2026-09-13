"""Ten slots, filled best-theta-first, with margin bounded by equity.

WHAT THIS OWNS

The scanner says what is dislocated. This decides what is actually held: which
candidates get a slot, how big each position is, when each one closes, and what
the account did. It is the piece that turns a list of opportunities into a book.

THE RULES, AND WHERE THEY COME FROM

  ten slots            concurrent position cap. Position count is not itself a
                       risk control -- ruin was 0% from 1 to 20 positions once
                       sizing was fixed -- so this is a practical ceiling, not a
                       safety one.
  rank by theta        fastest reverter first. Settled. NaN-theta candidates are
                       ranked LAST but kept: filtering on theta is a different
                       rule and would discard ~59% of the pool.
  margin <= equity     a position whose margin would not fit is skipped and the
                       NEXT candidate is still considered -- a big position must
                       not block a small one that fits.
  one per pair         never two open positions in the same pair at once.
                       Re-entry on a later bar after a close is allowed and is
                       real behaviour.

ON THE EQUITY CURVE

Equity compounds, and the ledger records it, but the compounded multiple is NOT
a result to quote. Percentage-of-equity sizing with no liquidity ceiling grows
notional without bound -- the full-spec walk-forward produced 1.1e11x that way,
arithmetically correct and physically impossible, since a position eventually
exceeds the depth of the pair it trades. Report per-trade net_pct and R
(profit per unit risked); both are immune to compounding. See
docs/SCANNER_SESSION_HANDOFF.md section 6c.

DIFFERENCE FROM risk_sim.simulate()

That shortlists then randomly samples, because a Monte Carlo needs spread in its
distribution -- deterministic top-k makes every path identical and "P(ruin) 0%"
would mean one path survived, not that ruin is unlikely. A real book has no such
need and takes the best available, so fill_slots is deterministic.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

from position_sizer import compute_position_size
from signal_generator import generate_exit_signal

# Round-trip cost across both legs, as a fraction of gross notional. 0.000993 is
# the measured live figure from 7 completed trades (research/risk_sim.py's
# MEASURED_COST), not an assumption -- exit_sweep's 0.0025 is a deliberately
# pessimistic modelling number and they are not interchangeable.
ROUND_TRIP_COST_FRAC = 0.000993


class Position:
    """One open pair trade. Everything needed to close it and to score it."""

    def __init__(self, trade_num, ticker_a, ticker_b, signal, sizing, opened_at,
                 stop_sigma):
        self.trade_num = trade_num
        self.stop_sigma = stop_sigma
        self.ticker_a = ticker_a
        self.ticker_b = ticker_b
        self.signal = signal            # the frozen entry signal; never mutated
        self.sizing = sizing
        self.opened_at = opened_at
        # Short the spread when it sits above its mean, long it when below.
        self.direction = -1.0 if signal["entry_spread"] > signal["mu_at_entry"] else 1.0

    @property
    def margin(self) -> float:
        return self.sizing["margin"]

    @property
    def pair(self) -> tuple[str, str]:
        return (self.ticker_a, self.ticker_b)

    def current_spread(self, price_a: float, price_b: float) -> float:
        """Spread under the coefficients FROZEN at entry, not re-estimated.

        Re-fitting the hedge ratio mid-trade would shift the baseline and make
        P&L accounting inconsistent with the level the stop is measured from.
        """
        return (price_a - self.signal["alpha_at_entry"]
                - self.signal["beta_at_entry"] * price_b)

    @property
    def exposure(self) -> tuple[float, float]:
        """Signed dollar exposure to each leg. Positive is long.

        Derived from pnl(), not asserted alongside it. P&L is
        direction * d(spread) * leg_a_notional, and spread is
        log(A) - beta*log(B) - alpha, so

            dPnL = (direction * N_a) * dlogA  +  (-direction * N_b) * dlogB

        because N_b == beta * N_a. Leg B's side is therefore the OPPOSITE of leg
        A's, scaled by beta. Two consequences worth naming:

          beta == 0   leg B is nothing, and the position is a naked bet on A
          beta  < 0   both legs point the SAME way, and net exposure exceeds
                      either leg -- this is not a hedge, it is a doubling
        """
        d = self.direction
        return d * self.sizing["leg_a_notional"], -d * self.sizing["leg_b_notional"]

    @property
    def net_exposure(self) -> float:
        """Dollars of one-way market exposure a 'market-neutral' position carries.

        Equals direction * leg_a_notional * (1 - beta). Zero ONLY at beta == 1.
        """
        ea, eb = self.exposure
        return ea + eb

    @property
    def net_exposure_frac(self) -> float:
        """net_exposure over gross. 0 is dollar-neutral, +/-1 fully directional."""
        ea, eb = self.exposure
        gross = abs(ea) + abs(eb)
        return (ea + eb) / gross if gross > 0 else float("nan")

    def pnl(self, exit_spread: float) -> tuple[float, float, float]:
        """(net dollars, net percent of notional, R) for closing here.

        net_pct and R follow risk_sim's definitions exactly so the two are
        directly comparable: net_pct is the spread move as a percent, net of
        costs on the same base, and R divides it by the planned stop distance.
        """
        move = self.direction * (exit_spread - self.signal["entry_spread"])
        gross = move * self.sizing["leg_a_notional"]
        cost = ROUND_TRIP_COST_FRAC * self.sizing["gross_notional"]
        net_pct = (move - ROUND_TRIP_COST_FRAC) * 100.0
        stop_pct = 100.0 * self.signal["sigma_at_entry"] * self.stop_sigma
        r = net_pct / stop_pct if stop_pct > 0 else float("nan")
        return gross - cost, net_pct, r


class Portfolio:
    """A book of up to max_slots pair positions."""

    def __init__(self, equity: float = 300.0, max_slots: int = 10,
                 capital_frac: float = 0.05, leverage: float = 20.0,
                 stop_sigma: float = 0.5, max_hold_hours: float = 72.0,
                 max_per_ticker: int | None = None,
                 stop_fill_overshoot: float | None = None,
                 max_notional: float | None = None):
        self.starting_equity = float(equity)
        self.equity = float(equity)
        self.max_slots = max_slots
        self.capital_frac = capital_frac
        self.leverage = leverage
        self.stop_sigma = stop_sigma
        self.max_hold_hours = max_hold_hours
        # None = the settled spec, which puts no limit on how many open
        # positions may share a leg. Worth knowing what that permits: a single
        # token dislocated against the whole universe can take most of the book,
        # which is a concentrated bet on that token rather than a spread book.
        self.max_per_ticker = max_per_ticker
        # COUNTERFACTUAL MODE, off by default. When True an adverse-move exit is
        # booked at exactly the stop level instead of where the spread actually
        # was when the breach was detected.
        #
        # This is the assumption research/exit_sweep.py scored every settled
        # parameter under (STOP_SLIP = 1.0), and it has been measured false:
        # across 9,704 stop-outs in three independent 6-month windows, ZERO
        # filled at or inside the level -- median overshoot 1.53x, mean 2.07x.
        # So a run with this on does not estimate what the account would do. It
        # measures the edge with execution removed, which is a different and
        # still useful quantity: the gap between the two IS the execution cost.
        # None == book the spread that actually occurred. The LIVE path must
        # always be None: the monitor books real fills and an assumed one here
        # would silently invent P&L. Backtests pass a measured multiple.
        self.stop_fill_overshoot = stop_fill_overshoot
        self.max_notional = max_notional
        self.open_positions: list[Position] = []
        self.closed: list[dict] = []
        self.next_trade_num = 1

    # -- state ------------------------------------------------------------ #

    @property
    def used_margin(self) -> float:
        return sum(p.margin for p in self.open_positions)

    @property
    def free_slots(self) -> int:
        return self.max_slots - len(self.open_positions)

    @property
    def available_margin(self) -> float:
        return self.equity - self.used_margin

    def _ticker_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for p in self.open_positions:
            counts[p.ticker_a] = counts.get(p.ticker_a, 0) + 1
            counts[p.ticker_b] = counts.get(p.ticker_b, 0) + 1
        return counts

    # -- exits ------------------------------------------------------------ #

    def evaluate_exits(self, prices: dict, now) -> list[dict]:
        """Close every open position whose exit condition has fired.

        Runs BEFORE fill_slots on each bar, so a slot freed this bar can be
        reused this bar -- which is what a live scanner would do.
        """
        closed = []
        still_open = []
        for pos in self.open_positions:
            pa, pb = prices.get(pos.ticker_a), prices.get(pos.ticker_b)
            if pa is None or pb is None or not (np.isfinite(pa) and np.isfinite(pb)):
                # A leg with no price this bar cannot be marked or closed. Hold
                # it rather than guessing a fill.
                still_open.append(pos)
                continue
            hours = (now - pos.opened_at).total_seconds() / 3600.0
            ex = generate_exit_signal(
                current_price_a=float(pa), current_price_b=float(pb),
                entry_signal=pos.signal, hours_elapsed=hours,
                stop_sigma=self.stop_sigma, max_hold_hours=self.max_hold_hours,
            )
            if ex is None:
                still_open.append(pos)
                continue
            overshoot = float("nan")
            if (self.stop_fill_overshoot is not None
                    and ex["exit_reason"] == "adverse_move"):
                # Book it `overshoot` stop-distances past entry, in the adverse
                # direction. direction is -1 when short the spread (adverse =
                # spread rises), so the level sits at entry - direction*distance
                # in both cases and overshoot scales that distance.
                #
                # overshoot = 1.00  perfect fill, never observed
                # overshoot = 1.04  MEASURED live, tick-watched (book_state)
                # overshoot = 1.53  what 30-minute bar-close checking produced
                overshoot = float(self.stop_fill_overshoot)
                stop_distance = self.stop_sigma * pos.signal["sigma_at_entry"]
                ex = dict(ex)
                ex["current_spread"] = (pos.signal["entry_spread"]
                                        - pos.direction * stop_distance * overshoot)
            closed.append(self._close(pos, ex, now, hours, overshoot))
        self.open_positions = still_open
        return closed

    def _close(self, pos: Position, ex: dict, now, hours: float,
               fill_overshoot: float = float("nan")) -> dict:
        net, net_pct, r = pos.pnl(ex["current_spread"])
        # Recomputed from the realized total, never `equity += pnl` -- the same
        # discipline PairsTradingActor._recompute_equity uses, so a rounding
        # drift cannot accumulate silently across hundreds of trades.
        self.closed.append({
            "trade_num": pos.trade_num,
            "ticker_a": pos.ticker_a, "ticker_b": pos.ticker_b,
            "opened_at": pos.opened_at, "closed_at": now,
            "hours_held": hours, "exit_reason": ex["exit_reason"],
            "entry_spread": pos.signal["entry_spread"],
            "exit_spread": ex["current_spread"],
            "mu_at_entry": pos.signal["mu_at_entry"],
            "sigma_at_entry": pos.signal["sigma_at_entry"],
            "z_at_entry": pos.signal["z_at_entry"],
            "theta_at_entry": pos.signal["theta_at_entry"],
            # Needed to reconstruct the spread path bar by bar after the fact.
            # Without them a closed trade cannot be re-walked to see WHERE a
            # stop actually filled versus where it was placed.
            "beta_at_entry": pos.signal["beta_at_entry"],
            "alpha_at_entry": pos.signal["alpha_at_entry"],
            "leg_a_notional": pos.sizing["leg_a_notional"],
            "leg_b_notional": pos.sizing["leg_b_notional"],
            "gross_notional": pos.sizing["gross_notional"],
            "margin": pos.margin,
            "notional_capped": pos.sizing.get("notional_capped", False),
            "realized_pnl_net": net, "net_pct": net_pct, "r": r,
            # Hedge quality, carried onto every row so "was this actually a pair
            # trade" is answerable from the ledger alone.
            "r2_at_entry": pos.signal.get("r2_at_entry", float("nan")),
            "net_exposure": pos.net_exposure,
            "net_exposure_frac": pos.net_exposure_frac,
            # Marked per row so a ledger can never be read later as measured
            # when the fill was modelled. NaN means the spread that actually
            # occurred was used; a number is the multiple that was assumed.
            "stop_fill_overshoot": fill_overshoot,
        })
        self.equity = self.starting_equity + sum(c["realized_pnl_net"] for c in self.closed)
        return self.closed[-1]

    # -- entries ---------------------------------------------------------- #

    def fill_slots(self, candidates: pd.DataFrame, now) -> list[Position]:
        """Take the best candidates that fit, in rank order.

        `candidates` must already be ranked -- scanner.scan() returns it sorted
        by theta descending with NaN last. This does not re-sort, so the ranking
        rule lives in exactly one place.
        """
        opened = []
        if candidates is None or not len(candidates):
            return opened
        held = {p.pair for p in self.open_positions}
        counts = self._ticker_counts()

        for row in candidates.itertuples(index=False):
            if self.free_slots <= 0:
                break
            pair = (row.ticker_a, row.ticker_b)
            if pair in held:
                continue
            if self.max_per_ticker is not None and (
                    counts.get(row.ticker_a, 0) >= self.max_per_ticker
                    or counts.get(row.ticker_b, 0) >= self.max_per_ticker):
                continue

            signal = {f: getattr(row, f) for f in (
                "entry_spread", "mu_at_entry", "sigma_at_entry", "z_at_entry",
                "beta_at_entry", "alpha_at_entry", "theta_at_entry",
                "take_profit_level")}
            sizing = compute_position_size(
                entry_signal=signal, equity=self.equity,
                capital_frac=self.capital_frac, leverage=self.leverage,
                available_margin=self.available_margin,
                max_notional=self.max_notional,
            )
            if sizing is None:
                continue
            if sizing["rejected"]:
                # Skip, do not break: every position is the same size under this
                # rule, so a rejection here means the book is full on margin and
                # no later candidate would fit either -- but that stops being
                # true the moment sizing varies, and a `break` would then
                # silently starve the book.
                continue

            pos = Position(self.next_trade_num, row.ticker_a, row.ticker_b,
                           signal, sizing, now, self.stop_sigma)
            self.next_trade_num += 1
            self.open_positions.append(pos)
            held.add(pair)
            counts[row.ticker_a] = counts.get(row.ticker_a, 0) + 1
            counts[row.ticker_b] = counts.get(row.ticker_b, 0) + 1
            opened.append(pos)
        return opened

    # -- reporting -------------------------------------------------------- #

    def summary(self) -> str:
        if not self.closed:
            return f"0 closed | {len(self.open_positions)} open | equity {self.equity:.2f}"
        d = pd.DataFrame(self.closed)
        by = d.exit_reason.value_counts().to_dict()
        return (f"{len(d)} closed | {len(self.open_positions)} open | "
                f"mean net_pct {d.net_pct.mean():+.3f}% | mean R {d.r.mean():+.3f} | "
                f"win {(d.realized_pnl_net > 0).mean()*100:.1f}% | {by}")

    def concentration(self) -> pd.Series:
        """How many open positions each ticker appears in. Watch this."""
        return pd.Series(self._ticker_counts()).sort_values(ascending=False)
