## [HL-PROFIT1 open20] Portfolio backtest, S1's live picks, build2 d3/asm price, slippage_spread_share=0.0, max_open=20

Runs ending above the $1000 start: 19/24.

| q | stop | fee | final_equity | total_return | n_trades | win_rate | profit_factor | sharpe | sortino | max_dd_pct |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.01 | 0p5 | taker | 130.73 | -0.8693 | 22,681 | 0.2805 | 0.7599 | -9.821 | -11.419 | -0.8693 |
| 0.01 | 0p5 | maker | 1207.36 | 0.2074 | 28,556 | 0.2766 | 1.0215 | 1.081 | 1.957 | -0.1683 |
| 0.01 | 1p0 | taker | 270.90 | -0.7291 | 24,169 | 0.4035 | 0.8925 | -5.187 | -7.201 | -0.7291 |
| 0.01 | 1p0 | maker | 3525.20 | 2.5252 | 25,127 | 0.4052 | 1.1117 | 5.274 | 12.709 | -0.1275 |
| 0.01 | 2p0 | taker | 1132.54 | 0.1325 | 20,432 | 0.5519 | 1.0093 | 0.692 | 1.261 | -0.3969 |
| 0.01 | 2p0 | maker | 9270.44 | 8.2704 | 20,508 | 0.5517 | 1.1686 | 8.036 | 20.308 | -0.0968 |
| 0.01 | none | taker | 4036.05 | 3.0360 | 13,699 | 0.6996 | 1.1579 | 4.644 | 8.130 | -0.1627 |
| 0.01 | none | maker | 16935.92 | 15.9359 | 13,735 | 0.7004 | 1.3184 | 8.681 | 16.611 | -0.1749 |
| 0.005 | 0p5 | taker | 282.29 | -0.7177 | 15,108 | 0.2799 | 0.7736 | -7.071 | -9.032 | -0.7177 |
| 0.005 | 0p5 | maker | 1379.20 | 0.3792 | 16,106 | 0.2812 | 1.0685 | 2.069 | 4.227 | -0.1211 |
| 0.005 | 1p0 | taker | 616.25 | -0.3838 | 14,755 | 0.4115 | 0.9270 | -2.368 | -3.614 | -0.3838 |
| 0.005 | 1p0 | maker | 2768.95 | 1.7689 | 15,139 | 0.4115 | 1.1724 | 5.362 | 12.653 | -0.0723 |
| 0.005 | 2p0 | taker | 1509.28 | 0.5093 | 13,241 | 0.5609 | 1.0551 | 2.014 | 3.467 | -0.1926 |
| 0.005 | 2p0 | maker | 5736.34 | 4.7363 | 13,340 | 0.5611 | 1.2507 | 7.541 | 15.538 | -0.0805 |
| 0.005 | none | taker | 3369.67 | 2.3697 | 9,965 | 0.7121 | 1.1932 | 4.263 | 7.371 | -0.1618 |
| 0.005 | none | maker | 9749.47 | 8.7495 | 9,992 | 0.7137 | 1.3802 | 7.383 | 13.457 | -0.1370 |
| 0.001 | 0p5 | taker | 865.11 | -0.1349 | 3,427 | 0.2971 | 0.8807 | -1.888 | -3.313 | -0.1387 |
| 0.001 | 0p5 | maker | 1225.71 | 0.2257 | 3,469 | 0.2998 | 1.2094 | 2.665 | 7.744 | -0.0363 |
| 0.001 | 1p0 | taker | 1033.16 | 0.0332 | 3,430 | 0.4289 | 1.0221 | 0.438 | 0.898 | -0.0885 |
| 0.001 | 1p0 | maker | 1459.65 | 0.4597 | 3,465 | 0.4291 | 1.2959 | 3.956 | 11.955 | -0.0297 |
| 0.001 | 2p0 | taker | 1200.27 | 0.2003 | 3,369 | 0.5767 | 1.1055 | 1.776 | 3.010 | -0.0751 |
| 0.001 | 2p0 | maker | 1686.80 | 0.6868 | 3,404 | 0.5764 | 1.3295 | 4.609 | 9.292 | -0.0449 |
| 0.001 | none | taker | 1586.60 | 0.5866 | 3,144 | 0.7376 | 1.2475 | 3.168 | 3.568 | -0.1140 |
| 0.001 | none | maker | 2078.90 | 1.0789 | 3,164 | 0.7383 | 1.4042 | 4.654 | 5.132 | -0.1098 |

### Costs (USD and share of gross), per run
| q | stop | fee | gross | fee | fee_share | slippage | slip_share | funding_paid | fund_paid_share | funding_received | fund_recv_share |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.01 | 0p5 | taker | 520.66 | 1390.33 | 2.6703 | 0.00 | 0.0000 | 13.03 | 0.0250 | 13.42 | 0.0258 |
| 0.01 | 0p5 | maker | 1810.22 | 1603.43 | 0.8858 | 0.00 | 0.0000 | 46.42 | 0.0256 | 47.00 | 0.0260 |
| 0.01 | 1p0 | taker | 1407.26 | 2132.81 | 1.5156 | 0.00 | 0.0000 | 41.02 | 0.0292 | 37.47 | 0.0266 |
| 0.01 | 1p0 | maker | 5424.22 | 2889.76 | 0.5328 | 0.00 | 0.0000 | 157.14 | 0.0290 | 147.87 | 0.0273 |
| 0.01 | 2p0 | taker | 4088.10 | 3947.24 | 0.9655 | 0.00 | 0.0000 | 132.13 | 0.0323 | 123.81 | 0.0303 |
| 0.01 | 2p0 | maker | 13265.90 | 4991.71 | 0.3763 | 0.00 | 0.0000 | 447.43 | 0.0337 | 443.69 | 0.0334 |
| 0.01 | none | taker | 8126.25 | 5036.80 | 0.6198 | 0.00 | 0.0000 | 417.15 | 0.0513 | 363.75 | 0.0448 |
| 0.01 | none | maker | 20570.67 | 4576.51 | 0.2225 | 0.00 | 0.0000 | 1021.22 | 0.0496 | 962.99 | 0.0468 |
| 0.005 | 0p5 | taker | 529.24 | 1246.38 | 2.3550 | 0.00 | 0.0000 | 12.08 | 0.0228 | 11.51 | 0.0218 |
| 0.005 | 0p5 | maker | 1317.99 | 937.64 | 0.7114 | 0.00 | 0.0000 | 27.10 | 0.0206 | 25.94 | 0.0197 |
| 0.005 | 1p0 | taker | 1340.24 | 1720.46 | 1.2837 | 0.00 | 0.0000 | 32.66 | 0.0244 | 29.13 | 0.0217 |
| 0.005 | 1p0 | maker | 3116.97 | 1340.36 | 0.4300 | 0.00 | 0.0000 | 74.34 | 0.0238 | 66.68 | 0.0214 |
| 0.005 | 2p0 | taker | 3162.49 | 2644.72 | 0.8363 | 0.00 | 0.0000 | 85.90 | 0.0272 | 77.41 | 0.0245 |
| 0.005 | 2p0 | maker | 6760.11 | 2004.51 | 0.2965 | 0.00 | 0.0000 | 186.60 | 0.0276 | 167.33 | 0.0248 |
| 0.005 | none | taker | 5679.96 | 3274.99 | 0.5766 | 0.00 | 0.0000 | 274.91 | 0.0484 | 239.61 | 0.0422 |
| 0.005 | none | maker | 10958.52 | 2166.90 | 0.1977 | 0.00 | 0.0000 | 515.33 | 0.0470 | 473.18 | 0.0432 |
| 0.001 | 0p5 | taker | 347.62 | 481.39 | 1.3848 | 0.00 | 0.0000 | 5.00 | 0.0144 | 3.86 | 0.0111 |
| 0.001 | 0p5 | maker | 420.49 | 193.14 | 0.4593 | 0.00 | 0.0000 | 6.26 | 0.0149 | 4.61 | 0.0110 |
| 0.001 | 1p0 | taker | 560.94 | 526.01 | 0.9377 | 0.00 | 0.0000 | 10.32 | 0.0184 | 8.54 | 0.0152 |
| 0.001 | 1p0 | maker | 673.95 | 212.00 | 0.3146 | 0.00 | 0.0000 | 12.62 | 0.0187 | 10.32 | 0.0153 |
| 0.001 | 2p0 | taker | 758.66 | 553.72 | 0.7299 | 0.00 | 0.0000 | 20.96 | 0.0276 | 16.29 | 0.0215 |
| 0.001 | 2p0 | maker | 916.40 | 223.95 | 0.2444 | 0.00 | 0.0000 | 25.37 | 0.0277 | 19.73 | 0.0215 |
| 0.001 | none | taker | 1219.05 | 615.20 | 0.5047 | 0.00 | 0.0000 | 61.21 | 0.0502 | 43.96 | 0.0361 |
| 0.001 | none | maker | 1338.56 | 238.21 | 0.1780 | 0.00 | 0.0000 | 72.25 | 0.0540 | 50.80 | 0.0380 |

### CAGR (annualised, N days), per run
| q | stop | fee | cagr | cagr_n_days |
|---|---|---|---|---|
| 0.01 | 0p5 | taker | -0.9747 | 202 |
| 0.01 | 0p5 | maker | 0.4033 | 203 |
| 0.01 | 1p0 | taker | -0.9045 | 203 |
| 0.01 | 1p0 | maker | 8.6350 | 203 |
| 0.01 | 2p0 | taker | 0.2508 | 203 |
| 0.01 | 2p0 | maker | 53.8120 | 203 |
| 0.01 | none | taker | 11.2893 | 203 |
| 0.01 | none | maker | 160.9700 | 203 |
| 0.005 | 0p5 | taker | -0.8983 | 202 |
| 0.005 | 0p5 | maker | 0.7826 | 203 |
| 0.005 | 1p0 | taker | -0.5812 | 203 |
| 0.005 | 1p0 | maker | 5.2416 | 203 |
| 0.005 | 2p0 | taker | 1.0962 | 203 |
| 0.005 | 2p0 | maker | 22.1232 | 203 |
| 0.005 | none | taker | 7.8842 | 203 |
| 0.005 | none | maker | 59.0091 | 203 |
| 0.001 | 0p5 | taker | -0.2304 | 202 |
| 0.001 | 0p5 | maker | 0.4445 | 202 |
| 0.001 | 1p0 | taker | 0.0607 | 202 |
| 0.001 | 1p0 | maker | 0.9806 | 202 |
| 0.001 | 2p0 | taker | 0.3908 | 202 |
| 0.001 | 2p0 | maker | 1.5721 | 202 |
| 0.001 | none | taker | 1.2932 | 203 |
| 0.001 | none | maker | 2.7280 | 203 |

