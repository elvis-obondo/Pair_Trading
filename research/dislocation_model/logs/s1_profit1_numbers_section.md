## [HL-PROFIT1] Portfolio backtest, S1's live picks, build2 d3/asm price, slippage_spread_share=0.0

Runs ending above the $1000 start: 18/24.

| q | stop | fee | final_equity | total_return | n_trades | win_rate | profit_factor | sharpe | sortino | max_dd_pct |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.01 | 0p5 | taker | 155.63 | -0.8444 | 19,901 | 0.2808 | 0.7595 | -11.939 | -14.962 | -0.8444 |
| 0.01 | 0p5 | maker | 1203.04 | 0.2030 | 21,952 | 0.2801 | 1.0265 | 1.335 | 2.596 | -0.1664 |
| 0.01 | 1p0 | taker | 351.90 | -0.6481 | 17,742 | 0.4031 | 0.8865 | -6.230 | -9.808 | -0.6481 |
| 0.01 | 1p0 | maker | 2417.34 | 1.4173 | 17,982 | 0.4060 | 1.1082 | 5.473 | 13.443 | -0.0870 |
| 0.01 | 2p0 | taker | 929.58 | -0.0704 | 13,531 | 0.5536 | 0.9913 | -0.260 | -0.498 | -0.3352 |
| 0.01 | 2p0 | maker | 3613.17 | 2.6132 | 13,538 | 0.5521 | 1.1632 | 7.455 | 18.306 | -0.0669 |
| 0.01 | none | taker | 2205.99 | 1.2060 | 8,078 | 0.7065 | 1.1692 | 3.898 | 5.646 | -0.1293 |
| 0.01 | none | maker | 5034.35 | 4.0344 | 8,069 | 0.7081 | 1.3685 | 7.706 | 11.269 | -0.0982 |
| 0.005 | 0p5 | taker | 353.37 | -0.6466 | 13,201 | 0.2838 | 0.7900 | -7.337 | -9.797 | -0.6466 |
| 0.005 | 0p5 | maker | 1332.97 | 0.3330 | 13,703 | 0.2851 | 1.0709 | 2.220 | 4.660 | -0.0955 |
| 0.005 | 1p0 | taker | 701.18 | -0.2988 | 11,920 | 0.4143 | 0.9363 | -2.359 | -3.817 | -0.2988 |
| 0.005 | 1p0 | maker | 2374.42 | 1.3744 | 12,055 | 0.4158 | 1.1764 | 6.171 | 13.720 | -0.0630 |
| 0.005 | 2p0 | taker | 1250.74 | 0.2507 | 9,834 | 0.5617 | 1.0389 | 1.577 | 2.986 | -0.2284 |
| 0.005 | 2p0 | maker | 3315.02 | 2.3150 | 9,879 | 0.5618 | 1.2275 | 7.607 | 18.920 | -0.0488 |
| 0.005 | none | taker | 1960.18 | 0.9602 | 6,587 | 0.7164 | 1.1735 | 3.725 | 5.721 | -0.1254 |
| 0.005 | none | maker | 4138.00 | 3.1380 | 6,595 | 0.7196 | 1.3954 | 6.983 | 10.156 | -0.1093 |
| 0.001 | 0p5 | taker | 858.01 | -0.1420 | 3,326 | 0.2971 | 0.8717 | -2.449 | -3.904 | -0.1420 |
| 0.001 | 0p5 | maker | 1189.94 | 0.1899 | 3,361 | 0.2981 | 1.1814 | 2.785 | 6.791 | -0.0340 |
| 0.001 | 1p0 | taker | 1009.06 | 0.0091 | 3,259 | 0.4277 | 1.0063 | 0.185 | 0.343 | -0.0851 |
| 0.001 | 1p0 | maker | 1417.70 | 0.4177 | 3,285 | 0.4286 | 1.2820 | 4.307 | 11.127 | -0.0280 |
| 0.001 | 2p0 | taker | 1199.47 | 0.1995 | 3,085 | 0.5802 | 1.1132 | 2.031 | 3.212 | -0.0715 |
| 0.001 | 2p0 | maker | 1638.86 | 0.6389 | 3,112 | 0.5794 | 1.3348 | 5.073 | 9.224 | -0.0449 |
| 0.001 | none | taker | 1511.91 | 0.5119 | 2,573 | 0.7439 | 1.2673 | 3.650 | 4.253 | -0.0720 |
| 0.001 | none | maker | 2012.22 | 1.0122 | 2,583 | 0.7449 | 1.4690 | 6.057 | 7.877 | -0.0597 |

### Costs (USD and share of gross), per run
| q | stop | fee | gross | fee | fee_share | slippage | slip_share | funding_paid | fund_paid_share | funding_received | fund_recv_share |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.01 | 0p5 | taker | 526.03 | 1370.44 | 2.6053 | 0.00 | 0.0000 | 12.91 | 0.0245 | 12.96 | 0.0246 |
| 0.01 | 0p5 | maker | 1495.80 | 1294.28 | 0.8653 | 0.00 | 0.0000 | 35.61 | 0.0238 | 37.12 | 0.0248 |
| 0.01 | 1p0 | taker | 1198.63 | 1843.69 | 1.5382 | 0.00 | 0.0000 | 33.60 | 0.0280 | 30.55 | 0.0255 |
| 0.01 | 1p0 | maker | 3108.35 | 1686.49 | 0.5426 | 0.00 | 0.0000 | 88.87 | 0.0286 | 84.34 | 0.0271 |
| 0.01 | 2p0 | taker | 2182.91 | 2248.24 | 1.0299 | 0.00 | 0.0000 | 71.84 | 0.0329 | 66.75 | 0.0306 |
| 0.01 | 2p0 | maker | 4258.85 | 1641.65 | 0.3855 | 0.00 | 0.0000 | 148.07 | 0.0348 | 144.05 | 0.0338 |
| 0.01 | none | taker | 3135.27 | 1892.56 | 0.6036 | 0.00 | 0.0000 | 166.61 | 0.0531 | 129.89 | 0.0414 |
| 0.01 | none | maker | 5122.67 | 1031.67 | 0.2014 | 0.00 | 0.0000 | 262.47 | 0.0512 | 205.82 | 0.0402 |
| 0.005 | 0p5 | taker | 584.30 | 1230.12 | 2.1053 | 0.00 | 0.0000 | 11.62 | 0.0199 | 10.81 | 0.0185 |
| 0.005 | 0p5 | maker | 1134.53 | 801.90 | 0.7068 | 0.00 | 0.0000 | 21.40 | 0.0189 | 21.74 | 0.0192 |
| 0.005 | 1p0 | taker | 1267.62 | 1562.27 | 1.2324 | 0.00 | 0.0000 | 28.02 | 0.0221 | 23.85 | 0.0188 |
| 0.005 | 1p0 | maker | 2407.20 | 1029.44 | 0.4276 | 0.00 | 0.0000 | 53.19 | 0.0221 | 49.85 | 0.0207 |
| 0.005 | 2p0 | taker | 2102.00 | 1842.92 | 0.8767 | 0.00 | 0.0000 | 59.17 | 0.0282 | 50.84 | 0.0242 |
| 0.005 | 2p0 | maker | 3399.17 | 1068.82 | 0.3144 | 0.00 | 0.0000 | 99.37 | 0.0292 | 84.04 | 0.0247 |
| 0.005 | none | taker | 2447.87 | 1470.35 | 0.6007 | 0.00 | 0.0000 | 123.71 | 0.0505 | 106.37 | 0.0435 |
| 0.005 | none | maker | 3920.39 | 756.67 | 0.1930 | 0.00 | 0.0000 | 188.78 | 0.0482 | 163.05 | 0.0416 |
| 0.001 | 0p5 | taker | 326.73 | 467.66 | 1.4313 | 0.00 | 0.0000 | 4.86 | 0.0149 | 3.80 | 0.0116 |
| 0.001 | 0p5 | maker | 376.98 | 185.51 | 0.4921 | 0.00 | 0.0000 | 6.00 | 0.0159 | 4.47 | 0.0119 |
| 0.001 | 1p0 | taker | 507.23 | 496.47 | 0.9788 | 0.00 | 0.0000 | 9.23 | 0.0182 | 7.53 | 0.0148 |
| 0.001 | 1p0 | maker | 619.70 | 199.84 | 0.3225 | 0.00 | 0.0000 | 11.18 | 0.0180 | 9.02 | 0.0146 |
| 0.001 | 2p0 | taker | 720.56 | 515.55 | 0.7155 | 0.00 | 0.0000 | 18.91 | 0.0262 | 13.38 | 0.0186 |
| 0.001 | 2p0 | maker | 851.07 | 204.80 | 0.2406 | 0.00 | 0.0000 | 22.91 | 0.0269 | 15.50 | 0.0182 |
| 0.001 | none | taker | 1020.55 | 500.19 | 0.4901 | 0.00 | 0.0000 | 44.40 | 0.0435 | 35.95 | 0.0352 |
| 0.001 | none | maker | 1222.67 | 199.71 | 0.1633 | 0.00 | 0.0000 | 53.44 | 0.0437 | 42.70 | 0.0349 |

### CAGR (annualised, N days), per run
| q | stop | fee | cagr | cagr_n_days |
|---|---|---|---|---|
| 0.01 | 0p5 | taker | -0.9653 | 202 |
| 0.01 | 0p5 | maker | 0.3943 | 203 |
| 0.01 | 1p0 | taker | -0.8471 | 203 |
| 0.01 | 1p0 | maker | 3.8894 | 203 |
| 0.01 | 2p0 | taker | -0.1230 | 203 |
| 0.01 | 2p0 | maker | 9.0716 | 203 |
| 0.01 | none | taker | 3.1477 | 203 |
| 0.01 | none | maker | 17.2858 | 203 |
| 0.005 | 0p5 | taker | -0.8459 | 203 |
| 0.005 | 0p5 | maker | 0.6766 | 203 |
| 0.005 | 1p0 | taker | -0.4718 | 203 |
| 0.005 | 1p0 | maker | 3.7344 | 203 |
| 0.005 | 2p0 | taker | 0.4952 | 203 |
| 0.005 | 2p0 | maker | 7.6268 | 203 |
| 0.005 | none | taker | 2.3539 | 203 |
| 0.005 | none | maker | 11.8531 | 203 |
| 0.001 | 0p5 | taker | -0.2417 | 202 |
| 0.001 | 0p5 | maker | 0.3692 | 202 |
| 0.001 | 1p0 | taker | 0.0164 | 202 |
| 0.001 | 1p0 | maker | 0.8789 | 202 |
| 0.001 | 2p0 | taker | 0.3891 | 202 |
| 0.001 | 2p0 | maker | 1.4415 | 202 |
| 0.001 | none | taker | 1.1028 | 203 |
| 0.001 | none | maker | 2.5157 | 203 |

