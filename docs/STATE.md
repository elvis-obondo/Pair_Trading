# State — crypto pairs trading

The current document. Written 2026-10-06, consolidating `SESSION_HANDOFF`,
`BACKTEST_HANDOFF`, `SCANNER_SESSION_HANDOFF`, `HANDOFF` and
`kalman_changepoint_experiment_spec`, which are now in `attic/docs/`.

Two operational files are still live and are NOT superseded:

    docs/VM_HANDOFF.md     VM state, deploy, retention, dated incident history
    docs/CLOUD_DEPLOY.md   how the VM was built, and the MIN_BARS cold-start incident

Everything below is measured. Where a number is weak or a claim is unverified it
says so. Section 2 is the part that changed most, and it changed against the
project's own previous headline.

---

## 1. The state, in one line

**The spread reverts, the reversion is smaller than the fee at every horizon, and
the one number that said otherwise was a favourable five weeks.**

Measured on 60,000 dislocations over 746 days — the full history, unselected:

    mean move toward the mean at 10h    +0.112 sigma   95% day-clustered [+0.020, +0.206]
    OKX taker round trip                 0.105-0.143 sigma
    horizons where the move clears it    NONE

Reversion is real. The interval excludes zero, and 56.2% of dislocations move
back at all. It is just not big enough to pay for the trade.

---

## 2. The +0.2826 sigma edge was the window, not the strategy

This replaces the previous headline, which read "the edge is real and the fee
takes a third to a half of it." That figure came from 2026-08-26 to 09-29.
Measured against unselected dislocations over the same calendar window:

    population                          n        days    mean move at 10h
    full history                        60,000   746     +0.112  [+0.022, +0.208]
    held-out slice, from 2026-07-18     18,064    79     +0.335  [+0.100, +0.555]
    THE TRADED WINDOW, unselected        7,579    35     +0.356  [+0.084, +0.618]

The traded sample recorded +0.28. Random dislocations in the same five weeks gave
**+0.356** — slightly better. So:

- **the window was favourable**, by about 3x the full-history mean, and
- **the selection added nothing.** Ranking, gating and slot allocation produced a
  result no better than taking dislocations at random over those weeks.

Month by month on the unselected set the sign flips constantly: 2025-01 −0.349,
2025-12 +0.265, 2026-02 −0.280, 2026-08 +0.400, 2026-09 +0.258, 2026-10 +0.982.
Fourteen of twenty-six months are negative. There is no stable level to quote.

**The held-out block is itself a favourable window (+0.335).** That does not
invalidate the predictability tests in section 3 — those ask whether anything
*varies with* the features, not what the level is — but no level measured on the
held-out block should be read as typical.

---

## 3. Direction is closed. Seven independent lines.

All on the same 60,000 dislocations, the same split (41,936 fit / 18,064 held out,
cut 2026-07-18), the held-out block scored once, against a permutation null.

| what was tried | result |
|---|---|
| 18 linear features, every subset | best single +0.144% R2; all 18 together −0.259% |
| 336 raw bars, gradient boosting | R2 −0.002 to −0.013 at every horizon, inside the null |
| 21 engineered window features | same, inside the null |
| 41 external features (which leg moved, market, wave, crowding) | reversion AUC 0.50–0.51, inside the null |
| 62 features combined | no cell clears the gates |
| the SDE's own centre | R2 0.42–0.93%; the unfitted E0 is the best of nine fits |
| the full 2x2x5x3 grid | 33 cells scored, **0 hits**, against 1.7 false positives expected |

A boosted tree over 336 raw bars is a far less constrained function class than
any SDE parameterisation. Nothing it finds means no parameter we could add will
find anything either.

**The unfolded reversion classifier reads AUC 0.59 and is an artifact.**
`sign(z_entry)` alone scores 0.4058 on the same target — 0.5942 inverted. It
recovers the entry sign, not the future. Sign-folded is the primary reading, and
unfolded numbers must be reported next to their sign-only column.