### Daily P&L, per run
| q | stop | fee | mean | median | share_positive_days | worst_day | best_day |
|---|---|---|---|---|---|---|---|
| 0.01 | 0p5 | taker | -4.2821 | -1.2179 | 0.2020 | -74.86 | 18.65 |
| 0.01 | 0p5 | maker | 1.0165 | -0.7887 | 0.4657 | -48.21 | 124.24 |
| 0.01 | 1p0 | taker | -3.5740 | -2.2311 | 0.3431 | -77.52 | 51.78 |
| 0.01 | 1p0 | maker | 12.3784 | 1.4245 | 0.5196 | -114.51 | 316.33 |
| 0.01 | 2p0 | taker | 0.6497 | -1.0191 | 0.4706 | -111.32 | 162.17 |
| 0.01 | 2p0 | maker | 40.5414 | 18.2574 | 0.6520 | -367.50 | 795.75 |
| 0.01 | none | taker | 14.8826 | 13.2884 | 0.6324 | -226.88 | 318.18 |
| 0.01 | none | maker | 78.1173 | 45.7313 | 0.7010 | -580.82 | 982.04 |
| 0.005 | 0p5 | taker | -3.5355 | -1.6245 | 0.2660 | -45.99 | 38.42 |
| 0.005 | 0p5 | maker | 1.8588 | -0.1563 | 0.4902 | -41.36 | 143.34 |
| 0.005 | 1p0 | taker | -1.8811 | -1.8573 | 0.3725 | -61.00 | 85.89 |
| 0.005 | 1p0 | maker | 8.6713 | 1.2776 | 0.5539 | -96.82 | 270.78 |
| 0.005 | 2p0 | taker | 2.4965 | 0.7539 | 0.5196 | -81.78 | 168.60 |
| 0.005 | 2p0 | maker | 23.2174 | 10.3922 | 0.6471 | -199.29 | 418.35 |
| 0.005 | none | taker | 11.6160 | 10.0456 | 0.6324 | -271.05 | 329.94 |
| 0.005 | none | maker | 42.8896 | 27.9889 | 0.7108 | -508.92 | 750.56 |
| 0.001 | 0p5 | taker | -0.6645 | -0.4765 | 0.3153 | -19.25 | 61.14 |
| 0.001 | 0p5 | maker | 1.1119 | 0.0000 | 0.4483 | -19.06 | 90.94 |
| 0.001 | 1p0 | taker | 0.1633 | -0.2423 | 0.3744 | -20.34 | 92.33 |
| 0.001 | 1p0 | maker | 2.2643 | 0.1943 | 0.5222 | -25.16 | 132.22 |
| 0.001 | 2p0 | taker | 0.9865 | 0.0000 | 0.4335 | -36.04 | 108.16 |
| 0.001 | 2p0 | maker | 3.3833 | 0.6392 | 0.5517 | -41.63 | 155.56 |
| 0.001 | none | taker | 2.8755 | 1.2255 | 0.6078 | -83.46 | 103.41 |
| 0.001 | none | maker | 5.2887 | 2.3997 | 0.6667 | -103.82 | 139.09 |

### Trades, per run
| q | stop | fee | win_rate(mu) | stop_share | timeout_share | mean_net | median_net | mean_roc | median_roc | mean_win | mean_loss | mean_holding_min |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.01 | 0p5 | taker | 0.2805 | 0.7173 | 0.0023 | -0.0383 | -0.1123 | -0.0018 | -0.0078 | 0.4292 | -0.2225 | 46.8 |
| 0.01 | 0p5 | maker | 0.2766 | 0.7213 | 0.0021 | 0.0073 | -0.3123 | 0.0002 | -0.0058 | 1.2408 | -0.4691 | 47.4 |
| 0.01 | 1p0 | taker | 0.4035 | 0.5886 | 0.0079 | -0.0302 | -0.2369 | -0.0010 | -0.0098 | 0.6128 | -0.4743 | 81.2 |
| 0.01 | 1p0 | maker | 0.4052 | 0.5868 | 0.0080 | 0.1005 | -0.6538 | 0.0010 | -0.0078 | 2.4354 | -1.5277 | 82.0 |
| 0.01 | 2p0 | taker | 0.5519 | 0.4178 | 0.0303 | 0.0065 | 0.4744 | 0.0002 | 0.0077 | 1.2459 | -1.6087 | 138.5 |
| 0.01 | 2p0 | maker | 0.5517 | 0.4179 | 0.0303 | 0.4033 | 1.1568 | 0.0022 | 0.0096 | 4.9243 | -5.5345 | 138.8 |
| 0.01 | none | taker | 0.6996 | 0.0000 | 0.3004 | 0.2216 | 1.1361 | 0.0021 | 0.0114 | 2.2149 | -5.2723 | 290.4 |
| 0.01 | none | maker | 0.7004 | 0.0000 | 0.2996 | 1.1602 | 2.3024 | 0.0042 | 0.0134 | 6.4735 | -14.1357 | 290.1 |
| 0.005 | 0p5 | taker | 0.2799 | 0.7184 | 0.0018 | -0.0475 | -0.1825 | -0.0017 | -0.0076 | 0.5770 | -0.2920 | 43.7 |
| 0.005 | 0p5 | maker | 0.2812 | 0.7172 | 0.0016 | 0.0235 | -0.3173 | 0.0004 | -0.0056 | 1.2993 | -0.4794 | 44.4 |
| 0.005 | 1p0 | taker | 0.4115 | 0.5816 | 0.0070 | -0.0260 | -0.3499 | -0.0006 | -0.0094 | 0.7948 | -0.6089 | 76.8 |
| 0.005 | 1p0 | maker | 0.4115 | 0.5814 | 0.0071 | 0.1168 | -0.5240 | 0.0014 | -0.0074 | 1.9087 | -1.1613 | 77.6 |
| 0.005 | 2p0 | taker | 0.5609 | 0.4120 | 0.0271 | 0.0385 | 0.4816 | 0.0007 | 0.0076 | 1.2855 | -1.6349 | 131.3 |
| 0.005 | 2p0 | maker | 0.5611 | 0.4117 | 0.0272 | 0.3550 | 0.9403 | 0.0027 | 0.0096 | 3.0775 | -3.3367 | 131.0 |
| 0.005 | none | taker | 0.7121 | 0.0000 | 0.2879 | 0.2378 | 1.0723 | 0.0026 | 0.0113 | 1.9790 | -4.7750 | 281.5 |
| 0.005 | none | maker | 0.7137 | 0.0000 | 0.2863 | 0.8756 | 1.8855 | 0.0047 | 0.0134 | 4.2309 | -9.2604 | 281.1 |
| 0.001 | 0p5 | taker | 0.2971 | 0.7015 | 0.0015 | -0.0394 | -0.3271 | -0.0008 | -0.0070 | 0.9759 | -0.4696 | 37.9 |
| 0.001 | 0p5 | maker | 0.2998 | 0.6988 | 0.0014 | 0.0651 | -0.2846 | 0.0012 | -0.0051 | 1.2487 | -0.4445 | 38.1 |
| 0.001 | 1p0 | taker | 0.4289 | 0.5653 | 0.0058 | 0.0097 | -0.4306 | 0.0002 | -0.0085 | 1.0384 | -0.7665 | 65.3 |
| 0.001 | 1p0 | maker | 0.4291 | 0.5651 | 0.0058 | 0.1327 | -0.3889 | 0.0022 | -0.0067 | 1.3447 | -0.7893 | 65.5 |
| 0.001 | 2p0 | taker | 0.5767 | 0.4046 | 0.0187 | 0.0594 | 0.4110 | 0.0011 | 0.0076 | 1.0744 | -1.3405 | 111.0 |
| 0.001 | 2p0 | maker | 0.5764 | 0.4048 | 0.0188 | 0.2018 | 0.5838 | 0.0031 | 0.0095 | 1.3953 | -1.4699 | 111.1 |
| 0.001 | none | taker | 0.7376 | 0.0000 | 0.2624 | 0.1866 | 0.7284 | 0.0031 | 0.0115 | 1.2440 | -3.0904 | 260.5 |
| 0.001 | none | maker | 0.7383 | 0.0000 | 0.2617 | 0.3410 | 0.9457 | 0.0048 | 0.0134 | 1.5488 | -3.5876 | 260.2 |

### Skips by reason, per run
| q | stop | fee | book_full | margin | min_order |
|---|---|---|---|---|---|
| 0.01 | 0p5 | taker | 1382 | 4006 | 7560 |
| 0.01 | 0p5 | maker | 3012 | 3604 | 457 |
| 0.01 | 1p0 | taker | 3521 | 6045 | 1894 |
| 0.01 | 1p0 | maker | 5243 | 5112 | 147 |
| 0.01 | 2p0 | taker | 6515 | 8412 | 270 |
| 0.01 | 2p0 | maker | 7875 | 7143 | 103 |
| 0.01 | none | taker | 11686 | 10140 | 104 |
| 0.01 | none | maker | 13169 | 8666 | 59 |
| 0.005 | 0p5 | taker | 243 | 861 | 1487 |
| 0.005 | 0p5 | maker | 491 | 814 | 288 |
| 0.005 | 1p0 | taker | 702 | 1582 | 660 |
| 0.005 | 1p0 | maker | 1106 | 1303 | 151 |
| 0.005 | 2p0 | taker | 1813 | 2444 | 201 |
| 0.005 | 2p0 | maker | 2217 | 2042 | 100 |
| 0.005 | none | taker | 3662 | 3967 | 105 |
| 0.005 | none | maker | 4320 | 3321 | 66 |
| 0.001 | 0p5 | taker | 2 | 35 | 174 |
| 0.001 | 0p5 | maker | 16 | 30 | 123 |
| 0.001 | 1p0 | taker | 28 | 38 | 142 |
| 0.001 | 1p0 | maker | 33 | 33 | 107 |
| 0.001 | 2p0 | taker | 46 | 94 | 129 |
| 0.001 | 2p0 | maker | 66 | 74 | 94 |
| 0.001 | none | taker | 105 | 292 | 97 |
| 0.001 | none | maker | 202 | 199 | 73 |

