# Handoff — making the backtest accurate and live-faithful

Paste this into a new session. Everything below is measured, not assumed. Where a
number is weak or a claim is unverified, it says so.

The general project handoff is `docs/SESSION_HANDOFF.md` (strategy, edge, what is
closed). The VM state is `docs/VM_HANDOFF.md`. **This file is only about whether
the backtest tells the truth and whether live does what the backtest said.**

---

## 1. What this session is for

Two questions, in this order:

1. **Is the backtest arithmetically and structurally correct?**
2. **Does the live path do the same thing the backtest did?**

They are different jobs. The second one is where the known holes are.

Branch is `feat/nautilus-backtest-fix`. **The name is stale.** Nautilus is retired
(`research/retired_nautilus_paper/`) and the current engine deliberately does not
use it — a 212-instrument Nautilus engine would materialise ~5.3M Bar objects. Do
not go looking for Nautilus work.

---

## 2. State in one line

**The dollar accounting has always been right. The divergences are in which code
path runs live, and in percentage/sigma columns derived after the fact.**

Three things were found wrong on 2026-09-29 and all three were in reporting or
invariants, not in P&L. See section 5. That is the pattern to expect: the engine
computes money correctly and then describes itself inaccurately.

---

## 3. THE WORK LIST — known backtest/live divergences

### 3a. `stop_monitor` never calls `evaluate_exits`. THE BIG ONE.

`Portfolio.evaluate_exits` does three things in order: liquidation check, then
`generate_exit_signal`, then grace/debounce tolerance. The live book
(`research/stop_monitor.py:302`) calls `generate_exit_signal` and then `pf._close`
directly and **never enters `evaluate_exits` at all.**

So live is missing **both** liquidation **and** grace/debounce. The existing
handoff only names liquidation; it is actually two behaviours.

What that costs today:

    liquidation      provably cannot fire at the live 1.0-sigma stop (0.11 of
                     margin headroom against a 0.0115 stop). So the live book is
                     not currently mispriced by it.
    grace/debounce   live runs neither. The backtest can. Any backtest run with
                     --grace-minutes or --debounce-minutes describes a book the
                     live system cannot produce.

**Liquidation is NOT theoretical.** The expansion run on 2026-09-29 (stop 0.5,
11,300 trades) liquidated 2 positions at mean -9.93R. First time it has fired in
any backtest. So the path works, and any strategy with a wider or faster stop
reaches it.

Fixing 3a is the single highest-value change in this session.

### 3b. The engine's grace/debounce disagrees with the sweep's.

`research/validate_exit_tolerance.py` fails **13/14**: "300 random paths x (grace,
debounce) agree exactly -> 5 mismatches FAIL".

Its own docstring says why this matters: `sweep_exits.walk` and
`Portfolio.evaluate_exits` are two implementations of one rule, "and the whole
study rests on them agreeing -- stage 1 finds the candidates, stage 2 prices them,
and if the two rules differ then stage 2 is not confirming stage 1, it is answering
a different question."

**This is pre-existing and uninvestigated.** Verified on the stashed pre-2026-09-29
tree: identical 5 mismatches. Nobody has looked at which of the two is wrong.

### 3c. Neither the backtest nor the paper book can measure execution.

Both fill at the recorded price. That makes slippage, bid-ask and maker fill rates
**structurally unmeasurable** on either. More paper trading will never improve the
cost number. Only real orders will.

The bid-ask is the one remaining thing that can invert the strategy's sign and it
is genuinely unmeasured. A 7.5bp spread is ordinary for thin names like WET and
SHELL, which this book trades most and which fail `pair_analysis`' own $450k/day
turnover floor. The old "fee 0.569, net -0.286, INVERTED" row was computed in
withdrawn units (see 5b) and must be re-derived before anyone repeats it.

### 3d. Entries are only evaluated at 30-minute bars; exits at 1 minute.

`--exit-check-minutes 1` walks exits intrabar while entries stay on the 30m grid.
That is what live does too, so it is consistent — but it means a candidate that
crosses the threshold and comes back inside within a bar is never seen by either.
Not a divergence. Noted so nobody reports it as one.