### Daily P&L, per run
| q | stop | fee | mean | median | share_positive_days | worst_day | best_day |
|---|---|---|---|---|---|---|---|
| 0.01 | 0p5 | taker | -4.1594 | -2.0211 | 0.1773 | -51.46 | 17.07 |
| 0.01 | 0p5 | maker | 0.9953 | -0.7687 | 0.4706 | -36.12 | 103.01 |
| 0.01 | 1p0 | taker | -3.1770 | -3.2575 | 0.3382 | -36.82 | 36.63 |
| 0.01 | 1p0 | maker | 6.9477 | 0.5036 | 0.5147 | -63.41 | 149.42 |
| 0.01 | 2p0 | taker | -0.3452 | -2.2062 | 0.4314 | -42.77 | 85.34 |
| 0.01 | 2p0 | maker | 12.8097 | 6.8271 | 0.6127 | -92.51 | 214.74 |
| 0.01 | none | taker | 5.9117 | 5.4990 | 0.5980 | -81.07 | 106.08 |
| 0.01 | none | maker | 19.7762 | 16.5426 | 0.6912 | -127.01 | 266.03 |
| 0.005 | 0p5 | taker | -3.1698 | -1.8603 | 0.2892 | -40.06 | 32.04 |
| 0.005 | 0p5 | maker | 1.6322 | -0.1914 | 0.4853 | -38.04 | 102.13 |
| 0.005 | 1p0 | taker | -1.4648 | -1.6963 | 0.3824 | -41.79 | 65.86 |
| 0.005 | 1p0 | maker | 6.7374 | 1.6062 | 0.5882 | -67.48 | 155.31 |
| 0.005 | 2p0 | taker | 1.2291 | -0.0761 | 0.5000 | -59.07 | 93.14 |
| 0.005 | 2p0 | maker | 11.3482 | 6.2665 | 0.6275 | -105.38 | 193.77 |
| 0.005 | none | taker | 4.7068 | 4.6412 | 0.6127 | -76.15 | 98.09 |
| 0.005 | none | maker | 15.3824 | 12.9803 | 0.7108 | -114.31 | 218.80 |
| 0.001 | 0p5 | taker | -0.6995 | -0.4821 | 0.3153 | -15.39 | 43.37 |
| 0.001 | 0p5 | maker | 0.9356 | 0.0000 | 0.4483 | -18.44 | 65.66 |
| 0.001 | 1p0 | taker | 0.0446 | -0.2128 | 0.3695 | -19.79 | 69.38 |
| 0.001 | 1p0 | maker | 2.0576 | 0.1903 | 0.5222 | -24.41 | 102.89 |
| 0.001 | 2p0 | taker | 0.9826 | 0.0000 | 0.4581 | -38.64 | 81.82 |
| 0.001 | 2p0 | maker | 3.1471 | 0.8258 | 0.5468 | -43.84 | 112.71 |
| 0.001 | none | taker | 2.5094 | 1.2082 | 0.6225 | -64.94 | 48.49 |
| 0.001 | none | maker | 4.9619 | 2.4452 | 0.6912 | -82.06 | 58.35 |

### Trades, per run
| q | stop | fee | win_rate(mu) | stop_share | timeout_share | mean_net | median_net | mean_roc | median_roc | mean_win | mean_loss | mean_holding_min |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.01 | 0p5 | taker | 0.2808 | 0.7175 | 0.0017 | -0.0424 | -0.1319 | -0.0019 | -0.0077 | 0.4744 | -0.2458 | 45.0 |
| 0.01 | 0p5 | maker | 0.2801 | 0.7184 | 0.0015 | 0.0092 | -0.3251 | 0.0002 | -0.0057 | 1.2747 | -0.4866 | 45.8 |
| 0.01 | 1p0 | taker | 0.4031 | 0.5907 | 0.0063 | -0.0365 | -0.2867 | -0.0012 | -0.0097 | 0.7007 | -0.5426 | 77.8 |
| 0.01 | 1p0 | maker | 0.4060 | 0.5875 | 0.0065 | 0.0788 | -0.6194 | 0.0010 | -0.0077 | 1.9655 | -1.2363 | 78.7 |
| 0.01 | 2p0 | taker | 0.5536 | 0.4185 | 0.0279 | -0.0052 | 0.4073 | -0.0001 | 0.0075 | 1.0425 | -1.3730 | 133.1 |
| 0.01 | 2p0 | maker | 0.5521 | 0.4205 | 0.0273 | 0.1930 | 0.8274 | 0.0019 | 0.0093 | 2.4290 | -2.7279 | 133.3 |
| 0.01 | none | taker | 0.7065 | 0.0000 | 0.2935 | 0.1493 | 0.8188 | 0.0020 | 0.0113 | 1.3947 | -3.3891 | 285.5 |
| 0.01 | none | maker | 0.7081 | 0.0000 | 0.2919 | 0.5000 | 1.3273 | 0.0041 | 0.0132 | 2.4824 | -5.3857 | 286.0 |
| 0.005 | 0p5 | taker | 0.2838 | 0.7149 | 0.0012 | -0.0490 | -0.2124 | -0.0016 | -0.0075 | 0.6468 | -0.3261 | 43.0 |
| 0.005 | 0p5 | maker | 0.2851 | 0.7139 | 0.0010 | 0.0243 | -0.3174 | 0.0004 | -0.0056 | 1.2823 | -0.4798 | 43.2 |
| 0.005 | 1p0 | taker | 0.4143 | 0.5798 | 0.0060 | -0.0251 | -0.3907 | -0.0006 | -0.0093 | 0.8822 | -0.6752 | 74.5 |
| 0.005 | 1p0 | maker | 0.4158 | 0.5783 | 0.0058 | 0.1140 | -0.5356 | 0.0015 | -0.0073 | 1.8114 | -1.1138 | 75.0 |
| 0.005 | 2p0 | taker | 0.5617 | 0.4132 | 0.0251 | 0.0255 | 0.4523 | 0.0005 | 0.0074 | 1.1892 | -1.5298 | 128.2 |
| 0.005 | 2p0 | maker | 0.5618 | 0.4130 | 0.0252 | 0.2343 | 0.8114 | 0.0025 | 0.0094 | 2.1984 | -2.4235 | 127.8 |
| 0.005 | none | taker | 0.7164 | 0.0000 | 0.2836 | 0.1458 | 0.7904 | 0.0021 | 0.0112 | 1.3216 | -3.3106 | 279.2 |
| 0.005 | none | maker | 0.7196 | 0.0000 | 0.2804 | 0.4758 | 1.2726 | 0.0044 | 0.0132 | 2.2230 | -4.9208 | 278.3 |
| 0.001 | 0p5 | taker | 0.2971 | 0.7017 | 0.0012 | -0.0427 | -0.3293 | -0.0009 | -0.0070 | 0.9758 | -0.4737 | 37.6 |
| 0.001 | 0p5 | maker | 0.2981 | 0.7007 | 0.0012 | 0.0565 | -0.2853 | 0.0011 | -0.0052 | 1.2310 | -0.4445 | 37.7 |
| 0.001 | 1p0 | taker | 0.4277 | 0.5670 | 0.0052 | 0.0028 | -0.4352 | 0.0001 | -0.0086 | 1.0316 | -0.7691 | 64.9 |
| 0.001 | 1p0 | maker | 0.4286 | 0.5659 | 0.0055 | 0.1272 | -0.3965 | 0.0022 | -0.0067 | 1.3401 | -0.7930 | 65.2 |
| 0.001 | 2p0 | taker | 0.5802 | 0.4016 | 0.0182 | 0.0647 | 0.4202 | 0.0012 | 0.0076 | 1.0896 | -1.3730 | 110.5 |
| 0.001 | 2p0 | maker | 0.5794 | 0.4033 | 0.0174 | 0.2053 | 0.5985 | 0.0032 | 0.0095 | 1.3941 | -1.4849 | 109.9 |
| 0.001 | none | taker | 0.7439 | 0.0000 | 0.2561 | 0.1990 | 0.7389 | 0.0033 | 0.0115 | 1.2369 | -3.1339 | 257.4 |
| 0.001 | none | maker | 0.7449 | 0.0000 | 0.2551 | 0.3919 | 0.9907 | 0.0055 | 0.0134 | 1.5916 | -3.6519 | 257.2 |

### Skips by reason, per run
| q | stop | fee | book_full | min_order |
|---|---|---|---|---|
| 0.01 | 0p5 | taker | 11788 | 3940 |
| 0.01 | 0p5 | maker | 13402 | 275 |
| 0.01 | 1p0 | taker | 16941 | 946 |
| 0.01 | 1p0 | maker | 17549 | 98 |
| 0.01 | 2p0 | taker | 21891 | 207 |
| 0.01 | 2p0 | maker | 22029 | 62 |
| 0.01 | none | taker | 27488 | 63 |
| 0.01 | none | maker | 27520 | 40 |
| 0.005 | 0p5 | taker | 3481 | 1017 |
| 0.005 | 0p5 | maker | 3767 | 229 |
| 0.005 | 1p0 | taker | 5392 | 387 |
| 0.005 | 1p0 | maker | 5540 | 104 |
| 0.005 | 2p0 | taker | 7734 | 131 |
| 0.005 | 2p0 | maker | 7754 | 66 |
| 0.005 | none | taker | 11049 | 63 |
| 0.005 | none | maker | 11060 | 44 |
| 0.001 | 0p5 | taker | 153 | 159 |
| 0.001 | 0p5 | maker | 157 | 120 |
| 0.001 | 1p0 | taker | 248 | 131 |
| 0.001 | 1p0 | maker | 256 | 97 |
| 0.001 | 2p0 | taker | 447 | 106 |
| 0.001 | 2p0 | maker | 443 | 83 |
| 0.001 | none | taker | 996 | 69 |
| 0.001 | none | maker | 1003 | 52 |

