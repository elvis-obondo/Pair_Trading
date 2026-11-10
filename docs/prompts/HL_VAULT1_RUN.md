# HL-VAULT1: open the vault once and run the HL-PROFIT1 backtest on it (brief, 2026-11-09)

Planner: Research Partner. Builder: Code Builder. Checker: Code Checker (names change: `ListAgents`).
Read CLAUDE.md, docs/PLANNER_HANDOFF.md section 3, docs/prompts/HL_PROFIT1_LIVE_PICKS.md and this brief first.

**Decided by the user 2026-11-09:** run the vault now. **No pass/fail rule**: the vault result is reported, not
judged. Every setting below is fixed BEFORE any vault row is read; nothing is changed after seeing it. The vault is
opened once. A second refit on all data (vault included) for paper trading happens only if the user likes the result
and asks; it is NOT part of this brief.

## What the vault is
Events with t0 >= `harness.VAULT_START` (2026-07-13T00:00Z) to the end of v1. Never loaded by any run so far
(harness asserts). `research/model/vault_loader.py` is referenced by harness.py but does not exist: write it. It is
the only code that may read vault rows, and only from step 3 on.

## Steps
1. **Coverage check (no vault labels or outcomes read).** Size every day of the vault window for: v1 pair events
   (count only), build2 d3/asm 1m prices for the coins involved, ctxs (funding, impact) and fundinghist. Print per
   day. Gaps are reported to the planner before step 2; nothing is filled.
2. **Model rebuild (AWS, the user's own yes in the builder's session; background watcher per memory).**
   a. **Reproduction check on fold 0** (the smallest train set): refit with fold 0's saved settings
      (fold0_done.json lam, l1_ratio) through s1_preprocess / s1_model exactly as s1_run did. Assert the
      coefficients match fold0_coefs.csv and the test predictions match fold0_test_predictions.csv (state the
      tolerance before running). If it does not match: STOP and report.
   b. **Pre-vault model:** fit on every search event with t0 < VAULT_START - EMBARGO (harness rules, train and val
      together, as s1_run's refit), with fold 7's selected lam and l1_ratio (no new grid search). Save the COMPLETE
      model: coefficients, the 20 step intercepts, every preprocessing statistic (dropped columns, clip quantiles,
      means, SDs, missing-indicator list), ticker one-hot levels, settings, input sha256s. Load it back and assert
      identical predictions on a sample.
3. **Score the vault** with the saved model: p_2h, p_5h, p_10h per vault event.
4. **Picks and probabilities (fixed rules, no tuning):**
   - Rule A: the vault cut-off for q = 1%, 0.5%, 0.1% is the top-q quantile of fold 7's saved test p_10h (the
     previous block, as every fold).
   - p_cal: isotonic, fitted on the pooled test-fold predictions (folds 1-7) with S1-H's guard (t0 + 10 h <
     VAULT_START). No vault row in the fit.
5. **Backtest on the vault** with s1_profit1.py, tags `vault_open10` and `vault_open20`, 24 configs each:
   start $1,000, margin 5%, leverage min(10, coin A max, coin B max) (coin_cap mode, real caps), max_open 10 /
   20, cross margin, fees 0.045% taker / 0.015% maker per fill (both), slippage 0.0, funding on, $10 min order,
   stops 0.5 / 1 / 2 / none, ties by highest p_cal. The same v1 cross-check (outcomes vs v1 vault labels) and
   move[0] assert, hard abort. The checker's manifest gate (cleaned price and impact files identical to their
   verified copies).
   NOT run on the vault: the |z| >= 3 filter (chosen in-sample) and the flat 10x (hypothetical).
6. **Report:** the numbers generator on both tags, one NUMBERS.md section each, headed "VAULT (opened once,
   2026-11-xx)". Plus one side-by-side table: test months (base, open20) vs vault (open10, open20) on final equity,
   return, CAGR, trades, win rate, profit factor, Sharpe, max drawdown, min distance to liquidation, fee share.
   Also: the vault's own S1 lift and calibration at top 1% (reported, not gated). Known gaps as in HL-PROFIT1
   (slippage 0 means an upper bound; maker fills assumed; leverage caps are today's snapshot).

## Process
Checker review of every script before it runs (step 2 before the AWS launch). Every number printed by a script.
After the vault is read, nothing in steps 4-5 may change; a bug found later is fixed and rerun with the fix
reported, never a setting change. Stop and report to the planner with the checker's verdict. No paper-trading
refit. No Word report unless the user asks.
