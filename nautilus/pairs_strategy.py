import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import csv
import fcntl
import numpy as np
import json
import pandas as pd
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.events import OrderFilled
from research.signal_generator import generate_entry_signal, generate_exit_signal
from research.position_sizer import compute_position_size

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Single, ever-growing ledger for every paper trade this strategy touches,
# across every pair and every run/restart — not per-pair, not per-session.
# TWO rows per trade, both written immediately (not batched at on_stop()):
# one with event="open" the moment both entry legs are confirmed filled, one
# with event="close" the moment both closing legs are confirmed filled. The
# open row exists so a still-open trade is visible in the CSV right away —
# previously nothing showed up until the trade closed, which meant a crashed
# or hung process (or one just taking a while to hit its exit condition)
# looked identical to "never traded" from the CSV's point of view. Both rows
# share the same trade_num so they can be paired up by a reader. See
# TRADE_CSV_FIELDNAMES for the fixed column set both row shapes conform to
# (open rows leave close-only columns blank).
PAPER_TRADES_CSV_PATH = os.path.join(PROJECT_ROOT, "research", "paper_trades.csv")

TRADE_CSV_FIELDNAMES = [
    "trade_num", "event", "instrument_a", "instrument_b",
    "entry_time", "exit_time", "hours_held", "exit_reason",
    "side_a", "side_b",
    "requested_qty_a", "filled_qty_a", "requested_qty_b", "filled_qty_b",
    "entry_px_a", "close_px_a", "entry_px_b", "close_px_b",
    "close_retry_count",
    "entry_spread", "exit_spread",
    "mu_at_entry", "beta_at_entry", "alpha_at_entry", "sigma_at_entry", "theta_at_entry",
    "pnl_pct", "deviation_sigma", "reversion_probability",
    "commission_total", "realized_pnl_net",
]

# Plain, append-only liveness log — separate from the verbose per-run nautilus
# log, so "is this actually alive and receiving fresh data" is one `tail`
# away instead of a process/log inspection each time. One line on start, one
# per bar-sync cycle (i.e. every ~bar_hours while running), one on stop —
# gated behind PairsStrategyConfig.heartbeat_enabled so backtest runs (which
# process thousands of historical bars in seconds) don't write a line per bar.
PAPER_TRADE_HEARTBEAT_PATH = os.path.join(PROJECT_ROOT, "research", "paper_trade_heartbeat.log")


class PairsStrategyConfig(StrategyConfig, frozen=True):
    instrument_id_a: InstrumentId
    instrument_id_b: InstrumentId
    bar_type_a: str
    bar_type_b: str
    min_bars: int = 720
    bar_hours: float = 1.0
    capital: float = 1000.0
    risk_budget_pct: float = 0.01
    target_leverage: float | None = None
    enable_coint_gate: bool = True

    # --- entry/exit geometry -------------------------------------------------
    # Defaults reproduce the behaviour these values were hardcoded at, so an
    # existing run is unchanged unless a caller sets them explicitly.
    #
    # The alternative set below came out of research/entry_exit_sweep.py, which
    # scored 661,465 candidate trades against what prices actually did rather
    # than against the cointegration gate agreeing with itself:
    #     min_deviation_sigma 3.0, take_profit_pct 1.0, stop_sigma 2.0,
    #     max_hold_hours 72
    # Out of sample that set returns +0.250% of notional per trade gross
    # against a measured round-trip commission of 0.099%, where the current
    # defaults lose 0.142% of notional per trade BEFORE any costs. Not promoted
    # to defaults here on purpose -- it wants a Nautilus backtest with real
    # fills and funding first, which this parameterisation exists to enable.
    min_deviation_sigma: float = 1.0   # entry: how far from mu, in stationary sigma
    take_profit_pct: float = 0.80      # exit: fraction of the entry gap to capture
    stop_sigma: float = 2.5            # exit: adverse move from entry, in sigma
    max_hold_hours: float | None = None  # exit: None -> min(model estimate, ceiling)
    force_first_signal: bool = False  # TEST ONLY: bypass entry gates on the first
                                       # evaluated bar so a real (ungated) trade fires
                                       # immediately, using live prices and a real OU
                                       # fit — for smoke-testing order/fill/exit wiring,
                                       # not for actual trading. Fires once, then reverts
                                       # to normal gated behavior for the rest of the run.
    log_trades_to_csv: bool = False  # Append each completed trade to the shared
                                      # PAPER_TRADES_CSV_PATH ledger immediately on
                                      # close. Off by default (backtest runs stay
                                      # unaffected); run_paper_trade.py turns this on.
    max_close_retries: int = 5  # If a closing leg partial-fills, _finalize_close
                                 # submits a fresh reduce_only order for exactly the
                                 # leftover amount, once per bar (~30min cadence),
                                 # up to this many attempts before giving up and
                                 # falling back to the old halt-and-alert behavior.
                                 # Self-healing for the common case; the safety net
                                 # is still there if a leg genuinely never clears.
    max_entry_retries: int = 5  # Same self-healing pattern as max_close_retries,
                                 # applied to entries: nautilus's SimulatedExchange
                                 # can leave a MARKET order PARTIALLY_FILLED forever
                                 # once it's matched all the size available at that
                                 # instant's quote (confirmed live — no config flag
                                 # anywhere makes it fill more than the book showed
                                 # in one shot). Rather than accept whatever partial
                                 # amount filled as "the position", _finalize_entry
                                 # submits a fresh order for exactly the leftover on
                                 # a partial leg, once per bar, up to this many
                                 # attempts — so a trade converges to its full
                                 # intended size (and correct hedge ratio) instead of
                                 # opening undersized on one leg. Only after retries
                                 # are exhausted does it fall back to opening at
                                 # whatever actually filled, logged loudly.
    heartbeat_enabled: bool = False  # Append a line to PAPER_TRADE_HEARTBEAT_PATH on
                                      # start, on every bar-sync cycle, and on stop —
                                      # see that constant's comment. Off by default
                                      # (backtest runs stay unaffected); run_paper_trade.py
                                      # turns this on.
    mc_seed: int = 0  # Seeds the Generator used by Gate 6's Monte Carlo reversion-
                       # probability simulation (see ou_reversion_probability). One
                       # Generator is built from this seed in __init__ and reused
                       # across every generate_entry_signal call for the life of the
                       # strategy instance, so a backtest run is bit-for-bit
                       # reproducible for a given seed instead of drawing fresh
                       # unseeded randomness on every bar.
    subscribe_quote_ticks: bool = False  # Live/paper trading only, no-op in backtest
                                          # (nothing sets this in run_backtest.py, so its
                                          # PairsStrategyConfig never subscribes and
                                          # behavior there is unchanged). A sandbox exec
                                          # client can only fill orders once it's seen a
                                          # bid/ask — bars alone never reach it (bar data
                                          # is published on a different message-bus topic
                                          # shape than the sandbox listens on), but quote
                                          # ticks are. This doesn't change what the
                                          # strategy trades on — signal generation still
                                          # reads bar history from the cache exactly as
                                          # before; this only gives the exec client a
                                          # live price to fill against.
    trade_log_output_path: str | None = None  # Overrides where on_stop() writes the
                                          # per-run trade log JSON (see PAPER_TRADES_CSV_PATH-
                                          # adjacent constant below for the default path this
                                          # falls back to). None (default): unchanged behavior,
                                          # always research/trade_log_dump.json. Set by
                                          # scripts/batch_backtest.py to a unique per-pair temp
                                          # path so multiple pairs in one batch run never
                                          # clobber each other's trade log, and a concurrent
                                          # solo run_backtest.py invocation is unaffected.