### Leverage and risk, per run
| q | stop | fee | peak_margin_used | mean_open | max_open | n_liquidations |
|---|---|---|---|---|---|---|
| 0.01 | 0p5 | taker | 496.72 | 4.04 | 10 | 0 |
| 0.01 | 0p5 | maker | 719.95 | 4.32 | 10 | 0 |
| 0.01 | 1p0 | taker | 500.11 | 5.42 | 10 | 0 |
| 0.01 | 1p0 | maker | 1320.88 | 5.52 | 10 | 0 |
| 0.01 | 2p0 | taker | 696.86 | 6.62 | 10 | 0 |
| 0.01 | 2p0 | maker | 1944.53 | 6.63 | 10 | 0 |
| 0.01 | none | taker | 1202.38 | 8.11 | 10 | 0 |
| 0.01 | none | maker | 2661.84 | 8.11 | 10 | 0 |
| 0.005 | 0p5 | taker | 498.72 | 3.15 | 10 | 0 |
| 0.005 | 0p5 | maker | 730.02 | 3.22 | 10 | 0 |
| 0.005 | 1p0 | taker | 498.39 | 4.12 | 10 | 0 |
| 0.005 | 1p0 | maker | 1249.12 | 4.17 | 10 | 0 |
| 0.005 | 2p0 | taker | 808.95 | 5.23 | 10 | 0 |
| 0.005 | 2p0 | maker | 1717.26 | 5.24 | 10 | 0 |
| 0.005 | none | taker | 1059.35 | 6.87 | 10 | 0 |
| 0.005 | none | maker | 2151.71 | 6.85 | 10 | 0 |
| 0.001 | 0p5 | taker | 497.34 | 1.89 | 10 | 0 |
| 0.001 | 0p5 | maker | 599.47 | 1.90 | 10 | 0 |
| 0.001 | 1p0 | taker | 538.31 | 2.27 | 10 | 0 |
| 0.001 | 1p0 | maker | 724.09 | 2.29 | 10 | 0 |
| 0.001 | 2p0 | taker | 644.85 | 2.71 | 10 | 0 |
| 0.001 | 2p0 | maker | 854.81 | 2.71 | 10 | 0 |
| 0.001 | none | taker | 814.76 | 3.72 | 10 | 0 |
| 0.001 | none | maker | 1071.54 | 3.70 | 10 | 0 |

### Liquidation events, per run
none, in any of the 24 runs.

### Splits: top/bottom 10 coins (net of trades involving the coin, each trade counted for both coins) and pairs, per run
**q0.01_stop0p5_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 67.05 |
| MEGA | 51.72 |
| NOT | 26.12 |
| MEW | 17.00 |
| STABLE | 11.20 |
| POLYX | 6.62 |
| BOME | 6.16 |
| ZETA | 5.70 |
| RENDER | 4.40 |
| VIRTUAL | 3.51 |
**q0.01_stop0p5_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| COMP | -21.49 |
| TON | -21.50 |
| kFLOKI | -21.93 |
| AVNT | -22.46 |
| VINE | -24.08 |
| TAO | -24.63 |
| ZK | -25.05 |
| LTC | -25.36 |
| PURR | -29.36 |
| FOGO | -33.86 |
**q0.01_stop0p5_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| HMSTR/MEGA | 10.75 |
| FXS/MEGA | 9.56 |
| MEGA/SYRUP | 8.53 |
| FOGO/MAVIA | 8.18 |
| USUAL/ZEREBRO | 6.98 |
| FOGO/STABLE | 6.79 |
| BOME/HMSTR | 6.66 |
| ACE/MEGA | 6.47 |
| FOGO/RENDER | 6.42 |
| HMSTR/MEW | 6.33 |
**q0.01_stop0p5_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| kBONK/kSHIB | -3.35 |
| MEGA/YZY | -3.35 |
| BRETT/FOGO | -3.37 |
| CHILLGUY/MEGA | -3.40 |
| MEGA/PROMPT | -3.64 |
| FOGO/VINE | -4.12 |
| ACE/HMSTR | -4.58 |
| HMSTR/LIT | -5.08 |
| FTT/TST | -5.09 |
| MEGA/MET | -6.08 |

**q0.01_stop0p5_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 377.59 |
| YZY | 165.56 |
| NOT | 115.43 |
| MEW | 104.19 |
| MEGA | 72.84 |
| BOME | 72.76 |
| FTT | 66.09 |
| ZETA | 49.88 |
| POLYX | 44.53 |
| LIT | 38.77 |
**q0.01_stop0p5_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| VINE | -29.53 |
| BABY | -29.58 |
| PURR | -31.60 |
| HYPE | -31.62 |
| EIGEN | -31.98 |
| TON | -34.49 |
| TAO | -36.02 |
| kFLOKI | -39.18 |
| kPEPE | -39.83 |
| CELO | -41.40 |
**q0.01_stop0p5_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| YZY/ZETA | 19.14 |
| GRASS/YZY | 19.13 |
| HMSTR/MEW | 18.02 |
| MAVIA/YZY | 17.68 |
| CRV/HMSTR | 17.11 |
| BOME/HMSTR | 16.43 |
| APT/WLD | 14.23 |
| MAV/ZEREBRO | 13.88 |
| LIT/YZY | 13.61 |
| YZY/kSHIB | 13.31 |
**q0.01_stop0p5_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| HYPE/NOT | -5.58 |
| kBONK/kSHIB | -5.69 |
| JUP/ZEC | -5.73 |
| TST/USUAL | -6.05 |
| FOGO/LAYER | -6.21 |
| WIF/XAI | -6.33 |
| TST/W | -6.44 |
| ACE/HMSTR | -6.63 |
| REZ/ZEREBRO | -9.15 |
| FTT/TST | -17.80 |

**q0.01_stop1p0_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 166.32 |
| MEGA | 78.95 |
| BOME | 51.77 |
| NOT | 48.86 |
| YZY | 45.55 |
| MEW | 43.57 |
| FOGO | 27.34 |
| FTT | 23.55 |
| ZEREBRO | 21.31 |
| LIT | 19.27 |
**q0.01_stop1p0_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| AVNT | -27.77 |
| PURR | -28.49 |
| CELO | -29.02 |
| kFLOKI | -29.34 |
| LINK | -29.69 |
| kPEPE | -30.56 |
| LTC | -32.27 |
| DOGE | -32.46 |
| HYPE | -33.39 |
| VINE | -34.83 |
**q0.01_stop1p0_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| AR/ZK | 15.36 |
| FOGO/GRIFFAIN | 14.25 |
| HMSTR/MEGA | 12.45 |
| FOGO/SAGA | 12.13 |
| FXS/MEGA | 10.83 |
| FOGO/NEAR | 10.37 |
| USUAL/ZEREBRO | 9.34 |
| GRASS/YZY | 9.20 |
| YZY/ZETA | 8.84 |
| BOME/HMSTR | 8.72 |
**q0.01_stop1p0_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| HYPE/NOT | -5.33 |
| CHILLGUY/FOGO | -5.36 |
| FOGO/PEOPLE | -5.39 |
| DYM/HMSTR | -5.48 |
| FOGO/LIT | -5.50 |
| FOGO/XPL | -5.53 |
| HMSTR/LINK | -5.63 |
| HMSTR/PYTH | -5.87 |
| HMSTR/kNEIRO | -9.14 |
| FTT/TST | -9.43 |

**q0.01_stop1p0_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 698.06 |
| YZY | 340.60 |
| BOME | 225.09 |
| MEW | 187.86 |
| NOT | 186.86 |
| FTT | 112.53 |
| MEGA | 104.29 |
| MAVIA | 100.76 |
| BLAST | 97.43 |
| RSR | 92.77 |
**q0.01_stop1p0_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| AVNT | -40.84 |
| ARB | -41.94 |
| ORDI | -44.73 |
| AVAX | -46.31 |
| EIGEN | -46.48 |
| LTC | -46.69 |
| kPEPE | -47.32 |
| CELO | -49.18 |
| BABY | -49.90 |
| HYPE | -50.16 |
**q0.01_stop1p0_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| GRASS/YZY | 34.78 |
| YZY/ZETA | 34.33 |
| MAVIA/YZY | 30.53 |
| APT/WLD | 27.20 |
| HMSTR/TST | 26.80 |
| BOME/HMSTR | 24.99 |
| CRV/HMSTR | 24.28 |
| YZY/kSHIB | 22.91 |
| HMSTR/NIL | 21.51 |
| AR/ZK | 21.06 |
**q0.01_stop1p0_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| HMSTR/kNEIRO | -11.49 |
| TST/W | -11.56 |
| LIT/ZEN | -11.84 |
| APT/ENA | -12.90 |
| NEAR/ONDO | -13.04 |
| AVAX/JUP | -13.07 |
| EIGEN/ENS | -13.39 |
| EIGEN/FTT | -14.74 |
| REZ/ZEREBRO | -18.97 |
| FTT/TST | -28.06 |

**q0.01_stop2p0_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 283.90 |
| MEW | 130.25 |
| YZY | 111.93 |
| MAVIA | 111.41 |
| BOME | 110.41 |
| NOT | 100.40 |
| FOGO | 69.18 |
| FTT | 53.63 |
| PNUT | 47.98 |
| RSR | 44.55 |
**q0.01_stop2p0_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| DOGE | -32.12 |
| EIGEN | -32.31 |
| DYM | -33.01 |
| kNEIRO | -36.15 |
| RESOLV | -37.04 |
| PUMP | -38.25 |
| APE | -39.44 |
| TAO | -42.37 |
| HYPE | -42.64 |
| LTC | -49.81 |
**q0.01_stop2p0_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| AR/ZK | 20.40 |
| GRASS/YZY | 20.27 |
| YZY/ZETA | 18.49 |
| MAVIA/YZY | 15.97 |
| MAV/ZEREBRO | 14.55 |
| HMSTR/SUSHI | 13.46 |
| FOGO/SAGA | 13.29 |
| CRV/HMSTR | 12.60 |
| MEGA/TNSR | 11.98 |
| APEX/MAVIA | 10.72 |
**q0.01_stop2p0_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| LTC/PUMP | -7.64 |
| ENA/LTC | -7.69 |
| GMX/RESOLV | -7.87 |
| EIGEN/ENS | -7.96 |
| APEX/HMSTR | -8.11 |
| BERA/COMP | -8.21 |
| AERO/MEGA | -8.22 |
| HMSTR/kNEIRO | -8.69 |
| CFX/DASH | -9.48 |
| REZ/ZEREBRO | -10.56 |

