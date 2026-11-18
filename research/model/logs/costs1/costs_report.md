# HL-COSTS1: does the edge survive realistic execution costs?

## 1. Verdict

**Verdict letter (c): the edge does not survive.** Under the table-based straight-line curve, none of the four vault headline nets is above zero (10 maker -$702.65, 20 maker -$1,645.09, 10 taker -$874.31, 20 taker -$1,568.83). Under the calibrated variant the letter is also (c) (10 maker -$702.65, 20 maker -$1,645.08, 10 taker -$874.31, 20 taker -$1,568.83).

Letters: (a) survives broadly = all four vault headline nets above zero and at least 75% of the sensitivity cells of each above zero; (c) does not survive = none of the four above zero; (b) survives only in named coins or sizes = anything else. The rule was fixed before any result. The letter is a label, not a recommendation to change the plan.

Sensitivity cells with a positive net (vault, conservative curve): 10 maker: 0 of 18, 20 maker: 0 of 18, 10 taker: 0 of 3, 20 taker: 0 of 3.

### 1.1 Conclusion

Conclusion: **(c) does not survive.** At the saved sizes and signals, costs take the edge below zero in all four vault configurations and in all four test-month configurations. Costs are reported, not optimised around: no q, stop, timeout or pick was changed in this analysis. The conclusion rests on these caveats:

- The curve is not conservative. Validation trigger T4 fired: the table curve is below the exact book walk on 5.1% of validation legs at sizes up to $1,000 and on 9.9% of all validation legs (limit 5%).
- Beyond-book legs cannot be priced from the table. Test open20 maker is -$20,068.67 without those trades and -$23,792.34 with them.
- The validation sample is small: 32 files, 16 coin-days. Validation legs at sizes up to $1,000 by tier: least liquid third 4,120, middle third 600, most liquid third 4,680.
- Maker queue position is not observed. The strict and lenient fill rules are a range, not a point estimate.
- Some prices rest on the no-book proxy. Share of trades touching a proxy lookup, by run: 3.8% to 7.0% across the eight headline runs (printed per run in costs_analysis.log, BOOK SOURCES).

### 1.2 Results by configuration

Equity is $1,000 plus the cumulative daily net with sizing held as saved. It can go below zero, so a drawdown above 100% of the start is possible. Drawdown is shown in dollars and as a share of the $1,000 start.

| run | net zero-cost | net with costs | profit factor (zero / costed) | Sharpe (zero / costed) | max drawdown (zero-cost / costed) | filled of saved | positive cells | break-even bp (arithmetic / model) |
|---|---|---|---|---|---|---|---|---|
| vault open10 maker | $1,068.41 | -$702.65 | 1.32 / 0.80 | 7.12 / -5.10 | $111.56 (11.2% of start) / $763.03 (76.3% of start) | 3,326 of 3,832 | 0 of 18 | 5.43 / -4.03 |
| vault open10 taker | $263.85 | -$874.31 | 1.10 / 0.71 | 2.34 / -7.82 | $99.04 (9.9% of start) / $874.31 (87.4% of start) | 3,789 of 3,789 | 0 of 3 | 1.77 / -5.85 |
| vault open20 maker | $2,357.10 | -$1,645.09 | 1.30 / 0.80 | 6.87 / -4.89 | $209.88 (21.0% of start) / $1,648.22 (164.8% of start) | 5,743 of 6,590 | 0 of 18 | 5.31 / -4.16 |
| vault open20 taker | $432.51 | -$1,568.83 | 1.09 / 0.72 | 2.29 / -8.14 | $169.92 (17.0% of start) / $1,568.83 (156.9% of start) | 6,513 of 6,513 | 0 of 3 | 1.62 / -5.88 |
| test open10 maker | $4,034.35 | -$4,072.75 | 1.37 / 0.66 | 7.57 / -8.70 | $318.24 (31.8% of start) / $4,120.78 (412.1% of start) | 7,004 of 8,069 | 0 of 18 | 5.87 / -6.71 |
| test open10 taker | $1,205.99 | -$4,405.99 | 1.17 / 0.51 | 3.80 / -13.81 | $211.77 (21.2% of start) / $4,423.54 (442.4% of start) | 8,078 of 8,078 | 0 of 3 | 2.87 / -10.48 |
| test open20 maker | $15,935.92 | -$23,792.34 | 1.32 / 0.59 | 6.41 / -7.23 | $1,300.87 (130.1% of start) / $23,851.56 (2385.2% of start) | 11,949 of 13,735 | 0 of 18 | 5.22 / -8.79 |
| test open20 taker | $3,036.05 | -$12,129.90 | 1.16 / 0.50 | 3.82 / -13.52 | $465.81 (46.6% of start) / $12,130.57 (1213.1% of start) | 13,699 of 13,699 | 0 of 3 | 2.71 / -10.84 |

Headline cell: maker runs use the strict fill rule, waiting window 5 minutes, impact multiplier 1; taker runs use multiplier 1. Profit factor, Sharpe and drawdown come from daily realised P&L by exit day. Sharpe is the daily mean over the daily standard deviation, annualised with the square root of 365.

### 1.3 The beyond-book trades and the curve artefact

| run | trades with a beyond-book leg | headline (curve remainder) | whole leg at last level | net without those trades |
|---|---|---|---|---|
| vault open10 maker | 0 | -$702.65 | -$702.65 | -$702.65 |
| vault open10 taker | 0 | -$874.31 | -$874.31 | -$874.31 |
| vault open20 maker | 1 | -$1,645.09 | -$1,645.09 | -$1,642.70 |
| vault open20 taker | 0 | -$1,568.83 | -$1,568.83 | -$1,568.83 |
| test open10 maker | 3 | -$4,072.75 | -$4,073.54 | -$3,976.16 |
| test open10 taker | 6 | -$4,405.99 | -$4,408.69 | -$4,344.95 |
| test open20 maker | 25 | -$23,792.34 | -$39,255.99 | -$20,068.67 |
| test open20 taker | 11 | -$12,129.90 | -$12,134.81 | -$11,967.76 |

**Reference number for test open20 maker: -$20,068.67** (without the 25 trades that have a beyond-book leg). The headline -$23,792.34 is affected by the curve artefact on beyond-book legs and is labelled as such. Validation on the 20 raw files: BEYOND-BOOK LEGS (curve beyond-book; exact walk defined for all of them): 470 legs; sizes {2500: 173, 5000: 297}. headline (remainder at last level): curve - exact, bp: mean 13943.671, median 1794.392, p90 57491.923, min 13.362, max 91613.212; curve below exact by > 0.01 bp: 0.0%; mean exact 73.47 bp, mean curve 14017.14 bp.

### 1.4 The curve wording

Validation T4: curve below exact by > 0.01 bp: S<=1000 5.1% of 9,400 legs, all S 9.9% of 12,690 legs (limit 5%)  ->  T4 FIRES; the word conservative is withdrawn for the table-based straight-line curve

The curve is a straight line from the half-spread to the 1,000-dollar slippage point plus depth bands. It is called the table-based straight-line curve in this report, not conservative. On validation legs the curve sits below the exact book walk more often than the 5% limit, so the word conservative was withdrawn.

### 1.5 Maker exit fee finding

saved maker runs charged the maker fee on every non-liquidation exit; stops and timeouts cannot rest as a limit order. Effect = exit leg USD x (0.045% - 0.015%) on exits with reason stop or timeout; nothing else changed; no run edited.

This finding applies to the saved zero-cost maker nets (the reference columns), which charged the maker fee on stop and timeout exits. The costed headline numbers in 1.2 already charge the taker fee on every exit that is not a mu exit (costs_analysis.py, the exit branch: only maker runs with exit reason mu use the limit order and the maker fee; every other exit is a taker fill with the taker fee). So the headline costed nets do include this fee and are not changed by it; the saved zero-cost nets are the ones that fall by the amounts in the table.

| run | stop or timeout exits | extra fee if charged as taker | saved net (zero-cost) | extra as share of net | break-even bp (as saved) | break-even bp (with the fee) |
|---|---|---|---|---|---|---|
| vault open10 | 1,111 | $85.79 | $1,068.41 | 8.0% | 5.43 | 4.99 |
| vault open20 | 1,963 | $197.67 | $2,357.10 | 8.4% | 5.31 | 4.86 |
| test open10 | 2,355 | $308.71 | $4,034.35 | 7.7% | 5.87 | 5.42 |
| test open20 | 4,115 | $1,417.37 | $15,935.92 | 8.9% | 5.22 | 4.76 |

## 2. Assumptions

- Signals, picks, sizes, exit times and exit reasons are exactly as saved. Only fills and costs are re-priced. Slippage in the saved runs is zero.
- Entry is priced at the close of label t0-1; exit at the close of label exit_time-1 (engine convention). Fees are the run's own fee mode: maker 0.015%, taker 0.045%.
- Costs come from the G8 table (the first snapshot of each coin-minute) through a straight-line curve: half-spread at size 0, the 1,000-dollar slippage point, and the 10, 25 and 50 bp depth bands. Beyond the last point the remainder is priced at the last level (an estimate, not a bound).
- No-book proxy: legs on a missing day, a missing minute, a crossed book or a NaN field are priced at half the ctxs impact spread. It is a weak proxy and the share of trades using it is printed.
- Maker fills: limit at the best bid or ask, waiting window 5 minutes (1 and 15 as sensitivity), strict and lenient fill rules as the range. No queue position is observed. A leg unfilled at the end of the window is crossed as taker; both legs unfilled means the trade is missed and its slot is not refilled.
- Equity is rebuilt from per-trade nets in exit order. Compounding, sizing and freed slots are not re-fed.
- Liquidity tiers are terciles of each coin's median daily traded notional; a trade takes its less liquid leg's tier.
- G8 days missing from the archive: day files missing: 7 ['20260708', '20260712', '20260713', '20260714', '20260715', '20260716', '20260717']. They are absent from the raw archive itself.
- BTC data in the one-leg check: the 30-minute BTC.feather (user_data/normalized/BTC.feather). BTC is not in the cleaned 1-minute price set and there is no 1-minute BTC in the cache. The BTC price is up to 30 minutes old at both ends, which blurs slopes toward zero. No rerun was done.
- No-bounce check: the matched comparator tests the close only on minutes where the mid exists. That comparator was decided after a smoke run on a sample of events (a missing mid minute can only hide a crossing, so the mid reach was biased low). The run order is in section 6.
- Leverage caps are today's snapshot, not historical limits. Nothing is simulated with different caps.

tiers vault: 177 coins; median daily traded notional by tier: least liquid third $119,327, middle third $394,970, most liquid third $4,293,723

tiers test: 192 coins; median daily traded notional by tier: least liquid third $117,187, middle third $286,597, most liquid third $2,594,029

## 3. Results by liquidity tier

Columns: trades saved, trades filled, zero-cost net, costed net. A trade takes its less liquid leg's tier.

**vault open10 maker**

| tier | saved | filled | net zero-cost | net with costs |
|---|---|---|---|---|
| least liquid third | 2,549 | 2,120 | $885.80 | -$511.14 |
| middle third | 977 | 914 | $71.38 | -$196.35 |
| most liquid third | 306 | 292 | $111.23 | $4.83 |

**vault open10 taker**

| tier | saved | filled | net zero-cost | net with costs |
|---|---|---|---|---|
| least liquid third | 2,510 | 2,510 | $341.19 | -$632.59 |
| middle third | 976 | 976 | $21.56 | -$109.64 |
| most liquid third | 303 | 303 | -$98.89 | -$132.08 |

**vault open20 maker**

| tier | saved | filled | net zero-cost | net with costs |
|---|---|---|---|---|
| least liquid third | 4,358 | 3,656 | $2,091.15 | -$1,049.76 |
| middle third | 1,713 | 1,598 | $217.35 | -$422.92 |
| most liquid third | 519 | 489 | $48.60 | -$172.41 |

**vault open20 taker**

| tier | saved | filled | net zero-cost | net with costs |
|---|---|---|---|---|
| least liquid third | 4,329 | 4,329 | $619.14 | -$1,089.22 |
| middle third | 1,676 | 1,676 | $16.73 | -$222.88 |
| most liquid third | 508 | 508 | -$203.36 | -$256.74 |

**test open10 maker**

| tier | saved | filled | net zero-cost | net with costs |
|---|---|---|---|---|
| least liquid third | 5,748 | 4,835 | $3,488.59 | -$2,980.57 |
| middle third | 1,782 | 1,651 | $392.41 | -$796.29 |
| most liquid third | 539 | 518 | $153.36 | -$295.88 |

**test open10 taker**

| tier | saved | filled | net zero-cost | net with costs |
|---|---|---|---|---|
| least liquid third | 5,752 | 5,752 | $1,421.28 | -$3,479.40 |
| middle third | 1,797 | 1,797 | -$84.55 | -$680.14 |
| most liquid third | 529 | 529 | -$130.74 | -$246.45 |

**test open20 maker**

| tier | saved | filled | net zero-cost | net with costs |
|---|---|---|---|---|
| least liquid third | 9,704 | 8,174 | $15,029.52 | -$17,136.45 |
| middle third | 3,123 | 2,894 | $357.09 | -$5,154.04 |
| most liquid third | 908 | 881 | $549.32 | -$1,501.85 |

**test open20 taker**

| tier | saved | filled | net zero-cost | net with costs |
|---|---|---|---|---|
| least liquid third | 9,677 | 9,677 | $3,760.51 | -$9,463.04 |
| middle third | 3,123 | 3,123 | -$703.87 | -$2,314.30 |
| most liquid third | 899 | 899 | -$20.59 | -$352.56 |

Tier cells with a positive costed net: 1 of 24. A positive tier cell is a hypothesis for later, not a result; no group was chosen.

### 3.1 Larger-leg size

**vault open10 maker**

| larger-leg size | saved | filled | net zero-cost | net with costs |
|---|---|---|---|---|
| < $100 | 420 | 322 | $92.70 | $1.17 |
| $100-250 | 3,038 | 2,648 | $860.90 | -$663.79 |
| $250-1,000 | 373 | 355 | $114.17 | -$40.64 |
| > $1,000 | 1 | 1 | $0.63 | $0.61 |

**vault open10 taker**

| larger-leg size | saved | filled | net zero-cost | net with costs |
|---|---|---|---|---|
| < $100 | 1,146 | 1,146 | $111.62 | -$293.47 |
| $100-250 | 2,484 | 2,484 | $184.93 | -$527.24 |
| $250-1,000 | 159 | 159 | -$32.70 | -$53.61 |

**vault open20 maker**

| larger-leg size | saved | filled | net zero-cost | net with costs |
|---|---|---|---|---|
| < $100 | 597 | 443 | $98.06 | -$51.25 |
| $100-250 | 3,985 | 3,477 | $1,536.69 | -$519.17 |
| $250-1,000 | 1,981 | 1,799 | $645.47 | -$1,136.90 |
| > $1,000 | 27 | 24 | $76.89 | $62.22 |

**vault open20 taker**

| larger-leg size | saved | filled | net zero-cost | net with costs |
|---|---|---|---|---|
| < $100 | 1,804 | 1,804 | $167.51 | -$406.90 |
| $100-250 | 4,397 | 4,397 | $402.89 | -$983.36 |
| $250-1,000 | 312 | 312 | -$137.89 | -$178.57 |

**test open10 maker**

| larger-leg size | saved | filled | net zero-cost | net with costs |
|---|---|---|---|---|
| < $100 | 496 | 434 | $136.20 | -$109.79 |
| $100-250 | 3,851 | 3,282 | $1,476.87 | -$1,496.39 |
| $250-1,000 | 3,637 | 3,207 | $2,508.61 | -$2,268.55 |
| > $1,000 | 85 | 81 | -$87.33 | -$198.02 |

**test open10 taker**

| larger-leg size | saved | filled | net zero-cost | net with costs |
|---|---|---|---|---|
| < $100 | 1,187 | 1,187 | $265.10 | -$417.23 |
| $100-250 | 6,099 | 6,099 | $1,045.09 | -$3,622.73 |
| $250-1,000 | 789 | 789 | -$103.71 | -$365.32 |
| > $1,000 | 3 | 3 | -$0.49 | -$0.70 |

**test open20 maker**

| larger-leg size | saved | filled | net zero-cost | net with costs |
|---|---|---|---|---|
| < $100 | 335 | 303 | $149.87 | -$27.84 |
| $100-250 | 3,770 | 3,281 | $1,736.22 | -$1,396.79 |
| $250-1,000 | 6,199 | 5,246 | $10,233.99 | -$9,198.62 |
| > $1,000 | 3,431 | 3,119 | $3,815.84 | -$13,169.09 |

**test open20 taker**

| larger-leg size | saved | filled | net zero-cost | net with costs |
|---|---|---|---|---|
| < $100 | 912 | 912 | $207.30 | -$281.34 |
| $100-250 | 6,445 | 6,445 | $1,420.87 | -$4,170.34 |
| $250-1,000 | 6,229 | 6,229 | $1,574.78 | -$7,454.65 |
| > $1,000 | 113 | 113 | -$166.91 | -$223.57 |

### 3.2 Positive cells across the cuts

6 of 78 cells across the tier, size and leverage cuts have a positive costed net. They are in: vault open10 maker, vault open20 maker. Cells with a positive net hold 1 to 322 filled trades. No group was chosen; no correction was made for the number of cells.

| run | cut | group | filled | net with costs |
|---|---|---|---|---|
| vault open10 maker | liquidity tier | most liquid third | 292 | $4.83 |
| vault open10 maker | larger-leg size | < $100 | 322 | $1.17 |
| vault open10 maker | larger-leg size | > $1,000 | 1 | $0.61 |
| vault open10 maker | leverage | 10x | 101 | $31.48 |
| vault open20 maker | larger-leg size | > $1,000 | 24 | $62.22 |
| vault open20 maker | leverage | 10x | 170 | $29.45 |

## 4. Answers to the two questions

### 4.1 (a) Volume versus depth

Question: does a leg's size relative to the coin's traded notional in the entry minute explain the walk cost beyond the half-spread? Fit: walk (bp) = intercept + slope x sqrt(leg / minute notional), on taker entry legs with a book in their own minute.

| period | legs fitted | intercept (bp) | slope | R squared | rank correlation | share of legs above 10% of minute notional |
|---|---|---|---|---|---|---|
| vault | 5,750 | 0.26 | 0.14 | 0.012 | 0.306 | 74.8% |
| test | 10,626 | 0.30 | 0.01 | 0.001 | 0.185 | 76.9% |

