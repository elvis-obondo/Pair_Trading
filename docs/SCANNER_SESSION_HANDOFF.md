# Handoff: universe scanner build

Written 2026-09-11 at the end of the risk-management session. Branch
`feat/nautilus-backtest-fix`, last commit `98b3732`.

**Start by reading this file, then `docs/HANDOFF.md` for the live system.**

---

## 1. What changed conceptually — read this first

The project was trying to detect cointegration relationships *earlier* so they
could be traded for longer. That goal is no longer what the strategy does, and
it was not a decision so much as a result.

Testing all 31 combinations of the five entry gates at 3-sigma entry found that
**no gate combination beats no gates**, and 25 of the 31 collapse the account to
6-14% of starting equity. The cointegration gate is among the ones that hurt.
The settled configuration therefore applies **no gates at all**.

So the strategy is now: **continuously scan the whole universe for spreads that
have moved far enough to trade, rank them by how fast that spread has been
mean-reverting recently, and take the fastest.** There is still a pairwise
model — a rolling 7-day hedge ratio — but no statistical test of cointegration
anywhere in the entry path.

The earliness question was not solved. It became irrelevant. If you want to
revisit it, `research/reversion_dataset.py`'s output contains 113,460 rows
dated before each pair's first detection (16,929 pairs, median 12 days of
runway, max 71). That asset is unused by the current spec.

---

## 2. The settled configuration

Do not re-derive these. They come from a full grid scored on both splits
(`research/param_stability.py`, `research/param_grid.parquet`).

| parameter | value | live today |
|---|---|---|
| entry | 3.0 sigma | 1.0 |
| take-profit | 1.0 — full reversion to mu | 0.80 |
| stop | 0.5 sigma **further from mu** (exits at 3.5) | 2.5 |
| max hold | 72h | 24h |
| entry gates | none | six |
| day / volume filter | none | n/a |
| candidate ranking | highest mean-reversion speed (theta) | n/a |
| concurrent positions | 10 | 1 |
| sizing | risk a fixed % of equity; size so the stop costs exactly that | fixed $30 x 20x |
| leverage | 20x, an **output** of sizing | 20x, an input |

Measured out of sample: **+0.806% of notional per trade, 8.4% win rate**, about
**9 new positions a day** (~242 a month) drawn from a pool of ~322 daily
candidates. Median 3.20x on a $300 account over 28 days, 5th percentile 0.07x.

### Two unit conversions that will cause bugs if missed

1. **The stop is in 7-day rolling sigma. Live's `stop_sigma` is in stationary
   sigma** (`sigma_ou / sqrt(2*theta)`). Ratio is 2.17x at the median, 1.47 to
   3.67 interquartile. `0.5` rolling is roughly `0.23` stationary. Live
   currently runs 2.5 stationary — about ten times wider. **Do not copy the
   number 0.5 into the live config.**
2. The `sigma` column in `exit_sweep_paths.parquet` is the rolling std;
   `sigma_stationary` in `entry_gates.parquet` is the OU quantity. Both are
   stored unrenamed so nothing silently substitutes one for the other.

---

## 3. What to build, in order

Everything is currently bound to a single hardcoded pair:
`run_trading.py` has `TICKER_A = "API3"` / `TICKER_B = "SOPH"`;
`PairsStrategyConfig` takes exactly `instrument_id_a` and `instrument_id_b`;
`run_backtest.py` has the same two constants.

**Build the position sizer first, not the scanner.** The edge was never the
binding problem — sizing was. A scanner that finds good trades and sizes them
at a flat $600 still carries a 10% chance of monthly ruin.

1. **Position sizer.** `notional = (risk_frac * equity) / stop_pct`, where
   `stop_pct` is the stop distance expressed as a percent of notional. Margin
   is `notional / 20`. Reject the position if posted margin would exceed
   equity. Reference implementation: `simulate()` in `research/risk_sim.py`.
2. **Data layer** for 212 instruments on one clock. `get_price_levels()`
   already returns the full panel; the constraint is memory, not access.
