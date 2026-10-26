# Step 7 — Backtest Revival: 30m Bars, Dynamic Pair Selection, and Leverage-Aware Sizing

## Overview

Step 6 left `nautilus/run_backtest.py` working once, against AVAX/LINK on 1h bars. By this session, the data pipeline had moved to 30m bars by default and the 1h feather files it hardcoded no longer existed on disk — the harness was dead. This step fixes that, and along the way corrects a unit bug in the OU fit that only mattered once bars stopped being hourly, replaces the hardcoded pair with dynamic selection, and reworks position sizing to separate "real account capital" from "per-trade budget" so leverage means something concrete.

## What changed

### 1. theta/sigma unit fix (ou_model.py, signal_generator.py)

`fit_ou()` computed theta from consecutive-bar differences with no time scaling — it was actually "per bar," not "per hour" as every docstring and downstream formula assumed. Harmless at 1h bars (bar = hour), wrong by roughly 2x at 30m bars. Fixed by adding a `bar_hours` parameter that rescales theta (`/ bar_hours`) and sigma (`/ sqrt(bar_hours)`) after fitting; `mu` is unaffected since it's computed from the raw regression before rescaling. `generate_entry_signal` threads `bar_hours` through to `fit_ou`, and also rescales the two 168-bar "7 day" gate windows (cointegration check, volatility regime) so they cover a fixed 7 real days regardless of bar frequency, not a fixed bar count. `pairs_strategy.py`'s `min_bars` was similarly rescaled (360 → 720 at 30m) to preserve the original 15-day OU-fit lookback.

Verified directly against real data: `theta_at_entry` on the fired signals implied a half-life matching `pair_analysis.py`'s independently-computed `half_life_hours` for the same pair — confirms the fix, not just that the script runs.

### 2. Dynamic pair selection, 30m bars (run_backtest.py)

Was hardcoded to AVAX/LINK on 1h feather files that no longer exist. Now:

- Calls `analyze_top_pairs()` + `get_tradeable_pairs()` to rank candidates by cointegration p-value, then filters to futures/futures pairs only (checked against `user_data/normalized/manifest.json`'s `instrument_type` field) — necessary because the harness only builds `CryptoPerpetual` instruments and only OKX-futures tickers have raw OHLCV feather files on disk.
- Picks the top-ranked futures/futures tradeable pair automatically; prints which pair was selected and why.
- Loads 30m bars (`TIMEFRAME = "30m"`), matching the data actually on disk.
- 30-day lookback, unchanged from Step 6.

### 3. Single source of truth for config (pairs_strategy.py, run_backtest.py)

`PairsStrategyConfig` gained `bar_hours`, `capital`, `risk_budget_pct`, and `target_leverage` fields. Previously `capital=1000.0` and implicit hourly-bar assumptions were hardcoded independently in both `pairs_strategy.py` and `run_backtest.py`. All of it now flows from one CONFIG block at the top of `run_backtest.py`.

### 4. Leverage: from decorative to real, and the capital/leverage rework

Discovered mid-session that Nautilus silently defaults `MARGIN` accounts to 10x leverage if `default_leverage` is never passed to `add_venue()` — the backtest had been implicitly leveraged the whole time without that being visible anywhere in the code. Made it explicit via a `LEVERAGE` constant.

Separately, discovered that leverage as configured had zero effect on trade P&L, because `compute_position_size` only ever sized positions from `risk_budget_pct` — the venue leverage setting is just a margin ceiling, not a sizing input. Added a genuine leverage-driven sizing mode to `compute_position_size` (`position_sizer.py`): pass `target_leverage` instead of relying on `risk_budget_pct` and it deploys `target_leverage * capital` in combined notional instead of solving for a fixed dollar-risk-at-stop.

The first implementation of this sized leg A alone as `target_leverage * capital` and stacked leg B on top, uncontrolled — combined with a $100 capital figure that was also (incorrectly) the same number used as the real account balance, this let a single adverse-move trade drive the account to about -$230, deeply negative. Nautilus does not model forced liquidation, so the backtest just kept trading through negative equity instead of getting stopped out the way a real exchange would.

Root cause: `capital` was doing two jobs — real account balance (`Money(CAPITAL, USDT)` in `add_venue`) and per-trade sizing base — with one number. Fixed by splitting it into two constants:

- `CAPITAL` — the real starting account balance.
- `TRADE_CAPITAL` — the per-trade budget: both legs combined, at 1x, before leverage.

`compute_position_size`'s leverage-target mode now splits `target_leverage * capital` between the two legs by `|beta|`, so `leg_a_notional + abs(leg_b_notional) == target_leverage * capital` exactly, regardless of beta's sign. Verified: at `TARGET_LEVERAGE=50`, `TRADE_CAPITAL=$100`, leg notionals summed to exactly $5,000.00 on a real trade.

## Current config (run_backtest.py)

| Constant | Value | Meaning |
|---|---|---|
| `TIMEFRAME` | `"30m"` | Bar interval, matches data on disk |
| `BAR_HOURS` | `0.5` | Real hours per bar, feeds the theta/sigma fix |
| `LOOKBACK_DAYS` | `30` | Backtest window |
| `CAPITAL` | `1000.0` | Real starting account balance |
| `TRADE_CAPITAL` | `100.0` | Per-trade budget (both legs combined, at 1x) |
| `TARGET_LEVERAGE` | `50.0` | Combined notional per trade = `TARGET_LEVERAGE * TRADE_CAPITAL` = $5,000 |
| `LEVERAGE` | `Decimal(75)` | Venue margin ceiling — headroom above `TARGET_LEVERAGE`, not a sizing target |
| `RISK_BUDGET_PCT` | `0.05` | Unused while `TARGET_LEVERAGE` is set; kept for switching back to risk-budget-mode sizing |
| `MIN_BARS` | `720` | OU-fit lookback, rescaled from Step 6's 360-bars-at-1h to preserve 15 real days |

## Result of the fixed pipeline

Auto-selected pair (this run): SNX/WLD, p-value 0.0002, half-life 10.4h. 7 trades over the 30-day window — trade timing and gate outcomes are identical regardless of sizing mode, since sizing doesn't affect which gates fire. At `TARGET_LEVERAGE=50` / `TRADE_CAPITAL=$100` / `CAPITAL=$1000`: net P&L +$117.46 (+11.7%), minimum account balance during the run $772.81 (stayed positive throughout, including through a -$230 single-trade loss on trade 2's adverse-move stop).

## Known open gap — carried forward, not addressed this session

**No liquidation modeling.** The backtest still doesn't force-close a position or reject an order when a loss would breach maintenance margin — it just lets the balance absorb whatever the move costs. The `CAPITAL` / `TRADE_CAPITAL` split gives more real cushion than the earlier $100-does-double-duty setup did, but doesn't eliminate the gap: a bad enough single trade can still, in principle, take the simulated account negative in a way a real OKX account would never be allowed to reach (real exchanges force-liquidate before that point). Explicitly deferred by decision this session ("let the account go negative, deal with that later") — flagged here so it isn't forgotten.

**Also still open, unrelated to this session's changes:**

- `research/run_all.py` remains broken (separate entry point, out of scope this session — see CODEBASE_AUDIT.md).
- Single-leg partial-fill handling remains unimplemented in `pairs_strategy.py` (documented as backtest-acceptable, blocking for paper/live).
- Reward:risk asymmetry (80% take-profit vs 2.5σ stop) untouched.