**`|z|` carries nothing.** AUC 0.5101 on predicting full reversion. Dislocation
size is the cleanest null in the project.

---

## 4. What IS predictable: how far it travels, not which way

This is the live finding and the only thing that cleared a gate.

    target: log realised variance over the next 10 hours, held out
    41 external features        26.05% R2
    21 window features          34.40%
    all 62                      36.43%
    external's increment        +2.04pp, CI [+0.49, +3.95]  -- FAILS the 3pp gate

Volatility prediction is strong and it comes from the spread's own window.
External information adds a little and not enough to matter. Rebuilt with the
full-universe wave feature instead of a 400-pair sample, the increment falls to
+1.36pp [−0.15, +3.20] — still a fail, so the verdict does not depend on it.

### And it is NOT a direction signal in disguise

Predicting full reversion looked like a hit: AUC 0.6488 from the volatility
predictor, 0.6533 from the 62-feature tree, both outside the null. It is travel
distance. Scored against the mirror-image target — the spread *widened* by at
least `|z_entry|` — the same predictors give:

    predictor                      FULL    ADVERSE   EITHER    gap
    volatility prediction (v_0)   0.6488   0.6124   0.6647   0.036
    boosted tree, 62 features     0.6533   0.6004   0.6807   0.053

They score as well on "went badly wrong" as on "fully reverted", and **best of
all on "moved far at all."** The target that signal actually answers is EITHER.
That closes the last apparent exception: nothing in this phase predicts direction.

### The volatility number has large headroom from measurement alone

83% of the predictor's spread is estimation noise, not signal. Squared returns are
a pathological variance estimator at nu ≈ 2.7 — the fourth moment barely exists —
and absolute returns cut the noise 2.6x at 335 observations.

    best observable today (48-bar squared returns)      29.47% R2
    same predictor at 1-minute precision, est.          ~79%

**Treat the 79% as an upper bound of unknown tightness.** The decomposition it
comes from also reports a signal-to-signal R2 of exactly 100.0%, which means it
saturated. The direction is trustworthy, the magnitude is not. 1-minute history
exists (`scripts/download_1m.sh`), so this is testable rather than theoretical.

---

## 5. The distribution: only the centre scores, and the centre is empty

    climatology CRPS at 10h              2.531 sigma
    best model                           2.517 = 99.4% of climatology
    the gate                             95%

Decomposed, **dispersion cannot move CRPS.** The band can be anything — ratios
0.38 to 1.33 across nine fits — and CRPS stays within 0.6% of climatology. Only
the centre scores, and the centre needs **9.75% R2 on the 10-hour change** to
reach 95%. The best centre measured delivers 0.1%. Two orders of magnitude.

What the band work did buy, and it is worth keeping:

- a Student-t with nu 2.689 on raw increments beats a gaussian by 57,062 log-lik
  on 361,280 real moves; nu falls to 2.523 on filter innovations
- conditioning on predicted volatility moves nu to 3.087 — thinner, as expected,
  once between-episode heterogeneity leaves the pool
- the mixture (not the point estimate) fixes the tail decile: outside-all drops
  0.35% → 0.14%, decile-10 coverage 66.0% → 72.7%
- coverage by *predicted* volatility is flat across deciles (3.5pp spread). By
  *realised* volatility it spans 33.9pp. The forecast is calibrated; it just
  cannot see which episodes will be violent.
- the largest real 30-minute move is 58 sigma (CORE/TURBO, 2026-07-23) and it is
  **real market behaviour, not a bad print** — 0.21 in log price

---

## 6. The strategy as it stands

Enter at `|z| >= 3.0` on the rolling spread. Stop 1.0 sigma beyond entry. Take
profit at full reversion to mu. 72h time stop, 72h re-entry cooldown after a loss,
10 slots, 5% margin at 20x, $5,000 notional cap, ranked by theta.

