# HL-TARGET2: retrain on a money target (net bp per trade at midpoint prices)

Owner: planner. Created 2026-11-20. (Not to be confused with HL_MODEL1_S2_TREES.md.) Code and rules files keep the
names s2_target_* (research/model/s2_target_rules.md, diagnostics/s2_target_sizing.py); planner ruling: no rename.
Missing mids (planner ruling 2026-11-20): forward-fill the mid only, up to 5 consecutive minutes; exit price = first real
mid at or after the trigger; longer gaps flagged for a with/without split; stop and report if >10% of test-month events
are flagged. Sample finding: G8-only 2025 training months may be ~40% flagged (decide at step C, not now).

## Why
S1 ranks real reversion (top-1% lift ~2.1x at book mids) but its dollar edge does not survive costs (HL-COSTS1,
verdict c). S1's label (reach mu, from closes) rewards small moves and bid-ask bounce. HL-TARGET2 asks the model
for what a trade earns.

## User decisions (2026-11-20, fixed)
- Target y = net bp per trade at book-midpoint prices.
- Cost = taker: 4.5 bp fee per fill on each leg at entry and exit + book half-spread per leg at entry and exit +
  funding as the engine computes it (say if the data does not allow). Depth impact excluded (COSTS1: small at our sizes).
- Exit = first minute in (t0, t0+600] where the MID spread reaches mu in the reversion direction, else minute 600.
- The data is ruled fresh for the new target (test months and vault). Discipline: every design choice is justified from
  test-month evidence and written down before the vault is scored, once, at the end.

## Target definition (the builder writes exact wording into a rules file; the checker reviews)
- Events: all saved events (search and vault) with their saved trigger, beta, mu, sigma, direction. Signal unchanged.
- Prices: per coin-minute mid, ctxs mid primary, G8 table mid fallback, same time alignment as the COSTS1 no-bounce
  section. Mid spread = ln mid_a - beta ln mid_b. Entry at the mid at t0.
- Gross bp = two-leg return at mids, legs weighted N/(1+|beta|) and N|beta|/(1+|beta|), as bp of N.
- y = gross - fees - half-spread - funding, all bp of N. Store every component (so a maker variant needs no rebuild),
  plus exit minute and reason.
- Missing mids: the builder proposes a rule (e.g. forward-fill up to k minutes, else drop); counts by period, month, tier,
  including the 7 missing G8 days.

## Steps (one at a time; the next starts only on the planner's go)
- A. Spec + sizing: events per period, mid coverage over the 10 h windows, where it runs (G8 table is in S3 Tokyo),
  time, cost, output size. No build, no AWS. Checker reviews; report to the planner.
- B. Ceiling check, TEST MONTHS ONLY: distribution of y (share y > 0, mean, quantiles), by S1 p decile, |z| bucket in
  sigma, liquidity tier, month; how much positive y exists and whether it is concentrated anywhere visible before entry.
- C. Refit on y, only if B shows something, and only on the user's yes.

## Standing rules
CLAUDE.md applies: checker before long runs and before reporting; every number script-printed; findings reported, not
acted on; AWS launches and local deletes need the user's own yes in the builder's session.

## User decisions (2026-11-20, label build)
- Build go: "lets just update the dataset label. Then report back, i have an idea of what to do with the missing labels". Unlabelled events keep their status row; nothing is dropped or imputed beyond the rules.
- Vault y is built in this run, in its own file (user chose this over building it at the end of step C). No vault y, gross or exit minute is printed. Nothing reads the file until the vault scoring is called.
- Trial on a few days first, checker OK, then the full run.
- S3: column-only G8 read (~1.5 GB, builder's estimate), user's yes in the builder session; the full 11.5 GB download was declined.
- Checker PASS on build code and rules (build 37d51eb86821, rules 0612678b8ad9). Stored tier column is not point-in-time: never a feature.
