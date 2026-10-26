# Builder prompt: Hyperliquid build 7 — the master dataset (features and labels for every dislocation). NO MODELS.

User, 2026-10-24: "focus on having a very complete and comprehensive dataset first before we
even get to the models." Hedge quality was never a model input on Hyperliquid and must go in
"immediately". This build comes BEFORE build 6's model passes and build 4b; those then run on this
table. Read `docs/HYPERLIQUID_HANDOFF.md`, `CLAUDE.md`, and the build 3/4/5/6 briefs (this brief only
states what differs). Do exactly this; nothing else. Findings that point elsewhere are reported, not
acted on. Be frugal with messages (batch questions; no status pings). Cloud only, bigger machines
allowed, cost no object, every machine auto-terminates on a hard timer. Standing rule: the FULL
dataset, no sampling caps; chunk or stream.

## What this build produces
One versioned master table per event unit, one row per dislocation, keyed by event id, with every
column below, plus a coverage report and a data dictionary. Units: (1) PAIR level: every trigger of
build 6's full population (adaptive rule, no cap, ~8M; the 60,004 rows of `disloc.npz` must be
reproducible inside it — assert by pair + entry time); (2) COIN level: build 4's 74,607 coin-vs-
market events. Columns that do not exist for a unit (e.g. pair hedge quality for a coin event) use
the coin-vs-benchmark analogue and say so in the dictionary.
No splits, no fitting, no feature selection, no dropping of columns. Nothing is tuned.

## Rules for every column
- Written definition (window, units, sign convention, normaliser), as-of rule (uses only
  information at minute < t = 0 = T+30 unless it is a label), missing-value rule, and a flag column
  where the value can be missing from an archive gap. Never fill a gap silently.
- Look-ahead validator per group: recompute the group for 2,000 random rows from the raw sources,
  truncated at each row's cutoff, compare to the stored values, 0 mismatches or STOP.
- Coverage: NaN share per column per month, in the report.
- Deliver group by group as parquet files keyed by event id (`research/datasets/master/{unit}/{group}.parquet`),
  plus `master.parquet` join. Order of delivery: G2, G3 and the labels FIRST (they need no new data,
  so the user sees hedge quality quickly), then G7, G8, then the rest. Data dictionary:
  `docs/DATASET_DICTIONARY.md` (column, group, definition, window, as-of rule, coverage, source).

## The groups

**G0 Keys and labels.** Event id, pair or coin, T, d, z, threshold. Labels (the only columns that may
use the future): reach mu within 2 h, 5 h, 10 h on 1-minute closes (mu frozen); max depth reached;
minutes to mu (NaN if none); ADVERSE = widened by >= |z| within 10 h; max favourable and adverse
excursion in sigma; sign-flip chance probability per horizon (50 seeds, as build 3); and the
STOP-AWARE payoff, because "what do the wins pay and what do the losers cost" is the decisive open
question: for stop distances s in {0.5, 1.0, 2.0} sigma beyond entry, the outcome (mu first / stopped
first / neither within 10 h) and the net return in sigma after the Hyperliquid taker fee
(0.099% of the position per round trip; position legs sized 1 : |beta|; define the conversion to
sigma in the dictionary and have Code Checker confirm it), and the same at a maker fee of half that.

**G2 Hedge quality (FIRST).** At t = 0, from the pair's legs: r2 of the 2-day fit and of a 7-day
fit; correlation of 30m returns over 2 d and 7 d; correlation of 1m returns over 24 h; beta, |beta|,
sign(beta); neutrality = |1 - |beta|| / (1 + |beta|); beta stability (std/|mean| of the rolling beta over
the 336 bars to t = 0); change in beta over 24 h and 7 d; ratio of the legs' volatilities; number of times
the spread crossed its own mean in the last 7 days; AR(1) half-life of the spread over 7 days (NaN if not
mean-reverting); variance ratio (vratio) and volatility slope (vol_slope) and cohesion (sandwich) as
defined in `envfeat.py`. Coin-level analogues against the market index. Expected direction recorded in
the dictionary (OKX evidence: higher r2 reverts more; the rest two-sided).