**q0.01_stop2p0_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 763.14 |
| YZY | 358.79 |
| MEW | 310.62 |
| MAVIA | 294.67 |
| BOME | 250.95 |
| TNSR | 217.62 |
| NOT | 207.46 |
| FTT | 184.94 |
| RSR | 172.47 |
| PNUT | 155.38 |
**q0.01_stop2p0_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| TAO | -53.20 |
| EIGEN | -55.98 |
| LTC | -63.39 |
| DYM | -64.80 |
| HYPE | -73.85 |
| RESOLV | -75.37 |
| FET | -76.26 |
| APE | -79.37 |
| CFX | -97.02 |
| ZRO | -102.70 |
**q0.01_stop2p0_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| MAVIA/YZY | 42.23 |
| MAV/ZEREBRO | 36.70 |
| HMSTR/SUSHI | 33.25 |
| UNI/WLD | 32.48 |
| GRASS/YZY | 31.95 |
| YZY/kSHIB | 31.74 |
| AR/ZK | 26.19 |
| YZY/ZETA | 26.17 |
| FARTCOIN/HMSTR | 26.11 |
| LDO/LIT | 24.45 |
**q0.01_stop2p0_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| BERA/COMP | -18.68 |
| DOGE/XPL | -19.17 |
| APT/ENA | -19.54 |
| LIT/ZEN | -20.11 |
| GMX/RESOLV | -21.37 |
| HMSTR/ORDI | -22.98 |
| WIF/kPEPE | -23.00 |
| CFX/DASH | -23.11 |
| EIGEN/ENS | -25.45 |
| REZ/ZEREBRO | -26.06 |

**q0.01_stopnone_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 393.52 |
| YZY | 212.18 |
| FTT | 146.48 |
| MEW | 131.96 |
| BOME | 125.92 |
| MAVIA | 111.24 |
| BLAST | 107.58 |
| NOT | 104.31 |
| RSR | 90.81 |
| TNSR | 89.03 |
**q0.01_stopnone_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| ZK | -56.90 |
| INIT | -57.21 |
| 2Z | -57.83 |
| DASH | -60.23 |
| COMP | -61.16 |
| APE | -67.00 |
| HYPE | -88.16 |
| SAGA | -90.13 |
| ORDI | -97.60 |
| HYPER | -98.99 |
**q0.01_stopnone_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| MAVIA/YZY | 16.22 |
| ACE/HMSTR | 16.09 |
| HMSTR/MINA | 14.78 |
| HMSTR/POLYX | 13.97 |
| CC/WLD | 13.45 |
| BLAST/GOAT | 13.42 |
| STABLE/STBL | 13.09 |
| JUP/ZEC | 12.86 |
| TST/XMR | 12.85 |
| DYDX/WCT | 12.31 |
**q0.01_stopnone_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| MERL/PROVE | -23.24 |
| ETHFI/XLM | -23.52 |
| CFX/KAITO | -24.76 |
| ARB/COMP | -25.76 |
| ORDI/REZ | -26.91 |
| ADA/VVV | -28.15 |
| 2Z/DASH | -29.48 |
| APE/ZK | -36.62 |
| FARTCOIN/HYPE | -60.60 |
| HYPER/SAGA | -76.69 |

**q0.01_stopnone_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 648.67 |
| YZY | 400.22 |
| FTT | 263.89 |
| NOT | 250.39 |
| MEW | 231.19 |
| BOME | 230.27 |
| BLAST | 228.56 |
| TNSR | 224.14 |
| RSR | 187.62 |
| MAVIA | 170.91 |
**q0.01_stopnone_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| ZK | -74.74 |
| COMP | -77.77 |
| KAITO | -80.37 |
| DASH | -84.28 |
| INIT | -84.38 |
| 2Z | -91.41 |
| SAGA | -129.48 |
| ORDI | -145.36 |
| HYPE | -150.03 |
| HYPER | -159.18 |
**q0.01_stopnone_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| ACE/HMSTR | 34.19 |
| JUP/ZEC | 30.24 |
| MAVIA/YZY | 27.86 |
| CC/WLD | 27.53 |
| DYDX/WCT | 26.69 |
| STABLE/STBL | 25.56 |
| HMSTR/MINA | 25.47 |
| INJ/STRK | 25.13 |
| HMSTR/POLYX | 24.82 |
| NOT/ORDI | 24.48 |
**q0.01_stopnone_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| ORDI/ZK | -39.41 |
| ORDI/REZ | -40.88 |
| ARB/COMP | -43.49 |
| CFX/KAITO | -48.72 |
| ETHFI/XLM | -51.26 |
| 2Z/DASH | -55.46 |
| APE/ZK | -61.57 |
| ADA/VVV | -61.87 |
| FARTCOIN/HYPE | -64.24 |
| HYPER/SAGA | -121.79 |

**q0.005_stop0p5_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 117.56 |
| MEGA | 28.59 |
| YZY | 27.78 |
| NOT | 21.04 |
| ZEREBRO | 17.98 |
| MEW | 15.56 |
| STABLE | 11.40 |
| ZETA | 11.04 |
| MANTA | 9.46 |
| RENDER | 6.96 |
**q0.005_stop0p5_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| SPX | -19.93 |
| VINE | -20.43 |
| kNEIRO | -20.45 |
| SAGA | -20.95 |
| XPL | -21.40 |
| SOPH | -21.80 |
| TAO | -22.11 |
| LTC | -22.47 |
| PURR | -23.58 |
| COMP | -26.33 |
**q0.005_stop0p5_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| HMSTR/MEGA | 11.10 |
| FOGO/STABLE | 8.72 |
| FOGO/MAVIA | 8.45 |
| HMSTR/MEW | 8.44 |
| NOT/OP | 8.22 |
| USUAL/ZEREBRO | 7.80 |
| GRASS/YZY | 7.15 |
| MAVIA/YZY | 6.86 |
| MEGA/SYRUP | 6.66 |
| FOGO/RENDER | 6.62 |
**q0.005_stop0p5_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| DOGE/kSHIB | -3.07 |
| FOGO/LAYER | -3.13 |
| FOGO/kNEIRO | -3.33 |
| BANANA/MEGA | -3.42 |
| FOGO/SAGA | -3.42 |
| kBONK/kSHIB | -3.43 |
| HYPE/NOT | -3.58 |
| HMSTR/LIT | -3.59 |
| FOGO/VINE | -4.16 |
| MEGA/MET | -4.50 |

**q0.005_stop0p5_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 372.26 |
| YZY | 166.72 |
| NOT | 73.43 |
| BOME | 72.36 |
| MEW | 63.45 |
| ZETA | 46.64 |
| MAVIA | 39.63 |
| MEGA | 35.51 |
| ZEREBRO | 31.04 |
| MANTA | 29.93 |
**q0.005_stop0p5_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| kPEPE | -20.95 |
| COMP | -21.26 |
| SAGA | -21.64 |
| DYM | -21.93 |
| kNEIRO | -22.13 |
| TST | -22.19 |
| TAO | -24.51 |
| SOPH | -27.80 |
| XPL | -28.40 |
| BABY | -29.41 |
**q0.005_stop0p5_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| GRASS/YZY | 18.93 |
| MAVIA/YZY | 17.73 |
| YZY/ZETA | 17.05 |
| BOME/HMSTR | 13.96 |
| LIT/YZY | 13.60 |
| HMSTR/MEW | 13.31 |
| HMSTR/MEGA | 12.79 |
| HMSTR/NEO | 11.38 |
| YZY/kSHIB | 11.26 |
| CRV/HMSTR | 10.80 |
**q0.005_stop0p5_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| MEGA/MET | -4.23 |
| DOGE/kSHIB | -4.27 |
| BANANA/MEGA | -4.49 |
| FOGO/LAYER | -5.14 |
| HYPE/NOT | -5.18 |
| UNI/WLD | -5.97 |
| WIF/XAI | -5.97 |
| TST/W | -6.30 |
| TST/USUAL | -6.54 |
| TST/ZK | -6.82 |

**q0.005_stop1p0_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 237.75 |
| YZY | 84.67 |
| NOT | 58.58 |
| BOME | 58.19 |
| FOGO | 37.67 |
| MEW | 36.02 |
| MAVIA | 35.27 |
| MEGA | 35.02 |
| ZEREBRO | 30.24 |
| ZETA | 27.86 |
**q0.005_stop1p0_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| BIO | -22.78 |
| PURR | -22.78 |
| COMP | -24.55 |
| BABY | -25.16 |
| CELO | -25.17 |
| LTC | -25.84 |
| AVNT | -26.80 |
| LINK | -27.51 |
| kNEIRO | -27.71 |
| SOPH | -27.86 |
**q0.005_stop1p0_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| FOGO/GRIFFAIN | 16.25 |
| HMSTR/MEGA | 14.60 |
| GRASS/YZY | 13.51 |
| FOGO/SAGA | 12.18 |
| MAVIA/YZY | 11.79 |
| HMSTR/TST | 11.28 |
| BOME/HMSTR | 11.24 |
| YZY/ZETA | 11.20 |
| FOGO/STABLE | 10.02 |
| USUAL/ZEREBRO | 9.17 |
**q0.005_stop1p0_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| MEGA/STBL | -4.58 |
| HYPE/LINK | -4.61 |
| MEGA/MET | -4.81 |
| FOGO/XPL | -5.01 |
| HMSTR/PYTH | -5.43 |
| DOOD/LIT | -5.52 |
| FOGO/VINE | -5.70 |
| EIGEN/FTT | -6.09 |
| HYPE/NOT | -6.99 |
| HMSTR/kNEIRO | -8.52 |

