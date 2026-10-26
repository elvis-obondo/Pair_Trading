> **ALL OF BUILD 5 CANCELLED (user, 2026-10-24). Results already produced stay on disk and S3, unused.**

# Builder prompt: Hyperliquid build 5 — the wallet table, exact concentration (H3) and wallet skill (H4)

**QUEUED (user, 2026-10-15). Do not start until build 4's Part A report has passed Code
Checker.** It reuses build 4's event table, controls, windows, harness and splits. Read
`docs/HYPERLIQUID_HANDOFF.md`, `CLAUDE.md` and `docs/prompts/HL_BUILD4_COIN_LEVEL_EVENT_STUDY.md`
first. Do exactly this; nothing else. Findings that point elsewhere are reported, not
acted on. Be frugal with messages (batch questions, no status pings).

## Why

Builds 3 and 4 measure wallet concentration with proxies (notional-weighted mean of the
per-minute top-3 share; distinct wallets summed per minute). Neither aggregates over a
30 min – 24 h window: one wallet working an order for an hour is counted as many
different top wallets. H3 (one big trader's push fades, broad participation sticks) and
H4 (moves pushed by historically weak wallets revert) need the real thing. The wallet
table also locates the liquidation backstop wallets, where forced flow actually goes.

## Verified facts (2026-10-14/15 — re-check any you rely on)

- Raw fills: `s3://hl-mainnet-node-data/` (ap-northeast-1, requester-pays), old format
  `node_fills` (one `[wallet, fill]` per line, to 2025-07-27 08:45) and `node_fills_by_block`
  (`events: [[wallet, fill], ...]`). The ingestion, execution-order, perps-only filter
  (drop names starting `@`/`#`, containing `:` or `/`), hole handling and AWS pattern
  (parallel on-demand/spot, auto-terminate, hard timer, `check` for nothing left running)
  are in `research/hyperliquid/build2_fills.py`, `build2_ec2.sh`, `build2_merge_parts.py`. Reuse
  them; do not re-derive.
- Fill fields used here: wallet, coin, px, sz, side, time (ms), dir, crossed (true = taker),
  closedPnl, fee, tid, twapId (new format), liquidation `{liquidatedUser, markPx, method}`.
  A forced leg = `liquidation.liquidatedUser == the fill's own wallet`. Backstop fills are
  trades whose fill dir starts "Liquidated…" (the absorbing side is the counterparty).
- Window: 2025-05-25 14:32 to 2026-10-13, same holes as build 2 (114 missing minutes).

## Hard rules

- No look-ahead: any wallet statistic used at a trigger T (t = 0 = T+30) uses bins < t = 0
  for concentration, and only UTC days strictly BEFORE the trigger's day for wallet skill.
- Features, windows, directions and cell counts are fixed in this text. Change after a
  result = plan change: stop and ask. Held-out used only for scoring, as build 3/4.
- Storage option B: raw stays with Hyperliquid; the derived tables live on our S3
  (ap-northeast-1) and are streamed to pt-research; nothing large on the laptop.
- Replace, don't accumulate.

## Part 0 — pilot (gate)

On 4 days (2025-10-10 crash day, 2025-07-27 format switch, 2026-07-08, 2025-06-01 old
format), build the tables below and report: rows per day, distinct wallets per day, bytes
(zstd parquet), wall time, projected total size and cost. **No cost or size cap (user,
2026-10-15): if the data is worth having, buy it.** The pilot is a correctness check (the
assertions in Part 1 must pass) and a measurement; proceed to the full run after Code Checker
passes it, keeping every machine on auto-terminate with a hard timer. Disk is not a reason to
drop columns: the tables live on S3 and are streamed. Still log the measured cost.

## Part 1 — the tables (perp coins only)

**T1 `wallet_bin`** — one row per (wallet, coin, 5-minute UTC bin) with any activity:
`taker_buy_usd, taker_sell_usd, open_buy_usd, open_sell_usd, close_buy_usd, close_sell_usd,
forced_long_usd, forced_short_usd (wallet is the liquidated user), twap_usd (NaN before
2025-07-27), n_taker_fills, maker_usd`. USD = px × sz. Aggregate by fill, not by tid; a
wallet's taker side is its own fills with crossed = true. Bin label = bin open; bins that
touch an archive hole are flagged.
**T2 `wallet_day`** — one row per (wallet, UTC day): `volume_usd, taker_share,
closed_pnl_usd (sum of closedPnl over all its perp fills), fees_usd, n_coins, n_forced_events
(own liquidations), forced_usd, n_fills`.
**T3 `vault_wallets`** — list the wallets that are the non-liquidated counterparty on
"Liquidated…" fills, by total absorbed USD (top 20 with share of all backstop USD, and by
month), plus any wallet that is the taker on Auto-Deleveraging. Name them
`backstop_candidate`; do not hard-code addresses; list for the user to confirm (HLP /
liquidator vault).

Assertions: the sum over wallets of T1 taker notional per (coin, minute→bin) equals the flow
table's `taker_buy_usd + taker_sell_usd` for the same bins on every pilot day (max abs error
reported); open/close and forced sums likewise.