- vault: legs with a minute notional 6,144; leg / minute notional median 0.80, share of legs above 10% of the minute's notional 74.8%, above 100% 46.8%; fit on 5,750 legs with a book walk: walk_bp = 0.26 + 0.14 x sqrt(leg/notional), R^2 0.012, rank correlation 0.306
    - least liquid third: n 2,066, slope 0.05, R^2 0.001, rank corr 0.103
    - middle third: n 1,844, slope 0.07, R^2 0.002, rank corr 0.160
    - most liquid third: n 1,840, slope 0.02, R^2 0.004, rank corr 0.180
- test: legs with a minute notional 11,039; leg / minute notional median 1.04, share of legs above 10% of the minute's notional 76.9%, above 100% 50.5%; fit on 10,626 legs with a book walk: walk_bp = 0.30 + 0.01 x sqrt(leg/notional), R^2 0.001, rank correlation 0.185
    - least liquid third: n 3,428, slope 0.01, R^2 0.000, rank corr 0.089
    - middle third: n 3,317, slope 0.01, R^2 0.001, rank corr 0.109
    - most liquid third: n 3,881, slope 0.01, R^2 0.000, rank corr 0.191

Reading: the fit explains little of the variation (R squared at most 0.012); the rank correlation of 0.19 to 0.31 shows a weak positive link; most legs are large against the minute's volume (74.8% to 76.9% are above 10% of the minute's traded notional).

### 4.2 (b) Leverage groups

Trades and net by the coin's maximum leverage (today's snapshot). Leverage changes sizing, not signals; nothing is simulated.

**vault open10 maker**

| max leverage | saved | filled | net zero-cost | net with costs |
|---|---|---|---|---|
| 3x | 3,119 | 2,646 | $939.58 | -$579.81 |
| 5x | 607 | 579 | $38.76 | -$154.31 |
| 10x | 106 | 101 | $90.07 | $31.48 |

**vault open10 taker**

| max leverage | saved | filled | net zero-cost | net with costs |
|---|---|---|---|---|
| 3x | 3,057 | 3,057 | $342.22 | -$701.58 |
| 5x | 625 | 625 | -$29.22 | -$106.61 |
| 10x | 107 | 107 | -$49.14 | -$66.12 |

**vault open20 maker**

| max leverage | saved | filled | net zero-cost | net with costs |
|---|---|---|---|---|
| 3x | 5,295 | 4,513 | $2,243.61 | -$1,170.34 |
| 5x | 1,115 | 1,060 | -$25.46 | -$504.21 |
| 10x | 180 | 170 | $138.95 | $29.45 |

**vault open20 taker**

| max leverage | saved | filled | net zero-cost | net with costs |
|---|---|---|---|---|
| 3x | 5,250 | 5,250 | $694.98 | -$1,138.90 |
| 5x | 1,085 | 1,085 | -$145.10 | -$285.99 |
| 10x | 178 | 178 | -$117.37 | -$143.94 |

**test open10 maker**

| max leverage | saved | filled | net zero-cost | net with costs |
|---|---|---|---|---|
| 3x | 6,916 | 5,899 | $3,828.64 | -$3,297.80 |
| 5x | 982 | 941 | $157.24 | -$622.95 |
| 10x | 171 | 164 | $48.48 | -$152.00 |

**test open10 taker**

| max leverage | saved | filled | net zero-cost | net with costs |
|---|---|---|---|---|
| 3x | 6,929 | 6,929 | $1,442.63 | -$3,808.40 |
| 5x | 971 | 971 | -$175.85 | -$493.21 |
| 10x | 178 | 178 | -$60.79 | -$104.38 |

**test open20 maker**

| max leverage | saved | filled | net zero-cost | net with costs |
|---|---|---|---|---|
| 3x | 11,728 | 10,016 | $15,314.03 | -$19,709.26 |
| 5x | 1,716 | 1,650 | $840.91 | -$2,920.28 |
| 10x | 291 | 283 | -$219.02 | -$1,162.80 |

**test open20 taker**

| max leverage | saved | filled | net zero-cost | net with costs |
|---|---|---|---|---|
| 3x | 11,724 | 11,724 | $3,468.60 | -$10,697.08 |
| 5x | 1,689 | 1,689 | -$323.68 | -$1,200.18 |
| 10x | 286 | 286 | -$108.87 | -$232.64 |

## 5. Validation of the curve (T1 to T4)

The 32 raw L2 files of the validation sample (16 coin-days). The G8 table row is recomputed from the raw book and the curve is compared with the exact book walk at seven sizes.

- Sample: ASKED vs FOUND (unique coin-minutes asked from the 32 files, 960; found 940; the T3 denominator is the found rows):
- Reproduction (i): REPRODUCTION: 940 of 940 raw rows equal the G8 row in every table field (1e-6 relative): 100.000%; T3 does not fire (threshold 99.9%)
- T1: mean overstatement S=250 0.543 bp, S=500 0.586 bp (limit 1.0); medians S<=1000 50: 0.000, 100: 0.000, 250: 0.000, 500: 0.000, 1000: 0.000  ->  T1 does not fire
- T3: reproduction 100.000% (limit 99.9%)  ->  T3 does not fire
- T4: curve below exact by > 0.01 bp: S<=1000 5.1% of 9,400 legs, all S 9.9% of 12,690 legs (limit 5%)  ->  T4 FIRES; the word 'conservative' is withdrawn for the table-based straight-line curve
- T2: sign flips in []; letter differs: False  ->  T2 does not fire

T1 (overstatement), T2 (verdict flip) and T3 (reproduction) do not fire. T4 (understatement) fires. A fired trigger means the full 88,405-file raw pull would be asked of the user, with the cost range printed. That pull has not been asked and is the user's and the planner's decision. The verdict letter and every sign are unchanged between the conservative and the calibrated variant.

Curve minus exact book walk, by size (a negative value means the curve is below the exact walk):

| size S | legs | mean overstatement (bp) | median | p90 | min (negative = understatement) | share curve below exact |
|---|---|---|---|---|---|---|
| $50 | 1,880 | 0.157 | 0.000 | 0.862 | -6.781 | 3.8% |
| $100 | 1,880 | 0.307 | 0.000 | 1.457 | -7.228 | 4.9% |
| $250 | 1,880 | 0.543 | 0.000 | 1.961 | -6.426 | 7.1% |
| $500 | 1,880 | 0.586 | 0.000 | 1.513 | -7.186 | 9.6% |
| $1,000 | 1,880 | 0.243 | 0.000 | 0.000 | -0.000 | 0.0% |
| $2,500 | 1,707 | 2.244 | 0.527 | 7.385 | -3.875 | 19.4% |
| $5,000 | 1,583 | 3.587 | 0.535 | 12.882 | -3.910 | 28.6% |

## 6. How long each piece took

| piece | time |
|---|---|
| G8 extraction on EC2 Tokyo (log) | 215 s |
| costs_analysis, conservative: load extract, G8 table and ctxs proxy | 124.3 s |
| costs_analysis, conservative: load geometry, cleaned prices and 1-minute bars | 231.2 s |
| costs_analysis, conservative: prepare runs (legs, reference prices, gross receipt) | 7.6 s |
| costs_analysis, conservative: prepare maker/exit fill windows (all 8 runs) | 13.3 s |
| costs_analysis, conservative: evaluate the sensitivity grid (all runs) | 14.9 s |
| costs_analysis, calibrated: load extract, G8 table and ctxs proxy | 126.7 s |
| costs_analysis, calibrated: load geometry, cleaned prices and 1-minute bars | 234.4 s |
| costs_analysis, calibrated: prepare runs (legs, reference prices, gross receipt) | 7.7 s |
| costs_analysis, calibrated: prepare maker/exit fill windows (all 8 runs) | 18.7 s |
| costs_analysis, calibrated: evaluate the sensitivity grid (all runs) | 19.1 s |
| costs_analysis, conservative: total | 404 s |
| costs_validate (20 raw files) | not timed in its log |
| no-bounce script (both periods, every event) | 176 s |
| one-leg script (eight runs) | 49 s |

Process order of the no-bounce check, from the transcript's own timestamps (UTC): checker review of the rules (no code) 2026-11-18T05:07:28.728Z; planner rulings 2026-11-18T05:07:36.480Z; first smoke run (event level) 2026-11-18T05:10:27.547Z; smoke run with the vault trade table 2026-11-18T05:11:16.812Z. The smoke runs printed vault trade numbers before review. The builder states that no rule was changed because of the trade numbers; the order of events rests on the timestamps and that statement.

## 7. Entry delay: engine-change write-up (text only, nothing run)


### What the delay means
The pick is made at wall-clock minute t0, as today. The order fills d minutes later (d = 1, 5, 15). Signals and picks stay exactly as saved, so there is no look-ahead.

### Exact engine changes (s1_profit1.py)
- compute_move_paths: start the 601-minute window at label t0-1+d. The entry spread becomes P[d] (the spread at the delayed fill). The move is measured from P[d]: move = -(P - P[d]) x s, so the target distance (z_abs in run_one) becomes |P[d]| and stops are measured from P[d]. The assert max |move[0]| < 1e-6 is re-pointed at the new entry.
- Gap and no-data status is evaluated on the shifted 601-minute window. Events near the end of a data period, or with a gap in the new window, drop out. They are counted as a new status.
- Skip rule at the delayed fill (PROPOSED; the planner and the user decide the rule): skip the pick if the spread has already crossed mu or its sign has flipped. The alternative is to enter anyway and measure. If skipping is chosen, a new counter is added to the skip table next to the engine's current reasons (book_full, margin, min_order, below_floor, liquidated_minute).
- run_one: the pick is admitted at cur_minute = t0+d. Sizing uses the account value at t0+d, not t0. Book occupancy and margin change. This is a real engine change, not a relabel.
- Because the book is almost always full, moving each admission by d minutes changes which picks get a free slot. Saved d = 0 skips for q 1% / no stop / taker: test open10 27,488 of 35,629 picks (admitted 8,078, book_full 27,488, min_order 63); vault open10 10,010 book_full (admitted 3,789, min_order 148). So some delayed trades are not in the saved trade set at all.
- Position fields: start_label, last_funding_h and the slippage lookup (label0) move to the fill minute t0+d. The 600-minute timeout runs from the delayed fill.
- dir_a, dir_b, la, lb: unchanged in form, but computed from the sign of the spread at the delayed fill.
- Trade log: keep the pick time t0 and add the fill time as its own column. costs_analysis, the G8 targets and every COSTS1 join today use t0 as both the pick time and the entry minute. They would need the fill time for entries (reference price = close of the label before the fill; the maker window starts at the fill).
- Cross-check: the v1 label check does not apply for d > 0. Replace it with a d = 0 regression: the new code at d = 0 must reproduce the saved trades exactly (same trade count, same net to the cent).
- Output tags carry a _delay{d} suffix so saved d = 0 files are never overwritten.
- COSTS1 re-run needs a new G8 extraction of BOTH entry and exit windows, scoped to the delayed run's trades. The existing extract covers [t0-1, t0+15] per saved pick. A fill at t0+d needs [t0+d-1, t0+d+W]: the maker windows (W = 5 and 15) fall outside for any d > 0, the plus-one-minute neighbour falls outside at d = 15, and only the taker own-minute entry is covered, and only for d <= 14 and only for trades that are also in the saved set. Exit windows move with the fill. That is a Tokyo pull: it needs spend and the user's own yes.

### Time (measured: the four saved 24-tag engine runs)

| Run | tags in log | engine log time (s) |
|---|---:|---:|
| vault open10 | 24 | 498 |
| vault open20 | 24 | 630 |
| test open10 | 24 | 1011 |
| test open20 | 24 | 1339 |

Sum of the four saved 24-tag runs: 3478 s (58.0 min). This is the only measured number. The logs hold one total per 24-tag run and no per-tag time. Total divided by 24 would be an average that includes loading, and q 1% is the heaviest tag, so a per-tag figure cannot be bounded from the logs.

**Not estimated:** the engine time for a delayed COSTS1 re-run. The d = 0 regression (needed anyway) will measure it. **Builder guess, not measured:** about half a day of code, plus one checker round, plus the new G8 extraction and the COSTS1 re-run and re-report (cost not estimated).

## 8. No-bounce check: close vs mid gap

Source: logs/costs1/costs_nobounce.json (sha256 874b5e11c115), written by diagnostics/costs_nobounce.py; the log is diagnostics/costs_nobounce.log. Rules: costs1_rules.md section 10. This section is written by diagnostics/costs_nobounce_section.py; no number is typed by hand.

### Headline cell
Vault, q 1% / no stop / taker / open10. With the G8 table mid as a labelled fallback where the ctxs mid is missing, 3,783 trades have all four mids (99.8% coverage). On those trades the close-based gross is $945.69 and the mid-to-mid gross is $508.34. **Gross ratio 53.8%. Band: PARTLY close vs mid gap (25% to 75%).**
Net after fees on the same trades: close-based $277.63, mid-to-mid $-159.72 (net ratio -57.5%). Fees do not change, so the net ratio moves more than the gross ratio.
Ctxs mid only (no band; coverage 74.8%, 2,836 trades, skewed to the earlier days): gross ratio 70.5%, close gross $953.17, mid gross $671.87.
How not to over-read the headline: the 53.8% mixes fresh and stale trades (1,839 fresh at a gross ratio of 85.0%, 1,944 stale at 28.4%). The ctxs-only 70.5% is a different, earlier set of trades, not the same trades with another mid. The two mid sources disagree by more than 1 bp on 45.0% of the vault minutes where both exist, but on the same trades they give the same gross ratio (source-sensitivity table below).

### Source-sensitivity line (print only; no change to the headline or the bands)
The same trades, two mid sources: only trades that have BOTH a ctxs mid and a G8 table mid at all four stamps (entry and exit, both legs). Gross ratio = mid-to-mid gross / saved close-based gross on those trades. The last two columns are the gap between the two mids at those stamps, in bp. Written by diagnostics/costs_nobounce_sources.py (log costs_nobounce_sources.log).
| run | trades with both mids / all | gross ratio, ctxs mid | gross ratio, G8 mid | median abs gap, bp | p90 abs gap, bp |
|---|---|---|---|---|---|
| vault open10 maker | 2,587 / 3,832 (67.5%) | 72.0% | 72.0% | 1.134 | 9.428 |
| vault open10 taker | 2,571 / 3,789 (67.9%) | 71.1% | 70.8% | 1.120 | 9.346 |
| vault open20 maker | 4,478 / 6,590 (68.0%) | 74.6% | 74.4% | 1.119 | 9.130 |
| vault open20 taker | 4,432 / 6,513 (68.0%) | 72.4% | 72.1% | 1.134 | 9.064 |
| test open10 maker | 7,501 / 8,069 (93.0%) | 26.4% | 26.4% | 0.153 | 6.632 |
| test open10 taker | 7,530 / 8,078 (93.2%) | 21.5% | 21.7% | 0.152 | 6.771 |
| test open20 maker | 12,806 / 13,735 (93.2%) | 24.3% | 24.4% | 0.152 | 6.183 |
| test open20 taker | 12,759 / 13,699 (93.1%) | 23.5% | 23.5% | 0.154 | 6.292 |
In the later vault months only the G8 mid exists, so the headline gross ratio (with fallback) against the ratios on the both-mids trades cannot be split between 'later period' and 'G8 source'. The overlap shows the source does not move the ratio, so the period is the likelier cause, but that is not tested here.
The period-sensitivity table below shows it: the vault's July to September gross ratios run 58.4% to 69.2% across the four runs, and the drop sits in October (vault open10 taker: close gross $41.04, mid gross $-52.73, 83.0% of the trades with a G8 stamp). The period is still confounded with the G8 source.
On the same trades the two sources give the same gross ratio. So the gap between the headline (ctxs + fallback) and the ctxs-only figure points to which trades are in the set (the ctxs-only set is the earlier trades), not to which mid is used.

