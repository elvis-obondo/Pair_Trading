# Handoff: from the reverter search to Hyperliquid flow data (2026-10-13)

Read this first in the new session. Every number below is measured and recorded
in `research/dislocation_model/NUMBERS.md` (sections named in brackets).

## The question we are on

At the moment a spread dislocates (|z| crosses 3 on the frozen 2-day geometry),
or up to 60 minutes after, can we tell which ones will reach mu within 10 hours,
**better than chance from their position**? No stop, no profitability yet; that
is a later stage, by the user's choice.

"Chance" = the same spread's 1-minute steps with random signs (sign-flip null).
Every "win" so far has been matched by chance.

## What is closed (do not re-run)

- **Envelope (MAE/MFE quantiles):** Linear QR is ~2% better than climatology.
  Volatility is the only predictable thing. Predicted MAE is too weak to size
  stops. [PLAIN-MISS]
- **Meta-label skip rules:** v1 void (two-sided target), v2 a clean no on live
  fills, 0 of 20 cells, 200 seeds. [META-LABEL]
- **Why-it-moved features** (lone mover, common move, lag, volume spike, vadj
  residual, lagger spread): MFE gain only in HO2, not adopted. [WHY-IT-MOVED,
  WHY-CHECKS]
- **Reach-mu at detection** (all features, logistic and trees depth 1-unlimited,
  DART): nothing beats volatility-only. Catch 80% of reverters = flag ~65%,
  hit 30%. Combinations add nothing. [REACH-MU, REACH-MU-V2]
- **Perp vs index basis:** no separation (AUC 0.49-0.51). [REACH-MU-V2]
- **Delayed decision at 30/60 min:** gain is entirely "distance to mu now".
  Path shape, refreshed features, changes since detection add nothing. Spreads
  behave memoryless. [DELAYED, DELAYED-V2]
- **Within the still-far group (>=2.5 sigma at 60 min):** top slices at or
  below chance. Reverters cannot be picked before they come back.
- **Within the top 1%:** first-hour features do not separate the 75% that
  finish from the 25% that don't (AUC 0.556, p=0.14).

## What is true and useful

- Top 1% at 60 min: model says ~70%, ~71-81% revert, median 1.07 sigma left,
  median 59 min to mu. Calibrated, but hit rate = chance from that position.
  Top 5%: 66% revert, 1.54 sigma left. Prob >75%: 90% (n=29), 0.85 sigma left.
- Fees (verified on the live paper ledger, 969 trades): 0.099% of the position
  per round trip, all taker; ~0.20 sigma typical, ~0.25 sigma for the top 1%.
  Maker would be ~0.10 sigma. Legs are sized 1 : |beta|.
- Live stop fills: median 1.035x (the stop monitor works). Live take-profit rate
  20%.
- With a random walk, any exit rule has expected value ~0 before fees. A high
  hit rate means larger losses. **The payoff of the top-5%/top-1% groups (what
  the failures cost) has never been measured.** That is the decisive open step
  for the delayed-entry idea.

## Open, not yet run

1. Payoff measurement for top-5% and top-1% at 60 min: wins, losses, fees,
   under a fixed exit rule (top 5% first).
2. 10 Oct 2025 cascade check: rule "BTC down >5% in 30 min", episodes detected
   in the next 3h vs the rest, beyond chance. Tests "forced flow reverts" on
   existing data. BTC low was 21:19 UTC, -12.1% in 30 min.
3. Sector (CoinGecko labels and return clustering) and coin track-record
   (past-only, ordered target statistics, smoothed) probes.
4. Chop-vs-drift: sign-flip null on 5m/30m steps, to test whether "below
   chance" is real or 1-minute bid-ask bounce.