3. **Scanner loop.** Cheap vectorised z-screen across all 22,366 pairs, then
   fit the OU model *only* on what clears 3 sigma. This ordering is what makes
   it tractable — see section 5.
4. **Portfolio manager.** 10 slots, rank waiting candidates by theta, enforce
   total margin <= equity.
5. **Strategy refactor.** `PairsStrategy` holds one pair. Do not instantiate
   22,366 of them. One scanner strategy subscribed to all 212 instruments,
   managing a set of open pair positions.
6. **Portfolio backtest harness.** The current one runs a single pair.

---

## 4. Settled — do not re-litigate

- **Gates do not control risk.** None of 31 combinations at 3 sigma reduces
  ruin. They raise the win rate (15.7% to 21.6%) and lose money anyway, by
  filtering out the rare large winners the edge depends on.
- **Gate 2 (OU fit) is a prerequisite, not an independent gate.** `THE` alone
  selects 2106 rows and so does `OU+THE`; same for `REG` and `PRB`. There are
  four independent gates, not five.
- **Do not sit out volatile days.** Tested both directions. Trading only calm
  days flips every per-trade number positive and cuts the account from 3.73x to
  0.60x while raising ruin. The busy days carry the tail. The only useful
  version is the inverse: trading *only* busy days takes ruin from 11% to 4%.
- **Position count is not a risk control once sizing is right** — 0% ruin from
  1 to 20 concurrent positions under stop-based sizing.
- **Ranking by spread volatility is a trap.** It looks best per-trade (+3.40%
  vs +0.30% random) because payoff scales with sigma, and carries **32% ruin**
  with a 5th percentile of zero. Highest cointegration p-value is the same trap
  diluted: it correlates **-0.223** with per-trade outcome and **+0.387** with
  sigma. Only theta correlates positively with outcome (+0.189).

---

## 5. Compute

Live needs no new hardware. The backtest does.

| step | measured basis | 2 years, 22,366 pairs |
|---|---|---|
| z-screen (vectorised rolling beta/mean/std) | 22K pairs x 72 days in ~90s | ~15-20 min |
| OU fit, candidates only | 1.4 ms per fit | ~235k fits, ~6 min |
| live, per 30-min bar | same | z-screen <1s, ~322 fits, ~0.5s |

The saving comes from screening before fitting: only ~322 pairs a day clear
3 sigma, so the OU model never runs on 22,366 pairs per bar. Dropping the gates
also removes the Monte Carlo reversion probability, which was 85% of the cost.

**The real constraint is memory.** 72 days of candidate rows was 96MB; 730 days
will be ~1GB. This laptop has 8GB and sat at ~200MB free under load — it shut
down three times during this session. Rent a 32GB VM for the backtest; keep
live where it is. If you must run locally, use the sharding pattern in
`research/entry_gates_dataset.py`: stream each shard to disk, skip finished
shards on rerun. It survives being killed.

---

## 6. Open bugs and gaps

- **`7f51ccd` is not deployed to live.** `_mc_reversion_probability` allocated
  an unbounded array; a pair fitting theta=1e-6 requests 26GB. It is fixed
  locally and bounded, but production still has it. It was pushed to the VM and
  then deliberately reverted — live is untouched, and still carries the bug.
- **The VM's `research/` is generally stale** versus local. `check_vm.sh switch`
  only syncs `run_trading.py`.
- **`update_data.sh` reports false "no new bars" warnings** — a diff bug in the
  script, flagged and not fixed.
- **72h is the edge of the horizon grid.** The true optimum may be longer.
  Extend the grid once the longer history is in.
- **`--days` does not extend history backwards.** Use
  `scripts/backfill_history.sh` (written this session); `update_data.sh` only
  goes forward.

---

## 6b. Walk-forward validation — run 2026-09-11, supersedes section 7's pessimism

`research/param_walkforward.py`, nine rolling-origin folds of 60 days across
714 days (3,646,435 candidate rows).