---

## 4. What the backtest already models correctly — do not spend time here

    stop overshoot      MEASURED_STOP_OVERSHOOT = 1.04, and it is CONFIRMED on 316
                        live stop-outs: p50 1.015x, p75 1.034x, p90 1.074x,
                        p95 1.104x, mean 1.031x, only 6.3% past 1.10x. Slightly
                        conservative. Execution is NOT the problem.
    the cost constant   ROUND_TRIP_COST_FRAC = 0.000993 of GROSS is correct.
                        4.965bp taker on each leg, in and out; gross already counts
                        both legs, so it is 2 x 4.965bp. Contains NO bid-ask.
    dollar P&L          never wrong. `realized_pnl_net` is correct in both books.
    funding             0.2% of the fee and cancels between legs. Irrelevant.
    liquidation path    asserted in `3e63313`, including which exit wins when both
                        fire. It works; it just is not reached live (3a).

---

## 5. Accuracy bugs found 2026-09-29 — fixed, and what they imply

### 5a. The entry-threshold invariant was hardcoded to 3.0.

`run_portfolio_backtest.report()` computed
`zbad = (d.z_at_entry.abs() < 3.0 - 1e-9).sum()` regardless of the run's actual
`--entry`. An `--entry 2.5` run aborted with "7954 trades opened below the entry
threshold" while its true minimum |z| was **exactly 2.5** and zero trades were
below it. Verified directly against the ledger before trusting any number.

**Implication: no run at `--entry` below 3.0 has ever completed in this engine.**
It would always have raised at the report. If you believed the entry threshold had
been swept downward, it has not been.

Fixed: the invariant now reads `cfg_entry_sigma` from the run's own stamp.

**The general lesson, and it is the one to carry:** an invariant that fires on a
correct run is as damaging as one that stays quiet on a broken one. Trap 7 (below)
is the same failure pointing the other way.

### 5b. The published fee was about double, in the docs only.

`0.2260 sigma` had no derivation anywhere in the repo and no population reproduced
it. Measured, two independent methods agreeing:

    3.6M backtest episodes                   0.066
    live archive, OLS/7d, n=403              0.105   (formula 0.105, measured 0.103)
    live fresh book, ratio/2d, n=14          0.143   (formula 0.154, measured 0.143)

`SESSION_HANDOFF`'s own archive line already used 0.105 — its gross -0.0663 and net
-0.1714 differ by exactly 0.1051 — while its headline said 0.226. Likely cause:
applying `(1+|beta|)` twice (gives 0.209), or using `exit_sweep`'s pessimistic
0.0025 instead of the real 0.000993 (gives 0.263).

**Cost in sigma is `frac*(1+|beta|)/sigma` and it is NOT a constant** — p5 0.063 to
p95 0.233 on the live book, nearly 4x. Both inputs are known at entry. Never quote
a cost in sigma without naming the population and whether the beta factor was
applied once.

Corrected in `SESSION_HANDOFF` and `VM_HANDOFF`. The code was never wrong.

### 5c. A float-exactness trap, hit and caught, worth knowing.

Refactoring `generate_exit_signal` to compare *distances travelled* instead of
*levels* is algebraically identical and numerically is not. At a stop exactly one
stop-distance away, `(0.035 - 0.03) >= 0.005` is FALSE in float64 while
`0.035 >= 0.03 + 0.005` is TRUE. `validate_exit_signal` tests that exact boundary
and failed. **Compare levels, not deltas.** The current code does.

---

## 6. Traps that have cost real time

1. **`Position.pnl`'s `net_pct` is flattered by ~0.09%.** It charges the round trip
   as a flat fraction of the spread move; the real cost is `frac*gross` while P&L
   rides leg A, so in spread units it is `frac*(1+|beta|)`. **Rank on
   `realized_pnl_net`.** The DOLLAR accounting was never wrong — only percentages.
2. **Always pass an explicit `--end-date`.** Without it one partially-formed
   trailing 30m bar cuts the universe from 212 tickers to 17, silently.
