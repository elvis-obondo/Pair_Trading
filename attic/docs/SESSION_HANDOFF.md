# Handoff — crypto pairs trading

Paste this into a new session. Everything below is measured, not assumed.

---

## 1. The state, in one line

**The edge is real and the fee takes a third to a half of it, not 80%.**

    gross edge per trade   +0.2826 sigma   95% CI [+0.2059, +0.3628]   REAL
    OKX taker round trip    0.143 sigma    MEASURED, fresh book, ratio/2d, n=14
                            0.105 sigma    MEASURED, archive,   OLS/7d,  n=403
    NET at 0.143           +0.140 sigma    [+0.063, +0.220]  (gross CI shifted)
    NET at 0.105           +0.178 sigma    [+0.101, +0.258]

The fee takes **37% of the edge on 403 trades, 51% on the fresh 14.** Use the
fresh-book figure for the current geometry and the archive figure for sample size;
they bracket the truth. Either way the net CI excludes zero.

**THE 0.2260 FIGURE THAT USED TO SIT HERE WAS ABOUT DOUBLE AND IS WITHDRAWN.** It
has no derivation anywhere in the repo and no population reproduces it: 3.6M
backtest episodes give 0.066, the 403-trade archive 0.105 (two independent
methods, 0.103 and 0.105), the fresh book 0.143. This document's OWN archive
arithmetic used 0.105 -- its gross -0.0663 and net -0.1714 differ by exactly
0.1051. Two ways to land near 0.226: apply the `(1+|beta|)` factor twice (0.209),
or use exit_sweep's pessimistic 0.0025 instead of the real 0.000993 (0.263).
The CONSTANT 0.000993 is correct; only the conversion to sigma was wrong.

The mechanism: the spread reverts more often than a driftless walk. Win rate
**28.17%** against a **22.60%** benchmark of `1/(1+|z|)` — excess **+5.57pp**,
CI [+3.90, +7.31], positive in all five weeks (+3.28, +6.81, +5.80, +8.07, +4.74).

---

## 2. The strategy

Enter when a rolling OLS-free spread hits |z| >= 3.0. Stop at 1.0 sigma beyond the
entry spread. Take profit at full reversion to mu. 72h time stop, 72h re-entry
cooldown after a loss, 10 slots, 5% margin at 20x, $5,000 notional cap, ranked by
theta. Costs 0.000993 of GROSS notional (OKX taker, four fills).

`research/rolling_spread.py` is THE geometry definition. scanner, live_scanner,
backtest_screen, signal_generator and dislocation_study all read through it.

---

## 3. What is CLOSED. Do not re-litigate any of it.

| question | verdict | where |
|---|---|---|
| entry gates, all 31 subsets | no subset beats no gates | `e5f494e` |
| the exit rule | closed by exhaustion | earlier sessions |
| lookback 1–7 days | ordering unreadable (1.06x parity vs seed noise); 4–5d reliably bad | `aec2bd6` |
| stop width 0.5–5.0 | nothing separates; above 2.0 is liquidation-contaminated | `9020cf7`, `440d658` |
| ranking key: theta / r2 / neutrality | no difference; changes turnover, not win rate | `58e0d08` |
| threshold combinations (149 tercile cells) | 1 of top 20 survived a time holdout; chance gives 10 | `nothing-separates-the-winners` |
| cointegration screening | 1.6x enrichment out of sample; no trading edge | `bd379f0`, `091c7f7` |
| theta | quantitatively broken — see below | `theta-is-quantitatively-broken` |

**Win rate is 27–28% no matter what you sort, gate or screen on.** It is set by
barrier placement. Every selection experiment came back flat because there is
nothing to select — all ~454 candidates per bar are the same small bet at
different sizes.

**theta specifically:** it claims a median 1.09h half-life. Actual |z| goes
3.30 -> 3.08 -> 2.99 -> 3.59 -> 7.09 at 0/1/4/13/72 hours. Only 16% of trades
halve by their own predicted half-life. Spearman vs actual |z| at 13h is **+0.047**
where a strong negative is needed. It ranks the ten slots and should not.

---

## 4. What is LIVE right now