| dimension | mean rho | folds rho>0 | train's pick | cost vs hindsight |
|---|---|---|---|---|
| entry | +0.75 | 89% | 3.5 in 9/9 folds | +0.124 |
| take-profit | +0.84 | 89% | 1.0 in 9/9 | **+0.011** |
| stop | +0.71 | 89% | 0.5 in 9/9 | **+0.021** |
| horizon | -0.39 | 33% | 72 in 7/9 | +0.092 |

**Take-profit 1.0 and stop 0.5 are settled.** Picked unanimously in every fold,
and choosing them from training data rather than hindsight costs 0.011 and
0.021 percent per trade. That is free.

**Two open items:**

- Entry picks 3.5, not the 3.0 in section 2 — and 3.5 is the edge of the grid,
  so it is a boundary, not a located optimum. The 3.0 recommendation came from
  total edge (per-trade x trade count); this walk-forward optimises per-trade
  alone. Extend ENTRY_GRID past 3.5 and decide on total edge.
- Horizon is genuinely unstable (train's ranking anti-predicts test in two
  thirds of folds) and 72 is also a grid edge. Extend HOR_GRID past 72.

Both grids live at the top of `research/param_walkforward.py`.

## 7. The caveat that governs everything above

Every number here comes from **43 training days and 29 test days of a single
quiet quarter** — 2026-06-14 to 2026-09-11, no crash, no sustained bear market.

**This section is superseded by 6b and is kept for the reasoning only.** The
-0.03 rank correlation quoted below was a sample-size artifact: with 714 days
and nine folds the same dimensions come out learnable. Read 6b for the current
position; the lesson worth keeping is that a single split of a short window
cannot distinguish "this parameter is unlearnable" from "this window is too
short to learn anything", and those have opposite implications.

Selection at that sample size is close to guessing, and this is measured rather
than assumed: ranking the six stop levels on train and on test gives a rank
correlation of **-0.03**. Train's best stop came 4th on test.

What survives that: the edge itself (every stop from 0.5 to 1.5 sigma has a
positive test return with the CI excluding zero), and the ruin relationship
(monotone in stop width, and mechanical rather than fitted).

What does not: any specific return figure, and arguably the exact parameter
values.

**The two-year backfill completed on 2026-09-11 at 20:24.** State now:

| | before | after |
|---|---|---|
| span | 89 days | 730 days |
| range | 2026-06-14 to 09-11 | 2024-09-11 to 2026-09-11 |
| bars | 893,746 | 5,322,215 |
| median bars/ticker | 4,201 | 30,404 |

Coverage is ragged, as expected — both legs must exist on the same bars:

| history | tickers | usable pairs |
|---|---|---|
| 90+ days | 204 of 212 | 20,706 |
| 180+ days | 188 | 17,578 |
| 1 year | 141 | 9,870 |
| 1.5 years | 118 | 6,903 |
| 2 years | 91 | 4,095 |

No cutoff needs choosing. `reversion_dataset.build_pair_rows` already does
`dropna()` per pair, so each pair uses its own overlap and short-history tokens
simply contribute fewer days. At 4,095 pairs the 3-sigma pool is still roughly
59 candidates a day against ~9 slots.

### Immediate next step

1. Rebuild `research/exit_sweep_paths.parquet` on the new history.
   **It does not need the cointegration p-value table.**
   `exit_sweep.attach_relationship_age` returns early when the file is absent
   (`if not pvalues_path.exists(): return`), and it only attaches
   `age_days`/`passing`/`p_value` — none of which the settled spec uses. The
   existing table covers only 2026-06-20 to 09-09, and regenerating it would
   mean re-running `coint_survival.py`, which took 54 minutes on 89 days and
   would take 8+ hours on 730. Skip it.
2. Re-run `research/param_stability.py`. Replace the single 60/40 split with
   proper walk-forward folds — 730 days supports roughly a dozen 60-day folds,
   which is what actually answers whether the parameters hold across regimes.
   The -0.03 rank correlation on one split is the thing being re-tested.
3. Re-run `research/signal_ranking.py` to check the theta ranking survives.

Memory: 72 days of candidate rows was 96MB, so 730 days will be ~1GB. Shard it
or run it somewhere with more RAM.
