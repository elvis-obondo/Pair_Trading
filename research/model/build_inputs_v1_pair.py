"""HL-MODEL1 B1: the frozen input list for the pair unit, v1.

    python -u research/model/build_inputs_v1_pair.py > research/model/logs/build_inputs_v1_pair.log

Reads the v1 pair-unit schema (16 group files) and classifies every column IN or OUT per the fixed
rules of docs/prompts/HL_MODEL1_REVERTER_MODEL.md Part A6. Writes research/model/inputs_v1_pair.csv:
one row per (file, column), with in_out, reason (quoting the rule), citation (the DATASET_DICTIONARY.md
line or section backing an IN column's as-of claim), and a duplicate_of column for the three known
duplicates (A6: beta, beta_stab stored in both events.parquet and g2.parquet; seg_bars = bars_into_segment).

This file hard-codes the per-column classification rather than re-deriving it from the live schema,
so a schema change on a later version will not silently reclassify anything: SCHEMA below is the
column list read from the v1 MANIFEST at the time this was written (research/dataset logs, 2026-10-27).
"""
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# (file, [columns]) in the order read from the v1 pair MANIFEST (research/datasets/master/work/pair/*.parquet)
SCHEMA = [
    ("events.parquet", ["ticker_a", "ticker_b", "bar_index", "z", "threshold", "beta", "alpha", "mu", "sigma", "r2",
                         "beta_stab", "vol_48", "mins_since_trade_a", "mins_since_trade_b", "seg_start_bar",
                         "seg_end_bar", "bars_into_segment", "pair_index", "entry_time", "pair_triggers_true",
                         "event_id", "d"]),
    ("labels.parquet", ["event_id", "label_gap", "label_nan_minutes", "depth_2h", "reach_2h", "depth_5h", "reach_5h",
                         "depth_10h", "reach_10h", "minutes_to_mu", "adverse", "minutes_to_adverse", "mfe_sigma",
                         "mae_sigma", "fee_sigma_taker", "fee_sigma_maker", "outcome_0p5", "gross_0p5",
                         "net_0p5_taker", "net_0p5_maker", "outcome_1p0", "gross_1p0", "net_1p0_taker",
                         "net_1p0_maker", "outcome_2p0", "gross_2p0", "net_2p0_taker", "net_2p0_maker",
                         "outcome_none", "gross_none", "net_none_taker", "net_none_maker", "chance_2h",
                         "chance_5h", "chance_10h"]),
    ("g2.parquet", ["event_id", "r2_2d", "r2_7d", "corr_30m_2d", "corr_30m_7d", "corr_1m_24h", "n_1m_24h",
                     "both_traded_share_24h", "beta", "abs_beta", "sign_beta", "neutrality", "beta_stab",
                     "beta_chg_24h", "beta_chg_7d", "vol_ratio_2d", "vol_ratio_7d", "crossings_7d", "halflife_h",
                     "phi_7d", "vratio", "vol_slope", "sandwich", "g2_nan_1m", "seg_bars"]),
    ("g2b.parquet", ["event_id", "sigma_sym", "z_sym", "z_ratio", "threshold_sym", "trig_sym"]),
    ("g3.parquet", ["event_id", "n_prev_triggers", "n_prev_resolved", "prev_reach_raw", "prev_reach_shrunk",
                     "global_reach_asof", "last1_reach", "last2_reach", "last3_reach", "last4_reach", "last5_reach",
                     "last5_mean", "days_since_last_trigger", "triggers_last_7d", "prev_mean_minutes_to_mu",
                     "a_coin_n_resolved", "a_coin_reach_raw", "a_coin_reach_shrunk", "b_coin_n_resolved",
                     "b_coin_reach_raw", "b_coin_reach_shrunk", "coin_reach_shrunk_diff"]),
    ("g4.parquet", ["event_id", "a_coin_code", "a_listing_src", "a_listing_left_censored", "a_log_price", "a_ret_7d",
                     "a_ret_30d", "a_rv_24h", "a_rv_7d", "a_rv_24h_rel90", "a_traded_share_24h",
                     "a_mins_since_trade", "a_listing_age_days", "a_liq_7d", "a_liq_30d", "a_liq_rank_7d",
                     "a_liq_rank_30d", "a_sector", "a_cg_status", "a_max_leverage", "a_tier1_max_leverage",
                     "a_size_decimals", "a_margin_table_id", "b_coin_code", "b_listing_src",
                     "b_listing_left_censored", "b_log_price", "b_ret_7d", "b_ret_30d", "b_rv_24h", "b_rv_7d",
                     "b_rv_24h_rel90", "b_traded_share_24h", "b_mins_since_trade", "b_listing_age_days", "b_liq_7d",
                     "b_liq_30d", "b_liq_rank_7d", "b_liq_rank_30d", "b_sector", "b_cg_status", "b_max_leverage",
                     "b_tier1_max_leverage", "b_size_decimals", "b_margin_table_id", "d_log_price", "d_ret_7d",
                     "d_ret_30d", "d_rv_24h", "d_rv_7d", "d_rv_24h_rel90", "d_traded_share_24h",
                     "d_listing_age_days", "d_liq_rank_7d", "d_liq_rank_30d", "liq_logratio_7d", "liq_logratio_30d",
                     "same_sector", "utc_hour", "hour_sin", "hour_cos", "weekday", "weekend", "mins_since_top_hour",
                     "sess_asia", "sess_europe", "sess_us", "near_seam"]),
    ("g9a.parquet", ["event_id", "ret_btc_1h", "ret_btc_6h", "ret_btc_24h", "ret_btc_7d", "rv_btc_1h", "rv_btc_24h",
                      "rv_btc_7d", "volratio_btc", "ret_eth_1h", "ret_eth_6h", "ret_eth_24h", "ret_eth_7d",
                      "rv_eth_1h", "rv_eth_24h", "rv_eth_7d", "volratio_eth", "ret_idx_1h", "ret_idx_6h",
                      "ret_idx_24h", "ret_idx_7d", "rv_idx_1h", "rv_idx_24h", "rv_idx_7d", "volratio_idx",
                      "breadth_extreme_1h", "share_up_24h", "xs_std_1h", "n_live_coins", "coherence_7d",
                      "mkt_liq_1h", "mkt_liq_24h", "mkt_liq_ratio_7d_28d", "adl_usd_24h", "mkt_backstop_usd_24h",
                      "mkt_taker_1h_rel", "ret_idx_1h_seg", "ret_idx_6h_seg", "ret_idx_24h_seg", "ret_idx_7d_seg",
                      "rv_idx_24h_seg", "rv_idx_7d_seg", "volratio_idx_seg", "rank90_idx_rv_24h_seg",
                      "rank90_idx_abs_ret_7d_seg", "rank90_idx_rv_24h", "rank90_idx_abs_ret_7d",
                      "rank90_mkt_liq_24h", "n_other_triggers_same_bar", "n_triggers_prev_24h"]),
]
# G5 (a/b/net x 140, shape x 10) and G6 (a/b x 109, net x 93) and G7 (111) and G8 (115) repeat a fixed
# per-window / per-leg pattern; built from the live schema dump (research/dataset, 2026-10-27) rather than
# retyped by hand, to avoid a transcription slip over ~700 names. See SCHEMA_BULK below.
import json
SCHEMA_BULK = json.loads(open(os.path.join(HERE, "schema_bulk_v1_pair.json")).read())
SCHEMA += [(f, cols) for f, cols in SCHEMA_BULK.items()]

