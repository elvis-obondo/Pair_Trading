# Builder prompt: Hyperliquid build 4 — coin-level event study: does flow trigger a dislocation, and does it explain the return to mu?

Continues build 3 (`[HL-FLOW1]` in NUMBERS.md: flow features at the trigger, windows 30/60 min,
pair-level 60,004-event sample, 0 of 210 cells beat the reference). Read
`docs/HYPERLIQUID_HANDOFF.md` and `CLAUDE.md` first. Do exactly this; nothing else.
Findings that point elsewhere are reported, not acted on.

## Why this build exists (user, 2026-10-15)

Build 3 used the minute data only as two summary windows before the trigger, on a
60k pair sample. The user's view: flow should explain both the dislocation and the
return to mu, the data is the whole Hyperliquid perp market minute by minute, and
all of it should be used. This build (1) uses every coin and every trigger with no
sampling cap, (2) looks at flow over event time (24 h before to 10 h after), (3)
compares triggers with matched non-trigger controls, (4) measures how much of each
move flow explains. Flow and price are mechanically linked on this venue (taker
buying pushes price up), so "flow explains the move" is expected and is NOT the
finding. The finding is whether the TYPE of flow, or the part of the move flow does
not explain, tells reversion.

## Verified facts (2026-10-15, from NUMBERS.md [HL-BUILD2]/[HL-FLOW1] — re-check any you rely on)

- Data on pt-research (laptop has only the 30m bars): 1m and 30m bars and
  `research/hyperliquid/flow/{COIN}.parquet` for 206 coins, 2025-05-25 14:32 to
  2026-10-13. Flow columns: n_trades, taker_buy_usd, taker_sell_usd,
  n_taker_wallets, open_taker_usd, close_taker_usd, open_buy_usd, open_sell_usd,
  close_buy_usd, close_sell_usd, twap_taker_usd (NaN before 2025-07-27 08:00),
  top3_taker_share, liq_forced_long_usd, liq_forced_short_usd, backstop_liq_usd,
  adl_usd; NaN on archive-hole minutes. backstop and ADL are almost always zero
  outside the 2025-10-10 crash: report, do not model.
- 30m panel: 24,305 bars × 206 tickers; BTC and ETH are factor-only (never traded
  as targets). Archive holes: 929 NaN 30m coin-bars, 5 seams where ≥ 50% of coins
  are NaN (list in NUMBERS.md). Segment rule (i) from build 2: split at NaN closes,
  no window or threshold spans one.
- Spread machinery: `rolling_spread_stats(price_a, price_b)` (log prices, 96-bar
  symmetric vol-matched geometry); adaptive trigger in `mkdisloc.py`: fresh
  crossing of |z| above the 99th percentile of the previous 96 |z| (bars i−96..i−1),
  no absolute floor. Frozen geometry at the trigger; mu frozen.
- Target and chance bar from build 3 (`hl3_*` scripts): reach = depth ≥ |z_entry| on
  1-minute closes, no stop, 10 h; chance probability = same path's steps with random
  signs, 50 seeds. Harness, Split, reading rules, pruning rule, permutation null as in
  build 3. Splits unchanged: CUT 2026-05-25; HO1 = held-out days to 2026-08-14,
  HO2 from 2026-08-15; validation = last 20% of fit days.
- Build 3 reuse: normalisation (dollar-scaled quantities ÷ coin's trailing 7-day
  median; ratios not), net-push sign conventions, the look-ahead validator pattern.

## Hard rules

- No look-ahead. Trigger bar label T closes at T+30; "t = 0" is T+30. Anything used as
  a feature, a control match or a threshold uses minutes < t = 0 only. After-trigger
  series (t > 0) are used only in Part C and never as inputs to a decision at t = 0.
- Everything below is fixed before any result is looked at: benchmark, event rule,
  control rule, windows, features, directions, splits. Changing any after a result is a
  plan change: stop and ask. Descriptive profiles are built on all events but TESTED
  only on the held-out halves; fit-period profiles are for display and for fitting the
  Part B impact model, never for choosing a window or feature.
- Memory: one coin at a time, one column at a time, event windows only; 5-minute bins
  outside [−60, +60] min, 1-minute inside. Runs on pt-research via `scripts/gcp_run.sh`;
  the machine must be TERMINATED afterwards. Code Checker reviews each part's code and
  rules before the run.
- Replace, don't accumulate: new modules `coinevents.py`, `eventstudy.py`, etc. under
  `research/dislocation_model/`; do not fork the pair-level code.

## Part A — the event set, controls, and the event-time profiles (Q1: does flow trigger it?)

**A1. Coin-level dislocation.** Benchmark = equal-weight market index of all OTHER live
coins (BTC and ETH included, the coin itself excluded): 30m index log-return at bar t =
mean of the finite 30m log returns of the other coins at t; index level = cumulative sum;
a bar where the coin or fewer than 30 other coins are finite is NaN (segment break).
The coin's spread = `rolling_spread_stats(log price of coin, index level)` (same 96-bar
geometry, same code). Trigger = the adaptive rule, unchanged, per coin, per segment.
Coins: the 204 non-factor coins. NO sampling cap: every trigger. Report the true event
count, per month, per coin (min/median/max), long/short split, and the |z| bands
(< 2, 2–3, ≥ 3). Save the full event table (coin, T, d = sign(z), z, threshold, beta, mu,
sigma, r2, segment id, vol_48 rank, hour, weekday) and the per-event reach, depth and
chance probability on 1-minute closes (matched population report, as build 3).

