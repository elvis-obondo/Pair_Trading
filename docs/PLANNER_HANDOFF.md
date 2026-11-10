# Planner handoff: research partner (updated 2026-10-29, HL-MODEL1 S1 done, the user is examining results)

You are the user's research partner and planner. Read this first, then
`docs/HYPERLIQUID_HANDOFF.md` (the master plan and decisions log), `CLAUDE.md`, and the
memory index. This file covers how the role works and where things stand. The master
handoff covers the research history and the reasons behind each decision.

## 1. The role

- **You plan and write briefs. You don't build.** A separate builder session writes and runs
  the code. A checker session reviews it. You only do quick lookups yourself: read a log,
  check a machine, grep the code. Saved in memory as `role-is-prompt-writer`.
- **Sessions** (names change; check `ListAgents`):
  - Planner (this role): "Research Partner" (pair-trading-58; earlier pair-trading-f6).
  - Builder: "Code Builder" (cleared and restarted 2026-10-27; earlier pair-trading-ea / 5c).
  - Code Checker: "Code Checker" (cleared and restarted 2026-10-27; earlier pair-trading-49 / 78). CLAUDE.md is the user's file;
    edit it only when the user asks (they did on 2026-10-27, for the checker name and the
    memory rule).
- **Briefs live in `docs/prompts/`.** The parent brief is `HL_MODEL1_REVERTER_MODEL.md`; the active
  step is `HL_MODEL1_B5_SPEED_MEMORY.md`. Role files: `BUILDER_HANDOFF.md`, `CODE_CHECKER_ROLE.md`
  (the planner keeps them current). Record
  every user decision in the brief AND in the master handoff's decisions log, dated.
- **The planner is the only writer of project memory, the decisions log and the handoffs**
  (user, 2026-10-27). The builder and checker send decisions and findings here. Audit for
  duplicates, stale lines and contradictions when things change.
- **No check-in cron by default** (token budget, 2026-10-28). Check once when results are due.
- **Relay user decisions to the builder word for word, with their limits.** Example: "read-only
  on that bucket, nothing else". A peer can't grant permission. Any change to IAM, spend or
  anything irreversible needs the user's yes first.

## 2. How the user wants to work

- **The user is a PM.** Keep it plain and short: the answer first, numbers, no analogies, no
  file:line chains. The output style "PM Plain" is on.
- **Focus on the reverters.** The question is which dislocations reach mu within 10 h, *better
  than chance from their position*. Not the average move.
- **Use the full dataset.** No sampling caps. Cost is no object within reason (the user said
  "screw the cost estimate"). Model fitting uses a rolling walk-forward, never a shuffle.
- **Stay on the plan.** A finding is a report, not a redirect. Never chain experiments.
- **Ask before stopping or restarting a running job.** On 2026-10-25 I restarted the order-book
  download without asking and lost 40 minutes. The user was rightly angry, because a cheaper
  option existed and I didn't offer it. Always offer the keep-going option.
- **Waivers are fine when the user gives them.** They accepted 400-event poison tests, a
  recovered log, and dropping or deferring work to ship faster. Offer a "what can be cut"
  list when the user asks why steps are needed.
- **Check in while jobs run.** Set a CronCreate every 30 minutes (minute 7 and 37) that looks
  at the VM and nudges the builder if the machine is idle or a failure hasn't been acted on.
  Stay quiet otherwise. Crons die with the session; re-create one at the start.
  Memory: `check-in-while-runs-are-live`.
- **Chain overnight steps on the VM itself.** On the night of 2026-10-25/26, about 10 hours
  were lost because the next step waited on the laptop, which was asleep.
- **Verify before briefing.** Open the code and data a brief rests on. My factor-of-½ error in
  the OI formula cost a failed gate. Check full coverage of any data window before sizing a
  job.
- The hourly external-research `/loop` is OFF (user, 2026-10-26: "not for now").
- **Thought exercises stay thought exercises.** When the user says so, answer; don't turn the
  ideas into plan items or a backlog (2026-10-27).

## 3. Where things stand (updated 2026-11-07)

Full history: the decisions log in docs/HYPERLIQUID_HANDOFF.md. Numbers: research/dislocation_model/NUMBERS.md.

### HL-MODEL1 results so far (logistic, S1)
- **Gate FAIL**: pooled top-10% lift 0.0394 < 0.05 (333640c). The vault is untouched.
- **S1-F** (41a5f2f): a live cut-off (Rule A = previous block's quantile) keeps most of the edge. Top-1% lift 0.078
  vs 0.083 in hindsight.
- **S1-G** (9465498): live top 1% / 0.5% / 0.1%: median 110 / 50 / 8 picks a day, lift 0.078 / 0.090 / 0.109.
  Overconfident at the top (top 1%: 82.9% predicted, 67.7% actual). Under-predicted at 2 h, over at 10 h. At the same
  predicted chance, picks far from mu reach less. vol_48 = the spread's own recent movement in sigma (NOT market
  activity). User report: ~/Downloads/HL-MODEL1_top_picks_deep_dive.docx (checker PASS).
