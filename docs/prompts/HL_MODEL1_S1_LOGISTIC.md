# HL-MODEL1 S1: logistic scoring build (brief, 2026-10-27)

Planner: Research Partner. Builder: Code Builder. Checker: Code Checker (names change: `ListAgents`).
Parent brief: `docs/prompts/HL_MODEL1_REVERTER_MODEL.md`. Part A's fixed rules apply unchanged.
Results to NUMBERS.md `[HL-MODEL1-S1]`.

**APPROVED by the user 2026-10-27 ("yes i approve"), rulings R1-R7 included. Starts only after B5 closes**
(Step 3 report, checker PASS, commit). No further go is needed at that point.
It runs on the B5 code: the cached IN-matrix (1,091 columns, sha bd5dc254...), `load_fold_features_cached`,
verify-once, fixed coin codes, and the B5-proved per-event logistic core (hazard rows never copy features).
If the B5 logistic core is not proved by then, S1 does not start; tell the planner.

## Goal (user, 2026-10-27)
Train candidate 1 (penalised logistic, discrete-time hazard) on all 8 folds at full data. Score it with
Part A's gate. Produce the use-case metrics below. Then STOP. No vault. No trees. No AWS spend.

## Planner rulings (fill gaps Part A leaves open; fixed before any model sees data)
- **R1 Refit.** For each fold: choose the setting on validation (model fitted on train), then refit with
  that setting on train + validation, then score the test block. The pre-validation embargo day stays out.
  This mirrors A5's vault rule ("refit on the whole search period").
- **R2 Selection metric.** The A5 lift formula on the fold's validation events: top 10% of validation by
  P(reach within 10 h). A tie goes to the larger penalty (smaller model). No other metric picks settings.