5. Adaptive trigger -- ADOPTED 2026-10-15 (user), replaces |z|>=3, no 3.0 baseline run:
   fire when |z_i| crosses the 99th percentile of |z| over the previous 96 bars
   (i-96..i-1), fresh crossing, no absolute floor; meta records threshold,
   r2, beta_stab, mins_since_trade per leg. No pair filter (record only).
   Original note:
   replace the fixed |z| >= 3 with "unusual for this pair over its own 2-day
   window" (e.g. its own |z| percentile, or z-jump vs its usual step size;
   exact measure fixed before testing). Why: 3.0 came from a 2026-09 profit
   sweep on the old 7-day OLS geometry (3.0 vs 3.5 equal total edge, 3.0 on
   twice the trades; walk-forward preferred 3.5 at the grid edge, never
   extended), never re-checked on the symmetric 2-day geometry or for the
   reach-mu question.

## The new direction: flow data

Price and volume reduce to volatility plus position. The missing information is
**forced vs deliberate**. Sources:

- **Open interest:** `scripts/collect_oi.py` on the VM, every 5 min, since
  ~2026-10-07 (OKX). Pull with `scripts/check_vm.sh oi`. HL OI history DOES
  exist: hyperliquid-archive/asset_ctxs/{YYYYMMDD}.csv.lz4, 2023-05-20..today
  (1,242 daily files, ~1-3 MB each), one row per coin per minute (1,440/day;
  217 coins on 2025-10-10): time, coin, funding, open_interest, prev_day_px,
  day_ntl_vlm, premium, oracle_px, mark_px, mid_px, impact_bid_px,
  impact_ask_px. Verified 2026-10-14. Gives 1m mid/mark/oracle closes and OI
  for ~3.4 years at ~4 GB total -- no fills or AWS machine needed for
  close-price bars (no OHLC or per-minute volume; those need fills).
- **HL order book history:** hyperliquid-archive/market_data/{YYYYMMDD}/{H}/
  l2Book/{COIN}.lz4, 2023-04-15..today (1,255 days). 20 levels per side,
  snapshot every ~0.5 s (6,551 in SOL 2025-10-10 21h); ~113 MB lz4 per hour
  for 217 coins (~2.7 GB/day, ~3.4 TB total): stream event windows only.
  Verified 2026-10-14. Makes H6 testable on history, not only live.
