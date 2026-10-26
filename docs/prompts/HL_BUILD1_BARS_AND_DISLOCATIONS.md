# Builder prompt: retire OKX, then Hyperliquid build 1 — bars from asset_ctxs and the dislocation set

Read `docs/HYPERLIQUID_HANDOFF.md` and `CLAUDE.md` first. Do exactly this;
nothing else. Findings that point elsewhere are reported, not acted on.

## User decisions this implements (2026-10-14)

- **OKX is dropped entirely.** Hyperliquid is the only venue for research. No
  OKX comparison, no venue switch, no parallel paths. The strategy is expected
  to translate; we test it on Hyperliquid directly.
- **The OKX paper book on the GCP VM stops now**, with the stop monitor, the
  scanner cron and the OKX open-interest collector.
- **OKX files move to the attic, not deleted**, so past NUMBERS.md results stay
  re-checkable.
- Hyperliquid data covers **2025-01-01 to today** only.
- Storage option B: raw stays in Hyperliquid's buckets; our S3 bucket and the
  laptop hold only derived per-minute outputs.

## Part A — retire OKX

### A1. VM (GCP project and zone in `docs/CLOUD_DEPLOY.md`; wrapper `scripts/check_vm.sh`)

In this order, recording each command and its output in the log:
1. `scripts/check_vm.sh status`, `positions`, `ledger 20`: snapshot the final state.
2. `scripts/check_vm.sh pull` and `scripts/check_vm.sh oi`: bring the final
   ledger, scan history and open-interest days down. Confirm the files landed.
3. On the VM: remove the `vm_scan_cycle` and `vm_housekeeping` crontab lines
   and whatever schedules `collect_oi.py` (find it: `crontab -l`, `docker ps`,
   systemd). Then stop the stop monitor so it does not restart:
   `docker compose -f docker-compose.trading.yml down` in `~/Pair_Trading`
   (it is `restart: unless-stopped`, so `down`, not `stop`).
4. Verify: `crontab -l` shows none of the three, `docker ps` shows no
   pairs containers. Do NOT delete or stop the instance itself; that is the
   user's call with the trial end (~2026-11-08).

### A2. Laptop files

- Move `user_data/data/okx/` to `attic/okx_data/`, and OKX-built datasets in
  `research/datasets/` (`disloc*`, `envfeat.npz`, `envelope_preds_*`, anything
  else built from OKX bars — list them) to `attic/okx_datasets/`. Add both to
  `.gitignore` before moving (2.3 GB must never be committed).
- Code: the build path below gets pointed at Hyperliquid by replacing the OKX
  source, not by adding a switch. `adapters/okx_futures.py`,
  `adapters/okx_spot.py`, `adapters/lst_tokens.py` (check `user_data/data/lst/`
  first; if any files exist, report and keep it) and the OKX download/ops
  scripts (`scripts/update_data.sh`, `download_1m.sh`, `backfill_history.sh`,
  `download_basis.sh`, `collect_oi.py`, `history_coverage.py`,
  `merge_bar_history.py`) move to `attic/`.
- Every OTHER module that reads OKX paths or names OKX (grep `okx`, `OKX`,
  `_USDT_USDT`): do not modify. List each one in the report with one line on
  what it does, so the user can decide whether it is ported or retired. The
  live trading code (scanner, stop monitor, signal generator) is in this list.
- NUMBERS.md and logs are history: leave them. Add one line at the top of
  NUMBERS.md: results before 2026-10-14 are OKX; OKX data is in attic/.

## Part B — Hyperliquid bars and the dislocation set

### Verified facts (checked 2026-10-14 — re-check any you rely on)

- AWS CLI works: `~/.local/bin/aws`, user `pair-trading`, account
  289869684922. Allowed regions: ap-northeast-1, us-east-1, us-east-2,
  us-west-2. Budget `pair-trading-monthly` $30.
- Source: `s3://hyperliquid-archive/asset_ctxs/{YYYYMMDD}.csv.lz4`, region
  us-east-1, **requester-pays** (`--request-payer requester` on every call).
  ~1–3 MB lz4 per day. Decompress with `lz4 -dc` (`/opt/homebrew/bin/lz4`).
- Columns: `time, coin, funding, open_interest, prev_day_px, day_ntl_vlm,
  premium, oracle_px, mark_px, mid_px, impact_bid_px, impact_ask_px`. `time`
  is a minute stamp like `2025-10-10T00:00:00Z`; 1,440 rows per coin per day;
  217 coins on 2025-10-10.
- The bar format the maths reads (from the OKX files): one feather per coin
  per timeframe, columns `date` (datetime64[ms, UTC], labelled by bar OPEN),
  `open, high, low, close, volume` (float64). Bar labelled T carries the close
  at T+bar.
- The dislocation path reads only `date` and `close`: the adapter's
  `sync_normalized_store` copies `[date, close]` into `user_data/normalized/`,
  `data_loader.get_price_levels` builds ln(close), `universe_panel.load_panel`
  caches it, `mkdisloc.py` reads the panel. `envelope.RAW_BAR_DIR` points at
  the 1m bar folder.