OUT_LABEL = "labels.parquet columns (A6 'Out, future-using: all G0 labels')"
HINDSIGHT = {"sector", "max_leverage", "tier1_max_leverage", "size_decimals", "margin_table_id", "cg_status"}
ARTEFACT_KEYS = {"event_id", "pair_index", "bar_index", "seg_start_bar", "entry_time"}
FUTURE_SINGLE = {"seg_end_bar": "A6 found 2026-10-27: seg_end_bar is future-using (segment end known only afterwards)",
                 "pair_triggers_true": "A6: pair_triggers_true is future-using, key only, never a feature"}
SNAPSHOT_AGE = {"a_snapshot_age_s", "b_snapshot_age_s"}
# A6 amended 2026-10-27 (user ruling via the planner): archive-age stamps are OUT; the OI/funding/ctx VALUES stay IN.
ARCHIVE_AGE_BASES = {"oi_obs_age", "oi_rec_age", "fund_age_h", "ctx_age_min"}
ARCHIVE_AGE_REASON = ("A6 amended 2026-10-27 (user ruling via the planner): 'Out, archive-age stamps: a_/b_/d_ oi_obs_age, "
                      "oi_rec_age, fund_age_h, ctx_age_min, and any other column measuring the age of the last archive "
                      "snapshot or row. The OI, funding and ctx VALUES stay IN.'")