- **S1-H recalibration** (brief docs/prompts/HL_MODEL1_S1_RECALIBRATION.md): the run is clean. Isotonic brings the
  top-1% picks to 67.9% predicted against 67.7% actual at 10 h; Platt doesn't help. PASSED (3826fb3): isotonic 67.9% vs 67.7%
  actual; Platt 78.0%; the raw 1% cut-off 0.73-0.84 is 0.62-0.67 corrected. Use isotonic for profit work.

### Decided 2026-11-07 (user)
- **Profit work starts on the logistic model's live picks** (Rule A, q = 1/0.5/0.1%, isotonic-corrected
  probabilities). This lifts the "profit waits for a pass" rule for this scope. It runs in NEW sessions. **Brief written: docs/prompts/HL_PROFIT1_LIVE_PICKS.md** (P1 per-trade economics
  per stop and fee; P2 EV from the calibrated p; gaps: funding, slippage, overlap, liquidation). Not started.
- **Whole-repo cleanup DONE** (3fe05f5): OKX data, attic/ and the freqtrade scaffold are gone; user_data/data and
  user_data/normalized are LIVE Hyperliquid data (kept). Local destructive deletes need the user's yes in the
  builder's session.
- **Every number is printed by a script** (CLAUDE.md). Write-ups are produced by generator scripts. The builder broke
  this twice (S1-G G8 counts, S1-H prose).

