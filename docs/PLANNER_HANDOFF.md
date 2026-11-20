# Planner handoff: research partner (updated 2026-11-20, HL-TARGET2 step A)

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
- **No check-in crons by default** (token budget; memory `save-tokens`). Check once when results are due.
- **Chain overnight steps on the VM itself.** On the night of 2026-10-25/26, about 10 hours
  were lost because the next step waited on the laptop, which was asleep.
- **Verify before briefing.** Open the code and data a brief rests on. My factor-of-½ error in
  the OI formula cost a failed gate. Check full coverage of any data window before sizing a
  job.
- The hourly external-research `/loop` is OFF (user, 2026-10-26: "not for now").
- **Thought exercises stay thought exercises.** When the user says so, answer; don't turn the
  ideas into plan items or a backlog (2026-10-27).

## 3. Where things stand (updated 2026-11-20, for a fresh planner session)

Full history: decisions log in docs/HYPERLIQUID_HANDOFF.md ("What is closed" holds the COSTS1 entry). Numbers:
research/dislocation_model/NUMBERS.md and the section files named below. Sessions: Planner, Code Builder, Code
Checker; names change, find them with ListAgents.

### ACTIVE: HL-TARGET2 (brief docs/prompts/HL_TARGET2_NET_BP.md), step A in progress
- Why: S1 ranks real reversion but its dollar edge does not survive costs (COSTS1 below). HL-TARGET2 retrains on a money target.
- User decisions (2026-11-20): target = net bp per trade at book-midpoint prices; cost = taker (4.5 bp/fill + book
  half-spread + funding); exit = mid spread reaches mu, else minute 600. Same events and signal as S1 (trigger from closes).
  The user rules the data fresh for the new target (test months and vault); discipline: design choices justified from
  test-month evidence and written down before the vault is scored once at the end.
- Step A COMMITTED (2281687) but NOT checker-passed (checker 2026-11-20: no PASS given; 3 blocking text/receipt fixes with the builder: hard stop on per-leg flag in section 7 too, store exit-mid source, availability stage computes trigger and exit minute only). Rules research/model/s2_target_rules.md, sizing diagnostics/s2_target_sizing.log.
  Rulings: mid forward-fill per leg up to 5 min; exit price = first real mid at/after trigger; per-leg gap flag (union =
  sensitivity); stops before labels if >10% of test-month events flagged or >1% dropped by the 60-min exit-mid cap.
  2025-06..2025-12-19 events (42% of search) are G8-only; sample suggests ~40% flagged there: a step C question.
- Label build: user go 2026-11-20; checker PASS on code; vault y built now (own file, unread); trial first, then full run.
  Step B (after the planner's go): ceiling check on TEST MONTHS only (how much y > 0 exists; visible before entry?).
  Step C: refit on the new target, only if B shows something, and only on the user's yes.

### S1 results that shaped this (all checker PASS, committed)
- HL-MODEL1 S1: penalised logistic, reach-mu label from closes. Pre-vault model: 192 non-zero weights of 2,377
  (research/model/logs/s1/vault_pull2/, S3 s1_vault/). Weights (0e305c1): events group 36% of |w| (threshold -0.355,
  vol_48 +0.275, sigma -0.187); flow groups G6/G7/G8 ~6%; coin one-hots 0. It mostly finds noisy, jumpy spreads.
- HL-PROFIT1 / HL-VAULT1 (zero slippage, close prices): test months 18-19/24 runs above $1,000, vault 12/24; top-1%
  lift vault 0.0621 vs 0.0841. Reports ~/Downloads/HL-PROFIT1_backtest_24_runs.docx, HL-VAULT1_vault_report.docx.
- HL-COSTS1 (0d2fb83..9a36aa1; report ~/Downloads/HL-COSTS1_costs_report.docx): verdict (c), every costed run loses
  (vault maker -$703/-$1,645, taker -$874/-$1,569). Cause: last-close prices sit favourably vs book mid in thin coins.
  No-bounce: mid/close gross 53.8% vault, ~20% test; test least-liquid third 16-18%, most liquid 56-81%; ranking holds
  at mids (top-1% lift ~2.1x). Leg split: no one-coin story; mover label is hero and culprit alike (4f7e59a).
- Open, user's call, not commissioned: full raw order-book pull (planner: no); entry-delay run (engine change + Tokyo
  G8 pull + skip rule); limit-order placement study; fee levers (HYPE staking tiers, volume tiers).
- Trade sizes: median win ~$1.5, loss ~$3.5, average trade +$0.07 to +$0.28 (5-12 bp) at zero cost.

### How to work (lessons this round)
- Token-limited: short replies, one message per finished step, no acknowledgements, no polling crons.
- Rule questions from the checker come to the planner; fix them BEFORE results are seen and say so.
- Relays can be wrong: check a peer's summary sentence against the table before repeating it (2026-11-20 "every leg
  group negative" was a relay error, not in the report).
- AWS: checker reviews launch files first; the user's yes for EACH launch in the builder's session; watcher on every launch.
- Word reports: docx validate.py; layout unviewed on this machine, the user opens once.

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
