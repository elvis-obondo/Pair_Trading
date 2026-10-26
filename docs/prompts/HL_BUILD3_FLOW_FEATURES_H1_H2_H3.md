# Builder prompt: Hyperliquid build 3 — flow features and the H1/H2/H3 tests (with the market block)

Continues build 2 (`[HL-BUILD2]` in NUMBERS.md; Code Checker passed). Read
`docs/HYPERLIQUID_HANDOFF.md` and `CLAUDE.md` first. Do exactly this; nothing
else. Findings that point elsewhere are reported, not acted on.

## The question

At the moment a spread dislocates, can we tell which ones will reach mu within
10 hours **better than chance from their position**, using who/what pushed the
move (forced vs deliberate flow)? Price-only features are closed: volatility
and distance to mu are the reference, flow has to beat them. No stop, no
profit, no delayed (H5) features in this build.

## Verified facts (checked 2026-10-15 against NUMBERS.md and the code — re-check any you rely on)

- Dislocation set, on pt-research: `research/datasets/disloc.npz` (`windows`
  60,004 × 336, `outcomes` 60,004 × 21 on the frozen geometry) +
  `disloc_meta.parquet` (a, b, entry_time, bar_index, z_at_entry, beta, alpha,
  mu, sigma, r2, pair_triggers_true, day, threshold_at_entry, beta_stab,
  mins_since_trade per leg). Adaptive trigger (|z| crosses its own previous-96-bar
  99th percentile). 3,004 pairs, 473 days. **Never regenerate it**: join by row
  position. 30m bar labelled T is observed at T+30.
- Flow table `research/hyperliquid/flow/{COIN}.parquet`, one row per minute,
  on pt-research (laptop has only the 30m bars). Columns: n_trades,
  taker_buy_usd, taker_sell_usd, n_taker_wallets, open_taker_usd,
  close_taker_usd, twap_taker_usd (NaN before 2025-07-27 08:00),
  top3_taker_share, liq_forced_long_usd, liq_forced_short_usd,
  backstop_liq_usd, adl_usd; NaN on archive-hole minutes. Definitions are in
  the header of `research/hyperliquid/build2_fills.py` (lines ~55-75): forced
  legs = liquidatedUser == the fill's own wallet, on the book; backstop =
  trades with a "Liquidated…" dir, once per tid; ADL once per tid.
- **Three gaps in the flow table that this build must handle:**
  1. `open_taker_usd`/`close_taker_usd` are not split by side, so "net opening
     flow in the move's direction" (H2) cannot be computed. Part 0 adds
     `open_buy_usd, open_sell_usd, close_buy_usd, close_sell_usd` (taker side ×
     taker dir; flips split as the existing columns do; open_buy+open_sell must
     equal open_taker_usd and close_buy+close_sell must equal close_taker_usd,
     asserted on every row).
  2. `top3_taker_share` is per minute and `n_taker_wallets` is distinct wallets
     per minute: neither can be aggregated exactly over a 30/60-minute window.
     The H3 features below are therefore PROXIES (notional-weighted mean of the
     per-minute top-3 share; sum of per-minute distinct-wallet counts per $M).
     Say so in every table that shows them. Do NOT rebuild from raw fills in
     this build; a true window-level concentration is a later decision for the
     user.
  3. `twap_taker_usd` is NaN before 2025-07-27: treat as missing, never 0.
- Existing test machinery (OKX-era, hard-coded dates — port by replacement, the
  OKX versions stay in git history):
  - `research/dislocation_model/harness.py`: `CUT = 2026-07-18` (OKX),
    `Split`, `fit_predict`, day-clustered bootstrap, permutation null, gates.
  - `reachmu.py` (target and chance bar): reach = depth ≥ |z_at_entry| on
    **1-minute closes**, mu frozen at entry, no stop, 10h; chance probability =
    the same spread's 1-minute steps with random signs, 50 seeds (whyscreen's
    sign flip). `reachmu2.py` (prune on validation, models, scoring, reading
    rules), `flag_share`, `top_set`, `envelope.day_boot`.
  - `envfeat.py` is the pattern for a feature builder: matrix only, no target,
    join by position, look-ahead audited by a validator.
  - 1m bars on HL: `envelope.RAW_BAR_DIR` was repointed in build 2 (check it).
