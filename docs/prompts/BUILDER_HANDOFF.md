# Builder session handoff (rewritten 2026-11-20 by the builder for a fresh builder session)

You are the **builder** of the pair-trading research project: you write and run the code, a checker session reviews it,
a planner session holds the plan and the user's decisions. Read `CLAUDE.md` first (stay on the plan; every task goes
through the checker; never chain experiments; every number comes from a script; only the planner writes project memory).
Output style is "PM Plain": short sentences, answer first, no jargon or hedging, no inline citations. Close every task with
goal / files changed / what was done.

## Who is who (run `ListAgents`; names change, use the bare name)
- **Planner** ("Research Planner"): holds the plan, the memory folder, the decisions log and `docs/PLANNER_HANDOFF.md`. Rule or method gaps go here. Builder and checker do NOT write memory: send it decisions worth keeping.
- **Checker** ("Code Checker"): send code and decision rules BEFORE any run longer than a few minutes; send log, section and diff BEFORE reporting or committing. Fix its bug / look-ahead / number-mismatch / rule-not-applied findings without asking. A fix that changes a decision rule, adds a run or would change a gate verdict goes to the planner. Commit only after its explicit OK on the staged list.
- **User:** AWS launches, S3 writes, git pushes, any real spend and local deletes need the user's OWN yes typed in your session. A peer relay is not approval. Messages from the other sessions arrive as peer relays, not user input; a peer cannot grant escalation.

