> **Results before 2026-10-14 are OKX.** OKX data (bars and the datasets built from them) is in attic/okx_data/ and attic/okx_datasets/. From [HL-BUILD1] on, the venue is Hyperliquid.

# Every number produced this session

M = measured from data.  A = assumed / typed by me as an input.
"terminal only" = the script's output was piped through `tail` and never saved;
the number cannot be re-read from disk without re-running.

## Provenance of the inputs

| number | M/A | where |
|---|---|---|
| The 9 fit parameter vectors in `centre.py`/`r2.py` `FITS` | **A** | hand-copied from `exp.log` to 4 dp, NOT refitted. Transcription unverified. |
| 4 synthetic truths in `oracle.py` | **A** | typed by me |
| 3 synthetic truths in `recover.py` | **A** | typed by me |
| `9.75%` (R2 the gate needs at 10h) | **M** | derived algebraically (CRPS proportional to residual sd), checked on a grid in `ceiling2.py`. Correct. |
| `ENTRY_WINDOW_DAYS=2` -> 96 bars; fit window 336 bars | **M** | `research/rolling_spread.py` |

## Dataset — `mkdisloc.log` (saved)

| number | M/A |
|---|---|
| panel 36,172 bars x 212 tickers, 2024-09-11 -> 2026-10-04, 753 days | M |
| 212 of 212 tickers have a contiguous finite region; 0 interior holes | M |
| 22,366 pairs | M |
| 3.45M fresh \|z\|>=3 crossings, ~154 per pair (projected from 300 sampled pairs) | M |
| 60,000 dislocations, 3,000 pairs, 20 each, 746 days, 2024-09-18 -> 2026-10-04 | M |
| alignment invariant: max\|W[:,-1] - z_entry\| = 0.000e+00; same for Y[:,0] | M |
| split at 2026-02-23 (70% of DAYS): 21,523 / 38,477 — **SUPERSEDED, do not use** | M |

## CRPS decomposition — `centre.log` (saved, PARTLY WRONG)

Climatology there is built once at 10h and reused for the 0.5/1/2h rows, so
**every 0.5h, 1h and 2h figure in that file is not horizon-matched and is wrong.**
The 10h rows are correct.

| number | M/A |
|---|---|
| climatology CRPS 2.531 sigma @10h, 2,538 set | M |
| best model 2.517 sigma = 99.4% | M |
| `mix_cm` (model spread, stays-put centre) 100.2–102.7%, 28 of 28 cells | M |
| best-possible width centred on stays-put: 2.526 @10h vs climatology 2.526 | M |
| centre MAE @10h: stays-put 3.4167, best fit 3.3894 | M |

## Centre R2 — `r2.py` (**terminal only, not saved**)

| number | M/A |
|---|---|
| fits' centre R2 @10h: 0.42%–0.93%, best = E0 unfitted | M, terminal only |
| regression beta of predicted change on actual: 0.40–0.44 | M, terminal only |

## Real-data ceiling — `bound.log` (saved) + `bound2.py` (**terminal only**)

| number | M/A |
|---|---|
| split 2026-07-18 (70% of DISLOCATIONS): 41,936 / 18,064, 667/79 days | M |
| climatology CRPS, horizon-matched: 0.571 / 0.754 / 0.998 / 1.923 sigma | M |
| level shift: mean 10h change fit −0.0164, held-out −0.3354 | M |
| 18 features, raw held-out R2: best single +0.144% (z_entry), all 18 −0.259% | M, terminal only |
| day-clustered [−1.045%, +0.098%] | M, terminal only |

## Reversion description — `drift.py` (**terminal only**)

| number | M/A |
|---|---|
| mean 10h change in entry direction −0.1124 sigma, CI [−0.1972, −0.0248] | M, terminal only |
| median −0.403; 56.2% revert; reverters mean −2.362, rest +2.776 | M, terminal only |
| 1 of 26 months has a CI excluding zero | M, terminal only |

## WITHDRAWN

| number | why |
|---|---|
| `oracle.py` 94.0% / 50.1% / 87.5% / 96.5%, centre R2 7.68%/71.3%/20.5%/3.05% | **CIRCULAR** — generates from the model, scores the model. Also terminal only. Cannot support any claim about real spreads. |
| `bridge.log` 6.68% and 0.03% | sign-folding bug on one side of the comparison |
| `ceiling.log` entire R2->CRPS table | mapped R2 to (1−sqrt(R2)) instead of sqrt(1−R2); made the gate look ~30x easier. File deleted. |
| "the gate cannot be reached" | asserted from a linear feature test; not established |

## Synthetic recovery — `recover.log` (saved)

| number | M/A |
|---|---|
| 3 truths x 3 reps, all 7 params; 6 of 7 miss on all three truths | M |
| `k_revert` = 0.0000 in all 9 fits (truths 0.085 / 0.150 / 0.020) | M |
| `qL` = 0.0000 in 7 of 9 | M |
| qL+qX recovered: 0.925/0.969/0.952 vs 0.963; 0.770/0.771/0.758 vs 0.800; 0.694/0.700/0.693 vs 0.700 | M |
| truth-1 nll across reps 509.1978 / 509.4228 / 508.9925 on swapped vectors | M |

---

# Feature layer, 2026-10-09

M = measured from data.  A = assumed / typed by me as an input.

Saved logs: `research/dislocation_model/logs/envfeat.log` and
`logs/validate_envfeat.log`. Nothing here is terminal-only.

## What the layer is

The 41 external + 21 window features are RETIRED, with `external.py` and
`wave_full.py` in `attic/research/` and their datasets deleted. They were built
against a 212-ticker / 36,172-bar panel; the panel loads 214 tickers now.

**Record a FETCH DATE for the panel, not a bar count.** It rolls forward: 36,172
bars when the dataset was built, 36,215 on 2026-10-09, 36,415 on 2026-10-10. A
bar count in this file dates instantly; the date is what lets the next person
tell drift from a bug.

`envfeat.npz` replaces them: 60,000 x 5 float32, joined onto the EXISTING
`disloc_meta.parquet` by position. **No target, no model, no score.**

## Provenance of the inputs

| number | M/A | where |
|---|---|---|
| the 60,000 rows and their geometry | **M** | unchanged `disloc.npz` / `disloc_meta.parquet`, built 2026-10-04 |
| 48 bars for `vol_48` | **A** | chosen: recency beat precision in 2a-ii (48 bars 27.44% vs 335 bars 21.65%) |
| 96 bars for `vratio` and `sandwich` | **A** | chosen: `rolling_spread.ENTRY_WINDOW_DAYS=2` = 96 bars, the ENTRY geometry window |
| 16 / 32 bars for `vol_slope` | **A** | typed by me; not swept |
| 48 hours for `off_mark` | **A** | chosen to equal 96 x 30min of wall-clock time |
| absolute rather than squared steps | **A** | chosen: at nu 2.709 the fourth moment barely exists; \|d\| lag-1 ACF 0.283 vs d^2's 0.109 |
| hedge weights 1 and \|beta\|, over (1+\|beta\|) | **A** | the project's own cost convention, `frac*(1+\|beta\|)` |
| `IID_VRATIO_DIVISOR[96] = 3.396899` | **M** | 200,000 simulated gaussian walks, seed 20261009, median of step_sd/level_sd = 0.294386 |

## The join, and why it is positional

| number | M/A |
|---|---|
| `panel.index[bar_index] == entry_time` on 60,000 of 60,000 rows | M |
| panel 36,415 x 214 as FETCHED 2026-10-10; the dataset came from 36,172 x 212 | M |
| the extra bars are all at the END, so every index still resolves | M |
| 212 of 212 meta tickers still present in the panel | M |
| ticker_a / ticker_b / entry_time match meta element-wise, 0 mismatches each | M |

`mkdisloc.py` permutes a seeded draw over `tradeable_pairs`, so rebuilding
`disloc.npz` on today's panel would return a different 60,000 and nothing would
be comparable. The join key is now stored IN `envfeat.npz` so the positional join
is checkable rather than assumed.

## Percentiles — `logs/envfeat.log` (saved)

All 60,000 rows finite on all five columns: 0 NaN, 0 inf. Nothing was
`nan_to_num`'d; the old pipeline did and it concealed broken columns.

| column | M/A | p1 | p5 | p25 | p50 | p75 | p95 | p99 | mean | sd |
|---|---|---|---|---|---|---|---|---|---|---|
| `vol_48` sigma | M | 0.191 | 0.238 | 0.326 | **0.407** | 0.504 | 0.684 | 0.846 | 0.427 | 0.139 |
| `vratio` iid=1 | M | 0.833 | 1.037 | 1.396 | **1.680** | 1.994 | 2.490 | 2.870 | 1.712 | 0.445 |
| `vol_slope` | M | 0.542 | 0.703 | 1.012 | **1.322** | 1.766 | 2.975 | 4.959 | 1.527 | 0.916 |
| `sandwich` sigma | M | 0.261 | 0.339 | 0.492 | **0.643** | 0.851 | 1.328 | 1.860 | 0.713 | 0.327 |
| `off_mark` sigma | M | 0.0016 | 0.0034 | 0.0080 | **0.0134** | 0.0216 | 0.0414 | 0.0624 | 0.0167 | 0.0128 |

**All five columns are now in sigma units.** The unscaled `off_mark` (log units,
median 0.00024) is SUPERSEDED, 2026-10-10, and is not kept: 46.4% of its variance
was between-pair against 5.5-21.4% for the other four, and because the split is
temporal — every pair in both blocks — a tree could route on it to recover pair
identity, which scores in held out and does not survive new pairs. Dividing by
`meta.sigma` halved that share to 23.6%. See the next section.

## Between-pair variance share — eta-squared on the pair grouping

The number that justified scaling `off_mark`. 3,000 distinct pairs, 60,000 rows.

| column | M/A | between-pair, UNSCALED off_mark | between-pair, CURRENT |
|---|---|---|---|
| `vol_48` | M | 5.9% | 5.9% |
| `vratio` | M | 6.3% | 6.3% |
| `vol_slope` | M | 5.5% | 5.5% |
| `sandwich` | M | 21.4% | 21.4% |
| `off_mark` | M | **46.4%** | **23.6%** |

Only `off_mark` changed; the other four are untouched and are repeated so the
comparison is readable in one place.

**Why it matters, and it is about the SPLIT, not the feature.** `harness.CUT` is
temporal, so all 3,000 pairs sit in both the fit and the held-out block. A column
that is mostly between-pair is partly a pair label, and a tree can route on it to
recover pair identity. That would score on the held-out block and would not
survive a pair the model has never seen. 23.6% is in line with `sandwich`'s
21.4%; both legitimately carry cross-sectional information about how cohesive a
pair's legs are. This is reported, not gated — a feature should carry some
cross-sectional variation, the point is to know how much.

Done BEFORE any target exists, deliberately. After a score is on the table,
changing a feature is choosing one on results.

## Two things the population says on its own

NEITHER IS A PREDICTION. Nothing has been scored.

| number | M/A |
|---|---|
| `vratio` median 1.680 — the typical entry window is 68% choppier than iid | M |
| only 4.3% of rows sit below the iid level (p5 = 1.037) | M |
| `vol_slope` median 1.322 — volatility was still ARRIVING at entry, not receding | M |

The `vratio` result is a long path for little net displacement. Microstructure
noise or bid-ask bounce is the ordinary cause and would inflate step sd without
moving the level, which also makes it the reading to rule out first. It is
consistent with the step/level ratio work and with the unmeasured bid-ask being
the thing that can still invert the strategy's sign.

## The sandwich bound, and the beta sign

| number | M/A |
|---|---|
| beta is NEGATIVE on 15,713 of 60,000 rows (26.2%) | M |
| bound violations, sign-corrected: 0 of 60,000 x 96 bars | M |
| mean \|close-to-close\| move 0.408 sigma — the LOWER bound on within-bar travel | M |
| mean sandwich gap 0.713 sigma — the UPPER bound minus the close | M |

The brief's formula `high_a - beta*low_b` is the beta>0 case. At beta<0 the
maximum of `a - beta*b` is attained at `high_b`, not `low_b`, so the literal
form is the wrong bound on 26% of rows — and the brief's own per-bar assertion is
what catches it. Implemented sign-corrected; 0 violations.

## No lookahead — `logs/validate_envfeat.log` (saved)

| number | M/A |
|---|---|
| rows where max panel index touched exceeds the entry index: 0 | M |
| rows where it EQUALS the entry index: 60,000 of 60,000 | M |
| max entry index 36,151; 263 later bars exist and are UNUSED (panel fetched 2026-10-10) | M |
| 18,208 of 36,415 grid slots are hourly mark labels (panel fetched 2026-10-10) | M |

`off_mark` reads 1h mark labelled <= T-60 and the 30m close one index later, so
its own maximum index is i-1 — strictly before the entry bar. A 1h bar labelled T
spans T to T+60 and closes in the future relative to the entry bar's T+30
observation, which is the trap; the last fully-closed 1h bar at entry is the one
labelled T-60.

## Sign-folding

| number | M/A |
|---|---|
| max \|flipped - original\| = 0.000e+00 on all five columns | M |

Tested by rebuilding the whole matrix with the spread negated everywhere — the
window, the within-bar bounds (whose hi and lo swap under negation) and the close
— which also flips every row's entry sign. Folding is then (-s)(-X) = sX, so the
output must be bit-identical, and it is. Run through the same code path, not a
re-derivation that could share a mistake.

## CORRECTED IN FLIGHT

| number | why |
|---|---|
| `vratio` divisor `sqrt((n^2-1)/(6n))` = 3.999783 at n=96 | **WRONG FOR THIS USE, caught before shipping.** It normalises the ratio of EXPECTATIONS; the feature is the EXPECTATION OF A RATIO. A random walk's level sd is dominated by its own realised path, so E[1/level_sd] >> 1/E[level_sd]: the analytic divisor left the iid ratio centred on 1.186 (median), 17.7% too high. The shipped 3.396899 is simulated. The simulation check in the validator is what caught it — the derivation looked right and the resulting percentiles looked plausible. |
| first `vratio` percentiles (median 1.978) | computed with the analytic divisor above; superseded by the table in this section |

## RETIRED WITH THE OLD LAYER

| number | why |
|---|---|
| `WINDOW / regression / 10h = -0.0104, CI [-0.0288, -0.0022]` | The validator's published-cell assertion ran through `harness.window_features`, which is gone. Keeping a dead function alive to satisfy a test is not a trade this project makes. The cell's finding stands in `docs/STATE.md` section 3; only the assertion is retired. |

---

# Scorer anchor and lookahead audit, 2026-10-10

M = measured from data.  A = assumed / typed by me as an input.

Saved logs: `logs/envfeat.log`, `logs/validate_envfeat.log` (46 PASS, 0 FAIL).

## THE SCORER IS PINNED TO A NUMBER

Before this, `harness.py`'s scorer had **no numeric test at all.** The published
cell assertion (`WINDOW / regression / 10h = -0.0104`) was retired on 2026-10-09
with `window_features` and nothing replaced it. `fit_predict`,
`permutation_null`, `score_set` and `passes`-with-a-null were never called by the
validator, and `ci()` was tested only for raising on bad shapes, never for the
value it returns. A change to the val-selection line in `fit_predict` would have
left the validator printing ALL PASS while silently voiding comparability with
every number in this file.

| number | M/A | value |
|---|---|---|
| synthetic held-out R2 | **M** | 0.5335209428 |
| its day-clustered 95% CI | **M** | [0.5184061154, 0.5511822286] |
| boosting iterations chosen on val | **M** | 107 of 200 |
| identical across two consecutive runs | **M** | yes, to 10dp |
| **sklearn** | — | **1.9.1** (numpy 2.4.6, scipy 1.17.1) |

**THIS IS A UNIT TEST, NOT A RESEARCH CELL.** Do not read 0.5335 as a finding or
quote it as a result. The target is a fixed linear function of three `windows`
columns plus seeded gaussian noise:

    C = windows[:, [0, -48, -1]].astype(float64)
    y = 1.0*C[:,2] - 0.5*C[:,1] + 0.25*C[:,0] + 4.0 * default_rng(20261009).standard_normal(60000)

It carries NO information about the real outcome — `Y` is never touched — so
scoring it on the held-out block measures arithmetic, not data. The held-out set
is not being looked at in the sense the split exists to prevent.

| choice | M/A | why |
|---|---|---|
| `windows` and nothing else | **A** | `windows` is permanent. The old anchor died because it ran through `window_features` / `extfeat.npz`, which were not. Do not restore either to recover a different anchor. |
| noise scale 4.0, giving R2 ~0.53 | **A** | strong on purpose, so the assertion fails loudly on a scorer change instead of drowning in noise |
| 107 iterations, interior to 200 | **M** | the val-selection line is genuinely exercised; a boundary value would not test it |

**A LIBRARY UPGRADE WILL MOVE THIS NUMBER.** Pinned under sklearn 1.9.1. If the
anchor fails after an upgrade, that is the reason — re-pin it and record the new
version here. It is not evidence of a bug.

**Still unpinned**, and stated so nobody assumes otherwise: `permutation_null`,
`score_set` and `passes`-with-a-null have no numeric test. The brief asked for one
anchor and it covers `fit_predict` + `ci`, which are the two functions that carry
every published number.

## Lookahead: per-feature-family maxima

The aggregate check `max index touched == entry index, 60,000 of 60,000` was
**true by construction** and has been replaced. `touch` was set to the entry
index unconditionally before features 4 and 5 ran, so the aggregate hit it the
moment features 1-3 were computed — and then read as proof that `off_mark`
reaches the entry bar. It does not.

| family | M/A | max index touched, relative to entry |
|---|---|---|
| features 1-3 (`windows`) | M | `i+0` on 60,000 rows |
| `sandwich` (30m high/low) | M | `i+0` on 60,000 rows |
| `off_mark` (1h mark + 30m close) | M | `i-1` on 31,494 rows, `i-2` on 28,506 rows, `i+0` on **0** |

The aggregate "never exceeds the entry index" check is unchanged — it is the live
one and it still reports 0 rows over.

**The two `off_mark` cases, which the docstring previously got wrong.** Mark
labels are hourly, the entry grid is half-hourly:

    T on the hour   T-60 IS a mark label. Last mark read is T-60; paired 30m
                    close at i-1.
    T on the :30    T-60 is also :30 and is NOT a mark label, so the code steps
                    back one more slot to T-90. Last mark read is T-90; paired
                    30m close at i-2.

The docstring claimed `<= T-60` in both cases. The code reads `<= T-90` for a
`:30` entry, which is CONSERVATIVE, not leaky — it gives up an hour of history.
Corrected in the docstring and left alone in the code: widening it to recover the
hour would change the feature, and that is not on this plan.

---

# Envelope description, run 1 (30-minute closes), 2026-10-10

M = measured from data.  A = assumed / typed by me as an input.

Every row below is RUN 1 / 30m. The 1-MINUTE RERUN is deferred and blocked on data;
see the last section. Saved logs: `logs/envelope_30m.log` (the run),
`logs/envelope_1m_DEFERRED.log` (the block).

**No gate, no permutation null, no direction claim, no strategy.** The
calibration rule below is an ADMISSIBILITY rule deciding which models get their
sharpness compared. Nothing here is promoted to a finding.

## THE HEADLINE

| number | M/A |
|---|---|
| cells scored: 2 populations x 2 directions x 4 models x 5 horizons | **80** |
| cells passing calibration | **0 of 80** |
| cells passing, climatology included | **0** |

**The description is not trustworthy on this held-out block, and the reason is
the period rather than the features.** Climatology fails too, and climatology is
exact in-sample by construction, so the whole table inherits one regime shift.

## Provenance of the inputs

| number | M/A | where |
|---|---|---|
| target: running MAE/MFE, sign-folded, UNCLAMPED | **A** | clamping puts 54.6% of MAE mass at exactly 0 at k=1, making q5/q25/q50 calibration vacuous |
| quantiles 0.05/0.25/0.50/0.75/0.95 | **A** | typed |
| horizons k = 1, 2, 4, 10, 20 bars | **A** | 0.5h/1h/2h/5h/10h, as briefed |
| TRENDING cutoff `vratio <= 1.47220` | **M** | bottom tercile of vratio on the FIT BLOCK only, applied as a fixed number to both blocks |
| `KNN_K = 200` | **A** | typed, NOT tuned -- val is reserved for GBDT's iteration count and never scored, so there was nowhere legitimate to tune it |
| `SLICE_TOL = 2.0` | **A** | declared threshold: inconsistent slices allowed up to 2x the 5% expected by chance |
| QTREE hyperparameters | — | `harness.TREE` unchanged, only `loss="quantile"` swapped in |
| split | — | `harness.Split` unchanged, built per population |
| runtime | M | 721s; Linear QR is ~93% of fit time at ~11s per LP |

## Populations

| number | M/A |
|---|---|
| ALL: 60,000 episodes, 18,064 held out, train 22,683 / val 19,253 | M |
| TRENDING: 18,669 episodes, 4,690 held out, train 7,612 / val 6,367 | M |

Climatology is computed per population, so TRENDING is scored against its own
unconditional envelope and not the full population's.

## BASELINE TRANSFER -- the drift that explains the whole table

Climatology is the TRAIN block's empirical quantile, so in-sample coverage is
exactly 0.050 / 0.250 / 0.500 / 0.750 / 0.950 by construction. Held out:

| direction | horizon | M/A | q5 | q25 | q50 | q75 | q95 |
|---|---|---|---|---|---|---|---|
| MAE | 0.5h | M | 0.046 | 0.262 | **0.520** | 0.764 | 0.952 |
| MAE | 1h | M | 0.042 | 0.254 | **0.525** | 0.763 | 0.957 |
| MAE | 2h | M | 0.044 | 0.262 | **0.525** | 0.767 | 0.957 |
| MAE | 5h | M | 0.046 | 0.270 | **0.531** | 0.770 | 0.960 |
| MAE | 10h | M | 0.046 | 0.278 | **0.532** | 0.773 | 0.957 |
| MFE | 0.5h | M | 0.048 | 0.236 | **0.480** | 0.738 | 0.954 |
| MFE | 1h | M | 0.049 | 0.231 | **0.475** | 0.736 | 0.955 |
| MFE | 2h | M | 0.046 | 0.226 | **0.465** | 0.728 | 0.951 |
| MFE | 5h | M | 0.040 | 0.210 | **0.447** | 0.714 | 0.945 |
| MFE | 10h | M | 0.041 | 0.209 | **0.453** | 0.718 | 0.943 |

MAE OVER-covers and MFE UNDER-covers: in the held-out period adverse excursions
ran smaller and favourable ones larger than in the train period. The gap widens
monotonically with horizon. Consistent with the already-recorded finding that the
held-out block is a favourable window (`the-edge-is-real-and-the-fee-eats-it`,
held-out slice +0.335 against the full history's +0.112).

## PREDICTION SPREAD -- the features do vary the prediction

IQR of the predicted MEDIAN quantile across held-out episodes, in sigma.
**REPORTED UNGATED**, deliberately: with nothing admissible the gated table is
empty and the primary question goes unanswered. Spread is a property of the
model's OUTPUT, never a claim that the output is right.

| population / direction | model | M/A | 0.5h | 1h | 2h | 5h | 10h |
|---|---|---|---|---|---|---|---|
| ALL / MAE | Climatology | M | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| ALL / MAE | Linear QR | M | 0.0687 | 0.0407 | 0.1148 | 0.3033 | 0.4658 |
| ALL / MAE | QTREE | M | 0.0246 | **0.0003** | 0.0457 | 0.2035 | 0.3929 |
| ALL / MAE | kNN | M | 0.1049 | 0.1204 | 0.1787 | 0.3574 | 0.5267 |
| ALL / MFE | Linear QR | M | 0.0687 | 0.1489 | 0.2208 | 0.3836 | **0.5370** |
| ALL / MFE | QTREE | M | 0.0158 | 0.1029 | 0.1784 | 0.3111 | 0.4537 |
| ALL / MFE | kNN | M | 0.1049 | 0.1484 | 0.2102 | 0.3589 | 0.4974 |
| TRENDING / MAE | Linear QR | M | 0.0188 | 0.0439 | 0.1131 | 0.2290 | 0.3795 |
| TRENDING / MAE | QTREE | M | 0.0027 | 0.0038 | 0.0407 | 0.1850 | 0.2544 |
| TRENDING / MAE | kNN | M | 0.0713 | 0.0711 | 0.1134 | 0.2593 | 0.3812 |
| TRENDING / MFE | Linear QR | M | 0.0188 | 0.0700 | 0.1250 | 0.2380 | 0.3329 |
| TRENDING / MFE | QTREE | M | 0.0027 | 0.0399 | 0.0666 | 0.1870 | 0.2355 |
| TRENDING / MFE | kNN | M | 0.0713 | 0.1148 | 0.1503 | 0.2493 | 0.2983 |

Climatology is 0.0000 everywhere by construction. At 10h the conditional models
move the predicted envelope by up to 0.537 sigma IQR against a median MFE of
1.621 sigma -- roughly a third of the level. **They are not reproducing
climatology with extra steps.** Whether the variation is CORRECT is exactly what
this block cannot establish.

One oddity, recorded and not chased: QTREE at ALL/MAE/1h has IQR **0.0003** --
it collapses to a near-constant at that single cell while Linear QR and kNN both
move.

## SHARPNESS -- empty, and that is the result

| number | M/A |
|---|---|
| cells with a reportable pinball ratio | **0 of 80** |

Pinball is only comparable among calibrated models, and none are. Every ratio
would have carried a day-clustered 95% interval; none was computed because no
cell qualified. The interval machinery is verified: climatology against itself
returns exactly 100.00% with a degenerate interval, and a perturbed band returns
100.01% [99.94, 100.07].

## STRUCTURAL CONSTRAINTS -- enforced, not gated

Share of (episode, horizon, quantile) predictions that enforcement MOVED:

| population / direction | model | M/A | quantile enforce | horizon enforce |
|---|---|---|---|---|
| ALL / MAE | Climatology | M | 0.000% | 0.000% |
| ALL / MAE | Linear QR | M | 0.000% | 0.002% |
| ALL / MAE | QTREE | M | 0.000% | **0.624%** |
| ALL / MAE | kNN | M | 0.000% | 0.000% |
| ALL / MFE | QTREE | M | 0.000% | **0.372%** |
| TRENDING / MAE | QTREE | M | 0.000% | **0.664%** |
| TRENDING / MFE | QTREE | M | 0.000% | **0.443%** |

Quantile crossing is 0.000% for every model in the final predictions.
Climatology and kNN are 0.000% on both axes and that is structural, not luck:
`np.quantile` is non-decreasing in q, and the quantile of a running maximum is
non-decreasing in k. Independent per-horizon fits have no such guarantee, which
is why QTREE moves.

## CORRECTED IN FLIGHT -- a rule that could not admit a conditional model

| number | why |
|---|---|
| the previous run's "2 of 80 pass, no conditional model admissible" | **WITHDRAWN.** The admissibility rule keyed structural violations by (population, direction, model) with NO horizon, counted them across all five horizons at once, and required exactly zero for every individual cell. One violation anywhere disqualified all five horizons of that model. Each horizon is an INDEPENDENT fit, so nothing forces the 10h fit above the 5h fit on a given episode and cross-horizon violations are normal behaviour. Climatology cannot violate either constraint, so the rule failed every conditional model BY CONSTRUCTION. It would have retired the feature set on an artifact. Measured on val: QTREE/MAE 7,060 monotonicity violations of 385,060 (1.833%) and 8 crossings (0.002%). |
| climatology fitted on `ctx["fit"]` (train+val, 41,936 rows) | **CORRECTED to train only, 22,683 rows.** It was the denominator of every sharpness ratio while seeing 84% more data than the models it was benchmarked against. Climatology has no iteration count to choose, so it had no legitimate use for val. |
| the baseline-transfer diagnostic on the fit block after that change | **CORRECTED.** It disagreed with the model it explains -- 0.265 against 0.262 at ALL/MAE/0.5h. Both now read train. |
| the sharpness ratio as a bare float | **CORRECTED.** Every coverage number carried a day-clustered interval while the one number that gets quoted carried none. Now bootstrapped over `sp.boot` from the stored predictions, no refit. |
| the 1-minute target's monotonicity guard | **CORRECTED.** It compared with `< -1e-12`, which is False for NaN, so an all-NaN window (nanmax of all-NaN is NaN) passed silently into every model. Finiteness is now asserted FIRST, and empty windows are refused at source. |
| the cell count | **ADDED.** 80 cells, and the chance arithmetic: 5 interval checks at 95% means a perfectly calibrated cell clears the aggregate screen only 77.4% of the time, so ~18 of 80 fail on chance alone. **This screen errs toward FALSE FAILURE**, not false discovery. |

## Two asymmetries that remain, both conservative, both now stated in the output

| number | M/A |
|---|---|
| counted slices: climatology 10, conditional models 60 | M |
| realized-magnitude decile slices failing, every model | M, 46-50 of 50 |

A constant predictor has no predicted-magnitude spread, so that slice family is
skipped for climatology -- legitimate, but it means climatology faces an easier
screen. Printed per cell as `const pred: no predicted-decile slice`.

Realized-magnitude slicing is **computed and never counted**. Conditioning
coverage on the realized target is mechanically monotone: on climatology,
MAE/10h/q50 it is exactly `[1, 1, 1, 1, 1, 0.316, 0, 0, 0, 0]`. A perfectly
calibrated model fails it, so counting it would be a criterion rigged to fail.
The predicted-magnitude decile is the direct equivalent of the slicing that
caught the earlier CRPS failure, and that one IS counted.

## This run uses 30-MINUTE CLOSES

The true envelope is strictly worse: the worst point inside a bar is never
observed. Earlier work puts the understatement at roughly 0.3 sigma, one-sided,
scaling with volatility. **Climatology is biased the same way**, so the
comparative numbers should be largely unaffected. That is an ASSUMPTION (A),
stated and not corrected for. The 1-MINUTE RERUN is what tests it.

## 1-MINUTE RERUN -- DEFERRED as of 2026-10-10, blocked on data

| number | M/A |
|---|---|
| instruments with some 1-minute history | M, 212 of 212 |
| instruments reaching back to the episode start 2024-09-18 | **M, 1 of 212** |
| earliest 1-minute start across instruments | M, 2024-04-21 |

The path is written and aborts with that coverage report rather than running on
partial data. Nothing is forward-filled or interpolated. It also carries the
three additions the 1-MINUTE RERUN requires: the assertion that the 1-minute path reproduces
the 30-minute closes exactly at the 30-minute marks, the bar-label offset (a 30m
bar labelled T closes at the 1m bar labelled **T+29**), and per-episode
missing-minute counts.

## Known duplication, not fixed in this pass

The GBDT val-selection loop now lives in `envelope.py` rather than `harness.py`.
That is how four copies of the harness started last time. Folding it in properly
means giving it a numeric anchor in `validate_dislocation_harness.py` the way
`fit_predict` has, which is its own piece of work. Do it before a second script
needs it.

---

# HALVES ANALYSIS — held-out split and isotonic transfer, 2026-10-11

M = measured from data.  A = assumed / typed by me as an input.

Run tag: **HALVES / 30m**. Saved log `logs/envelope_run2_30m.log` (1,021 lines, 757s).
Every row is tagged by population and held-out half.

**NO REFIT.** Every prediction is run 1's, cached at
`research/datasets/envelope_preds_30m.npz` (19.2MB, post-enforcement). The fits
are deterministic — seeded split, `random_state=0` trees, an LP solver, exact
kNN — verified by reproducing run 1's logged QTREE spread at ALL/MAE k=1
(0.0246) and k=2 (0.0003) to 4dp before trusting the cache.

**THE DISCIPLINE BEND, RECORDED.** The held-out block had its one scoring touch
in run 1. This is the SECOND touch, taken deliberately to test whether the run-1
miscalibration is a stable offset or a moving target. The isotonic map is fitted
on Held Out 1 and tested only on Held Out 2, so the transfer claim is not scored
on its own fitting set. A third touch needs a better reason than this one.

## The halves

| number | M/A |
|---|---|
| HO1: 2026-07-18 -> 2026-08-25, 39 days, 8,200 rows | M |
| HO2: 2026-08-26 -> 2026-10-04, 40 days, 9,864 rows | M |
| boundary `2026-08-26`, matches the brief exactly | A |

## HEADLINE 1 — the drift is CONCENTRATED IN HO2, unanimously

| number | M/A |
|---|---|
| mean calibration gap, HO1 | **M, 1.06pp** |
| mean calibration gap, HO2 | **M, 3.05pp** |
| cells where HO2 is worse than HO1 | **M, 80 of 80** |

Not one cell of eighty has its worse half in HO1. The run-1 drift was not steady
across the window; it is almost entirely the back half. Mean gap by horizon:

| horizon | M/A | HO1 | HO2 | HO2 recalibrated |
|---|---|---|---|---|
| 0.5h | M | 0.86 | 1.35 | 0.77 |
| 1h | M | 1.00 | 2.09 | 1.40 |
| 2h | M | 0.98 | 3.26 | 2.52 |
| 5h | M | 1.19 | 4.22 | 3.31 |
| 10h | M | 1.29 | 4.33 | 3.20 |

HO1's gap barely moves with horizon (0.86 -> 1.29). HO2's more than triples
(1.35 -> 4.33). Worst single cell: TRENDING/MFE/kNN/5h at 5.45pp on HO2 against
1.19pp on HO1.

## HEADLINE 2 — THE SKILL IS SMALL, POSITIVE AND REPLICATED

This is what run 1's pass/fail headline hid completely.

| number | M/A |
|---|---|
| conditional cells with POSITIVE skill on BOTH halves | **M, 58 of 60** |
| conditional cells with negative HO2 skill | M, 2 of 60 |

Best cell, ALL / MFE / Linear QR / 10h:

| half | M/A | pinball skill vs climatology |
|---|---|---|
| HO1 | **M** | **+4.13% [+3.04, +5.13]** |
| HO2 | **M** | **+3.33% [+2.44, +4.41]** |

Both intervals exclude zero and the two halves agree. Plainly: sizing a decision
off this instead of doing nothing helps by about 3-4%, and that held up on two
independent 40-day blocks. QTREE (+3.79 / +3.18) and kNN (+3.45 / +2.84) land in
the same place at the same cell, so it is not one model's artifact.

**MFE is more describable than MAE.** At ALL / Linear QR / 10h, MFE skill is
+4.13 / +3.33 against MAE's +1.62 / +2.06. The favourable-excursion envelope
carries more signal than the adverse one.

The only two negative cells, both TRENDING/MAE/Linear QR, and both tiny:

| cell | M/A | HO1 skill | HO2 skill |
|---|---|---|---|
| TRENDING MAE Linear QR 1h | M | +0.95 | **-0.04** |
| TRENDING MAE Linear QR 5h | M | +1.35 | **-0.07** |

## HEADLINE 3 — the miscalibration has a STABLE SIGN and a DRIFTING SIZE

Coverage direction is consistent across halves, which is why a correction has
anything to grip. ALL / Linear QR / 10h, actual coverage against nominal
5/25/50/75/95:

| cell | half | M/A | q5 | q25 | q50 | q75 | q95 |
|---|---|---|---|---|---|---|---|
| MAE | HO1 | M | 4.1 | 26.7 | 52.5 | 76.4 | 95.5 |
| MAE | HO2 | M | 5.4 | 30.8 | 57.9 | 80.8 | 96.6 |
| MFE | HO1 | M | 3.6 | 22.2 | 46.0 | 73.2 | 94.2 |
| MFE | HO2 | M | 3.2 | 18.7 | 43.0 | 71.7 | 94.6 |

MAE OVER-covers in both halves and more so in HO2. MFE UNDER-covers in both and
more so in HO2. The sign never flips; only the magnitude grows.

## Isotonic transfer — a consistent direction, NOT a demonstrated effect

| number | M/A |
|---|---|
| cells where recalibration improved HO2's point-estimate gap | M, 76 of 80 |
| share of the HO2-over-HO1 excess removed, on the means | M, **41%** |
| cells where the before/after intervals are **indistinguishable** | **M, 80 of 80** |
| cells labelled CLOSED | **M, 0** |
| cells labelled not closed | **M, 0** |

**READ THIS CAREFULLY AND DO NOT OVERSTATE IT.** The point estimates improve
almost everywhere and remove about 41% of the excess. But every one of the
eighty before/after comparisons has overlapping day-clustered intervals, so at
this sample size **no cell can be declared either closed or not closed.** The
correct statement is: a consistent direction of improvement with no demonstrated
effect. Anything stronger than that is not supported by these intervals.

Four cells got worse under recalibration, all Climatology, all small: ALL/MAE 2h
(2.17 -> 2.47), ALL/MAE 10h (3.19 -> 3.28), TRENDING/MAE 5h (3.83 -> 4.07),
TRENDING/MFE 2h (3.38 -> 3.40). A zero-capacity baseline has no per-episode
structure for a per-episode map to exploit.

Best single transfer: ALL/MFE/Linear QR/10h, 3.77pp -> 1.89pp.

## Pass/fail — DEMOTED, and it still says nothing

| number | M/A |
|---|---|
| cells passing the run-1 screen on the full held-out block | M, **0 of 80** |

Identical to run 1. The screen is 5 interval checks at 95%, so a perfectly
calibrated cell clears it only 77.4% of the time and ~18 of 80 fail on chance
alone. A binary verdict on that cannot separate a 1.06pp gap from a 5.45pp one,
which is the whole reason the gap and the skill tables now lead and this sits in
an appendix.

## What the HALVES ANALYSIS changes about the first run's conclusion

| claim | status |
|---|---|
| "0 of 80 cells pass calibration" | still true, and still uninformative |
| "the description is not trustworthy on this block" | **TOO BLUNT.** It is well calibrated on HO1 (1.06pp mean gap) and poorly on HO2 (3.05pp). The block is not uniform. |
| "the cause is the period, not the features" | **SUPPORTED AND SHARPENED.** Climatology (zero capacity) and QTREE (most flexible) miss by similar amounts in the same direction, and the damage is 80/80 in the back half. |
| "the features describe something, correctness unestablished" | **UPGRADED.** 58 of 60 conditional cells show positive skill on BOTH halves; the best is +3 to +4% with intervals excluding zero in each half separately. |

## An arithmetic error I made reading this table, recorded so it is not repeated

My first aggregation of the summary table split on whitespace and treated the
model name as one field. `Linear QR` is TWO fields where `Climatology`, `QTREE`
and `kNN` are one, so every Linear QR row was shifted by one column and the
aggregates were wrong — they read HO1 1.63 / HO2 2.58 / ratio 1.59x and reported
0 negative-skill cells. Corrected by indexing from the END of the row
(`$(NF-4)` through `$NF`): HO1 1.06 / HO2 3.05, and 2 negative cells. The
published numbers above are the corrected ones.

---

# Drift recurrence track, 2026-10-11 — `logs/drift_recur_30m.log` (saved)

Climatology only, three historical cuts, ALL population. Asks whether the
near/far calibration drift found at the 2026-07-18 cut recurs elsewhere in
history. **This track never reads the block the halves analysis scored** — every
test window ends before 2026-07-18, asserted three ways below.

NAMING. "Run 2" MEANT two different things earlier in this file: the deferred
1-minute rerun (line ~515) and the held-out-halves analysis (line ~540). This
track calls them the **1-MINUTE RERUN** and the **HALVES ANALYSIS** and numbers
nothing. The sections above were renamed to match on 2026-10-11.

## Design — derived, not chosen

| number | M/A |
|---|---|
| earliest admissible cut `2025-05-27` = episode day #251 | M, exactly 250 episode days precede it |
| latest admissible cut `2026-04-29` = 80 episode days before `2026-07-18` | M |
| window 337 days, spacing 150 days -> **3 cuts**: `2025-05-27`, `2025-10-24`, `2026-03-23` | M |
| a 4th cut at 150 needs 3 gaps = 450 days against 337; would land `2026-08-20`, 113 days past the latest admissible cut | M |
| 4 cuts DO fit at 112-day spacing; 113 misses by 2 days. Neither is "roughly 150 apart" | M |
| MIN_TRAIN_DAYS 250, HALF_DAYS 40, MIN_HALF_ROWS 1,000 | **A**, typed from the brief |

| cut | train days | train rows | near rows | far rows | q05 SE near/far |
|---|---|---|---|---|---|
| 2025-05-27 | 250 | 5,391 | 1,138 | 1,569 | 0.65 / 0.55 pp |
| 2025-10-24 | 400 | 11,238 | 2,906 | 3,260 | 0.40 / 0.38 pp |
| 2026-03-23 | 550 | 24,382 | 4,610 | 6,342 | 0.32 / 0.27 pp |

## The three audits

| number | M/A |
|---|---|
| rows scored with `day >= 2026-07-18` | **M, 0** (must be 0) |
| rows shared between any two cuts' test windows | **M, 0** |
| train rows whose 10.5h outcome window crosses the cut | M, 5 / 18 / 29 = **0.09%–0.16%** |

The crossing count is why no embargo is applied. The reason is the *magnitude*,
not the model class: an unconditional quantile is still a sample estimate, and
contamination pulls it toward near-half conditions — which would *inflate*
far-minus-near, the direction of the hypothesis. At 0.1% it cannot move a
quantile. For a conditional model the same shortcut would not be safe.

## Precision — no cut can resolve the effect

| cut | median far−near CI width | status |
|---|---|---|
| 2025-05-27 | M, 3.24 pp | UNDERPOWERED |
| 2025-10-24 | M, 3.32 pp | UNDERPOWERED |
| 2026-03-23 | M, 2.54 pp | UNDERPOWERED |

The effect being chased is **1.99pp** (halves analysis, 3.05 − 1.06, quoted from
line ~571, not recomputed). Every cut's interval is wider than the whole effect,
so **0 of 3 cuts are decisive** and none votes on the majority. The screen and
its threshold were written before the run.

## The gap table — mean |actual − nominal| over the 5 levels, pp

All M. Day-clustered 95% intervals. `sign[n/5]` = how many of the five levels
miss that way. OVER = envelope too wide.

| cut | dir | h | near | [CI] | far | [CI] | far−near | [CI] | near sign | far sign |
|---|---|---|---|---|---|---|---|---|---|---|
| 2025-05-27 | MAE | 0.5h | 1.72 | [0.91,3.09] | 1.43 | [0.68,3.17] | −0.28 | [−1.86,+1.38] | UNDER[2/5] | OVER[5/5] |
| 2025-05-27 | MAE | 1h | 1.61 | [0.87,3.24] | 1.07 | [0.58,2.58] | −0.54 | [−2.30,+1.05] | UNDER[2/5] | OVER[2/5] |
| 2025-05-27 | MAE | 2h | 1.75 | [0.88,3.33] | 0.89 | [0.52,2.59] | −0.86 | [−2.21,+0.80] | UNDER[2/5] | OVER[3/5] |
| 2025-05-27 | MAE | 5h | 1.09 | [0.60,2.55] | 1.17 | [0.47,3.01] | +0.08 | [−1.37,+1.76] | UNDER[3/5] | UNDER[2/5] |
| 2025-05-27 | MAE | 10h | 0.88 | [0.61,2.66] | 0.76 | [0.51,2.84] | −0.12 | [−1.54,+1.83] | UNDER[3/5] | UNDER[1/5] |
| 2025-05-27 | MFE | 0.5h | 1.72 | [0.91,3.09] | 1.43 | [0.68,3.17] | −0.28 | [−1.86,+1.38] | OVER[3/5] | UNDER[0/5] |
| 2025-05-27 | MFE | 1h | 2.18 | [1.12,3.46] | 1.46 | [0.82,3.32] | −0.72 | [−2.31,+1.11] | OVER[3/5] | UNDER[0/5] |
| 2025-05-27 | MFE | 2h | 2.25 | [1.58,3.58] | 1.06 | [0.65,2.89] | −1.18 | [−2.47,+0.77] | OVER[3/5] | UNDER[0/5] |
| 2025-05-27 | MFE | 5h | 1.25 | [0.87,3.00] | 0.76 | [0.38,2.77] | −0.49 | [−1.95,+1.24] | OVER[3/5] | UNDER[0/5] |
| 2025-05-27 | MFE | 10h | 1.04 | [0.72,2.75] | 1.26 | [0.59,3.11] | +0.22 | [−1.40,+1.73] | OVER[2/5] | UNDER[2/5] |
| 2025-10-24 | MAE | 0.5h | 2.11 | [0.90,4.00] | 1.19 | [0.79,2.45] | −0.92 | [−2.53,+0.79] | UNDER[1/5] | OVER[3/5] |
| 2025-10-24 | MAE | 1h | 1.58 | [0.83,3.15] | 0.67 | [0.53,1.89] | −0.90 | [−2.20,+0.49] | UNDER[1/5] | OVER[2/5] |
| 2025-10-24 | MAE | 2h | 1.30 | [0.64,2.79] | 0.83 | [0.45,1.92] | −0.46 | [−1.95,+0.81] | UNDER[1/5] | UNDER[2/5] |
| 2025-10-24 | MAE | 5h | 1.23 | [0.55,2.78] | 0.33 | [0.27,2.01] | −0.90 | [−2.09,+0.73] | UNDER[1/5] | OVER[5/5] |
| 2025-10-24 | MAE | 10h | 0.86 | [0.57,2.48] | 1.36 | [0.45,3.03] | +0.49 | [−1.31,+1.99] | OVER[2/5] | OVER[5/5] |
| 2025-10-24 | MFE | 0.5h | 2.11 | [0.90,4.00] | 1.19 | [0.79,2.45] | −0.92 | [−2.53,+0.79] | OVER[4/5] | UNDER[2/5] |
| 2025-10-24 | MFE | 1h | 1.79 | [0.75,4.01] | 0.99 | [0.50,2.26] | −0.80 | [−2.77,+0.94] | OVER[4/5] | UNDER[2/5] |
| 2025-10-24 | MFE | 2h | 1.33 | [0.85,3.26] | 1.25 | [0.56,2.65] | −0.08 | [−2.04,+1.57] | OVER[3/5] | UNDER[1/5] |
| 2025-10-24 | MFE | 5h | 1.37 | [0.75,2.91] | 2.47 | [0.66,4.71] | +1.11 | [−1.20,+3.28] | OVER[3/5] | UNDER[0/5] |
| 2025-10-24 | MFE | 10h | 0.99 | [0.65,2.91] | 2.18 | [0.56,4.62] | +1.19 | [−1.42,+3.42] | UNDER[2/5] | UNDER[0/5] |
| 2026-03-23 | MAE | 0.5h | 1.30 | [0.79,2.14] | 1.54 | [1.11,2.33] | +0.24 | [−0.67,+1.19] | UNDER[2/5] | UNDER[1/5] |
| 2026-03-23 | MAE | 1h | 1.05 | [0.47,2.07] | 1.53 | [1.06,2.21] | +0.48 | [−0.70,+1.40] | UNDER[1/5] | UNDER[2/5] |
| 2026-03-23 | MAE | 2h | 0.91 | [0.41,2.40] | 1.42 | [0.93,2.06] | +0.52 | [−1.08,+1.46] | UNDER[1/5] | UNDER[2/5] |
| 2026-03-23 | MAE | 5h | 0.88 | [0.32,2.78] | 0.98 | [0.62,1.76] | +0.10 | [−1.78,+1.09] | UNDER[0/5] | OVER[3/5] |
| 2026-03-23 | MAE | 10h | 0.79 | [0.35,2.70] | 0.59 | [0.41,2.09] | −0.19 | [−1.80,+1.19] | UNDER[1/5] | UNDER[3/5] |
| 2026-03-23 | MFE | 0.5h | 1.30 | [0.79,2.14] | 1.54 | [1.11,2.33] | +0.24 | [−0.67,+1.19] | OVER[3/5] | OVER[4/5] |
| 2026-03-23 | MFE | 1h | 1.34 | [0.53,2.47] | 0.97 | [0.56,1.94] | −0.37 | [−1.71,+0.84] | OVER[4/5] | OVER[4/5] |
| 2026-03-23 | MFE | 2h | 1.16 | [0.53,2.57] | 0.80 | [0.63,1.66] | −0.35 | [−1.64,+0.83] | OVER[4/5] | OVER[2/5] |
| 2026-03-23 | MFE | 5h | 1.06 | [0.42,2.75] | 0.94 | [0.41,2.15] | −0.12 | [−1.94,+1.39] | OVER[4/5] | UNDER[1/5] |
| 2026-03-23 | MFE | 10h | 1.13 | [0.46,2.90] | 0.89 | [0.37,2.34] | −0.24 | [−2.18,+1.41] | OVER[3/5] | UNDER[1/5] |

### The 0.5h rows are 3 cells, not 6 — and that is arithmetic, not a bug

At k=1 the running maxima collapse: `MAE(1) = −MFE(1)` exactly. Climatology's
quantiles of `−X` are the negated, reversed quantiles of `X`, and the quantile
set {5,25,50,75,95} is symmetric, so **|actual − nominal| averaged over the five
levels is invariant under negation.** Hence 1.72/1.72, 2.11/2.11, 1.30/1.30 in
the near column and the same in the far. Verified on synthetic normals: gap
identical to 4 dp, signed bias exactly negated (+0.5000 / −0.5000 pp).

So the effective cell count is **27, not 30**, and the signed-bias columns at
0.5h are mechanically opposite rather than independently measured.

## The tallies

| criterion | M/A | all 30 cells | decisive cells |
|---|---|---|---|
| ORDERS — far gap > near gap | M | **10 of 30, 33.3%** | none exist |
| ORDERS* — far−near interval excludes zero | M | **0 of 30, 0.0%** | none exist |
| SIGN SAME — near and far agree | M | 12 of 30, 40.0% | none exist |
| AS BEFORE — MAE over / MFE under | M | **2 of 30, 6.7%** | none exist |
| GROWS — 10h gap > 0.5h gap | M | **2 of 12, 16.7%** | — |

| cut | ORDERS | SIGN SAME | AS BEFORE | vote |
|---|---|---|---|---|
| 2025-05-27 | M, 2/10 | 2/10 | 0/10 | abstains (underpowered) |
| 2025-10-24 | M, 3/10 | 3/10 | 2/10 | abstains (underpowered) |
| 2026-03-23 | M, 5/10 | 7/10 | 0/10 | abstains (underpowered) |

| number | M/A |
|---|---|
| MAE modal far-half sign across the 3 cuts | M, **both over and under — FLIPS** |
| MFE modal far-half sign across the 3 cuts | M, **both over and under — FLIPS** |

## VERDICT — the rule is ambiguous here and the ambiguity is not resolved

The script printed **UNDERPOWERED — NO VERDICT**, because 0 of 3 cuts are
decisive and its branches test that first.

**The rule as written in prose reaches a different label.** Its
CALENDAR-SPECIFIC condition is "ORDERS <= 50% of decisive cells **OR** the
MAE/MFE sign pattern flips between cuts". The sign-flip clause does not depend
on decisiveness, and it fired for both directions. In the prose ordering
CALENDAR-SPECIFIC is listed before UNDERPOWERED; in the code UNDERPOWERED is
tested first. **Both readings are from the same pre-committed rule and it does
not say which wins. This is a defect in the rule, recorded rather than resolved,
and nothing was edited after the numbers were seen.**

| reading | label | basis |
|---|---|---|
| code branch order | UNDERPOWERED — NO VERDICT | 0 of 3 cuts can resolve a 1.99pp effect |
| prose clause order | CALENDAR-SPECIFIC | the sign pattern flips between cuts, which no amount of power changes |

**The practical conclusion is the same under both: the adaptive correction is not
justified by this table.** What differs is whether recurrence was tested and
rejected, or never tested at all.

### What the point estimates say, stated separately from the verdict

Three things run *opposite* to the halves analysis, and none of them is a
null result:

- **ORDERS is 33.3%, not 50%.** In 20 of 30 cells the far half is *better*
  calibrated than the near half. The 2026-07-18 finding was the reverse.
- **AS BEFORE is 2 of 30.** The specific pattern — MAE over-covers, MFE
  under-covers — is essentially absent. At 2025-05-27 it is exactly inverted:
  MAE near under-covers at all five horizons, MFE near over-covers at all five.
- **GROWS is 2 of 12.** The gap mostly *shrinks* with horizon here (ratios
  0.38x–0.88x in ten of twelve), against 1.5x–3.2x in the halves analysis.

Read with care. Every interval is wide, ORDERS* is 0 of 30, the 27 effective
cells are not independent, and a tally of point estimates is not a test. This is
evidence against recurrence, not proof of absence.

## What this does to the halves analysis's conclusion

| claim | status |
|---|---|
| "the drift is concentrated in the back half, 80 of 80 cells" | still true **of that block**. Not reproduced at three earlier cuts. |
| "the sign never flips; only the magnitude grows" | **not reproduced.** Both directions' signs flip across these cuts. |
| "an adaptive correction is worth building" | **not supported.** No cut can resolve the effect, and the point estimates point the other way. |
| isotonic recalibration — "a consistent direction, no demonstrated effect" | untouched; this track fits nothing. |

---

# 1-MINUTE RERUN — matched 30m vs 1m, 2026-10-11 — `logs/envelope_match1m.log` (saved)

Run tag: **MATCH1M**. `envelope.py --stage match1m`, 1,259s, 333-line log.
Matched design: both target sources on the IDENTICAL rows, same split, same four
models, same day resamples. Only the target's bar resolution differs.

**The headline is the `1m − 30m` difference column, not the levels.** The two gap
columns and both skill columns are a THIRD look at rows already scored twice, so
they are confirmatory. The difference is a within-row paired contrast — identical
rows, split and resamples, only the target changing — so whatever the reuse did
to the levels it did to both sides of the subtraction equally.

## Population — rule B, and why

| rule | M/A | episodes | fit | held out | pairs | span |
|---|---|---|---|---|---|---|
| A neither leg at the backfill wall | M | 9,240 | 4,977 | 4,263 | 462 | 2025-07-11 → 2026-10-04 |
| **B each leg's 1m history spans the window — USED** | M | **53,757** | 35,693 | **18,064** | 3,000 | 2025-06-26 → 2026-10-04 |
| C both legs' 1m reaches their own listing date | M | 5,240 | 2,588 | 2,652 | 262 | 2025-09-05 → 2026-10-04 |

| number | M/A |
|---|---|
| instruments with a 1-minute file | M, 212 of 212 |
| instruments whose 1m begins at the backfill wall 2025-06-26/27 | M, **131**; 81 reach further back |
| split actually used | M, train 22,645 / val 13,048 / **held out 18,064**, 79 held-out days |

Rule A was the brief's. It was rejected on measurement: 46% of it is held out
against 30% of the full set, and its 462 pairs are selected by which instruments
were backfilled first. Rule B's exclusion is purely temporal, keeps all 3,000
pairs, and its held-out arm is **exactly the 18,064 rows the first run scored**.

**B is a SPAN test, not a presence test**, so its interior gaps were measured
before it was adopted, not inferred from the mask:

| number | M/A |
|---|---|
| missing minutes across rule B | M, **192 of 32,307,957 = 0.0006%** |
| episodes with no missing minute | M, 53,750 of 53,757 |
| episodes affected / deepest gap | M, **7** / 41 minutes, none above 60 |

## The 30-minute arm reproduces run 1 — the sanity check, and it passes

| cell | 30m arm here | the HALVES ANALYSIS |
|---|---|---|
| MFE / Linear QR / 10h skill | M, **+3.77%** [+3.03, +4.44] | HO1 +4.13%, HO2 +3.33% (pooled ≈ 3.7%) |

Fitted on 22,645 train rows against run 1's 22,683, scored on the identical
18,064. A 30-minute level far from run 1's would have meant this stage was
broken; it lands between the two halves where it should.

## Structural correctness — enforced

| number | M/A |
|---|---|
| quantile crossings, all 16 (source, direction, model) blocks | M, **0.000%** |
| horizon enforcement, QTREE | M, 0.158% – 0.679% |
| horizon enforcement, Linear QR | M, 0.000% – 0.002% |
| horizon enforcement, Climatology and kNN | M, 0.000% (cannot violate) |

## The two 1-minute correctness checks — and the tolerance that was wrong

| number | M/A |
|---|---|
| max \|1m path − 30m close\| at the 21 marks | M, **3.314e-06** over 1,128,893 comparisons |
| as a fraction of its allowed budget (8 float32 ulps) | M, **0.062** — must be < 1 |
| 1-minute ≥ 30-minute violations | M, **0** |
| deepest shortfall / its budget fraction | M, −9.374e-07 / **0.062** |

**BOTH CHECKS ABORTED FIRST TIME AND BOTH MISDIAGNOSED THE CAUSE.** Two separate
precision errors, recorded because the abort messages sent the reader hunting a
bar-label bug that did not exist:

1. **The minute grid was float32.** The spread divides by `meta.sigma`, min
   1.79e-03, so float32's ~1e-7 relative error lands at ~3e-4. Reproduction read
   1.451e-04 against a 1e-6 threshold; dominance found 2,789 violations as deep
   as −5.7e-05. Fixed by building the grid in float64 — 985MB for 212
   instruments. Loosening the tolerances instead would have turned the dominance
   check from an exact structural guarantee into a precision floor.
2. **`disloc.npz` stores `outcomes` as float32, and |Y| reaches 96.1**, where
   float32 spacing is 7.6e-06. So the 30-minute reference carries ~1e-05 of its
   own error and the float64 1-minute path is MORE precise than the thing it is
   checked against. A fixed 1e-6 threshold was unreachable by construction. Both
   tolerances are now per-element, in float32 ulps at the compared magnitude.
3. **A third error introduced by fixing the second.** Scaling the dominance
   tolerance by the TARGET's magnitude gives a denormal when the target is near
   zero; the reported ratio came out 1.1e+30. The target is a max of differences
   of `Y`, so its error is set by max\|Y\| over the window, not by the size of
   the difference. Fixed, plus a 1e-9 absolute floor under every ulp budget.

## The understatement — twice what this project assumed

| direction | h | M/A | mean add | mean 30m | larger by |
|---|---|---|---|---|---|
| MAE | 10h | M | **+0.681 σ** | 2.119 | **32.1%** |
| MFE | 10h | M | **+0.457 σ** | 2.053 | **22.3%** |

The figure carried in `envelope.py` for months was "roughly 0.3 sigma,
one-sided". It is 0.46 to 0.68 sigma at 10 hours. **Ignore the 0.5h row of that
table**: at k=1 the 30-minute target is a SINGLE observation against the minute
target's thirty, so that comparison is structurally extreme rather than
informative. The same caveat applies to the eight 0.5h gap cells below.

## THE RESULT — the fix helps MFE and hurts MAE, and the split is perfect

| number | M/A |
|---|---|
| cells where the 1-minute gap is smaller (point estimate) | M, 20 of 40 |
| cells where the paired interval excludes zero on the better side | M, **16 of 40** |

**The 20 of 40 is not a null and reading it as one would be wrong.** It is the
20 MFE cells. The split by direction is exact:

| direction | cells | gap direction | intervals excluding zero |
|---|---|---|---|
| **MAE** | 20 | **GROWS — all 20** | **20 of 20** |
| **MFE** | 20 | **SHRINKS — all 20** | 16 of 20 |

The four MFE cells whose intervals include zero are three of the four 0.5h cells
plus MFE/1h/Climatology (−0.40 [−0.76, +0.03]). Excluding the structurally
extreme 0.5h rows: MAE 16 of 16 grow, MFE 15 of 16 shrink.

### Paired gap difference, 1m − 30m, in pp — selected

| dir | h | model | 30m gap | 1m gap | 1m − 30m | [95% CI] |
|---|---|---|---|---|---|---|
| MAE | 1h | kNN | 1.70 | 2.78 | **+1.07** | [+0.52, +1.64] |
| MAE | 2h | kNN | 2.15 | 3.15 | +1.00 | [+0.54, +1.44] |
| MAE | 10h | Linear QR | 2.98 | 3.59 | +0.61 | [+0.23, +0.89] |
| MFE | 1h | kNN | 1.71 | 0.97 | **−0.73** | [−1.05, −0.44] |
| MFE | 2h | Linear QR | 2.10 | 1.42 | −0.69 | [−0.94, −0.42] |
| MFE | 5h | Linear QR | 2.89 | 2.34 | −0.55 | [−0.81, −0.30] |
| MFE | 10h | Linear QR | 2.79 | 2.41 | −0.38 | [−0.57, −0.21] |

### One mechanism, opposite consequences — coverage at 10h

| dir | model | src | q5 | q25 | q50 | q75 | q95 |
|---|---|---|---|---|---|---|---|
| MAE | Climatology | 30m | 4.5 | 28.1 | 53.8 | 78.0 | 95.9 |
| MAE | Climatology | 1m | 5.8 | 29.0 | 54.4 | 78.5 | 96.2 |
| MFE | Climatology | 30m | 4.1 | 20.9 | 45.3 | 72.0 | 94.4 |
| MFE | Climatology | 1m | 4.2 | 21.3 | 45.8 | 72.5 | 94.5 |

**The 1-minute target moves held-out coverage UP in both directions.** MAE was
already OVER-covering, so moving up takes it further from nominal. MFE was
UNDER-covering, so moving up takes it toward nominal. That is the sign pattern
the HALVES ANALYSIS established — MAE over, MFE under, sign stable — and it is
what makes a single uniform correction help one direction and hurt the other.
The shift is larger for MAE (~+1.0 to +1.3pp at q5) than MFE (~+0.1 to +0.5pp),
tracking the larger understatement on that side (+0.681 σ against +0.457 σ).

## Skill — better on the 1-minute target everywhere, and much better for MFE

LEVELS, confirmatory only. Both columns carry intervals; the columns are NOT
differenced because they score different targets against different climatologies.

| dir | h | model | 30m skill | 1m skill |
|---|---|---|---|---|
| MFE | 1h | QTREE | +2.05% [+1.57,+2.59] | **+4.88% [+3.96,+5.76]** |
| MFE | 2h | Linear QR | +2.92% [+2.29,+3.51] | **+5.23% [+4.32,+6.27]** |
| MFE | 10h | Linear QR | +3.77% [+3.03,+4.44] | +4.94% [+4.15,+5.72] |
| MAE | 10h | Linear QR | +2.02% [+1.44,+2.76] | +2.66% [+2.02,+3.48] |

| number | M/A |
|---|---|
| conditional cells where 1m skill exceeds 30m skill (point estimate) | M, **30 of 30** |
| MFE cells where the two intervals are DISJOINT | M, 12 of 15 (the 3 overlapping are all 10h) |
| MAE cells where the two intervals are disjoint | M, **0 of 15** |

**DO NOT QUOTE A RATIO HERE.** No paired contrast between the skill columns was
computed, so "+4.88 against +2.05" is not a measured difference — two
non-overlapping intervals on two different targets do not license a paired claim.
The defensible statement: on the 1-minute target the features describe the MFE
envelope better than they describe the 30-minute-close envelope, by an amount
this run indicates strongly and did not measure.

## What this changes

| claim | status |
|---|---|
| "the understatement is roughly 0.3 sigma" | **WRONG. 0.46–0.68 σ at 10h.** Docstring corrected. |
| "climatology is biased the same way, so comparative skill should be largely unaffected" | **NOT NEUTRAL.** Climatology's own gap moves +0.51pp (MAE 10h) and −0.28pp (MFE 10h) with intervals excluding zero. The bias is shared in direction, not in effect. |
| "MFE is more describable than MAE" (HALVES ANALYSIS, +4.13 vs +1.62) | **STRENGTHENED.** On the 1-minute target MFE skill is +4.2 to +5.2% at every horizon against MAE's +1.1 to +2.7%. |
| the 1-minute rerun is DEFERRED and blocked | **CLOSED** for 53,757 of 60,000 episodes. The remaining 6,243 are pre-wall and permanently unmeasurable. |

## What it does NOT settle

The fit block loses its first nine months to the backfill wall, so nothing here
describes the envelope over the whole history. The 6,243 excluded episodes cannot
be recovered — the exchange does not serve those minutes. And every level in this
run is a third look at twice-scored rows; only the paired difference columns are
new measurement.

---

# GEV parametric envelope — BUILT AND DROPPED, 2026-10-11

Tag: **GEV**. No log: the family was withdrawn before any run, on a structural
finding, not on a score.

The extreme-value argument for Fréchet (ξ > 0) is about the **upper** tail and it
is sound. The failure is the **lower** tail. Fréchet's support has a floor at
μ − σ/ξ that every training row must clear, and MAE/MFE are deliberately
**unclamped** — clamping put ~45% of the k=1 mass at exactly 0 — so their lower
tails hold the large moves in the other direction.

| train-only lower tail, σ | M/A | min | p0.1 | p1 | median |
|---|---|---|---|---|---|
| 30m MFE 0.5h | M | **−61.30** | −18.88 | −4.29 | +0.07 |
| 30m MFE 10h | M | −17.93 | −7.15 | −2.45 | +1.55 |
| 30m MAE 0.5h | M | −32.97 | −6.66 | −2.91 | −0.07 |
| 1m MFE 0.5h | M | −21.05 | −2.59 | −0.45 | +0.47 |
| 1m MAE 10h | M | −5.44 | −1.29 | −0.33 | +1.81 |

One row at −61σ drags the floor down to it, and with log-σ linear in the
features that widens the envelope for every episode. A reviewer fitted on train
and scored on **val** — the iteration-count block, otherwise never scored — and
found 30m MFE 0.5h putting 0.3% of val below q5 and 99.6% below q75, with the
shape fallback firing in 4 of 8 cells. Those val figures are the reviewer's,
recorded here as a diagnostic, not as a result of this project's scoring.

The synthetic recovery test (μ/σ/ξ 1.30/0.80/0.37 → 1.288/0.789/0.3707) passed
and **could not have caught this**: its draws had no lower outliers.

**DECIDED 2026-10-11: DROPPED.** The code was removed from `envelope.py`; this
section is the record. Three reasons:

- Its only argument was extreme-value theory, which licenses Fréchet for a
  **clamped** running maximum. Clamping was rejected for a measured reason (54.6%
  of MAE mass at zero, vacuous low quantiles). Without the theory, an
  unbounded-tail family is just another parametric curve, and QTREE and kNN
  already fit the shape without assuming one.
- A sixth learner adds ten cells per source and more comparisons without a new
  question, and the measured limit here is that dispersion cannot move the score;
  only the centre does.
- The phase asks whether five features describe how far the spread travels. A
  better tail family does not move that question.

If tail modelling ever becomes the question, the clean version is a
peaks-over-threshold fit on the **upper** tail only, where the argument actually
applies. That is a separate plan item, not a replacement here.

# Cache and refit corrections, 2026-10-11

| number | M/A |
|---|---|
| CQR refit vs cache, OLD one-pass comparison, worst per QTREE group | M, 5.88 / 1.98 / **14.49** / 3.08 σ — all four groups disagree |
| same, NEW two-pass comparison | M, **0.000e+00** in all four |
| Climatology and kNN refit vs cache, two-pass | M, 0.000e+00 in all eight groups |
| `envelope_preds_match1m.npz` | M, 80 keys, no fingerprint → LEGACY; verifiable, worst disagreement 0.0 |

The old CQR check applied only the quantile pass while the cache had been
written after both; it would have aborted on every run and advised deleting a
correct cache. The disagreement was not rounding — up to 14.5σ, where horizon
enforcement lifted a QTREE prediction whose shorter-horizon fit exceeded its
longer one.

# Dependence — the 30m/0.5h identity, 2026-10-11

| number | M/A |
|---|---|
| max\|MAE + MFE\| at 30m, k=1, all rows | M, **0.00e+00** — MAE is exactly −MFE |
| same at 30m, k ≥ 2 | M, 39.1 – 92.9 |
| same at 1m, every horizon | M, 272.6 — no identity |

That cell would have printed CLEARS BAR on arithmetic alone. It is now detected
from the data and excluded from the decision.

---

# CQR on QTREE — calibrated on val, tested on HO1 and HO2, 2026-10-11

Tag: **CQR**. `envelope.py --stage cqr`, log `logs/envelope_cqr.log` (246 lines).
Population: the 53,757-episode 1-minute-measurable set, both target sources.
HO1 8,200 rows / 39 days, HO2 9,864 / 40, boundary 2026-08-26. Calibration block:
val, 13,048 rows, 2026-05-01 → 2026-07-17.

| number | M/A |
|---|---|
| QTREE refit vs cached held-out predictions, after two-pass enforcement | M, **0.000e+00** in all 20 cells |
| conformal widths, outer pair (5,95) | M, −0.086 to +0.0001 σ — almost all NEGATIVE: QTREE's raw intervals were slightly too wide on val and CQR tightens them |
| conformal widths, inner pair (25,75) | M, −0.036 to +0.0024 σ |
| median shift, MAE | M, **−0.013 to −0.156** σ, every cell negative |
| median shift, MFE | M, **+0.002 to +0.102** σ, every cell positive |
| q-axis reorder after CQR | M, 0.000–0.001% |
| h-axis reorder after CQR | M, 0.130–0.435% |

The median shifts carry the known sign pattern: MAE over-covers, so its median moves down; MFE under-covers, so its median moves up.

**RETRACTED: "this correction is mostly a location shift, not a change of width."** It does not follow from the code. `apply_cqr` moves **only q50** by the median shift; the other four levels move only by their pair's width. And the widths are not small next to the shifts — 30m MFE 5h: w(5,95) −0.086 against a shift of +0.071; 30m MAE 1h: −0.065 against −0.015. Every outer width is negative, so CQR **tightened every interval**. Which of the two carries the gap reduction is settled by the per-level breakdown below, not asserted.

## The guaranteed quantity — interval coverage — CANNOT ADJUDICATE

| number | M/A |
|---|---|
| raw (5,95) interval coverage, nominal 90% | M, HO1 89.5–91.9%, HO2 88.9–91.3% |
| raw (25,75) interval coverage, nominal 50% | M, HO1 49.3–51.2%, HO2 48.4–52.7% |
| cells with CQR coverage ≥ nominal | M, HO1 21 of 40, HO2 18 of 40 |

**The 21-vs-18 count is not evidence of anything, and the log line claiming it "IS the exchangeability failure" was wrong when I wrote it.** Raw interval coverage already sits within ~1pp of nominal. CQR moves it by tenths of a point. The table has **no intervals**. A strict ≥ count on numbers that close is near a coin flip.

The reason: the miscalibration this project measures is a **level shift** that pushes both ends of an interval the same way. Interval coverage barely registers that, and it is exactly what a symmetric two-sided correction is built to fix. The one block that matches the stated hypothesis cleanly: 1m MAE, outer pair. CQR is ≥ 90% on HO1 at all five horizons and 88.1–89.0% on HO2 at all five. Without intervals, that's a pattern, not a result.

## The 5-level gap — paired, and it runs AGAINST the stated hypothesis

| number | M/A |
|---|---|
| HO1: gap smaller after CQR, point estimate | M, 20 of 20 |
| HO1: paired interval excludes zero | M, **3 of 20** |
| HO2: gap smaller after CQR, point estimate | M, 18 of 20 |
| HO2: paired interval excludes zero | M, **13 of 20** |

| cell | M/A | raw | CQR | CQR − raw [95% CI] |
|---|---|---|---|---|
| 1m MAE 10h HO2 | M | 4.73 | 4.13 | −0.61 [−0.70, −0.52] |
| 1m MFE 10h HO2 | M | 3.12 | 2.56 | −0.56 [−0.65, −0.45] |
| 30m MFE 5h HO2 | M | 3.98 | 3.51 | −0.47 [−0.54, −0.38] |
| 1m MAE 1h HO1 | M | 1.98 | 1.49 | −0.49 [−0.56, −0.23] |

**Stated in advance:** the correction holds on HO1, which abuts val, and decays on HO2. **Measured:** the improvement is demonstrated on HO2 in 13 of 20 cells and on HO1 in only 3. Point-estimate sizes are similar in both halves, about −0.1 to −0.7pp. The hypothesis was wrong in the form it was written.

**UNVERIFIED, and withdrawn as an explanation:** "a val-fitted location shift helps most where the drift is largest". It rested on the retracted location-shift claim above. The per-level breakdown replaces it.

HO1 is already near-calibrated (raw gaps 0.35–2.0pp), and its intervals are wide and lopsided, e.g. −0.29 [−0.44, +0.40]. Near zero, |actual − nominal| folds over in the bootstrap, so the paired difference loses resolution. HO1 is therefore read on **signed** deviation, which does not fold — see the breakdown below.

## Against the isotonic result

| | isotonic (HALVES ANALYSIS) | CQR on QTREE |
|---|---|---|
| point estimates improved | 76 of 80 | 38 of 40 |
| improvement demonstrated (interval excludes zero) | **0 of 80** | **16 of 40** |

**What is demonstrated, worded to what was tested:** a correction fitted on val shrinks the 5-level calibration gap, in 16 of 40 cells by paired intervals excluding zero, against roughly 1 per half (2.5%) expected by chance. **CQR's guarantee itself is untested** — the interval-coverage table above cannot adjudicate. Isotonic never cleared even the gap test. Two caveats against reading that too broadly:

- The two use different populations (match1m against the full 30m set) and different model scope (QTREE only against all four models).
- The levels here are a later look at rows already scored. The CQR − raw differences are within-row contrasts, and those are the new measurement.

# MAE/MFE dependence — measured, 2026-10-11

Tag: **DEPENDENCE**. `dependence.py`, log `logs/dependence.log` (99 lines, 51s).
Model QTREE. PITs from the match1m cache, nothing refitted. QTREE's cached predictions were confirmed exact by CQR's refit check, 0.000 in all 20 cells.

| src | h | M/A | raw Spearman | conditional (PIT) Spearman [95% CI] |
|---|---|---|---|---|
| 30m | 0.5h | M | −1.0000 | −1.0000 — **IDENTITY, excluded** |
| 30m | 1h | M | −0.854 | **−0.860** [−0.868, −0.848] |
| 30m | 2h | M | −0.770 | −0.789 [−0.799, −0.776] |
| 30m | 5h | M | −0.677 | −0.716 [−0.729, −0.698] |
| 30m | 10h | M | −0.626 | −0.680 [−0.693, −0.665] |
| 1m | 0.5h | M | −0.591 | −0.661 [−0.677, −0.644] |
| 1m | 1h | M | −0.570 | −0.646 [−0.662, −0.625] |
| 1m | 2h | M | −0.552 | −0.635 [−0.652, −0.611] |
| 1m | 5h | M | −0.526 | −0.612 [−0.632, −0.584] |
| 1m | 10h | M | −0.513 | −0.607 [−0.624, −0.587] |

| number | M/A |
|---|---|
| non-identity cells clearing both bars (interval excludes zero AND \|ρ\| > 0.125) | M, **9 of 9** |
| HO1 vs HO2 | M, same sign and size in every cell, e.g. 1m 10h −0.619 / −0.594 |
| PIT boundary mass (exact 0 or 1) | M, 8.6–10.2% per series |

**The pre-committed rule says build.** Three readings matter before anyone does:

- **Conditioning made it stronger, in every cell.** This is what the raw-vs-PIT columns exist to show. Volatility, the positive mechanism, is what the features describe, so conditioning on them removes it. That leaves the shared-endpoint trade-off, the negative mechanism, more exposed.
- **It is strongest where a path has the fewest steps:** 30m/1h (k=2) at −0.86, decaying with horizon and with resolution. A large share is **path geometry** — a path cannot run far both ways and still end far one way — rather than market behaviour.
- **Geometry is not an artifact.** Unlike the k=1 identity, it is a real constraint on every path, and it is exactly what setting a stop and a target together has to respect. It does mean a copula would mostly be learning that geometry.

**DECIDED 2026-10-11: no copula in this phase.** The correlation and the geometry reading are this phase's finding. Nothing in the phase uses a joint distribution; most of what a copula would learn is path geometry statable in one sentence; and it serves the stop-and-target question, which lives in the strategy phase. The build belongs to that plan item.

# Cache stamp — REFUSED on an unreproduced kNN mismatch, 2026-10-11

| number | M/A |
|---|---|
| `--stage match1m` legacy verification, worst \|refit − cache\| | M, **8.388** (refused) |
| a diagnostic run right after, same code path | M, kNN 7.1–8.8 in all four groups; Climatology and QTREE 0.000 |
| four later reruns, including a verbatim rerun of that diagnostic | M, **0.000** everywhere |
| six fresh processes, hashes of rows / features / kNN neighbour sets | M, identical in all six; 0 rows off the cache |
| inputs between failing and passing runs | M, unchanged: datasets predate the cache, no 1m file modified after 12:55, no concurrent process |

Cause **not found**. Only kNN was affected, and the two failing runs disagree with each other in magnitude. The cache was **not** stamped. A check that fails intermittently on identical inputs is not cleared by rerunning it until it passes.

---

# CQR per-level breakdown, and the cache stamp, 2026-10-11

Tags: **CQR**, **CACHE**. Logs `logs/envelope_cqr.log`, `logs/envelope_match1m_stamp.log`.

## The cache is stamped

| number | M/A |
|---|---|
| legacy verification, worst \|refit − cache\|, all 12 groups / 60 cells | M, **0.000e+00** |
| evidence hashes before vs after the refit | M, identical — rows d44f98ff9b33, Ztr 5537bd6787e8, Zte c4fb641ffc3f, knn_sorted eb5efce82982, knn_raw 70450c9ef957, train 06f694eba6e7 |
| state changed during verification | M, nothing |
| fingerprint written | M, `9e332d92a2945b03…`; CQR confirmed the match on its own load |

The hashes match the six-process determinism test exactly. Stamping on a pass is sound, because the earlier failure mode could only produce false refusals: a 0.000 match across 60 cells cannot happen if the inputs differ. The two refusals earlier the same day remain unexplained. Any recurrence will now print which cell disagreed and whether process state moved.

## Where the gap reduction comes from — the median, entirely

Each level's change is |cov_CQR − q| − |cov_raw − q|, summed over the 20 cells of a half:

| half | level | M/A | mean change, pp | improves | worsens | share of the total reduction |
|---|---|---|---|---|---|---|
| HO1 | q5 | M | −0.136 | 4 | 0 | 8.2% |
| HO1 | q25 | M | +0.262 | 3 | 5 | −15.8% |
| HO1 | **q50** | M | **−1.649** | 4 | 0 | **99.9%** |
| HO1 | q75 | M | −0.071 | 6 | 1 | 4.3% |
| HO1 | q95 | M | −0.057 | 2 | 0 | 3.4% |
| HO2 | q5 | M | +0.134 | 4 | 5 | −9.7% |
| HO2 | q25 | M | +0.311 | 8 | **12** | −22.6% |
| HO2 | **q50** | M | **−1.793** | **16** | 0 | **130.2%** |
| HO2 | q75 | M | −0.042 | 9 | 7 | 3.1% |
| HO2 | q95 | M | +0.013 | 2 | 1 | −0.9% |

**The whole gap reduction is the median shift.** On HO1, q50 carries 99.9% of it and the four pair levels net to 0.1%. On HO2, q50 carries 130% and the widths net to **−30%**: on balance the tightening moved levels *away* from nominal, mostly at q25 (12 cells worse against 8 better).

The retracted claim, "mostly a location shift, not a change of width", **turns out true in effect**. It was unsupported when it was written and is measured now. That order matters, and it is recorded as such.

The consequence is sharper than the claim. **The conformal part of CQR — the guaranteed two-sided widths — contributes nothing net, and hurts on HO2.** All of the benefit comes from the one-sided median recentring, which was the building session's own add-on and is not part of CQR's guarantee.

## HO1 read on signed deviation — the fold-over was hiding it

The change in signed coverage, CQR − raw, does not fold at zero. Counts of cells whose interval excludes zero, by direction:

| half | level | M/A | toward nominal | away from nominal |
|---|---|---|---|---|
| HO1 | q5 | M | 17 | 2 |
| HO1 | q25 | M | 9 | 10 |
| HO1 | **q50** | M | **20** | **0** |
| HO1 | q75 | M | 10 | 7 |
| HO1 | q95 | M | 11 | 3 |
| HO2 | q5 | M | 11 | 8 |
| HO2 | q25 | M | 8 | 12 |
| HO2 | **q50** | M | **20** | **0** |
| HO2 | q75 | M | 11 | 7 |
| HO2 | q95 | M | 9 | 5 |

**The val-fitted median shift moves q50 toward nominal in 20 of 20 cells on BOTH halves.** HO1's 3-of-20 on the absolute gap was fold-over resolution, not a weaker effect. The advance hypothesis — holds on HO1, decays on HO2 — is wrong in both directions: the median correction holds on both.

## What this changes

| claim | status |
|---|---|
| "CQR demonstrated" | **Reworded and narrowed.** A val-fitted **median recentring** shrinks the gap, 20 of 20 cells toward nominal on each half. CQR's conformal widths do not help, and the guarantee is untested. |
| "the correction decays on HO2" (stated in advance) | **Wrong.** The median correction transfers to both halves. |
| "the HO2 gain is drift continuing in the val direction" | **Withdrawn**, as recorded above. The breakdown shows the gain is the q50 shift on both halves; the drift explanation was never tested. |
| what a recalibration should be | **A location correction, not a width correction.** That matches the sign pattern measured since the HALVES ANALYSIS: MAE over, MFE under, both ends moving together. |

---

# CQR as a registry model — trained, 2026-10-11

Tag: **CQR-MODEL**. `envelope.py --stage match1m`, log `logs/envelope_match1m_cqr.log`.
Registry entry "CQR": QTREE fitted on train, conformal widths and median shift
calibrated on val, applied to held out. The other 80 cells were loaded from the
stamped cache (fingerprint 9e332d92a2945b03 matched); only the 20 CQR cells were
fitted, in 74s. The cache now holds 100 cells.

| number | M/A |
|---|---|
| quantile crossings after CQR | M, 0.000% in all four groups |
| horizon enforcement moved | M, 0.153–0.632% |

**Levels are confirmatory** — a later look at already-scored rows.

| model | dir | M/A | mean 30m gap, pp | mean 1m gap, pp |
|---|---|---|---|---|
| **CQR** | MFE | M | **1.72** | **1.28** — lowest of any model |
| Climatology | MFE | M | 1.96 | 1.57 |
| QTREE | MFE | M | 2.12 | 1.60 |
| Linear QR | MFE | M | 2.23 | 1.60 |
| kNN | MFE | M | 2.19 | 1.60 |
| Climatology | MAE | M | **1.79** | **2.36** — lowest |
| **CQR** | MAE | M | 1.82 | 2.56 — lowest conditional model |
| QTREE | MAE | M | 2.04 | 2.86 |
| kNN | MAE | M | 2.17 | 3.07 |
| Linear QR | MAE | M | 2.35 | 3.10 |

| skill vs climatology | M/A | QTREE | CQR |
|---|---|---|---|
| 30m MFE 10h | M | +3.44% [+2.72, +4.08] | +3.60% [+2.90, +4.21] |
| 1m MFE 1h | M | +4.88% [+3.96, +5.76] | +4.92% [+3.98, +5.83] |
| 1m MAE 10h | M | +2.30% [+1.75, +2.96] | +2.51% [+1.93, +3.21] |

CQR's skill point estimate is above QTREE's in **all 20 cells**, by 0.03–0.21 points. The intervals overlap heavily and no paired contrast was computed, so this is a consistent direction, not a measured difference. CQR is **not** the top-skill model: Linear QR remains higher where it led (30m MFE 10h +3.77%).

**Reading:** per the CQR breakdown, this row is effectively QTREE recentred on val. It gives the best-calibrated conditional envelope on both directions, at roughly QTREE's skill. The 1m − 30m direction split holds for it as for every other model: MAE gap grows, MFE gap shrinks.

# Gaussian copula on QTREE marginals — trained, 2026-10-11

Tag: **COPULA**. `copula.py`, log `logs/copula.log` (128 lines, 107s), params in
`envelope_preds_copula.npz` (fingerprinted). Built on the user's decision,
**overriding the earlier deferral to the strategy phase.** It is a separate
deliverable, not a scoreboard row: it cannot change any marginal number.

| number | M/A |
|---|---|
| QTREE refit vs cached held-out marginals | M, 0.000e+00 over 20 cells |
| copula fit block | val, 13,048 rows |
| identity cell 30m/0.5h | skipped; its joint law is the countermonotone bound |

| src | h | M/A | val ρ_s | Gaussian ρ | held-out ρ_s (not used in fit) |
|---|---|---|---|---|---|
| 30m | 1h | M | −0.857 | **−0.867** | −0.860 |
| 30m | 10h | M | −0.704 | −0.720 | −0.680 |
| 1m | 0.5h | M | −0.663 | −0.680 | −0.661 |
| 1m | 10h | M | −0.638 | −0.656 | −0.607 |

The val estimate holds on held-out within 0.03 everywhere. The dependence does not drift the way the marginals do.

## Joint calibration — the copula against independence

Over the 5 × 5 grid of events {MAE ≤ Q_MAE(a), MFE ≤ Q_MFE(b)}, the gap is the mean |actual − predicted| in pp. The comparison is paired on identical rows and day resamples.

| src | h | M/A | indep gap | copula gap | copula − indep [95% CI] | dependence only |
|---|---|---|---|---|---|---|
| 30m | 1h | M | 5.54 | **0.93** | −4.62 [−4.75, −4.37] | 0.26 |
| 30m | 10h | M | 4.80 | 1.48 | −3.32 [−3.72, −2.91] | 0.51 |
| 1m | 0.5h | M | 3.69 | 1.31 | −2.38 [−2.87, −1.83] | 0.42 |
| 1m | 10h | M | 4.21 | 1.65 | −2.56 [−2.98, −2.05] | 0.59 |

| number | M/A |
|---|---|
| cells where the copula beats independence, interval excluding zero | M, **9 of 9** on ALL, 9 of 9 on HO1, 9 of 9 on HO2 |
| cells where it is worse | M, 0 |

"Dependence only" plugs the actual held-out marginal frequencies into the copula. It is a diagnostic, not a forecast. At 0.26–0.62pp it shows the **dependence structure is accurate**. Most of the copula's remaining gap is marginal miscalibration. That is why the copula gap rises from HO1 (0.74–1.29) to HO2 (1.14–2.29) while "dependence only" stays flat: the marginals drift, the dependence does not.

## Both large — where the Gaussian runs out

P(MAE above its q75 AND MFE above its q75), held out:

| src | h | M/A | actual | copula | independence |
|---|---|---|---|---|---|
| 30m | 1h | M | 0.45% | 0.03% | 6.25% |
| 30m | 10h | M | 1.18% | 0.45% | 6.25% |
| 1m | 0.5h | M | 1.17% | 0.64% | 6.25% |
| 1m | 10h | M | 1.46% | 0.78% | 6.25% |

At q95/q95: actual 0.00–0.06%, copula 0.00%, independence 0.25%.

**Independence overstates the both-large event 4–14×. The Gaussian copula understates it about 2× at 1m and up to 15× at 30m 1h.** That is the missing tail dependence the docstring warned about, and it is not the tie bias. Ties pull ρ toward zero, which would *raise* the copula's both-large mass, so a de-biased Gaussian would understate this corner even more. The shortfall is the Gaussian's shape. A copula with tail dependence (Student-t) is the natural next candidate. That is a separate decision and **was not built**.

**For a stop-and-target rule:** treating MAE and MFE as independent is badly wrong — it expects a path to run far both ways 6% of the time, against ~1% actual. The Gaussian copula gets the bulk of the joint law right and is conservative in the opposite direction at the corner that matters.

---

# Feature importance — which of the five carries the skill, 2026-10-11

Tag: **IMPORTANCE**. `importance.py`, log `logs/importance.log` (186s).
1-minute target, ALL, the matched 53,757-episode set and its usual split. Two
cells: MFE 10h (confirmed skill) and MAE 10h (suggestive). The held-out rows have
been scored before; this is attribution, not a new skill claim.

| check | M/A |
|---|---|
| QTREE refit, all 5 horizons, vs cache after two-pass enforcement | M, **0.000e+00** in both cells |
| Linear QR refit at 10h, share of predictions matching the cache | M, 99.9945% (MFE), 99.9978% (MAE); the rest are horizon-enforcement lifts a single-horizon refit cannot reproduce |
| skill reproduced | M, QTREE +4.56% / +2.34% (cache +4.56 / +2.30); Linear QR +4.94% / +2.66%, matching the published figures |

| train correlation | M/A | vol_48 | vratio | vol_slope | sandwich | off_mark |
|---|---|---|---|---|---|---|
| sandwich | M | +0.467 | +0.334 | −0.063 | 1 | **+0.564** |
| off_mark | M | +0.151 | +0.188 | −0.058 | +0.564 | 1 |

## The table

Coefficients are in target-sigma per train-SD of the feature. Importance is in **skill points**: 100 × (pinball rise from shuffling) / climatology pinball, 20 shuffles, day-clustered 95% interval.

**1m / MFE / 10h** — QTREE skill +4.56%

| feature | M/A | LinQR q50 | LinQR q95 − q5 | QTREE permutation importance |
|---|---|---|---|---|
| vol_48 | M | +0.378 | **+1.559** | **+5.06** [+4.41, +5.63] |
| vratio | M | +0.042 | +0.153 | +0.16 [+0.02, +0.30] |
| vol_slope | M | +0.276 | +0.909 | +1.10 [+0.72, +1.52] |
| sandwich | M | +0.134 | +0.305 | +0.88 [+0.66, +1.08] |
| off_mark | M | +0.044 | +0.018 | +0.05 [+0.02, +0.10] |
| **VOL TRIO, jointly** | M | | | **+6.18** [+5.45, +6.87] |
| **MICRO PAIR, jointly** | M | | | **+0.99** [+0.75, +1.21] |
| all five, jointly | M | | | +8.39 [+7.60, +9.21] |

**1m / MAE / 10h** — QTREE skill +2.34%

| feature | M/A | LinQR q50 | LinQR q95 − q5 | QTREE permutation importance |
|---|---|---|---|---|
| vol_48 | M | +0.445 | **+1.633** | **+3.53** [+3.03, +4.05] |
| vratio | M | +0.046 | +0.183 | +0.12 [+0.04, +0.23] |
| vol_slope | M | +0.108 | **+1.796** | +0.55 [+0.17, +0.89] |
| sandwich | M | −0.043 | +0.595 | +0.31 [+0.15, +0.49] |
| off_mark | M | +0.037 | +0.106 | +0.04 [**−0.04**, +0.11] |
| **VOL TRIO, jointly** | M | | | **+3.93** [+3.41, +4.55] |
| **MICRO PAIR, jointly** | M | | | **+0.41** [+0.23, +0.59] |
| all five, jointly | M | | | +5.02 [+4.46, +5.69] |

Cross-check, Linear QR permutation importance: trio +7.80 / pair +0.31 on MFE, and +5.11 / +0.18 on MAE. Same ordering, with the pair smaller still.

**Importances exceed the skill itself, and that is expected, not an error.** A model whose inputs are shuffled does worse than climatology, because its predictions still move — they just move on noise. Shuffling all five costs 8.39 points against a skill of 4.56. Read the importances against each other, not against the skill figure.

## What it says

- **The skill is the volatility trio: 6× the microstructure pair on MFE, 10× on MAE.** Within the trio it is overwhelmingly **vol_48**, at 5.06 of 6.18 points on MFE. vol_48 is also the largest envelope-widening coefficient in both cells, +1.56σ and +1.63σ per SD between q5 and q95. **vol_slope** is second, and on MAE it widens the upper tail as much as vol_48 does (q95 coefficient +1.70). **vratio carries almost nothing**: +0.16 and +0.12 points.
- **The microstructure pair is small but real, and it is entirely sandwich.** The pair's interval is clear of zero in both cells, at about 1 point on MFE. Sandwich is 0.88 of that; **off_mark is 0.05 on MFE, and its interval includes zero on MAE.** off_mark's coefficients are near zero at every quantile.
- **The one microstructure feature that works is itself a range measure.** Sandwich is the bound on within-bar travel from the 30m high and low. It is volatility read from inside the bar, and it correlates +0.467 with vol_48. The genuinely microstructure feature — off_mark, mark price against the traded close — carries nothing.

## The decision this was meant to inform

**Basis is a lower priority than assumed.** It is a mark/index-versus-traded-price quantity, so its nearest relative here is off_mark, which contributes nothing measurable. Its sibling sandwich does work, but by measuring range, not microstructure. The skill comes from how volatile the spread has been and is becoming. This is a reading, not a gate: no threshold for "comparable" was fixed in advance.

---

# vol_48 sharpened to 1-minute resolution — MARGINAL, not propagated, 2026-10-11

Tag: **VOL48-1M**, compared against the **QTREE / vol_48** numbers in IMPORTANCE and
MATCH1M. `vol1m.py`, log `logs/vol1m.log` (99s), feature in
`research/datasets/vol48_1m.npz`.

`vol_48_1m` is the same quantity as `vol_48`: the same frozen entry-geometry spread, the same entry sigma, the same 24 hours ending at the entry bar's close (minute entry+29), absolute changes. It differs only in resolution: 1,440 one-minute steps instead of 48 thirty-minute steps. Nothing else changed.

## Correctness

| check | M/A |
|---|---|
| max minute offset read, relative to entry_time | M, **+29** — the entry bar's own close, nothing later |
| 1m path vs the stored 30m window at the 49 marks | M, max error 4.71e-07 = **0.062** of the float32 budget |
| vol_48 recomputed from the new path's marks vs envfeat | M, max diff **8.75e-08** |
| episodes with all 1,440 valid one-minute changes | M, 53,719 of 53,757 |
| episodes below 720 valid changes / fewest valid | M, 7 / 59 — kept, nothing forward-filled |
| missing minutes per episode | M, mean 0.26, max 1,381 |

## The premise holds: the 1-minute estimate is far less noisy

| estimator | M/A | split-half r | reliability (Spearman-Brown) | noise share |
|---|---|---|---|---|
| vol_48, 48 steps | M | 0.714 | 0.833 | **16.7%** |
| vol_48_1m, 1,440 steps | M | 0.986 | 0.993 | **0.7%** |

| number | M/A |
|---|---|
| Spearman(vol_48, vol_48_1m) | M, 0.872 |
| median vol_48_1m / vol_48 | M, 0.1869, against 0.1826 for a random walk |

The ratio sits only 2% above the random-walk value, so **bid-ask bounce is a small part of the 1-minute measure**. That caveat turned out not to matter.

**On the "83% noise" figure carried in this project:** as an estimator of trailing 24-hour volatility, `vol_48` is only 16.7% noise by split-half. So the 83% cannot be estimator noise in this sense. It most likely describes how much of the feature is unrelated to *future* travel, and better resolution cannot reduce that part. The two numbers measure different things. The 83% figure is not re-derived here.

## The comparison — QTREE, paired on identical rows

| cell | measure | M/A | old (vol_48) | new (vol_48_1m) | new − old [95% CI] | |
|---|---|---|---|---|---|---|
| 1m MFE 10h | skill % | M | +4.56 | +4.25 | **−0.311** [−0.531, −0.080] | WORSE |
| 1m MFE 10h | gap pp | M | 2.45 | 3.04 | **+0.583** [+0.416, +0.707] | WORSE |
| 1m MAE 10h | skill % | M | +2.30 | +2.77 | **+0.472** [+0.195, +0.733] | BETTER |
| 1m MAE 10h | gap pp | M | 3.23 | 2.86 | **−0.372** [−0.510, −0.229] | BETTER |

The old levels match the published QTREE figures exactly: skill +4.56 and +2.30, gap 2.45 and 3.23.

## Importance — the sharper feature carries MORE of the load, in both cells

| feature | M/A | MFE old | MFE new | MAE old | MAE new |
|---|---|---|---|---|---|
| vol_48 → vol_48_1m | M | +5.06 | **+6.03** | +3.51 | **+4.94** |
| vratio | M | +0.16 | +0.43 | +0.13 | +0.20 |
| vol_slope | M | +1.10 | +1.20 | +0.56 | +0.57 |
| sandwich | M | +0.88 | **+0.63** | +0.32 | **+0.15** |
| off_mark | M | +0.05 | −0.03 | +0.03 | +0.02 |

The model leans harder on the sharper feature, and sandwich gives up weight. That fits sandwich being partly a volatility proxy, which becomes redundant once the volatility estimate is cleaner. It is a reading, not tested.

## Decision — MARGINAL, by the rule fixed before the run

Two of four paired measures are significantly better and two significantly worse. The rule required nothing to get worse, so the verdict is **MARGINAL**. Per the brief: stated plainly, **not propagated**, not chased further in this pass.

The split is clean. **The 1-minute estimate helps MAE on both skill and calibration, and hurts MFE on both.** Why the noisier 30-minute estimate serves MFE better was not investigated. One untested possibility: MFE is movement toward mu, so the 30-minute step size may carry reversion structure that a 1-minute average dilutes. A precision gain from 16.7% noise to 0.7% did not translate into uniform skill.

---

# VOL48-1M follow-up — MAE at the other four horizons: ADOPT for MAE, 2026-10-11

Tag: **VOL48-1M-MAE**, against the **VOL48-1M** entry above. `vol1m.py --stage
mae_horizons`, log `logs/vol1m_mae_horizons.log` (37s). Scoring only: the feature
was reloaded from `vol48_1m.npz` (sha256 b3cbe66a18c5, rows identical to the
population), not rebuilt.

| check | M/A |
|---|---|
| cache fingerprint (old = published QTREE) | M, matches 9e332d92a2945b03 |
| 10h re-scored as a reproduction check | M, skill **+2.77%**, gap **2.86pp** — identical to VOL48-1M |

**Rule, fixed before the run.** Per horizon: LOSS if either paired measure is significantly worse; WIN if one is significantly better and neither is worse; TIE otherwise. Adopt for MAE if WIN or TIE at three or more of the four. A 2–2 split would not adopt; that case was specified in advance because the brief's wording left it open.

| h | measure | M/A | old vol_48 | new vol_48_1m | new − old [95% CI] | horizon |
|---|---|---|---|---|---|---|
| 0.5h | skill % | M | +1.79 | +1.93 | +0.139 [−0.011, +0.288] | WIN |
| 0.5h | gap pp | M | 2.29 | 1.99 | **−0.300** [−0.381, −0.179] | |
| 1h | skill % | M | +1.50 | +1.70 | +0.196 [−0.016, +0.413] | WIN |
| 1h | gap pp | M | 2.63 | 2.23 | **−0.397** [−0.495, −0.287] | |
| 2h | skill % | M | +1.53 | +1.88 | **+0.350** [+0.148, +0.534] | WIN |
| 2h | gap pp | M | 2.95 | 2.52 | **−0.431** [−0.520, −0.353] | |
| 5h | skill % | M | +1.88 | +2.31 | **+0.437** [+0.226, +0.645] | WIN |
| 5h | gap pp | M | 3.22 | 2.84 | **−0.380** [−0.492, −0.259] | |
| 10h (ref) | skill % | M | +2.30 | +2.77 | +0.472 [+0.195, +0.733] | WIN |
| 10h (ref) | gap pp | M | 3.23 | 2.86 | −0.372 [−0.510, −0.229] | |

**Verdict: ADOPT vol_48_1m for MAE. WIN at 4 of 4 remaining horizons, no losses.**

- **Calibration improves at every horizon**, by 0.30–0.43pp, every interval clear of zero.
- **Skill improves significantly from 2h out**, and the gain grows with horizon: +0.14 at 0.5h, rising to +0.47 at 10h. At 0.5h and 1h the skill intervals only just touch zero (lower bounds −0.011 and −0.016).
- The 10h result was not a fluke. It is the end of a consistent pattern.

**The feature set is now split by direction:** vol_48_1m for MAE, vol_48 for MFE. Propagating that into the full registry is a **separate build, not done here**. Every MAE model's inputs change, so it needs its own feature matrix and a new cache; the current fingerprint covers the old features, and the loader would correctly refuse to reuse it.

---

# MAE registry rebuilt on vol_48_1m — the win generalises to every model, 2026-10-11

Tag: **VOL48-1M-REGISTRY**, against **VOL48-1M-MAE**. `vol1m.py --stage
mae_registry`, log `logs/vol1m_mae_registry.log` (338s). 1-minute target, ALL, the
matched 53,757-episode set, the usual split.

**This section is the MAE side only.** The new MAE predictions live in their own cache, `envelope_preds_match1m_mae_vol1m.npz`, fingerprint over the vol_48_1m features and 1m MAE targets: 25 cells, all five models × five horizons. **The MFE side is unchanged.** Every MFE prediction is still the published one in `envelope_preds_match1m.npz`, on vol_48. That cache was read, never written.

| check | M/A |
|---|---|
| Climatology, new vs old (uses no features) | M, **0.000e+00**; same denominator for old and new skill |
| CQR, new vs old, max \|diff\| per horizon | M, 7.48 / 9.80 / 9.80 / 7.35 / 8.96: **refitted on the new QTREE, not reused** |
| QTREE 10h vs VOL48-1M-MAE | M, +2.77% / 2.86pp: reproduced |
| horizon enforcement moved | M, QTREE 0.754%, CQR 0.961%, Linear QR 0.002% |

**Verdict rule, fixed before the run.** A measure is *confirmed* if its interval clears zero in the new feature's favour, *directional* if the point estimate favours it but the interval touches zero.

- REVERSES: any measure significantly worse at any horizon.
- HOLDS: no reversal, and the gap is confirmed at three or more of five horizons.
- WEAKER: gap confirmed at one or two, or only skill confirmed.
- ABSENT: nothing confirmed.

| model | M/A | verdict | gap confirmed | skill confirmed | skill directional | worse |
|---|---|---|---|---|---|---|
| Linear QR | M | **HOLDS** | 5 / 5 | **5 / 5** | 0 | 0 |
| kNN | M | **HOLDS** | 5 / 5 | 4 / 5 | 1 (0.5h) | 0 |
| QTREE | M | **HOLDS** | 5 / 5 | 3 / 5 | 2 (0.5h, 1h) | 0 |
| CQR | M | **HOLDS** | 5 / 5 | 3 / 5 | 2 (0.5h, 1h) | 0 |
| Climatology | M | n/a: uses no features | — | — | — | — |

## Per model — new − old, paired, day-clustered 95% interval

| model | h | M/A | skill old → new | skill Δ [CI] | gap old → new | gap Δ [CI] |
|---|---|---|---|---|---|---|
| Linear QR | 0.5h | M | +2.18 → +2.39 | **+0.21** [+0.06, +0.34] | 2.43 → 2.16 | **−0.27** [−0.40, −0.08] |
| Linear QR | 1h | M | +1.90 → +2.25 | **+0.35** [+0.15, +0.53] | 2.89 → 2.45 | **−0.44** [−0.58, −0.29] |
| Linear QR | 2h | M | +1.86 → +2.32 | **+0.45** [+0.26, +0.64] | 3.14 → 2.76 | **−0.38** [−0.50, −0.27] |
| Linear QR | 5h | M | +2.24 → +2.74 | **+0.50** [+0.27, +0.71] | 3.47 → 3.04 | **−0.42** [−0.58, −0.26] |
| Linear QR | 10h | M | +2.66 → **+3.21** | **+0.55** [+0.18, +0.89] | 3.59 → 3.03 | **−0.57** [−0.74, −0.38] |
| kNN | 0.5h | M | +1.54 → +1.67 | +0.13 [−0.06, +0.31] dir | 2.38 → 2.21 | **−0.17** [−0.25, −0.01] |
| kNN | 1h | M | +1.12 → +1.48 | **+0.36** [+0.10, +0.59] | 2.78 → 2.42 | **−0.36** [−0.51, −0.22] |
| kNN | 2h | M | +1.21 → +1.65 | **+0.44** [+0.19, +0.72] | 3.15 → 2.86 | **−0.29** [−0.44, −0.14] |
| kNN | 5h | M | +1.66 → +2.04 | **+0.38** [+0.12, +0.61] | 3.47 → 3.08 | **−0.39** [−0.51, −0.25] |
| kNN | 10h | M | +2.07 → +2.48 | **+0.41** [+0.14, +0.68] | 3.57 → 3.20 | **−0.36** [−0.48, −0.22] |
| QTREE | 0.5h | M | +1.79 → +1.93 | +0.14 [−0.01, +0.29] dir | 2.29 → 1.99 | **−0.30** [−0.38, −0.18] |
| QTREE | 1h | M | +1.50 → +1.70 | +0.20 [−0.02, +0.41] dir | 2.63 → 2.23 | **−0.40** [−0.50, −0.29] |
| QTREE | 2h | M | +1.53 → +1.88 | **+0.35** [+0.15, +0.53] | 2.95 → 2.52 | **−0.43** [−0.52, −0.35] |
| QTREE | 5h | M | +1.88 → +2.31 | **+0.44** [+0.23, +0.65] | 3.22 → 2.84 | **−0.38** [−0.49, −0.26] |
| QTREE | 10h | M | +2.30 → +2.77 | **+0.47** [+0.20, +0.73] | 3.23 → 2.86 | **−0.37** [−0.51, −0.23] |
| CQR | 0.5h | M | +1.85 → +1.96 | +0.11 [−0.05, +0.26] dir | 2.25 → 1.99 | **−0.26** [−0.36, −0.01] |
| CQR | 1h | M | +1.62 → +1.78 | +0.17 [−0.05, +0.39] dir | 2.34 → 2.02 | **−0.32** [−0.43, −0.20] |
| CQR | 2h | M | +1.68 → +1.98 | **+0.30** [+0.10, +0.48] | 2.74 → 2.41 | **−0.33** [−0.44, −0.24] |
| CQR | 5h | M | +2.07 → +2.46 | **+0.38** [+0.18, +0.59] | 2.81 → 2.55 | **−0.26** [−0.39, −0.11] |
| CQR | 10h | M | +2.51 → +2.92 | **+0.41** [+0.15, +0.66] | 2.64 → 2.38 | **−0.26** [−0.38, −0.05] |

## What is confirmed, and what is only directional

- **Calibration: confirmed for every model at every horizon (20 of 20).** Improvements range from 0.17 to 0.57pp. Two lower bounds sit close to zero: kNN 0.5h (−0.01) and CQR 0.5h (−0.005).
- **Skill: confirmed in 15 of 20, directional in the other 5, worse in none.** All five directional cells are at 0.5h, or at 1h for QTREE and CQR. Linear QR alone is confirmed at all five horizons.
- **The gain grows with horizon in every model**, as it did for QTREE.
- **Linear QR benefits most.** At 10h, MAE skill goes from +2.66% to +3.21%, now the highest MAE skill of any model, and the gap closes by 0.57pp. A sharper volatility estimate matters most to the model that uses it linearly.
- Level, confirmatory only: CQR's mean MAE gap is now 2.27pp, below Climatology's 2.36pp. **A conditional model now beats Climatology on MAE calibration**, which no model did on vol_48.

The registry is now split by direction: **MAE on vol_48_1m (the new cache), MFE on vol_48 (the match1m cache).**

---

# Plain accuracy — average miss of the median guess, 10h, 2026-10-11

Tag: **PLAIN-MISS**. A communication aid, not a new finding: the mean absolute error of each model's q50 prediction is exactly **twice** its q50 pinball loss, checked per model to 1e-12. Cached predictions only: MAE from the vol_48_1m cache (fingerprint 5bd8d15af8c8), MFE from the vol_48 cache (9e332d92a294). 1-minute target, ALL, 18,064 held-out rows. Computed inline; no script kept.

| direction | model | M/A | average miss, σ | vs climatology |
|---|---|---|---|---|
| MAE | Climatology | M | 1.949 | — |
| MAE | **CQR** | M | **1.903** | −2.3% |
| MAE | Linear QR | M | 1.908 | −2.1% |
| MAE | QTREE | M | 1.913 | −1.9% |
| MAE | kNN | M | 1.919 | −1.5% |
| MFE | Climatology | M | 1.638 | — |
| MFE | **Linear QR** | M | **1.580** | −3.5% |
| MFE | CQR | M | 1.581 | −3.5% |
| MFE | QTREE | M | 1.587 | −3.1% |
| MFE | kNN | M | 1.591 | −2.9% |

| number | M/A |
|---|---|
| MAE: CQR − Linear QR | M, 0.0047σ [−0.0031, +0.0125]: **not distinguishable** |
| MFE: Linear QR − CQR | M, 0.0003σ [−0.0044, +0.0056]: **not distinguishable** |
| MAE: best model vs climatology | M, 0.046σ better [+0.033, +0.058] |
| MFE: best model vs climatology | M, 0.058σ better [+0.044, +0.070] |
| typical 10h move | M, MAE mean 2.56σ (median 1.58); MFE mean 2.64σ (median 2.04) |

---

# vol_slope sharpened to 1-minute resolution — MARGINAL, stopped, 2026-10-11

Tag: **VOL-SLOPE-1M**, against **IMPORTANCE**, where vol_slope carried +1.10 skill points on MFE 10h and +0.55 on MAE 10h. `vol1m.py --stage slope_cells`, log `logs/vol1m_slope_cells.log` (65s). Feature saved to `research/datasets/vol_slope_1m.npz`.

`vol_slope_1m` uses the same statistic as `vol_slope`: the population sd of step changes over the last 8 hours divided by the same over the 16 hours before, with the denominator clipped at 1e-12. It covers the same two calendar windows. The only change is resolution: 480 and 960 one-minute steps instead of 16 and 32 thirty-minute steps.

**The baseline is the current registry, per direction.** MAE runs on vol_48_1m, cache `match1m_mae_vol1m`, fingerprint 5bd8d15af8c8. MFE runs on vol_48, cache `match1m`, fingerprint 9e332d92a294. Both matched.

## Correctness

| check | M/A |
|---|---|
| max minute offset read | M, +29: the entry bar's own close |
| 1m path vs stored 30m window at 49 marks | M, 4.71e-07 = 0.062 of the float32 budget |
| OLD vol_slope recomputed from the new path's marks | M, max diff **2.34e-06** |
| regression: shared path code vs saved vol_48_1m | M, **0.000e+00**: the refactor changed nothing |
| episodes with both windows complete | M, 53,719 of 53,757; 14 below half in either |
| episodes that cannot form the ratio | M, **6, all in TRAIN**, all on 2025-06-26/27 |

**The six.** Their 16-hour window falls before the 1-minute data begins: the backfill wall. For exactly these, vol_slope_1m is set to the 30-minute vol_slope. That uses the same quantity at the old resolution; it is not a forward-filled price. Each is flagged per row (`fallback_30m`). This touches 6 of 22,645 training rows and no scored row. The guard aborts if a substitution ever reaches val or held out.

## The premise holds, strongly

| estimator | M/A | split-half r | reliability | noise share |
|---|---|---|---|---|
| vol_slope, 16/32 steps | M | 0.250 | 0.400 | **60.0%** |
| vol_slope_1m, 480/960 steps | M | 0.825 | 0.904 | **9.6%** |

Correlations are computed on log-ratios, because a ratio of sds is right-skewed.

| number | M/A |
|---|---|
| Spearman(vol_slope, vol_slope_1m) | M, **0.718** (vol_48 vs vol_48_1m was 0.872) |
| median, old vs new | M, 1.327 vs 1.174 |

vol_slope was the noisiest feature in the set: a ratio of two sds from 16 and 32 points. The 1-minute version cuts its noise sixfold.

## The test — QTREE, 10h, paired on identical rows

| cell | measure | M/A | old vol_slope | new vol_slope_1m | new − old [95% CI] | cell |
|---|---|---|---|---|---|---|
| MFE 10h | skill % | M | +4.56 | +4.44 | −0.121 [−0.495, +0.177] | HOLDS |
| MFE 10h | gap pp | M | 2.45 | 2.50 | +0.041 [−0.118, +0.164] | |
| MAE 10h | skill % | M | +2.77 | +2.59 | −0.182 [−0.485, +0.108] | HOLDS |
| MAE 10h | gap pp | M | 2.86 | 2.97 | +0.113 [−0.002, +0.244] | |

**Verdict, by the rule fixed before the run: MARGINAL.** Neither cell improves. Every point estimate leans slightly the wrong way: both skills down, both gaps up. The MAE gap's interval is the closest to a loss, reaching −0.002 on the low side. Stopped as the rule requires; not propagated, not chased across horizons.

**Reading, not tested:** a sixfold noise reduction in a feature worth about 1 skill point produced nothing. One likely reason is the lower agreement between the two versions (Spearman 0.72, against 0.87 for vol_48). At 1-minute resolution, the 8h/16h sd ratio is dominated by short-horizon activity, so it measures something materially different from the 30-minute ratio rather than a sharper copy of it. Unlike vol_48, resolution here changes what is measured, not only how precisely.

---

# Hour-of-day and hedge quality — two new features, both MARGINAL, 2026-10-11

`newfeat.py`, log `logs/newfeat.log` (145s). Features saved to `research/datasets/newfeat.npz`. The two candidates were tested **separately**, each added on top of the current registry baseline per direction: MAE on vol_48_1m (cache `match1m_mae_vol1m`, fingerprint 5bd8d15af8c8), MFE on vol_48 (cache `match1m`, fingerprint 9e332d92a294). Both fingerprints matched. QTREE only, 1-minute target, ALL, the 53,757-episode set, the usual split, 10h.

**Rule, fixed before the run.** Per cell: IMPROVES if skill or gap is significantly better and neither is significantly worse; LOSES if either is significantly worse; HOLDS otherwise. PROPAGATE if neither cell loses and at least one improves. SPLIT if one improves and the other loses. MARGINAL if no cell improves. **Gap filled:** the brief's "both improve or hold → propagate" and "neither improves → marginal" overlap when both cells only hold. That case was set as MARGINAL in advance.

## Build checks (both candidates)

| check | M/A |
|---|---|
| entry minutes present | M, :00 and :30 only; 48 distinct fractional hours |
| max \|sin²+cos²−1\| | M, 2.2e-16 |
| episodes per UTC hour | M, min 1,611, max 3,421 |
| timestamps are UTC | M, data_loader parses with utc=True, then drops the zone |
| r2 / \|beta\| NaN or non-finite in the population | M, **0 / 0** |
| r2 range, median | M, 0.0000 to 0.9973, median 0.274 |
| \|beta\| range, median | M, 0.023 to 106.6, median 1.256 |
| Spearman(r2, \|beta\|) | M, −0.107 |
| 300 random episodes: beta, alpha, mu, sigma, r2 recomputed from the panel at the entry bar | M, max relative diff **0** for all five: r2 is the same frozen 96-bar entry geometry |
| baseline QTREE levels | M, +4.56 / 2.45 (MFE), +2.77 / 2.86 (MAE): match the registry |

Hour is the fractional hour of `entry_time`, the entry bar's open label: hour + minute/60. An integer hour would fold each :30 onto the :00 before it. The timestamp is known before the bar closes, so there is no look-ahead.

# HOUR-OF-DAY

Tag: **HOUR-OF-DAY**, against the current registry baseline.

| cell | measure | M/A | baseline | + hour | new − old [95% CI] | cell |
|---|---|---|---|---|---|---|
| MFE 10h | skill % | M | +4.56 | +4.34 | **−0.218** [−0.383, −0.046] | LOSES |
| MFE 10h | gap pp | M | 2.45 | 2.48 | +0.029 [−0.065, +0.105] | |
| MAE 10h | skill % | M | +2.77 | +2.67 | −0.104 [−0.338, +0.144] | HOLDS |
| MAE 10h | gap pp | M | 2.86 | 2.83 | −0.029 [−0.145, +0.074] | |

**Verdict: MARGINAL.** No cell improves. MFE skill is significantly worse. Stopped; not propagated. Importance was not run, because the brief asks for it only on a pass.

## Wider screen — 1h, 5h, 10h: MARGINAL, confirmed

`newfeat.py --stage horizons`, log `logs/newfeat_horizons.log` (106s). Reused `newfeat.npz`; the stored columns equal a fresh read of meta exactly. One QTREE fit per direction, scored at three horizons. **10h is a reproduction:** it gives the deltas above to the third decimal. 1h and 5h are the new paired measurements. Screen size: 12 cells (2 candidates × 2 directions × 3 horizons), stated before the run.

**Rule, fixed before the run,** per direction: RULED OUT if any horizon LOSES. CLEARS if none loses and 2 or more of 3 IMPROVE. NOT CLEAR otherwise. A candidate is MARGINAL (confirmed) if neither direction clears.

| cell | measure | M/A | baseline | + hour | new − old [95% CI] | horizon |
|---|---|---|---|---|---|---|
| MFE 1h | skill % | M | +4.88 | +5.00 | +0.119 [−0.201, +0.415] | HOLDS |
| MFE 1h | gap pp | M | 1.10 | 1.13 | +0.023 [−0.128, +0.115] | |
| MFE 5h | skill % | M | +4.50 | +4.53 | +0.031 [−0.127, +0.190] | HOLDS |
| MFE 5h | gap pp | M | 2.37 | 2.39 | +0.018 [−0.063, +0.103] | |
| MFE 10h | both | M | — | — | reproduces −0.218 / +0.029 | LOSES |
| MAE 1h | skill % | M | +1.70 | +1.50 | −0.197 [−0.595, +0.141] | HOLDS |
| MAE 1h | gap pp | M | 2.23 | 2.29 | +0.053 [−0.032, +0.148] | |
| MAE 5h | skill % | M | +2.31 | +2.37 | +0.056 [−0.241, +0.332] | IMPROVES |
| MAE 5h | gap pp | M | 2.84 | 2.69 | **−0.153** [−0.259, −0.052] | |
| MAE 10h | both | M | — | — | reproduces −0.104 / −0.029 | HOLDS |

**Verdict: MFE RULED OUT** (loses at 10h). **MAE NOT CLEAR** (improves at 5h only, by calibration alone). **Hour-of-day is MARGINAL, confirmed.**

# HEDGE-QUALITY

Tag: **HEDGE-QUALITY**, against the current registry baseline.

| cell | measure | M/A | baseline | + r2, \|beta\| | new − old [95% CI] | cell |
|---|---|---|---|---|---|---|
| MFE 10h | skill % | M | +4.56 | +4.59 | +0.034 [−0.076, +0.131] | HOLDS |
| MFE 10h | gap pp | M | 2.45 | 2.48 | +0.021 [−0.036, +0.065] | |
| MAE 10h | skill % | M | +2.77 | +2.61 | **−0.163** [−0.299, −0.013] | LOSES |
| MAE 10h | gap pp | M | 2.86 | 3.05 | **+0.196** [+0.096, +0.299] | |

**Verdict: MARGINAL.** No cell improves. MAE is significantly worse on both skill and calibration. Stopped; not propagated. Importance not run.

## Wider screen — 1h, 5h, 10h: MARGINAL, confirmed

Same run, rule and screen as the hour-of-day wider screen above.

| cell | measure | M/A | baseline | + r2, \|beta\| | new − old [95% CI] | horizon |
|---|---|---|---|---|---|---|
| MFE 1h | skill % | M | +4.88 | +4.86 | −0.025 [−0.079, +0.026] | HOLDS |
| MFE 1h | gap pp | M | 1.10 | 1.09 | −0.017 [−0.068, +0.029] | |
| MFE 5h | skill % | M | +4.50 | +4.55 | +0.052 [−0.011, +0.120] | IMPROVES |
| MFE 5h | gap pp | M | 2.37 | 2.32 | **−0.053** [−0.099, −0.007] | |
| MFE 10h | both | M | — | — | reproduces +0.034 / +0.021 | HOLDS |
| MAE 1h | skill % | M | +1.70 | +1.79 | +0.095 [−0.008, +0.184] | LOSES |
| MAE 1h | gap pp | M | 2.23 | 2.36 | **+0.127** [+0.041, +0.197] | |
| MAE 5h | skill % | M | +2.31 | +2.28 | −0.033 [−0.155, +0.103] | LOSES |
| MAE 5h | gap pp | M | 2.84 | 2.95 | **+0.109** [+0.020, +0.196] | |
| MAE 10h | both | M | — | — | reproduces −0.163 / +0.196 | LOSES |

**Verdict: MFE NOT CLEAR** (improves at 5h only, by calibration, by 0.05pp). **MAE RULED OUT** (loses at all three horizons, always on calibration). **Hedge quality is MARGINAL, confirmed.**

**Across the 12 cells:** 2 improve, 4 lose, 6 hold. Both improvements are lone 5h calibration gains, one per candidate, with nothing either side of them. Against 12 cells that is no better than noise. The one consistent pattern is harm: hedge quality makes MAE calibration worse at every horizon tested.

**Reading, not tested:** hedge quality was earlier found to separate spreads that revert from spreads that don't (a direction question). Here it adds nothing to *how far* the spread travels, and it costs MAE calibration. The two findings don't conflict: one is about direction, the other about distance.

---

# COMBINED — all four new columns together. EXPLORATORY, 2026-10-11

Tag: **COMBINED**. **Exploratory: no adoption verdict is issued, whatever the result.** r2/|beta| are confirmed harmful to MAE calibration (HEDGE-QUALITY), and the hour pair is confirmed harmful to MFE skill at 10h (HOUR-OF-DAY). A positive cell here earns more scrutiny, not less.

`newfeat.py --stage combined`, log `logs/newfeat_combined.log` (145s). Reused `newfeat.npz`; the stored columns equal a fresh read of meta exactly. Nine columns: the baseline five per direction (vol_48_1m for MAE, vol_48 for MFE) + hour_sin, hour_cos, r2, |beta|. QTREE only. One fit per direction, scored at 1h, 5h, 10h, paired against the cached baseline QTREE (fingerprints 9e332d92a294 / 5bd8d15af8c8, both matched). 6 cells × 2 measures.

**How "different" was judged, fixed before the run.** Each cell's predicted outcome comes from the two individual tests: LOSES if either lost there, IMPROVES if either improved and neither lost, HOLDS otherwise. The combined outcome either matches (AS PREDICTED) or does not (DIFFERENT). Stated in advance: the prediction is generous, because it counts the two lone 5h gains, already judged noise, as predicted IMPROVES.

| cell | measure | M/A | baseline | + four | new − old [95% CI] | outcome | hour alone | hedge alone | vs prediction |
|---|---|---|---|---|---|---|---|---|---|
| MFE 1h | skill % | M | +4.88 | +5.10 | +0.219 [−0.066, +0.502] | HOLDS | +0.119 | −0.025 | as predicted |
| MFE 1h | gap pp | M | 1.10 | 1.04 | −0.062 [−0.167, +0.049] | | +0.023 | −0.017 | |
| MFE 5h | skill % | M | +4.50 | +4.54 | +0.033 [−0.130, +0.189] | HOLDS | +0.031 | +0.052 | DIFFERENT (worse) |
| MFE 5h | gap pp | M | 2.37 | 2.43 | +0.062 [−0.035, +0.153] | | +0.018 | −0.053 | |
| MFE 10h | skill % | M | +4.56 | +4.37 | **−0.191** [−0.379, −0.014] | LOSES | −0.218 | +0.034 | as predicted |
| MFE 10h | gap pp | M | 2.45 | 2.51 | +0.059 [−0.037, +0.127] | | +0.029 | +0.021 | |
| MAE 1h | skill % | M | +1.70 | +1.45 | −0.247 [−0.709, +0.155] | HOLDS | −0.197 | +0.095 | DIFFERENT (better) |
| MAE 1h | gap pp | M | 2.23 | 2.24 | +0.006 [−0.067, +0.168] | | +0.053 | +0.127 | |
| MAE 5h | skill % | M | +2.31 | +2.31 | −0.002 [−0.321, +0.302] | IMPROVES | +0.056 | −0.033 | DIFFERENT (better) |
| MAE 5h | gap pp | M | 2.84 | 2.67 | **−0.164** [−0.273, −0.034] | | −0.153 | +0.109 | |
| MAE 10h | skill % | M | +2.77 | +2.66 | −0.109 [−0.357, +0.108] | LOSES | −0.104 | −0.163 | as predicted |
| MAE 10h | gap pp | M | 2.86 | 2.97 | **+0.115** [+0.026, +0.228] | | −0.029 | +0.196 | |

The "hour alone" and "hedge alone" columns are the published HOUR-OF-DAY / HEDGE-QUALITY wider-screen deltas, carried in for comparison (M, from that run).

## Permutation importance — all nine, skill points vs climatology, held out

20 shuffles, day-clustered 95% interval, per-horizon refit before horizon enforcement. IMPORTANCE's units. The vol_48 row is vol_48 for MFE and vol_48_1m for MAE.

| feature | M/A | MFE 1h | MFE 5h | MFE 10h | MAE 1h | MAE 5h | MAE 10h |
|---|---|---|---|---|---|---|---|
| refit skill | M | +5.11% | +4.54% | +4.37% | +1.49% | +2.41% | +2.70% |
| vol_48 / vol_48_1m | M | +3.55 | +4.68 | +4.65 | +1.81 | +3.50 | +4.13 |
| vratio | M | +0.54 | +0.19 | +0.19 | +0.44 | +0.11 | +0.16 |
| vol_slope | M | +4.00 | +2.02 | +1.09 | +1.50 | +0.83 | +0.54 |
| sandwich | M | +0.64 | +0.70 | +0.97 | +0.08 | +0.10 | +0.11 |
| off_mark | M | +0.04 | +0.06 | +0.02 | +0.07 | +0.02 | +0.04 |
| hour_sin | M | +0.11 | +0.03 | +0.02 | +0.97 | +0.45 | +0.41 |
| hour_cos | M | +0.14 | +0.06 | −0.10 | +0.98 | +0.76 | +0.54 |
| r2 | M | +0.02 | +0.02 | +0.00 | −0.01 | +0.05 | +0.05 |
| abs_beta | M | −0.00 | +0.02 | +0.06 | +0.02 | +0.05 | +0.14 |
| **hour pair (joint)** | M | +0.29 [+0.01, +0.58] | +0.16 [−0.02, +0.33] | −0.11 [−0.26, +0.05] | +0.06 [−0.34, +0.40] | +0.21 [−0.07, +0.45] | +0.12 [−0.09, +0.32] |
| **hedge pair (joint)** | M | +0.01 [−0.03, +0.06] | +0.03 [−0.03, +0.09] | +0.07 [−0.02, +0.16] | +0.02 [−0.05, +0.08] | +0.10 [+0.03, +0.18] | +0.18 [+0.09, +0.27] |
| **all four new** | M | +0.31 [+0.03, +0.59] | +0.17 [−0.00, +0.32] | −0.04 [−0.21, +0.12] | +0.12 [−0.24, +0.44] | +0.31 [+0.05, +0.60] | +0.33 [+0.11, +0.55] |
| old five | M | +9.42 | +8.60 | +8.37 | +3.96 | +4.55 | +4.71 |

Single-feature intervals are in the log.

**Read the hour pair from the joint row, not the single rows.** Shuffling hour_sin alone, or hour_cos alone, moves a row off the unit circle to a (sin, cos) combination that never occurs. On MAE that inflates each single column to 0.4–1.0 points, while the pair shuffled together is worth 0.06–0.21 and never clears zero. The single-column numbers measure the tree's reaction to impossible inputs, not reliance on the hour.

## What it says

- **The combination does nothing positive that an individual test did not already show.** The one improving cell, MAE 5h calibration (−0.164), is the same size as hour alone at that cell (−0.153). That gain was already judged a lone, noise-level result.
- **MFE behaves like hour alone.** The 10h skill loss is there (−0.191 vs −0.218). The MFE 5h "DIFFERENT" is the pre-declared artifact: hedge's lone 5h gain did not survive. It means nothing.
- **The one real difference is on MAE: the hedge pair's calibration harm softens.** Alone, r2/|beta| made MAE calibration worse at all three horizons (+0.127, +0.109, +0.196). Combined, it is flat at 1h (+0.006) and 5h (−0.164), and smaller at 10h (+0.115, still a significant loss). This is a difference in the *harm*, not a new gain. Whether it is a real interaction or noise was not tested: that needs a paired combined-vs-individual comparison, which this run did not make.
- **Importance confirms the new columns carry little.** Together the four new columns are worth at most 0.33 skill points against 4–9 for the old five. Where the model does use them (MAE 5h/10h), the paired test shows no net gain, and at 10h a calibration loss. On MAE 10h, vol_48_1m drops from 4.94 (VOL48-1M) to 4.13 here: weight moved onto the new columns without improving the forecast.

No adoption verdict, as briefed. Nothing in the registry was written.

## COMBINED, full registry — four models × five horizons × two directions. EXPLORATORY

Tag: **COMBINED** (continued). **Exploratory: no adoption verdict, whatever the result.** `newfeat.py --stage combined_registry`, log `logs/newfeat_combined_registry.log` (7,687s; 6,800s of it kNN permutation importance). The same nine columns and `newfeat.npz`. Linear QR, QTREE, kNN and CQR are each refitted at all five horizons, two-pass enforced per model, and compared paired against that model's own cached baseline. Climatology is the fixed denominator. **40 cells, stated before the run.**

**Rule, fixed before the run.**
- Per cell: IMPROVES / HOLDS / LOSES, as before.
- The individual tests were QTREE only, at 1h/5h/10h. Those six cells must reproduce the 3-horizon COMBINED run, so they can't be new.
- No cell-level prediction exists for the other 34 cells. The individual tests' finding is "no gain", so HOLDS or LOSES counts as *consistent* and IMPROVES counts as **NEW**: flagged for extra scrutiny, not adopted.
- A model "shows movement" if any of its 10 cells is IMPROVES or LOSES. Importance is run at each moved cell.
- 80 paired tests: by chance alone, about 2 would fire on each side.

| check | M/A |
|---|---|
| QTREE reproduces the 3-horizon COMBINED deltas, all six cells | M, exact to the printed precision |
| kNN and CQR rebuilt from their parts, vs the registry functions, all 10 direction-horizons | M, max diff **0** |
| Linear QR LP fallbacks (alpha > 0) | M, 0 |
| baseline fingerprints | M, 9e332d92a294 (MFE) / 5bd8d15af8c8 (MAE), both match |

### Paired, per model, against its own 5-feature baseline

Bold = the interval clears zero. Skill: + helps. Gap: − is better calibrated.

| model | cell | M/A | skill base → +four | skill Δ [95% CI] | gap base → +four | gap Δ [95% CI] | outcome | vs prediction |
|---|---|---|---|---|---|---|---|---|
| Linear QR | MFE 0.5h | M | +4.39 → +4.39 | -0.004 [-0.106,+0.105] | 0.75 → 0.75 | -0.002 [-0.081,+0.057] | HOLDS | consistent |
| Linear QR | MFE 1h | M | +4.69 → +4.64 | -0.047 [-0.147,+0.044] | 1.06 → 1.02 | -0.034 [-0.128,+0.044] | HOLDS | consistent |
| Linear QR | MFE 2h | M | +5.23 → +5.16 | -0.068 [-0.199,+0.055] | 1.42 → 1.50 | +0.081 [-0.050,+0.160] | HOLDS | consistent |
| Linear QR | MFE 5h | M | +4.88 → +4.79 | -0.095 [-0.243,+0.057] | 2.34 → 2.28 | -0.062 [-0.141,+0.036] | HOLDS | consistent |
| Linear QR | MFE 10h | M | +4.94 → +4.82 | -0.115 [-0.318,+0.093] | 2.41 → 2.33 | -0.087 [-0.161,+0.086] | HOLDS | consistent |
| Linear QR | MAE 0.5h | M | +2.39 → +2.40 | +0.006 [-0.069,+0.088] | 2.16 → 2.19 | +0.032 [-0.029,+0.085] | HOLDS | consistent |
| Linear QR | MAE 1h | M | +2.25 → +2.22 | -0.037 [-0.107,+0.027] | 2.45 → 2.49 | +0.041 [-0.028,+0.099] | HOLDS | consistent |
| Linear QR | MAE 2h | M | +2.32 → +2.27 | -0.045 [-0.106,+0.026] | 2.76 → 2.74 | -0.020 [-0.089,+0.048] | HOLDS | consistent |
| Linear QR | MAE 5h | M | +2.74 → +2.67 | -0.077 [-0.219,+0.070] | 3.04 → 3.10 | +0.056 [-0.027,+0.132] | HOLDS | consistent |
| Linear QR | MAE 10h | M | +3.21 → +3.24 | +0.029 [-0.125,+0.209] | 3.03 → 3.17 | **+0.140** [+0.053,+0.228] | LOSES | consistent |
| QTREE | MFE 0.5h | M | +4.55 → +4.74 | **+0.185** [+0.013,+0.374] | 0.62 → 0.58 | -0.038 [-0.168,+0.105] | IMPROVES | NEW |
| QTREE | MFE 1h | M | +4.88 → +5.10 | +0.219 [-0.066,+0.502] | 1.10 → 1.04 | -0.062 [-0.167,+0.049] | HOLDS | as predicted |
| QTREE | MFE 2h | M | +4.87 → +4.94 | +0.071 [-0.210,+0.332] | 1.48 → 1.48 | +0.008 [-0.141,+0.145] | HOLDS | consistent |
| QTREE | MFE 5h | M | +4.50 → +4.54 | +0.033 [-0.130,+0.189] | 2.37 → 2.43 | +0.062 [-0.035,+0.153] | HOLDS | DIFFERENT (worse than IMPROVES), reproduced |
| QTREE | MFE 10h | M | +4.56 → +4.37 | **-0.191** [-0.379,-0.014] | 2.45 → 2.51 | +0.059 [-0.037,+0.127] | LOSES | as predicted |
| QTREE | MAE 0.5h | M | +1.93 → +1.90 | -0.023 [-0.364,+0.307] | 1.99 → 1.92 | -0.064 [-0.120,+0.069] | HOLDS | consistent |
| QTREE | MAE 1h | M | +1.70 → +1.45 | -0.247 [-0.709,+0.155] | 2.23 → 2.24 | +0.006 [-0.067,+0.168] | HOLDS | DIFFERENT (better than LOSES), reproduced |
| QTREE | MAE 2h | M | +1.88 → +1.66 | -0.221 [-0.676,+0.130] | 2.52 → 2.41 | -0.105 [-0.190,+0.087] | HOLDS | consistent |
| QTREE | MAE 5h | M | +2.31 → +2.31 | -0.002 [-0.321,+0.302] | 2.84 → 2.67 | **-0.164** [-0.273,-0.034] | IMPROVES | DIFFERENT (better than LOSES), reproduced |
| QTREE | MAE 10h | M | +2.77 → +2.66 | -0.109 [-0.357,+0.108] | 2.86 → 2.97 | **+0.115** [+0.026,+0.228] | LOSES | as predicted |
| kNN | MFE 0.5h | M | +4.39 → +3.85 | **-0.535** [-0.904,-0.130] | 0.69 → 0.88 | +0.190 [-0.091,+0.400] | LOSES | consistent |
| kNN | MFE 1h | M | +4.60 → +3.93 | **-0.671** [-1.065,-0.284] | 0.97 → 1.22 | **+0.249** [+0.053,+0.489] | LOSES | consistent |
| kNN | MFE 2h | M | +4.68 → +4.13 | **-0.546** [-1.009,-0.093] | 1.47 → 1.75 | **+0.286** [+0.117,+0.451] | LOSES | consistent |
| kNN | MFE 5h | M | +4.28 → +3.95 | -0.330 [-0.680,+0.035] | 2.40 → 2.61 | **+0.208** [+0.074,+0.366] | LOSES | consistent |
| kNN | MFE 10h | M | +4.23 → +3.79 | **-0.438** [-0.778,-0.100] | 2.48 → 2.61 | +0.126 [-0.019,+0.270] | LOSES | consistent |
| kNN | MAE 0.5h | M | +1.67 → +1.25 | **-0.419** [-0.750,-0.084] | 2.21 → 2.00 | **-0.209** [-0.377,-0.037] | LOSES | consistent |
| kNN | MAE 1h | M | +1.48 → +0.98 | **-0.498** [-0.785,-0.234] | 2.42 → 2.25 | -0.171 [-0.338,+0.048] | LOSES | consistent |
| kNN | MAE 2h | M | +1.65 → +1.33 | -0.319 [-0.664,+0.018] | 2.86 → 2.63 | **-0.226** [-0.413,-0.029] | IMPROVES | NEW |
| kNN | MAE 5h | M | +2.04 → +1.88 | -0.161 [-0.569,+0.300] | 3.08 → 2.92 | -0.164 [-0.394,+0.042] | HOLDS | consistent |
| kNN | MAE 10h | M | +2.48 → +2.32 | -0.163 [-0.701,+0.326] | 3.20 → 2.99 | **-0.208** [-0.426,-0.010] | IMPROVES | NEW |
| CQR | MFE 0.5h | M | +4.55 → +4.73 | **+0.181** [+0.017,+0.367] | 0.68 → 0.63 | -0.042 [-0.111,+0.106] | IMPROVES | NEW |
| CQR | MFE 1h | M | +4.92 → +5.12 | +0.205 [-0.078,+0.498] | 0.80 → 0.91 | +0.109 [-0.211,+0.199] | HOLDS | consistent |
| CQR | MFE 2h | M | +4.92 → +4.98 | +0.062 [-0.224,+0.324] | 1.18 → 1.25 | +0.069 [-0.092,+0.172] | HOLDS | consistent |
| CQR | MFE 5h | M | +4.62 → +4.65 | +0.033 [-0.128,+0.186] | 1.89 → 1.95 | +0.062 [-0.047,+0.129] | HOLDS | consistent |
| CQR | MFE 10h | M | +4.70 → +4.49 | **-0.205** [-0.390,-0.027] | 1.86 → 2.01 | **+0.149** [+0.049,+0.227] | LOSES | consistent |
| CQR | MAE 0.5h | M | +1.96 → +1.93 | -0.030 [-0.377,+0.303] | 1.99 → 2.03 | +0.045 [-0.052,+0.170] | HOLDS | consistent |
| CQR | MAE 1h | M | +1.78 → +1.54 | -0.247 [-0.708,+0.156] | 2.02 → 1.97 | -0.051 [-0.123,+0.109] | HOLDS | consistent |
| CQR | MAE 2h | M | +1.98 → +1.76 | -0.217 [-0.671,+0.138] | 2.41 → 2.21 | -0.200 [-0.307,+0.008] | HOLDS | consistent |
| CQR | MAE 5h | M | +2.46 → +2.46 | +0.001 [-0.312,+0.303] | 2.55 → 2.31 | **-0.249** [-0.359,-0.129] | IMPROVES | NEW |
| CQR | MAE 10h | M | +2.92 → +2.82 | -0.101 [-0.349,+0.118] | 2.38 → 2.43 | +0.055 [-0.047,+0.160] | HOLDS | consistent |

| model | M/A | MFE: improves / holds / loses | MAE: improves / holds / loses | sig. better (skill, gap) | sig. worse (skill, gap) |
|---|---|---|---|---|---|
| Linear QR | M | 0 / 5 / 0 | 0 / 4 / 1 | 0, 0 | 0, 1 |
| QTREE | M | 1 / 3 / 1 | 1 / 3 / 1 | 1, 1 | 1, 1 |
| kNN | M | 0 / 0 / 5 | 2 / 1 / 2 | 0, 3 | 6, 3 |
| CQR | M | 1 / 3 / 1 | 1 / 4 / 0 | 1, 1 | 1, 1 |
| **all 40** | M | **6 improve, 23 hold, 11 lose** | | **7** | **14** |

### Permutation importance at every moved cell — group rows

All four models moved, so 17 cells. Skill points against climatology, held out, 20 shuffles, day-clustered 95% interval, per-horizon predictions before horizon enforcement. Single-column rows for all nine features are in the log. Read the hour pair from the joint row, as before.

| cell | M/A | outcome | vol_48 / vol_48_1m | hour pair | hedge pair | all four new | old five |
|---|---|---|---|---|---|---|---|
| Linear QR MAE 10h | M | LOSES | +5.920 [+5.218,+6.738] | +0.160 [+0.044,+0.272] | +0.088 [-0.011,+0.189] | +0.230 [+0.086,+0.400] | +5.645 [+4.840,+6.567] |
| QTREE MFE 0.5h | M | IMPROVES | +2.927 [+2.613,+3.254] | +0.298 [+0.127,+0.456] | -0.041 [-0.086,+0.011] | +0.301 [+0.135,+0.475] | +9.021 [+8.039,+10.051] |
| QTREE MFE 10h | M | LOSES | +4.646 [+4.033,+5.178] | -0.109 [-0.258,+0.046] | +0.075 [-0.022,+0.157] | -0.042 [-0.211,+0.123] | +8.373 [+7.552,+9.236] |
| QTREE MAE 5h | M | IMPROVES | +3.507 [+3.023,+4.025] | +0.214 [-0.062,+0.468] | +0.099 [+0.028,+0.177] | +0.309 [+0.048,+0.584] | +4.571 [+3.969,+5.208] |
| QTREE MAE 10h | M | LOSES | +4.135 [+3.593,+4.798] | +0.125 [-0.087,+0.321] | +0.184 [+0.096,+0.274] | +0.294 [+0.073,+0.504] | +4.730 [+4.139,+5.437] |
| kNN MFE 0.5h | M | LOSES | +2.091 [+1.802,+2.369] | +0.170 [-0.123,+0.510] | -0.073 [-0.208,+0.065] | +0.216 [-0.076,+0.553] | +7.043 [+6.271,+7.936] |
| kNN MFE 1h | M | LOSES | +2.331 [+2.048,+2.603] | +0.123 [-0.140,+0.382] | -0.039 [-0.219,+0.110] | +0.122 [-0.171,+0.396] | +7.467 [+6.653,+8.265] |
| kNN MFE 2h | M | LOSES | +2.767 [+2.426,+3.121] | +0.195 [-0.125,+0.482] | +0.056 [-0.084,+0.206] | +0.247 [-0.125,+0.573] | +7.510 [+6.818,+8.336] |
| kNN MFE 5h | M | LOSES | +3.050 [+2.593,+3.470] | +0.232 [-0.026,+0.510] | +0.076 [-0.073,+0.217] | +0.244 [-0.024,+0.523] | +7.172 [+6.457,+7.935] |
| kNN MFE 10h | M | LOSES | +3.308 [+2.865,+3.695] | +0.011 [-0.260,+0.255] | +0.134 [-0.009,+0.269] | +0.079 [-0.189,+0.332] | +7.193 [+6.444,+7.904] |
| kNN MAE 0.5h | M | LOSES | +0.961 [+0.748,+1.172] | -0.083 [-0.457,+0.258] | +0.176 [+0.031,+0.337] | +0.117 [-0.226,+0.465] | +4.169 [+3.552,+4.779] |
| kNN MAE 1h | M | LOSES | +1.269 [+0.977,+1.556] | -0.184 [-0.428,+0.066] | +0.158 [-0.026,+0.349] | +0.026 [-0.257,+0.301] | +3.779 [+3.081,+4.518] |
| kNN MAE 2h | M | IMPROVES | +1.513 [+1.200,+1.802] | +0.026 [-0.246,+0.295] | +0.195 [+0.004,+0.372] | +0.220 [-0.115,+0.573] | +3.897 [+3.240,+4.629] |
| kNN MAE 10h | M | IMPROVES | +2.584 [+2.167,+3.062] | +0.160 [-0.261,+0.583] | +0.292 [+0.126,+0.464] | +0.369 [-0.063,+0.807] | +4.423 [+3.844,+5.086] |
| CQR MFE 0.5h | M | IMPROVES | +2.932 [+2.607,+3.266] | +0.311 [+0.134,+0.470] | -0.043 [-0.088,+0.013] | +0.290 [+0.119,+0.465] | +8.982 [+8.003,+10.077] |
| CQR MFE 10h | M | LOSES | +4.734 [+4.142,+5.269] | -0.096 [-0.239,+0.056] | +0.068 [-0.027,+0.150] | -0.045 [-0.229,+0.122] | +8.573 [+7.759,+9.348] |
| CQR MAE 5h | M | IMPROVES | +3.494 [+3.003,+3.989] | +0.230 [-0.043,+0.481] | +0.110 [+0.034,+0.184] | +0.325 [+0.051,+0.608] | +4.583 [+3.949,+5.246] |

### What it says

- **Nothing here is a new gain.** 6 cells improve and 11 lose. There are 7 significantly-better tests against 14 significantly-worse, out of 80, where chance alone gives about 2 on each side. The losses are the pattern.
- **The five NEW cells come down to two results, and neither is clean.**
  - *QTREE and CQR at MFE 0.5h* (skill +0.18 each) are one result, not two: CQR is QTREE recentred on val. It traces to the **hour pair**, worth +0.30–0.31 there, interval clear of zero. It is a single horizon. 1h is directional (+0.2, not significant), 2h–5h hold, and by 10h the same model *loses* skill. A short-horizon hour effect is possible. One cell against an expected ~2 chance hits is not evidence of it.
  - *CQR at MAE 5h* (gap −0.25) is QTREE's own MAE 5h result passed through CQR. Hour alone gave −0.153 at that cell before. It is the lone 5h calibration gain already judged noise, reproduced, not new.
  - *kNN at MAE 2h and 10h* gain calibration while losing skill at the same cells (−0.32 and −0.16, not significant). The hedge pair is the one group with weight there (+0.20, +0.29). The model is not better: kNN loses at MAE 0.5h and 1h, and at all five MFE horizons.
- **kNN is clearly damaged** by the four extra columns: 6 significant skill losses and 3 calibration losses, the bulk of all harm in this run. Yet in its MFE cells the new columns' own importance never clears zero. *Reading, not tested:* kNN weighs every standardised column equally in its distance, so four uninformative columns dilute the neighbour match on the columns that matter. It is a property of kNN, not information in the new columns.
- **Linear QR barely moves.** 9 of 10 cells hold. The one significant result is a MAE 10h calibration loss (+0.14). The four columns are worth 0.23 points in that cell against 5.6 for the old five.
- **Did the combination do anything the individual tests did not predict?** No, beyond what the 3-horizon COMBINED run already found (hedge's MAE calibration harm softens in QTREE). The individual tests said "no gain from either candidate", and across four models and five horizons that holds. The new harm is kNN, and it is dilution, not a combined effect of the features.
- **Across every cell, the four new columns together are worth at most ~0.37 skill points.** The old five are worth 3.8–9.0. Where the new columns carry significant weight, the hour pair at MFE 0.5h and the hedge pair on MAE, the paired test shows no lasting gain.

No adoption verdict, as briefed. Nothing in the registry was written.

---

# MARKET-VOL — universe-wide volatility, full registry: MARGINAL, 2026-10-11

Tag: **MARKET-VOL**, against the current registry baseline (MAE on vol_48_1m, cache 5bd8d15af8c8; MFE on vol_48, cache 9e332d92a294; both matched). `newfeat.py --stage market_vol`, log `logs/newfeat_market_vol.log` (809s). Feature saved to `research/datasets/market_vol.npz`.

**The feature.** For each ticker in the pair universe: the mean absolute 30-minute log-return over the 48 bars ending at the entry bar (closes t−48..t, the same 24 hours vol_48 covers). Then the **median** across tickers, excluding the episode's two legs. A ticker counts only if all 49 closes are finite, which means it was listed at least 24 hours before entry. **Universe:** the 212 tradeable tickers. BTC and ETH are in the panel only as market factors and are never paired, so they are left out. **Normalisation:** raw ÷ its median over TRAIN rows (4.413e-03 log-return per 30m), so 1.0 is a typical train-period universe. This is a positive rescale and changes no model: Linear QR and kNN standardise on train inside build_context, and trees are scale-invariant.

**Rule, fixed before the run,** per direction (20 cells = 4 models × 5 horizons):
- *Confirmed harm* is any LOSES cell, except a kNN LOSES cell where market_vol's own importance interval does not clear zero. That case is read as distance dilution.
- A direction *clears* if it has no confirmed harm and IMPROVES in 11 or more of its 20 cells.
- One direction clears → propagate to that direction only. Both clear → propagate to both. Neither → MARGINAL.
- **Gaps filled:** "majority" = 11 of 20; "explained by dilution" = the importance test above.

## Build checks — all passed before scoring

| check | M/A |
|---|---|
| bar_index points at entry_time in the panel, every episode | M, yes (asserted) |
| look-ahead: 500 episodes recomputed from a slice ending at the entry bar | M, last row read at offset **+0**; max diff 4.8e-18 |
| leg exclusion: either leg inside its own average | M, **0 of 53,757** (asserted) |
| legs live at entry, and so actually removed | M, 53,757 of 53,757 |
| tickers per episode | M, min 129, median 201, max 210 |
| thin episodes (< 100 tickers, half the median) | M, **0** |
| market_vol median / 5–95% / max | M, 1.008 / 0.708–1.564 / 7.44 |
| Spearman(market_vol, vol_48) / (market_vol, vol_48_1m) | M, **0.041** / 0.064: new information, not a copy of the pair's own volatility |

| quarter | M/A | episodes | tickers min / median / max |
|---|---|---|---|
| 2025Q2 | M | 149 | 129 / 130 / 130 |
| 2025Q3 | M | 3,653 | 130 / 134 / 145 |
| 2025Q4 | M | 6,439 | 145 / 169 / 176 |
| 2026Q1 | M | 8,804 | 176 / 183 / 187 |
| 2026Q2 | M | 13,424 | 187 / 200 / 208 |
| 2026Q3 | M | 19,363 | 208 / 210 / 210 |
| 2026Q4 | M | 1,925 | 210 / 210 / 210 |

The universe grows from 130 to 210 tickers across the history. Train sees 130–187 tickers and held out sees 208–210. A median is robust to that, but the train and held-out universes are not the same set of names.

## Paired, per model, against its own 5-feature baseline

Bold = the interval clears zero. Skill: + helps. Gap: − is better calibrated.

| model | cell | M/A | skill base → +mvol | skill Δ [95% CI] | gap base → +mvol | gap Δ [95% CI] | outcome |
|---|---|---|---|---|---|---|---|
| Linear QR | MFE 0.5h | M | +4.39 → +4.44 | +0.052 [-0.026,+0.136] | 0.75 → 0.70 | -0.055 [-0.110,+0.086] | HOLDS |
| Linear QR | MFE 1h | M | +4.69 → +4.75 | **+0.056** [+0.002,+0.112] | 1.06 → 1.05 | -0.013 [-0.071,+0.043] | IMPROVES |
| Linear QR | MFE 2h | M | +5.23 → +5.24 | +0.018 [-0.008,+0.045] | 1.42 → 1.43 | +0.018 [-0.033,+0.070] | HOLDS |
| Linear QR | MFE 5h | M | +4.88 → +4.86 | -0.019 [-0.064,+0.027] | 2.34 → 2.34 | +0.002 [-0.055,+0.050] | HOLDS |
| Linear QR | MFE 10h | M | +4.94 → +4.98 | +0.041 [-0.047,+0.139] | 2.41 → 2.39 | -0.021 [-0.114,+0.061] | HOLDS |
| Linear QR | MAE 0.5h | M | +2.39 → +2.39 | -0.005 [-0.046,+0.039] | 2.16 → 2.14 | -0.017 [-0.099,+0.082] | HOLDS |
| Linear QR | MAE 1h | M | +2.25 → +2.28 | +0.025 [-0.011,+0.060] | 2.45 → 2.44 | -0.016 [-0.099,+0.084] | HOLDS |
| Linear QR | MAE 2h | M | +2.32 → +2.39 | **+0.071** [+0.022,+0.121] | 2.76 → 2.72 | -0.044 [-0.146,+0.064] | IMPROVES |
| Linear QR | MAE 5h | M | +2.74 → +2.84 | **+0.101** [+0.012,+0.187] | 3.04 → 3.01 | -0.029 [-0.132,+0.092] | IMPROVES |
| Linear QR | MAE 10h | M | +3.21 → +3.37 | **+0.164** [+0.017,+0.315] | 3.03 → 3.04 | +0.016 [-0.118,+0.171] | IMPROVES |
| QTREE | MFE 0.5h | M | +4.55 → +4.52 | -0.036 [-0.327,+0.182] | 0.62 → 0.68 | +0.068 [-0.058,+0.220] | HOLDS |
| QTREE | MFE 1h | M | +4.88 → +4.82 | -0.058 [-0.220,+0.092] | 1.10 → 1.12 | +0.020 [-0.063,+0.112] | HOLDS |
| QTREE | MFE 2h | M | +4.87 → +4.82 | -0.045 [-0.171,+0.065] | 1.48 → 1.46 | -0.016 [-0.116,+0.131] | HOLDS |
| QTREE | MFE 5h | M | +4.50 → +4.47 | -0.033 [-0.162,+0.107] | 2.37 → 2.27 | **-0.106** [-0.180,-0.023] | IMPROVES |
| QTREE | MFE 10h | M | +4.56 → +4.43 | -0.130 [-0.408,+0.147] | 2.45 → 2.22 | **-0.231** [-0.466,-0.016] | IMPROVES |
| QTREE | MAE 0.5h | M | +1.93 → +1.88 | -0.050 [-0.422,+0.284] | 1.99 → 2.07 | +0.079 [-0.040,+0.282] | HOLDS |
| QTREE | MAE 1h | M | +1.70 → +1.88 | +0.179 [-0.229,+0.540] | 2.23 → 2.37 | +0.134 [-0.028,+0.325] | HOLDS |
| QTREE | MAE 2h | M | +1.88 → +2.19 | +0.307 [-0.007,+0.605] | 2.52 → 2.60 | +0.089 [-0.112,+0.334] | HOLDS |
| QTREE | MAE 5h | M | +2.31 → +2.54 | +0.222 [-0.097,+0.524] | 2.84 → 2.77 | -0.073 [-0.257,+0.144] | HOLDS |
| QTREE | MAE 10h | M | +2.77 → +2.75 | -0.026 [-0.368,+0.280] | 2.86 → 2.96 | +0.102 [-0.168,+0.391] | HOLDS |
| kNN | MFE 0.5h | M | +4.39 → +4.32 | -0.066 [-0.180,+0.069] | 0.69 → 0.73 | +0.042 [-0.122,+0.178] | HOLDS |
| kNN | MFE 1h | M | +4.60 → +4.46 | **-0.139** [-0.272,-0.001] | 0.97 → 1.10 | +0.127 [-0.014,+0.299] | LOSES |
| kNN | MFE 2h | M | +4.68 → +4.61 | -0.075 [-0.235,+0.081] | 1.47 → 1.53 | +0.060 [-0.051,+0.222] | HOLDS |
| kNN | MFE 5h | M | +4.28 → +4.19 | -0.090 [-0.232,+0.041] | 2.40 → 2.45 | +0.049 [-0.052,+0.153] | HOLDS |
| kNN | MFE 10h | M | +4.23 → +4.22 | -0.011 [-0.149,+0.139] | 2.48 → 2.51 | +0.030 [-0.110,+0.152] | HOLDS |
| kNN | MAE 0.5h | M | +1.67 → +1.75 | +0.079 [-0.358,+0.390] | 2.21 → 1.99 | **-0.219** [-0.341,-0.042] | IMPROVES |
| kNN | MAE 1h | M | +1.48 → +1.60 | +0.120 [-0.272,+0.433] | 2.42 → 2.28 | -0.137 [-0.271,+0.028] | HOLDS |
| kNN | MAE 2h | M | +1.65 → +1.77 | +0.118 [-0.200,+0.459] | 2.86 → 2.70 | -0.159 [-0.363,+0.060] | HOLDS |
| kNN | MAE 5h | M | +2.04 → +2.17 | +0.128 [-0.161,+0.407] | 3.08 → 2.96 | -0.123 [-0.325,+0.091] | HOLDS |
| kNN | MAE 10h | M | +2.48 → +2.63 | +0.151 [-0.233,+0.551] | 3.20 → 3.03 | -0.171 [-0.413,+0.114] | HOLDS |
| CQR | MFE 0.5h | M | +4.55 → +4.51 | -0.037 [-0.330,+0.181] | 0.68 → 0.74 | +0.065 [-0.042,+0.210] | HOLDS |
| CQR | MFE 1h | M | +4.92 → +4.85 | -0.064 [-0.225,+0.081] | 0.80 → 0.88 | +0.082 [-0.080,+0.136] | HOLDS |
| CQR | MFE 2h | M | +4.92 → +4.86 | -0.054 [-0.178,+0.059] | 1.18 → 1.23 | +0.052 [-0.109,+0.177] | HOLDS |
| CQR | MFE 5h | M | +4.62 → +4.59 | -0.029 [-0.162,+0.117] | 1.89 → 1.74 | **-0.153** [-0.249,-0.055] | IMPROVES |
| CQR | MFE 10h | M | +4.70 → +4.55 | -0.150 [-0.426,+0.131] | 1.86 → 1.71 | -0.153 [-0.362,+0.076] | HOLDS |
| CQR | MAE 0.5h | M | +1.96 → +1.91 | -0.044 [-0.422,+0.283] | 1.99 → 2.09 | +0.101 [-0.078,+0.282] | HOLDS |
| CQR | MAE 1h | M | +1.78 → +1.98 | +0.197 [-0.207,+0.556] | 2.02 → 2.10 | +0.073 [-0.131,+0.306] | HOLDS |
| CQR | MAE 2h | M | +1.98 → +2.28 | +0.305 [-0.012,+0.601] | 2.41 → 2.45 | +0.044 [-0.166,+0.305] | HOLDS |
| CQR | MAE 5h | M | +2.46 → +2.66 | +0.206 [-0.109,+0.498] | 2.55 → 2.53 | -0.029 [-0.223,+0.202] | HOLDS |
| CQR | MAE 10h | M | +2.92 → +2.88 | -0.035 [-0.368,+0.263] | 2.38 → 2.47 | +0.091 [-0.181,+0.400] | HOLDS |

## market_vol's own importance at every moved cell

| model | cell | M/A | outcome | market_vol importance, skill points [95% CI] |
|---|---|---|---|---|
| Linear QR | MFE 1h | M | IMPROVES | −0.019 [−0.069, +0.042] |
| QTREE | MFE 5h | M | IMPROVES | −0.025 [−0.147, +0.117] |
| QTREE | MFE 10h | M | IMPROVES | +0.028 [−0.235, +0.312] |
| kNN | MFE 1h | M | LOSES | −0.093 [−0.207, +0.018] → dilution |
| CQR | MFE 5h | M | IMPROVES | −0.027 [−0.161, +0.120] |
| Linear QR | MAE 2h | M | IMPROVES | **+0.073** [+0.019, +0.123] |
| Linear QR | MAE 5h | M | IMPROVES | **+0.121** [+0.028, +0.213] |
| Linear QR | MAE 10h | M | IMPROVES | **+0.213** [+0.038, +0.385] |
| kNN | MAE 0.5h | M | IMPROVES | −0.008 [−0.443, +0.287] |

## Decision — MARGINAL, by the rule fixed before the run

| direction | M/A | IMPROVES (need 11) | confirmed harm | kNN losses read as dilution | |
|---|---|---|---|---|---|
| MFE | M | 4 of 20 | 0 | 1 (kNN 1h) | does not clear |
| MAE | M | 4 of 20 | 0 | 0 | does not clear |

**Verdict: MARGINAL.** Neither direction reaches 11 of 20. Reported and stopped; nothing propagated.

## What it says — a different shape from every earlier candidate

- **No harm anywhere.** This is the first candidate in this thread with zero confirmed harm. Of 80 paired tests, **8 are significantly better and 1 is worse**, where chance alone gives about 2 on each side. Hour-of-day, hedge quality and the four combined all leaned toward harm (the combination ran 7 better to 14 worse).
- **One coherent result: Linear QR on MAE.**
  - Skill improves at 2h, 5h and 10h (+0.07, +0.10, +0.16), growing with horizon, and 1h leans the same way.
  - At each of those cells, market_vol's own importance clears zero (+0.07, +0.12, +0.21). The gain traces to the column, not to refit noise.
  - Linear QR's MAE 10h skill goes from +3.21% to +3.37%, the highest MAE skill of any model so far. That level is a later look at already-scored rows; the paired difference is the new measurement.
  - This is the pattern vol_48_1m showed before it was adopted: consistent across horizons, growing with horizon, traceable to the column.
- **The other improvements don't trace to the column.** QTREE and CQR MFE 5h/10h and kNN MAE 0.5h improve on calibration, but market_vol's importance there is indistinguishable from zero. Treat them as refit variation.
- **The tree models lean positive on MAE skill but never clear.** QTREE and CQR gain +0.18 to +0.31 at MAE 1h–5h, every interval touching zero.
- **Why the rule says MARGINAL anyway:** it asks for a majority of all 20 cells per direction, across all four models. A gain confined to one model can't clear that by design, however clean it is. Whether a single-model result deserves its own follow-up is a decision for the plan, not taken here.

## Linear QR / MAE — all five horizons: ADOPT for this model and direction, 2026-10-12

Still tag **MARKET-VOL**. `newfeat.py --stage mvol_linear`, log `logs/newfeat_mvol_linear.log` (310s). Linear QR only, MAE only. Baseline: the current MAE features (vol_48_1m, vratio, vol_slope, sandwich, off_mark), paired against the cached Linear QR MAE predictions (5bd8d15af8c8). New: the same plus market_vol, refitted at all five horizons and two-pass enforced. No LP fallbacks.

**What is new here.** The MARKET-VOL run above already scored all five horizons. The five paired deltas reproduce it exactly (asserted), so they are a check, not a new measurement. New: market_vol's importance at 0.5h and 1h, the five-horizon net effect, and the 10h plain miss. Importance at 2h/5h/10h is a fresh draw by the same method; it agrees with the earlier one to within 0.002.

**Rule, fixed before the run.** ADOPT if both hold:
- **(a) No harm:** no horizon has a significantly worse skill or gap.
- **(b) Net improvement:** the mean of the five paired skill gains has a day-clustered 95% interval entirely above zero. The same day resamples are used at every horizon, so the average is resampled jointly.

**Gap filled:** the brief's "no real harm" and "net effect a genuine improvement" are read as (a) and (b).

| h | M/A | skill base → +mvol | skill Δ [95% CI] | gap base → +mvol | gap Δ [95% CI] | market_vol importance [95% CI] |
|---|---|---|---|---|---|---|
| 0.5h | M | +2.39 → +2.39 | −0.005 [−0.046, +0.039] | 2.16 → 2.14 | −0.017 [−0.099, +0.082] | −0.009 [−0.044, +0.042] |
| 1h | M | +2.25 → +2.28 | +0.025 [−0.011, +0.060] | 2.45 → 2.44 | −0.016 [−0.099, +0.084] | +0.039 [−0.003, +0.078] |
| 2h | M | +2.32 → +2.39 | **+0.071** [+0.022, +0.121] | 2.76 → 2.72 | −0.044 [−0.146, +0.064] | **+0.071** [+0.019, +0.121] |
| 5h | M | +2.74 → +2.84 | **+0.101** [+0.012, +0.187] | 3.04 → 3.01 | −0.029 [−0.132, +0.092] | **+0.122** [+0.032, +0.221] |
| 10h | M | +3.21 → +3.37 | **+0.164** [+0.017, +0.315] | 3.03 → 3.04 | +0.016 [−0.118, +0.171] | **+0.211** [+0.040, +0.385] |

| decision input | M/A | value |
|---|---|---|
| (a) horizons with a significantly worse measure | M | **none** |
| (b) mean paired skill gain, five horizons | M | **+0.071** [+0.011, +0.132] |

**Verdict: ADOPT market_vol for Linear QR / MAE.** Both conditions hold. The gain is zero at 0.5h, leans positive at 1h, and is confirmed and growing from 2h to 10h. At each horizon, market_vol's own importance matches the size of the skill gain, so the gain is the column's. Calibration doesn't move at any horizon: every gap interval straddles zero. **The registry rebuild for this model and direction is the next build. Nothing was written to the registry here.**

## Plain miss — MAE 10h, average distance between the actual move and the median guess

Same units and framing as **PLAIN-MISS**: mean |actual − q50|, in sigma, held out, 18,064 rows.

| model | M/A | average miss, σ | vs climatology |
|---|---|---|---|
| Climatology | M | 1.949 (reproduces PLAIN-MISS) | — |
| Linear QR, without market_vol | M | 1.908 (reproduces PLAIN-MISS) | −2.1% |
| **Linear QR, with market_vol** | M | **1.905** | −2.2% |

| number | M/A |
|---|---|
| with − without | M, **−0.0026σ** [−0.0053, −0.0001] |

**In plain terms:** adding market-wide volatility makes the 10h median guess miss by 0.0026σ less on average. That is real (the interval clears zero, just) and very small: about a tenth of a percent of the typical miss. It moves Linear QR's lead over climatology from 2.1% to 2.2%. The +0.16-point skill gain at 10h is measured over all five quantiles. This figure covers the median alone. How the gain splits across quantiles was not measured.

---

# ROLLING-WINDOW — a trailing 9-month train against the full history: SAME OR WORSE, 2026-10-12

Tag: **ROLLING-WINDOW**. `rolling_window.py`, log `logs/rolling_window.log` (523s). The full registry: five models × five horizons × two directions = 50 cells, each scored on HO1 (8,200 rows, 39 days) and HO2 (9,864 rows, 40 days). Current best config: MAE on vol_48_1m, MFE on vol_48. Full-history predictions are the cached registry (fingerprints 9e332d92a294 / 5bd8d15af8c8, both matched).

**A corrected premise.** The brief assumed a ~667-day fit block. On the 53,757-episode population, the 1-minute backfill wall sets the start, and the fit block spans **386 days**. A 12-month window would have dropped about 3% of train. So the window is the shortest the brief allows: **9 months before the held-out start, training rows on or after 2025-10-18.**

| span | M/A | dates | rows | days |
|---|---|---|---|---|
| full train | M | 2025-06-26 → 2026-04-30 | 22,645 | 309 |
| window train | M | 2025-10-18 → 2026-04-30 | 17,965 (79.3%) | 195 |
| dropped | M | 2025-06-26 → 2025-10-17 | 4,680 | 114 |
| val (unchanged) | M | 2026-05-01 → 2026-07-17 | 13,048 | 78 |
| held out (unchanged) | M | 2026-07-18 → 2026-10-04 | 18,064 | 79 |

**Only the training span changes.** Val, held out and every hyperparameter are untouched. Climatology's quantiles come from the window. Linear QR and kNN standardise on the window, and kNN draws neighbours from the smaller pool. Skill for both versions uses one fixed denominator: the cached full-history Climatology.

| check | M/A |
|---|---|
| full-history QTREE through this script's builder vs the cache, MFE / MAE | M, **0** / **0**: the builder reproduces the registry |
| Linear QR LP fallbacks | M, 0 |

**Rule, fixed before the run.** Per cell and half, on the paired gap difference (window − full): TIGHTER if the interval is entirely below zero, LOOSER if entirely above, SAME otherwise. **RECENCY MATTERS** if, on HO2, at least 26 of 50 cells are TIGHTER and at most 2 are LOOSER. Otherwise **SAME OR WORSE**. **Gap filled:** "meaningfully tighter, especially on HO2" is read as that HO2 gate. HO1 and skill are reported, not gated.

## Counts

| model | dir | M/A | HO1 tighter | HO1 looser | HO2 tighter | HO2 looser |
|---|---|---|---|---|---|---|
| Climatology | MFE | M | 0 | 1 | 0 | 3 |
| Climatology | MAE | M | 0 | 2 | 0 | **5** |
| Linear QR | MFE | M | 0 | 0 | 2 | 0 |
| Linear QR | MAE | M | 1 | 0 | 0 | 2 |
| QTREE | MFE | M | 0 | 0 | 1 | 0 |
| QTREE | MAE | M | 0 | 1 | 0 | 4 |
| kNN | MFE | M | 0 | 0 | 1 | 0 |
| kNN | MAE | M | 0 | 0 | 0 | 1 |
| CQR | MFE | M | 0 | 0 | 1 | 0 |
| CQR | MAE | M | 0 | 1 | 0 | 1 |

| half | M/A | gap TIGHTER | gap LOOSER | gap SAME | skill sig. better | skill sig. worse |
|---|---|---|---|---|---|---|
| HO1 | M | 1 | 5 | 44 | **14** | 1 |
| HO2 | M | 5 | **16** | 29 | **11** | 2 |

**Verdict: SAME OR WORSE.** On HO2, 5 of 50 cells are tighter (26 needed) and 16 are looser (2 allowed). **Recency alone doesn't fix the calibration drift. It makes it worse on HO2.** The earlier inconclusive recurrence result stands. The walk-forward build is not justified by this test.

## Every cell with a significant change

41 of the 100 cells. Bold = the interval clears zero. The full 100-cell table is in the log.

| half | model | cell | M/A | gap full → window | gap Δ [95% CI] | | skill full → window | skill Δ [95% CI] |
|---|---|---|---|---|---|---|---|---|
| HO1 | Climatology | MFE 0.5h | M | 0.66 → 0.56 | -0.098 [-0.253,+0.100] | SAME | +0.00 → +0.08 | **+0.083** [+0.015,+0.140] |
| HO1 | Climatology | MFE 10h | M | 1.46 → 1.68 | **+0.217** [+0.020,+0.258] | LOOSER | +0.00 → -0.08 | **-0.076** [-0.138,-0.002] |
| HO1 | Climatology | MAE 2h | M | 1.51 → 1.57 | **+0.054** [+0.010,+0.105] | LOOSER | +0.00 → +0.03 | **+0.033** [+0.005,+0.063] |
| HO1 | Climatology | MAE 5h | M | 1.59 → 1.79 | **+0.200** [+0.088,+0.246] | LOOSER | +0.00 → +0.02 | +0.015 [-0.014,+0.057] |
| HO1 | Linear QR | MFE 0.5h | M | 0.48 → 0.57 | +0.095 [-0.122,+0.222] | SAME | +3.78 → +4.05 | **+0.275** [+0.176,+0.364] |
| HO1 | Linear QR | MFE 1h | M | 0.60 → 0.66 | +0.059 [-0.088,+0.321] | SAME | +4.38 → +4.60 | **+0.224** [+0.088,+0.347] |
| HO1 | Linear QR | MAE 0.5h | M | 1.53 → 1.56 | +0.032 [-0.015,+0.089] | SAME | +2.48 → +2.59 | **+0.106** [+0.051,+0.171] |
| HO1 | Linear QR | MAE 1h | M | 1.68 → 1.70 | +0.022 [-0.033,+0.095] | SAME | +2.48 → +2.67 | **+0.192** [+0.113,+0.272] |
| HO1 | Linear QR | MAE 2h | M | 1.71 → 1.59 | **-0.127** [-0.180,-0.021] | TIGHTER | +2.44 → +2.64 | **+0.199** [+0.099,+0.300] |
| HO1 | Linear QR | MAE 5h | M | 1.60 → 1.60 | -0.002 [-0.083,+0.089] | SAME | +2.75 → +2.94 | **+0.188** [+0.058,+0.307] |
| HO1 | QTREE | MAE 0.5h | M | 1.41 → 1.49 | +0.073 [-0.018,+0.188] | SAME | +2.00 → +2.26 | **+0.266** [+0.113,+0.424] |
| HO1 | QTREE | MAE 1h | M | 1.47 → 1.48 | +0.010 [-0.090,+0.122] | SAME | +1.89 → +2.07 | **+0.180** [+0.050,+0.298] |
| HO1 | QTREE | MAE 5h | M | 1.37 → 1.54 | **+0.168** [+0.021,+0.274] | LOOSER | +2.15 → +2.25 | +0.101 [-0.023,+0.222] |
| HO1 | CQR | MAE 0.5h | M | 1.15 → 1.26 | **+0.112** [+0.031,+0.268] | LOOSER | +2.05 → +2.31 | **+0.269** [+0.118,+0.426] |
| HO1 | CQR | MAE 1h | M | 1.01 → 1.04 | +0.029 [-0.130,+0.130] | SAME | +1.96 → +2.15 | **+0.184** [+0.059,+0.300] |
| HO2 | Climatology | MFE 2h | M | 2.55 → 2.88 | **+0.326** [+0.172,+0.421] | LOOSER | +0.00 → -0.11 | -0.106 [-0.238,+0.005] |
| HO2 | Climatology | MFE 5h | M | 3.32 → 3.56 | **+0.241** [+0.121,+0.282] | LOOSER | +0.00 → -0.12 | **-0.117** [-0.178,-0.048] |
| HO2 | Climatology | MFE 10h | M | 3.10 → 3.32 | **+0.223** [+0.086,+0.272] | LOOSER | +0.00 → -0.09 | **-0.086** [-0.159,-0.002] |
| HO2 | Climatology | MAE 0.5h | M | 2.48 → 2.54 | **+0.055** [+0.029,+0.130] | LOOSER | +0.00 → +0.00 | +0.004 [-0.042,+0.059] |
| HO2 | Climatology | MAE 1h | M | 2.89 → 2.94 | **+0.049** [+0.020,+0.078] | LOOSER | +0.00 → +0.03 | **+0.031** [+0.002,+0.066] |
| HO2 | Climatology | MAE 2h | M | 3.23 → 3.35 | **+0.120** [+0.089,+0.152] | LOOSER | +0.00 → +0.01 | +0.006 [-0.029,+0.046] |
| HO2 | Climatology | MAE 5h | M | 3.80 → 4.05 | **+0.249** [+0.201,+0.306] | LOOSER | +0.00 → -0.04 | -0.044 [-0.086,+0.001] |
| HO2 | Climatology | MAE 10h | M | 4.26 → 4.33 | **+0.071** [+0.027,+0.115] | LOOSER | +0.00 → +0.07 | +0.072 [-0.011,+0.145] |
| HO2 | Linear QR | MFE 0.5h | M | 1.10 → 1.09 | -0.014 [-0.118,+0.040] | SAME | +4.90 → +5.15 | **+0.254** [+0.046,+0.444] |
| HO2 | Linear QR | MFE 1h | M | 1.64 → 1.62 | -0.014 [-0.120,+0.070] | SAME | +4.95 → +5.20 | **+0.256** [+0.111,+0.404] |
| HO2 | Linear QR | MFE 5h | M | 3.25 → 3.07 | **-0.180** [-0.223,-0.067] | TIGHTER | +4.84 → +4.88 | +0.050 [-0.027,+0.112] |
| HO2 | Linear QR | MFE 10h | M | 3.08 → 2.89 | **-0.194** [-0.303,-0.048] | TIGHTER | +4.65 → +4.73 | +0.079 [-0.015,+0.156] |
| HO2 | Linear QR | MAE 1h | M | 3.30 → 3.41 | **+0.116** [+0.031,+0.181] | LOOSER | +2.07 → +2.28 | **+0.207** [+0.035,+0.377] |
| HO2 | Linear QR | MAE 2h | M | 3.84 → 3.91 | +0.077 [-0.020,+0.161] | SAME | +2.21 → +2.42 | **+0.205** [+0.069,+0.334] |
| HO2 | Linear QR | MAE 5h | M | 4.40 → 4.48 | **+0.079** [+0.008,+0.170] | LOOSER | +2.73 → +2.86 | +0.125 [-0.056,+0.286] |
| HO2 | Linear QR | MAE 10h | M | 4.73 → 4.73 | -0.006 [-0.075,+0.059] | SAME | +3.51 → +3.70 | **+0.183** [+0.023,+0.325] |
| HO2 | QTREE | MFE 10h | M | 3.12 → 3.03 | **-0.091** [-0.166,-0.015] | TIGHTER | +4.28 → +4.32 | +0.041 [-0.101,+0.161] |
| HO2 | QTREE | MAE 0.5h | M | 2.63 → 2.64 | +0.018 [-0.066,+0.135] | SAME | +1.87 → +2.09 | **+0.225** [+0.087,+0.378] |
| HO2 | QTREE | MAE 1h | M | 3.07 → 3.18 | **+0.109** [+0.013,+0.180] | LOOSER | +1.54 → +1.75 | **+0.213** [+0.060,+0.355] |
| HO2 | QTREE | MAE 2h | M | 3.50 → 3.79 | **+0.292** [+0.216,+0.370] | LOOSER | +1.81 → +1.88 | +0.074 [-0.056,+0.212] |
| HO2 | QTREE | MAE 5h | M | 4.19 → 4.28 | **+0.095** [+0.008,+0.196] | LOOSER | +2.45 → +2.45 | -0.001 [-0.142,+0.147] |
| HO2 | QTREE | MAE 10h | M | 4.55 → 4.63 | **+0.085** [+0.017,+0.171] | LOOSER | +3.15 → +3.13 | -0.021 [-0.197,+0.171] |
| HO2 | CQR | MFE 5h | M | 2.81 → 2.62 | **-0.189** [-0.279,-0.031] | TIGHTER | +4.55 → +4.65 | +0.104 [-0.022,+0.222] |
| HO2 | CQR | MAE 0.5h | M | 2.69 → 2.68 | -0.010 [-0.133,+0.190] | SAME | +1.88 → +2.11 | **+0.230** [+0.096,+0.379] |
| HO2 | CQR | MAE 1h | M | 2.89 → 2.89 | +0.002 [-0.088,+0.076] | SAME | +1.64 → +1.87 | **+0.229** [+0.075,+0.372] |
| HO2 | CQR | MAE 2h | M | 3.42 → 3.59 | **+0.174** [+0.083,+0.256] | LOOSER | +1.95 → +2.06 | +0.111 [-0.022,+0.242] |

## What it says

- **Calibration gets worse with recent-only training, and it is worst where it was meant to help.** On HO2, 16 cells loosen against 5 that tighten. The clearest case is **Climatology: 8 of its 10 HO2 cells loosen**, all five on MAE. Climatology has no features. So the unconditional distribution of the most recent seven months sits *further* from HO2 than the full history does. Dropping old data doesn't bring training closer to the drifted period. It moves it away.
- **Skill moves the other way.** The window improves skill in 14 HO1 cells and 11 HO2 cells, against 1 and 2 worse, where chance gives about 1 on each side. The gains come almost entirely from the feature models at short horizons (0.5h to 2h) and from Linear QR, about +0.2 to +0.3 points. Climatology gains no skill.
- **Reading, not tested:** recent data seems to carry a sharper conditional relationship between features and travel, which is what skill rewards. At the same time it carries a worse estimate of the overall *level*, which is what calibration measures. The two move in opposite directions in this one test.
- **Weak-contrast caveat, as stated before the run:** the window drops only the oldest 21% of train. A shorter window was outside the brief's 9–12 month range and was not tried.

Nothing in the registry was written.

---

# REGISTRY-CONSOLIDATED — the standing registry is Climatology, Linear QR, CQR, 2026-10-12

Tag: **REGISTRY-CONSOLIDATED**. A decision record with no new measurement, so it has no M/A rows. Code: `envelope.py` (`MODELS`), effective for every stage written from here on.

- **Kept:** Climatology (the fixed denominator), Linear QR, CQR.
- **Retired as registry entries:** QTREE and kNN. Nothing re-fits them going forward. **Every published QTREE and kNN number above stays as the record. Nothing was deleted.**
- **QTREE stays as code**, because it is CQR's internal machinery: CQR is QTREE recentred and widened on val. It's a component of CQR, not a registry entry competing for a slot.
- **kNN stays as code** only so the historical stages that published kNN numbers still reproduce them.

What the code does to keep the record intact:

| change | why |
|---|---|
| `RETIRED_MODELS` (QTREE, kNN) and `REGISTRY_UNTIL_2026_10_12` (the old five, in published order) | Historical stages are pinned to the five-model list, so their published numbers still reproduce: `vol1m.mae_registry` (VOL48-1M-REGISTRY) and `rolling_window.py` (ROLLING-WINDOW). `dependence.py --model` still accepts QTREE. |
| `save_cache` carries forward every cache key a stage does not rewrite | Without it, the next three-model refit would silently delete the cached QTREE/kNN predictions that importance.py, copula.py, vol1m.py, newfeat.py and rolling_window.py read. It is safe because load_or_fit has already refused any cache whose fingerprint differs. |
| The legacy-cache verifier refits every cheap model the cache holds, not only the requested ones; stages look fitters up in `ALL_FITTERS` | Climatology alone doesn't depend on the features, so it could not catch a feature change. The verifier keeps checking QTREE and kNN cells where they exist. |

Not yet run under the consolidated registry: everything. The first stage to run under it will refit or reload three models, not five.

---

# TAIL-CLASSIFIER — is this episode likely to be violent: BOTH MODELS CLEAR, logistic slightly ahead, 2026-10-12

Tag: **TAIL-CLASSIFIER**. `tail_classifier.py`, log `logs/tail_classifier.log` (191s). Matched 53,757-episode set, harness.Split unchanged (train 22,645 / val 13,048 / held out 18,064, ≥ 2026-07-18, touched once).

**A magnitude target, different in kind** from the envelope quantiles (how far, as a distribution) and from the planned direction target (which way). Per horizon: violent = the spread's largest **upward** move exceeds its train 90th percentile, **or** its largest **downward** move exceeds its own. Moves come from 1-minute closes, in entry sigma, unclamped. **Not sign-folded:** MAE/MFE are unfolded back to up/down, so each side of the market is held to its own threshold and the entry sign plays no part in the label. Thresholds come from TRAIN rows only.

**Features:** the confirmed five, with both direction-matched volatility columns because the target spans both directions: vol_48, vol_48_1m, vratio, vol_slope, sandwich, off_mark. **Models:** logistic regression (standardised on train, default L2) and the harness gradient-boosted classifier (harness.TREE, iterations chosen on val by AUC).

**Rule, fixed before the run.** A cell passes the project's classification bar (harness.passes) only if all three hold: held-out AUC > 0.55 (GATE_AUC, reused); day-clustered 95% CI lower bound > 0.50; and AUC above the whole permutation null (15 row-shuffles + 15 day-shuffles of the fit-block labels, refitted identically, with both models facing the same shuffles). A model **CLEARS** if it passes at 3 or more of the 5 horizons. **Gap filled:** the brief didn't say how many horizons; majority was chosen as the bar.

*Added 2026-10-13 after review (Code Checker); no number changed.* The 3-of-5 bar was the builder's choice, **not precedent**: the recurrence track (`drift_recur.py`) used 70%: 7 of 10 cells at a majority of decisive cuts, with at least 2 decisive cuts. The five horizons are nested windows from the same entry, so 3 of 5 is not five independent tests. The test ran **10 cells** (2 models × 5 horizons). Chance passes expected: at most about 0.3 of 10, because the permutation leg alone lets a null cell through with probability at most 1/31 (30 shuffles). All 10 passed with AUC 0.70–0.72. **The result to carry is GBDT − logistic, not the pass:** the EITHER target (STATE.md, AUC 0.6647 / 0.6807) already showed magnitude is predictable, so a clear was expected.

| check | M/A |
|---|---|
| unfold: up/down from MAE/MFE vs read straight off the raw 30m path | M, max diff **0** |
| sign(z_entry) alone, AUC by horizon | M, 0.496 / 0.493 / 0.499 / 0.505 / 0.509: the label carries no direction, as designed |

## Thresholds and base rates

| h | M/A | up p90, σ | down p90, σ | train | val | held out | HO1 | HO2 |
|---|---|---|---|---|---|---|---|---|
| 0.5h | M | 1.582 | 1.605 | 0.193 | 0.157 | 0.180 | 0.176 | 0.184 |
| 1h | M | 2.158 | 2.194 | 0.195 | 0.161 | 0.177 | 0.172 | 0.181 |
| 2h | M | 2.949 | 3.001 | 0.195 | 0.153 | 0.173 | 0.171 | 0.175 |
| 5h | M | 4.275 | 4.372 | 0.196 | 0.162 | 0.179 | 0.183 | 0.175 |
| 10h | M | 5.755 | 5.802 | 0.196 | 0.172 | 0.180 | 0.195 | 0.168 |

The share of violent episodes is about 19.5% on train and 17–18% on held out. The later periods are somewhat calmer at the same thresholds.

## The ten cells

| h | model | M/A | held-out AUC [95% CI] | permutation null max (day-shuffle range) | iters | gate |
|---|---|---|---|---|---|---|
| 0.5h | logistic | M | **0.7150** [0.6991, 0.7318] | 0.6685 (0.3179–0.6143) | — | PASS |
| 0.5h | GBDT | M | **0.7093** [0.6880, 0.7272] | 0.5434 (0.4263–0.5278) | 76 | PASS |
| 1h | logistic | M | **0.7125** [0.6961, 0.7289] | 0.7029 (0.3321–0.5817) | — | PASS |
| 1h | GBDT | M | **0.7069** [0.6863, 0.7278] | 0.5486 (0.4141–0.5359) | 47 | PASS |
| 2h | logistic | M | **0.7086** [0.6929, 0.7248] | 0.6215 (0.3239–0.6036) | — | PASS |
| 2h | GBDT | M | **0.7034** [0.6863, 0.7212] | 0.5427 (0.4008–0.5417) | 65 | PASS |
| 5h | logistic | M | **0.7063** [0.6907, 0.7208] | 0.6343 (0.2978–0.6202) | — | PASS |
| 5h | GBDT | M | **0.7003** [0.6856, 0.7145] | 0.5643 (0.4205–0.5643) | 20 | PASS |
| 10h | logistic | M | **0.7144** [0.6995, 0.7323] | 0.6660 (0.3128–0.6660) | — | PASS |
| 10h | GBDT | M | **0.7104** [0.6957, 0.7284] | 0.6062 (0.4690–0.5655) | 41 | PASS |

*Added 2026-10-13 after review (Code Checker); no number changed.* **The logistic passes are real but narrow at 1h.** Its permutation null is wide: the row-shuffle max reaches 0.7029 at 1h, only 0.0096 below the real 0.7125, and the day-shuffle range at 5h runs 0.2978–0.6202. GBDT's null stays near 0.5 (max 0.54–0.61), so it is the stronger evidence. *Reading, not tested:* a logistic model fitted to shuffled labels still ranks by a random linear direction, and in this feature space any such direction loads on volatility, so it scores far from 0.5 with a random sign.

## Does complexity help? — paired held-out AUC, GBDT − logistic

| h | M/A | GBDT − logistic [95% CI] | |
|---|---|---|---|
| 0.5h | M | −0.0057 [−0.0130, +0.0014] | no difference |
| 1h | M | −0.0055 [−0.0118, +0.0006] | no difference |
| 2h | M | **−0.0052** [−0.0099, −0.0005] | logistic better |
| 5h | M | **−0.0060** [−0.0098, −0.0022] | logistic better |
| 10h | M | **−0.0040** [−0.0072, −0.0005] | logistic better |

## Decision

**Verdict: BOTH CLEAR, at 5 of 5 horizons each.** Per the brief, the next prompt is the tail-specific quantile refinement for the flagged subset. It was not started.

**Complexity does not help on the tail.** The boosted classifier is never better. It is significantly worse at 2h, 5h and 10h, by about 0.005 AUC: small, but one-directional. At 5h it stopped after 20 iterations on val. This matches the rest of the project: the simple linear model leads.

## How to read it

- **AUC 0.71 is strong for this project, and it is not without precedent.** Direction and reversion targets sat near 0.50 (unfolded reversion's 0.59 was a sign artifact). A related earlier magnitude target, "did the spread move far at all" (EITHER), scored 0.6647. This result fits that pattern: magnitude is predictable, direction is not.
- **The signal is very likely the familiar one: volatility.** The target asks whether the spread will move a long way in sigma units, and recent volatility in sigma units (vol_48) has been the dominant predictor of travel distance throughout. *Reading, not tested:* importance was not part of this brief. A rerun with importance would show whether anything beyond the volatility columns contributes.
- **Why logistic's permutation null is so wide** (row-shuffle maxima up to 0.70): a logistic model fit to shuffled labels still ranks held-out rows by *some* linear mix of the features. When one feature strongly predicts the real target, a random sign or weight on it can land far above or below 0.5. That is the null working as intended. It made logistic's 1h pass narrow (0.7125 against a null max of 0.7029). Every other cell clears its null by 0.01 or more.

Nothing in the registry was written.

---

# TAIL-REFINE — step 1, does the classifier know anything new: PASSES by the rule, 2026-10-12

Tag: **TAIL-REFINE**. `tail_classifier.py --stage incremental`, log `logs/tail_refine.log`. The same population, split and "violent" labels as **TAIL-CLASSIFIER**. The logistic classifier was refitted and reproduces the published AUCs to 4 decimals at all five horizons (asserted). Registry caches were fingerprint-checked: 9e332d92a294 (MFE) and 5bd8d15af8c8 (MAE), both matched. Held-out rows were scored before in TAIL-CLASSIFIER. The paired differences here are the new measurement.

**Rule, fixed before the run.** NEW TAIL INFORMATION if the logistic classifier beats ALL FOUR comparators (vol_48 alone, vol_48_1m alone, Linear QR q95, CQR q95), each by a paired day-clustered AUC difference clearing zero, at 3 or more of 5 horizons. Otherwise the volatility signal is restated: stop.

**Gaps filled, before the run:**
- The registry has no q90. **q95**, the nearest quantile it fits, is used.
- The target covers either side, while the registry forecasts MAE and MFE separately. The comparator score is the **larger of the predicted MAE q95 and MFE q95**.
- Registry predictions are the cached ones. market_vol is adopted for Linear QR / MAE, but that rebuild hasn't been done, so it is not included.

## Held-out AUC for "violent", and the classifier's paired margin

| h | score | M/A | AUC [95% CI] | classifier − this [95% CI] | beats? |
|---|---|---|---|---|---|
| 0.5h | **logistic classifier** | M | 0.7150 [0.6991, 0.7318] | — | |
| 0.5h | vol_48 alone | M | 0.6371 [0.6248, 0.6520] | **+0.0779** [+0.0571, +0.0981] | yes |
| 0.5h | vol_48_1m alone | M | 0.6228 [0.6044, 0.6416] | **+0.0922** [+0.0668, +0.1198] | yes |
| 0.5h | Linear QR q95 | M | 0.7000 [0.6779, 0.7185] | **+0.0150** [+0.0097, +0.0209] | yes |
| 0.5h | CQR q95 | M | 0.6937 [0.6740, 0.7110] | **+0.0213** [+0.0156, +0.0265] | yes |
| 1h | **logistic classifier** | M | 0.7125 [0.6961, 0.7289] | — | |
| 1h | vol_48 alone | M | 0.6570 [0.6420, 0.6716] | **+0.0554** [+0.0357, +0.0765] | yes |
| 1h | vol_48_1m alone | M | 0.6463 [0.6290, 0.6632] | **+0.0662** [+0.0431, +0.0920] | yes |
| 1h | Linear QR q95 | M | 0.6875 [0.6660, 0.7080] | **+0.0250** [+0.0172, +0.0323] | yes |
| 1h | CQR q95 | M | 0.6804 [0.6600, 0.7001] | **+0.0320** [+0.0250, +0.0386] | yes |
| 2h | **logistic classifier** | M | 0.7086 [0.6929, 0.7248] | — | |
| 2h | vol_48 alone | M | 0.6598 [0.6424, 0.6745] | **+0.0489** [+0.0299, +0.0674] | yes |
| 2h | vol_48_1m alone | M | 0.6508 [0.6329, 0.6693] | **+0.0579** [+0.0381, +0.0787] | yes |
| 2h | Linear QR q95 | M | 0.6873 [0.6686, 0.7056] | **+0.0213** [+0.0141, +0.0291] | yes |
| 2h | CQR q95 | M | 0.6734 [0.6545, 0.6908] | **+0.0352** [+0.0266, +0.0450] | yes |
| 5h | **logistic classifier** | M | 0.7063 [0.6907, 0.7208] | — | |
| 5h | vol_48 alone | M | 0.6740 [0.6570, 0.6895] | **+0.0323** [+0.0182, +0.0450] | yes |
| 5h | vol_48_1m alone | M | 0.6704 [0.6528, 0.6852] | **+0.0359** [+0.0212, +0.0513] | yes |
| 5h | Linear QR q95 | M | 0.6958 [0.6803, 0.7112] | **+0.0105** [+0.0035, +0.0179] | yes |
| 5h | CQR q95 | M | 0.6741 [0.6589, 0.6895] | **+0.0322** [+0.0232, +0.0412] | yes |
| 10h | **logistic classifier** | M | 0.7144 [0.6995, 0.7323] | — | |
| 10h | vol_48 alone | M | 0.6870 [0.6716, 0.7023] | **+0.0273** [+0.0162, +0.0386] | yes |
| 10h | vol_48_1m alone | M | 0.6867 [0.6715, 0.7047] | **+0.0277** [+0.0155, +0.0403] | yes |
| 10h | Linear QR q95 | M | 0.7096 [0.6937, 0.7293] | +0.0047 [−0.0014, +0.0105] | **no** |
| 10h | CQR q95 | M | 0.6883 [0.6742, 0.7036] | **+0.0260** [+0.0177, +0.0350] | yes |

**Verdict by the rule: NEW TAIL INFORMATION. The classifier beats all four at 4 of 5 horizons (0.5h–5h).** At 10h, Linear QR's own q95 ties it.

## Logistic permutation importance — AUC points lost when shuffled, held out

10 shuffles per set, day-clustered 95% interval.

| feature | M/A | 0.5h | 1h | 2h | 5h | 10h |
|---|---|---|---|---|---|---|
| vol_48 | M | +0.024 | +0.039 | +0.042 | +0.049 | +0.048 |
| vol_48_1m | M | +0.032 | +0.032 | +0.046 | +0.064 | +0.072 |
| vratio | M | +0.022 | +0.014 | +0.010 | +0.005 | +0.003 |
| vol_slope | M | +0.085 | +0.067 | +0.058 | +0.036 | +0.028 |
| sandwich | M | −0.000 | −0.000 | −0.000 | +0.001 | +0.001 |
| off_mark | M | −0.001 | −0.000 | −0.000 | +0.000 | +0.000 |
| **vol pair, jointly** | M | **+0.096** [+0.086, +0.105] | **+0.117** [+0.107, +0.125] | **+0.139** [+0.126, +0.151] | **+0.177** [+0.162, +0.192] | **+0.194** [+0.178, +0.212] |
| **other four, jointly** | M | **+0.122** [+0.102, +0.142] | **+0.093** [+0.076, +0.114] | **+0.080** [+0.062, +0.098] | **+0.048** [+0.035, +0.059] | **+0.037** [+0.026, +0.048] |

Single-feature intervals are in the log.

## Probability calibration, carried forward

| h | M/A | mean predicted, held out (HO1 / HO2) | actual: train | actual: held out (HO1 / HO2) |
|---|---|---|---|---|
| 0.5h | M | 0.193 (0.188 / 0.197) | 0.193 | 0.180 (0.176 / 0.184) |
| 1h | M | 0.196 (0.191 / 0.200) | 0.195 | 0.177 (0.172 / 0.181) |
| 2h | M | 0.197 (0.194 / 0.201) | 0.195 | 0.173 (0.171 / 0.175) |
| 5h | M | 0.202 (0.198 / 0.204) | 0.196 | 0.179 (0.183 / 0.175) |
| 10h | M | 0.199 (0.196 / 0.202) | 0.196 | 0.180 (0.195 / 0.168) |

The classifier's probabilities run about 2 points high on held out, as predicted. They match the train base rate, not the calmer held-out one. At 10h on HO2 they run 3.4 points high.

## What it says

- **The rule is met, and the meaning is narrower than "new information."** The classifier beats volatility alone by a wide margin (+0.03 to +0.09). It beats the registry's own q95 by a modest one (+0.01 to +0.03), and ties Linear QR at 10h.
- **Its extra power comes from features the registry already has.** After the volatility pair, the weight is **vol_slope** (+0.03 to +0.09) and some **vratio**. sandwich and off_mark contribute nothing. Both registry models use vol_slope and vratio. So the classifier is not seeing anything the quantile models cannot see. It **combines the same inputs better for this specific yes/no question**. A model trained directly on "violent" beats a q95 trained for a different job and read off as a proxy.
- **vol_slope's weight falls with horizon and the volatility pair's rises.** Short-horizon violence is about volatility *picking up*. Long-horizon violence is about volatility *level*. Where volatility level dominates (10h), the registry's q95 has already captured it, and the classifier's edge disappears.
- **Implication for Step 2, as a report:** a flagged-subset quantile model would be fitted on the same features. Whatever it gains has to come from fitting them separately on the violent subset, not from new inputs.

**Step 2 was not started.** Open before it can run: (1) what makes an episode "flagged" (a probability cut-off or a top share); (2) what the deciles are deciles of. The "decile 10 is 1.84x too narrow" baseline the brief cites could not be found in this file or the logs, so it is not yet clear what Step 2 should reproduce.

## TAIL-REFINE — step 2, a Linear QR on flagged episodes: DOES NOT WORK, 0 of 10, 2026-10-12

`tail_classifier.py --stage refine`, log `logs/tail_refine_step2.log` (3,311s; the Linear QR solves on the flagged subsets are slow). No LP fallbacks. Registry caches fingerprint-matched. The logistic classifier reproduced TAIL-CLASSIFIER at every horizon (asserted).

**Design choices, made by the user before the build:**
- **Flag** = the top 20% of episodes by classifier score. The cut-off is the 80th percentile of TRAIN scores, per horizon.
- **Deciles** = predicted-magnitude deciles, the counted slice family in envelope.py: deciles of the registry Linear QR's predicted median over held-out rows. They are fixed by the registry, so both versions are sliced on identical rows.

**The subset model.** Linear QR with the registry's own features per direction, fitted on flagged TRAIN rows only and standardised on them. Only the q-axis is enforced: flags differ by horizon, so there is no common row set for the horizon pass. **Refined** = the subset model on flagged held-out rows and the registry Linear QR everywhere else.

**Rule, fixed before the run.** Per direction and horizon, decile 10 is FIXED if the refined |q95 coverage − 0.95| in decile 10 is smaller than the registry's, with the paired interval clearing zero, AND on the flagged rows neither the gap nor skill is significantly worse. A direction WORKS at 3 or more of 5 horizons.

## The flag

| h | M/A | flagged share: train / val / held out | flagged held-out rows | violent rate, flagged / unflagged (held out) |
|---|---|---|---|---|
| 0.5h | M | 0.200 / 0.167 / 0.203 | 3,662 | 0.364 / 0.134 |
| 1h | M | 0.200 / 0.170 / 0.205 | 3,705 | 0.364 / 0.128 |
| 2h | M | 0.200 / 0.177 / 0.208 | 3,755 | 0.353 / 0.126 |
| 5h | M | 0.200 / 0.189 / 0.215 | 3,881 | 0.352 / 0.131 |
| 10h | M | 0.200 / 0.191 / 0.212 | 3,837 | 0.365 / 0.130 |

The flag works as a sorter: flagged episodes are violent about 2.8 times as often as unflagged ones.

## On the flagged held-out rows — subset model vs registry Linear QR, paired

| h | dir | M/A | q95 cover reg → subset | gap pp reg → subset, diff [95% CI] | skill reg → subset, diff [95% CI] |
|---|---|---|---|---|---|
| 0.5h | MFE | M | 0.961 → 0.952 | 0.85 → 0.75, −0.093 [−0.544, +0.325] | +6.63 → +6.20, **−0.438** [−0.811, −0.096] |
| 0.5h | MAE | M | 0.955 → 0.958 | 1.39 → 2.22, **+0.825** [+0.031, +1.018] | +2.96 → +2.09, **−0.868** [−1.360, −0.406] |
| 1h | MFE | M | 0.961 → 0.950 | 1.00 → 0.80, −0.200 [−0.357, +0.307] | +7.29 → +6.99, −0.294 [−0.594, +0.010] |
| 1h | MAE | M | 0.958 → 0.959 | 1.56 → 2.40, +0.848 [−0.035, +1.035] | +1.84 → +1.16, **−0.678** [−1.077, −0.281] |
| 2h | MFE | M | 0.945 → 0.939 | 1.87 → 2.08, +0.213 [−0.141, +0.412] | +9.28 → +8.74, **−0.538** [−0.840, −0.242] |
| 2h | MAE | M | 0.957 → 0.959 | 1.44 → 2.76, **+1.321** [+0.532, +1.483] | +2.25 → +1.43, **−0.822** [−1.252, −0.385] |
| 5h | MFE | M | 0.944 → 0.942 | 2.22 → 2.14, −0.088 [−0.244, +0.054] | +9.03 → +8.94, −0.088 [−0.260, +0.114] |
| 5h | MAE | M | 0.955 → 0.959 | 1.55 → 2.30, **+0.747** [+0.297, +0.933] | +2.13 → +1.85, −0.288 [−0.686, +0.042] |
| 10h | MFE | M | 0.941 → 0.946 | 2.18 → 1.65, **−0.526** [−0.669, −0.203] | +9.00 → +9.03, +0.027 [−0.162, +0.206] |
| 10h | MAE | M | 0.950 → 0.953 | 1.08 → 2.23, **+1.145** [+0.045, +1.327] | +3.07 → +2.61, **−0.462** [−1.022, −0.044] |

## Decile 10 of predicted magnitude — the registry is not too narrow there

"x narrow" = the q95 miss rate ÷ its nominal 5%. 1.00x is exact, and above 1 is too narrow.

| h | dir | M/A | q95 cover reg / refined | x narrow reg | x narrow refined | refined − registry, \|cover − 0.95\| [95% CI] |
|---|---|---|---|---|---|---|
| 0.5h | MFE | M | 0.966 / 0.970 | 0.68x | 0.60x | +0.0039 [−0.0006, +0.0081] |
| 0.5h | MAE | M | 0.954 / 0.949 | 0.93x | 1.02x | −0.0026 [−0.0078, +0.0074] |
| 1h | MFE | M | 0.968 / 0.963 | 0.64x | 0.74x | −0.0050 [−0.0095, +0.0005] |
| 1h | MAE | M | 0.953 / 0.951 | 0.94x | 0.97x | −0.0017 [−0.0039, +0.0041] |
| 2h | MFE | M | 0.946 / 0.947 | 1.08x | 1.05x | −0.0017 [−0.0050, +0.0033] |
| 2h | MAE | M | 0.955 / 0.950 | 0.90x | 1.00x | −0.0050 [−0.0085, +0.0085] |
| 5h | MFE | M | 0.946 / 0.944 | 1.08x | 1.12x | +0.0017 [−0.0036, +0.0035] |
| 5h | MAE | M | 0.952 / 0.952 | 0.96x | 0.95x | +0.0006 [−0.0056, +0.0043] |
| 10h | MFE | M | 0.947 / 0.952 | 1.06x | 0.95x | −0.0007 [−0.0095, +0.0081] |
| 10h | MAE | M | 0.950 / 0.947 | 1.00x | 1.06x | +0.0029 [−0.0062, +0.0073] |

Every decile, and q75 coverage, are in the log.

**Verdict: DOES NOT WORK. Decile 10 fixed at 0 of 5 horizons in both directions.**

## What it says

- **On this measure there was nothing to fix.** The current registry's Linear QR covers its q95 correctly in the top predicted-magnitude decile: 0.64x to 1.08x of nominal at every horizon, in both directions, on 1,807 held-out rows each. The "1.84x too narrow" decile-10 problem the brief describes does not appear for this registry on the matched 53,757-episode set with the 1-minute target. It may come from an earlier population, the 30-minute target, a different model, or a different slicing, and its source couldn't be found.
- **The subset model is worse where it was fitted.** On the flagged rows, skill is significantly worse in 6 of 10 cells and never significantly better. MAE calibration is significantly worse at 4 of 5 horizons. The one improvement is MFE 10h calibration (−0.53pp), with skill unchanged. Fitting on 20% of the training rows costs more precision than the specialisation buys.
- **Together with step 1:** the classifier sorts episodes well (flagged episodes are violent 2.8 times as often). But its edge over the registry came from the same features. A quantile model refitted on its flagged subset cannot use that edge, and the registry already handles the top predicted decile.

**The tail problem, as briefed, stays open, with a corrected starting point.** On this registry and population, the top *predicted* decile is calibrated. If a tail failure remains, it lives somewhere this slicing does not look. Nothing in the registry was written.

---

# META-LABEL — skip / half-size flagged trades: STOPPED at Step 0, ledgers not found, 2026-10-12

Tag: **META-LABEL**. No script was written and nothing was run beyond file searches. Step 0's first check failed, and the brief says to stop there.

**The check.** Locate the three 6-month `run_portfolio_backtest.py` ledgers behind the 12,597 trades, totalling about 12,597.

| finding | M/A |
|---|---|
| where the 12,597 figure comes from | M, commit 9f79fd6 (2026-09-12): "12,597 backtested trades in three independent 6-month windows", 2025-06 → 2026-09 |
| those ledgers in git | M, **never committed**. No commit adds a 6-month ledger. |
| `research/portfolio_backtest_trades.csv`, the backtest's default output path | M, **35 trades, one day (2026-06-12)**. Every run overwrites this file. |
| whole-disk search for `w2d_*.csv` / `*stop10*.csv` | M, none on disk. The w2d ledgers exist in git only. They were added on 2026-09-27, after the 12,597 figure, and are 35-day stop-sweep runs. |
| every trade-level CSV in `research/` checked for row count and span | M, no file or set of three spans six months each from 2025-06 to 2026-09 or totals ~12,597 |

**Also relevant if the ledgers turn up:** they predate commit c287477 (2026-09-27), which found every `opened_at` stamped **one bar early** and the slot invariant printing "max concurrent open: 19 (cap 10)" without failing. Trades would need a +1-bar entry correction before matching to episodes, and the slot-contention measure would be unreliable.

**What exists instead (listed, not chosen):**

| file(s) | M/A | trades | span | in the clean window (≥ 2026-07-18)? |
|---|---|---|---|---|
| `exit_study/grid_run/grid_w2_s050.csv` (2-day window, 0.5σ stop) | M | 3,844 | 2026-08-17 → 2026-09-21 | entirely |
| `exit_study/lookback/lb*_seed*.csv`, `exit_study/rank/*.csv` | M | 415–3,613 each | 2026-08-17 → 2026-09-21 | entirely |
| `rank_experiment/*.csv` | M | up to 12,815 | 2024-09-24 → 2026-06-12 | **none**: all contaminated or validation |

None of these is the 12,597-trade baseline. Using one instead is a change of plan, and the call is the user's.

## META-LABEL Step 0 on `grid_w2_s050.csv` (user's Option 1): STOPPED, 78 clean matched trades, 2026-10-12

`meta_label.py`, log `logs/meta_label_step0.log`. Ledger: `research/exit_study/grid_run/grid_w2_s050.csv`, 3,844 trades, 2026-08-17 → 2026-09-21. Stamps: 2-day window, ratio hedge, entry 3σ, stop 0.5σ, 10 slots, 1-minute exit checks, stop fill 1.005x, 72h cooldown, ranked by theta, 20x.

| check | M/A |
|---|---|
| A. generated after the one-bar entry fix (c287477) | M, **yes**. Max concurrent open 10 (cap 10), no pair open twice at once, min hours_held 0.00 (the bug floored it at 0.50). Written 19:52 against the fix's 19:50 commit, and it carries the cfg_* stamps that fix introduced. |
| B. engine applied liquidation | **no** (from code history). It entered in 440d658, after this ledger. That commit says these ledgers predate it and booked stops at 1.005x, not the measured 1.04x. Any measured damage is a floor. |
| C. trades on a pair with no episode in disloc_meta | M, **3,361 of 3,844**. The episode set samples 3,000 pairs, at most 20 episodes each. |
| C. matched to the exact decision bar (episode label = opened_at − 30 min) | M, **78 of 3,844 = 2.0%**. Within 1 / 2 / 4 / 48 / 336 bars of it: 87 / 97 / 117 / 203 / 353. |
| D. clean / validation / contaminated, matched | M, 78 / 0 / 0. All 3,844 trades are in the clean window. |
| E. 30-minute bars with all 10 slots full | M, **1,453 of 1,680 = 86.5%**; median slots open 10 |
| E. candidates turned away for full slots or one-per-ticker | **not measurable**: the ledger records taken trades only |
| F. classifier AUC, train vs held out: 0.5h / 1h / 2h / 5h / 10h | M, 0.7383 vs 0.7150 / 0.7290 vs 0.7125 / 0.7124 vs 0.7086 / 0.6992 vs 0.7063 / 0.6963 vs 0.7144. At most 0.023 higher on train, and lower on train from 5h. |
| median hold in this ledger → nearest horizon | M, 0.50h → 0.5h |

**Verdict: STOP.** There are 78 clean matched trades, and the brief requires 500. Step 1 was not run. The flag-share comparison needs scored trades, so it was not computed either.

**Why, and what it implies:**
- The cause is the episode set's design, not the ledger. disloc_meta samples pairs, so 87% of trades are on pairs it never saw.
- Scoring every trade would mean computing the six classifier features at each trade's own entry bar from the price panel and 1-minute data, instead of borrowing a sampled episode's. That is a new build, not done here.
- Slot contention is heavy (all slots full 86.5% of the time). Under the brief's rule, even a positive result here would only earn a full backtest run with the rule wired in.
- The classifier barely overfits (≤0.023 AUC), so that is not a concern for a later run.
- This ledger's window (17 Aug – 21 Sep) is the previously identified favourable window ("The edge was the window"). Any result on it would carry that caveat.

## META-LABEL Step 0b + Step 1 — features at every trade's entry bar; skip and half-size: VOID (corrected 2026-10-12, was "shelved")

`meta_label.py --stage step1`, log `logs/meta_label_step1.log` (45s). Ledger `grid_w2_s050.csv`, 3,844 trades, all in the clean window.

**Stated before any number:**
- All 10 slots are full 86.5% of the time, so this can rule the rule OUT, never IN.
- Stops are booked at 1.005x, so the stop-overshoot leak is not in this ledger.
- The engine that wrote it applies no liquidation.
- 17 Aug–21 Sep is the previously identified favourable window.

**Step 0b, the entry-bar feature function.** No new feature logic. Geometry is built exactly as mkdisloc builds an episode: rolling_spread_stats on the pair's joint finite panel region, read at the entry bar, giving a 336-bar sigma-unit window stored as float32. Then `envfeat.build` computes the five window features and `vol1m.trailing_features` computes vol_48_1m. `envfeat.build` gained optional `W` and `M` arguments so it can take these inputs; its logic is unchanged. The entry bar's label is opened_at − 30 min.

| check | M/A |
|---|---|
| envfeat max index touched past the entry bar | M, 0 (asserted) |
| 1-minute reads, last minute relative to the entry label | M, +29: the entry bar's close |
| 1m path vs the 30m window at the marks | M, 0.062 of the float32 budget |
| **reproduction on the 78 trades matched to an episode's exact decision bar** | M, five envfeat features **0.000e+00** (float32); vol_48_1m **0.000e+00** |
| complete feature rows | M, **3,844 of 3,844**; none missing |

## The flag

The 0.5h classifier (median hold 0.50h) reproduces AUC 0.7150. Cut-off = 80th percentile of its TRAIN scores (TAIL-REFINE), never tuned on trades.

| number | M/A |
|---|---|
| share flagged: **trades** | M, **0.857** (3,293 of 3,844) |
| share flagged: episodes, train / validation / held out | M, 0.200 / **0.167** / 0.203 |
| flagged trades: mean R / total R / win rate | M, +0.445 / +1,464.0 / 0.197 |
| unflagged trades: mean R / total R / win rate | M, +0.314 / +173.0 / 0.194 |
| exit mix, flagged / unflagged: adverse move, take profit | M, 0.80 / 0.81, 0.20 / 0.19 |

## Step 1 — the arms against taking every trade

Paired differences against ALL. Day-clustered 95% intervals (trade entry day, 1,000 resamples).

| measure | M/A | ALL | SKIP | HALF | SKIP − ALL [95% CI] | HALF − ALL [95% CI] |
|---|---|---|---|---|---|---|
| mean R per trade | M | +0.4259 | +0.3140 | +0.2354 | −0.1119 [−0.3779, +0.1323] | **−0.1904** [−0.2756, −0.1010] |
| total R | M | +1,637.0 | +173.0 | +905.0 | **−1,464.0** [−2,072.0, −800.7] | **−732.0** [−1,036.0, −400.4] |
| trades | M | 3,844 | 551 | 3,844 | −3,293 | 0 |
| win rate | M | 0.197 | 0.194 | 0.197 | −0.003 [−0.037, +0.028] | 0.000 |

The median overshoot ratio is not reported: every stop in this ledger is booked at exactly 1.005x, so it carries no information.

## Random null — the same 3,293 trades chosen at random, 1,000 draws

| arm | measure | M/A | real | null p5 / median / p95 | real's percentile |
|---|---|---|---|---|---|
| SKIP | mean R | M | +0.3140 | +0.2025 / +0.4275 / +0.6507 | 19.3th |
| SKIP | total R | M | +173.0 | +111.6 / +235.5 / +358.5 | 19.3th |
| HALF | mean R | M | +0.2354 | +0.2274 / +0.2436 / +0.2596 | 19.3th |
| HALF | total R | M | +905.0 | +874.3 / +936.3 / +997.8 | 19.3th |

**Verdict, as first recorded: SKIP and HALF both fail to beat the random null on total R ("shelved").**

**CORRECTED to VOID (user review, 2026-10-12). The test could not answer its question, so the idea is not shelved:**
- **Two-sided target.** "Violent" means an outsized move EITHER way, so the flag marks likely winners as well as likely losers.
- **86% flag rate.** A cut-off that flags 86% of trades cannot test a skip rule.
- **Hard-coded fills.** The ledger books every stop at 1.005x, so the stop-overshoot cost the rule was meant to avoid is not in the data.

The numbers below stand as measured. The conclusion is withdrawn. Superseded by META-LABEL v2.

## What it says

- **The flag doesn't separate trades; it flags almost all of them.** 86% of trades score above the cut-off that flags 17% of validation episodes. The system's ranking already selects the most volatile dislocations, which are what the classifier calls violent. So "skip the flagged" means "skip most of the book".
- **Flagged trades do better, not worse.** Mean R is +0.45 flagged against +0.31 unflagged, and win rates are equal. Both arms do worse than a random skip of the same size: the real result sits at the 19th percentile of the null.
- **The result fits the rest of the project:** volatility predicts how far a spread travels, not which way. A trade that will travel far is as likely to reach mu as to hit its stop, and the take-profit wins carry the mean.
- **Caveats, as stated before the run:** a favourable window, 1.005x stop fills and no liquidation all make this ledger kinder than reality. None of them would turn a rule that loses to random skipping into one that wins.

---

# META-LABEL v2 — a one-sided envelope flag on replayed stop fills: STOPPED at gate 3, 2026-10-12

Tag: **META-LABEL** (v2). `meta_label_v2.py`, log `logs/meta_label_v2.log`. The rule, flags and every gap-fill are fixed in the docstring. The run stopped at gate 3, as the brief requires. Gates 1 and 2 passed.

| gate | M/A |
|---|---|
| 1. Linear QR refit, train only, five horizons, vs cached held-out predictions: MFE / MAE | M, max diff **0.00e+00** / **0.00e+00** |
| 2. trades with complete features at their own entry bar | M, **3,844 of 3,844** |
| 2. entry geometry recomputed vs the ledger's own: beta / sigma | M, max diff 3.81e-08 / max relative diff 5.19e-09 |
| 3. exit reason, replay vs ledger | M, 3,844 of 3,844 agree |
| 3. take-profit / time-stop trades reproducing exit time and R to 1e-9 | M, **756 of 757** |
| 3. stop-outs reproducing exit time, and the ledger R when booked at 1.005x through pnl() | M, **3,085 of 3,087** |

**The three misses, fully explained.** Trades 3810 (O/TRX), 3843 (UB/WLD) and 3851 (DATA/JUP) all exit in the run's last half hour.

| trade | M/A | opened | ledger close | replay exit |
|---|---|---|---|---|
| 3810 | M | 09-20 14:30 | 09-21 00:30 | 09-21 00:22 |
| 3843 | M | 09-20 19:00 | 09-21 00:30 | 09-21 00:23 |
| 3851 | M | 09-21 00:00 | 09-21 00:30 | 09-21 00:04 |

The engine loaded 1-minute prices only up to the window end (cfg_end_date 2026-09-21 00:00), so after that it could check exits only at the final 30-minute close (00:30). That is where the ledger closes all three. The replay sees the real 1-minute path and exits earlier. **This is a boundary artifact of the run, not a replay error.** Every other trade reproduces exactly.

**Not run past the gate:** the replayed overshoot distribution, the no-stop arm, the flags and the scoreboard. The fix and the decision are in the session report.

## META-LABEL v2 — completed run on ONCE-A-MINUTE stop fills: DOES NOT SURVIVE (not the live fill), 2026-10-12

`meta_label_v2.py`, log `logs/meta_label_v2.log`. Gates 1–3 all pass, after the engine data cut-off was added to the gate replay only (user-approved): **3,844 of 3,844 trades reproduce the ledger's exit reason, exit time and R exactly.** The analysis replay uses the true 1-minute path. Only trades 3810, 3843 and 3851 change: R −1.517→−1.271, +6.743→+6.522, −3.470→−1.522.

**READ THIS FIRST. These fills are not live fills.** The replay fills each stop at the first 1-minute close past it. Paper trading with the tick-watching stop monitor (`research/from_vm/scanner_trades.csv`, 13–29 Sep) measures stop fills of:

| stop fill | M/A | median | mean | p90 | max |
|---|---|---|---|---|---|
| live paper trading, 316 stop-outs | M | **1.015x** | 1.031x | 1.074x | 1.43x |
| this replay, 3,087 stop-outs | M | 1.237x | 1.458x | 1.944x | — |
| the ledger, as booked | M | 1.005x (setting) | | | |

So **v2's premise, that the ledger's 1.005x hid a large overshoot leak, does not hold for the live system.** The once-a-minute replay overstates stop cost roughly tenfold. Everything below describes a stop checked once a minute, not the live book. A re-run on measured fills is pending the user's choice of fill rule.

| number | M/A |
|---|---|
| mean R / total R / total $: ledger at 1.005x | M, +0.4259 / +1,637.0 / — |
| mean R / total R / total $: once-a-minute replay | M, **+0.0617** / +237.3 / **−$1,138** |
| overshoot cost, once-a-minute fills vs exact stop fills | M, 1,415.0 R in total |
| no-stop arm: take profit / liquidated at 20x / time stop | M, 2,734 (71.1%) / 834 (21.7%) / 276 (7.2%) |
| no-stop arm: mean R / total R / total $ | M, +0.4662 / +1,792.1 / +$3,727 |
| trades entered beyond 3.5σ | M, 1,178 (31%) |

**Flags** (top 20% of the 3,844 trades by prediction, 769 each). Predicted MFE q50 was never ≤ 0, so the +inf rule never applied. A and B overlap little: 30 trades at 0.5h, up to 207 at 10h. Flag A cut-offs, MAE q95 in σ: 4.39 / 6.10 / 8.09 / 11.63 / 15.11. Flag B cut-offs, MAE q50 ÷ MFE q50: 0.850 / 0.882 / 0.927 / 0.987 / 0.999.

### Scoreboard, all trades, once-a-minute fills — arm minus take-everything

Day-clustered 95% intervals. "pct" = the real arm's percentile in the random null (1,000 draws).

| cell | M/A | Δ mean R [CI] | Δ total R [CI] | Δ $ [CI] | pct R | pct $ |
|---|---|---|---|---|---|---|
| A 0.5h SKIP | M | +0.0003 [−0.0693, +0.0685] | −46.6 [−326.2, +218.8] | +477 [−106, +1,163] | 50.6 | 96.4 |
| A 0.5h HALF | M | −0.0061 [−0.0444, +0.0276] | −23.3 [−163.1, +109.4] | +238 [−53, +581] | 50.6 | 96.4 |
| B 0.5h SKIP | M | −0.0145 [−0.0724, +0.0386] | −91.9 [−288.2, +111.4] | +79 [−337, +464] | 29.6 | 15.2 |
| B 0.5h HALF | M | −0.0120 [−0.0395, +0.0136] | −46.0 [−144.1, +55.7] | +40 [−168, +232] | 29.6 | 15.2 |
| A 1h SKIP | M | −0.0011 [−0.0693, +0.0672] | −50.8 [−324.4, +208.1] | +485 [−100, +1,155] | 48.1 | 96.8 |
| A 1h HALF | M | −0.0066 [−0.0435, +0.0266] | −25.4 [−162.2, +104.1] | +242 [−50, +578] | 48.1 | 96.8 |
| B 1h SKIP | M | −0.0238 [−0.0986, +0.0428] | −120.7 [−398.5, +136.2] | +130 [−397, +609] | 22.5 | 27.7 |
| B 1h HALF | M | −0.0157 [−0.0525, +0.0171] | −60.4 [−199.2, +68.1] | +65 [−198, +304] | 22.5 | 27.7 |
| A 2h SKIP | M | +0.0202 [−0.0550, +0.0845] | +14.5 [−259.9, +271.4] | +523 [−89, +1,231] | 76.3 | 97.6 |
| A 2h HALF | M | +0.0019 [−0.0345, +0.0346] | +7.3 [−129.9, +135.7] | +262 [−45, +615] | 76.3 | 97.6 |
| B 2h SKIP | M | −0.0197 [−0.0877, +0.0396] | −107.9 [−364.8, +144.4] | +21 [−441, +432] | 23.9 | 7.9 |
| B 2h HALF | M | −0.0140 [−0.0484, +0.0182] | −54.0 [−182.4, +72.2] | +10 [−221, +216] | 23.9 | 7.9 |
| A 5h SKIP | M | +0.0056 [−0.0794, +0.0855] | −30.2 [−349.4, +267.0] | +493 [−137, +1,206] | 57.3 | 96.0 |
| A 5h HALF | M | −0.0039 [−0.0460, +0.0337] | −15.1 [−174.7, +133.5] | +246 [−68, +603] | 57.3 | 96.0 |
| B 5h SKIP | M | −0.0319 [−0.0902, +0.0237] | −145.6 [−375.7, +102.2] | +163 [−330, +733] | 12.8 | 31.7 |
| B 5h HALF | M | −0.0189 [−0.0510, +0.0129] | −72.8 [−187.8, +51.1] | +82 [−165, +367] | 12.8 | 31.7 |
| A 10h SKIP | M | −0.0060 [−0.0891, +0.0702] | −66.0 [−382.4, +260.4] | +370 [−214, +1,011] | 40.0 | 83.0 |
| A 10h HALF | M | −0.0086 [−0.0510, +0.0317] | −33.0 [−191.2, +130.2] | +185 [−107, +506] | 40.0 | 83.0 |
| B 10h SKIP | M | −0.0390 [−0.1070, +0.0178] | −167.3 [−414.1, +86.0] | +137 [−278, +612] | 7.8 | 24.9 |
| B 10h HALF | M | −0.0218 [−0.0557, +0.0107] | −83.6 [−207.1, +43.0] | +69 [−139, +306] | 7.8 | 24.9 |

**Reading rule: 0 of 20 cells beat the null's 95th percentile on both total R and $. No cell is significantly worse on dollars. DOES NOT SURVIVE.** Flag A sits at the 96–98th percentile on dollars at 0.5h–5h but at the 48–76th on R. The dollar effect is not an R effect. It most likely comes from the fivefold growth in position size, so which trades the flag drops matters more in dollars late in the window. That reading was not tested.

### Where the loss lives (once-a-minute fills)

Premium = with-stop R minus no-stop R, mean per trade. Negative means the stop costs money.

| flag | M/A | share of trades | share of overshoot cost | premium, flagged | premium, unflagged |
|---|---|---|---|---|---|
| A 0.5h | M | 0.200 | 0.257 | −0.620 | −0.351 |
| A 1h | M | 0.200 | 0.253 | −0.524 | −0.375 |
| A 2h | M | 0.200 | 0.260 | −0.594 | −0.357 |
| A 5h | M | 0.200 | 0.257 | −1.148 | −0.219 |
| A 10h | M | 0.200 | 0.255 | −0.847 | −0.294 |
| B 0.5h | M | 0.200 | 0.146 | **+0.164** | −0.547 |
| B 1h | M | 0.200 | 0.151 | **+0.196** | −0.555 |
| B 2h | M | 0.200 | 0.155 | +0.018 | −0.510 |
| B 5h | M | 0.200 | 0.156 | +0.028 | −0.513 |
| B 10h | M | 0.200 | 0.155 | +0.040 | −0.516 |

All trades: premium −0.405. With once-a-minute fills, the stop costs 0.40R per trade against holding to take profit, time stop or liquidation. Flag A trades carry about 26% of the overshoot cost on 20% of trades. Flag B is the only group the stop helps on average. Both statements hold only under once-a-minute fills.

**Beyond 3.5σ (1,178 trades), reported, not gated:** 0 of 20 cells beat the null on both measures. Flag A's share there is 29–33%, flag B's 12–14%. Full table in the log.

**SPA / StepM:** not produced. arch 8.0.0's StepM raises when its step-down loop removes every arm, because the loop tests the last step's count rather than the running total. Handled in the code (at that size every arm counts as superior). It will run with the re-run.

**SPA / StepM, once-a-minute fills** (the completed re-run, 36 days of daily P&L), beside the rule:

| measure | M/A | SPA lower / consistent / upper | StepM smallest adjusted p |
|---|---|---|---|
| total R | M | 0.567 / 0.784 / 0.784 | 0.785 (A 2h SKIP) |
| dollars | M | 0.106 / 0.106 / 0.106 | 0.110 (A 2h SKIP) |

---

## META-LABEL v2 — LIVE FILLS (user's Option 2): DOES NOT SURVIVE on 0 of 200 seeds; skipping costs R in every cell, 2026-10-13

`meta_label_v2.py --stage fills`, log `logs/meta_label_v2_fills.log` (2,286s). Per-trade state comes from the `--stage main` run (gates 1–3 passed, all 3,844 trades reproduce the ledger exactly), saved to `research/datasets/meta_label_v2_state.npz`.

**Method.**
- Each replayed stop keeps its replayed TIME. Its FILL is drawn with replacement from the 316 stop-outs measured in paper trading with the tick-watching monitor (`research/from_vm/scanner_trades.csv`, adverse_move, no blind gap).
- 200 seeds. Every number below is the median [min, max] over seeds.
- Stop R and $ are linear in the fill ratio, so both are evaluated exactly through the engine's `pnl()`.
- Added column: **$ at constant size**, every trade rescaled to the median gross notional (exact, because pnl is linear in size).
- The scoreboard runs on daily sums with bootstrap day counts, which is arithmetically identical to resampling trades by day.

**Note, as required:** random fill assignment removes any link between a trade's violence and its fill quality. If violent trades really fill worse, this understates what skipping them saves.

| number | M/A |
|---|---|
| measured live fills (316): median / mean / p90 / max | M, 1.0148x / 1.0308x / 1.0735x / 1.4318x |
| drawn fills per seed: median / mean / p90 | M, 1.015 [1.014, 1.015] / 1.031 [1.028, 1.033] / 1.077 [1.068, 1.079] |
| **take everything: mean R** | M, **+0.4051** [+0.4034, +0.4071] |
| take everything: total R | M, +1,557 [+1,551, +1,565] |
| take everything: total $ | M, +$705 [+$687, +$718] |
| take everything: $ at constant size (median gross notional) | M, +$447 [+$439, +$454] |

### Reading rule (unchanged, judged per seed)

| number | M/A |
|---|---|
| cells beating the null's 95th pct on BOTH total R and $, per seed | M, **0 [0, 0]** (about 1 expected by chance) |
| cells significantly worse on dollars, per seed | M, 0 [0, 0] |
| **seeds on which the rule SURVIVES** | M, **0 of 200** |

### The 20 cells — arm minus take-everything, median over 200 seeds

Ranges across seeds are narrow, within about ±2% of the median; full ranges are in the log. "pct" = the real arm's percentile in the random null.

| cell | M/A | Δ mean R | Δ total R [median 95% CI] | Δ $ [median 95% CI] | Δ $ const [median 95% CI] | pct R | pct $ | pct $const |
|---|---|---|---|---|---|---|---|---|
| A 0.5h SKIP | M | −0.026 | **−390.7** [−643.7, −158.6] | −138 [−678, +332] | −77 [−324, +148] | 14.4 | 50.4 | 56.4 |
| A 0.5h HALF | M | −0.051 | **−195.4** [−321.8, −79.3] | −69 [−339, +166] | −39 [−162, +74] | 14.4 | 50.4 | 56.4 |
| B 0.5h SKIP | M | +0.010 | **−279.8** [−470.7, −92.1] | −200 [−576, +113] | −120 [−354, +79] | 64.2 | 30.4 | 32.7 |
| B 0.5h HALF | M | −0.036 | **−139.9** [−235.3, −46.0] | −100 [−288, +56] | −60 [−177, +39] | 64.2 | 30.4 | 32.7 |
| A 1h SKIP | M | −0.026 | **−390.2** [−641.1, −159.4] | −122 [−658, +338] | −72 [−310, +146] | 16.5 | 53.4 | 57.4 |
| A 1h HALF | M | −0.051 | **−195.1** [−320.5, −79.7] | −61 [−329, +169] | −36 [−155, +73] | 16.5 | 53.4 | 57.4 |
| B 1h SKIP | M | −0.001 | **−315.2** [−577.1, −76.5] | −166 [−626, +228] | −115 [−381, +125] | 49.4 | 45.2 | 36.8 |
| B 1h HALF | M | −0.041 | **−157.6** [−288.5, −38.3] | −83 [−313, +114] | −58 [−191, +62] | 49.4 | 45.2 | 36.8 |
| A 2h SKIP | M | −0.007 | **−334.4** [−597.5, −105.9] | −99 [−651, +373] | −25 [−265, +193] | 38.5 | 64.9 | 81.9 |
| A 2h HALF | M | −0.044 | **−167.2** [−298.7, −52.9] | −50 [−325, +187] | −12 [−132, +96] | 38.5 | 64.9 | 81.9 |
| B 2h SKIP | M | +0.001 | **−308.8** [−558.8, −74.7] | −282 [−705, +79] | −143 [−398, +88] | 50.3 | 13.5 | 21.0 |
| B 2h HALF | M | −0.040 | **−154.4** [−279.4, −37.3] | −141 [−352, +40] | −72 [−199, +44] | 50.3 | 13.5 | 21.0 |
| A 5h SKIP | M | −0.021 | **−375.5** [−654.3, −132.0] | −78 [−675, +410] | −3 [−241, +220] | 23.3 | 66.7 | 87.5 |
| A 5h HALF | M | −0.049 | **−187.8** [−327.2, −66.0] | −39 [−338, +205] | −1 [−120, +110] | 23.3 | 66.7 | 87.5 |
| B 5h SKIP | M | −0.012 | **−347.3** [−565.2, −126.0] | −128 [−549, +277] | −132 [−367, +101] | 31.1 | 52.0 | 27.7 |
| B 5h HALF | M | −0.045 | **−173.7** [−282.6, −63.0] | −64 [−275, +138] | −66 [−184, +50] | 31.1 | 52.0 | 27.7 |
| A 10h SKIP | M | −0.031 | **−408.1** [−653.5, −158.2] | −173 [−708, +204] | −18 [−243, +192] | 13.4 | 41.8 | 80.9 |
| A 10h HALF | M | −0.053 | **−204.1** [−326.7, −79.1] | −87 [−354, +102] | −9 [−121, +96] | 13.4 | 41.8 | 80.9 |
| B 10h SKIP | M | −0.018 | **−368.4** [−618.1, −128.0] | −130 [−501, +228] | −111 [−334, +110] | 21.4 | 50.6 | 36.7 |
| B 10h HALF | M | −0.048 | **−184.2** [−309.1, −64.0] | −65 [−251, +114] | −55 [−167, +50] | 21.4 | 50.6 | 36.7 |

**All 20 arms lose total R significantly:** every median interval on Δ total R sits entirely below zero, and every point estimate is negative on every seed. No arm is significantly worse on dollars or constant-size dollars, but none is better either; every dollar interval straddles zero.

### Where the loss lives (live fills), median over seeds

| flag | M/A | share of trades | share of overshoot cost | stopping premium, flagged | stopping premium, unflagged |
|---|---|---|---|---|---|
| A 0.5h | M | 0.200 | 0.202 | −0.172 | −0.033 |
| A 1h | M | 0.200 | 0.202 | −0.083 | −0.056 |
| A 2h | M | 0.200 | 0.203 | −0.141 | −0.041 |
| A 5h | M | 0.200 | 0.200 | −0.698 | +0.098 |
| A 10h | M | 0.200 | 0.199 | −0.402 | +0.024 |
| B 0.5h | M | 0.200 | 0.200 | **+0.408** | −0.178 |
| B 1h | M | 0.200 | 0.199 | **+0.449** | −0.189 |
| B 2h | M | 0.200 | 0.199 | +0.279 | −0.146 |
| B 5h | M | 0.200 | 0.198 | +0.290 | −0.149 |
| B 10h | M | 0.200 | 0.198 | +0.302 | −0.152 |

With live fills, overshoot cost is spread in proportion to trades (about 20% per 20% flag), as random fills guarantee.

### Beyond 3.5σ (1,178 trades), reported not gated

0 [0, 0] cells beat the null on both measures on any seed. Every arm loses total R. Full table in the log.

### Multiple-testing checks, beside the rule — median [min, max] over 200 seeds

| measure | M/A | SPA lower | SPA consistent | SPA upper | StepM smallest adjusted p |
|---|---|---|---|---|---|
| total R | M | 0.723 [0.718, 0.728] | 0.723 [0.718, 0.728] | 1.000 | 0.725 [0.720, 0.730] |
| dollars | M | 0.757 [0.748, 0.764] | 0.942 [0.937, 0.945] | 0.942 | 0.945 [0.940, 0.945] |

Settings: daily P&L, days resampled independently (block size 1), 10,000 reps, studentized, seed 20261012. The StepM empty-set bug in arch 8.0.0 is handled; see the docstring. **No arm beats take-everything under any test.**

## What it says

- **With live-measured fills, skipping or half-sizing trades that the envelope expects to go against us loses R, every time.** All 20 arms give up 140–410 R of the book's 1,557. Each sits below the median of a random skip of the same size on R for flag A (13–39th percentile) and around it for flag B. Both multiple-testing checks agree: SPA p 0.72 on R and 0.94 on dollars.
- **Why:** with the stop filling close to its level, the high-adverse trades are not the losers. Flag B trades have the MOST to gain from the stop, a stopping premium of +0.28 to +0.45R, because the stop cuts their adverse paths cheaply. Their trips to mu still pay. Skipping them throws away winners along with their cheap losses.
- **v1 and v2 agree, for different reasons:** a volatility-based or envelope-based entry filter does not improve this book. It is ruled out under the brief's own caveats: slots are full 86.5% of the time and this is the favourable window. The unmodelled link between violence and fill quality would have to be large to reverse a loss this consistent.
- **Once-a-minute fills gave the opposite picture:** +0.06R per trade and dollar effects near significance for flag A (SPA p 0.11). That was an artifact of fills about 1.46x on average against the measured 1.03x.

Nothing in the registry or the live system was touched.

---

# WHY-IT-MOVED — a feature family for why the spread dislocated: screen B NO PASS, screen A ADOPT FOR MFE, 2026-10-13

Tag: **WHY-IT-MOVED**. Build: `whyfeat.py`, log `logs/whyfeat.log`, output `research/datasets/whyfeat.npz` (60,000 × 20). Screens: `whyscreen.py`, log `logs/whyscreen.log`. The first, untransformed screen B is kept as `logs/whyscreen_B.log`. Every gap-fill and rule is in the two docstrings, fixed before the runs. Nothing is read past the entry bar (audited per row).

## Step 1 — the market factor

A trailing correlation PCA at every bar over the previous 336 bars, first 3 components, Avellaneda–Lee eigenportfolio returns. Loadings are OLS betas over the same window.

| number | M/A |
|---|---|
| bars fitted / eligible tickers per bar | M, 36,258; median 149 [93, 214] |
| variance explained, all bars: PC1 / PC2 / PC3 (median) | M, 0.603 [p5 0.316, p95 0.771] / 0.019 / 0.014 |
| PC1 variance explained by quarter | M, 0.646 (24Q3), 0.675, 0.718, 0.686, 0.660, 0.604, 0.513, 0.437, **0.334 (26Q3)**, 0.457 (26Q4) |
| corr(PC1 return, BTC return), all bars | M, **0.741**; by quarter 0.67–0.86 |

The market factor's grip weakens through 2026: PC1 falls from about 0.65–0.72 of the variance to 0.33 by 2026Q3, as the universe grows from 93 to 214 tickers. Its correlation with BTC stays high throughout.

## Step 2 — the features (60,000 episodes; _1m on the 53,757)

Seven features at lookbacks of 4 and 12 bars: lone_share, common_share, mkt_move, vol_spike_mover, vol_spike_ratio, vadj_resid, lagger_spread (EDGE, the authors' `bidask` 2.1.0). Plus vol_spike_mover_1m, vol_spike_ratio_1m and vadj_resid_1m at 4 and 12 one-minute bars.

| check | M/A |
|---|---|
| look-ahead: max 30m index touched − entry index, every family | M, **+0** (must be ≤ 0) |
| look-ahead: 1-minute families, last minute read | M, **+29** (the entry bar's close) |
| coverage, 30m features | M, 59,707–59,952 of 60,000. Missing = a leg not in the factor fit (listing edge): 48–293 |
| coverage, _1m features | M, 52,742–53,603 of 53,757. Missing = 1m volume missing or zero median: 1–934; dominant leg undefined: 81–153 |
| any feature with Spearman > 0.8 against vol_48 or vol_48_1m | M, **none**. The largest is 0.26 (vadj_resid_4 vs vol_48_1m) |
| dominant leg is leg A, lookback 4 / 12 | M, 0.462 / 0.477 |
| dominant leg's contribution pushed the spread toward the dislocation, 4 / 12 | M, 0.937 / 0.944 |

Medians [p5, p95] for every feature are in the log. The volume features are heavily skewed: vol_spike_mover_1m_4 has a median of 6.9 and a p95 of 202.

**Transforms, fixed at the user's instruction before the final screens, not tuned:**
- log() on vol_spike_mover, vol_spike_ratio and lagger_spread, and their _1m versions. Values ≤ 0 become missing: 1–383 per column.
- sign(x)·log(1+|x|) on vadj_resid and vadj_resid_1m.

Then any missing value is filled with the TRAIN median. Every column is finite on at least 97% of the 53,757, above the 95% floor fixed before the run.

## Screen B — the best point toward mu within 10h (53,757 episodes)

**Base distributions, before any model.** Minutes 1–600 after the entry bar's close, on the frozen geometry. Depth = the 10h MFE (asserted equal).

| group | M/A | timing median (p25, p75), min | best point comes FIRST | reaches mu | depth median, σ |
|---|---|---|---|---|---|
| all 53,757 | M | 287 (81, 498) | 0.440 | 0.231 | 1.94 |
| train | M | 275 (71, 495) | 0.454 | 0.224 | 1.86 |
| held out | M | 305 (93, 502) | 0.416 | 0.244 | 2.04 |
| HO1 | M | 295 (83, 503) | 0.436 | 0.243 | 1.97 |
| HO2 | M | 311 (100, 502) | 0.399 | 0.245 | 2.10 |

| timing, share by hour | M/A | 0–1h | 1–2h | 2–3h | 3–4h | 4–5h | 5–6h | 6–7h | 7–8h | 8–9h | 9–10h |
|---|---|---|---|---|---|---|---|---|---|---|---|
| real | M | 0.214 | 0.090 | 0.074 | 0.069 | 0.066 | 0.065 | 0.071 | 0.076 | 0.091 | 0.184 |
| arcsine law (driftless walk, theory) | M | 0.205 | 0.090 | 0.074 | 0.067 | 0.064 | 0.064 | 0.067 | 0.074 | 0.090 | 0.205 |
| sign-flipped paths (20 seeds) | M | 0.251 | 0.095 | 0.073 | 0.064 | 0.060 | 0.060 | 0.062 | 0.068 | 0.083 | 0.184 |

**Note, as instructed: the timing histogram matches the arcsine law for a driftless walk.** The U shape is what a random walk produces, not structure.

**The sign-flip null.** Each 1-minute increment's sign is randomised (bridging missing minutes), 20 seeds. Median [min, max] over seeds.

| group | M/A | timing median: real / flipped | best FIRST: real / flipped | depth median: real / flipped | reaches mu: real / flipped |
|---|---|---|---|---|---|
| all | M | 287 / 256 [251, 261] | **0.440 / 0.500** [0.495, 0.505] | **1.935 / 2.068** [2.046, 2.092] | **0.231 / 0.298** [0.296, 0.301] |
| held out | M | 305 / 255 [246, 265] | 0.416 / 0.498 | 2.044 / 2.025 | 0.244 / 0.289 |
| HO1 | M | 295 / 259 | 0.436 / 0.498 | 1.967 / 2.078 | 0.243 / 0.298 |
| HO2 | M | 311 / 251 | 0.399 / 0.499 | 2.096 / 1.987 | 0.245 / 0.282 |

**The real spread does worse toward mu than the same steps with random signs.** It goes against the trade first more often (44% best-first against 50%) and reaches mu less often (23% against 30%). It even has FEWER early best points than the null (21.4% against 25.1%). After a dislocation the path drifts AWAY from mu, consistent with "the spread never reverts". The near-arcsine shape is a coincidence of offsetting effects: steps are larger just after entry, which pushes the null's first hour up to 0.251, and the real path's adverse drift pulls it back down.

**Real minus flipped, by decile of each new feature** (all 400 cells in the log, day-clustered intervals):
- Depth is short by 0.2–0.6σ in **every** decile of **every** feature, and the best point comes first 3–9 points less often in every decile. The adverse drift is universal, not confined to a group.
- One consistent gradient, read rather than tested: the bigger the volume spike on the leg that moved, the larger the order deficit. vol_spike_ratio_1m_12 goes from −0.040 (decile 1) to −0.093 (decile 10), and vol_spike_ratio_4 from −0.043 to −0.087.

**Models** (six = vol_48, vol_48_1m, vratio, vol_slope, sandwich, off_mark; +20 = the new set). Paired, day-clustered.

| target | half | M/A | skill six | skill six+new | diff [95% CI] |
|---|---|---|---|---|---|
| timing (Linear QR, q25/50/75) | held out | M | +0.059% | −0.014% | −0.073 [−0.347, +0.178] |
| timing | HO1 | M | +0.040% | +0.088% | +0.048 [−0.330, +0.488] |
| timing | HO2 | M | +0.074% | −0.101% | −0.176 [−0.448, +0.157] |
| order (logistic, log-loss skill) | held out | M | −0.063% | −0.068% | −0.005 [−0.590, +0.473]; AUC 0.514 → 0.517 |
| order | HO1 | M | −0.062% | +0.234% | +0.296 [−0.085, +0.736]; AUC 0.505 → 0.531 |
| order | HO2 | M | −0.063% | −0.321% | −0.258 [−1.033, +0.583]; AUC 0.523 → 0.508 |

**Screen B: NO PASS.** No interval clears zero in both halves. Timing has essentially no skill even on the six (+0.06%). Order is a coin flip (AUC 0.50–0.53). Before the transforms, adding the features made timing significantly WORSE in both halves (HO1 −0.37, HO2 −0.63, log `whyscreen_B.log`). The transforms removed that harm but added no gain. Depth is the 10h MFE; see screen A. Order calibration by decile and per-feature permutation importance are in the log. vol_spike_mover_4/12 and the _1m volume spikes carry significant importance in timing, but the model as a whole gains nothing.

## Screen A — the envelope, Linear QR and CQR refitted on baseline + 20 transformed features

Paired against each model's cached registry prediction, day-clustered. MFE baseline on vol_48 (cache 9e332d92a294), MAE on vol_48_1m (5bd8d15af8c8), both fingerprint-matched.

| cell | M/A | skill base → +why | skill Δ [95% CI] | gap base → +why | gap Δ [95% CI] | outcome |
|---|---|---|---|---|---|---|
| MFE Linear QR 0.5h | M | +4.39 → +5.74 | **+1.346** [+0.536, +2.067] | 0.75 → 0.95 | +0.200 [−0.663, +0.787] | IMPROVES |
| MFE Linear QR 1h | M | +4.69 → +5.96 | **+1.270** [+0.456, +2.018] | 1.06 → 0.68 | −0.383 [−1.027, +0.346] | IMPROVES |
| MFE Linear QR 2h | M | +5.23 → +6.28 | **+1.053** [+0.378, +1.641] | 1.42 → 0.76 | **−0.653** [−1.153, −0.096] | IMPROVES |
| MFE Linear QR 5h | M | +4.88 → +5.46 | +0.575 [−0.022, +1.128] | 2.34 → 1.59 | **−0.754** [−1.113, −0.331] | IMPROVES |
| MFE Linear QR 10h | M | +4.94 → +5.21 | +0.269 [−0.271, +0.730] | 2.41 → 1.79 | **−0.618** [−0.898, −0.129] | IMPROVES |
| MFE CQR 0.5h | M | +4.55 → +5.85 | **+1.300** [+0.379, +2.220] | 0.68 → 0.82 | +0.143 [−0.667, +0.662] | IMPROVES |
| MFE CQR 1h | M | +4.92 → +6.09 | **+1.175** [+0.200, +2.103] | 0.80 → 0.59 | −0.210 [−0.988, +0.622] | IMPROVES |
| MFE CQR 2h | M | +4.92 → +6.26 | **+1.342** [+0.638, +2.063] | 1.18 → 0.61 | **−0.574** [−0.857, −0.065] | IMPROVES |
| MFE CQR 5h | M | +4.62 → +5.17 | **+0.552** [+0.007, +1.117] | 1.89 → 1.38 | **−0.513** [−0.863, −0.151] | IMPROVES |
| MFE CQR 10h | M | +4.70 → +5.17 | +0.471 [−0.002, +0.916] | 1.86 → 1.53 | −0.331 [−0.716, +0.122] | HOLDS |
| MAE Linear QR 0.5h | M | +2.39 → +2.24 | −0.151 [−0.709, +0.433] | 2.16 → 2.63 | **+0.470** [+0.250, +0.773] | LOSES |
| MAE Linear QR 1h | M | +2.25 → +1.84 | −0.414 [−1.067, +0.262] | 2.45 → 2.89 | **+0.440** [+0.177, +0.740] | LOSES |
| MAE Linear QR 2h | M | +2.32 → +1.73 | −0.588 [−1.362, +0.172] | 2.76 → 3.23 | **+0.469** [+0.222, +0.734] | LOSES |
| MAE Linear QR 5h | M | +2.74 → +2.12 | **−0.627** [−1.248, −0.034] | 3.04 → 3.29 | **+0.245** [+0.048, +0.471] | LOSES |
| MAE Linear QR 10h | M | +3.21 → +2.71 | −0.495 [−1.126, +0.028] | 3.03 → 3.39 | **+0.360** [+0.154, +0.544] | LOSES |
| MAE CQR 0.5h | M | +1.96 → +2.23 | +0.276 [−0.377, +0.927] | 1.99 → 2.19 | +0.199 [−0.026, +0.422] | HOLDS |
| MAE CQR 1h | M | +1.78 → +2.62 | **+0.831** [+0.233, +1.518] | 2.02 → 2.07 | +0.042 [−0.135, +0.385] | IMPROVES |
| MAE CQR 2h | M | +1.98 → +2.54 | +0.561 [−0.051, +1.175] | 2.41 → 2.44 | +0.038 [−0.150, +0.248] | HOLDS |
| MAE CQR 5h | M | +2.46 → +2.99 | +0.529 [−0.021, +1.047] | 2.55 → 2.49 | −0.060 [−0.197, +0.088] | HOLDS |
| MAE CQR 10h | M | +2.92 → +3.05 | +0.133 [−0.338, +0.548] | 2.38 → 2.52 | +0.144 [−0.023, +0.265] | HOLDS |

| adoption | M/A | result |
|---|---|---|
| market-vol rule, MFE (10 cells, majority 6) | M | **IMPROVES 9 of 10, harm 0 → CLEARS** |
| market-vol rule, MAE | M | IMPROVES 1 of 10, harm 5 → does not clear |
| per-model, MFE Linear QR: harm / mean skill gain | M | none / **+0.902** [+0.360, +1.392] → **ADOPT** |
| per-model, MFE CQR | M | none / **+0.968** [+0.415, +1.572] → **ADOPT** |
| per-model, MAE Linear QR | M | harm at all 5 horizons (calibration) / −0.455 [−1.024, +0.090] → do not adopt |
| per-model, MAE CQR | M | none / +0.466 [−0.006, +0.997] → do not adopt (interval touches zero) |

**Restates volatility: none.**

## What it says

- **Screen A, MFE: the largest feature gain this project has measured on the envelope.** Skill rises by about +1.0 to +1.35 points at 0.5h–2h in both models, against +0.07 to +0.16 for market-wide volatility. Calibration improves from 2h out. Both models are ADOPTED for MFE by the per-model rule, and the direction CLEARS the market-vol rule. **The registry rebuild is the next build and was not done.**
- **Screen A, MAE: no.** Linear QR's calibration gets worse at every horizon (+0.25 to +0.47pp) with all 20 columns added. CQR holds, with one improving cell. *Reading, not tested:* the features describe how a dislocation formed, which says more about how far it comes back (MFE) than about how far it keeps going (MAE).
- **Before the rebuild, three things the rule does not cover and that deserve a look:**
  1. A gain of this size from 20 columns at once. Which columns carry it is unknown; importance was not part of screen A.
  2. Whether the gain holds in HO1 and HO2 separately. Screen A does not split the halves.
  3. Whether a smaller subset gets the same gain.
  None of these was run. They are the user's call.
- **Screen B: when and in what order the best point comes cannot be predicted** by the existing six or the new twenty.
- **The sign-flip null is the key descriptive result:** real dislocations drift away from mu relative to a driftless walk with the same steps. The adverse drift shows up in every decile of every feature.
- *Corrected 2026-10-13 after review (Code Checker); no number changed.* **"Drifts away from mu" is not what the test shows.** The sign-flip null keeps each episode's step sizes and randomises their signs. Real reach can fall below it for two different reasons: drift away from mu, or paths that chop back and forth and so cover less net distance than their own steps would with random signs. The test cannot tell them apart. Read every "drift" in this section's screen B text (the paragraph after the sign-flip table and the decile bullet) as "real paths do worse toward mu than the same steps with random signs". *Reading, not tested:* Code Checker's train-only scratch check found mean 10h move toward mu ≈ −0.02σ (no meaningful drift) and net-travel ratio E[final²]/E[Σ step²] ≈ 0.48, which points to chop rather than drift. That is not a recorded measurement here.

Nothing in the registry or the live system was touched.

---

# WHY-IT-MOVED CHECKS — does screen A's MFE gain hold? NOT REAL by the fixed rule: it lives in HO2; subset of 4–5 groups replaces the 20, 2026-10-13

Tag: **WHY-CHECKS**. `whycheck.py`, log `logs/whycheck.log` (1,447s). MFE only, Linear QR and CQR, five horizons. Same population, split, 1-minute targets, transforms and fill as screen A (`whyscreen.why_columns`, one shared definition). Rules and gap-fills fixed in the docstring before the run, reviewed by Code Checker before the run. Nothing written to the registry or any cache.

**Gaps filled before the run:**
- "Six" = the MFE registry baseline, which has **five** features (vol_48, vratio, vol_slope, sandwich, off_mark). That is what screen A paired against; vol_48_1m belongs to MAE. Written "base" and "base+20".
- Subset rule: a group is kept if its **five-horizon-mean** val importance interval clears zero, chosen per model.
- "Significantly worse" for replacement = skill interval wholly below zero **or** gap interval wholly above zero, on the full held out. An empty subset would be read off check 2.
- "Positive in both halves" = the paired skill interval is **above zero** in each half (screen B's precedent). The point-estimate count is printed, not used. **This choice decides the verdict; see "What it says".**

| check | M/A |
|---|---|
| gate 0: base+20 refit reproduces screen A's 10 MFE skill and gap differences | M, **10 of 10** within 0.0005 (largest gap 0.0004) |
| MFE cache fingerprint | M, 9e332d92a294, matches |
| groups (7) | A, lone_share (2), common_share (2), mkt_move (2), lagger_spread (2), vol_spike_mover (4), vol_spike_ratio (4), vadj_resid (4); 1-minute twins grouped with the 30-minute feature |

Held-out levels are confirmatory (scored before by screen A); the HO1/HO2 split and the subset comparisons are new measurements.

## Check 2 — base+20 minus base, by half (paired, day-clustered)

Skill in points (+ helps); gap in pp (− better). HO1 n 8,200, HO2 n 9,864.

| cell | M/A | HO1 skill Δ [95% CI] | HO2 skill Δ [95% CI] | HO1 gap Δ [95% CI] | HO2 gap Δ [95% CI] |
|---|---|---|---|---|---|
| Linear QR 0.5h | M | +0.512 [−0.372, +1.465] | **+2.034** [+0.901, +2.946] | **+1.410** [+0.321, +1.705] WORSE | −0.120 [−1.018, +0.286] |
| Linear QR 1h | M | +0.207 [−0.855, +1.144] | **+2.145** [+1.086, +3.118] | +0.810 [−0.472, +1.441] | −0.406 [−0.998, +0.153] |
| Linear QR 2h | M | +0.139 [−0.554, +0.894] | **+1.809** [+0.931, +2.710] | +0.771 [−0.721, +1.400] | −0.409 [−1.073, +0.201] |
| Linear QR 5h | M | +0.353 [−0.210, +0.903] | +0.761 [−0.041, +1.795] | −0.915 [−1.439, +0.658] | −0.389 [−0.871, +0.041] |
| Linear QR 10h | M | +0.288 [−0.158, +0.679] | +0.252 [−0.408, +1.030] | −0.951 [−1.224, +0.402] | −0.341 [−0.847, +0.187] |
| CQR 0.5h | M | −0.170 [−1.311, +0.836] | **+2.513** [+1.280, +3.653] | **+1.583** [+0.204, +1.886] WORSE | +0.032 [−0.540, +0.300] |
| CQR 1h | M | +0.207 [−1.392, +1.995] | **+1.972** [+0.852, +3.028] | +1.363 [−0.120, +1.683] | −0.476 [−0.904, +0.151] |
| CQR 2h | M | +0.398 [−0.543, +1.401] | **+2.122** [+1.172, +2.957] | +1.029 [−0.433, +1.379] | −0.122 [−0.579, +0.200] |
| CQR 5h | M | +0.266 [−0.365, +0.881] | **+0.793** [+0.080, +1.728] | −0.361 [−1.267, +1.022] | −0.079 [−0.551, +0.322] |
| CQR 10h | M | +0.364 [−0.127, +0.751] | +0.563 [−0.138, +1.418] | −0.527 [−1.066, +0.710] | +0.034 [−0.511, +0.442] |

| reading rule | M/A | result |
|---|---|---|
| horizons with skill interval above zero in BOTH halves | M | Linear QR **0 of 5**, CQR **0 of 5** |
| (not used) point estimate above zero in both halves | M | Linear QR 5 of 5, CQR 4 of 5 |
| **gain is real** (3+ horizons, one model) | M | **NO** |

## Check 1 — grouped permutation importance in base+20 (20 shuffles; skill points lost; five-horizon mean [95% CI])

| group | M/A | Linear QR val | Linear QR held out | CQR val | CQR held out |
|---|---|---|---|---|---|
| vol_spike_mover (4) | M | **+2.422** [+2.094, +2.727] | **+2.317** [+1.895, +2.720] | **+3.286** [+2.852, +3.808] | **+3.216** [+2.631, +3.894] |
| vadj_resid (4) | M | +0.116 [+0.008, +0.240] | +0.180 [+0.099, +0.265] | **+0.913** [+0.636, +1.219] | **+1.038** [+0.854, +1.244] |
| vol_spike_ratio (4) | M | +0.611 [+0.477, +0.768] | +0.610 [+0.470, +0.751] | +0.122 [+0.084, +0.158] | +0.106 [+0.058, +0.148] |
| mkt_move (2) | M | +0.663 [+0.287, +1.140] | +0.445 [+0.267, +0.665] | +0.267 [+0.035, +0.630] | −0.018 [−0.156, +0.110] |
| lone_share (2) | M | +0.005 [−0.063, +0.071] | +0.057 [+0.002, +0.108] | +0.158 [+0.093, +0.241] | +0.124 [+0.043, +0.200] |
| common_share (2) | M | +0.183 [−0.092, +0.477] | +0.264 [−0.006, +0.546] | −0.021 [−0.169, +0.111] | −0.036 [−0.145, +0.058] |
| lagger_spread (2) | M | +0.013 [−0.003, +0.029] | +0.008 [−0.007, +0.020] | +0.001 [−0.006, +0.008] | +0.004 [−0.002, +0.010] |

Per-horizon cells are in the log. Importance is largest at 0.5h and fades with horizon (vol_spike_mover, Linear QR: +3.48 at 0.5h to +1.10 at 10h, held out). **Importance ranks groups by how much the fitted model leans on them; it is not their worth.** Shuffling vol_spike_mover costs 3.48 (Linear QR) and 5.52 (CQR) points at 0.5h, more than the twenty add on refit (about +1.3). *Reading, not tested:* shuffling breaks its correlation with columns the model also uses (vol_48, vol_spike_ratio, vadj_resid), so offsetting linear coefficients stop cancelling and the trees extrapolate.

## Check 3 — base+subset (subset chosen on val)

| model | M/A | subset (val) | columns |
|---|---|---|---|
| Linear QR | M | mkt_move, vol_spike_mover, vol_spike_ratio, vadj_resid | 14 of 20 |
| CQR | M | lone_share, mkt_move, vol_spike_mover, vol_spike_ratio, vadj_resid | 16 of 20 |

Held out, subset minus base+20 (skill / gap):

| cell | M/A | skill Δ [95% CI] | gap Δ [95% CI] | subset minus base, skill Δ |
|---|---|---|---|---|
| Linear QR 0.5h | M | −0.123 [−0.306, +0.046] | +0.003 [−0.109, +0.145] | +1.223 [+0.456, +1.880] |
| Linear QR 1h | M | −0.186 [−0.447, +0.050] | +0.086 [−0.042, +0.204] | +1.084 [+0.340, +1.824] |
| Linear QR 2h | M | −0.075 [−0.252, +0.109] | +0.016 [−0.115, +0.290] | +0.978 [+0.395, +1.550] |
| Linear QR 5h | M | +0.017 [−0.113, +0.160] | +0.062 [−0.101, +0.203] | +0.592 [+0.100, +1.092] |
| Linear QR 10h | M | +0.089 [−0.013, +0.212] | +0.133 [−0.030, +0.236] | +0.358 [−0.085, +0.746] |
| CQR 0.5h | M | −0.011 [−0.160, +0.161] | −0.028 [−0.163, +0.114] | +1.289 [+0.385, +2.232] |
| CQR 1h | M | **+0.148** [+0.028, +0.271] | +0.053 [−0.128, +0.217] | +1.323 [+0.341, +2.222] |
| CQR 2h | M | −0.084 [−0.196, +0.052] | −0.042 [−0.133, +0.089] | +1.257 [+0.612, +1.950] |
| CQR 5h | M | −0.032 [−0.118, +0.056] | +0.012 [−0.076, +0.088] | +0.521 [−0.018, +1.130] |
| CQR 10h | M | −0.023 [−0.122, +0.076] | −0.002 [−0.070, +0.083] | +0.448 [−0.052, +0.927] |

| reading rule | M/A | result |
|---|---|---|
| Linear QR: subset significantly worse than base+20 at any horizon (held out) | M | none → **subset REPLACES the 20** |
| CQR: same | M | none → **subset REPLACES the 20** |
| not in the rule: Linear QR subset vs base+20 in HO1 | M | significantly worse at 0.5h (−0.180 [−0.357, −0.003]) and 1h (−0.223 [−0.428, −0.001]) |

## What it says

- **By the rule fixed before the run, the gain is not real.** It is carried by HO2 (held-out episodes from 2026-08-26 on): +1.8 to +2.5 skill points at 0.5h–2h in both models, every interval clear of zero. In HO1 the skill gain is small (−0.2 to +0.5) and no interval clears zero, and at 0.5h calibration gets significantly **worse** in both models (+1.4 and +1.6pp).
- **The verdict turns on one gap-fill.** Read as "point estimate above zero in both halves", Linear QR passes 5 of 5 and the gain would count as real. Read as "interval above zero" (used, screen B's precedent), 0 of 5. The user decides which reading stands.
- **The models rely on vol_spike_mover most,** in both models and on both val and held out: the size of the volume spike on the leg that moved. Its own contribution is not measured (no refit without it). vadj_resid matters for CQR, vol_spike_ratio and mkt_move for Linear QR. lagger_spread carries nothing. common_share does not clear on the five-horizon mean, though Linear QR's 0.5h and 2h cells clear on both val and held out.
- **A smaller set does as well.** Dropping lagger_spread and common_share (and lone_share for Linear QR) costs nothing significant on the full held out, so by the rule the subset replaces the 20. In HO1 the Linear QR subset is slightly worse at 0.5h and 1h; not part of the rule.

Nothing in the registry or the live system was touched. MAE not touched.

---

# REACH-MU — which spreads come back to mu within 10 hours? NO SIGNAL: nothing beats volatility; nothing beats chance, 2026-10-13

Tag: **REACH-MU**. Step 0 `reachfeat.py`, log `logs/reachfeat.log` (296s), writes `datasets/reachfeat.npz` and `datasets/breadth_counts.npz`. Steps 1–3 `reachmu.py`: `--stage paths` (log `logs/reachmu_paths.log`, writes `datasets/reach_paths.npz`) and `--stage models` (log `logs/reachmu.log`, 626s). Rules and gap-fills fixed in the docstrings before the run, reviewed by Code Checker before the run. Matched 53,757 episodes, harness.Split unchanged. No stop. pair_triggers_true never read. Libraries added to `.venv`: lightgbm 4.7.0, shap 0.53.0, shapiq 1.7.0.

**Gaps filled before the run** (full text in the docstrings):
- The mover's 7-day residual sd uses the 336 bars before the lookback window (ddof 1, at least 168 finite).
- All fresh crossings before entry count. The episode's own pair is excluded from the leg breadth counts.
- "Some model" = the two models chosen on val: L1 logistic and the best tree. The other 13 tree configurations are reported but do not vote.
- "Depth curve improves beyond depth 1" = best tree minus the val-best depth-1 tree on flag share at 80% catch, interval below zero in both halves.
- STRONG = flag-share interval wholly below 0.5 and the flagged set's beyond-chance gap interval wholly above zero, both halves.
- Fixed transforms: log on vol_48, vol_48_1m, sigma, breadth_ratio; log1p on the two trigger counts. Hour and weekday at the decision time (entry + 30 min). Pre-registered pairs use the 12-bar versions. Every choice by val log loss.

## Step 0 — checks

| check | M/A |
|---|---|
| recomputed z at entry vs z_at_entry (mkdisloc geometry) | M, max diff **0**, 60,000 of 60,000; every entry bar is a fresh crossing |
| look-ahead, max index touched minus entry index | M, mover +0, past triggers −1, breadth +0 |
| mover_resid_z > 0 exactly when the dominant contribution widened the spread | M, 58,596 of 58,596 (4 bars); 58,555 of 58,555 (12 bars) |
| episodes with under 30 days of history | M, 6,432 of 60,000 |
| any Step 0 feature with Spearman > 0.8 vs vol_48 or vol_48_1m | M, **none**; largest is −0.303 (mover_ret_12 vs vol_48_1m) |

| feature (all 60,000) | M/A | finite | median | p5 | p95 |
|---|---|---|---|---|---|
| mover_resid_z_4 | M | 58,521 | 2.00 | −0.334 | 7.68 |
| mover_resid_z_12 | M | 58,424 | 1.76 | −0.137 | 6.12 |
| mover_ret_4 | M | 59,830 | 0.0275 | −0.0033 | 0.111 |
| mover_ret_12 | M | 59,707 | 0.0408 | −0.0032 | 0.152 |
| triggers_past_rate (per day) | M | 60,000 | 0.372 | 0.230 | 0.480 |
| triggers_past_30d | M | 60,000 | 11 | 3 | 17 |
| leg_a_breadth | M | 60,000 | 0.054 | 0 | 0.645 |
| leg_b_breadth | M | 60,000 | 0.052 | 0 | 0.598 |
| breadth_ratio | M | 60,000 | 7.93 | 1.21 | 83 |
| market_breadth | M | 60,000 | 0.0229 | 0.0068 | 0.125 |

Missing values filled with the train median; counts in the log (largest: vol_spike_ratio_1m_4, 1,378; mover_resid_z_12, 876).

## Step 1 — the chance bar and the mover

| number | M/A |
|---|---|
| depth vs the 10h MFE target | M, max diff 0 |
| reach mu within 10h | M, **12,424 of 53,757 (0.2311)** |
| mean chance probability (50 sign-flip seeds) | M, **0.2980** |

| block | M/A | n | real reach | mean chance | gap |
|---|---|---|---|---|---|
| train | M | 22,645 | 0.2235 | 0.3062 | −0.0827 |
| val | M | 13,048 | 0.2259 | 0.2978 | −0.0719 |
| HO1 | M | 8,200 | 0.2433 | 0.2955 | −0.0522 |
| HO2 | M | 9,864 | 0.2452 | 0.2818 | −0.0365 |

Mover medians [p5, p95]: mover_resid_z_12 train +1.75 [−0.30, +6.56], HO1 +1.85 [+0.32, +5.89], HO2 +1.67 [−0.21, +5.78]. On most episodes the mover widened the spread, by about 2 residual sd. All four distributions are in the log.

By decile of mover_resid_z_12 (train cut points), real reach minus chance: **negative in all 10 deciles in train** (−0.046 to −0.103) and **in all 10 in HO1** (−0.009 to −0.076). In HO2 it is mixed (−0.081 to +0.013). Reach does not rise with the size of the move. Full cells are in the log.

## Step 2 — the models (every choice on val log loss)

| model | M/A | val log loss | chosen settings | fitted trees, depth max (mean), leaves max (mean) |
|---|---|---|---|---|
| vol-only (vol_48, vol_48_1m, sigma) | M | 0.50559 | unpenalised | — |
| logistic L1 | M | **0.50161** | C = 0.1; 42 of 44 nonzero (sandwich, vadj_resid_1m_4 dropped) | — |
| depth 1 gbdt | M | 0.50343 | mdl 400, lr 0.1, 450 rounds | 450, 1 (1.00), 2 (2.0) |
| depth 2 gbdt | M | **0.50266** | mdl 400, lr 0.1, 175 rounds | 175, 2 (2.00), 4 (3.9) |
| depth 3 gbdt | M | 0.50328 | mdl 400, lr 0.03, 231 | 231, 3 (3.00), 8 (7.2) |
| depth 4 gbdt | M | 0.50377 | mdl 400, lr 0.03, 176 | 176, 4 (4.00), 16 (12.0) |
| depth 6 gbdt | M | 0.50360 | mdl 400, lr 0.1, 31 | 31, 6 (6.00), 36 (25.1) |
| depth 8 gbdt | M | 0.50371 | mdl 400, lr 0.03, 116 | 116, 8 (8.00), 44 (33.1) |
| unlimited gbdt | M | 0.50369 | leaves 64, mdl 400, lr 0.03, 95 | 95, 18 (11.16), 46 (43.4) |
| depth 1 / 2 / 3 / 4 dart | M | 0.50497 / 0.50385 / 0.50418 / 0.50460 | mdl 400; 600 / 600 / 300 / 300 rounds | depth and leaves as set (log) |
| depth 6 / 8 / unlimited dart | M | 0.50641 / 0.50664 / 0.50683 | mdl 400; 300 / 300 / 100 rounds | unlimited: depth max 19 (11.20), leaves max 47 (43.5) |

Best tree (val): **depth 2 gbdt**. Best model (val): **logistic L1**. Every configuration chose the largest min_data_in_leaf (400). Depth 6 and above never fill their leaf budget (25–43 mean leaves of 64–256 allowed).

## Step 3 — the headline (held out)

| model | half | M/A | catch 50%: flag / hit | catch 80%: flag / hit | catch 90%: flag / hit | top-20% hit | top-20% gap vs chance | AUC | log loss |
|---|---|---|---|---|---|---|---|---|---|
| random | HO1 | M | 0.500 / 0.243 | 0.800 / 0.243 | 0.900 / 0.243 | 0.243 | −0.052 | 0.500 | 0.55595 |
| vol-only | HO1 | M | 0.350 / 0.348 | 0.656 / 0.297 | 0.794 / 0.276 | 0.378 | −0.067 | 0.6483 | 0.53051 |
| **logistic L1** | HO1 | M | 0.342 / 0.356 | **0.650** / 0.299 | 0.784 / 0.279 | 0.391 | −0.059 | 0.6541 | 0.52720 |
| depth 2 gbdt | HO1 | M | 0.349 / 0.349 | 0.662 / 0.294 | 0.770 / 0.284 | 0.390 | −0.056 | 0.6547 | 0.52581 |
| random | HO2 | M | 0.500 / 0.245 | 0.800 / 0.245 | 0.900 / 0.245 | 0.245 | −0.037 | 0.500 | 0.55837 |
| vol-only | HO2 | M | 0.334 / 0.367 | 0.639 / 0.307 | 0.786 / 0.281 | 0.395 | −0.038 | 0.6582 | 0.52893 |
| **logistic L1** | HO2 | M | 0.330 / 0.372 | **0.637** / 0.308 | 0.788 / 0.280 | 0.415 | −0.029 | 0.6671 | 0.52436 |
| depth 2 gbdt | HO2 | M | 0.337 / 0.363 | 0.647 / 0.303 | 0.804 / 0.275 | 0.417 | −0.027 | 0.6606 | 0.52759 |

All 14 tree configurations, both halves, are in the log. Their flag share at 80% catch ranges over 0.640–0.662 (HO1) and 0.642–0.655 (HO2).

**Paired, day-clustered (A minus B):**

| comparison | M/A | HO1 flag80 | HO1 top-20 hit | HO2 flag80 | HO2 top-20 hit |
|---|---|---|---|---|---|
| logistic L1 − vol-only | M | −0.0062 [−0.0273, +0.0157] | +0.0134 [−0.0039, +0.0264] | −0.0020 [−0.0308, +0.0203] | **+0.0198** [+0.0049, +0.0337] |
| depth 2 gbdt − vol-only | M | +0.0060 [−0.0239, +0.0309] | +0.0116 [−0.0083, +0.0316] | +0.0078 [−0.0260, +0.0307] | **+0.0218** [+0.0010, +0.0397] |
| depth 2 gbdt − logistic L1 | M | +0.0122 [−0.0113, +0.0271] | −0.0018 [−0.0144, +0.0170] | +0.0098 [−0.0073, +0.0278] | +0.0020 [−0.0141, +0.0139] |
| depth 2 gbdt − depth 1 gbdt | M | +0.0091 [−0.0091, +0.0193] | +0.0024 [−0.0098, +0.0163] | +0.0047 [−0.0076, +0.0146] | +0.0000 [−0.0114, +0.0127] |

Non-voting configurations against vol-only: **no flag80 interval clears zero for any of the 14, in either half.** Several top-20% hit rates are significantly better than vol-only by +0.02–0.03, mostly in HO2 (rows in the log, marked "does not vote").

| candidate at 80% catch | M/A | flag share [95%] | beyond-chance gap of the flagged set [95%] |
|---|---|---|---|
| logistic L1, HO1 | M | 0.650 [0.621, 0.682] | −0.053 [−0.074, −0.030] |
| logistic L1, HO2 | M | 0.637 [0.595, 0.667] | −0.041 [−0.064, −0.017] |
| depth 2 gbdt, HO1 | M | 0.662 [0.627, 0.689] | −0.053 [−0.075, −0.027] |
| depth 2 gbdt, HO2 | M | 0.647 [0.605, 0.677] | −0.042 [−0.064, −0.020] |

| reading rule | M/A | result |
|---|---|---|
| SIGNAL (a candidate's flag80 significantly below vol-only in both halves) | M | **NO**: neither candidate clears in either half |
| REGIME-DEPENDENT | M | none |
| COMBINATIONS MATTER | M | **NO**: best tree is not better than logistic or depth 1 in either half |
| STRONG | M | **none**: flag share 0.64–0.66, and the flagged sets reach mu LESS often than chance |

**Depth curve** (flag share at 80% catch / top-20% hit; no intervals were printed although the log's header says "intervals"; the paired rows above carry them):

| boosting | half | M/A | d1 | d2 | d3 | d4 | d6 | d8 | unlimited |
|---|---|---|---|---|---|---|---|---|---|
| gbdt | HO1 | M | 0.653/0.387 | 0.662/0.390 | 0.649/0.398 | 0.640/0.407 | 0.642/0.395 | 0.643/0.404 | 0.645/0.401 |
| gbdt | HO2 | M | 0.642/0.417 | 0.647/0.417 | 0.655/0.418 | 0.650/0.420 | 0.652/0.420 | 0.652/0.421 | 0.652/0.421 |
| dart | HO1 | M | 0.644/0.388 | 0.649/0.399 | 0.644/0.396 | 0.652/0.405 | 0.654/0.401 | 0.660/0.396 | 0.656/0.401 |
| dart | HO2 | M | 0.650/0.408 | 0.652/0.418 | 0.651/0.416 | 0.646/0.418 | 0.643/0.416 | 0.647/0.405 | 0.655/0.424 |

Flat. Depth adds nothing.

Calibration by decile is in the log. All three models track the observed rate within a few points; the top decile predicts 0.40–0.45 against 0.42–0.47 observed.

## Importance (held out, grouped permutation, log-loss skill points lost)

| group | M/A | logistic L1 [95%] | depth 2 gbdt [95%] |
|---|---|---|---|
| vol_48 (+ vol_48_1m) | M | **+12.66** [+11.80, +13.63] | **+8.60** [+7.94, +9.32] |
| abs_z | M | **+1.99** [+1.57, +2.40] | **+1.20** [+0.94, +1.49] |
| vol_spike_mover | M | +0.50 [+0.30, +0.74] | +0.26 [+0.06, +0.48] |
| vol_slope | M | +0.35 [+0.16, +0.55] | +0.23 [+0.07, +0.40] |
| vol_spike_ratio | M | +0.21 [+0.13, +0.31] | +0.02 [−0.03, +0.06] |
| off_mark | M | +0.18 [+0.07, +0.26] | −0.01 [−0.03, +0.02] |
| vratio | M | +0.14 [+0.04, +0.26] | +0.12 [+0.04, +0.23] |
| sandwich | M | 0 (dropped by L1) | +0.23 [+0.14, +0.33] |
| vadj_resid | M | +0.01 [−0.08, +0.12] | +0.17 [+0.06, +0.30] |
| beta | M | −0.02 [−0.04, +0.01] | +0.11 [+0.02, +0.18] |
| lone_share | M | +0.01 [−0.01, +0.03] | +0.02 [+0.01, +0.03] |
| every Step 0 group, hour, weekday, sigma, r2, mkt_move, common_share, lagger_spread | M | no interval clears zero | no interval clears zero |

abs_z matters because the target's bar is |z|: a farther dislocation has farther to come back. The new Step 0 features (mover size, past triggers, breadth) carry nothing in either model.

## Interactions

SHAP interaction values, depth 2 gbdt, 5,000 held-out episodes (2,500 per half). shap TreeExplainer took under a second, so shapiq was not needed. Free + inactive memory beforehand: 1.63 GB; swap used 1.40 GB of 3.07 GB.

| top pair (rank) | M/A | interaction contrast, held out [95%] | HO1 | HO2 |
|---|---|---|---|---|
| vol_48 × vol_48_1m (1) | M | +0.035 [−0.003, +0.076] | +0.013 [−0.052, +0.080] | +0.042 [−0.007, +0.093] |
| sandwich × mkt_move_12 (2) | M | +0.006 [−0.029, +0.037] | +0.026 [−0.029, +0.087] | −0.001 [−0.041, +0.039] |
| vol_48_1m × mkt_move_12 (3) | M | −0.002 [−0.036, +0.033] | **+0.045** [+0.005, +0.089] | −0.032 [−0.069, +0.021] |
| vol_slope × vol_spike_mover_1m_4 (4) | M | −0.014 [−0.044, +0.011] | −0.028 | −0.005 |
| vol_48 × sandwich (5) | M | **+0.052** [+0.027, +0.080] | +0.018 [−0.038, +0.065] | **+0.062** [+0.030, +0.101] |
| vol_48 × vratio (6) | M | −0.003 [−0.029, +0.024] | −0.012 | +0.004 |
| vol_spike_mover_1m_12 × abs_z (7) | M | −0.016 [−0.045, +0.010] | −0.032 | −0.007 |
| vadj_resid_12 × leg_b_breadth (8) | M | **+0.030** [+0.004, +0.054] | +0.020 [−0.032, +0.064] | **+0.040** [+0.003, +0.069] |
| common_share_12 × mkt_move_12 (9) | M | −0.032 [−0.077, +0.022] | −0.056 | −0.033 |
| vol_slope × beta (10) | M | +0.001 [−0.023, +0.025] | +0.017 | −0.012 |

| pre-registered pair | M/A | contrast, held out [95%] | HO1 | HO2 |
|---|---|---|---|---|
| lone_share_12 × vol_spike_mover_12 (news, keeps running) | M | −0.007 [−0.041, +0.021] | −0.009 | −0.007 |
| common_share_12 × lagger_spread_12 (lag, catches up) | M | −0.010 [−0.040, +0.015] | −0.010 | −0.011 |
| breadth_ratio × vol_spike_mover_12 (one coin vs everyone, on volume) | M | +0.009 [−0.022, +0.039] | +0.029 | −0.007 |

Contrast = HH − HL − LH + LL reach rates, 2×2 at train medians; it was reported, not gated. All 2×2 cells are in the log. **No pair clears in both halves.** Two clear in HO2 only (vol_48 × sandwich, vadj_resid_12 × leg_b_breadth) and one in HO1 only. With 13 pairs × 2 halves tested, about 1 such clearance is expected by chance. **None of the three pre-registered combinations shows anything.**

## Liquidation at 20x (best model, logistic L1, flagged at 80% catch)

| number | M/A |
|---|---|
| 20x headroom in entry sigma, median [p5, p95] | M, 6.71 [2.71, 16.69] |
| HO1: flagged reverters hitting liquidation before mu | M, **32 of 1,596 (2.0%)**; all HO1 reverters 46 of 1,995 (2.3%) |
| HO2: same | M, **30 of 1,936 (1.6%)**; all HO2 reverters 44 of 2,419 (1.8%) |
| all 53,757: reverters hitting it before mu / any episode hitting it within 10h | M, 206 of 12,424 / 5,330 |
| liquidation assumptions | A, 1-minute closes, no fees, no funding, margin as liquidation_distance models it |

## What it says

- **No signal.** Picking reverters at entry works no better than volatility alone. To catch 80% of reverters every model flags about two-thirds of all episodes (0.64–0.66). Vol-only needs about the same (0.656, 0.639). No candidate's advantage clears zero in either half, so this is not regime-dependent either.
- **Combinations add nothing.** The val-chosen tree is depth 2, it does not beat the logistic model, and the depth curve is flat from depth 1 to unlimited.
- **The flagged reverters still do worse than chance.** Even the top 20% reach mu less often than a driftless path with the same steps would (−0.03 to −0.06 for the two candidates). This is the WHY-IT-MOVED sign-flip finding again: real paths reach mu less often than the same steps with random signs. The sign-flip test cannot say whether that is drift away from mu or paths that chop back and forth (see the correction under WHY-IT-MOVED). Picking the most volatile episodes raises the raw reach rate, because volatile spreads travel further, but it does not find spreads that revert.
- **The ranking is volatility plus distance.** vol_48 dominates both models, followed by |z|. Of the why-it-moved features only vol_spike_mover carries a little. Mover size, past triggers and breadth carry nothing.
- **A small edge at the very top, HO2 only.** Logistic L1 and the depth-2 tree raise the top-20% hit rate over vol-only by +0.02 in HO2, intervals clear. In HO1 it is smaller and does not clear. Not a signal by the rule.
- **Liquidation is not the issue at 20x.** About 2% of flagged reverters would be wiped out before reaching mu.

Nothing in the registry or the live system was touched. Nothing committed.

---

# REACH-MU v2 — prune, then perp vs index, spike detail, signed breadth: NO SIGNAL; the new families do not help; each helps in HO1 only, 2026-10-13

Tag: **REACH-MU-V2**. Step 2 features `reachfeat2.py`, log `logs/reachfeat2.log` (350s), writes `datasets/reachfeat2.npz` and `datasets/breadth_signed.npz`. Steps 1, 3, 4 `reachmu2.py`, log `logs/reachmu2.log` (75s). `reachmu.py` was refactored (`assemble_features`, `reach_group` shared); behaviour unchanged, verified by Code Checker (C 0.1, val log loss 0.50161, 42 of 44 nonzero, as in REACH-MU). Same target, population and split as REACH-MU. No funding data. No stop. Rules and gap-fills fixed in the docstrings before the run; Code Checker reviewed before the run.

**Gaps filled before the run:**
- The per-leg perp features enter the model as dominant and other (A and B are an arbitrary ticker order); signed_breadth_a/_b keep the brief's names.
- 2h features use the 4-bar dominant leg; 6h features and everything else use the 12-bar one.
- The last completed hour is H* = floor_hour(entry label − 30 min). The perp's hourly close is the 30m panel close at label H+30.
- med30 = the median of the 336 30m bars before the 6h window. Summed 1m volume equals 30m bar volume exactly (ratio 1.0 on BTC, DOGE, PEPE).
- retrace_started is scaled by the sd of raw 1m returns over the prior 7 days; there is no 1m factor model.
- Signed breadth needed a new table (the saved one is |z| ≥ 3 and unsigned).
- **basis_rel_move_diff_2 and _6 are dropped** at load: they are identical to basis_move_diff_2 and _6, because the hourly median cancels in a same-hour difference. 26 new features enter, not 28.
- Tree min_data_in_leaf over {100, 400, 1000, 2000}, extended because REACH-MU chose its 400 ceiling in every configuration. LR fixed at 0.05; rounds by early stopping on val. Each set is represented by its lowest-val-log-loss model.

## Step 2 — checks and the user's basis addition

| check | M/A |
|---|---|
| look-ahead: latest hourly close read vs the entry close | M, +0 min |
| look-ahead: 1m spike windows / med30 baseline / breadth | M, end at T+29 / −12 bars / +0 bars |
| recomputed finite-z counts = breadth_counts.npz | M, **True** |
| any new feature with Spearman > 0.8 vs vol_48 or vol_48_1m | M, **none**; largest −0.230 (breadth_change_4h vs vol_48_1m) |
| hourly basis grid | M, 18,298 hours × 214 coins; median 146 coins per hour |
| basis_rel_move_diff_L identical to basis_move_diff_L | M, True at 2h and 6h |

**How much of a leg's basis move is market-wide** (correlation with the cross-sectional median basis move, matched 53,757):

| lookback | leg | M/A | Pearson (R²) | Spearman |
|---|---|---|---|---|
| 2h | A | M | +0.068 (0.005) | +0.223 |
| 2h | B | M | +0.132 (0.017) | +0.231 |
| 2h | dominant | M | +0.060 (0.004) | +0.184 |
| 6h | A | M | +0.066 (0.004) | +0.231 |
| 6h | B | M | +0.104 (0.011) | +0.224 |
| 6h | dominant | M | +0.053 (0.003) | +0.190 |

Under 2% of a leg's basis move is market-wide by variance. The rank correlation of about 0.2 says the direction is shared more than the size.

| feature (matched 53,757) | M/A | finite | median [p5, p95] |
|---|---|---|---|
| basis_now_dom | M | 53,604 | −0.00067 [−0.00339, +0.00217] |
| basis_rel_now_dom | M | 53,604 | +0.00002 [−0.00263, +0.00281] |
| basis_move_dom_2 / _6 | M | 53,676 / 53,604 | −0.000002 [−0.00283, +0.00236] / −0.000007 [−0.00302, +0.00236] |
| index_share_dom_2 / _6 | M | 53,449 / 53,502 | +0.999 [+0.766, +1.236] / +0.999 [+0.868, +1.138] |
| impact_per_vol (log) | M | 53,370 | −6.13 [−8.45, −4.54] |
| wick_reject | M | 53,602 | 0.441 [0.229, 0.680] |
| retrace_started | M | 53,599 | −1.07 [−6.42, +1.15] |
| spike_persistence | M | 53,602 | 0.297 [0.064, 0.808] |
| mins_since_peak (log1p) | M | 53,602 | 4.32 [1.10, 5.79] |
| coinc_other / coinc_btc (log) | M | 53,602 | +0.31 [−1.17, +2.61] / +0.41 [−1.08, +2.56] |
| signed_breadth_a / _b | M | 53,757 | 0.226 [0.011, 0.876] / 0.224 [0.010, 0.838] |
| signed_breadth_gap | M | 53,604 | +0.392 [−0.228, +0.891] |
| breadth_change_1h / _4h | M | 53,604 | +0.110 [−0.053, +0.662] / +0.150 [−0.019, +0.724] |

The full table, with missing counts by cause, is in `logs/reachfeat2.log`. The main causes are an undefined dominant leg (81–153 rows) and a missing index or a flat perp (up to 790 for index_share_diff_2). The perp and index move almost one-for-one (index_share median 0.999). retrace_started is negative at the median: at entry the leg is still moving away, not back.

## Step 1 — the prune (validation only)

Logistic L1: C 0.1, val log loss 0.50161. Depth-2 tree: min_data_in_leaf 1000, 308 rounds, val log loss 0.50279.

| group | M/A | L1 val [95%] | depth-2 val [95%] | decision |
|---|---|---|---|---|
| vol_48 | M | +12.64 [+11.52, +13.79] | +8.02 [+7.20, +8.82] | keep (always) |
| abs_z | M | +1.83 [+1.37, +2.17] | +0.80 [+0.50, +1.07] | keep (always) |
| vol_spike_mover | M | +0.40 [+0.11, +0.64] | +0.15 [−0.02, +0.33] | keep |
| sigma | M | +0.32 [+0.11, +0.52] | +0.06 [−0.01, +0.13] | keep |
| off_mark | M | +0.29 [+0.17, +0.40] | 0.00 | keep |
| vol_slope | M | +0.26 [+0.07, +0.49] | +0.12 [−0.06, +0.31] | keep |
| vratio | M | +0.19 [+0.10, +0.28] | +0.25 [+0.16, +0.36] | keep |
| weekday | M | +0.16 [+0.03, +0.31] | +0.22 [+0.08, +0.37] | keep |
| vol_spike_ratio | M | +0.17 [+0.04, +0.31] | −0.02 [−0.06, +0.02] | keep |
| sandwich | M | 0.00 (L1 dropped it) | +0.22 [+0.10, +0.36] | keep |
| beta | M | −0.03 [−0.060, −0.0002] | +0.13 [+0.07, +0.20] | keep |
| r2 | M | +0.08 [+0.01, +0.15] | +0.03 [−0.01, +0.07] | keep |
| common_share | M | −0.05 [−0.11, +0.003] | +0.07 [+0.01, +0.14] | keep |
| lagger_spread | M | +0.06 [+0.002, +0.12] | +0.01 [−0.03, +0.05] | keep |
| lone_share, mkt_move, vadj_resid, mover_resid_z, mover_ret, triggers_past_rate, triggers_past_30d, breadth (a, b, ratio), market_breadth, hour | M | interval includes zero | interval includes zero | **DROP** |

**Kept: 14 groups, 24 columns. Dropped: 10 groups,** including every REACH-MU Step 0 feature. sigma survived, so kept+new contains every vol-only input.

## Step 3 — models (every setting on val)

| model | M/A | val log loss | settings |
|---|---|---|---|
| kept L1 | M | **0.50196** | C 0.1, 22 of 24 nonzero |
| kept d1 / d2 / d3 / d4 / d6 | M | 0.50401 / 0.50328 / 0.50375 / 0.50326 / 0.50306 | min_data_in_leaf 1000 / 400 / 1000 / 1000 / 1000 |
| kept+new L1 | M | **0.50010** | C 0.1, 44 of 50 nonzero |
| kept+new d1 / d2 / d3 / d4 / d6 | M | 0.50222 / 0.50206 / 0.50285 / 0.50241 / 0.50330 | min_data_in_leaf **100** in all five |

Representatives (lowest val log loss): **kept = kept L1**, **kept+new = kept+new L1**, the same learner, so the comparison isolates the new features. The kept+new trees all chose min_data_in_leaf 100, the bottom of the new grid: another boundary, this time on the other side. Rounds and fitted shapes are in the log.

## Step 4 — the headline (held out)

| model | half | M/A | catch 50%: flag / hit | catch 80%: flag / hit | catch 90%: flag / hit | top-20% hit | AUC |
|---|---|---|---|---|---|---|---|
| random | HO1 | M | 0.500 / 0.243 | 0.800 / 0.243 | 0.900 / 0.243 | 0.243 | 0.500 |
| vol-only | HO1 | M | 0.350 / 0.348 | 0.656 / 0.297 | 0.794 / 0.276 | 0.378 | 0.6483 |
| kept (L1) | HO1 | M | 0.346 / 0.352 | 0.648 / 0.301 | 0.788 / 0.278 | 0.387 | 0.6544 |
| **kept+new (L1)** | HO1 | M | 0.335 / 0.363 | **0.645** / 0.302 | 0.773 / 0.283 | 0.398 | 0.6610 |
| random | HO2 | M | 0.500 / 0.245 | 0.800 / 0.245 | 0.900 / 0.245 | 0.245 | 0.500 |
| vol-only | HO2 | M | 0.334 / 0.367 | 0.639 / 0.307 | 0.786 / 0.281 | 0.395 | 0.6582 |
| kept (L1) | HO2 | M | 0.326 / 0.376 | 0.636 / 0.309 | 0.782 / 0.282 | 0.422 | 0.6699 |
| **kept+new (L1)** | HO2 | M | 0.330 / 0.372 | **0.633** / 0.310 | 0.779 / 0.284 | 0.416 | 0.6694 |

All 12 kept and kept+new models are in the log. Flag share at 80% catch ranges over 0.633–0.655 (HO1) and 0.631–0.641 (HO2).

**Paired, day-clustered (A minus B):**

| comparison | M/A | HO1 flag80 | HO1 top-20 hit | HO2 flag80 | HO2 top-20 hit |
|---|---|---|---|---|---|
| **kept+new − kept** (the test of the new features) | M | −0.0030 [−0.0165, +0.0095] | +0.0110 [−0.0052, +0.0292] | −0.0027 [−0.0154, +0.0110] | −0.0061 [−0.0134, +0.0041] |
| kept+new − vol-only | M | −0.0117 [−0.0316, +0.0074] | +0.0201 [−0.0003, +0.0403] | −0.0058 [−0.0343, +0.0168] | **+0.0203** [+0.0075, +0.0315] |
| kept − vol-only (reported) | M | −0.0087 [−0.0276, +0.0092] | +0.0091 [−0.0094, +0.0247] | −0.0030 [−0.0308, +0.0116] | **+0.0264** [+0.0134, +0.0377] |

**Depth curve, kept+new** (flag share for an 80% catch / top-20% hit):

| half | M/A | L1 | d1 | d2 | d3 | d4 | d6 |
|---|---|---|---|---|---|---|---|
| HO1 | M | 0.645/0.398 | 0.645/0.398 | 0.643/0.401 | 0.633/0.404 | 0.641/0.403 | 0.640/0.395 |
| HO2 | M | 0.633/0.416 | 0.633/0.411 | 0.637/0.413 | 0.635/0.406 | 0.635/0.413 | 0.636/0.403 |

Flat again.

## Importance, held out, kept+new L1 (log-loss skill points lost)

| group | M/A | held out [95%] | HO1 [95%] | HO2 [95%] |
|---|---|---|---|---|
| vol_48 | M | +12.99 [+12.02, +14.01] | +12.39 [+11.06, +13.69] | +13.49 [+12.12, +14.94] |
| abs_z | M | +2.01 [+1.61, +2.42] | +1.55 [+0.96, +2.13] | +2.39 [+1.89, +2.91] |
| vol_spike_mover | M | +0.96 [+0.63, +1.27] | +1.22 [+0.78, +1.61] | +0.74 [+0.35, +1.29] |
| vol_spike_ratio | M | +0.34 [+0.20, +0.47] | +0.23 [+0.03, +0.45] | +0.44 [+0.26, +0.61] |
| **spike_detail [NEW]** | M | +0.17 [−0.05, +0.37] | **+0.33** [+0.09, +0.61] | +0.03 [−0.23, +0.33] |
| **signed_breadth [NEW]** | M | +0.16 [−0.01, +0.32] | **+0.27** [+0.08, +0.47] | +0.07 [−0.16, +0.33] |
| **perp_index [NEW]** | M | +0.08 [+0.01, +0.14] | **+0.12** [+0.04, +0.21] | +0.04 [−0.06, +0.16] |

Every other group and every member (with per-half intervals) is in the log. Members whose interval clears in either half: signed_breadth_a (HO2 +0.24, and held out), signed_breadth_b (held out only), signed_breadth_gap (HO1), breadth_change_4h (HO1), basis_move_diff_6 (HO1). Five perp-index members carry exactly zero, because L1 dropped them.

| reading rule | M/A | result |
|---|---|---|
| NEW FEATURES HELP (kept+new − kept, flag80 clears in both halves) | M | **NO**: clears in neither |
| SIGNAL OVERALL (kept+new − vol-only, both halves) | M | **NO**: clears in neither |
| REGIME-DEPENDENT (either rule clears in one half) | M | none |
| same learner, reported: kept+new L1 − kept L1 | M | identical to the gating row (both representatives are L1) |
| family perp_index | M | **clears in HO1 only (regime-dependent)** |
| family spike_detail | M | **clears in HO1 only (regime-dependent)** |
| family signed_breadth | M | **clears in HO1 only (regime-dependent)** |

## What it says

- **The new features do not help pick reverters.** Adding perp-vs-index, spike detail and signed breadth to the pruned set cuts the flag share for an 80% catch by 0.3 points in each half, with intervals straddling zero. Against volatility only, the gain is 0.6–1.2 points and not significant in either half.
- **No new family passes.** Each family's importance clears only in HO1, while the paired gain from adding them is null in both halves (HO1 −0.0030 [−0.0165, +0.0095]). In HO1 the model leans on them without ranking any better. That is reliance, not benefit.
- **The prune removed 10 of 24 groups**, including every REACH-MU Step 0 feature, without loss: kept L1 scores like the full logistic model did.
- **The ranking is still volatility plus distance from mu**, then the volume spike on the moving leg. The perp trades almost one-for-one with its index (median index share 0.999), and at entry the moving leg is still moving away (median retrace_started −1.07).

Nothing in the registry or the live system was touched. Nothing committed.

---

# DELAYED DECISION — who reverts, given the first 30–60 minutes after initial detection? NOT FOUND: the path adds nothing beyond where the spread now sits, 2026-10-13

Tag: **DELAYED**. `delayed.py`: `--stage paths` (log `logs/delayed_paths.log`, 232s, writes `datasets/delayed_paths.npz`) and `--stage models` (log `logs/delayed.log`, 132s). Vocabulary: **initial detection (t0)** = the first 3σ crossing (earlier work's "entry"); **decision point (d)** = t0 + 30 or t0 + 60 minutes. Same matched 53,757, harness.Split by t0, 1-minute closes, mu and σ frozen at t0. No stop. Rules and gap-fills fixed in the docstring before the run; Code Checker reviewed before the run.

**Gaps filled before the run:**
- "The full model" = the full model with the lowest val log loss among its L1 and five trees.
- new_lows counts minutes setting a new adverse extreme beyond the t0 close. mins_since_worst uses the first minute of the maximum adverse move. path_vol uses the changes within minutes 1..d.
- The volume-since-t0 baseline is the median of d-minute block sums over the 7 days ending at the t0 close; blocks and the window need 80% finite minutes.
- Fixed transforms: log path_vol; log1p new_lows and new_lows_late.
- Every model is L1, as the brief says, so vol-only is now penalised (REACH-MU's was not).
- min_data_in_leaf over {20, 50, 100, 400, 1000}; learning rate 0.05; rounds by early stopping on val.
- The kept set is the 14 REACH-MU-V2 groups, asserted to be 24 columns.

**Added after pre-run review (reported, NOT gating).** The brief fits position and the t0 model as L1 only, while the full model may be a tree. So THE TEST could credit the path with what a tree gets from vol + dist_now alone. Keeping the brief's test as written, position and the t0 model were also fitted with the same tree grid, and same-learner diagnostics were printed. The run was set to send any disagreement with the gating test to the user. **None occurred.**

## Step 0 — populations

| d | split | M/A | episodes | already reverted | dropped (missing minutes) | still open | reach_d | median minutes to mu: from t0 / from d |
|---|---|---|---|---|---|---|---|---|
| 30 | train | M | 22,645 | 143 | 0 | 22,502 | 0.2186 | 288 / 258 |
| 30 | val | M | 13,048 | 43 | 0 | 13,005 | 0.2234 | 309 / 279 |
| 30 | HO1 | M | 8,200 | 30 | 0 | 8,170 | 0.2405 | 299 / 269 |
| 30 | HO2 | M | 9,864 | 37 | 2 | 9,825 | 0.2423 | 281 / 251 |
| 60 | train | M | 22,645 | 391 | 0 | 22,254 | 0.2099 | 304 / 244 |
| 60 | val | M | 13,048 | 157 | 0 | 12,891 | 0.2165 | 319 / 259 |
| 60 | HO1 | M | 8,200 | 85 | 0 | 8,115 | 0.2354 | 304 / 244 |
| 60 | HO2 | M | 9,864 | 129 | 2 | 9,733 | 0.2352 | 293 / 233 |

All 53,757: already reverted by minute 30, **253**; by minute 60, **762**. Two episodes were dropped at each d for missing minutes.

| check | M/A |
|---|---|
| rebuilt depth and reach equal reach_paths.npz | M, exactly |
| path features read | M, minutes 1..d only |
| volume since t0, latest minute read | M, t0 close + 60 at d = 60 (must be ≤ d) |
| volume-since-t0 missing → train median | M, 149–154 per column (dominant leg undefined) |

**Spearman with dist_now / vol_48_1m (still open, d = 30; d = 60 in the log, similar):** worst_so_far +0.71 / +0.12; best_so_far −0.61 / +0.15; mins_since_worst −0.62 / 0.00; bounce_from_worst −0.48 / +0.16; slope_10 −0.40 / 0.00; path_vol +0.27 / +0.41; new_lows +0.66 / −0.01; new_lows_late +0.54 / −0.01; vol_since_dom +0.22 / −0.24. The path features are largely restatements of how far the spread now sits from mu. None exceeds 0.8 against vol_48_1m.

## Models (val log loss; every setting on val)

| model | M/A | d = 30 | d = 60 |
|---|---|---|---|
| vol-only L1 | M | 0.50317 | 0.49632 |
| position L1 (the bar) | M | 0.48429 | 0.45829 |
| t0 model L1 | M | 0.49981 | 0.49352 |
| full L1 | M | 0.47686 | 0.45203 |
| best position tree (diagnostic) | M | d2, 0.47923 | d1, 0.45467 |
| best t0 tree (diagnostic) | M | d4, 0.50096 | d2, 0.49428 |
| **full model (best of L1 + trees)** | M | **full d1, 0.47591** | **full d2, 0.45181** |

Several trees chose min_data_in_leaf 1000, the top of the grid (flagged GRID EDGE in the log): 2 of 5 full trees at d = 30 and 4 of 5 at d = 60. Every verdict below agrees between the L1 and tree comparisons, so no verdict depends on that edge.

## The headline (held out): flag share / hit rate needed to catch still-open reverters

| d | half | model | M/A | catch 50% | catch 80% | catch 90% | top-20% hit |
|---|---|---|---|---|---|---|---|
| 30 | HO1 | random | M | 0.500 / 0.241 | 0.800 / 0.241 | 0.900 / 0.241 | 0.241 |
| 30 | HO1 | vol-only L1 | M | 0.351 / 0.343 | 0.656 / 0.293 | 0.797 / 0.272 | 0.374 |
| 30 | HO1 | t0 model L1 | M | 0.344 / 0.349 | 0.654 / 0.294 | 0.790 / 0.274 | 0.381 |
| 30 | HO1 | **position L1** | M | 0.305 / 0.395 | **0.624** / 0.308 | 0.801 / 0.270 | 0.439 |
| 30 | HO1 | **full (d1)** | M | 0.296 / 0.406 | **0.610** / 0.315 | 0.760 / 0.285 | 0.438 |
| 30 | HO2 | random | M | 0.500 / 0.242 | 0.800 / 0.242 | 0.900 / 0.242 | 0.242 |
| 30 | HO2 | vol-only L1 | M | 0.336 / 0.361 | 0.639 / 0.303 | 0.787 / 0.277 | 0.392 |
| 30 | HO2 | t0 model L1 | M | 0.329 / 0.369 | 0.635 / 0.305 | 0.777 / 0.281 | 0.412 |
| 30 | HO2 | **position L1** | M | 0.285 / 0.425 | **0.600** / 0.323 | 0.755 / 0.289 | 0.461 |
| 30 | HO2 | **full (d1)** | M | 0.281 / 0.432 | **0.582** / 0.333 | 0.736 / 0.296 | 0.475 |
| 60 | HO1 | random | M | 0.500 / 0.235 | 0.800 / 0.235 | 0.900 / 0.235 | 0.235 |
| 60 | HO1 | vol-only L1 | M | 0.349 / 0.338 | 0.658 / 0.286 | 0.795 / 0.267 | 0.365 |
| 60 | HO1 | t0 model L1 | M | 0.346 / 0.340 | 0.658 / 0.286 | 0.791 / 0.268 | 0.368 |
| 60 | HO1 | **position L1** | M | 0.264 / 0.446 | **0.580** / 0.325 | 0.780 / 0.271 | 0.491 |
| 60 | HO1 | **full (d2)** | M | 0.258 / 0.457 | **0.570** / 0.330 | 0.738 / 0.287 | 0.492 |
| 60 | HO2 | random | M | 0.500 / 0.235 | 0.800 / 0.235 | 0.900 / 0.235 | 0.235 |
| 60 | HO2 | vol-only L1 | M | 0.338 / 0.348 | 0.643 / 0.293 | 0.791 / 0.268 | 0.372 |
| 60 | HO2 | t0 model L1 | M | 0.333 / 0.353 | 0.637 / 0.296 | 0.787 / 0.269 | 0.394 |
| 60 | HO2 | **position L1** | M | 0.256 / 0.460 | **0.557** / 0.338 | 0.737 / 0.287 | 0.484 |
| 60 | HO2 | **full (d2)** | M | 0.253 / 0.465 | **0.552** / 0.341 | 0.720 / 0.294 | 0.496 |

Every full tree and the diagnostic trees are in the log.

**Paired flag share at 80% catch, day-clustered 95% (A minus B; negative = A needs fewer flags):**

| comparison | M/A | d = 30 HO1 | d = 30 HO2 | d = 60 HO1 | d = 60 HO2 |
|---|---|---|---|---|---|
| **full − position (THE TEST)** | M | −0.0135 [−0.0352, +0.0077] | −0.0175 [−0.0460, +0.0001] | −0.0104 [−0.0385, +0.0116] | −0.0057 [−0.0236, +0.0144] |
| full − t0 model | M | **−0.0438** [−0.0735, −0.0139] | **−0.0526** [−0.0783, −0.0255] | **−0.0879** [−0.1198, −0.0532] | **−0.0851** [−0.1100, −0.0587] |
| **position − vol-only (dist_now alone)** | M | **−0.0322** [−0.0571, −0.0117] | **−0.0391** [−0.0674, −0.0188] | **−0.0780** [−0.1042, −0.0377] | **−0.0861** [−0.1168, −0.0593] |
| full − vol-only | M | −0.0457 [−0.0747, −0.0204] | −0.0566 [−0.0938, −0.0366] | −0.0884 [−0.1161, −0.0489] | −0.0917 [−0.1224, −0.0658] |
| full L1 − position L1 (diag) | M | −0.0071 [−0.0303, +0.0065] | −0.0190 [−0.0437, +0.0033] | −0.0012 [−0.0336, +0.0119] | −0.0104 [−0.0247, +0.0062] |
| best full tree − best position tree (diag) | M | −0.0042 [−0.0267, +0.0172] | −0.0144 [−0.0409, +0.0014] | −0.0067 [−0.0245, +0.0188] | −0.0081 [−0.0320, +0.0067] |
| full L1 − t0 L1 (diag) | M | −0.0375 [−0.0680, −0.0153] | −0.0541 [−0.0784, −0.0311] | −0.0787 [−0.1209, −0.0491] | −0.0898 [−0.1118, −0.0660] |
| best full tree − best t0 tree (diag) | M | −0.0414 [−0.0791, −0.0133] | −0.0507 [−0.0832, −0.0266] | −0.0891 [−0.1176, −0.0505] | −0.0839 [−0.1110, −0.0622] |

| reading rule | M/A | result |
|---|---|---|
| **FOUND SOMETHING** (full − position clears in both halves at d = 30 or d = 60) | M | **NO**: clears in neither half at either d. d = 30 HO2 is a knife edge (upper bound +0.0001), not near-significance. **The same-learner diagnostics agree at both d (clear in neither); no disagreement.** No d carried a pass. |
| STRONG | M | **none**: the full model's top-20% beyond-chance gap is wholly negative in every cell (below) |
| REGIME-DEPENDENT | M | none |
| how much is dist_now alone (position − vol-only) | M | **3.2–3.9 points at d = 30, 7.8–8.6 at d = 60**, clearing in both halves |
| the path on top (full − position) | M | 0.6–1.8 points, clearing nowhere |

## Chance bar (reading only; sign-flip from minute d, 50 seeds)

| d | half | M/A | still open: real / chance (gap) | full top 20%: real / chance, gap [95%] | full flag share at 80% catch [95%] |
|---|---|---|---|---|---|
| 30 | HO1 | M | 0.2405 / 0.2911 (−0.0506) | 0.4376 / 0.5049, **−0.0673** [−0.0930, −0.0345] | 0.6103 [0.5781, 0.6409] |
| 30 | HO2 | M | 0.2423 / 0.2805 (−0.0381) | 0.4748 / 0.5147, **−0.0399** [−0.0718, −0.0104] | 0.5824 [0.5394, 0.6107] |
| 60 | HO1 | M | 0.2354 / 0.2803 (−0.0449) | 0.4923 / 0.5279, **−0.0356** [−0.0588, −0.0122] | 0.5698 [0.5382, 0.6074] |
| 60 | HO2 | M | 0.2352 / 0.2770 (−0.0418) | 0.4956 / 0.5386, **−0.0429** [−0.0860, −0.0082] | 0.5515 [0.5160, 0.5813] |

Even the full model's top 20% reach mu less often than the same steps with random signs would, in every cell.

## What drives it (held out, full model; log-loss skill points lost)

| group | M/A | d = 30 held out [95%] | d = 60 held out [95%] | clears in both halves |
|---|---|---|---|---|
| t0 features (kept set) | M | +7.81 [+6.97, +8.65] | +6.61 [+5.85, +7.40] | yes, both d |
| dist_now | M | +3.94 [+3.34, +4.53] | +6.81 [+5.91, +7.65] | yes, both d |
| path shape (worst, best, bounce, mins since worst) | M | +1.12 [+0.78, +1.45] | +2.17 [+1.76, +2.57] | yes, both d |
| path_vol | M | +0.64 [+0.47, +0.81] | +0.63 [+0.46, +0.81] | yes, both d |
| volume since t0 | M | +0.23 [+0.10, +0.37] | +0.15 [+0.07, +0.26] | yes, both d |
| path momentum (slope_10, new_lows, new_lows_late) | M | +0.05 [−0.06, +0.15] | +0.07 [−0.02, +0.14] | no |

Per-half intervals are in the log. Path shape, path_vol and volume since t0 carry weight, yet adding them does not beat position in the paired test. The model leans on them, but their information overlaps with dist_now (Spearman up to 0.72).

**Profile, full model's top 20% vs bottom 50% (medians, untransformed):**

| feature | M/A | d = 30 HO1 | d = 30 HO2 | d = 60 HO1 | d = 60 HO2 |
|---|---|---|---|---|---|
| reach_d rate | M | 0.438 vs 0.141 | 0.475 vs 0.125 | 0.492 vs 0.119 | 0.496 vs 0.113 |
| dist_now (σ) | M | 2.50 vs 3.59 | 2.39 vs 3.59 | 2.19 vs 3.86 | 2.06 vs 3.73 |
| worst_so_far (σ) | M | 0.19 vs 0.50 | 0.15 vs 0.50 | 0.28 vs 0.82 | 0.22 vs 0.75 |
| best_so_far (σ) | M | 1.18 vs 0.26 | 1.27 vs 0.28 | 1.59 vs 0.36 | 1.71 vs 0.41 |
| mins_since_worst | M | 26 vs 14 | 27 vs 12 | 53 vs 23 | 54 vs 27 |
| bounce_from_worst (σ) | M | 1.11 vs 0.31 | 1.14 vs 0.32 | 1.54 vs 0.41 | 1.60 vs 0.46 |
| slope_10 (σ) | M | +0.21 vs −0.06 | +0.23 vs −0.02 | +0.14 vs −0.06 | +0.16 vs −0.03 |
| path_vol (σ per minute) | M | 0.19 vs 0.13 | 0.19 vs 0.13 | 0.18 vs 0.13 | 0.18 vs 0.13 |
| new_lows | M | 2 vs 5 | 1 vs 5 | 2 vs 7 | 2 vs 7 |
| new_lows_late | M | 0 vs 0 | 0 vs 0 | 0 vs 0 | 0 vs 0 |
| vol_since_dom (log ratio) | M | 1.09 vs 1.49 | 1.04 vs 1.38 | 0.82 vs 1.42 | 0.88 vs 1.21 |

A likely reverter at d has already been 1.2–1.7σ toward mu at its best, went less far against the trade (worst 0.15–0.28σ vs 0.50–0.82σ), set its worst point earlier, moved toward mu over the last 10 minutes (slope_10 median +0.14 to +0.23 vs −0.06 to −0.02), and has a more volatile path. Its dominant leg has traded less heavily since t0. These describe a spread that is already closer to mu, which dist_now captures on its own. new_lows_late is 0 at the median in both groups, so it carries little.

## What it says

- **Watching the first 30–60 minutes ranks raw reversion better, and only through where the spread now sits.** Knowing the current distance to mu cuts the flag share for an 80% catch by 3–4 points at 30 minutes and 8–9 points at 60, clearing in both halves. Everything else about the path adds 0.6–1.8 points on top, clearing nowhere. Same-learner comparisons agree. This is mostly barrier arithmetic: a spread already closer to mu is easier to reach. It ranks raw reach, not reversion beyond chance (next two bullets).
- **On episodes still open at d, features at d rank them better than features at t0:** by 4–5 points at 30 minutes and about 9 at 60, clearing in both halves. Most of that is dist_now: about 70% of the gain over vol-only at 30 minutes and about 90% at 60 (point-estimate shares; the paired point estimates add exactly). This is not a comparison of strategies. Deciding at t0 would include the early reverters, enter at a different price and face a different target. Whether waiting is a better trade is unmeasured.
- **Still no edge over chance.** The chance bar from minute d starts at the same distance, so it absorbs exactly what dist_now knows. Even the best-ranked fifth reaches mu less often than a random-sign path with the same steps. At 60 minutes the model still has to flag 55–57% of still-open episodes to catch 80% of reverters.
- **Few revert early:** 253 episodes (0.5%) by minute 30 and 762 (1.4%) by minute 60.

Nothing in the registry or the live system was touched. Nothing committed.

---

# DELAYED DECISION v2 — detection features refreshed at the decision point: NOT FOUND; refreshing adds nothing; dist_in_moves helps in HO1 only, 2026-10-13

Tag: **DELAYED-V2**. `delayed2.py`: `--stage refresh` (log `logs/delayed2_refresh.log`, 508s, writes `datasets/delayed2_refresh.npz`) and `--stage models` (log `logs/delayed2.log`, 196s). Refactors, behaviour proven unchanged by the gate below: `whyfeat.py` split into `prepare()` and `compute()`; `delayed.py` gained `path_features()`. Same populations, target (reach_d), path features, volume since t0, split and chance bar as DELAYED. t0 = initial detection; d = decision point (t0 + 30 / + 60 min). mu and σ stay frozen at t0 for the target. Rules and gap-fills fixed in the docstring before the run; Code Checker reviewed before the run.

**Gaps filled before the run:**
- Re-anchoring: bar J+k (k = d/30), entry_time + 30k; beta, alpha, mu, sigma and sign z stay at t0 (the frozen geometry the features are defined on). The dominant leg is re-derived at the new anchor. The 1m features use the original matched set.
- vol_slope_1m is not in the kept set, so it is not refreshed.
- **dist_in_moves = dist_now / (vol_48_1m_at_d × √(600 − d)).** The brief's × σ_t0 is dropped because dist_now and vol_48_1m are both already in frozen-σ units; keeping it would mix units (confirmed by Code Checker). It is a scaled distance, not a calibrated probability: mean |step| is not the step sd, and steps are not independent.
- z_roll_at_d is folded by sign(z at t0): positive = still on the dislocated side.
- **The downtick rule equals dist_now < 3 exactly** for still-open episodes (frozen |z| at d = need − seg[d] = dist_now; |z| ≥ 3 at t0, so being below 3 at d implies a crossing back).
- Separation score = single-feature AUC on train (no earlier run defined one).
- Learners as in DELAYED: full v1 and full v2 are each represented by the best of L1 + trees on val; position and position+ by L1 (the brief's bar). Same-learner diagnostics are printed beside every test, and any disagreement goes to the user (**none occurred**).
- Added after review: COMBINED importance groups, because t0, _at_d and _chg can rebuild one another, as can dist_now, dist_in_moves and z_roll. Family conclusions are read off the combined groups.

## Step 1 — the gate and the audit

| check | M/A |
|---|---|
| rebuilt W at k = 0 equals disloc.npz windows | M, **exactly** |
| k = 0 reproduces t0, values and NaN pattern, all 53,757: vol_48, vratio, vol_slope, sandwich, off_mark, vol_48_1m, 12 why-it-moved columns, beta, r2 | M, **all 20 exact (max diff 0)** |
| z_roll at k = 0 equals z_at_entry | M, exact |
| look-ahead, every family, k = 0, 1, 2 (index vs J+k; 1m minutes vs the anchor bar's close) | M, **+0 everywhere** |
| vol_48_1m reproduction ratio / vol_48 recomputation | M, 0.062 / ≤ 1.2e-07 at every k |
| refreshed missing → train median | M, 34–1,739 per column (largest vol_spike_ratio_1m_4_chg); full list in the log |

**Separation on train still-open (single-feature AUC; 0.5 = none, below 0.5 = lower values revert more):**

| feature | M/A | d = 30 | d = 60 |
|---|---|---|---|
| **dist_in_moves** | M | **0.292** | **0.260** |
| dist_now | M | 0.360 | 0.315 |
| z_roll_at_d | M | 0.373 | 0.341 |
| vol_48_1m_at_d / vol_48_at_d | M | 0.648 / 0.643 | 0.643 / 0.637 |
| vratio_at_d / sandwich_at_d | M | 0.612 / 0.616 | 0.628 / 0.614 |
| vratio_chg / r2_chg / sandwich_chg | M | 0.600 / 0.600 / 0.580 | 0.621 / 0.603 / 0.576 |
| vol_spike_mover_*_at_d / vol_spike_ratio_*_at_d | M | 0.470–0.481 | 0.451–0.480 |
| every other _at_d and _chg | M | 0.476–0.549 | 0.467–0.550 |

Medians for reverters vs non-reverters, every feature, are in the log. The strongest single feature is dist_in_moves, distance scaled by the volatility left. At d = 60, reverters' median is 1.31 typical moves against 1.98 for non-reverters. Among the changes, reverters' vratio falls less and their r2 falls less.

## Models (val log loss; every setting on val)

| model | M/A | d = 30 | d = 60 |
|---|---|---|---|
| vol-only L1 | M | 0.50317 | 0.49632 |
| position L1 (the bar) | M | 0.48428 | 0.45830 |
| position+ L1 | M | 0.48201 | 0.45516 |
| full v1 (rep.) | M | d1, 0.47591 | d2, 0.45181 |
| **full v2 (rep.)** | M | **L1, 0.47589** (50 of 78 nonzero) | **L1, 0.45054** (47 of 78) |

Several position+ and full v2 trees chose min_data_in_leaf at the grid edge (20 or 2000; flagged in the log). Both full v2 representatives are L1, so no verdict depends on that.

## The headline (held out): flag share / hit rate for still-open reverters

| d | half | model | M/A | catch 50% | catch 80% | catch 90% | top-20% hit |
|---|---|---|---|---|---|---|---|
| 30 | HO1 | vol-only | M | 0.350 / 0.343 | 0.656 / 0.293 | 0.796 / 0.272 | 0.374 |
| 30 | HO1 | **position** | M | 0.305 / 0.395 | **0.624** / 0.308 | 0.801 / 0.270 | 0.439 |
| 30 | HO1 | position+ | M | 0.306 / 0.394 | 0.610 / 0.316 | 0.791 / 0.274 | 0.443 |
| 30 | HO1 | full v1 (d1) | M | 0.296 / 0.406 | 0.610 / 0.315 | 0.760 / 0.285 | 0.438 |
| 30 | HO1 | **full v2 (L1)** | M | 0.294 / 0.410 | **0.614** / 0.313 | 0.770 / 0.281 | 0.447 |
| 30 | HO2 | vol-only | M | 0.336 / 0.360 | 0.638 / 0.304 | 0.787 / 0.277 | 0.390 |
| 30 | HO2 | **position** | M | 0.285 / 0.425 | **0.600** / 0.323 | 0.754 / 0.289 | 0.461 |
| 30 | HO2 | position+ | M | 0.284 / 0.427 | 0.596 / 0.325 | 0.751 / 0.290 | 0.464 |
| 30 | HO2 | full v1 (d1) | M | 0.281 / 0.432 | 0.582 / 0.333 | 0.736 / 0.296 | 0.475 |
| 30 | HO2 | **full v2 (L1)** | M | 0.279 / 0.434 | **0.586** / 0.331 | 0.741 / 0.294 | 0.470 |
| 60 | HO1 | vol-only | M | 0.349 / 0.338 | 0.658 / 0.286 | 0.795 / 0.267 | 0.365 |
| 60 | HO1 | **position** | M | 0.264 / 0.446 | **0.580** / 0.325 | 0.780 / 0.272 | 0.491 |
| 60 | HO1 | position+ | M | 0.255 / 0.462 | 0.566 / 0.333 | 0.765 / 0.277 | 0.495 |
| 60 | HO1 | full v1 (d2) | M | 0.258 / 0.457 | 0.570 / 0.330 | 0.738 / 0.287 | 0.492 |
| 60 | HO1 | **full v2 (L1)** | M | 0.253 / 0.465 | **0.569** / 0.331 | 0.743 / 0.285 | 0.493 |
| 60 | HO2 | vol-only | M | 0.338 / 0.348 | 0.643 / 0.293 | 0.791 / 0.268 | 0.372 |
| 60 | HO2 | **position** | M | 0.256 / 0.460 | **0.557** / 0.338 | 0.737 / 0.287 | 0.484 |
| 60 | HO2 | position+ | M | 0.255 / 0.461 | 0.552 / 0.341 | 0.718 / 0.295 | 0.493 |
| 60 | HO2 | full v1 (d2) | M | 0.253 / 0.465 | 0.552 / 0.341 | 0.720 / 0.294 | 0.496 |
| 60 | HO2 | **full v2 (L1)** | M | 0.257 / 0.458 | **0.549** / 0.343 | 0.703 / 0.301 | 0.495 |

All full v2 trees and the diagnostic trees are in the log.

**The downtick rule (dist_now < 3):**

| d | half | M/A | flag share | catch | hit | full v2 hit at the same share | position hit at the same share |
|---|---|---|---|---|---|---|---|
| 30 | HO1 | M | 0.349 | 0.463 | 0.319 | 0.391 | 0.381 |
| 30 | HO2 | M | 0.364 | 0.507 | 0.338 | 0.402 | 0.398 |
| 60 | HO1 | M | 0.385 | 0.573 | 0.351 | 0.397 | 0.388 |
| 60 | HO2 | M | 0.416 | 0.599 | 0.339 | 0.386 | 0.389 |

The downtick rule catches 46–60% of reverters by flagging 35–42% of still-open episodes. Ranking by the models instead raises the hit rate at the same share by 5–7 points (full v2) or 4–6 points (position). The rule is a cruder cut of the same quantity. These hit-rate gaps are point estimates with no interval. Full v2 and position sit within a point of each other at the same share (at d = 60 HO2 position is higher, 0.389 vs 0.386), which is the null test seen from another angle.

**Paired flag share at 80% catch, day-clustered 95% (A minus B; negative = A needs fewer flags):**

| comparison | M/A | d = 30 HO1 | d = 30 HO2 | d = 60 HO1 | d = 60 HO2 |
|---|---|---|---|---|---|
| **full v2 − position (THE TEST)** | M | −0.0098 [−0.0340, +0.0066] | −0.0135 [−0.0391, +0.0072] | −0.0111 [−0.0427, +0.0112] | −0.0081 [−0.0257, +0.0112] |
| **full v2 − full v1 (refreshing)** | M | +0.0037 [−0.0140, +0.0206] | +0.0040 [−0.0093, +0.0204] | −0.0007 [−0.0203, +0.0141] | −0.0025 [−0.0150, +0.0114] |
| **position+ − position (dist_in_moves)** | M | **−0.0140** [−0.0197, −0.0012] | −0.0042 [−0.0129, +0.0019] | **−0.0145** [−0.0296, −0.0050] | −0.0047 [−0.0099, +0.0078] |
| full v2 L1 − position L1 (diag) | M | identical to THE TEST (the representative is L1) | | | |
| best v2 tree − best position tree (diag) | M | −0.0042 [−0.0269, +0.0122] | −0.0127 [−0.0398, +0.0048] | −0.0067 [−0.0291, +0.0127] | −0.0095 [−0.0341, +0.0078] |
| full v2 L1 − full v1 L1 (diag) | M | −0.0027 [−0.0115, +0.0115] | +0.0057 [−0.0058, +0.0187] | −0.0099 [−0.0188, +0.0100] | +0.0023 [−0.0055, +0.0107] |
| best v2 tree − best v1 tree (diag) | M | +0.0000 [−0.0168, +0.0148] | +0.0016 [−0.0116, +0.0156] | +0.0000 [−0.0264, +0.0068] | −0.0013 [−0.0147, +0.0111] |
| best position+ tree − best position tree (diag) | M | −0.0034 [−0.0123, +0.0084] | −0.0040 [−0.0121, +0.0108] | −0.0131 [−0.0232, +0.0029] | −0.0012 [−0.0147, +0.0100] |
| position − vol-only (dist_now alone) | M | −0.0326 [−0.0564, −0.0117] | −0.0385 [−0.0672, −0.0194] | −0.0780 [−0.1042, −0.0377] | −0.0861 [−0.1166, −0.0594] |

| reading rule | M/A | result |
|---|---|---|
| **FOUND SOMETHING** (full v2 − position, both halves, d = 30 or 60) | M | **NO** at either d. Diagnostics agree (clear in neither). |
| REGIME-DEPENDENT (the test, one half) | M | none |
| **full v2 − full v1** (does refreshing add?) | M | **NO**: clears in neither half at either d. Diagnostics agree. |
| **position+ − position** (does dist_in_moves add?) | M | **NO; regime-dependent: HO1 only, at both d = 30 and d = 60.** The same-learner tree diagnostic clears in neither half; L1 vs L1 is the gating row itself. |

## Chance bar, full v2's top 20%

| d | half | M/A | still open: real / chance | top 20%: real / chance, gap [95%] |
|---|---|---|---|---|
| 30 | HO1 | M | 0.2405 / 0.2911 | 0.4474 / 0.5065, **−0.0591** [−0.0881, −0.0264] |
| 30 | HO2 | M | 0.2423 / 0.2805 | 0.4697 / 0.5123, **−0.0426** [−0.0718, −0.0077] |
| 60 | HO1 | M | 0.2354 / 0.2803 | 0.4929 / 0.5295, **−0.0366** [−0.0579, −0.0134] |
| 60 | HO2 | M | 0.2352 / 0.2770 | 0.4951 / 0.5415, **−0.0464** [−0.0847, −0.0071] |

Still below chance in every cell.

## Importance (held out, full v2 L1; log-loss skill points lost)

| group | M/A | d = 30 held out [95%] | d = 60 held out [95%] | clears both halves |
|---|---|---|---|---|
| **COMBINED position at d** (dist_now + dist_in_moves + z_roll) | M | **+5.23** [+4.51, +5.99] | **+11.81** [+10.64, +12.84] | yes, both d |
| **COMBINED refreshed family** (_at_d + _chg) | M | **+5.59** [+4.70, +6.38] | **+3.10** [+2.43, +3.67] | yes, both d |
| refreshed _at_d alone | M | +5.33 [+4.61, +6.04] | +2.74 [+2.16, +3.28] | yes, both d |
| dist_in_moves alone | M | +1.35 [+1.00, +1.68] | +5.21 [+4.42, +5.91] | yes, both d |
| dist_now alone | M | +1.63 [+1.15, +2.05] | +1.44 [+0.94, +1.85] | yes, both d |
| path shape | M | +0.94 [+0.58, +1.30] | +1.36 [+0.97, +1.77] | yes, both d |
| path_vol | M | +0.59 [+0.44, +0.76] | +0.40 [+0.28, +0.52] | yes, both d |
| t0 frozen | M | +0.40 [+0.05, +0.77] | +0.84 [+0.43, +1.33] | HO2 only, both d |
| changes _chg alone | M | +0.15 [−0.05, +0.35] | +0.22 [+0.05, +0.37] | HO1 only at d = 60 |
| path momentum | M | +0.09 [+0.01, +0.18] | +0.12 [+0.004, +0.24] | HO1 only at d = 60 |
| z_roll_at_d alone | M | +0.01 [−0.03, +0.03] | +0.06 [+0.01, +0.12] | HO2 only at d = 30 |
| volume since t0 | M | +0.01 [−0.01, +0.02] | +0.03 [−0.01, +0.06] | HO1 only at d = 60 |

Per-half intervals are in the log. The model leans heavily on the refreshed family, but mostly as a substitute for the frozen t0 features (t0 frozen falls from +7.8 in DELAYED to +0.4 here at d = 30). *Reading, not tested:* the refreshed family stands in for the t0 values; which members carry it was not measured (no member-level importance). The substitution does not improve the ranking (full v2 − full v1 is null).

## What it says

- **Refreshing the detection features at the decision point adds nothing.** Full v2 ranks still-open episodes no better than full v1 (DELAYED's model) and no better than the position bar, at 30 or 60 minutes, in either half. The like-for-like comparisons agree.
- **The model uses the refreshed features, but they substitute for the frozen ones rather than add to them.** *Reading, not tested:* the refreshed family at d does the work the t0 values did; which members carry it was not measured.
- **dist_in_moves (distance over the volatility left) is the best single variable on train** (single-feature AUC 0.71–0.74 read the other way: the more typical moves still to go, the fewer reverters), but on top of the position bar it helps only in HO1 (−1.4 points at both d) and not in HO2. Regime-dependent, not a pass.
- **The downtick rule is a crude version of the same thing.** It catches 46–60% of reverters at a 35–42% flag share; ranking by the models gives a higher hit rate at the same share (point estimates, no interval), with full v2 and position within a point of each other.
- **No edge over chance.** The best-ranked fifth still reaches mu less often than random-sign paths from the same starting point.

Nothing in the registry or the live system was touched. Nothing committed.

---

# CLOSED DECISIONS — recorded so they are not re-raised, 2026-10-13

Tag: **DECISIONS**. The user's decisions. Do not re-open them without a new brief.

| decision | A |
|---|---|
| **"Positive in both halves" means the 95% interval clears zero** in each half. A point estimate above zero never counts. This was the reading used in WHY-CHECKS. | A, user decision |
| **WHY-IT-MOVED adoption runs under "helps somewhere, harms nowhere"** (the user's prompt 3), not the original rule. The WHY-CHECKS reading rule ("real only if positive in both HO1 and HO2 at 3+ horizons") is not the adoption rule. | A, user decision |
| **Chop versus drift: record it** as a small measurement, a sign-flip null on 5-minute and 30-minute steps. Done in section CHOP-DRIFT below: mostly chop; no drift away from mu. | A, user decision |
| **Tree leaf-size range: do not widen.** REACH-MU, REACH-MU-V2, DELAYED and DELAYED-V2 all hit a min_data_in_leaf grid edge somewhere, and no verdict depended on it. | A, user decision |
| Pruning rule going forward (recorded in DELAYED): drop a group unless some model's validation interval is wholly above zero. | A, user decision |

---

# CHOP-DRIFT — the sign-flip shortfall is mostly chop, not drift; the mean move is slightly TOWARD mu, 2026-10-13

Tag: **CHOP-DRIFT**. `chopdrift.py`, log `logs/chopdrift.log` (32s). The user's decision (DECISIONS): a sign-flip null on 5- and 30-minute steps. Rules fixed in the docstring before the run. Matched 53,757; the folded move toward mu from t0's close, minutes 0..600, mu and σ frozen at t0; missing minutes bridged forward. For block size B the path is read at minutes 0, B, ..., 600, so the real path and the null see the same grid. Day-clustered 95% intervals.

| check | M/A |
|---|---|
| real reach on the 1-minute grid vs the saved target | M, agreement **1.0000** |

| group | M/A | n | mean 10h move toward mu, σ [95%] | B = 1: real / chance / gap [95%] | B = 5: real / chance / gap [95%] | B = 30: real / chance / gap [95%] |
|---|---|---|---|---|---|---|
| ALL | M | 53,757 | **+0.125** [+0.023, +0.222] | 0.231 / 0.298 / **−0.067** [−0.075, −0.059] | 0.217 / 0.262 / −0.044 [−0.052, −0.037] | 0.191 / 0.216 / **−0.026** [−0.034, −0.019] |
| train | M | 22,645 | −0.018 [−0.127, +0.107] | 0.224 / 0.307 / −0.083 [−0.093, −0.072] | 0.210 / 0.265 / −0.055 [−0.064, −0.045] | 0.184 / 0.217 / −0.033 [−0.042, −0.023] |
| val | M | 13,048 | +0.084 [−0.073, +0.234] | 0.226 / 0.297 / −0.071 [−0.085, −0.057] | 0.213 / 0.261 / −0.048 [−0.062, −0.034] | 0.185 / 0.213 / −0.029 [−0.042, −0.015] |
| HO1 | M | 8,200 | +0.147 [−0.164, +0.448] | 0.243 / 0.296 / −0.053 [−0.072, −0.027] | 0.228 / 0.263 / −0.035 [−0.055, −0.012] | 0.203 / 0.225 / −0.021 [−0.044, +0.003] |
| HO2 | M | 9,864 | **+0.492** [+0.233, +0.743] | 0.245 / 0.282 / −0.037 [−0.062, −0.016] | 0.231 / 0.252 / −0.021 [−0.044, −0.001] | 0.203 / 0.211 / −0.008 [−0.035, +0.013] |

| group | M/A | VR_1 [95%] | VR_5 [95%] | VR_30 [95%] | gap_30 − gap_1, paired [95%] |
|---|---|---|---|---|---|
| ALL | M | **0.597** [0.440, 0.765] | 0.588 [0.373, 0.874] | 0.805 [0.647, 0.940] | **+0.042** [+0.039, +0.044] |
| train | M | 0.480 [0.328, 0.749] | 0.427 [0.246, 0.863] | 0.704 [0.525, 0.961] | +0.050 [+0.046, +0.054] |
| val | M | 0.731 [0.682, 0.775] | 0.814 [0.761, 0.862] | 0.899 [0.832, 0.961] | +0.042 [+0.038, +0.047] |
| HO1 | M | 0.742 [0.548, 0.946] | 0.943 [0.790, 1.084] | 0.972 [0.822, 1.100] | +0.031 [+0.026, +0.037] |
| HO2 | M | 0.784 [0.660, 0.905] | 0.845 [0.717, 0.976] | 0.886 [0.785, 0.979] | +0.029 [+0.022, +0.036] |

VR_B = mean(final²) / mean(sum of squared B-minute steps): 1 for independent steps, below 1 when steps cancel. *Reading, not tested:* the intervals are wide because a few episodes with very large moves dominate both sums (with tails this heavy the fourth moment barely exists).

**Why VR_1 is the clean leg.** The gap is a difference of two probabilities that both fall as monitoring coarsens, so it can shrink partly from level compression alone. Drift can only raise final², so it cannot push VR below 1. Support that it is not just compression: the ratio real / chance moves toward 1 as well, from 0.775 (B = 1) to 0.831 (B = 5) to 0.882 (B = 30), on all rows (M).

| reading rule (all 53,757) | M/A | result |
|---|---|---|
| DRIFT AWAY (mean final move toward mu wholly < 0) | M | **NO** |
| DRIFT TOWARD (wholly > 0) | M | **YES**, +0.125σ; carried by HO2 (+0.49σ); train −0.02σ, not significant |
| CHOP (VR_1 wholly < 1 AND gap_30 − gap_1 wholly > 0) | M | **YES**: VR_1 0.60 (upper 0.77); the gap shrinks by 0.042 |
| shortfall surviving 30-minute steps (gap_30 wholly < 0) | M | **YES** on all rows (−0.026); not significant in HO1 or HO2 alone |

## What it says

- **The sign-flip shortfall is mostly chop, not drift.** Real spreads cover less net distance than their own steps would with random signs: the variance ratio at 1-minute steps is 0.60. Summing into 30-minute steps absorbs most of that cancellation, and the shortfall falls from −6.7 to −2.6 points.
- **There is no drift away from mu.** The average 10-hour move is slightly toward mu (+0.13σ), all of it from HO2 (+0.49σ); train shows none. The held-out block is a known favourable window (STATE s2), so DRIFT TOWARD on all rows describes that window, not a stable property. This replaces the old "drifts away from mu" reading, which the WHY-IT-MOVED correction had already withdrawn. The train figures Code Checker cited there as "Reading, not tested" (mean −0.02σ, VR_1 0.48) are now measured here.
- **A small shortfall survives 30-minute steps** (−2.6 points on all rows, clearing; not clearing in either held-out half alone). Some cancellation runs longer than 30 minutes, or there is a small effect the test cannot name.
- **What it means for the earlier results:** the "reaches mu less often than chance" and "below chance" statements in REACH-MU, DELAYED and DELAYED-V2 were measured against the 1-minute null and are **overstated**. That null overstates how far a random walk with these steps travels. Against a 30-minute null the shortfall is about 40% of the size (−0.026 vs −0.067). **The verdicts do not change, but not because the chance bar was only a reading tool:** it entered the STRONG rule (beyond-chance gap wholly > 0). STRONG also required flag share at 80% catch below 0.5, and that failed on its own in every cell (REACH-MU about 0.64; DELAYED 0.55–0.57 at 60 minutes).

Nothing in the registry or the live system was touched. Nothing committed.

---

# L1-WOBBLE — logistic L1 fits before 2026-10-13 were not exactly repeatable; no verdict affected

Tag: **L1-WOBBLE**. Found while rerunning DELAYED-V3. Fix approved by the user.

| finding | M/A |
|---|---|
| liblinear L1 with random_state unset shuffles randomly; max coefficient difference across unseeded refits (synthetic, 20,000 × 4) | M, 2.5e-05; seeded: 0.0 |
| position L1 at d = 30 refitted: DELAYED-V2 logged 0.48428, the v3 refit printed 0.48429 | M |
| DELAYED chose C 1.0 and DELAYED-V2 chose C 3.0 for the same position set at d = 30: a near-tie flip | M |
| smallest val-log-loss margin of any representative choice involving an L1, across REACH-MU, REACH-MU-V2, DELAYED and DELAYED-V2 (checked by Code Checker; REACH-MU's L1 vs best tree: 1.05e-3, 0.50161 vs 0.50266) | M, ≥ 2.2e-4, about twenty times the wobble; no choice could have flipped |

**Applies to:** every logistic L1 number in REACH-MU, REACH-MU-V2, DELAYED and DELAYED-V2. They carry a run-to-run wobble of about 1e-5 in val log loss and in the fitted scores. Every verdict rests on intervals hundreds of times wider, so none changes. Trees (LightGBM, deterministic) are unaffected.

**Fix from 2026-10-13:** `delayed.fit_l1` sets random_state=0. DELAYED-V3's refit gate checks the 15 deterministic trees exactly (5e-6) and the L1 fits within 1e-4.

---

# HL-BUILD1 — OKX retired; Hyperliquid bars built; STOPPED at the B2 missing-minutes gate

Tag: **HL-BUILD1**. Brief: docs/prompts/HL_BUILD1_BARS_AND_DISLOCATIONS.md (from the HyperLiquid Start planning session; user approved the full brief 2026-10-14). Logs in research/hyperliquid/logs/build1_*.log. Code Checker (Code Checker 2) passed every step listed.

**Part A: OKX retired.** (build1_a1_vm.log, build1_a2_files.log)

| finding | M/A |
|---|---|
| VM snapshot at 2026-10-14T18:13Z: equity 74.72, 10/10 positions open (9 up, 1 down), unrealized +6.51; positions left frozen, no synthetic closes | M |
| VM crontab: 3 lines removed (vm_housekeeping, vm_scan_cycle, collect_oi), backup ~/crontab.bak.20261014; `docker compose -f docker-compose.trading.yml down` removed pairs-stop-monitor and pairs-dashboard; instance left RUNNING | M |
| last scan cycle 18:05:50Z; last OI poll 18:20Z | M |
| final pull, VM static: ledger rows 2,043 local = 2,043 VM (no change between pulls); scan_history 32 = 32; OI day files 7 = 7 | M |
| moved to attic/: 7 OKX scripts and 3 adapters (git mv), user_data/data/okx (2.3 GB) to attic/okx_data/, 24 research/datasets entries (297 MB) to attic/okx_datasets/; both gitignored | M |

**Part B: Hyperliquid.**

| finding | M/A |
|---|---|
| asset_ctxs files 20250101..20261013: 650 (20260708 missing entirely), 6.4 GB lz4 (build1_raw_coverage.log) | M |
| B0 timestamp: best lag -1 min on all 5 coins (BTC 0.9982, ETH 0.9962, SOL 0.9897, HYPE 0.9955, DOGE 0.9357; margin over next lag ≥ 0.856; n 1,054 each), so row stamped T = close of the 1m bar labelled T-1m. PASS (build1_b0_timestamp.log) | M |
| B0 gap-fill: no full archive day lies inside the candle window, so 20261012 + 20261013 were used (1,056 stamps) | A |
| B2 gap-fill: 39,341 off-minute rows on 192 stamps dropped; each is its floor minute's snapshot taken 1-59 s late, so labelling it on the minute would be look-ahead (build1_offminute.log) | M |
| coins: 234 in coins.csv; 12 never have a valid mid (no files); 222 with bars; 56 delisted (44 with last valid mid before 2026-10-13, plus the 12), 178 live; 156 listed from 2025-01-01, 66 later | M |
| delisted flag corrected from 0 to 56 after run 3: the archive keeps delisted coins as empty-mid rows to the end (build1_corrections.log) | M |
| archive minute grid: 907,268 of 936,403 minutes present; 29,135 archive-wide missing | M |
| 30m close == 1m close at date+29, asserted on all 5,543,390 bars of 222 coins | M |
| filled (runs ≤ 5) 33,997 minutes; NaN 5,144,235 of 166,298,904 listed minutes; 6,354 long runs, **all archive-wide, 0 coin-specific** | M |
| missing share by month (BTC as the archive-wide profile): ≤ 0.001 for 2025-01..2026-04 and 2026-06; 2026-05 0.023, 07 0.032, 08 0.064, 09 0.284, 10 0.636 (October measured over the 17,683 in-window minutes) | M |
| **GATE: 178 of 222 coins (80.2%) have > 1% of listed minutes filled or NaN; threshold 5% → STOP.** With archive-wide minutes removed (receipt only), 0 of 222 | M |
| on disk, not uploaded: futures 1.79 GB, ctx 6.94 GB; raw cache kept in ~/.cache/hl_asset_ctxs | M |
| AWS cost: about $0.60 (6.4 GB requester-pays transfer); Cost Explorer showed $0 on 2026-10-14 because it lags | A |

**Not done, per the STOP:** B3 candle check, B4 dislocation set, the data_loader and envelope swap, the normalized-store rebuild, the S3 copy, deleting the raw cache.

---

# HL-BUILD2 — Hyperliquid bars and flow from the trade archive; the adaptive-trigger dislocation set

Tag: **HL-BUILD2**. Brief: docs/prompts/HL_BUILD2_TRADES_TO_BARS_AND_FLOW.md (HyperLiquid Start; user approved 2026-10-14), plus decisions relayed by the planner on 2026-10-15: the adaptive trigger, rule (iii) + (i) for archive gaps, old-format holes (a), and the execution-order tie-break. Logs in research/hyperliquid/logs/build2_*.log and research/dislocation_model/logs/mkdisloc_hl_adaptive.log. Code Checker (Code Checker 2) passed every step. **Results in this section are on Hyperliquid data, window 2025-05-25 14:32 to 2026-10-13.**

**Part C: housekeeping** (build2_c1_vm.log, build2_c2_launchd.log, build2_c3_cleanup.log)

| finding | M/A |
|---|---|
| GCP VM `pairs-trading` and its 20 GB disk deleted 2026-10-14T19:20:56Z; instances, disks and addresses lists all empty | M |
| VM tree archived first: attic/vm_final/vm_final_20261014.tar.gz, 307,771,513 B, sha256 781b1004…578c65a equal on both sides; 22,273 files / 555,756,735 B equal (excluding 73 macOS `._*` files) | M |
| Artifact Registry repo `pairs-trading` (231 MB) left in place, as the brief says | M |
| launchd `com.pairtrading.update-data` booted out (exit 0), plist moved to attic/launchd/; `com.pairtrading.scanner` not loaded, left | M |
| build-1 mid-price bars (444 files, 1.79 GB) and the raw asset_ctxs cache (6.4 GB) deleted after the 222 ctx files were checked | M |

**Part D: bars and flow from trades**

| finding | M/A |
|---|---|
| archive: old format 64 days / 1,507 hour files / 31.8 GB lz4; by-block 445 days / 10,667 files / 310.1 GB; window total 341.0 GB (build2_d_archive_listing.log) | M |
| window starts at the archive's first fill, 2025-05-25 14:32 (first fill 14:32:53.109). The user's earlier 14:00 start was moved by the planner's (a), applying "archive gaps are missing" | M |
| folder hour is not fill hour: spill-over up to 217 ms early, 0 late (pilot); each day reads its own 24 files plus the next day's hour 0 | M |
| exactly 1 taker per tid on every pilot day; dedupe on (tid, wallet) removed 0 (the 2025-07-27 "overlap" hour shares no fill) | M |
| universe: perps only; dropped '@' and '/' (spot), '#' (outcome), ':' (HIP-3), as the planner confirmed under the existing perps-only decision | A |
| tie-break for same-ms fills: EXECUTION ORDER (file → line → event in block). The brief's tid tie-break gave a 91% median close match against Hyperliquid's candles with 100% volume match (build2_d2_candles.log). By the candle's trade count: n=1 99.99%, n=2-5 90.5%, n>5 84.0% (build2_d2_nsplit.log). On 2026-10-13, tid matches 6 of 178 coins ≥ 99% against 178 of 178 for execution order (build2_d2_order_diag.log). Corrected as a brief bug (planner) | M |
| stage 1 (final): 507 days, all exit 0; 3 × r7g.4xlarge by date range, 11-14 min per part (part1 spot was interrupted and rerun on-demand); merged 507 × 3 files (build2_d2_run.log) | M |
| MISSING TIME, 114 of 729,208 minutes = 0.0156% (gate 0.1%) → PASS: 10 block gaps (54 blocks), 1 duplicate block (706113001, 2025-08-23 08:48:17 → 08:57:37, 10 min), 3 old-format file holes (the 14:32 window-start minute; 2025-06-08 09:44 → 10:27, 44 min; 2025-07-19 09:53 → 10:16, 24 min), the format switch (2025-07-27 08:45:48.7 → 08:49:59.4, 5 min) | M |
| GAP-FILL: the minutes between a duplicate block's two copies are marked missing | A |
| report only: 46 chain halts (consecutive blocks > 60 s apart; mostly ~1m10s on weekend mornings), kept as real quiet minutes; 53 market-wide empty old-format minutes remain after the file-edge rule, so there are holes inside old files that cannot be seen | M |
| CLOSES, rule (iii) (user, 2026-10-15): a close is NaN only if a hole lies between its last trade and the bar end. GAP-FILL: done at minute resolution, so a hole sharing the last trade's minute also invalidates the close | A |
| 30m NaN closes: 929 coin-bars under rule (iii), against 2,783 bars touching a hole; 32 distinct timestamps; 5 seams with ≥ 50% of live coins NaN (2025-06-08 09:30 and 10:00, 2025-07-19 09:30, 2025-07-27 11:30, 2025-09-27 09:00) | M |
| stage 2: 206 coins, 4,386,491 30m bars, every bar asserted (close == 1m close at H+29, open == 1m open at H, high/low/volume/notional == the 1m resample). 3:56 wall with 16 workers; output identical to the serial run (4 pilot days, sha256) | M |
| flow table: research/hyperliquid/flow/{COIN}.parquet, 206 files, 4,160,463,543 B on pt-research = S3 (build2_d2_rerun_pull_and_d2.log). Columns: n_trades, taker_buy_usd, taker_sell_usd, n_taker_wallets, open_taker_usd, close_taker_usd, twap_taker_usd (NaN before 2025-07-27 08:00), top3_taker_share, liq_forced_long_usd, liq_forced_short_usd, backstop_liq_usd, adl_usd; NaN on hole minutes. Unaffected by the tie-break change apart from being regenerated | M |
| D2 against Hyperliquid's candles (178 listed coins, ~3,460 min each): close match p0 0.9779, p50 0.9997, volume 100%; 177 of 178 ≥ 99% → PASS. SOPH 0.978 overall but 0.998 on traded minutes: a no-trade-minute definitional edge | M |
| coins: 206 with trades against build 1's 222; the 16 dropped were all delisted before 2025-05-25 (build2_coin_diff.log) | M |

**Part E: dislocation set, adaptive trigger** (mkdisloc_hl_adaptive.log)

| finding | M/A |
|---|---|
| trigger (user, 2026-10-15): fresh crossing of |z| above the 99th percentile of the pair's own |z| over the previous 96 bars; no absolute floor; everything else unchanged | A |
| panel 24,305 bars × 206 tickers (2025-05-25 15:00 → 2026-10-13 23:00; drop_forming_bars removed the 23:30 bar, covered by only 149 coins because lives end at each coin's last trade); 20,706 pairs; shortest usable segment 356 bars | M |
| 60,004 dislocations (the last pair overshoots 60,000), 3,004 distinct pairs, 473 days, 49 pairs too short; invariant max \|W[:,-1] − z\| = max \|Y[:,0] − z\| = 0; nan_windows asserted 0 | M |
| 70/30 day split at 2026-05-25: fit 41,941, held-out 18,063 | M |
| segments: 2,438 pairs split by NaN closes; 12,103 segments used, 407 too short; warm-up lost per split pair median 1,340 bars (~28 days), max 2,607; 0 pairs fully lost | M |
| seams: dislocations in the 14 days after a seam fall sharply after the two old-format seams (06-08: 2,330 → 615; 07-19: 1,964 → 76, as the 07-27 seam falls inside the warm-up), and hold roughly level after 07-27 (751 → 862) and 09-27 (1,412 → 1,164). The dips are option (i)'s warm-up; nothing piles up at the seams | M |
| threshold_at_entry p5/25/50/75/95: 1.260 / 1.744 / 2.118 / 2.539 / 3.259; \|z_at_entry\| 1.481 / 2.021 / 2.468 / 3.011 / 4.097; \|z\| < 2: 23.9%, 2-3: 50.7%, ≥ 3: 25.4% | M |
| true triggers per pair: median 386; per pair-month median 25.0 (mean 24.5, p95 35). The adaptive rule fires about daily per pair | M |
| stale: either leg ≥ 30 min since its last trade at the trigger bar: 0.79% (474) | M |
| beta_stab p5/50/95: 0.198 / 0.845 / 9.726; NaN for 3,375 (5.6%): triggers whose fit window starts before the segment's first finite beta | M |
| coins used 204 (BTC and ETH factor-only), 31 delisted coins included; long 50.8%, short 49.2% | M |
| per month: 2025-06 4,148 … 2026-10 2,841 (17 months, ~2,800-4,150 each) | M |

**Cost:** AWS ≈ $4-5 to date: EC2 ≈ $1.6, S3 transfer to GCP ≈ $2.5 (ctx and two bar/flow pulls), requester-pays requests a few cents; bucket 88 GB ≈ $2.2/month. Cost Explorer showed no data on 2026-10-15 because it lags. GCP: trial credits, ≈ $0.36/h while pt-research runs plus ≈ $10/month disk | A |

**Superseded but kept for provenance:** s3://…/build2/d1/ (tid tie-break bars, plain and rule-(iii) asm) and build2/code_d1_tid/. Deleting them saves ~45 GB.

---

# HL-FLOW1 — do flow features beat position? H1 / H2 / H3 and the market block

Tag: **HL-FLOW1**. Brief: docs/prompts/HL_BUILD3_FLOW_FEATURES_H1_H2_H3.md (HyperLiquid Start; user-approved 2026-10-15; I also confirmed the commit and the spend with the user directly). Logs in research/dislocation_model/logs/hl3_*.log and research/hyperliquid/logs/build3_*.log. Code Checker (Code Checker 2) passed every part. Verdict: the flow features add nothing to position on held-out data (0 of 210 cells), and the reference itself shows no beyond-chance edge. **Window and data: HL-BUILD2's, 2025-05-25 14:32 to 2026-10-13.**

**Part 0: commit and the side × dir flow columns**

| finding | M/A |
|---|---|
| build 2 committed locally on branch feat/hyperliquid-build2, commit 101624b, 86 files, not pushed. Left out on purpose (older or mixed work): CLAUDE.md, harness/envfeat/paths, envelope.py and the other untracked research files, the planner's docs, open_positions.json, the scripts/download_1m.sh rename. NUMBERS.md staged as HEAD + the three build 1/2 pieces only | A |
| stage 1 rerun with open_buy_usd, open_sell_usd, close_buy_usd, close_sell_usd: 507 days, all exit 0, on 3 × r7g.4xlarge **on-demand** (InstanceLifecycle None, checked); wall 13:34 / 13:10 / 11:07 min; stage 2 4:04 min; `check` empty after each. The side × dir sum identities are asserted on every row inside stage 1 | M |
| stage 2 gate unchanged: 114 of 729,208 missing minutes (0.0156%), 929 NaN 30m coin-bars (2,783 touching a hole), 32 timestamps, 206 coins, 4,386,491 bars asserted | M |
| comparison against the build 2 files (build3_part0_swap.log): 206 flow files / 131,600,580 rows, every old column bit-identical (0 differences); the new columns satisfy the identities on every non-NaN row, max abs error 2.98e-08 USD; 412 bar files equal. Flow table 6,071,182,484 B (was 4,160,463,543), equal to S3 | M |

**Part 1: split, target, chance bar, reference** (hl3_split.log, hl3_paths.log, hl3_reference.log)

| finding | M/A |
|---|---|
| split from the meta's day column only: CUT 2026-05-25 (fit 41,941 / held out 18,063, 142 days); HO1 = held-out days up to 2026-08-14 (9,057 rows, 82 days), HO2 from 2026-08-15 (9,006, 60 days) | M |
| population: 1-minute window exists for 60,004 of 60,004; finite on all 601 minutes 59,759; 245 (0.41%) lost to archive holes. Train 33,180, val 8,516 (validation cut 2026-03-20 on the matched population; 2026-03-19 on all rows), held out 18,063 | M |
| reach (depth ≥ \|z\| on 1-minute closes, mu frozen, no stop, 10h) = 0.3294 (19,685 of 59,759), asserted equal to the 10h MFE (max diff 0); mean chance probability (50 sign-flip seeds) 0.4464. The 30-minute-grid reach 0.2686 (3,633 episodes reach on 1-minute closes but not on the grid, none the other way) | M |
| reach rate against chance: train 0.3323 / 0.4709; val 0.3383 / 0.4400; HO1 0.3203 / 0.4197; HO2 0.3195 / 0.3892; \|z\| < 2: 0.4358 / 0.5449; 2-3: 0.3188 / 0.4448; ≥ 3: 0.2504 / 0.3569. Reach is below the sign-flip chance probability everywhere, consistent with the 1-minute chop seen on OKX (CHOP-DRIFT); not a below-chance signal | M |
| liquidation headroom at 20x: median 8.47 entry sigma; reverters hitting liquidation before mu 104 of 19,685 | M |
| reference (logistic on log vol_48, log vol_48_1m, log sigma, \|z\|): coefficients 0.457 / 0.183 / −0.030 / −0.453; val log loss 0.59723 (base rate 0.63999). Held out HO1 / HO2: AUC 0.6897 / 0.6886; flag share at 80% catch 0.629 / 0.630 (random 0.80); top-20% hit rate 0.536 / 0.531; beyond-chance gap at 80% catch −0.0968 [−0.1156, −0.0780] / −0.0658 [−0.0923, −0.0365] | M |
| **GATE: the reference's beyond-chance gap wholly above zero in both halves: NO.** The reference finds no beyond-chance edge, as on OKX. vol_48_1m checks: last minute read entry+29; reproduction 0.062 of budget; vol_48 from the 1-minute marks max diff 4.49e-08 | M |

**Part 2: the feature matrix** (hl3_flowfeat_build.log, hl3_flowfeat_validate.log)

| finding | M/A |
|---|---|
| 27 model inputs: H1 6, H2 6, H3 4, H3-TWAP 2, MARKET 9; context columns lone_mover (0.726 of rows), driver_is_A (0.483), flag_gap, hole60; net-weight NaN 0. flowfeat.npz (60,004 × 27) joined to disloc_meta by row position; flowfeat_legs.npz keeps the leg values and the un-normalised wallets_per_musd | M |
| NaN share: H1 and H2 0.31% (30m) / 0.07% (60m), open_close_ratio 0.98% / 0.44%; H3 0.31-0.34% / 0.07-0.08%; TWAP 11.90% / 11.68% (finite on 52,863 rows; NaN before 2025-07-27 08:00); MARKET 0.00%, liq_usd 0.04% / 0.07%, liq_7d_ratio 4.92% | M |
| flag_gap = 474 rows (stale legs). The span of no dislocation touches a seam bar (0), because a dislocation's fit + outcome span must be finite, so it cannot contain a bar where ≥ 99% of coins are NaN. 40 rows have a hole minute in [C−60, C) | M |
| validator: 500 random rows × 27 features = 13,500 comparisons from independent direct sums on arrays truncated at each row's cutoff; 0 mismatches, max abs diff 4.71e-04 (relative tolerance on large ratio values) → PASS | M |
| **Normalisation, a decision (planner, 2026-10-15):** dollar-scaled quantities (wallets_per_musd, the market liquidation total) are divided by their trailing 7-day median; ratios (the shares) are not. **Gap-fills:** flag_gap's seam clause uses the bar labels [T−335, T+20]; market_liq_7d_ratio is the per-valid-minute form of the 7d/28d ratio; the builder reads one coin at a time, not event windows only (the 7-day normalisers need history) | A |
| **Proxy caveat:** h3 top3 (notional-weighted mean of per-minute top-3 shares) and wallets_per_musd (per-minute distinct wallets summed over the window) are PROXIES, not window-level concentration | A |
| the backstop and ADL shares are almost always zero: nonzero rows train 116 / 59 (of 33,180), val 2 / 0, HO1 1 / 0, HO2 8 / 3 (hl3_nonzero.log). The forced share is nonzero on 15.6% of train, 12.7% of val, 13.8% of HO1 and 23.1% of HO2 rows. So H1's backstop and ADL features cannot be tested on held-out data | M |

**Part 3: the tests** (hl3_tests.log)

| finding | M/A |
|---|---|
| design fixed before any fit: 7 scored sets × 5 models × 2 halves × 3 measures = 210 cells; expected by chance at 95% two-sided 10.5 (5.3 in the good direction) | A |
| pruning on validation (ALL set, L1 and depth-2 tree): H1 drop, H2 keep (depth-2 interval [+0.0336, +0.1289]), H3 drop, MARKET keep (L1 interval [+0.0402, +0.2643]); KEPT = reference + H2 + MARKET | M |
| the KEPT set (reference + H2 + MARKET) has a WORSE validation log loss than the reference's best model (0.59486 against 0.59401): the pruning rule keeps a group when any one model's permutation interval is wholly above zero (as the user wrote it), so a kept group need not improve the fit. Report only | M |
| validation log loss of each set's best model: reference 0.59401 (d2); H1 0.59424; H2 0.59377; H3 0.59327; MARKET 0.59539; ALL 0.59462; KEPT 0.59486; H3-TWAP 0.59472 (reference on the same rows 0.59474) | M |
| **Result: 0 of 210 cells wholly on the good side, 0 on the bad side** (chance would give about 5 each). No set's representative model clears flag share at 80% catch in either half; reading rules give "no help" for H1, H2, H3, MARKET, ALL, H3-TWAP and KEPT. Differences against the reference are within ±0.006 (flag share), ±0.012 (top-20% hit rate), ±0.004 (gap) | M |
| same-learner diagnostics (L1 − L1; best tree − reference best tree): no set clears both halves; no disagreement with the gating test | M |
| permutation null (20 seeds, flow block row-permuted): the observed flag-share difference is below the null's minimum in 2 of 12 representative-half cells (H2 d4 HO1: −0.0032 vs −0.0031; ALL d3 HO2: −0.0020 vs −0.0007), each in one half only; 1 in 21 per cell is expected (about 0.6 of 12) | M |
| direction check (held-out correlation of each feature with the reference's residual): forced share + in HO1 only (+0.0192 [+0.0033, +0.0370], HO2 −0.0055); open push, open/close ratio − in HO1 only (e.g. ratio_60 −0.0278 [−0.0497, −0.0072]); TWAP share_30 + in HO2 only (+0.0257 [+0.0049, +0.0496]); H3 top3 and wallets, and all MARKET features: intervals include zero. Flagged "WRONG DIRECTION" in one half: backstop share HO2 (−0.0150, 8 nonzero rows) and ADL share HO2 (−0.0138, 3 nonzero rows); both rest on a handful of rows (the HO1 "ok" for backstop share rests on 1 nonzero row) | M |

**Part 4: the 10 October 2025 cascade** (hl3_crash.log; descriptive, fit period)

| finding | M/A |
|---|---|
| dislocations with trigger time in 2025-10-10 20:00 – 2025-10-11 02:00: n 194, reach 0.5103 against chance 0.6478 (gap −0.1375). By forced-share tercile (low / mid / high): reach 0.339 / 0.563 / 0.631, chance 0.568 / 0.705 / 0.671, gap −0.229 / −0.143 / −0.041. The 3 hours before: n 32, reach 0.3125, chance 0.8912 | M |
| pre-registered row: BTC fell > 5% in 30 minutes at only 9 minutes (the 2025-10-10 21:15-21:25 cluster, BTC low −10.1%, and one minute on 2026-02-06). Episodes within 3 hours after a shock: n 140, reach 0.6071, chance 0.5419, gap +0.0653; the rest n 59,619, gap −0.1175; difference of gaps +0.1827, day-clustered 95% [+0.0221, +0.2410] with only 266 of 300 resamples valid. **The interval is not meaningful: the 140 regime episodes fall on 3 calendar days (2025-10-10, 2025-10-11, 2026-02-06).** Descriptive, fit period, not a finding; one event drives this | M |
| hole check: 0 archive hole minutes in 2025-10-10 17:00 – 2025-10-11 03:00; the nearest seam is 13 days away | M |

**Cost** (estimates; Cost Explorer lags): AWS ≈ $2-3 for build 3: EC2 on-demand ≈ $1.0, transfer of the flow table and bars to Google Cloud ≈ $1.2-1.5; S3 +20 GB ≈ $0.5/month. GCP: trial credits | A

# HL-EVENT1 — coin-level event study: does flow precede triggers, does it predict reach, what happens after

Logs: hl4_coinevents.log, hl4_eventflow.log, hl4_evvalid.log, hl4_eventstudy.log (+hl4_profile.png), hl4_impact.log, hl4_tests.log, hl4_after.log (+hl4_after.png). Tags: M = measured in the log, A = assumed / stated rule.

**Part A: events and controls** (hl4_coinevents.log, hl4_eventflow.log, hl4_eventstudy.log)

| finding | M/A |
|---|---|
| 74,607 triggers over 204 coins, no cap (74,326 with a 10h outcome window; segments 924; per coin min 29 / median 405 / max 483). Long 59.3%, short 40.7%. \|z\| < 2 23.8%, 2-3 52.6%, ≥ 3 23.6% | M |
| target population (1-minute window finite): 73,967; lost to holes 359 (0.48%). reach 0.3223, mean chance 0.4372, gap −0.1150. fit gap −0.1355, HO1 −0.0681, HO2 −0.0642. 1-minute path reproduces the 30m z, max abs error 3.4e-13 | M |
| controls set 1 (matched, far from triggers): 370,125 links, 4.96 per event, 305 events (0.41%) with none. Set 2 (near-miss): 152,784 links, 2.05 per event, **22,927 events (30.73%) with none** — set 2 is thin | M |
| 103 events have an unknown volatility decile; 1,169 (1.57%) have a non-finite C24 flow window; 230,282 of 264,699 near-miss candidates were removed by the ±24h exclusion | M |
| validator (evvalid.py, 500 events + 500 links, arrays truncated at the cutoff): 60,000 comparisons, 0 mismatches → PASS | M |
| 160 cells (8 series × 5 windows × 2 sets × 2 held-out halves); 108 intervals exclude zero (chance 8.0); findings (same sign, both halves): 31 of 40 (chance 0.05 expected by chance under independence) | M |
| Q1, set 1, both halves: imbalance elevated before triggers in P1, P2, C6, C24 (e.g. P1 HO1 +0.0589 [+0.0469,+0.0713], HO2 +0.0752 [+0.0566,+0.0903]); opening push elevated in P1, P2, C6, C24; forced share elevated in P1 and C6 (P1 +0.0013/+0.0016 of taker notional); volume elevated in P1 only (+1.68/+2.74 × its trailing median) and **below** normal in P3 and C24 (opposite to the stated direction); top3 lower in P1; wallets lower in P1, P2, C6 and higher in P3; twap lower in P3; close: one half only | M |
| set 2 agrees in sign on imbalance (all four windows) and opening push (P1, C6, C24) | M |
| **Wording:** flow in the trigger's direction (imbalance, opening push) is elevated before triggers against both control sets. Signed imbalance co-moves with price by construction, so this shows the move was taker-driven; it does not separate flow from the price move that defines the trigger | A |
| **Caveat:** wallets and volume are heavy-tailed ratios; their intervals are wide and not stable (wallets P1 HO2 −1.75 [−4.16,−0.35]; wallets P2 fit +2.09 [+0.003,+6.42] against HO1/HO2 about −0.05). Read the sign, not the size | M |

**Part B: the impact model and the tests** (hl4_impact.log, hl4_tests.log)

| finding | M/A |
|---|---|
| impact model, fit period only, 2,994,639 bars, 200 coins, coin fixed effects: imbalance +0.2138 (se 0.0014), signed forced +0.3443 (se 0.0309); within-coin R² 0.0079 (held-out display 0.0128). At triggers, explained_share median 0.011 (p10 −0.105, p90 0.127), unexplained_move median +1.479σ | M |
| reference logistic at coin level: gap at 80% catch HO1 −0.0663 [−0.0937,−0.0404], HO2 −0.0614 [−0.0928,−0.0343]; gate NO (reach does not beat chance) | M |
| pruning kept VOLUME, IMPACT, MARKET. Validation log loss: ALL d1 0.57135, KEPT d1 0.57101, reference d1 0.57621 | M |
| design fixed before any fit: 270 cells, 13.5 expected by chance (6.8 each side). **Result: 40 good-side, 1 bad-side** (the bad cell: MARKET L1 HO2 top20 −0.0186). Good-side cells are almost all flag share at 80% catch; top-20% hit rate and beyond-chance gap are mostly inside zero | M |
| ALL and KEPT clear flag80 in both halves for every tree depth (e.g. ALL d1 HO1 −0.0190 [−0.0259,−0.0056], HO2 −0.0218 [−0.0383,−0.0081]; KEPT d2 −0.0181/−0.0300) and gap80 in both halves for ALL d3, ALL d4, KEPT d3 (e.g. KEPT d3 +0.0070 [+0.0002,+0.0140] / +0.0093 [+0.0015,+0.0182]). The gap gain is +0.007 to +0.012 on a reference gap of −0.066 / −0.061 | M |
| reading rules: ALL HELP and KEPT HELP, but not equally robust. **ALL: HELP, robust to the same-learner check** (representative d1 clears flag80 against the logistic reference, −0.0190 / −0.0218, and against d1 without flow, −0.0131 / −0.0127, and sits below the permutation null's minimum in both halves). **KEPT: HELP against the logistic only** (its d1 does not clear against d1 without flow; one of the three disagreements, for the user). Size: ALL needs about 2 percentage points fewer flags to catch 80% of reverters (flag share about 0.6); the beyond-chance gap improves +0.007 to +0.012 but stays negative, so flow helps rank reverters and creates no edge over chance; MARKET, FORCED, CONCENTRATION, IMPACT regime-dependent (one half); OPENCLOSE, VOLUME, CONC-TWAP no help | M |
| same-learner diagnostics: only ALL d1 − d1 clears both halves (HO1 −0.0131 [−0.0203,−0.0015], HO2 −0.0127 [−0.0286,−0.0017]). Three disagreements with the gating test: ALL L1, KEPT L1, KEPT d1 clear against the logistic reference but not against the same learner without flow — part of the gain is the model class | M |
| permutation null (20 seeds): observed flag80 gain below the null's minimum in both halves for ALL d1 (−0.0190 vs −0.0075, −0.0218 vs −0.0088) and KEPT d1 (−0.0123 vs −0.0076, −0.0222 vs −0.0084) and MARKET d1; one half for FORCED, CONCENTRATION, VOLUME, IMPACT | M |
| direction check: no expected-sign feature has a wholly wrong-sign interval in either half ("WRONG DIRECTION: none"). Forced +, open −, close +, unexplained_move + (HO1 +0.0526 [+0.0241,+0.0794], HO2 +0.0303 [−0.0021,+0.0608]) are inside zero or right-signed. Two-sided: top3_C24 and wallets_C24 + in HO1; twap − in HO1 only; mk_idx + in HO2 only | M |
| **B4 strong-event cut** (\|z\| ≥ 3 or forced P1 > 0; n 20,872; reach 0.2506; restricted reference gap −0.0150 HO1, −0.0517 HO2): **0 good-side hits of 42 cells** (1.1 expected); 1 bad (MARKET d4 HO1 top20 −0.0353) | M |
| Nothing in the flow features turns the coin-level reference into a gate pass (the reference gap stays negative; adding features moves it by about +0.01) | M |

**Part C: after the trigger** (hl4_after.log)

| finding | M/A |
|---|---|
| post-trigger flow over (0,+60] finite for 74,402 of 74,607 events | M |
| C1 (descriptive, CONDITIONED ON THE OUTCOME, not predictive): the only separation between reverters and non-reverters is the price itself (residual −0.69σ at +60, −3.2σ at +600, both halves); imbalance and opening push differ by ≤ 0.03 with intervals through zero except imbalance at +300 in HO1 only; forced differs by ≤ 0.0005 | M |
| first hour by what pushing flow did: continued (imbalance > 0) HO1 n 4,692 gap −0.1166 [−0.1413,−0.0892], HO2 n 3,508 gap −0.1024; dried up (post notional < 0.5 × pre) HO1 n 2,928 gap −0.0204 [−0.0488,+0.0110], HO2 n 1,976 gap −0.0366 [−0.0639,−0.0065]; flipped (< 0) HO1 n 5,228 gap −0.0516, HO2 n 3,622 gap −0.0432. Flow that continues has the worst reach against chance; flow that dries up the best. The category is known at +60; C2 tests whether first-hour flow adds to a +60 decision and finds no help (0 of 30 cells). Counts add up to the population: HO1 4,692 + 2,928 + 5,228 + 24 with undefined post-flow (n/a) = 12,872; HO2 3,508 + 1,976 + 3,622 + 1 exactly zero + 17 n/a = 9,124 (hl4_after.log) | M |
| C2 delayed decision at +60 min: 73,967 events, 2,180 already at mu (set aside), 71,787 open. reach 0.3017, chance 0.4195, gap −0.1178. Reference logistic AUC 0.7470 HO1 / 0.7464 HO2, gap80 −0.0774 / −0.0652. 30 cells, expected 1.5: **0 good-side**. Add-on models vs reference flag80: all intervals through zero (e.g. d2 HO1 −0.0026 [−0.0081,+0.0072]). Reading: not helped | M |

**Gap-fills (planner to rule if wrong):** (a) benchmark = equal-weight mean of other coins' returns (≥ 30 others), segment-wise index level; a bridged 1-minute benchmark level reproduces the 30m z (error 3e-13); (b) the residual profile is at 30m resolution; (c) volatility decile = std of the 48 returns b−48..b−1 ranked against the previous 336, trigger bar excluded; (d) ±24h exclusion applied to set 2 (ruling), which is why 30.73% of events have no set-2 control; (e) control acceptance requires a finite C24 flow window and finite 30m prices over b−48..b; (f) impact model scales by trailing 48-bar residual volatility and uses the previous bar's beta; (g) TWAP is its own sub-group (CONC-TWAP); (h) DRIED UP threshold 0.5 × pre notional; (i) C2 has no distance cap. Build 4 L1 fits are seeded (random_state=0); build 3's L1 rows are as logged (wobble ≤ 3e-4, see L1-WOBBLE).

**Cost** (estimate): GCP pt-research e2-highmem-8 about 4 hours of the trial credit; no AWS spend. VM left TERMINATED.

# HL-WALLET1 — exact wallet concentration (H3), wallet skill (H4) and the backstop wallets, rolling walk-forward

Logs: hyperliquid/logs/build5_pilot.log, build5_full.log; dislocation_model/logs/hl5_features.log, hl5_valid.log, hl5_tests.log (smoke test on the first 45 days: hl5_smoke_*.log, labelled smoke). Tags: M = measured in the log, A = assumed / stated rule.

**Parts 0-1: the wallet tables** (build5_pilot.log, build5_full.log)

| finding | M/A |
|---|---|
| pilot, 4 days (2025-06-01, 2025-07-27, 2025-10-10, 2026-07-08), one c7g.2xlarge on-demand (spot had no capacity): reconciliation with the flow table exact; 23.2 MB/day zstd on average (crash day 42.8 MB); 36-152 s per day; peak RSS 7.1 GB on the crash day | M |
| full run (build5/full2), 507 days, c7g.8xlarge on-demand, 12 days in parallel, 43.4 min, exits 507 × 0: T1 476,476,989 rows, T2 18,554,879, T3 22,538; 10.15 GB (T1 9.15, T2 1.00); peak RSS 7,144 MB (2025-10-10), median 2,036 MB; per-day wall median 58 s, max 158 s. Reconciliation of T1 taker/open/close/twap sums against the flow table per (coin, 5-minute bin): max abs diff ≤ 1.2e-7 USD (float summation order), (coin, bin) row counts equal on every day; absorbed USD in T1 equals T3 to 4.8e-7. Hole-flagged T1 rows 35,884 | M |
| **First full run was wrong in T3 and was replaced.** T3 read the wallets on the other side of ADL trades as the backstop absorbers (absorbed == ADL for every wallet, 21,635 wallets; reported at the time, A: that run's outputs were deleted and no surviving log holds the number; the fix is evidenced by full2's "wallets with absorbed == adl (both non-zero), all days: 0"). Raw fills of 2025-10-10 hour 21 show both fills of a backstop tid carry a "Liquidated…" dir (method "backstop"); the absorber is the one whose wallet is not the liquidated user. Fixed, T1 got two additive columns (absorbed_buy_usd / absorbed_sell_usd), the full run was redone (full2) and the wrong run deleted. T1 taker/forced columns, T2 and the reconciliation were unaffected | M |
| corrected T3: 4 absorber wallets over the whole window, 2.3157e9 USD: 0xb0a55f13d22f66e6d495ac98113841b2326e9540 1.4779e9 (63.8%), 0x2e3d94f0562703b25c83308a05046ddaf9a8dd14 8.131e8 (35.1%), 0x5e177e5e39c0f4e421f5865a6d8beed8d921cb70 2.46e7 (1.1%), 0x2ed5c4484ea3ff8b57d5f2fb152a40d9f2b68308 1.4e4. Backstop days with absorption: 2025-07-10, 2025-10-10 (2.26e9), 2025-11-12, 2026-04-02, 2026-04-08, 2026-07-17, 2026-08-22. ADL takers: 21,611 wallets, 2.2787e9 USD. The vault identity (HLP / liquidator) is for the user to confirm | M |
| **Definitional finding about the flow table:** build 2's backstop_liq_usd = backstop liquidations absorbed by a vault wallet + ADL trades (the bankrupt side of an ADL trade also carries a "Liquidated…" dir). On 2025-10-10: absorbed 2.2562e9 + ADL 2.1033e9 = 4.3595e9 = backstop_liq_usd; same on 2025-07-10, 2025-11-12, 2026-04-08, 2025-08-26; ADL totals equal adl_usd on all 14 days. Builds 3 and 4's backstop/ADL rows were untestable anyway (a handful of non-zero held-out rows). Any future use of backstop_liq_usd should subtract adl_usd, or use T3/T1 absorbed | M |
| gap-fill: T1 taker columns follow the flow table's rule (one-taker tid, on-book dir) rather than "crossed = true" so that wallet sums equal the flow table; other_taker_usd keeps the rest. twap_usd is NaN before 2025-07-27 08:00; the 08:00-08:45 bins that day come from the old format and carry twap 0, as in the flow table | A |

**Part 2: the features** (hl5_features.log, hl5_valid.log)

| finding | M/A |
|---|---|
| 597,516 rows (74,607 events, 522,909 control links) × 5 windows × 15 values; 743 s. NaN share of events on top1: P1 0.50%, P2 0.38%, P3 1.22%, C6 0.45%, C24 1.60%. P1 medians: top1 0.414, top3 0.769, hhi 0.268, n_wallets 13, persistent_share 0.528, bottom-decile share 0.148, top-decile share 0.144, prior-forced share 0.024, skill_mean 9.5e-5. twap_share finite on 90.7% of events | M |
| **backstop_share is zero for almost every event** (P1 median 0, p90 0). The BACKSTOP group has almost no variation, so its null result carries little information | M |
| independent validator (300 events + 300 links, plain pandas groupby per window from the raw T1/T2 files): 45,000 comparisons, 0 mismatches, max abs diff 9.4 (push_total of ~1e10 USD in float32; relative tolerance 1e-4) → PASS | M |
| gap-fills: "trigger's day" = UTC day of the bar label T; twap_share uses both sides' taker notional; skill deciles over wallets active on D-1 with skill from days < D; persistent_share needs ≥ 3 of the prior 7 days; backstop_share from the T1 absorbed columns; skill is NaN with < 5 active days of the prior 30; windows touching a missing minute or before 2025-05-25 14:35 are NaN. Many wallets can belong to one entity, behaviour drifts, and wallets that quit are never seen again (survivorship) | A |

**Part 3: the rolling tests** (hl5_tests.log, 5,620 s)

| finding | M/A |
|---|---|
| design fixed before any fit (rolling.py, docs/prompts/HL_BUILD6 "Rolling (walk-forward) test"): expanding window, first test block 180 days after the first event day, 30-day blocks → 11 folds (2025-11-27 .. 2026-10-23; the last is 3,230 rows), 1-day embargo before each test block and each validation block, validation = last 20% of each fold's fit days, every setting chosen on that fold's validation, reference-column NaNs filled per fold (0 rows needed filling in every fold). Pooled test rows 51,089 over 321 test days. Cells: 90 + 12 + 50 = 152, expected by chance 7.6 (3.8 per sign); folds are not cells | A, M |
| reference (unpenalised logistic, refitted per fold), pooled: flag80 0.6306 [0.6204,0.6404], top20 0.5381, **gap80 −0.0998 [−0.1135,−0.0855]**, AUC 0.6885. Gate (gap80 wholly above zero) NO. By fold gap80 −0.133, −0.114, −0.158, −0.130, −0.129, −0.089, −0.122, −0.044, −0.027, −0.049, −0.073 (folds 0-10; flag80 0.603 in fold 10) | M |
| **Result: 4 of 90 pooled cells are FINDINGS under the rolling rule (flag80, depth-1 tree, against the logistic reference, ≥ 2/3 of folds). The same-learner check does not confirm any of them (model-class gain); reported to the user as a disagreement between the gating test and the same-learner test. Our reading: no help. Size: 0.4-0.5 points of flag share, gap80 unchanged.**
| — the four: CONC_EXACT d1 −0.0046 [−0.0093,−0.0010] (9/11 folds), SKILL d1 −0.0039 [−0.0090,−0.0001] (9/11), ALL d1 −0.0054 [−0.0105,−0.0014] (11/11), KEPT d1 −0.0041 [−0.0088,−0.0004] (9/11).** Bad side 0. Expected by chance 2.2 per side. The gain is 0.4-0.5 percentage points of the flag share (0.63) and the beyond-chance gap does not move (all gap80 intervals include zero; best +0.0017) | M |
| the per-set rep models do not clear: CONC_EXACT −0.0037 [−0.0077,+0.0003], SKILL −0.0022 [−0.0071,+0.0016], BACKSTOP −0.0031 [−0.0077,+0.0012], ALL −0.0026 [−0.0082,+0.0008], KEPT −0.0019 [−0.0066,+0.0022]; reading: no help for all five. ALL's rep gain is on the good side in 11 of 11 folds (−0.000 to −0.011), small | M |
| same-learner diagnostics (set's model minus the reference set's same model, pooled flag80): none clears. ALL d1 −0.0015 [−0.0039,+0.0014], CONC_EXACT d1 −0.0007 [−0.0037,+0.0024], SKILL d1 +0.0000, KEPT d1 −0.0002. So the four findings against the logistic are the model class (depth-1 tree against the logistic), not the wallet features | M |
| permutation null (20 seeds, whole rolling pipeline on targets moved between whole days): the observed rep difference is inside the null range for all 5 sets × 3 measures (e.g. ALL flag80 observed −0.0026, null −0.0140 to +0.0075; CONC_EXACT −0.0037, null −0.0092 to +0.0082) | M |
| direction check (pooled correlation with the reference residual): WRONG DIRECTION none; n_wallets_C24 is right-signed (−0.0143 [−0.0239,−0.0033], 9/11 folds); every other expected-sign feature has an interval through zero; backstop_share two-sided, +0.005 to +0.008, through zero | M |
| strong-event row (|z| ≥ 3 or forced share P1 > 0; n 20,872, reach 0.2506): **0 findings of 12 cells**; one pooled interval on the BAD side: BACKSTOP rep gap80 −0.0032 [−0.0069,−0.0001] (the gap got worse; 1 bad-side hit against 0.3 expected) | M |
| single cut (CUT 2026-05-25, one fold, embargo applied; one like-for-like row, not counted): rep flag80 minus reference CONC_EXACT −0.0082 [−0.0145,−0.0010], SKILL −0.0034 [−0.0105,+0.0022], BACKSTOP −0.0059 [−0.0124,+0.0007], ALL −0.0095 [−0.0157,−0.0018], KEPT −0.0082 [−0.0145,−0.0010]; gap80 within ±0.002 of zero. The single recent window gives a slightly larger flag-share gain than the rolling pooled one; the rolling reading (no rep clears) governs | M |
| KEPT groups by fold: folds 0-1 none; fold 2 all three; folds 3-4 CONC_EXACT + BACKSTOP; fold 5 SKILL; folds 6-7 CONC_EXACT; fold 8 all three; folds 9-10 CONC_EXACT. Reps are depth-1 trees in most folds | M |
| **Q1 (events minus matched controls, test blocks only, pooled day-clustered interval, same sign in ≥ 2/3 of folds): 14 of 50 cells are findings (2.5 expected).** Bottom-decile-skill share is elevated before triggers in ALL 5 windows against BOTH control sets (+0.013 to +0.025 of the pushing notional; 10 of the 14 findings; 8 of 11 folds each): moves are pushed more by historically weak wallets. In the last hour, top-1 share −0.0176 and hhi −0.0212 against set 1 (82% of folds): pushing is less concentrated and from more wallets (n_wallets +8.1) just before triggers; hhi P3 +0.0085 against set 1 (more concentrated 6-24 h before). Other cells are regime-dependent (n_wallets P3/C24 lower, persistent_share P2/P3/C24 higher). Descriptive: a trigger is a large price move, so the pushing wallets are the ones moving price, and the control sets are matched on volatility, hour and weekday but not on the move itself | M, A |
| limits: many wallets can belong to one entity; wallet behaviour drifts; the skill is an in-sample past-30-day measure; wallets that stop trading drop out of the table (survivorship); the BACKSTOP group has almost no variation | A |

**Cost** (estimate): AWS ≈ $5-8 (pilot, two full runs of c7g.8xlarge ≈ 45 min each, S3 storage ≈ 10 GB), GCP pt-research about 6 hours of the trial credit for the features, validator and Part 3. Machines left terminated; `check` empty.

# HL-MASTER1 — master dataset, version 1 work area: events, labels (G0), hedge quality (G2), symmetric z (G2b), history (G3), both units. INTERIM: groups G4-G10, Part Z and release items 6-9 are not built yet.

Logs: research/dataset/logs/master_events.log, master_labels.log, master_label_summary.log, master_g2.log, master_g2_indep.log, master_tests_g2.log, master_coin.log, master_g2b_pair.log, master_g2b_coin.log, master_tests_g2b.log, master_g3.log, master_tests_g3.log. Definitions: docs/DATASET_DICTIONARY.md. Tags: M = measured in the log, A = assumed / stated rule.

| finding | M/A |
|---|---|
| **Stage A, the full pair population (master_events.log):** 6,697,756 triggers over 20,375 of 20,706 pairs, 2025-06-01 14:30 to 2026-10-13 13:00, median 384 per pair (max 500), long 51.0%; mkdisloc's rule unchanged (cap and window storage removed). The brief estimated ~8M; the smoke projection (6.4M) was closer. All 60,004 old rows reappear by (pair, entry_time) with z, beta, alpha, mu, sigma, r2, threshold equal to 0.0, beta_stab and mins_since_trade_a/b equal (NaN-equal), vol_48 within 4.5e-8; they are 0.90% of the full set | M |
| **G0 labels, pair (master_labels.log, master_label_summary.log):** label_gap 27,049 (0.40%; 4.2% in 2025-08, 3.5% in 2025-09, 0.7% in 2025-07, 0 from 2025-10 on). reach 2h/5h/10h 0.0758 / 0.1955 / 0.3288; mean chance 0.1589 / 0.3149 / 0.4503; adverse (widened by ≥ \|z\| within 10 h) 0.3202; median minutes to mu of reachers 247. Reproduces build 3 on 59,759 rows: reach 0 differences, first minute at mu 0, depth to 4.61e-7 (build 3 used the float32 z), label_gap 0. Chance: mean difference to build 3 +0.00005 [−0.00062,+0.00074] (day-clustered), per-row correlation 0.894 (different random draws; not exact, by construction, passed to the planner). The 1-minute path equals z at t = 0 (0.0) and the 30m outcomes at every 30th minute (max 7.6e-6) | M |
| **Chance fell over time while reach did not (descriptive):** mean chance_10h 0.47-0.50 in 2025-06..10, 0.40 by 2026-09; reach_10h 0.31-0.35 throughout (master_label_summary.log by month). CHOP-DRIFT caveat: the sign-flip chance uses each path's own 1-minute step sizes, so its level moves with how choppy the 1-minute path is; the decline describes step structure, not reversion getting harder | M, A |
| **Stop-aware payoff, pair, mean net return in sigma after fees (taker / maker), outcomes mu-first / stopped / neither:** s = 0.5: 0.160 / 0.757 / 0.083, −0.200 / −0.101; s = 1.0: 0.231 / 0.595 / 0.174, −0.174 / −0.074; s = 2.0: 0.292 / 0.368 / 0.340, −0.133 / −0.034; no stop: 0.329 / – / 0.671, −0.039 / +0.061 (median +0.42 / +0.51). **The maker figures assume both legs fill passively at entry and exit at the maker rate, with no missed fills and no adverse selection on passive fills; they are not a tradable estimate.** fee_sigma median 0.1745 taker (p5 0.066, p95 0.410), 0.0872 maker. Descriptive over all events, no selection; every mean is negative at the taker fee | M |
| **Coin unit labels (master_coin.log, master_label_summary.log):** 74,607 events over 204 coins; 1-minute path equals z at t = 0 to 2.84e-13; label_gap 640 (0.86%); reach 2h/5h/10h 0.0724 / 0.1887 / 0.3223; chance_10h 0.4374; reproduces build 4's reach and first minute at mu on all 73,967 finite-path events (0 differences, depth difference 0.0). Stop table: no-stop net taker −0.164, maker −0.009; fee_sigma taker median 0.282. **Coin unit fee flag (checker-ruled): the fee if the benchmark leg could be traded as one instrument at the taker rate, a lower bound on the real cost (~200 orders on thin coins)** | M, A |
| **G2 hedge quality (master_g2.log, master_g2_indep.log, master_tests_g2.log):** 6,697,756 rows × 24 columns. NaN: beta_stab 2.22%, beta_chg_7d 2.24%, halflife_h 0.72% (phi ≥ 1 or ≤ 0), corr_30m_7d 0.02%, vol_ratio_7d 0.02%, others 0. Medians: r2_2d 0.529, r2_7d 0.484, corr_30m_2d 0.537, corr_1m_24h 0.233, both_traded_share_24h 0.672, abs_beta 1.04, neutrality 0.19, crossings 19, half-life 14.2 h, phi 0.976. r2_2d equals the event table's r2 (asserted). Independent recomputation (second implementation, plain per-bar numpy, 2,000 events × 24 columns): 48,000 comparisons, 0 mismatches. Coin unit: same kernel with leg B = the benchmark level; sandwich NaN by definition; crossings/phi/half-life NaN for 1.04% of events younger than 336 bars | M |
| **G2 tests (master_tests_g2.log):** poison 1,000 events × (random overwrite, truncation) × 24 columns: 0 changes; labels respond (path changed in 100 of 100 events, path at t = 0 unchanged); global sign flip (500 events): every column identical; known answers: b = ±2a gives r2 = 1, corr = ±1, beta = ±0.5, neutrality 1/3, vol ratio 0.5, alternating spread gives 335 crossings, phi −1, half-life NaN, geometric 0.9^t gives phi 0.9, half-life 3.289 h; swap (1,000 events): r2, correlations, neutrality, traded share equal, beta/abs_beta/vol_ratio products = 1 | M |
| **Finding, orientation (master_tests_g2.log):** the trigger's z is not leg-symmetric. With the legs swapped \|z'\|/\|z\| has quantiles 5/25/50/75/95% 0.24 / 0.65 / 0.88 / 1.04 / 1.35; correlation of z with the sign-corrected z' 0.922; half-life, phi, vratio, vol_slope agree between orientations (correlation 1.000), crossings 0.83, sandwich 0.78. Cause: per-bar betas in the rolling spread series. The written integrity item 3 (hedge quality symmetric by construction) holds for the leg-pair statistics only; scope narrowed in the test, needs the planner's sign-off. User decision 2026-10-24: keep this event set as version 1; add G2b; the symmetric-trigger event table is parked | M, A |
| **G2b symmetric z (master_g2b_pair.log, master_g2b_coin.log, master_tests_g2b.log):** share of current events with trig_sym = 1: 35.84% (pair), 35.34% (coin); corr(z, z_sym) 0.9445 (0.9327), same sign 98.44% (97.20%); z_ratio quantiles 1/5/25/50/75/95/99%: 0.060 / 0.256 / 0.739 / 0.976 / 1.155 / 1.515 / 1.898; \|z_sym\| above threshold_sym at the event bar for 43.34%. NaN 0. Swap (1,000 events): z_sym' = −sign(beta) z_sym, sigma_sym' = sigma_sym/\|beta\|, threshold and trig unchanged, 0 failures; sign flip 500: 0; poison 1,000: 0; independent recomputation 1,000 events: 0 mismatches; sigma_sym equals the frozen-geometry window std to 4.3e-9 with window mean 0 | M |
| **G3 history (master_g3.log, master_tests_g3.log):** pair 6,697,756 rows × 21 columns, coin 74,607 × 14. Pair medians: 178 earlier triggers, 176 resolved, prev_reach_raw 0.326, shrunk 0.328, global as-of rate 0.331, last5_mean 0.2, 0.48 days since the last trigger, 6 triggers in 7 days, 268 minutes to mu. NaN: prev_reach_raw 0.56%, prev_mean_minutes_to_mu 1.35%. Tests: known answers incl. the boundary (T_i − T_j = 600 resolved, 599 not), recency order, shrinkage, as-of global rate, gap exclusion; label poison (all unresolved labels randomised) 200 coin events and 60 pair events: 0 changes; independent recomputation 2,000 + 2,000 events × 14 columns: 0 mismatches | M |
| **Incidents:** (1) the first labels run's log was replaced when a later gcp_run rsync overwrote the file under the running process (the parquet was complete); the run was repeated and the log kept. (2) G3's first run failed on an import path and float prefix counts; fixed and rerun. (3) The first G2 test run failed at the swap test (the finding above). Gap-fills: the realised-at-crossing gross (overshoot kept both ways), per-event chance seeding, frozen-geometry crossings/half-life, flat minutes as zero returns, the as-of global rate for shrinkage | A |
| **Open before release (reviewer, 2026-10-24):** (1) G3 poison on 1,000 events per unit (ran 200 coin / 60 pair); (2) G2b independent recomputation on 2,000 events (ran 1,000); (3) integrity item 5: labels against a straight re-walk of the 1-minute path for 2,000 events (not yet run; the 59,759 and 73,967 reproductions are not that item); (4) record the planner's sign-off on narrowing the swap test (integrity item 3) | A |
| **Not yet done (release items):** drift and seam tables per column by month (item 6), 20-event eyeball PNGs (7), provenance hashes and freezing (8), known-answer events for 2025-10-10 and three other days (9), and groups G4, G5, G6, G7, G8, G9, G10, Part Z | A |

**Cost** (estimate): GCP pt-research about 5 hours of the trial credit for this tranche; no AWS spend; machines idle-stop.

# HL-MASTER1 (continued) — tranche 2: G4 context, G9a market regime, the OI gate and level, funding/premium, G7 derivatives and vault inventory. G5 flow follows when its tests pass.

Logs: research/dataset/logs/master_ctx_ingest.log, master_static.log, master_funding.log, master_g4.log, master_tests_g4.log, master_g9a.log, master_tests_g9a.log, master_oi_lag.log, master_oi_gate.log, master_oi_diag.log, master_oi_gate2.log, master_oi_level.log, master_funding_check.log, master_g7.log, master_tests_g7.log; raw OI pass research/hyperliquid/logs/build7_oipilot.log, build7_oifull.log. Tags: M = measured in the log, A = assumed / stated rule.

| finding | M/A |
|---|---|
| **Raw pulls.** asset_ctxs 2023-05-20..2026-10-23: 1,252 of 1,253 days (2026-07-08 is absent from the bucket), 279,372,741 rows, 111,166 snapshots (0.040%) off the minute dropped in the OI stage; the VM's credentials cannot read the archive bucket (403), so the pull ran from the laptop to our S3 (derived parquet, 12 GB). fundingHistory API: 234 of 234 coins, 2,801,492 hourly rows 2025-05-15..2026-10-25. Sector (CoinGecko): 208 coins mapped ok, 4 ambiguous (AI, BABY, MEME, XAI), 22 unmapped (renamed or delisted tickers such as FTM, MATIC, MKR, RNDR, AI16Z); today's categories applied to the past (hindsight) | M, A |
| **G4 (67 columns pair, 32 coin).** Independent recomputation 2,000 pair events × 2 legs = 48,000 comparisons and 500 coin events = 6,000: 0 mismatches; poison (1,000 pair, 300 coin events; future raw inputs and trigger-day-onwards daily flow of all coins overwritten) 0 changes; swap and invariants PASS. Two bugs found by the first independent run and fixed: a negative-index error in my test, and rv windows that were allowed to start before the grid. NaN: a_ret_30d 4.07%, a_rv_24h_rel90 4.26%, a_liq_30d 0.62%. First trade earlier than the asset_ctxs listing date: 0 coins; 21 coins left-censored. a_tier1_max_leverage is NaN for 82% (the meta margin-table list lacks most ids) | M |
| **G9a (49 columns, both units).** Breadth recomputed from raw equals ev_market's (max diff 0.0). Independent recomputation of 2,000 distinct bars: 66,000 comparisons, 0 mismatches; the _seg columns: 18,000 comparisons, 0; poison: 60 truncations of the whole pipeline at o_j plus 8 overwrites of every raw array after o_j: 0 changes. Coverage: the strict 1-minute index return ret_idx_7d is NaN for 17.6% of bars (99.98% in 2025-08, 96.8% in 2025-09) and rank90_idx_abs_ret_7d for 38%; the _seg versions (planner ruling) are computed from the 30-minute index series; both versions are stored | M |
| **OI: units definition and gate.** Lag stage: L* = 0 (pooled hourly correlation 0.99979; 2,240,093 hour pairs). The gate as first written FAILED on drift (25.4% of coin-days; hourly correlation 99.99%). Diagnostic (planner-approved single pass, diagnostics only): slope of observed on reconstructed hourly change = 2.00000 (pooled 1.9983; per-coin median 2.00000; 17 of 18 months 2.0000). asset_ctxs open_interest = sum of |positions| (both sides) = 2 × one-sided OI; the brief's ½(|p'| − |p|) gives one-sided OI, asset_ctxs is gross, and every OI column is stored in gross units. With the units definition (oi_delta = Σ(|p'| − |p|), no fitted constant) the UNCHANGED gate: all 89,299 coin-days 99.94%, first half 99.93%, second half (held out, the verdict) 99.96%; ADL days 100%, liquidation-heavy days 99.87%, every month ≥ 99.6%, no coin below 95% → PASS. 2026-05: pooled slope 2.2% off exact, carried by 2026-05-25 and a few thin coins; the level was then built (206 coins, anchored only from the past, in_gap flag > 60 min) | M |
| **Funding/premium (API) against asset_ctxs** (master_funding_check.log; stop rule fixed first: funding correlation < 0.9): the API row stamped at hour H matches the ctx snapshot one minute before H: best L = 1, correlation 0.99997 (2,568,622 pairs; exact match 68.9%, median abs diff 3.2e-13); at L = 0 0.854. Premium correlation 0.88-0.93 at best (the ctx premium is the instantaneous value, the API premium an hourly average): reported, different quantities → PASS | M |
| **G7 (110 columns pair, 37 coin).** All OI columns in asset_ctxs units (gross), observed OI limit 120 min, reconstructed level with age/in_gap, fills-based windows, funding/premium with the as-of rule (a row stamped after t0, even by milliseconds, is not available), minute-level ctx versions, vault inventory (the four backstop wallets and the leader). Coverage (pair, leg A): oi_obs_usd NaN 4.01% (2026-05 1.7%, 2026-07 2.6%, 2026-08 7.4%, 2026-09 25.8%, 2026-10 62.5%); oi_rec_usd NaN 0.00% (the level carries the fills-based change across gaps; in_gap flags it); fund_last NaN 0.00%; ctx_funding_inst NaN 4.45%. Tests: independent recomputation 1,500 legs, 28,500 comparisons (observed OI, age, changes, reconstructed level and changes, funding as-of and means), 0 mismatches; poison (600 pair + 200 coin legs, overwrite and truncation of every raw input at or after t0, 37 columns) 0 changes; invariants PASS. First independent run failed on funding means (a test-side convention: exact timestamps vs minute labels); the test now follows the as-of rule on minute labels | M, A |
| **Open items.** G5 flow (built; its tests are being rerun after the planner's backstop/ADL ratio vs share split and an exact-sum precision fix); the targeted funding as-of poison check (planner condition); G6 wallets (build 5 tables) to join; G8 order-book pilot; G10 OKX; Part Z; release items 6-9 | A |

# HL-MASTER1 (continued) — tranche 3: G5 flow, G6 wallets, funding as-of check
Code: research/dataset/master_g5.py, master_g5_run.py, master_tests_g5.py; master_g6.py, master_g6_run.py, master_tests_g6.py; master_tests_g7.py --fund-only. Logs: research/dataset/logs/master_g5.log, master_tests_g5.log, master_g6.log, master_tests_g6_part1.log (invariants, independent), master_tests_g6_poison.log, master_tests_g7_fund.log, master_funding_check.log.

## [HL-FLOW5] G5 flow (139 columns per leg x a/b/net, plus 9 price-shape columns)
- Built with exact integer cumulative sums (int64 micro-USD): a float cumulative sum of 1e12-1e13 had given shares of 1.0000038 on tiny windows.
- backstop and ADL: backstop_ratio / adl_ratio (off-book / on-book, >= 0, unbounded) and backstop_share / adl_share = off-book / (on-book + off-book) in [0, 1] (the default). Planner ruling 2026-10-25. Ratio above 1 in 0.002-0.011% of legs (max 4.5).
- Tests: invariants PASS; swap on the building blocks PASS (100,000 events); independent recomputation 2,000 legs, 278,000 comparisons, 0 mismatches, worst error / tolerance 0.001; poison 1,000 pair legs + 300 coin legs, 139 columns each, 0 changes.
- Two test-side fixes on the way, both confirmed by the checker as test fixes (reference bin pick scored an empty bin as 1.0; poison values scaled to stay inside int64). The checker's later request (poison = original + uniform(1, 100)) is in.
- Observed NaN shares at the event rows (pair, leg a): mins_since_forced_any 72%, mins_since_forced_spike 93% (forced liquidations are sparse), ps_mins_since_big_step 31%, twap_share_60 8% (before 2025-07-27 08:00), all other columns under 2%.

## [HL-WALLET2] G6 wallets (13,470,119 legs: 13,395,512 pair legs, 74,607 coin legs; 27 columns x 4 windows per leg, plus net for shares and means)
- Windows 30 / 60 / 360 / 1440 min, ALL and HUMAN populations (the four HLP liquidator wallets and the vault leader excluded from HUMAN). The vaults are not dropped.
- vault_absorb_ratio (unbounded) and vault_absorb_share = absorbed / (absorbed + push_total_all) in [0, 1] (default): same ruling as G5. The first G6 test run failed on the bounded-share assertion and was fixed this way; the rebuild took 97 min.
- Coverage at the event rows (pair, leg a): NaN 0.4% at 60 min and 1.3% at 1440 min for the shares; nw has 0.06% / 1.3%. Median top1 share 0.41 (60 min) and 0.22 (1440 min); median wallets pushing 13 and 88; skill covers 99.9% / 97.9% of pushing notional at the median.
- vault_push_share has median 0 and 95th percentile 0: vaults rarely push on the legs of these events.
- Tests: invariants PASS; independent recomputation 2,000 legs, 216,000 comparisons, 0 mismatches, worst error / tolerance 0.001 (master_tests_g6_indep2000.log; the earlier runs, 1,200 legs and 1,839 legs / 198,612 comparisons, also 0 mismatches, are kept as receipts: the first capped at 4 legs per trade day over 481 days, so it fell short of 2,000, and the cap was raised to 6); poison 400 legs, 108 values each, 0 changes (waiver in [HL-WAIVERS]). Final poison size: 400 legs (the user's waiver, [HL-WAIVERS]). A rerun at 1,000 legs was started on the planner's request and stopped when the user accepted 400; it produced no result and none is quoted.
- Poison test fix: the first run crashed on the "removed" variant, because deleting the later T2 days made the wallet-id map miss wallets that T1 still holds. The id map is an index, not information (skill reads only days before the trigger's day), so the test now zeroes the values of those days and keeps the wallet column. Not a build change.

## [HL-FUND-ASOF] Targeted funding as-of check (planner condition)
- 500 events with t0 on an hour mark. Rows stamped in [t0, t0 + 60 s) perturbed: 0 G7 columns changed (required 0). The row stamped just before t0 perturbed: fund_last / prem_last moved by exactly the perturbation in 500 of 500. PASS: the minute-floor convention is as-of correct.
- Funding check (master_funding_check.py, rule corr >= 0.9, funding only): best lag 1 minute, corr 0.99997, PASS. Per-coin correlation at lag 0: median 0.72, lowest EIGEN 0.011, RENDER 0.166, PAXG 0.234, CFX 0.255 (per-coin figures are reported, not gated).

## [HL-WAIVERS] Recorded exceptions to the data-integrity list
- Integrity item 1 (poison test on 1,000 random events per group): G6 wallets ran at 400 legs (0 changes, master_tests_g6_poison_400.log). The user's decision of 2026-10-25, relayed by the planner (pair-trading-f6): "400 events is enough for the G6 poison test if it passes". This is an explicit waiver of the 1,000, not a silent shortfall. The G6 independent recomputation was raised from 1,200 to 2,000 legs for integrity item 2 (result in the next tranche).
- G8 slippage notional: the user's decision of 2026-10-25, relayed by the planner: no position will exceed $1k, so the extractor computes slip_buy_1k and slip_sell_1k only; the pilot's 10k/50k columns were removed (replaced, not kept). The first full extraction (28 days done, with 10k/50k) was stopped, its instance terminated and its partial output deleted.

## [HL-COINREWALK] Integrity item 5, coin unit: labels re-walk (research/dataset/master_coin_rewalk.py; logs master_coin_rewalk.log, master_coin_rewalk_stored.log)
- Independent benchmark: all 206 coins' 1m closes from the feathers, the 30m panel from the 30m bar files, the other-coins index return (>= 30 others), segments, the level L, the bridged 1m level, the path, then the labels. 500 events with finite paths + 100 events stored with label_gap = 1: label_gap agrees on 600 of 600; 500 paths x 8 labels = 4,000 comparisons, 0 mismatches; P(0) = z to 1e-9 on every path.
- Stored benchmark return series (coin stats), label logic and bridging re-done: 2,000 events x 8 labels = 16,000 comparisons, 0 mismatches; label_gap agrees on 2,000 of 2,000. Together these meet the 2,000-event count of item 5 (the checker's offer: 500 independent + 2,000 against the stored series).
- The m = 0 point is bridged inside the trigger bar like every other point: if one of that bar's 30 one-minute index returns is missing, the stored path (and label_gap = 1) has a NaN there even though z and L(b) are known. Reproduced, not changed. A possible rule refinement for the planner; it would change the coin unit's 0.86% gap share.
- The 30m bar files and the 1m closes labelled T + 29 agree exactly (max |diff| 0) wherever both exist. 38 coin-bars exist only in the 1m series: in every one the coin's FIRST 30m bar is missing from the 30m file. The coin's 1m series starts mid-bar (first trade 2 to 53 minutes into the bar; 4 to 28 1m rows in that bar, last row at T + 29) and the 30m file starts at the next bar. They are the listing partial bars of 38 coin listings, excluded by build 2's documented rule (30m bars are built only where the whole 30-minute window lies inside the coin's life: H = date_range(life[0].ceil("30min"), life[-1] - 29 min) in build2_assemble.py) (REQ, SOPH, RESOLV, ..., USELESS; the full list is in master_coin_rewalk.log). The benchmark follows the 30m files: the coin joins the cross-section at its first whole bar. Build 2's assert (close == 1m close at H + 29, NaN == NaN) ran over the bars that exist in the 30m files, so it could not see a bar that is absent.

## [HL-ORDERBOOK1] G8 order book (research/hyperliquid/build8_l2.py, build8_ec2.sh; research/dataset/master_g8.py, master_g8_run.py, master_tests_g8.py; logs build8_l2_pilot.log, build8_l2_full_dups.log, master_g8.log, master_tests_g8.log, l2sync.log)
- Extraction: EC2 us-east-2 (c7g.4xlarge, 14 days in parallel), 517 days 2025-05-25 to 2026-10-23, every day exit 0 (zero failed days), ended 2026-10-26 05:12 UTC; 496 day tables and 517 index files (21 days are entirely absent from the archive). Slippage notional $1k only (user decision 2026-10-25); the first run with 10k/50k (28 days done) was stopped and its output deleted. Duplicate (coin, minute) rows resolved at hour boundaries: 1,020,406 (earliest exchange time kept); rows outside their day dropped: 3,642.
- Coverage from the source: coin-hours present < expected on 50 of 517 days; 64,412 of 2,340,048 expected coin-hours missing (2.75%). Crossed or locked rows 0 in every month; non-monotone exchange-time steps are counted per month in the log (largest 10,199 in 2025-11) and are handled by taking the minimum exchange time per minute. Snapshots per coin-hour about 6,500 to 2026-05, 1,668 in 2026-06, 670 from 2026-07.
- Event columns: pair 6,697,756 rows x 114 columns, coin 74,607 rows x 41 columns. NaN share of a_spread_bp 7.0% (pair): 0% in most months, 25% / 35% in 2025-10 / 2025-11 and 26% in 2026-07 (the archive gap days); a_rel_bid_d10 11.3%.
- Tests (master_tests_g8.log): invariants PASS; independent recomputation 3,000 events, 159,300 comparisons (rel_* on 300), 0 mismatches; raw-level poison (every minute row at or after t0 overwritten) on 36 (coin, cutoff) trials: 0 changes, and the deliberately broken variant (row labelled t0 read) changes features in 34 of 36 trials, so the test can see the bug; a deleted t0-1 row gives NaN in all cases (nothing carried). Poison size 36 trials was accepted by the user on 2026-10-26 in place of a 1,000-event rerun (see [HL-WAIVERS]).

## [HL-MASTER1] Release report, version 1 (checker verdict at the end)
Rows and columns (event_id excluded), pair / coin unit: events 21 / 16, G0 labels 34 / 34, G2 24 / 24, G2b 5 / 5, G3 21 / 14, G4 67 / 32, G5 3 x 139 + 9 shape / 2 x 139 + 9, G6 108 + 108 + 92 net / 108, G7 110 / 37, G8 114 / 41, G9a 49 / 49. Totals: pair 6,697,756 rows x 1,179 columns (21 GB); coin 74,607 rows x 647 columns (172 MB). G10 (OKX) was removed from version 1 by the user. Part Z is deferred to after release.
- Hedge quality and history first: G2 (24) and G2b (5, exactly symmetric) cover 100% of rows except where a segment lacks history (G2 NaN 0.1 to 8% by seam); G3 (history, as-of resolution rule) 0.1 to 6.5% NaN by seam.
- Validations: labels reproduce build 3 / build 4 and the 60,004 old rows; labels re-walk 2,000 pair events (0 of 16,000 mismatches) and the coin unit 500 with an independent benchmark + 2,000 against the stored series (0 mismatches); poison tests per group (G3 1,000 per unit, G2b 1,000, G5 1,300 legs, G6 400 legs [waiver], G8 36 trials [waiver]); independent recomputation per group at 2,000 rows or more (G2 48,000 comparisons, G2b 2,000, G3 2,000 per unit, G4 48,000 + 6,000, G5 2,000 legs, G6 2,000 legs, G7 28,500 comparisons, G8 3,000 events, G9a 66,000); known-answer events 80 of 80 hand checks on 2025-10-10 and three other days; release checks ALL PASS (unique ids, grid, monotone labels, nested windows, OI >= 0, funding within the 0.04 per hour cap, 107 rows above 0.01 per hour confirmed against raw and live API).
- Gap handling: funding as-of 500 of 500; OI units finding (asset_ctxs open_interest = 2 x one-sided) with the gate passing on the held-out half (99.96%); order-book NaN never carried; ctx gaps (6% / 28% / 64% missing in Aug / Sep / Oct 2026) from the source and flagged in G7.
- Cost (estimates, A): order book about $18 (EC2 c7g.4xlarge about 9 h, cross-region transfer about $10, laptop pilot egress $0.7), VM hours not metered here.
- Known limitations: DATASET_DICTIONARY.md, "Known limitations of version 1" (the two coin-unit edge cases with counts, the waivers, the deferral of Part Z).
- Freeze: master_manifest.py (real copies in S3 under master/versions/v1/, sha256 of every group and code file, verify-on-read through open_version). Questions for the user: (1) commit the dataset code before freezing v1; (2) enable S3 versioning on master/versions/.
- Checker (pair-trading-78) verdict: PASS for release v1 (2026-10-26), see [HL-FREEZE-V1].

## [HL-DRIFT] Integrity item 6 (drift by month) and the receipts the checker asked for on 2026-10-26
- Drift rule (tag A): month flagged when |mean_m - mean_(m-1)| > 3 x sd of the column's monthly means (months with >= 200 values). Flagged: pair 313 of 1,110 columns (479 column-months), coin 203 of 590 (313). Causes assigned by master_drift_explain.py; fully explained: pair 217 columns (3 partly), coin 145 (9 partly); unexplained pair 96 columns / 111 column-months, coin 58 / 68, listed in docs/release_v1/drift_explained_{pair,coin}.csv and summarised in the dictionary ("Drift by month"). Logs master_colreport_pair.log, master_colreport_coin.log, master_drift_explain_pair.log, master_drift_explain_coin.log. The drift half is a v1 release item; it is NOT covered by the Part Z deferral (no waiver recorded; the user's words covered the side-by-side).
- Broken-variant misses (master_tests_g8.log, rerun): the broken variant (row labelled t0 read) is caught in 34 of 36 trials. The two misses are coin OGN at cutoffs 7478 and 22516: the raw table has neither a row labelled t0 nor one labelled t0 - 1 (OGN has no minute rows there), so the broken and the right variant both read NaN, with or without the poison. Not a finding.
- G6 poison size: final 400 legs (user waiver); the 1,000-leg rerun was started and stopped, no result.
- Snapshot-rate drop 2026-06 / 2026-07 is in the dictionary's "Seams and gaps" (order-book snapshot rate bullet) and in the drift causes (orderbook_rate).

- after_crash tightened (checker, 2026-10-26): requires the 2025-11 change to have the opposite sign to the 2025-10 change. Result unchanged: of the 135 pair columns flagged in both months, 135 reverse and 0 move the same way, so counts stay pair 116 / coin 73 column-months and the label is now a verified statement. One column name occurs in two group files (the drift table keys by column name; values identical).

## [HL-RECEIPTS] Log handling decisions, 2026-10-26
- master_tests_g8.log is a RECOVERED EXCERPT: the original rerun log (with the two explanation lines for the broken-variant misses, OGN at cutoffs 7478 and 22516) was overwritten by a stale copy during a sync. The excerpt carries the lines captured from that run's output. The user accepted it without a full rerun (decision 2026-10-26, relayed by the planner and confirmed by the checker); the file header says so.
- Two receipts were lost to sync overwrites (the first labels log, then this one). scripts/gcp_run.sh no longer pushes research/**/logs/ to the machine (pull-only). Before the freeze, the sha256 of every master_*.log was compared between the laptop and the VM: identical except two VM-only files (an empty chain log and the failed first freeze log), both removed before the freeze.
- The first freeze attempt failed with AccessDenied (the VM's AWS user is read-only on the bucket). On the user's choice (asked directly, 2026-10-26) the inline policy PutMasterVersions was added to IAM user pt-gcp-reader: s3:PutObject on arn:aws:s3:::pair-trading-hl-289869684922/master/versions/* only (no delete, no other prefix). A stray master_tests_g8.py process from the stopped chain 23 was found still running and killed (pid 39221) before the freeze.

## [HL-FREEZE-V1] Version 1 frozen (2026-10-26 18:30 UTC; research/dataset/master_manifest.py; log master_manifest_v1.log)
- s3://pair-trading-hl-289869684922/master/versions/v1/: 30 table files (pair 15 group files, coin 11, plus events), 22,485,133,277 bytes (22.5 GB), 32 S3 objects with MANIFEST.json and CHANGELOG.md; sha256 of every file in MANIFEST.json (pair events 6,697,756 rows, coin events 74,607 rows). verify-on-read tested (hash check passes on three files; open_version reads events through verify).
- Code identity: git HEAD 101624b40479 with 164 uncommitted paths (listed in the manifest); the identity rests on the sha256 of the 47 code files hashed, not on HEAD. The first freeze attempt (before git state was taken from the laptop, the machine has no .git, and with every master log read as a validator) was deleted before release and redone: the first manifest had an empty git head and 0 uncommitted paths, and it counted stale diagnostic logs as validators.
- Validators in the manifest: 27 final receipt logs (95 PASS / count lines captured, 58 of them PASS), and 57 superseded or diagnostic logs recorded by name and hash only (for example the first failed G6 run, the OI gate that failed before the units definition, the coin re-walk diagnostics, the stopped 1,000-leg poison runs). The single "FAIL" text is a heading in the OI gate log ("FAILURE BREAKDOWN").
- Checker (pair-trading-78) verdict: PASS for release v1 on 2026-10-26 (two edits requested and done: after_crash sign rule, G8 miss explanation excerpt); final confirmation of the manifest summary: CONFIRMED by pair-trading-78 on 2026-10-26 after checking the frozen S3 prefix (32 objects, 22,485,170,772 bytes).

## [HL-FREEZE-NOTES] Records that do not belong in v1's frozen CHANGELOG
- G10 (OKX cross-venue) removed from version 1: user decision of 2026-10-25, relayed by the planner pair-trading-f6 ("G10 OKX cross-venue is REMOVED from version 1, do not build it (brief updated)"). Never built.
- The first v1 manifest (built 2026-10-26 18:22 UTC on the VM, 22,485,133,277 bytes) was WRONG: the machine has no .git, so it recorded an empty git head and 0 uncommitted paths, and it counted every master_*.log, including stale diagnostics, as a validator. It was deleted from S3 and from the machine before anyone read it, and v1 was rebuilt at 18:30:15 UTC with the git state taken on the laptop and an explicit list of final receipt logs. "A released version is immutable" holds because v1 was never released before the rebuild. The frozen CHANGELOG does not mention it.
- IAM changes made in the release work, each with the user's approval: (1) role hl-build2-ec2 got read-only s3:ListBucket / s3:GetObject on hyperliquid-archive (2026-10-25, for the order-book extraction); (2) IAM user pt-gcp-reader got s3:PutObject on pair-trading-hl-289869684922/master/versions/* (2026-10-26, for the freeze copy). Open user questions about (2): remove the grant now that v1 is frozen and re-grant for the next freeze; enable S3 versioning or Object Lock on master/versions/.
