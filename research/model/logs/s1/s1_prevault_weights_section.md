# S1 pre-vault model: which feature groups it relies on

Source: logs/s1/s1_prevault_weights.json, written by s1_prevault_weights.py (log: logs/s1/s1_prevault_weights.log). Model: s1_prevault_model.json (sha c30bbfa6fd7c) and s1_prevault_model_w.npy (sha 8af9ee742dff). No refit and no data read.

Scale. Numeric weights are on the model's own standardised scale (per 1 SD of the fit set; nothing was rescaled). Missing-indicator and coin weights are per 0/1 switch, not per SD; the SD of a 0/1 column is at most 0.5, so their per-SD weights would be smaller than shown. The 20 step intercepts (one per half-hour of the 10 h) are the time terms and are not counted as features: -4.535, -4.048, -3.879, -3.809, -3.792, -3.787, -3.807, -3.847, -3.881, -3.903, -3.933, -3.937, -3.965, -3.999, -4.023, -4.045, -4.077, -4.094, -4.122, -4.156.

Sign. A positive weight raises the per-step chance of reaching mu, so a higher value of that feature makes a revert more likely; a negative weight makes it less likely.

192 of 2,377 weights are non-zero. Total sum of |w| = 2.5384.

## Feature groups

| group | columns in group | non-zero | sum of abs w | share of total abs w (all columns) | share among numeric groups only | largest positive | largest negative |
|---|---|---|---|---|---|---|---|
| G2 | 19 | 13 | 0.3461 | 13.6% | 14.0% | sandwich (+0.1143) | sign_beta (-0.0333) |
| G2B | 5 | 4 | 0.1880 | 7.4% | 7.6% | sigma_sym (+0.0682) | trig_sym (-0.0520) |
| G3 | 21 | 7 | 0.0326 | 1.3% | 1.3% | days_since_last_trigger (+0.0137) | global_reach_asof (-0.0115) |
| G4 | 47 | 17 | 0.1556 | 6.1% | 6.3% | sess_europe (+0.0281) | weekend (-0.0265) |
| G5 | 417 | 71 | 0.3261 | 12.8% | 13.2% | contrib_b (+0.0239) | ps_efficiency (-0.0606) |
| G6 | 302 | 17 | 0.0336 | 1.3% | 1.4% | net_prior_forced_human_60 (+0.0043) | a_vault_push_share_60 (-0.0062) |
| G7 | 75 | 13 | 0.0460 | 1.8% | 1.9% | b_ctx_impact_spread_bp (+0.0154) | a_fund_last (-0.0043) |
| G8 | 110 | 20 | 0.0697 | 2.7% | 2.8% | a_slip_buy_1k (+0.0151) | b_rel_ask_d25 (-0.0047) |
| G9A | 49 | 21 | 0.3694 | 14.6% | 15.0% | rank90_idx_abs_ret_7d_seg (+0.0451) | rank90_idx_rv_24h_seg (-0.0344) |
| events | 13 | 6 | 0.8981 | 35.4% | 36.4% | vol_48 (+0.2753) | threshold (-0.3547) |
| coin one-hots (per switch, not per SD; not comparable) | 400 | 0 | 0.0000 | 0.0% | n/a | none | none |
| missing indicators (per switch, not per SD; not comparable) | 919 | 3 | 0.0731 | 2.9% | n/a | d_chg1h_imb_10__isnan (+0.0064) | ps_mins_since_big_step__isnan (-0.0360) |

## Top 25 columns by absolute weight

