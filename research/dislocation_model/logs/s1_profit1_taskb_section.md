
## [HL-PROFIT1 taskB] |z| x p_cal descriptive grid, max_open=10, stop=none runs (DESCRIPTIVE ONLY -- no filter or rule chosen here)

distance = |z| (sigma, known at entry); probability = p_cal_10h; return per trade = net/notional; win_rate = share exit_reason==mu; profit_factor on net$.

**Any threshold read off this table needs the vault or paper-trading check before it means anything -- the test months already drove the cutoff, the deep dive and the calibration upstream of this same data.**

### Monotonicity across the 6 runs (script-counted, not eyeballed)
| measure | direction | monotone q0->q4 | top quintile has the highest value |
|---|---|---|---|
| abs_z_win_rate | decreasing q0->q4 | 2/6 | n/a |
| abs_z_mean_return | increasing q0->q4 | 0/6 | 6/6 |
| abs_z_median_return | increasing q0->q4 | 4/6 | 6/6 |
| p_cal_win_rate | increasing q0->q4 | 2/6 | n/a |
| p_cal_mean_return | increasing q0->q4 | 0/6 | 6/6 |
| p_cal_median_return | increasing q0->q4 | 0/6 | 0/6 |

### q0.01_stopnone_feetaker (n_trades=8,078)

|z| quintiles:
| quintile | range | n | win_rate | mean_return | median_return | profit_factor |
|---|---|---|---|---|---|---|
| 0 | [0.519, 1.518] | 1616 | 0.7772 | 0.0003 | 0.0026 | 1.0901 |
| 1 | [1.518, 1.829] | 1615 | 0.7319 | 0.0006 | 0.0032 | 1.1296 |
| 2 | [1.829, 2.131] | 1616 | 0.7147 | 0.0009 | 0.0037 | 1.2746 |
| 3 | [2.131, 2.563] | 1615 | 0.6916 | 0.0006 | 0.0040 | 1.1015 |
| 4 | [2.563, 8.108] | 1616 | 0.6170 | 0.0013 | 0.0050 | 1.2293 |

p_cal_10h quintiles:
| quintile | range | n | win_rate | mean_return | median_return | profit_factor |
|---|---|---|---|---|---|---|
| 0 | [0.6250, 0.6559] | 1785 | 0.6706 | 0.0007 | 0.0034 | 1.1591 |
| 1 | [0.6559, 0.6832] | 1636 | 0.6993 | 0.0007 | 0.0035 | 1.2090 |
| 2 | [0.6832, 0.6953] | 1474 | 0.7130 | 0.0008 | 0.0035 | 1.1907 |
| 3 | [0.6953, 0.7177] | 1655 | 0.7057 | 0.0006 | 0.0034 | 1.1179 |
| 4 | [0.7177, 0.8966] | 1528 | 0.7507 | 0.0010 | 0.0035 | 1.1766 |

5x5 grid (|z| quintile x p_cal quintile):
| |z| q \ p_cal q | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| 0 | n=375 wr=0.76 mret=0.000 pf=1.18 | n=374 wr=0.77 mret=0.000 pf=1.10 | n=298 wr=0.78 mret=0.000 pf=1.06 | n=317 wr=0.78 mret=-0.000 pf=1.00 | n=252 wr=0.81 mret=0.001 pf=1.09 |
| 1 | n=370 wr=0.75 mret=0.001 pf=1.46 | n=332 wr=0.73 mret=0.001 pf=1.16 | n=292 wr=0.72 mret=0.000 pf=1.02 | n=315 wr=0.70 mret=-0.000 pf=0.92 | n=306 wr=0.77 mret=0.001 pf=1.03 |
| 2 | n=328 wr=0.69 mret=0.001 pf=1.33 | n=319 wr=0.70 mret=0.001 pf=1.14 | n=302 wr=0.69 mret=0.000 pf=1.06 | n=335 wr=0.74 mret=0.002 pf=1.81 | n=332 wr=0.76 mret=0.001 pf=1.17 |
| 3 | n=375 wr=0.60 mret=0.000 pf=0.94 | n=315 wr=0.68 mret=0.000 pf=1.16 | n=289 wr=0.71 mret=0.001 pf=1.47 | n=324 wr=0.72 mret=0.000 pf=0.99 | n=312 wr=0.77 mret=0.001 pf=1.18 |
| 4 | n=337 wr=0.55 mret=0.001 pf=1.09 | n=296 wr=0.61 mret=0.002 pf=1.43 | n=293 wr=0.67 mret=0.002 pf=1.32 | n=364 wr=0.60 mret=0.001 pf=1.10 | n=326 wr=0.67 mret=0.002 pf=1.33 |