### Leverage and risk, per run
| q | stop | fee | peak_margin_used | mean_open | max_open | n_liquidations |
|---|---|---|---|---|---|---|
| 0.01 | 0p5 | taker | 998.54 | 5.16 | 20 | 0 |
| 0.01 | 0p5 | maker | 1415.25 | 5.81 | 20 | 0 |
| 0.01 | 1p0 | taker | 1001.92 | 7.72 | 20 | 0 |
| 0.01 | 1p0 | maker | 4006.71 | 8.03 | 20 | 0 |
| 0.01 | 2p0 | taker | 1883.74 | 10.39 | 20 | 0 |
| 0.01 | 2p0 | maker | 10234.54 | 10.45 | 20 | 0 |
| 0.01 | none | taker | 4464.04 | 13.97 | 20 | 0 |
| 0.01 | none | maker | 18198.73 | 14.00 | 20 | 0 |
| 0.005 | 0p5 | taker | 998.74 | 3.71 | 20 | 0 |
| 0.005 | 0p5 | maker | 1456.90 | 3.88 | 20 | 0 |
| 0.005 | 1p0 | taker | 1001.87 | 5.27 | 20 | 0 |
| 0.005 | 1p0 | maker | 2917.35 | 5.40 | 20 | 0 |
| 0.005 | 2p0 | taker | 1859.87 | 7.20 | 20 | 0 |
| 0.005 | 2p0 | maker | 5845.77 | 7.24 | 20 | 0 |
| 0.005 | none | taker | 3811.02 | 10.46 | 20 | 0 |
| 0.005 | none | maker | 10558.82 | 10.47 | 20 | 0 |
| 0.001 | 0p5 | taker | 965.74 | 1.96 | 20 | 0 |
| 0.001 | 0p5 | maker | 1085.74 | 1.98 | 20 | 0 |
| 0.001 | 1p0 | taker | 1039.31 | 2.39 | 20 | 0 |
| 0.001 | 1p0 | maker | 1321.10 | 2.42 | 20 | 0 |
| 0.001 | 2p0 | taker | 1208.52 | 2.97 | 20 | 0 |
| 0.001 | 2p0 | maker | 1597.54 | 2.99 | 20 | 0 |
| 0.001 | none | taker | 1697.95 | 4.58 | 20 | 0 |
| 0.001 | none | maker | 2175.39 | 4.56 | 20 | 0 |

### Liquidation events, per run
none, in any of the 24 runs.

### Splits: top/bottom 10 coins (net of trades involving the coin, each trade counted for both coins) and pairs, per run
**q0.01_stop0p5_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 78.43 |
| MEGA | 61.69 |
| NOT | 38.80 |
| MEW | 13.77 |
| STABLE | 8.39 |
| ZEREBRO | 6.74 |
| ZETA | 6.61 |
| POLYX | 4.83 |
| YZY | 4.47 |
| LDO | 3.45 |
**q0.01_stop0p5_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| ETC | -21.90 |
| LTC | -22.29 |
| OM | -22.33 |
| LINK | -22.63 |
| COMP | -22.88 |
| VINE | -23.00 |
| AVNT | -23.64 |
| DYDX | -24.11 |
| MORPHO | -24.43 |
| FOGO | -56.41 |
**q0.01_stop0p5_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| HMSTR/MEGA | 9.43 |
| FXS/MEGA | 8.59 |
| HMSTR/MEW | 7.88 |
| MEGA/SYRUP | 7.81 |
| CRV/HMSTR | 6.91 |
| FOGO/MAVIA | 6.81 |
| NOT/OP | 6.70 |
| MEGA/TNSR | 6.42 |
| ACE/MEGA | 6.22 |
| BLAST/FOGO | 6.21 |
**q0.01_stop0p5_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| MEGA/PROMPT | -3.33 |
| FOGO/PUMP | -3.35 |
| DOOD/FTT | -3.36 |
| FOGO/SAGA | -3.39 |
| FOGO/PROMPT | -3.56 |
| AIXBT/FOGO | -3.91 |
| ACE/HMSTR | -4.01 |
| FOGO/VINE | -4.11 |
| FOGO/OM | -6.05 |
| FOGO/MELANIA | -6.78 |

**q0.01_stop0p5_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 532.69 |
| YZY | 197.77 |
| NOT | 162.63 |
| MEW | 124.56 |
| BOME | 93.43 |
| MEGA | 88.98 |
| FTT | 84.96 |
| ZETA | 68.85 |
| POLYX | 47.13 |
| RSR | 44.69 |
**q0.01_stop0p5_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| kLUNC | -31.76 |
| EIGEN | -33.47 |
| CELO | -33.73 |
| DYM | -34.06 |
| PURR | -38.52 |
| VINE | -40.09 |
| TON | -42.12 |
| AVNT | -42.60 |
| kPEPE | -44.26 |
| FOGO | -52.85 |
**q0.01_stop0p5_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| HMSTR/MEW | 21.00 |
| CRV/HMSTR | 20.11 |
| YZY/ZETA | 19.05 |
| BOME/HMSTR | 17.77 |
| NOT/OP | 17.74 |
| GRASS/YZY | 16.72 |
| MAVIA/YZY | 15.71 |
| HMSTR/VIRTUAL | 14.95 |
| HMSTR/WCT | 14.70 |
| MAV/ZEREBRO | 13.99 |
**q0.01_stop0p5_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| WIF/XAI | -6.36 |
| TST/USUAL | -6.49 |
| TST/XAI | -6.54 |
| TST/ZK | -7.04 |
| FOGO/OM | -7.07 |
| JUP/ZEC | -7.38 |
| BCH/JUP | -8.26 |
| REZ/ZEREBRO | -9.26 |
| FTT/TST | -9.50 |
| ACE/HMSTR | -9.74 |

**q0.01_stop1p0_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 184.17 |
| MEGA | 110.61 |
| NOT | 100.28 |
| BOME | 63.49 |
| MEW | 55.89 |
| YZY | 38.45 |
| FTT | 31.05 |
| STABLE | 20.35 |
| MANTA | 16.08 |
| REZ | 13.28 |
**q0.01_stop1p0_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| COMP | -27.92 |
| LINK | -28.15 |
| EIGEN | -28.65 |
| SOPH | -29.08 |
| HYPE | -29.69 |
| BLUR | -31.52 |
| PURR | -33.33 |
| VINE | -33.84 |
| AVNT | -35.68 |
| LTC | -40.18 |
**q0.01_stop1p0_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| FOGO/STABLE | 19.67 |
| FOGO/GRIFFAIN | 12.59 |
| HMSTR/MEGA | 11.94 |
| AR/ZK | 11.74 |
| MEGA/TNSR | 10.51 |
| FXS/MEGA | 10.21 |
| BOME/HMSTR | 9.99 |
| FOGO/MEGA | 9.89 |
| FOGO/NEAR | 9.06 |
| CRV/HMSTR | 8.14 |
**q0.01_stop1p0_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| FOGO/VINE | -5.71 |
| AIXBT/FOGO | -6.03 |
| MEGA/ZEREBRO | -6.06 |
| FOGO/MELANIA | -6.22 |
| HMSTR/TAO | -6.38 |
| FOGO/kLUNC | -6.63 |
| HMSTR/NOT | -6.74 |
| AERO/MEGA | -6.77 |
| FTT/TST | -7.35 |
| HMSTR/kNEIRO | -7.84 |

**q0.01_stop1p0_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 1240.72 |
| YZY | 555.90 |
| NOT | 382.05 |
| BOME | 352.08 |
| MEW | 348.27 |
| FTT | 245.16 |
| TNSR | 177.09 |
| MAVIA | 169.58 |
| RSR | 158.14 |
| BLAST | 146.17 |
**q0.01_stop1p0_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| COMP | -64.25 |
| AVNT | -67.18 |
| BABY | -68.65 |
| LTC | -72.40 |
| CELO | -77.10 |
| CFX | -77.22 |
| BLUR | -77.81 |
| ORDI | -84.17 |
| ARB | -96.04 |
| EIGEN | -117.79 |
**q0.01_stop1p0_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| YZY/ZETA | 45.86 |
| MAVIA/SKR | 45.16 |
| LDO/LIT | 41.31 |
| GRASS/YZY | 39.98 |
| APT/WLD | 39.34 |
| MAVIA/YZY | 37.97 |
| BOME/HMSTR | 37.27 |
| MAV/ZEREBRO | 35.21 |
| HMSTR/TST | 33.77 |
| PENDLE/XLM | 33.22 |
**q0.01_stop1p0_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| DOGE/INJ | -17.23 |
| EIGEN/FTT | -17.60 |
| AVAX/JUP | -18.31 |
| APT/ENA | -18.64 |
| BCH/JUP | -18.65 |
| EIGEN/ENS | -19.34 |
| CFX/ZRO | -21.67 |
| NEAR/ONDO | -21.69 |
| REZ/ZEREBRO | -23.33 |
| FTT/TST | -33.31 |

**q0.01_stop2p0_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 577.35 |
| MEW | 235.23 |
| BOME | 220.79 |
| YZY | 200.59 |
| MAVIA | 163.34 |
| NOT | 163.23 |
| FOGO | 137.42 |
| TNSR | 104.54 |
| RSR | 92.79 |
| TRB | 87.95 |
**q0.01_stop2p0_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| EIGEN | -50.86 |
| COMP | -51.40 |
| MORPHO | -52.68 |
| ZRO | -54.03 |
| PAXG | -55.60 |
| SOPH | -57.87 |
| VINE | -59.57 |
| LTC | -61.86 |
| CFX | -64.42 |
| HYPE | -77.90 |
**q0.01_stop2p0_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| GRASS/YZY | 25.90 |
| YZY/ZETA | 23.82 |
| FOGO/STABLE | 23.05 |
| AR/ZK | 21.75 |
| MAVIA/YZY | 21.19 |
| LDO/LIT | 20.76 |
| HMSTR/MOODENG | 19.80 |
| YZY/kSHIB | 19.39 |
| MAV/ZEREBRO | 18.65 |
| FOGO/GRIFFAIN | 18.37 |
**q0.01_stop2p0_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| EIGEN/ENS | -11.19 |
| DYM/HMSTR | -11.27 |
| HYPER/TNSR | -11.27 |
| MORPHO/S | -11.93 |
| CFX/DASH | -12.28 |
| NEO/VINE | -12.54 |
| REZ/ZEREBRO | -13.64 |
| WLD/kBONK | -13.76 |
| ARB/ZK | -14.33 |
| FTT/TST | -18.61 |

