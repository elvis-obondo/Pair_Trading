import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


class PairsStrategyConfig(StrategyConfig, frozen=True):
    instrument_id_a: InstrumentId
    instrument_id_b: InstrumentId
    bar_type_a: str
    bar_type_b: str
    min_bars: int = 720


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
        self.signal_eval_count = 0
        self.signal_fire_count = 0
        self.entry_ts = None
        self.leg_a_order_id = None
        self.leg_b_order_id = None
        self.leg_a_filled = False
        self.leg_b_filled = False
        self.order_submit_count = 0
        self.side_a = None
        self.side_b = None
        self.qty_a = None
        self.qty_b = None
        self.close_submitted = False
        self.close_leg_a_order_id = None
        self.close_leg_b_order_id = None
        self.close_leg_a_filled = False
        self.close_leg_b_filled = False
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
        self.log.info("PairsStrategy started. Subscribed to both bar series.")

    def on_bar(self, bar: Bar) -> None:
        if bar.bar_type == self.bar_type_a:
            self.last_ts_a = bar.ts_event
        elif bar.bar_type == self.bar_type_b:
            self.last_ts_b = bar.ts_event

        if self.last_ts_a != self.last_ts_b:
            return

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

            signal = generate_entry_signal(log_prices_a, log_prices_b)

            if signal is not None:
                self.signal_fire_count += 1

                position_size = compute_position_size(
                    entry_signal=signal,
                    capital=1000.0,
                    risk_budget_pct=0.01,
                    stop_sigma=2.5,
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

                # Single-leg partial fills (one leg fills, other rejected) are
                # unhandled — deferred to live/paper deployment.
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

            hours_elapsed = (bar.ts_event - self.entry_ts) / 1e9 / 3600

            current_log_price_a = np.log(bars_a[0].close.as_double())
            current_log_price_b = np.log(bars_b[0].close.as_double())

            exit_signal = generate_exit_signal(
                current_price_a=current_log_price_a,
                current_price_b=current_log_price_b,
                entry_signal=self.entry_signal,
                hours_elapsed=hours_elapsed,
                stop_sigma=2.5,
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

            close_order_a = self.order_factory.market(
                instrument_id=self.instrument_a.id,
                order_side=OrderSide.BUY if self.side_a == OrderSide.SELL else OrderSide.SELL,
                quantity=self.qty_a,
            )
            close_order_b = self.order_factory.market(
                instrument_id=self.instrument_b.id,
                order_side=OrderSide.BUY if self.side_b == OrderSide.SELL else OrderSide.SELL,
                quantity=self.qty_b,
            )

            self.close_leg_a_order_id = close_order_a.client_order_id
            self.close_leg_b_order_id = close_order_b.client_order_id

            # Single-leg partial fills (one leg fills, other rejected) are
            # unhandled — deferred to live/paper deployment.
            self.submit_order(close_order_a)
            self.submit_order(close_order_b)
            self.close_submitted = True

            self.log.info("CLOSING ORDERS SUBMITTED")
            self.log.info(f"  close_leg_a_order_id: {self.close_leg_a_order_id}")
            self.log.info(f"  close_leg_b_order_id: {self.close_leg_b_order_id}")

    def on_order_filled(self, event: OrderFilled) -> None:
        self.trade_commission_total += event.commission.as_double()

        if (event.client_order_id == self.leg_a_order_id or
                event.client_order_id == self.leg_b_order_id):

            if event.instrument_id == self.instrument_a.id:
                self.leg_a_filled = True
                self.entry_px_a = event.last_px.as_double()
                leg_label = "LEG_A"
            elif event.instrument_id == self.instrument_b.id:
                self.leg_b_filled = True
                self.entry_px_b = event.last_px.as_double()
                leg_label = "LEG_B"
            else:
                return

            self.log.info(f"FILL CONFIRMED: {leg_label}")
            self.log.info(f"  instrument:  {event.instrument_id}")
            self.log.info(f"  order_side:  {event.order_side.name}")
            self.log.info(f"  last_qty:    {event.last_qty.as_double():.4f}")
            self.log.info(f"  last_px:     {event.last_px.as_double():.4f}")
            self.log.info(f"  commission:  {event.commission}")

            if self.leg_a_filled and self.leg_b_filled:
                self.entry_ts = event.ts_event
                self.log.info("TRADE OPEN — both legs confirmed filled")
                self.log.info(f"  entry_ts:    {self.entry_ts}")
                self.log.info(f"  entry_spread:{self.entry_signal['entry_spread']:.6f}")
                self.log.info(f"  mu_at_entry: {self.entry_signal['mu_at_entry']:.6f}")

        # --- CLOSING FILL TRACKING ---
        if (event.client_order_id != self.close_leg_a_order_id and
                event.client_order_id != self.close_leg_b_order_id):
            return

        if event.instrument_id == self.instrument_a.id:
            self.close_leg_a_filled = True
            self.close_px_a = event.last_px.as_double()
            close_leg_label = "CLOSE_LEG_A"
        elif event.instrument_id == self.instrument_b.id:
            self.close_leg_b_filled = True
            self.close_px_b = event.last_px.as_double()
            close_leg_label = "CLOSE_LEG_B"
        else:
            return

        self.log.info(f"CLOSE FILL CONFIRMED: {close_leg_label}")
        self.log.info(f"  instrument: {event.instrument_id}")
        self.log.info(f"  order_side: {event.order_side.name}")
        self.log.info(f"  last_qty:   {event.last_qty.as_double():.4f}")
        self.log.info(f"  last_px:    {event.last_px.as_double():.4f}")
        self.log.info(f"  commission: {event.commission}")

        if self.close_leg_a_filled and self.close_leg_b_filled:
            self.trade_count += 1
            self.log.info("TRADE CLOSED — both closing legs confirmed filled")
            self.log.info(f"  trade_count:  {self.trade_count}")
            self.log.info(f"  exit_reason:  {self.exit_reason}")

            # --- D4: realized_pnl_net from real fill prices, net of commission ---
            direction_a = +1 if self.side_a == OrderSide.BUY else -1
            direction_b = +1 if self.side_b == OrderSide.BUY else -1
            leg_a_pnl = (self.close_px_a - self.entry_px_a) \
                        * self.qty_a.as_double() * direction_a
            leg_b_pnl = (self.close_px_b - self.entry_px_b) \
                        * self.qty_b.as_double() * direction_b
            realized_pnl_net = leg_a_pnl + leg_b_pnl - self.trade_commission_total

            # --- D2: append one record per completed trade ---
            self.trade_log.append({
                "trade_num":        self.trade_count,
                "entry_time":       pd.Timestamp(self.entry_ts, tz="UTC")
                                        .strftime("%Y-%m-%d %H:%M"),
                "exit_time":        pd.Timestamp(event.ts_event, tz="UTC")
                                        .strftime("%Y-%m-%d %H:%M"),
                "hours_held":       (event.ts_event - self.entry_ts) / 1e9 / 3600,
                "exit_reason":      self.exit_reason,
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
            })

            # Clear all trade state
            self.entry_signal = None
            self.entry_ts = None
            self.leg_a_filled = False
            self.leg_b_filled = False
            self.leg_a_order_id = None
            self.leg_b_order_id = None
            self.side_a = None
            self.side_b = None
            self.qty_a = None
            self.qty_b = None
            self.close_submitted = False
            self.close_leg_a_order_id = None
            self.close_leg_b_order_id = None
            self.close_leg_a_filled = False
            self.close_leg_b_filled = False
            self.exit_reason = None
            self.trade_commission_total = 0.0
            self.exit_signal_cache = None
            self.entry_px_a = None
            self.entry_px_b = None
            self.close_px_a = None
            self.close_px_b = None

    def on_stop(self) -> None:
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

        out_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "research", "trade_log_dump.json"
        )
        with open(out_path, "w") as fh:
            json.dump(self.trade_log, fh, indent=2)
        print(f"\n[INFO] Trade log written to {out_path}")