3. **Hand-run PASS/FAIL validators, never pytest.** `research/validate_*.py`.
4. **Day-clustered CIs.** Episodes cluster in time and share legs. Resample DAYS,
   never trades, and never compare against a pooled band.
5. **Stored-path analysis can only rule things OUT.** It removes slot contention
   and has twice ruled a change in falsely. Calibration: on the reversion question
   stored paths give a ~50% hit rate where the real engine gives 27.57% — the
   method is optimistic by nearly 2x on exactly that question.
6. **Bars are labelled by OPEN time.** This has bitten the project four times
   (`ac3ac48`, `dislocation_study`, the intrabar walk, `opened_at` in `c287477`).
   A 30m bar labelled T closes at T+30.
7. **Read the invariant block.** It RAISES now, but seven runs once printed
   "duplicate pair open: FOUND — BUG" and exited 0 while a whole stop sweep was
   built on them. And see 5a for the opposite failure.
8. **A single run is one path.** `--pool-mult 3 --seed N` makes it stochastic. Seed
   spread inside one config was $330–$1,056 on a $300 account. Deterministic top-k
   is the LIVE policy, so it is legitimate — but it gives one number, not a
   distribution. The engine WARNs when you are in that mode; the warning is real.
9. **The engine WARNs when a run does not describe the live strategy** (stop or
   entry differing from the live 1.0 / 3.0). Those warnings fired on the expansion
   run and were correct.

---

## 7. Validator baseline as of 2026-09-29

Run from `research/`, with the repo venv: `../.venv/bin/python validate_X.py`.

    PASS   validate_exit_signal        25/25
    PASS   validate_portfolio          99/99
    PASS   validate_stop_monitor      112/112
    PASS   validate_live_scanner       48/48
    PASS   validate_sweep_exits        25/25
    PASS   validate_signal_generator   24/24
    PASS   validate_scanner            17/17
    PASS   validate_intrabar           22/22
    PASS   validate_backtest_screen    13/13
    PASS   validate_dislocation_study  16/16
    PASS   validate_position_sizer     44/44
    PASS   validate_rolling_spread     20/20
    FAIL   validate_exit_tolerance     13/14   <- section 3b, pre-existing

Not run this session: `validate_hedge_estimators`, `validate_ou_analytics`,
`validate_ou_diagnostics`, `validate_universe_panel`. Status unknown — check them
before trusting anything downstream of those modules.

---

## 8. UNCOMMITTED IN THE TREE RIGHT NOW. Read before you start.

Nothing from 2026-09-29 is committed. `git status` on the tracked code:

    M docs/SESSION_HANDOFF.md            fee correction (5b)
    M docs/VM_HANDOFF.md                 fee correction (5b)
    M research/signal_generator.py       direction axis + level-comparison fix (5c)
    M research/portfolio.py              Position leg signs, fill_slots passthrough
    M research/backtest_screen.py        rank_bar direction + target placement
    M research/run_portfolio_backtest.py --direction/--target flags, invariant fix (5a)
    M research/scanner.py                SIGNAL_FIELDS gains "direction"
    M research/validate_scanner.py       compares the one string field exactly
    M research/validate_signal_generator.py  key contract gains "direction"

`research/open_positions.json` is also modified — that is a local runtime artifact,
not part of this work.

**The `--direction expand` axis is new.** It defaults to `revert`, so every
existing path is unchanged; the validator sweep above confirms that. `fill_slots`
copies a field whitelist and silently drops anything not named, which is why
`direction` had to be added there explicitly — that whitelist is the same reason
`r2_at_entry` was blank in every ledger ever written before 2026-09-27.

---

## 9. Numbers not to re-derive

    gross edge per trade        +0.2826 sigma   CI [+0.2059, +0.3628]
    taker round trip            0.105 (n=403) to 0.143 (n=14) sigma  -- see 5b
    NET                         +0.140 to +0.178 sigma, CI excludes zero either way
    win rate                    28.17% vs a 22.60% driftless benchmark, +5.57pp,
                                CI [+3.90, +7.31], positive in all five weeks
    MEASURED_STOP_OVERSHOOT     1.04, confirmed on 316 live stop-outs
    ROUND_TRIP_COST_FRAC        0.000993 of gross

