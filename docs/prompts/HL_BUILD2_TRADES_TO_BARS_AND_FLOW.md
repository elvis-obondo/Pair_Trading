# Builder prompt: Hyperliquid build 2 — bars and flow table from the trade archive, then the dislocation set

Continues build 1 (`docs/prompts/HL_BUILD1_BARS_AND_DISLOCATIONS.md`, stopped at
the B2 missing-data gate). Read `docs/HYPERLIQUID_HANDOFF.md` and `CLAUDE.md`
first. Do exactly this; nothing else. Findings that point elsewhere are
reported, not acted on.

## User decisions this implements (2026-10-14)

- **Option (c), from trades.** asset_ctxs has archive gaps from May 2026 (64%
  of October missing, 2026-07-08 entirely). No synthetic fill, no OKX fill.
  Price bars are rebuilt from the trade archive, which has all 24 hours on the
  gap days checked (2026-07-08, 08-15, 09-15, 09-20, 10-05).
- **One price source for the whole window: trades, 2025-05-25 to today.**
  No splicing of asset_ctxs mid prices with trade prices (seams would create
  false dislocations). Jan–May 2025 is given up.
- The per-minute flow table (plan build 2) is built in the same pass.
- **End Google Cloud billing.** **Unload the laptop update-data job.**
- Storage option B unchanged: raw stays in Hyperliquid's buckets; our bucket
  and the laptop hold only derived per-minute outputs.

## Part C — housekeeping (do first)

### C1. End Google Cloud billing (irreversible — follow the order exactly)

1. Inventory what is on the VM that is not already on the laptop:
   `trading_data/`, `logs/`, any `*.csv`/`*.json` state, the OI collector's
   output. Pull anything not already pulled; confirm by file count and size.
2. Send Code Checker the inventory and the pull receipts before step 3.
3. Delete the instance `pairs-trading` (us-central1-a) and its boot disk;
   release any reserved static IP; stop/delete the Cloudflare tunnel config
   for the dashboard if it lives on the VM (it points at nothing now).
4. Verify with `gcloud compute instances list`, `gcloud compute disks list`,
   `gcloud compute addresses list` on the project in `docs/CLOUD_DEPLOY.md`:
   all empty. Do NOT delete the GCP project or the billing account; report
   any other billable resource you find instead of deleting it.
5. Update `docs/CLOUD_DEPLOY.md` and `docs/VM_HANDOFF.md` top line: VM deleted
   2026-10-14, why, where the final ledger now lives.

### C2. Unload the laptop job

`launchctl` unload/bootout `com.pairtrading.update-data` and remove its plist
from `~/Library/LaunchAgents/` (move it to `attic/`). Check for any other
`com.pairtrading.*` agents (`launchctl list | grep pairtrading`); list them;
unload any that call a script now in `attic/`. Report what was unloaded.

### C3. Clean up build 1