**G2b Symmetric z (added 2026-10-24, user-approved; orientation finding by the G2 swap test).** The event
set stays EXACTLY the current rule (orientation of `tradeable_pairs`, version 1, reproduces the 60,004 rows). Add
orientation-proof columns on every event, at t = 0, closed form from the 96-bar window sums with bar i's own
beta_i and alpha_i applied to the WHOLE window (the frozen-geometry normalisation the outcomes already use):
`sigma_sym` = std (ddof = 1) over the window bars k of (a_k − beta_i b_k) = sqrt(var_a + beta_i² var_b − 2 beta_i
cov_ab); `z_sym` = (a_i − beta_i b_i − alpha_i) / sigma_sym (the window mean is 0 by construction of alpha_i);
`z_ratio` = |z_sym| / |z|; the per-pair series of z_sym over all bars, from which `threshold_sym` = 99th
percentile of |z_sym| over the previous 96 bars (bars i−96..i−1) and `trig_sym` = |z_sym,i| > threshold_sym with the
bar before not above its own (a fresh crossing; same rule as the adaptive trigger, on z_sym). Requirement
(asserted in the swap test): computing the same columns with the legs swapped gives z_sym' = −sign(beta) z_sym,
sigma_sym' = sigma_sym / |beta|, trig_sym' = trig_sym on every event. Report: the share of current events with
trig_sym = 1, the correlation of z and z_sym, and the distribution of z_ratio. Coin-level events: z_sym against
the index is the same construction with the index as leg B. This only ADDS columns: no new event table, no new
labels.

**G3 Pair and coin history (as-of).** For the event's pair: number of previous triggers; reach rate of
previous triggers whose 10 h outcome window ENDED before t = 0 (no outcome from the last 10 hours),
raw and shrunk toward the global rate with weight n/(n+20); outcome of the last 5 resolved triggers;
days since the last trigger; triggers in the last 7 days. For each leg: its coin-vs-market reach rate
from coin-level events, same rule. Mean time-to-mu of the pair's previous reverters.

**G4 Coin and time context.** Per leg (A, B) and for the pair the difference or ratio.
Coin: coin code (categorical, dictionary lists the 204 codes); listing date = first appearance in
`asset_ctxs` (archive reaches back to 2023-05-20; coins older than that are flagged left-censored) and
listing age in days at t = 0; liquidity = mean daily taker notional over the previous 7 and 30 days, its
rank among live coins (past only) and the ratio of the two legs; share of minutes with a trade in the
last 24 h and minutes since last trade; log price, price return over 7 d and 30 d; own 1-minute realized
volatility over 24 h and 7 d and the 24 h value relative to its trailing 90-day median; sector label
(CoinGecko category, one fixed snapshot with its date recorded in the dictionary) and `same_sector` for
pairs; static Hyperliquid meta traits (max leverage, margin tier, size decimals) from ONE current snapshot,
flagged static (they may have changed over time). Time: UTC hour (integer plus sin/cos), weekday, weekend
flag, minutes since the top of the hour (funding is hourly), Asia/Europe/US session flags by UTC hour, and
`near_seam` = inside 24 h after an archive hole. NO calendar date, month or time-trend column is stored
as a feature (a model could memorise periods); the event time stays as a key only.

**G5 Flow.** All build 3 and build 4 groups (FORCED [backstop-absorbed = backstop_liq_usd − adl_usd, because the flow table's backstop_liq_usd already includes ADL, verified exactly on every checked day; ADL = adl_usd], OPENCLOSE, CONCENTRATION proxies, TWAP, VOLUME,
IMPACT with the impact model REFIT per rolling fold later — store here the per-fold-free ingredients,
i.e. the signed imbalance and forced flow series statistics — not the fitted explained_share),
MARKET) at windows 30 min, 60 min, 6 h, 24 h; plus build 6 pass 3's minute-shape flow and price-shape
columns, net and per leg. Use per-coin prefix sums for window sums.

