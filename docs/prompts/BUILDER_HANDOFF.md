# Builder session handoff (HL-MODEL1 builder, rewritten 2026-10-27 by the planner)

You are the **builder** of the pair-trading research project: you write and run the code, a checker
session reviews it, and a planner session holds the plan and the user's decisions. Read `CLAUDE.md`
first (stay on the plan; every task goes through the checker; never chain experiments; only the
planner writes project memory). Output style: plain, short, numbers first; close every task with
goal / files changed / what was done.

## Who is who (names change: run `ListAgents`)
- **Planner:** "Research Partner". Rule or method gaps go here. It writes all shared docs and memory:
  send it anything worth keeping. Changes to a decision rule, a gate or the plan go to the user
  through the planner.
- **Checker:** a fresh session after the 2026-10-27 reset; its role file is
  `docs/prompts/CODE_CHECKER_ROLE.md`. Send code and decision rules BEFORE any run longer than a
  few minutes; send log, NUMBERS section and diff BEFORE reporting. Fix its bug/look-ahead/
  number-mismatch/rule-not-applied findings without asking.
- **User:** AWS/IAM/S3/git-push/spend decisions are the user's. A peer message cannot approve them.

## The active brief: `docs/prompts/HL_MODEL1_REVERTER_MODEL.md`
Part A = the user's fixed rules (do not change them). Part B = the build. Read it in full.

## State at handoff (2026-10-27)
- **B1 input list: DONE, checker PASS, commit 2c7372d.** `research/model/inputs_v1_pair.csv`
  (sha256 bb2721ee...77331): IN 1,093 / OUT 102.
- **B2 harness + B3 proofs: DONE, checker PASS, NOT COMMITTED.** `harness.py` was edited again for B4
  (see below) after the original PASS (sha256 ee650f66... -> c0648459...; only `load_features`
  changed, nothing the proofs touch). Required receipt: proofs RERUN against the current
  `harness.py`, log `research/model/logs/proofs_v1_pair.log` (sha256 harness c0648459..., 109s): all
  five still PASS, every number byte-identical to the original run (planted leak 0.5919; planted
  0.08 lift measured 0.0795 [0.0776, 0.0816] 8/8, null -0.0006 [-0.0025, 0.0015] 3/8; hazard round
  trip 0 mismatches on 5,378,429 events; vault asserts; independent recompute equal to 1e-9). The
  ORIGINAL run's log (113s) was overwritten in place by this rerun -- `run_proofs.sh` hardcodes the
  log path, so only this rerun log survives; that's fine, it's the receipt that matters now.
