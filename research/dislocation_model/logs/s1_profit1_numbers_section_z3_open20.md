## [HL-PROFIT1 z3_open20] Portfolio backtest, S1's live picks, build2 d3/asm price, slippage_spread_share=0.0, max_open=20 min_abs_z=3.0

Runs ending above the $1000 start: 19/24.

| q | stop | fee | final_equity | total_return | n_trades | win_rate | profit_factor | sharpe | sortino | max_dd_pct |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.01 | 0p5 | taker | 706.84 | -0.2932 | 3,744 | 0.1960 | 0.8054 | -3.849 | -4.563 | -0.2932 |
| 0.01 | 0p5 | maker | 1019.44 | 0.0194 | 3,819 | 0.1940 | 1.0129 | 0.301 | 0.409 | -0.1101 |
| 0.01 | 1p0 | taker | 781.15 | -0.2188 | 3,754 | 0.2789 | 0.8937 | -2.214 | -2.758 | -0.2188 |
| 0.01 | 1p0 | maker | 1146.15 | 0.1461 | 3,822 | 0.2802 | 1.0662 | 1.396 | 2.058 | -0.1181 |
| 0.01 | 2p0 | taker | 917.35 | -0.0826 | 3,718 | 0.3889 | 0.9726 | -0.400 | -0.531 | -0.1900 |
| 0.01 | 2p0 | maker | 1355.72 | 0.3557 | 3,767 | 0.3913 | 1.1046 | 2.038 | 2.971 | -0.1052 |
| 0.01 | none | taker | 1590.97 | 0.5910 | 3,280 | 0.5460 | 1.1575 | 2.022 | 2.362 | -0.2154 |
| 0.01 | none | maker | 2334.71 | 1.3347 | 3,314 | 0.5480 | 1.3050 | 3.405 | 4.111 | -0.1987 |
| 0.005 | 0p5 | taker | 902.08 | -0.0979 | 1,908 | 0.2070 | 0.8798 | -1.688 | -2.161 | -0.1259 |
| 0.005 | 0p5 | maker | 1093.07 | 0.0931 | 1,928 | 0.2064 | 1.1255 | 1.601 | 2.331 | -0.0609 |
| 0.005 | 1p0 | taker | 1016.13 | 0.0161 | 1,917 | 0.3026 | 1.0145 | 0.291 | 0.339 | -0.0875 |
| 0.005 | 1p0 | maker | 1232.16 | 0.2322 | 1,935 | 0.3034 | 1.2149 | 3.005 | 3.721 | -0.0461 |
| 0.005 | 2p0 | taker | 1088.05 | 0.0881 | 1,918 | 0.4093 | 1.0583 | 0.831 | 0.747 | -0.1020 |
| 0.005 | 2p0 | maker | 1335.78 | 0.3358 | 1,935 | 0.4109 | 1.2179 | 2.640 | 2.420 | -0.0946 |
| 0.005 | none | taker | 1678.67 | 0.6787 | 1,847 | 0.5696 | 1.3451 | 3.116 | 3.496 | -0.1398 |
| 0.005 | none | maker | 2035.80 | 1.0358 | 1,861 | 0.5707 | 1.4982 | 4.184 | 4.837 | -0.1240 |
| 0.001 | 0p5 | taker | 989.99 | -0.0100 | 399 | 0.2105 | 0.9418 | -0.377 | -0.502 | -0.0372 |
| 0.001 | 0p5 | maker | 1030.63 | 0.0306 | 399 | 0.2105 | 1.2138 | 1.232 | 1.901 | -0.0221 |
| 0.001 | 1p0 | taker | 1034.60 | 0.0346 | 399 | 0.3133 | 1.1597 | 1.036 | 1.210 | -0.0208 |
| 0.001 | 1p0 | maker | 1077.07 | 0.0771 | 399 | 0.3133 | 1.4001 | 2.226 | 2.795 | -0.0161 |
| 0.001 | 2p0 | taker | 1042.08 | 0.0421 | 399 | 0.4185 | 1.1486 | 0.949 | 0.750 | -0.0376 |
| 0.001 | 2p0 | maker | 1084.86 | 0.0849 | 399 | 0.4185 | 1.3198 | 1.855 | 1.495 | -0.0366 |
| 0.001 | none | taker | 1164.30 | 0.1643 | 397 | 0.6121 | 1.4758 | 2.964 | 3.154 | -0.0462 |
| 0.001 | none | maker | 1211.79 | 0.2118 | 398 | 0.6131 | 1.6258 | 3.691 | 4.011 | -0.0399 |

### Costs (USD and share of gross), per run
| q | stop | fee | gross | fee | fee_share | slippage | slip_share | funding_paid | fund_paid_share | funding_received | fund_recv_share |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.01 | 0p5 | taker | 192.47 | 486.52 | 2.5278 | 0.00 | 0.0000 | 6.37 | 0.0331 | 7.26 | 0.0377 |
| 0.01 | 0p5 | maker | 215.60 | 197.20 | 0.9147 | 0.00 | 0.0000 | 7.75 | 0.0360 | 8.80 | 0.0408 |
| 0.01 | 1p0 | taker | 294.85 | 514.63 | 1.7454 | 0.00 | 0.0000 | 13.07 | 0.0443 | 14.00 | 0.0475 |
| 0.01 | 1p0 | maker | 356.88 | 211.52 | 0.5927 | 0.00 | 0.0000 | 16.56 | 0.0464 | 17.34 | 0.0486 |
| 0.01 | 2p0 | taker | 500.38 | 586.35 | 1.1718 | 0.00 | 0.0000 | 25.67 | 0.0513 | 29.00 | 0.0580 |
| 0.01 | 2p0 | maker | 592.76 | 241.06 | 0.4067 | 0.00 | 0.0000 | 31.89 | 0.0538 | 35.90 | 0.0606 |
| 0.01 | none | taker | 1237.25 | 626.33 | 0.5062 | 0.00 | 0.0000 | 93.07 | 0.0752 | 73.13 | 0.0591 |
| 0.01 | none | maker | 1617.23 | 260.18 | 0.1609 | 0.00 | 0.0000 | 112.48 | 0.0696 | 90.15 | 0.0557 |
| 0.005 | 0p5 | taker | 175.44 | 273.56 | 1.5593 | 0.00 | 0.0000 | 3.24 | 0.0185 | 3.44 | 0.0196 |
| 0.005 | 0p5 | maker | 194.25 | 101.28 | 0.5214 | 0.00 | 0.0000 | 3.75 | 0.0193 | 3.84 | 0.0198 |
| 0.005 | 1p0 | taker | 309.54 | 294.13 | 0.9502 | 0.00 | 0.0000 | 7.64 | 0.0247 | 8.35 | 0.0270 |
| 0.005 | 1p0 | maker | 340.46 | 109.17 | 0.3207 | 0.00 | 0.0000 | 8.59 | 0.0252 | 9.46 | 0.0278 |
| 0.005 | 2p0 | taker | 396.21 | 310.12 | 0.7827 | 0.00 | 0.0000 | 13.26 | 0.0335 | 15.22 | 0.0384 |
| 0.005 | 2p0 | maker | 449.63 | 115.69 | 0.2573 | 0.00 | 0.0000 | 15.21 | 0.0338 | 17.05 | 0.0379 |
| 0.005 | none | taker | 1040.34 | 358.60 | 0.3447 | 0.00 | 0.0000 | 48.25 | 0.0464 | 45.18 | 0.0434 |
| 0.005 | none | maker | 1172.84 | 134.31 | 0.1145 | 0.00 | 0.0000 | 53.64 | 0.0457 | 50.91 | 0.0434 |
| 0.001 | 0p5 | taker | 49.95 | 59.87 | 1.1986 | 0.00 | 0.0000 | 0.77 | 0.0155 | 0.68 | 0.0137 |
| 0.001 | 0p5 | maker | 51.08 | 20.36 | 0.3986 | 0.00 | 0.0000 | 0.79 | 0.0155 | 0.70 | 0.0137 |
| 0.001 | 1p0 | taker | 95.80 | 61.32 | 0.6401 | 0.00 | 0.0000 | 1.87 | 0.0195 | 2.00 | 0.0208 |
| 0.001 | 1p0 | maker | 97.80 | 20.86 | 0.2132 | 0.00 | 0.0000 | 1.91 | 0.0196 | 2.04 | 0.0209 |
| 0.001 | 2p0 | taker | 103.33 | 61.18 | 0.5921 | 0.00 | 0.0000 | 3.26 | 0.0316 | 3.19 | 0.0309 |
| 0.001 | 2p0 | maker | 105.74 | 20.81 | 0.1968 | 0.00 | 0.0000 | 3.34 | 0.0316 | 3.27 | 0.0309 |
| 0.001 | none | taker | 230.69 | 64.81 | 0.2809 | 0.00 | 0.0000 | 9.61 | 0.0417 | 8.04 | 0.0348 |
| 0.001 | none | maker | 235.51 | 22.10 | 0.0938 | 0.00 | 0.0000 | 9.83 | 0.0417 | 8.21 | 0.0349 |

### CAGR (annualised, N days), per run
| q | stop | fee | cagr | cagr_n_days |
|---|---|---|---|---|
| 0.01 | 0p5 | taker | -0.4658 | 202 |
| 0.01 | 0p5 | maker | 0.0354 | 202 |
| 0.01 | 1p0 | taker | -0.3600 | 202 |
| 0.01 | 1p0 | maker | 0.2795 | 202 |
| 0.01 | 2p0 | taker | -0.1443 | 202 |
| 0.01 | 2p0 | maker | 0.7331 | 202 |
| 0.01 | none | taker | 1.3046 | 203 |
| 0.01 | none | maker | 3.5930 | 203 |
| 0.005 | 0p5 | taker | -0.1699 | 202 |
| 0.005 | 0p5 | maker | 0.1744 | 202 |
| 0.005 | 1p0 | taker | 0.0293 | 202 |
| 0.005 | 1p0 | maker | 0.4582 | 202 |
| 0.005 | 2p0 | taker | 0.1647 | 202 |
| 0.005 | 2p0 | maker | 0.6873 | 202 |
| 0.005 | none | taker | 1.5380 | 203 |
| 0.005 | none | maker | 2.5902 | 203 |
| 0.001 | 0p5 | taker | -0.0180 | 202 |
| 0.001 | 0p5 | maker | 0.0560 | 202 |
| 0.001 | 1p0 | taker | 0.0634 | 202 |
| 0.001 | 1p0 | maker | 0.1436 | 202 |
| 0.001 | 2p0 | taker | 0.0773 | 202 |
| 0.001 | 2p0 | maker | 0.1586 | 202 |
| 0.001 | none | taker | 0.3146 | 203 |
| 0.001 | none | maker | 0.4126 | 203 |

