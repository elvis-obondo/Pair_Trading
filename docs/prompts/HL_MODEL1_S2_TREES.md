# HL-MODEL1 S2: boosted-tree scoring build (brief, 2026-10-30)

Planner: Research Partner. Builder: Code Builder. Checker: Code Checker (names change: `ListAgents`).
Parent brief: `docs/prompts/HL_MODEL1_REVERTER_MODEL.md`. Part A's fixed rules apply unchanged.
Results to NUMBERS.md `[HL-MODEL1-S2]`.

**APPROVED by the user 2026-10-30 ("yes i approve"), rulings T1-T9 included.** The user chose trees on
2026-10-30 ("lets move to the boosted trees"). The S1 follow-up checks run alongside, on the saved S1
predictions, as the user picks them. Every AWS launch needs the user's yes, typed in the builder session.

## Goal
Train candidate 2 (gradient-boosted trees, discrete-time hazard, step index as an input; A3) on all 8 folds
at full data. Score it with Part A's gate. Produce the S1 use-case metrics. Then STOP. No vault.

## What this rests on (checked by the planner 2026-10-30)
- B5 Step 2 tree report (NUMBERS [HL-MODEL1-B5]): LightGBM's own binned store is about 71.75 GB for
  fold 7's train set, 90.82 GB for its refit, and 96.97 GB for the full search set, at max_bin 255 with
  1,092 columns. This does not fit the GCP VM, so the run goes to AWS (user, 2026-10-27: trees on AWS spot Tokyo).
- `lgb.Sequence` can feed hazard rows in batches from the event-level matrix, so the full hazard-row array
  never has to exist at once. The resident binned store is still the memory limit.
- S1's AWS launch scripts (`research/model/aws_s1_*`) and the cached IN-matrix (1,091 columns,
  sha bd5dc254...) are the starting point. Reuse them; don't build parallel copies.

## Planner rulings (gaps Part A leaves open; fixed before any model sees data)
- **T1 Library and objective.** LightGBM, `objective=binary` on the hazard rows of A2. Each row has the
  event's 1,091 trigger-time inputs plus `step` (1..20) as a numeric input. P(reach within h) =
  1 - prod over steps k <= h of (1 - h_k), exactly as in S1.
- **T2 Refit.** The same as S1's R1. Choose the setting on validation using a model fitted on train. Refit on
  train + validation with that setting, then score the test block. The pre-validation embargo day stays out.
- **T3 Selection metric.** The same as S1's R2: the A5 lift on the fold's validation events, top 10% by
  P(reach within 10 h). Ties go to fewer trees, then to the smaller num_leaves, then to the larger
  min_data_in_leaf.
- **T4 Grid.** Fixed settings: learning_rate 0.05, max_bin 255, feature_fraction 0.3, lambda_l2 1.0, no row
  bagging. Searched: num_leaves in {63, 255} x min_data_in_leaf in {1,000, 10,000} hazard rows, giving 4
  fits per fold. Each fit trains up to 2,000 trees. Validation lift is read at every 100 trees, giving 80
  candidate settings per fold from 4 fits. A fit stops early when validation hazard-row log-loss has not
  improved for 200 trees. Lift is read only at the checkpoints reached. A best setting at a grid edge,
  including 2,000 trees, is reported, never extended.
- **T5 Preprocessing.**
  - Bin edges come from the fold's fit rows only (A4), counted at event level: each event once (as R8a).
    If LightGBM can only bin from hazard rows, say so to the planner before Step 2.
  - No clipping or scaling. NaN goes to LightGBM's native missing handling.
  - Degenerate columns are dropped on the raw fit rows with the harness rule (`drop_degenerate_for_fold`).
    Log the count.
- **T6 Coin identity.** ticker_a and ticker_b are LightGBM categorical inputs, with levels from the fit rows.
  An unseen coin maps to one "unseen" level (A6), never to a seen coin's code.
- **T7 Determinism.** `deterministic=True`, one logged seed, a fixed logged thread count. A rerun reproduces
  every number.
- **T8 Spot safety.** Each fit saves its model at every 100-tree checkpoint, and each fold writes a done
  marker. A reclaimed machine resumes from the last checkpoint (LightGBM `init_model`). A finished fold is
  never redone. Logs and outputs go to S3. Machines self-terminate when done.
- **T8b Watcher (user, 2026-10-30).** Every launch, Step 1 and Step 2, starts a background shell watcher
  in the builder session that exits when the instance leaves `running`. When it exits, pull the S3 log and
  report to the planner at once, success or failure.
- **T9 Drivers (M6), changed from S1.** Use LightGBM total-gain importance on the selection fit, not
  permutation importance. Permutation over about 1,000 columns would cost about a tree-predict of the
  validation set per column per fold. Gain shares are not directly comparable with S1's permutation shares.
  Say so in the report.

## Step 1: sizing (on AWS, small spend)
On fold 7 (the largest), at full data, on one candidate machine:
- Build the Dataset and report peak RSS and build time.
- Train 200 trees at num_leaves 255 and min_data_in_leaf 1,000. Report seconds per tree.
- Time one validation P(reach) predict at 200 trees.
- Project the full run: 8 folds x (4 fits up to 2,000 trees, with early stopping making this an upper
  bound) + 8 refits + scoring + metrics. Give hours and spot cost for 1 and for 2 machines.
- The machine needs room for the ~97 GB binned store plus gradients and the event matrix. Propose the type
  and say why. Use Tokyo spot first and us-east-2 as the fallback.
- **STOP after Step 1 and report to the planner.** If the projection is over 24 h on 2 machines, list the
  options (fewer max trees, a smaller grid, max_bin 63). Do not apply any of them. A grid cut is the
  user's call, made before any validation result exists.
- Checker review of the sizing script before it runs. The Step 1 launch needs the user's yes in the
  builder session.

## Step 2: the full run
One job per machine runs its folds in sequence, unattended. Per fold, it saves under `research/model/logs/s2/`:
- the validation lift at every checkpoint of every fit, the early-stop point, and the chosen setting;
- the refit model file;
- test predictions: event_id, fold, p_2h, p_5h, p_10h;
- gain importance per column (T9).
The search-only asserts run everywhere. The vault loader is not imported.
Checker review of the full script before launch. The launch needs the user's yes.

## Step 3: report (NUMBERS `[HL-MODEL1-S2]`), then STOP
- **Gate (A5), using the harness functions only:** per-fold lift, pooled lift, the 98.75% day-bootstrap
  interval (2,000 resamples), the folds-positive count, and the verdict from `pass_search`.
- **Use-case metrics M1-M5 exactly as S1** (M2 includes the top 1%). M6 as T9: the top 20 per fold, group
  shares, the top column's share, the drift share and the drift columns named in any top 20.
- **Side by side with S1:** pooled lift and M2 at 1/5/10/20% for both models, read from the two reports.
  This is a plain table with no new statistics.
- **Top 1% deep dive (user, 2026-10-30), descriptive, gate unchanged:** S1-D items 1-5 exactly as written
  in the S1 brief, on the tree model's test predictions, plus the median |z| x sigma (distance to mu) for
  the top 1% against the rest, and the overlap between the tree top 1% and the S1 top 1% (share of
  event_ids in both). The planner writes the user's detailed report from these numbers.
Then send the checker the log, the NUMBERS section and the diff. Commit on PASS, then report to the planner.

## Not in S2
No vault. No RSF. No coin unit. No profit, fee or stop metrics (A1). No seed or permutation checks on
results (user). No subsampling. No change to Part A, the input list or the folds. No pruning.
