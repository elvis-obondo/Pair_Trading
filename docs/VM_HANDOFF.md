# The paper system on the VM — state as of 2026-09-21

Everything runs on GCP. The laptop is not required and can stay off.

## What is running, where

| | |
|---|---|
| Instance | `pairs-trading`, us-central1-a, **e2-medium** (2 vCPU, 3.9GB, 2GB swap) |
| Monitor | `pairs-stop-monitor` container, `restart: unless-stopped`, always up |
| Scanner | host cron `*/30`, `scripts/vm_scan_cycle.sh` |
| Housekeeping | host cron `15 4 * * *`, `scripts/vm_housekeeping.sh` |
| Laptop | LaunchAgents `com.pairtrading.scanner` and `.update-data` **unloaded** |

Resized from e2-micro on 2026-09-13 03:38. That ended the free tier.

**Free trial: 63 days left from 2026-09-13, $300 unused.** e2-medium is ~$25/month,
so ~$52 over the trial. **At trial end Google SUSPENDS resources, it does not
throttle** — decide before ~2026-11-08 whether to upgrade to paid or go back to
micro mode (`scripts/vm_migrate.sh micro`). Do not let it lapse with a book open.

GCP account: **elvisodangaobondo@gmail.com** (not elvisobondo31, which is the git
identity). Project `project-0671be06-e22a-44d8-83c`.

## Checking on it

```
scripts/check_vm.sh positions    # live book, marked to the monitor's own quotes
scripts/check_vm.sh overshoot    # THE number
scripts/check_vm.sh ledger [N]
scripts/check_vm.sh scanner [N]  # cron cycle log
scripts/check_vm.sh status       # instance, containers, memory, disk
scripts/check_vm.sh pull         # copy the ledger down
```

Deploy is always: build on the laptop, push to Artifact Registry, VM pulls.
`./scripts/release.sh`. **The VM never builds.**

## The result so far

The build exists to fix one thing: across 12,597 backtested trades, **0 of 9,704
stop-outs filled at or inside the 0.5σ stop** — median overshoot 1.53x, mean 2.07x,
p90 3.26x. That costs 0.83R and turns a +0.74R edge into −0.083R. Cause was
checking the stop only at 30-minute bar closes.

Live, watching every tick over the OKX `tickers` websocket, **13 stop-outs**:

```
median 1.042x   mean 1.075x   worst 1.402x
confirm delays 100-255ms
```

Twelve of thirteen landed between 1.002x and 1.128x. **The mechanism works.**

### The open question — trade #22

#22 VANA/WET closed at **1.402x**, the only bad one, and it lived entirely inside
the migration window: opened 03:45:06 (4s after the resize restart), container
restarted again 03:48:03, freqtrade download saturating both vCPUs 03:49–04:02,
closed 03:57:06.

The ledger does **not** corroborate a feed problem: `blind_gap_seconds=0`,
`feed_state=live`, `confirm_delay 138ms` — indistinguishable from the clean ones.

Two readings, not separable on one trade:
- **CPU contention.** The staleness guard measures quote age at evaluation time,
  so a tick queued behind a busy CPU still looks fresh when finally read. The stop
  would fire late with nothing marked.
- **VANA/WET just gapped.** 5.3% of single 30m bars clear the whole stop distance.

**The test is free and already running.** The scanner downloads every 30 minutes
forever. If contention delays exits, overshoots inside download windows will run
systematically higher than outside them. `closed_at` is in the ledger and the cron
schedule is known — it is a groupby in a week. If real, fix is cheap (`nice` the
download, or pin the monitor to a core).

### Unmeasured: how long a non-first download takes

The first was **12m58s** for 212 tickers (1447 candles each). Later runs are
incremental — 1-2 new candles — so the payload collapses, but the request count
does not: 212 tickers x 3 series (30m futures, 1h mark, 1h funding) is ~636 calls
regardless. Expect request-bound, not bytes-bound. **Not yet measured.** First cron
cycle was due 04:30. Check `logs/cron.log` for `scan cycle start`/`done` pairs.

This matters because it sets the CPU-contention duty cycle, which is the #22
hypothesis above.

## Bugs found and fixed this session

All four were live, all four are committed with regression tests.