**q0.005_stop1p0_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 617.09 |
| YZY | 289.71 |
| BOME | 159.10 |
| NOT | 131.09 |
| MEW | 115.90 |
| MAVIA | 112.94 |
| ZETA | 81.06 |
| FTT | 68.85 |
| FOGO | 64.79 |
| LIT | 58.50 |
**q0.005_stop1p0_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| CFX | -21.53 |
| IMX | -22.63 |
| kNEIRO | -23.54 |
| COMP | -26.17 |
| BIO | -28.38 |
| kLUNC | -29.37 |
| TST | -33.03 |
| CELO | -35.09 |
| TON | -37.32 |
| BABY | -44.90 |
**q0.005_stop1p0_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| GRASS/YZY | 32.44 |
| MAVIA/YZY | 28.96 |
| YZY/ZETA | 27.48 |
| HMSTR/TST | 26.79 |
| BOME/HMSTR | 23.27 |
| LIT/YZY | 21.24 |
| HMSTR/NEO | 17.76 |
| MAVIA/SKR | 17.56 |
| HMSTR/PROVE | 17.38 |
| YZY/kSHIB | 17.16 |
**q0.005_stop1p0_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| TST/ZETA | -8.19 |
| BIO/HEMI | -8.21 |
| BSV/FTT | -8.32 |
| HMSTR/kNEIRO | -8.92 |
| AERO/MEGA | -9.94 |
| TST/W | -10.48 |
| UNI/WLD | -10.67 |
| TST/USUAL | -10.69 |
| HYPE/NOT | -11.09 |
| EIGEN/FTT | -12.14 |

**q0.005_stop2p0_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 378.46 |
| YZY | 161.60 |
| FOGO | 119.54 |
| BOME | 111.85 |
| MEW | 101.98 |
| NOT | 91.69 |
| MAVIA | 61.86 |
| TRB | 41.66 |
| kSHIB | 40.02 |
| PNUT | 37.41 |
**q0.005_stop2p0_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| HYPE | -28.42 |
| ZRO | -28.59 |
| TRUMP | -32.39 |
| kNEIRO | -34.20 |
| CFX | -35.86 |
| TAO | -37.37 |
| BABY | -37.63 |
| RESOLV | -38.42 |
| TON | -38.99 |
| APEX | -39.56 |
**q0.005_stop2p0_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| GRASS/YZY | 23.31 |
| FOGO/GRIFFAIN | 19.54 |
| YZY/ZETA | 18.42 |
| HMSTR/TST | 17.48 |
| MAVIA/YZY | 17.36 |
| YZY/kSHIB | 14.70 |
| HMSTR/NEO | 14.01 |
| BOME/HMSTR | 13.86 |
| FOGO/SAGA | 13.52 |
| FOGO/RENDER | 12.08 |
**q0.005_stop2p0_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| TST/VINE | -7.45 |
| LIT/ZEN | -7.69 |
| APEX/HMSTR | -7.73 |
| GMX/RESOLV | -8.15 |
| HMSTR/kNEIRO | -9.01 |
| AERO/MEGA | -9.14 |
| EIGEN/FTT | -9.28 |
| EIGEN/ENS | -10.37 |
| CFX/DASH | -10.80 |
| REZ/ZEREBRO | -10.82 |

**q0.005_stop2p0_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 789.42 |
| YZY | 401.99 |
| MEW | 216.98 |
| BOME | 212.65 |
| NOT | 176.71 |
| FOGO | 173.74 |
| MAVIA | 168.39 |
| TNSR | 122.97 |
| kSHIB | 110.69 |
| FTT | 104.60 |
**q0.005_stop2p0_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| SAGA | -39.34 |
| ZRO | -40.12 |
| MEGA | -40.43 |
| PUMP | -45.48 |
| EIGEN | -47.14 |
| kNEIRO | -47.39 |
| TON | -48.85 |
| RESOLV | -52.17 |
| BABY | -57.72 |
| CFX | -65.72 |
**q0.005_stop2p0_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| GRASS/YZY | 45.37 |
| YZY/ZETA | 36.30 |
| MAVIA/YZY | 34.84 |
| HMSTR/TST | 33.77 |
| HMSTR/NEO | 29.98 |
| UNI/WLD | 29.93 |
| YZY/kSHIB | 29.54 |
| BOME/HMSTR | 28.71 |
| HYPE/ONDO | 25.55 |
| FOGO/GRIFFAIN | 23.49 |
**q0.005_stop2p0_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| TST/W | -14.06 |
| MEGA/ONDO | -14.13 |
| LAYER/kLUNC | -15.02 |
| BIO/RESOLV | -15.23 |
| EIGEN/FTT | -15.31 |
| LIT/ZEN | -17.50 |
| GMX/RESOLV | -18.66 |
| CFX/DASH | -20.65 |
| REZ/ZEREBRO | -21.30 |
| EIGEN/ENS | -24.45 |

**q0.005_stopnone_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 409.16 |
| YZY | 238.96 |
| BOME | 142.07 |
| FTT | 120.67 |
| NOT | 111.92 |
| MEW | 86.78 |
| FOGO | 79.72 |
| MAVIA | 76.08 |
| MEGA | 73.37 |
| LIT | 68.71 |
**q0.005_stopnone_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| TON | -40.47 |
| CFX | -45.84 |
| TAO | -48.67 |
| JUP | -48.68 |
| COMP | -50.34 |
| kLUNC | -52.48 |
| HYPE | -62.25 |
| ZK | -64.15 |
| TRX | -64.30 |
| DOGE | -68.67 |
**q0.005_stopnone_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| MAVIA/YZY | 25.27 |
| YZY/ZETA | 21.39 |
| YZY/kSHIB | 17.01 |
| HMSTR/NEO | 14.26 |
| YZY/ZRO | 14.17 |
| NOT/ORDI | 12.93 |
| CFX/SEI | 12.73 |
| BOME/HMSTR | 12.70 |
| ACE/HMSTR | 12.52 |
| LDO/LIT | 12.22 |
**q0.005_stopnone_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| TAO/kBONK | -20.57 |
| COMP/INJ | -23.96 |
| ARB/COMP | -25.61 |
| BLUR/PROVE | -26.17 |
| ORDI/REZ | -26.22 |
| FARTCOIN/HYPE | -29.56 |
| HMSTR/SUPER | -29.94 |
| PUMP/TRX | -34.39 |
| APE/ZK | -38.70 |
| CFX/KAITO | -45.96 |

**q0.005_stopnone_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 639.96 |
| YZY | 458.14 |
| BOME | 269.40 |
| NOT | 231.22 |
| FTT | 219.53 |
| TNSR | 185.39 |
| MAVIA | 171.63 |
| MEW | 162.69 |
| FOGO | 133.36 |
| kSHIB | 122.34 |
**q0.005_stopnone_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| XLM | -44.51 |
| PUMP | -45.00 |
| APE | -47.43 |
| BSV | -55.58 |
| ZK | -64.58 |
| DOGE | -71.69 |
| TRX | -81.89 |
| HYPE | -85.23 |
| HYPER | -134.10 |
| SAGA | -150.70 |
**q0.005_stopnone_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| MAVIA/YZY | 41.09 |
| YZY/ZRO | 36.59 |
| YZY/kSHIB | 28.35 |
| NOT/ORDI | 27.75 |
| CFX/SEI | 27.69 |
| HMSTR/NEO | 26.71 |
| JTO/POL | 23.48 |
| ACE/HMSTR | 23.25 |
| PEOPLE/POLYX | 21.84 |
| APT/HMSTR | 21.26 |
**q0.005_stopnone_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| MON/PENGU | -38.82 |
| COMP/INJ | -39.15 |
| ORDI/REZ | -39.37 |
| ARB/COMP | -40.69 |
| HMSTR/SUPER | -42.97 |
| CFX/KAITO | -43.63 |
| PUMP/TRX | -53.98 |
| FARTCOIN/HYPE | -60.56 |
| APE/ZK | -60.81 |
| HYPER/SAGA | -116.37 |

**q0.001_stop0p5_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 88.30 |
| YZY | 41.83 |
| FOGO | 31.65 |
| NOT | 16.38 |
| MEW | 12.68 |
| MEGA | 11.96 |
| STABLE | 11.56 |
| BOME | 10.63 |
| JTO | 9.49 |
| MAVIA | 7.36 |
**q0.001_stop0p5_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| ZORA | -9.92 |
| PUMP | -9.96 |
| SPX | -10.58 |
| BRETT | -11.29 |
| ZEC | -11.47 |
| MORPHO | -12.55 |
| HYPE | -13.41 |
| VINE | -13.65 |
| FTT | -14.28 |
| TST | -20.97 |
**q0.001_stop0p5_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| FOGO/MAVIA | 11.77 |
| MAVIA/YZY | 11.41 |
| FOGO/STABLE | 10.77 |
| HMSTR/MEW | 10.47 |
| HMSTR/MEGA | 8.46 |
| BOME/HMSTR | 6.71 |
| CAKE/FOGO | 6.54 |
| FOGO/TON | 6.38 |
| HMSTR/MANTA | 6.19 |
| HMSTR/JTO | 5.86 |
**q0.001_stop0p5_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| ACE/HMSTR | -2.26 |
| ALGO/MORPHO | -2.28 |
| POL/ZRO | -2.35 |
| INIT/TAO | -2.36 |
| HYPE/NOT | -2.70 |
| HMSTR/MAVIA | -2.76 |
| FOGO/LAYER | -3.18 |
| SPX/STX | -3.37 |
| TST/W | -4.27 |
| TST/USUAL | -4.64 |

**q0.001_stop0p5_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 142.74 |
| YZY | 80.04 |
| FOGO | 40.21 |
| NOT | 31.89 |
| BOME | 27.20 |
| MEGA | 22.36 |
| MEW | 21.45 |
| MAVIA | 15.50 |
| JTO | 13.96 |
| STABLE | 13.88 |
**q0.001_stop0p5_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| SAGA | -7.82 |
| SOPH | -7.94 |
| MORPHO | -8.22 |
| ZEC | -8.54 |
| ZORA | -8.65 |
| BRETT | -8.66 |
| VINE | -9.44 |
| SPX | -9.59 |
| HYPE | -12.11 |
| TST | -22.20 |
**q0.001_stop0p5_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| MAVIA/YZY | 15.34 |
| FOGO/MAVIA | 12.80 |
| HMSTR/MEW | 12.08 |
| FOGO/STABLE | 11.48 |
| HMSTR/MEGA | 9.30 |
| BOME/HMSTR | 8.76 |
| HMSTR/MANTA | 8.32 |
| HMSTR/JTO | 7.61 |
| CAKE/FOGO | 7.42 |
| HMSTR/PROVE | 7.40 |
**q0.001_stop0p5_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| ACE/HMSTR | -2.23 |
| POL/ZRO | -2.35 |
| TST/XMR | -2.41 |
| INIT/TAO | -2.85 |
| HMSTR/MAVIA | -2.90 |
| FOGO/LAYER | -2.91 |
| HYPE/NOT | -2.92 |
| SPX/STX | -3.46 |
| TST/W | -5.47 |
| TST/USUAL | -5.77 |