# A6 amended again 2026-10-27 (user, same day, same rule): near_seam and a_/b_oi_rec_in_gap are OUT too, category
# archive_age (checker: quote the bullet at docs/prompts/HL_MODEL1_REVERTER_MODEL.md lines 91-97).
ARCHIVE_GAP_FLAG = {"near_seam", "oi_rec_in_gap"}
ARCHIVE_GAP_FLAG_REASON = ("A6 amended 2026-10-27 (user, same rule, same day): 'near_seam (a build 2 hole minute in "
                           "the last 24 h) and a_/b_oi_rec_in_gap (OI bridged across an archive gap) are OUT: "
                           "archive-gap flags, not market state.' (HL_MODEL1_REVERTER_MODEL.md lines 95-96)")
# duplicate pairs, verified equal (research/model/logs/dup_check.log): keep the first of each pair
DUP_DROP = {
    ("g2.parquet", "beta"): "events.parquet/beta",
    ("g2.parquet", "beta_stab"): "events.parquet/beta_stab",
    ("g2.parquet", "seg_bars"): "events.parquet/bars_into_segment",
    # research/model/dup_audit_v1_pair.py full-screen run, 2026-10-27 (re-gated, research/model/logs/regate_v1_pair.log).
    # The listing_src/vault_leader_usd group and the g5_net all-NaN group are NOT here: every copy of those is
    # degenerate (see DEGENERATE_COLUMNS below), which takes precedence over "duplicate, keep one" (planner
    # ruling 2026-10-27: constant-or-all-NaN-on-every-row columns carry no information, so ALL copies go, not
    # just the extra ones). Only the two real, non-degenerate duplicates remain here.
    ("g4.parquet", "a_mins_since_trade"): "events.parquet/mins_since_trade_a",
    ("g4.parquet", "b_mins_since_trade"): "events.parquet/mins_since_trade_b",
    ("g2.parquet", "r2_2d"): "events.parquet/r2",
}
# Planner ruling 2026-10-27 (relayed by Research Partner; checker cross-check, HL_MODEL1_REVERTER_MODEL.md
# lines 134-136): a column constant on EVERY row, or NaN on EVERY row, of the full 6,697,756-row pair unit
# carries no information and is dropped outright, including a duplicate-audit component's kept copy. A column
# constant or all-NaN only inside SOME folds stays IN (the harness's job, per fold, logged there).
# From research/model/scan_degenerate_v1_pair.py (full 1,097-column scan, all rows, research/model/degenerate_v1_pair.csv):
# g4/a_listing_src, g5_net/net_max_abs_imb_5m_bin are the two components' survivors that are themselves
# degenerate; their already-dropped duplicates (b_listing_src, a_/b_/d_vault_leader_usd, net_mins_since_forced_
# any/spike) are degenerate too (same group, same value). g8's a_/b_crossed are constant among their OWN
# finite rows (0.0) but have 468,865 / 435,672 NaN rows out of 6,697,756 -- NOT constant on EVERY row, so they
# stay IN as ordinary features, per the planner's own branching ("if a_crossed and b_crossed are constant on
# all rows [they are not]... else IN 1,095").
DEGENERATE_COLUMNS = {
    ("g4.parquet", "a_listing_src"), ("g4.parquet", "b_listing_src"),
    ("g7.parquet", "a_vault_leader_usd"), ("g7.parquet", "b_vault_leader_usd"), ("g7.parquet", "d_vault_leader_usd"),
    ("g5_net.parquet", "net_max_abs_imb_5m_bin"), ("g5_net.parquet", "net_mins_since_forced_any"),
    ("g5_net.parquet", "net_mins_since_forced_spike"),
    # planner addendum, 2026-10-27: a single-value-plus-NaN column is degenerate only if its NaN mask equals
    # another IN column's mask (research/model/logs/check_crossed_mask_v1_pair.py). a_crossed/b_crossed match
    # 16 other IN g8 columns per leg exactly (a_/b_mid, spread_bp, bid/ask_d10/25/50, trunc_*, book_reach_*),
    # all of which stay IN, so the match counts.
    ("g8.parquet", "a_crossed"), ("g8.parquet", "b_crossed"),
}