class PairsStrategy(Strategy):
    def __init__(self, config: PairsStrategyConfig) -> None:
        super().__init__(config)
        self.bar_type_a = BarType.from_str(config.bar_type_a)
        self.bar_type_b = BarType.from_str(config.bar_type_b)
        self.instrument_a = None
        self.instrument_b = None
        self.last_ts_a = None
        self.last_ts_b = None
        self.entry_signal = None
        self.forced_signal_used = False
        self._rng = np.random.default_rng(config.mc_seed)
        self.signal_eval_count = 0
        self.signal_fire_count = 0
        self.entry_ts = None
        self.leg_a_order_id = None
        self.leg_b_order_id = None
        self.leg_a_filled = False
        self.leg_b_filled = False
        # Running totals across possibly-multiple entry attempts for a single
        # leg (see _finalize_entry's retry logic) — mirrors
        # close_leg_a_closed_qty/notional below, same reason: a retry order's
        # own filled_qty only reflects ITS fills, not what earlier attempts
        # already filled for that leg.
        self.leg_a_filled_qty = 0.0
        self.leg_a_filled_notional = 0.0
        self.leg_b_filled_qty = 0.0
        self.leg_b_filled_notional = 0.0
        self.entry_retry_count = 0
        self.order_submit_count = 0
        self.side_a = None
        self.side_b = None
        self.qty_a = None
        self.qty_b = None
        # qty_a/qty_b get overwritten with ACTUAL filled quantities by
        # _finalize_entry — these preserve what the position sizer originally
        # asked for, purely for the trade-log record (see PAPER_TRADES_CSV_PATH).
        self.requested_qty_a = None
        self.requested_qty_b = None
        self.close_submitted = False
        self.close_leg_a_order_id = None
        self.close_leg_b_order_id = None
        self.close_leg_a_filled = False
        self.close_leg_b_filled = False
        # Running totals across possibly-multiple close attempts for a single
        # leg (see _finalize_close's retry logic) — a leg's current order only
        # reflects its OWN fills, not what earlier retry attempts already
        # closed, so these accumulate the true cumulative picture.
        self.close_leg_a_closed_qty = 0.0
        self.close_leg_a_closed_notional = 0.0
        self.close_leg_b_closed_qty = 0.0
        self.close_leg_b_closed_notional = 0.0
        self.close_retry_count = 0
        self.exit_reason = None
        self.trade_count = 0
        self.trade_log = []
        self.trade_commission_total = 0.0
        self.exit_signal_cache = None
        self.entry_px_a = None
        self.entry_px_b = None
        self.close_px_a = None
        self.close_px_b = None

    def on_start(self) -> None:
        self.instrument_a = self.cache.instrument(self.config.instrument_id_a)
        if self.instrument_a is None:
            self.log.error(
                f"Instrument not found: {self.config.instrument_id_a}"
            )
            self.stop()
            return

        self.instrument_b = self.cache.instrument(self.config.instrument_id_b)
        if self.instrument_b is None:
            self.log.error(
                f"Instrument not found: {self.config.instrument_id_b}"
            )
            self.stop()
            return

        self.subscribe_bars(self.bar_type_a)
        self.subscribe_bars(self.bar_type_b)

        if self.config.subscribe_quote_ticks:
            self.subscribe_quote_ticks(self.config.instrument_id_a)
            self.subscribe_quote_ticks(self.config.instrument_id_b)
            self.log.info(
                "PairsStrategy started. Subscribed to both bar series "
                "and both quote-tick streams (exec client needs quotes to fill)."
            )
        else:
            self.log.info("PairsStrategy started. Subscribed to both bar series.")

        if self.config.heartbeat_enabled:
            self._append_heartbeat("STARTED")

    def on_bar(self, bar: Bar) -> None:
        if bar.bar_type == self.bar_type_a:
            self.last_ts_a = bar.ts_event
        elif bar.bar_type == self.bar_type_b:
            self.last_ts_b = bar.ts_event

        if self.last_ts_a != self.last_ts_b:
            return

        if self.config.heartbeat_enabled:
            self._append_heartbeat("ALIVE")

        # --- BACKSTOP RECONCILIATION ---
        # A tracked leg order that hasn't produced a terminal OrderFilled by
        # the time the next bar arrives has had a full bar interval to
        # resolve. nautilus's SimulatedExchange (which backs both the
        # backtest engine and the live/paper sandbox exec client) can leave
        # a MARKET order PARTIALLY_FILLED forever with no further OrderFilled
        # or OrderCanceled event ever following — confirmed against
        # nautilus_trader==1.228.0 in a live smoke test (SNX leg: 2,190 of
        # 19,035 filled, then never touched again for 17.5 hours; no cancel
        # anywhere in the session). on_order_filled() finalizes opportunistically
        # on each fill event (covers the common same-burst full-fill case);
        # this call is the backstop that stops waiting on an event that may
        # never come and reconciles against whatever the cache actually shows.
        if self.leg_a_order_id is not None:
            self._finalize_entry(force=True)
        if self.close_submitted:
            self._finalize_close(force=True)

        bars_a = self.cache.bars(self.bar_type_a)
        bars_b = self.cache.bars(self.bar_type_b)

        if len(bars_a) < self.config.min_bars or len(bars_b) < self.config.min_bars:
            return

        # --- ENTRY BRANCH ---
        if self.entry_signal is None:
            log_prices_a = np.log([
                b.close.as_double()
                for b in bars_a[:self.config.min_bars][::-1]
            ])
            log_prices_b = np.log([
                b.close.as_double()
                for b in bars_b[:self.config.min_bars][::-1]
            ])

            self.signal_eval_count += 1

            if self.config.force_first_signal and not self.forced_signal_used:
                self.log.warning(
                    "force_first_signal enabled — bypassing entry gates "
                    "(min_deviation/theta_p/regime/prob) for a wiring smoke test"
                )
                signal = generate_entry_signal(
                    log_prices_a, log_prices_b,
                    bar_hours=self.config.bar_hours,
                    enable_coint_gate=False,
                    min_deviation_sigma=0.0,
                    theta_p_threshold=1.0,
                    regime_threshold=float("inf"),
                    prob_threshold=0.0,
                    rng=self._rng,
                )
                if signal is not None:
                    self.forced_signal_used = True
            else:
                signal = generate_entry_signal(
                    log_prices_a, log_prices_b,
                    bar_hours=self.config.bar_hours,
                    enable_coint_gate=self.config.enable_coint_gate,
                    min_deviation_sigma=self.config.min_deviation_sigma,
                    take_profit_pct=self.config.take_profit_pct,
                    rng=self._rng,
                )

            if signal is not None:
                self.signal_fire_count += 1

                position_size = compute_position_size(
                    entry_signal=signal,
                    capital=self.config.capital,
                    risk_budget_pct=self.config.risk_budget_pct,
                    stop_sigma=self.config.stop_sigma,
                    target_leverage=self.config.target_leverage,
                )
                if position_size is None:
                    self.log.warning("Position sizer returned None — skipping signal")
                    return

                if signal['entry_spread'] > signal['mu_at_entry']:
                    self.side_a = OrderSide.SELL
                    self.side_b = OrderSide.BUY
                else:
                    self.side_a = OrderSide.BUY
                    self.side_b = OrderSide.SELL

                real_price_a = np.exp(log_prices_a[-1])
                real_price_b = np.exp(log_prices_b[-1])

                self.qty_a = self.instrument_a.make_qty(
                    position_size['leg_a_notional'] / real_price_a
                )
                self.qty_b = self.instrument_b.make_qty(
                    abs(position_size['leg_b_notional']) / real_price_b
                )
                # Preserved for the trade-log record — _finalize_entry
                # overwrites self.qty_a/self.qty_b with actual filled amounts.
                self.requested_qty_a = self.qty_a
                self.requested_qty_b = self.qty_b

                order_a = self.order_factory.market(
                    instrument_id=self.instrument_a.id,
                    order_side=self.side_a,
                    quantity=self.qty_a,
                )
                order_b = self.order_factory.market(
                    instrument_id=self.instrument_b.id,
                    order_side=self.side_b,
                    quantity=self.qty_b,
                )

                self.leg_a_order_id = order_a.client_order_id
                self.leg_b_order_id = order_b.client_order_id

                # Neither order is trusted as "done" just because an
                # OrderFilled event arrives for it — see _finalize_entry()
                # for why and how completeness/partial-fill quantities are
                # actually determined.
                self.submit_order(order_a)
                self.submit_order(order_b)
                self.order_submit_count += 1

                self.entry_signal = signal

                self.log.info("SIGNAL FIRED — orders submitted")
                self.log.info(f"  entry_spread:            {signal['entry_spread']:.6f}")
                self.log.info(f"  reversion_probability:   {signal['reversion_probability']:.6f}")
                self.log.info(f"  expected_reversion_time: {signal['expected_reversion_time']:.4f} hrs")
                self.log.info(f"  mu_at_entry:             {signal['mu_at_entry']:.6f}")
                self.log.info(f"  sigma_at_entry:          {signal['sigma_at_entry']:.6f}")
                self.log.info(f"  take_profit_level:       {signal['take_profit_level']:.6f}")
                self.log.info(f"  regime_log_ratio:        {signal['regime_log_ratio']:.6f}")
                self.log.info(f"  beta_at_entry:           {signal['beta_at_entry']:.6f}")
                self.log.info(f"  alpha_at_entry:          {signal['alpha_at_entry']:.6f}")
                self.log.info(f"  theta_at_entry:          {signal['theta_at_entry']:.6f}")
                self.log.info(f"  side_a:                  {self.side_a.name}")
                self.log.info(f"  side_b:                  {self.side_b.name}")
                self.log.info(f"  real_price_a:            {real_price_a:.4f}")
                self.log.info(f"  real_price_b:            {real_price_b:.4f}")
                self.log.info(f"  qty_a:                   {self.qty_a}")
                self.log.info(f"  qty_b:                   {self.qty_b}")
                self.log.info(f"  leg_a_notional:          {position_size['leg_a_notional']:.4f}")
                self.log.info(f"  leg_b_notional:          {position_size['leg_b_notional']:.4f}")
                self.log.info(f"  total_deployed:          {position_size['total_deployed']:.4f}")
                self.log.info(f"  fraction:                {position_size['fraction']:.6f}")
                self.log.info(f"  sigma_stationary:        {position_size['sigma_stationary']:.6f}")
                self.log.info(f"  leg_a_order_id:          {self.leg_a_order_id}")
                self.log.info(f"  leg_b_order_id:          {self.leg_b_order_id}")

        # --- EXIT BRANCH ---
        else:
            if self.close_submitted:
                return

            if self.entry_ts is None:
                # Entry hasn't finalized yet (still waiting on a leg fill,
                # or a full bar hasn't passed for the backstop above to have
                # forced a decision) — nothing to evaluate an exit against.
                return

            hours_elapsed = (bar.ts_event - self.entry_ts) / 1e9 / 3600

            current_log_price_a = np.log(bars_a[0].close.as_double())
            current_log_price_b = np.log(bars_b[0].close.as_double())

            exit_signal = generate_exit_signal(
                current_price_a=current_log_price_a,
                current_price_b=current_log_price_b,
                entry_signal=self.entry_signal,
                hours_elapsed=hours_elapsed,
                stop_sigma=self.config.stop_sigma,
                max_hours_override=self.config.max_hold_hours,
            )

            if exit_signal is None:
                return

            self.exit_reason = exit_signal["exit_reason"]
            self.exit_signal_cache = exit_signal

            self.log.info(f"EXIT SIGNAL — {self.exit_reason}")
            self.log.info(f"  exit_reason:    {exit_signal['exit_reason']}")
            self.log.info(f"  current_spread: {exit_signal['current_spread']:.6f}")
            self.log.info(f"  entry_spread:   {exit_signal['entry_spread']:.6f}")
            self.log.info(f"  pnl_pct:        {exit_signal['pnl_pct']:.6f}")
            self.log.info(f"  stop_sigma:     {exit_signal['stop_sigma']:.4f}")
            self.log.info(f"  hours_elapsed:  {hours_elapsed:.2f}")

            # self.qty_a/self.qty_b are the ACTUAL entry-filled quantities
            # (set by _finalize_entry, not the originally-requested size),
            # so these close orders are already sized to the real open
            # position. reduce_only guards against overshoot if that belief
            # is ever stale (e.g. an untracked fill slipped in).
            close_order_a = self.order_factory.market(
                instrument_id=self.instrument_a.id,
                order_side=OrderSide.BUY if self.side_a == OrderSide.SELL else OrderSide.SELL,
                quantity=self.qty_a,
                reduce_only=True,
            )
            close_order_b = self.order_factory.market(
                instrument_id=self.instrument_b.id,
                order_side=OrderSide.BUY if self.side_b == OrderSide.SELL else OrderSide.SELL,
                quantity=self.qty_b,
                reduce_only=True,
            )

            self.close_leg_a_order_id = close_order_a.client_order_id
            self.close_leg_b_order_id = close_order_b.client_order_id

            # Neither closing order is trusted as "done" just because an
            # OrderFilled event arrives for it — see _finalize_close().
            self.submit_order(close_order_a)
            self.submit_order(close_order_b)
            self.close_submitted = True

            self.log.info("CLOSING ORDERS SUBMITTED")
            self.log.info(f"  close_leg_a_order_id: {self.close_leg_a_order_id}")
            self.log.info(f"  close_leg_b_order_id: {self.close_leg_b_order_id}")

    def on_order_filled(self, event: OrderFilled) -> None:
        # NOTE: OrderFilled carries only last_qty (this one fill's size), never
        # a cumulative/remaining quantity — it is NOT proof that the order (or
        # "leg") is fully filled. A single market order can and does produce
        # more than one OrderFilled event (e.g. a multi-tranche fill that
        # completes in one burst), and in live/paper it can also stop after
        # ONE partial event and never produce another — nautilus's
        # SimulatedExchange has no cancel/retry path for an under-filled
        # MARKET order's remainder (confirmed live: a 19,035-unit SNX entry
        # order filled only 2,190 units, then received no further fill or
        # cancel event for the next 17.5 hours). So every event here just
        # logs the tranche and defers the "is this leg actually done?"
        # decision to _finalize_entry()/_finalize_close(), which check the
        # order's real cumulative state via self.cache.order(...).
        self.trade_commission_total += event.commission.as_double()

        if (event.client_order_id == self.leg_a_order_id or
                event.client_order_id == self.leg_b_order_id):
            if event.instrument_id == self.instrument_a.id:
                leg_label = "LEG_A"
            elif event.instrument_id == self.instrument_b.id:
                leg_label = "LEG_B"
            else:
                leg_label = None

            if leg_label:
                self.log.info(f"FILL EVENT: {leg_label}")
                self.log.info(f"  instrument:  {event.instrument_id}")
                self.log.info(f"  order_side:  {event.order_side.name}")
                self.log.info(f"  last_qty:    {event.last_qty.as_double():.4f}")
                self.log.info(f"  last_px:     {event.last_px.as_double():.4f}")
                self.log.info(f"  commission:  {event.commission}")

            self._finalize_entry(force=False)

        if (event.client_order_id == self.close_leg_a_order_id or
                event.client_order_id == self.close_leg_b_order_id):
            if event.instrument_id == self.instrument_a.id:
                close_leg_label = "CLOSE_LEG_A"
            elif event.instrument_id == self.instrument_b.id:
                close_leg_label = "CLOSE_LEG_B"
            else:
                close_leg_label = None

            if close_leg_label:
                self.log.info(f"CLOSE FILL EVENT: {close_leg_label}")
                self.log.info(f"  instrument: {event.instrument_id}")
                self.log.info(f"  order_side: {event.order_side.name}")
                self.log.info(f"  last_qty:   {event.last_qty.as_double():.4f}")
                self.log.info(f"  last_px:    {event.last_px.as_double():.4f}")
                self.log.info(f"  commission: {event.commission}")

            self._finalize_close(force=False)

    def _finalize_entry(self, force: bool) -> None:
        """
        Check whether both entry legs have reached a state we're willing to
        treat as final. Mirrors _finalize_close(): a partial fill does NOT
        get accepted as final on sight — it self-heals by submitting a fresh
        order for exactly the leftover amount on whichever leg is short,
        once per bar, up to config.max_entry_retries attempts, because
        nautilus's SimulatedExchange can leave a MARKET order PARTIALLY_FILLED
        forever with no further OrderFilled or OrderCanceled event ever
        following (confirmed live: a 19,035-unit SNX entry order filled only
        2,190 units, then received nothing more for 17.5 hours; no cancel
        anywhere in the session) — so the ORIGINAL order is never going to
        resolve the rest on its own no matter how long this waits. Only once
        retries are exhausted does it give up and open at whatever actually
        filled, logged loudly. Opens the trade using the ACTUAL cumulative
        filled quantities/prices across every attempt (never the originally-
        submitted requested_qty_a/requested_qty_b, which are preserved
        separately purely for the trade-log record).

        `force=False` (called from on_order_filled) only accepts an order
        that's genuinely closed (FILLED/REJECTED/CANCELED/EXPIRED) as ready
        to evaluate — this catches the common case where a market order
        fully resolves within the same fill burst, without waiting a whole
        bar for it.

        `force=True` (called from on_bar as a backstop) additionally treats a
        still-open PARTIALLY_FILLED order as ready to evaluate once a full
        bar has passed with no further fill event, since nothing else is
        ever going to prompt a decision on it — see the note above.
        """
        if self.leg_a_filled and self.leg_b_filled:
            return  # already finalized

        order_a = self.cache.order(self.leg_a_order_id) if self.leg_a_order_id else None
        order_b = self.cache.order(self.leg_b_order_id) if self.leg_b_order_id else None
        if order_a is None or order_b is None:
            return

        a_ready = order_a.is_closed or (force and order_a.filled_qty.as_double() > 0)
        b_ready = order_b.is_closed or (force and order_b.filled_qty.as_double() > 0)
        if not (a_ready and b_ready):
            return

        this_attempt_a = order_a.filled_qty.as_double()
        this_attempt_b = order_b.filled_qty.as_double()
        total_filled_a = self.leg_a_filled_qty + this_attempt_a
        total_filled_b = self.leg_b_filled_qty + this_attempt_b

        if total_filled_a == 0 or total_filled_b == 0:
            self.log.error(
                "ENTRY FAILED — one leg got zero fill across every attempt "
                f"(leg_a status={order_a.status}, filled={total_filled_a}; "
                f"leg_b status={order_b.status}, filled={total_filled_b}). "
                "Flattening whichever leg did fill and resetting to flat."
            )
            self._flatten_leg(self.instrument_a, self.side_a, self.instrument_a.make_qty(total_filled_a))
            self._flatten_leg(self.instrument_b, self.side_b, self.instrument_b.make_qty(total_filled_b))
            self._reset_entry_state()
            return

        residual_a = self.requested_qty_a.as_double() - total_filled_a
        residual_b = self.requested_qty_b.as_double() - total_filled_b

        if residual_a > 1e-9 or residual_b > 1e-9:
            # Fold this attempt into the running totals before deciding
            # whether to retry or give up — either way it's now accounted
            # for and shouldn't be double-counted on the next pass.
            self.leg_a_filled_qty = total_filled_a
            self.leg_a_filled_notional += order_a.avg_px * this_attempt_a
            self.leg_b_filled_qty = total_filled_b
            self.leg_b_filled_notional += order_b.avg_px * this_attempt_b

            if self.entry_retry_count < self.config.max_entry_retries:
                self.entry_retry_count += 1
                self.log.warning(
                    f"RESIDUAL ON ENTRY, attempt {self.entry_retry_count}/"
                    f"{self.config.max_entry_retries} — retrying the leftover amount. "
                    f"leg_a residual {residual_a:.4f}, leg_b residual {residual_b:.4f}"
                )
                if residual_a > 1e-9:
                    retry_a = self.order_factory.market(
                        instrument_id=self.instrument_a.id,
                        order_side=self.side_a,
                        quantity=self.instrument_a.make_qty(residual_a),
                    )
                    self.leg_a_order_id = retry_a.client_order_id
                    self.submit_order(retry_a)
                else:
                    self.leg_a_filled = True  # this leg is already fully filled
                if residual_b > 1e-9:
                    retry_b = self.order_factory.market(
                        instrument_id=self.instrument_b.id,
                        order_side=self.side_b,
                        quantity=self.instrument_b.make_qty(residual_b),
                    )
                    self.leg_b_order_id = retry_b.client_order_id
                    self.submit_order(retry_b)
                else:
                    self.leg_b_filled = True
                self.log.info(f"  retry_leg_a_order_id: {self.leg_a_order_id}")
                self.log.info(f"  retry_leg_b_order_id: {self.leg_b_order_id}")
                return

            self.log.warning(
                "ENTRY RETRY LIMIT REACHED — opening at the reduced size actually "
                f"filled after {self.entry_retry_count} retry attempt(s), instead of "
                "halting. "
                f"leg_a requested {self.requested_qty_a} filled {total_filled_a:.4f} (residual {residual_a:.4f}); "
                f"leg_b requested {self.requested_qty_b} filled {total_filled_b:.4f} (residual {residual_b:.4f})."
            )
            # Falls through to open at whatever filled — same as the old
            # single-shot behavior, but now only reached after genuinely
            # trying to fill the rest, not on the very first partial.

        # Fully filled — either on the first attempt or after retries closed
        # the gap. avg_px is the notional-weighted average across every
        # attempt, not just the last one. From here on, qty_a/qty_b ARE the
        # real position — close-order sizing and PnL must reconcile against
        # what actually filled, not the signal-time request.
        final_notional_a = self.leg_a_filled_notional + order_a.avg_px * this_attempt_a
        final_notional_b = self.leg_b_filled_notional + order_b.avg_px * this_attempt_b
        self.qty_a = self.instrument_a.make_qty(total_filled_a)
        self.qty_b = self.instrument_b.make_qty(total_filled_b)
        self.entry_px_a = final_notional_a / total_filled_a
        self.entry_px_b = final_notional_b / total_filled_b
        self.entry_ts = self.clock.timestamp_ns()
        self.leg_a_filled = True
        self.leg_b_filled = True

        self.log.info("TRADE OPEN — both legs confirmed filled")
        self.log.info(f"  entry_ts:       {self.entry_ts}")
        self.log.info(f"  qty_a (actual): {self.qty_a}")
        self.log.info(f"  qty_b (actual): {self.qty_b}")
        self.log.info(f"  entry_spread:   {self.entry_signal['entry_spread']:.6f}")
        self.log.info(f"  mu_at_entry:    {self.entry_signal['mu_at_entry']:.6f}")

        if self.config.log_trades_to_csv:
            self._append_trade_to_csv({
                "trade_num": self.trade_count + 1,  # trade_count itself only
                                                     # increments on close — see
                                                     # PAPER_TRADES_CSV_PATH.
                "event": "open",
                "instrument_a": str(self.instrument_a.id),
                "instrument_b": str(self.instrument_b.id),
                "entry_time": pd.Timestamp(self.entry_ts, tz="UTC").strftime("%Y-%m-%d %H:%M"),
                "side_a": self.side_a.name,
                "side_b": self.side_b.name,
                "requested_qty_a": self.requested_qty_a.as_double(),
                "filled_qty_a": self.qty_a.as_double(),
                "requested_qty_b": self.requested_qty_b.as_double(),
                "filled_qty_b": self.qty_b.as_double(),
                "entry_px_a": self.entry_px_a,
                "entry_px_b": self.entry_px_b,
                "entry_spread": self.entry_signal["entry_spread"],
                "mu_at_entry": self.entry_signal["mu_at_entry"],
                "beta_at_entry": self.entry_signal["beta_at_entry"],
                "alpha_at_entry": self.entry_signal["alpha_at_entry"],
                "sigma_at_entry": self.entry_signal["sigma_at_entry"],
                "theta_at_entry": self.entry_signal["theta_at_entry"],
                "deviation_sigma": self.entry_signal["deviation_sigma"],
                "reversion_probability": self.entry_signal["reversion_probability"],
                "commission_total": self.trade_commission_total,
            })

    def _finalize_close(self, force: bool) -> None:
        """
        Mirror of _finalize_entry() for the closing legs. Crucially: if the
        closing fills don't actually cover the full open position, this does
        NOT log TRADE CLOSED and does NOT reset state to flat — doing that
        with real exposure still open is exactly how the original SNX
        leftover short position went undetected.

        Instead, it self-heals: it submits a fresh reduce_only order for
        exactly the leftover amount on whichever leg still has one (never
        touching a leg that already fully closed), and keeps doing that once
        per bar for up to config.max_close_retries attempts — a leg's
        cumulative closed quantity/notional across every attempt is tracked
        separately from any single order's own filled_qty, since after a
        retry the "requested" amount for the new order is only the residual,
        not the original full leg size. Only once retries are exhausted does
        it fall back to the old behavior: log loudly, leave close_submitted
        =True, and permanently short-circuit the EXIT branch for this pair
        until a human resolves the residual position.
        """
        if self.close_leg_a_filled and self.close_leg_b_filled:
            return  # already finalized

        order_a = self.cache.order(self.close_leg_a_order_id) if self.close_leg_a_order_id else None
        order_b = self.cache.order(self.close_leg_b_order_id) if self.close_leg_b_order_id else None
        if order_a is None or order_b is None:
            return

        a_ready = order_a.is_closed or (force and order_a.filled_qty.as_double() > 0)
        b_ready = order_b.is_closed or (force and order_b.filled_qty.as_double() > 0)
        if not (a_ready and b_ready):
            return

        this_attempt_a = order_a.filled_qty.as_double()
        this_attempt_b = order_b.filled_qty.as_double()
        total_closed_a = self.close_leg_a_closed_qty + this_attempt_a
        total_closed_b = self.close_leg_b_closed_qty + this_attempt_b
        residual_a = self.qty_a.as_double() - total_closed_a
        residual_b = self.qty_b.as_double() - total_closed_b

        if residual_a > 1e-9 or residual_b > 1e-9:
            # Fold this attempt into the running totals before deciding
            # whether to retry or give up — either way this attempt's fill
            # is now accounted for and shouldn't be double-counted later.
            self.close_leg_a_closed_qty = total_closed_a
            self.close_leg_a_closed_notional += order_a.avg_px * this_attempt_a
            self.close_leg_b_closed_qty = total_closed_b
            self.close_leg_b_closed_notional += order_b.avg_px * this_attempt_b

            if self.close_retry_count < self.config.max_close_retries:
                self.close_retry_count += 1
                self.log.warning(
                    f"RESIDUAL POSITION on close attempt {self.close_retry_count}/"
                    f"{self.config.max_close_retries} — retrying the leftover amount. "
                    f"leg_a residual {residual_a:.4f}, leg_b residual {residual_b:.4f}"
                )
                if residual_a > 1e-9:
                    retry_a = self.order_factory.market(
                        instrument_id=self.instrument_a.id,
                        order_side=OrderSide.BUY if self.side_a == OrderSide.SELL else OrderSide.SELL,
                        quantity=self.instrument_a.make_qty(residual_a),
                        reduce_only=True,
                    )
                    self.close_leg_a_order_id = retry_a.client_order_id
                    self.submit_order(retry_a)
                else:
                    self.close_leg_a_filled = True  # this leg is already fully closed
                if residual_b > 1e-9:
                    retry_b = self.order_factory.market(
                        instrument_id=self.instrument_b.id,
                        order_side=OrderSide.BUY if self.side_b == OrderSide.SELL else OrderSide.SELL,
                        quantity=self.instrument_b.make_qty(residual_b),
                        reduce_only=True,
                    )
                    self.close_leg_b_order_id = retry_b.client_order_id
                    self.submit_order(retry_b)
                else:
                    self.close_leg_b_filled = True
                self.log.info(
                    f"  retry_close_leg_a_order_id: {self.close_leg_a_order_id}"
                )
                self.log.info(
                    f"  retry_close_leg_b_order_id: {self.close_leg_b_order_id}"
                )
                return

            self.log.error(
                "RESIDUAL POSITION — exit did not fully close the pair after "
                f"{self.close_retry_count} retry attempt(s). "
                f"leg_a requested {self.qty_a} closed {total_closed_a:.4f} (residual {residual_a:.4f}); "
                f"leg_b requested {self.qty_b} closed {total_closed_b:.4f} (residual {residual_b:.4f}). "
                "NOT marking this trade closed and NOT resetting to flat — "
                "check cache.positions_open() for the real exposure and "
                "resolve manually before this strategy will trade again."
            )
            return

        # Fully closed — possibly across multiple retry attempts, so the
        # final close price is the notional-weighted average over all of
        # them, not just whichever order happened to finish it off.
        final_notional_a = self.close_leg_a_closed_notional + order_a.avg_px * this_attempt_a
        final_notional_b = self.close_leg_b_closed_notional + order_b.avg_px * this_attempt_b
        self.close_px_a = final_notional_a / total_closed_a
        self.close_px_b = final_notional_b / total_closed_b
        self.close_leg_a_filled = True
        self.close_leg_b_filled = True

        exit_ts = self.clock.timestamp_ns()
        self.trade_count += 1
        self.log.info("TRADE CLOSED — both closing legs confirmed filled")
        self.log.info(f"  trade_count:  {self.trade_count}")
        self.log.info(f"  exit_reason:  {self.exit_reason}")

        # --- realized_pnl_net from real fill prices/quantities, net of commission ---
        direction_a = +1 if self.side_a == OrderSide.BUY else -1
        direction_b = +1 if self.side_b == OrderSide.BUY else -1
        leg_a_pnl = (self.close_px_a - self.entry_px_a) \
                    * self.qty_a.as_double() * direction_a
        leg_b_pnl = (self.close_px_b - self.entry_px_b) \
                    * self.qty_b.as_double() * direction_b
        realized_pnl_net = leg_a_pnl + leg_b_pnl - self.trade_commission_total

        trade_record = {
            "trade_num":        self.trade_count,
            "event":            "close",
            "instrument_a":     str(self.instrument_a.id),
            "instrument_b":     str(self.instrument_b.id),
            "entry_time":       pd.Timestamp(self.entry_ts, tz="UTC")
                                    .strftime("%Y-%m-%d %H:%M"),
            "exit_time":        pd.Timestamp(exit_ts, tz="UTC")
                                    .strftime("%Y-%m-%d %H:%M"),
            "hours_held":       (exit_ts - self.entry_ts) / 1e9 / 3600,
            "exit_reason":      self.exit_reason,
            "side_a":           self.side_a.name,
            "side_b":           self.side_b.name,
            "requested_qty_a":  self.requested_qty_a.as_double(),
            "filled_qty_a":     self.qty_a.as_double(),
            "requested_qty_b":  self.requested_qty_b.as_double(),
            "filled_qty_b":     self.qty_b.as_double(),
            "entry_px_a":       self.entry_px_a,
            "close_px_a":       self.close_px_a,
            "entry_px_b":       self.entry_px_b,
            "close_px_b":       self.close_px_b,
            "close_retry_count": self.close_retry_count,
            "entry_spread":     self.entry_signal["entry_spread"],
            "exit_spread":      self.exit_signal_cache["current_spread"],
            "mu_at_entry":      self.entry_signal["mu_at_entry"],
            "beta_at_entry":    self.entry_signal["beta_at_entry"],
            "alpha_at_entry":   self.entry_signal["alpha_at_entry"],
            "sigma_at_entry":   self.entry_signal["sigma_at_entry"],
            "theta_at_entry":   self.entry_signal["theta_at_entry"],
            "pnl_pct":          self.exit_signal_cache["pnl_pct"],
            "deviation_sigma":  self.entry_signal["deviation_sigma"],
            "reversion_probability": self.entry_signal["reversion_probability"],
            "commission_total": self.trade_commission_total,
            "realized_pnl_net": realized_pnl_net,
        }
        self.trade_log.append(trade_record)
        if self.config.log_trades_to_csv:
            self._append_trade_to_csv(trade_record)

        # Clear all trade state
        self.entry_signal = None
        self.entry_ts = None
        self.leg_a_filled = False
        self.leg_b_filled = False
        self.leg_a_order_id = None
        self.leg_b_order_id = None
        self.leg_a_filled_qty = 0.0
        self.leg_a_filled_notional = 0.0
        self.leg_b_filled_qty = 0.0
        self.leg_b_filled_notional = 0.0
        self.entry_retry_count = 0
        self.side_a = None
        self.side_b = None
        self.qty_a = None
        self.qty_b = None
        self.requested_qty_a = None
        self.requested_qty_b = None
        self.close_submitted = False
        self.close_leg_a_order_id = None
        self.close_leg_b_order_id = None
        self.close_leg_a_filled = False
        self.close_leg_b_filled = False
        self.close_leg_a_closed_qty = 0.0
        self.close_leg_a_closed_notional = 0.0
        self.close_leg_b_closed_qty = 0.0
        self.close_leg_b_closed_notional = 0.0
        self.close_retry_count = 0
        self.exit_reason = None
        self.trade_commission_total = 0.0
        self.exit_signal_cache = None
        self.entry_px_a = None
        self.entry_px_b = None
        self.close_px_a = None
        self.close_px_b = None

    def _append_trade_to_csv(self, record: dict) -> None:
        """
        Append one row (event="open" or event="close" — see PAPER_TRADES_CSV_PATH)
        to the shared ledger, across every pair and every run/restart this
        strategy is used for, not a per-pair or per-session file.

        Called immediately from _finalize_entry (open) and _finalize_close
        (close), not batched at on_stop(): a force-killed or crashed process
        (this strategy has been restarted plenty of times already) must not
        lose rows for state changes that had already genuinely happened.
        fcntl.flock guards the append in case multiple pair instances ever
        write to this file concurrently in the future.

        Always writes against the fixed TRADE_CSV_FIELDNAMES column set
        (restval="" fills whichever columns `record` doesn't have — e.g. an
        open row has no exit_time/close_px_a/etc. yet), not `record`'s own
        keys, so the two row shapes can't accidentally produce mismatched
        columns under one header.
        """
        os.makedirs(os.path.dirname(PAPER_TRADES_CSV_PATH), exist_ok=True)
        file_exists = os.path.exists(PAPER_TRADES_CSV_PATH) and os.path.getsize(PAPER_TRADES_CSV_PATH) > 0
        with open(PAPER_TRADES_CSV_PATH, "a", newline="") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                writer = csv.DictWriter(fh, fieldnames=TRADE_CSV_FIELDNAMES, restval="")
                if not file_exists:
                    writer.writeheader()
                writer.writerow(record)
                fh.flush()
                os.fsync(fh.fileno())
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        self.log.info(f"Trade {record.get('event')} row appended to {PAPER_TRADES_CSV_PATH}")

    def _append_heartbeat(self, status: str) -> None:
        """Append one line to PAPER_TRADE_HEARTBEAT_PATH — see that constant's
        comment for why this exists separately from the nautilus log. Same
        flock-append pattern as _append_trade_to_csv, same concurrent-write
        safety reason.
        """
        os.makedirs(os.path.dirname(PAPER_TRADE_HEARTBEAT_PATH), exist_ok=True)
        in_trade = self.leg_a_filled and self.leg_b_filled and not self.close_submitted
        bars_a = len(self.cache.bars(self.bar_type_a)) if self.cache.has_bars(self.bar_type_a) else 0
        bars_b = len(self.cache.bars(self.bar_type_b)) if self.cache.has_bars(self.bar_type_b) else 0
        line = (
            f"{pd.Timestamp.now(tz='UTC').strftime('%Y-%m-%dT%H:%M:%SZ')} "
            f"{status:<8} pair={self.instrument_a.id}/{self.instrument_b.id} "
            f"in_trade={in_trade} bars_a={bars_a} bars_b={bars_b}"
        )
        with open(PAPER_TRADE_HEARTBEAT_PATH, "a") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                fh.write(line + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    def _flatten_leg(self, instrument, entry_side, filled_qty) -> None:
        """Best-effort close of a stray single-leg fill (the other leg of an
        entry attempt got zero fill). Not a complete solution to single-leg
        risk — just a safety net so a rejected/zero-filled sibling doesn't
        leave a naked, untracked position sitting open indefinitely."""
        if filled_qty is None or filled_qty.as_double() <= 0:
            return
        close_side = OrderSide.BUY if entry_side == OrderSide.SELL else OrderSide.SELL
        order = self.order_factory.market(
            instrument_id=instrument.id,
            order_side=close_side,
            quantity=filled_qty,
            reduce_only=True,
        )
        self.log.warning(
            f"FLATTENING stray fill: {instrument.id} {close_side.name} {filled_qty}"
        )
        self.submit_order(order)

    def _reset_entry_state(self) -> None:
        """Reset entry-phase state after an aborted (zero-fill-one-leg) entry
        attempt. The close-phase fields are untouched since a close was never
        submitted for an entry that never opened."""
        self.entry_signal = None
        self.entry_ts = None
        self.leg_a_filled = False
        self.leg_b_filled = False
        self.leg_a_order_id = None
        self.leg_b_order_id = None
        self.leg_a_filled_qty = 0.0
        self.leg_a_filled_notional = 0.0
        self.leg_b_filled_qty = 0.0
        self.leg_b_filled_notional = 0.0
        self.entry_retry_count = 0
        self.side_a = None
        self.side_b = None
        self.qty_a = None
        self.qty_b = None
        self.requested_qty_a = None
        self.requested_qty_b = None
        self.entry_px_a = None
        self.entry_px_b = None

    def on_stop(self) -> None:
        if self.config.heartbeat_enabled:
            self._append_heartbeat("STOPPED")

        self.log.info(
            f"PairsStrategy stopped. "
            f"Bars evaluated: {self.signal_eval_count} | "
            f"Signals fired: {self.signal_fire_count} | "
            f"Signals rejected: {self.signal_eval_count - self.signal_fire_count} | "
            f"Orders submitted: {self.order_submit_count} | "
            f"Trades completed: {self.trade_count} | "
            f"Trade open at shutdown: "
            f"{self.leg_a_filled and self.leg_b_filled and not self.close_submitted}"
        )

        tl = self.trade_log
        print("\n" + "=" * 120)
        print("TRADE LOG")
        print("=" * 120)

        if not tl:
            print("No completed trades.")
            print("=" * 120)
            return

        header = (
            f"{'#':>3}  {'entry_time':<16}  {'exit_time':<16}  {'hrs':>6}  "
            f"{'reason':<12}  {'entry_spr':>10}  {'exit_spr':>10}  "
            f"{'mu':>10} {'dev_σ':>7}  {'pnl_pct':>9}  {'comm':>9}  {'pnl_net':>11}"
        )
        print(header)
        print("-" * 120)
        for t in tl:
            print(
                f"{t['trade_num']:>3}  {t['entry_time']:<16}  {t['exit_time']:<16}  "
                f"{t['hours_held']:>6.2f}  {t['exit_reason']:<12}  "
                f"{t['entry_spread']:>10.5f}  {t['exit_spread']:>10.5f}  "
                f"{t['mu_at_entry']:>10.5f}  {t['deviation_sigma']:>7.2f}  {t['pnl_pct']:>9.4f}  "
                f"{t['commission_total']:>9.4f}  {t['realized_pnl_net']:>11.4f}"
            )
        print("=" * 120)

        # ---- Aggregate statistics ----
        n = len(tl)
        reasons = ["take_profit", "time_stop", "adverse_move"]
        hrs = [t["hours_held"] for t in tl]
        pnl_pcts = [t["pnl_pct"] for t in tl]
        comm_sum = sum(t["commission_total"] for t in tl)
        pnl_net_sum = sum(t["realized_pnl_net"] for t in tl)

        print("\nAGGREGATE STATISTICS")
        print("-" * 120)
        print(f"Total trades completed: {n}")

        print("\nBy exit reason (count / % of trades):")
        for r in reasons:
            c = sum(1 for t in tl if t["exit_reason"] == r)
            pct = 100.0 * c / n
            print(f"  {r:<14} {c:>4}   {pct:6.2f}%")

        print("\nHours held (overall):")
        print(f"  avg {np.mean(hrs):8.2f}   min {np.min(hrs):8.2f}   "
              f"max {np.max(hrs):8.2f}")

        print("\nAvg hours held by exit reason:")
        for r in reasons:
            sub = [t["hours_held"] for t in tl if t["exit_reason"] == r]
            if sub:
                print(f"  {r:<14} {np.mean(sub):8.2f}   (n={len(sub)})")
            else:
                print(f"  {r:<14}      n/a   (n=0)")

        print("\nP&L:")
        print(f"  Total commission drag (USDT): {comm_sum:12.4f}")
        print(f"  Total realized_pnl_net (USDT, net of commission): "
              f"{pnl_net_sum:12.4f}")
        print(f"  Net P&L (= total realized_pnl_net): {pnl_net_sum:12.4f}")
        print(f"  Avg pnl_pct (overall): {np.mean(pnl_pcts):8.4f}")

        print("\nAvg pnl_pct by exit reason:")
        for r in reasons:
            sub = [t["pnl_pct"] for t in tl if t["exit_reason"] == r]
            if sub:
                print(f"  {r:<14} {np.mean(sub):8.4f}   (n={len(sub)})")
            else:
                print(f"  {r:<14}      n/a   (n=0)")

        print("\nCumulative realized_pnl_net per trade (equity curve):")
        cum = 0.0
        curve = []
        for t in tl:
            cum += t["realized_pnl_net"]
            curve.append(round(cum, 4))
        print(f"  {curve}")
        print("=" * 120)

        out_path = self.config.trade_log_output_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "research", "trade_log_dump.json"
        )
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w") as fh:
            json.dump(self.trade_log, fh, indent=2)
        print(f"\n[INFO] Trade log written to {out_path}")
