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
against a 212-ticker / 36,172-bar panel; the panel now loads 214 / 36,215.

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
| panel today 36,215 x 214; the dataset came from 36,172 x 212 | M |
| the 43 extra bars are all at the END, so every index still resolves | M |
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
| `off_mark` log | M | 0.00008 | 0.00011 | 0.00018 | **0.00024** | 0.00032 | 0.00045 | 0.00058 | 0.00026 | 0.00011 |

`off_mark` is in log-price units, NOT sigma. The brief specified sigma for
`vol_48` and `sandwich` only, and a log difference is already a relative
quantity. Do not compare it to the other four without rescaling.

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
| max entry index 36,151 of 36,215; 63 later bars exist and are UNUSED | M |
| 18,108 of 36,215 grid slots are hourly mark labels | M |

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