`research/rolling_spread.py` is THE geometry definition. scanner, live_scanner,
backtest_screen, signal_generator and dislocation_study all read through it.

Live as of 2026-09-29: `ENTRY_WINDOW_DAYS = 2`, `HEDGE_ESTIMATOR = "ratio"`,
verified in the container. Before that it ran the pre-`0bb61a9` OLS build on a
7-day window, so **every live result before 2026-09-29 came from geometry the
backtests had abandoned.**

**It is beta-hedged, not dollar-neutral, and only 18% of candidates are actually
hedged.** See VM_HANDOFF for the instrumentation added rather than the filter not
added.

**Theta ranks the ten slots and should not.** It claims a 1.09h median half-life.
Actual median retracement at 10h is 0.403 of a ~3.3 sigma dislocation; 18.9% reach
full reversion, and among those that do the median time is 5.5h. Spearman against
actual `|z|` at 13h is +0.047 where a strong negative is needed. Theta also picks
the expensive end of the book: median cost climbs 0.056 → 0.081 monotonically
across nine of ten theta deciles.

---

## 7. What is CLOSED. Do not re-litigate.

| question | verdict | where |
|---|---|---|
| entry gates, all 31 subsets | no subset beats no gates | `e5f494e` |
| the exit rule | closed by exhaustion | earlier sessions |
| lookback 1–7 days | ordering unreadable; 4–5d reliably bad | `aec2bd6` |
| stop width 0.5–5.0 | no optimum; above 2.0 is liquidation-contaminated | `9020cf7`, `440d658` |
| ranking key: theta / r2 / neutrality | no difference; changes turnover, not win rate | `58e0d08` |
| threshold combinations, 149 tercile cells | 1 of top 20 survived a holdout; chance gives 10 | memory |
| cointegration screening | 1.6x enrichment out of sample; no trading edge | `bd379f0`, `091c7f7` |
| theta as a ranker | quantitatively broken, wrong sign | memory |
| **direction, linear and nonlinear** | **closed on seven lines, section 3** | 2026-10-04 |
| **dispersion as a CRPS lever** | **cannot move it; only the centre scores** | section 5 |
| **the SDE's identifiability** | **only `qL+qX` recovers; `k_revert` = 0 in 9 of 9 fits** | NUMBERS.md |

**Win rate is 27–28% no matter what you sort, gate or screen on.** It is set by
barrier placement. Every selection experiment came back flat because there is
nothing to select.

### Claims from the old docs that are now wrong

- **"hedge quality is the only thing that separates reverters"** (r2 +0.309,
  |beta| +0.341, neutrality −0.355). `r2` and `|beta|` are both in the 21-feature
  window set; nothing in that set beats the null on reversion at any horizon.
  Treat the decile gap as a within-window regime marker, not a selector.
- **"the spread does not revert at all."** It reverts weakly and measurably:
  +0.112 sigma at 10h, CI excluding zero, 56.2% revert at all.
- **the $626 labelling band.** Real under OLS, where A-on-B and B-on-A are
  different strategies. The symmetric hedge shipped 2026-09-24 closed it.
  Pre-2026-09-24 single-parameter comparisons still carry it.
- **"taker is breakeven by construction"** and the whole two-levers section. Both
  were built on the withdrawn 0.226 fee and then on the +0.2826 edge. The fee
  correction stands; the edge it was subtracted from does not.

### Two results kept from modules now in `attic/research/`

- **The earliness question is not open, it is irrelevant.** The project once tried
  to detect cointegration relationships sooner so they could be held longer. Gate
  testing closed it: no gate combination beats no gates, and the settled spec has
  no statistical test of cointegration anywhere in the entry path. The asset built
  for it still exists and is unused — `reversion_dataset.py`'s output carries
  113,460 rows dated before each pair's first detection, 16,929 pairs, median 12
  days of runway, max 71. `reversion_analysis.py` was the script that asked whether
  a model could beat the detector on them; direction being closed answers it.