### q0.01_stopnone_feemaker (n_trades=8,069)

|z| quintiles:
| quintile | range | n | win_rate | mean_return | median_return | profit_factor |
|---|---|---|---|---|---|---|
| 0 | [0.519, 1.513] | 1614 | 0.7844 | 0.0010 | 0.0032 | 1.3599 |
| 1 | [1.513, 1.822] | 1614 | 0.7274 | 0.0013 | 0.0038 | 1.4006 |
| 2 | [1.822, 2.126] | 1613 | 0.7241 | 0.0016 | 0.0043 | 1.5207 |
| 3 | [2.126, 2.547] | 1614 | 0.6952 | 0.0012 | 0.0046 | 1.2688 |
| 4 | [2.547, 8.108] | 1614 | 0.6097 | 0.0017 | 0.0055 | 1.3418 |

p_cal_10h quintiles:
| quintile | range | n | win_rate | mean_return | median_return | profit_factor |
|---|---|---|---|---|---|---|
| 0 | [0.6250, 0.6559] | 1795 | 0.6813 | 0.0014 | 0.0041 | 1.3942 |
| 1 | [0.6559, 0.6832] | 1640 | 0.7024 | 0.0013 | 0.0041 | 1.4236 |
| 2 | [0.6832, 0.6953] | 1474 | 0.7056 | 0.0012 | 0.0040 | 1.3527 |
| 3 | [0.6953, 0.7177] | 1646 | 0.7047 | 0.0013 | 0.0040 | 1.3203 |
| 4 | [0.7177, 1.0000] | 1514 | 0.7523 | 0.0015 | 0.0040 | 1.3234 |

5x5 grid (|z| quintile x p_cal quintile):
| |z| q \ p_cal q | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| 0 | n=372 wr=0.78 mret=0.001 pf=1.57 | n=372 wr=0.77 mret=0.001 pf=1.36 | n=296 wr=0.77 mret=0.001 pf=1.23 | n=327 wr=0.77 mret=0.001 pf=1.20 | n=247 wr=0.83 mret=0.002 pf=1.35 |
| 1 | n=392 wr=0.74 mret=0.002 pf=1.78 | n=330 wr=0.73 mret=0.001 pf=1.54 | n=295 wr=0.72 mret=0.001 pf=1.28 | n=308 wr=0.68 mret=0.001 pf=1.15 | n=289 wr=0.76 mret=0.001 pf=1.09 |
| 2 | n=329 wr=0.70 mret=0.002 pf=1.65 | n=331 wr=0.71 mret=0.002 pf=1.37 | n=297 wr=0.69 mret=0.001 pf=1.18 | n=319 wr=0.75 mret=0.002 pf=2.18 | n=337 wr=0.77 mret=0.002 pf=1.42 |
| 3 | n=367 wr=0.63 mret=0.001 pf=1.14 | n=322 wr=0.67 mret=0.000 pf=1.27 | n=291 wr=0.70 mret=0.002 pf=1.83 | n=325 wr=0.71 mret=0.001 pf=1.20 | n=309 wr=0.77 mret=0.001 pf=1.22 |
| 4 | n=335 wr=0.54 mret=0.001 pf=1.20 | n=285 wr=0.60 mret=0.002 pf=1.59 | n=295 wr=0.64 mret=0.002 pf=1.34 | n=367 wr=0.62 mret=0.002 pf=1.22 | n=332 wr=0.65 mret=0.002 pf=1.51 |

### q0.005_stopnone_feetaker (n_trades=6,587)

|z| quintiles:
| quintile | range | n | win_rate | mean_return | median_return | profit_factor |
|---|---|---|---|---|---|---|
| 0 | [0.519, 1.528] | 1318 | 0.7914 | 0.0006 | 0.0026 | 1.2022 |
| 1 | [1.528, 1.837] | 1317 | 0.7304 | 0.0005 | 0.0032 | 1.0779 |
| 2 | [1.837, 2.138] | 1317 | 0.7365 | 0.0011 | 0.0038 | 1.3484 |
| 3 | [2.138, 2.578] | 1317 | 0.6940 | 0.0001 | 0.0039 | 1.0057 |
| 4 | [2.578, 7.511] | 1318 | 0.6297 | 0.0016 | 0.0050 | 1.2655 |