CITATION = {
    "events.parquet": "DATASET_DICTIONARY.md Keys section: 'key / geometry at t = 0' (frozen entry geometry, 96-bar fit at the trigger)",
    "g2.parquet": "DATASET_DICTIONARY.md G2: 'feature, windows end at the trigger bar / the 1m bar T + 29'",
    "g2b.parquet": "DATASET_DICTIONARY.md G2b: 'feature, orientation-proof'; 96-bar window ending at the trigger bar (NaN before bar 96/192)",
    "g3.parquet": "DATASET_DICTIONARY.md G3: 'feature; reads past LABELS' -- resolution rule T_i - T_j >= 600 min AND label_gap_j = 0 before any resolved value is used",
    "g6_a.parquet": "DATASET_DICTIONARY.md G6: 'Window. 30/60/360/1440 minutes ending at t0, whole 5-minute bins strictly before t0'",
    "g6_b.parquet": "DATASET_DICTIONARY.md G6: 'Window. 30/60/360/1440 minutes ending at t0, whole 5-minute bins strictly before t0'",
    "g6_net.parquet": "DATASET_DICTIONARY.md G6: 'Window. 30/60/360/1440 minutes ending at t0, whole 5-minute bins strictly before t0'",
    "g7.parquet": "DATASET_DICTIONARY.md G7: observed/reconstructed OI anchored only from the past; funding/premium 'a row stamped after t0 is not available'",
    "g8.parquet": "DATASET_DICTIONARY.md G8: 'As-of rule. t0 = T + 30 min. The row used is the one labelled t0 - 1 minute ... Never the row labelled t0.'",
}

G9A_NOTE = ("VERIFIED by code docstring (planner ruling 2026-10-27: a docstring line counts as as-of evidence where "
            "DATASET_DICTIONARY.md has no window wording). research/dataset/master_g9a.py:5: 'every window is "
            "[o - W, o) (minutes labelled <= T + 29)'. Backup: research/dataset/logs/master_tests_g9a.log, "
            "'[G9a POISON truncation] 60 cutoffs ... columns changed 0' and '[G9a POISON overwrite] 8 cutoffs ... "
            "columns changed 0', PASS.")

# --- G4: per-column citation, applying the SAME strict standard as g9a (checker finding 2, 2026-10-27) ---
# CITED (explicit dictionary line): liq_7d/30d "ending the day BEFORE the trigger's day"; liq_rank_7d/30d
# "past-only percentile"; their d_/logratio derivatives; the time columns "on t0"; near_seam "within the last 24 h".
G4_CITED_BASES = {"liq_7d", "liq_30d", "liq_rank_7d", "liq_rank_30d"}
G4_CITED_EXACT = {"d_liq_rank_7d", "d_liq_rank_30d", "liq_logratio_7d", "liq_logratio_30d",
                   "utc_hour", "hour_sin", "hour_cos", "weekday", "weekend", "mins_since_top_hour",
                   "sess_asia", "sess_europe", "sess_us"}