**Equity reset by restart** (`e54e2ef`). `load_portfolio` re-summed equity from the
ledger but left `starting_equity` at 300 and `pf.closed` empty. `_close` recomputes
as `starting_equity + sum(closed)`, so the first close after ANY restart erased
every prior loss. Live: 7 closes totalling −20.31 reported equity 290.93 instead of
279.69. Equity drifted UP across restarts and size is a function of equity.

**Ledger corrupted by a schema change** (`a1a3e38`). Adding 3 columns made every
append 39 fields wide under the 36-field header already on disk. pandas refuses to
parse it at all — `Expected 36 fields in line 26, saw 39` — and the monitor
crash-looped on restart, unable to load the book. Surfaced only when the VM
rebooted. Repaired in place; corrupt copy at `trading_data/scanner_trades.csv.corrupt36.bak`
and `research/backups/`. `migrate_ledger_schema()` now rewrites onto the current
schema before any append and before any load, via a temp file. Columns dropped
from the schema are KEPT — a ledger is history.

**`_exec_spread` leg B sign** (`85378a1`). Used `+direction * leg_b_notional`;
exposure to B is `-direction * leg_b_notional`. Picked the wrong side of book on
every exit. Diagnostic column only, no fill used it — but `exec_spread_at_exit`
values recorded before this are wrong.

**MAX_PER_TICKER** (`a5fa43f`). Was None; every measured result used 1. First live
book filled with BERA in 4 of 10 slots. Now 1.

## THE STRATEGIC FINDING — it is not market neutral

Raised by the user after seeing AGLD/DOT sized $290 vs $9.78.

The strategy is **beta-hedged, not dollar-neutral**. Net dollar exposure of one
position is `(1 - beta) / (1 + |beta|)` of gross:

- beta = +1 → net 0, genuinely neutral
- beta = 0 → net 100%, a naked single-coin bet
- beta = −1 → net 100% with **both legs the same way**; not a hedge, a doubling

Measured over 3.6M candidate observations in `exit_sweep_paths.parquet`:

| | |
|---|---|
| beta in [0.8, 1.2] (properly hedged) | **18.4%** |
| beta < 0 (both legs same side) | **17.4%** |
| median position net/gross | **34.6%** |
| over 90% directional | **20.2%** |

And in the 79-trade 10-slot portfolio backtest, book-level net exposure ran a
**median +54.9%**, p90 +82.1%, over 50% directional **57.7% of the time**, peaking
at **+$2,694 net on a $300 account — 9x equity, one-way long.**

The screen is `|z| >= 3` and nothing else. No cointegration test, no beta bound, no
fit quality. At beta ≈ 0 the spread `log(A) − beta·log(B) − alpha` collapses to
`log(A) − constant`: a bet on one coin reverting to its own 7-day mean. Different
strategy, untested.

**Argues against panic:** low-beta trades do NOT stop out more often — 58.5%
take-profit rate at |beta| < 0.10 vs 55.5% at 0.75–1.5. This is not currently
costing P&L. But the backtest window was a chop; directional exposure costs nothing
in a chop and everything in a trend.

### What was done about it — instrumentation, not a filter

Deliberately recorded, NOT gated. Adding a filter changes which trades the strategy
takes and nothing has measured that.

- `rolling_r2` in `rolling_spread.py`; `r2_at_entry` on every signal. Kept out of
  `last_bar`'s finite check so a NaN R² can never silently decline a trade.
- `Position.exposure` / `.net_exposure` / `.net_exposure_frac`, derived from the
  same algebra as `pnl()` and **tested against it at five betas** so they cannot
  drift apart.
- Ledger columns `r2_at_entry`, `net_exposure`, `net_exposure_frac` on open and
  close rows.

**In a week, ask the ledger:** do low-R² trades lose more? Do directional days cost
money? Then pick one of:

1. **Cap beta** to ~0.5–2.0. Costs ~60% of the pool.
2. **Cap book net exposure** — let the portfolio refuse a slot that pushes
   net/gross past a limit. Keeps the pool, adds a constraint the sizer lacks.
3. **Filter on R²**, not beta. beta near 1 with R² near 0 is the same problem in
   better clothes.

`r2_at_entry` is NaN on positions opened before 2026-09-13 04:00 — the column did
not exist yet. New entries carry it.

## Live positions view