p_cal_10h quintiles:
| quintile | range | n | win_rate | mean_return | median_return | profit_factor |
|---|---|---|---|---|---|---|
| 0 | [0.6487, 0.6806] | 1333 | 0.6999 | 0.0007 | 0.0034 | 1.1898 |
| 1 | [0.6806, 0.6953] | 1533 | 0.7032 | 0.0006 | 0.0034 | 1.1393 |
| 2 | [0.6953, 0.7026] | 1281 | 0.7034 | 0.0007 | 0.0036 | 1.1385 |
| 3 | [0.7026, 0.7350] | 1147 | 0.7245 | 0.0006 | 0.0033 | 1.1072 |
| 4 | [0.7350, 0.8966] | 1293 | 0.7548 | 0.0013 | 0.0036 | 1.3225 |

5x5 grid (|z| quintile x p_cal quintile):
| |z| q \ p_cal q | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| 0 | n=315 wr=0.79 mret=0.001 pf=1.42 | n=311 wr=0.80 mret=0.001 pf=1.30 | n=260 wr=0.73 mret=-0.001 pf=0.73 | n=203 wr=0.82 mret=0.000 pf=1.21 | n=229 wr=0.83 mret=0.002 pf=1.58 |
| 1 | n=275 wr=0.75 mret=0.001 pf=1.07 | n=317 wr=0.71 mret=-0.000 pf=0.95 | n=263 wr=0.71 mret=0.000 pf=1.05 | n=191 wr=0.70 mret=-0.000 pf=0.95 | n=271 wr=0.79 mret=0.002 pf=1.55 |
| 2 | n=245 wr=0.71 mret=0.001 pf=1.36 | n=301 wr=0.66 mret=-0.000 pf=0.92 | n=250 wr=0.73 mret=0.002 pf=1.62 | n=255 wr=0.80 mret=0.002 pf=1.77 | n=266 wr=0.80 mret=0.002 pf=1.43 |
| 3 | n=258 wr=0.65 mret=-0.000 pf=0.95 | n=304 wr=0.68 mret=0.001 pf=1.16 | n=238 wr=0.72 mret=0.000 pf=1.00 | n=250 wr=0.70 mret=0.000 pf=0.94 | n=267 wr=0.72 mret=0.000 pf=1.00 |
| 4 | n=240 wr=0.57 mret=0.001 pf=1.31 | n=300 wr=0.67 mret=0.002 pf=1.38 | n=270 wr=0.63 mret=0.002 pf=1.39 | n=248 wr=0.61 mret=0.000 pf=0.98 | n=260 wr=0.65 mret=0.002 pf=1.34 |

### q0.005_stopnone_feemaker (n_trades=6,595)

|z| quintiles:
| quintile | range | n | win_rate | mean_return | median_return | profit_factor |
|---|---|---|---|---|---|---|
| 0 | [0.519, 1.534] | 1319 | 0.7870 | 0.0012 | 0.0032 | 1.4186 |
| 1 | [1.534, 1.842] | 1319 | 0.7316 | 0.0009 | 0.0037 | 1.2175 |
| 2 | [1.842, 2.142] | 1319 | 0.7407 | 0.0019 | 0.0044 | 1.7588 |
| 3 | [2.142, 2.581] | 1319 | 0.7066 | 0.0009 | 0.0046 | 1.1774 |
| 4 | [2.581, 7.511] | 1319 | 0.6323 | 0.0024 | 0.0056 | 1.5044 |

p_cal_10h quintiles:
| quintile | range | n | win_rate | mean_return | median_return | profit_factor |
|---|---|---|---|---|---|---|
| 0 | [0.6487, 0.6806] | 1335 | 0.6981 | 0.0011 | 0.0040 | 1.3464 |
| 1 | [0.6806, 0.6953] | 1535 | 0.7049 | 0.0013 | 0.0041 | 1.4069 |
| 2 | [0.6953, 0.7026] | 1272 | 0.7052 | 0.0015 | 0.0042 | 1.4296 |
| 3 | [0.7026, 0.7350] | 1150 | 0.7304 | 0.0013 | 0.0039 | 1.2999 |
| 4 | [0.7350, 1.0000] | 1303 | 0.7636 | 0.0020 | 0.0042 | 1.5957 |