**G6 Wallets (RESTORED, user 2026-10-24: "keep the wallets in version 1; have everything we can, trim later").**
Reuse build 5's validated tables (S3 `build5/full2`: T1 wallet-coin-5-minute bins, T2 wallet-days, T3
backstop wallets; reconciled to the flow table; reviewed by pair-trading-78) and build 5's Part 2
definitions in `docs/prompts/HL_BUILD5_WALLET_TABLE.md` (CONC_EXACT, SKILL with K = 5000, BACKSTOP) with its
look-ahead rules (skill and top-wallet rankings only from UTC days strictly before the trigger's day). The
four backstop wallets are CONFIRMED as Hyperliquid's own HLP Liquidator vaults (HLP Liquidator, Liquidator 2,
3, 4; same leader address 0xdfc24b077bc1425ad1dea75bcb6f8158e10df303): label them in the dictionary and keep
them OUT of the human-wallet concentration and skill shares (report both with and without as separate
columns). Compute for EVERY event of both units: the existing `hl5_features.npz` covers only the
coin-level events; the pair-level population needs the per-leg then net-weighted version (as build 3's
net rule), windows 30 min, 60 min, 6 h, 24 h. Add VAULT INVENTORY: net position (coin units and USD) of the
four liquidator vaults per coin at t = 0, its change over 1 h, 6 h, 24 h, and its share of the coin's OI;
derive it from the vaults' fills (`startPosition`) inside the same all-fills pass as the OI reconstruction.
Build 5's tests stay cancelled; only the columns are built. Caveats go in the dictionary: one entity can run
many wallets; skill is noisy (heavy-tailed PnL); the first 30 days of skill are NaN.

**G7 Derivatives state (funding, premium, open interest).** Per leg at t = 0; pair = leg A, leg B and
the signed difference. Principle: ONE definition of each core column across the whole window, so there
is no seam where the source changes (the lesson of build 1: never splice two sources).
- **Funding and premium, core columns, from the public `fundingHistory` API everywhere**
  (`POST https://api.hyperliquid.xyz/info {"type":"fundingHistory","coin":C,"startTime":ms,"endTime":ms}`;
  hourly rows `{fundingRate, premium, time}`, 500 per call, history verified back to May 2025). The row
  stamped at hour H reports the hour that ENDED at H, so at t = 0 use the last row with time <= t = 0, and
  nothing later. Columns: funding last hour, 8 h mean, 24 h mean, 7 d mean; premium last hour and its change
  over 1 h and 24 h. On days when `asset_ctxs` is complete, report how well the API series agrees with the
  `asset_ctxs` series at the hour marks (correlation and median absolute difference) before use; if they
  disagree materially, STOP and report. The minute-level `asset_ctxs` versions (instantaneous funding,
  instantaneous premium, mark − oracle basis, impact bid/ask prices) are SEPARATE columns, NaN with a gap
  flag where `asset_ctxs` is missing; never filled.
