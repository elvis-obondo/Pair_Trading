# Pair Trading

Statistical arbitrage on OKX perpetual futures. The system watches 22,366 pairs drawn
from 212 instruments, takes positions when a spread stretches three standard deviations
from its seven-day mean, and holds up to ten at once.

It is a paper system. **No orders are submitted anywhere in this repository.**

## The strategy, in full

Everything below is settled and measured. Nothing here is a placeholder.

| | |
|---|---|
| spread | `log(A) − β·log(B) − α`, β and α from a **7-day rolling** OLS, frozen at entry |
| entry | \|z\| ≥ **3.0** rolling sigma from the rolling mean |
| stop | **0.5 sigma beyond the entry spread** — a distance travelled, not a fixed level |
| take profit | full reversion to mu |
| time stop | 72 hours |
| ranking | OU theta, fastest reverter first; unranked candidates sort last but are kept |
| sizing | `gross = 20x leverage × 5% of equity`, capped at $5,000 notional |
| book | 10 concurrent positions, one per pair, margin ≤ equity |

**There are no entry gates.** There used to be six. All 31 combinations of the five
boolean ones were scored at a 3-sigma entry: no combination beats no gates, and 25 of
the 31 collapse the account to 6–14% of starting equity. They raise the win rate from
15.7% to 21.6% and lose money anyway, by filtering out the rare large winners the edge
depends on. The cointegration gate is among the ones that hurt.

**Theta ranks, it does not filter.** On the two-year panel only 40.8% of 3-sigma
candidates fit a positive theta, so declining the rest would silently discard nearly
six candidates in ten.

## The finding that shapes the whole system

Across 12,597 trades in three independent six-month windows, **0 of 9,704 stop-outs
filled at or inside the stop**. Median overshoot 1.53x, mean 2.07x, p90 3.26x. That
costs 0.83R per trade and turns a +0.74R edge into −0.083R.

It is not the stop width — sweeping 0.5σ to 2.5σ moves mean R from −0.201 to −0.024 and
converges on zero without crossing it. It is how often the stop is checked. The spread
moves a median 0.11σ per 30-minute bar and 5.3% of single bars clear the whole stop
distance alone.

No exchange can fix it: the stop is on a synthetic across two instruments, and no venue
has an order type that watches one. Per-leg stops are worse, because one firing leaves
the other naked. So it is a monitoring problem, and `research/stop_monitor.py` is the
answer to it.

## How it runs

Two processes, and the split is deliberate.

**`research/live_scanner.py`** — single-shot, every 30 minutes. Refreshes 30m candles,
screens 22,366 pairs, writes `scanner_candidates.json` and appends `scan_history/`.
It holds no positions and never writes the book. A process that starts, does one cycle
and exits cannot leak.

**`research/stop_monitor.py`** — long-lived. Subscribes to the OKX tickers websocket for
the instruments it cares about and re-checks every open position's stop on every quote.
Owns the book: opening, closing, sizing, the state file and the ledger. It is the only
writer of `scanner_trades.csv`, which is what keeps two processes from corrupting one
ledger.

Checking the stop is cheap because the level is fully determined at entry — two logs, a
multiply, a subtract, a compare. No panel, no rolling window, no OU fit.

```bash
scripts/run_scanner.sh                    # one scan cycle
scripts/run_stop_monitor.sh --dry-run     # watch the book, book nothing
scripts/check_vm.sh status                # what the cloud VM is doing
scripts/check_vm.sh overshoot             # the number this is all about
```

### Where each half runs

Because the monitor is the sole writer of the book, the scanner can live on a
different machine — it only produces a file.

**Micro (default, free).** The monitor runs on a 1GB GCP e2-micro; the scanner
stays on the laptop and ships `scanner_candidates.json` over after each cycle.
The stop is watched 24/7 whether the laptop is up or not. While the laptop
sleeps no new candidates arrive, so nothing new *opens* — positions already open
keep being watched, and the monitor's 60-minute staleness guard handles it with
no configuration.

**Full.** Both halves on an e2-medium, so entries continue with the laptop
closed. The scanner needs 531MB peak plus a freqtrade download and does not fit
on the micro.

```bash
scripts/vm_migrate.sh          # micro
scripts/vm_migrate.sh full     # resize and move both halves
scripts/vm_migrate.sh status   # read-only
```

Measured 2026-09-12: scanner 531MB peak RSS, monitor 174MB, VM OS+docker 258MB.

### What grows, and what deletes it

| | rate | retention |
|---|---|---|
| `monitor_ticks/` | 18.5 MB/day | 14 days → 259 MB |
| `scan_history/` | ~1-2 MB/day | 90 days |
| logs | ~1 MB/day | rotate at 32 MB |
| 30m candle data | 63 MB/year | left alone |
| Docker layers | GBs per rebuild | `vm_housekeeping.sh`, daily |

The ledger is never pruned. It is the record of what the account did, equity is
re-summed from it on every start, and it is small.

## Repository layout

```
research/            Everything. Model, scanner, book, monitor, and the
                     hand-run validators.
  rolling_spread.py    the one definition of the 7-day geometry
  scanner.py           z-screen across the universe, theta-ranked
  portfolio.py         ten slots, margin bounded by equity
  position_sizer.py    gross = leverage x capital_frac x equity
  signal_generator.py  entry and exit, measured in rolling sigma
  book_state.py        the settled config, and the only state IO
  live_scanner.py      one scan cycle
  stop_monitor.py      the tick-speed stop
  validate_*.py        PASS/FAIL scripts, run by hand (not pytest)
user_data/           Freqtrade scaffold, used only to download OHLCV.
scripts/             Runners, the LaunchAgents, and the VM helpers.
docs/                Handoffs and the cloud deployment record.
```

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Freqtrade runs via `docker-compose.yml` and is used only to pull market data into
`user_data/data/`. Copy `user_data/config.json` from your own Freqtrade setup; it is
gitignored and never committed.

## Validating

Repo convention is hand-run PASS/FAIL scripts, not pytest.

```bash
for v in rolling_spread position_sizer signal_generator exit_signal \
         portfolio scanner universe_panel backtest_screen \
         live_scanner stop_monitor; do
  python research/validate_$v.py
done
```

`research/validate_stop_monitor.py` section 5 is the one that matters: it asserts that
an exact-touch price path books an overshoot of ~1.0x against the 1.53x median the
30-minute check produced.

## What this is not

It does not submit orders. `StopMonitor._submit_close` is a stub, and wiring it needs
API keys, a kill switch, and an answer to one leg filling while the other does not.

It does not model forced liquidation.

The equity curves it produces compound, and the compounded multiple is **not** a result
worth quoting — percentage-of-equity sizing grows notional until a position exceeds the
depth of the pair it trades. Report per-trade `net_pct` and `R`; both are immune to
compounding.

## License

No license file is currently included.