5x5 grid (|z| quintile x p_cal quintile):
| |z| q \ p_cal q | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| 0 | n=317 wr=0.78 mret=0.001 pf=1.61 | n=310 wr=0.79 mret=0.001 pf=1.46 | n=261 wr=0.74 mret=0.000 pf=0.94 | n=198 wr=0.83 mret=0.001 pf=1.44 | n=233 wr=0.82 mret=0.002 pf=1.67 |
| 1 | n=276 wr=0.74 mret=0.001 pf=1.26 | n=321 wr=0.70 mret=0.000 pf=1.14 | n=254 wr=0.71 mret=0.000 pf=1.13 | n=197 wr=0.70 mret=0.000 pf=1.01 | n=271 wr=0.80 mret=0.002 pf=1.80 |
| 2 | n=243 wr=0.72 mret=0.002 pf=1.78 | n=303 wr=0.68 mret=0.001 pf=1.48 | n=247 wr=0.72 mret=0.002 pf=2.20 | n=261 wr=0.79 mret=0.003 pf=1.88 | n=265 wr=0.80 mret=0.002 pf=1.66 |
| 3 | n=259 wr=0.64 mret=-0.001 pf=0.88 | n=298 wr=0.69 mret=0.001 pf=1.41 | n=235 wr=0.75 mret=0.002 pf=1.70 | n=250 wr=0.73 mret=0.001 pf=1.21 | n=277 wr=0.73 mret=0.001 pf=1.19 |
| 4 | n=240 wr=0.58 mret=0.002 pf=1.64 | n=303 wr=0.67 mret=0.003 pf=1.55 | n=275 wr=0.62 mret=0.003 pf=1.50 | n=244 wr=0.61 mret=0.001 pf=1.18 | n=257 wr=0.67 mret=0.003 pf=1.85 |

### q0.001_stopnone_feetaker (n_trades=2,573)

|z| quintiles:
| quintile | range | n | win_rate | mean_return | median_return | profit_factor |
|---|---|---|---|---|---|---|
| 0 | [0.519, 1.554] | 515 | 0.8078 | 0.0009 | 0.0025 | 1.2244 |
| 1 | [1.554, 1.862] | 514 | 0.7607 | 0.0013 | 0.0033 | 1.3258 |
| 2 | [1.862, 2.150] | 515 | 0.7845 | 0.0017 | 0.0041 | 1.5323 |
| 3 | [2.150, 2.589] | 514 | 0.7160 | 0.0003 | 0.0039 | 1.0213 |
| 4 | [2.589, 7.473] | 515 | 0.6505 | 0.0018 | 0.0053 | 1.3267 |

p_cal_10h quintiles:
| quintile | range | n | win_rate | mean_return | median_return | profit_factor |
|---|---|---|---|---|---|---|
| 0 | [0.6962, 0.7193] | 615 | 0.7268 | 0.0006 | 0.0033 | 1.0740 |
| 1 | [0.7193, 0.7398] | 435 | 0.7747 | 0.0014 | 0.0035 | 1.3537 |
| 2 | [0.7398, 0.7685] | 730 | 0.7247 | 0.0014 | 0.0035 | 1.3608 |
| 3 | [0.7685, 0.7743] | 468 | 0.7479 | 0.0007 | 0.0042 | 1.2395 |
| 4 | [0.7743, 0.8966] | 325 | 0.7723 | 0.0023 | 0.0037 | 1.4581 |

5x5 grid (|z| quintile x p_cal quintile):
| |z| q \ p_cal q | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| 0 | n=133 wr=0.83 mret=0.001 pf=1.38 | n=77 wr=0.81 mret=0.000 pf=0.82 | n=142 wr=0.80 mret=0.001 pf=1.30 | n=102 wr=0.75 mret=-0.001 pf=0.82 | n=61 wr=0.89 mret=0.004 pf=3.67 |
| 1 | n=112 wr=0.71 mret=-0.000 pf=0.98 | n=82 wr=0.76 mret=-0.000 pf=0.87 | n=137 wr=0.81 mret=0.003 pf=2.73 | n=99 wr=0.74 mret=0.001 pf=1.68 | n=84 wr=0.79 mret=0.002 pf=1.20 |
| 2 | n=118 wr=0.75 mret=0.002 pf=1.41 | n=100 wr=0.84 mret=0.002 pf=1.51 | n=144 wr=0.80 mret=0.003 pf=2.15 | n=89 wr=0.80 mret=0.001 pf=1.43 | n=64 wr=0.72 mret=0.000 pf=0.98 |
| 3 | n=124 wr=0.70 mret=-0.001 pf=0.83 | n=95 wr=0.74 mret=0.002 pf=1.63 | n=150 wr=0.65 mret=-0.001 pf=0.73 | n=92 wr=0.78 mret=0.001 pf=1.38 | n=53 wr=0.79 mret=0.002 pf=1.38 |
| 4 | n=128 wr=0.64 mret=0.001 pf=1.06 | n=81 wr=0.73 mret=0.003 pf=1.99 | n=157 wr=0.59 mret=0.002 pf=1.33 | n=86 wr=0.67 mret=0.000 pf=1.16 | n=63 wr=0.68 mret=0.004 pf=1.54 |

