# COSTS1 - hero / culprit check: does the pre-entry mover label point to the leg that drives the trade?
Source: logs/costs1/costs_legs_hero.json, written by diagnostics/costs_legs_hero.py; the log is diagnostics/costs_legs_hero.log. Rules: costs1_rules.md section 12. Every number is printed by the script. Print-only: no selection, no tuning, no significance statement (trades overlap in time).

What the labels are. Mover = the leg whose beta-weighted 60-minute return before the entry moved the spread more (beta-adjusted headline). Larger = the leg with the larger notional at entry. Both use only information before the entry. Hedge and smaller are the other leg. Classification uses closes in both versions; the mid version covers the trades with all four mids.

"Hero" and "culprit" are names for two shares, not a claim about cause. The beta-adjusted mover is the leg with the larger dollar 60-minute move before the entry: la |r_a| against lb |r_b|, since lb = la |beta|.

The close version uses all trades; the mid version only trades with all four mids. Trades in the mid set, by run: vault open10 maker 3,827 of 3,832 (99.9%); vault open10 taker 3,783 of 3,789 (99.8%); vault open20 maker 6,581 of 6,590 (99.9%); vault open20 taker 6,504 of 6,513 (99.9%); test open10 maker 8,033 of 8,069 (99.6%); test open10 taker 8,042 of 8,078 (99.6%); test open20 maker 13,682 of 13,735 (99.6%); test open20 taker 13,646 of 13,699 (99.6%).

Hero share = among winning trades (trade gross > 0), the share where the first leg (mover or larger) made strictly more than the second. Culprit share = among losing trades (trade gross < 0), the share where the first leg lost strictly more than the second. Ties are counted in the log and the json. A share on fewer than 30 trades prints as n/m.

## Reading, run by run (ALL tiers; hero share minus culprit share, in percentage points)
How to read it. The difference, not either share, is the reading. Both shares near 50%: on these trades the label does not separate the legs. Difference positive: the first leg more often makes the larger gross when the trade wins than it makes the smaller gross when the trade loses. Both shares high with a difference near zero: the first leg is the bigger swinger in either direction. For the larger-notional label, size alone can push both shares above 50%, so 50% is not a baseline for it. A positive difference can also come from one leg having more drift (for example long vs short); this table cannot separate that. These are numbers on these trades, with no intervals and no significance statement.

- **vault open10 maker**: close mover: hero 61.4% (n 2,887) minus culprit 58.5% (n 944) = +2.9 pp; close larger: hero 68.0% (n 2,888) minus culprit 64.0% (n 944) = +4.0 pp; mid mover: hero 61.6% (n 2,831) minus culprit 58.0% (n 994) = +3.6 pp; mid larger: hero 66.9% (n 2,831) minus culprit 63.8% (n 995) = +3.1 pp.
- **vault open10 taker**: close mover: hero 61.4% (n 2,838) minus culprit 57.8% (n 950) = +3.6 pp; close larger: hero 68.5% (n 2,839) minus culprit 63.8% (n 950) = +4.8 pp; mid mover: hero 61.7% (n 2,779) minus culprit 57.6% (n 1,002) = +4.1 pp; mid larger: hero 67.6% (n 2,779) minus culprit 63.6% (n 1,003) = +4.0 pp.
- **vault open20 maker**: close mover: hero 62.1% (n 4,926) minus culprit 57.4% (n 1,663) = +4.7 pp; close larger: hero 68.3% (n 4,927) minus culprit 64.0% (n 1,663) = +4.2 pp; mid mover: hero 62.2% (n 4,832) minus culprit 56.9% (n 1,746) = +5.3 pp; mid larger: hero 67.5% (n 4,832) minus culprit 63.9% (n 1,747) = +3.7 pp.
- **vault open20 taker**: close mover: hero 61.7% (n 4,842) minus culprit 56.9% (n 1,670) = +4.8 pp; close larger: hero 68.0% (n 4,843) minus culprit 63.5% (n 1,670) = +4.5 pp; mid mover: hero 62.0% (n 4,745) minus culprit 56.4% (n 1,756) = +5.6 pp; mid larger: hero 67.2% (n 4,745) minus culprit 63.3% (n 1,757) = +3.9 pp.
- **test open10 maker**: close mover: hero 59.8% (n 6,080) minus culprit 59.9% (n 1,988) = -0.1 pp; close larger: hero 63.7% (n 6,080) minus culprit 62.4% (n 1,988) = +1.3 pp; mid mover: hero 60.8% (n 5,716) minus culprit 57.9% (n 2,314) = +2.9 pp; mid larger: hero 63.7% (n 5,716) minus culprit 61.0% (n 2,314) = +2.7 pp.
- **test open10 taker**: close mover: hero 59.8% (n 6,069) minus culprit 59.7% (n 2,008) = +0.1 pp; close larger: hero 63.3% (n 6,069) minus culprit 63.5% (n 2,008) = -0.3 pp; mid mover: hero 61.1% (n 5,706) minus culprit 57.5% (n 2,334) = +3.6 pp; mid larger: hero 63.4% (n 5,706) minus culprit 61.7% (n 2,334) = +1.7 pp.
- **test open20 maker**: close mover: hero 59.9% (n 10,261) minus culprit 59.7% (n 3,472) = +0.2 pp; close larger: hero 64.0% (n 10,262) minus culprit 62.9% (n 3,472) = +1.1 pp; mid mover: hero 60.8% (n 9,687) minus culprit 58.0% (n 3,989) = +2.9 pp; mid larger: hero 63.9% (n 9,687) minus culprit 61.6% (n 3,990) = +2.3 pp.
- **test open20 taker**: close mover: hero 60.0% (n 10,218) minus culprit 59.8% (n 3,479) = +0.2 pp; close larger: hero 63.7% (n 10,219) minus culprit 63.3% (n 3,479) = +0.4 pp; mid mover: hero 61.0% (n 9,645) minus culprit 57.8% (n 3,994) = +3.1 pp; mid larger: hero 63.7% (n 9,645) minus culprit 62.2% (n 3,995) = +1.5 pp.

