# HL-PROFIT1: a $1,000 cross-margin account trading the logistic model's live picks (brief, rewritten 2026-11-08)

Planner: Research Partner. Builder: Code Builder. Checker: Code Checker (names change: `ListAgents`).
Results to NUMBERS.md `[HL-PROFIT1]`. Read CLAUDE.md, docs/PLANNER_HANDOFF.md section 3 and this brief first.
This replaces the earlier per-trade brief (P1/P2 and the P2 ruling). Decided by the user 2026-11-08: go straight to
the portfolio simulation; no no-model baseline; per-trade and EV tables come out of the simulation's trade log.
The S1 gate stays FAIL and the vault stays locked. Plan order after this: confirm on the vault or live paper trading.

## Picks and probabilities (no refit of S1)
- Picks: S1-F Rule A on the RAW p_10h (pick if p_10h >= the top-q% quantile of the previous test block's p_10h),
  q = 1%, 0.5%, 0.1%, test folds 1-7, from `research/model/logs/s1/fold*_test_predictions.csv`. Assert per-fold n
  against `s1g_report.json` g7 cutoff_table (as S1-H does).
- p_cal: S1-H's isotonic 10 h correction, rebuilt with S1-H's own functions and look-ahead guard (S1-H saved only a
  JSON report, not per-event p_cal). Assert the pooled top-1% mean p_cal equals S1-H's reported 67.9%.
- Event geometry from v1: t0, ticker_a, ticker_b, beta, alpha, mu, sigma, z. Entry is the 1-minute close at
  entry_time + 29 (path minute m = 0), as in master_labels.py `paths_for`.

## Prices, funding, spread (all already held; no new data)
- 1-minute closes per coin: the series master_labels.py uses (`envelope.load_1m_series`). NOT user_data/normalized
  (that is 30-minute).
- Funding and impact bid/ask: asset_ctxs (`master_ctx_ingest.py`, S3 read-only, only the columns needed).

## CONFIG (one block at the top of the script; every value a setting, nothing hard-coded below it)
| setting | first run |
|---|---|
| start_equity | 1000 (USD) |
| margin_frac | 0.05 (initial margin per position = 5% of current account value at entry) |
| leverage_cap | 10 |
| leverage rule | lev = min(leverage_cap, max_leverage of coin A, max_leverage of coin B) |
| max_open | 10 positions in total; no per-coin limit (same coin or same pair twice is allowed) |
| margin_mode | cross (one pool) |
| fee_taker, fee_maker | 0.00045, 0.00015 per fill (Hyperliquid base tier, user 2026-11-08) |
| fee_mode | taker / maker (both run) |
| slippage_spread_share | 0.0 (user 2026-11-09: legs are small; 0.5 = half the impact spread per fill, the earlier rule) |
| funding | on |
| min_order_usd | 10 per leg |
| q | 1%, 0.5%, 0.1% |
| stop_sigma | 0.5, 1, 2, none |
Runs: 3 q x 4 stops x 2 fee modes = 24, each one continuous account over folds 1-7 starting at start_equity.

## Account rules (applied on 1-minute closes)
- **Size:** notional N = margin_frac x account value x lev. Legs 1 : |beta|: leg A = N / (1 + |beta|), leg B =
  N |beta| / (1 + |beta|), directions from sign(z) and sign(beta). If either leg < min_order_usd: skip, count it.
- **Entry:** a pick is taken if fewer than max_open positions are open and free collateral covers its initial
  margin. Several picks at the same minute: highest p_cal first. Skipped picks are counted by reason (book full,
  margin, min order).
- **Exit:** first minute with move >= |z| (mu), move <= -stop (stop), or minute 600 (time-out), as labels define
  move. Exit at that minute's close.
- **Costs:** fee on each leg's notional at entry and at exit. Slippage: half the impact spread at the fill minute
  (fallback: the coin's median over the previous 30 days; count the fallback fills). Funding: each leg pays or
  receives the hourly rate x its notional at each funding stamp while open (longs pay positive funding).
- **Cross margin and liquidation:** account value = cash + unrealised P&L of all open legs. Maintenance margin per
  leg = notional / (2 x that coin's max_leverage) (Hyperliquid rule). If account value < sum of maintenance margins
  at a minute close: close every open position at that close with taker fees and slippage, log a liquidation event.
  If account value then falls below what one minimum position needs, stop the run and report the date.
- **Missing minutes:** carry the last close for marking; no exit or liquidation fires on a missing minute; count them.

## Report (generator script writes the NUMBERS section; every number printed by the script)
Per run (24):
- Final equity, total return, CAGR, equity curve (one plain matplotlib PNG per q, all stops on it).
- Daily P&L: mean, median, share of positive days, worst day, best day; monthly P&L table (folds 1-7).
- Max drawdown (USD and %), its start, bottom and recovery dates, longest time under water.
- Sharpe and Sortino on daily returns (zero-trade days counted).
- Trades: n taken, n skipped by reason, win rate (exit at mu), stop share, time-out share, mean/median net USD and
  net return on margin, mean win, mean loss, profit factor, mean holding minutes.
- Costs: total fees, slippage, funding paid and received, each as USD and as a share of gross P&L.
- Leverage and risk: liquidation events (date, positions closed, loss), peak margin use, minimum distance to
  liquidation per day (account value / maintenance margin), mean and max open positions.
- Splits: by month, by coin (top and bottom 10 by P&L), by pair, by stop, by fee mode, by q.
- EV check (stop = none only; p_cal is P(reach mu), not P(reach mu before a stop)): EV per trade = p_cal x
  mean net(reached) + (1 - p_cal) x mean net(not reached), means fitted on EARLIER test months only with the
  t0 + 10 h guard; 5 EV quintiles: mean EV against realised mean net.
- Trade log: one parquet per run (every trade, every cost, every skip), under research/model/logs/profit1/.

## Known gaps (state them; do not model them)
- max_leverage is today's snapshot (hindsight); limits were different in the past.
- Liquidation is checked on 1-minute closes; a move inside a minute can liquidate earlier.
- Maker fills are assumed to fill; in practice they may not.
- Slippage is set to zero by the user's choice (small legs): costs are a lower bound, so results are an upper bound (optimistic).
- The test months were already used for the cut-off, the deep dive and the calibration: results are optimistic
  until the vault or paper-trading check.

## Process
One script. Send it and this rule list to the checker before running. Then the log, the NUMBERS section and the
diff. Stop and report to the planner with the checker's verdict. No vault. No refit of S1. AWS launches and local
deletes need the user's own yes in the builder's session.