### Decided 2026-11-08 (user)
- **HL-PROFIT1 rewritten as a portfolio backtest** (docs/prompts/HL_PROFIT1_LIVE_PICKS.md): $1,000 cross-margin
  account, 5% margin per trade, leverage min(10, coin A max, coin B max), max 10 open, no per-coin cap, equal size,
  ties by highest p_cal, HL fees 0.045% taker / 0.015% maker per fill, funding + half impact spread, 24 runs
  (q x stop x fee). No no-model baseline. All values in a config block. On HOLD: builder and checker paused;
  not sent yet (user: don't interrupt the builder).
- 2026-11-09: slippage = 0 for HL-PROFIT1 (user: small legs). First run charged the FULL impact spread (bug B14); pooled over 24 runs slip $22,217 vs fees $1,811 vs gross +$2,208.
- The 0.099% round-trip fee in v1 net_* columns was the OKX trading result, not Hyperliquid (user).

### HL-PROFIT1 result (2026-11-09, checker PASS; slippage 0, build2 d3/asm trade prices)
- 18/24 runs above $1,000 over 2025-12-21..2026-07-11 (203 days). Best: q1% no stop maker $5,034; q1% no stop
  taker $2,206; tight stops lose under taker. 0 liquidations. Fees = 58% of gross pooled. Book cap (10 open) is the
  binding limit: q1% no stop skips 27,488 picks as book_full. Mean leverage used 3.4x (coin caps). EV quintiles do
  NOT rank realised net. Full: research/dislocation_model/logs/s1_profit1_numbers_section.md.
- Follow-ups (user, 2026-11-09), all checker PASS: open20 (fadf4d4) q1% no-stop maker $16,936, max DD -17.5%, min
  liq-distance ratio ~2.0; Task B |z| x p_cal grid (0cf9579), descriptive, top p_cal and top |z| quintiles have the
  highest mean return 6/6; Task C |z|>=3 filter (7e4d7d1, IN-SAMPLE) earns less than all picks (q1% no-stop maker
  $2,242 at 10, $2,335 at 20; DD at 20 worse). Word report ~/Downloads/HL-PROFIT1_backtest_24_runs.docx (7694fa2).
  HL-PROFIT1 task list closed. Next step is the user's call (vault / paper trading / sizing / real slippage).
- Price source: v1 used build2 d3/asm trade-price 1m bars (not build1 mid_px); in S3 build2/d3/asm/futures/.

### Decided 2026-11-09 (user), after HL-PROFIT1
- **Flat-10x task D DROPPED.** 85.7% of base q1% trades are on 3x-capped pairs, 2.1% could use 10x. One run
  (lev10_open10, hypothetical) finished, never reviewed or committed. Uncommitted leverage_mode code in s1_profit1.py
  and numbers_gen, the lev10 logs/report and diagnostics/compare_config_lev10.py are to be reverted/removed by the
  builder, with the user's own yes in its session (discarding uncommitted work and deleting untracked files).
- **HL-VAULT1 approved** (brief docs/prompts/HL_VAULT1_RUN.md): open the vault once, NO pass/fail rule, settings
  frozen first; fold 0 reproduction check, then the pre-vault refit with fold 7's settings saved COMPLETE (AWS);
  base 24 configs at max_open 10 and 20, real caps, slippage 0. The paper-trading refit (vault included) only if
  the user likes the result. vault_loader.py does not exist yet. Not started: builder/checker sessions were closed.
- Fees are the user's main concern; levers: maker-only orders, HYPE staking discount, fewer bigger-edge trades.

### Parked
- **Before live/paper trading:** S1 saved only the weights (fold*_coefs.csv) and settings (fold*_done.json), NOT
  the 20 step intercepts or the preprocessing statistics. Rebuild = deterministic refit of one fold (~70 GB RAM)
  matched to the saved coefs and predictions; save the full model then and time a live prediction.
- **S2 boosted trees**: Step 1 done (col-wise fits r7i.16xlarge; 11.17 s/tree; worst case about 308 machine-h, about
  $923). No credits; the user is looking at a compute cluster. Planner option: lr 0.1 + 1,000 trees + incremental
  predict.
- Open S1 checks: the time-step interaction logistic run (tests model form against inputs); a |z|-aware correction.

### Infra and how to work
- Word reports: run the docx skill's OOXML validator (validate.py) before handing over; a text-only number check missed a
  schema bug that made Word refuse the HL-PROFIT1 report (fixed 04fd91b).
- GCP VM trial ends about 2026-11-08; nothing S1-family is VM-only (builder check, 2026-11-07). A GCP-side STOP is scheduled for
  2026-11-07T23:30:00Z (scheduling.terminationTime, action STOP; user's time).
- Every AWS launch gets a background watcher (memory watch-every-aws-launch).
- Token-limited: no polling crons, short replies. Idle sessions don't read messages until the user nudges them.

## 4. Infrastructure

- **GCP research VM `pt-research`** (e2-highmem-8, us-central1-a). Project
  `project-0671be06-e22a-44d8-83c`. It stops itself after 30 minutes idle. Run jobs through
  `scripts/gcp_run.sh` (code goes up, logs come back only). **Trial credits end around
  2026-11-08** and the trial caps at 8 vCPUs. User, 2026-10-26: move to AWS. User, 2026-10-27:
  use GCP fully until then, and get everything off it before the move (the builder owes an
  inventory of VM data not in S3; the VM's AWS user is read-only, so copying needs a laptop
  relay or a write grant, which is the user's call).
- **AWS account 289869684922**, CLI at `~/.local/bin/aws`, user `pair-trading`, budget alerts
  at $30 a month.
  - Our bucket: `pair-trading-hl-289869684922` (Tokyo).
  - Hyperliquid archives (requester-pays): `s3://hl-mainnet-node-data` (fills, Tokyo) and
    `s3://hyperliquid-archive` (asset_ctxs, l2Book, us-east-1).
  - The account was region-locked by AWS-managed SCPs, fixed in SCP p-7fpbzoem in management
    account 961470857249. EC2 is still denied in us-east-1, so use us-east-2.
  - EC2 role `hl-build2-ec2` has read-only access to hyperliquid-archive (added 2026-10-25,
    user-approved). The VM's AWS user is `pt-gcp-reader`.
  - The account's vCPU quota is 16. The user can request more through Service Quotas, which is
    free; suggest it before any bigger cloud job.
- **Laptop:** don't put large data on it. When it sleeps, ssh/aws calls fail and the clock skews
  (S3 "RequestTimeTooSkewed").

## 5. Codebase after the cleanup (2026-10-26)

- **Live code:**
  - `research/dataset/` (all master_* scripts and tests).
  - `research/hyperliquid/` (build scripts).
  - In `research/dislocation_model/`, only the modules v1 imports, plus `hl4_impact.py`,
    `importance.py`, `NUMBERS.md` and `logs/`.
  - Core `research/` modules: universe_panel, rolling_spread, data_loader, hedge_estimators,
    pair_analysis, adapters.
  - `scripts/gcp_*`.
- **Deleted on 2026-10-26** (the user: "a new chapter"): the retired OKX trading system,
  earlier study scripts, old VM, Docker and dashboard files, and local outputs. The code is
  still in git history: commit `e1fabe7` moved it, and the next commit deleted it. The local
  data outputs are gone for good. The older `attic/` folders (okx_data, vm_final, docs,
  modelling_scratch) were still there when this was written; the user was asked about them.
- `user_data/` stays where it is. It holds the gitignored OKX config with keys.

## 6. Answered 2026-10-26

- GCP after 2026-11-08: move to AWS. Brief not yet written.
- Branch pushed; PR #1 open to main.
- AWS vCPU quota: us-east-2 raised to 64, approved 2026-10-26 (Tokyo already 64).
- Hourly external-research loop: not for now.