**q0.001_stop1p0_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 168.28 |
| YZY | 70.82 |
| FOGO | 42.12 |
| NOT | 29.40 |
| MEW | 25.42 |
| ASTER | 16.57 |
| JTO | 15.55 |
| STABLE | 13.34 |
| MANTA | 12.63 |
| BOME | 12.61 |
**q0.001_stop1p0_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| EIGEN | -11.94 |
| SAGA | -12.16 |
| SOPH | -12.40 |
| VINE | -12.64 |
| WLFI | -12.77 |
| ZEC | -13.16 |
| ACE | -13.33 |
| CHILLGUY | -13.35 |
| JUP | -13.97 |
| TST | -15.71 |
**q0.001_stop1p0_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| HMSTR/TST | 16.76 |
| MAVIA/YZY | 12.31 |
| HMSTR/MEGA | 12.28 |
| FOGO/STABLE | 11.00 |
| FOGO/MAVIA | 10.21 |
| HMSTR/MEW | 10.04 |
| BOME/HMSTR | 7.73 |
| HMSTR/JTO | 6.76 |
| FOGO/TON | 6.51 |
| CAKE/FOGO | 6.37 |
**q0.001_stop1p0_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| CC/FXS | -3.26 |
| FOGO/MON | -3.28 |
| FOGO/LAYER | -3.49 |
| VIRTUAL/ZEC | -3.61 |
| HMSTR/TON | -3.71 |
| FARTCOIN/HYPE | -3.96 |
| POL/ZRO | -3.97 |
| SPX/STX | -4.44 |
| TST/W | -4.99 |
| TST/USUAL | -5.35 |

**q0.001_stop1p0_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 249.00 |
| YZY | 117.71 |
| FOGO | 56.88 |
| NOT | 49.31 |
| MEW | 38.21 |
| BOME | 32.88 |
| ASTER | 22.40 |
| MEGA | 21.97 |
| JTO | 21.24 |
| WIF | 19.03 |
**q0.001_stop1p0_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| JUP | -9.75 |
| ZEC | -10.25 |
| SKY | -10.33 |
| SOPH | -10.99 |
| SAGA | -11.28 |
| INIT | -11.35 |
| EIGEN | -11.46 |
| WLFI | -11.83 |
| ACE | -12.31 |
| TST | -16.01 |
**q0.001_stop1p0_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| HMSTR/TST | 21.31 |
| MAVIA/YZY | 16.92 |
| HMSTR/MEGA | 13.19 |
| FOGO/STABLE | 11.76 |
| HMSTR/MEW | 11.64 |
| FOGO/MAVIA | 11.19 |
| BOME/HMSTR | 10.23 |
| HMSTR/JTO | 8.90 |
| HMSTR/PROVE | 8.25 |
| DOGE/HMSTR | 7.94 |
**q0.001_stop1p0_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| VIRTUAL/ZEC | -3.54 |
| ONDO/STRK | -3.55 |
| ETHFI/XLM | -3.65 |
| IOTA/W | -3.67 |
| INIT/TAO | -3.99 |
| HMSTR/TON | -4.11 |
| POL/ZRO | -4.22 |
| SPX/STX | -4.74 |
| TST/W | -6.49 |
| TST/USUAL | -6.77 |

**q0.001_stop2p0_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 222.94 |
| YZY | 76.33 |
| FOGO | 54.70 |
| MEW | 41.77 |
| NOT | 34.45 |
| BOME | 30.89 |
| ASTER | 25.74 |
| MEGA | 22.90 |
| ALGO | 21.61 |
| STABLE | 20.48 |
**q0.001_stop2p0_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| POL | -14.94 |
| SUPER | -15.08 |
| ACE | -15.16 |
| CFX | -15.23 |
| BRETT | -16.07 |
| ETHFI | -16.46 |
| XLM | -16.75 |
| VINE | -16.87 |
| ZEC | -17.30 |
| TST | -28.37 |
**q0.001_stop2p0_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| HMSTR/TST | 19.04 |
| MAVIA/YZY | 14.61 |
| HMSTR/MEGA | 12.43 |
| FOGO/STABLE | 10.97 |
| HMSTR/MEW | 10.23 |
| BOME/HMSTR | 8.71 |
| ARK/HMSTR | 8.58 |
| HMSTR/ZEN | 8.22 |
| HMSTR/SUSHI | 7.77 |
| FOGO/MAVIA | 7.73 |
**q0.001_stop2p0_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| MEGA/VINE | -5.26 |
| VIRTUAL/ZEC | -5.30 |
| TST/VINE | -5.38 |
| TST/W | -5.86 |
| JUP/TST | -6.01 |
| TST/XPL | -6.16 |
| MELANIA/TST | -6.20 |
| ETHFI/XLM | -6.45 |
| POL/ZRO | -6.91 |
| SPX/STX | -8.11 |

**q0.001_stop2p0_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 309.74 |
| YZY | 135.72 |
| FOGO | 66.31 |
| NOT | 58.68 |
| MEW | 57.55 |
| BOME | 47.03 |
| MEGA | 39.83 |
| ASTER | 32.72 |
| ALGO | 30.02 |
| WIF | 29.37 |
**q0.001_stop2p0_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| ACE | -13.50 |
| HYPE | -14.17 |
| ZEC | -14.31 |
| EIGEN | -14.54 |
| W | -14.88 |
| CFX | -15.55 |
| ETHFI | -15.85 |
| BRETT | -16.94 |
| XLM | -18.68 |
| TST | -29.00 |
**q0.001_stop2p0_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| HMSTR/TST | 23.53 |
| MAVIA/YZY | 19.23 |
| HMSTR/MEGA | 13.27 |
| HMSTR/MEW | 11.71 |
| FOGO/STABLE | 11.55 |
| ARK/HMSTR | 11.20 |
| BOME/HMSTR | 11.19 |
| HMSTR/NEO | 10.21 |
| DOGE/HMSTR | 10.01 |
| HMSTR/JTO | 9.79 |
**q0.001_stop2p0_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| BCH/FARTCOIN | -6.36 |
| YZY/ZEN | -6.40 |
| FARTCOIN/HYPE | -6.75 |
| JUP/TST | -7.09 |
| TST/XPL | -7.28 |
| MELANIA/TST | -7.32 |
| TST/W | -7.41 |
| POL/ZRO | -7.44 |
| ETHFI/XLM | -8.20 |
| SPX/STX | -8.78 |

**q0.001_stopnone_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 290.74 |
| YZY | 148.46 |
| FOGO | 83.49 |
| MEGA | 63.17 |
| MAVIA | 59.91 |
| BOME | 50.29 |
| NOT | 45.08 |
| TST | 43.56 |
| STABLE | 31.59 |
| MEW | 30.06 |
**q0.001_stopnone_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| DOOD | -28.82 |
| VINE | -29.49 |
| ORDI | -29.89 |
| LTC | -30.33 |
| GRASS | -32.96 |
| FARTCOIN | -33.24 |
| INIT | -35.12 |
| ZK | -35.86 |
| XLM | -42.87 |
| HYPE | -59.44 |
**q0.001_stopnone_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| FOGO/MAVIA | 23.19 |
| HMSTR/TST | 22.27 |
| MAVIA/YZY | 17.24 |
| MELANIA/TST | 14.01 |
| JUP/TST | 12.30 |
| FOGO/STABLE | 11.60 |
| HMSTR/MEGA | 11.23 |
| HMSTR/NEO | 10.30 |
| BOME/HMSTR | 10.00 |
| HMSTR/JTO | 9.20 |
**q0.001_stopnone_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| BOME/INIT | -17.45 |
| TAO/kPEPE | -18.19 |
| DOOD/INIT | -18.45 |
| CFX/KAITO | -19.62 |
| TRB/XLM | -19.70 |
| GRASS/PEOPLE | -19.75 |
| FOGO/TST | -22.65 |
| MORPHO/S | -23.33 |
| FARTCOIN/HYPE | -29.33 |
| ORDI/ZK | -30.44 |

**q0.001_stopnone_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 373.31 |
| YZY | 218.16 |
| FOGO | 94.28 |
| MAVIA | 74.91 |
| NOT | 72.60 |
| BOME | 68.81 |
| MEGA | 67.30 |
| TST | 63.48 |
| STABLE | 39.67 |
| ARK | 39.26 |
**q0.001_stopnone_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| PEOPLE | -29.14 |
| CFX | -30.05 |
| FARTCOIN | -30.39 |
| S | -31.68 |
| LTC | -33.91 |
| GRASS | -36.30 |
| INIT | -41.59 |
| HYPE | -45.29 |
| ZK | -46.19 |
| XLM | -52.42 |
**q0.001_stopnone_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| HMSTR/TST | 27.63 |
| FOGO/MAVIA | 24.24 |
| MAVIA/YZY | 22.79 |
| MELANIA/TST | 17.09 |
| JUP/TST | 15.02 |
| HMSTR/MANTA | 13.51 |
| HMSTR/NEO | 13.45 |
| BOME/HMSTR | 12.81 |
| FOGO/STABLE | 12.07 |
| HMSTR/JTO | 11.75 |
**q0.001_stopnone_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| TAO/kPEPE | -21.23 |
| BOME/INIT | -21.91 |
| DOOD/INIT | -23.00 |
| FOGO/TST | -23.35 |
| GRASS/PEOPLE | -24.00 |
| CFX/KAITO | -24.88 |
| TRB/XLM | -25.59 |
| MORPHO/S | -29.33 |
| FARTCOIN/HYPE | -29.63 |
| ORDI/ZK | -39.54 |