`stop_monitor.positions_snapshot()` writes `trading_data/open_positions.json` every
heartbeat (10s), marked to **the monitor's own quotes** — never a fresh fetch. A
status view that prices itself can show green while the monitor is closing the
position. A blind position reports no mark at all rather than a stale number.

`scripts/check_vm.sh positions` renders it. `->stop` is progress toward the stop
level; negative means moving toward take-profit.

At 04:15: **7 up, 3 down, unrealized +35.27** on equity 270.14. The three losers
were −$0.31, −$0.19, −$0.08. #15 BERA/DOT at −472% (nearly 5 stop-distances the
right way), +$19.90, +4.66R.

## Validators — repo convention, hand-run, NOT pytest

```
validate_signal_generator  24/24      validate_scanner        18/18
validate_rolling_spread    19/19      validate_live_scanner   48/48
validate_portfolio         64/64      validate_stop_monitor   71/71
validate_position_sizer    44/44      validate_exit_signal    25/25
```

Run them all before any release. `validate_stop_monitor` redirects EVERY path in
`book_state` to a temp dir and asserts it is not the real one — an earlier version
redirected only `LEDGER_PATH` and wiped a live book of 10 positions.

## Settled spec — do not re-litigate

Entry `|z| >= 3.0` rolling sigma. Stop 0.5σ **beyond the entry spread** (a distance
travelled, not a level from mu). Take profit at full reversion to mu. 72h time stop.
Ranked by OU theta, NaN sorts last but is KEPT — theta is the ranking key, never a
gate. 10 slots, 1 per ticker. `gross = 20x leverage x 5% equity`, $5,000 notional cap.
7-day rolling OLS over 336 bars at 30m; `min_bars_required = 671`.

Two feeds, unrelated: **entries on 30-minute candles**, **exits on the websocket
tickers channel**, which is not candles at all. The stop level is frozen at entry,
so checking it is two logs, a multiply, a subtract and a compare.

Trigger on **mid**, not the executable side: beta/alpha were fitted on log closes,
so triggering on the crossable side would make the live stop systematically tighter
than the measured one. `exec_spread_at_exit` records the difference.

## Not built, on purpose

- **Live order submission.** `_submit_close` is a stub. Needs API keys, a kill
  switch, and an answer to one leg filling and the other not.
- **Historical 1-minute replay.** Tick capture at 1 Hz is accumulating in
  `trading_data/monitor_ticks/` (14-day retention) and will support it in a few weeks.

## Retention — everything scheduled is capped

Ticks 14 days (~18.5MB/day measured). Scan history 90 days. Logs rotate at 32MB via
`rotate_logs_in()`, which covers every `*.log` — an earlier hardcoded list of 3
files missed the cron/LaunchAgent stdout duplicates. **The ledger is never pruned.**

VM after migration: 9.3GB of 20GB used, 397MB of 3,913MB RAM. No pressure.

## SESSION 2026-09-13 -> 09-21: what was settled, and the number that governs it

### THE NOISE FLOOR. Read this before trusting any comparison below.

`tradeable_pairs` returns `itertools.combinations`, so **which coin is called A
is arbitrary**, and everything downstream regresses the first on the second.
Randomise that choice and re-run: six books, identical data, rules and window.

    end equity   307  394  471  495  628  933     spread $626, sd $221
    alphabetical (what we run)  676      fully reversed  164

Only **56 of ~1000 trades** are common to the alphabetical and reversed arms.
Flipping does not re-scale a hedge on the same positions; it selects a different
strategy. `beta(A on B) x beta(B on A) = R^2` exactly, so the two directions
diverge as far as the fit is bad -- and they ALWAYS share a sign. **Flipping
cannot fix negative beta.**

**Anything under ~$626 on this window is a coin flip.** That retroactively voids
most single-parameter comparisons, including two this session reported as
measurements (cooldown $129, time stop $56).

**Matched-pair or nothing.** Comparing a config against a POOLED noise band is
not the same as comparing it against ITSELF under the same labelling.
`max_per_ticker=1` looked like the one winner at +$926 pooled; matched-pair it
goes +926, -39, +645, -444 across four seeds. Two of four. It is noise.

### The exit rule is closed by exhaustion