- Reading rules, fixed: "clears" = the 95% day-clustered interval excludes zero.
  Pruning rule (user, 2026-10-13): drop a feature group unless some model's
  validation interval is wholly above zero. Sign folding is the primary
  reading. Nothing is chosen on held-out.

## Hard rules

- No look-ahead. A feature for the dislocation at bar label T may use only fills
  with minute < T+30 (the trigger bar closes at T+30). Window W minutes =
  minutes [T+30−W, T+30). Add a validator that, for a random 500 rows, recomputes
  each feature from the raw flow files restricted to that cutoff and compares,
  and an assertion that no minute ≥ T+30 is ever read.
- (Amended 2026-10-15: dollar-scaled quantities are divided by the coin's trailing
  7-day median; ratios/shares are not. wallets_per_musd is normalised and also
  stored raw.)
- Normalisation uses past data only: each coin's value divided by its trailing
  7-day median of the same quantity (minutes before the window start), NaN if
  fewer than 3 days of history. The normaliser for window features is the
  median of the trailing 7-day W-minute windows' totals.
- Features, windows and expected directions below are FIXED before any model is
  fitted. Adding or changing a feature after seeing a result is a plan change:
  stop and ask.
- Memory: never load the whole flow table. Read per coin, per column, and only
  the event windows (≤ 60 min per event). Runs on pt-research via
  `scripts/gcp_run.sh`; the machine must be TERMINATED after each run.
- Replace, don't accumulate: update the OKX constants in harness.py and the
  reach-mu scripts to the HL values below; no parallel venue paths.

## Part 0 — commit, then extend the flow table

1. Commit build 2 on a new branch `feat/hyperliquid-build2` (the working tree
   also holds older uncommitted research files from before today: commit
   today's OKX retirement + Hyperliquid work only, leave the rest untouched,
   and list what you left). Do not push.
2. Add the four side×dir columns to the flow table: update `build2_fills.py`,
   rerun stage 1 + 2 as in build 2 (parallel spot, auto-terminate, hard timer,
   nothing left running), regenerate `flow/{COIN}.parquet`, push to our S3 and
   pt-research. Assert all existing columns are bit-identical to the old files
   and the new ones satisfy the sum identities. Code Checker reviews before the
   rerun.

## Part 1 — split, target, chance bar, reference (before any flow feature)

- **Split (fixed now; the only date choices allowed):** CUT = 2026-05-25 (the
  70/30 day split mkdisloc printed: 41,941 fit / 18,063 held-out). Validation =
  last 20% of the fit days. Held-out halves HO1/HO2 = first/second half of the
  held-out days by dislocation count; compute the boundary date from the meta
  `day` column only, before touching any target or model, and log it.
  Update `harness.CUT` and the Split text.
- **Target:** reach on 1-minute closes as in reachmu (depth ≥ |z_at_entry|,
  mu frozen, 10h), plus the 30-minute-grid reach as a secondary. Population =
  dislocations whose 1-minute window exists and is finite (report the matched
  count and the share lost to archive holes). Chance probability per episode,
  50 sign-flip seeds, as reachmu.
- **Reference ("position"):** vol-only logistic (vol_48, vol_48_1m, sigma) plus
  |z_at_entry|, as REACH-MU. Report its held-out flag share at 80% catch,
  top-20% hit rate and beyond-chance gap, both halves. This is the bar every
  flow group must beat. Also report reach rate and mean chance probability
  overall and by |z_at_entry| band (< 2, 2-3, ≥ 3), since 24% of the set is
  below 2.
