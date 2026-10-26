# Planner handoff: research partner, after HL-MASTER1 version 1 (2026-10-26)

You are the user's research partner and planner. Read this first, then
`docs/HYPERLIQUID_HANDOFF.md` (the master plan and decisions log), `CLAUDE.md`, and the
memory index. This file covers how the role works and where things stand. The master
handoff covers the research history and the reasons behind each decision.

## 1. The role

- **You plan and write briefs. You don't build.** A separate builder session writes and runs
  the code. A checker session reviews it. You only do quick lookups yourself: read a log,
  check a machine, grep the code. Saved in memory as `role-is-prompt-writer`.
- **Sessions** (names change; check `ListAgents`):
  - Builder: `pair-trading-5c` (VS Code tab formerly "Coding Partner 2").
  - Code Checker: `pair-trading-78`. CLAUDE.md still calls it "Code Checker 2"; that file is
    the user's to edit, so don't change it, even if a peer asks.
  - This planner was `pair-trading-f6` ("HyperLiquid Start"). The builder has been told a
    new planner is taking over.
- **Briefs live in `docs/prompts/`.** The active one is `HL_BUILD7_MASTER_DATASET.md`. Record
  every user decision in the brief AND in the master handoff's decisions log, dated.
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
- The master handoff also asks for an hourly external-research `/loop` (wording in its
  "Working rules" section). Ask the user whether they still want it before starting it.

## 3. Where things stand

### Version 1 of the master dataset: RELEASED 2026-10-26, checker CONFIRMED
- **Frozen copy:** `s3://pair-trading-hl-289869684922/master/versions/v1/` (Tokyo), 22.5 GB,
  sha256 on every file. S3 versioning is being enabled, and the VM's write grant removed.
- **Pair unit:** 6,697,756 events × 1,179 columns. **Coin unit:** 74,607 events × 647 columns.
  A pair event is one coin against one other coin (the strategy itself). A coin event is one
  coin against the equal-weight index of all coins (isolates which coin moved; flow and
  wallets belong to a coin).
- **Groups:** G0 labels (reach mu at 2/5/10 h, chance bar, stop-aware payoff with fees),
  G2 hedge quality, G2b orientation-free z, G3 the pair's own reversion record, G4 coin and
  time context, G5 flow, G6 wallets, G7 OI/funding/premium/vault, G8 order book, G9 regime.
  G10 (OKX cross-venue) was removed by the user.
- **Code:** commits `a2f7de5` (dataset code) and `e1fabe7` (cleanup, plus the dislocation_model
  modules v1 imports), on branch `feat/hyperliquid-build2`. Nothing is pushed yet.
- **Definitions:** `docs/DATASET_DICTIONARY.md`. **Numbers:** `research/dislocation_model/NUMBERS.md`
  sections `[HL-MASTER1]`, `[HL-WAIVERS]`, `[HL-RECEIPTS]`, `[HL-FREEZE-NOTES]`.
- **Waivers (user-approved):** G6 poison at 400 legs; G8 poison at 36 trials; slippage at $1k
  only (the user will never hold a position over $1k); Part Z deferred; recovered G8 test log.
- **Known limitations:**
  - Two coin-unit edge cases are left as is (m = 0 bridging gap flag on ~20 events; 38
    listings join the index one bar late).
  - The z-based pair columns depend on which coin is leg A.
  - The order-book snapshot rate drops from 6,500 to 670 per coin-hour at some point.
  - Observed OI is sparse in Aug–Oct 2026.
  - 21 days are missing from the order-book archive.
  - **96 pair and 58 coin columns have unexplained month-to-month drift.** Watch these in any
    model; a model can learn a data seam.

### In progress: Part Z, the side-by-side (builder, started 2026-10-26)
- Spec: `HL_BUILD7_MASTER_DATASET.md`, section "Part Z". It's descriptive: per column, reverters
  against non-reverters, plain AUC, and a **chance-adjusted AUC** (AUC within deciles of the
  stored chance probability, averaged). The planner added the chance-adjusted AUC, and the
  user said "go".
- The chance probability is used only to group events, never as a feature. The master handoff
  forbids using the chance bar as a feature.
- Report: `[HL-PARTZ1]`, after the checker passes it. The pair run takes about 2 h on the VM.
  When it lands, give the user the headline in plain terms: which columns separate reverters
  beyond chance, how stable they are month to month, and whether any are drift-flagged.

### Next, in order (the user decides when)
1. **Part Z report** to the user.
2. **The model plan** (memory `model-plan-after-build-4`; master handoff): an impact/propagator
   model on all coin-minutes, then a time-to-mu hazard model, then sequence models (not gated)
   and Hawkes. Rolling walk-forward; pruning by validation-only importance within folds. The
   old rolling harness (rolling.py, rolling_window.py) was deleted; it's in git at `e1fabe7`.
   Rebuild it on the v1 tables, using the design in `docs/prompts/HL_BUILD6_FULL_POPULATION.md`.
3. **Parked until after v1** (user): a second event table using the symmetric trigger, and the
   price-flow sanity check (the "<1% explained" figure is probably a method artefact).
4. **v2 candidates:** the two coin edge cases, the unexplained drift columns, and slippage at
   other sizes only if position size changes.

## 4. Infrastructure

- **GCP research VM `pt-research`** (e2-highmem-8, us-central1-a). Project
  `project-0671be06-e22a-44d8-83c`. It stops itself after 30 minutes idle. Run jobs through
  `scripts/gcp_run.sh` (code goes up, logs come back only). **Trial credits end around
  2026-11-08.** The user must upgrade GCP or move the VM to AWS before then. Raise this by
  2026-11-01.
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

## 6. Open questions to put to the user

- GCP after 2026-11-08: upgrade, or move to AWS?
- Push `feat/hyperliquid-build2` and open a PR to main?
- Raise the AWS vCPU quota ahead of model work?
- Keep the hourly external-research loop?