**A2. Controls.** For every event draw up to 5 control bars from the SAME coin:
(i) matched on the coin's own trailing 48-bar volatility decile (past only), UTC hour of
day ±2 h, and weekday/weekend; (ii) not within ±24 h of any trigger of that coin; (iii)
finite window; control sign d' = sign(z) at the control bar. Control set 1 = these.
Control set 2 = "near-miss": bars of the same coin where |z| ≥ its own previous-96-bar
90th percentile but no fresh crossing of the 99th occurred in the previous 4 bars, same
matching otherwise. Matching uses no outcome and no flow. Report match counts and drop
rates; events with no control are reported, not hidden.

**A3. Flow series per event/control, signed by d** (positive = pushing the coin the way
it dislocated): net taker imbalance (buy − sell)/(buy + sell); forced share on the
pushing side (liq_forced_short_usd if d>0 else liq_forced_long_usd, ÷ taker notional);
opening push share (open_buy if d>0 else open_sell, ÷ taker notional); closing push
share; top-3 share (proxy); wallets per $M (normalised); taker notional ÷ trailing
7-day median; TWAP share (NaN before 2025-07-27). Plus the coin's own residual return
(coin minus β × index, close-to-close) as the price path.

**A4. Pre-registered windows (minutes relative to t = 0):** P1 [−60, 0), P2 [−360, −60),
P3 [−1440, −360), C6 [−360, 0), C24 [−1440, 0). For each of the 8 A3 series × 5 windows,
the events-minus-controls difference (matched, per event, mean over its controls), for
control sets 1 and 2, day-clustered 95% interval, fit period (display) and HO1/HO2
(test). Cells counted before running: 8 × 5 × 2 sets × 2 halves = 160; report expected
false positives. Expected directions (stated now): forced share, taker notional ÷ median,
imbalance and opening push elevated before triggers vs control set 1; versus control set
2 the differences are reported without a sign assumption. A "finding" = the same sign
and an interval excluding zero in both halves. Also draw the average event-time profile
(−1440 to +600 min) of imbalance, forced share and residual price, events vs controls,
as a PNG (plain matplotlib).

## Part B — does the type of flow, or the unexplained part of the move, predict the return? (Q2, Q3)

**B1. Impact model (fit period only).** Pooled regression, coin fixed effects, 30m bars:
coin residual return on the same bar's net signed imbalance and signed forced flow (both
normalised). Frozen coefficients applied everywhere else. At a trigger: `explained_share`
= (flow-predicted residual move over the last 4 bars) ÷ (actual residual move over the
last 4 bars), clipped to [−1, 2]; `unexplained_move` = actual − predicted, in sigma units.
Report the fit-period R² and the coefficients. Coefficients are never refit on
held-out.

**B2. Features at t = 0, long windows** (net, coin-level, same definitions as A3, windows
P1, C6, C24): groups FORCED (forced share, backstop/ADL excluded), OPENCLOSE (opening
push, closing push, ratio), CONCENTRATION (top-3, wallets per $M, TWAP share, as
proxies), VOLUME (taker notional ÷ median), IMPACT (explained_share, unexplained_move),
MARKET (index return over P1/C6/C24, market-wide forced liquidation ÷ its 7-day median,
breadth as in build 3). Expected directions fixed now: forced share → reaches mu more;
opening push → less; closing push → more; IMPACT: larger unexplained_move → reaches mu
more; others two-sided.

**B3. Tests**, exactly the build 3 design: reference (vol_48, vol_48_1m, sigma, |z|) vs
reference + each group alone vs all vs the pruned set, models logistic L1 and LightGBM
depth 1–4, held-out halves separately, flag share at 80% catch, top-20% hit rate,
beyond-chance gap, paired day-clustered intervals, permutation null, pruning rule on
validation, reading rules HELP / SIGNAL / REGIME-DEPENDENT. Count the cells before
running and report expected false positives. Also report the reference's result on
these coin-level events (it may differ from the pair-level gap of −0.097/−0.066).

**B4. The strong-event cut (pre-registered, one extra row per group):** the same group
test restricted to events with (|z| ≥ 3) OR (forced share P1 > 0). Report n; this is
the "signal may live in strong events" check and is not used to choose anything.

## Part C — after the trigger (H5 and the return to mu)

**C1. Descriptive.** Average event-time paths (0 to +600 min) of imbalance, forced share,
opening push and residual price for reverters vs non-reverters (held-out halves, day-
clustered bands), and for the first 60 min after t = 0 split by whether pushing flow
continued (A1 window imbalance > 0), dried up, or flipped.
**C2. Delayed decision test** (the build 3 DELAYED pattern): decision at t = +60 min,
population = events not yet at mu and not past a pre-stated distance (use the same
population rule as DELAYED/DELAYED-V2); reference = distance to mu now + volatility +
the t = 0 reference; add-on = flow features over (0, +60] min (imbalance, forced share,
opening push, volume). Same models, scoring, halves and reading rules. A finding needs
both halves. State the cell count first.

## Review and receipts

- Code Checker ("Code Checker 2"; check `ListAgents`): A1–A3 code and the control rule
  before the event/control build; the A4 and B designs before they run; C before it
  runs; log + NUMBERS.md section + diff before reporting. Fix its findings on bugs,
  look-ahead, mismatched numbers, rules not applied as written, missing receipts. A fix
  that changes a feature, window, control rule or gate verdict goes to the user.
- Be frugal: batch questions into one message, ask only when you cannot proceed, and do
  not message for status. The user's usage limit is close.
- Logs `research/dislocation_model/logs/hl4_*.log`; NUMBERS.md section `[HL-EVENT1]`,
  every number with its log and M/A tag.
- Final report: plain and short (PM-level, numbers first, stats out of the main line):
  event counts; does flow precede triggers (Q1, one line per series); does type of flow
  or the unexplained move predict reversion (Q2/Q3, one line per group, with directions
  checked); after-trigger findings (Q5); the reference's coin-level result; the checker's
  verdict; files changed; cost.
