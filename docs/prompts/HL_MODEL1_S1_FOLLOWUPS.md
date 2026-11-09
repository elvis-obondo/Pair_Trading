# HL-MODEL1 S1-F: two follow-up checks on the logistic results (brief, 2026-10-31)

Planner: Research Partner. Builder: Code Builder. Checker: Code Checker (names change: `ListAgents`).
Parent: `docs/prompts/HL_MODEL1_S1_LOGISTIC.md`. Results to NUMBERS.md `[HL-MODEL1-S1-F]`.

**Asked for by the user 2026-10-31** (checks 1 and 4 of the planner's list, the user's items 1 and 2).
S2 trees are PARKED until new AWS credits arrive (user, 2026-10-31).

Descriptive only. No refit, no vault, no profit, fee or stop metrics. The S1 gate verdict (FAIL) does not
change. Inputs: the saved `research/model/logs/s1/fold*_test_predictions.csv`, `report.json`,
`fold*_val_permutation_importance.csv`, and v1 events and labels for the same event_ids. Run on the GCP VM,
where the data is (as S1-D). Use the harness functions for lift and for the 98.75% day-bootstrap (2,000
resamples). One script. Checker review of the script before it runs, then of the log, the NUMBERS section
and the diff.

## F1. Fixed cut-off test (what a live system would do)
The S1 top-X% was picked by ranking each finished month. Live, the cut-off must be set from the past.
Rules fixed here, before any number is seen:
- **Score:** each fold's saved test p_10h. **Targets:** q = 1% and q = 10%.
- **Rule A (primary):** for test block k, cut-off c_k = the (1 - q) quantile of p_10h over test block k-1.
- **Rule B:** the same quantile over all earlier test blocks 0..k-1, pooled.
- Picks in block k = events with p_10h >= c_k. Scored folds: 1-7. Fold 0 has no history and is not scored.
- **Per fold, for each rule and target:** c_k, the number of picks, picks per UTC day, the share of the
  block picked (against q), reach_10h rate, chance_10h rate, gap, and lift = gap(picks) - gap(all usable
  events of the block). Alongside: the in-block top-q% lift for the same fold (the S1 way).
- **Pooled over folds 1-7:** lift with the 98.75% day-bootstrap interval for each rule and target, and the
  in-block top-q% lift over the same folds 1-7, so the comparison uses the same months.
- A fold with 0 picks reports n = 0 and no lift. It is not dropped from the table.

## F2. Why are the last three months weaker?
- **Table per fold (0-7):** lift at top 10% and at top 1%; the drift share of validation importance, split
  into vol_48 alone and the other 94 drift columns; the top column's name and share; the block's event
  count, reach_10h rate, chance_10h rate and gap(all). Read from the saved reports where they exist. Say which
  numbers are read and which are computed.
- **Shift check, for each fold:** for every column in that fold's top 20 by importance, compute the shift at
  event level: (median on the test block - median on the fold's refit rows) / IQR on the refit rows. Refit
  rows are train + validation, as in R1. Report the mean |shift| of the drift columns and of the non-drift
  columns in each fold's top 20, and list each top-20 column's shift. This shows whether the columns the
  model leans on moved more in folds 5-7.
- Report what the table shows. Do not claim a cause beyond it.

## Report
One table per item plus a 10-line plain summary. Then STOP and report to the planner with the checker's verdict.