**q0.01_stop2p0_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 2386.35 |
| YZY | 1178.76 |
| MEW | 920.16 |
| BOME | 888.54 |
| MAVIA | 840.51 |
| TNSR | 787.76 |
| RSR | 633.78 |
| NOT | 600.41 |
| FTT | 538.57 |
| TRB | 532.27 |
**q0.01_stop2p0_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| PUMP | -142.04 |
| JUP | -148.94 |
| KAS | -170.75 |
| POL | -172.23 |
| RESOLV | -176.62 |
| FET | -182.77 |
| ZRO | -193.08 |
| APE | -204.17 |
| EIGEN | -280.24 |
| CFX | -284.62 |
**q0.01_stop2p0_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| YZY/ZETA | 104.17 |
| GRASS/YZY | 97.08 |
| LDO/LIT | 96.81 |
| MAVIA/YZY | 93.67 |
| YZY/kSHIB | 87.10 |
| UNI/WLD | 84.16 |
| MAV/ZEREBRO | 81.77 |
| HYPE/ONDO | 73.44 |
| TNSR/TURBO | 73.27 |
| STRK/YZY | 72.42 |
**q0.01_stop2p0_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| SNX/XLM | -52.82 |
| DOGE/INJ | -53.53 |
| CFX/DASH | -53.77 |
| REZ/ZEREBRO | -55.16 |
| GMX/RESOLV | -55.53 |
| WIF/kPEPE | -57.33 |
| FTT/TST | -63.79 |
| ARB/ZK | -64.12 |
| NEO/VINE | -65.66 |
| EIGEN/ENS | -71.79 |

**q0.01_stopnone_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 996.27 |
| YZY | 642.42 |
| BOME | 330.38 |
| MAVIA | 318.38 |
| MEW | 314.67 |
| NOT | 308.55 |
| FTT | 292.82 |
| TNSR | 274.56 |
| RSR | 254.01 |
| kSHIB | 172.85 |
**q0.01_stopnone_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| KAS | -109.89 |
| WCT | -137.99 |
| APE | -139.16 |
| INIT | -166.71 |
| COMP | -171.11 |
| HYPER | -172.47 |
| SAGA | -175.24 |
| TRX | -184.37 |
| ZK | -193.00 |
| HYPE | -213.48 |
**q0.01_stopnone_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| YZY/ZETA | 47.11 |
| MAVIA/YZY | 43.45 |
| MAV/ZEREBRO | 40.68 |
| YZY/kSHIB | 38.11 |
| GRASS/YZY | 34.51 |
| BRETT/PENDLE | 30.71 |
| HYPE/ONDO | 29.64 |
| APT/HMSTR | 28.54 |
| HMSTR/SUSHI | 28.46 |
| YZY/ZRO | 27.96 |
**q0.01_stopnone_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| MORPHO/S | -48.96 |
| BOME/INIT | -49.27 |
| RUNE/ZK | -51.25 |
| ORDI/TNSR | -51.62 |
| ADA/VVV | -51.99 |
| 2Z/DASH | -53.72 |
| GMX/RESOLV | -53.98 |
| APE/ZK | -59.80 |
| PUMP/TRX | -63.85 |
| HYPER/SAGA | -132.01 |

**q0.01_stopnone_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 2582.71 |
| YZY | 1996.65 |
| TNSR | 1198.94 |
| NOT | 1159.20 |
| BOME | 1036.44 |
| MEW | 919.42 |
| RSR | 919.33 |
| FTT | 839.77 |
| USUAL | 664.87 |
| MAVIA | 638.84 |
**q0.01_stopnone_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| AVNT | -347.70 |
| SAGA | -368.42 |
| HYPER | -369.29 |
| HYPE | -380.32 |
| WCT | -383.57 |
| COMP | -384.17 |
| KAS | -408.03 |
| MEGA | -440.76 |
| ZK | -460.97 |
| TRX | -498.88 |
**q0.01_stopnone_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| GRASS/YZY | 143.59 |
| HYPE/ONDO | 131.48 |
| YZY/ZETA | 129.37 |
| MAVIA/YZY | 120.30 |
| CFX/SEI | 114.54 |
| NOT/ORDI | 110.58 |
| MAV/ZEREBRO | 107.96 |
| BCH/TNSR | 100.35 |
| MORPHO/UNI | 99.21 |
| APT/HMSTR | 96.15 |
**q0.01_stopnone_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| MON/PENGU | -158.74 |
| 2Z/DASH | -165.19 |
| BCH/SOL | -167.57 |
| ETHFI/XLM | -174.18 |
| NEAR/TRX | -195.20 |
| GMX/RESOLV | -201.33 |
| PUMP/TRX | -202.35 |
| ADA/VVV | -209.91 |
| CFX/KAITO | -298.30 |
| HYPER/SAGA | -328.73 |

**q0.005_stop0p5_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 113.90 |
| NOT | 33.48 |
| MEW | 22.68 |
| MEGA | 18.98 |
| ZEREBRO | 18.85 |
| YZY | 18.14 |
| MANTA | 10.49 |
| ZETA | 9.79 |
| POL | 8.96 |
| STABLE | 8.78 |
**q0.005_stop0p5_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| SPX | -20.62 |
| XPL | -20.66 |
| TAO | -20.74 |
| SAGA | -21.53 |
| FOGO | -22.72 |
| LTC | -22.77 |
| AVNT | -23.09 |
| SOPH | -23.13 |
| COMP | -25.62 |
| VINE | -25.66 |
**q0.005_stop0p5_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| HMSTR/MEGA | 10.80 |
| HMSTR/MEW | 9.25 |
| FOGO/STABLE | 8.04 |
| FOGO/MAVIA | 7.79 |
| MEGA/UMA | 7.36 |
| NOT/OP | 6.92 |
| USUAL/ZEREBRO | 6.82 |
| CRV/HMSTR | 6.71 |
| FOGO/RENDER | 6.08 |
| 2Z/MEGA | 6.07 |
**q0.005_stop0p5_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| HYPE/NOT | -3.13 |
| FOGO/LAYER | -3.13 |
| FOGO/SAGA | -3.26 |
| AERO/MEGA | -3.33 |
| HMSTR/LIT | -3.58 |
| MEGA/MOODENG | -3.68 |
| FOGO/VINE | -4.14 |
| MEGA/MET | -4.15 |
| HMSTR/NOT | -4.34 |
| kBONK/kSHIB | -4.35 |

**q0.005_stop0p5_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 460.93 |
| YZY | 189.46 |
| NOT | 114.02 |
| MEW | 89.39 |
| BOME | 65.54 |
| ZETA | 51.48 |
| MEGA | 49.69 |
| MANTA | 38.08 |
| ZEREBRO | 35.68 |
| POL | 34.76 |
**q0.005_stop0p5_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| COMP | -23.15 |
| CFX | -23.65 |
| kPEPE | -23.83 |
| SAGA | -24.06 |
| SPX | -24.31 |
| DYM | -26.32 |
| BABY | -29.94 |
| SOPH | -31.04 |
| XPL | -32.40 |
| TST | -34.97 |
**q0.005_stop0p5_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| GRASS/YZY | 19.59 |
| YZY/ZETA | 17.57 |
| HMSTR/MEW | 17.49 |
| MAVIA/YZY | 17.33 |
| LIT/YZY | 14.65 |
| CRV/HMSTR | 14.50 |
| BOME/HMSTR | 13.79 |
| NOT/OP | 13.78 |
| HMSTR/MEGA | 12.68 |
| DOT/HMSTR | 11.65 |
**q0.005_stop0p5_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| MEGA/MET | -4.95 |
| kBONK/kSHIB | -4.96 |
| FOGO/LAYER | -5.13 |
| HYPE/NOT | -5.20 |
| WIF/XAI | -6.13 |
| UNI/WLD | -6.17 |
| TST/W | -6.45 |
| TST/USUAL | -6.68 |
| TST/ZK | -6.95 |
| REZ/ZEREBRO | -9.91 |

**q0.005_stop1p0_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 275.81 |
| YZY | 85.83 |
| NOT | 74.78 |
| MEW | 54.90 |
| BOME | 52.17 |
| ZEREBRO | 45.64 |
| MEGA | 36.95 |
| MANTA | 27.07 |
| ZETA | 26.79 |
| PROMPT | 25.60 |
**q0.005_stop1p0_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| BIO | -25.42 |
| kNEIRO | -26.02 |
| LINK | -26.97 |
| SOPH | -27.40 |
| DYM | -28.06 |
| TON | -29.43 |
| LTC | -30.10 |
| BABY | -30.25 |
| COMP | -31.99 |
| TST | -35.46 |
**q0.005_stop1p0_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| HMSTR/MEGA | 14.08 |
| FOGO/GRIFFAIN | 12.36 |
| GRASS/YZY | 12.10 |
| YZY/ZETA | 10.04 |
| MAVIA/YZY | 9.87 |
| HMSTR/TST | 9.70 |
| BOME/HMSTR | 9.22 |
| FOGO/STABLE | 8.93 |
| FOGO/RENDER | 8.77 |
| HMSTR/PROVE | 8.46 |
**q0.005_stop1p0_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| kBONK/kSHIB | -4.99 |
| FOGO/kNEIRO | -5.00 |
| TST/ZK | -5.03 |
| FOGO/MON | -5.19 |
| EIGEN/FTT | -5.21 |
| HMSTR/PYTH | -5.43 |
| FOGO/VINE | -5.72 |
| REZ/ZEREBRO | -5.73 |
| HMSTR/kNEIRO | -7.49 |
| AERO/MEGA | -8.57 |