G4_CITED_TEXT = {
    "liq_7d": "DATASET_DICTIONARY.md G4: 'liq_7d, liq_30d (mean daily taker notional over the 7/30 UTC days ending the day BEFORE the trigger's day)'",
    "liq_30d": "DATASET_DICTIONARY.md G4: 'liq_7d, liq_30d (... ending the day BEFORE the trigger's day)'",
    "liq_rank_7d": "DATASET_DICTIONARY.md G4: 'liq_rank_7d/30d (past-only percentile among coins)'",
    "liq_rank_30d": "DATASET_DICTIONARY.md G4: 'liq_rank_7d/30d (past-only percentile among coins)'",
    "d_liq_rank_7d": "derived from liq_rank_7d (cited); difference of two past-only percentiles",
    "d_liq_rank_30d": "derived from liq_rank_30d (cited); difference of two past-only percentiles",
    "liq_logratio_7d": "derived from liq_7d a_/b_ (cited, 'ending the day BEFORE'); log ratio of two cited quantities",
    "liq_logratio_30d": "derived from liq_30d a_/b_ (cited, 'ending the day BEFORE'); log ratio of two cited quantities",
    "utc_hour": "DATASET_DICTIONARY.md G4 Time: 'Time (on t0): utc_hour, hour_sin, hour_cos, weekday, weekend, mins_since_top_hour, sess_asia, sess_europe, sess_us'",
}
for _k in ("hour_sin", "hour_cos", "weekday", "weekend", "mins_since_top_hour", "sess_asia", "sess_europe", "sess_us"):
    G4_CITED_TEXT[_k] = G4_CITED_TEXT["utc_hour"]
# No explicit window-end line in DATASET_DICTIONARY.md's G4 paragraph for these (unlike liq_7d/30d's "ending the
# day BEFORE" or liq_rank's "past-only"); VERIFIED instead by the code docstring (planner ruling 2026-10-27).
G4_UNVERIFIED_BASES = {"listing_src", "listing_left_censored", "log_price", "ret_7d", "ret_30d", "rv_24h", "rv_7d",
                        "rv_24h_rel90", "traded_share_24h", "mins_since_trade", "listing_age_days"}
G4_DOCSTRING_LINE = {
    "listing_src": "research/dataset/master_g4.py:7: 'listing_src records which (0 = asset_ctxs, 1 = trade day earlier)'",
    "listing_left_censored": "research/dataset/master_g4.py:7: 'listing_left_censored = 1 if the asset_ctxs date is within 3 days of 2023-05-20' -- a fixed fact about the listing date, not from the future",
    "log_price": "research/dataset/master_g4.py:13: 'log_price: log of the 1m close at m0' (m0 = T + 29, line 5)",
    "ret_7d": "research/dataset/master_g4.py:14: 'ret_7d, ret_30d: log price at m0 minus log price 10,080/43,200 minutes earlier'",
    "ret_30d": "research/dataset/master_g4.py:14: 'ret_7d, ret_30d: log price at m0 minus log price 10,080/43,200 minutes earlier'",
    "rv_24h": "research/dataset/master_g4.py:15: 'rv_24h, rv_7d: sd of 1-minute log returns over the 1,440/10,080 minutes ending at m0'",
    "rv_7d": "research/dataset/master_g4.py:15: 'rv_24h, rv_7d: sd of 1-minute log returns over the 1,440/10,080 minutes ending at m0'",
    "rv_24h_rel90": "research/dataset/master_g4.py:16: 'rv_24h divided by the median of rv_24h sampled at the same minute on each of the previous 90 days'",
    "traded_share_24h": "research/dataset/master_g4.py:11: 'traded_share_24h: share of the 1,440 minutes ending at m0 with a trade'",
    "mins_since_trade": "research/dataset/master_g4.py:12: 'mins_since_trade of the 1m bar m0'",
    "listing_age_days": "research/dataset/master_g4.py:7 (listing_date) and A6: listing_age_days = (t0 - 00:00 of the listing date) / 1 day",
}
G4_UNVERIFIED_NOTE_TMPL = ("VERIFIED by code docstring (planner ruling 2026-10-27). {line} Backup: "
                           "research/dataset/logs/master_tests_g4.log, '[G4 POISON pair] 1000 events, future raw "
                           "inputs ... randomised: columns changed in 0 cases', PASS.")