### q0.001_stopnone_feemaker (n_trades=2,583)

|z| quintiles:
| quintile | range | n | win_rate | mean_return | median_return | profit_factor |
|---|---|---|---|---|---|---|
| 0 | [0.519, 1.557] | 517 | 0.8085 | 0.0016 | 0.0032 | 1.4810 |
| 1 | [1.557, 1.863] | 516 | 0.7713 | 0.0020 | 0.0039 | 1.6115 |
| 2 | [1.863, 2.152] | 517 | 0.7756 | 0.0021 | 0.0046 | 1.7125 |
| 3 | [2.152, 2.583] | 516 | 0.7093 | 0.0009 | 0.0045 | 1.1581 |
| 4 | [2.583, 7.473] | 517 | 0.6596 | 0.0027 | 0.0060 | 1.5212 |

p_cal_10h quintiles:
| quintile | range | n | win_rate | mean_return | median_return | profit_factor |
|---|---|---|---|---|---|---|
| 0 | [0.6962, 0.7193] | 620 | 0.7258 | 0.0011 | 0.0039 | 1.2053 |
| 1 | [0.7193, 0.7398] | 434 | 0.7742 | 0.0020 | 0.0041 | 1.5351 |
| 2 | [0.7398, 0.7685] | 733 | 0.7312 | 0.0022 | 0.0041 | 1.6506 |
| 3 | [0.7685, 0.7743] | 463 | 0.7473 | 0.0015 | 0.0048 | 1.4987 |
| 4 | [0.7743, 0.8966] | 333 | 0.7688 | 0.0029 | 0.0042 | 1.7215 |

5x5 grid (|z| quintile x p_cal quintile):
| |z| q \ p_cal q | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| 0 | n=134 wr=0.84 mret=0.001 pf=1.83 | n=77 wr=0.81 mret=0.001 pf=0.97 | n=147 wr=0.79 mret=0.002 pf=1.39 | n=99 wr=0.74 mret=0.000 pf=1.04 | n=60 wr=0.90 mret=0.005 pf=5.98 |
| 1 | n=111 wr=0.71 mret=0.001 pf=1.20 | n=80 wr=0.76 mret=0.000 pf=1.03 | n=139 wr=0.83 mret=0.004 pf=4.11 | n=102 wr=0.73 mret=0.002 pf=1.76 | n=84 wr=0.81 mret=0.003 pf=1.63 |
| 2 | n=121 wr=0.74 mret=0.002 pf=1.48 | n=100 wr=0.84 mret=0.002 pf=1.75 | n=143 wr=0.79 mret=0.003 pf=2.40 | n=88 wr=0.77 mret=0.001 pf=1.35 | n=65 wr=0.71 mret=0.002 pf=1.64 |
| 3 | n=124 wr=0.69 mret=-0.000 pf=0.89 | n=96 wr=0.73 mret=0.002 pf=1.77 | n=148 wr=0.64 mret=-0.001 pf=0.88 | n=91 wr=0.78 mret=0.002 pf=1.71 | n=57 wr=0.77 mret=0.002 pf=1.40 |
| 4 | n=130 wr=0.63 mret=0.001 pf=1.12 | n=81 wr=0.73 mret=0.004 pf=2.18 | n=156 wr=0.62 mret=0.003 pf=1.66 | n=83 wr=0.72 mret=0.003 pf=1.70 | n=67 wr=0.66 mret=0.003 pf=1.39 |

Full section (this file, all 6 runs' tables): research/dislocation_model/logs/s1_profit1_taskb_section.md
