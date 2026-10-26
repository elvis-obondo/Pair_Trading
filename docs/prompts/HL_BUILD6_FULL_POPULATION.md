> **CANCELLED/PARKED (user, 2026-10-24): only the master dataset (build 7) proceeds. Kept for its design, which later model work reuses.**

# Builder prompt: Hyperliquid build 6 — the full population, a wide net (pair level, no sampling cap)

User, 2026-10-15: "cast a wider net. we should always use the full dataset." Standing rule from now
on: no sampling caps on events; subsample only for a smoke test, and say so. If the data does not
fit the machine, chunk or stream it, do not thin it.

Read `docs/HYPERLIQUID_HANDOFF.md`, `CLAUDE.md`, and the build 3 and build 4 briefs
(`docs/prompts/HL_BUILD3_*.md`, `HL_BUILD4_*.md`) first; this brief only states what differs.
Do exactly this; nothing else. Findings that point elsewhere are reported, not acted on. Be frugal
with messages (batch questions, no status pings). Runs may use a larger machine than pt-research
(AWS spot up to 32 vCPU is now allowed; GCP trial max is 8 vCPU); cost is not a constraint, every
machine auto-terminates with a hard timer.

## What this tests

1. **Was the 60,004-event sample misleading?** Rerun build 3's reference and flow design on every
   pair trigger. If the reference gap and the flow gain match, the sample was fine.
2. **A wider net with the same discipline**: more horizons, windows and feature groups than builds
   3 and 4, with the cell count fixed and counted before any fit.

## Hard rules (unchanged unless stated)

- Same adaptive trigger and geometry (`mkdisloc.py`, 96-bar symmetric, fresh crossing of the pair's
  own previous-96-bar 99th percentile of |z|, segment rule (i) for NaN closes). **Remove PER_PAIR
  and TARGET (no cap).** Do not regenerate or overwrite `disloc.npz` / `disloc_meta.parquet`
  (build 3 and 4 depend on them): write the full set to new files `disloc_full_*`, row-for-row
  reproducible with the same seed order. The 60,004 rows must reappear in it (assert it, by
  pair + entry_time); report the share of the full set they represent.
- Do not store the 336-bar windows. Per event keep: meta columns, the reference inputs (vol_48,
  vol_48_1m, sigma, |z|), reach/depth at 4, 10 and 20 half-hour horizons (2 h, 5 h, 10 h) on
  1-minute closes with mu frozen, chance probability (50 sign-flip seeds) per horizon. Work in
  chunks by pair block; peak memory must stay under the machine's RAM (report it).
- Flow features: use per-coin cumulative sums of each flow column over minutes (prefix sums), so any
  window is two lookups; same definitions as build 3 (net-weighted by leg contribution, push sign,
  normalisation rules), no look-ahead (minutes < t = 0 only), same validator on a random 2,000 rows.
- Splits unchanged: CUT 2026-05-25, HO1 to 2026-08-14, HO2 from 2026-08-15, validation = last 20% of
  fit days. Held-out touched once, at scoring. Day-clustered intervals, permutation null, pruning
  rule on validation, reading rules as before. A finding needs the same direction and an interval
  excluding zero in BOTH halves.
- Nothing is chosen on held-out; nothing here is tuned to a result.

## The design (fixed now)

- **Horizons:** reach mu within 2 h, 5 h, 10 h (10 h is the primary; the others are reported with the
  same models). Chance probability per horizon.
- **Windows:** W in {30 min, 60 min, 6 h, 24 h}, all ending at t = 0.
- **Groups:** FORCED (forced share on the pushing side; backstop and ADL reported, not modelled),
  OPENCLOSE (opening push, closing push, ratio), CONCENTRATION (proxies; to be replaced by build 5's
  exact version), VOLUME (taker notional ÷ trailing 7-day median), IMPACT (explained_share,
  unexplained_move using build 4's FROZEN fit-period coefficients, applied pair-level with the same
  net-weighting), MARKET (as build 3). Directions as stated in builds 3 and 4.
- **Models:** logistic L1 and LightGBM depth 1–6. **Leaf size:** the OKX-era min_data_in_leaf grid was
  set for ~40k rows; at N ≈ 8M the same absolute counts act as almost no regularisation. Run BOTH
  the old absolute grid and a grid scaled by N/60,004, report both, and flag this to the user: the
  leaf-size grid was a closed decision on 2026-10-13, so do not choose between them yourself.
- **Sets:** reference; reference + each group; + all; pruned set (pruning rule on validation).
- **Measures:** flag share at 80% catch, top-20% hit rate, beyond-chance gap, as before. Also report
  the effect sizes in plain numbers and the monthly series of the gap (descriptive) for the
  reference and for ALL; and the same by |z| band (< 2, 2–3, ≥ 3).
- **Cell count:** sets × models × halves × measures × horizons × windows, counted and logged before
  any fit, with the expected false positives at the 95% level next to the hits. State the effective
  independent sample (held-out days) next to every interval.
- Run build 3's exact design (windows 30/60, horizon 10 h, leaf grid as OKX) as pass 1 so the
  comparison with the 60k result is like for like; the wide design is pass 2.

## Pass 3 — the minute-by-minute view (user, 2026-10-15: "the minute by minute data as well, to see the granular movement of everything")

Passes 1 and 2 use window SUMS. Pass 3 gives the models the SHAPE inside the windows, on every event.