### Period-sensitivity line (print only; no change to the headline or the bands)
Gross ratio (mid-to-mid gross / close-based gross, ctxs + G8 fallback, trades with all four mids) by entry month, for each of the eight runs, with the trade counts and the mid source used. 'Source' = share of the matched trades whose four mids all come from the ctxs cache / share with at least one stamp taken from the G8 table. n/m = not meaningful: the month's close gross is zero or negative or under 5% of the run's close gross. Dollars are kept. Written by diagnostics/costs_nobounce_sources.py.
| run | month | trades matched / all | close gross | mid gross | gross ratio | source: all ctxs / some G8 |
|---|---|---|---|---|---|---|
| vault open10 maker | 2026-07 | 840 / 840 | $194.80 | $133.83 | 68.7% | 100.0% / 0.0% |
| vault open10 maker | 2026-08 | 1,264 / 1,265 | $366.02 | $248.72 | 68.0% | 90.1% / 9.9% |
| vault open10 maker | 2026-09 | 1,241 / 1,243 | $764.56 | $469.58 | 61.4% | 64.7% / 35.3% |
| vault open10 maker | 2026-10 | 482 / 484 | $52.90 | $-107.56 | n/m | 16.2% / 83.8% |
| vault open10 taker | 2026-07 | 831 / 831 | $161.03 | $102.99 | 64.0% | 100.0% / 0.0% |
| vault open10 taker | 2026-08 | 1,260 / 1,261 | $272.38 | $183.04 | 67.2% | 90.6% / 9.4% |
| vault open10 taker | 2026-09 | 1,222 / 1,224 | $471.24 | $275.04 | 58.4% | 64.2% / 35.8% |
| vault open10 taker | 2026-10 | 470 / 473 | $41.04 | $-52.73 | n/m | 17.0% / 83.0% |
| vault open20 maker | 2026-07 | 1,441 / 1,441 | $252.69 | $148.36 | 58.7% | 100.0% / 0.0% |
| vault open20 maker | 2026-08 | 2,200 / 2,204 | $780.91 | $540.38 | 69.2% | 90.3% / 9.7% |
| vault open20 maker | 2026-09 | 2,127 / 2,129 | $1,672.03 | $997.02 | 59.6% | 64.4% / 35.6% |
| vault open20 maker | 2026-10 | 813 / 816 | $332.82 | $-39.76 | -11.9% | 15.0% / 85.0% |
| vault open20 taker | 2026-07 | 1,432 / 1,432 | $230.82 | $135.65 | 58.8% | 100.0% / 0.0% |
| vault open20 taker | 2026-08 | 2,188 / 2,191 | $462.61 | $296.66 | 64.1% | 90.2% / 9.8% |
| vault open20 taker | 2026-09 | 2,087 / 2,089 | $814.95 | $479.29 | 58.8% | 64.0% / 36.0% |
| vault open20 taker | 2026-10 | 797 / 801 | $125.01 | $-35.52 | -28.4% | 15.8% / 84.2% |
| test open10 maker | 2025-12 | 499 / 499 | $175.07 | $80.86 | n/m | 100.0% / 0.0% |
| test open10 maker | 2026-01 | 1,263 / 1,263 | $269.80 | $9.23 | 3.4% | 100.0% / 0.0% |
| test open10 maker | 2026-02 | 1,134 / 1,134 | $561.78 | $-37.94 | -6.8% | 100.0% / 0.0% |
| test open10 maker | 2026-03 | 947 / 947 | $270.62 | $-48.94 | -18.1% | 100.0% / 0.0% |
| test open10 maker | 2026-04 | 1,356 / 1,356 | $1,199.59 | $460.18 | 38.4% | 100.0% / 0.0% |
| test open10 maker | 2026-05 | 1,257 / 1,257 | $806.15 | $-101.54 | -12.6% | 98.0% / 2.0% |
| test open10 maker | 2026-06 | 1,214 / 1,214 | $1,757.70 | $825.44 | 47.0% | 100.0% / 0.0% |
| test open10 maker | 2026-07 | 363 / 399 | $95.80 | $-29.74 | n/m | 100.0% / 0.0% |
| test open10 taker | 2025-12 | 501 / 501 | $161.95 | $72.75 | 44.9% | 100.0% / 0.0% |
| test open10 taker | 2026-01 | 1,259 / 1,259 | $220.38 | $-1.19 | -0.5% | 100.0% / 0.0% |
| test open10 taker | 2026-02 | 1,151 / 1,151 | $490.53 | $19.71 | 4.0% | 100.0% / 0.0% |
| test open10 taker | 2026-03 | 940 / 940 | $221.62 | $-13.45 | -6.1% | 100.0% / 0.0% |
| test open10 taker | 2026-04 | 1,342 / 1,342 | $703.75 | $218.27 | 31.0% | 100.0% / 0.0% |
| test open10 taker | 2026-05 | 1,253 / 1,253 | $422.87 | $-68.71 | -16.2% | 98.0% / 2.0% |
| test open10 taker | 2026-06 | 1,229 / 1,229 | $877.30 | $418.55 | 47.7% | 100.0% / 0.0% |
| test open10 taker | 2026-07 | 367 / 403 | $40.57 | $-27.36 | n/m | 100.0% / 0.0% |
| test open20 maker | 2025-12 | 917 / 917 | $374.57 | $188.56 | n/m | 100.0% / 0.0% |
| test open20 maker | 2026-01 | 2,297 / 2,297 | $758.61 | $162.67 | n/m | 100.0% / 0.0% |
| test open20 maker | 2026-02 | 1,937 / 1,937 | $1,702.13 | $78.58 | 4.6% | 100.0% / 0.0% |
| test open20 maker | 2026-03 | 1,462 / 1,462 | $1,207.79 | $207.27 | 17.2% | 100.0% / 0.0% |
| test open20 maker | 2026-04 | 2,317 / 2,317 | $4,726.06 | $1,609.17 | 34.0% | 100.0% / 0.0% |
| test open20 maker | 2026-05 | 2,106 / 2,107 | $3,382.29 | $-1,139.41 | -33.7% | 97.6% / 2.4% |
| test open20 maker | 2026-06 | 2,017 / 2,017 | $8,073.59 | $3,398.81 | 42.1% | 100.0% / 0.0% |
| test open20 maker | 2026-07 | 629 / 681 | $283.67 | $-589.35 | n/m | 100.0% / 0.0% |
| test open20 taker | 2025-12 | 929 / 929 | $279.23 | $89.76 | n/m | 100.0% / 0.0% |
| test open20 taker | 2026-01 | 2,276 / 2,276 | $560.63 | $112.10 | 20.0% | 100.0% / 0.0% |
| test open20 taker | 2026-02 | 1,919 / 1,919 | $1,031.35 | $63.18 | 6.1% | 100.0% / 0.0% |
| test open20 taker | 2026-03 | 1,470 / 1,470 | $614.12 | $96.43 | 15.7% | 100.0% / 0.0% |
| test open20 taker | 2026-04 | 2,310 / 2,310 | $1,961.10 | $666.80 | 34.0% | 100.0% / 0.0% |
| test open20 taker | 2026-05 | 2,109 / 2,110 | $1,287.88 | $-330.83 | -25.7% | 97.6% / 2.4% |
| test open20 taker | 2026-06 | 2,007 / 2,007 | $2,231.76 | $939.46 | 42.1% | 100.0% / 0.0% |
| test open20 taker | 2026-07 | 626 / 678 | $144.60 | $-49.64 | n/m | 100.0% / 0.0% |

### The eight priority runs (q 1% / no stop), ctxs + G8 fallback
Gross ratio = mid-to-mid gross / close-based gross on the trades with all four mids. Fresh = all four closes had a trade in their minute; stale = at least one close was an older trade. A = saved net (close, zero cost). B = mid-to-mid net (same fees and funding). C = costed net with the book spread and depth model already reported (conservative curve). Only the vault taker open10 cell carries a band; the others carry no label.

| run | trades matched / all | close gross | mid gross | gross ratio | gross ratio, fresh | gross ratio, stale | net A | net B | net C | ctxs-only gross ratio |
|---|---|---|---|---|---|---|---|---|---|---|
| vault open10 maker | 3,827 / 3,832 | $1,378.27 | $744.55 | 54.0% | 84.1% | 35.2% | $1,088.35 | $454.63 | $-680.73 | 72.1% |
| vault open10 taker | 3,783 / 3,789 | $945.69 | $508.34 | 53.8% | 85.0% | 28.4% | $277.63 | $-159.72 | $-859.55 | 70.5% |
| vault open20 maker | 6,581 / 6,590 | $3,038.45 | $1,645.99 | 54.2% | 85.7% | 33.1% | $2,386.31 | $993.85 | $-1,603.25 | 74.2% |
| vault open20 taker | 6,504 / 6,513 | $1,633.39 | $876.08 | 53.6% | 84.0% | 31.6% | $441.38 | $-315.92 | $-1,557.64 | 71.9% |
| test open10 maker | 8,033 / 8,069 | $5,136.51 | $1,157.54 | 22.5% | 74.7% | 5.8% | $4,057.32 | $78.34 | $-4,040.58 | 22.6% |
| test open10 taker | 8,042 / 8,078 | $3,138.97 | $618.59 | 19.7% | 72.2% | 3.8% | $1,222.18 | $-1,298.20 | $-4,364.35 | 19.7% |
| test open20 maker | 13,682 / 13,735 | $20,508.70 | $3,916.29 | 19.1% | 70.9% | 4.5% | $15,919.05 | $-673.36 | $-23,725.99 | 18.6% |
| test open20 taker | 13,646 / 13,699 | $8,110.67 | $1,587.26 | 19.6% | 72.6% | 3.6% | $3,054.94 | $-3,468.46 | $-12,044.84 | 19.2% |

#### Gross ratio by liquidity tier (ctxs + G8 fallback)
n/m = not meaningful: the tier's close gross is zero or negative, or under 5% of the run's close gross, so the ratio sits on a near-zero denominator. The dollars are kept.
| run | least liquid | middle | most liquid |
|---|---|---|---|
| vault open10 maker | 45.2% (n 2,547, close gross $1,070.20, mid gross $483.30) | 76.6% (n 977, close gross $146.63, mid gross $112.32) | 92.2% (n 303, close gross $161.45, mid gross $148.94) |
| vault open10 taker | 45.8% (n 2,507, close gross $737.94, mid gross $337.85) | 85.8% (n 976, close gross $206.37, mid gross $177.07) | n/m (n 300, close gross $1.38, mid gross $-6.59) |
| vault open20 maker | 48.0% (n 4,354, close gross $2,491.97, mid gross $1,195.44) | 80.5% (n 1,712, close gross $398.62, mid gross $320.80) | n/m (n 515, close gross $147.86, mid gross $129.76) |
| vault open20 taker | 47.8% (n 4,325, close gross $1,327.29, mid gross $634.98) | 85.3% (n 1,675, close gross $344.70, mid gross $294.10) | n/m (n 504, close gross $-38.61, mid gross $-53.00) |
| test open10 maker | 15.8% (n 5,724, close gross $4,237.56, mid gross $667.84) | 46.5% (n 1,776, close gross $636.12, mid gross $295.97) | 73.7% (n 533, close gross $262.84, mid gross $193.72) |
| test open10 taker | 15.9% (n 5,728, close gross $2,683.35, mid gross $426.24) | 38.3% (n 1,790, close gross $357.68, mid gross $137.12) | n/m (n 524, close gross $97.94, mid gross $55.22) |
| test open20 maker | 17.7% (n 9,671, close gross $18,077.07, mid gross $3,203.16) | -2.0% (n 3,112, close gross $1,380.29, mid gross $-27.63) | 70.5% (n 899, close gross $1,051.35, mid gross $740.76) |
| test open20 taker | 16.2% (n 9,644, close gross $7,014.53, mid gross $1,138.25) | -6.3% (n 3,112, close gross $501.94, mid gross $-31.75) | 80.9% (n 890, close gross $594.19, mid gross $480.77) |

#### B - C, per fill
B minus C over twice the notional of the filled matched trades, in bp, as a check that the gap between B and C is the spread and depth cost (fees can differ; plus-minus 1 minute and proxy rows are priced off the close). The cost decomposition of costs_analysis for the same trades is in the log next to each line.
| run | B - C bp per fill (ctxs + G8 fallback) | costs_analysis mean cost per leg-fill, bp (same trades) |
|---|---|---|
| vault open10 maker | 6.01 | 2.72 |
| vault open10 taker | 4.69 | 5.39 |
| vault open20 maker | 6.03 | 2.65 |
| vault open20 taker | 4.66 | 5.27 |
| test open10 maker | 6.36 | 4.43 |
| test open10 taker | 7.34 | 8.90 |
| test open20 maker | 8.14 | 5.52 |
| test open20 taker | 7.72 | 9.25 |
For taker runs B - C differs from the leg cost by 0.6 to 0.7 bp in the vault and 1.5 to 1.6 bp in test. For maker runs B - C is about twice the leg cost, because C also includes maker legs that were crossed as taker after the window, taker exits for timeouts and the adverse selection of the fills. The second column is read from the log of costs_nobounce.py (the costs_analysis decomposition on the same matched filled trades).

### Entry stretch: |z| from closes vs from mids (sigma)
Gap share = sum(|z| - |z_mid|) / sum(|z|) on events that have the entry mid of both legs. Fresh = both entry closes had a trade in that minute; only that stratum's gap may be called bounce (an upper bound, see notes). Stale gap is stale price.
| period | set | events | mean abs z | mean abs z_mid | gap share | gap share, fresh | gap share, stale | no stretch in mid terms |
|---|---|---|---|---|---|---|---|---|
| vault | all events | 1,006,960 | 2.581 | 2.566 | 0.6% | 0.3% | 1.5% | 0.0% |
| vault | q1% picks | 10,963 | 2.177 | 2.112 | 3.0% | 0.8% | 6.8% | 0.3% |
| test | all events | 3,076,124 | 2.579 | 2.537 | 1.6% | 0.5% | 3.2% | 0.1% |
| test | q1% picks | 35,515 | 2.159 | 1.944 | 10.0% | 2.3% | 15.5% | 1.5% |

Picks by tier (gap share, fresh / stale):
| period | tier | picks | gap share | fresh | stale |
|---|---|---|---|---|---|
| vault | least liquid third | 7,087 | 4.3% | 1.0% | 8.3% |
| vault | middle third | 2,984 | 0.7% | 0.5% | 1.4% |
| vault | most liquid third | 892 | 0.5% | 0.4% | 1.5% |
| test | least liquid third | 24,434 | 13.5% | 3.3% | 18.0% |
| test | middle third | 8,445 | 2.5% | 1.3% | 4.3% |
| test | most liquid third | 2,636 | 1.4% | 1.1% | 2.7% |

### Reversion in mid terms
Reach = the spread got back to mu within the horizon. The close is tested only on the minutes where the mid exists (same-minutes comparator, decided after a smoke run found the missing minutes bias the mid reach down); the close on all minutes is the last column. Mean gross move in sigma at the horizon, close (same minute) and mid. Events already through mu at entry in mid terms count as not reached.
| period | set | horizon | events | reach close (same minutes) | reach mid | reach close (all minutes) | gross move close | gross move mid | events through mu at entry (mid) |
|---|---|---|---|---|---|---|---|---|---|
| vault | q1% picks | 2 h | 10,963 | 33.4% | 31.4% | 33.9% | 0.227 | 0.173 | 0.3% |
| vault | q1% picks | 5 h | 10,963 | 53.2% | 51.1% | 54.9% | 0.369 | 0.308 | 0.3% |
| vault | q1% picks | 10 h | 10,963 | 65.6% | 63.9% | 68.4% | 0.345 | 0.277 | 0.3% |
| vault | all events | 2 h | 1,006,960 | 7.0% | 6.8% | 7.1% | 0.095 | 0.082 | 0.0% |
| vault | all events | 5 h | 1,006,960 | 18.8% | 18.4% | 19.5% | 0.163 | 0.149 | 0.0% |
| vault | all events | 10 h | 1,006,960 | 31.1% | 30.6% | 33.0% | 0.153 | 0.138 | 0.0% |
| test | q1% picks | 2 h | 35,515 | 34.7% | 28.9% | 34.7% | 0.184 | -0.027 | 1.5% |
| test | q1% picks | 5 h | 35,515 | 54.7% | 48.2% | 54.7% | 0.211 | -0.001 | 1.5% |
| test | q1% picks | 10 h | 35,515 | 67.7% | 61.9% | 67.7% | 0.170 | -0.027 | 1.5% |
| test | all events | 2 h | 3,076,124 | 7.5% | 6.7% | 7.5% | 0.059 | 0.018 | 0.1% |
| test | all events | 5 h | 3,076,124 | 19.4% | 18.1% | 19.4% | 0.078 | 0.037 | 0.1% |
| test | all events | 10 h | 3,076,124 | 32.8% | 31.2% | 32.8% | 0.100 | 0.059 | 0.1% |

Picks, 10 h, by tier:
| period | tier | picks | reach close (same minutes) | reach mid | gross move close | gross move mid |
|---|---|---|---|---|---|---|
| vault | least liquid third | 7,087 | 65.5% | 63.1% | 0.350 | 0.257 |
| vault | middle third | 2,984 | 65.3% | 64.5% | 0.330 | 0.309 |
| vault | most liquid third | 892 | 68.3% | 67.9% | 0.359 | 0.331 |
| test | least liquid third | 24,434 | 68.2% | 60.7% | 0.202 | -0.066 |
| test | middle third | 8,445 | 66.0% | 63.9% | 0.037 | -0.012 |
| test | most liquid third | 2,636 | 68.2% | 67.0% | 0.310 | 0.276 |

### Does p still rank in mid terms
10-hour reach rate by quintile of raw p_10h (1 = lowest), close (same minutes) vs mid, and the lift at the top 1% (reach of the q 1% picks / reach of all events). Test months pool the predictions of different fold models.
| period | q1 close / mid | q2 | q3 | q4 | q5 | lift top 1%, close | lift top 1%, mid |
|---|---|---|---|---|---|---|---|
| vault | 13.4% / 13.3% | 22.0% / 21.6% | 30.0% / 29.5% | 38.7% / 38.1% | 51.3% / 50.3% | 2.11x | 2.09x |
| test | 14.2% / 13.8% | 23.5% / 22.6% | 31.8% / 30.5% | 40.6% / 38.8% | 53.7% / 50.4% | 2.07x | 1.98x |

### Coverage and the two mids
Share of events without the entry mid of both legs (ctxs cache), by month:
| period | month | events | no mid |
|---|---|---|---|
| vault | 2026-07 | 261,717 | 0.0% |
| vault | 2026-08 | 426,713 | 8.4% |
| vault | 2026-09 | 416,082 | 28.9% |
| vault | 2026-10 | 175,576 | 66.5% |
| test | 2025-12 | 170,090 | 0.0% |
| test | 2026-01 | 484,058 | 0.0% |
| test | 2026-02 | 447,658 | 0.0% |
| test | 2026-03 | 500,646 | 0.0% |
| test | 2026-04 | 476,855 | 0.0% |
| test | 2026-05 | 452,664 | 1.9% |
| test | 2026-06 | 418,460 | 0.0% |
| test | 2026-07 | 146,629 | 8.3% |

Trades with all four mids, ctxs only vs with the G8 fallback (all four run files):
| run | trades | coverage, ctxs only | coverage, with fallback |
|---|---|---|---|
| vault open10 maker | 3,832 | 74.6% | 99.9% |
| vault open10 taker | 3,789 | 74.8% | 99.8% |
| vault open20 maker | 6,590 | 74.7% | 99.9% |
| vault open20 taker | 6,513 | 74.7% | 99.9% |
| test open10 maker | 8,069 | 99.2% | 99.6% |
| test open10 taker | 8,078 | 99.2% | 99.6% |
| test open20 maker | 13,735 | 99.2% | 99.6% |
| test open20 taker | 13,699 | 99.2% | 99.6% |

ctxs mid vs G8 table mid on the (coin, minute) pairs both have, in bp:
| period | tier | pairs | median | p90 | p99 | share within 1 bp |
|---|---|---|---|---|---|---|
| vault | ALL | 311,190 | 0.768 | 7.11 | 29.67 | 55.0% |
| vault | least liquid third | 129,518 | 1.240 | 11.61 | 30.58 | 47.3% |
| vault | middle third | 95,032 | 0.622 | 5.48 | 16.52 | 58.9% |
| vault | most liquid third | 86,640 | 0.518 | 4.20 | 12.63 | 62.1% |
| test | ALL | 837,043 | 0.058 | 3.90 | 30.77 | 78.3% |
| test | least liquid third | 363,041 | 0.089 | 9.78 | 33.44 | 70.8% |
| test | middle third | 241,780 | 0.063 | 2.02 | 9.74 | 82.9% |
| test | most liquid third | 232,222 | 0.000 | 1.48 | 6.12 | 85.3% |

Receipts: close-based reach and time to mu recomputed by the script equal labels.parquet on every event of both periods (counts in the log); the saved gross is reproduced from the cleaned closes on every trade of the eight runs; the close |z| equals the saved |z|.