## Close prices, label: mover vs hedge
Columns: classified trades (unclassified in brackets); share of trades where the mover leg made money; share where the hedge leg made money; winners and hero share; losers and culprit share; hero minus culprit (percentage points); mean leg gross in winners (mover / hedge); mean leg gross in losers (mover / hedge).

| run | group | trades (unclassified) | mover gross>0 | hedge gross>0 | winners | hero | losers | culprit | hero - culprit | winners: mean mover / hedge | losers: mean mover / hedge |
|---|---|---|---|---|---|---|---|---|---|---|---|
| vault open10 maker | ALL | 3,831 (1) | 67.1% | 58.3% | 2,887 | 61.4% | 944 | 58.5% | +2.9 pp | $1.080 / $0.531 | -$2.292 / -$1.197 |
| vault open10 maker | least liquid third | 2,548 (1) | 67.5% | 59.0% | 1,947 | 60.5% | 601 | 59.1% | +1.4 pp | $0.947 / $0.515 | -$1.939 / -$1.029 |
| vault open10 maker | middle third | 977 (0) | 66.9% | 56.0% | 707 | 64.6% | 270 | 57.4% | +7.2 pp | $1.282 / $0.485 | -$2.661 / -$1.425 |
| vault open10 maker | most liquid third | 306 (0) | 64.1% | 59.5% | 233 | 59.2% | 73 | 57.5% | +1.7 pp | $1.575 / $0.805 | -$3.835 / -$1.736 |
| vault open10 taker | ALL | 3,788 (1) | 67.2% | 57.7% | 2,838 | 61.4% | 950 | 57.8% | +3.6 pp | $0.826 / $0.392 | -$1.767 / -$0.891 |
| vault open10 taker | least liquid third | 2,509 (1) | 67.4% | 58.3% | 1,905 | 60.0% | 604 | 58.3% | +1.7 pp | $0.708 / $0.378 | -$1.434 / -$0.775 |
| vault open10 taker | middle third | 976 (0) | 67.9% | 56.0% | 714 | 65.0% | 262 | 56.5% | +8.5 pp | $1.011 / $0.358 | -$1.908 / -$1.036 |
| vault open10 taker | most liquid third | 303 (0) | 63.0% | 58.1% | 219 | 61.6% | 84 | 58.3% | +3.3 pp | $1.257 / $0.624 | -$3.725 / -$1.272 |
| vault open20 maker | ALL | 6,589 (1) | 67.4% | 57.8% | 4,926 | 62.1% | 1,663 | 57.4% | +4.7 pp | $1.477 / $0.698 | -$3.061 / -$1.572 |
| vault open20 maker | least liquid third | 4,357 (1) | 67.8% | 58.1% | 3,299 | 61.6% | 1,058 | 58.2% | +3.4 pp | $1.335 / $0.654 | -$2.589 / -$1.262 |
| vault open20 maker | middle third | 1,713 (0) | 67.1% | 56.7% | 1,243 | 63.6% | 470 | 55.7% | +7.9 pp | $1.682 / $0.696 | -$3.365 / -$2.090 |
| vault open20 maker | most liquid third | 519 (0) | 65.3% | 59.0% | 384 | 61.7% | 135 | 57.0% | +4.7 pp | $2.034 / $1.087 | -$5.706 / -$2.196 |
| vault open20 taker | ALL | 6,512 (1) | 67.2% | 57.8% | 4,842 | 61.7% | 1,670 | 56.9% | +4.8 pp | $0.887 / $0.411 | -$1.837 / -$0.955 |
| vault open20 taker | least liquid third | 4,328 (1) | 67.2% | 57.9% | 3,253 | 60.9% | 1,075 | 57.7% | +3.2 pp | $0.789 / $0.377 | -$1.548 / -$0.745 |
| vault open20 taker | middle third | 1,676 (0) | 67.8% | 57.1% | 1,223 | 64.0% | 453 | 55.6% | +8.4 pp | $1.032 / $0.413 | -$1.968 / -$1.170 |
| vault open20 taker | most liquid third | 508 (0) | 64.8% | 58.5% | 366 | 61.5% | 142 | 55.6% | +5.8 pp | $1.283 / $0.711 | -$3.606 / -$1.853 |
| test open10 maker | ALL | 8,069 (0) | 65.6% | 59.3% | 6,080 | 59.8% | 1,988 | 59.9% | -0.1 pp | $1.673 / $0.918 | -$3.674 / -$1.674 |
| test open10 maker | least liquid third | 5,748 (0) | 65.8% | 60.4% | 4,385 | 58.3% | 1,362 | 60.2% | -1.9 pp | $1.549 / $0.920 | -$3.483 / -$1.373 |
| test open10 maker | middle third | 1,782 (0) | 64.9% | 56.3% | 1,300 | 63.9% | 482 | 60.2% | +3.8 pp | $1.815 / $0.852 | -$3.755 / -$2.128 |
| test open10 maker | most liquid third | 539 (0) | 65.7% | 57.1% | 395 | 62.0% | 144 | 56.2% | +5.8 pp | $2.582 / $1.105 | -$5.202 / -$3.002 |
| test open10 taker | ALL | 8,078 (0) | 65.5% | 59.4% | 6,069 | 59.8% | 2,008 | 59.7% | +0.1 pp | $1.044 / $0.560 | -$2.251 / -$1.036 |
| test open10 taker | least liquid third | 5,752 (0) | 65.7% | 60.4% | 4,375 | 58.1% | 1,376 | 59.4% | -1.3 pp | $0.961 / $0.577 | -$2.049 / -$0.898 |
| test open10 taker | middle third | 1,797 (0) | 64.8% | 57.0% | 1,312 | 63.9% | 485 | 60.2% | +3.7 pp | $1.130 / $0.487 | -$2.419 / -$1.214 |
| test open10 taker | most liquid third | 529 (0) | 65.8% | 56.5% | 382 | 64.4% | 147 | 59.9% | +4.5 pp | $1.700 / $0.617 | -$3.586 / -$1.745 |
| test open20 maker | ALL | 13,734 (1) | 65.1% | 59.1% | 10,261 | 59.9% | 3,472 | 59.7% | +0.2 pp | $4.484 / $2.272 | -$9.487 / -$4.557 |
| test open20 maker | least liquid third | 9,703 (1) | 65.7% | 60.0% | 7,360 | 58.5% | 2,342 | 59.4% | -0.9 pp | $4.086 / $2.239 | -$8.446 / -$3.737 |
| test open20 maker | middle third | 3,123 (0) | 63.4% | 56.3% | 2,237 | 63.8% | 886 | 61.4% | +2.4 pp | $4.946 / $2.156 | -$10.696 / -$5.603 |
| test open20 maker | most liquid third | 908 (0) | 64.3% | 58.4% | 664 | 62.2% | 244 | 56.6% | +5.6 pp | $7.337 / $3.032 | -$15.087 / -$8.630 |
| test open20 taker | ALL | 13,698 (1) | 65.2% | 59.0% | 10,218 | 60.0% | 3,479 | 59.8% | +0.2 pp | $1.676 / $0.864 | -$3.505 / -$1.622 |
| test open20 taker | least liquid third | 9,676 (1) | 65.7% | 60.0% | 7,322 | 58.5% | 2,353 | 59.4% | -0.9 pp | $1.554 / $0.872 | -$3.164 / -$1.410 |
| test open20 taker | middle third | 3,123 (0) | 63.5% | 56.2% | 2,233 | 63.7% | 890 | 61.5% | +2.2 pp | $1.807 / $0.769 | -$3.964 / -$1.918 |
| test open20 taker | most liquid third | 899 (0) | 65.1% | 58.0% | 663 | 63.5% | 236 | 57.2% | +6.3 pp | $2.584 / $1.099 | -$5.165 / -$2.617 |