### Drawdown and distance to liquidation, per run
| q | stop | fee | max_dd_usd | max_dd_pct | dd_start | dd_bottom | dd_recovery | longest_underwater_days | min_dist_ratio | median_dist_ratio | date_of_min |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.01 | 0p5 | taker | -844.37 | -0.8444 | 2025-12-20 | 2026-07-11 | None | 203 | 4.0441 | 4.7083 | 2026-01-19 |
| 0.01 | 0p5 | maker | -240.21 | -0.1664 | 2026-05-07 | 2026-07-12 | None | 66 | 3.9968 | 4.4779 | 2026-04-23 |
| 0.01 | 1p0 | taker | -648.10 | -0.6481 | 2025-12-20 | 2026-07-12 | None | 204 | 3.9846 | 4.4371 | 2026-05-08 |
| 0.01 | 1p0 | maker | -230.48 | -0.0870 | 2026-06-29 | 2026-07-12 | None | 48 | 3.9846 | 4.4443 | 2025-12-23 |
| 0.01 | 2p0 | taker | -468.76 | -0.3352 | 2026-05-04 | 2026-07-12 | None | 69 | 3.9779 | 4.3502 | 2025-12-24 |
| 0.01 | 2p0 | maker | -258.77 | -0.0669 | 2026-06-30 | 2026-07-08 | None | 14 | 3.9768 | 4.3569 | 2025-12-24 |
| 0.01 | none | taker | -182.50 | -0.1293 | 2026-05-04 | 2026-05-09 | 2026-05-24 | 29 | 3.5797 | 4.3645 | 2026-04-18 |
| 0.01 | none | maker | -234.56 | -0.0982 | 2026-07-03 | 2026-07-12 | None | 15 | 3.5811 | 4.3493 | 2026-04-18 |
| 0.005 | 0p5 | taker | -646.63 | -0.6466 | 2025-12-20 | 2026-07-12 | None | 204 | 4.0742 | 5.8789 | 2026-04-29 |
| 0.005 | 0p5 | maker | -139.28 | -0.0955 | 2026-05-04 | 2026-07-12 | None | 69 | 4.0130 | 5.7659 | 2026-02-22 |
| 0.005 | 1p0 | taker | -298.82 | -0.2988 | 2025-12-20 | 2026-07-12 | None | 204 | 3.9838 | 4.9729 | 2026-05-08 |
| 0.005 | 1p0 | maker | -151.25 | -0.0630 | 2026-05-04 | 2026-06-03 | 2026-06-21 | 47 | 3.9860 | 5.0574 | 2026-04-22 |
| 0.005 | 2p0 | taker | -370.32 | -0.2284 | 2026-05-04 | 2026-07-12 | None | 69 | 3.9964 | 4.6065 | 2026-01-11 |
| 0.005 | 2p0 | maker | -154.97 | -0.0488 | 2026-05-04 | 2026-05-17 | 2026-06-09 | 35 | 4.0099 | 4.6494 | 2026-02-22 |
| 0.005 | none | taker | -167.22 | -0.1254 | 2026-05-04 | 2026-05-09 | 2026-06-05 | 31 | 3.6611 | 4.4155 | 2026-04-18 |
| 0.005 | none | maker | -230.44 | -0.1093 | 2026-05-04 | 2026-05-09 | 2026-05-13 | 13 | 3.6627 | 4.4142 | 2026-04-18 |
| 0.001 | 0p5 | taker | -141.99 | -0.1420 | 2025-12-20 | 2026-07-11 | None | 203 | 3.9933 | 16.8097 | 2026-04-22 |
| 0.001 | 0p5 | maker | -41.45 | -0.0340 | 2026-05-08 | 2026-05-18 | None | 69 | 3.9952 | 16.8111 | 2026-04-22 |
| 0.001 | 1p0 | taker | -93.89 | -0.0851 | 2026-05-04 | 2026-07-11 | None | 77 | 3.9942 | 14.1196 | 2026-04-22 |
| 0.001 | 1p0 | maker | -40.54 | -0.0280 | 2026-05-08 | 2026-05-18 | 2026-06-23 | 45 | 3.9969 | 14.1218 | 2026-04-22 |
| 0.001 | 2p0 | taker | -92.39 | -0.0715 | 2026-05-04 | 2026-07-11 | None | 68 | 3.9800 | 11.9673 | 2026-02-18 |
| 0.001 | 2p0 | maker | -77.09 | -0.0449 | 2026-06-28 | 2026-07-11 | None | 26 | 3.9810 | 11.9704 | 2026-02-18 |
| 0.001 | none | taker | -110.46 | -0.0720 | 2026-06-28 | 2026-07-11 | None | 58 | 3.9643 | 9.1351 | 2026-02-18 |
| 0.001 | none | maker | -127.69 | -0.0597 | 2026-06-28 | 2026-07-11 | None | 31 | 3.9722 | 9.1383 | 2026-02-18 |

### Monthly (fold) total P&L, per run
All 7 test blocks start/end exactly at 00:00:00 UTC (not mid-day). "outside" is the exit spill after fold 7's nominal end; sum(fold totals) + outside reconciles to final_equity - start to 1e-6 (asserted in the generator).