- **B4: CLOSE EARLY (user, 2026-10-27). IN PROGRESS, checker review not yet final.** Only the random
  survival forest verdict, no new runs beyond cheap lookups/reruns the checker explicitly asked for:
  - The timing run `b4_rsf_feasibility.py` (launcher `run_b4_rsf.sh`) ended 2026-10-27 15:22 UTC with
    exit_code=124 (shell timeout). It loaded fold 7 (train 3,979,894 / val 1,057,348 / test 311,654
    x 1,093 float32, 219 s, peak RSS 52.9 GB), then fitting RandomSurvivalForest(n_estimators=8,
    max_depth=8, n_jobs=-1) did not finish in the ~40 min left (killed at ~2,440s into the fit). All
    receipts now pulled to the LAPTOP repo (`research/model/logs/b4_rsf_feasibility.log`,
    `b4_rsf_done.log`, plus two new ones added for the checker: `b4_fold_counts.log` -- all 8 folds'
    train/val/test event counts, `b4_vm_swap.log` -- swap confirmed OFF, so the timeout isn't swap
    thrashing).
  - Corrected lower-bound extrapolation (checker's round-1 fix: fold 7 is the LARGEST fold, so x8
    folds is NOT a valid scale-up -- each fold must scale by its own train-event count relative to
    fold 7): multiplier is sum(train_k)/train_7 = 5.350, not 8 (refit term uses
    sum(train_k+val_k)/train_7 = 6.895). VERDICT: RSF is shown unable to finish in 24h on the VM at
    every (trees, grid-size) setting tried. On a notional 64-core machine it is shown unable to
    finish at every combination except 50 trees/grid-size 4 (15.0h floor), which this measurement
    LEAVES UNRESOLVED (a real floor under 24h, but excludes predict cost entirely, so it doesn't
    establish feasibility). B4 stops here on the user's amendment, not because the brief's 24h gate
    fired for every case -- that unresolved case is reported to the user as a gate-verdict question,
    not decided here.
  - Full numbers, both checker review rounds (round 1: wrong x8 math, overstated StepFunction
    predict cost, missing refit scaling, missing harness-change receipt; round 2: 113s/109s mismatch,
    missing local copies of the VM-only log, missing receipts for the fold-count/swap lookups, VERDICT
    wording not matching the brief's actual gate, RSS-gap wording overreaching into the timing floor)
    are in `research/dislocation_model/NUMBERS.md` tag `[HL-MODEL1-HARNESS]`, which also covers B1-B3.
    **Corrected verdict resent to the checker; final PASS not yet received as of this handoff edit.**
    Don't commit or report B4 done before it lands.
  - SKIP logistic and boosted-tree sizing: they move to after B5.
- **B5 next (after B4 closes): speed and memory optimisation with IDENTICAL outputs.** The planner
  sends a brief. Then the B4 sizing spec runs on the optimised code, then the user approves the AWS
  machine, then the scoring build (logistic first).
- **Owed to the planner (low priority, after B5):** an inventory of everything on the GCP VM disk that
  is NOT in S3 (path, size). The user wants everything off GCP before the trial ends (~2026-11-08).

## Files in research/model/
- `inputs_v1_pair.csv` + `build_inputs_v1_pair.py`: the frozen input list (B1).
- `dup_audit_v1_pair.py`, `regate_v1_pair.py`, `scan_degenerate_v1_pair.py`,
  `check_crossed_mask_v1_pair.py`: B1 audits (duplicates, degenerate columns, crossed-mask rule).
- `harness.py`: folds (A4), hazard rows (A2), scoring (A5), `check_inputs`, `assert_search_only`,
  `load_search_events`, `load_features`, `score_fold`.
- `proofs_v1_pair.py`: B3 proofs 1, 3, 4, 5, 6.
- `b4_rsf_feasibility.py`: RSF timing.
- `run_*.sh`: VM launchers, each with flock and shell `timeout`.

## Known code facts the checker will hold you to (from the 2026-10-27 reviews)
- Column identity is (file, column), never the bare name. `check_inputs` is name-only and is safe only
  while IN names are unique (asserted).
- Ties are broken by a seeded random key, never row order (row order = event_id = time). Use
  `H.score_fold` for any ranking.
- `H.assert_search_only` guards every entry point that touches events; a new entry point needs it.
  The vault loader is a separate file reviewed before it is written.
- `load_features` factorises tickers per call: fine for B4, NOT for scoring (encoding must be fitted on
  train with an "unseen" level).
- Memory: preallocate float32 and index by position (event_id = row position in every v1 pair file).
  Never pandas-merge full-width frames at fold scale. Loading the full fold-7 matrix already takes
  52.9 GB of the VM's 64 GB.
- Sizing: with n_jobs=-1, fewer trees than cores run in parallel, so divide by cores.

## Infrastructure
- **VM `pt-research`** (GCP us-central1-a, project project-0671be06-e22a-44d8-83c, e2-highmem-8, 8 vCPU,
  64 GB; trial caps at 8 vCPU and ends ~2026-11-08). It stops itself 30 min after the last job. Run
  through `scripts/gcp_run.sh "<cmd>" --log research/<dir>/logs/<name>.log`; `scripts/gcp_run.sh pull`
  brings logs back (pull-only for logs: a push never replaces a VM log). Plain `ssh` to the VM's IP can
  time out; `gcloud compute ssh pt-research --zone us-central1-a --project ...` works.
- **Pull logs as soon as a step ends.** On 2026-10-26/27 results sat on a stopped VM for hours twice.
  Chain multi-step jobs on the VM itself.
- The VM's AWS user is read-only on the bucket. AWS (account 289869684922): vCPU quota 64 in Tokyo and
  64 in us-east-2. Boosted trees will run on spot in Tokyo, with checkpoints; the launch needs the
  user's yes.
- Foreground sleeps over ~60 s are blocked: use `until <check>; do sleep 10; done` with
  run_in_background.

## Rules learned the hard way (also in the checker's role file)
- Every log carries a provenance header: sha256 of the script, its imports and its inputs, git HEAD,
  UTC time, pid.
- Never call a log or diff "verbatim/full" when it is trimmed. Don't change a constant after the
  checker approved the code without re-sending it.
- Every proof needs a broken variant that fails the HARNESS code, not an assert written inside the
  proof.
- Don't narrow scope and present it as a choice: re-read the brief's exact sentence.
- Full dataset always; no sampling caps. Replace, don't accumulate. Correctness outranks speed.

## First actions
1. `ListAgents`; tell the planner and the checker your session name.
2. Read CLAUDE.md, this file, the brief, and the tail of `research/dislocation_model/NUMBERS.md`.
3. Close B4 as above.