### Notes (what the numbers are and are not)
- The signal is still built from closes. A signal built from mids is NOT tested here.
- The engine's close is the last trade, which can be older than the mid snapshot. 'Fresh' means a trade in that minute, not at the end of it, so a fresh close can still be up to 59 seconds older than the mid. The fresh stratum's gap is therefore an upper bound on bounce, and the stale stratum's gap is stale price.
- The ctxs mid and the G8 table mid disagree by more than 1 bp on a large share of minutes (table above). Either one is a few seconds after the bar's last trade. The fallback mixes the two sources inside some trades. Results with the fallback and without it differ, and the ctxs-only set leans to the earlier months.
- The same-minutes close comparator was decided after a smoke run of about 3,000 vault events. Process, from this session's own transcript timestamps (UTC, diagnostics/costs_process_times.py): the planner's rulings on the G8 fallback, the gross-ratio bands and the 'close vs mid gap' label reached the builder at 2026-11-18T05:07:36.480Z; the first smoke run (event-level statistics only, no trade table) first appears in the transcript at 2026-11-18T05:10:27.547Z; the smoke run that first printed the vault trade table (it ran the rewritten reprice()) first appears in the transcript at 2026-11-18T05:11:16.812Z. The rulings came first. The 25% and 75% band values were in the original brief.
- Test-month quintiles pool the predictions of different fold models.
- Findings are reported, not acted on. No pick, exit or parameter was changed.

## 9. One-leg check: is the profit mostly generated by one leg?

Left out here to keep the report readable: the raw-version mover split, and all splits in mid prices. They are in logs/costs1/costs_legs_section.md.

Source: logs/costs1/costs_legs.json (sha256 9872148e012a), written by diagnostics/costs_legs.py; the log is diagnostics/costs_legs.log. Rules: costs1_rules.md section 11. This section is written by diagnostics/costs_legs_section.py; no number is typed by hand.

### What is measured
Gross profit of each leg of every saved trade (q 1% / no stop; the eight headline runs), from the prices between the entry and the exit: leg gross = leg dollars x direction x (price change). The two legs add up to the saved gross of the trade (receipts below). 'Close' uses the cleaned 1-minute closes the engine used. 'Mid' uses the exchange mid with the order-book table mid as the labelled fallback, on the trades with all four mids (same rules as the no-bounce section). Share = leg group's gross / the trade gross of the same set of trades.
The mover is the leg whose 60-minute move before entry moved the spread more. Headline definition is beta-adjusted (|r60 of A| against |beta| x |r60 of B|); the raw version (larger |r60|) is printed beside it. Larger vs smaller leg is the same split as |beta| < 1 vs |beta| > 1.

### Receipts
| run | trades | max abs diff, legs vs saved gross ($) | max relative deviation, saved fee vs rate x USD | trades with all four mids | mid legs total | section 10 mid gross | same-direction pairs (beta < 0) |
|---|---|---|---|---|---|---|---|
| vault open10 maker | 3,832 | 0.0e+00 | 2.2e-16 | 3,827 | $744.55 | $744.55 | 21.5% |
| vault open10 taker | 3,789 | 0.0e+00 | 2.2e-16 | 3,783 | $508.34 | $508.34 | 20.9% |
| vault open20 maker | 6,590 | 0.0e+00 | 2.2e-16 | 6,581 | $1,645.99 | $1,645.99 | 22.7% |
| vault open20 taker | 6,513 | 0.0e+00 | 2.2e-16 | 6,504 | $876.08 | $876.08 | 22.0% |
| test open10 maker | 8,069 | 0.0e+00 | 2.2e-16 | 8,033 | $1,157.54 | $1,157.54 | 14.6% |
| test open10 taker | 8,078 | 0.0e+00 | 2.2e-16 | 8,042 | $618.59 | $618.59 | 14.7% |
| test open20 maker | 13,735 | 0.0e+00 | 2.2e-16 | 13,682 | $3,916.29 | $3,916.29 | 14.7% |
| test open20 taker | 13,699 | 0.0e+00 | 2.2e-16 | 13,646 | $1,587.26 | $1,587.26 | 14.8% |

Coverage of trades with all four mids (ctxs + G8 fallback), by entry month and by tier (vault months, then test months):
| run | 2026-07 | 2026-08 | 2026-09 | 2026-10 | least liquid third | middle third | most liquid third |
|---|---|---|---|---|---|---|---|
| vault open10 maker | 100.0% | 99.9% | 99.8% | 99.6% | 99.9% | 100.0% | 99.0% |
| vault open10 taker | 100.0% | 99.9% | 99.8% | 99.4% | 99.9% | 100.0% | 99.0% |
| vault open20 maker | 100.0% | 99.8% | 99.9% | 99.6% | 99.9% | 99.9% | 99.2% |
| vault open20 taker | 100.0% | 99.9% | 99.9% | 99.5% | 99.9% | 99.9% | 99.2% |

| run | 2025-12 | 2026-01 | 2026-02 | 2026-03 | 2026-04 | 2026-05 | 2026-06 | 2026-07 | least liquid third | middle third | most liquid third |
|---|---|---|---|---|---|---|---|---|---|---|---|
| test open10 maker | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 91.0% | 99.6% | 99.7% | 98.9% |
| test open10 taker | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 91.1% | 99.6% | 99.6% | 99.1% |
| test open20 maker | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 92.4% | 99.7% | 99.6% | 99.0% |
| test open20 taker | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 92.3% | 99.7% | 99.6% | 99.0% |

### Split: long vs short (close prices)
Total gross of each leg group over all its legs, and its share of the trade gross of the same set (n/m = not meaningful: the group's trade gross is zero or negative or under 5% of the run's gross; the dollars are kept). Groups: all trades, the trade's least liquid tier, and each exit reason found.
| run | group | trades | trade gross | long total | long mean per leg | long share | short total | short mean per leg | short share |
|---|---|---|---|---|---|---|---|---|---|
| vault open10 maker | ALL | 3,832 | $1,358.79 | $1,004.64 | $0.26 | 73.9% | $354.15 | $0.09 | 26.1% |
| vault open10 maker | least liquid third | 2,549 | $1,064.30 | $549.10 | $0.22 | 51.6% | $515.20 | $0.20 | 48.4% |
| vault open10 maker | middle third | 977 | $146.63 | $280.14 | $0.29 | 191.1% | $-133.51 | $-0.13 | -91.1% |
| vault open10 maker | most liquid third | 306 | $147.86 | $175.40 | $0.56 | 118.6% | $-27.53 | $-0.09 | -18.6% |
| vault open10 maker | exit mu | 2,721 | $4,538.64 | $2,346.55 | $0.87 | 51.7% | $2,192.09 | $0.80 | 48.3% |
| vault open10 maker | exit timeout | 1,111 | $-3,179.85 | $-1,341.92 | $-1.19 | n/m | $-1,837.93 | $-1.67 | n/m |
| vault open10 taker | ALL | 3,789 | $932.87 | $574.86 | $0.15 | 61.6% | $358.01 | $0.09 | 38.4% |
| vault open10 taker | least liquid third | 2,510 | $734.26 | $372.89 | $0.15 | 50.8% | $361.37 | $0.14 | 49.2% |
| vault open10 taker | middle third | 976 | $206.37 | $187.87 | $0.19 | 91.0% | $18.50 | $0.02 | 9.0% |
| vault open10 taker | most liquid third | 303 | $-7.76 | $14.10 | $0.04 | n/m | $-21.85 | $-0.08 | n/m |
| vault open10 taker | exit mu | 2,673 | $3,366.22 | $1,637.37 | $0.62 | 48.6% | $1,728.84 | $0.64 | 51.4% |
| vault open10 taker | exit timeout | 1,116 | $-2,433.35 | $-1,062.51 | $-0.94 | n/m | $-1,370.83 | $-1.25 | n/m |
| vault open20 maker | ALL | 6,590 | $3,010.10 | $1,855.30 | $0.28 | 61.6% | $1,154.80 | $0.18 | 38.4% |
| vault open20 maker | least liquid third | 4,358 | $2,487.01 | $1,256.61 | $0.29 | 50.5% | $1,230.40 | $0.28 | 49.5% |
| vault open20 maker | middle third | 1,713 | $391.39 | $452.53 | $0.26 | 115.6% | $-61.14 | $-0.04 | -15.6% |
| vault open20 maker | most liquid third | 519 | $131.70 | $146.16 | $0.28 | n/m | $-14.46 | $-0.03 | n/m |
| vault open20 maker | exit mu | 4,627 | $10,430.43 | $5,223.47 | $1.14 | 50.1% | $5,206.96 | $1.12 | 49.9% |
| vault open20 maker | exit timeout | 1,963 | $-7,420.33 | $-3,368.17 | $-1.69 | n/m | $-4,052.16 | $-2.09 | n/m |
| vault open20 taker | ALL | 6,513 | $1,626.08 | $975.60 | $0.15 | 60.0% | $650.47 | $0.10 | 40.0% |
| vault open20 taker | least liquid third | 4,329 | $1,325.26 | $593.73 | $0.14 | 44.8% | $731.53 | $0.17 | 55.2% |
| vault open20 taker | middle third | 1,676 | $346.23 | $310.79 | $0.18 | 89.8% | $35.44 | $0.02 | 10.2% |
| vault open20 taker | most liquid third | 508 | $-45.42 | $71.08 | $0.14 | n/m | $-116.50 | $-0.23 | n/m |
| vault open20 taker | exit mu | 4,548 | $6,114.17 | $3,034.13 | $0.67 | 49.6% | $3,080.04 | $0.68 | 50.4% |
| vault open20 taker | exit timeout | 1,965 | $-4,488.09 | $-2,058.52 | $-1.04 | n/m | $-2,429.57 | $-1.25 | n/m |
| test open10 maker | ALL | 8,069 | $5,122.67 | $2,545.26 | $0.32 | 49.7% | $2,577.42 | $0.32 | 50.3% |
| test open10 maker | least liquid third | 5,748 | $4,216.15 | $1,875.88 | $0.33 | 44.5% | $2,340.28 | $0.40 | 55.5% |
| test open10 maker | middle third | 1,782 | $631.67 | $632.58 | $0.35 | 100.1% | $-0.91 | $-0.00 | -0.1% |
| test open10 maker | most liquid third | 539 | $274.85 | $36.80 | $0.07 | 13.4% | $238.05 | $0.43 | 86.6% |
| test open10 maker | exit mu | 5,714 | $15,362.49 | $7,368.48 | $1.30 | 48.0% | $7,994.01 | $1.39 | 52.0% |
| test open10 maker | exit timeout | 2,355 | $-10,239.82 | $-4,823.22 | $-2.06 | n/m | $-5,416.60 | $-2.28 | n/m |
| test open10 taker | ALL | 8,078 | $3,135.27 | $1,485.10 | $0.19 | 47.4% | $1,650.17 | $0.20 | 52.6% |
| test open10 taker | least liquid third | 5,752 | $2,673.81 | $1,152.91 | $0.20 | 43.1% | $1,520.90 | $0.26 | 56.9% |
| test open10 taker | middle third | 1,797 | $360.22 | $353.72 | $0.19 | 98.2% | $6.50 | $0.00 | 1.8% |
| test open10 taker | most liquid third | 529 | $101.24 | $-21.53 | $-0.04 | n/m | $122.77 | $0.23 | n/m |
| test open10 taker | exit mu | 5,707 | $9,488.78 | $4,523.58 | $0.80 | 47.7% | $4,965.20 | $0.86 | 52.3% |
| test open10 taker | exit timeout | 2,371 | $-6,353.51 | $-3,038.48 | $-1.29 | n/m | $-3,315.03 | $-1.39 | n/m |
| test open20 maker | ALL | 13,735 | $20,570.67 | $10,978.32 | $0.81 | 53.4% | $9,592.34 | $0.69 | 46.6% |
| test open20 maker | least liquid third | 9,704 | $18,027.67 | $8,460.22 | $0.88 | 46.9% | $9,567.45 | $0.97 | 53.1% |
| test open20 maker | middle third | 3,123 | $1,444.97 | $2,219.94 | $0.71 | 153.6% | $-774.97 | $-0.25 | -53.6% |
| test open20 maker | most liquid third | 908 | $1,098.02 | $298.16 | $0.33 | 27.2% | $799.87 | $0.87 | 72.8% |
| test open20 maker | exit mu | 9,620 | $67,577.23 | $33,342.51 | $3.50 | 49.3% | $34,234.72 | $3.52 | 50.7% |
| test open20 maker | exit timeout | 4,115 | $-47,006.57 | $-22,364.19 | $-5.50 | n/m | $-24,642.38 | $-5.92 | n/m |
| test open20 taker | ALL | 13,699 | $8,126.25 | $3,993.01 | $0.30 | 49.1% | $4,133.24 | $0.30 | 50.9% |
| test open20 taker | least liquid third | 9,677 | $7,003.27 | $3,279.27 | $0.34 | 46.8% | $3,724.01 | $0.38 | 53.2% |
| test open20 taker | middle third | 3,123 | $517.51 | $638.22 | $0.21 | 123.3% | $-120.70 | $-0.04 | -23.3% |
| test open20 taker | most liquid third | 899 | $605.46 | $75.53 | $0.09 | 12.5% | $529.94 | $0.58 | 87.5% |
| test open20 taker | exit mu | 9,584 | $25,238.88 | $12,225.96 | $1.29 | 48.4% | $13,012.92 | $1.34 | 51.6% |
| test open20 taker | exit timeout | 4,115 | $-17,112.63 | $-8,232.95 | $-2.03 | n/m | $-8,879.68 | $-2.13 | n/m |

### Split: mover vs hedge (beta-adjusted, HEADLINE) (close prices)
Total gross of each leg group over all its legs, and its share of the trade gross of the same set (n/m = not meaningful: the group's trade gross is zero or negative or under 5% of the run's gross; the dollars are kept). Groups: all trades, the trade's least liquid tier, and each exit reason found.
| run | group | trades | trade gross | mover total | mover mean per leg | mover share | hedge total | hedge mean per leg | hedge share |
|---|---|---|---|---|---|---|---|---|---|
| vault open10 maker | ALL | 3,832 | $1,358.79 | $954.52 | $0.25 | 70.2% | $403.33 | $0.11 | 29.7% |
| vault open10 maker | least liquid third | 2,549 | $1,064.30 | $679.25 | $0.27 | 63.8% | $384.11 | $0.15 | 36.1% |
| vault open10 maker | middle third | 977 | $146.63 | $188.33 | $0.19 | 128.4% | $-41.71 | $-0.04 | -28.4% |
| vault open10 maker | most liquid third | 306 | $147.86 | $86.94 | $0.28 | 58.8% | $60.92 | $0.20 | 41.2% |
| vault open10 maker | exit mu | 2,721 | $4,538.64 | $3,041.09 | $1.12 | 67.0% | $1,496.61 | $0.55 | 33.0% |
| vault open10 maker | exit timeout | 1,111 | $-3,179.85 | $-2,086.57 | $-1.88 | n/m | $-1,093.28 | $-0.98 | n/m |
| vault open10 taker | ALL | 3,789 | $932.87 | $666.51 | $0.18 | 71.4% | $265.64 | $0.07 | 28.5% |
| vault open10 taker | least liquid third | 2,510 | $734.26 | $481.85 | $0.19 | 65.6% | $251.69 | $0.10 | 34.3% |
| vault open10 taker | middle third | 976 | $206.37 | $222.16 | $0.23 | 107.7% | $-15.79 | $-0.02 | -7.7% |
| vault open10 taker | most liquid third | 303 | $-7.76 | $-37.50 | $-0.12 | n/m | $29.74 | $0.10 | n/m |
| vault open10 taker | exit mu | 2,673 | $3,366.22 | $2,285.28 | $0.86 | 67.9% | $1,080.22 | $0.40 | 32.1% |
| vault open10 taker | exit timeout | 1,116 | $-2,433.35 | $-1,618.77 | $-1.45 | n/m | $-814.58 | $-0.73 | n/m |
| vault open20 maker | ALL | 6,590 | $3,010.10 | $2,183.48 | $0.33 | 72.5% | $825.46 | $0.13 | 27.4% |
| vault open20 maker | least liquid third | 4,358 | $2,487.01 | $1,664.10 | $0.38 | 66.9% | $821.74 | $0.19 | 33.0% |
| vault open20 maker | middle third | 1,713 | $391.39 | $508.66 | $0.30 | 130.0% | $-117.27 | $-0.07 | -30.0% |
| vault open20 maker | most liquid third | 519 | $131.70 | $10.72 | $0.02 | n/m | $120.98 | $0.23 | n/m |
| vault open20 maker | exit mu | 4,627 | $10,430.43 | $6,991.46 | $1.51 | 67.0% | $3,437.80 | $0.74 | 33.0% |
| vault open20 maker | exit timeout | 1,963 | $-7,420.33 | $-4,807.98 | $-2.45 | n/m | $-2,612.35 | $-1.33 | n/m |
| vault open20 taker | ALL | 6,513 | $1,626.08 | $1,229.41 | $0.19 | 75.6% | $395.93 | $0.06 | 24.3% |
| vault open20 taker | least liquid third | 4,329 | $1,325.26 | $900.92 | $0.21 | 68.0% | $423.60 | $0.10 | 32.0% |
| vault open20 taker | middle third | 1,676 | $346.23 | $370.96 | $0.22 | 107.1% | $-24.74 | $-0.01 | -7.1% |
| vault open20 taker | most liquid third | 508 | $-45.42 | $-42.48 | $-0.08 | n/m | $-2.94 | $-0.01 | n/m |
| vault open20 taker | exit mu | 4,548 | $6,114.17 | $4,137.71 | $0.91 | 67.7% | $1,975.72 | $0.43 | 32.3% |
| vault open20 taker | exit timeout | 1,965 | $-4,488.09 | $-2,908.30 | $-1.48 | n/m | $-1,579.79 | $-0.80 | n/m |
| test open10 maker | ALL | 8,069 | $5,122.67 | $2,870.64 | $0.36 | 56.0% | $2,252.03 | $0.28 | 44.0% |
| test open10 maker | least liquid third | 5,748 | $4,216.15 | $2,049.93 | $0.36 | 48.6% | $2,166.22 | $0.38 | 51.4% |
| test open10 maker | middle third | 1,782 | $631.67 | $549.93 | $0.31 | 87.1% | $81.74 | $0.05 | 12.9% |
| test open10 maker | most liquid third | 539 | $274.85 | $270.78 | $0.50 | 98.5% | $4.07 | $0.01 | 1.5% |
| test open10 maker | exit mu | 5,714 | $15,362.49 | $9,828.10 | $1.72 | 64.0% | $5,534.39 | $0.97 | 36.0% |
| test open10 maker | exit timeout | 2,355 | $-10,239.82 | $-6,957.47 | $-2.95 | n/m | $-3,282.35 | $-1.39 | n/m |
| test open10 taker | ALL | 8,078 | $3,135.27 | $1,815.20 | $0.22 | 57.9% | $1,320.07 | $0.16 | 42.1% |
| test open10 taker | least liquid third | 5,752 | $2,673.81 | $1,383.60 | $0.24 | 51.7% | $1,290.21 | $0.22 | 48.3% |
| test open10 taker | middle third | 1,797 | $360.22 | $309.55 | $0.17 | 85.9% | $50.66 | $0.03 | 14.1% |
| test open10 taker | most liquid third | 529 | $101.24 | $122.05 | $0.23 | n/m | $-20.80 | $-0.04 | n/m |
| test open10 taker | exit mu | 5,707 | $9,488.78 | $6,117.58 | $1.07 | 64.5% | $3,371.20 | $0.59 | 35.5% |
| test open10 taker | exit timeout | 2,371 | $-6,353.51 | $-4,302.37 | $-1.81 | n/m | $-2,051.13 | $-0.87 | n/m |
| test open20 maker | ALL | 13,735 | $20,570.67 | $13,072.69 | $0.95 | 63.6% | $7,488.49 | $0.55 | 36.4% |
| test open20 maker | least liquid third | 9,704 | $18,027.67 | $10,294.74 | $1.06 | 57.1% | $7,723.44 | $0.80 | 42.8% |
| test open20 maker | middle third | 3,123 | $1,444.97 | $1,587.15 | $0.51 | 109.8% | $-142.18 | $-0.05 | -9.8% |
| test open20 maker | most liquid third | 908 | $1,098.02 | $1,190.80 | $1.31 | 108.4% | $-92.77 | $-0.10 | -8.4% |
| test open20 maker | exit mu | 9,620 | $67,577.23 | $44,616.85 | $4.64 | 66.0% | $22,950.89 | $2.39 | 34.0% |
| test open20 maker | exit timeout | 4,115 | $-47,006.57 | $-31,544.17 | $-7.67 | n/m | $-15,462.40 | $-3.76 | n/m |
| test open20 taker | ALL | 13,699 | $8,126.25 | $4,935.77 | $0.36 | 60.7% | $3,186.52 | $0.23 | 39.2% |
| test open20 taker | least liquid third | 9,677 | $7,003.27 | $3,934.06 | $0.41 | 56.2% | $3,065.24 | $0.32 | 43.8% |
| test open20 taker | middle third | 3,123 | $517.51 | $507.26 | $0.16 | 98.0% | $10.25 | $0.00 | 2.0% |
| test open20 taker | most liquid third | 899 | $605.46 | $494.44 | $0.55 | 81.7% | $111.02 | $0.12 | 18.3% |
| test open20 taker | exit mu | 9,584 | $25,238.88 | $16,565.54 | $1.73 | 65.6% | $8,669.37 | $0.90 | 34.3% |
| test open20 taker | exit timeout | 4,115 | $-17,112.63 | $-11,629.77 | $-2.83 | n/m | $-5,482.86 | $-1.33 | n/m |

