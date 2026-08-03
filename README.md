# Pair Trading

Statistical-arbitrage research for crypto perpetual futures (OKX), built around an
Ornstein-Uhlenbeck (OU) model fitted to the log-price spread between two cointegrated
assets. Includes a cointegration screener, a gated entry/exit signal generator, an
OU-based position sizer, and a [Nautilus Trader](https://nautilustrader.io/) backtest
integration.

This is an active research project, not a production trading system. See
[CODEBASE_AUDIT.md](CODEBASE_AUDIT.md) for a detailed, evidence-based breakdown of
what works, what's tested, and what's currently broken.

## How it works

1. **Screen for pairs** — `research/pair_analysis.py` runs Engle-Granger cointegration
   tests across all pairwise combinations of a ticker universe, then ranks candidates
   by half-life, Hurst exponent, cointegration stability, and hedge-ratio stability.
2. **Fit the spread** — `research/ou_model.py` fits an OU process
   (`dS = -theta*(S - mu)*dt + sigma*dW`) to the spread of a candidate pair via OLS,
   with residual diagnostics (Jarque-Bera, Ljung-Box, theta significance) to validate
   the fit.
3. **Generate signals** — `research/signal_generator.py` applies six sequential gates
   (cointegration, OU-fit validity, minimum deviation, theta significance, volatility
   regime, reversion probability) before firing an entry signal, and three ordered exit
   gates (time stop, adverse move, take profit).
4. **Size the position** — `research/position_sizer.py` sizes both legs so a
   `stop_sigma`-unit adverse move costs exactly a fixed fraction of capital, using the
   OU stationary distribution as the risk unit.
5. **Backtest** — `nautilus/pairs_strategy.py` wires the above into a Nautilus Trader
   `Strategy`, and `nautilus/run_backtest.py` auto-selects the top-ranked tradeable
   futures/futures pair (via `pair_analysis.py`) and drives it against historical
   30m OHLCV bars.
6. **Diagnose** — `diagnostics/*.py` are forensic, read-only scripts written to test
   specific hypotheses against backtest output (e.g. confirming a Nautilus Trader
   order-routing bug, checking spread-path reconstruction fidelity, and probing whether
   rolling OU parameters could serve as an early-exit signal).

## Repository layout

```
research/          Core model: data loading, cointegration screening, OU fitting,
                    signal generation, position sizing, and manual validation scripts.
nautilus/           Nautilus Trader strategy + backtest harness.
diagnostics/        Forensic, read-only scripts investigating specific backtest findings.
user_data/          Freqtrade scaffold, used mainly to download OHLCV data via
                    `freqtrade download-data`. Not wired to the OU strategy.
```

## Setup

No dependency manifest is checked in yet. The known runtime dependencies are:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install numpy pandas scipy statsmodels ccxt nautilus_trader
```

Freqtrade itself runs via the Docker image referenced in `docker-compose.yml` — it is
only used to pull market data into `user_data/data/`, not to run the OU strategy.

Copy `user_data/config.json` from your own Freqtrade setup (or generate one with
`freqtrade new-config`) and fill in exchange credentials; this file is gitignored and
never committed.

## Usage

```bash
# Screen the configured ticker universe for cointegrated, tradeable pairs
python research/pair_analysis.py

# Fit and sanity-check the OU model / signal gates / position sizer
python research/validate_ou_analytics.py
python research/validate_ou_diagnostics.py
python research/validate_signal_generator.py
python research/validate_exit_signal.py
python research/validate_position_sizer.py

# Backtest a specific pair via Nautilus Trader
python nautilus/run_backtest.py
```

Note: `research/run_all.py` is out of sync with `pair_analysis.py`'s current API —
tracked as a known issue in [CODEBASE_AUDIT.md](CODEBASE_AUDIT.md).
`nautilus/run_backtest.py` was also broken (hardcoded to a pair and a timeframe no
longer on disk) but was fixed in Step 7 — see below.

## Status

The Nautilus backtest was revived in Step 7: it now auto-selects a pair instead of
hardcoding AVAX/LINK, runs on 30m bars (matching the current data pipeline) instead
of missing 1h files, and fixes a unit bug where the OU model's mean-reversion speed
was silently off by ~2x at non-hourly bar sizes. Position sizing supports two modes
— a fixed risk-budget-per-trade mode (Step 5's original design) and a
leverage-target mode added in Step 7, where a per-trade capital budget is scaled by
an explicit leverage multiple and split across both legs by the hedge ratio. See
[research/markdowns/STEP7_SUMMARY.md](research/markdowns/STEP7_SUMMARY.md) for the
full account of what changed and why.

The strategy has now been backtested on multiple pairs/configurations, most recently
SNX/WLD over a single 30-day window (7 completed trades). Results remain directional
only — not enough trades to draw statistical conclusions, the current take-profit/stop
configuration has a structural reward:risk asymmetry that hasn't been addressed yet,
and the backtest still does not model forced liquidation, so results at higher
leverage are optimistic relative to what a real exchange would allow (see
STEP7_SUMMARY.md's "Known open gap"). The original AVAX/LINK run (6 trades, net -8.46
USDT) is preserved in
[research/markdowns/STEP6_SUMMARY.md](research/markdowns/STEP6_SUMMARY.md).

## License

No license file is currently included.
