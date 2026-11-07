# HL-MODEL1 S1-G: why the live top 1% works and where it fails (brief, 2026-11-06)

Planner: Research Partner. Builder: Code Builder. Checker: Code Checker (names change: `ListAgents`).
Parent: `docs/prompts/HL_MODEL1_S1_FOLLOWUPS.md` (S1-F). Results to NUMBERS.md `[HL-MODEL1-S1-G]`.

**Asked for by the user 2026-11-06:** "lets focus on the top 1% ... lets understand why exactly it works and
where exactly it fails." S2 trees stay PARKED: no credits yet; the user is looking at a compute cluster.

Descriptive only. No refit, no vault, no fees or profit. The gate (FAIL) does not change. Every slice
here is chosen after seeing results, so a good number is a lead, not a pass. Run on the GCP VM while it lasts
(trial ends about 2026-11-08). If it is gone, stop and tell the planner. One script. Checker review of the
script before it runs, then of the log, the NUMBERS section and the diff.

## The pick set
**Picks = S1-F Rule A, q = 1%, folds 1-7**: in test block k, events with p_10h >= the 99% quantile of
block k-1's p_10h. That is 35,629 picks. **Rest** = the block's other usable events. The cut-off is
the live-feasible one, so everything below is about trades a live system could have taken.
Lift uses the harness definition: gap(picks) - gap(population). Intervals are the harness 98.75% day bootstrap
(2,000 resamples).

## G1. Trade count (the user's question)
- Picks per UTC day: median, mean, 10th and 90th percentile and max, per fold and pooled. Days with an
  event but no pick count as 0.
- Open at once: hold each pick from t0 until minutes_to_mu, or for 10 h if it never reaches. Report the
  peak, median and 90th percentile of the number open at once, and the peak per single coin.

## G2. Why it works: the same starting position, a different result
- Cut every block event into 10 bins by chance_10h, using deciles of the pooled folds 1-7 events.
- In each bin: n and reach_10h for the picks and for the rest, with the difference.
- This shows whether picks beat other events that started from the same position, and in which bins.

## G3. Why the model picked them (exact for a linear model)
- Per fold, rebuild the refit preprocessing exactly as S1's R4 and R8 (train + validation rows, event level).
  Apply it to the test block and multiply by the saved `fold*_coefs.csv`.
- **Proof first (amended by the planner 2026-11-06: the step intercepts b were never saved, so p_10h cannot be
  rebuilt):** p_10h is strictly increasing in the linear score eta = X·w within a fold, so the ranking needs no b.
  In every fold, the rebuilt eta must (1) separate the picks perfectly, with min eta over picks > max eta over the
  rest of the block, and (2) have a Spearman correlation >= 0.999999 with the saved p_10h over the block. If
  either fails, STOP and report. Do not solve for b.
- Then for picks against the rest:
  - the mean contribution (coef x preprocessed value) per column and per group (events, G2..G9, coin one-hots,
    missing indicators);
  - the top 20 columns by the difference in mean contribution between picks and rest, with sign.
- This says which inputs push an event into the top 1%.

## G4. Where it works and where it fails: fixed slices
For each slice below, give the number of picks, the share of the slice picked, the picks' reach_10h and
chance_10h, and lift with its interval. **Lift inside a slice is measured against that slice's own events**
(gap(picks in the slice) - gap(all block events in the slice)), so it is skill within the slice.
Tercile cut points come from all block events, folds 1-7 pooled.
- Side of the spread: z > 0 against z < 0.
- YZY in either leg against not.
- vol_48 terciles. r2 terciles. sigma terciles. (|z| - threshold) terciles.
- UTC hour in four 6-hour blocks. Weekend against weekday.
- Fold (1-7).

## G5. Anatomy of the misses
- Picks that reached mu within 10 h against picks that did not: medians of the S1-D item-3 columns.
- For the misses, compared with the rest's misses: the median and quartiles of depth_10h and mae_sigma. These
  show where a miss ended up and how far it went the wrong way, in sigma. They are path measures, not profit,
  and no fees are applied.

## G6. Overconfidence at the top
- By fold: the picks' mean p_10h against their actual reach_10h.
- Pooled: the picks in 5 bins of p_10h (quintiles of the picks), with mean p_10h against actual reach_10h.

## G7. Tighter cut-offs: top 0.5% and top 0.1% (user, 2026-11-06: "100 trades a day is so much")
Same Rule A, with q = 0.5% and q = 0.1% (block k-1's 99.5% and 99.9% p_10h quantiles), folds 1-7. For each q,
with q = 1% beside it in the same tables:
- Per fold and pooled: n, picks per active day, share picked, reach_10h, chance_10h, gap and lift. Pooled lift
  gets its 98.75% interval.
- G1's trade-count items.
- Outcomes: reach at 2, 5 and 10 h against chance; median minutes_to_mu among reachers; the share reaching
  within 30 and 60 min.
- Size, IN SIGMA (user, 2026-11-07): the median and quartiles of the distance to mu in standard deviations, |z|,
  plus |z| - threshold. The price-percent version (|z| x sigma) goes in the JSON only, not the report.
- G5's miss measures (depth_10h, mae_sigma) and G6's calibration by fold.
- G4's slices, pooled only, with each slice's n shown (q = 0.1% gives few picks per slice).
Small n is reported as it is. Nothing is merged or dropped to make a cell bigger.

## G8. Distance from mu against the model's probability (user, 2026-11-07; corrected the same day: "not distance vs
reversion. Distance from mu vs model's probability")
- Cut every block event in folds 1-7 into 10 bins by |z| at entry, in sigma. Bin edges are the deciles of
  |z| over those events, pooled. Print the edges.
- **Headline, per bin, for all events:** n and the model's p_10h: mean, median, 25th and 75th percentile.
- The same per bin for the Rule A picks at q = 1%, 0.5% and 0.1%, using the same edges, with n shown. Report thin or
  empty bins as they are.
- Side columns only: actual reach_10h per bin, beside the mean p_10h.
- This shows how the model's probability changes with distance from mu.

## Report
One table per item plus a 10-line plain summary: why it works (G2, G3), where it fails (G4, G5), how many
trades (G1), and how far the percentages can be trusted (G6). Then STOP and report to the planner with the
checker's verdict.
