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

## 3. Where things stand (updated 2026-11-12)

Full history: the decisions log in docs/HYPERLIQUID_HANDOFF.md. Numbers: research/dislocation_model/NUMBERS.md.

### Model (HL-MODEL1, S1 penalised logistic, hazard framing)
- Gate FAIL (pooled top-10% lift 0.0394 < 0.05). Live Rule A picks (top q% of p_10h vs the previous block's
  quantile) keep the edge: S1-F/S1-G. Isotonic recalibration per horizon (S1-H) fixes calibration: top 1% at 10 h
  67.9% predicted vs 67.7% actual; also 2 h 34.2 vs 34.7, 5 h 54.2 vs 54.7 (NUMBERS [HL-MODEL1-S1-H]).
- **Pre-vault model saved COMPLETE** (HL-VAULT1 step 2b): fit on all 5,378,429 search events, fold 7's lam 14187.2,
  l1_ratio 0.5; KKT 2.2e-08; 192 non-zero weights; S3 s1_vault/logs/outputs/ and research/model/logs/s1/vault_pull2/.
  Known gap (user-accepted): the fold 0 reproduction (2a) missed its strict tolerance; max |dp| 0.001748 / 0.002003
  / 0.001832 (2/5/10 h), start-point dependence. This model is what paper trading would start from (a second refit
  including the vault only if the user likes the vault result).

### HL-PROFIT1 backtest (test months 2025-12-21..2026-07-11, 203 days), committed, checker PASS
- Engine research/model/s1_profit1.py: $1,000 cross margin, 5% margin/trade, leverage min(10, coin caps) (avg
  3.4x; 85.7% of trades on 3x-capped pairs), max_open 10 (also 20), HL fees 0.045% taker / 0.015% maker per fill,
  slippage 0 (user), funding on, $10 min order, stops 0.5/1/2/none. Prices = build2 d3/asm 1m trade prices (what v1
  used), cleaned copy in S3 profit1_cleaned/.
- Best: q1% no stop maker $5,034 (10 open, DD -9.8%), $16,936 (20 open, DD -17.5%). Every loser = taker + stop.
  Fees ~58% of gross. |z|>=3 filter (in-sample) earns less. EV quintiles don't rank profit. Word report
  ~/Downloads/HL-PROFIT1_backtest_24_runs.docx. Horizons analysis (98c74c9): high p_2h/p_5h = faster reversion and
  higher win rate (q1%: 64.6% -> 71.7% by p_5h quintile) but flat profit/trade; trades still open at 5 h end ~-0.5%.
- Flat 10x runs: DROPPED (user).

### HL-VAULT1 (brief docs/prompts/HL_VAULT1_RUN.md) -- IN PROGRESS, vault OPENED 2026-11-12
- Vault = 2026-07-13..2026-10-13, 1,280,088 events. No pass/fail rule (user). Steps 1-3 done and checker-passed
  (coverage; pre-vault model; scoring, sha ede424aa..). Step 4 picks: cut-offs from fold 7 (0.7295 / 0.7809 /
  0.8779), picks 13,947 / 7,188 / 1,480; p_cal isotonic on folds 0-7, guard <= (planner ruling = S1-H literally).
- Step 5: vault_open10 done (0/13,947 cross-check mismatches, 0 liquidations); PROVISIONAL, not checker-reviewed:
  q1% no stop maker $2,068, taker $1,264; q0.5% none $1,777/$1,269; q0.1% none $1,230/$1,083; taker+stops lose.
  vault_open20 was running 2026-11-12. NEXT: checker post-run review of both, step 6 report (side-by-side with the
  test months, vault calibration at 2/5/10 h), commit. See BUILDER_HANDOFF.md for files and what is uncommitted.

### Parked (user's order: after the vault, analysis only)
- Picks = Rule A AND high corrected p_5h ("safer" picks); a 5 h time-exit test; a maker-only fill model; real
  slippage from the fills archive; sizing (max_open, margin); fee levers (maker orders, HYPE staking).
- Paper trading needs: the final refit including the vault (user's yes), live feature build timing.

### How to work (lessons this round)
- Token-limited: one message per finished step, no acknowledgements, no polling crons, fresh sessions often.
- AWS: every launch gets a watcher that survives API errors; userdata must upload its log even on early failure;
  preflight every file each step opens from a clean payload extract. Three launches failed on startup this round.
- Word reports: run the docx skill's validate.py. Numbers in prose come from script output only.

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