- **R3 Grid.** l1_ratio in {1.0, 0.5}. For each, 8 penalties log-spaced from 0.5 x lambda_max down to
  1e-3 x lambda_max (lambda_max computed on the fold's train rows), warm-started along the path. 16 fits
  per fold plus 1 refit. A best setting at the grid's edge is reported, never extended.
- **R4 Preprocessing, fitted on the rows being fitted only** (train for selection; train + val for the
  refit):
  - Clip each numeric column to its 0.1% and 99.9% quantiles (finite values).
  - Standardise with the mean and SD of the finite values.
  - Set NaN to 0. Add a missing indicator for every column with any NaN in the fit rows. Indicators may be
    computed on the fly per chunk instead of stored.
  - Drop columns that are degenerate on the fit rows (the harness's `drop_degenerate_for_fold` rule).
    Log the count.
- **R5 Coin identity.** ticker_a and ticker_b are one-hot only, never used as numbers. Levels are the
  coins seen in the fit rows for that leg. An unseen coin is all zeros (the "unseen" level, A6).
- **R6 Model.** 20 step intercepts, unpenalised, plus penalised weights on the standardised inputs. The
  objective is the hazard-row log-likelihood of A2, exactly as in the B5 proof. Converged when the relative
  objective change is below 1e-7, or at most 2,000 iterations. Non-converged fits are flagged in the log,
  not dropped.
- **R8 Clarifications (planner, 2026-10-27, on the checker's five gaps; same substance as R1-R7):**
  - (a) All preprocessing statistics are computed at EVENT level: each fit event counts once, not once
    per hazard row. This covers quantiles, mean, SD, missing indicators and the degenerate check.
  - (b) One-hot coin columns and missing indicators stay 0/1. They are not clipped or standardised, and
    they ARE penalised. Only the 20 step intercepts are unpenalised.
  - (c) The order is: drop degenerate columns on the RAW fit rows (`drop_degenerate_for_fold` rule), then
    clip, then standardise. A column whose SD is 0 after clipping is also dropped, and logged separately.
  - (d) M6 permutes the RAW column before preprocessing, so its missing indicator moves with it.
    ticker_a and ticker_b are each permuted as one unit, all their one-hot columns together.
  - (e) R2 tie-break: l1_ratio 1.0 first, then the larger penalty.
- **R6 amended (planner, 2026-10-28, after the user chose proximal Newton):** the iteration cap is 50 Newton outer
  iterations, not 2,000. The objective and the 1e-7 stop rule are unchanged. Fits that hit the cap, or whose final
  step had a capped coordinate-descent sweep, are flagged in the log and the per-fold table.
- **R7 Seeds and threads.** One seed, logged, for the score_fold tie-break, the bootstrap and the
  permutation importance. A fixed thread count, logged.

## Step 1: logistic sizing (the B4 spec, on the B5 code)
On fold 7 (largest), at full data: time one fit at the middle penalty, l1_ratio 0.5, with iterations to
convergence. Also time one warm-started step down the path. Report peak RSS. Extrapolate to the full run:
8 folds x (16 fits + 1 refit) + scoring + metrics.
- If the projection is over **24 h** on the GCP VM: STOP and report the options to the planner. Do not
  shrink the grid or subsample on your own. A grid cut needs the user, before any validation result exists.
- Checker review of the sizing script before it runs.

## Step 2: the full run (one job, chained on the VM)
One script runs folds 0..7 in sequence, unattended. A finished fold is not redone after a restart: each
fold writes its outputs and a done marker. The laptop may sleep. Nothing waits on it.
Per fold, it saves (under `research/model/logs/s1/`):
- the validation lift of every grid setting, the chosen setting, iterations and convergence;
- coefficients of the refit (column, standardised coefficient), and the non-zero count;
- test predictions: event_id, fold, p_2h, p_5h, p_10h, where p_h = 1 - prod over steps k <= h of (1 - h_k);
- validation permutation importance (see M6).
The code checks the search-only asserts everywhere. The vault loader is not imported.
Checker review of the full script before launch.

## Step 3: report (NUMBERS `[HL-MODEL1-S1]`), then STOP

**The gate (Part A, A5), computed with the harness functions and nothing else:**
- per-fold lift; pooled lift; the 98.75% day-bootstrap interval (2,000 resamples); the folds-positive
  count; the verdict from `pass_search`. The vault is not touched, whatever the verdict.

**Use-case metrics (user, 2026-10-27). Descriptive only, never a gate, never used to choose settings.**
- **M1 Hit rate.** For 2 h, 5 h and 10 h, each ranked by its own p_h, per fold and pooled: the reach rate
  and chance rate of the top 10%, and of all events.
- **M2 Selectivity.** Lift (10 h) at the top 1%, 5%, 10% and 20%, per fold and pooled, with a pooled
  98.75% day-bootstrap interval for each.
- **M3 Calibration.** Pooled test events in 10 bins by p_10h decile: mean p_10h against the actual
  reach_10h. Also per-fold test log-loss and Brier score.
- **M4 Speed.** Top 10% against the rest: the reach_10h rate, the median minutes_to_mu among reachers,
  and the share reaching within 2 h.
- **M5 Breadth.**
  - By coin, as either leg, pooled: lift restricted to that coin's events. Listed only for coins with at
    least 200 top-10% picks.
  - The share of all top-10% picks held by the 10 most-picked coins.
  - By test block: this is the per-fold table, one 30-day block each.
- **M6 Drivers.**
  - Validation permutation importance: one permutation per column, seeded, scored as the increase in
    validation log-loss. Run on the selection fit, for columns with a non-zero coefficient.
  - Per fold: the top 20 columns, with standardised coefficient and sign.
  - The importance share of each group (events, G2..G9).
  - The share held by the single top column.
  - The share held by the 95 unexplained-drift IN columns. Their list is the columns in
    `docs/release_v1/drift_explained_pair.csv` with cause "unexplained", intersected with IN. Name any
    drift column in a top 20 (A6 watch rule).
  - No pruning (HL-MODEL1 rule).

Then STOP. Send the checker the log, the NUMBERS section and the diff. Commit on PASS, then report to the
planner. Next steps are the user's call: tree sizing (GCP), then the AWS tree run (needs the user's yes).

## Not in S1
No vault. No boosted trees or RSF. No coin unit. No profit metrics (A1: profit waits for a pass). No
seed or permutation checks on results, and no shuffled labels (user). No subsampling. No change to
Part A, the input list or the folds.

## S1-D: the top 1% of picks, examined (user, 2026-10-29: "lets look deeper into the top 1% of picks")
Descriptive only. It reads the saved test predictions (all 8 folds) plus v1 events and labels for the same
event_ids. No refit, no vault, and the gate verdict (FAIL) does not change. The top 1% is a post-hoc slice: a
good number here is a lead for the vault or a later model, not a pass. Run on the GCP VM (the data is there).
One script, checker review, NUMBERS [HL-MODEL1-S1-D].
Top 1% = per test block, the top 1% by p_10h (the same rule as M2). For it, against the block's other 99%:
1. **Size and robustness:** n per fold. Lift per fold and the folds-positive count. Pooled lift with the 98.75%
   day-bootstrap interval. The same for the top 2% and 5%, to see whether the edge rises smoothly or jumps.
2. **Concentration:** distinct pairs, coins and UTC days. The share of picks on the 10 busiest days, and the lift
   with those days removed. The top 10 pairs and coins by count, each with their own gap.
3. **What they look like:** medians (top 1% against the rest) of z, |z| - threshold, sigma, vol_48, r2,
   beta_stab, mins_since_trade_a/b, bars_into_segment, chance_10h, and utc_hour/weekday counts.
4. **Outcomes:** reach rate at 2/5/10 h against chance, median minutes_to_mu among reachers, and the share
   reaching within 30 and 60 min.
5. **Drivers:** for the top 10 inputs by M6 importance, their median value in the top 1% against the rest,
   and the share of top-1% lift left after removing events in the top decile of vol_48.
No profit, fee or stop metrics (A1). Output: one table per item plus a 10-line plain summary.