| rank | column | group | weight | what it is, and what a higher value does |
|---|---|---|---|---|
| 1 | threshold | events | -0.3547 | higher value: LESS likely to revert (the trigger size: the 99th percentile of the pair's previous 96 |z|, which today's |z| crossed) |
| 2 | vol_48 | events | +0.2753 | higher value: MORE likely to revert (mean absolute 30-minute step of the standardised spread over the last 48 bars) |
| 3 | sigma | events | -0.1874 | higher value: LESS likely to revert (the spread's rolling sd (log-price units) at entry) |
| 4 | sandwich | G2 | +0.1143 | higher value: MORE likely to revert (how far the spread's within-bar extreme ran past its close, in sigma, averaged over 96 bars) |
| 5 | sigma_sym | G2B | +0.0682 | higher value: MORE likely to revert (spread sd over the 96-bar window using the entry bar's beta (leg-order symmetric)) |
| 6 | ps_efficiency | G5 | -0.0606 | higher value: LESS likely to revert (net move of the folded 1-minute spread over the last 60 minutes divided by the sum of the absolute 1-minute steps (1 = a straight line, near 0 = choppy)) |
| 7 | trig_sym | G2B | -0.0520 | higher value: LESS likely to revert (1 if the leg-order-symmetric |z| is above its own threshold and the previous bar was not above its own threshold) |
| 8 | abs_beta | G2 | +0.0513 | higher value: MORE likely to revert (the size of the hedge ratio |beta|) |
| 9 | rank90_idx_abs_ret_7d_seg | G9A | +0.0451 | higher value: MORE likely to revert (where the market index's absolute 7-day return sits against its previous 90 days (share of past samples below it)) |
| 10 | z_ratio | G2B | +0.0397 | higher value: MORE likely to revert (|leg-order-symmetric z| divided by |z|) |
| 11 | ps_mins_since_big_step__isnan | missing indicator of a G5 column | -0.0360 | when 1: LESS likely to revert (1 when ps_mins_since_big_step is missing (a sparse column)) |
| 12 | rank90_idx_rv_24h_seg | G9A | -0.0344 | higher value: LESS likely to revert (where the market index's 24-hour realised volatility sits against its previous 90 days) |
| 13 | sign_beta | G2 | -0.0333 | higher value: LESS likely to revert (the sign of the hedge ratio beta) |
| 14 | mins_since_trade_a | events | +0.0330 | higher value: MORE likely to revert (minutes since leg A last traded) |
| 15 | n_other_triggers_same_bar | G9A | -0.0329 | higher value: LESS likely to revert (number of other triggers of the same unit on the same 30-minute bar) |
| 16 | n_triggers_prev_24h | G9A | +0.0310 | higher value: MORE likely to revert (number of earlier triggers of the same unit in the previous 24 hours) |
| 17 | ret_idx_7d__isnan | missing indicator of a G9A column | -0.0307 | when 1: LESS likely to revert (1 when the market index's 7-day return is missing) |
| 18 | mins_since_trade_b | events | +0.0300 | higher value: MORE likely to revert (minutes since leg B last traded) |
| 19 | rv_btc_24h | G9A | -0.0288 | higher value: LESS likely to revert (BTC 24-hour realised volatility) |
| 20 | threshold_sym | G2B | -0.0282 | higher value: LESS likely to revert (99th percentile of the leg-order-symmetric |z| over the previous 96 bars) |
| 21 | sess_europe | G4 | +0.0281 | higher value: MORE likely to revert (1 during the European session (07-16 UTC)) |
| 22 | rv_eth_1h | G9A | +0.0279 | higher value: MORE likely to revert (ETH 1-hour realised volatility) |
| 23 | corr_1m_24h | G2 | -0.0268 | higher value: LESS likely to revert (correlation of the two legs' 1-minute returns over 24 hours) |
| 24 | vol_slope | G2 | +0.0268 | higher value: MORE likely to revert (sd of the last 16 spread steps over the sd of the 32 steps before) |
| 25 | volratio_idx_seg | G9A | -0.0268 | higher value: LESS likely to revert (the market index's 24-hour volatility divided by its 7-day volatility, from 30-minute returns) |

The top 25 hold 67.1% of the total abs w; the top 10 hold 49.2%.

## Note
Elastic-net weights on correlated features split credit between them, so these shares are descriptive, not causal. A group-removal refit would be the causal version and is not part of this. The coin one-hot row holds two sets (leg A and leg B); its non-zero count is stated in the table. The one-line meanings come from the dataset dictionary and the build scripts (master_g5.py, master_g9a.py, master_g4.py). The group map is the v1 dataset's own (the one the pruning rule uses); G5 and G6 merge their a, b, net and shape files. Missing indicators and coin one-hots are shown as their own rows, not folded into the raw column's group.