**q0.01_stop0p5_feetaker** (n_months_positive=0/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | -356.33 | -0.3563 |
| 2 | 30 | -207.34 | -0.3221 |
| 3 | 30 | -48.15 | -0.1104 |
| 4 | 30 | -86.47 | -0.2228 |
| 5 | 30 | -59.85 | -0.1984 |
| 6 | 30 | -48.98 | -0.2025 |
| 7 | 23 | -37.25 | -0.1931 |
| outside | 0 | 0.00 | n/a |

**q0.01_stop0p5_feemaker** (n_months_positive=5/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 18.62 | 0.0186 |
| 2 | 30 | 55.19 | 0.0542 |
| 3 | 30 | 13.66 | 0.0127 |
| 4 | 30 | 9.07 | 0.0083 |
| 5 | 30 | 308.70 | 0.2815 |
| 6 | 30 | -92.94 | -0.0661 |
| 7 | 23 | -108.04 | -0.0823 |
| outside | 1 | -1.23 | n/a |

**q0.01_stop1p0_feetaker** (n_months_positive=0/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | -114.28 | -0.1143 |
| 2 | 30 | -151.69 | -0.1713 |
| 3 | 30 | -35.43 | -0.0483 |
| 4 | 30 | -129.23 | -0.1850 |
| 5 | 30 | -22.46 | -0.0394 |
| 6 | 30 | -96.47 | -0.1764 |
| 7 | 23 | -97.52 | -0.2165 |
| outside | 1 | -1.02 | n/a |

**q0.01_stop1p0_feemaker** (n_months_positive=5/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 279.49 | 0.2795 |
| 2 | 30 | 262.78 | 0.2054 |
| 3 | 30 | 112.92 | 0.0732 |
| 4 | 30 | 134.80 | 0.0814 |
| 5 | 30 | 675.01 | 0.3771 |
| 6 | 30 | -14.92 | -0.0061 |
| 7 | 23 | -27.59 | -0.0113 |
| outside | 1 | -5.14 | n/a |

**q0.01_stop2p0_feetaker** (n_months_positive=4/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 17.87 | 0.0179 |
| 2 | 30 | 51.48 | 0.0506 |
| 3 | 30 | 1.93 | 0.0018 |
| 4 | 30 | -57.15 | -0.0533 |
| 5 | 30 | 257.38 | 0.2538 |
| 6 | 30 | -152.54 | -0.1200 |
| 7 | 23 | -185.18 | -0.1655 |
| outside | 1 | -4.20 | n/a |

**q0.01_stop2p0_feemaker** (n_months_positive=6/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 301.39 | 0.3014 |
| 2 | 30 | 398.43 | 0.3062 |
| 3 | 30 | 191.32 | 0.1126 |
| 4 | 30 | 346.47 | 0.1832 |
| 5 | 30 | 1398.39 | 0.6249 |
| 6 | 30 | 129.18 | 0.0355 |
| 7 | 23 | -136.35 | -0.0362 |
| outside | 1 | -15.67 | n/a |

**q0.01_stopnone_feetaker** (n_months_positive=7/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 78.32 | 0.0783 |
| 2 | 30 | 229.80 | 0.2131 |
| 3 | 30 | 40.97 | 0.0313 |
| 4 | 30 | 180.18 | 0.1336 |
| 5 | 30 | 329.15 | 0.2152 |
| 6 | 30 | 205.90 | 0.1108 |
| 7 | 23 | 144.58 | 0.0700 |
| outside | 1 | -2.90 | n/a |

**q0.01_stopnone_feemaker** (n_months_positive=7/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 199.85 | 0.1999 |
| 2 | 30 | 476.48 | 0.3971 |
| 3 | 30 | 189.09 | 0.1128 |
| 4 | 30 | 514.44 | 0.2758 |
| 5 | 30 | 1106.35 | 0.4649 |
| 6 | 30 | 780.84 | 0.2240 |
| 7 | 23 | 786.25 | 0.1843 |
| outside | 1 | -18.94 | n/a |

**q0.005_stop0p5_feetaker** (n_months_positive=0/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | -248.32 | -0.2483 |
| 2 | 30 | -147.58 | -0.1963 |
| 3 | 30 | -31.87 | -0.0527 |
| 4 | 30 | -83.52 | -0.1459 |
| 5 | 30 | -34.19 | -0.0700 |
| 6 | 30 | -45.66 | -0.1005 |
| 7 | 23 | -55.36 | -0.1354 |
| outside | 1 | -0.14 | n/a |

**q0.005_stop0p5_feemaker** (n_months_positive=4/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 28.70 | 0.0287 |
| 2 | 30 | 39.97 | 0.0389 |
| 3 | 30 | 6.17 | 0.0058 |
| 4 | 30 | -7.80 | -0.0073 |
| 5 | 30 | 298.08 | 0.2794 |
| 6 | 30 | -13.53 | -0.0099 |
| 7 | 23 | -18.14 | -0.0134 |
| outside | 1 | -0.48 | n/a |

**q0.005_stop1p0_feetaker** (n_months_positive=1/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | -95.71 | -0.0957 |
| 2 | 30 | -52.12 | -0.0576 |
| 3 | 30 | -13.86 | -0.0163 |
| 4 | 30 | -54.27 | -0.0647 |
| 5 | 30 | 54.73 | 0.0698 |
| 6 | 30 | -71.98 | -0.0858 |
| 7 | 23 | -64.72 | -0.0844 |
| outside | 1 | -0.88 | n/a |

**q0.005_stop1p0_feemaker** (n_months_positive=7/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 198.31 | 0.1983 |
| 2 | 30 | 274.78 | 0.2293 |
| 3 | 30 | 56.34 | 0.0382 |
| 4 | 30 | 121.74 | 0.0796 |
| 5 | 30 | 629.62 | 0.3813 |
| 6 | 30 | 22.72 | 0.0100 |
| 7 | 23 | 73.67 | 0.0320 |
| outside | 1 | -2.77 | n/a |

**q0.005_stop2p0_feetaker** (n_months_positive=4/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 79.83 | 0.0798 |
| 2 | 30 | 109.18 | 0.1011 |
| 3 | 30 | 12.30 | 0.0103 |
| 4 | 30 | -20.07 | -0.0167 |
| 5 | 30 | 263.01 | 0.2227 |
| 6 | 30 | -84.67 | -0.0586 |
| 7 | 23 | -105.26 | -0.0774 |
| outside | 1 | -3.58 | n/a |

**q0.005_stop2p0_feemaker** (n_months_positive=7/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 278.83 | 0.2788 |
| 2 | 30 | 444.56 | 0.3476 |
| 3 | 30 | 111.24 | 0.0645 |
| 4 | 30 | 222.50 | 0.1213 |
| 5 | 30 | 1044.32 | 0.5077 |
| 6 | 30 | 112.92 | 0.0364 |
| 7 | 23 | 109.69 | 0.0341 |
| outside | 1 | -9.04 | n/a |

**q0.005_stopnone_feetaker** (n_months_positive=7/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 71.67 | 0.0717 |
| 2 | 30 | 231.26 | 0.2158 |
| 3 | 30 | 13.36 | 0.0103 |
| 4 | 30 | 149.09 | 0.1133 |
| 5 | 30 | 314.78 | 0.2148 |
| 6 | 30 | 153.61 | 0.0863 |
| 7 | 23 | 32.40 | 0.0168 |
| outside | 1 | -5.98 | n/a |

**q0.005_stopnone_feemaker** (n_months_positive=7/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 219.26 | 0.2193 |
| 2 | 30 | 482.39 | 0.3956 |
| 3 | 30 | 106.09 | 0.0623 |
| 4 | 30 | 452.32 | 0.2502 |
| 5 | 30 | 863.42 | 0.3820 |
| 6 | 30 | 569.06 | 0.1822 |
| 7 | 23 | 444.24 | 0.1203 |
| outside | 1 | 1.23 | n/a |

**q0.001_stop0p5_feetaker** (n_months_positive=1/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | -28.55 | -0.0286 |
| 2 | 30 | -53.46 | -0.0550 |
| 3 | 30 | -5.83 | -0.0063 |
| 4 | 30 | -37.81 | -0.0414 |
| 5 | 30 | 20.92 | 0.0239 |
| 6 | 30 | -4.71 | -0.0053 |
| 7 | 23 | -32.56 | -0.0366 |
| outside | 0 | 0.00 | n/a |

**q0.001_stop0p5_feemaker** (n_months_positive=5/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 69.22 | 0.0692 |
| 2 | 30 | 8.47 | 0.0079 |
| 3 | 30 | 7.21 | 0.0067 |
| 4 | 30 | -15.20 | -0.0140 |
| 5 | 30 | 114.06 | 0.1066 |
| 6 | 30 | 8.82 | 0.0074 |
| 7 | 23 | -2.64 | -0.0022 |
| outside | 0 | 0.00 | n/a |

**q0.001_stop1p0_feetaker** (n_months_positive=2/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | -6.60 | -0.0066 |
| 2 | 30 | -20.53 | -0.0207 |
| 3 | 30 | 4.29 | 0.0044 |
| 4 | 30 | -6.85 | -0.0070 |
| 5 | 30 | 82.17 | 0.0847 |
| 6 | 30 | -6.03 | -0.0057 |
| 7 | 23 | -37.40 | -0.0357 |
| outside | 0 | 0.00 | n/a |

**q0.001_stop1p0_feemaker** (n_months_positive=6/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 101.88 | 0.1019 |
| 2 | 30 | 57.06 | 0.0518 |
| 3 | 30 | 20.93 | 0.0181 |
| 4 | 30 | 24.51 | 0.0208 |
| 5 | 30 | 207.18 | 0.1720 |
| 6 | 30 | 9.85 | 0.0070 |
| 7 | 23 | -3.71 | -0.0026 |
| outside | 0 | 0.00 | n/a |

**q0.001_stop2p0_feetaker** (n_months_positive=5/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 30.24 | 0.0302 |
| 2 | 30 | 39.95 | 0.0388 |
| 3 | 30 | 10.37 | 0.0097 |
| 4 | 30 | -8.00 | -0.0074 |
| 5 | 30 | 174.93 | 0.1631 |
| 6 | 30 | 14.51 | 0.0116 |
| 7 | 23 | -62.53 | -0.0495 |
| outside | 0 | 0.00 | n/a |

**q0.001_stop2p0_feemaker** (n_months_positive=6/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 124.86 | 0.1249 |
| 2 | 30 | 114.42 | 0.1017 |
| 3 | 30 | 26.78 | 0.0216 |
| 4 | 30 | 26.22 | 0.0207 |
| 5 | 30 | 333.87 | 0.2584 |
| 6 | 30 | 39.61 | 0.0244 |
| 7 | 23 | -26.91 | -0.0162 |
| outside | 0 | 0.00 | n/a |

**q0.001_stopnone_feetaker** (n_months_positive=6/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 134.81 | 0.1348 |
| 2 | 30 | 77.16 | 0.0680 |
| 3 | 30 | 3.65 | 0.0030 |
| 4 | 30 | 126.34 | 0.1039 |
| 5 | 30 | 175.11 | 0.1305 |
| 6 | 30 | 50.58 | 0.0333 |
| 7 | 23 | -57.41 | -0.0366 |
| outside | 1 | 1.66 | n/a |

**q0.001_stopnone_feemaker** (n_months_positive=6/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 247.85 | 0.2478 |
| 2 | 30 | 168.75 | 0.1352 |
| 3 | 30 | 21.58 | 0.0152 |
| 4 | 30 | 188.27 | 0.1309 |
| 5 | 30 | 325.78 | 0.2003 |
| 6 | 30 | 90.56 | 0.0464 |
| 7 | 23 | -32.94 | -0.0161 |
| outside | 1 | 2.39 | n/a |

### EV check (stop=none only; fold 1 not scored, no earlier test month to fit on)
EV quintiles rank realised net monotonically (quintile 0 to 4 non-decreasing) in 0/6 tables (e.g. q0.01_feetaker: quintile 1 mean_realised_net=0.3055 is above quintile 2's 0.0689). EV here is descriptive only -- it does not rank realised net in these tables, and no claim that it predicts profit should be drawn from this table.

**q0.01_feetaker** (n_scored=6790):
| quintile | n | mean_ev | mean_realised_net |
|---|---|---|---|
| 0 | 1511 | -0.1074 | 0.1773 |
| 1 | 1231 | -0.0240 | 0.3055 |
| 2 | 1558 | 0.0821 | 0.0689 |
| 3 | 1375 | 0.1452 | 0.1016 |
| 4 | 1115 | 0.3383 | 0.2211 |

**q0.01_feemaker** (n_scored=6797):
| quintile | n | mean_ev | mean_realised_net |
|---|---|---|---|
| 0 | 1422 | 0.0141 | 0.6115 |
| 1 | 1303 | 0.1227 | 0.8662 |
| 2 | 1466 | 0.2345 | 0.3563 |
| 3 | 1308 | 0.3080 | 0.5505 |
| 4 | 1298 | 0.5207 | 0.4662 |

**q0.005_feetaker** (n_scored=5420):
| quintile | n | mean_ev | mean_realised_net |
|---|---|---|---|
| 0 | 1152 | -0.0613 | 0.2425 |
| 1 | 1077 | 0.0301 | 0.1386 |
| 2 | 1052 | 0.0839 | -0.0013 |
| 3 | 1122 | 0.1513 | 0.1744 |
| 4 | 1017 | 0.3386 | 0.2665 |

**q0.005_feemaker** (n_scored=5439):
| quintile | n | mean_ev | mean_realised_net |
|---|---|---|---|
| 0 | 1144 | 0.1009 | 0.6043 |
| 1 | 1117 | 0.2115 | 0.5158 |
| 2 | 1303 | 0.2701 | 0.4779 |
| 3 | 870 | 0.3344 | 0.4848 |
| 4 | 1005 | 0.5481 | 0.6097 |

**q0.001_feetaker** (n_scored=1917):
| quintile | n | mean_ev | mean_realised_net |
|---|---|---|---|
| 0 | 404 | 0.1075 | -0.1615 |
| 1 | 398 | 0.1563 | 0.2495 |
| 2 | 376 | 0.2296 | 0.4893 |
| 3 | 653 | 0.3947 | 0.2140 |
| 4 | 86 | 0.6538 | 0.2455 |

**q0.001_feemaker** (n_scored=1920):
| quintile | n | mean_ev | mean_realised_net |
|---|---|---|---|
| 0 | 409 | 0.2747 | -0.0634 |
| 1 | 396 | 0.3302 | 0.4774 |
| 2 | 378 | 0.4057 | 0.7742 |
| 3 | 652 | 0.5522 | 0.4111 |
| 4 | 85 | 0.8223 | 0.4993 |

### cost-share diagnostic (OVERLAPPING accounts across the 24 runs, not a combined P&L)
n_trades=229,151 gross=43,937.08 fee=25,541.23 funding_net=221.80 net=18,174.04 fee_share_of_gross=0.5813

### Known gaps
- slippage excluded by the user's choice (legs are small); costs are a lower bound and results an upper bound (optimistic).
- max_leverage is today's snapshot (hindsight); limits were different in the past.
- liquidation is checked on 1-minute closes; a move inside a minute can liquidate earlier.
- maker fills are assumed to fill; in practice they may not.
- the test months were already used for the cut-off, the deep dive and the calibration: results are optimistic until the vault or paper-trading check.

### Equity curve PNGs
- research/dislocation_model/logs/s1_profit1_equity_q0.01_feetaker.png
- research/dislocation_model/logs/s1_profit1_equity_q0.01_feemaker.png
- research/dislocation_model/logs/s1_profit1_equity_q0.005_feetaker.png
- research/dislocation_model/logs/s1_profit1_equity_q0.005_feemaker.png
- research/dislocation_model/logs/s1_profit1_equity_q0.001_feetaker.png
- research/dislocation_model/logs/s1_profit1_equity_q0.001_feemaker.png