GCP VM `pairs-trading`, us-central1-a. Monitor container always up, scanner on a
`*/30` host cron. **Deploy is `scripts/release.sh` — the VM never builds.**

As of 2026-09-29 the VM runs `ENTRY_WINDOW_DAYS = 2` and `HEDGE_ESTIMATOR =
"ratio"` (verified in the container, not assumed). Before that it ran the
pre-`0bb61a9` OLS build on a 7-day window, so **every live result before
2026-09-29 came from geometry the backtests had abandoned.**

The book was archived and restarted flat at $300 on 2026-09-29. The previous book
— 403 trades, 2026-09-13 to 09-29, $300 -> $135.03 — is at
`research/live_archive/` and on the VM at `trading_data/archive/20260929T035550Z/`.

**That old book showed no edge:** gross −0.0663 sigma CI [−0.2945, +0.1966], win
rate 21.59% against a 22.54% benchmark. The backtest says +0.2826 [+0.2059,
+0.3628]. The intervals barely touch. Different system, weak evidence, wrong
direction. The fresh book is the first live test of the measured geometry.

    scripts/check_vm.sh positions | overshoot | ledger [N] | status | pull

**Trial ends ~2026-11-08.** Google SUSPENDS at trial end, it does not throttle.
Decide before then; do not let it lapse with a book open.

---

## 5. Traps that have cost real time

1. **`Position.pnl`'s `net_pct` is flattered by ~0.09%.** It charges the round-trip
   cost as a flat fraction of the spread move; the real cost is `frac*gross` while
   P&L rides leg A, so in spread units it is `frac*(1+|beta|)`. **Rank on
   `realized_pnl_net` (which is correct) or recompute.** The DOLLAR accounting was
   never wrong — only the percentage columns.

2. **Always pass an explicit `--end-date`.** Without it one partially-formed
   trailing 30m bar cuts the universe from 212 tickers to 17, silently.

3. **Hand-run PASS/FAIL validators, never pytest.** `research/validate_*.py`.

4. **Day-clustered CIs.** Episodes cluster in time and share legs. Resample DAYS,
   never trades, and never compare against a pooled band.

5. **Stored-path analysis can only rule things OUT.** It removes slot contention
   and has twice ruled a change in falsely.

6. **Bars are labelled by OPEN time.** This has bitten the project four times
   (`ac3ac48`, `dislocation_study`, the intrabar walk, `opened_at` in `c287477`).
   A 30m bar labelled T closes at T+30.

7. **Read the invariant block.** It now RAISES, but seven runs once printed
   "duplicate pair open: FOUND — BUG" and exited 0 while a whole stop sweep was
   built on them.

8. **A single run is one path.** `--pool-mult 3 --seed N` makes it stochastic.
   Seed spread inside one config was $330–$1,056 on a $300 account. Deterministic
   top-k is the LIVE policy, so it is legitimate — but it gives one number, not a
   distribution.

---

## 6. Numbers not to re-derive

    MEASURED_STOP_OVERSHOOT = 1.04    confirmed on 316 live stop-outs: p50 1.015x,
                                      mean 1.031x, p95 1.104x, only 6.3% past 1.10x.
                                      Slightly conservative. Execution is NOT the problem.
    ROUND_TRIP_COST_FRAC = 0.000993   this is the OKX TAKER SCHEDULE to three decimals
                                      (4.965bp on each leg, in and out; gross already
                                      counts both legs). It contains NO bid-ask.
    cost in SIGMA units               = frac*(1+|beta|)/sigma, per trade. It is NOT a
                                      constant: p5 0.063 to p95 0.233 on the live book,
                                      nearly 4x. BOTH INPUTS ARE KNOWN AT ENTRY, so it
                                      can be ranked on. Never quote a single number
                                      without saying which population it came from.
                                      Applying (1+|beta|) twice is how 0.226 happened.
    funding                            0.2% of the fee; cancels between legs. Irrelevant.

**The live book is PAPER.** It fills at the recorded price, so it is structurally
incapable of measuring slippage or maker fill rates. More paper trading will never
improve the cost number. Only real orders will.

---

## 7. Two levers, and the fee one is less urgent than it looked