## Part 2 — features at t = 0 for build 4's coin-level events (and its matched controls)

All net of the event's push sign d (positive = pushing the coin the way it dislocated), on the
same windows as build 4: P1 [−60, 0), C6 [−360, 0), C24 [−1440, 0).

Group CONC_EXACT (taker flow on the pushing side, from T1): `top1_share`, `top3_share`,
`hhi` (Σ share²), `n_wallets` (distinct pushing-side wallets), `persistent_share` (share of
pushing-side notional from the coin's 10 largest taker wallets by trailing 7-day notional,
ranked from days before the trigger's day; missing → NaN), `twap_share` (T1 twap_usd ÷ taker
notional). Expected directions fixed now: higher top1/top3/hhi/persistent_share/twap_share
→ reaches mu MORE; more wallets → LESS. Retire the proxy H3 group from the tests (keep the
columns).

Group SKILL (from T2, strictly before the trigger's day): per wallet `skill` = trailing 30-day
sum of closed_pnl_usd ÷ trailing 30-day volume_usd, shrunk to 0 with weight n_fills ÷ (n_fills
+ 5,000) (K fixed here); NaN with < 5 active days. Event features: pushing-side notional-
weighted mean skill; share of pushing-side notional from wallets in the bottom decile of
skill and the top decile (deciles computed on the day before, across active wallets);
`share_prior_forced` = share from wallets liquidated at least once in the prior 30 days.
Expected directions: pushing by weak wallets (bottom-decile share, prior-forced share) →
reaches mu MORE; by strong → LESS. One entity may run many wallets and behaviour drifts;
say so in the report.

Group BACKSTOP (from T3 + T1): share of the window's pushing-side notional taken by
`backstop_candidate` wallets on the other side, and forced dollars absorbed on the book vs by
those wallets. Descriptive plus one feature `backstop_share`; direction two-sided.

## Part 3 — tests (the build 3/4 design, scored by the ROLLING walk-forward)

(Amended 2026-10-15, user: everything that fits a model uses the rolling design. Use the
"Rolling (walk-forward) test" section of `docs/prompts/HL_BUILD6_FULL_POPULATION.md` exactly:
expanding window, first test block ~180 days in, 30-day blocks, 1-day embargo, settings per fold on
that fold's validation, pooled + per-fold scoring, finding = pooled interval excludes zero AND same
sign in >= 2/3 of folds, pooled permutation null. Wherever this section says "HO1/HO2" or "both
halves", read "the rolling design". Skill scores are already past-only and need no refit. Keep
the single cut only as one like-for-like row against build 4.)

Reference (vol_48, vol_48_1m, sigma, |z|) vs reference + CONC_EXACT, + SKILL, + BACKSTOP,
+ all, + pruned set (pruning rule on validation); logistic L1 and LightGBM depth 1–4; HO1/HO2
separately; flag share at 80% catch, top-20% hit rate, beyond-chance gap, paired day-
clustered intervals, permutation null; reading rules HELP / SIGNAL / REGIME-DEPENDENT. Also
add the Q1 event-time comparison from build 4 (events minus matched controls, control sets
1 and 2, windows P1/P2/P3/C6/C24) for `top1_share, hhi, n_wallets, persistent_share,
bottom-decile share`. Count every cell before running and report the expected false
positives. The pre-registered strong-event row (|z| ≥ 3 OR forced share P1 > 0) is repeated
for each group. A finding = same direction and an interval excluding zero in both halves.

## Review and receipts

- Code Checker ("Code Checker 2"; check `ListAgents`): schema and code before the pilot;
  the pilot numbers before the full run; the feature code and the test design before Part 3;
  log + NUMBERS.md + diff before reporting. A fix that changes a feature, window, K, a gate
  or the cell count goes to the user.
- Logs `research/hyperliquid/logs/build5_*.log` and `research/dislocation_model/logs/hl5_*.log`;
  NUMBERS.md section `[HL-WALLET1]`, every number with its log and M/A tag.
- Final report: plain and short (PM-level): the table sizes and cost, the backstop candidates,
  one line per group (help / no / wrong direction / regime-dependent) for H3 and H4, the
  limits (many wallets per entity, drift, survivorship), the checker's verdict, files changed.