### Daily P&L, per run
| q | stop | fee | mean | median | share_positive_days | worst_day | best_day |
|---|---|---|---|---|---|---|---|
| 0.01 | 0p5 | taker | -1.4441 | -0.9032 | 0.3005 | -41.65 | 31.92 |
| 0.01 | 0p5 | maker | 0.0958 | -0.3237 | 0.4039 | -43.64 | 46.67 |
| 0.01 | 1p0 | taker | -1.0781 | -0.8905 | 0.3547 | -38.55 | 36.18 |
| 0.01 | 1p0 | maker | 0.7199 | -0.0333 | 0.4631 | -38.12 | 53.64 |
| 0.01 | 2p0 | taker | -0.4071 | -0.1596 | 0.4532 | -82.29 | 85.00 |
| 0.01 | 2p0 | maker | 1.7523 | 0.3031 | 0.5222 | -98.26 | 92.40 |
| 0.01 | none | taker | 2.8969 | 1.0255 | 0.5637 | -191.48 | 130.43 |
| 0.01 | none | maker | 6.5427 | 2.3746 | 0.6078 | -213.03 | 147.79 |
| 0.005 | 0p5 | taker | -0.4824 | -0.3989 | 0.3251 | -28.58 | 30.26 |
| 0.005 | 0p5 | maker | 0.4585 | 0.0000 | 0.4039 | -30.95 | 36.99 |
| 0.005 | 1p0 | taker | 0.0795 | 0.0000 | 0.4384 | -38.17 | 35.10 |
| 0.005 | 1p0 | maker | 1.1436 | 0.0000 | 0.4926 | -47.10 | 43.02 |
| 0.005 | 2p0 | taker | 0.4337 | 0.0461 | 0.5025 | -111.44 | 43.62 |
| 0.005 | 2p0 | maker | 1.6541 | 0.3967 | 0.5567 | -117.89 | 53.79 |
| 0.005 | none | taker | 3.3268 | 1.7390 | 0.6029 | -90.37 | 95.73 |
| 0.005 | none | maker | 5.0775 | 2.2721 | 0.6422 | -96.73 | 103.59 |
| 0.001 | 0p5 | taker | -0.0493 | 0.0000 | 0.2069 | -10.07 | 22.51 |
| 0.001 | 0p5 | maker | 0.1509 | 0.0000 | 0.2266 | -9.61 | 23.57 |
| 0.001 | 1p0 | taker | 0.1705 | 0.0000 | 0.2562 | -16.60 | 23.79 |
| 0.001 | 1p0 | maker | 0.3797 | 0.0000 | 0.2857 | -16.52 | 24.87 |
| 0.001 | 2p0 | taker | 0.2073 | 0.0000 | 0.3202 | -37.41 | 24.81 |
| 0.001 | 2p0 | maker | 0.4180 | 0.0000 | 0.3300 | -37.79 | 25.95 |
| 0.001 | none | taker | 0.8054 | 0.0000 | 0.3971 | -26.89 | 30.47 |
| 0.001 | none | maker | 1.0382 | 0.0000 | 0.4167 | -26.81 | 31.95 |

### Trades, per run
| q | stop | fee | win_rate(mu) | stop_share | timeout_share | mean_net | median_net | mean_roc | median_roc | mean_win | mean_loss | mean_holding_min |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.01 | 0p5 | taker | 0.1960 | 0.7957 | 0.0083 | -0.0783 | -0.3616 | -0.0018 | -0.0085 | 1.5900 | -0.5053 | 56.5 |
| 0.01 | 0p5 | maker | 0.1940 | 0.7979 | 0.0081 | 0.0051 | -0.3292 | 0.0001 | -0.0065 | 1.9742 | -0.4930 | 56.4 |
| 0.01 | 1p0 | taker | 0.2789 | 0.6971 | 0.0240 | -0.0583 | -0.5161 | -0.0013 | -0.0116 | 1.6562 | -0.7790 | 94.9 |
| 0.01 | 1p0 | maker | 0.2802 | 0.6960 | 0.0238 | 0.0382 | -0.5235 | 0.0008 | -0.0097 | 2.0648 | -0.8231 | 95.2 |
| 0.01 | 2p0 | taker | 0.3889 | 0.5543 | 0.0568 | -0.0222 | -0.7620 | -0.0004 | -0.0149 | 1.8642 | -1.4087 | 156.8 |
| 0.01 | 2p0 | maker | 0.3913 | 0.5516 | 0.0571 | 0.0944 | -0.7961 | 0.0017 | -0.0126 | 2.3259 | -1.5802 | 157.8 |
| 0.01 | none | taker | 0.5460 | 0.0000 | 0.4540 | 0.1802 | 1.0469 | 0.0032 | 0.0174 | 2.0959 | -3.1057 | 382.6 |
| 0.01 | none | maker | 0.5480 | 0.0000 | 0.4520 | 0.4028 | 1.3963 | 0.0055 | 0.0192 | 2.6721 | -3.7176 | 382.1 |
| 0.005 | 0p5 | taker | 0.2070 | 0.7872 | 0.0058 | -0.0513 | -0.3872 | -0.0011 | -0.0082 | 1.7702 | -0.5422 | 53.0 |
| 0.005 | 0p5 | maker | 0.2064 | 0.7879 | 0.0057 | 0.0483 | -0.3220 | 0.0010 | -0.0062 | 2.0453 | -0.4878 | 53.2 |
| 0.005 | 1p0 | taker | 0.3026 | 0.6766 | 0.0209 | 0.0084 | -0.5442 | 0.0002 | -0.0108 | 1.8669 | -0.8445 | 90.7 |
| 0.005 | 1p0 | maker | 0.3034 | 0.6755 | 0.0212 | 0.1200 | -0.4904 | 0.0022 | -0.0088 | 2.1409 | -0.8171 | 91.3 |
| 0.005 | 2p0 | taker | 0.4093 | 0.5412 | 0.0495 | 0.0459 | -0.7049 | 0.0010 | -0.0132 | 1.9162 | -1.3931 | 146.2 |
| 0.005 | 2p0 | maker | 0.4109 | 0.5380 | 0.0512 | 0.1735 | -0.6655 | 0.0031 | -0.0112 | 2.2005 | -1.4245 | 148.0 |
| 0.005 | none | taker | 0.5696 | 0.0000 | 0.4304 | 0.3674 | 1.1302 | 0.0059 | 0.0181 | 2.2118 | -3.0210 | 366.2 |
| 0.005 | none | maker | 0.5707 | 0.0000 | 0.4293 | 0.5566 | 1.3605 | 0.0079 | 0.0200 | 2.5324 | -3.2949 | 365.9 |
| 0.001 | 0p5 | taker | 0.2105 | 0.7794 | 0.0100 | -0.0251 | -0.3926 | -0.0005 | -0.0079 | 1.8606 | -0.5509 | 55.3 |
| 0.001 | 0p5 | maker | 0.2105 | 0.7794 | 0.0100 | 0.0768 | -0.2983 | 0.0015 | -0.0058 | 1.9989 | -0.4592 | 55.3 |
| 0.001 | 1p0 | taker | 0.3133 | 0.6491 | 0.0376 | 0.0867 | -0.4979 | 0.0017 | -0.0098 | 1.9334 | -0.8057 | 97.5 |
| 0.001 | 1p0 | maker | 0.3133 | 0.6491 | 0.0376 | 0.1932 | -0.4063 | 0.0038 | -0.0079 | 2.0589 | -0.7188 | 97.5 |
| 0.001 | 2p0 | taker | 0.4185 | 0.5213 | 0.0602 | 0.1055 | -0.5710 | 0.0021 | -0.0112 | 1.8586 | -1.2642 | 150.0 |
| 0.001 | 2p0 | maker | 0.4185 | 0.5213 | 0.0602 | 0.2127 | -0.4899 | 0.0041 | -0.0094 | 1.9563 | -1.2060 | 150.0 |
| 0.001 | none | taker | 0.6121 | 0.0000 | 0.3879 | 0.4139 | 0.9628 | 0.0079 | 0.0181 | 1.9304 | -2.5965 | 348.2 |
| 0.001 | none | maker | 0.6131 | 0.0000 | 0.3869 | 0.5321 | 1.0700 | 0.0099 | 0.0199 | 2.0380 | -2.6442 | 347.7 |

### Skips by reason, per run
| q | stop | fee | book_full | margin | min_order |
|---|---|---|---|---|---|
| 0.01 | 0p5 | taker | 2 | 79 | 238 |
| 0.01 | 0p5 | maker | 7 | 73 | 164 |
| 0.01 | 1p0 | taker | 6 | 93 | 210 |
| 0.01 | 1p0 | maker | 21 | 78 | 142 |
| 0.01 | 2p0 | taker | 53 | 137 | 155 |
| 0.01 | 2p0 | maker | 83 | 121 | 92 |
| 0.01 | none | taker | 146 | 526 | 111 |
| 0.01 | none | maker | 178 | 510 | 61 |
| 0.005 | 0p5 | taker | 0 | 22 | 116 |
| 0.005 | 0p5 | maker | 1 | 22 | 95 |
| 0.005 | 1p0 | taker | 1 | 26 | 102 |
| 0.005 | 1p0 | maker | 1 | 26 | 84 |
| 0.005 | 2p0 | taker | 7 | 34 | 87 |
| 0.005 | 2p0 | maker | 7 | 35 | 69 |
| 0.005 | none | taker | 36 | 104 | 59 |
| 0.005 | none | maker | 47 | 91 | 47 |
| 0.001 | 0p5 | taker | 0 | 0 | 35 |
| 0.001 | 0p5 | maker | 0 | 0 | 35 |
| 0.001 | 1p0 | taker | 0 | 0 | 35 |
| 0.001 | 1p0 | maker | 0 | 0 | 35 |
| 0.001 | 2p0 | taker | 0 | 0 | 35 |
| 0.001 | 2p0 | maker | 0 | 0 | 35 |
| 0.001 | none | taker | 0 | 4 | 33 |
| 0.001 | none | maker | 0 | 4 | 32 |