- **Hyperliquid:** 121 of our 214 coins listed (median $1.8M/day volume; 52
  coins under $1M). All trades, book, liquidations, OI public.
  - Archive (requester-pays S3): `hl-mainnet-node-data` (node_trades,
    node_fills, node_fills_by_block) and `hyperliquid-archive` (market_data L2
    snapshots, asset_ctxs). Regions (checked 2026-10-14): hl-mainnet-node-data
    = ap-northeast-1 (Tokyo), hyperliquid-archive = us-east-1. Fills start
    2025-05-25 (arXiv 2608.03616); format changes to node_fills_by_block on
    2025-07-27 (Dwellir), so the converter reads two formats. Liquidation
    object rides BOTH legs of a trade: dedupe on the liquidated-user leg.
    Liquidation flag in the older format still unverified.
  - Fill record, seen on live API samples 2026-10-14 (node_fills = "API fills
    format" per the node README): coin, px, sz (strings), side B/A, time (ms),
    startPosition, dir (Open Long / Close Long / Open Short / Close Short /
    Long > Short / Short > Long; spot fills Buy/Sell; in the archive also
    "Liquidated Cross|Isolated Long|Short", "Auto-Deleveraging", "Net Child
    Vaults" -- seen in the 2025-10-10 21h file, absent from live API samples),
    closedPnl, hash, oid,
    crossed (true = taker), fee, feeToken, tid, cloid, twapId (labels TWAP
    flow), builderFee optional. Liquidation = optional object {liquidatedUser,
    markPx, method}; it appears on the counterparty's fill too, so a forced fill
    is one where liquidatedUser == the fill's own wallet. One trade = two fills
    (one per side) sharing tid. HIP-3 markets carry a "dex:" prefix (xyz:, io:,
    para:, mkts:); exclude by prefix. Spot fills are "@N"; exclude.
  - ARCHIVE VERIFIED 2026-10-14 (one hour of each format opened):
    node_trades 2025-03-22..2025-06-21 (66 days, gaps; not needed);
    node_fills 2025-05-25..2025-07-27 (64 days): one [wallet, fill] per line,
    ~0.3 GB/day lz4, liquidation object present, no twapId;
    node_fills_by_block 2025-07-27..today (445 days, contiguous): one block
    per line {local_time, block_time, block_number, events:[[wallet, fill]]},
    ~1.0-1.5 GB/day lz4 (crash hour 21h on 2025-10-10 alone = 359 MB lz4,
    2.0 GB raw, 4.93M fills). Folder date/hour = UTC hour of fill time.
    Liquidation object on exactly half the flagged fills is the wallet's own
    (old 440/880, crash hour 285,920/571,840): dedupe rule confirmed.
    Total archive ~550 GB lz4. Access needed the SCP edit below.
    Corrections from the build-2 pilot (2026-10-14): folder hour follows the
    node's clock, not fill time -- a by-block hour file can hold fills from
    the previous second (bucket by fill `time`, read hour H+1 for spillover).
    The 2025-07-27 format overlap is hour 8 only (old 0-8, by-block 8-23).
    Empty blocks are recorded, so block_number gaps are real data gaps. A
    fourth name type '#NNNN' (outcome/prediction markets, by-block format) is
    excluded with spot '@N' (and 'PURR/USDC', spot pair 0) and HIP-3 'dex:'.
    Rule: drop names starting '@' or '#', or containing ':' or '/'. Window starts 2025-05-25 14:00
    UTC (first archive file). VM deleted 2026-10-14; its tree is in attic/vm_final.
  - Baselight has shut down (checked 2026-10-14). SQD has fills only from
    2025-10-02; 0xArchive sells liquidations only. AWS is the route (user).
- **On-chain (Dune, free):** ~160 coins on EVM/Solana. Exchange deposits
  (intent to sell), DEX swap imbalance (real flow with history), unlocks.

Date range (user, 2026-10-14): ALL Hyperliquid builds cover 2025-01-01 to today
only. Market data, bars and order-book windows start 2025-01-01; trades start
2025-05-25 (archive start). Older archive history is not used.

Storage decision (user, revised 2026-10-14, option B): NO lossless copy. Raw
stays in Hyperliquid's buckets and is streamed when needed. Convert inside AWS
in ap-northeast-1 (in-region transfer free); our bucket (Tokyo) holds only
the per-minute outputs (bars + flow table, a few GB, < $1/month). Laptop holds
the same per-minute outputs: bars in user_data/data/hyperliquid/futures/
(same filenames as okx/futures), flow table in research/hyperliquid/flow/.
New fields later = a fresh streaming pass over the raw archive (accepted risk:
HL could change or remove it). Monthly job to stay current; free live
collector (trades with wallets, book, asset ctxs) on the VM from now.

BUILD 3 RESULT (2026-10-15, [HL-FLOW1]): reference reach 0.329 vs sign-flip chance 0.446, no
beyond-chance edge; 27 flow features (30/60 min before the trigger, pair-level 60k sample)
add nothing, 0 of 210 cells. User then asked for a full-data coin-level event study over
event time (24 h before to 10 h after) with matched controls: BUILD 4, prompt
docs/prompts/HL_BUILD4_COIN_LEVEL_EVENT_STUDY.md, results to [HL-EVENT1].

CHANCE-BAR CAUTION (research check 2026-10-15): HL bars are built from TRADE prices, so
both legs carry bid-ask bounce (Roll 1984: negative lag-1 autocorrelation under a pure
random walk). Sign-flipping 1m steps destroys that, inflating the chance bar; build 3's
0.329 vs 0.446 gap (12 pts, vs 7 on OKX) may be largely bounce. Before trusting any
beyond-chance verdict: (a) lag-1 autocorrelation of 1m spread changes; (b) chance bar on
mid prices (l2Book snapshot mids in event windows; asset_ctxs mid_px where present) or on
5m/30m steps. Applies to build 4. Decision for the user.

BUILD 4b QUEUED behind build 6 (user, 2026-10-15): rolling rerun of build 4's coin-level tests, docs/prompts/HL_BUILD4B_ROLLING_RERUN.md, results to [HL-EVENT2].
ROLLING TEST APPLIES TO EVERYTHING THAT FITS A MODEL (user, 2026-10-15): also build 5's tests; queue a rolling rerun of build 4's coin-level tests after build 6 (74,607 events, cheap); later models (impact, hazard, sequence) start rolling. Descriptive event-vs-control comparisons fit nothing, so no split; add a month-by-month stability view.
ROLLING TEST (user, 2026-10-15): passes 2-3 of build 6 and later model work are scored by an
expanding walk-forward (first test block ~2025-11-21, 30-day blocks, 1-day embargo, settings
chosen per fold on that fold's validation, finding = pooled interval excludes zero AND same sign in
>= 2/3 of folds); the single 2026-05-25 cut stays only for pass 1.

G10 OKX CROSS-VENUE REMOVED from version 1 (user, 2026-10-25).
User decisions 2026-10-25/26: G8 runs on EC2 us-east-2 with a read-only inline policy on hl-build2-ec2;
book_reach_bp added; slippage at $1k only (no position will exceed $1k); G6 poison at 400 events accepted;
the two coin-unit edge cases (m = 0 bridging gap flag, 38 listings joining the benchmark one bar late) are
LEFT as they are in v1 and documented. Lesson: overnight, the next step should chain on the VM itself, not
wait on the laptop (about 10 h were lost on 2026-10-26).
PARKED UNTIL VERSION 1 IS RELEASED (user, 2026-10-25: nothing else until v1 is in): (1) the symmetric-trigger second event table; (2) a price-flow sanity check (1-minute, signed taker dollars scaled by normal volume, per liquidity tier, linear and square-root) -- build 4's '<1% explained' is most likely a method artefact, not a finding.
ORIENTATION FINDING (2026-10-24, found by the G2 swap test): the pair trigger depends on which coin is leg A (rolling spread uses each bar's own beta). User: keep the current set as version 1; add symmetric-z columns (G2b) on every event; the symmetric-trigger second event table is PARKED until the dataset is complete.
WALLETS BACK IN VERSION 1 (user, 2026-10-24, last word): build 7 restores group G6 (wallets) reusing build 5's tables, plus vault inventory; build 5's tests stay cancelled; trimming comes after the dataset exists, by feature importance computed on validation inside rolling folds only. The four backstop wallets are Hyperliquid's own HLP Liquidator vaults (leader 0xdfc24b07...).
SUPERSEDED: ALL BUILD 5 WORK CANCELLED (user, 2026-10-24, later same day): no wallet columns in the dataset (G6 removed). Existing
build 5 outputs (S3 build5/full2 ~10 GB, datasets/hl5_features.npz) are kept untouched, unused; delete only if the user says.
HL-WALLET1 results are provisional (final review never done). Backstop absorber wallets list is not needed.
PLAN CANCELLED (user, 2026-10-24): all planned builds are cancelled except the dataset work --
build 6 (model passes), build 4b (rolling rerun), and build 5's TEST part are cancelled/parked; build 5's
wallet TABLES stay as dataset group G6. Only build 7 (master dataset) proceeds; models resume after it.
Model plan notes, the rolling-test design and the full-dataset rule stay as the rules for later.
DATASET FIRST (user, 2026-10-24): build the complete master dataset BEFORE more modelling.
BUILD 7: docs/prompts/HL_BUILD7_MASTER_DATASET.md, results to [HL-MASTER1]: hedge quality (r2,
beta, neutrality, stability, mean-crossings, half-life), pair/coin reversion history (as-of),
identity/context, flow (builds 3-4 + minute shape), wallets (build 5), derivatives state (funding/
premium filled from the fundingHistory API, OI reconstructed from fills and validated), order book
(L2, 96% of hours), market regime, stop-aware payoff labels, and a reachers-vs-non-reachers
side-by-side. Builds 6 (model passes) and 4b run ON this table afterwards. Hedge quality was never
a HL model input -- it was recorded in the event table only (a planner omission, found 2026-10-24).
Measured 2026-10-24: L2 book 489/517 days complete, 21 missing, 7 partial; asset_ctxs ~97% complete,
28% missing Sep 2026, 64% Oct; fundingHistory API recovers funding and premium (hourly), not OI.
EC2 is denied in us-east-1 (SCP): run L2 processing in us-east-2.
STANDING RULE (user, 2026-10-15): always use the full dataset -- no sampling caps on events,
chunk or stream if it does not fit, subsample only for a labelled smoke test. BUILD 6 (full
pair population, ~8M triggers, wide net: horizons 2/5/10 h, windows 30m-24h, six groups):
docs/prompts/HL_BUILD6_FULL_POPULATION.md, results to [HL-FULL1]. Pending user decisions:
KEPT reading in [HL-EVENT1] (planner recommends: ALL = help, KEPT = logistic-only, not a pass);
the leaf-size grid at N ~ 8M (closed decision 2026-10-13; build 6 reports both grids).

MODEL PLAN -- KEEP AT THE FOREFRONT (user, 2026-10-15; scope after build 4 Part A results):
the models are not the bottleneck (trees found nothing beyond volatility on OKX and in
build 3), so match the model to the question, in this order: (1) GBDT / L1 logistic with
the permutation-null harness stays the scoring layer; (2) NEXT NEW MODEL: price-impact /
propagator model fitted on ALL coin-minutes (~130M), splitting transient (reverts) from
permanent impact; gives per-trigger "transient share of the dislocation" -- an upgrade of
build 4's B1 impact step; (3) time-to-mu hazard model (discrete-time, censored at 10 h,
time-varying flow after the trigger) = the H5 / delayed question; (4) sequence models on
raw minute flow (pre-train on all coin-minutes, fine-tune on events) -- NOT gated on (2)
or (3) (user, 2026-10-15); guard against overfitting with the permutation null and
day-clustered intervals; (5) Hawkes
process for liquidation cascades (H1/H9). Not worth more: trees on more hand-made
features, more SDE/OU work (closed on OKX).

BUILD 5 QUEUED (user 2026-10-15) behind build 4 Part A: wallet table (T1 wallet-coin-5min,
T2 wallet-day, T3 backstop candidates), exact concentration and wallet skill; prompt
docs/prompts/HL_BUILD5_WALLET_TABLE.md; results to [HL-WALLET1]. Replaces the H3 proxies.

BUILD 1 STOPPED at the missing-data gate (asset_ctxs gaps from May 2026: 64% of
October, all of 2026-07-08). User 2026-10-14: no synthetic or OKX fill; ALL bars
rebuilt from the trade archive, one source, window 2025-05-25..today (Jan-May 2025
given up); flow table in the same pass; GCP VM deleted; laptop update-data job
unloaded. Prompt: docs/prompts/HL_BUILD2_TRADES_TO_BARS_AND_FLOW.md.

OKX DROPPED (user, 2026-10-14, supersedes the comparison plan below): Hyperliquid is
the only venue. No OKX comparison, no H7. OKX paper book on the VM stopped; OKX
files moved to attic/. Build 1 prompt: docs/prompts/HL_BUILD1_BARS_AND_DISLOCATIONS.md.

Venue decision, updated by the user 2026-10-14: switching to Hyperliquid data is
now the FIRST order of business, maths unchanged. Build bars and the minute flow
table for EVERY HL crypto perp (234 listed today, delisted coins included to
avoid survivorship; HIP-3 non-crypto markets excluded; BTC/ETH factor-only as
now), then subset on volume/history/listing dates only, never on results. Order:
(1) raw lossless copy + 1m/30m bars, (2) re-run the dislocation set at |z|>=3
and compare with OKX on the 121 shared coins, (3) OKX-fitted models run
untouched on HL, then refit on HL with held-out splits redrawn by date, (4) flow
features for H1/H2. Run tests on a sample by default; full set only to confirm.
Every AWS machine has auto-shutdown; raw data is read once, tests read the
minute table. Original plan text, still valid as the test design: build a
parallel Hyperliquid episode set (same 3σ rule on HL prices rebuilt from fills)
and test H1/H2 both as HL flow -> HL
spreads and HL flow -> OKX spreads. Works on HL only: move research AND trading
to HL together (after the eligibility check). Works on both: trade OKX, use HL
as the information source. Neither: stop. Rule: research venue = trading venue.
Switching costs: lose 93 coins (incl. CAP, DATA, BLEND, BILL, PROS) but gain
~57 HL-only coins; unknown archive history. NOT a code rewrite: the maths reads
per-coin feathers (`COIN_USDT_USDT-{1m,30m}-futures.feather`); the exchange is
named only in `adapters/okx_futures.py` and `RAW_BAR_DIR` in envelope.py. Work =
(1) a converter from archived fills to 1m/30m bars in the same format (HL's
candle API keeps only ~5,000 bars), (2) a name map (kPEPE etc.), (3) re-run the
pipeline. Index/mark/funding come from asset_ctxs instead of OKX's 1h files. Liquidity, measured
2026-10-13 (one snapshot, 116 shared coins): OKX volume ~4.8x HL (median $7.7M
vs $1.9M/day), but book depth within 0.5% of mid only ~1.6x (median $106k vs
$49k, 20 coins; HL truncated at 20 levels) and quoted spreads similar (2.9bp vs
2.5bp). Both books are far deeper than a $300 position; "thinner books" is not
a real blocker at our size.

## Hypotheses (fix measures and direction before any test)

- H1 liquidation-driven dislocations revert
- H2 opening-flow moves persist, closing-flow moves revert
- H3 concentrated (1-3 wallets) moves revert, broad moves persist
- H4 moves pushed by historically weak wallets revert (past-only track record)
- H5 flow that dries up or flips after detection means reversion
- H6 thin, fast-refilling books revert
- H7 OKX-only dislocations (absent on Hyperliquid prices) revert
- H8 crowded positioning (funding, OI build-up) squeezes; direction uncertain
- H9 market-wide liquidation waves mark reversion season
- H10 dislocations heading into dense liquidation-price clusters overshoot then
  revert (exact only on live data; history approximate)

Data shape: raw fills kept lossless (Parquet). Working view = per-coin
per-minute table (aggressive buy/sell $, liquidation $ long/short, opening vs
closing $, top-3 wallet share, distinct wallets, trades), normalised to each
coin's own 7-day median. Episode flow features (liquidations, opening flow,
OI change) are SURPRISES: actual minus a trailing same-hour forecast for that
coin (Bessembinder & Seguin 1993: unexpected volume drives volatility; high OI
dampens it). Include the OI level as a depth control so OI features don't
restate volatility. Second-level detail only in event windows (+/-10 min
around detection) for H5/H10 and cascades. Per-episode features built from the
minute table; same models, target, chance bar and scoring as REACH-MU/DELAYED.

Side mission (parallel, after H1/H2): wallet classification. Deliverable: a
dated table (wallet, as-of date, type, past-only skill score). Types expected:
market makers, HFT/arb, directional whales, retail, vaults (HLP address known).
Traps: past-only labels, one entity many wallets, behaviour drift, survivorship.
Feeds H3, H4 and sharper H1/H2. Label the HLP and "Liquidator" vault
addresses first: they absorb HL liquidations by design (returns tracked on
tradingstrategy.ai), so their fills are the cleanest record of forced flow, a
direct measure of the H1 edge, and our competition for it. Prior work: Bitcoin trader typology (Cardiff;
<1% of users = >95% of volume; K-means found 5 types) and GMM wallet
archetypes on behaviour features. Start with the top few hundred wallets by
volume; lump the tail as small/retail.

H1 hazard (JELLY, 2025-03-26): liquidations can be MANUFACTURED (coordinated
self-liquidation into HLP on a thin coin; price +400%, no reversion), and HL
validators froze, delisted and reset the price by decree. So: test H1 split by
coin liquidity; flag admin events (freezes, oracle resets, forced closes at
decreed prices) in the converter and keep them out of the target; keep
delisted coins in (survivorship). Sources: theblock.co/post/348314,
info.arkm.com/research/jellyjelly-exploit-on-hyperliquid,
research.4pillars.io/en/research/exploring-hyperliquid-hlp-residual-attack-vectors.

ADL is a separate forced category with the OPPOSITE sign (2025-10-10: $2.1B of
profitable positions force-closed in 12 min; arXiv 2512.01112). In a crash,
liquidations force selling, ADL forces buying. Flow table keeps them apart
("Liquidated ..." vs "Auto-Deleveraging" dir); net forced flow = liquidations
minus ADL in the move's direction. Flag ADL windows; report H1 with and without
them.

Priority: H1, H2 first; then H3, H5; H4 needs careful past-only wallet scoring.
All tests: beyond chance from position, both held-out halves, false-discovery
control across hypotheses.

## Decisions waiting on the user

- 2026-11-01 reminder — GCP trial credits end ~2026-11-08: upgrade GCP or move `pt-research` to AWS. (Also deactivate the AWS key of IAM user `pt-gcp-reader` if pt-research goes.)

- AWS budget: pair-trading-monthly, $30/month, emails at 50/80/100% actual and
  100% forecast to elvisodangaobondo@gmail.com (warns, does not stop spend).
- AWS: DONE 2026-10-14. Account 289869684922 on the Paid plan (free credits
  carry over), spend limit with all three early cost controls on. CLI user
  `pair-trading` (access key in ~/.aws), default region ap-northeast-1. CLI is
  AWS's official installer in ~/aws-cli (Homebrew's build crashes on XML).
  Signed up via the "new AWS experience": region-locked to us-east-2 by
  AWS-managed SCPs. Fixed by activating advanced features (irreversible;
  removes the spend limit -- replace with an AWS Budget) and editing SCP
  p-7fpbzoem in the management account 961470857249: ap-northeast-1 added to
  RegionFloor. Statement UsEast1Partitional still denies S3 reads in us-east-1
  (blocks hyperliquid-archive: asset_ctxs, L2) until s3 reads are added to it.
- GCP VM trial ends ~2026-11-08: upgrade (~$25/mo) or move. The OI collector
  and live paper book stop if it lapses.
- Eligibility: Binance and Bybit blocked the user's location; Hyperliquid's
  front end also restricts some countries. Check before trading anywhere new.

## Working rules carried forward

- The user is a PM: plain, short, numbers first, no analogies.
- Test all models and all horizons. "Clears" = 95% interval excludes zero.
- Verify every assumption against code and data before writing a builder
  prompt.
- External research **every hour** (user's instruction). Cron jobs are
  session-only, so the new session must create it at start:
  `/loop 1h research check: search external literature and existing techniques
  relevant to the current open question(s) in the Pair_Trading research (right
  now: forced-vs-deliberate flow as the source of reversion edge -- Hyperliquid
  fills/liquidations/wallets, open interest, on-chain flows; hypotheses H1-H10
  in docs/HYPERLIQUID_HANDOFF.md; and whatever else is actively open). Report
  concrete, sourced findings that could change or improve the current plan; if
  nothing changes a definition or decision, say so in one line.`
- Never use held-out data to choose anything. Never use `pair_triggers_true` or
  the chance bar as features.
