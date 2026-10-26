# The strategy in plain language (2026-10-24)

## The idea
Pick two crypto perpetual futures that usually move together. When one runs far ahead of
the other, the gap is a "dislocation". Buy the laggard, sell the leader, sized so general
market moves cancel. The trade pays when the gap returns to its recent average (the "mean")
within about 10 hours. Dislocations that do that are the reverters. They are the prize.

## How it works
1. **Spread.** The gap between two coins, hedged by relative volatility, over the last 2 days.
2. **Dislocation.** The gap is unusually far from its mean: past that pair's own 99th
   percentile of the last 2 days (originally a fixed 3 standard deviations, "sigma").
3. **Trade.** Enter, take profit at the mean, stop-loss just beyond entry, time stop after
   a few days. Up to 10 trades at once.
4. **Venue.** Paper-traded on OKX from 12 Sep to 14 Oct 2026. Research now runs entirely on
   Hyperliquid: 206 coins, 17 months of every trade, minute by minute.

## The question that matters
Which dislocations will get back to the mean within 10 hours, and can we tell before they do,
**better than a random walk starting from the same place would**?

## The prize
- About 1 in 3 dislocations reach the mean within 10 hours (33% on Hyperliquid; a random walk
  from the same positions would reach it 45% of the time).
- A reverter earns the whole distance back, roughly 2 to 3 sigma, against a fee of about 0.2
  sigma per round trip. For the ones that revert, the fee is not the problem.
- The cost is the ones that don't revert. Win rate is 28%, and 0.4% of trades made 178% of profit.
- Reverters come back slowly: median about 5.5 hours, not the 1 hour our old model claimed.

## What helps pick the reverters
- **Volatility.** How far a dislocation will travel is predictable, but the direction is not.
- **Hedge quality.** Pairs that really move together revert more often. Not enough alone.
- **Flow data.** Buying and selling pressure, forced liquidations and opening vs closing
  trades help slightly. To catch 80% of reverters you must flag 63% of all dislocations; with
  flow, about 61%.
- **After flagging.** The top 1 to 5% at 60 minutes revert 66 to 81% of the time, with about 1
  sigma left and about an hour to go. But from that position a random walk does as well.

## What does not
- **Size.** How big the dislocation is carries no information about whether it reverts.
- **Our old ranking (theta).** Pointed the wrong way.
- **Beating chance.** Seven attempts on OKX found nothing. On Hyperliquid, flow and market
  features move the odds by about 1 point. Position alone reaches the mean less often than chance.
  (A crude first measure said Hyperliquid flow explains under 1% of each 30-minute price move.
  That is most likely an artefact of the method: imbalance as a ratio, one slope for all coins,
  30-minute bars. Not a finding; a sanity check is proposed.)
- **Flow after the trigger.** Reverters and non-reverters look the same in flow; only price differs.
- **Telling them apart in the first hour.** First-hour features can't separate the ones that
  finish from the ones that don't.
- **The 5-week "edge".** The +0.28 sigma we once saw was a favourable window. Random
  dislocations in the same weeks did better.

## The decisive open step
For the groups we can pick, what do the wins pay and what do the losers cost after fees?
A high hit rate can still lose money if the misses are large. This has never been measured.
It is the first item in the handoff's open list.

## Where we are
No profitable version exists yet. **Done:** data pipeline, flow tests (small ranking gain, no
edge over chance). **In progress or queued:** wallet-level detail (exact concentration, good
vs weak wallets), the full 8-million-event run with a rolling test, minute-level features and
a sequence model, then an impact model and a time-to-mu model.

## Ground rules
Use all the data, no sampling. Test on a rolling forward window. Score everything against
random-sign chance. A second session reviews all work before it is reported.