### Leverage and risk, per run
| q | stop | fee | peak_margin_used | mean_open | max_open | n_liquidations |
|---|---|---|---|---|---|---|
| 0.01 | 0p5 | taker | 930.64 | 2.17 | 20 | 0 |
| 0.01 | 0p5 | maker | 1038.12 | 2.17 | 20 | 0 |
| 0.01 | 1p0 | taker | 974.10 | 2.73 | 20 | 0 |
| 0.01 | 1p0 | maker | 1116.51 | 2.75 | 20 | 0 |
| 0.01 | 2p0 | taker | 1107.75 | 3.41 | 20 | 0 |
| 0.01 | 2p0 | maker | 1321.85 | 3.47 | 20 | 0 |
| 0.01 | none | taker | 1572.26 | 5.68 | 20 | 0 |
| 0.01 | none | maker | 2249.98 | 5.73 | 20 | 0 |
| 0.005 | 0p5 | taker | 960.50 | 1.70 | 20 | 0 |
| 0.005 | 0p5 | maker | 1015.61 | 1.70 | 20 | 0 |
| 0.005 | 1p0 | taker | 995.73 | 2.08 | 20 | 0 |
| 0.005 | 1p0 | maker | 1097.65 | 2.09 | 20 | 0 |
| 0.005 | 2p0 | taker | 1067.97 | 2.50 | 20 | 0 |
| 0.005 | 2p0 | maker | 1181.59 | 2.53 | 20 | 0 |
| 0.005 | none | taker | 1538.38 | 3.95 | 20 | 0 |
| 0.005 | none | maker | 1843.29 | 3.96 | 20 | 0 |
| 0.001 | 0p5 | taker | 552.79 | 1.32 | 11 | 0 |
| 0.001 | 0p5 | maker | 564.55 | 1.32 | 11 | 0 |
| 0.001 | 1p0 | taker | 642.52 | 1.59 | 13 | 0 |
| 0.001 | 1p0 | maker | 645.55 | 1.59 | 13 | 0 |
| 0.001 | 2p0 | taker | 642.53 | 1.61 | 13 | 0 |
| 0.001 | 2p0 | maker | 645.55 | 1.61 | 13 | 0 |
| 0.001 | none | taker | 947.54 | 2.09 | 19 | 0 |
| 0.001 | none | maker | 951.83 | 2.09 | 19 | 0 |

### Liquidation events, per run
none, in any of the 24 runs.

### Splits: top/bottom 10 coins (net of trades involving the coin, each trade counted for both coins) and pairs, per run
**q0.01_stop0p5_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 37.72 |
| NOT | 35.62 |
| MEW | 27.37 |
| STABLE | 17.05 |
| ZETA | 14.50 |
| POLYX | 14.45 |
| ZEREBRO | 13.20 |
| LDO | 12.04 |
| PEOPLE | 10.59 |
| RENDER | 10.52 |
**q0.01_stop0p5_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| ZK | -13.09 |
| XPL | -13.38 |
| FET | -13.51 |
| SAGA | -13.89 |
| MELANIA | -15.03 |
| TNSR | -15.39 |
| CHILLGUY | -16.70 |
| VINE | -19.35 |
| AVNT | -20.49 |
| TST | -40.56 |
**q0.01_stop0p5_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| FOGO/MAVIA | 11.99 |
| FOGO/STABLE | 10.16 |
| YZY/ZETA | 8.96 |
| LAYER/MEGA | 7.49 |
| YZY/ZRO | 7.30 |
| OP/ZEREBRO | 7.04 |
| ADA/UNI | 6.34 |
| BLAST/MEGA | 5.93 |
| ACE/MEGA | 5.72 |
| MEGA/TRB | 5.67 |
**q0.01_stop0p5_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| MEGA/SAGA | -3.54 |
| HMSTR/NOT | -3.68 |
| MEGA/YZY | -3.83 |
| HMSTR/UNI | -3.86 |
| UNI/USUAL | -5.02 |
| CHILLGUY/MEGA | -5.19 |
| FOGO/OM | -5.75 |
| HMSTR/LIT | -6.73 |
| FOGO/MELANIA | -6.95 |
| FTT/TST | -13.19 |

**q0.01_stop0p5_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 67.68 |
| NOT | 55.63 |
| MEW | 41.15 |
| YZY | 31.49 |
| STABLE | 24.57 |
| ZETA | 24.15 |
| POLYX | 20.08 |
| PEOPLE | 18.68 |
| LDO | 17.60 |
| POL | 15.93 |
**q0.01_stop0p5_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| XPL | -11.79 |
| 0G | -11.89 |
| ZK | -12.02 |
| SAGA | -13.12 |
| MELANIA | -13.32 |
| TNSR | -14.61 |
| CHILLGUY | -15.42 |
| VINE | -17.40 |
| AVNT | -18.30 |
| TST | -41.64 |
**q0.01_stop0p5_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| FOGO/MAVIA | 12.92 |
| YZY/ZETA | 11.98 |
| FOGO/STABLE | 10.82 |
| YZY/ZRO | 9.80 |
| LAYER/MEGA | 8.10 |
| OP/ZEREBRO | 7.81 |
| YZY/kSHIB | 7.56 |
| ADA/UNI | 7.05 |
| BANANA/HMSTR | 6.40 |
| ADA/HMSTR | 6.15 |
**q0.01_stop0p5_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| MEGA/SAGA | -3.44 |
| HMSTR/NOT | -3.83 |
| HMSTR/UNI | -4.36 |
| FOGO/LAYER | -4.94 |
| CHILLGUY/MEGA | -5.70 |
| FOGO/OM | -5.73 |
| UNI/USUAL | -5.79 |
| FOGO/MELANIA | -6.94 |
| HMSTR/LIT | -7.06 |
| FTT/TST | -16.46 |

**q0.01_stop1p0_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 64.65 |
| NOT | 58.31 |
| MEW | 44.83 |
| ZEREBRO | 22.33 |
| STABLE | 21.49 |
| MEGA | 19.94 |
| ASTER | 16.14 |
| PEOPLE | 15.77 |
| LDO | 14.49 |
| POLYX | 12.99 |
**q0.01_stop1p0_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| LINEA | -17.73 |
| RESOLV | -17.76 |
| ZRO | -18.96 |
| SAGA | -20.46 |
| PURR | -22.62 |
| CHILLGUY | -23.21 |
| AVNT | -24.09 |
| TNSR | -24.92 |
| VINE | -39.46 |
| TST | -45.46 |
**q0.01_stop1p0_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| FOGO/MEGA | 14.92 |
| FOGO/MAVIA | 11.68 |
| HMSTR/TST | 10.83 |
| FOGO/STABLE | 10.47 |
| YZY/ZETA | 9.89 |
| FOGO/TON | 9.88 |
| AR/ZEC | 9.09 |
| GRASS/MEGA | 8.19 |
| YZY/ZRO | 8.07 |
| OP/ZEREBRO | 6.91 |
**q0.01_stop1p0_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| MEGA/YZY | -4.55 |
| MEGA/SAGA | -5.04 |
| CHILLGUY/MEGA | -5.28 |
| UNI/USUAL | -5.35 |
| FOGO/OM | -5.80 |
| FARTCOIN/TST | -6.52 |
| HMSTR/LIT | -6.90 |
| FOGO/MELANIA | -7.01 |
| HMSTR/JTO | -7.42 |
| FTT/TST | -14.06 |

**q0.01_stop1p0_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 104.75 |
| NOT | 80.73 |
| MEW | 64.88 |
| YZY | 41.47 |
| STABLE | 29.50 |
| ZEREBRO | 26.31 |
| MEGA | 26.10 |
| PEOPLE | 25.83 |
| ASTER | 22.86 |
| LDO | 20.96 |
**q0.01_stop1p0_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| MELANIA | -15.66 |
| BABY | -17.56 |
| PURR | -18.88 |
| LINEA | -19.65 |
| SAGA | -19.90 |
| AVNT | -22.77 |
| CHILLGUY | -24.46 |
| TNSR | -25.38 |
| VINE | -39.55 |
| TST | -48.38 |
**q0.01_stop1p0_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| FOGO/MEGA | 15.24 |
| HMSTR/TST | 14.04 |
| YZY/ZETA | 13.42 |
| FOGO/MAVIA | 12.67 |
| AR/ZEC | 11.90 |
| FOGO/STABLE | 11.21 |
| YZY/ZRO | 10.98 |
| FOGO/TON | 10.49 |
| GRASS/MEGA | 8.78 |
| YZY/kSHIB | 7.99 |
**q0.01_stop1p0_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| MEGA/SAGA | -5.03 |
| FOGO/LAYER | -5.19 |
| FOGO/OM | -5.78 |
| CHILLGUY/MEGA | -5.86 |
| UNI/USUAL | -6.26 |
| FOGO/MELANIA | -7.00 |
| HMSTR/LIT | -7.29 |
| HMSTR/JTO | -7.84 |
| FARTCOIN/TST | -8.21 |
| FTT/TST | -17.79 |

**q0.01_stop2p0_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| MEGA | 164.70 |
| HMSTR | 86.17 |
| MEW | 72.62 |
| NOT | 71.54 |
| ZEREBRO | 37.87 |
| ASTER | 36.38 |
| FOGO | 27.88 |
| PEOPLE | 27.23 |
| MAVIA | 26.28 |
| WIF | 24.57 |
**q0.01_stop2p0_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| DYM | -24.22 |
| MELANIA | -27.20 |
| LINEA | -27.30 |
| RESOLV | -29.06 |
| ZEC | -32.96 |
| CHILLGUY | -33.92 |
| FTT | -34.63 |
| XPL | -34.65 |
| VINE | -62.29 |
| TST | -84.52 |
**q0.01_stop2p0_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| FOGO/MEGA | 16.95 |
| HMSTR/TST | 16.43 |
| MEGA/MET | 12.40 |
| YZY/ZETA | 12.26 |
| FOGO/STABLE | 11.70 |
| FOGO/MAVIA | 11.68 |
| BERA/MEGA | 11.33 |
| AR/ZEC | 10.74 |
| YZY/ZRO | 10.00 |
| YZY/kSHIB | 9.37 |
**q0.01_stop2p0_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| MEGA/YZY | -6.32 |
| MELANIA/TST | -6.67 |
| TST/ZEC | -6.84 |
| FOGO/MELANIA | -7.02 |
| HYPER/TNSR | -7.32 |
| BANANA/YZY | -7.37 |
| HMSTR/LIT | -7.65 |
| HMSTR/JTO | -8.22 |
| TST/XAI | -9.76 |
| FTT/TST | -16.57 |