- **Open interest, core column, reconstructed from fills.** OI is the sum of long positions, equal to the
  sum of shorts, in coin units. Every fill changes one wallet's position from p (the `startPosition`
  field) to p ± sz (buy +, sell −). Total gross position = sum of |position| over wallets = 2 × OI, so
  the OI change of a fill is exactly ½ (|p ± sz| − |p|) in ONE-SIDED units, summed over EVERY fill [CORRECTION 2026-10-25, found by the OI diagnostic: `asset_ctxs` open_interest equals the SUM of absolute positions (longs + shorts), i.e. 2 × the one-sided OI, so in `asset_ctxs` units the fill change is Σ(|p ± sz| − |p|) with NO half; store `oi_delta_coin` in asset_ctxs units and state it in the dictionary] (both parties, maker and
  taker, liquidation, ADL and "Net Child Vaults" fills included; spot, HIP-3 and `#` names excluded;
  dedupe (tid, wallet)). Sum per coin per minute: `oi_delta_coin`. This needs one more pass over the whole
  trade archive reading maker fills too (same method and machines as build 2); in the SAME pass also write
  the maker-side open and close dollars (the flow table only kept the taker side) so the wallet and flow
  columns can use both sides.
  - **Level:** OI(t) = the last observed `asset_ctxs` OI at or before t, plus the cumulative `oi_delta_coin`
    since that observation. When `asset_ctxs` is present this equals the observed value at every minute, so the
    definition is the same everywhere. ANCHOR ONLY FROM THE PAST: never use a later observation to correct
    the path inside a gap, because that would leak the future into features. Archive holes (the 114 missing
    minutes) simply add no delta and are flagged.
  - **Validation before use (a gate):** on days when `asset_ctxs` is complete, compare minute-by-minute and
    hour-by-hour: reconstructed ΔOI against observed ΔOI (check the timestamp lag first, as in build 1 step
    B0); require correlation >= 0.99 on hourly changes and a cumulative one-day drift below 0.5% of the
    coin's OI for >= 95% of coin-days; report the coins that fail. Separately measure the drift accumulated
    across real gaps: at each gap's end, the reconstructed level against the first observed level. If the
    gate fails, STOP and report; leave gap values NaN.
  - Columns: OI level in USD (OI × mid), % change over 1 h, 6 h, 24 h, 7 d, OI ÷ 24 h taker notional, and a
    flag for "level comes from a gap path" with the number of minutes since the last observation.

