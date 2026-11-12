
## [HL-VAULT1 iso25] VAULT (opened once, 2026-11-12): isotonic maps for 2 h and 5 h on the vault, calibration at 2/5/10 h next to S1-H's test months (script s1_vault_iso_2h5h.py)

Reported, not gated. The 2 h and 5 h maps are fitted on the pooled test-fold predictions of folds 0-7 with S1-H's guard at the horizon's own length (t0 + h <= vault start), the 10 h map is the existing p_cal_10h of step 4. Test-month columns are s1h_report.json (isotonic maps fitted per fold on earlier folds, scored on that fold's out-of-fold predictions); the vault is scored by the single pre-vault refit with one map fitted on folds 0-7. Different fits, so the two sides are not the same model. Deciles are the vault's own (cut-offs from the vault's raw p); the test deciles are the test months' own.

**2 h** -- all vault events: log loss raw 0.2328, calibrated 0.2291; Brier raw 0.0623, calibrated 0.0617. S1-H pooled test months: log loss raw 0.2411, isotonic 0.2387; Brier raw 0.0651, isotonic 0.0648. Calibrated values at exactly 0 or 1 on the vault: 84, contradicted by the label: 1.

| bucket | n | mean raw p | mean calibrated p | actual reach | actual - calibrated | test mean raw | test mean calibrated | test actual |
|---|---|---|---|---|---|---|---|---|
| decile 0 | 128,009 | 0.0242 | 0.0131 | 0.0125 | -0.0007 | 0.0254 | 0.0173 | 0.0111 |
| decile 1 | 128,009 | 0.0362 | 0.0197 | 0.0171 | -0.0026 | 0.0381 | 0.0257 | 0.0184 |
| decile 2 | 128,009 | 0.0445 | 0.0258 | 0.0235 | -0.0023 | 0.0470 | 0.0335 | 0.0252 |
| decile 3 | 128,008 | 0.0523 | 0.0336 | 0.0318 | -0.0018 | 0.0555 | 0.0423 | 0.0345 |
| decile 4 | 128,009 | 0.0603 | 0.0425 | 0.0418 | -0.0008 | 0.0643 | 0.0517 | 0.0451 |
| decile 5 | 128,009 | 0.0690 | 0.0538 | 0.0557 | +0.0019 | 0.0742 | 0.0644 | 0.0590 |
| decile 6 | 128,008 | 0.0793 | 0.0692 | 0.0725 | +0.0033 | 0.0858 | 0.0819 | 0.0773 |
| decile 7 | 128,009 | 0.0926 | 0.0911 | 0.0970 | +0.0059 | 0.1009 | 0.1053 | 0.1031 |
| decile 8 | 128,009 | 0.1124 | 0.1238 | 0.1365 | +0.0127 | 0.1239 | 0.1427 | 0.1416 |
| decile 9 | 128,009 | 0.1677 | 0.2084 | 0.2207 | +0.0123 | 0.1884 | 0.2295 | 0.2342 |
| all vault events | 1,280,088 | 0.0739 | 0.0681 | 0.0709 | +0.0028 | n/a | n/a | n/a |
| own top 1% by p_2h | 12,801 | 0.2696 | 0.3261 | 0.3429 | +0.0169 | n/a | n/a | n/a |
| Rule A picks q=0.01 | 13,947 | 0.2655 | 0.3218 | 0.3387 | +0.0169 | 0.2949 | 0.3423 | 0.3467 |
| Rule A picks q=0.005 | 7,188 | 0.2975 | 0.3540 | 0.3670 | +0.0130 | 0.3328 | 0.3744 | 0.3766 |
| Rule A picks q=0.001 | 1,480 | 0.3763 | 0.4114 | 0.4230 | +0.0116 | 0.4204 | 0.4343 | 0.4409 |

**5 h** -- all vault events: log loss raw 0.4501, calibrated 0.4484; Brier raw 0.1430, calibrated 0.1425. S1-H pooled test months: log loss raw 0.4504, isotonic 0.4501; Brier raw 0.1431, isotonic 0.1431. Calibrated values at exactly 0 or 1 on the vault: 1, contradicted by the label: 0.

| bucket | n | mean raw p | mean calibrated p | actual reach | actual - calibrated | test mean raw | test mean calibrated | test actual |
|---|---|---|---|---|---|---|---|---|
| decile 0 | 128,009 | 0.0667 | 0.0496 | 0.0478 | -0.0018 | 0.0693 | 0.0604 | 0.0456 |
| decile 1 | 128,009 | 0.0987 | 0.0756 | 0.0738 | -0.0018 | 0.1028 | 0.0901 | 0.0739 |
| decile 2 | 128,009 | 0.1205 | 0.0979 | 0.0986 | +0.0007 | 0.1259 | 0.1152 | 0.0984 |
| decile 3 | 128,008 | 0.1406 | 0.1231 | 0.1239 | +0.0008 | 0.1475 | 0.1396 | 0.1265 |
| decile 4 | 128,009 | 0.1608 | 0.1485 | 0.1529 | +0.0044 | 0.1695 | 0.1655 | 0.1550 |
| decile 5 | 128,009 | 0.1827 | 0.1762 | 0.1863 | +0.0100 | 0.1936 | 0.1949 | 0.1874 |
| decile 6 | 128,008 | 0.2080 | 0.2107 | 0.2244 | +0.0137 | 0.2216 | 0.2292 | 0.2240 |
| decile 7 | 128,009 | 0.2397 | 0.2499 | 0.2679 | +0.0180 | 0.2570 | 0.2704 | 0.2687 |
| decile 8 | 128,009 | 0.2855 | 0.3050 | 0.3290 | +0.0239 | 0.3086 | 0.3278 | 0.3285 |
| decile 9 | 128,009 | 0.3998 | 0.4090 | 0.4281 | +0.0191 | 0.4362 | 0.4296 | 0.4353 |
| all vault events | 1,280,088 | 0.1903 | 0.1846 | 0.1933 | +0.0087 | n/a | n/a | n/a |
| own top 1% by p_5h | 12,801 | 0.5821 | 0.5303 | 0.5543 | +0.0240 | n/a | n/a | n/a |
| Rule A picks q=0.01 | 13,947 | 0.5756 | 0.5267 | 0.5499 | +0.0233 | 0.6156 | 0.5423 | 0.5469 |
| Rule A picks q=0.005 | 7,188 | 0.6250 | 0.5545 | 0.5769 | +0.0225 | 0.6692 | 0.5746 | 0.5743 |
| Rule A picks q=0.001 | 1,480 | 0.7303 | 0.6093 | 0.6324 | +0.0231 | 0.7739 | 0.6439 | 0.6284 |

**10 h** -- all vault events: log loss raw 0.5848, calibrated 0.5838; Brier raw 0.2000, calibrated 0.1996. S1-H pooled test months: log loss raw 0.5879, isotonic 0.5876; Brier raw 0.2011, isotonic 0.2011. Calibrated values at exactly 0 or 1 on the vault: 1, contradicted by the label: 0.

| bucket | n | mean raw p | mean calibrated p | actual reach | actual - calibrated | test mean raw | test mean calibrated | test actual |
|---|---|---|---|---|---|---|---|---|
| decile 0 | 128,009 | 0.1218 | 0.1186 | 0.1086 | -0.0100 | 0.1260 | 0.1356 | 0.1139 |
| decile 1 | 128,009 | 0.1779 | 0.1725 | 0.1656 | -0.0069 | 0.1844 | 0.1934 | 0.1709 |
| decile 2 | 128,009 | 0.2150 | 0.2123 | 0.2126 | +0.0003 | 0.2235 | 0.2345 | 0.2137 |
| decile 3 | 128,008 | 0.2483 | 0.2502 | 0.2522 | +0.0020 | 0.2592 | 0.2717 | 0.2565 |
| decile 4 | 128,009 | 0.2814 | 0.2890 | 0.2965 | +0.0074 | 0.2949 | 0.3105 | 0.2980 |
| decile 5 | 128,009 | 0.3162 | 0.3261 | 0.3376 | +0.0114 | 0.3329 | 0.3470 | 0.3389 |
| decile 6 | 128,008 | 0.3556 | 0.3666 | 0.3842 | +0.0176 | 0.3757 | 0.3888 | 0.3812 |
| decile 7 | 128,009 | 0.4034 | 0.4110 | 0.4312 | +0.0202 | 0.4281 | 0.4334 | 0.4317 |
| decile 8 | 128,009 | 0.4692 | 0.4688 | 0.4928 | +0.0240 | 0.5005 | 0.4915 | 0.4899 |
| decile 9 | 128,009 | 0.6127 | 0.5625 | 0.5820 | +0.0194 | 0.6536 | 0.5824 | 0.5844 |
| all vault events | 1,280,088 | 0.3202 | 0.3178 | 0.3263 | +0.0086 | n/a | n/a | n/a |
| own top 1% by p_10h | 12,801 | 0.8031 | 0.6647 | 0.6873 | +0.0226 | n/a | n/a | n/a |
| Rule A picks q=0.01 | 13,947 | 0.7973 | 0.6617 | 0.6836 | +0.0219 | 0.8294 | 0.6786 | 0.6770 |
| Rule A picks q=0.005 | 7,188 | 0.8392 | 0.6848 | 0.7003 | +0.0156 | 0.8709 | 0.7042 | 0.6990 |
| Rule A picks q=0.001 | 1,480 | 0.9135 | 0.7263 | 0.7547 | +0.0284 | 0.9362 | 0.7633 | 0.7383 |