**q0.01_stop2p0_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| MEGA | 172.50 |
| HMSTR | 133.60 |
| MEW | 104.33 |
| NOT | 98.41 |
| YZY | 69.16 |
| ASTER | 46.09 |
| ZEREBRO | 43.74 |
| MAVIA | 43.64 |
| PEOPLE | 40.39 |
| FOGO | 35.66 |
**q0.01_stop2p0_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| LTC | -23.05 |
| RESOLV | -25.92 |
| ZEC | -27.56 |
| MELANIA | -28.56 |
| CHILLGUY | -29.08 |
| LINEA | -31.92 |
| FTT | -34.86 |
| XPL | -35.67 |
| VINE | -66.51 |
| TST | -96.49 |
**q0.01_stop2p0_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| HMSTR/TST | 21.04 |
| FOGO/MEGA | 17.24 |
| YZY/ZETA | 16.77 |
| AR/ZEC | 14.09 |
| YZY/ZRO | 13.72 |
| YZY/kSHIB | 13.12 |
| BERA/MEGA | 12.80 |
| MEGA/MET | 12.74 |
| FOGO/MAVIA | 12.53 |
| FOGO/STABLE | 12.36 |
**q0.01_stop2p0_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| FET/TRX | -7.70 |
| APT/FTT | -7.74 |
| HMSTR/LIT | -7.96 |
| BANANA/YZY | -8.09 |
| MELANIA/TST | -8.24 |
| HMSTR/JTO | -8.56 |
| TST/ZEC | -8.65 |
| HYPER/TNSR | -9.18 |
| TST/XAI | -12.40 |
| FTT/TST | -21.10 |

**q0.01_stopnone_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 186.33 |
| MEGA | 180.04 |
| FOGO | 119.53 |
| YZY | 102.74 |
| NOT | 97.93 |
| MAVIA | 86.61 |
| MEW | 86.35 |
| STABLE | 52.88 |
| ARK | 49.45 |
| XAI | 48.42 |
**q0.01_stopnone_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| 0G | -47.67 |
| AVNT | -54.12 |
| INIT | -54.39 |
| ORDI | -54.53 |
| POL | -55.38 |
| SAGA | -56.74 |
| DYM | -56.79 |
| VINE | -59.87 |
| DOGE | -62.81 |
| XPL | -139.23 |
**q0.01_stopnone_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| HMSTR/TST | 17.63 |
| FOGO/MEGA | 17.00 |
| CHILLGUY/FOGO | 16.98 |
| FOGO/MAVIA | 16.92 |
| YZY/ZETA | 16.78 |
| YZY/ZRO | 13.68 |
| YZY/kSHIB | 12.83 |
| MEGA/MET | 12.62 |
| FOGO/STABLE | 12.41 |
| AR/ZEC | 11.74 |
**q0.01_stopnone_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| ETC/XPL | -20.24 |
| POL/XPL | -20.50 |
| FARTCOIN/FIL | -20.58 |
| HYPER/PEOPLE | -20.67 |
| DOOD/ORDI | -21.59 |
| LDO/XPL | -21.68 |
| SYRUP/UNI | -23.00 |
| BERA/DOGE | -23.53 |
| BANANA/TNSR | -23.60 |
| SUI/XPL | -44.05 |

**q0.01_stopnone_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 253.49 |
| MEGA | 204.91 |
| YZY | 173.85 |
| FOGO | 144.33 |
| NOT | 123.27 |
| MAVIA | 118.65 |
| MEW | 118.26 |
| STABLE | 72.66 |
| ARK | 69.87 |
| NEAR | 66.90 |
**q0.01_stopnone_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| VINE | -47.04 |
| KAITO | -47.73 |
| POL | -48.80 |
| ORDI | -59.92 |
| SAGA | -60.45 |
| AVNT | -66.16 |
| DYM | -66.27 |
| DOGE | -67.81 |
| INIT | -68.11 |
| XPL | -157.15 |
**q0.01_stopnone_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| YZY/ZETA | 22.55 |
| HMSTR/TST | 22.22 |
| YZY/ZRO | 18.45 |
| FOGO/MAVIA | 18.13 |
| CHILLGUY/FOGO | 18.08 |
| YZY/kSHIB | 17.64 |
| FOGO/MEGA | 17.45 |
| JUP/LINK | 16.15 |
| AR/ZEC | 15.16 |
| BERA/MEGA | 14.93 |
**q0.01_stopnone_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| ETC/XPL | -23.30 |
| DYM/INIT | -23.33 |
| POL/XPL | -23.62 |
| BANANA/TNSR | -23.84 |
| DOOD/INIT | -24.10 |
| LDO/XPL | -24.97 |
| BERA/DOGE | -25.97 |
| DOOD/ORDI | -28.97 |
| SYRUP/UNI | -33.08 |
| SUI/XPL | -50.76 |

**q0.005_stop0p5_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| NOT | 23.78 |
| MEW | 21.47 |
| STABLE | 18.81 |
| HMSTR | 17.55 |
| FOGO | 15.24 |
| ADA | 14.01 |
| YZY | 13.91 |
| ZETA | 11.92 |
| GMX | 10.19 |
| VVV | 8.70 |
**q0.005_stop0p5_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| PUMP | -8.78 |
| CHILLGUY | -9.32 |
| 0G | -9.46 |
| BABY | -10.46 |
| AVNT | -10.87 |
| XRP | -11.72 |
| PURR | -13.92 |
| VINE | -14.06 |
| ZEC | -17.49 |
| TST | -32.34 |
**q0.005_stop0p5_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| FOGO/MAVIA | 12.51 |
| FOGO/STABLE | 10.60 |
| YZY/ZETA | 10.55 |
| YZY/ZRO | 8.60 |
| LAYER/MEGA | 7.81 |
| ADA/UNI | 6.79 |
| FOGO/TON | 6.28 |
| MEGA/UMA | 5.64 |
| AVAX/UNI | 5.55 |
| WLFI/ZEREBRO | 5.45 |
**q0.005_stop0p5_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| AVNT/PURR | -2.25 |
| MEGA/MINA | -2.25 |
| MEGA/STX | -2.28 |
| CHILLGUY/FOGO | -2.33 |
| LINEA/TST | -2.38 |
| XPL/kSHIB | -2.95 |
| TST/XAI | -3.17 |
| HMSTR/UNI | -4.65 |
| FOGO/LAYER | -5.19 |
| HMSTR/LIT | -7.09 |

**q0.005_stop0p5_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| NOT | 32.11 |
| HMSTR | 30.50 |
| MEW | 28.63 |
| YZY | 27.77 |
| STABLE | 22.44 |
| FOGO | 18.82 |
| ADA | 17.06 |
| ZETA | 16.22 |
| GMX | 12.91 |
| CAKE | 11.58 |
**q0.005_stop0p5_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| PUMP | -7.50 |
| AVNT | -8.03 |
| CHILLGUY | -8.35 |
| XRP | -8.36 |
| 0G | -9.23 |
| BABY | -10.08 |
| VINE | -11.09 |
| PURR | -11.30 |
| ZEC | -13.69 |
| TST | -34.25 |
**q0.005_stop0p5_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| FOGO/MAVIA | 13.20 |
| YZY/ZETA | 12.43 |
| FOGO/STABLE | 11.06 |
| YZY/ZRO | 10.17 |
| LAYER/MEGA | 8.31 |
| ADA/UNI | 7.37 |
| FOGO/TON | 6.58 |
| CAKE/RESOLV | 6.23 |
| AVAX/UNI | 6.07 |
| YZY/kSHIB | 5.96 |
**q0.005_stop0p5_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| AVNT/PURR | -2.12 |
| MEGA/MINA | -2.18 |
| MEGA/STX | -2.20 |
| CHILLGUY/FOGO | -2.23 |
| XPL/kSHIB | -2.66 |
| FARTCOIN/TST | -3.48 |
| TST/XAI | -3.49 |
| HMSTR/UNI | -4.99 |
| FOGO/LAYER | -5.10 |
| HMSTR/LIT | -7.26 |

**q0.005_stop1p0_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 66.83 |
| NOT | 38.99 |
| MEW | 31.36 |
| STABLE | 24.18 |
| FOGO | 23.03 |
| ADA | 20.51 |
| YZY | 19.33 |
| ASTER | 14.01 |
| WIF | 13.85 |
| ZEREBRO | 13.50 |
**q0.005_stop1p0_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| JUP | -11.88 |
| AVNT | -11.91 |
| SOL | -12.08 |
| BABY | -13.81 |
| CHILLGUY | -14.60 |
| DYM | -18.74 |
| PURR | -20.74 |
| ZEC | -20.97 |
| VINE | -27.13 |
| TST | -34.05 |
**q0.005_stop1p0_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| HMSTR/TST | 13.98 |
| FOGO/MAVIA | 12.10 |
| YZY/ZETA | 11.80 |
| FOGO/STABLE | 10.85 |
| YZY/ZRO | 9.63 |
| ADA/UNI | 6.95 |
| FIL/ZEREBRO | 6.58 |
| FOGO/TON | 6.42 |
| BCH/TST | 5.89 |
| DYDX/FIL | 5.86 |
**q0.005_stop1p0_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| TST/ZEC | -3.38 |
| CC/FOGO | -3.46 |
| CHILLGUY/FOGO | -3.57 |
| AAVE/SOL | -3.58 |
| DOGE/TST | -3.64 |
| TST/ZETA | -3.67 |
| TST/XAI | -4.70 |
| HMSTR/UNI | -5.02 |
| FOGO/LAYER | -5.50 |
| HMSTR/LIT | -7.31 |

**q0.005_stop1p0_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 86.56 |
| NOT | 48.84 |
| MEW | 40.72 |
| YZY | 35.91 |
| STABLE | 28.83 |
| FOGO | 27.93 |
| ADA | 24.19 |
| ASTER | 18.06 |
| WIF | 17.41 |
| ZEREBRO | 15.14 |
**q0.005_stop1p0_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| JUP | -10.85 |
| STRK | -10.88 |
| LINEA | -11.68 |
| CHILLGUY | -14.02 |
| BABY | -15.10 |
| ZEC | -16.60 |
| DYM | -17.20 |
| PURR | -19.01 |
| VINE | -24.67 |
| TST | -36.88 |
**q0.005_stop1p0_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| HMSTR/TST | 15.98 |
| YZY/ZETA | 13.91 |
| FOGO/MAVIA | 12.77 |
| YZY/ZRO | 11.38 |
| FOGO/STABLE | 11.30 |
| ADA/UNI | 7.53 |
| DYDX/FIL | 7.23 |
| FIL/ZEREBRO | 7.07 |
| CAKE/RESOLV | 7.03 |
| BCH/TST | 6.80 |
**q0.005_stop1p0_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| IOTA/TST | -3.46 |
| CHILLGUY/FOGO | -3.51 |
| TST/ZRO | -3.55 |
| TST/ZEC | -3.73 |
| DOGE/TST | -4.04 |
| TST/ZETA | -4.19 |
| HMSTR/UNI | -5.40 |
| FOGO/LAYER | -5.43 |
| HMSTR/LIT | -7.48 |
| FARTCOIN/TST | -8.78 |

