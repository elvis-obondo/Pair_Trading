# HL-MODEL1: can a model pick reverters better than chance? (brief, 2026-10-27)

Planner: Research Partner (pair-trading-58). Builder: Code Builder (pair-trading-ea). Checker: pair-trading-49.
Results go to NUMBERS.md `[HL-MODEL1-HARNESS]` (this build) and `[HL-MODEL1]` (the scoring build).

Part A holds the FIXED RULES, decided by the user on 2026-10-27. They are written before any
model sees data and they do not change after results are seen. A change to any of them is a
user decision, through the planner. Part B is THIS build: the input list, the harness, its
proofs and the sizing. **No real model is scored in this build.**

---

## Part A. Fixed rules (user decisions 2026-10-27)

### A1. The question
At the trigger minute, using only data available then, can a model rank pair events so that its
top 10% reach mu within 10 h more often than their position and luck explain, by a margin that
is large enough to matter? Profit, stops and fees are OUT of scope until this is answered (user:
"get profit out of the way").

### A2. Unit and target
- **Unit: the pair unit** (6,697,756 events, frozen v1). It is the strategy. The coin unit is
  NOT scored in HL-MODEL1 (planner default; it would add tries; ask the user before adding it).
- **Target: time to mu, hazard framing.** Twenty half-hour steps over 10 h. An event contributes
  one row per step it was still waiting. The row's label is 1 in the step where `minutes_to_mu`
  falls (step k covers minutes 30(k-1)+1 .. 30k), else 0. Non-reachers give 20 zero rows.
  `label_gap = 1` events are excluded (0.40%; their labels are NaN). Every row carries the
  event's trigger-time inputs plus the step index.
- **Scored quantity:** the model's P(reach within 10 h) = 1 - prod_k (1 - h_k) at the trigger.
  It must reproduce `reach_10h` exactly when fed the true step labels (a proof in B3).
- **Decision time = the trigger.** No input from after the trigger. Updating after entry is out of
  scope.

### A3. Candidate models (fixed list, in this order)
1. Penalised logistic (discrete-time hazard, step dummies, L1 or elastic net).
2. Gradient-boosted trees (discrete-time hazard, step index as an input).
3. Random survival forest (on (minutes_to_mu capped at 600, reached flag) directly).
4. Sequence net on raw minute flow: LATER, needs a raw-minute extract that is sized first.

No volatility-only baseline model (user, 2026-10-27). Consequence, recorded: a pass cannot be
split into "volatility in a new form" versus new information. The bar below is against chance.

### A4. Folds, gap and vault (dates from the data: 2025-05-25 14:32 to 2026-10-13)
- **Vault: events with t0 from 2026-07-13 00:00 UTC to the end.** Locked. Not loaded by any
  search code. Opened ONCE, at the end, for the models that pass the search, through a separate
  script the checker reviews first.
- **Gap:** events with t0 on 2026-07-12 (UTC) are used nowhere.
- **Search period: t0 before 2026-07-12 00:00 UTC.**
- **Expanding walk-forward:** test blocks of 30 calendar days starting 2025-11-21 00:00 UTC
  (180 days after the first event): 2025-11-21, 12-21, 2026-01-20, 02-19, 03-21, 04-20, 05-20,
  06-19; the last block is cut at 2026-07-12 (23 days). Eight folds. Fold k fits on every search
  event before its block.
- **Embargo:** events in the 1 day before a test block, and in the 1 day before the validation
  block, are dropped from fitting (a 10 h label crosses the boundary otherwise).
- **Validation inside each fold:** the last 20% of that fold's fit days, after the embargo. Every
  setting (penalty, iterations, depth, leaf size, trees) is chosen on that fold's validation
  only. Nothing is carried back from a later fold.
- **Normalisers, imputation and encodings** are fitted on the fold's fit rows only.

### A5. The score and the pass bar (version B, user 2026-10-27)
Per test block: rank the block's usable events by the model's P(reach within 10 h); take the top
10% of that block. For any set of events S, gap(S) = mean(reach_10h over S) - mean(chance_10h over S).
- **Lift = gap(top 10%) - gap(all usable events of the block).** This removes the constant
  shortfall of reach against chance (about 11 points, most likely bid-ask bounce in the 1-minute
  chance bar), which affects every event alike.