- **Past equity is exactly reconstructable, within the tick retention window.**
  `MTM(t)` = account equity + realised P&L of every close before `t` (from the
  ledger) + unrealised of every position open at `t` (from `monitor_ticks/`, 1 Hz
  bid/ask on both legs). Exact, not estimated, using `Position.pnl` unchanged.
  Past `RETAIN_TICK_DAYS` the raw prices are gone and it cannot reach back — which
  is why the monitor writes the curve forward instead of relying on rebuilding it.
  `backfill_equity.py` did this once for time already elapsed; its window has closed.

---

## 8. Open engine and live divergences

### 8a. `stop_monitor` never calls `evaluate_exits`. Still open.

`Portfolio.evaluate_exits` does liquidation, then `generate_exit_signal`, then
grace/debounce. The live book calls `generate_exit_signal` and `pf._close`
directly and never enters it. **Live is missing both liquidation and
grace/debounce**, not just liquidation.

    liquidation      cannot fire at the live 1.0-sigma stop (0.11 of margin
                     headroom against a 0.0115 stop), so the live book is not
                     mispriced by it today. It is NOT theoretical: the 2026-09-29
                     expansion run at stop 0.5 liquidated 2 positions at -9.93R.
                     Any wider or faster stop reaches it.
    grace/debounce   live runs neither. Any backtest using --grace-minutes or
                     --debounce-minutes describes a book live cannot produce.

**No position is ever wiped in the engine** — margin gates admission only. Wide-stop
backtest results are fantasy for that reason.

### 8b. `validate_exit_tolerance` fails 13/14. Pre-existing, uninvestigated.

`sweep_exits.walk` and `Portfolio.evaluate_exits` are two implementations of one
rule and they disagree on 5 of 300 random paths. Stage 1 finds candidates, stage 2
prices them; if the rules differ then stage 2 answers a different question.
Identical 5 mismatches on the stashed pre-2026-09-29 tree. Nobody has looked at
which is wrong.

### 8c. Execution is structurally unmeasurable on what we have.

Backtest and paper book both fill at the recorded price. Slippage, bid-ask and
maker fill rates cannot be measured on either. **More paper trading will never
improve the cost number. Only real orders will.**

The bid-ask is the one remaining thing that can invert the sign and it is
unmeasured. 7.5bp is ordinary for thin names like WET and SHELL, which this book
trades most and which fail `pair_analysis`' own $450k/day turnover floor.

### 8d. Entries at 30m, exits at 1m.

Consistent with live, so not a divergence. It does mean a candidate that crosses
the threshold and returns inside within a bar is invisible to both. Noted so
nobody reports it as a bug.

---

## 9. Numbers not to re-derive

    MEASURED_STOP_OVERSHOOT = 1.04      confirmed on 316 live stop-outs: p50 1.015x,
                                        mean 1.031x, p95 1.104x, 6.3% past 1.10x.
                                        Slightly conservative. Execution is NOT the problem.
    ROUND_TRIP_COST_FRAC = 0.000993     the OKX TAKER SCHEDULE: 4.965bp per leg, in and
                                        out. Gross already counts both legs. NO bid-ask.
    cost in SIGMA                       = frac*(1+|beta|)/sigma, per trade. NOT a constant:
                                        p5 0.063 to p95 0.233 on the live book, nearly 4x.
                                        Both inputs are known at entry. Never quote one
                                        number without naming the population, or saying
                                        whether the beta factor was applied once.
                                        Applying it twice is how 0.226 happened.
    funding                             0.2% of the fee; cancels between legs. Irrelevant.
    the panel                           36,172 bars x 212 tickers, 22,366 pairs,
                                        2024-09-11 -> 2026-10-04. 212 of 212 tickers have
                                        ONE contiguous finite region. The "holes" are
                                        staggered listing dates, not missing data.
    fresh |z|>=3 crossings              3.45M, ~154 per pair