**q0.005_stop1p0_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 898.55 |
| YZY | 396.36 |
| MEW | 190.24 |
| NOT | 183.54 |
| BOME | 183.11 |
| MAVIA | 119.24 |
| ZETA | 97.88 |
| FTT | 86.19 |
| UMA | 82.42 |
| NIL | 80.07 |
**q0.005_stop1p0_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| LTC | -30.22 |
| kLUNC | -34.85 |
| BIO | -36.91 |
| DYM | -39.17 |
| CFX | -46.34 |
| COMP | -47.67 |
| CELO | -50.30 |
| TON | -51.64 |
| BABY | -53.63 |
| TST | -78.29 |
**q0.005_stop1p0_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| GRASS/YZY | 38.69 |
| MAVIA/YZY | 31.32 |
| YZY/ZETA | 31.00 |
| HMSTR/TST | 28.24 |
| HMSTR/NIL | 24.46 |
| BOME/HMSTR | 24.10 |
| LIT/YZY | 22.89 |
| HMSTR/PROVE | 22.03 |
| HMSTR/NEO | 21.78 |
| DOGE/HMSTR | 20.61 |
**q0.005_stop1p0_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| EIGEN/ENS | -9.29 |
| BIO/HEMI | -9.36 |
| AERO/MEGA | -11.16 |
| TST/W | -11.82 |
| TST/USUAL | -11.97 |
| EIGEN/FTT | -12.41 |
| UNI/WLD | -12.46 |
| TST/ZK | -12.98 |
| TST/ZRO | -14.92 |
| REZ/ZEREBRO | -18.07 |

**q0.005_stop2p0_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 622.24 |
| YZY | 228.38 |
| BOME | 155.81 |
| NOT | 148.30 |
| MEW | 146.59 |
| MAVIA | 92.46 |
| FOGO | 88.59 |
| TNSR | 72.17 |
| ZETA | 54.49 |
| ZEREBRO | 53.17 |
**q0.005_stop2p0_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| EIGEN | -40.26 |
| TRUMP | -41.80 |
| kNEIRO | -41.93 |
| BIO | -42.20 |
| RESOLV | -44.45 |
| TON | -46.89 |
| CFX | -46.94 |
| BABY | -49.49 |
| APEX | -51.48 |
| TST | -60.93 |
**q0.005_stop2p0_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| GRASS/YZY | 26.12 |
| YZY/ZETA | 21.01 |
| MAVIA/YZY | 20.72 |
| HMSTR/NEO | 19.57 |
| HMSTR/TST | 18.83 |
| FOGO/GRIFFAIN | 18.09 |
| HMSTR/MOODENG | 17.03 |
| YZY/kSHIB | 16.71 |
| BOME/HMSTR | 15.53 |
| CRV/HMSTR | 14.39 |
**q0.005_stop2p0_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| SPX/STX | -9.55 |
| TST/VINE | -9.67 |
| HMSTR/SOPH | -9.70 |
| EIGEN/FTT | -9.75 |
| GMX/RESOLV | -9.86 |
| FOGO/XPL | -10.97 |
| FOGO/kNEIRO | -11.58 |
| CFX/DASH | -12.20 |
| REZ/ZEREBRO | -12.42 |
| EIGEN/ENS | -12.65 |

**q0.005_stop2p0_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 1643.31 |
| YZY | 751.20 |
| MEW | 412.65 |
| BOME | 366.54 |
| NOT | 348.21 |
| TNSR | 302.16 |
| MAVIA | 301.18 |
| UMA | 207.77 |
| TRB | 175.31 |
| FOGO | 169.77 |
**q0.005_stop2p0_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| kNEIRO | -59.25 |
| PUMP | -63.55 |
| TON | -71.60 |
| BIO | -76.08 |
| RESOLV | -78.36 |
| EIGEN | -81.94 |
| APEX | -88.50 |
| BABY | -91.77 |
| TST | -93.79 |
| CFX | -136.57 |
**q0.005_stop2p0_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| GRASS/YZY | 68.76 |
| YZY/ZETA | 56.04 |
| MAVIA/YZY | 54.73 |
| HMSTR/NEO | 51.92 |
| UNI/WLD | 51.60 |
| HMSTR/TST | 48.22 |
| YZY/kSHIB | 45.49 |
| HYPE/ONDO | 44.07 |
| NEAR/XLM | 40.89 |
| LIT/YZY | 37.42 |
**q0.005_stop2p0_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| TST/ZK | -23.01 |
| ARB/ZK | -23.14 |
| BIO/RESOLV | -24.75 |
| LAYER/kLUNC | -24.89 |
| BNB/EIGEN | -25.67 |
| LIT/ZEN | -29.59 |
| GMX/RESOLV | -31.58 |
| CFX/DASH | -31.77 |
| REZ/ZEREBRO | -33.30 |
| EIGEN/ENS | -41.77 |

**q0.005_stopnone_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 924.73 |
| YZY | 585.10 |
| MAVIA | 285.24 |
| BOME | 269.82 |
| FTT | 257.74 |
| MEW | 230.24 |
| NOT | 211.05 |
| TNSR | 197.50 |
| FOGO | 171.52 |
| PNUT | 141.01 |
**q0.005_stopnone_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| ORDI | -89.06 |
| TON | -89.99 |
| JUP | -96.60 |
| ZK | -112.80 |
| DOGE | -118.26 |
| KAITO | -124.18 |
| HYPER | -128.88 |
| INIT | -134.74 |
| SAGA | -166.30 |
| TRX | -170.98 |
**q0.005_stopnone_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| GRASS/YZY | 44.28 |
| MAVIA/YZY | 41.23 |
| YZY/ZRO | 37.94 |
| HMSTR/NEO | 36.70 |
| YZY/ZETA | 36.46 |
| YZY/kSHIB | 28.86 |
| HMSTR/PROVE | 26.19 |
| BOME/HMSTR | 25.72 |
| FTT/HMSTR | 24.98 |
| HMSTR/MANTA | 22.93 |
**q0.005_stopnone_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| 0G/HMSTR | -43.96 |
| ARB/COMP | -44.11 |
| MORPHO/S | -44.12 |
| GMX/RESOLV | -49.01 |
| NEAR/TRX | -51.08 |
| PUMP/TRX | -57.01 |
| APE/ZK | -62.26 |
| ORDI/ZK | -68.16 |
| CFX/KAITO | -79.94 |
| HYPER/SAGA | -117.72 |

**q0.005_stopnone_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 2074.14 |
| YZY | 1365.69 |
| BOME | 661.63 |
| TNSR | 563.53 |
| MAVIA | 559.02 |
| FTT | 535.30 |
| MEW | 518.74 |
| NOT | 509.87 |
| NEO | 360.87 |
| NIL | 348.45 |
**q0.005_stopnone_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| JUP | -177.03 |
| APE | -182.59 |
| CFX | -184.02 |
| DOGE | -199.68 |
| ZK | -200.43 |
| HYPER | -218.64 |
| KAITO | -237.95 |
| INIT | -244.52 |
| TRX | -315.30 |
| SAGA | -332.86 |
**q0.005_stopnone_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| GRASS/YZY | 92.37 |
| MAVIA/YZY | 85.85 |
| YZY/ZRO | 80.41 |
| YZY/ZETA | 76.79 |
| HMSTR/NEO | 75.76 |
| CFX/SEI | 67.25 |
| NOT/ORDI | 65.82 |
| YZY/kSHIB | 62.05 |
| BANANA/BOME | 58.16 |
| ADA/LTC | 57.33 |
**q0.005_stopnone_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| MORPHO/S | -92.67 |
| MON/PENGU | -94.25 |
| IOTA/PYTH | -100.90 |
| NEAR/TRX | -122.83 |
| GMX/RESOLV | -124.78 |
| APE/ZK | -126.19 |
| PUMP/TRX | -129.59 |
| ORDI/ZK | -180.43 |
| CFX/KAITO | -191.68 |
| HYPER/SAGA | -230.00 |

**q0.001_stop0p5_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 106.41 |
| YZY | 41.47 |
| FOGO | 31.28 |
| NOT | 16.26 |
| MEW | 14.98 |
| MEGA | 13.24 |
| STABLE | 11.11 |
| BOME | 10.46 |
| JTO | 9.45 |
| PROMPT | 7.28 |
**q0.001_stop0p5_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| PUMP | -9.89 |
| BRETT | -11.24 |
| SPX | -11.33 |
| ZEC | -11.37 |
| MORPHO | -12.00 |
| HYPE | -13.31 |
| ZRO | -13.74 |
| VINE | -14.47 |
| FTT | -16.22 |
| TST | -20.96 |
**q0.001_stop0p5_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| FOGO/MAVIA | 11.64 |
| MAVIA/YZY | 11.03 |
| FOGO/STABLE | 10.65 |
| HMSTR/MEW | 10.35 |
| HMSTR/MEGA | 8.43 |
| BOME/HMSTR | 6.76 |
| CAKE/FOGO | 6.47 |
| FOGO/TON | 6.31 |
| HMSTR/MANTA | 6.14 |
| HMSTR/JTO | 5.83 |
**q0.001_stop0p5_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| ALGO/MORPHO | -2.26 |
| ACE/HMSTR | -2.27 |
| INIT/TAO | -2.39 |
| HYPE/NOT | -2.67 |
| HMSTR/MAVIA | -2.74 |
| POL/ZRO | -3.14 |
| FOGO/LAYER | -3.18 |
| SPX/STX | -3.34 |
| TST/W | -4.32 |
| TST/USUAL | -4.68 |

**q0.001_stop0p5_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 169.74 |
| YZY | 89.62 |
| FOGO | 39.62 |
| NOT | 33.75 |
| BOME | 29.75 |
| MEW | 25.67 |
| MEGA | 24.49 |
| MAVIA | 14.25 |
| JTO | 14.14 |
| STABLE | 13.61 |
**q0.001_stop0p5_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| SAGA | -7.86 |
| SOPH | -8.06 |
| ZEC | -8.50 |
| BRETT | -8.73 |
| ZORA | -8.73 |
| FTT | -9.39 |
| SPX | -9.65 |
| VINE | -9.96 |
| HYPE | -12.14 |
| TST | -22.56 |
**q0.001_stop0p5_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| MAVIA/YZY | 15.26 |
| FOGO/MAVIA | 12.74 |
| HMSTR/MEW | 12.05 |
| FOGO/STABLE | 11.42 |
| HMSTR/MEGA | 9.29 |
| BOME/HMSTR | 8.97 |
| HMSTR/MANTA | 8.39 |
| HMSTR/JTO | 7.68 |
| HMSTR/PROVE | 7.47 |
| CAKE/FOGO | 7.39 |
**q0.001_stop0p5_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| ACE/HMSTR | -2.27 |
| TST/XMR | -2.49 |
| POL/ZRO | -2.63 |
| HYPE/NOT | -2.91 |
| HMSTR/MAVIA | -2.91 |
| FOGO/LAYER | -2.92 |
| INIT/TAO | -2.94 |
| SPX/STX | -3.45 |
| TST/W | -5.65 |
| TST/USUAL | -5.94 |

