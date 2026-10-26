# Handoff — Pair Trading System

> **RETIRED SYSTEM — historical record, 2026-09-12.**
>
> This documents the single-pair nautilus paper process, which was deleted on
> 2026-09-12 along with `nautilus/`, `diagnostics/` and `scripts/batch_backtest.py`.
> Its final ledger is archived at `research/retired_nautilus_paper/`, with a README
> explaining what the numbers actually mean.
>
> It is kept for two things that still apply: the ledger-corruption incident recorded
> below, and the MIN_BARS cold-start gap. The current system is described in
> `docs/SCANNER_SESSION_HANDOFF.md` and the top-level README.

Last updated: 2026-08-20. Read this first in a new session — it's the current
state of the live system and the reasoning behind it. Details on individual
pieces live in code comments and `docs/paper_trading_v2_design.md`; this file
is the "what's true right now and why" summary.

**This file was stale for at least a few days before this update** — the
previous version (dated 2026-08-17) still said the live pair was GALA/UMA;
by the time this was corrected the VM had already moved through GALA/UMA →
IOST/UMA → SOPH/WAL without this doc being updated for any of it. Don't
assume this file is current without cross-checking `scripts/check_vm.sh
status` and `ledger` against it — that's what caught the drift this time.

## What's live right now

- **Runs on a cloud VM, not the laptop.** Moved 2026-08-16 — see
  `docs/CLOUD_DEPLOY.md` for the full deploy record (GCP, not Oracle —
  Oracle's Ampere A1 free tier hit "out of capacity" and we switched). Check
  on it with `scripts/check_vm.sh status` (or `logs`/`ledger`/`heartbeat` —
  see that script's header comment for the full list).
- **Pair**: API3/SOPH, paper mode, switched 2026-08-20. Picked via a fresh
  full-universe walk-forward `run_all.py` scan (3,000 pairs diagnosed):
  `p_value=0.0000, half_life_hours=9.6, coint_stability=0.5,
  recent_cointegrated=True` — top-ranked tradeable candidate at selection
  time. Prior pairs this week, in order: RLS/ZK → GALA/UMA → GALA/SAND
  (abandoned) → IOST/UMA (3 trades, closed/manual-closed) → SOPH/WAL (never
  opened a trade) → API3/SOPH (current). Switch with `scripts/check_vm.sh
  switch TICKER_A TICKER_B ["stats string"]` — see that script's header for
  what it automates, and the "Full code sync" note below for what it doesn't.
- **Model change, deployed alongside this pair switch**: Gate 2's OU fit is
  now EWMA-only (`fit_ou_ewma` in `research/ou_model.py`, pair-adaptive
  half-life = 2.0x each pair's own reference half-life). The old static
  full-window fit (`fit_ou`) is no longer used in the live entry-signal path
  — still used elsewhere (diagnostics, visualizer, validation scripts), just
  not for Gate 2 anymore. Backtested across 7 pairs and 3 distinct 7-day
  holdout windows before deploying: all 3 windows net positive
  (+$92/+$159/+$58 across the 7 pairs), consistently higher take-profit rate
  and lower adverse-move rate than the static estimator. Sweep data at
  `research/ab_sweep2_results.csv`, `ab_sweep3_results.csv`. Known gap, not
  fixed: Gate 4 (theta significance) still tests the *static* fit's
  significance, not EWMA's — a real mismatch, flagged in code, not silently
  glossed over. Also live from earlier the same week: Student-t OU
  residuals, Monte Carlo (not reflection-principle) reversion probability,
  `prob_threshold` 0.67 → 0.60.
- **Full code sync is a separate step from `check_vm.sh switch`** —
  discovered this session. `switch` only pushes `nautilus/run_trading.py` to
  the VM; `research/` and the rest of `nautilus/` are NOT auto-synced on
  every switch, so a pair rotation alone can silently leave the VM running
  stale model code. Before switching pairs when source has changed:
  `gcloud compute scp --recurse nautilus/ research/
  pairs-trading:~/Pair_Trading/ --project=project-0671be06-e22a-44d8-83c
  --zone=us-central1-a` (stage a clean copy first if `research/` has large
  scratch/log files in it — the Docker build context has no exclude list).
- **Ledger was reset to empty on 2026-08-17**, then accumulated real trades
  again since (GALA/UMA, IOST/UMA) — as of the API3/SOPH switch,
  `next_trade_num=5`, `equity=0.9397` (not the bare `TRADE_CAPITAL=30`
  anymore; this reflects realized losses from the trades since the reset).
  Ledger history before the 2026-08-17 reset (trades #1-3, including the
  abandoned GALA/SAND position) is archived at
  `research/paper_trades_archive_20260817_105807.csv`.
- **Config**: `TRADE_CAPITAL=30`, `TARGET_LEVERAGE=50x`, `CAPITAL=300`
  (displayed equity = `TRADE_CAPITAL + cumulative realized PnL`, recomputed
  fresh from the ledger on every restart — it is NOT a persisted balance).
- **Cointegration significance threshold: 0.01**, not the textbook 0.05 —
  changed deliberately this week, see below.

## Math/model improvement backlog (2026-08-20)

Not urgent, not started — a prioritized list from a session reviewing where
this system's math has known gaps, meant to be worked one at a time in
future sessions. Context for all of it: this week already added Student-t OU
residuals, Monte Carlo (not reflection-principle) reversion probability, and
switched Gate 2 from a static full-window OU fit to `fit_ou_ewma` (pair-
adaptive EWMA, half-life = 2.0x each pair's own reference half-life,
validated across 7 pairs / 3 holdout windows before deploying — see
`research/ab_sweep2_results.csv`, `ab_sweep3_results.csv`). Ranked by how
ready-to-build each is, not by novelty:

**Already identified, not yet built:**
1. **FDR correction on the cointegration screen.** Testing ~35,778 pairs/week
   at a flat p<0.01 isn't a real multiple-comparisons correction — see "Why
   threshold = 0.01" below. A Benjamini-Hochberg correction would replace the
   blunt flat threshold with a principled false-discovery-rate target.
2. **Change-point detection as a live monitor.** Already validated this week
   (qualified go — detects a real cointegration breakdown same-day to a few
   days after it happens, tested on real positive/negative controls; see the
   experiment writeup this backlog came out of). Not wired up yet. Lowest
   effort here since the validation work is already done — build it as a
   standalone daily check the user reads, not wired into live trading
   automatically (that was the recommended integration path).
3. **Gate 4's significance-test mismatch.** Gate 2 now fits theta/mu via
   EWMA, but Gate 4 (theta significance, `ou_residual_diagnostics`) still
   tests the *static* full-window fit's significance — a real, flagged
   mismatch. Needs a proper standard-error formula for a weighted/recursive
   regression (the current OLS SE formula doesn't apply), not just swapping
   the function call.

**New gaps found working the OU/EWMA/backtest chain this week:**
4. **The hedge ratio itself is still a static single-window OLS fit.**
   `compute_spread` (`research/pair_analysis.py`) never got the EWMA
   treatment theta/mu/sigma just did — same idea, one layer earlier in the
   pipeline. Worth testing the same way (backtest sweep, not just swap and
   ship).
5. **OLS asymmetry in the hedge ratio.** `compute_spread` regresses price_a
   on price_b, treating price_b as noise-free — arbitrary, since both legs
   are equally noisy real prices. Total least squares (orthogonal
   regression) would treat them symmetrically. Small, well-scoped fix.
6. **Exit stops are heuristic, not derived from the model.** Take-profit at
   80% of distance-to-mu, a flat 24h time cap (`MAX_TIME_STOP_HOURS`), a flat
   2.5σ adverse-move stop — none of these come from the OU model itself.
   There's real optimal-stopping theory for mean-reverting processes (a
   free-boundary problem: solve for the exit boundary that maximizes
   expected return net of transaction costs) that would replace these
   hand-picked constants with one derived policy. The most mathematically
   substantial item on this list, not just a parameter tweak.
7. **Position sizing isn't linked to model confidence.** Sizing
   (`research/position_sizer.py`) is a fixed leverage target split by beta —
   it doesn't scale with how strong the signal actually is. A
   fractional-Kelly rule driven by the Monte Carlo reversion probability
   would size bigger on stronger signals instead of the same bet every time.

**Bigger lift, more speculative — want more evidence before recommending:**
8. Johansen's test instead of Engle-Granger for the cointegration screen
   (symmetric, no forced regression-order choice) — real upgrade, but EG
   isn't obviously broken today, so this is "nice to have."
9. HMM regime-switching instead of the change-point detector's hard
   break/no-break call — more expressive, but this is the same
   complexity-vs-payoff question the Kalman filter (see below) just lost on.
   Want a Kalman-style go/no-go test before building it.

**Cuts across all of the above**: only one walk-forward fold has ever been
run (see below — "one fold is not enough to draw statistical conclusions").
Every backtest number behind this week's changes, including the EWMA sweep,
is small-sample. More folds would give real statistical footing to
prioritize between the items above, not just this one.

**Already tested and rejected — don't rebuild without new evidence**: a
2-state Kalman filter (random-walk theta/mu, replacing the EWMA/static
split) was implemented and backtested against EWMA on real fitted OU
parameters this week. Clear no-go: median convergence took 78% of the
30-day window against a ~20-25% target, and EWMA tracked more accurately in
17 of 20 test runs even with EWMA deliberately handicapped to match
Kalman's own (slow) convergence speed. Not a close call.

## Walk-forward methodology (why RLS/ZK, and how to repeat it)

The core problem we solved this week: pair screening and backtest evaluation
were using nearly the same data window (both anchored to "today", both ~30
real days), so batch backtest returns were largely in-sample and not
predictive of forward performance. Fixed by separating them in time:

1. Selection uses data **through 7 days before "now"** (`end_date` param on
   `analyze_top_pairs()` in `research/pair_analysis.py`).
2. Backtest evaluates **only the following 7-day holdout week** — pass
   `BATCH_LOOKBACK_DAYS=22` env var to `nautilus/run_backtest.py` (15-day
   `MIN_BARS` warm-up + 7-day holdout, not carved out of it).
3. Only pairs that pass selection on the earlier window AND perform well on
   the holdout week are candidates for live trading.

This is not wired into a single script yet — it was run manually via
scratchpad scripts (see "Scratchpad artifacts" below). One fold has been run.
One fold is not enough to draw statistical conclusions from; if you want more
confidence before rotating pairs again, run another fold (advance the anchor
by a week, repeat).

Reusable pieces already in the codebase:
- `analyze_top_pairs(..., end_date: str | None = None)` in
  `research/pair_analysis.py` — pass an ISO date string to anchor selection
  to a past "now".
- `BATCH_LOOKBACK_DAYS` env var in `nautilus/run_backtest.py`.
- `BATCH_TICKER_A` / `BATCH_TICKER_B` env vars in `nautilus/run_backtest.py`
  — lets a driver script backtest many pairs without editing the file per run.

`research/run_all.py` does **not** do walk-forward — it calls
`analyze_top_pairs(days=30)` with no `end_date`, so it's a full-sample scan
anchored to today. Correct for "what looks tradeable right now"; not
equivalent to the walk-forward selection above. Takes ~15-20 min per run
(`candidate_pool=10000`, `top_n=140`).

## Why threshold = 0.01, not 0.05

With ~35,778 pairs tested weekly at p<0.05, ~5% (~27) false positives are
expected by chance alone. We were observing ~94 passes — real signal, but
diluted by noise. Tightening to 0.01 was an explicit, deliberate choice this
week, not a default. It's a blunt instrument, not a rigorous correction (a
proper Benjamini-Hochberg FDR correction was discussed as the "principled"
version of this but not built — see Known gaps / explicitly deferred).

Also tested and found **negative/inconclusive**, so don't re-litigate without
new data:
- Return-correlation and funding-rate-correlation as leading indicators of
  next-week cointegration — both negative, no predictive power found.
- "Does passing cointegration this week predict tradeable behavior the next
  3-4 days" — mostly negative at p<0.05, weak/inconclusive improvement at
  p<0.01.

## Known gaps / explicitly deferred (do not fix unless asked)

- **MIN_BARS cold-start gap on the cloud VM** — worked around, not patched at
  the root. `DataObserver` needs 720 bars (`MIN_BARS`, 15 days of 30-min
  bars) before the strategy will evaluate any entry signal, and it issues
  exactly one historical-backfill request to OKX on cold start with no
  pagination. That request caps at 300 candles, so a pair with no local
  cache gets stuck ~420 bars short and would otherwise sit for ~8 days
  accumulating the rest one bar at a time from the live feed before it could
  ever fire a trade. Discovered 2026-08-17 on GALA/UMA (almost a day live,
  zero trades, `bars_a` growing by exactly 1 per 30 min — the tell). Full
  incident writeup in `docs/CLOUD_DEPLOY.md`. **Now handled automatically**:
  `scripts/check_vm.sh switch` merges the laptop's full local canonical
  history (`scripts/merge_bar_history.py`) into the VM's `paper_live` cache
  as part of every pair switch, so this shouldn't recur — but the underlying
  300-candle cap / no-pagination behavior in `nautilus/data_cache.py` is
  still there. If a ticker has no local canonical feather on the laptop
  either (not every ticker is guaranteed downloaded), the merge script warns
  and skips it, and the ~8-day gap would apply for real.
- Nautilus quantity-rounding bug: `ValueError: ... was rounded to zero due to
  size increment 0.1` — hits low-unit-price tokens (IOST, HMSTR pairs).
  Unfixed.
- FLOKI pairs showed exactly 0 trades in the 69-pair batch backtest — flagged,
  not investigated.
- SATS ticker silently fails to download despite being live on OKX — flagged,
  not investigated (1 of 269 whitelist tickers).
- `autolag='aic'` costs 125ms/call vs `autolag=None, maxlag=1` at 1.15ms in
  the cointegration test — user said explicitly to hold off on this change.
  Still at the slow default everywhere.
- Multiprocessing for the pair scan: measured directly, it's SLOWER than
  sequential once the per-call cost is this cheap (process-spawn overhead
  dominates). Don't parallelize the scan.
- Root cause of an earlier ledger CSV corruption incident (merged rows via a
  stray quote character) was never conclusively identified. Recovered from,
  not prevented — if the live process crashes again with a `ParserError` on
  `paper_trades.csv`, that's the likely recurrence.
- Live execution mode (`EXECUTION_MODE="live"` in `run_trading.py`) is not
  implemented — `PairsTradingActor._execute_leg` raises `NotImplementedError`
  if selected. Paper only for now.

## Operating model reminders

- **One pair, one process — now on the cloud VM, not the laptop.** To switch
  pairs: check for an open position first (`tail` the ledger — now at
  `~/Pair_Trading/trading_data/paper_trades.csv` on the VM, not
  `research/paper_trades.csv` locally), edit `TICKER_A`/`TICKER_B` (+
  `LAST_SELECTED_DATE`/`LAST_SELECTED_STATS`) in `nautilus/run_trading.py`,
  `scp` it to the VM, `docker compose -f docker-compose.trading.yml up -d
  --build` to rebuild and restart, verify the "Ledger read: no unresolved
  open position" line in `docker logs pairs-trading`. Full commands in
  `docs/CLOUD_DEPLOY.md`.
- `scripts/update_data.sh` + the `com.pairtrading.update-data` LaunchAgent
  refresh OHLCV data every 12 hours automatically — no manual action needed
  for data freshness.
- `user_data/config.json`'s `pair_whitelist` (269 tickers, genuine-crypto-only
  via OKX's `instCategory` field, BTC/ETH/peg-excluded) is the universe that
  feeds both the scheduled downloads and the pair scan.

## Scratchpad artifacts (not permanent, session-specific tmp dir)

These implement the one walk-forward fold that's been run so far. They're
disposable/reference — if you want to run another fold, either reuse the
pattern or promote it into a real script under `scripts/`:
- `walkforward_select.py` — selection with `end_date = today - 7 days`.
- `walkforward_backtest.py` — holdout-week backtest of the selected pairs,
  writes `research/walkforward_backtest_results.csv`.
- `relationship_age_profile.py` — full 8-window pass/fail history per pair.

`scripts/batch_backtest.py` (permanent, in-repo) is the **non**-walk-forward
batch backtest — same-window screening and evaluation, useful for "what looks
good right now" but not for forward-looking confidence.

## Open questions the user has not yet decided

Don't act on these without being asked — they're live discussion threads, not
tasks:
- Whether/when to run a second walk-forward fold for more statistical
  confidence before the next pair rotation.
- Whether to build the FDR correction as a more principled replacement for
  the flat 0.01 threshold.
- Whether to move toward multi-pair portfolio diversification instead of the
  current single-pair rotation model.
