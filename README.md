# Pair Trading

Research into pair-spread mean reversion on Hyperliquid perpetual futures.

It is research code. **No orders are submitted anywhere in this repository.**

## The question

When the spread between two coins stretches far from its recent mean, can we tell
which of those dislocations will revert to the mean within 10 hours, better than
chance from where they start? And can that be traded at a profit after costs?

## Where it stands

- **Dataset (HL-MASTER1 v1, frozen 2026-10-26).** Every dislocation event across the
  Hyperliquid universe, with price, order-book, funding, open-interest and
  wallet-flow features. Built from 1-minute prices and Hyperliquid's own archives.
- **Model (HL-MODEL1, S1).** A penalised logistic model, fitted on a rolling
  walk-forward with a held-out vault. Its ranking of which events revert is real
  and holds at order-book midpoint prices.
- **Costs (HL-COSTS1, 2026-11-18).** Every costed configuration lost money. The
  earlier backtest priced trades at last-trade closes, which sit favourably against
  the book midpoint in thin coins. Once fees and the bid-ask spread are paid, the
  edge is gone.
- **Now (HL-TARGET2).** Retraining on a money target: net basis points per trade at
  midpoint prices, after taker fees, half-spread and funding. The labels are built;
  the next step checks how many test-month trades make money after costs, and
  whether they can be spotted before entry.

Every figure behind these statements is printed by a script and recorded in
`research/dislocation_model/NUMBERS.md`, with the script and log named beside it.

## Repository layout

```
research/
  dataset/            HL-MASTER1 dataset build, tests, dictionary and receipts
  hyperliquid/        Hyperliquid data pulls (prices, order book, flows, OI)
  dislocation_model/  event definition, features, NUMBERS.md
  model/              model fits, backtests, cost studies, label builds
    diagnostics/      one script per check, each with its own log
  adapters/           exchange and data adapters
docs/
  HYPERLIQUID_HANDOFF.md   master plan and dated decisions log
  prompts/                 briefs for each research step
scripts/              cloud provisioning and run helpers
```

Large data (the dataset, cleaned prices, labels, model outputs) lives in cloud
storage, not in git.

## How the work is run

- Each step has a written brief in `docs/prompts/` with its decision rules fixed
  before results are seen.
- Every step's code is reviewed before it runs and its results are reviewed before
  they are reported.
- Models are fitted on a rolling walk-forward, never a shuffle. The vault months are
  scored once, at the end.

## Earlier work

The project began as a paper trading system on OKX perpetuals (7-day rolling spreads,
3-sigma entries, a tick-speed stop monitor). It found that direction was not
predictable, volatility was, and stop fills overshot badly on a two-leg synthetic.
That code has been retired and is in the git history.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## License

No license file is currently included.