- Gate: if the reference's beyond-chance gap is wholly above zero in both
  halves, say so prominently (it would contradict OKX); if not, carry on.

## Part 2 — `flowfeat.py` (matrix only, no target, no model)

Output `research/datasets/flowfeat.npz` (X float32, names), joined by row
position onto `disloc_meta.parquet`. Notation: leg A = ticker_a, leg B =
ticker_b, d = sign(z_at_entry) (+1: spread above mu), β = meta.beta. The spread
is a − β·b − α, so the spread rises when A rises or when B falls (when β < 0,
B's sign flips again — handle with sign(β)). Window W ∈ {30, 60} minutes.

**Leg-signed quantities.** For a leg with taker flow in the window:
- imbalance = (taker_buy_usd − taker_sell_usd) / (taker_buy_usd + taker_sell_usd)
- A-push = d · imbalance_A ;  B-push = −d · sign(β) · imbalance_B
  (positive = flow pushed the spread in the direction it dislocated).
- Contribution of each leg to the spread's move over the previous 60 minutes:
  cA = d·Δlog(a), cB = −d·β·Δlog(b) (close-to-close, 1m bars, same cutoff).
  Weights wA = max(cA,0)/(max(cA,0)+max(cB,0)), wB = 1−wA; if both ≤ 0, 0.5/0.5.
- **net(x) = wA·x_A + wB·x_B** for any leg-signed x. `lone_mover` = 1 if
  max(wA,wB) ≥ 0.8 else 0 (one flag, plus `driver_is_A`).
- Store leg-level values too (`_A`, `_B`) in a separate file
  `flowfeat_legs.npz`; they are NOT model inputs in this build (net only).

**Groups, features, expected direction (reach more = revert more):**

H1 — FORCED VS DELIBERATE. For W ∈ {30, 60}, per leg then net, as shares of the
leg's taker notional in the window:
- `h1_forced_share_W` = (liq_forced_long_usd + liq_forced_short_usd) / (taker_buy_usd + taker_sell_usd)
  on the leg, **restricted to the forced side that pushed the spread's way**:
  for a leg with push sign s (A: d; B: −d·sign(β)), a forced SELL (forced long
  liquidation, liq_forced_long_usd) pushes price down, a forced BUY (forced
  short liquidation) pushes up; use liq_forced_short_usd if s>0 else
  liq_forced_long_usd for the pushing side. Net-weighted.
- `h1_backstop_share_W` = backstop_liq_usd / taker notional (net-weighted, no side).
- `h1_adl_share_W` = adl_usd / taker notional (net-weighted).
Direction: higher forced share → reaches mu MORE often than chance.

H2 — OPENING VS CLOSING (side×dir columns from Part 0). On the pushing side
only (taker buys if s>0, sells if s<0):
- `h2_open_push_W` = open (buy if s>0 else sell) / taker notional;
  `h2_close_push_W` = the matching close share; `h2_open_close_ratio_W` =
  open_push / (open_push + close_push), NaN if both 0. Net-weighted.
Direction: opening-driven → reaches mu LESS than chance; closing-driven → MORE.

H3 — CONCENTRATION (proxies, see gap 2): for W ∈ {30, 60}, net-weighted:
- `h3_top3_W` = notional-weighted mean of per-minute top3_taker_share;
- `h3_wallets_per_musd_W` = Σ n_taker_wallets / (taker notional in $M);
- `h3_twap_share_W` = twap_taker_usd / taker notional (NaN before 2025-07-27).
Direction: concentrated (high top3, few wallets per $M, high TWAP share) →
reaches mu MORE. TWAP is reported as its own sub-group (it is NaN for part of
the set — report the count) and tested only on rows where it exists.

MARKET BLOCK (direction two-sided — tested both ways, no sign assumed), at the
trigger cutoff, W ∈ {30, 60}:
- `mk_btc_ret_W`, `mk_eth_ret_W` signed by d (BTC/ETH close-to-close return over
  the window, times d); `mk_btc_corr_7d` = A's and B's trailing 7-day
  correlation of 30m returns with BTC (average of the two).
- `mk_liq_usd_W` = market-wide forced liquidation notional in the window summed
  over all live perp coins (long+short), divided by its trailing 7-day median
  for the same window; `mk_liq_7d_ratio` = trailing 7-day total / trailing 28-day
  total (H9's regime signal).
- `mk_breadth_60` = share of live coins whose 60-minute |log return| exceeds
  2 × the std of that coin's 60-minute returns over its trailing 7 days
  (past only). A high value means a market-wide move; a low value, a local one.

Total ≈ 40 features in 4 groups (H1, H2, H3, MARKET); the exact count is
reported. Missing values stay NaN (no zero fill); report NaN share per feature
and per group. Stale legs (mins_since_trade ≥ 30) and rows touching the five
mid-2025 seams (list in NUMBERS.md) get a `flag_gap` column, kept, not dropped.

## Part 3 — tests (held-out touched once, at scoring)

Models, fitted on train (settings on validation), as reachmu2: logistic L1 and
LightGBM depth 1, 2, 3, 4 (min_data_in_leaf grid as reachmu2). Sets:
1. reference (Part 1);
2. reference + each group alone (H1, H2, H3, MARKET), group NaNs median-filled
   from train with an indicator, counts reported;
3. reference + all groups;
4. after the pruning rule on validation (grouped permutation importance on val,
   20 shuffles, day-clustered 95%): drop a group unless some model's val
   interval is wholly above zero; then score the kept set.

Scoring on held-out, HO1 and HO2 separately, exactly as reachmu2 Step 4: flag
share at 80% catch, top-20% hit rate, beyond-chance gap of the flagged set,
paired day-clustered 95% intervals vs the reference, permutation null. Reading
rules as reachmu2 (HELP / SIGNAL / REGIME-DEPENDENT / PER FAMILY): "clears" in
both halves = a finding; one half = regime-dependent, not a pass.

False-discovery control: the number of (group × model × half × measure) cells is
fixed by the design above — count it in the log before running, and report the
expected number of false positives at the 95% level next to the hits.

Also report, per group, the direction check: the sign of the group's effect on
reach against the expected direction above (a clear result in the wrong
direction is a finding to report, not a pass).

## Part 4 — the 10 Oct 2025 cascade, as its own event

The set's earliest dislocations start 2025-05-25, so the crash is inside it.
Take dislocations with trigger time in 2025-10-10 20:00-2025-10-11 02:00 UTC
(BTC low 21:19, −12.1% in 30 min). Report: n, reach rate vs mean chance
probability, split by H1 forced share terciles (descriptive, no model), and the
same for the 3 hours before the crash start. Descriptive only; the rule
"BTC down >5% in 30 min → episodes in the next 3 h vs the rest, beyond chance"
is run on all dislocations as one more row (pre-registered here), with n
reported. Note the seam/hole check for that window.

## Review and receipts

- Code Checker ("Code Checker 2"; check `ListAgents`): Part 0 code before the
  rerun; the feature definitions, the validator and the test design (this text)
  before Part 3 runs; log + NUMBERS.md section + diff before reporting.
  Fix findings on bugs, look-ahead, mismatched numbers, rules not applied as
  written, missing receipts; re-send until it passes. A fix that changes a
  feature definition, adds a run this brief did not ask for, or changes a
  gate's verdict goes to the user.
- Logs: `research/dislocation_model/logs/hl3_*.log`, one per part.
  NUMBERS.md: new section `[HL-FLOW1]`, every number with its log and M/A tag.
- Final report: plain and short (PM-level, numbers first, stats out of the main
  line): the reference's result, then one line per hypothesis group (help /
  no / wrong direction / regime-dependent), the proxy caveats, the crash
  check, the checker's verdict, files changed, cost.
