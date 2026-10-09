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