**q0.001_stop1p0_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 192.21 |
| YZY | 76.04 |
| FOGO | 44.09 |
| NOT | 31.95 |
| MEW | 27.44 |
| MEGA | 16.61 |
| ASTER | 16.39 |
| JTO | 15.70 |
| BOME | 14.42 |
| MANTA | 14.29 |
**q0.001_stop1p0_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| SOPH | -12.55 |
| WLFI | -12.89 |
| INIT | -13.05 |
| ZEC | -13.11 |
| VINE | -13.12 |
| ACE | -13.41 |
| JUP | -14.11 |
| CHILLGUY | -14.14 |
| TST | -15.99 |
| FTT | -16.41 |
**q0.001_stop1p0_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| HMSTR/TST | 16.86 |
| HMSTR/MEGA | 12.26 |
| MAVIA/YZY | 12.04 |
| FOGO/STABLE | 10.90 |
| FOGO/MAVIA | 10.12 |
| HMSTR/MEW | 9.97 |
| BOME/HMSTR | 7.88 |
| HMSTR/MANTA | 7.15 |
| HMSTR/LINEA | 7.10 |
| HMSTR/JTO | 6.82 |
**q0.001_stop1p0_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| FOGO/MON | -3.29 |
| INIT/TAO | -3.31 |
| FOGO/LAYER | -3.49 |
| VIRTUAL/ZEC | -3.58 |
| HMSTR/TON | -3.70 |
| FARTCOIN/HYPE | -3.94 |
| SPX/STX | -4.41 |
| POL/ZRO | -4.64 |
| TST/W | -5.12 |
| TST/USUAL | -5.48 |

**q0.001_stop1p0_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 281.86 |
| YZY | 133.14 |
| FOGO | 55.60 |
| NOT | 52.66 |
| MEW | 41.48 |
| BOME | 33.42 |
| MEGA | 24.68 |
| ASTER | 22.20 |
| JTO | 21.51 |
| WIF | 19.20 |
**q0.001_stop1p0_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| CHILLGUY | -10.44 |
| ETHFI | -10.87 |
| ZEC | -10.88 |
| SKY | -10.96 |
| SOPH | -11.19 |
| SAGA | -11.31 |
| WLFI | -11.86 |
| ACE | -12.21 |
| INIT | -13.48 |
| TST | -16.36 |
**q0.001_stop1p0_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| HMSTR/TST | 21.50 |
| MAVIA/YZY | 16.77 |
| HMSTR/MEGA | 13.18 |
| FOGO/STABLE | 11.68 |
| HMSTR/MEW | 11.59 |
| FOGO/MAVIA | 11.12 |
| BOME/HMSTR | 10.46 |
| HMSTR/MANTA | 9.77 |
| HMSTR/LINEA | 9.43 |
| HMSTR/JTO | 9.00 |
**q0.001_stop1p0_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| FARTCOIN/HYPE | -3.55 |
| TST/VINE | -3.59 |
| ONDO/STRK | -3.65 |
| ETHFI/XLM | -3.76 |
| HMSTR/TON | -4.10 |
| INIT/TAO | -4.11 |
| POL/ZRO | -4.56 |
| SPX/STX | -4.70 |
| TST/W | -6.69 |
| TST/USUAL | -6.95 |

**q0.001_stop2p0_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 250.76 |
| YZY | 85.38 |
| NOT | 45.35 |
| MEW | 44.17 |
| FOGO | 43.23 |
| BOME | 31.13 |
| MEGA | 30.00 |
| ASTER | 22.37 |
| WIF | 21.74 |
| STABLE | 21.32 |
**q0.001_stop2p0_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| HYPE | -15.38 |
| ACE | -16.29 |
| ZEC | -16.74 |
| XLM | -17.24 |
| EIGEN | -17.27 |
| BRETT | -19.31 |
| ETHFI | -20.09 |
| VINE | -21.28 |
| TST | -27.60 |
| FTT | -30.19 |
**q0.001_stop2p0_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| HMSTR/TST | 18.60 |
| MAVIA/YZY | 14.39 |
| HMSTR/MEGA | 12.31 |
| FOGO/STABLE | 10.77 |
| ARK/HMSTR | 10.34 |
| HMSTR/MEW | 9.95 |
| BOME/HMSTR | 8.70 |
| DOGE/HMSTR | 8.39 |
| HMSTR/MOODENG | 8.22 |
| HMSTR/ZEN | 8.14 |
**q0.001_stop2p0_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| FOGO/XPL | -5.26 |
| TST/VINE | -5.40 |
| JUP/TST | -5.83 |
| TST/W | -5.89 |
| TST/XPL | -5.98 |
| MELANIA/TST | -6.02 |
| ETHFI/XLM | -6.45 |
| POL/ZRO | -6.70 |
| FARTCOIN/HYPE | -7.02 |
| SPX/STX | -7.79 |

**q0.001_stop2p0_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 357.82 |
| YZY | 150.90 |
| NOT | 66.38 |
| MEW | 62.58 |
| FOGO | 53.44 |
| BOME | 49.65 |
| MEGA | 41.88 |
| WIF | 32.94 |
| ASTER | 29.60 |
| TRB | 29.40 |
**q0.001_stop2p0_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| ZEC | -13.96 |
| VINE | -15.18 |
| ACE | -15.79 |
| CFX | -16.00 |
| EIGEN | -18.20 |
| XLM | -18.87 |
| BRETT | -19.08 |
| ETHFI | -19.91 |
| FTT | -25.39 |
| TST | -28.90 |
**q0.001_stop2p0_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| HMSTR/TST | 23.54 |
| MAVIA/YZY | 19.69 |
| ARK/HMSTR | 13.79 |
| HMSTR/MEGA | 13.22 |
| HMSTR/MEW | 11.58 |
| DOGE/HMSTR | 11.52 |
| BOME/HMSTR | 11.50 |
| FOGO/STABLE | 11.46 |
| HMSTR/ZEN | 10.61 |
| HMSTR/LINEA | 10.32 |
**q0.001_stop2p0_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| BCH/FARTCOIN | -6.55 |
| YZY/ZEN | -6.60 |
| FARTCOIN/HYPE | -6.75 |
| JUP/TST | -7.04 |
| TST/XPL | -7.23 |
| POL/ZRO | -7.27 |
| MELANIA/TST | -7.27 |
| TST/W | -7.64 |
| ETHFI/XLM | -8.44 |
| SPX/STX | -8.56 |

**q0.001_stopnone_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 377.58 |
| YZY | 160.03 |
| MEGA | 86.52 |
| NOT | 74.75 |
| FOGO | 69.89 |
| BOME | 67.39 |
| MAVIA | 59.33 |
| TST | 41.86 |
| MEW | 34.09 |
| ARK | 33.09 |
**q0.001_stopnone_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| FARTCOIN | -28.69 |
| LTC | -31.86 |
| ZK | -32.33 |
| GRASS | -32.68 |
| DYM | -33.40 |
| INIT | -37.34 |
| MORPHO | -40.51 |
| VINE | -51.06 |
| HYPE | -57.98 |
| XLM | -62.44 |
**q0.001_stopnone_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| HMSTR/TST | 22.45 |
| FOGO/MAVIA | 22.06 |
| MAVIA/YZY | 17.89 |
| MELANIA/TST | 13.94 |
| HMSTR/MANTA | 13.20 |
| HMSTR/MEGA | 12.91 |
| JUP/TST | 12.23 |
| HMSTR/NEO | 12.08 |
| HMSTR/MOODENG | 11.91 |
| FOGO/STABLE | 11.04 |
**q0.001_stopnone_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| DOOD/INIT | -19.59 |
| AVNT/FOGO | -19.68 |
| GRASS/PEOPLE | -19.95 |
| CFX/KAITO | -20.74 |
| TRB/XLM | -20.93 |
| FOGO/TST | -21.24 |
| MORPHO/S | -24.81 |
| FARTCOIN/HYPE | -28.76 |
| ORDI/ZK | -32.14 |
| ETHFI/XLM | -33.85 |

**q0.001_stopnone_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 441.38 |
| YZY | 228.67 |
| NOT | 102.88 |
| MEGA | 99.02 |
| BOME | 86.55 |
| FOGO | 84.36 |
| MAVIA | 75.19 |
| TST | 58.09 |
| MEW | 50.11 |
| ARK | 44.47 |
**q0.001_stopnone_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| DYM | -33.96 |
| LTC | -34.90 |
| VINE | -37.55 |
| MORPHO | -39.33 |
| ZK | -40.98 |
| INIT | -41.44 |
| 0G | -43.40 |
| FARTCOIN | -54.77 |
| HYPE | -74.10 |
| XLM | -78.98 |
**q0.001_stopnone_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| HMSTR/TST | 26.71 |
| FOGO/MAVIA | 23.17 |
| MAVIA/YZY | 22.97 |
| HMSTR/MANTA | 16.53 |
| MELANIA/TST | 16.23 |
| HMSTR/NEO | 15.20 |
| JUP/TST | 14.26 |
| HMSTR/MEGA | 13.72 |
| HMSTR/MOODENG | 13.56 |
| DOGE/HMSTR | 13.56 |
**q0.001_stopnone_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| BOME/INIT | -22.41 |
| GRASS/PEOPLE | -23.21 |
| DOOD/INIT | -23.52 |
| CFX/KAITO | -25.50 |
| TRB/XLM | -26.69 |
| MORPHO/S | -30.04 |
| 0G/HMSTR | -37.46 |
| ORDI/ZK | -40.99 |
| ETHFI/XLM | -43.17 |
| FARTCOIN/HYPE | -61.18 |