- `universe_panel.FACTOR_ONLY = {BTC, ETH}`: carried, never paired. Keep.
- `mkdisloc.py` assumes every ticker's finite region runs to the LAST bar and
  slices each pair from `max(first_a, first_b)` to the end. Delisted coins end
  early, so as written their pairs would hit trailing NaN and
  `rolling_spread_stats` would return all-NaN: silently dropped.

### Hard rules

- No look-ahead. Bar labelled T carries only what is observable at T+bar.
- Nothing chosen on held-out data. Nothing tuned. Rule parameters unchanged.
- Replace, don't accumulate: one adapter, one data path, no copies of
  mkdisloc or data_loader.

### B0. Timestamp convention (gate, before building anything)

Does the `asset_ctxs` row stamped T describe the state at T (so it is the close
of the 1m bar labelled T−1m), or something else?
- Hyperliquid's candle API keeps the last ~5,000 1m candles per coin:
  `POST https://api.hyperliquid.xyz/info {"type":"candleSnapshot","req":{"coin":C,"interval":"1m","startTime":ms,"endTime":ms}}`.
  For BTC, ETH, SOL, HYPE, DOGE and the most recent full day of `asset_ctxs`,
  correlate `mid_px` 1m log returns with candle close returns at lags −2..+2
  minutes. Report the best lag per coin.
- **Decision rule:** same best lag for all 5 → use it to set the label. Coins
  disagree → STOP and report.

### B1. Coin list

- Every coin appearing in any `asset_ctxs` file from 2025-01-01 to today,
  including delisted ones (never today's listing). Exclude names containing `:`
  (HIP-3) or starting with `@` (spot), if any appear.
- Keep Hyperliquid's names (kPEPE etc.); log-price spreads ignore the 1000x
  scale.
- Output `research/hyperliquid/coins.csv`: coin, first_date, last_date,
  listed_minutes, filled_minutes, nan_minutes, delisted yes/no.

### B2. Bars

- Price: `mid_px` (not mark, not oracle). 30m close = the 1m close of the
  bar's last minute; assert equality on every bar.
- New adapter `research/adapters/hyperliquid_futures.py` with the same
  `sync_normalized_store` contract, replacing the OKX one in `data_loader`.
  Bar files: `user_data/data/hyperliquid/futures/{COIN}-{1m,30m}.feather`
  (choose the naming in the adapter; one place), exactly the schema above.
  `close` holds the price; `open, high, low, volume` are NaN — never fake them.
  README in that folder: USDC-margined Hyperliquid perps, close-only bars from
  asset_ctxs mid_px, 2025-01-01 onward.
- Point `envelope.RAW_BAR_DIR` at the new 1m folder. Rebuild the normalized
  store from Hyperliquid only.
- Missing minutes, **decision rule**: forward-fill runs of ≤5 consecutive
  missing minutes inside a coin's listed life and count them; never fill before
  first or after last appearance; longer runs stay NaN and are listed. If more
  than 5% of coins have >1% of listed minutes filled or NaN, STOP and report.
- Extras: other columns (funding, open_interest, premium, oracle_px, mark_px,
  impact_bid_px, impact_ask_px, day_ntl_vlm) per coin at 1m to
  `user_data/data/hyperliquid/ctx/{COIN}-1m-ctx.feather`. Unused here.
- Raw downloads go to a cache outside git; delete after Code Checker passes.
  Copy finished bars and ctx files to `s3://pair-trading-hl-289869684922/`
  (create it in ap-northeast-1).

### B3. Bar check against Hyperliquid's own candles (gate)

For every coin still listed, over the candle API's window (~3.5 days):
correlation of 30m log returns, mid bars vs candle closes, at lags −1, 0, +1.
**Decision rule:** lag 0 best for ≥90% of coins, else STOP — the label is
wrong. List coins with lag-0 correlation below 0.9 (report, do not drop).

### B4. Dislocation set

- Fix `mkdisloc.py`: slice each pair to the overlap of its coins' finite
  regions, `[max(first), min(last)]`; the contiguity assertion checks each
  coin is contiguous between its own first and last. Update its docstring
  (the "753 days / 212 tickers" text is OKX).
- Run with all parameters unchanged (ENTRY_SIG 3.0, FIT_BARS 336, HORIZONS 20,
  PER_PAIR 20, TARGET 60,000, seed 20261004). Output to
  `research/datasets/` via `paths.DISLOC_PREFIX` (the OKX files are in the
  attic by now).
- Report mkdisloc's summary lines plus: coins and pairs used, pairs skipped as
  too short, delisted coins included, dislocations per month, the 70/30 day
  split date.

## Review and receipts

- Before any step longer than a few minutes, send Code Checker (session
  "Code Checker 2" as of 2026-10-14; check `ListAgents` for the current name)
  the code and these decision rules as text. Before reporting, send the log,
  the NUMBERS.md section and the diff. Fix its findings on bugs, look-ahead,
  mismatched numbers, rules not applied as written, missing receipts; re-send
  until it passes. Anything that would change a decision rule goes to the user.
- Part A's VM steps are not long runs, but send the A1 command list to Code
  Checker before running it.
- Logs: `research/hyperliquid/logs/build1_*.log`, one per step.
- NUMBERS.md: new section `[HL-BUILD1]`, every number with its log.
- Final report: plain and short (PM-level, numbers first), the checker's
  verdict, files changed and moved, the list of OKX-bound modules left in
  place, what was done, and AWS cost incurred.