### Split: larger vs smaller leg (close prices)
Total gross of each leg group over all its legs, and its share of the trade gross of the same set (n/m = not meaningful: the group's trade gross is zero or negative or under 5% of the run's gross; the dollars are kept). Groups: all trades, the trade's least liquid tier, and each exit reason found.
| run | group | trades | trade gross | larger total | larger mean per leg | larger share | smaller total | smaller mean per leg | smaller share |
|---|---|---|---|---|---|---|---|---|---|
| vault open10 maker | ALL | 3,832 | $1,358.79 | $1,310.63 | $0.34 | 96.5% | $48.16 | $0.01 | 3.5% |
| vault open10 maker | least liquid third | 2,549 | $1,064.30 | $903.97 | $0.35 | 84.9% | $160.33 | $0.06 | 15.1% |
| vault open10 maker | middle third | 977 | $146.63 | $273.44 | $0.28 | 186.5% | $-126.81 | $-0.13 | -86.5% |
| vault open10 maker | most liquid third | 306 | $147.86 | $133.22 | $0.44 | 90.1% | $14.64 | $0.05 | 9.9% |
| vault open10 maker | exit mu | 2,721 | $4,538.64 | $3,597.21 | $1.32 | 79.3% | $941.43 | $0.35 | 20.7% |
| vault open10 maker | exit timeout | 1,111 | $-3,179.85 | $-2,286.58 | $-2.06 | n/m | $-893.27 | $-0.80 | n/m |
| vault open10 taker | ALL | 3,789 | $932.87 | $968.29 | $0.26 | 103.8% | $-35.42 | $-0.01 | -3.8% |
| vault open10 taker | least liquid third | 2,510 | $734.26 | $607.25 | $0.24 | 82.7% | $127.01 | $0.05 | 17.3% |
| vault open10 taker | middle third | 976 | $206.37 | $255.33 | $0.26 | 123.7% | $-48.96 | $-0.05 | -23.7% |
| vault open10 taker | most liquid third | 303 | $-7.76 | $105.72 | $0.35 | n/m | $-113.48 | $-0.37 | n/m |
| vault open10 taker | exit mu | 2,673 | $3,366.22 | $2,710.94 | $1.01 | 80.5% | $655.27 | $0.25 | 19.5% |
| vault open10 taker | exit timeout | 1,116 | $-2,433.35 | $-1,742.65 | $-1.56 | n/m | $-690.70 | $-0.62 | n/m |
| vault open20 maker | ALL | 6,590 | $3,010.10 | $2,981.25 | $0.45 | 99.0% | $28.85 | $0.00 | 1.0% |
| vault open20 maker | least liquid third | 4,358 | $2,487.01 | $2,346.96 | $0.54 | 94.4% | $140.05 | $0.03 | 5.6% |
| vault open20 maker | middle third | 1,713 | $391.39 | $448.06 | $0.26 | 114.5% | $-56.67 | $-0.03 | -14.5% |
| vault open20 maker | most liquid third | 519 | $131.70 | $186.23 | $0.36 | n/m | $-54.54 | $-0.11 | n/m |
| vault open20 maker | exit mu | 4,627 | $10,430.43 | $8,391.85 | $1.81 | 80.5% | $2,038.58 | $0.44 | 19.5% |
| vault open20 maker | exit timeout | 1,963 | $-7,420.33 | $-5,410.60 | $-2.76 | n/m | $-2,009.73 | $-1.02 | n/m |
| vault open20 taker | ALL | 6,513 | $1,626.08 | $1,600.15 | $0.25 | 98.4% | $25.93 | $0.00 | 1.6% |
| vault open20 taker | least liquid third | 4,329 | $1,325.26 | $1,150.10 | $0.27 | 86.8% | $175.17 | $0.04 | 13.2% |
| vault open20 taker | middle third | 1,676 | $346.23 | $363.88 | $0.22 | 105.1% | $-17.65 | $-0.01 | -5.1% |
| vault open20 taker | most liquid third | 508 | $-45.42 | $86.17 | $0.17 | n/m | $-131.59 | $-0.26 | n/m |
| vault open20 taker | exit mu | 4,548 | $6,114.17 | $4,823.61 | $1.06 | 78.9% | $1,290.56 | $0.28 | 21.1% |
| vault open20 taker | exit timeout | 1,965 | $-4,488.09 | $-3,223.46 | $-1.64 | n/m | $-1,264.64 | $-0.64 | n/m |
| test open10 maker | ALL | 8,069 | $5,122.67 | $3,699.71 | $0.46 | 72.2% | $1,422.96 | $0.18 | 27.8% |
| test open10 maker | least liquid third | 5,748 | $4,216.15 | $3,075.26 | $0.54 | 72.9% | $1,140.89 | $0.20 | 27.1% |
| test open10 maker | middle third | 1,782 | $631.67 | $623.67 | $0.35 | 98.7% | $8.00 | $0.00 | 1.3% |
| test open10 maker | most liquid third | 539 | $274.85 | $0.78 | $0.00 | 0.3% | $274.07 | $0.51 | 99.7% |
| test open10 maker | exit mu | 5,714 | $15,362.49 | $11,014.54 | $1.93 | 71.7% | $4,347.96 | $0.76 | 28.3% |
| test open10 maker | exit timeout | 2,355 | $-10,239.82 | $-7,314.83 | $-3.11 | n/m | $-2,924.99 | $-1.24 | n/m |
| test open10 taker | ALL | 8,078 | $3,135.27 | $2,087.99 | $0.26 | 66.6% | $1,047.28 | $0.13 | 33.4% |
| test open10 taker | least liquid third | 5,752 | $2,673.81 | $1,743.43 | $0.30 | 65.2% | $930.38 | $0.16 | 34.8% |
| test open10 taker | middle third | 1,797 | $360.22 | $424.17 | $0.24 | 117.8% | $-63.96 | $-0.04 | -17.8% |
| test open10 taker | most liquid third | 529 | $101.24 | $-79.61 | $-0.15 | n/m | $180.86 | $0.34 | n/m |
| test open10 taker | exit mu | 5,707 | $9,488.78 | $6,705.73 | $1.18 | 70.7% | $2,783.05 | $0.49 | 29.3% |
| test open10 taker | exit timeout | 2,371 | $-6,353.51 | $-4,617.74 | $-1.95 | n/m | $-1,735.77 | $-0.73 | n/m |
| test open20 maker | ALL | 13,735 | $20,570.67 | $15,374.38 | $1.12 | 74.7% | $5,196.29 | $0.38 | 25.3% |
| test open20 maker | least liquid third | 9,704 | $18,027.67 | $13,542.32 | $1.40 | 75.1% | $4,485.35 | $0.46 | 24.9% |
| test open20 maker | middle third | 3,123 | $1,444.97 | $1,471.02 | $0.47 | 101.8% | $-26.05 | $-0.01 | -1.8% |
| test open20 maker | most liquid third | 908 | $1,098.02 | $361.04 | $0.40 | 32.9% | $736.99 | $0.81 | 67.1% |
| test open20 maker | exit mu | 9,620 | $67,577.23 | $48,553.82 | $5.05 | 71.8% | $19,023.41 | $1.98 | 28.2% |
| test open20 maker | exit timeout | 4,115 | $-47,006.57 | $-33,179.44 | $-8.06 | n/m | $-13,827.12 | $-3.36 | n/m |
| test open20 taker | ALL | 13,699 | $8,126.25 | $5,620.09 | $0.41 | 69.2% | $2,506.16 | $0.18 | 30.8% |
| test open20 taker | least liquid third | 9,677 | $7,003.27 | $4,696.47 | $0.49 | 67.1% | $2,306.80 | $0.24 | 32.9% |
| test open20 taker | middle third | 3,123 | $517.51 | $571.33 | $0.18 | 110.4% | $-53.81 | $-0.02 | -10.4% |
| test open20 taker | most liquid third | 899 | $605.46 | $352.30 | $0.39 | 58.2% | $253.17 | $0.28 | 41.8% |
| test open20 taker | exit mu | 9,584 | $25,238.88 | $17,979.82 | $1.88 | 71.2% | $7,259.06 | $0.76 | 28.8% |
| test open20 taker | exit timeout | 4,115 | $-17,112.63 | $-12,359.72 | $-3.00 | n/m | $-4,752.90 | $-1.16 | n/m |

#### Long vs short on opposite-direction pairs only (close prices)
| run | trades | trade gross | long total | long share | short total | short share |
|---|---|---|---|---|---|---|
| vault open10 maker | 3,009 | $1,216.77 | $911.08 | 74.9% | $305.69 | 25.1% |
| vault open10 taker | 2,997 | $926.39 | $552.46 | 59.6% | $373.93 | 40.4% |
| vault open20 maker | 5,092 | $2,515.04 | $1,585.96 | 63.1% | $929.08 | 36.9% |
| vault open20 taker | 5,079 | $1,481.69 | $860.93 | 58.1% | $620.76 | 41.9% |
| test open10 maker | 6,888 | $4,420.76 | $2,154.25 | 48.7% | $2,266.51 | 51.3% |
| test open10 taker | 6,890 | $2,723.64 | $1,298.93 | 47.7% | $1,424.71 | 52.3% |
| test open20 maker | 11,718 | $19,427.65 | $10,714.99 | 55.2% | $8,712.66 | 44.8% |
| test open20 taker | 11,667 | $7,602.24 | $3,799.37 | 50.0% | $3,802.87 | 50.0% |

