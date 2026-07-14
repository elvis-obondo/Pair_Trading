# Step 6 — Nautilus Backtesting Integration: Completion Summary

## Overview

Step 6 integrated the research pair-trading signals into Nautilus Trader 1.228.0 for backtesting on the AVAX/LINK pair using OKX perpetual futures (SWAP) contracts, 1-hour bars, and a 30-day rolling data window. The strategy is driven by an Ornstein-Uhlenbeck model fitted to the log-price spread, with position sizing calibrated so a 2.5-sigma adverse move costs exactly 1% of capital. Tasks 0–6 are complete.

## What was built

- **Strategy skeleton (Task 0–1):** `PairsStrategy` subclass of Nautilus `Strategy`; subscribes to dual bar series, syncs bars by timestamp before acting.
- **Entry signal integration (Task 2):** On each synchronized bar pair, calls `generate_entry_signal` over the trailing `min_bars` window; fires a market order list (both legs simultaneously) when all gates pass.
- **Order submission and position sizing (Task 3):** `compute_position_size` determines notional per leg from the OU stationary distribution; quantities are quantized to instrument precision and submitted as a two-leg `OrderList`.
- **Exit signal and position closing (Task 4):** On each bar while a trade is open, calls `generate_exit_signal`; submits a closing `OrderList` on the first exit condition (time stop, adverse move, or take profit).
- **Custom trade recorder (Task 6):** Per-trade metrics are accumulated in `on_order_filled` and written to `trade_log` in `on_stop`; a formatted table and aggregate statistics are printed; the log is serialised to `research/trade_log_dump.json`.
- **Minimum-deviation entry gate (diagnostic fix):** Gate 3 added to `generate_entry_signal`: `abs(S0 - mu) >= min_deviation_sigma * sigma_stationary`, default 1.0. Trade count 16 → 8, loss roughly halved.
- **1.5× reversion-time correction (diagnostic fix):** `expected_reversion_time` changed from `ln(1/f)/theta` to `1.5 * ln(1/f)/theta` based on the reversion-timing probe; the probability-gate tau is unchanged.

## The custom trade recorder (Task 6)

Nautilus's built-in performance statistics treat every order fill as a position event. For a pairs trade, each round-trip generates four fills (two entry, two exit) across two instruments, so Nautilus counts 2 open positions and 2 closed positions per trade. Its Win Rate, Expectancy, and Profit Factor are computed over these per-leg position records, not over logical pairs trades, making them meaningless for evaluation: a strategy with every pairs trade winning can show a 50% win rate because half the per-leg closes are on the short leg.

The custom recorder works at the logical trade level. `on_order_filled` accumulates commission as each leg fills and records entry prices per leg. When both closing legs are confirmed, it computes:

```
realized_pnl_net = (close_px_a - entry_px_a) * qty_a * direction_a
                 + (close_px_b - entry_px_b) * qty_b * direction_b
                 - commission_total
```

and appends one record to `trade_log` with these fields: `trade_num`, `entry_time`, `exit_time`, `hours_held`, `exit_reason`, `entry_spread`, `exit_spread`, `mu_at_entry`, `beta_at_entry`, `alpha_at_entry`, `pnl_pct`, `deviation_sigma`, `commission_total`, `realized_pnl_net`.

`on_stop()` prints a per-trade table, then aggregate statistics broken down by exit reason (count, average hours held, average `pnl_pct`), commission drag, net P&L sum, and a cumulative equity curve list. The full log is written to `research/trade_log_dump.json` for post-hoc analysis.

## Diagnostic findings and fixes

### Minimum-deviation entry gate

The five original gates (cointegration, OU fit validity, theta significance, volatility regime, reversion probability) never checked how far the current spread sat from the long-run mean `mu`. Gate 5, the reversion-probability check, is easiest to satisfy when the spread is near `mu` because the reflection-principle formula approaches its maximum there. This allowed entries with near-zero deviation, where the available P&L move is too small to clear round-trip commission. These trades registered small positive `pnl_pct` values (spread moved in the right direction by a fraction of its entry deviation) but negative `realized_pnl_net` after commission.

Gate 3 was added between the OU-fit validity check and the theta-significance check:

```
abs(S0 - mu) >= min_deviation_sigma * sigma_stationary
```

where `sigma_stationary = sigma / sqrt(2 * theta)` is the OU long-run spread volatility — the same unit used by the position sizer and the adverse-move stop. Default `min_deviation_sigma = 1.0`. Effect: trade count fell from 16 to 8 and aggregate loss roughly halved. The threshold is flagged for empirical sweep; 1.0 was chosen as the natural unit.

### Reversion-time correction

After applying the minimum-deviation gate, `probe_reversion_timing.py` was run on the 8-trade log. It walked a 3× predicted-tau forward window for each time-stopped trade, measuring hours to take-profit. Result: 4 of 7 time-stopped trades did eventually revert to the take-profit level, but the reversion arrived 6–45 hours after the predicted horizon. The OU closed-form tau (`ln(1/f) / theta`) systematically under-predicts realized reversion time on hourly-discrete crypto data by a factor of 1.3×–1.9×.