**q0.005_stop2p0_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 73.94 |
| MEGA | 57.11 |
| MEW | 51.26 |
| NOT | 45.44 |
| FOGO | 45.09 |
| ASTER | 37.60 |
| YZY | 25.61 |
| STABLE | 25.26 |
| ZEREBRO | 20.87 |
| PEOPLE | 20.12 |
**q0.005_stop2p0_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| CHILLGUY | -17.90 |
| MELANIA | -17.91 |
| STRK | -18.48 |
| FTT | -18.90 |
| AVNT | -19.54 |
| LINEA | -19.67 |
| DYM | -27.97 |
| VINE | -39.39 |
| ZEC | -46.98 |
| TST | -79.25 |
**q0.005_stop2p0_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| HMSTR/TST | 15.17 |
| YZY/ZETA | 12.69 |
| FOGO/STABLE | 11.36 |
| FOGO/MAVIA | 11.31 |
| YZY/ZRO | 10.35 |
| MEGA/STX | 8.06 |
| YZY/kSHIB | 7.86 |
| MEGA/MINA | 7.38 |
| ADA/UNI | 7.03 |
| MEGA/SUPER | 6.92 |
**q0.005_stop2p0_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| CHILLGUY/FOGO | -5.74 |
| SCR/TST | -6.02 |
| JUP/TST | -6.03 |
| TST/XPL | -6.18 |
| MELANIA/TST | -6.22 |
| APT/FTT | -6.57 |
| LINEA/TST | -7.29 |
| TST/ZEC | -7.54 |
| HMSTR/LIT | -7.59 |
| TST/XAI | -10.77 |

**q0.005_stop2p0_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 96.55 |
| MEW | 63.67 |
| MEGA | 62.07 |
| NOT | 56.45 |
| FOGO | 50.40 |
| YZY | 48.95 |
| ASTER | 43.46 |
| STABLE | 30.62 |
| PEOPLE | 25.23 |
| ADA | 23.28 |
**q0.005_stop2p0_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| AVNT | -15.60 |
| CHILLGUY | -16.62 |
| BABY | -17.67 |
| MELANIA | -17.89 |
| FTT | -18.14 |
| STRK | -18.47 |
| DYM | -27.22 |
| VINE | -37.83 |
| ZEC | -44.88 |
| TST | -81.73 |
**q0.005_stop2p0_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| HMSTR/TST | 17.43 |
| YZY/ZETA | 15.14 |
| YZY/ZRO | 12.39 |
| FOGO/MAVIA | 11.95 |
| FOGO/STABLE | 11.83 |
| YZY/kSHIB | 9.58 |
| MEGA/STX | 8.20 |
| DYDX/FIL | 7.82 |
| ICP/NOT | 7.76 |
| CAKE/RESOLV | 7.68 |
**q0.005_stop2p0_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| CHILLGUY/FOGO | -5.74 |
| SOL/TST | -6.38 |
| SCR/TST | -6.76 |
| JUP/TST | -6.77 |
| TST/XPL | -6.95 |
| MELANIA/TST | -6.99 |
| APT/FTT | -7.36 |
| HMSTR/LIT | -7.76 |
| TST/ZEC | -8.50 |
| TST/XAI | -12.18 |

**q0.005_stopnone_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 121.59 |
| MEGA | 110.59 |
| FOGO | 102.92 |
| TST | 101.69 |
| YZY | 92.60 |
| NOT | 54.73 |
| MEW | 48.71 |
| ASTER | 45.38 |
| STABLE | 45.23 |
| MAVIA | 42.81 |
**q0.005_stopnone_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| SAGA | -24.16 |
| XPL | -24.94 |
| kBONK | -25.03 |
| ZEC | -26.83 |
| BRETT | -28.07 |
| TAO | -29.22 |
| TIA | -30.58 |
| DOGE | -46.86 |
| VINE | -78.34 |
| DYM | -84.32 |
**q0.005_stopnone_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| YZY/ZETA | 17.69 |
| HMSTR/TST | 16.99 |
| CHILLGUY/FOGO | 16.13 |
| FOGO/MAVIA | 15.87 |
| YZY/ZRO | 14.42 |
| MELANIA/TST | 13.60 |
| TST/ZEC | 13.24 |
| TST/XAI | 11.97 |
| JUP/TST | 11.94 |
| FOGO/STABLE | 11.83 |
**q0.005_stopnone_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| IOTA/PYTH | -15.23 |
| BRETT/XPL | -15.31 |
| SAGA/VVV | -16.27 |
| CFX/KAITO | -16.85 |
| TAO/kPEPE | -18.54 |
| DOOD/INIT | -18.98 |
| BERA/SOL | -19.13 |
| TIA/XPL | -19.35 |
| BERA/DOGE | -21.45 |
| TAO/kBONK | -25.92 |

**q0.005_stopnone_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 152.63 |
| YZY | 126.91 |
| MEGA | 119.36 |
| TST | 115.02 |
| FOGO | 112.11 |
| NOT | 68.99 |
| MEW | 63.64 |
| MAVIA | 53.19 |
| STABLE | 53.05 |
| ASTER | 52.49 |
**q0.005_stopnone_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| SAND | -23.62 |
| XPL | -25.16 |
| kBONK | -26.18 |
| BRETT | -27.51 |
| TAO | -29.34 |
| TIA | -29.74 |
| SOL | -31.07 |
| DOGE | -50.73 |
| VINE | -79.05 |
| DYM | -87.47 |
**q0.005_stopnone_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| YZY/ZETA | 20.82 |
| HMSTR/TST | 19.43 |
| YZY/ZRO | 17.03 |
| CHILLGUY/FOGO | 16.67 |
| FOGO/MAVIA | 16.51 |
| MELANIA/TST | 15.57 |
| TST/ZEC | 15.17 |
| JUP/TST | 13.69 |
| YZY/kSHIB | 13.17 |
| FARTCOIN/HMSTR | 12.38 |
**q0.005_stopnone_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| BRETT/XPL | -16.66 |
| SOPH/XLM | -16.87 |
| IOTA/PYTH | -18.08 |
| CFX/KAITO | -19.68 |
| BERA/SOL | -19.99 |
| TAO/kPEPE | -20.40 |
| TIA/XPL | -20.99 |
| DOOD/INIT | -21.89 |
| BERA/DOGE | -22.48 |
| TAO/kBONK | -22.66 |

**q0.001_stop0p5_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| FOGO | 29.05 |
| STABLE | 12.60 |
| HMSTR | 10.04 |
| NOT | 9.57 |
| TON | 7.87 |
| MAVIA | 7.69 |
| ASTER | 6.84 |
| UNI | 6.62 |
| AVAX | 5.98 |
| BERA | 4.28 |
**q0.001_stop0p5_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| PUMP | -3.67 |
| CHILLGUY | -3.82 |
| DYM | -4.19 |
| RESOLV | -4.76 |
| LAYER | -4.98 |
| PURR | -5.66 |
| FTT | -5.67 |
| ZEC | -6.17 |
| MEGA | -6.94 |
| TST | -12.73 |
**q0.001_stop0p5_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| FOGO/MAVIA | 13.08 |
| FOGO/STABLE | 11.12 |
| FOGO/TON | 6.58 |
| AVAX/UNI | 5.98 |
| YZY/ZRO | 5.12 |
| ADA/ASTER | 4.40 |
| ASTER/PYTH | 3.60 |
| KAITO/MAV | 2.75 |
| FOGO/GMX | 2.64 |
| FOGO/FXS | 2.53 |
**q0.001_stop0p5_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| PENGU/ZEC | -1.26 |
| GMX/TST | -1.34 |
| MERL/MORPHO | -1.36 |
| BOME/MELANIA | -1.45 |
| ONDO/PUMP | -1.54 |
| HMSTR/TST | -1.55 |
| AVNT/PURR | -1.71 |
| JUP/TST | -1.76 |
| FTT/MEGA | -2.15 |
| FOGO/LAYER | -4.98 |

**q0.001_stop0p5_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| FOGO | 30.99 |
| STABLE | 12.93 |
| HMSTR | 12.68 |
| NOT | 11.17 |
| MAVIA | 8.78 |
| TON | 8.20 |
| ASTER | 7.97 |
| UNI | 7.85 |
| AVAX | 6.34 |
| BERA | 4.59 |
**q0.001_stop0p5_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| PUMP | -2.89 |
| CHILLGUY | -3.02 |
| DYM | -3.53 |
| RESOLV | -3.57 |
| PURR | -4.68 |
| LAYER | -4.83 |
| FTT | -5.04 |
| ZEC | -5.32 |
| MEGA | -5.75 |
| TST | -11.92 |
**q0.001_stop0p5_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| FOGO/MAVIA | 13.46 |
| FOGO/STABLE | 11.31 |
| FOGO/TON | 6.73 |
| AVAX/UNI | 6.34 |
| YZY/ZRO | 5.38 |
| ADA/ASTER | 4.61 |
| ASTER/PYTH | 3.80 |
| KAITO/MAV | 2.88 |
| FOGO/GMX | 2.84 |
| FOGO/FXS | 2.64 |
**q0.001_stop0p5_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| CHILLGUY/MEGA | -1.17 |
| ONDO/PUMP | -1.28 |
| GMX/TST | -1.29 |
| MERL/MORPHO | -1.29 |
| BOME/MELANIA | -1.30 |
| HMSTR/TST | -1.50 |
| AVNT/PURR | -1.62 |
| JUP/TST | -1.71 |
| FTT/MEGA | -2.09 |
| FOGO/LAYER | -4.83 |