**3a. Granular features for the tree/logistic models** (fixed now; all at t = 0, no look-ahead, net
and signed as in build 3; computed from 1-minute arrays per coin, not from sums):
- Flow shape: net signed imbalance and forced share in each 5-minute bin of the last 60 minutes
  (12 bins) and each 30-minute bin of the 6 h before (12 bins), as separate columns; the index of
  the 5-minute bin with the largest |imbalance| and its size; minutes since the last minute whose
  signed forced notional exceeded 3× its trailing 7-day median (NaN if none in 24 h); slope of
  cumulative imbalance over the last 30 and 60 minutes; share of the last 60 minutes' pushing flow
  that fell in the last 15 minutes (acceleration vs fade).
- Price shape: the spread's 1-minute path over the last 60 minutes in sigma units (frozen
  geometry at t = 0): realized variance, path efficiency (|net move| ÷ sum of |steps|), largest
  1-minute step and its minute index, minutes since the last 3-sigma-of-step minute, drawdown from
  the window's extreme.
- Both legs separately AND net (the granular block may use leg-level columns; count them in the cell
  design). Same groups' directions as before; shape features are two-sided.
- Same scoring, halves and cell-count discipline. Add the cells to the count BEFORE fitting.

**3b. A sequence model on the raw minute stream** (not gated on any other model; the permutation
null is the guard):
- Input per event: the last 6 h of the spread path at 1-minute resolution (sigma units) and, at 1-minute
  resolution for the last 60 minutes then 5-minute bins out to 24 h, the net signed flow channels
  (imbalance, forced share, opening push, closing push, volume ÷ trailing median), plus the reference
  scalars (vol_48, vol_48_1m, sigma, |z|) concatenated before the output layer.
- Small model: 1-D convolutions then pooling then a linear head, ≤ 200k parameters, fixed
  architecture chosen once now by the builder and logged BEFORE training (no search on held-out);
  early stopping on validation; sign folding as before; same target (reach, 10 h primary), same
  scoring against the reference, same halves and permutation null (shuffled targets by whole day).
- Trains on EVERY fit-period event (no thinning). Build tensors on the fly from the per-coin
  minute arrays by index (do not materialise 8M × all channels). If it cannot train on all rows in
  12 hours on available hardware (AWS GPU spot is allowed), STOP and report the options; do not thin
  silently.
- Report beside the tree results: does the raw-stream model beat the same-learner tree on the
  granular features, in both halves?

## Rolling (walk-forward) test — replaces the single held-out cut as the PRIMARY reading (user, 2026-10-15)

The single cut (CUT 2026-05-25, HO1/HO2) is kept for pass 1 only, so pass 1 stays like for like
with the 60k result. Passes 2 and 3 use this design (fixed now):
- **Folds:** expanding window (all past data, per the full-dataset rule). First test block starts
  180 days after the first event (about 2025-11-21); test blocks are 30 calendar days; about 10
  folds. Fold k fits on every event before its block, tests on its block, then the window grows.
- **Embargo (purge):** events within 1 day before a test block, and within 1 day before the
  validation block, are dropped from fitting, because a 10-hour outcome would otherwise run across
  the boundary. This is part of doing the walk-forward correctly; say so in the log. The first
  planner suggestion, a gap at the old cut, is folded in here.
- **Validation inside each fold:** the last 20% of that fold's fit days (after the embargo). Every
  setting (iterations, C, leaf size, the sequence model's early stopping) is chosen on that fold's
  validation only. No setting is carried back from a later fold, and no fold sees its own test block.
- **Features and normalisers** are past-only as before, so they are valid at every fold. The
  impact-model coefficients (build 4) were fitted on the old fit period (before 2026-05-25), which
  leaks into earlier folds' test blocks: REFIT the impact model per fold on that fold's fit period
  and report the old frozen version only as a comparison.
- **Scoring:** per fold and pooled over all test blocks (concatenated out-of-sample predictions):
  flag share at 80% catch, top-20% hit rate, beyond-chance gap, the reference and each set. Pooled
  day-clustered 95% intervals; paired differences against the reference on the pooled predictions.
  Permutation null: rerun the whole rolling pipeline on targets shuffled by whole day (20 seeds),
  pooled.
- **Reading rule, fixed now:** a finding = the pooled interval excludes zero in the good direction
  AND the same sign in at least two thirds of the folds. A result in a minority of folds is
  REGIME-DEPENDENT, reported, not a pass. Report the fold-by-fold series of the reference gap and of
  ALL's gain (descriptive).
- Cell count: folds are NOT cells; the pooled measures are. Count cells as before and log them.
- Compute: use the cloud; the sequence model refits every fold. If the full rolling sequence model
  cannot finish in 24 hours on the hardware allowed, STOP and report the options (for example
  refit every second fold); do not thin the data.

## Review and receipts

- Code Checker ("Code Checker 2"; check `ListAgents`): the full-population build and the prefix-sum
  feature code before the run; the cell count and design before pass 2; log + NUMBERS.md + diff
  before reporting. A fix that changes a feature, window, grid, gate, architecture or cell count goes to the user.
- Logs `research/dislocation_model/logs/hl6_*.log`; NUMBERS.md section `[HL-FULL1]`, every number
  with its log and M/A tag.
- Final report plain and short (PM-level, numbers first): event count and memory/time/cost; pass 1
  vs the 60k result in one line; pass 2 per group and horizon (help / no / wrong direction /
  regime-dependent); the leaf-grid question for the user; the checker's verdict; files changed.
