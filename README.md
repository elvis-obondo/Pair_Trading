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
   `Strategy`, and `nautilus/run_backtest.py` drives it against historical OHLCV bars.
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

Note: `nautilus/run_backtest.py` currently expects 1h feather files that aren't
present in this repo's data layout, and `research/run_all.py` is out of sync with
`pair_analysis.py`'s current API — both are tracked as known issues in
[CODEBASE_AUDIT.md](CODEBASE_AUDIT.md).

## Status

The strategy has been backtested on a single pair (AVAX/LINK) over a single 30-day
window: 6 completed trades, net -8.46 USDT. See
[research/markdowns/STEP6_SUMMARY.md](research/markdowns/STEP6_SUMMARY.md) for the
full run and the diagnostic fixes (minimum-deviation gate, reversion-time correction)
that produced it. Results are directional only — not enough trades to draw statistical
conclusions, and the current take-profit/stop configuration has a structural
reward:risk asymmetry that hasn't been addressed yet.

## License

No license file is currently included.
