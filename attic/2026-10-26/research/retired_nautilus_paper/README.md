# Retired single-pair nautilus paper system — final ledger

Pulled off the GCP `pairs-trading` VM on 2026-09-12, before the system was deleted.
This is the complete record of the single-pair `PairsTradingActor` paper run.

## What it actually did

    started            $30.00   (TRADE_CAPITAL = 30.0)
    realized          -$26.13
    ended              $3.87    -87%
    closed trades      7        2026-08-18 to 2026-09-12 (25 days)
    pairs traded       GALA/UMA, IOST/UMA, API3/SOPH

    exit reasons       time_stop    4
                       adverse_move 1
                       manual_close 1
                       take_profit  1

## Read this before quoting the numbers

**The starting capital was $30, not $300.** The local repo's `run_trading.py` had
`ACCOUNT_EQUITY = 300.0`, but the VM was never updated — the container was running
`TRADE_CAPITAL = 30.0`, a constant that no longer exists in the local code at all.
The two machines had diverged well before this ledger was written.

**The VM code was stale in a way that matters more than the constant.** It predates
the rolling-sigma rewrite entirely. Every distance in this ledger is measured in the
OU stationary sigma, roughly 2.17x smaller than the 7-day rolling sigma the current
spec uses. So these trades were NOT taken under the settled parameters and are not
evidence about them.

**One trade is most of the loss.** Trade 1 (GALA/UMA, adverse_move, 1 hour held) lost
$28.24 on its own — more than the account's entire net loss. The other six roughly
cancelled out. With a single stop-out in the whole record, this ledger cannot confirm
or refute the stop-overshoot finding; the sample is one.

## Why it is kept

It is the only ledger produced by a real process against live OKX data rather than a
simulation, and it records a live `adverse_move` exit with its actual fill prices,
book depth on both legs, and hedge-ratio drift. That makes it worth keeping even
though it cannot carry a statistical argument.