### Drawdown and distance to liquidation, per run
| q | stop | fee | max_dd_usd | max_dd_pct | dd_start | dd_bottom | dd_recovery | longest_underwater_days | min_dist_ratio | median_dist_ratio | date_of_min |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.01 | 0p5 | taker | -869.27 | -0.8693 | 2025-12-20 | 2026-07-11 | None | 203 | 2.1086 | 4.3855 | 2025-12-28 |
| 0.01 | 0p5 | maker | -244.35 | -0.1683 | 2026-05-04 | 2026-07-12 | None | 71 | 2.0281 | 3.2225 | 2026-04-28 |
| 0.01 | 1p0 | taker | -729.10 | -0.7291 | 2025-12-20 | 2026-07-12 | None | 204 | 2.0438 | 2.6977 | 2026-02-17 |
| 0.01 | 1p0 | maker | -515.26 | -0.1275 | 2026-06-29 | 2026-07-12 | None | 42 | 2.0312 | 2.5449 | 2026-03-27 |
| 0.01 | 2p0 | taker | -745.38 | -0.3969 | 2026-05-06 | 2026-07-12 | None | 67 | 2.0177 | 2.3890 | 2026-03-19 |
| 0.01 | 2p0 | maker | -993.56 | -0.0968 | 2026-06-29 | 2026-07-12 | None | 15 | 2.0211 | 2.3736 | 2026-03-19 |
| 0.01 | none | taker | -432.70 | -0.1627 | 2026-05-04 | 2026-05-09 | 2026-06-06 | 32 | 1.9770 | 2.2901 | 2026-04-18 |
| 0.01 | none | maker | -1089.40 | -0.1749 | 2026-07-09 | 2026-07-12 | None | 10 | 1.9759 | 2.2730 | 2026-04-18 |
| 0.005 | 0p5 | taker | -717.71 | -0.7177 | 2025-12-20 | 2026-07-11 | None | 203 | 2.1341 | 6.0537 | 2026-01-02 |
| 0.005 | 0p5 | maker | -145.78 | -0.1211 | 2026-05-04 | 2026-05-18 | None | 74 | 2.0296 | 5.7416 | 2026-03-27 |
| 0.005 | 1p0 | taker | -383.75 | -0.3838 | 2025-12-20 | 2026-07-12 | None | 204 | 2.0525 | 4.5704 | 2026-03-27 |
| 0.005 | 1p0 | maker | -196.08 | -0.0723 | 2026-05-04 | 2026-05-18 | 2026-06-20 | 46 | 2.0181 | 4.4075 | 2026-03-27 |
| 0.005 | 2p0 | taker | -359.96 | -0.1926 | 2026-05-04 | 2026-07-12 | None | 69 | 2.0319 | 3.4959 | 2026-03-19 |
| 0.005 | 2p0 | maker | -258.92 | -0.0805 | 2026-05-04 | 2026-05-15 | 2026-05-21 | 16 | 2.0384 | 3.5222 | 2026-03-19 |
| 0.005 | none | taker | -529.94 | -0.1618 | 2026-05-04 | 2026-05-09 | 2026-06-07 | 33 | 2.0326 | 2.4922 | 2026-03-19 |
| 0.005 | none | maker | -936.00 | -0.1370 | 2026-05-04 | 2026-05-09 | 2026-05-21 | 16 | 2.0348 | 2.4982 | 2026-03-19 |
| 0.001 | 0p5 | taker | -138.74 | -0.1387 | 2025-12-20 | 2026-04-17 | None | 203 | 2.1324 | 16.8097 | 2026-03-27 |
| 0.001 | 0p5 | maker | -45.74 | -0.0363 | 2026-05-08 | 2026-05-18 | None | 69 | 2.0196 | 16.8111 | 2026-03-27 |
| 0.001 | 1p0 | taker | -100.31 | -0.0885 | 2026-05-04 | 2026-07-11 | None | 119 | 2.0222 | 14.1196 | 2026-03-27 |
| 0.001 | 1p0 | maker | -44.26 | -0.0297 | 2026-05-08 | 2026-05-18 | 2026-06-25 | 47 | 2.0236 | 14.1218 | 2026-03-27 |
| 0.001 | 2p0 | taker | -97.48 | -0.0751 | 2026-05-04 | 2026-07-11 | None | 68 | 2.0222 | 11.9673 | 2026-03-27 |
| 0.001 | 2p0 | maker | -79.35 | -0.0449 | 2026-06-28 | 2026-07-11 | None | 27 | 2.0193 | 11.9704 | 2026-04-22 |
| 0.001 | none | taker | -133.46 | -0.1140 | 2026-06-28 | 2026-07-11 | None | 47 | 2.0179 | 8.9403 | 2026-03-27 |
| 0.001 | none | maker | -132.06 | -0.1098 | 2026-06-28 | 2026-07-11 | None | 40 | 2.0197 | 8.9428 | 2026-03-27 |

### Monthly (fold) total P&L, per run
All 7 test blocks start/end exactly at 00:00:00 UTC (not mid-day). "outside" is the exit spill after fold 7's nominal end; sum(fold totals) + outside reconciles to final_equity - start to 1e-6 (asserted in the generator).