450 combinations of stop width (0.5-5.0 sigma), debounce (0-30 min, fine below
15) and grace (0-120 min), at 1-minute resolution, honest fills. **Zero
profitable.** Best is 5 sigma at -0.031% -- and it liquidates 21.9% of the book.
Enforce margin and 51 of 450 survive, all 0.5 sigma, best -0.060%.

The mechanism, measured: winners breach the stop for a **median 4 minutes** and
recover; losers breach and keep going. You cannot tell them apart at the
crossing, and there are ~30 losers per winner rescued. No debounce length fixes
that ratio.

### THE $5,018 BACKTEST WAS COMPOUNDING, NOT EXECUTION

Both arms take the **identical 1,041 trades**, same 235 take-profits. Breakdown
of the $5,038 gap: stops **-$8,169**, take-profits **+$12,799**. The 1.04x arm
does WORSE on stops. It wins because a couple of dollars saved per early stop
keeps equity alive, and `gross = 20x * 5% * equity` compounds it: mean position
$161 vs $1,818, and **97.9x** by the last trade. The 235 take-profits earn
+9.208% in BOTH arms -- identical -- and $5.51 vs $59.98 in dollars.

Of 795 stop-outs, only **39** actually filled inside 1.04x. Median 1.63x, mean
2.40x, max 50x.

### The intrabar experiment: hypothesis CONFIRMED

Take-profit rate **22.5% -> 15.6%** at 1-minute checking. Median stop hold
collapses 2.00h -> 0.58h. **75 of the 235 take-profits (32%) crossed the 0.5
sigma stop while open** -- a tick monitor kills all of them. The +0.740R was
optimistic by roughly a third of its winners.

Note the design assumed "same entries, both arms". Wrong: 1,044 vs 1,977 trades.
Ten slots couple exits to entries. The take-profit RATE is the valid comparison;
their P&L is not.

### Fill quality vs how often you look (measured on 1m paths, 0.5 sigma)

    1 min 1.149x | 5 min 1.316x | 15 min 1.492x | 30 min 1.651x
    live tick monitor ~100ms: 1.005x median, 1.011x mean (14 stop-outs)

**Sub-minute watching is what buys the fill.** 1-minute checking with honest
fills LOSES (-$298) -- it pays the slow-fill penalty without the slow-trigger
leniency.

### What the live config measures at

    30m trigger + 1.04x fill   $5,018   <- impossible blend
    30m trigger + actual fill  $   51
    1m trigger + actual 1m     $    2
    1m trigger + 1.005x fill, stop 1.0  $805 (no cooldown) / $676 (cooldown 72h)

### SHIPPED THIS SESSION

**Re-entry cooldown, 72h, rolling** (`79766d5`). A pair that stopped out cannot
re-enter for 72h from its own losing close. Keyed on the SORTED pair. Restored
from the ledger on load -- without that a deploy would erase it, since a deploy
IS a restart. `recent_losses` is deliberately NOT `pf.closed`: filling `closed`
double-counts equity, which is bug `e54e2ef`.

**The engine measured it WORSE** ($676 vs $805) and the user shipped it anyway
knowing that. Both numbers are inside the noise band, so neither is meaningful.

**r2_at_entry was never reaching the ledger** (`1a6660d`). `try_open` rebuilds
the signal dict to re-anchor entry to the real fill, and r2 was never added to
it. The scanner computed it correctly all along. 28 of 28 opens read NaN. Fixed
with an explicit `is None` check -- NOT `or`, because `0.0 or nan` is nan and an
R^2 of exactly zero is the degenerate case the column exists to find. Now
populating: 162 of 205 opens.

**Cooldown skips now log one summary line per cycle.** A blocked entry leaves no
trade behind, so a rule doing nothing looked identical to one working.

### THE LIVE BOOK: -32%, and one day did it

    start 300  peak 329.57  trough 167.04  now 202.98  (+26.15 unrealised)
    195 closes, 8.6 days, mean R -0.045 vs backtest +0.221

    Sep 16  -117.48 on 44 trades   <- the CLARITY Act
    every other day between -31.86 and +25.34, seven of nine positive

**2026-09-16 is the US Senate rejecting the CLARITY Act 49-50 on cloture (Sep
15), plus a Fed rate hike.** Not a mechanism failure: mean R on that day's losers
was **-1.081** (normal), overshoot median **1.013x** (perfect), losses spread
across 17 hours. It was **44 trades instead of ~19 at a normal loss each**.