**q0.001_stop1p0_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 38.75 |
| FOGO | 28.54 |
| ASTER | 19.18 |
| STABLE | 12.73 |
| MANTA | 9.91 |
| MAVIA | 8.79 |
| NOT | 8.23 |
| UNI | 8.16 |
| TON | 7.71 |
| MAV | 6.40 |
**q0.001_stop1p0_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| STRK | -4.91 |
| ZK | -4.99 |
| LAYER | -5.01 |
| RESOLV | -5.69 |
| WLFI | -6.11 |
| DYM | -6.64 |
| FTT | -7.11 |
| CHILLGUY | -7.28 |
| PURR | -7.86 |
| ZEC | -8.26 |
**q0.001_stop1p0_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| HMSTR/TST | 14.17 |
| FOGO/MAVIA | 12.43 |
| FOGO/STABLE | 11.20 |
| FOGO/TON | 6.63 |
| AVAX/UNI | 6.04 |
| YZY/ZRO | 5.34 |
| ADA/ASTER | 4.43 |
| HMSTR/MAV | 3.99 |
| ASTER/TST | 3.87 |
| ASTER/PYTH | 3.63 |
**q0.001_stop1p0_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| TST/XPL | -2.05 |
| FTT/MEGA | -2.17 |
| GMX/TST | -2.29 |
| MELANIA/TST | -2.49 |
| FOGO/TRX | -2.59 |
| ONDO/STRK | -2.66 |
| JUP/TST | -2.67 |
| SKY/TST | -2.80 |
| TST/WLFI | -2.89 |
| FOGO/LAYER | -5.01 |

**q0.001_stop1p0_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 42.09 |
| FOGO | 30.55 |
| ASTER | 20.56 |
| STABLE | 13.07 |
| MANTA | 10.53 |
| MAVIA | 9.88 |
| NOT | 9.83 |
| UNI | 9.44 |
| TON | 8.04 |
| MAV | 6.76 |
**q0.001_stop1p0_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| STRK | -4.44 |
| RESOLV | -4.47 |
| ZK | -4.60 |
| LAYER | -4.86 |
| WLFI | -5.37 |
| DYM | -6.01 |
| FTT | -6.50 |
| CHILLGUY | -6.53 |
| PURR | -6.89 |
| ZEC | -7.43 |
**q0.001_stop1p0_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| HMSTR/TST | 14.65 |
| FOGO/MAVIA | 12.81 |
| FOGO/STABLE | 11.39 |
| FOGO/TON | 6.78 |
| AVAX/UNI | 6.41 |
| YZY/ZRO | 5.62 |
| ADA/ASTER | 4.65 |
| HMSTR/MAV | 4.12 |
| ASTER/TST | 4.07 |
| ASTER/PYTH | 3.83 |
**q0.001_stop1p0_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| TST/XPL | -2.01 |
| FTT/MEGA | -2.11 |
| GMX/TST | -2.26 |
| MELANIA/TST | -2.46 |
| FOGO/TRX | -2.50 |
| ONDO/STRK | -2.61 |
| JUP/TST | -2.64 |
| SKY/TST | -2.79 |
| TST/WLFI | -2.88 |
| FOGO/LAYER | -4.86 |

**q0.001_stop2p0_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 39.13 |
| FOGO | 31.60 |
| ASTER | 26.26 |
| STABLE | 12.69 |
| UNI | 11.57 |
| MEW | 9.28 |
| MANTA | 9.18 |
| MEGA | 7.39 |
| TON | 7.14 |
| MAV | 6.20 |
**q0.001_stop2p0_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| STRK | -6.06 |
| ZRO | -7.14 |
| RESOLV | -7.21 |
| XPL | -7.55 |
| DYM | -8.08 |
| MELANIA | -8.27 |
| JUP | -8.74 |
| WLFI | -8.80 |
| ZEC | -13.90 |
| TST | -17.89 |
**q0.001_stop2p0_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| HMSTR/TST | 14.20 |
| FOGO/STABLE | 11.14 |
| FOGO/MAVIA | 11.06 |
| FOGO/TON | 6.59 |
| AVAX/UNI | 5.96 |
| YZY/ZRO | 5.34 |
| CHILLGUY/MEGA | 4.77 |
| ADA/ASTER | 4.38 |
| ASTER/UNI | 4.26 |
| HMSTR/MAV | 3.96 |
**q0.001_stop2p0_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| EIGEN/MEGA | -2.96 |
| CHILLGUY/W | -2.97 |
| DOT/XRP | -3.19 |
| CHILLGUY/NIL | -3.42 |
| TST/WLFI | -3.43 |
| YZY/ZEN | -4.12 |
| GMX/TST | -4.43 |
| JUP/TST | -5.65 |
| TST/XPL | -5.79 |
| MELANIA/TST | -5.83 |

**q0.001_stop2p0_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| HMSTR | 42.52 |
| FOGO | 33.57 |
| ASTER | 27.74 |
| STABLE | 13.03 |
| UNI | 12.90 |
| MEW | 10.60 |
| MANTA | 9.76 |
| MEGA | 8.68 |
| TON | 7.45 |
| ALGO | 7.10 |
**q0.001_stop2p0_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| NIL | -5.39 |
| STRK | -5.61 |
| RESOLV | -6.04 |
| DYM | -7.48 |
| XPL | -7.58 |
| MELANIA | -7.81 |
| WLFI | -8.10 |
| JUP | -8.61 |
| ZEC | -13.16 |
| TST | -17.06 |
**q0.001_stop2p0_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| HMSTR/TST | 14.68 |
| FOGO/MAVIA | 11.42 |
| FOGO/STABLE | 11.33 |
| FOGO/TON | 6.74 |
| AVAX/UNI | 6.32 |
| YZY/ZRO | 5.61 |
| CHILLGUY/MEGA | 4.98 |
| ADA/ASTER | 4.60 |
| ASTER/UNI | 4.48 |
| HMSTR/MAV | 4.08 |
**q0.001_stop2p0_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| CHILLGUY/W | -2.85 |
| DOT/XRP | -2.90 |
| EIGEN/MEGA | -2.92 |
| CHILLGUY/NIL | -3.32 |
| TST/WLFI | -3.43 |
| YZY/ZEN | -4.16 |
| GMX/TST | -4.46 |
| JUP/TST | -5.70 |
| TST/XPL | -5.85 |
| MELANIA/TST | -5.89 |

**q0.001_stopnone_feetaker** -- top 10 coins:
| coin | net |
|---|---|
| FOGO | 58.43 |
| HMSTR | 45.39 |
| TST | 37.80 |
| ASTER | 27.96 |
| ZRO | 22.35 |
| MEGA | 18.85 |
| GMX | 14.93 |
| NOT | 14.49 |
| XRP | 14.19 |
| CHILLGUY | 13.82 |
**q0.001_stopnone_feetaker** -- bottom 10 coins:
| coin | net |
|---|---|
| GRASS | -10.90 |
| kPEPE | -12.18 |
| INIT | -13.57 |
| VVV | -16.08 |
| ZK | -16.55 |
| SAGA | -17.48 |
| TAO | -18.68 |
| VINE | -19.50 |
| ZEC | -24.63 |
| DYM | -26.27 |
**q0.001_stopnone_feetaker** -- top 10 pairs:
| pair | net |
|---|---|
| FOGO/MAVIA | 16.01 |
| HMSTR/TST | 15.04 |
| MELANIA/TST | 12.03 |
| FOGO/STABLE | 11.60 |
| JUP/TST | 10.56 |
| CHILLGUY/FOGO | 8.52 |
| FOGO/TON | 6.87 |
| GMX/TST | 6.34 |
| AVAX/UNI | 6.14 |
| YZY/ZRO | 5.95 |
**q0.001_stopnone_feetaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| TST/ZEREBRO | -5.41 |
| TNSR/XPL | -5.64 |
| HYPE/PURR | -5.84 |
| ANIME/SOL | -7.89 |
| MEW/ZK | -8.78 |
| GRASS/JUP | -9.27 |
| ORDI/ZK | -9.46 |
| DOOD/INIT | -14.13 |
| SAGA/VVV | -16.08 |
| TAO/kPEPE | -16.23 |

**q0.001_stopnone_feemaker** -- top 10 coins:
| coin | net |
|---|---|
| FOGO | 60.66 |
| HMSTR | 49.19 |
| TST | 40.32 |
| ASTER | 29.51 |
| ZRO | 24.95 |
| MEGA | 20.43 |
| NOT | 16.34 |
| GMX | 16.00 |
| XRP | 15.40 |
| CHILLGUY | 15.02 |
**q0.001_stopnone_feemaker** -- bottom 10 coins:
| coin | net |
|---|---|
| GRASS | -10.88 |
| kPEPE | -11.88 |
| INIT | -13.73 |
| VVV | -16.02 |
| ZK | -16.62 |
| SAGA | -17.34 |
| TAO | -18.50 |
| VINE | -18.72 |
| ZEC | -23.88 |
| DYM | -25.96 |
**q0.001_stopnone_feemaker** -- top 10 pairs:
| pair | net |
|---|---|
| FOGO/MAVIA | 16.42 |
| HMSTR/TST | 15.53 |
| MELANIA/TST | 12.45 |
| FOGO/STABLE | 11.79 |
| JUP/TST | 10.94 |
| CHILLGUY/FOGO | 8.68 |
| FOGO/TON | 7.02 |
| GMX/TST | 6.61 |
| AVAX/UNI | 6.51 |
| YZY/ZRO | 6.25 |
**q0.001_stopnone_feemaker** -- bottom 10 pairs:
| pair | net |
|---|---|
| TST/ZEREBRO | -5.34 |
| TNSR/XPL | -5.74 |
| HYPE/PURR | -5.94 |
| ANIME/SOL | -7.91 |
| MEW/ZK | -8.95 |
| GRASS/JUP | -9.43 |
| ORDI/ZK | -9.72 |
| DOOD/INIT | -14.49 |
| SAGA/VVV | -16.02 |
| TAO/kPEPE | -16.41 |