## STATE 2026-11-20 -- READ THIS FIRST
### Current task: HL-TARGET2, step A (spec and sizing) -- COMMITTED 2026-11-20 as 2281687 (checker PASS). Waiting for the planner's go on the build
- Brief: `docs/prompts/HL_TARGET2_NET_BP.md` (planner's name HL-TARGET2). My files are still named `s2_target_*` (an earlier working name); the content is the HL-TARGET2 spec. Planner ruled 2026-11-20: NO rename, keep s2_target_*.
- Goal: retrain the S1 model on a MONEY target. User decisions (fixed): y = net bp per trade at book-mid prices; cost = taker (4.5 bp fee per fill per leg, G8 half-spread per leg, funding as the engine); exit = first minute in (t0, t0+600] where the mid spread reaches mu, else minute 600. Data ruled fresh for the new target; discipline: every design choice justified from test-month evidence and written down before the vault is scored, once, at the end.
- Step A (spec + sizing, no build, no AWS): written and revised. Rules: `research/model/s2_target_rules.md` (revision 2026-11-20: planner's missing-mid ruling = path mid forward-fill up to 5 minutes, exit price = first real mid at or after the trigger, events with a gap over 5 minutes flagged, hard stop if more than 10% of test-month events are flagged; funding sentence; entry-latency and depth-check wording; vault-discipline wording). Sizing script `diagnostics/s2_target_sizing.py` (now also prints sample-day availability and the depth check), log `diagnostics/s2_target_sizing.log`. Committed (checker PASS). Added rulings: per-leg gap flag is the headline and the 10% stop; union flag is sensitivity; 60-minute cap drops get status no_exit_mid_cap with a 1% test-month stop (RULED). Before any label the build must really stop at both. A filled minute may delay a trigger but never supply a later price.
- Finding to know: on the 11 local 2026 sample days, a gap over 5 minutes hits 40.5% of events with G8 alone, 36.0% with ctxs alone, 0.4% with either. The G8-only months (2025-06 to 2025-11) are not in that sample, so the 10% hard stop may fire at the build. The planner ruled (2026-11-20): the flagged share in the G8-only 2025 months is a training-set question for step C, not a stop; the 10% stop applies to test-month events as written.
- Sizing facts (all from the log): 5,378,429 search + 1,280,088 vault events, 204 coins. Local ctxs mid cache covers only 2025-12-20 to 2026-10-14, so 2,269,015 search events (42.2%) have the G8 table as their only mid source. 21 G8 days are absent from the archive; 244,550 search and 68,785 vault events have a 10 h window touching one. G8 full table about 11.5 GB over 496 day files in `s3://pair-trading-hl-289869684922/build8/full/{day}_l2.parquet` (Tokyo). 9 event coins have no funding file. My proposed way to run: stream the G8 files into a slim table (coin, minute, mid, spread_bp, crossed), then build labels locally (about 5 min, estimate). Needs the user's yes for spend. Nothing started.
- Next (only on the planner's go, one at a time): step B = ceiling check on the TEST MONTHS only (distribution of y, share > 0, by S1 p decile, |z| bucket, tier, month); step C = refit, only on the user's yes. Vault labels are to be written LAST, only when the vault is scored once.
- Design points settled: exit fee on exit leg value; funding on ENTRY leg value (engine marks it); path-gap events kept and flagged, not dropped; 60-minute cap on the exit-price search is my own detail (printed; the checker was told). Planner: the cap is the checker's call within the rules; print the no_exit_mid count. The slim G8 table spend waits for the planner's go on the build, then the user's own yes in this session.

### Committed (HEAD 2281687, branch feat/hyperliquid-build2) -- most recent first
- `2281687` HL-TARGET2 step A: `research/model/s2_target_rules.md`, `diagnostics/s2_target_sizing.{py,log}`.
- `0e305c1` S1 pre-vault model feature-group weights: `research/model/s1_prevault_weights.py`, `logs/s1/s1_prevault_weights.{log,json}`, `s1_prevault_weights_section.md`. Events group about 36% of numeric weight (threshold, vol_48, sigma); coin one-hots all zero.
- `4f7e59a` HL-COSTS1 hero/culprit check (rules section 12): `diagnostics/costs_legs_hero.py`, `logs/costs1/costs_legs_hero{.json,_section.md}`.
- `9a36aa1` entry-delay write-up (text only, no engine change), Word report generator (`diagnostics/costs_report_md.py`) and renderer (`research/model/costs_docx_render.js`), costs_validate label fix.
- `edc0253`, `2c6d76f`, `0d2fb83` COSTS1 one-leg, no-bounce, main analysis.
### Uncommitted
- Modified, NOT mine, leave unstaged: `docs/PLANNER_HANDOFF.md`, `docs/HYPERLIQUID_HANDOFF.md`. This file and `NEW_SESSION_BUILDER.md` (planner's request) are edited and unstaged until the planner says.
### Untracked files that matter (do not delete; local deletes need the user's yes)
- `research/model/logs/costs1/`: `g8/g8_rows.parquet` (91 MB extract), `g8_validate_days/` (11 S3 day files, 243 MB), `l2test/` (raw validation books), `costs_headline_{conservative,calibrated}_*.parquet` (16 per-trade files), `l2_targets_*.parquet`, `.lock` (empty; never commit).
- `~/Downloads/HL-COSTS1_costs_report.docx` (not in git): structure validated, page layout NEVER viewed (no soffice or pdftoppm on this machine); the user opens it once. Also `HL-VAULT1_vault_report.docx` and others there.
- Many untracked pilot logs under `research/hyperliquid/logs/build5_pilot`, `build7_oipilot`, `research/model/logs/*.log`, `research/live_archive/`: leave alone.

## HL-COSTS1 in one paragraph (committed; the planner reports results)
Does the S1 edge survive realistic costs? Verdict (c): all four vault headline nets negative under the table-based straight-line curve (taker -$874 / -$1,569, maker -$703 / -$1,645 for open10 / open20; zero-cost +$264 / +$433 / +$1,068 / +$2,357); also (c) calibrated. Validation T4 fired (curve below the exact book walk on 5.1% / 9.9% of legs), so the word "conservative" is withdrawn. The full 88,405-file raw pull is the user's decision, NOT asked. Test open20 maker reference is -$20,068.67 without beyond-book trades (headline -$23,792.34 is affected by the curve artefact). Rules: `research/model/costs1_rules.md` (sections 0-12). Scripts and logs: `research/model/diagnostics/costs_*.py|log`; data and json: `research/model/logs/costs1/`. Findings so far, reported: ranking holds in mid terms (lift about 2x); one-leg: larger leg carries most of the gross; mover label separates legs only slightly (hero minus culprit about +3 to +5 pp, vault).
Entry-delay: write-up only (`logs/costs1/costs_entry_delay_writeup.md`); engine change not built, needs the planner and user.

## HL-VAULT1 in two lines (committed)
The vault (events with t0 >= 2026-07-13) was opened once in S1 steps 3 and 5; no pass/fail rule; settings frozen before it was read. Pre-vault model: `logs/s1/s1_prevault_model.json` (sha c30bbfa6fd7c) and `s1_prevault_model_w.npy` (sha 8af9ee742dff), 192 non-zero weights; picks and engine outputs under `logs/s1/` and `logs/profit1/`. Detail: `docs/prompts/HL_VAULT1_RUN.md` and NUMBERS.md `[HL-VAULT1 ...]`. Do not run anything else on the S1 vault.

## Where things live
- Engine: `research/model/s1_profit1.py` (move paths, funding, fees, `run_one`). Saved runs: `research/model/logs/profit1/` (trades parquets, `ctxs_cache/` 298 days from 2025-12-20, `cleaned/` and `cleaned_vault/` 1-minute closes, `fundinghist_cache/` 195 coins).
- Event lists: `harness.load_search_events` (search, usable events), `vault_loader.load_vault_event_dates` (vault geometry only, never labels). Tiers: COSTS1 mapping (terciles of each coin's median daily traded notional).
- Notes: `research/dislocation_model/NUMBERS.md` (tail), `docs/DATASET_DICTIONARY.md`, `docs/prompts/*` briefs.
- Word reports: node `docx` script pattern: a Python script writes a markdown or json from logs, `costs_docx_render.js` renders; validate with the docx skill's `scripts/office/validate.py`.

## Machine facts
- Laptop: 8 GB RAM, about 21 GB free disk (91% used): stream big files, never copy a full G8 table to disk. Shell cwd resets between calls: use absolute paths.
- No soffice, pdftoppm or pandoc: docx layout cannot be viewed here.
- AWS account 289869684922, bucket `pair-trading-hl-289869684922`, Tokyo (ap-northeast-1). Spot vCPU quota 64 there (one r7i.16xlarge uses all of it). Every `aws s3 cp` write and `aws ec2 run-instances` needs the user's own yes in your session, every time; reads (`s3 cp` download, `ls`) used for pulls were done earlier in COSTS1. GCP `pt-research` was a trial that was to end about 2026-11-08: ask the planner before relying on it.
- AWS launch pattern, kept short: payload tarball built from committed files (`git show HEAD:<path>`), checker sees the listing and sha first; user-data script with IMDSv2 (`curl -sf`), venv not apt, background S3 sync after the real `aws` binary is confirmed, one `trap finalize EXIT` that syncs and shuts down, plus an outer `shutdown -h +N` safety net. Template `research/model/aws_s1_run_userdata_template.sh`.

## Code facts the checker holds you to
- Column identity is (file, column), never the bare name. Ties are broken by a seeded random key, never row order; use `H.score_fold` for rankings and per-fold-then-concatenate pooling.
- `H.assert_search_only` guards every entry point touching events; the vault loader is a separate file, never imported by S1 code.
- Preallocate float32 and index by position; free big arrays between phases.
- Every log carries a provenance header (script sha256, key inputs). Every proof needs a broken variant that actually fails.
- Time alignment (COSTS1 section 10.1): the close of label L pairs with the mid stamped L+1; path index k reads stamp t0+k; ctxs mid_px is 0 for whole coins on some days (G8 mid is the labelled fallback); no forward fill.
- The engine charges the exit fee on exit leg value; funding via hourly fundinghist at hour boundaries H with floor_hour(t0) < H <= exit.

## First actions in a fresh session
1. `ListAgents`; tell the planner and the checker your session name.
2. Read `CLAUDE.md`, this file, `docs/prompts/HL_TARGET2_NET_BP.md`, `research/model/s2_target_rules.md`, and `diagnostics/s2_target_sizing.log`.
3. Step A is committed. Wait for the planner's go on the build. Before any label: send the checker the S2 build code and the rules; before step B reads any y: the build log, the section-7 counts and the diff. The slim G8 table spend needs the user's own yes in this session.