## Close prices, label: larger vs smaller
Columns: classified trades (unclassified in brackets); share of trades where the larger leg made money; share where the smaller leg made money; winners and hero share; losers and culprit share; hero minus culprit (percentage points); mean leg gross in winners (larger / smaller); mean leg gross in losers (larger / smaller).

| run | group | trades (unclassified) | larger gross>0 | smaller gross>0 | winners | hero | losers | culprit | hero - culprit | winners: mean larger / smaller | losers: mean larger / smaller |
|---|---|---|---|---|---|---|---|---|---|---|---|
| vault open10 maker | ALL | 3,832 (0) | 68.7% | 56.7% | 2,888 | 68.0% | 944 | 64.0% | +4.0 pp | $1.276 / $0.335 | -$2.514 / -$0.974 |
| vault open10 maker | least liquid third | 2,549 (0) | 68.5% | 58.0% | 1,948 | 67.0% | 601 | 64.7% | +2.3 pp | $1.138 / $0.324 | -$2.184 / -$0.784 |
| vault open10 maker | middle third | 977 (0) | 69.2% | 53.7% | 707 | 69.9% | 270 | 62.2% | +7.7 pp | $1.440 / $0.328 | -$2.758 / -$1.328 |
| vault open10 maker | most liquid third | 306 (0) | 69.0% | 54.6% | 233 | 70.4% | 73 | 64.4% | +6.0 pp | $1.931 / $0.449 | -$4.338 / -$1.233 |
| vault open10 taker | ALL | 3,789 (0) | 68.5% | 56.4% | 2,839 | 68.5% | 950 | 63.8% | +4.8 pp | $0.978 / $0.240 | -$1.903 / -$0.755 |
| vault open10 taker | least liquid third | 2,510 (0) | 68.1% | 57.6% | 1,906 | 66.9% | 604 | 64.4% | +2.5 pp | $0.842 / $0.243 | -$1.651 / -$0.557 |
| vault open10 taker | middle third | 976 (0) | 69.7% | 54.3% | 714 | 71.3% | 262 | 63.7% | +7.5 pp | $1.127 / $0.242 | -$2.097 / -$0.847 |
| vault open10 taker | most liquid third | 303 (0) | 68.6% | 52.5% | 219 | 74.0% | 84 | 59.5% | +14.4 pp | $1.673 / $0.208 | -$3.103 / -$1.894 |
| vault open20 maker | ALL | 6,590 (0) | 68.7% | 56.5% | 4,927 | 68.3% | 1,663 | 64.0% | +4.2 pp | $1.747 / $0.428 | -$3.383 / -$1.251 |
| vault open20 maker | least liquid third | 4,358 (0) | 68.7% | 57.2% | 3,300 | 67.0% | 1,058 | 63.8% | +3.2 pp | $1.583 / $0.405 | -$2.721 / -$1.130 |
| vault open20 maker | middle third | 1,713 (0) | 68.8% | 55.0% | 1,243 | 70.7% | 470 | 64.0% | +6.7 pp | $1.892 / $0.485 | -$4.052 / -$1.404 |
| vault open20 maker | most liquid third | 519 (0) | 68.4% | 55.9% | 384 | 71.4% | 135 | 65.9% | +5.4 pp | $2.679 / $0.442 | -$6.242 / -$1.661 |
| vault open20 taker | ALL | 6,513 (0) | 68.4% | 56.5% | 4,843 | 68.0% | 1,670 | 63.5% | +4.5 pp | $1.022 / $0.276 | -$2.005 / -$0.786 |
| vault open20 taker | least liquid third | 4,329 (0) | 67.9% | 57.2% | 3,254 | 66.3% | 1,075 | 63.4% | +2.8 pp | $0.890 / $0.275 | -$1.623 / -$0.670 |
| vault open20 taker | middle third | 1,676 (0) | 69.5% | 55.5% | 1,223 | 70.7% | 453 | 63.1% | +7.6 pp | $1.156 / $0.289 | -$2.318 / -$0.820 |
| vault open20 taker | most liquid third | 508 (0) | 68.7% | 54.5% | 366 | 74.0% | 142 | 64.8% | +9.3 pp | $1.749 / $0.244 | -$3.902 / -$1.557 |
| test open10 maker | ALL | 8,069 (0) | 66.7% | 58.2% | 6,080 | 63.7% | 1,988 | 62.4% | +1.3 pp | $1.830 / $0.761 | -$3.736 / -$1.612 |
| test open10 maker | least liquid third | 5,748 (0) | 67.0% | 59.2% | 4,385 | 62.9% | 1,362 | 61.3% | +1.6 pp | $1.712 / $0.758 | -$3.254 / -$1.602 |
| test open10 maker | middle third | 1,782 (0) | 66.4% | 54.8% | 1,300 | 67.0% | 482 | 66.4% | +0.6 pp | $2.130 / $0.537 | -$4.452 / -$1.431 |
| test open10 maker | most liquid third | 539 (0) | 64.4% | 58.4% | 395 | 61.8% | 144 | 59.7% | +2.0 pp | $2.153 / $1.534 | -$5.901 / -$2.304 |
| test open10 taker | ALL | 8,078 (0) | 66.3% | 58.6% | 6,069 | 63.3% | 2,008 | 63.5% | -0.3 pp | $1.118 / $0.486 | -$2.338 / -$0.949 |
| test open10 taker | least liquid third | 5,752 (0) | 66.4% | 59.7% | 4,375 | 62.1% | 1,376 | 62.6% | -0.6 pp | $1.036 / $0.502 | -$2.027 / -$0.920 |
| test open10 taker | middle third | 1,797 (0) | 67.0% | 54.8% | 1,312 | 67.8% | 485 | 66.6% | +1.2 pp | $1.305 / $0.312 | -$2.656 / -$0.977 |
| test open10 taker | most liquid third | 529 (0) | 62.8% | 59.5% | 382 | 62.0% | 147 | 61.9% | +0.1 pp | $1.410 / $0.907 | -$4.206 / -$1.126 |
| test open20 maker | ALL | 13,735 (0) | 66.4% | 57.7% | 10,262 | 64.0% | 3,472 | 62.9% | +1.1 pp | $4.799 / $1.957 | -$9.756 / -$4.288 |
| test open20 maker | least liquid third | 9,704 (0) | 67.0% | 58.7% | 7,361 | 63.0% | 2,342 | 61.8% | +1.2 pp | $4.432 / $1.893 | -$8.148 / -$4.035 |
| test open20 maker | middle third | 3,123 (0) | 65.1% | 54.6% | 2,237 | 67.1% | 886 | 66.0% | +1.1 pp | $5.376 / $1.726 | -$11.913 / -$4.386 |
| test open20 maker | most liquid third | 908 (0) | 64.6% | 58.0% | 664 | 64.6% | 244 | 61.9% | +2.7 pp | $6.924 / $3.445 | -$17.363 / -$6.354 |
| test open20 taker | ALL | 13,699 (0) | 66.2% | 57.9% | 10,219 | 63.7% | 3,479 | 63.3% | +0.4 pp | $1.790 / $0.750 | -$3.643 / -$1.484 |
| test open20 taker | least liquid third | 9,677 (0) | 66.6% | 59.1% | 7,323 | 62.4% | 2,353 | 62.5% | -0.1 pp | $1.660 / $0.766 | -$3.171 / -$1.404 |
| test open20 taker | middle third | 3,123 (0) | 65.4% | 54.4% | 2,233 | 67.8% | 890 | 66.3% | +1.5 pp | $2.002 / $0.574 | -$4.381 / -$1.501 |
| test open20 taker | most liquid third | 899 (0) | 65.3% | 57.7% | 663 | 64.6% | 236 | 60.2% | +4.4 pp | $2.514 / $1.170 | -$5.570 / -$2.213 |

