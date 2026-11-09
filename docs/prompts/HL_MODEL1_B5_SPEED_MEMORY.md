# HL-MODEL1 B5: speed and memory, identical outputs (brief, 2026-10-27)

Planner: Research Partner. Builder: Code Builder. Checker: Code Checker (names change: `ListAgents`).
Parent brief: `docs/prompts/HL_MODEL1_REVERTER_MODEL.md` (Part A fixed rules apply unchanged).
Results to NUMBERS.md `[HL-MODEL1-B5]`.

## Goal (user, 2026-10-27)
Make the harness, and the model-fitting code still to be written, as fast and as memory-efficient as
possible **without changing any result and without sacrificing model quality or correctness.** All
work runs on the GCP VM (no AWS spend in B5). After B5, the B4 sizing spec runs on the optimised code.

## The equivalence rule (the gate for every change)
- **Existing code (harness.py and its callers):** outputs must be IDENTICAL before and after:
  fold id sets, embargo counts, hazard rows (event, step, label), the feature matrix
  (`np.array_equal` with NaN positions equal, same dtype, same column order), score_fold and
  bootstrap numbers to the last bit for the same seed. Prove it with a before/after comparison script
  on fold 7 (the largest) and fold 0. Then rerun the B3 proofs: every number in proofs_v1_pair.log must
  be unchanged.
- **Model code not yet written (logistic, boosted trees):** written efficiently from the start. Any
  shortcut (for example avoiding the hazard-row expansion) must optimise the SAME objective as the
  naive version. Prove it against the naive version on a labelled smoke-test subset: same objective
  value and coefficients within stated float tolerance for logistic; same predictions for trees given
  the same seed and settings. The subset is a test only; the real runs use the full data.
- A change that cannot meet this rule is reported, not shipped. If an optimisation would change model
  quality (for example fewer bins, a coarser histogram, fewer trees, float16), it goes to the user
  through the planner.

## Step 1: measure first (no optimisation before this is reported)
Profile the current code on fold 7, on the VM, and report time and peak RSS for each stage:
manifest verification, the per-file row-order assert, the column reads, the take/cast, train/val/test
loading, hazard-row build, and scoring.
- **Explain the memory gap first:** the fold-7 load peaked at 52.9 GB RSS against 23.4 GB for the
  float32 matrices (2.3x, unexplained in B4). Measure Arrow's memory pool
  (`pa.total_allocated_bytes()`, pool stats) alongside RSS. Candidate causes, to confirm or rule out,
  not to assume: Arrow pool retention between column reads; full-column decompression and float64
  intermediates before take/cast; three separate loads (train, val, test) each re-reading every
  column; temporary copies in `to_numpy`.
- **Time the verification:** `load_features` calls `MF.verify` per file on every call, which re-hashes
  the group files (the pair unit is about 21 GB) each time train, val and test are loaded. Measure how
  much of the 219 s load this is.

## Step 2: optimise (each change through the equivalence rule)
Candidates, in rough order of expected gain. Measure each one; keep only what helps.
**Go given by the user 2026-10-27 ("okay yeah do it"): the full list below. The Arrow-memory item is
DROPPED: Step 1 showed the pool never above 0.55 GB (NUMBERS [HL-MODEL1-B5], commit f43f451).**
- **Verify once per process**, not per call: hash-verify the v1 files once at start, cache the result
  keyed by the manifest sha256, assert it on later calls. Verification still happens before any read.
- **Load each fold once:** read the union of train, val and test rows in one pass, then split by
  position. Avoid reading every column three times.
- **A cached IN-matrix on the VM disk:** build once a float32 matrix of all 6,697,756 events x 1,093 IN
  columns (about 29 GB) as a memory-mapped file, plus a manifest (its own sha256, the v1 manifest
  sha256, the input-list sha256, the column order). Folds then index rows by position from the memory
  map. It must be byte-identical to `load_features` output for the same rows (assert on fold 7 and
  fold 0). The cache keeps NaN exactly as `load_features` returns it (no fill; planner and checker,
  2026-10-27). Rebuild it whenever v1, the input list or the cast rules change. The string tickers are NOT
  factorised into this cache: store a stable integer code from a fixed sorted list instead (see below).
- **Ticker encoding (a correctness fix that is also needed for scoring):** `load_features` factorises
  tickers per call, so codes differ between train, val and test. Replace it with codes from the fixed
  sorted coin list (`research/hyperliquid/coins.csv`, already used by G4's coin_code). Coins unseen in
  a fold's training rows are handled by the model code (an "unseen" level), per A6. This changes the
  ticker columns' values by design: report it as the one intended difference, and check that the
  ordering of every other column is unaffected.
- **Hazard rows without copying features:** keep hazard rows as (event position, step, label) only.
  Features are looked up by event position at fit time, never replicated 20 times.
  - Logistic: compute the linear predictor once per event (X_event @ w), add the step intercept per
    hazard row, and accumulate gradients back per event. Same likelihood as the expanded design. A
    chunked or out-of-core solver is fine if it reaches the same optimum (prove it as above).
  - Boosted trees: report what the library can do without materialising (event x step) rows (for
    example LightGBM Dataset construction from an indexed source, or binning once at event level and
    expanding the uint8 bins rather than float32 values). Memory of the binned hazard matrix at full
    size goes into the sizing.
- **Use all cores:** parallel column reads across files; threads where the library supports them.

**Ticker duplicate (planner ruling, user-approved 2026-10-27: "yes drop the duplicates"; amends "Not in B5" below):** a_/b_coin_code equal fixed_code(ticker_a/b) on every row. After
the ticker fix, B1's duplicate rule applies: ticker_a/b kept, a_/b_coin_code OUT (1,093 -> 1,091 IN). Order: bitwise
before/after on the 1,093 list; then the list revision as its own commit (checker, new sha256); cache built on 1,091;
B3 proofs rerun, any changed number explained by the column change or FAIL.

## Step 3: report, then STOP
- Before/after table per stage: time and peak RSS, on fold 7.
- The equivalence evidence: the comparison script's output, and the rerun proofs log diffed against
  the B3 log (identical apart from timings and provenance headers).
- What memory each model will need at full data after the changes. This feeds the B4 sizing, which is
  the NEXT step, not part of B5.
- Checker review before any run over a few minutes, and before reporting: code, logs, NUMBERS
  `[HL-MODEL1-B5]`, diff. Commit when it passes.

## Not in B5
No real-model scoring. No AWS spend. No change to Part A rules, the input list or the fold design.
No subsampling outside labelled smoke tests. RSF is parked (user, 2026-10-27): it is re-measured
after B5 with the other models, prediction time included.