### Drawdown and distance to liquidation, per run
| q | stop | fee | max_dd_usd | max_dd_pct | dd_start | dd_bottom | dd_recovery | longest_underwater_days | min_dist_ratio | median_dist_ratio | date_of_min |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.01 | 0p5 | taker | -293.16 | -0.2932 | 2025-12-20 | 2026-07-11 | None | 203 | 2.1225 | 12.2546 | 2026-03-16 |
| 0.01 | 0p5 | maker | -118.80 | -0.1101 | 2026-02-09 | 2026-04-19 | None | 152 | 2.1210 | 12.2441 | 2026-03-16 |
| 0.01 | 1p0 | taker | -218.85 | -0.2188 | 2025-12-20 | 2026-07-11 | None | 203 | 2.0978 | 11.0781 | 2026-03-16 |
| 0.01 | 1p0 | maker | -138.61 | -0.1181 | 2026-02-09 | 2026-04-18 | 2026-06-28 | 138 | 2.0972 | 10.9276 | 2026-03-16 |
| 0.01 | 2p0 | taker | -215.13 | -0.1900 | 2026-02-09 | 2026-07-11 | None | 152 | 2.0978 | 9.4556 | 2026-03-16 |
| 0.01 | 2p0 | maker | -140.95 | -0.1052 | 2026-03-28 | 2026-04-18 | 2026-05-03 | 67 | 2.1037 | 9.3701 | 2026-03-16 |
| 0.01 | none | taker | -292.64 | -0.2154 | 2026-02-11 | 2026-04-05 | 2026-05-03 | 80 | 2.0738 | 6.0875 | 2026-01-02 |
| 0.01 | none | maker | -314.23 | -0.1987 | 2026-02-11 | 2026-02-15 | 2026-04-24 | 71 | 2.0755 | 6.0150 | 2026-01-02 |
| 0.005 | 0p5 | taker | -125.91 | -0.1259 | 2025-12-20 | 2026-05-02 | None | 203 | 2.1384 | 19.9980 | 2026-02-22 |
| 0.005 | 0p5 | maker | -65.48 | -0.0609 | 2026-02-09 | 2026-05-02 | 2026-06-24 | 134 | 2.1394 | 19.9993 | 2026-02-22 |
| 0.005 | 1p0 | taker | -93.32 | -0.0875 | 2026-02-09 | 2026-05-02 | None | 152 | 2.1337 | 19.8729 | 2026-02-22 |
| 0.005 | 1p0 | maker | -53.69 | -0.0461 | 2026-02-09 | 2026-04-18 | 2026-05-04 | 83 | 2.1347 | 19.8618 | 2026-02-22 |
| 0.005 | 2p0 | taker | -115.40 | -0.1020 | 2026-04-16 | 2026-04-18 | None | 86 | 2.1323 | 16.1811 | 2026-02-22 |
| 0.005 | 2p0 | maker | -122.13 | -0.0946 | 2026-04-16 | 2026-04-18 | 2026-05-04 | 45 | 2.1333 | 16.1869 | 2026-02-22 |
| 0.005 | none | taker | -191.11 | -0.1398 | 2026-02-11 | 2026-03-22 | 2026-04-20 | 67 | 2.0973 | 11.6323 | 2026-02-15 |
| 0.005 | none | maker | -186.11 | -0.1240 | 2026-02-11 | 2026-03-22 | 2026-04-17 | 64 | 2.0984 | 11.7421 | 2026-02-15 |
| 0.001 | 0p5 | taker | -37.70 | -0.0372 | 2026-01-29 | 2026-05-03 | None | 163 | 3.6926 | 39.8905 | 2026-02-22 |
| 0.001 | 0p5 | maker | -22.78 | -0.0221 | 2026-01-29 | 2026-04-18 | 2026-07-08 | 159 | 3.6936 | 39.8923 | 2026-02-22 |
| 0.001 | 1p0 | taker | -20.88 | -0.0208 | 2025-12-23 | 2025-12-31 | 2026-01-02 | 86 | 3.6895 | 39.8013 | 2026-02-22 |
| 0.001 | 1p0 | maker | -17.14 | -0.0161 | 2026-04-16 | 2026-04-18 | 2026-06-22 | 66 | 3.6905 | 39.8031 | 2026-02-22 |
| 0.001 | 2p0 | taker | -39.32 | -0.0376 | 2026-04-16 | 2026-04-19 | None | 86 | 3.6873 | 39.6664 | 2026-02-22 |
| 0.001 | 2p0 | maker | -39.31 | -0.0366 | 2026-04-16 | 2026-04-19 | 2026-06-19 | 63 | 3.6883 | 39.6682 | 2026-02-22 |
| 0.001 | none | taker | -51.47 | -0.0462 | 2026-02-10 | 2026-04-06 | 2026-04-17 | 65 | 2.5586 | 38.4163 | 2025-12-31 |
| 0.001 | none | maker | -45.32 | -0.0399 | 2026-02-10 | 2026-04-06 | 2026-04-16 | 64 | 2.5607 | 38.4180 | 2025-12-31 |

### Monthly (fold) total P&L, per run
All 7 test blocks start/end exactly at 00:00:00 UTC (not mid-day). "outside" is the exit spill after fold 7's nominal end; sum(fold totals) + outside reconciles to final_equity - start to 1e-6 (asserted in the generator).