### One-leg trades
Among trades with gross > 0: how many have one leg above 100% of the trade gross (the other leg strictly negative), how many have one leg carrying all of it with the other flat, the share of the run's positive gross those trades carry, and which leg it was. Among trades with gross < 0: the share where one leg made money.
| run | prices | group | gross > 0 trades | one leg > 100% | share | share of positive gross | one leg, other flat | long / short leg (add up to the total only for opposite-direction pairs) | same-direction pairs among them | beta-adj. mover / hedge leg | larger / smaller leg | gross < 0 trades | one leg made money |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vault open10 maker | close | ALL | 2,888 | 1,392 | 48.2% | 46.5% | 89 | 724 / 668 | 150 | 884 / 507 | 993 / 399 | 944 | 508 (53.8%) |
| vault open10 maker | close | least liquid third | 1,948 | 930 | 47.7% | 45.8% | 83 | 476 / 454 | 91 | 580 / 349 | 650 / 280 | 601 | 341 (56.7%) |
| vault open10 maker | close | middle third | 707 | 340 | 48.1% | 46.6% | 5 | 177 / 163 | 47 | 233 / 107 | 254 / 86 | 270 | 132 (48.9%) |
| vault open10 maker | close | most liquid third | 233 | 122 | 52.4% | 49.5% | 1 | 71 / 51 | 12 | 71 / 51 | 89 / 33 | 73 | 35 (47.9%) |
| vault open10 maker | mid | ALL | 2,831 | 1,503 | 53.1% | 48.7% | 92 | 789 / 714 | 153 | 942 / 561 | 1,044 / 459 | 995 | 547 (55.0%) |
| vault open10 maker | mid | least liquid third | 1,890 | 1,029 | 54.4% | 49.3% | 89 | 533 / 496 | 96 | 628 / 401 | 691 / 338 | 656 | 380 (57.9%) |
| vault open10 maker | mid | middle third | 709 | 353 | 49.8% | 47.3% | 3 | 184 / 169 | 45 | 245 / 108 | 266 / 87 | 268 | 132 (49.3%) |
| vault open10 maker | mid | most liquid third | 232 | 121 | 52.2% | 49.2% | 0 | 72 / 49 | 12 | 69 / 52 | 87 / 34 | 71 | 35 (49.3%) |
| vault open10 taker | close | ALL | 2,839 | 1,374 | 48.4% | 46.4% | 88 | 688 / 686 | 145 | 883 / 490 | 988 / 386 | 950 | 517 (54.4%) |
| vault open10 taker | close | least liquid third | 1,906 | 918 | 48.2% | 46.2% | 83 | 456 / 462 | 88 | 576 / 341 | 645 / 273 | 604 | 345 (57.1%) |
| vault open10 taker | close | middle third | 714 | 345 | 48.3% | 46.3% | 4 | 170 / 175 | 46 | 239 / 106 | 258 / 87 | 262 | 131 (50.0%) |
| vault open10 taker | close | most liquid third | 219 | 111 | 50.7% | 47.7% | 1 | 62 / 49 | 11 | 68 / 43 | 85 / 26 | 84 | 41 (48.8%) |
| vault open10 taker | mid | ALL | 2,779 | 1,479 | 53.2% | 48.3% | 88 | 755 / 724 | 148 | 941 / 538 | 1,036 / 443 | 1,003 | 560 (55.8%) |
| vault open10 taker | mid | least liquid third | 1,845 | 1,009 | 54.7% | 49.3% | 85 | 511 / 498 | 91 | 623 / 386 | 682 / 327 | 661 | 386 (58.4%) |
| vault open10 taker | mid | middle third | 716 | 360 | 50.3% | 46.7% | 3 | 181 / 179 | 46 | 252 / 108 | 271 / 89 | 260 | 132 (50.8%) |
| vault open10 taker | mid | most liquid third | 218 | 110 | 50.5% | 47.6% | 0 | 63 / 47 | 11 | 66 / 44 | 83 / 27 | 82 | 42 (51.2%) |
| vault open20 maker | close | ALL | 4,927 | 2,367 | 48.0% | 46.6% | 142 | 1,183 / 1,184 | 282 | 1,534 / 832 | 1,701 / 666 | 1,663 | 907 (54.5%) |
| vault open20 maker | close | least liquid third | 3,300 | 1,577 | 47.8% | 46.1% | 131 | 786 / 791 | 167 | 1,013 / 563 | 1,116 / 461 | 1,058 | 594 (56.1%) |
| vault open20 maker | close | middle third | 1,243 | 597 | 48.0% | 46.4% | 10 | 298 / 299 | 95 | 402 / 195 | 443 / 154 | 470 | 242 (51.5%) |
| vault open20 maker | close | most liquid third | 384 | 193 | 50.3% | 49.9% | 1 | 99 / 94 | 20 | 119 / 74 | 142 / 51 | 135 | 71 (52.6%) |
| vault open20 maker | mid | ALL | 4,832 | 2,537 | 52.5% | 48.9% | 156 | 1,282 / 1,255 | 285 | 1,618 / 919 | 1,779 / 758 | 1,747 | 980 (56.1%) |
| vault open20 maker | mid | least liquid third | 3,201 | 1,722 | 53.8% | 49.9% | 146 | 868 / 854 | 171 | 1,083 / 639 | 1,175 / 547 | 1,151 | 671 (58.3%) |
| vault open20 maker | mid | middle third | 1,249 | 624 | 50.0% | 46.8% | 10 | 316 / 308 | 95 | 418 / 206 | 461 / 163 | 463 | 238 (51.4%) |
| vault open20 maker | mid | most liquid third | 382 | 191 | 50.0% | 49.2% | 0 | 98 / 93 | 19 | 117 / 74 | 143 / 48 | 133 | 71 (53.4%) |
| vault open20 taker | close | ALL | 4,843 | 2,324 | 48.0% | 45.5% | 145 | 1,158 / 1,166 | 264 | 1,505 / 818 | 1,662 / 662 | 1,670 | 919 (55.0%) |
| vault open20 taker | close | least liquid third | 3,254 | 1,563 | 48.0% | 45.5% | 134 | 770 / 793 | 156 | 999 / 563 | 1,093 / 470 | 1,075 | 605 (56.3%) |
| vault open20 taker | close | middle third | 1,223 | 583 | 47.7% | 44.9% | 10 | 294 / 289 | 89 | 397 / 186 | 433 / 150 | 453 | 241 (53.2%) |
| vault open20 taker | close | most liquid third | 366 | 178 | 48.6% | 47.0% | 1 | 94 / 84 | 19 | 109 / 69 | 136 / 42 | 142 | 73 (51.4%) |
| vault open20 taker | mid | ALL | 4,745 | 2,491 | 52.5% | 47.6% | 152 | 1,249 / 1,242 | 266 | 1,587 / 904 | 1,735 / 756 | 1,757 | 993 (56.5%) |
| vault open20 taker | mid | least liquid third | 3,155 | 1,708 | 54.1% | 49.0% | 143 | 847 / 861 | 161 | 1,068 / 640 | 1,150 / 558 | 1,168 | 678 (58.0%) |
| vault open20 taker | mid | middle third | 1,226 | 604 | 49.3% | 45.2% | 9 | 308 / 296 | 87 | 411 / 193 | 447 / 157 | 449 | 240 (53.5%) |
| vault open20 taker | mid | most liquid third | 364 | 179 | 49.2% | 46.9% | 0 | 94 / 85 | 18 | 108 / 71 | 138 / 41 | 140 | 75 (53.6%) |
| test open10 maker | close | ALL | 6,080 | 3,090 | 50.8% | 46.0% | 204 | 1,513 / 1,577 | 232 | 1,872 / 1,218 | 2,026 / 1,064 | 1,988 | 1,209 (60.8%) |
| test open10 maker | close | least liquid third | 4,385 | 2,162 | 49.3% | 45.2% | 189 | 1,040 / 1,122 | 155 | 1,279 / 883 | 1,394 / 768 | 1,362 | 835 (61.3%) |
| test open10 maker | close | middle third | 1,300 | 718 | 55.2% | 48.7% | 12 | 378 / 340 | 58 | 462 / 256 | 506 / 212 | 482 | 289 (60.0%) |
| test open10 maker | close | most liquid third | 395 | 210 | 53.2% | 45.6% | 3 | 95 / 115 | 19 | 131 / 79 | 126 / 84 | 144 | 85 (59.0%) |
| test open10 maker | mid | ALL | 5,716 | 3,398 | 59.4% | 50.0% | 204 | 1,687 / 1,711 | 233 | 2,060 / 1,338 | 2,219 / 1,179 | 2,314 | 1,454 (62.8%) |
| test open10 maker | mid | least liquid third | 4,041 | 2,403 | 59.5% | 50.2% | 196 | 1,175 / 1,228 | 156 | 1,431 / 972 | 1,542 / 861 | 1,680 | 1,074 (63.9%) |
| test open10 maker | mid | middle third | 1,286 | 777 | 60.4% | 50.9% | 5 | 408 / 369 | 57 | 496 / 281 | 544 / 233 | 490 | 295 (60.2%) |
| test open10 maker | mid | most liquid third | 389 | 218 | 56.0% | 46.6% | 3 | 104 / 114 | 20 | 133 / 85 | 133 / 85 | 144 | 85 (59.0%) |
| test open10 taker | close | ALL | 6,069 | 3,062 | 50.5% | 45.7% | 209 | 1,485 / 1,577 | 223 | 1,856 / 1,206 | 2,000 / 1,062 | 2,008 | 1,223 (60.9%) |
| test open10 taker | close | least liquid third | 4,375 | 2,141 | 48.9% | 44.5% | 195 | 1,017 / 1,124 | 151 | 1,260 / 881 | 1,367 / 774 | 1,376 | 841 (61.1%) |
| test open10 taker | close | middle third | 1,312 | 716 | 54.6% | 48.7% | 13 | 371 / 345 | 53 | 461 / 255 | 511 / 205 | 485 | 293 (60.4%) |
| test open10 taker | close | most liquid third | 382 | 205 | 53.7% | 47.4% | 1 | 97 / 108 | 19 | 135 / 70 | 122 / 83 | 147 | 89 (60.5%) |
| test open10 taker | mid | ALL | 5,706 | 3,377 | 59.2% | 49.8% | 194 | 1,655 / 1,722 | 219 | 2,057 / 1,320 | 2,199 / 1,178 | 2,334 | 1,467 (62.9%) |
| test open10 taker | mid | least liquid third | 4,029 | 2,386 | 59.2% | 49.6% | 187 | 1,149 / 1,237 | 147 | 1,422 / 964 | 1,522 / 864 | 1,697 | 1,083 (63.8%) |
| test open10 taker | mid | middle third | 1,299 | 778 | 59.9% | 50.8% | 4 | 401 / 377 | 52 | 499 / 279 | 551 / 227 | 491 | 296 (60.3%) |
| test open10 taker | mid | most liquid third | 378 | 213 | 56.3% | 48.3% | 3 | 105 / 108 | 20 | 136 / 77 | 126 / 87 | 146 | 88 (60.3%) |
| test open20 maker | close | ALL | 10,262 | 5,202 | 50.7% | 46.8% | 336 | 2,545 / 2,657 | 378 | 3,147 / 2,055 | 3,425 / 1,777 | 3,472 | 2,065 (59.5%) |
| test open20 maker | close | least liquid third | 7,361 | 3,619 | 49.2% | 45.9% | 312 | 1,750 / 1,869 | 250 | 2,148 / 1,471 | 2,348 / 1,271 | 2,342 | 1,408 (60.1%) |
| test open20 maker | close | middle third | 2,237 | 1,222 | 54.6% | 49.9% | 19 | 626 / 596 | 100 | 781 / 441 | 848 / 374 | 886 | 505 (57.0%) |
| test open20 maker | close | most liquid third | 664 | 361 | 54.4% | 46.0% | 5 | 169 / 192 | 28 | 218 / 143 | 229 / 132 | 244 | 152 (62.3%) |
| test open20 maker | mid | ALL | 9,687 | 5,713 | 59.0% | 50.3% | 323 | 2,798 / 2,915 | 374 | 3,481 / 2,232 | 3,747 / 1,966 | 3,990 | 2,440 (61.2%) |
| test open20 maker | mid | least liquid third | 6,817 | 4,030 | 59.1% | 50.7% | 308 | 1,958 / 2,072 | 243 | 2,417 / 1,613 | 2,600 / 1,430 | 2,849 | 1,772 (62.2%) |
| test open20 maker | mid | middle third | 2,216 | 1,309 | 59.1% | 51.2% | 12 | 658 / 651 | 101 | 842 / 467 | 908 / 401 | 896 | 516 (57.6%) |
| test open20 maker | mid | most liquid third | 654 | 374 | 57.2% | 46.2% | 3 | 182 / 192 | 30 | 222 / 152 | 239 / 135 | 245 | 152 (62.0%) |
| test open20 taker | close | ALL | 10,219 | 5,170 | 50.6% | 46.2% | 339 | 2,510 / 2,660 | 367 | 3,138 / 2,032 | 3,403 / 1,767 | 3,479 | 2,082 (59.8%) |
| test open20 taker | close | least liquid third | 7,323 | 3,586 | 49.0% | 44.9% | 313 | 1,721 / 1,865 | 242 | 2,131 / 1,455 | 2,313 / 1,273 | 2,353 | 1,419 (60.3%) |
| test open20 taker | close | middle third | 2,233 | 1,220 | 54.6% | 49.8% | 22 | 620 / 600 | 97 | 780 / 440 | 860 / 360 | 890 | 515 (57.9%) |
| test open20 taker | close | most liquid third | 663 | 364 | 54.9% | 47.3% | 4 | 169 / 195 | 28 | 227 / 137 | 230 / 134 | 236 | 148 (62.7%) |
| test open20 taker | mid | ALL | 9,645 | 5,681 | 58.9% | 49.9% | 327 | 2,765 / 2,916 | 364 | 3,470 / 2,211 | 3,725 / 1,956 | 3,995 | 2,449 (61.3%) |
| test open20 taker | mid | least liquid third | 6,777 | 4,007 | 59.1% | 50.0% | 312 | 1,931 / 2,076 | 235 | 2,408 / 1,599 | 2,571 / 1,436 | 2,861 | 1,781 (62.3%) |
| test open20 taker | mid | middle third | 2,213 | 1,295 | 58.5% | 50.8% | 12 | 652 / 643 | 99 | 830 / 465 | 913 / 382 | 899 | 522 (58.1%) |
| test open20 taker | mid | most liquid third | 655 | 379 | 57.9% | 47.6% | 3 | 182 / 197 | 30 | 232 / 147 | 241 / 138 | 235 | 146 (62.1%) |

### Leg signs
Up = leg gross > 0, down = < 0, flat = exactly 0. Trades and total gross per pair of leg signs, close prices and mid prices.
| run | prices | up + up | down + down | flat + flat | up + down | up + flat | down + flat |
|---|---|---|---|---|---|---|---|
| vault open10 maker | close | 1,407 trades, $2,371.57 | 423 trades, $-2,047.69 | 0 trades, $0.00 | 1,900 trades, $941.47 | 89 trades, $118.85 | 13 trades, $-25.41 |
| vault open10 maker | mid | 1,236 trades, $2,007.22 | 431 trades, $-2,026.52 | 1 trades, $0.00 | 2,050 trades, $716.64 | 92 trades, $73.79 | 17 trades, $-26.58 |
| vault open10 taker | close | 1,377 trades, $1,771.66 | 421 trades, $-1,591.00 | 0 trades, $0.00 | 1,891 trades, $687.71 | 88 trades, $81.50 | 12 trades, $-17.00 |
| vault open10 taker | mid | 1,212 trades, $1,522.95 | 424 trades, $-1,566.59 | 1 trades, $0.00 | 2,039 trades, $531.27 | 88 trades, $52.08 | 19 trades, $-31.37 |
| vault open20 maker | close | 2,418 trades, $5,464.71 | 732 trades, $-4,797.61 | 0 trades, $0.00 | 3,274 trades, $2,156.70 | 142 trades, $253.72 | 24 trades, $-67.42 |
| vault open20 maker | mid | 2,139 trades, $4,633.59 | 740 trades, $-4,769.89 | 2 trades, $0.00 | 3,517 trades, $1,677.39 | 156 trades, $176.25 | 27 trades, $-71.36 |
| vault open20 taker | close | 2,374 trades, $3,274.51 | 729 trades, $-2,950.46 | 0 trades, $0.00 | 3,243 trades, $1,186.86 | 145 trades, $150.92 | 22 trades, $-35.77 |
| vault open20 taker | mid | 2,102 trades, $2,818.58 | 734 trades, $-2,914.90 | 2 trades, $0.00 | 3,484 trades, $928.38 | 152 trades, $102.85 | 30 trades, $-58.83 |
| test open10 maker | close | 2,786 trades, $8,014.32 | 750 trades, $-5,738.21 | 1 trades, $0.00 | 4,299 trades, $2,411.54 | 204 trades, $497.46 | 29 trades, $-62.43 |
| test open10 maker | mid | 2,114 trades, $5,729.22 | 805 trades, $-5,837.24 | 3 trades, $0.00 | 4,852 trades, $1,072.52 | 204 trades, $274.72 | 55 trades, $-81.68 |
| test open10 taker | close | 2,798 trades, $4,966.18 | 758 trades, $-3,485.76 | 1 trades, $0.00 | 4,285 trades, $1,377.73 | 209 trades, $322.03 | 27 trades, $-44.91 |
| test open10 taker | mid | 2,135 trades, $3,542.91 | 810 trades, $-3,567.32 | 2 trades, $0.00 | 4,844 trades, $537.83 | 194 trades, $156.93 | 57 trades, $-51.76 |
| test open20 maker | close | 4,724 trades, $34,842.03 | 1,366 trades, $-26,481.62 | 1 trades, $0.00 | 7,267 trades, $10,449.68 | 336 trades, $2,021.84 | 41 trades, $-261.27 |
| test open20 maker | mid | 3,651 trades, $25,424.85 | 1,451 trades, $-27,012.57 | 5 trades, $0.00 | 8,153 trades, $4,827.48 | 323 trades, $1,131.19 | 99 trades, $-454.66 |
| test open20 taker | close | 4,710 trades, $13,153.05 | 1,358 trades, $-9,646.03 | 1 trades, $0.00 | 7,252 trades, $3,902.14 | 339 trades, $816.31 | 39 trades, $-99.21 |
| test open20 taker | mid | 3,637 trades, $9,492.83 | 1,452 trades, $-9,871.99 | 6 trades, $0.00 | 8,130 trades, $1,694.57 | 327 trades, $439.61 | 94 trades, $-167.76 |