G4_COIN_IDENTITY_CITE = "A6 fixed rule (user 2026-10-27): 'Coin identity: IN ... a_/b_coin_code / ticker as categorical' -- an identity label, not a windowed statistic, so no as-of window applies"

# --- G5: per-column citation, same strict standard ---
# CITED (explicit bracket/window in the dictionary): the minute-shape columns and ps_* summary stats.
G5_MINUTE_SHAPE_PREFIXES = ("imb_5m_", "forced_5m_", "imb_30m_pre_", "forced_30m_pre_", "imb_30m_", "forced_30m_")
G5_MINUTE_SHAPE_EXACT = {"max_abs_imb_5m", "max_abs_imb_5m_bin", "mins_since_forced_any", "mins_since_forced_spike"}
G5_CITED_TEXT = ("DATASET_DICTIONARY.md G5: minute shape is explicitly windowed, e.g. 'imb_5m_k, forced_5m_k (k = 0..11, "
                 "[o-60, o))', 'imb_30m_k, forced_30m_k ... [o-360, o))', 'imb_30m_pre_k, forced_30m_pre_k ... "
                 "[o-420, o-60))'; mins_since_forced_any '0 = the minute labelled o-1'; mins_since_forced_spike "
                 "'threshold ... over 7 days'; max_abs_imb_5m(+_bin) is the max of the already-bracketed imb_5m_k series")
# UNVERIFIED: the per-leg/net window-W aggregates (W in {30,60,360,1440}) have a stated window LENGTH but no
# stated window END in the dictionary text, unlike G6's explicit "ending at t0, strictly before t0".
G5_WINDOW_W_METRICS = {"imb", "forced_share", "forced_net", "backstop_ratio", "adl_ratio", "backstop_share",
                        "adl_share", "open_push", "close_push", "open_close_ratio", "top3", "wallets_raw",
                        "wallets_per_musd", "twap_share", "volume_ratio"}
G5_WINDOWS = {"30", "60", "360", "1440"}
G5_NO_BRACKET_EXACT = {"slope_cum_imb_30", "slope_cum_imb_60", "accel_share"}
G5_POISON_BACKUP = ("Backup: research/dataset/logs/master_tests_g5.log, '[G5 POISON] 1000 pair legs + 300 coin "
                     "legs (all raw flow minutes at or after o replaced), 139 columns each: changed in 0 cases', PASS.")
G5_UNVERIFIED_NOTE_WINDOW = ("VERIFIED by code docstring (planner ruling 2026-10-27): DATASET_DICTIONARY.md's G5 "
                             "paragraph gives the window LENGTH only ('window W in {30,60,360,1440} minutes'); "
                             "research/dataset/master_g5.py:5 gives the end point: 'Cutoff o = the minute index of "
                             "t0 = T + 30 min; windows [o - W, o) (minutes labelled <= T + 29).' " + G5_POISON_BACKUP)
G5_UNVERIFIED_NOTE_NOBRACKET = ("VERIFIED by code docstring (planner ruling 2026-10-27): "
                                "research/dataset/master_g5.py:11-12: 'slope_cum_imb_30/60 (OLS slope per minute of "
                                "the cumulative s(buy - sell) / TN_W over the last 30/60 minutes); accel_share "
                                "(push-side taker USD in the last 15 of the last 60 minutes / the 60-minute "
                                "total)' -- both windows are 'the last N minutes', i.e. ending at o = t0. " + G5_POISON_BACKUP)
G5_SHAPE_CITED = {"ps_realized_var", "ps_efficiency", "ps_max_step", "ps_max_step_min", "ps_drawdown"}
G5_SHAPE_CITED_TEXT = {
    "ps_realized_var": "DATASET_DICTIONARY.md G5: 'g5_shape: price shape of the folded 1-minute spread path over the last 60 minutes (ps_realized_var, ps_efficiency, ps_max_step(+_min), ... ps_drawdown)'",
}
for _k in ("ps_efficiency", "ps_max_step", "ps_max_step_min", "ps_drawdown"):
    G5_SHAPE_CITED_TEXT[_k] = G5_SHAPE_CITED_TEXT["ps_realized_var"]
