# Builder session handoff (HL-MODEL1 builder, rewritten 2026-10-29 by the planner)

You are the **builder** of the pair-trading research project: you write and run the code, a checker
session reviews it, and a planner session holds the plan and the user's decisions. Read `CLAUDE.md`
first (stay on the plan; every task goes through the checker; never chain experiments; only the
planner writes project memory). Output style: plain, short, numbers first; close every task with
goal / files changed / what was done.

## Who is who (names change: run `ListAgents`)
- **Planner:** "Research Partner". Rule or method gaps go here. It writes all shared docs and memory:
  send it anything worth keeping. Changes to a decision rule, a gate or the plan go to the user
  through the planner.
- **Checker:** "Code Checker". Send code and decision rules BEFORE any run longer than a few minutes;
  send the log, NUMBERS section and diff BEFORE reporting or committing. Fix its bug/look-ahead/
  number-mismatch/rule-not-applied findings without asking.
- **User:** AWS launches, S3 writes, git pushes and any real spend are the user's own direct call,
  typed to you in your own session. A peer's relay of approval is NOT enough -- Claude Code's own
  safety classifier blocks real-world AWS actions regardless of what any other session has already
  approved, and re-blocks on every fresh launch attempt.

## The active brief: `docs/prompts/HL_MODEL1_S1_LOGISTIC.md`
Part A (fixed rules, from the parent brief `docs/prompts/HL_MODEL1_REVERTER_MODEL.md`) does not change.
S1-D is appended at the end of the S1 brief itself -- read the whole file, not just the top.

## State at handoff (2026-10-29)

**HL-MODEL1 S1 (candidate 1, penalised discrete-time hazard logistic, proximal Newton solver): DONE,
checker PASS, committed.**
- Trained on all 8 folds, real data, 2x AWS r7i.16xlarge spot (Tokyo): machine A (folds 7,4,3,0, ~8.4h)
  and machine B (folds 6,5,2,1, ~8.1h), both exit_code=0, both well under the Gram-build speed tripwire
  (A 59.28s, B 55.74s vs a 120s cap). Commits: `9209a96` (solver + Gram-BLAS fix), `d91846b` (run
  script), `433c0aa` (AWS launch scripts), `333640c` (Step 3 report).
- **Part A gate verdict: FAIL.** Pooled lift 0.0394 (< the 0.05 bar, checked first regardless of fold
  count). 98.75% bootstrap interval (0.0316, 0.0475) -- wholly above zero -- and 8/8 folds positive. A
  real, consistent signal below the bar, not a pass. No vault touched. Full M1-M6 use-case metrics and
  the gate's own numbers: `research/dislocation_model/NUMBERS.md` tag `[HL-MODEL1-S1]`.

**HL-MODEL1 S1-D (top 1% of picks, examined -- user, 2026-10-29): DONE, checker PASS, commit `d179a79`.**
Descriptive only, gate verdict unchanged. Pooled lift 0.084/0.070/0.053 at top 1/2/5%, 8/8 folds
positive at every slice -- smooth, not jumpy. Not concentrated in a handful of pairs/coins/days. One
finding worth carrying forward: 87% of the top 1% IS itself a top-decile-vol_48 event (not a population
that avoids high recent volatility); the small remainder's lift looks similar, not clearly different
(wide bootstrap interval at n=4,730). Full tables: NUMBERS.md tag `[HL-MODEL1-S1-D]`.