### Market exposure
Net notional = long dollars minus short dollars at entry (share of the trade's notional). BTC return over the trade from the 30-minute BTC file (price up to 30 minutes old at both ends; the primary reads the file's date as the bar's open, the alternative as its end). Slope and correlation are descriptive only (trades overlap in time). Exposure P&L = sum of net dollars x BTC return over each trade (assumes both legs move one-for-one with BTC).
| run | mean net notional | mean net share | mean abs net share | BTC slope, $ gross per +1% BTC | correlation | slope, bp of notional per +1% | correlation (bp) | exposure P&L | gross (same trades) | alternative convention: slope / correlation |
|---|---|---|---|---|---|---|---|---|---|---|
| vault open10 maker | $1.24 | 0.5% | 44.0% | -0.140 | -0.0308 | -5.524 | -0.0337 | $-154.19 | $1,358.79 | -0.159 / -0.0366 |
| vault open10 taker | $0.31 | 0.2% | 43.3% | -0.184 | -0.0557 | -8.396 | -0.0521 | $-178.94 | $932.87 | -0.221 / -0.0696 |
| vault open20 maker | $0.76 | 0.1% | 45.0% | -0.075 | -0.0124 | -4.152 | -0.0273 | $-320.17 | $3,010.10 | -0.131 / -0.0227 |
| vault open20 taker | $0.17 | 0.2% | 44.3% | -0.191 | -0.0551 | -6.992 | -0.0459 | $-329.05 | $1,626.08 | -0.220 / -0.0664 |
| test open10 maker | $1.22 | -0.1% | 35.8% | +0.116 | +0.0207 | +5.000 | +0.0394 | $-1,159.61 | $5,122.67 | +0.095 / +0.0176 |
| test open10 taker | $0.54 | -0.1% | 35.9% | +0.097 | +0.0296 | +5.343 | +0.0429 | $-686.23 | $3,135.27 | +0.060 / +0.0190 |
| test open20 maker | $3.40 | -0.7% | 36.2% | +0.158 | +0.0097 | +4.755 | +0.0384 | $-6,125.59 | $20,570.67 | +0.148 / +0.0094 |
| test open20 taker | $-0.08 | -0.7% | 36.4% | +0.130 | +0.0242 | +4.997 | +0.0399 | $-2,003.65 | $8,126.25 | +0.102 / +0.0198 |

Mean gross per trade by tercile of the signed BTC return over the trade (primary convention), with the mean holding time and the share of mu exits in each tercile. The terciles are confounded with holding time (mu exits are short and winning, timeouts are long); do not read this as calm-market profit.
| run | BTC down third | BTC middle third | BTC up third |
|---|---|---|---|
| vault open10 maker | $-0.04 (n 1,277; mean holding 344 min; mu exits 64.1%) | $1.12 (n 1,277; mean holding 161 min; mu exits 87.6%) | $-0.01 (n 1,278; mean holding 369 min; mu exits 61.3%) |
| vault open10 taker | $-0.03 (n 1,263; mean holding 344 min; mu exits 64.5%) | $0.83 (n 1,263; mean holding 164 min; mu exits 87.3%) | $-0.06 (n 1,263; mean holding 373 min; mu exits 59.9%) |
| vault open20 maker | $-0.12 (n 2,197; mean holding 349 min; mu exits 63.1%) | $1.46 (n 2,196; mean holding 168 min; mu exits 87.2%) | $0.03 (n 2,197; mean holding 376 min; mu exits 60.4%) |
| vault open20 taker | $-0.10 (n 2,171; mean holding 353 min; mu exits 62.1%) | $0.88 (n 2,171; mean holding 170 min; mu exits 87.0%) | $-0.03 (n 2,171; mean holding 375 min; mu exits 60.4%) |
| test open10 maker | $-0.00 (n 2,690; mean holding 351 min; mu exits 62.8%) | $1.97 (n 2,689; mean holding 150 min; mu exits 88.5%) | $-0.06 (n 2,690; mean holding 357 min; mu exits 61.2%) |
| test open10 taker | $-0.02 (n 2,693; mean holding 354 min; mu exits 62.0%) | $1.19 (n 2,692; mean holding 148 min; mu exits 88.5%) | $-0.00 (n 2,693; mean holding 355 min; mu exits 61.4%) |
| test open20 maker | $-0.03 (n 4,578; mean holding 356 min; mu exits 61.8%) | $4.89 (n 4,578; mean holding 154 min; mu exits 87.8%) | $-0.36 (n 4,579; mean holding 360 min; mu exits 60.5%) |
| test open20 taker | $0.02 (n 4,566; mean holding 357 min; mu exits 61.5%) | $1.81 (n 4,566; mean holding 154 min; mu exits 87.8%) | $-0.05 (n 4,567; mean holding 360 min; mu exits 60.6%) |
What the table shows: in 8 of 8 runs the middle tercile (BTC return near zero) has a shorter mean holding time than both outer terciles, and in 8 of 8 it has the highest share of mu exits. Holding time is therefore part of why the middle tercile differs; this table does not separate it from BTC.

### Costs per leg (fees and half-spread only)
LEG NET IS NOT THE COSTED NET C: no depth impact, no funding, no fill model. This answers which leg makes the profit only. Fees are the saved fees split by leg dollars. Taker runs also carry the order-book half-spread at the entry and exit minute (own minute only; trades without it are left out). Maker runs show fees only; the maker fill model is not split by leg.
Left out = trades in the group that this split cannot classify (same-direction pairs for long vs short, unclassified for mover vs hedge, equal legs for larger vs smaller), so the legs add up.
| run | group | split | trades in the table / left out | first group: legs, gross, fees, half-spread, net | second group: legs, gross, fees, half-spread, net |
|---|---|---|---|---|---|
| vault open10 maker | ALL | long vs short | 3,832 / 823 | long: 3,009, $911.08, $119.23, $0.00, $791.85 | short: 3,009, $305.69, $116.88, $0.00, $188.81 |
| vault open10 maker | ALL | mover vs hedge (beta-adjusted, HEADLINE) | 3,832 / 1 | mover: 3,831, $954.52, $167.60, $0.00, $786.92 | hedge: 3,831, $403.33, $127.75, $0.00, $275.58 |
| vault open10 maker | ALL | mover vs hedge (raw) | 3,832 / 1 | mover: 3,831, $663.12, $137.70, $0.00, $525.42 | hedge: 3,831, $694.73, $157.65, $0.00, $537.08 |
| vault open10 maker | ALL | larger vs smaller leg | 3,832 / 0 | larger: 3,832, $1,310.63, $194.84, $0.00, $1,115.79 | smaller: 3,832, $48.16, $100.57, $0.00, $-52.41 |
| vault open10 maker | least liquid third | long vs short | 2,549 / 474 | long: 2,075, $493.00, $73.79, $0.00, $419.21 | short: 2,075, $402.59, $70.82, $0.00, $331.76 |
| vault open10 maker | least liquid third | mover vs hedge (beta-adjusted, HEADLINE) | 2,549 / 1 | mover: 2,548, $679.25, $96.57, $0.00, $582.68 | hedge: 2,548, $384.11, $78.04, $0.00, $306.07 |
| vault open10 maker | least liquid third | mover vs hedge (raw) | 2,549 / 1 | mover: 2,548, $567.13, $83.81, $0.00, $483.32 | hedge: 2,548, $496.23, $90.81, $0.00, $405.42 |
| vault open10 maker | least liquid third | larger vs smaller leg | 2,549 / 0 | larger: 2,549, $903.97, $111.14, $0.00, $792.83 | smaller: 2,549, $160.33, $63.54, $0.00, $96.79 |
| vault open10 maker | middle third | long vs short | 977 / 280 | long: 697, $242.62, $29.30, $0.00, $213.32 | short: 697, $-97.81, $29.97, $0.00, $-127.78 |
| vault open10 maker | middle third | mover vs hedge (beta-adjusted, HEADLINE) | 977 / 0 | mover: 977, $188.33, $47.07, $0.00, $141.26 | hedge: 977, $-41.71, $32.91, $0.00, $-74.61 |
| vault open10 maker | middle third | mover vs hedge (raw) | 977 / 0 | mover: 977, $90.62, $36.39, $0.00, $54.23 | hedge: 977, $56.01, $43.59, $0.00, $12.42 |
| vault open10 maker | middle third | larger vs smaller leg | 977 / 0 | larger: 977, $273.44, $54.74, $0.00, $218.69 | smaller: 977, $-126.81, $25.23, $0.00, $-152.05 |
| vault open10 maker | most liquid third | long vs short | 306 / 69 | long: 237, $175.46, $16.14, $0.00, $159.32 | short: 237, $0.91, $16.09, $0.00, $-15.17 |
| vault open10 maker | most liquid third | mover vs hedge (beta-adjusted, HEADLINE) | 306 / 0 | mover: 306, $86.94, $23.96, $0.00, $62.98 | hedge: 306, $60.92, $16.80, $0.00, $44.13 |
| vault open10 maker | most liquid third | mover vs hedge (raw) | 306 / 0 | mover: 306, $5.37, $17.50, $0.00, $-12.13 | hedge: 306, $142.49, $23.25, $0.00, $119.24 |
| vault open10 maker | most liquid third | larger vs smaller leg | 306 / 0 | larger: 306, $133.22, $28.95, $0.00, $104.27 | smaller: 306, $14.64, $11.80, $0.00, $2.84 |
| vault open10 taker | ALL | long vs short | 3,518 / 743 | long: 2,775, $570.43, $250.74, $239.38, $80.30 | short: 2,775, $318.79, $248.32, $223.85, $-153.37 |
| vault open10 taker | ALL | mover vs hedge (beta-adjusted, HEADLINE) | 3,518 / 1 | mover: 3,517, $630.34, $357.83, $299.45, $-26.93 | hedge: 3,517, $249.84, $272.74, $238.68, $-261.58 |
| vault open10 taker | ALL | mover vs hedge (raw) | 3,518 / 1 | mover: 3,517, $432.04, $295.36, $255.17, $-118.49 | hedge: 3,517, $448.14, $335.21, $282.95, $-170.03 |
| vault open10 taker | ALL | larger vs smaller leg | 3,518 / 0 | larger: 3,518, $931.47, $415.65, $382.30, $133.52 | smaller: 3,518, $-50.57, $215.07, $156.04, $-421.68 |
| vault open10 taker | least liquid third | long vs short | 2,332 / 409 | long: 1,923, $350.72, $153.08, $205.96, $-8.32 | short: 1,923, $237.20, $149.28, $189.72, $-101.81 |
| vault open10 taker | least liquid third | mover vs hedge (beta-adjusted, HEADLINE) | 2,332 / 1 | mover: 2,331, $438.61, $202.33, $245.85, $-9.56 | hedge: 2,331, $220.42, $162.66, $202.61, $-144.85 |
| vault open10 taker | least liquid third | mover vs hedge (raw) | 2,332 / 1 | mover: 2,331, $379.06, $175.40, $208.19, $-4.53 | hedge: 2,331, $279.97, $189.58, $240.27, $-149.88 |
| vault open10 taker | least liquid third | larger vs smaller leg | 2,332 / 0 | larger: 2,332, $564.27, $232.50, $325.81, $5.96 | smaller: 2,332, $95.48, $132.63, $122.87, $-160.01 |
| vault open10 taker | middle third | long vs short | 911 / 269 | long: 642, $160.31, $62.86, $26.82, $70.63 | short: 642, $14.32, $65.59, $27.71, $-78.98 |
| vault open10 taker | middle third | mover vs hedge (beta-adjusted, HEADLINE) | 911 / 0 | mover: 911, $200.22, $102.94, $43.34, $53.94 | hedge: 911, $-12.00, $74.27, $29.68, $-115.94 |
| vault open10 taker | middle third | mover vs hedge (raw) | 911 / 0 | mover: 911, $104.02, $80.42, $37.63, $-14.03 | hedge: 911, $84.21, $96.79, $35.40, $-47.98 |
| vault open10 taker | middle third | larger vs smaller leg | 911 / 0 | larger: 911, $265.67, $120.74, $46.01, $98.92 | smaller: 911, $-77.44, $56.47, $27.01, $-160.92 |
| vault open10 taker | most liquid third | long vs short | 275 / 65 | long: 210, $59.39, $34.80, $6.60, $17.99 | short: 210, $67.27, $33.44, $6.41, $27.41 |
| vault open10 taker | most liquid third | mover vs hedge (beta-adjusted, HEADLINE) | 275 / 0 | mover: 275, $-8.50, $52.56, $10.25, $-71.31 | hedge: 275, $41.41, $35.82, $6.39, $-0.79 |
| vault open10 taker | most liquid third | mover vs hedge (raw) | 275 / 0 | mover: 275, $-51.04, $39.53, $9.35, $-99.93 | hedge: 275, $83.96, $48.84, $7.29, $27.83 |
| vault open10 taker | most liquid third | larger vs smaller leg | 275 / 0 | larger: 275, $101.53, $62.41, $10.48, $28.64 | smaller: 275, $-68.61, $25.97, $6.16, $-100.74 |
| vault open20 maker | ALL | long vs short | 6,590 / 1,498 | long: 5,092, $1,585.96, $264.97, $0.00, $1,320.99 | short: 5,092, $929.08, $263.16, $0.00, $665.92 |
| vault open20 maker | ALL | mover vs hedge (beta-adjusted, HEADLINE) | 6,590 / 1 | mover: 6,589, $2,183.48, $379.63, $0.00, $1,803.85 | hedge: 6,589, $825.46, $286.22, $0.00, $539.24 |
| vault open20 maker | ALL | mover vs hedge (raw) | 6,590 / 1 | mover: 6,589, $1,778.19, $311.86, $0.00, $1,466.33 | hedge: 6,589, $1,230.74, $353.99, $0.00, $876.75 |
| vault open20 maker | ALL | larger vs smaller leg | 6,590 / 0 | larger: 6,590, $2,981.25, $441.04, $0.00, $2,540.21 | smaller: 6,590, $28.85, $224.88, $0.00, $-196.03 |
| vault open20 maker | least liquid third | long vs short | 4,358 / 857 | long: 3,501, $1,120.67, $163.83, $0.00, $956.84 | short: 3,501, $1,003.78, $160.59, $0.00, $843.20 |
| vault open20 maker | least liquid third | mover vs hedge (beta-adjusted, HEADLINE) | 4,358 / 1 | mover: 4,357, $1,664.10, $217.15, $0.00, $1,446.95 | hedge: 4,357, $821.74, $175.16, $0.00, $646.58 |
| vault open20 maker | least liquid third | mover vs hedge (raw) | 4,358 / 1 | mover: 4,357, $1,526.61, $190.00, $0.00, $1,336.61 | hedge: 4,357, $959.22, $202.31, $0.00, $756.92 |
| vault open20 maker | least liquid third | larger vs smaller leg | 4,358 / 0 | larger: 4,358, $2,346.96, $249.72, $0.00, $2,097.24 | smaller: 4,358, $140.05, $142.67, $0.00, $-2.62 |
| vault open20 maker | middle third | long vs short | 1,713 / 516 | long: 1,197, $336.57, $65.94, $0.00, $270.63 | short: 1,197, $-87.55, $67.56, $0.00, $-155.11 |
| vault open20 maker | middle third | mover vs hedge (beta-adjusted, HEADLINE) | 1,713 / 0 | mover: 1,713, $508.66, $109.20, $0.00, $399.46 | hedge: 1,713, $-117.27, $74.63, $0.00, $-191.90 |
| vault open20 maker | middle third | mover vs hedge (raw) | 1,713 / 0 | mover: 1,713, $344.86, $83.30, $0.00, $261.56 | hedge: 1,713, $46.54, $100.54, $0.00, $-54.00 |
| vault open20 maker | middle third | larger vs smaller leg | 1,713 / 0 | larger: 1,713, $448.06, $127.21, $0.00, $320.85 | smaller: 1,713, $-56.67, $56.63, $0.00, $-113.30 |
| vault open20 maker | most liquid third | long vs short | 519 / 125 | long: 394, $128.71, $35.20, $0.00, $93.51 | short: 394, $12.85, $35.02, $0.00, $-22.17 |
| vault open20 maker | most liquid third | mover vs hedge (beta-adjusted, HEADLINE) | 519 / 0 | mover: 519, $10.72, $53.28, $0.00, $-42.56 | hedge: 519, $120.98, $36.42, $0.00, $84.56 |
| vault open20 maker | most liquid third | mover vs hedge (raw) | 519 / 0 | mover: 519, $-93.28, $38.55, $0.00, $-131.84 | hedge: 519, $224.98, $51.14, $0.00, $173.84 |
| vault open20 maker | most liquid third | larger vs smaller leg | 519 / 0 | larger: 519, $186.23, $64.12, $0.00, $122.12 | smaller: 519, $-54.54, $25.58, $0.00, $-80.12 |
| vault open20 taker | ALL | long vs short | 6,070 / 1,355 | long: 4,715, $864.13, $443.85, $418.62, $1.66 | short: 4,715, $536.43, $443.73, $389.12, $-296.42 |
| vault open20 taker | ALL | mover vs hedge (beta-adjusted, HEADLINE) | 6,070 / 1 | mover: 6,069, $1,170.64, $643.86, $534.32, $-7.54 | hedge: 6,069, $371.32, $489.76, $411.69, $-530.13 |
| vault open20 taker | ALL | mover vs hedge (raw) | 6,070 / 1 | mover: 6,069, $970.09, $537.92, $468.68, $-36.51 | hedge: 6,069, $571.87, $595.70, $477.32, $-501.15 |
| vault open20 taker | ALL | larger vs smaller leg | 6,070 / 0 | larger: 6,070, $1,540.72, $748.64, $669.23, $122.85 | smaller: 6,070, $1.98, $385.13, $277.00, $-660.15 |
| vault open20 taker | least liquid third | long vs short | 4,035 / 763 | long: 3,272, $533.03, $272.70, $360.61, $-100.27 | short: 3,272, $521.86, $268.65, $329.99, $-76.78 |
| vault open20 taker | least liquid third | mover vs hedge (beta-adjusted, HEADLINE) | 4,035 / 1 | mover: 4,034, $860.78, $366.78, $441.20, $52.79 | hedge: 4,034, $375.29, $294.39, $346.91, $-266.01 |
| vault open20 taker | least liquid third | mover vs hedge (raw) | 4,035 / 1 | mover: 4,034, $808.89, $323.31, $386.92, $98.66 | hedge: 4,034, $427.18, $337.86, $401.19, $-311.88 |
| vault open20 taker | least liquid third | larger vs smaller leg | 4,035 / 0 | larger: 4,035, $1,103.92, $421.23, $570.74, $111.95 | smaller: 4,035, $132.88, $240.09, $217.59, $-324.79 |
| vault open20 taker | middle third | long vs short | 1,569 / 478 | long: 1,091, $208.53, $112.31, $46.74, $49.48 | short: 1,091, $16.30, $114.79, $47.42, $-145.91 |
| vault open20 taker | middle third | mover vs hedge (beta-adjusted, HEADLINE) | 1,569 / 0 | mover: 1,569, $331.84, $185.17, $75.74, $70.93 | hedge: 1,569, $-4.14, $132.24, $53.11, $-189.50 |
| vault open20 taker | middle third | mover vs hedge (raw) | 1,569 / 0 | mover: 1,569, $220.53, $145.67, $66.11, $8.75 | hedge: 1,569, $107.16, $171.74, $62.74, $-127.32 |
| vault open20 taker | middle third | larger vs smaller leg | 1,569 / 0 | larger: 1,569, $368.73, $217.55, $80.32, $70.86 | smaller: 1,569, $-41.04, $99.86, $48.53, $-189.43 |
| vault open20 taker | most liquid third | long vs short | 466 / 114 | long: 352, $122.56, $58.84, $11.27, $52.45 | short: 352, $-1.73, $60.28, $11.71, $-73.73 |
| vault open20 taker | most liquid third | mover vs hedge (beta-adjusted, HEADLINE) | 466 / 0 | mover: 466, $-21.97, $91.92, $17.37, $-131.26 | hedge: 466, $0.17, $63.12, $11.67, $-74.63 |
| vault open20 taker | most liquid third | mover vs hedge (raw) | 466 / 0 | mover: 466, $-59.33, $68.94, $15.65, $-143.92 | hedge: 466, $37.52, $86.10, $13.39, $-61.96 |
| vault open20 taker | most liquid third | larger vs smaller leg | 466 / 0 | larger: 466, $68.06, $109.86, $18.16, $-59.95 | smaller: 466, $-89.86, $45.19, $10.88, $-145.93 |
| test open10 maker | ALL | long vs short | 8,069 / 1,181 | long: 6,888, $2,154.25, $450.43, $0.00, $1,703.83 | short: 6,888, $2,266.51, $437.40, $0.00, $1,829.10 |
| test open10 maker | ALL | mover vs hedge (beta-adjusted, HEADLINE) | 8,069 / 0 | mover: 8,069, $2,870.64, $567.83, $0.00, $2,302.81 | hedge: 8,069, $2,252.03, $463.84, $0.00, $1,788.20 |
| test open10 maker | ALL | mover vs hedge (raw) | 8,069 / 0 | mover: 8,069, $2,861.65, $490.69, $0.00, $2,370.96 | hedge: 8,069, $2,261.03, $540.97, $0.00, $1,720.05 |
| test open10 maker | ALL | larger vs smaller leg | 8,069 / 0 | larger: 8,069, $3,699.71, $659.12, $0.00, $3,040.59 | smaller: 8,069, $1,422.96, $372.55, $0.00, $1,050.41 |
| test open10 maker | least liquid third | long vs short | 5,748 / 736 | long: 5,012, $1,726.49, $289.72, $0.00, $1,436.77 | short: 5,012, $2,095.64, $285.78, $0.00, $1,809.86 |
| test open10 maker | least liquid third | mover vs hedge (beta-adjusted, HEADLINE) | 5,748 / 0 | mover: 5,748, $2,049.93, $353.84, $0.00, $1,696.09 | hedge: 5,748, $2,166.22, $298.94, $0.00, $1,867.28 |
| test open10 maker | least liquid third | mover vs hedge (raw) | 5,748 / 0 | mover: 5,748, $1,822.07, $316.73, $0.00, $1,505.34 | hedge: 5,748, $2,394.08, $336.05, $0.00, $2,058.03 |
| test open10 maker | least liquid third | larger vs smaller leg | 5,748 / 0 | larger: 5,748, $3,075.26, $408.92, $0.00, $2,666.34 | smaller: 5,748, $1,140.89, $243.86, $0.00, $897.03 |
| test open10 maker | middle third | long vs short | 1,782 / 352 | long: 1,430, $446.24, $101.17, $0.00, $345.07 | short: 1,430, $7.06, $97.14, $0.00, $-90.08 |
| test open10 maker | middle third | mover vs hedge (beta-adjusted, HEADLINE) | 1,782 / 0 | mover: 1,782, $549.93, $140.88, $0.00, $409.06 | hedge: 1,782, $81.74, $106.45, $0.00, $-24.71 |
| test open10 maker | middle third | mover vs hedge (raw) | 1,782 / 0 | mover: 1,782, $593.22, $116.34, $0.00, $476.88 | hedge: 1,782, $38.45, $130.98, $0.00, $-92.53 |
| test open10 maker | middle third | larger vs smaller leg | 1,782 / 0 | larger: 1,782, $623.67, $162.19, $0.00, $461.48 | smaller: 1,782, $8.00, $85.14, $0.00, $-77.14 |
| test open10 maker | most liquid third | long vs short | 539 / 93 | long: 446, $-18.48, $59.53, $0.00, $-78.01 | short: 446, $163.81, $54.49, $0.00, $109.32 |
| test open10 maker | most liquid third | mover vs hedge (beta-adjusted, HEADLINE) | 539 / 0 | mover: 539, $270.78, $73.12, $0.00, $197.66 | hedge: 539, $4.07, $58.45, $0.00, $-54.38 |
| test open10 maker | most liquid third | mover vs hedge (raw) | 539 / 0 | mover: 539, $446.36, $57.62, $0.00, $388.74 | hedge: 539, $-171.50, $73.95, $0.00, $-245.45 |
| test open10 maker | most liquid third | larger vs smaller leg | 539 / 0 | larger: 539, $0.78, $88.01, $0.00, $-87.23 | smaller: 539, $274.07, $43.55, $0.00, $230.52 |
| test open10 taker | ALL | long vs short | 7,555 / 1,088 | long: 6,467, $1,174.82, $768.24, $1,113.44, $-706.86 | short: 6,467, $1,408.98, $747.57, $1,176.40, $-514.98 |
| test open10 taker | ALL | mover vs hedge (beta-adjusted, HEADLINE) | 7,555 / 0 | mover: 7,555, $1,724.48, $968.09, $1,403.54, $-647.15 | hedge: 7,555, $1,318.42, $793.21, $1,256.63, $-731.42 |
| test open10 taker | ALL | mover vs hedge (raw) | 7,555 / 0 | mover: 7,555, $1,725.54, $839.64, $1,304.81, $-418.90 | hedge: 7,555, $1,317.36, $921.67, $1,355.36, $-959.67 |
| test open10 taker | ALL | larger vs smaller leg | 7,555 / 0 | larger: 7,555, $2,028.15, $1,124.97, $1,546.27, $-643.09 | smaller: 7,555, $1,014.75, $636.33, $1,113.90, $-735.48 |
| test open10 taker | least liquid third | long vs short | 5,397 / 685 | long: 4,712, $978.14, $500.16, $966.06, $-488.08 | short: 4,712, $1,279.72, $489.64, $1,026.46, $-236.37 |
| test open10 taker | least liquid third | mover vs hedge (beta-adjusted, HEADLINE) | 5,397 / 0 | mover: 5,397, $1,322.01, $607.23, $1,203.02, $-488.23 | hedge: 5,397, $1,278.60, $517.87, $1,085.47, $-324.74 |
| test open10 taker | least liquid third | mover vs hedge (raw) | 5,397 / 0 | mover: 5,397, $1,173.14, $544.01, $1,116.27, $-487.14 | hedge: 5,397, $1,427.47, $581.09, $1,172.22, $-325.83 |
| test open10 taker | least liquid third | larger vs smaller leg | 5,397 / 0 | larger: 5,397, $1,703.98, $705.94, $1,336.07, $-338.03 | smaller: 5,397, $896.64, $419.16, $952.42, $-474.94 |
| test open10 taker | middle third | long vs short | 1,666 / 315 | long: 1,351, $225.56, $172.54, $120.64, $-67.63 | short: 1,351, $55.33, $164.68, $123.11, $-232.46 |
| test open10 taker | middle third | mover vs hedge (beta-adjusted, HEADLINE) | 1,666 / 0 | mover: 1,666, $315.37, $235.69, $164.76, $-85.08 | hedge: 1,666, $55.79, $179.80, $142.13, $-266.13 |
| test open10 taker | middle third | mover vs hedge (raw) | 1,666 / 0 | mover: 1,666, $294.27, $195.05, $155.19, $-55.97 | hedge: 1,666, $76.89, $220.44, $151.70, $-295.25 |
| test open10 taker | middle third | larger vs smaller leg | 1,666 / 0 | larger: 1,666, $432.93, $272.78, $175.30, $-15.15 | smaller: 1,666, $-61.77, $142.71, $131.59, $-336.06 |
| test open10 taker | most liquid third | long vs short | 492 / 88 | long: 404, $-28.88, $95.54, $26.73, $-151.15 | short: 404, $73.93, $93.24, $26.83, $-46.15 |
| test open10 taker | most liquid third | mover vs hedge (beta-adjusted, HEADLINE) | 492 / 0 | mover: 492, $87.09, $125.17, $35.76, $-73.84 | hedge: 492, $-15.98, $95.55, $29.02, $-140.55 |
| test open10 taker | most liquid third | mover vs hedge (raw) | 492 / 0 | mover: 492, $258.12, $100.58, $33.34, $124.20 | hedge: 492, $-187.01, $120.14, $31.44, $-338.59 |
| test open10 taker | most liquid third | larger vs smaller leg | 492 / 0 | larger: 492, $-108.77, $146.25, $34.89, $-289.91 | smaller: 492, $179.88, $74.47, $29.89, $75.53 |
| test open20 maker | ALL | long vs short | 13,735 / 2,017 | long: 11,718, $10,714.99, $2,008.80, $0.00, $8,706.19 | short: 11,718, $8,712.66, $1,942.57, $0.00, $6,770.09 |
| test open20 maker | ALL | mover vs hedge (beta-adjusted, HEADLINE) | 13,735 / 1 | mover: 13,734, $13,072.69, $2,528.67, $0.00, $10,544.02 | hedge: 13,734, $7,488.49, $2,047.58, $0.00, $5,440.91 |
| test open20 maker | ALL | mover vs hedge (raw) | 13,735 / 1 | mover: 13,734, $12,708.80, $2,175.40, $0.00, $10,533.40 | hedge: 13,734, $7,852.37, $2,400.86, $0.00, $5,451.52 |
| test open20 maker | ALL | larger vs smaller leg | 13,735 / 0 | larger: 13,735, $15,374.38, $2,933.26, $0.00, $12,441.12 | smaller: 13,735, $5,196.29, $1,643.26, $0.00, $3,553.03 |
| test open20 maker | least liquid third | long vs short | 9,704 / 1,272 | long: 8,432, $8,421.60, $1,248.66, $0.00, $7,172.94 | short: 8,432, $8,851.06, $1,231.60, $0.00, $7,619.46 |
| test open20 maker | least liquid third | mover vs hedge (beta-adjusted, HEADLINE) | 9,704 / 1 | mover: 9,703, $10,294.74, $1,533.15, $0.00, $8,761.59 | hedge: 9,703, $7,723.44, $1,281.17, $0.00, $6,442.28 |
| test open20 maker | least liquid third | mover vs hedge (raw) | 9,704 / 1 | mover: 9,703, $9,048.02, $1,362.36, $0.00, $7,685.66 | hedge: 9,703, $8,970.16, $1,451.96, $0.00, $7,518.20 |
| test open20 maker | least liquid third | larger vs smaller leg | 9,704 / 0 | larger: 9,704, $13,542.32, $1,764.35, $0.00, $11,777.97 | smaller: 9,704, $4,485.35, $1,050.23, $0.00, $3,435.12 |
| test open20 maker | middle third | long vs short | 3,123 / 599 | long: 2,524, $1,987.99, $475.06, $0.00, $1,512.92 | short: 2,524, $-585.21, $453.50, $0.00, $-1,038.71 |
| test open20 maker | middle third | mover vs hedge (beta-adjusted, HEADLINE) | 3,123 / 0 | mover: 3,123, $1,587.15, $649.98, $0.00, $937.17 | hedge: 3,123, $-142.18, $494.63, $0.00, $-636.82 |
| test open20 maker | middle third | mover vs hedge (raw) | 3,123 / 0 | mover: 3,123, $1,538.21, $539.55, $0.00, $998.66 | hedge: 3,123, $-93.24, $605.07, $0.00, $-698.31 |
| test open20 maker | middle third | larger vs smaller leg | 3,123 / 0 | larger: 3,123, $1,471.02, $752.91, $0.00, $718.11 | smaller: 3,123, $-26.05, $391.71, $0.00, $-417.76 |
| test open20 maker | most liquid third | long vs short | 908 / 146 | long: 762, $305.41, $285.07, $0.00, $20.33 | short: 762, $446.80, $257.47, $0.00, $189.34 |
| test open20 maker | most liquid third | mover vs hedge (beta-adjusted, HEADLINE) | 908 / 0 | mover: 908, $1,190.80, $345.54, $0.00, $845.26 | hedge: 908, $-92.77, $271.78, $0.00, $-364.55 |
| test open20 maker | most liquid third | mover vs hedge (raw) | 908 / 0 | mover: 908, $2,122.57, $273.49, $0.00, $1,849.08 | hedge: 908, $-1,024.55, $343.83, $0.00, $-1,368.38 |
| test open20 maker | most liquid third | larger vs smaller leg | 908 / 0 | larger: 908, $361.04, $416.00, $0.00, $-54.96 | smaller: 908, $736.99, $201.32, $0.00, $535.67 |
| test open20 taker | ALL | long vs short | 12,810 / 1,869 | long: 10,941, $3,522.42, $2,041.00, $3,009.59, $-1,528.18 | short: 10,941, $3,931.65, $1,987.00, $3,098.85, $-1,154.20 |
| test open20 taker | ALL | mover vs hedge (beta-adjusted, HEADLINE) | 12,810 / 1 | mover: 12,809, $4,820.94, $2,576.05, $3,879.11, $-1,634.21 | hedge: 12,809, $3,320.94, $2,087.76, $3,231.07, $-1,997.89 |
| test open20 taker | ALL | mover vs hedge (raw) | 12,810 / 1 | mover: 12,809, $4,554.09, $2,222.65, $3,607.55, $-1,276.10 | hedge: 12,809, $3,587.79, $2,441.16, $3,502.63, $-2,356.00 |
| test open20 taker | ALL | larger vs smaller leg | 12,810 / 0 | larger: 12,810, $5,614.92, $2,987.97, $4,100.33, $-1,473.38 | smaller: 12,810, $2,530.93, $1,676.17, $3,012.52, $-2,157.76 |
| test open20 taker | least liquid third | long vs short | 9,098 / 1,190 | long: 7,908, $2,859.65, $1,302.00, $2,606.08, $-1,048.43 | short: 7,908, $3,599.72, $1,282.32, $2,691.13, $-373.72 |
| test open20 taker | least liquid third | mover vs hedge (beta-adjusted, HEADLINE) | 9,098 / 1 | mover: 9,097, $3,843.44, $1,596.67, $3,330.20, $-1,083.44 | hedge: 9,097, $3,117.49, $1,346.73, $2,785.12, $-1,014.36 |
| test open20 taker | least liquid third | mover vs hedge (raw) | 9,098 / 1 | mover: 9,097, $3,389.44, $1,418.78, $3,095.49, $-1,124.83 | hedge: 9,097, $3,571.49, $1,524.62, $3,019.84, $-972.97 |
| test open20 taker | least liquid third | larger vs smaller leg | 9,098 / 0 | larger: 9,098, $4,702.74, $1,851.71, $3,540.15, $-689.12 | smaller: 9,098, $2,262.14, $1,092.02, $2,577.86, $-1,407.73 |
| test open20 taker | middle third | long vs short | 2,875 / 543 | long: 2,332, $560.65, $471.24, $327.87, $-238.46 | short: 2,332, $-71.45, $450.80, $334.31, $-856.56 |
| test open20 taker | middle third | mover vs hedge (beta-adjusted, HEADLINE) | 2,875 / 0 | mover: 2,875, $503.20, $639.55, $450.52, $-586.87 | hedge: 2,875, $100.07, $484.04, $368.23, $-752.20 |
| test open20 taker | middle third | mover vs hedge (raw) | 2,875 / 0 | mover: 2,875, $462.18, $530.35, $420.64, $-488.80 | hedge: 2,875, $141.08, $593.24, $398.11, $-850.27 |
| test open20 taker | middle third | larger vs smaller leg | 2,875 / 0 | larger: 2,875, $623.23, $740.04, $461.46, $-578.27 | smaller: 2,875, $-19.96, $383.54, $357.29, $-760.80 |
| test open20 taker | most liquid third | long vs short | 837 / 136 | long: 701, $102.12, $267.76, $75.64, $-241.28 | short: 701, $403.37, $253.88, $73.41, $76.08 |
| test open20 taker | most liquid third | mover vs hedge (beta-adjusted, HEADLINE) | 837 / 0 | mover: 837, $474.31, $339.83, $98.39, $36.09 | hedge: 837, $103.39, $257.00, $77.71, $-231.32 |
| test open20 taker | most liquid third | mover vs hedge (raw) | 837 / 0 | mover: 837, $702.47, $273.52, $91.42, $337.53 | hedge: 837, $-124.77, $323.30, $84.68, $-532.76 |
| test open20 taker | most liquid third | larger vs smaller leg | 837 / 0 | larger: 837, $288.95, $396.21, $98.73, $-205.99 | smaller: 837, $288.75, $200.61, $77.38, $10.76 |

Receipt: sum of leg nets vs the saved net A on the same trades; the gap is the funding paid net added back less the half-spread (asserted equal).
The saved net A in this table is on the trades in the cost table (taker runs: only trades with a half-spread row at all four stamps), so it can differ from the run's net A on other sets (for example the matched set of the no-bounce section).
| run | trades in the table / all trades | leg nets | saved net A (same trades) | funding paid net | half-spread |
|---|---|---|---|---|---|
| vault open10 maker | 3,832 / 3,832 | $1,063.37 | $1,068.41 | $-5.03 | $0.00 |
| vault open10 taker | 3,518 / 3,789 | $-288.16 | $252.93 | $-2.75 | $538.34 |
| vault open20 maker | 6,590 / 6,590 | $2,344.18 | $2,357.10 | $-12.93 | $0.00 |
| vault open20 taker | 6,070 / 6,513 | $-537.30 | $414.69 | $-5.77 | $946.22 |
| test open10 maker | 8,069 / 8,069 | $4,091.01 | $4,034.35 | $56.66 | $0.00 |
| test open10 taker | 7,555 / 8,078 | $-1,378.57 | $1,252.16 | $29.43 | $2,660.16 |
| test open20 maker | 13,735 / 13,735 | $15,994.15 | $15,935.92 | $58.23 | $0.00 |
| test open20 taker | 12,810 / 13,699 | $-3,631.14 | $3,437.84 | $43.87 | $7,112.86 |

### Reading, run by run (sentences filled from the tables above; close prices unless said)
- **vault open10 maker**: saved gross $1,358.79. Long legs made $1,004.64 (73.9% of the gross), short legs $354.15 (26.1%). Mover legs made $954.52 (70.2%), hedge legs $403.33 (29.7%); 2 legs unclassified. Larger-notional legs made $1,310.63 (96.5%), smaller legs $48.16 (3.5%). Of 2,888 winning trades, 1,392 (48.2%) had one leg above 100% of the gross; they carry 46.5% of the positive gross. Gross against the BTC return: slope -0.140 dollars per +1% BTC, correlation -0.0308; exposure P&L $-154.19.
- **vault open10 taker**: saved gross $932.87. Long legs made $574.86 (61.6% of the gross), short legs $358.01 (38.4%). Mover legs made $666.51 (71.4%), hedge legs $265.64 (28.5%); 2 legs unclassified. Larger-notional legs made $968.29 (103.8%), smaller legs $-35.42 (-3.8%). Of 2,839 winning trades, 1,374 (48.4%) had one leg above 100% of the gross; they carry 46.4% of the positive gross. Gross against the BTC return: slope -0.184 dollars per +1% BTC, correlation -0.0557; exposure P&L $-178.94.
- **vault open20 maker**: saved gross $3,010.10. Long legs made $1,855.30 (61.6% of the gross), short legs $1,154.80 (38.4%). Mover legs made $2,183.48 (72.5%), hedge legs $825.46 (27.4%); 2 legs unclassified. Larger-notional legs made $2,981.25 (99.0%), smaller legs $28.85 (1.0%). Of 4,927 winning trades, 2,367 (48.0%) had one leg above 100% of the gross; they carry 46.6% of the positive gross. Gross against the BTC return: slope -0.075 dollars per +1% BTC, correlation -0.0124; exposure P&L $-320.17.
- **vault open20 taker**: saved gross $1,626.08. Long legs made $975.60 (60.0% of the gross), short legs $650.47 (40.0%). Mover legs made $1,229.41 (75.6%), hedge legs $395.93 (24.3%); 2 legs unclassified. Larger-notional legs made $1,600.15 (98.4%), smaller legs $25.93 (1.6%). Of 4,843 winning trades, 2,324 (48.0%) had one leg above 100% of the gross; they carry 45.5% of the positive gross. Gross against the BTC return: slope -0.191 dollars per +1% BTC, correlation -0.0551; exposure P&L $-329.05.
- **test open10 maker**: saved gross $5,122.67. Long legs made $2,545.26 (49.7% of the gross), short legs $2,577.42 (50.3%). Mover legs made $2,870.64 (56.0%), hedge legs $2,252.03 (44.0%); 0 legs unclassified. Larger-notional legs made $3,699.71 (72.2%), smaller legs $1,422.96 (27.8%). Of 6,080 winning trades, 3,090 (50.8%) had one leg above 100% of the gross; they carry 46.0% of the positive gross. Gross against the BTC return: slope +0.116 dollars per +1% BTC, correlation +0.0207; exposure P&L $-1,159.61.
- **test open10 taker**: saved gross $3,135.27. Long legs made $1,485.10 (47.4% of the gross), short legs $1,650.17 (52.6%). Mover legs made $1,815.20 (57.9%), hedge legs $1,320.07 (42.1%); 0 legs unclassified. Larger-notional legs made $2,087.99 (66.6%), smaller legs $1,047.28 (33.4%). Of 6,069 winning trades, 3,062 (50.5%) had one leg above 100% of the gross; they carry 45.7% of the positive gross. Gross against the BTC return: slope +0.097 dollars per +1% BTC, correlation +0.0296; exposure P&L $-686.23.
- **test open20 maker**: saved gross $20,570.67. Long legs made $10,978.32 (53.4% of the gross), short legs $9,592.34 (46.6%). Mover legs made $13,072.69 (63.6%), hedge legs $7,488.49 (36.4%); 2 legs unclassified. Larger-notional legs made $15,374.38 (74.7%), smaller legs $5,196.29 (25.3%). Of 10,262 winning trades, 5,202 (50.7%) had one leg above 100% of the gross; they carry 46.8% of the positive gross. Gross against the BTC return: slope +0.158 dollars per +1% BTC, correlation +0.0097; exposure P&L $-6,125.59.
- **test open20 taker**: saved gross $8,126.25. Long legs made $3,993.01 (49.1% of the gross), short legs $4,133.24 (50.9%). Mover legs made $4,935.77 (60.7%), hedge legs $3,186.52 (39.2%); 2 legs unclassified. Larger-notional legs made $5,620.09 (69.2%), smaller legs $2,506.16 (30.8%). Of 10,219 winning trades, 5,170 (50.6%) had one leg above 100% of the gross; they carry 46.2% of the positive gross. Gross against the BTC return: slope +0.130 dollars per +1% BTC, correlation +0.0242; exposure P&L $-2,003.65.

### Notes (what the numbers are and are not)
- Findings are reported, not acted on. No pick, exit, hedge ratio or parameter was changed.
- Exposure P&L negative means the net market exposure lost money on average over the trades. It assumes a beta of 1 to BTC for both legs and is not a hedge-quality result.
- Leg gross is price movement only. Depth impact, funding and the maker fill model are not split by leg.
- The mover split classifies by the 60 minutes before entry, from closes. A stale close in that window can misplace a leg; the classification is the same in the mid version.
- The BTC return over a trade is read from 30-minute prices, up to 30 minutes old at both ends; this blurs the slope toward zero. Slope and correlation carry no significance statement.

## 10. Where every number comes from

- logs/costs1/costs_analysis_conservative.json (sha256 d323b8655a3e)
- logs/costs1/costs_analysis_calibrated.json (sha256 db80b34bf562)
- logs/costs1/costs_validate.json (sha256 0d6864f7000d)
- logs/costs1/costs_legs.json (sha256 9872148e012a)
- logs/costs1/costs_nobounce.json (sha256 874b5e11c115)
- logs/costs1/costs_nobounce_section.md (sha256 4c0eccae499e)
- logs/costs1/costs_legs_section.md (sha256 49401e87b40d)
- logs/costs1/costs_entry_delay_writeup.md (sha256 a19144641176)
- logs/costs1/process_times.json (sha256 27e3897f1b3b)
- diagnostics/costs_analysis.log
- diagnostics/costs_analysis_calibrated.log
- diagnostics/costs_validate.log
- diagnostics/costs_t2.log
- diagnostics/costs_nobounce.log
- diagnostics/costs_legs.log
- Scripts: diagnostics/costs_analysis.py, costs_validate.py, costs_nobounce.py, costs_nobounce_sources.py, costs_legs.py, costs_legs_section.py, costs_nobounce_section.py, costs_delay_writeup.py, costs_report_md.py; rules: costs1_rules.md.

