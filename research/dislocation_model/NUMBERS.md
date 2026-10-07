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