- The asset_ctxs mid-price bar files in `user_data/data/hyperliquid/futures/`
  are superseded: delete them (replace, don't accumulate). KEEP the ctx files
  (funding, OI, premium, oracle, mark, impact prices) in
  `user_data/data/hyperliquid/ctx/`; they are features, gaps stay NaN.
- Delete the 6.4 GB raw asset_ctxs cache once the ctx files are confirmed.
- `research/adapters/hyperliquid_futures.py` stays the one adapter; repoint it
  at the trade-built bars in Part D.

## Part D — bars and flow table from trades

### Verified facts (checked 2026-10-14 — re-check any you rely on)

- `s3://hl-mainnet-node-data/` (ap-northeast-1, **requester-pays**):
  - `node_fills/hourly/{YYYYMMDD}/{H}.lz4`: 2025-05-25..2025-07-27, one JSON
    `[wallet, fill]` per line, ~0.3 GB lz4/day, no `twapId`.
  - `node_fills_by_block/hourly/{YYYYMMDD}/{H}.lz4`: 2025-07-27..today,
    one block per line `{local_time, block_time, block_number, events:
    [[wallet, fill], ...]}`, ~1.0–1.5 GB lz4/day; crash hour 2025-10-10 21h =
    359 MB lz4, 2.0 GB raw, 4.93M fills.
  - **2025-07-27 exists in BOTH formats.** Dedupe on (tid, wallet).
  - Folder date/hour = UTC hour of the fill `time` (ms).
- Fill fields: coin, px, sz (strings), side B/A, time (ms), startPosition,
  dir, closedPnl, hash, oid, crossed (true = taker), fee, feeToken, tid,
  cloid, twapId (new format only), builder/builderFee optional, liquidation
  optional `{liquidatedUser, markPx, method}`.
- `dir` values seen: Open Long, Close Long, Open Short, Close Short,
  Long > Short, Short > Long; spot Buy/Sell; plus Liquidated Cross|Isolated
  Long|Short, Auto-Deleveraging, Net Child Vaults (2025-10-10 21h).
- One trade = two fills (one per side) sharing `tid`. The liquidation object
  appears on both legs; the forced leg is where `liquidatedUser` == the fill's
  own wallet (exactly half of flagged fills in both formats' samples).
- Coin names: perps plain (BTC, kPEPE); spot `@N`; HIP-3 `dex:COIN`.
- AWS: `~/.local/bin/aws`, user `pair-trading`, account 289869684922; EC2 and
  S3 allowed in ap-northeast-1 (SCP edited). Budget `pair-trading-monthly`
  $30, alerts only, no hard cap. Our bucket `pair-trading-hl-289869684922`
  in ap-northeast-1 (create if build 1 did not).

### Rules (decision rules — fixed before running)

- **Universe:** perp coins only (drop `@…`, anything with `:`), BTC/ETH kept
  as FACTOR_ONLY. Delisted coins included over their trading life.
- **Which fills make a trade:** for price and volume, one fill per `tid` —
  the taker fill (`crossed == true`). Report trades with zero or two takers.
- **Which trades set the price:** only on-book trades — taker fill `dir` in
  {Open Long, Close Long, Open Short, Close Short, Long > Short, Short > Long}.
  Off-book transfers (Liquidated Cross/Isolated…, Auto-Deleveraging, Net
  Child Vaults) are excluded from OHLCV and counted in the flow table instead.
  Report their counts and notional.
- **Bars:** 1m bar labelled T covers fills with T ≤ time < T+1m (label = bar
  OPEN, as before). open/high/low/close from trade px in time order (tie-break
  by tid), volume = sum of sz (coin units) and a `notional` column = sum
  px·sz. 30m bars aggregated from the 1m bars (open of first, close of last,
  max/min, sums); assert on every bar.
- **No-trade minutes** inside a coin's life are real, not missing: close =
  previous close, open=high=low=close, volume 0, and a column
  `mins_since_trade`. Never carry before the first trade or after the last.
- **Archive gaps are missing, not quiet:** every hour file from 2025-05-25 to
  yesterday must exist. Also check `block_number` continuity in the by-block
  format and report gaps. A missing hour or block gap makes those minutes NaN
  for every coin. **If missing time exceeds 0.1% of the window, STOP and
  report.**
- **Flow table**, one row per coin per minute, from taker fills unless stated:
  `taker_buy_usd`, `taker_sell_usd` (side B / A); `n_trades`;
  `n_taker_wallets`; `top3_taker_share` (top-3 taker wallets' share of the
  minute's taker notional); `open_taker_usd`, `close_taker_usd` (from the
  taker's dir; for flips, the closing part is min(|startPosition|, sz) and the
  rest opens); `liq_forced_long_usd`, `liq_forced_short_usd` (forced legs on
  the book: liquidatedUser == wallet, split by the side being closed — count
  the forced leg whether it is taker or maker, once per tid);
  `backstop_liq_usd` (dir Liquidated…), `adl_usd` (Auto-Deleveraging);
  `twap_taker_usd` (twapId not null; NaN before 2025-07-27, not 0). Raw
  dollars only; normalisation to each coin's 7-day median is a later feature
  step, not this build.
- No look-ahead: a minute's row uses only fills with time inside that minute.

### D0. Pilot (gate)

On ONE small EC2 machine in ap-northeast-1 (spot if available), process
2025-10-10 (crash day), 2025-07-27 (both formats, dedupe), 2026-07-08 (a
day asset_ctxs is missing) and 2025-06-01 (old format). Report: wall time,
peak memory, output size, and the projected time and AWS cost for the whole
window. Send code + decision rules + pilot numbers to Code Checker.
~~Cost gate~~ REMOVED by the user 2026-10-14: no stop on cost or time. The pilot is a
correctness check only (Code Checker reviews its outputs); then proceed to D1.
Measured time and projected cost are still logged.

Every EC2 machine: instance-initiated shutdown = terminate, a hard
`shutdown -h +N` timer set at launch (N = 2 × the projected runtime), and a
check after the run that nothing is left running (`aws ec2
describe-instances` empty of running instances).

### D1. Full run

- Process 2025-05-25..yesterday. Read raw straight from Hyperliquid's bucket
  in-region; write per-coin per-month Parquet (bars + flow) to our bucket.
- Bring down to the laptop: bars as `user_data/data/hyperliquid/futures/`
  feathers in the existing schema (`date, open, high, low, close, volume`,
  plus `notional`, `mins_since_trade`), flow table to
  `research/hyperliquid/flow/{COIN}.parquet`.
- Repoint `research/adapters/hyperliquid_futures.py` and `data_loader` at
  these bars (this also fixes `data_loader`'s broken import — remove the LST
  import). Point `envelope.RAW_BAR_DIR` at the 1m folder.

### D2. Bar check against Hyperliquid's candles (gate)

Hyperliquid's candle API is trade-based, so this is an exact check. For every
listed coin over the API window (~3.5 days, latest data): share of 1m bars
whose close equals the candle close, and the same for volume within 0.5%.
**Decision rule:** ≥99% matching closes for ≥95% of coins, else STOP and
report. List every coin below.

## Part E — dislocation set

- Apply the `mkdisloc.py` fix from build 1 (slice each pair to
  `[max(first), min(last)]`; per-coin contiguity; docstring updated) if not
  already done. Internal NaN (archive gaps) must not be silently dropped:
  report how many candidate windows contain NaN and are skipped by the
  existing finite checks.
- Run with all parameters unchanged (ENTRY_SIG 3.0, FIT_BARS 336, HORIZONS 20,
  PER_PAIR 20, TARGET 60,000, seed 20261004) on the trade-built 30m panel.
- Report mkdisloc's summary lines plus: coins and pairs used, pairs skipped as
  too short, delisted coins included, dislocations per month, the 70/30 day
  split date.

## Review and receipts

- Code Checker (session "Code Checker 2" as of 2026-10-14; check
  `ListAgents`): C1 inventory before deleting the VM; code and rules before
  D0; pilot numbers before D1; log + NUMBERS.md section + diff before
  reporting. Fix its findings on bugs, look-ahead, mismatched numbers, rules
  not applied as written, missing receipts; re-send until it passes.
  Anything that would change a decision rule goes to the user.
- Logs: `research/hyperliquid/logs/build2_*.log`, one per step.
- NUMBERS.md: new section `[HL-BUILD2]`, every number with its log.
- Final report: plain and short (PM-level, numbers first), the checker's
  verdict, files changed, what was deleted (VM, bars, caches), what was done,
  and AWS + GCP cost incurred.