**The live book is PAPER.** It fills at the recorded price.

---

## 10. Traps that have cost real time

1. **`Position.pnl`'s `net_pct` is flattered by ~0.09%.** It charges the round trip
   as a flat fraction of the spread move; the real cost is `frac*(1+|beta|)` in
   spread units. **Rank on `realized_pnl_net`.** Dollars were never wrong, only
   percentages.
2. **Always pass an explicit `--end-date`.** One partially-formed trailing 30m bar
   silently cuts the universe from 212 tickers to 17.
3. **Hand-run PASS/FAIL validators, never pytest.** `research/validate_*.py`.
4. **Day-clustered CIs.** Episodes cluster in time and share legs. Resample DAYS,
   never trades, and never compare against a pooled band.
5. **Stored-path analysis can only rule things OUT.** It removes slot contention and
   has twice ruled a change in falsely. On the reversion question it gives ~50%
   where the real engine gives 27.57% — optimistic by nearly 2x on that question.
6. **Bars are labelled by OPEN time.** This has bitten the project four times
   (`ac3ac48`, `dislocation_study`, the intrabar walk, `opened_at` in `c287477`).
   A 30m bar labelled T closes at T+30.
7. **Read the invariant block.** It RAISES now, but seven runs once printed
   "duplicate pair open: FOUND — BUG" and exited 0 while a stop sweep was built on
   them. The opposite failure also happened: the entry invariant was hardcoded to
   3.0, so **no run below `--entry 3.0` ever completed in this engine.** An
   invariant that fires on a correct run is as damaging as one that stays quiet on
   a broken one.
8. **A single run is one path.** `--pool-mult 3 --seed N` makes it stochastic. Seed
   spread inside one config was $330–$1,056 on a $300 account.
9. **Compare levels, not deltas.** Refactoring `generate_exit_signal` to compare
   distances travelled is algebraically identical and numerically is not:
   `(0.035 - 0.03) >= 0.005` is FALSE in float64 where `0.035 >= 0.03 + 0.005` is
   TRUE. `validate_exit_signal` tests that exact boundary.
10. **Duplicated analysis harnesses drift and the drift is invisible.** Four copies
    of one harness produced a bootstrap that indexed a full-length target with
    held-out-relative positions. Caught only by an interval excluding its own point
    estimate. There is now one harness: `research/dislocation_model/harness.py`.

---

## 11. The modelling pipeline

    research/dislocation_model/paths.py      where the datasets live. One definition.
    research/dislocation_model/mkdisloc.py   builds the 60,000 dislocations
    research/dislocation_model/envfeat.py    THE feature layer: five environment features
    research/dislocation_model/harness.py    THE harness: split, folding, scorer,
                                             day-clustered bootstrap, permutation null, gates
    research/dislocation_model/REBUILD.md    the exact command for each dataset
    research/dislocation_model/NUMBERS.md    every number of the modelling phase, with
                                             M/A provenance and a WITHDRAWN section
    research/dislocation_model/logs/         saved runs: envfeat, validate_envfeat
    research/datasets/                       ~85MB, not tracked, rebuilt from REBUILD.md
    research/validate_dislocation_harness.py PASS/FAIL: the CI-bug regression test, the
                                             PINNED SCORER ANCHOR, and the whole quality
                                             bar for the feature matrix

**The scorer is pinned to a number as of 2026-10-10.** `harness.fit_predict` and
`harness.ci` are run end to end on a SYNTHETIC target (a fixed function of three
`windows` columns plus seeded noise, carrying no information about `Y`) and the
score and both CI bounds are asserted to 4dp. Before that the scorer had no
numeric test: a change to the val-selection line would have left the validator
printing ALL PASS while voiding comparability with every number in NUMBERS.md.
The anchor is version-sensitive — pinned under sklearn 1.9.1.