The edge is fixed at +0.2826 sigma. Rebuilt on the measured taker fee of 0.143
(fresh book, current geometry), maker rows scaled by OKX's own maker/taker ratio:

    taker both legs, in and out    fee 0.143   net +0.140   keeps 50%
    maker in, taker out            fee 0.101   net +0.182   keeps 64%
    maker both ways                fee 0.058   net +0.225   keeps 80%
    taker + a 7.5bp bid-ask        UNVERIFIED -- the old 0.569 was built on the
                                   withdrawn 0.226 and must be re-derived before use

**Taker is NOT breakeven by construction.** That claim came from the doubled fee.
Maker execution still helps; it is no longer the only thing that can work.

**The second lever is new: the fee is selectable.** Cost in sigma is
frac*(1+|beta|)/sigma, known before you enter, and it varies ~4x across the book.
Theta ranking currently picks the EXPENSIVE end -- median cost climbs 0.056 to
0.081 monotonically across nine of ten theta deciles, so the ranker that provably
does not improve the win rate reliably raises the fee by ~45%. Ranking on cost is
untested and, unlike everything in section 3, it does not have to predict
anything. Caveat: the cheapest decile is cheap because sigma is large, and it
reverts worse (39% vs ~50% on stored paths), so the cheap extreme is a trap.

**The bid-ask is still the thing that can invert this and it is still unmeasured.**
A 7.5bp spread is ordinary for thin names like WET and SHELL — which this book
trades most, and which fail `pair_analysis`' own $450k/day turnover floor. In the
withdrawn units that cost flipped the sign. Re-derive it against the corrected fee
before repeating the claim; the direction of the risk is unchanged, the size is not
known.

Open and unblocked, in rough priority:

1. **Rank on cost instead of theta.** New, cheap, and it needs no forecast — see
   the second lever above. The only selection experiment left that is arithmetic
   rather than prediction.
2. **Maker execution.** Fill rates are unmeasurable on paper — needs real orders.
   Still worth having; no longer the only hope.
3. **Liquidation does not reach the live book.** The check added in `440d658` is in
   `Portfolio.evaluate_exits`; `stop_monitor` calls `generate_exit_signal` then
   `pf._close` and never touches it. Cannot fire at a 1.0-sigma stop (0.11 headroom
   vs a 0.0115 stop), but it is a real engine/live divergence.
4. **Walk-forward across several periods.** Everything here is ONE 35-day window.
   The 4–5 day lookback collapse may be this window, not the lookback.
5. **`ENTRY_WINDOW_DAYS = 2` is unjustified.** Shipped on reasoning; the sweep
   cannot rank it against 1, 3, 6 or 7. Not wrong, just unsupported.

---

## 8. File map

    research/rolling_spread.py         THE geometry. Read its docstring first.
    research/hedge_estimators.py       ols / tls / ratio + cost and liquidation helpers
    research/portfolio.py              slots, margin, liquidation, cooldown, equity
    research/run_portfolio_backtest.py the engine. --pairs-file, --pool-mult, --seed,
                                       --entry-window-days, --end-date
    research/coint_screen.py           order-free cointegration screen
    research/stop_monitor.py           THE LIVE BOOK. Sole writer. Do not write while up.
    research/book_state.py             live constants + the ledger path
    research/validate_*.py             17 hand-run validators
    docs/VM_HANDOFF.md                 VM state, deploy, incident history
    scripts/release.sh                 build -> registry -> VM pulls
    scripts/reset_book.sh              archive the book and start flat (asks first)
    scripts/check_vm.sh                positions / overshoot / ledger / status / pull

Memory lives in `~/.claude/projects/-Users-elvisobondo-Pair-Trading/memory/`;
`MEMORY.md` is the index.

---

## 9. How the user wants to work

- Plain language, lead with the answer. Keep statistics out of the main line.
- One change at a time. Do not fix several things in one pass.
- "Can we test X" means analyse existing data, not write a patch.
- Replace, do not accumulate: rewrite in place, delete orphans, no A/B flags
  unless asked.
- Say plainly when something does not work. This project has been advanced far
  more by falsifying things than by finding them.