G5_SHAPE_CITED_TEXT["ps_mins_since_big_step"] = "DATASET_DICTIONARY.md G5: 'ps_mins_since_big_step [3 x the sd of the 24 h of steps ending at o-60]'"
G5_SHAPE_UNVERIFIED = {"w_a", "contrib_a", "contrib_b"}
G5_SHAPE_UNVERIFIED_NOTE = ("VERIFIED by code docstring (planner ruling 2026-10-27): DATASET_DICTIONARY.md says only "
                            "'and the weights (w_a, contrib_a, contrib_b)' with no window of its own, but "
                            "research/dataset/master_g5.py:13: 'NET: net(x) = wA x_A + wB x_B, cA = d dlog a, "
                            "cB = -d beta dlog b over [o-60, o) (1m closes), wA = max(cA,0) / (max(cA,0) + "
                            "max(cB,0))' -- w_a = wA and contrib_a/contrib_b = cA/cB are explicitly windowed "
                            "[o-60, o). " + G5_POISON_BACKUP)


def _strip_leg(col):
    for pfx in ("a_", "b_", "d_", "net_"):
        if col.startswith(pfx):
            return col[len(pfx):]
    return col


def classify_g4(col):
    bare = _strip_leg(col)
    if col in {"a_coin_code", "b_coin_code"}:
        return "IN", "feature", "default IN (A6: every column except the exclusions)", G4_COIN_IDENTITY_CITE
    if bare in G4_CITED_BASES or col in G4_CITED_EXACT:
        return "IN", "feature", "default IN (A6: every column except the exclusions)", G4_CITED_TEXT[bare if bare in G4_CITED_BASES else col]
    if bare in G4_UNVERIFIED_BASES:
        return "IN", "feature", "default IN (A6: every column except the exclusions)", G4_UNVERIFIED_NOTE_TMPL.format(line=G4_DOCSTRING_LINE[bare])
    raise ValueError(f"g4.parquet column not classified: {col}")


def classify_g5(file, col):
    bare = _strip_leg(col)
    if file == "g5_shape.parquet":
        if bare in G5_SHAPE_CITED:
            return "IN", "feature", "default IN (A6: every column except the exclusions)", G5_SHAPE_CITED_TEXT[bare]
        if bare == "ps_mins_since_big_step":
            return "IN", "feature", "default IN (A6: every column except the exclusions)", G5_SHAPE_CITED_TEXT[bare]
        if bare in G5_SHAPE_UNVERIFIED:
            return "IN", "feature", "default IN (A6: every column except the exclusions)", G5_SHAPE_UNVERIFIED_NOTE
        raise ValueError(f"g5_shape.parquet column not classified: {col}")
    if bare.startswith(G5_MINUTE_SHAPE_PREFIXES) or bare in G5_MINUTE_SHAPE_EXACT:
        return "IN", "feature", "default IN (A6: every column except the exclusions)", G5_CITED_TEXT
    if bare in G5_NO_BRACKET_EXACT:
        return "IN", "feature", "default IN (A6: every column except the exclusions)", G5_UNVERIFIED_NOTE_NOBRACKET
    parts = bare.rsplit("_", 1)
    if len(parts) == 2 and parts[0] in G5_WINDOW_W_METRICS and parts[1] in G5_WINDOWS:
        return "IN", "feature", "default IN (A6: every column except the exclusions)", G5_UNVERIFIED_NOTE_WINDOW
    raise ValueError(f"{file} column not classified: {col}")