## Mid prices, label: mover vs hedge
Columns: classified trades (unclassified in brackets); share of trades where the mover leg made money; share where the hedge leg made money; winners and hero share; losers and culprit share; hero minus culprit (percentage points); mean leg gross in winners (mover / hedge); mean leg gross in losers (mover / hedge).

| run | group | trades (unclassified) | mover gross>0 | hedge gross>0 | winners | hero | losers | culprit | hero - culprit | winners: mean mover / hedge | losers: mean mover / hedge |
|---|---|---|---|---|---|---|---|---|---|---|---|
| vault open10 maker | ALL | 3,826 (1) | 64.5% | 56.1% | 2,831 | 61.6% | 994 | 58.0% | +3.6 pp | $0.987 / $0.445 | -$2.181 / -$1.150 |
| vault open10 maker | least liquid third | 2,546 (1) | 63.7% | 55.8% | 1,890 | 60.5% | 655 | 57.6% | +2.9 pp | $0.825 / $0.398 | -$1.803 / -$0.988 |
| vault open10 maker | middle third | 977 (0) | 66.8% | 55.4% | 709 | 65.6% | 268 | 59.3% | +6.3 pp | $1.245 / $0.462 | -$2.676 / -$1.421 |
| vault open10 maker | most liquid third | 303 (0) | 64.0% | 60.7% | 232 | 58.6% | 71 | 57.7% | +0.9 pp | $1.523 / $0.779 | -$3.804 / -$1.619 |
| vault open10 taker | ALL | 3,782 (1) | 64.8% | 55.6% | 2,779 | 61.7% | 1,002 | 57.6% | +4.1 pp | $0.762 / $0.333 | -$1.680 / -$0.851 |
| vault open10 taker | least liquid third | 2,506 (1) | 63.8% | 55.2% | 1,845 | 60.1% | 660 | 57.0% | +3.1 pp | $0.623 / $0.299 | -$1.330 / -$0.735 |
| vault open10 taker | middle third | 976 (0) | 67.7% | 55.3% | 716 | 66.1% | 260 | 58.5% | +7.6 pp | $0.982 / $0.338 | -$1.923 / -$1.032 |
| vault open10 taker | most liquid third | 300 (0) | 63.3% | 59.3% | 218 | 61.0% | 82 | 59.8% | +1.3 pp | $1.218 / $0.610 | -$3.729 / -$1.213 |
| vault open20 maker | ALL | 6,580 (1) | 64.9% | 55.9% | 4,832 | 62.2% | 1,746 | 56.9% | +5.3 pp | $1.355 / $0.592 | -$2.919 / -$1.525 |
| vault open20 maker | least liquid third | 4,353 (1) | 64.3% | 55.3% | 3,201 | 61.4% | 1,150 | 56.5% | +4.9 pp | $1.169 / $0.510 | -$2.400 / -$1.234 |
| vault open20 maker | middle third | 1,712 (0) | 66.4% | 56.4% | 1,249 | 64.1% | 463 | 57.5% | +6.7 pp | $1.634 / $0.661 | -$3.413 / -$2.086 |
| vault open20 maker | most liquid third | 515 (0) | 65.4% | 59.6% | 382 | 62.0% | 133 | 57.9% | +4.1 pp | $2.003 / $1.043 | -$5.683 / -$2.091 |
| vault open20 taker | ALL | 6,503 (1) | 64.7% | 55.8% | 4,745 | 62.0% | 1,756 | 56.4% | +5.6 pp | $0.821 / $0.354 | -$1.752 / -$0.921 |
| vault open20 taker | least liquid third | 4,324 (1) | 63.7% | 55.1% | 3,155 | 61.1% | 1,167 | 56.3% | +4.8 pp | $0.700 / $0.301 | -$1.438 / -$0.721 |
| vault open20 taker | middle third | 1,675 (0) | 67.4% | 56.7% | 1,226 | 64.7% | 449 | 56.8% | +7.9 pp | $1.003 / $0.391 | -$1.991 / -$1.159 |
| vault open20 taker | most liquid third | 504 (0) | 64.7% | 59.1% | 364 | 61.0% | 140 | 56.4% | +4.6 pp | $1.255 / $0.687 | -$3.603 / -$1.825 |
| test open10 maker | ALL | 8,033 (0) | 61.5% | 54.0% | 5,716 | 60.8% | 2,314 | 57.9% | +2.9 pp | $1.462 / $0.637 | -$3.187 / -$1.499 |
| test open10 maker | least liquid third | 5,724 (0) | 60.8% | 53.7% | 4,041 | 59.5% | 1,680 | 57.4% | +2.1 pp | $1.286 / $0.571 | -$2.840 / -$1.228 |
| test open10 maker | middle third | 1,776 (0) | 63.1% | 54.3% | 1,286 | 64.2% | 490 | 60.6% | +3.5 pp | $1.701 / $0.733 | -$3.777 / -$2.007 |
| test open10 maker | most liquid third | 533 (0) | 63.8% | 56.7% | 389 | 63.0% | 144 | 54.2% | +8.8 pp | $2.504 / $1.015 | -$5.234 / -$2.927 |
| test open10 taker | ALL | 8,042 (0) | 61.6% | 54.1% | 5,706 | 61.1% | 2,334 | 57.5% | +3.6 pp | $0.912 / $0.380 | -$1.958 / -$0.934 |
| test open10 taker | least liquid third | 5,728 (0) | 61.0% | 53.7% | 4,029 | 59.6% | 1,697 | 56.4% | +3.2 pp | $0.797 / $0.353 | -$1.674 / -$0.804 |
| test open10 taker | middle third | 1,790 (0) | 63.1% | 54.9% | 1,299 | 64.4% | 491 | 61.3% | +3.1 pp | $1.057 / $0.407 | -$2.445 / -$1.148 |
| test open10 taker | most liquid third | 524 (0) | 63.9% | 55.9% | 378 | 65.1% | 146 | 57.5% | +7.5 pp | $1.637 / $0.576 | -$3.628 / -$1.724 |
| test open20 maker | ALL | 13,681 (1) | 61.3% | 54.0% | 9,687 | 60.8% | 3,989 | 58.0% | +2.9 pp | $3.933 / $1.585 | -$8.306 / -$4.112 |
| test open20 maker | least liquid third | 9,670 (1) | 60.9% | 53.5% | 6,817 | 59.8% | 2,848 | 57.1% | +2.7 pp | $3.405 / $1.373 | -$6.976 / -$3.336 |
| test open20 maker | middle third | 3,112 (0) | 62.2% | 54.3% | 2,216 | 63.6% | 896 | 61.6% | +2.0 pp | $4.617 / $1.873 | -$10.724 / -$5.358 |
| test open20 maker | most liquid third | 899 (0) | 63.0% | 57.5% | 654 | 62.2% | 245 | 55.1% | +7.1 pp | $7.121 / $2.812 | -$14.922 / -$8.570 |
| test open20 taker | ALL | 13,645 (1) | 61.4% | 53.9% | 9,645 | 61.0% | 3,994 | 57.8% | +3.1 pp | $1.457 / $0.600 | -$3.074 / -$1.497 |
| test open20 taker | least liquid third | 9,643 (1) | 60.9% | 53.3% | 6,777 | 59.9% | 2,860 | 56.7% | +3.1 pp | $1.280 / $0.539 | -$2.620 / -$1.291 |
| test open20 taker | middle third | 3,112 (0) | 62.2% | 54.8% | 2,213 | 63.5% | 899 | 61.8% | +1.6 pp | $1.694 / $0.659 | -$3.975 / -$1.852 |
| test open20 taker | most liquid third | 890 (0) | 63.7% | 57.0% | 655 | 63.7% | 235 | 55.7% | +7.9 pp | $2.495 / $1.034 | -$5.152 / -$2.640 |

