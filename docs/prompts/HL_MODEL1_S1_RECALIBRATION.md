# HL-MODEL1 S1-H: recalibrating the logistic model's probabilities (brief, 2026-11-07)

Planner: Research Partner. Builder: Code Builder. Checker: Code Checker (names change: `ListAgents`).
Parent: `docs/prompts/HL_MODEL1_S1_TOP1_DEEP.md` (S1-G). Results to NUMBERS.md `[HL-MODEL1-S1-H]`.

**Asked for by the user 2026-11-07** ("i like that recalibration idea", then "yes" to this design). S2 trees stay
PARKED.

## Goal
S1-G found the model overconfident at the top. Top-1% picks are predicted at 82.9% and reach mu 67.7% of the
time; they are under-predicted at 2 h and over-predicted at 10 h. Test whether a correction learned only from
earlier months makes the percentages match reality. A correction that only moves higher predictions higher does
not change the ranking, so the picks and lift stay the same. This is about the numbers, not the edge.

Descriptive only. No refit of the S1 model, no vault, no fees or profit. The gate (FAIL) does not change.
Inputs: saved `research/model/logs/s1/fold*_test_predictions.csv` (p_2h, p_5h, p_10h) and v1 labels
(reach_2h, reach_5h, reach_10h) for the same event_ids. Run on the GCP VM if it is still up. If not, read only the
needed label columns from S3, read-only. Checker review of the script before it runs, then of the log, the
NUMBERS section and the diff. Every reported number is printed by the script (CLAUDE.md rule).

## Rules (fixed before any number is seen)
- **Fit set for month k (folds 1-7):** all test events of folds 0..k-1 pooled (expanding). Fold 0 is fit data
  only and is not scored. **Look-ahead guard (planner ruling 2026-11-07, on the checker's finding):** for
  horizon h, a fit event is used only if t0 + h <= the start of test block k, so its outcome was known before
  month k began. This drops at most the last 10 h of events of block k-1. Report the drop count per fold and
  horizon. (Rule A's cut-off needs no guard: it uses predictions only, which are known at t0.)
- **Horizons:** 2 h, 5 h and 10 h, each corrected separately: p_h against reach_h.
- **Method 1, Platt (smooth curve):** an unpenalised logistic regression of reach_h on logit(p_h), with p_h
  clipped to [1e-6, 1 - 1e-6] and 2 parameters (intercept, slope). Event level. If a slope is <= 0, report it and
  do not use that fit.
- **Method 2, isotonic (step function):** `sklearn.isotonic.IsotonicRegression(increasing=True,
  out_of_bounds="clip", y_min=0, y_max=1)` on p_h against reach_h, at event level.
- **Picks:** S1-F Rule A on the RAW p_10h, q = 1%, 0.5% and 0.1%, exactly as in S1-G (assert the per-fold n
  equals S1-G's). Recalibration never re-selects picks.
- **Ranking check:** per month, the Spearman correlation between raw and Platt-corrected p_10h must be 1. For
  isotonic, report the number of tied groups it creates; ties are expected.

## What to report
- **R1 Fitted maps:** per month and horizon, the Platt intercept and slope. For isotonic, the corrected value
  at raw p = 0.1, 0.2, ..., 0.9.
- **R2 Error scores:** per month and pooled over months 2-8 (folds 1-7), for each horizon: log-loss and
  Brier for raw, Platt and isotonic, all events.
- **R3 Calibration by decile:** pooled over months 2-8, 10 bins of raw p_10h (deciles over those events).
  Per bin: n, mean raw, mean Platt, mean isotonic and actual reach_10h. The same table for 2 h and 5 h.
- **R4 The picks:** for q = 1%, 0.5% and 0.1%, per month and pooled: n, mean raw, mean Platt, mean isotonic
  and actual, at 2, 5 and 10 h.
- **R5 The cut-off in real terms:** per month, the Rule A q = 1% cut-off c_k (raw), with its Platt- and
  isotonic-corrected values.
- **R6 Horizon order:** the count of events where the corrected p_2h > p_5h or p_5h > p_10h, per method. Report
  it; do not fix it.

## Report
One table per item plus a 10-line plain summary. Then STOP and report to the planner with the checker's verdict.
A version that also uses distance from mu (|z|) in the correction is a possible next step. It can change the
ranking, so it is NOT part of this brief.