**q0.01_stop0p5_feetaker** (n_months_positive=0/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | -80.44 | -0.0804 |
| 2 | 30 | -42.63 | -0.0464 |
| 3 | 30 | -31.90 | -0.0364 |
| 4 | 30 | -88.90 | -0.1052 |
| 5 | 30 | -14.20 | -0.0188 |
| 6 | 30 | -10.52 | -0.0142 |
| 7 | 23 | -24.57 | -0.0336 |
| outside | 0 | 0.00 | n/a |

**q0.01_stop0p5_feemaker** (n_months_positive=5/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 18.66 | 0.0187 |
| 2 | 30 | 34.66 | 0.0340 |
| 3 | 30 | -19.44 | -0.0185 |
| 4 | 30 | -73.93 | -0.0715 |
| 5 | 30 | 47.02 | 0.0490 |
| 6 | 30 | 7.27 | 0.0072 |
| 7 | 23 | 5.20 | 0.0051 |
| outside | 0 | 0.00 | n/a |

**q0.01_stop1p0_feetaker** (n_months_positive=1/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | -66.46 | -0.0665 |
| 2 | 30 | -0.97 | -0.0010 |
| 3 | 30 | -37.25 | -0.0399 |
| 4 | 30 | -81.88 | -0.0915 |
| 5 | 30 | 2.81 | 0.0034 |
| 6 | 30 | -7.17 | -0.0088 |
| 7 | 23 | -27.93 | -0.0345 |
| outside | 0 | 0.00 | n/a |

**q0.01_stop1p0_feemaker** (n_months_positive=5/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 45.21 | 0.0452 |
| 2 | 30 | 88.84 | 0.0850 |
| 3 | 30 | -26.82 | -0.0237 |
| 4 | 30 | -62.72 | -0.0567 |
| 5 | 30 | 77.66 | 0.0743 |
| 6 | 30 | 16.87 | 0.0150 |
| 7 | 23 | 7.12 | 0.0062 |
| outside | 0 | 0.00 | n/a |

**q0.01_stop2p0_feetaker** (n_months_positive=3/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 74.85 | 0.0748 |
| 2 | 30 | 35.08 | 0.0326 |
| 3 | 30 | -44.59 | -0.0402 |
| 4 | 30 | -124.26 | -0.1166 |
| 5 | 30 | 58.45 | 0.0621 |
| 6 | 30 | -19.64 | -0.0196 |
| 7 | 23 | -62.54 | -0.0638 |
| outside | 0 | 0.00 | n/a |

**q0.01_stop2p0_feemaker** (n_months_positive=4/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 198.61 | 0.1986 |
| 2 | 30 | 139.23 | 0.1162 |
| 3 | 30 | -26.74 | -0.0200 |
| 4 | 30 | -94.32 | -0.0719 |
| 5 | 30 | 172.49 | 0.1418 |
| 6 | 30 | 3.76 | 0.0027 |
| 7 | 23 | -37.32 | -0.0268 |
| outside | 0 | 0.00 | n/a |

**q0.01_stopnone_feetaker** (n_months_positive=4/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 226.54 | 0.2265 |
| 2 | 30 | -62.61 | -0.0510 |
| 3 | 30 | -82.41 | -0.0708 |
| 4 | 30 | 69.51 | 0.0643 |
| 5 | 30 | 291.57 | 0.2533 |
| 6 | 30 | -28.57 | -0.0198 |
| 7 | 23 | 170.78 | 0.1208 |
| outside | 1 | 6.16 | n/a |

**q0.01_stopnone_feemaker** (n_months_positive=5/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 378.54 | 0.3785 |
| 2 | 30 | -2.14 | -0.0016 |
| 3 | 30 | -72.52 | -0.0527 |
| 4 | 30 | 161.11 | 0.1236 |
| 5 | 30 | 499.24 | 0.3408 |
| 6 | 30 | 7.44 | 0.0038 |
| 7 | 23 | 353.39 | 0.1792 |
| outside | 1 | 9.65 | n/a |

**q0.005_stop0p5_feetaker** (n_months_positive=2/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | -22.19 | -0.0222 |
| 2 | 30 | -12.10 | -0.0124 |
| 3 | 30 | -18.53 | -0.0192 |
| 4 | 30 | -56.48 | -0.0596 |
| 5 | 30 | -9.25 | -0.0104 |
| 6 | 30 | 4.42 | 0.0050 |
| 7 | 23 | 16.22 | 0.0183 |
| outside | 0 | 0.00 | n/a |

**q0.005_stop0p5_feemaker** (n_months_positive=5/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 41.22 | 0.0412 |
| 2 | 30 | 27.02 | 0.0260 |
| 3 | 30 | -9.54 | -0.0089 |
| 4 | 30 | -45.93 | -0.0434 |
| 5 | 30 | 22.50 | 0.0222 |
| 6 | 30 | 16.34 | 0.0158 |
| 7 | 23 | 41.45 | 0.0394 |
| outside | 0 | 0.00 | n/a |

**q0.005_stop1p0_feetaker** (n_months_positive=5/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 13.17 | 0.0132 |
| 2 | 30 | 30.50 | 0.0301 |
| 3 | 30 | -18.98 | -0.0182 |
| 4 | 30 | -48.33 | -0.0472 |
| 5 | 30 | 8.55 | 0.0088 |
| 6 | 30 | 5.95 | 0.0060 |
| 7 | 23 | 25.27 | 0.0255 |
| outside | 0 | 0.00 | n/a |

**q0.005_stop1p0_feemaker** (n_months_positive=5/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 78.45 | 0.0785 |
| 2 | 30 | 77.75 | 0.0721 |
| 3 | 30 | -9.70 | -0.0084 |
| 4 | 30 | -33.89 | -0.0296 |
| 5 | 30 | 44.67 | 0.0402 |
| 6 | 30 | 19.30 | 0.0167 |
| 7 | 23 | 55.58 | 0.0472 |
| outside | 0 | 0.00 | n/a |

**q0.005_stop2p0_feetaker** (n_months_positive=5/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 69.82 | 0.0698 |
| 2 | 30 | 57.24 | 0.0535 |
| 3 | 30 | -21.31 | -0.0189 |
| 4 | 30 | -88.32 | -0.0799 |
| 5 | 30 | 39.85 | 0.0392 |
| 6 | 30 | 6.77 | 0.0064 |
| 7 | 23 | 24.00 | 0.0226 |
| outside | 0 | 0.00 | n/a |

**q0.005_stop2p0_feemaker** (n_months_positive=5/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 138.19 | 0.1382 |
| 2 | 30 | 108.94 | 0.0957 |
| 3 | 30 | -11.00 | -0.0088 |
| 4 | 30 | -65.34 | -0.0529 |
| 5 | 30 | 87.69 | 0.0749 |
| 6 | 30 | 21.94 | 0.0174 |
| 7 | 23 | 55.35 | 0.0432 |
| outside | 0 | 0.00 | n/a |

**q0.005_stopnone_feetaker** (n_months_positive=6/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 224.24 | 0.2242 |
| 2 | 30 | 40.21 | 0.0328 |
| 3 | 30 | -77.20 | -0.0611 |
| 4 | 30 | 163.52 | 0.1377 |
| 5 | 30 | 128.23 | 0.0949 |
| 6 | 30 | 32.30 | 0.0218 |
| 7 | 23 | 160.85 | 0.1064 |
| outside | 1 | 6.51 | n/a |

**q0.005_stopnone_feemaker** (n_months_positive=6/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 298.49 | 0.2985 |
| 2 | 30 | 98.61 | 0.0759 |
| 3 | 30 | -71.79 | -0.0514 |
| 4 | 30 | 208.95 | 0.1577 |
| 5 | 30 | 203.31 | 0.1325 |
| 6 | 30 | 57.42 | 0.0330 |
| 7 | 23 | 232.38 | 0.1295 |
| outside | 1 | 8.43 | n/a |

**q0.001_stop0p5_feetaker** (n_months_positive=3/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 6.89 | 0.0069 |
| 2 | 30 | -1.47 | -0.0015 |
| 3 | 30 | -4.77 | -0.0047 |
| 4 | 30 | -20.38 | -0.0204 |
| 5 | 30 | -3.99 | -0.0041 |
| 6 | 30 | 5.00 | 0.0051 |
| 7 | 23 | 8.72 | 0.0089 |
| outside | 0 | 0.00 | n/a |

**q0.001_stop0p5_feemaker** (n_months_positive=5/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 22.05 | 0.0220 |
| 2 | 30 | 4.52 | 0.0044 |
| 3 | 30 | -1.77 | -0.0017 |
| 4 | 30 | -16.91 | -0.0165 |
| 5 | 30 | 3.49 | 0.0035 |
| 6 | 30 | 6.52 | 0.0064 |
| 7 | 23 | 12.74 | 0.0125 |
| outside | 0 | 0.00 | n/a |

**q0.001_stop1p0_feetaker** (n_months_positive=4/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 17.22 | 0.0172 |
| 2 | 30 | 10.64 | 0.0105 |
| 3 | 30 | -1.19 | -0.0012 |
| 4 | 30 | -7.36 | -0.0072 |
| 5 | 30 | -1.40 | -0.0014 |
| 6 | 30 | 4.47 | 0.0044 |
| 7 | 23 | 12.22 | 0.0120 |
| outside | 0 | 0.00 | n/a |

**q0.001_stop1p0_feemaker** (n_months_positive=6/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 32.54 | 0.0325 |
| 2 | 30 | 16.95 | 0.0164 |
| 3 | 30 | 1.97 | 0.0019 |
| 4 | 30 | -3.42 | -0.0032 |
| 5 | 30 | 6.47 | 0.0062 |
| 6 | 30 | 6.02 | 0.0057 |
| 7 | 23 | 16.54 | 0.0156 |
| outside | 0 | 0.00 | n/a |

**q0.001_stop2p0_feetaker** (n_months_positive=5/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 14.12 | 0.0141 |
| 2 | 30 | 12.30 | 0.0121 |
| 3 | 30 | -3.55 | -0.0035 |
| 4 | 30 | -16.68 | -0.0163 |
| 5 | 30 | 21.75 | 0.0216 |
| 6 | 30 | 5.96 | 0.0058 |
| 7 | 23 | 8.17 | 0.0079 |
| outside | 0 | 0.00 | n/a |

**q0.001_stop2p0_feemaker** (n_months_positive=5/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 29.39 | 0.0294 |
| 2 | 30 | 18.63 | 0.0181 |
| 3 | 30 | -0.46 | -0.0004 |
| 4 | 30 | -13.01 | -0.0124 |
| 5 | 30 | 30.34 | 0.0293 |
| 6 | 30 | 7.59 | 0.0071 |
| 7 | 23 | 12.37 | 0.0115 |
| outside | 0 | 0.00 | n/a |

**q0.001_stopnone_feetaker** (n_months_positive=6/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 79.66 | 0.0797 |
| 2 | 30 | 14.81 | 0.0137 |
| 3 | 30 | -22.22 | -0.0203 |
| 4 | 30 | 65.60 | 0.0612 |
| 5 | 30 | 4.66 | 0.0041 |
| 6 | 30 | 8.58 | 0.0075 |
| 7 | 23 | 11.14 | 0.0097 |
| outside | 1 | 2.07 | n/a |

**q0.001_stopnone_feemaker** (n_months_positive=6/7):
| fold | n_days | total_pnl_usd | total_pnl_pct |
|---|---|---|---|
| 1 | 30 | 95.32 | 0.0953 |
| 2 | 30 | 21.66 | 0.0198 |
| 3 | 30 | -19.25 | -0.0172 |
| 4 | 30 | 71.69 | 0.0653 |
| 5 | 30 | 13.65 | 0.0117 |
| 6 | 30 | 10.46 | 0.0088 |
| 7 | 23 | 16.05 | 0.0135 |
| outside | 1 | 2.21 | n/a |

### EV check (stop=none only; fold 1 not scored, no earlier test month to fit on)
EV quintiles rank realised net monotonically (quintile 0 to 4 non-decreasing) in 0/6 tables (e.g. q0.01_feetaker: quintile 1 mean_realised_net=0.5007 is above quintile 2's 0.3238). EV here is descriptive only -- it does not rank realised net in these tables, and no claim that it predicts profit should be drawn from this table.

**q0.01_feetaker** (n_scored=2434):
| quintile | n | mean_ev | mean_realised_net |
|---|---|---|---|
| 0 | 487 | 0.5632 | -0.0239 |
| 1 | 502 | 0.6610 | 0.5007 |
| 2 | 509 | 0.7856 | 0.3238 |
| 3 | 587 | 0.9255 | -0.1574 |
| 4 | 349 | 1.1536 | 0.1540 |

**q0.01_feemaker** (n_scored=2465):
| quintile | n | mean_ev | mean_realised_net |
|---|---|---|---|
| 0 | 621 | 0.7841 | 0.5332 |
| 1 | 389 | 0.9112 | 0.5971 |
| 2 | 486 | 1.0195 | 0.5089 |
| 3 | 533 | 1.1445 | -0.0104 |
| 4 | 436 | 1.3600 | 0.3501 |

**q0.005_feetaker** (n_scored=1330):
| quintile | n | mean_ev | mean_realised_net |
|---|---|---|---|
| 0 | 276 | 0.7419 | 0.4743 |
| 1 | 347 | 0.8546 | 0.5945 |
| 2 | 242 | 0.9407 | 0.1095 |
| 3 | 273 | 1.0158 | 0.0144 |
| 4 | 192 | 1.2412 | 0.4600 |

**q0.005_feemaker** (n_scored=1343):
| quintile | n | mean_ev | mean_realised_net |
|---|---|---|---|
| 0 | 270 | 0.9180 | 0.6666 |
| 1 | 311 | 1.0311 | 0.8409 |
| 2 | 233 | 1.1092 | 0.5409 |
| 3 | 318 | 1.1735 | 0.0657 |
| 4 | 211 | 1.4144 | 0.7129 |

**q0.001_feetaker** (n_scored=257):
| quintile | n | mean_ev | mean_realised_net |
|---|---|---|---|
| 0 | 57 | 0.8600 | 0.5064 |
| 1 | 52 | 0.9780 | 1.2513 |
| 2 | 55 | 1.0352 | -0.2260 |
| 3 | 78 | 1.1804 | 0.0935 |
| 4 | 15 | 1.3138 | -0.2771 |

**q0.001_feemaker** (n_scored=258):
| quintile | n | mean_ev | mean_realised_net |
|---|---|---|---|
| 0 | 58 | 0.9835 | 0.6273 |
| 1 | 52 | 1.1017 | 1.3999 |
| 2 | 55 | 1.1572 | -0.1124 |
| 3 | 77 | 1.3006 | 0.2628 |
| 4 | 16 | 1.4322 | -0.4218 |

### cost-share diagnostic (OVERLAPPING accounts across the 24 runs, not a combined P&L)
n_trades=47,656 gross=10,056.02 fee=5,151.97 funding_net=34.66 net=4,869.39 fee_share_of_gross=0.5123

### Known gaps
- slippage excluded by the user's choice (legs are small); costs are a lower bound and results an upper bound (optimistic).
- max_leverage is today's snapshot (hindsight); limits were different in the past.
- liquidation is checked on 1-minute closes; a move inside a minute can liquidate earlier.
- maker fills are assumed to fill; in practice they may not.
- the test months were already used for the cut-off, the deep dive and the calibration: results are optimistic until the vault or paper-trading check.
- in-sample: the |z| >= 3.0 threshold was chosen after seeing these test months' results; these numbers are not evidence for the rule until the vault or paper-trading check.

### Equity curve PNGs
- research/dislocation_model/logs/s1_profit1_equity_q0.01_feetaker_z3_open20.png
- research/dislocation_model/logs/s1_profit1_equity_q0.01_feemaker_z3_open20.png
- research/dislocation_model/logs/s1_profit1_equity_q0.005_feetaker_z3_open20.png
- research/dislocation_model/logs/s1_profit1_equity_q0.005_feemaker_z3_open20.png
- research/dislocation_model/logs/s1_profit1_equity_q0.001_feetaker_z3_open20.png
- research/dislocation_model/logs/s1_profit1_equity_q0.001_feemaker_z3_open20.png