## Mid prices, label: larger vs smaller
Columns: classified trades (unclassified in brackets); share of trades where the larger leg made money; share where the smaller leg made money; winners and hero share; losers and culprit share; hero minus culprit (percentage points); mean leg gross in winners (larger / smaller); mean leg gross in losers (larger / smaller).

| run | group | trades (unclassified) | larger gross>0 | smaller gross>0 | winners | hero | losers | culprit | hero - culprit | winners: mean larger / smaller | losers: mean larger / smaller |
|---|---|---|---|---|---|---|---|---|---|---|---|
| vault open10 maker | ALL | 3,827 (0) | 65.6% | 55.0% | 2,831 | 66.9% | 995 | 63.8% | +3.1 pp | $1.144 / $0.289 | -$2.393 / -$0.935 |
| vault open10 maker | least liquid third | 2,547 (0) | 63.8% | 55.6% | 1,890 | 65.6% | 656 | 63.9% | +1.7 pp | $0.959 / $0.265 | -$2.031 / -$0.756 |
| vault open10 maker | middle third | 977 (0) | 69.1% | 53.1% | 709 | 69.4% | 268 | 63.4% | +6.0 pp | $1.402 / $0.305 | -$2.768 / -$1.329 |
| vault open10 maker | most liquid third | 303 (0) | 69.0% | 55.8% | 232 | 69.8% | 71 | 64.8% | +5.0 pp | $1.867 / $0.435 | -$4.312 / -$1.111 |
| vault open10 taker | ALL | 3,783 (0) | 65.6% | 54.7% | 2,779 | 67.6% | 1,003 | 63.6% | +4.0 pp | $0.888 / $0.208 | -$1.801 / -$0.729 |
| vault open10 taker | least liquid third | 2,507 (0) | 63.7% | 55.2% | 1,845 | 65.5% | 661 | 63.4% | +2.1 pp | $0.719 / $0.203 | -$1.520 / -$0.543 |
| vault open10 taker | middle third | 976 (0) | 69.5% | 53.6% | 716 | 71.2% | 260 | 65.0% | +6.2 pp | $1.096 / $0.224 | -$2.106 / -$0.849 |
| vault open10 taker | most liquid third | 300 (0) | 69.0% | 53.7% | 218 | 73.4% | 82 | 61.0% | +12.4 pp | $1.628 / $0.200 | -$3.093 / -$1.848 |
| vault open20 maker | ALL | 6,581 (0) | 65.9% | 54.9% | 4,832 | 67.5% | 1,747 | 63.9% | +3.7 pp | $1.577 / $0.369 | -$3.235 / -$1.207 |
| vault open20 maker | least liquid third | 4,354 (0) | 64.6% | 54.9% | 3,201 | 66.0% | 1,151 | 63.0% | +3.0 pp | $1.347 / $0.332 | -$2.544 / -$1.088 |
| vault open20 maker | middle third | 1,712 (0) | 68.2% | 54.6% | 1,249 | 70.3% | 463 | 65.2% | +5.1 pp | $1.843 / $0.452 | -$4.094 / -$1.404 |
| vault open20 maker | most liquid third | 515 (0) | 69.1% | 55.9% | 382 | 71.7% | 133 | 66.9% | +4.8 pp | $2.640 / $0.406 | -$6.227 / -$1.547 |
| vault open20 taker | ALL | 6,504 (0) | 65.6% | 54.9% | 4,745 | 67.2% | 1,757 | 63.3% | +3.9 pp | $0.932 / $0.242 | -$1.915 / -$0.757 |
| vault open20 taker | least liquid third | 4,325 (0) | 63.9% | 54.9% | 3,155 | 65.2% | 1,168 | 62.8% | +2.3 pp | $0.766 / $0.234 | -$1.515 / -$0.643 |
| vault open20 taker | middle third | 1,675 (0) | 69.0% | 55.1% | 1,226 | 70.4% | 449 | 63.7% | +6.7 pp | $1.125 / $0.268 | -$2.333 / -$0.817 |
| vault open20 taker | most liquid third | 504 (0) | 69.2% | 54.6% | 364 | 73.6% | 140 | 65.7% | +7.9 pp | $1.717 / $0.225 | -$3.909 / -$1.519 |
| test open10 maker | ALL | 8,033 (0) | 62.4% | 53.2% | 5,716 | 63.7% | 2,314 | 61.0% | +2.7 pp | $1.614 / $0.486 | -$3.311 / -$1.375 |
| test open10 maker | least liquid third | 5,724 (0) | 61.5% | 53.1% | 4,041 | 62.6% | 1,680 | 59.8% | +2.8 pp | $1.448 / $0.409 | -$2.762 / -$1.305 |
| test open10 maker | middle third | 1,776 (0) | 64.9% | 52.5% | 1,286 | 67.6% | 490 | 65.7% | +1.9 pp | $2.000 / $0.434 | -$4.413 / -$1.371 |
| test open10 maker | most liquid third | 533 (0) | 63.4% | 57.0% | 389 | 62.5% | 144 | 59.7% | +2.7 pp | $2.058 / $1.461 | -$5.962 / -$2.199 |
| test open10 taker | ALL | 8,042 (0) | 62.1% | 53.6% | 5,706 | 63.4% | 2,334 | 61.7% | +1.7 pp | $0.980 / $0.312 | -$2.075 / -$0.817 |
| test open10 taker | least liquid third | 5,728 (0) | 61.1% | 53.5% | 4,029 | 62.0% | 1,697 | 60.5% | +1.5 pp | $0.869 / $0.281 | -$1.726 / -$0.752 |
| test open10 taker | middle third | 1,790 (0) | 65.6% | 52.4% | 1,299 | 67.9% | 491 | 66.0% | +1.9 pp | $1.215 / $0.248 | -$2.631 / -$0.961 |
| test open10 taker | most liquid third | 524 (0) | 61.3% | 58.6% | 378 | 62.4% | 146 | 61.6% | +0.8 pp | $1.350 / $0.864 | -$4.268 / -$1.084 |
| test open20 maker | ALL | 13,682 (0) | 62.4% | 53.0% | 9,687 | 63.9% | 3,990 | 61.6% | +2.3 pp | $4.244 / $1.274 | -$8.690 / -$3.725 |
| test open20 maker | least liquid third | 9,671 (0) | 61.7% | 52.8% | 6,817 | 62.6% | 2,849 | 60.2% | +2.4 pp | $3.759 / $1.019 | -$6.944 / -$3.365 |
| test open20 maker | middle third | 3,112 (0) | 64.1% | 52.4% | 2,216 | 67.5% | 896 | 65.7% | +1.7 pp | $5.012 / $1.478 | -$11.826 / -$4.256 |
| test open20 maker | most liquid third | 899 (0) | 63.6% | 56.8% | 654 | 64.7% | 245 | 62.0% | +2.6 pp | $6.690 / $3.243 | -$17.522 / -$5.970 |
| test open20 taker | ALL | 13,646 (0) | 62.1% | 53.2% | 9,645 | 63.7% | 3,995 | 62.2% | +1.5 pp | $1.575 / $0.482 | -$3.264 / -$1.305 |
| test open20 taker | least liquid third | 9,644 (0) | 61.2% | 53.1% | 6,777 | 62.2% | 2,861 | 61.0% | +1.2 pp | $1.393 / $0.426 | -$2.723 / -$1.186 |
| test open20 taker | middle third | 3,112 (0) | 64.5% | 52.5% | 2,213 | 67.9% | 899 | 66.2% | +1.7 pp | $1.876 / $0.477 | -$4.355 / -$1.472 |
| test open20 taker | most liquid third | 890 (0) | 64.2% | 56.5% | 655 | 64.7% | 235 | 60.4% | +4.3 pp | $2.443 / $1.087 | -$5.681 / -$2.111 |

## Receipts
Asserted by the script: classified + unclassified = trades in the set; winners + losers + zero-gross = classified; first-leg + second-leg gross = trade gross over the classified trades; the first-leg total (ALL, close and mid, both labels) equals the costs_legs.json split total to 1e-6 with the same leg count.