Live book: restarted flat at $300 on 2026-09-29 03:56 UTC on the symmetric 2-day
geometry. **At 8 hours in it was 24 opened / 14 closed, 2 winners, -$4.80 realized,
+$13.31 unrealized, equity $295.20, stop overshoot 1.001-1.067.** Those numbers are
now a day stale — re-run `scripts/check_vm.sh positions` before quoting them.

One unexpected observation from that first batch, not on anyone's list: the ten
slots are not ten independent bets. Across 24 opens `O` was a leg in four, `CAP` in
four, `PI` and `BARD` in three each, and the first batch opened four `O/*` shorts
that all stopped out, three within 33 minutes. Book net exposure was -24.9%
directional at -2.47x equity. That is a sizing question, not a selection one.

---

## 10. CLOSED. Do not re-litigate.

Section 3 of `SESSION_HANDOFF` carries the full list with commit references: entry
gates (all 31 subsets), the exit rule, lookback 1–7 days, stop width 0.5–5.0,
ranking key (theta/r2/neutrality), 149 threshold combinations, cointegration
screening, and theta itself (quantitatively broken — Spearman +0.047 against
eventual reversion where a strong negative is needed).

**Win rate is 27–28% no matter what you sort, gate or screen on.** It is set by
barrier placement.

**NEW 2026-09-29 — the expansion direction is closed.** Betting the spread widens
instead of reverts, at entry 2.5 / stop 0.5 / target 1.0 sigma beyond entry, 2-day
window, 1m exits, 35 days to 2026-09-28:

    trades                 11,300          hit rate      30.20%
    driftless walk         33.33% exact    excess        -3.13 pp  CI [-4.40, -1.86]
    mean R                 -0.1918         CI            [-0.2416, -0.1411]
    end equity             $0.01 from $300
    median hold            0.17h           trades/day    323   (1,292 fills/day)

Both CIs exclude zero. This is the mirror of the +5.57pp reversion excess and it
had to come out negative: the same paths cannot reward both directions. A 0.5-sigma
retrace stop sits inside the noise, so the book paid the round trip every ten
minutes. **No ranker fixes this** — the gross hit rate was below a driftless walk,
so re-sorting only re-sorts a losing population.

Untested, if anyone insists: a wider expansion stop. Be aware that is the
liquidation-contaminated region the stop sweep already warned about.

---

## 11. Commands and file map

    research/rolling_spread.py          THE geometry. Read its docstring first.
    research/signal_generator.py        entry + exit rules, now direction-aware
    research/portfolio.py               slots, margin, liquidation, cooldown, equity
    research/backtest_screen.py         build_screen + rank_bar (the ranker)
    research/run_portfolio_backtest.py  the engine
    research/sweep_exits.py             the standalone walk that must agree with it
    research/stop_monitor.py            THE LIVE BOOK. Sole writer. Do not write while up.
    research/hedge_estimators.py        ols/tls/ratio, cost and liquidation helpers
    research/validate_*.py              17 hand-run validators
    scripts/check_vm.sh                 positions / overshoot / ledger / status / pull
    scripts/release.sh                  build -> registry -> VM pulls. The VM never builds.

A run that describes the live strategy, with every flag that matters:

    ../.venv/bin/python run_portfolio_backtest.py \
      --entry 3.0 --stop 1.0 --hold 72 \
      --entry-window-days 2 --exit-check-minutes 1 \
      --days 35 --end-date 2026-09-28 \
      --pool-mult 3 --seed 1 \
      --out /tmp/baseline.csv

Drop `--pool-mult/--seed` for the deterministic live policy, and accept that you
then have one path and no distribution.

---

## 12. How the user wants to work

- Plain language, lead with the answer. Keep statistics out of the main line.
- One change at a time. Do not fix several things in one pass.
- "Can we test X" means analyse existing data, not write a patch.
- Replace, do not accumulate: rewrite in place, delete orphans, no A/B flags
  unless asked. A sweep axis in the research engine is not an A/B flag.
- Say plainly when something does not work. This project has been advanced far
  more by falsifying things than by finding them.