def classify(file, col):
    if file == "labels.parquet":
        if col == "event_id":
            return "OUT", "artefact_key", "A6: Out, artefacts and keys (event_id)", CITATION["events.parquet"]
        return "OUT", "future_label", OUT_LABEL, "DATASET_DICTIONARY.md G0 Labels: 'the only columns that use the future'"
    if col in FUTURE_SINGLE:
        return "OUT", "future_single", FUTURE_SINGLE[col], "DATASET_DICTIONARY.md Keys: seg_end_bar / pair_triggers_true rows"
    if col in ARTEFACT_KEYS:
        return "OUT", "artefact_key", "A6: Out, artefacts and keys", CITATION.get(file, "")
    if col in SNAPSHOT_AGE:
        return "OUT", "snapshot_age", "A6: Out, artefacts and keys: a_/b_snapshot_age_s (archive sampling rate, not market state)", "DATASET_DICTIONARY.md G8 As-of rule section"
    bare = _strip_leg(col)
    if file == "g7.parquet" and bare in ARCHIVE_AGE_BASES:
        return "OUT", "archive_age", ARCHIVE_AGE_REASON, "A6 amendment, 2026-10-27 (relayed by the planner, Research Partner)"
    if bare in ARCHIVE_GAP_FLAG:
        return "OUT", "archive_age", ARCHIVE_GAP_FLAG_REASON, "A6 amendment, 2026-10-27 (relayed by the planner, Research Partner; checker: category archive_age)"
    if bare in HINDSIGHT or col in {"same_sector"}:
        return "OUT", "hindsight_static", "A6: Out, hindsight static (today's values applied to the past)", "DATASET_DICTIONARY.md G4: 'static snapshot, outside the as-of rule (hindsight)'"
    if (file, col) in DEGENERATE_COLUMNS:
        return ("OUT", "degenerate",
                "Planner ruling 2026-10-27 (relayed by Research Partner): constant or all-NaN on every row of "
                "the full pair unit, every copy dropped (takes precedence over 'duplicate, keep one')",
                "research/model/degenerate_v1_pair.csv, research/model/logs/scan_degenerate_v1_pair.log")
    if (file, col) in DUP_DROP:
        return ("OUT", "duplicate_dropped",
                f"A6 duplicate rule: kept {DUP_DROP[(file, col)]} instead (research/model/dup_audit_v1_pair.csv, "
                f"research/model/dup_audit_keep_v1_pair.csv, research/model/logs/regate_v1_pair.log)",
                "research/model/logs/dup_audit_v1_pair.log (full-screen run, 2026-10-27, re-gated)")
    if file == "g9a.parquet":
        return "IN", "feature", "default IN (A6: every column except the exclusions)", G9A_NOTE
    if file == "g4.parquet":
        return classify_g4(col)
    if file in ("g5_a.parquet", "g5_b.parquet", "g5_net.parquet", "g5_shape.parquet"):
        return classify_g5(file, col)
    return "IN", "feature", "default IN (A6: every column except the exclusions)", CITATION.get(file, "")


def main():
    rows = []
    for file, cols in SCHEMA:
        for col in cols:
            if col == "event_id" and file != "labels.parquet":
                in_out, cat, reason, cite = "OUT", "artefact_key", "A6: Out, artefacts and keys (event_id, join key)", CITATION.get(file, "")
            else:
                in_out, cat, reason, cite = classify(file, col)
            rows.append({"file": file, "column": col, "in_out": in_out, "category": cat, "reason": reason, "citation": cite})

    out_path = os.path.join(HERE, "inputs_v1_pair.csv")
    with open(out_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["file", "column", "in_out", "category", "reason", "citation"])
        w.writeheader()
        w.writerows(rows)

    n_in = sum(1 for r in rows if r["in_out"] == "IN")
    n_out = sum(1 for r in rows if r["in_out"] == "OUT")
    by_cat = {}
    for r in rows:
        by_cat.setdefault((r["in_out"], r["category"]), 0)
        by_cat[(r["in_out"], r["category"])] += 1
    n_unverified = sum(1 for r in rows if r["in_out"] == "IN" and r["citation"].startswith("UNVERIFIED"))
    print(f"[B1] {len(rows):,} (file, column) rows across {len(SCHEMA)} files; IN {n_in:,}, OUT {n_out:,}")
    for (io, cat), n in sorted(by_cat.items()):
        print(f"   {io:3} {cat:20} {n:4}")
    print(f"[B1] UNVERIFIED IN columns (no as-of citation line, per B1 rule): {n_unverified:,}")
    print(f"[B1] wrote {out_path}")


if __name__ == "__main__":
    main()