**G8 Order book.** Source: `s3://hyperliquid-archive/market_data/{YYYYMMDD}/{H}/l2Book/{COIN}.lz4`
(us-east-1, requester-pays; 20 levels per side, snapshot every ~0.5 s). Coverage measured 2026-10-24
over 2025-05-25 to 2026-10-23: 489 of 517 days complete, 21 days entirely missing (2025-10-17 to 22,
2025-11-18 to 25, 2026-07-08, 2026-07-12 onward for several days), 7 partial; about 96% of hours.
Missing hours stay NaN, flagged. Build a per coin-minute table (first snapshot of each minute): spread
in bp, depth within 10/25/50 bp of mid on each side in USD, book imbalance at those depths, depth
relative to the coin's trailing 7-day median, and the slippage in bp to buy and to sell $1k
(NaN when beyond the 20 levels). (User, 2026-10-25: no position will exceed $1k, so $1k replaces the
earlier $10k/$50k.) Event columns per leg at t = 0 (the last minute before), and the change
versus 1 h and 6 h earlier; pair = A, B, difference. NOTE: EC2 is denied in us-east-1 by the account's
SCP (UsEast1Partitional); run in us-east-2 (cross-region read ~$0.01/GB, acceptable) or ask the user to
allow EC2 in us-east-1. Pilot on 4 days first and report size, time and cost; no cap.
User decisions 2026-10-25: (1) the full run goes on EC2 us-east-2. The user approves adding an inline
read-only policy (s3:ListBucket on arn:aws:s3:::hyperliquid-archive, s3:GetObject on
arn:aws:s3:::hyperliquid-archive/*) to role hl-build2-ec2, and nothing else. Test one GetObject from
the instance before launching the full run. (2) Add `book_reach_bp` per side: the distance in bp from mid
to the 20th (last stored) level, so every depth value shows whether the 20 levels reached its band.
Carry it through to the event columns like the other book measures.

**G9 Market regime.** All as of t = 0, past only, raw measures (no hand-set regime labels in the first
version). Benchmarks: BTC, ETH and the equal-weight index of all live coins (build 4's definition).
- Trend and volatility: log return of BTC, ETH and the index over 1 h, 6 h, 24 h, 7 d; 1-minute realized
  volatility of each over 1 h, 24 h, 7 d; the ratio 24 h / 7 d (rising or falling volatility).
- Breadth and dispersion: share of live coins with |60-minute return| > 2 × own trailing 7-day std; share
  of coins up over 24 h; cross-sectional std of 1-hour returns; coherence = mean over live coins of the
  trailing 7-day correlation of 30m returns with the index.
- Leverage and crowding: mean funding last hour across coins, OI-weighted mean funding, share of coins with
  positive funding; total market OI in USD and its 24 h % change (from the reconstructed OI); market-wide
  forced liquidations (long + short) in USD over 1 h and 24 h, each divided by its trailing 7-day median,
  and the 7-day / 28-day ratio; ADL USD over 24 h.
- Activity: total taker notional over 1 h relative to its trailing 7-day median; number of other triggers on
  the same 30m bar (as of t = 0) and in the previous 24 h.
- Derived rank columns (continuous, 0 to 1, no cutoffs): percentile rank of the index's 24 h volatility, of
  the index's |7 d return|, and of 24 h forced liquidations, each within its own trailing 90 days; NaN for
  the first 90 days of data.

**G10 Cross-venue (OKX) -- REMOVED FROM VERSION 1 by the user 2026-10-25. Do not build.** (Original spec kept below for reference only.) Source: the OKX data moved to the attic
(`attic/okx_data/`, also on S3 `attic/`): 1-minute and 30-minute bars for 214 OKX coins through about
2026-10-11 (30m to 10-13) and 1 h funding/index/mark files. OKX is retired for research, but this history is
kept as a SECOND price source for the coins both exchanges list (~120; map names with the build 1 rule, e.g. kPEPE
-> PEPE with scale 1000, and require the price check: median |ln(HL close) − ln(OKX close) − ln(scale)| < 1% on
overlapping 30m closes, otherwise the coin is NOT shared; list the failures, e.g. LUNA vs LUNC). For shared coins,
per leg at t = 0 (NaN if the leg is not shared or OKX has no data yet; coverage ends ~2026-10-11, never filled):
OKX log return over 1 h, 6 h, 24 h; the same Hyperliquid returns and their difference; the Hyperliquid-minus-OKX
log price gap at t = 0 and its change over 1 h and 6 h; lead-lag = for the trailing 24 h, the lag in −5..+5 minutes
that maximises the correlation of 1-minute returns (positive = OKX leads) and that correlation; the OKX 1 h
funding minus Hyperliquid funding; OKX volume against its trailing 7-day median; `okx_dislocated` = whether the
coin's own coin-vs-market |z| on OKX also crossed its adaptive threshold within ±1 bar. Pair columns = leg A,
leg B and flags for how many legs are shared. OKX bar convention: a bar labelled T carries the close at T + bar
(same as the Hyperliquid bars). Integrity checks as every group; also report the share of events with both
legs shared.

## Parked until the dataset is complete and released (user, 2026-10-24: "not now, no side-tracking")
A second event table triggered by the symmetric rule (trig_sym), with the same labels and groups, to test
whether results depend on the orientation quirk. Do NOT start it. It is decided after version 1 is released.

## Data integrity (user, 2026-10-24: "getting this data right is the most important thing")

Correctness outranks speed and breadth. Nothing is released as a version until every item below passes
and the checker has signed it. Each check is a script that writes a log, kept with the dataset.

1. **Poison test for look-ahead (every group).** For 1,000 random events, overwrite ALL raw inputs at or
   after t = 0 (flow, prices, fills, funding, book, ctx) with random values, recompute the group, and require
   the features to be unchanged to the last digit. Labels must change. Any change in a feature = look-ahead = STOP.
   (User, 2026-10-25: G6 wallets may use 400 events; a clean pass at 400 is accepted.)
2. **Independent recomputation.** The checker (or a second implementation written without reading the first)
   recomputes 2,000 random rows per group from the raw sources. 0 mismatches beyond float tolerance.
3. **Symmetry tests.** Swapping leg A and leg B must flip the sign of every signed column and leave symmetric
   columns unchanged (hedge quality is symmetric by construction). Reversing the sign of z must flip every
   push-signed column. Test on synthetic events with known answers (hand-computed, in a tests file).
4. **Invariants.** Shares in [0,1]; nested windows (24 h >= 6 h >= 1 h >= 30 m) for non-negative sums;
   open + close = total; OI never negative; funding within plausible bounds; r2 in [0,1]; labels monotone in
   horizon (reach 2 h <= 5 h <= 10 h); no duplicated event ids; event times on the 30m grid; all times UTC.
5. **Reconciliations to the source of truth.** Bars vs Hyperliquid's candles (done in build 2; rerun on the
   final bars); flow vs trades on complete days; OI reconstruction vs asset_ctxs (gate above); funding and
   premium API vs asset_ctxs (gate above); labels vs a straight re-walk of the 1-minute path for 2,000 events;
   the 60,004 old rows reproduce their old labels exactly.
6. **Drift and seam checks.** Per column: distribution by month (mean, quartiles, NaN share); list months where a
   column changes level by more than 3 monthly standard deviations; show event counts and NaN shares around the
   five archive seams, the order-book gaps and the Sep/Oct 2026 ctx gaps. Explain each jump or flag it in the
   dictionary.
7. **Eyeball sample.** 20 random events (stratified: long/short, early/late, reached/not) plotted from raw data with
   the key columns annotated; a human-readable one-page check per event saved as PNGs (plain matplotlib).
8. **Provenance and freezing.** Each table version records the input file hashes, the code commit, the build date,
   row counts and the validator results. A released version is immutable; a fix creates version n+1 with a change
   log. Models only ever read a named version.
9. **Known-answer events.** The 2025-10-10 crash and 3 other hand-picked days: print every group's values for
   2 events each and check them by hand against the raw data. Record what was checked.

## Part Z — the side-by-side (descriptive, no model)

> **MOVED TO AFTER RELEASE (user, 2026-10-26).** Not part of version 1. It is the first post-v1 task. The G8
> 1,000-event poison rerun was also dropped; the earlier G8 poison pass is accepted.
For every column in the master table: median and quartiles for reachers vs non-reachers (10 h), the
standardized difference, the AUC of the single column against the reach label, and the month-by-month
series of that AUC, all events. No split is applied because nothing is fitted; the report says the table is
for orientation, not selection. Include a plain bar chart of the largest single-column AUCs
(matplotlib PNG, minimal). Count columns with a stable sign across months.
**Added 2026-10-26 (planner, approved with "go"):** the question is reverting BETTER THAN CHANCE from
the position, so beside the plain AUC report the AUC within deciles of the stored chance probability
(the sign-flip bar), averaged over deciles ("chance-adjusted AUC"). A column that only tracks distance or
volatility will drop toward 0.5 there. Rank the chart by chance-adjusted AUC. Flag columns that are on the
v1 dictionary's unexplained-drift list next to their AUC. Both units, run on the frozen v1 files (read from
master/versions/v1, verify hashes on read). Logs `master_partz_*.log`; NUMBERS.md `[HL-PARTZ1]`; the
checker reviews code before the run and the log + numbers before reporting.

## Review and receipts
Code Checker (session `pair-trading-78` as of 2026-10-24; check `ListAgents`): the definitions of each group and the
look-ahead validators before the group is built; the fee-to-sigma conversion; the OI reconstruction
and its validation before the full archive pass; the order-book pilot before the full run;
log + NUMBERS.md + diff before reporting. Anything that changes a definition, adds a run this brief
did not ask for, or changes a gate goes to the user. Logs `research/dataset/logs/master_*.log`;
NUMBERS.md section `[HL-MASTER1]`, every number with its log and M/A tag.
Final report plain and short: row counts per unit, columns per group with coverage, the hedge-quality
and history columns first, the funding/OI/order-book gap handling and validations, the side-by-side
headlines, cost, checker's verdict.