**The old feature layer was retired 2026-10-09.** `external.py` (41 external
features) and `wave_full.py` are in `attic/research/`, and `extfeat.npz` /
`wave_full.npz` are deleted. They were built against a 212-ticker / 36,172-bar
panel and the panel now loads 214 / 36,215, so they were stale as well as
superseded by section 3. `harness.window_features` went with them; the three
columns worth keeping (rv48, two, vr) are three lines of numpy over `windows`.

**The current feature matrix is 60,000 x 5**, joined onto the existing
`disloc_meta.parquet` by position and validated rather than scored — there is no
target attached to it yet, by design (section 12). All five columns are in sigma
units; `off_mark` was rescaled on 2026-10-10 because 46.4% of its variance was
between-pair, which a temporal split turns into a pair label. Scaling halved that
to 23.6%.

    vol_48      SCALE     mean |30m spread step|, last 48 bars, in sigma    median 0.407
    vratio      SHAPE     step sd / level sd, last 96 bars, iid = 1         median 1.680
    vol_slope   TIMING    sd(last 16 steps) / sd(prior 32)                  median 1.322
    sandwich    COHESION  leg-high/low spread bound minus close, in sigma   median 0.643
    off_mark    BASIS     hedge-weighted mean |close - mark|, in sigma      median 0.013

Two of those medians say something on their own. **vratio's median of 1.68 means
the typical entry window is 68% choppier than an iid walk** — a long path for
little net displacement, which is what microstructure noise or bid-ask bounce
looks like and is consistent with the step/level ratio work. **vol_slope's median
of 1.32 means volatility was still arriving at entry**, not receding, matching
the finding that sigma rises through 96-99% of episodes. Neither is a prediction;
both are descriptions of the population, and neither has been scored.

The one-off analyses are in `attic/modelling_scratch/` with their logs. Section 3,
4 and 5 are their findings; the scripts are not pipeline and are not expected to
run against a rebuilt dataset without path edits. `attrib`, `horizon`, `leakcheck`
and `robust` had **no saved logs** — their output was terminal-only — and were
re-run on 2026-10-06 to recover it before being quarantined. Those four logs are
new.

---

## 12. The open design question: what is the target?

Do not start building until this is decided. It is the genuinely new question and
it is not answered by anything above.

Everything so far predicted a **scalar**: signed change, reverted yes/no, log
realised variance. All three are closed or settled — the first two by section 3,
the third by section 4 (predictable, and it is travel distance).

"Describe the spread" may mean predicting a **distribution** or a **path**. That is
a different output shape and a different loss, and the choice determines
everything downstream:

- a distribution over the 10h change → CRPS, and section 5 says the centre is the
  only thing that scores and it has 0.1% against a 9.75% gate
- a path over 21 steps → a different loss entirely, and the question becomes
  whether the *shape* carries anything the endpoint does not
- a conditional volatility surface → the one target with measured signal (36.4%)
  and measured headroom (section 4), and the one nothing has tried to exploit

**This is an extension, not a new direction.** `nonlinear.py` and `extscore.py`
already were machine learning: gradient boosting over 336 raw bars and 62
engineered features, held out, against a permutation null. The promoted harness IS
the training harness. The gates, the split, the null and the day-clustered
bootstrap carry over unchanged. Do not build a parallel stack.

---

## 13. How the user wants to work

- Plain language, lead with the answer. Statistics out of the main line.
- One change at a time. Do not fix several things in one pass.
- "Can we test X" means analyse existing data, not write a patch.
- Replace, do not accumulate: rewrite in place, delete orphans, no A/B flags
  unless asked.
- **Stay on the plan.** A finding that points elsewhere is a report, not a
  redirect. Never chain experiments. See `CLAUDE.md`.
- Say plainly when something does not work. This project has been advanced far
  more by falsifying things than by finding them.
