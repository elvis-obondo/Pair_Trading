# COSTS1 - no-bounce check: the close vs mid gap
Source: logs/costs1/costs_nobounce.json (sha256 874b5e11c115), written by diagnostics/costs_nobounce.py; the log is diagnostics/costs_nobounce.log. Rules: costs1_rules.md section 10. This section is written by diagnostics/costs_nobounce_section.py; no number is typed by hand.

## Headline cell
Vault, q 1% / no stop / taker / open10. With the G8 table mid as a labelled fallback where the ctxs mid is missing, 3,783 trades have all four mids (99.8% coverage). On those trades the close-based gross is $945.69 and the mid-to-mid gross is $508.34. **Gross ratio 53.8%. Band: PARTLY close vs mid gap (25% to 75%).**
Net after fees on the same trades: close-based $277.63, mid-to-mid $-159.72 (net ratio -57.5%). Fees do not change, so the net ratio moves more than the gross ratio.
Ctxs mid only (no band; coverage 74.8%, 2,836 trades, skewed to the earlier days): gross ratio 70.5%, close gross $953.17, mid gross $671.87.
How not to over-read the headline: the 53.8% mixes fresh and stale trades (1,839 fresh at a gross ratio of 85.0%, 1,944 stale at 28.4%). The ctxs-only 70.5% is a different, earlier set of trades, not the same trades with another mid. The two mid sources disagree by more than 1 bp on 45.0% of the vault minutes where both exist, but on the same trades they give the same gross ratio (source-sensitivity table below).

## Source-sensitivity line (print only; no change to the headline or the bands)
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

## Period-sensitivity line (print only; no change to the headline or the bands)
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

## The eight priority runs (q 1% / no stop), ctxs + G8 fallback
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

### Gross ratio by liquidity tier (ctxs + G8 fallback)
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

### B - C, per fill
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

## Entry stretch: |z| from closes vs from mids (sigma)
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

## Reversion in mid terms
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

## Does p still rank in mid terms
10-hour reach rate by quintile of raw p_10h (1 = lowest), close (same minutes) vs mid, and the lift at the top 1% (reach of the q 1% picks / reach of all events). Test months pool the predictions of different fold models.
| period | q1 close / mid | q2 | q3 | q4 | q5 | lift top 1%, close | lift top 1%, mid |
|---|---|---|---|---|---|---|---|
| vault | 13.4% / 13.3% | 22.0% / 21.6% | 30.0% / 29.5% | 38.7% / 38.1% | 51.3% / 50.3% | 2.11x | 2.09x |
| test | 14.2% / 13.8% | 23.5% / 22.6% | 31.8% / 30.5% | 40.6% / 38.8% | 53.7% / 50.4% | 2.07x | 1.98x |

## Coverage and the two mids
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

## Notes (what the numbers are and are not)
- The signal is still built from closes. A signal built from mids is NOT tested here.
- The engine's close is the last trade, which can be older than the mid snapshot. 'Fresh' means a trade in that minute, not at the end of it, so a fresh close can still be up to 59 seconds older than the mid. The fresh stratum's gap is therefore an upper bound on bounce, and the stale stratum's gap is stale price.
- The ctxs mid and the G8 table mid disagree by more than 1 bp on a large share of minutes (table above). Either one is a few seconds after the bar's last trade. The fallback mixes the two sources inside some trades. Results with the fallback and without it differ, and the ctxs-only set leans to the earlier months.
- The same-minutes close comparator was decided after a smoke run of about 3,000 vault events. Process, from this session's own transcript timestamps (UTC, diagnostics/costs_process_times.py): the planner's rulings on the G8 fallback, the gross-ratio bands and the 'close vs mid gap' label reached the builder at 2026-11-18T05:07:36.480Z; the first smoke run (event-level statistics only, no trade table) first appears in the transcript at 2026-11-18T05:10:27.547Z; the smoke run that first printed the vault trade table (it ran the rewritten reprice()) first appears in the transcript at 2026-11-18T05:11:16.812Z. The rulings came first. The 25% and 75% band values were in the original brief.
- Test-month quintiles pool the predictions of different fold models.
- Findings are reported, not acted on. No pick, exit or parameter was changed.