- **Pooled lift:** over the concatenated out-of-sample top-10% sets and block populations of all
  eight folds (each block's top 10% weighted by its size).
- **Interval:** bootstrap by whole UTC day (2,000 resamples); one coin move lands on one day, so
  its many pair events move together. **98.75% level** (Bonferroni for four candidate models).
- **PASS (search):** pooled lift >= 0.05 AND the lower end of the 98.75% interval > 0 AND lift > 0
  in at least 6 of the 8 folds. Fewer folds = REGIME-DEPENDENT, reported, not a pass.
- **No permutation null / seed checks on results (user, 2026-10-27: "i dont want any seed
  checks"; the shuffled-label proof was removed too).** The guards are the remaining B3 proofs (run once, before real training), the 98.75%
  day-bootstrap interval, the 6-of-8 fold rule and the vault.
- **Vault:** the passing models are refit on the whole search period (settings chosen on its last
  20% of days as validation) and scored once on the vault: three blocks (07-13..08-11,
  08-12..09-10, 09-11..10-13). PASS = pooled lift >= 0.05 AND interval lower end > 0 (Bonferroni
  over the number of models taken into the vault) AND lift > 0 in at least 2 of the 3 blocks.
- **Deadline for the go/stop decision: 2026-11-15** (user).

### A6. Inputs
- **In:** every column of the v1 pair unit, except the exclusions below.
- **Out, future-using:** all G0 labels (depth_*, reach_*, minutes_to_mu, adverse*, mfe/mae,
  chance_*, fee_*, outcome_*, gross_*, net_*, label_gap, label_nan_minutes), pair_triggers_true,
  y00..y20.
- **Out, future-using (found 2026-10-27):** seg_end_bar (where the event's NaN-free segment ENDS:
  known only afterwards, for example at a delisting) and anything derived from it.
- **Out, hindsight static (today's values applied to the past):** a_/b_sector, same_sector,
  max_leverage, tier1_max_leverage, size_decimals, margin_table_id, cg_status, and any other
  column the dictionary marks "outside the as-of rule".
- **Out, archive-age stamps (user, 2026-10-27, raised by the checker):** a_/b_/d_ oi_obs_age,
  oi_rec_age, fund_age_h, ctx_age_min, and any other column that measures the age of the last
  archive snapshot or row. They measure archive gaps (concentrated in Aug-Oct 2026, mostly the
  vault), not market state, and a live feed would not reproduce them; fund_age_h restates
  mins_since_top_hour. The OI, funding and ctx VALUES stay in. Same rule, same day (user):
  near_seam (a build 2 hole minute in the last 24 h) and a_/b_oi_rec_in_gap (OI bridged across an
  archive gap) are OUT: archive-gap flags, not market state.
- **As-of evidence (planner ruling 2026-10-27):** where the dictionary has no window wording, the
  code docstring line counts (cite file and line), backed by the group's poison-test log.
- **Out, artefacts and keys:** a_/b_snapshot_age_s (archive sampling rate, not market state),
  event_id, pair_index, bar_index, seg_start_bar, raw timestamps (absolute time indices
  extrapolate badly in a walk-forward; calendar columns such as utc_hour and weekday stay in).
- **Duplicates, one copy in:** beta and beta_stab (stored in events.parquet AND g2.parquet);
  seg_bars = bars_into_segment. Assert the copies are equal before dropping one.
- **Coin identity: IN** (user, 2026-10-27): a_/b_coin_code / ticker as categorical. Coins first
  seen after a fold's fit period get an "unseen" level.
- **Drift columns (96 pair, unexplained): IN, watched** (user, 2026-10-27). Every scoring report
  gives the share of validation importance carried by drift columns, per fold, and names any
  drift column in a model's top 20. Watch only: it is not a gate.
- **No pruning in HL-MODEL1.** Validation importance per fold is logged so a pruned run can follow
  if the user asks.

---

## Part B. This build: input list, harness, proofs, sizing

### B1. Input list (frozen file)
Write `research/model/inputs_v1_pair.csv`: every v1 pair column with in/out, the reason from A6,
its source file and its dictionary entry. Every OUT reason quotes the rule. Then:
- **As-of audit:** for every IN column, the dictionary line showing its window ends at or before
  the trigger. Any column without such a line is listed as UNVERIFIED and goes to the planner;
  do not decide it yourself.
- **Duplicate audit (planner ruling 2026-10-27, fixed before the audit runs):** every pair of IN
  columns whose correlation rounds to 1.000 in absolute value, EITHER sign, is examined.
  - It is a DUPLICATE (kind = duplicate for +, anti_duplicate for -) only if BOTH hold: (a) the pair
    is an exact affine transform, y = a + b*x, on every row where both are finite, within float32
    tolerance; and (b) the NaN pattern is identical (same rows NaN in both).
  - Otherwise it is a NEAR_DUPLICATE: reported, both kept.
  - Which copy is kept is MECHANICAL, not a judgement: the column from the earliest file in v1
    group order (events, g2, g2b, g3, g4, g5_a, g5_b, g5_net, g5_shape, g6_a, g6_b, g6_net, g7,
    g8, g9a); within one file, the alphabetically first name. An exact affine copy carries no new
    information, so the choice cannot change what a model can learn. No sign-off is needed. The
    full pair list goes to the planner with the checker's review, for the record.
- **Degenerate columns (planner ruling 2026-10-27):** a column constant on every row, or NaN on
  every row, of the pair unit is OUT (category degenerate), every copy. Columns degenerate only
  inside some folds stay IN; the harness drops them for that fold's fit and logs the count.
  Extended (planner ruling 2026-10-27): a column with ONE value on every finite row (the rest NaN)
  is also degenerate and OUT, provided its NaN mask equals the NaN mask of another IN column of
  the same file (so the missingness it carries is already in the inputs). Otherwise it stays IN
  and is listed. First case: g8 a_crossed, b_crossed.
- Send the file to the checker before anything else is built on it.

### B2. Harness (research/model/, one module, no model-specific logic in the split code)
- Loads only through `master_manifest.open_version("v1", "pair", ...)` (verifies sha256 first).
- **The vault cannot be read by search code:** the split module filters t0 < 2026-07-12 00:00 UTC
  at load and asserts no row at or after it reaches any fit, validation or test array. The vault
  loader is a separate function, not called in this build.
- Builds the folds, embargo and validation exactly as A4; prints each fold's date ranges, event
  counts, embargo drops and reach rate.
- Builds the hazard rows as A2, keyed by event_id, so all rows of one event fall in one fold and
  one side of every boundary (asserted).
- Scoring exactly as A5, including the day-block bootstrap and the permutation null.
- Deterministic: fixed seeds, logged; a rerun reproduces every number.

### B3. Proofs (all must pass before any real model runs; each must be able to fail)
1. **Leak check by planted future column:** add a column built from the event's own reach_10h
   plus noise. The harness must flag it (lift far beyond any plausible value, the input-list
   check refusing it). A variant that skips the check must be caught.
2. **Shuffled labels: REMOVED (user, 2026-10-27).** The planted future column (proof 1) is the
   leak check.
3. **Planted real signal of known size:** synthetic outcomes generated from one input with a
   known lift (for example 0.08); the harness must recover it within its interval, and must
   report 0 when the planted effect is 0.
4. **Hazard round trip:** the true step labels fed back give P(reach within 10 h) = reach_10h on
   every event (0 mismatches); step boundaries checked on 2,000 events by hand.
5. **Vault and boundary asserts:** a deliberately mis-dated row (t0 = 2026-07-13) injected into
   the search set must make the run fail.
6. **Independent recompute:** fold dates, embargo drops and the lift on one fold recomputed by a
   separate short script, numbers equal.

### B4. Sizing (report, then STOP)
- Hazard rows expected (about 15 per event, about 100M rows) and memory for each model at full
  data. The VM has 64 GB; this will not fit as a dense matrix.
- **Machines (user, 2026-10-27):** use the GCP VM fully while it lasts (trial ends ~2026-11-08;
  the trial caps at 8 vCPUs, 64 GB). Logistic runs on the GCP VM with chunked or out-of-core
  fitting; the B3 proofs run there too. Boosted trees (and the survival forest, if feasible) run
  on AWS SPOT in Tokyo (64 vCPU quota there; us-east-2 also 64), with resumable checkpoints
  because spot can be reclaimed. Report memory and the method for each model, and the AWS cost
  per full rolling run. **The AWS launch still needs the user's yes, through the planner.**
- **Random survival forest feasibility:** time one fold at full data with a fixed small number of
  trees and extrapolate. If the full rolling run cannot finish in 24 h on the largest allowed
  machine, STOP and report the options. Do not subsample (standing rule: full dataset always).
- No real-model scoring in this build. The scoring build follows after the checker passes B1-B4
  and the user approves the machine.

### Review and receipts
- Checker: B1 file before B2; harness code and proof designs before any run over a few minutes;
  logs, NUMBERS `[HL-MODEL1-HARNESS]` and the diff before reporting.
- Report to the planner: proofs PASS/FAIL with numbers, the sizing, the machine proposal, the
  UNVERIFIED column list (if any), and the checker's verdict.
