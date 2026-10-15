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