**q0.01_stop0p5_feetaker** (n_months_positive=0/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | -484.86 | -0.4849 |
| 2 | 30 | -215.06 | -0.4175 |
| 3 | 30 | -26.79 | -0.0893 |
| 4 | 30 | -58.93 | -0.2156 |
| 5 | 30 | -36.80 | -0.1717 |
| 6 | 30 | -28.48 | -0.1604 |
| 7 | 23 | -18.35 | -0.1231 |
| outside | 0 | 0.00 | n/a |

**q0.01_stop0p5_feemaker** (n_months_positive=3/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | -24.56 | -0.0246 |
| 2 | 30 | 17.91 | 0.0184 |
| 3 | 30 | 4.76 | 0.0048 |
| 4 | 30 | -27.20 | -0.0272 |
| 5 | 30 | 408.37 | 0.4206 |
| 6 | 30 | -84.09 | -0.0610 |
| 7 | 23 | -86.59 | -0.0669 |
| outside | 1 | -1.24 | n/a |

**q0.01_stop1p0_feetaker** (n_months_positive=0/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | -271.06 | -0.2711 |
| 2 | 30 | -115.23 | -0.1581 |
| 3 | 30 | -50.55 | -0.0824 |
| 4 | 30 | -125.51 | -0.2229 |
| 5 | 30 | -14.07 | -0.0321 |
| 6 | 30 | -74.72 | -0.1764 |
| 7 | 23 | -77.68 | -0.2227 |
| outside | 1 | -0.27 | n/a |

**q0.01_stop1p0_feemaker** (n_months_positive=7/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 286.12 | 0.2861 |
| 2 | 30 | 492.55 | 0.3830 |
| 3 | 30 | 137.62 | 0.0774 |
| 4 | 30 | 172.64 | 0.0901 |
| 5 | 30 | 1376.39 | 0.6589 |
| 6 | 30 | 53.57 | 0.0155 |
| 7 | 23 | 15.86 | 0.0045 |
| outside | 1 | -9.56 | n/a |

**q0.01_stop2p0_feetaker** (n_months_positive=4/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 30.95 | 0.0310 |
| 2 | 30 | 235.46 | 0.2284 |
| 3 | 30 | 37.68 | 0.0298 |
| 4 | 30 | -175.60 | -0.1347 |
| 5 | 30 | 474.05 | 0.4201 |
| 6 | 30 | -193.02 | -0.1204 |
| 7 | 23 | -272.47 | -0.1933 |
| outside | 1 | -4.52 | n/a |

**q0.01_stop2p0_feemaker** (n_months_positive=7/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 638.01 | 0.6380 |
| 2 | 30 | 1332.80 | 0.8137 |
| 3 | 30 | 518.52 | 0.1745 |
| 4 | 30 | 557.50 | 0.1598 |
| 5 | 30 | 4360.97 | 1.0776 |
| 6 | 30 | 766.64 | 0.0912 |
| 7 | 23 | 130.88 | 0.0143 |
| outside | 1 | -34.86 | n/a |

**q0.01_stopnone_feetaker** (n_months_positive=7/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 240.88 | 0.2409 |
| 2 | 30 | 515.89 | 0.4157 |
| 3 | 30 | 159.68 | 0.0909 |
| 4 | 30 | 433.61 | 0.2263 |
| 5 | 30 | 1178.73 | 0.5016 |
| 6 | 30 | 311.31 | 0.0882 |
| 7 | 23 | 203.56 | 0.0530 |
| outside | 1 | -7.61 | n/a |

**q0.01_stopnone_feemaker** (n_months_positive=7/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 690.27 | 0.6903 |
| 2 | 30 | 1338.18 | 0.7917 |
| 3 | 30 | 699.90 | 0.2311 |
| 4 | 30 | 1815.65 | 0.4870 |
| 5 | 30 | 5153.12 | 0.9295 |
| 6 | 30 | 3164.84 | 0.2959 |
| 7 | 23 | 3113.87 | 0.2246 |
| outside | 1 | -39.91 | n/a |

**q0.005_stop0p5_feetaker** (n_months_positive=0/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | -338.24 | -0.3382 |
| 2 | 30 | -175.13 | -0.2646 |
| 3 | 30 | -26.93 | -0.0553 |
| 4 | 30 | -76.82 | -0.1671 |
| 5 | 30 | -20.98 | -0.0548 |
| 6 | 30 | -31.41 | -0.0868 |
| 7 | 23 | -48.20 | -0.1458 |
| outside | 0 | 0.00 | n/a |

**q0.005_stop0p5_feemaker** (n_months_positive=5/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 19.27 | 0.0193 |
| 2 | 30 | 47.43 | 0.0465 |
| 3 | 30 | 3.94 | 0.0037 |
| 4 | 30 | -34.23 | -0.0320 |
| 5 | 30 | 342.94 | 0.3309 |
| 6 | 30 | 1.52 | 0.0011 |
| 7 | 23 | -1.18 | -0.0009 |
| outside | 1 | -0.49 | n/a |

**q0.005_stop1p0_feetaker** (n_months_positive=1/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | -220.65 | -0.2207 |
| 2 | 30 | -35.72 | -0.0458 |
| 3 | 30 | -22.04 | -0.0296 |
| 4 | 30 | -62.03 | -0.0860 |
| 5 | 30 | 73.98 | 0.1122 |
| 6 | 30 | -52.23 | -0.0712 |
| 7 | 23 | -64.27 | -0.0943 |
| outside | 1 | -0.77 | n/a |

**q0.005_stop1p0_feemaker** (n_months_positive=7/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 129.72 | 0.1297 |
| 2 | 30 | 358.85 | 0.3176 |
| 3 | 30 | 60.62 | 0.0407 |
| 4 | 30 | 110.60 | 0.0714 |
| 5 | 30 | 905.62 | 0.5456 |
| 6 | 30 | 65.84 | 0.0257 |
| 7 | 23 | 140.94 | 0.0536 |
| outside | 1 | -3.23 | n/a |

**q0.005_stop2p0_feetaker** (n_months_positive=4/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 74.58 | 0.0746 |
| 2 | 30 | 211.99 | 0.1973 |
| 3 | 30 | 14.72 | 0.0114 |
| 4 | 30 | -105.97 | -0.0814 |
| 5 | 30 | 468.56 | 0.3920 |
| 6 | 30 | -67.69 | -0.0407 |
| 7 | 23 | -82.58 | -0.0517 |
| outside | 1 | -4.32 | n/a |

**q0.005_stop2p0_feemaker** (n_months_positive=7/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 452.15 | 0.4522 |
| 2 | 30 | 860.68 | 0.5927 |
| 3 | 30 | 164.07 | 0.0709 |
| 4 | 30 | 214.34 | 0.0865 |
| 5 | 30 | 2238.44 | 0.8317 |
| 6 | 30 | 308.31 | 0.0625 |
| 7 | 23 | 513.99 | 0.0981 |
| outside | 1 | -15.65 | n/a |

**q0.005_stopnone_feetaker** (n_months_positive=6/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 272.23 | 0.2722 |
| 2 | 30 | 433.77 | 0.3409 |
| 3 | 30 | 89.28 | 0.0523 |
| 4 | 30 | 331.50 | 0.1846 |
| 5 | 30 | 818.13 | 0.3847 |
| 6 | 30 | 459.00 | 0.1559 |
| 7 | 23 | -11.56 | -0.0034 |
| outside | 1 | -22.68 | n/a |

**q0.005_stopnone_feemaker** (n_months_positive=7/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 554.03 | 0.5540 |
| 2 | 30 | 995.31 | 0.6405 |
| 3 | 30 | 281.05 | 0.1102 |
| 4 | 30 | 1077.30 | 0.3806 |
| 5 | 30 | 2866.03 | 0.7334 |
| 6 | 30 | 1846.28 | 0.2726 |
| 7 | 23 | 1186.33 | 0.1376 |
| outside | 1 | -56.85 | n/a |

**q0.001_stop0p5_feetaker** (n_months_positive=1/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | -39.19 | -0.0392 |
| 2 | 30 | -48.73 | -0.0507 |
| 3 | 30 | -8.20 | -0.0090 |
| 4 | 30 | -39.70 | -0.0439 |
| 5 | 30 | 38.83 | 0.0449 |
| 6 | 30 | -4.75 | -0.0053 |
| 7 | 23 | -33.15 | -0.0369 |
| outside | 0 | 0.00 | n/a |

**q0.001_stop0p5_feemaker** (n_months_positive=5/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 66.11 | 0.0661 |
| 2 | 30 | 16.76 | 0.0157 |
| 3 | 30 | 6.69 | 0.0062 |
| 4 | 30 | -16.14 | -0.0148 |
| 5 | 30 | 147.03 | 0.1370 |
| 6 | 30 | 9.09 | 0.0074 |
| 7 | 23 | -3.83 | -0.0031 |
| outside | 0 | 0.00 | n/a |

**q0.001_stop1p0_feetaker** (n_months_positive=2/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | -14.69 | -0.0147 |
| 2 | 30 | -10.09 | -0.0102 |
| 3 | 30 | 4.78 | 0.0049 |
| 4 | 30 | -7.99 | -0.0082 |
| 5 | 30 | 105.02 | 0.1080 |
| 6 | 30 | -6.17 | -0.0057 |
| 7 | 23 | -37.70 | -0.0352 |
| outside | 0 | 0.00 | n/a |

**q0.001_stop1p0_feemaker** (n_months_positive=6/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 91.84 | 0.0918 |
| 2 | 30 | 65.40 | 0.0599 |
| 3 | 30 | 26.69 | 0.0231 |
| 4 | 30 | 24.49 | 0.0207 |
| 5 | 30 | 243.86 | 0.2018 |
| 6 | 30 | 10.13 | 0.0070 |
| 7 | 23 | -2.76 | -0.0019 |
| outside | 0 | 0.00 | n/a |

**q0.001_stop2p0_feetaker** (n_months_positive=5/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 0.37 | 0.0004 |
| 2 | 30 | 38.86 | 0.0388 |
| 3 | 30 | 11.13 | 0.0107 |
| 4 | 30 | -8.32 | -0.0079 |
| 5 | 30 | 205.85 | 0.1975 |
| 6 | 30 | 14.52 | 0.0116 |
| 7 | 23 | -62.15 | -0.0492 |
| outside | 0 | 0.00 | n/a |

**q0.001_stop2p0_feemaker** (n_months_positive=6/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 102.06 | 0.1021 |
| 2 | 30 | 120.93 | 0.1097 |
| 3 | 30 | 35.45 | 0.0290 |
| 4 | 30 | 26.25 | 0.0209 |
| 5 | 30 | 386.76 | 0.3011 |
| 6 | 30 | 40.72 | 0.0244 |
| 7 | 23 | -25.36 | -0.0148 |
| outside | 0 | 0.00 | n/a |

**q0.001_stopnone_feetaker** (n_months_positive=5/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 99.04 | 0.0990 |
| 2 | 30 | 120.30 | 0.1095 |
| 3 | 30 | -6.29 | -0.0052 |
| 4 | 30 | 126.11 | 0.1040 |
| 5 | 30 | 264.96 | 0.1979 |
| 6 | 30 | 53.49 | 0.0333 |
| 7 | 23 | -72.74 | -0.0439 |
| outside | 1 | 1.74 | n/a |

**q0.001_stopnone_feemaker** (n_months_positive=6/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 181.78 | 0.1818 |
| 2 | 30 | 166.62 | 0.1410 |
| 3 | 30 | 16.99 | 0.0126 |
| 4 | 30 | 184.39 | 0.1350 |
| 5 | 30 | 450.77 | 0.2909 |
| 6 | 30 | 92.80 | 0.0464 |
| 7 | 23 | -16.90 | -0.0081 |
| outside | 1 | 2.46 | n/a |

### EV check (stop=none only; fold 1 not scored, no earlier test month to fit on)
EV quintiles rank realised net monotonically (quintile 0 to 4 non-decreasing) in 0/6 tables (e.g. q0.01_feetaker: quintile 0 mean_realised_net=0.3363 is above quintile 1's 0.2034). EV here is descriptive only -- it does not rank realised net in these tables, and no claim that it predicts profit should be drawn from this table.

**q0.01_feetaker** (n_scored=11307):
| quintile | n | mean_ev | mean_realised_net |
|---|---|---|---|
| 0 | 2498 | -0.0976 | 0.3363 |
| 1 | 2029 | -0.0002 | 0.2034 |
| 2 | 2503 | 0.1227 | 0.1884 |
| 3 | 2280 | 0.2009 | 0.2048 |
| 4 | 1997 | 0.4000 | 0.3078 |

**q0.01_feemaker** (n_scored=11341):
| quintile | n | mean_ev | mean_realised_net |
|---|---|---|---|
| 0 | 2382 | 0.1089 | 1.4377 |
| 1 | 2694 | 0.3136 | 1.4952 |
| 2 | 1876 | 0.4339 | 0.3127 |
| 3 | 2282 | 0.5627 | 1.7777 |
| 4 | 2107 | 0.9421 | 1.5013 |

**q0.005_feetaker** (n_scored=7981):
| quintile | n | mean_ev | mean_realised_net |
|---|---|---|---|
| 0 | 1756 | -0.0044 | 0.4156 |
| 1 | 1515 | 0.1084 | 0.1929 |
| 2 | 1575 | 0.1627 | 0.1061 |
| 3 | 1649 | 0.2328 | 0.2194 |
| 4 | 1486 | 0.4442 | 0.3723 |

**q0.005_feemaker** (n_scored=8014):
| quintile | n | mean_ev | mean_realised_net |
|---|---|---|---|
| 0 | 1924 | 0.2403 | 1.2263 |
| 1 | 1366 | 0.3504 | 0.5510 |
| 2 | 1558 | 0.4006 | 1.1384 |
| 3 | 1589 | 0.5285 | 1.1967 |
| 4 | 1577 | 0.7710 | 0.8977 |

**q0.001_feetaker** (n_scored=2255):
| quintile | n | mean_ev | mean_realised_net |
|---|---|---|---|
| 0 | 479 | 0.1101 | -0.0758 |
| 1 | 459 | 0.1569 | 0.2515 |
| 2 | 427 | 0.2244 | 0.4652 |
| 3 | 794 | 0.3538 | 0.2289 |
| 4 | 96 | 0.6128 | 0.3095 |

**q0.001_feemaker** (n_scored=2271):
| quintile | n | mean_ev | mean_realised_net |
|---|---|---|---|
| 0 | 483 | 0.2184 | 0.0930 |
| 1 | 591 | 0.2775 | 0.7421 |
| 2 | 299 | 0.3570 | 0.2898 |
| 3 | 761 | 0.4625 | 0.3157 |
| 4 | 137 | 0.6783 | 0.6457 |

### cost-share diagnostic (OVERLAPPING accounts across the 24 runs, not a combined P&L)
n_trades=303,425 gross=94,314.48 fee=44,948.16 funding_net=309.54 net=49,056.78 fee_share_of_gross=0.4766

### Known gaps
- slippage excluded by the user's choice (legs are small); costs are a lower bound and results an upper bound (optimistic).
- max_leverage is today's snapshot (hindsight); limits were different in the past.
- liquidation is checked on 1-minute closes; a move inside a minute can liquidate earlier.
- maker fills are assumed to fill; in practice they may not.
- the test months were already used for the cut-off, the deep dive and the calibration: results are optimistic until the vault or paper-trading check.

### Equity curve PNGs
- research/dislocation_model/logs/s1_profit1_equity_q0.01_feetaker_open20.png
- research/dislocation_model/logs/s1_profit1_equity_q0.01_feemaker_open20.png
- research/dislocation_model/logs/s1_profit1_equity_q0.005_feetaker_open20.png
- research/dislocation_model/logs/s1_profit1_equity_q0.005_feemaker_open20.png
- research/dislocation_model/logs/s1_profit1_equity_q0.001_feetaker_open20.png
- research/dislocation_model/logs/s1_profit1_equity_q0.001_feemaker_open20.png