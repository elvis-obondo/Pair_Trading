# Builder session handoff (HL-MODEL1 builder, rewritten 2026-10-29 by the planner; HL-VAULT1 state added 2026-11-12 by the builder)

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

## STATE 2026-11-18 -- COSTS1 committed (0d2fb83); no-bounce check run, in review -- NEWEST, READ THIS FIRST
- COSTS1 commit 0d2fb83 (41 files) after the checker's OK. Next on the plan: no-bounce section (done, in review), entry-delay engine-change write-up (no code), then ONE Word write-up in ~/Downloads.
- No-bounce: rules = costs1_rules.md section 10. Code `research/model/diagnostics/costs_nobounce.py` (sha ce44ea80, run 176 s) -> `costs_nobounce.log`, `logs/costs1/costs_nobounce.json`; `costs_nobounce_sources.py` (source-sensitivity line, 50 s) -> `.log`, `logs/costs1/costs_nobounce_sources.json`; `costs_nobounce_section.py` writes `logs/costs1/costs_nobounce_section.md` from those json files and the log. Per-trade headline parquets in logs/costs1 are untracked and stay on disk.
- Process note for the write-up: the same-minutes close comparator was decided after a ~3,000-event smoke run; the planner's G8-fallback / gross-ratio-band rulings came before the vault trade table was first printed (checker asked that the order be stated as resting on the planner's message and the builder's statement).
- No-bounce committed 2c6d76f (section 11 draft rules in it). One-leg check (rules section 11, planner order): `diagnostics/costs_legs.py` (run 49 s) -> `costs_legs.log`, `logs/costs1/costs_legs.json`; `costs_legs_section.py` writes `logs/costs1/costs_legs_section.md`; `costs_process_times.py` -> `logs/costs1/process_times.json` (order of the planner's rulings vs the smoke runs, from transcript timestamps). Checker passed the numbers; commit follows its OK. Still to do: entry-delay engine-change write-up (no code), then ONE Word write-up in ~/Downloads (verdict, results by configuration and tier, validation, no-bounce, one-leg, entry delay, assumptions, timings).
- Results belong to the planner to report.

## STATE 2026-11-14 -- COSTS1 (does the edge survive realistic execution costs?)
Rules (written before any result, edited with dated notes): `research/model/costs1_rules.md`. Code: `research/model/diagnostics/costs_*.py` (+ `.log` receipts), `research/hyperliquid/build9_l2_books.py` (raw 20-level extractor, kept for validation), launchers `research/model/aws_costs_*.sh`.
Done: (1) sizing and targets for the raw pull (88,405 files, not pulled); (2) existing G8 table used instead (`s3://.../build8/full/{day}_l2.parquet`), 1,233,079 of 1,291,668 wanted coin-minutes extracted on a Tokyo EC2 (7 target days have no file: 2026-07-08, 07-12..17); (3) `costs_analysis.py` re-costs the 8 priority runs (q1%/no stop/maker+taker, open10/20, vault and test): maker fill model strict/lenient, W=5 headline, curve costs from the table, exact accounting against the engine's reference prices; log `costs_analysis.log` (headline) and `costs_analysis_calibrated.log`; (4) 32-file raw validation (`costs_validate.py`, log `costs_validate.log`): T3 no, T1 no, T4 FIRES (5.1% of legs up to $1,000, 9.9% all sizes), T2 no (`costs_t2.log`).
Result: verdict (c) -- all four vault headline nets negative (-$703 / -$1,645 maker, -$874 / -$1,569 taker, zero-cost +$1,068 / +$2,357 / +$264 / +$433), 0 positive sensitivity cells. Beyond-book legs cannot be priced from the table (curve 14,017 bp vs exact walk 73 bp on 470 validated legs): show test open20 maker as -$20,069 without beyond-book trades, -$23,792 labelled as affected by that artefact. The curve is NOT "conservative" (word withdrawn after T4).
Order from the planner (2026-11-14): commit COSTS1 after the checker's OK on the staged list -> the no-bounce check (mid vs last-trade close; new section of the write-up; rules and code to the checker first) -> ONE Word write-up with everything incl. the entry-delay engine-change write-up (not yet written; plan in the log of the summary: start labels t0-1+d, window 601+d, entry z at the delayed spread, mu target |z_d|, stops, skip rule, funding hour, slippage lookup, exit timeout; about 0.5 day code + review + 3 delays x 4 tags x ~9 min engine time). The full 88,405-file raw pull is the user's decision (the planner asked).
Which script produced which log: `costs_analysis.py` sha 6e2039ce produced `costs_analysis.log` (uncalibrated, re-run 2026-11-16 as a reproduction of the 2026-11-14 run, headline nets identical) and `costs_analysis_calibrated.log` (`--scale logs/costs1/costs_scale_calibrated.json`); `costs_validate.py` sha 53c75c39 produced `costs_validate.log` and `costs_t2.log` (`--t2`). The first 2026-11-14 run's log was overwritten by the reproduction run (its copy was in a temporary folder that no longer exists).
Large untracked data (not committed, in S3 or regenerable): `logs/costs1/g8/g8_rows.parquet` (91 MB), `logs/costs1/g8_validate_days/` (243 MB, copies of S3 day files), per-trade headline parquets `logs/costs1/costs_headline_*`.

## STATE AT HANDOFF 2026-11-12 -- HL-VAULT1 (brief `docs/prompts/HL_VAULT1_RUN.md`) -- READ THIS FIRST
The sections below this one (dated 2026-11-08) are older history; HL-VAULT1 is the live work.

**Vault was opened once, in step 3 (features only) and step 5 (backtest). No pass/fail rule; settings frozen
before any vault row was read; after the vault read nothing in steps 4-5 may change (a bug is fixed and rerun,
never a setting change).** HL-PROFIT1 (Tasks A-C, Word report) and HL-PROFIT1-H (horizons) are committed
(`04fd91b`, `98c74c9`); Task D (flat 10x) was dropped by the user and its code deleted.

### Steps and status
| step | what | status |
|---|---|---|
| 1 | coverage check, no labels | DONE, checker PASS. `research/model/s1_vault_coverage_check.py`, log `logs/s1/s1_vault_coverage_check.log`: 1,280,088 vault events, 177 coins, 93 days |
| 2a | fold-0 reproduction (refit only) | FAILED its pre-set tolerance 6.557e-05; max abs diff p_2h 0.001748, p_5h 0.002003, p_10h 0.001832; ACCEPTED on the user's explicit yes as solver-level agreement (recorded in the model JSON known_gaps; `diagnostics/vault_2a_maxdiff.{py,log,json}`). Round-3 log `logs/s1/vault_pull/` |
| 2b | pre-vault refit on AWS | DONE, checker PASS. n=5,378,429, lam 14187.2 l1_ratio 0.5 (fold 7's), 7 iters, KKT 2.231e-08, 192 non-zero, inner CD cap hit 7/7, reload bit-identical. Model `logs/s1/s1_prevault_model.json` sha c30bbfa6fd7ccf8bc0559625eb30aaf2e144d994f4ac33f4c77cb412a3bd0cda, `_w.npy` sha 8af9ee742dff542ff34f61611ab0cb771a867b1b604d8acc7b400c3e471a27f5 (copies in `logs/s1/` and `logs/s1/vault_pull2/`) |
| 3 | score the vault, AWS, features only | DONE, checker PASS. `s1_vault_score.py` (sha 0498bd19...). Predictions `logs/s1/vault_pull3/s1_vault_predictions.parquet` sha ede424aac78a849c4288f223ad8e3750a0bbc343b1bdaad1ec2a657efdb689a7 (1,280,088 rows). 24,094 events involve coins the model never saw (CASHCAT, PONS, USELESS; zero one-hot) |
| 4 | picks and p_cal | DONE, checker PASS. `s1_vault_picks.py`; log `logs/s1/s1_vault_picks.log`. Rule A cut-offs from fold 7's saved test p_10h: 0.7295204552 / 0.7808598143 / 0.8778663336 (q 1% / 0.5% / 0.1%); picks 13,947 / 7,188 / 1,480. p_cal = S1-H's recipe literally (pool folds 0-7, guard t0+10h <= VAULT_START, n_fit 3,525,909, 251 levels) per the planner's ruling 2026-11-12 (the brief said folds 1-7 and `<`). Stage A `s1_vault_picks_all.parquet` sha b8aa5faff7b5f6eff00abe5d0d8173fb6760b84d9f32857ad8e06bef26291021; usable `s1_vault_picks.parquet` sha 15b4f56cd66ad6b2a4e2bc056f03cf03febb519459491310d4f7745e50e44a72; settings `s1_vault_picks_settings.json`. A one-line bug (event_id both index and column) crashed the first run in stage B and was fixed and rerun; stage A sha identical both times -- report as "bug fixed and rerun". label_gap: 0 of 1,280,088 (the data ends with a full 10 h window; `diagnostics/vault_labelgap_check.{py,log}`) |
| 5 | backtest, `s1_profit1.py` with `PROFIT1_VAULT=1` | DONE, checker PASS (committed `d54cfb7`) |
| 6 | report | DONE 2026-11-12, checker PASS on scripts and logs; NUMBERS.md appended (3 blocks, `diagnostics/vault_numbers_append_check.log` shows additions only, byte-identical to the section files). `s1_profit1_numbers_gen.py` has a PROFIT1_VAULT switch; `s1_vault_report.py` makes the side-by-side, vault lift and calibration. Commit only after the checker's staged-list OK. Default-mode identity: generator outputs for the base and open20 tags are byte-identical (HEAD generator vs edited; open20 numbers report sha unchanged); the open20 engine rerun (user's yes, incl. S3 sync of identical cleaned files) differs from the committed report JSON only in generated_utc and the `min_abs_z` config key, which `98c74c9..HEAD` did not touch; `manifest_profit1_outputs.py check` 578/579 (1 expected diff). The committed JSON was restored. |

### Step 5 outputs (both runs finished, both cross-checks clean)
- Commands used: `PROFIT1_VAULT=1 PROFIT1_RUN_TAG=vault_open10 PROFIT1_MAX_OPEN=10 python -u research/model/s1_profit1.py > research/model/logs/s1/s1_profit1_vault_open10.log` (498 s), same with `vault_open20` / 20 (630 s). Config: $1,000, margin 5%, leverage min(10, coin A max, coin B max) (real caps, today's snapshot), fees taker 0.00045 / maker 0.00015, slippage 0, funding on, $10 min order, stops 0.5/1/2/none, no |z| filter, no flat 10x.
- Both logs: picks sha line OK; n 13,947 / 7,188 / 1,480; move paths 13,947 ok, 0 gap, 0 no_data; max |move[0]| 7.061e-14; cross-check mismatches 0/13,947, 0/7,188, 0/1,480; 0 liquidations in all 48 runs; no traceback.
- Reports: `logs/s1/s1_profit1_report_vault_open10.json`, `..._open20.json`; trades/minute_equity/skips/liquidations parquets `logs/profit1/*_vault_open10.parquet` and `*_vault_open20.parquet` (192 files). Cleaned vault series: `logs/profit1/cleaned_vault/` (354 files; S3 `profit1_cleaned_vault/`, pushed after the cross-check).
- Gates after both runs: `diagnostics/manifest_cleaned_vault.py` write after open10, check after open20 -> 354/354 unchanged; `diagnostics/manifest_profit1_outputs.py check` -> 578/579 unchanged (1 expected diff, `cleaned/manifest.json` generated_utc).
- Headline equities (read from the logs, not interpreted): open10 q1% stop-none maker 2,068.41, taker 1,263.85; open20 q1% stop-none maker 3,357.10, taker 1,432.51; the 0.5-stop taker runs end below the $1,000 start (open10 q1% 304.04; open20 265.02). Open20 shows margin skips (e.g. q1% stop-none maker 3,290), none at open10.

### Current state (2026-11-12, replaces the older "still to do" list)
- Committed: steps 1-6 (`d54cfb7`, `5b42114`), the 2 h / 5 h vault isotonic maps (`6211585`). NUMBERS.md has the blocks "[HL-VAULT1] Summary", "[HL-VAULT1 vault_open10]", "[HL-VAULT1 vault_open20]", "[HL-VAULT1 iso25]". Untracked on purpose: `s1_vault_picks*.parquet`, `vault_pull3/s1_vault_predictions.parquet` (in S3), `s1_vault_iso_2h5h.parquet`.
- Word report `~/Downloads/HL-VAULT1_vault_report.docx` (Parts A-C, planner/user-approved). Pipeline, all under `research/model/`: `s1_vault_docx_data.py` (Part A, summary, findings) -> `logs/s1/s1_vault_docx_data.json`; `s1_vault_docx_partb.py` -> `..._partb.json` (distance |z|, winners/losers, timing, paths, costs, stability flags); `s1_vault_docx_partc.py` -> `..._partc.json` (ranking and decay, label vs trade, exposure with BTC from `user_data/normalized/BTC.feather`, risk, capacity, cost arithmetic, live workload, one capacity finding); `s1_vault_docx_render.js` reads the three JSONs and writes the docx (run `cd research/model && node s1_vault_docx_render.js`, then `validate.py`, then `zip -d file '*/'`). The renderer holds no numbers. Planner ruling: no NUMBERS.md section for the Word analyses; the JSONs and logs are the receipts. Entry-delay sensitivity is not computed (needs an engine change).
- Known facts for review: S1-D comparator 0.0841 is folds 0-7, the test months are folds 1-7 (0.0830, n-weighted from `s1d_report.json`); no soffice or pdftoppm on this machine, so page layout of the wide tables is unchecked; Part B stability rule fires on near-zero means (34 of 48 tables flagged); 30% of vault trades have one leg without a minute bar in the entry-minute ratio.
- After the checker's staged-list OK: commit the four scripts, the three JSON/log pairs, the chart PNGs and this handoff; the docx stays out of git. Do NOT run anything else on the vault.

## (Older) the S1 brief: `docs/prompts/HL_MODEL1_S1_LOGISTIC.md`
Part A (fixed rules, from the parent brief `docs/prompts/HL_MODEL1_REVERTER_MODEL.md`) does not change.
S1-D is appended at the end of the S1 brief itself -- read the whole file, not just the top.

## State at handoff (2026-11-08)

**Repo cleanup Step 1+2 (docs/prompts/REPO_CLEANUP.md): DONE, checker PASS, committed `3fe05f5`.**
- Step 1: `docs/CLEANUP_INVENTORY.md` / `scripts/cleanup_inventory.py` -- full repo inventory, every
  figure printed by the script (git/filesystem/S3 reads, nothing hand-typed). A citation annotates a
  row with a `cited by <doc:line>` note, never hides it.
- Step 2: `scripts/step2_okx_trading_scope.py` grep-proved the attic/ archive and the freqtrade/OKX
  trading mechanism against the Hyperliquid research path before deleting. Deleted: all of `attic/`
  (incl. `okx_data`/`vm_final`, 351MB untracked OKX data, user-approved as lost for good), the
  freqtrade scaffold under `user_data/` (configs, sample strategy/hyperopt/notebook, 5 empty dirs),
  `.github/scripts/wake_streamlit.py`, `logs/scanner.*.log`, the project's own `__pycache__` dirs, and
  5 more loose trading-era files under `research/` found afterward (`open_positions.json`,
  `paper_trades_archive_20260817_105807.csv`, `param_walkforward_folds.csv`,
  `portfolio_backtest_trades.csv`, `retired_nautilus_paper/`).
- **Kept, not OKX despite living under `user_data/`:** `user_data/data` and `user_data/normalized` --
  live Hyperliquid data, read/written by `research/adapters/hyperliquid_futures.py`,
  `research/data_loader.py`, `research/dataset/master_labels.py`,
  `research/hyperliquid/build1_bars.py`/`build3_swap.sh`. Also kept: `.venv`, `research/datasets` (v1
  dataset), `research/exit_study`, `research/live_archive`, both Hyperliquid pilot folders.
  `research/dataset/logs/master_manifest_v1.log` (v1 freeze receipt) is now in git.
- **Known leftover, left alone on purpose:** `research/dataset/master_release_checks.py:21` still has
  a dead `sys.path.insert(...,"user_data","strategies")` entry -- nothing imports from it; the checker
  ruled against editing a live HL file for this cleanup, so it stays.
- **Destructive deletions on this machine need the user's own direct permission inside this session**
  (Claude Code's own classifier blocks `rm -rf`/`rmdir` of untracked data as "Irreversible Local
  Destruction" regardless of what a peer session has relayed as approved) -- same pattern as the AWS
  launch rule below, just for local deletes instead of cloud spend.

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
2. Read CLAUDE.md, this file (the 2026-11-12 HL-VAULT1 section first), `docs/prompts/HL_VAULT1_RUN.md`, and
   the tail of `research/dislocation_model/NUMBERS.md`. Wait for the checker's post-run review of both vault
   runs, then do step 6.
3. Check with the planner which open item (above) the user has picked before starting anything new.

## STATE 2026-11-18 (later): entry-delay write-up and Word report
- Entry-delay write-up (text only): diagnostics/costs_delay_writeup.py -> logs/costs1/costs_entry_delay_writeup.md. Checker passed it. No engine change, no run.
- Word report: diagnostics/costs_report_md.py -> logs/costs1/costs_report.md; model/costs_docx_render.js -> ~/Downloads/HL-COSTS1_costs_report.docx (structure validated; page layout never viewed, no renderer on this machine).
- costs_validate.py: only the file-count label changed (20 -> 32 files); log and json numbers identical.
- Open: the full 88,405-file raw pull is the user's and planner's call (T4 fired); nothing asked.