The time-stop horizon (`expected_reversion_time` in the signal dict, which `generate_exit_signal` reads as `max_hours`) was corrected by a 1.5× multiplier:

```python
expected_reversion_time = 1.5 * np.log(1.0 / f) / params.theta
```

The probability-gate tau (`tau = ln(1/f) / theta` passed to `ou_reversion_probability`) is deliberately not corrected — correcting it there would inflate the analytical probability estimate and could cause false passes on the gate.

## Current results

Final backtest run: AVAX/LINK, OKX SWAP, 1h bars, 30-day window, 1,000 USDT starting capital.

| Metric | Value |
|---|---|
| Total trades completed | 6 |
| take_profit exits | 3 |
| time_stop exits | 3 |
| adverse_move exits | 0 |
| Total commission drag | 6.4216 USDT |
| Total realized_pnl_net | −8.4551 USDT |
| Starting balance | 1,000.0000 USDT |
| Final balance | 991.5449 USDT |

Per-trade breakdown:

| # | Entry | Exit | Hrs | Reason | Net PnL (USDT) | Commission (USDT) |
|---|-------|------|-----|--------|---------------:|------------------:|
| 1 | 2026-05-15 05:00 | 2026-05-16 05:00 | 24.0 | time_stop | −5.9580 | 0.9700 |
| 2 | 2026-05-17 19:00 | 2026-05-19 06:00 | 35.0 | time_stop | −1.5832 | 0.8482 |
| 3 | 2026-05-19 08:00 | 2026-05-19 18:00 | 10.0 | take_profit | −2.3747 | 1.0979 |
| 4 | 2026-05-20 14:00 | 2026-05-21 12:00 | 22.0 | time_stop | −1.3109 | 1.3704 |
| 5 | 2026-05-21 13:00 | 2026-05-22 12:00 | 23.0 | take_profit | −3.5377 | 1.3022 |
| 6 | 2026-05-27 16:00 | 2026-05-29 14:00 | 46.0 | take_profit | +6.3095 | 0.8329 |

## Known limitations and open questions

- **Small sample.** Six completed trades is not enough to draw statistical conclusions. The results are directional only; confidence intervals would span the entire outcome distribution.
- **Structural reward:risk asymmetry.** Position sizing targets a 2.5-sigma stop costing 1% of capital, but the take-profit captures 80% of the entry deviation (roughly 0.8 sigma at 1-sigma entry). This produces an approximate 0.32:1 reward:risk per trade before commission. The asymmetry is structural given the current gate thresholds and take-profit fraction; it has been identified but not addressed.
- **Non-reverting entries.** The reversion-timing probe found that trades 1, 2, and 5 (by original numbering from the probe run) did not reach the take-profit level within 3× the predicted horizon. Whether these represent genuine regime breaks or insufficient holding time is unresolved. Candidate for Step 7 entry-gate refinement or regime-detection work.
- **`run_backtest.py` is not pair-agnostic.** Feather file paths, instrument definitions, and price/size precisions (4 decimal places for price, 1 for size) are hardcoded for AVAX and LINK. Swapping to a different pair requires manual edits throughout the file and risks silent mis-rounding if the new instruments have different tick sizes. Deferred.
- **Static OU fit.** The OU model is fitted once over the full 30-day window at each bar, not recalibrated on a rolling basis as the window advances. In practice, OU parameters (particularly `mu` and `theta`) drift over the 30-day period. Rolling recalibration is the primary scope of Step 7.

## Files

| File | Role |
|---|---|
| `nautilus/pairs_strategy.py` | Nautilus Strategy subclass: entry/exit signal dispatch, order submission, fill tracking, commission accounting, custom trade recorder |
| `nautilus/run_backtest.py` | BacktestEngine configuration: instruments (AVAX/LINK OKX SWAP), 1h bars, 1,000 USDT starting capital, feather data paths, maker/taker fees |
| `research/signal_generator.py` | Gated OU entry signal (6 gates) and exit signal (time_stop / adverse_move / take_profit) |
| `research/ou_model.py` | OU parameter fitting and residual diagnostics (Jarque-Bera, Ljung-Box, theta t-stat) |
| `research/pair_analysis.py` | Spread computation via OLS (beta/alpha), half-life, Hurst exponent, rolling cointegration |
| `research/position_sizer.py` | Position sizing via OU stationary distribution; worst-case stop-out calibrated to 1% of capital |
| `research/trade_diagnostics.py` | Pre-entry cointegration check (168-bar Engle-Granger) and spread volatility regime classifier |
| `research/probe_reversion_timing.py` | Post-hoc reversion timing probe: walks 3× tau forward window on time-stopped trades, measures hours-to-take-profit and closeness to mu |