## Where the outputs live
- **Per-fold receipts (small), committed to git:** `research/model/logs/s1/fold{0-7}_{done,grid,coefs,
  val_permutation_importance}.{json,csv}`, plus `report.json` (S1's aggregated M1-M6) and
  `s1d_report.json` (S1-D's item1-5 tables).
- **Per-fold test predictions (large, ~233MB total, 3.5M rows): NOT in git**, deliberately -- they live
  on the laptop (`research/model/logs/s1/fold{0-7}_test_predictions.csv`) and in S3, under
  `s3://pair-trading-hl-289869684922/s1_run/logs/{A,B}/outputs/`. Pull with
  `aws s3 sync s3://pair-trading-hl-289869684922/s1_run/logs/A/outputs/ research/model/logs/s1/` (and
  the same for `B/`) before running anything that needs them (`s1_report.py`, `s1d_top1pct.py`).
- **AWS instance logs:** same S3 prefix, `s1-run_<instance-id>.log` / `build_cache_<instance-id>.log`
  per machine, keyed by machine ROLE (A/B) not instance-id -- a relaunch after a spot reclaim restores
  that role's already-finished folds instead of redoing them.

## The AWS launch pattern (proven across the probe + the real 2-machine run)
1. Build a payload tarball from exactly the committed files (`git show HEAD:<path>` per file, never the
   working tree), upload to `s3://pair-trading-hl-289869684922/s1_run/<sha256>.tar.gz`. Send the
   Checker the file listing and the sha before uploading.
2. User-data script (template: `research/model/aws_s1_run_userdata_template.sh`): IMDSv2 token for the
   instance id (`curl -sf`, never bare `curl -s` -- a 401 page can silently become the instance id),
   venv + pip (not apt, not system pip) for numpy/scipy/pandas/pyarrow/threadpoolctl/awscli, a 60s
   background S3-sync loop started only AFTER the venv's `aws` binary is confirmed real, a single
   `trap finalize EXIT` (sync, 120s wait, sync again, `shutdown -h now`) as the only normal shutdown
   path besides a generous outer `shutdown -h +<minutes> &` hard safety net.
3. One parallel layer at a time: process-wide `OMP_NUM_THREADS=1` etc. (for `hazard_nll_grad`'s own
   `ThreadPoolExecutor`), with `threadpoolctl.threadpool_limits` scoped ONLY around the Gram-build
   matmul loop to let BLAS multithread there. Nesting the two is a real, easy-to-miss bug -- it shipped
   once before the Checker caught it from the launch script, not the proof.
4. **Every AWS launch command (`aws s3 cp` for the payload, `aws ec2 run-instances` for either
   machine) needs the user's own direct "yes" typed to you in this session**, every time, even after
   a prior launch was approved -- Claude Code's own classifier re-blocks on each fresh attempt.
5. `MaxSpotInstanceCountExceeded` is a real, hard account-level vCPU cap (64 in Tokyo, one
   r7i.16xlarge uses all of it) -- not a transient capacity issue. Running 2 machines in parallel needs
   a quota increase; running them sequentially (one at a time) works within the existing cap and was
   the user's choice last time.

## Open items -- need the user's choice before any further work
- **What's next after S1's FAIL.** The brief says tree sizing, then a tree model, needs the user's
  yes. Not started.
- **The vol_48/driver finding from S1-D.** Whether it's worth a model that leans harder on vol_48,
  sandwich, abs_beta (S1-D's top driver columns) -- or the vault question generally -- is the user's
  call, not something decided in a report.
- **GCP VM inventory.** Carried over from the pre-S1 handoff: an inventory of anything on the `pt-
  research` VM disk that is NOT already in S3, before the GCP trial ends. Check with the planner
  whether this is still open or already done.

## Known code facts the checker will hold you to
- Column identity is (file, column), never the bare name.
- Ties are broken by a seeded random key, never row order (row order = event_id = time). Use
  `H.score_fold` for any ranking, and the SAME per-fold-then-concatenate pooling convention for any
  "pooled top-k%" figure -- a single rank across all folds' pooled rows is a different population and
  was a real bug once (S1's M1/M2/M4/M5, caught by the checker before commit).
- `H.assert_search_only` guards every entry point that touches events; a new entry point needs it. The
  vault loader is a separate file, reviewed before it is written, never imported by S1/S1-D code.
- Memory: preallocate float32 and index by position (event_id = row position). Free large arrays
  (`del` + `gc.collect()`) between phases that don't need them both at once, and log VmRSS (current)
  alongside VmHWM (peak, never drops) so a log can actually show a free took effect.
- Every log carries a provenance header: sha256 of the script and its key inputs, git HEAD, UTC time,
  pid. Every proof needs a broken variant that actually fails -- verify it fails BEFORE trusting it as
  the proof's negative case; a "broken" variant that still converges to the same answer isn't decisive
  (found once with proximal Newton's cross-Hessian block).

## Infrastructure
- **GCP VM `pt-research`** (us-central1-a, project project-0671be06-e22a-44d8-83c): `scripts/
  gcp_run.sh "<cmd>" --log research/<dir>/logs/<name>.log` to run, `scripts/gcp_run.sh pull` to bring
  logs back (pull-only: a push never replaces a VM-written log). It holds the 29GB cached IN-matrix
  (`research/datasets/model_cache/`) that the laptop does not -- any task needing raw feature columns
  beyond events.parquet/labels.parquet (which the laptop CAN load directly from S3) runs on GCP.
  Files outside `research/**/logs/` sync automatically on every `gcp_run.sh` call; large files under
  `logs/` need an explicit `gcloud compute scp` push (the normal sync deliberately excludes them, to
  protect VM-written receipts from being overwritten).
- **AWS** (account 289869684922): r7i.16xlarge spot in Tokyo (ap-northeast-1) for the real S1 run; spot
  vCPU quota is 64 there, a hard cap. Bucket `pair-trading-hl-289869684922`.

## First actions
1. `ListAgents`; tell the planner and the checker your session name.
2. Read CLAUDE.md, this file, the brief (all of it, including S1-D at the end), and the tail of
   `research/dislocation_model/NUMBERS.md`.
3. Check with the planner which open item (above) the user has picked before starting anything new.