The book was net SHORT (-0.176 mean) and still lost. This was not directional --
it was **correlation breakdown**. One macro headline moves everything at once,
beta fitted on seven normal days stops applying, and spreads trend instead of
reverting. Three ARB pairs and two DASH pairs among the eight worst.

Against the backtest's own 195-close windows, -32.3% is the **3rd percentile**.
Bad tail, not impossible.

### THE NEXT THING TO TEST, and why

**A dislocation-count circuit breaker.** The vulnerability is that dislocation
COUNT spikes exactly when dislocations are least likely to revert -- the scanner
sees a target-rich environment and fills the book at the worst moment. No exit
parameter helps when 44 spreads trend at once.

There is prior work: commit `e5f494e` tested universe-wide dislocation count as a
trade/do-not-trade switch and found **trading only busy days takes ruin from 11%
to 4%, the lowest measured**, at 1.37x instead of 3.73x.

Test it matched-pair across seeds, on a window that INCLUDES Sep 16.

### Also open

- **Liquidation is not modelled.** 18 of 1,041 backtested trades lose more than
  the margin posted; worst **-$54.14 on $18.20**. ~$180 of a -$249 run. Needs a
  decision: isolated or cross margin. And the backtest margins the PAIR as one
  unit while OKX sees two positions with two liquidation prices.
- **r2 backfill is available and exact.** `scan_history/*.parquet` has
  `r2_at_entry` on all 8,743 rows; join to the ledger on (ticker_a, ticker_b,
  exact beta) matched **44 of 44**, and reproduced trade 44's value to the last
  digit. Decide: write it into the ledger (needs the monitor stopped, given the
  `a1a3e38` corruption history) or merge at analysis time.
- **1m data top-up running.** `download_1m.sh` keys on file EXISTENCE so it is a
  no-op once every ticker has a feather -- useless for topping up. Driven
  directly instead. Batches take 1-3 HOURS each under `config_slow.json`, not
  minutes. 30m is current.

### Entry gates: already tested, do not re-litigate

Commit `e5f494e`, all 31 combinations at 3 sigma: **no combination beats no
gates.** "Gates do raise the win rate -- 15.7% to 21.6% -- and lose money anyway,
which is the signature of filtering out the rare large winners the edge depends
on." The six gates in `entry_gates_dataset.py`'s docstring are STALE; current
`generate_entry_signal` takes only `min_deviation_sigma`, `take_profit_pct`,
`bar_hours`.

Every intervention tested this session has that same signature: wider stops took
the win rate to 58% and lost money; a debounce took take-profits 170 -> 309 and
lost money. **Raising the win rate by removing trades has failed every time.**

---

## IN FLIGHT as of 2026-09-13 09:20 UTC

**1-minute download running on the LAPTOP.** 212 pairs x 35 days, started 09:13.
OKX throttles hard -- roughly 1 pair/minute, so expect ~3-9 hours. `caffeinate`
is holding the laptop awake until it exits; closing the lid is fine, sleeping is
not. Progress: `grep -c "Downloaded data.*1m" /tmp/dl1m.log`.

It is only needed for the intrabar experiment. Nothing about the live book
depends on it -- that runs on the VM and is unaffected if the download dies.

### The intrabar experiment, and why

The backtest checks its stop at 30-minute bar closes. A position that crosses the
level intrabar and recovers before the close is NEVER stopped there -- it stays
open and can go on to take profit. The live monitor sees that crossing in ~100ms
and kills it.

So the backtest's 20% take-profit rate may be partly intrabar stop-outs in
disguise, and +0.740R may be optimistic. Evidence:

  - the backtest's FIRST closed trade of 4,438 was a take profit at 2.5h, with
    six more inside 21 hours
  - the first live book went 19 for 19 on stops in 5.5h -- about 1% likely if the
    true stop rate is 76%
  - backtest median stop hold 2.0h with a 0.5h FLOOR it cannot cross; the live
    book's was 0.27h, mostly inside a single bar

**The 1.04x runs are a blend that cannot exist**: bar-close TRIGGER with
tick-speed FILL. You cannot have both -- the leniency comes from not looking and
the good fill comes from looking. Three configurations:

| trigger | fill | mean R |
|---|---|---|
| bar close | bar close | +0.006 measured |
| tick | tick | UNKNOWN -- this is live |
| bar close | 1.04x | +0.740 measured, not achievable |

### What is already built for it

- `research/intrabar.py` -- 1m log prices straight from the OKX feathers.
  Deliberately NOT via data_loader: the normalized cache is one file per ticker
  with no timeframe in the name, so a 1m sync overwrites the 30m store.
- `run_portfolio_backtest --exit-check-minutes N` -- default is the bar length
  (reproduces today's behaviour exactly); smaller walks the minutes between bar
  closes checking the frozen levels. Entries untouched, so both arms open
  identical trades. REFUSES to run if any traded ticker lacks fine data.
- `research/validate_intrabar.py` -- 18/18, including one constructed trade that
  survives at 30m and dies at 1m.

### To run it once the download finishes

```
python research/intrabar.py                      # confirm coverage
python research/run_portfolio_backtest.py --days 30 --rank-by theta \
    --out research/rank_experiment/ib_30m.csv
python research/run_portfolio_backtest.py --days 30 --rank-by theta \
    --exit-check-minutes 1 --out research/rank_experiment/ib_1m.csv
```

Same window, same entries. The difference in take-profit rate IS the hypothesis.
Also gives overshoot vs checking frequency: 30m = 1.53x measured, 1m = ?,
~100ms = 1.04x measured live at 0.5 sigma.

## LIVE EXPERIMENT: stop at 1.0 sigma

`STOP_SIGMA = 1.0` since 2026-09-13 08:56, testing the same hypothesis from the
other end -- give positions room and see whether winners appear. The backtest
stays at 0.5 (its CLI default is a literal), and every run now prints

    [WARN] stop_sigma=0.5 but the LIVE book runs 1.0

**Read results carefully.** R is normalised by stop distance, so one R is now
TWICE the dollars -- a -1R stop costs ~$6 on a $300 book, not $3. And
MEASURED_STOP_OVERSHOOT = 1.04 was derived against 0.5 sigma; the same absolute
overshoot is half the ratio at 1.0, so it must be re-derived before being quoted.

This is NOT the existing 0.5->2.5 sigma sweep. That ran at bar close, where
intrabar pokes are invisible by construction.

Next dial position discussed but NOT built: keep the stop at 0.5 and require the
breach to PERSIST for ~15 minutes before acting. Bar-close checking is just the
far end of that dial, with the added defect that its tolerance is aligned to
wall-clock half-hours -- a position opened at 03:01 gets 29 minutes of leniency,
one opened at 03:29 gets one minute.

## Book resets

Three on 2026-09-13, all archived under `trading_data/archive/<timestamp>/`,
nothing deleted. `scripts/reset_book.sh`. The last one (082908Z) is the true
start: uncapped per-ticker, $5,000 notional, all of the day's fixes in.

Open positions are booked `exit_reason="book_reset"` so they stay complete rows
but can never be mistaken for take-profits. Overshoot POOLS across a reset -- it
is exit-side and independent of entry rules.

## Settled by measurement on 2026-09-13

| | |
|---|---|
| ranking | **theta**. +0.740R vs neutrality +0.425 vs both +0.368 (180d, 171 tickers) |
| per-ticker cap | **None**. +0.740 uncapped vs +0.620 capped; and every prior result was uncapped |
| max notional | **$5,000**. Inert below $5k equity |

Neutrality ranking looked best at bar-close fills and worst at realistic ones --
it was compensating for bad execution, not generating alpha. It takes 2,580
trades to theta's 4,438 and skips the good ones: take-profit rate 12.2% vs 20.2%.

Both live and backtest read these from `book_state`; the backtest WARNS on any
divergence.

## Next session should

1. Read `logs/cron.log` — confirm cron cycles are firing every 30 min and measure
   how long a non-first download takes.
2. `scripts/check_vm.sh overshoot` — is the median holding near 1.04x?
3. Once there are enough closes, split overshoot by whether `closed_at` falls inside
   a download window. That settles #22.
4. After a week, read `r2_at_entry` and `net_exposure` off the close rows and decide
   whether the directional exposure is costing anything.
