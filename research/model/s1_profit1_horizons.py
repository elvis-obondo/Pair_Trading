"""HL-PROFIT1-H (brief docs/prompts/HL_PROFIT1_HORIZONS.md, 2026-11-11): do the 2 h and 5 h predictions tell
us which picks revert fast? TEST MONTHS ONLY (folds 1-7); no vault row, no refit, no new model. Descriptive:
no exit rule or filter is chosen here.

    python -u research/model/s1_profit1_horizons.py > research/model/logs/s1/s1_profit1_horizons.log

Reuses S1-H's own code (s1h_recalibration: load_data, compute_picks, fit_and_apply) so the picks (Rule A on
RAW p_10h, q = 1%, 0.5%, 0.1%; compute_picks ASSERTS per-fold n against s1g_report.json) and the isotonic-
corrected probabilities (expanding pool of earlier test folds, look-ahead guard t0 + h <= test start) are the
same ones, not a re-derivation. Cross-check (assert): the corrected p_10h of every traded pick equals the
base HL-PROFIT1 trade log's p_cal_10h.

DEFINITIONS (printed in the log and the NUMBERS.md section header, fixed here before any result is seen):
  - "corrected p_h" = the isotonic p_h (iso_{h}h) from S1-H's fit for that event's fold.
  - Quintiles are over the PICKS of that q (all picks, traded or not). Isotonic output is a step function, so
    ties are common: the quintile is taken from the AVERAGE rank (ties share a bin, bins can be unequal;
    each table prints its n, so nothing is hidden) -- never an arbitrary tie-break.
  - Q1: per q, per horizon h in (2,5,10): quintiles of corrected p_h: n, actual reach_h, mean corrected p_h.
  - Q2: per q, for corrected p_2h and (same table) corrected p_5h: per quintile median/mean minutes_to_mu
    (among picks that reach within 10 h, the only ones with a minutes_to_mu), share reaching within 2/5/10 h,
    and -- for the TRADED picks -- mean holding minutes and mean net/notional, for each fee mode.
  - Q3: per q, within each corrected-p_10h quintile, split by corrected p_2h above/below the MEDIAN OF THAT
    p_10h QUINTILE's p_2h (above = strictly greater; below = the rest), and separately by p_5h likewise:
    n, reach_10h, mean/median minutes_to_mu (reachers), mean net/notional (traded, per fee mode).
  - Q4: traded picks, per fee mode: share still open at 2 h (holding > 120 min) and at 5 h (> 300 min), their
    eventual exit reasons, mean net/notional and mean holding, versus those already out; split by the corrected
    p_2h (resp. p_5h) quintile (quintiles as defined over all picks of that q). No rule chosen.
  - Trades: base HL-PROFIT1 logs (open cap 10), stop = none, fee modes maker and taker, net / notional per
    trade; only picks that were actually traded.
Writes the section to research/dislocation_model/logs/s1_profit1_horizons_section.md and APPENDS the same bytes
to research/dislocation_model/NUMBERS.md (marker-guarded, asserted byte-identical). Reads no cleaned-price file.
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402
import s1h_recalibration as S1H  # noqa: E402

LOG_DIR = os.path.join(HERE, "logs", "s1")
TRADE_DIR = os.path.join(HERE, "logs", "profit1")
NUMBERS_MD = os.path.join(os.path.dirname(HERE), "dislocation_model", "NUMBERS.md")
SECTION_OUT = os.path.join(os.path.dirname(HERE), "dislocation_model", "logs", "s1_profit1_horizons_section.md")
QS = S1H.QS
HORIZONS = S1H.HORIZONS
FEES = ("maker", "taker")
SECTION = []
MARKER = "## [HL-PROFIT1 horizons]"
TRADED_NOTE = ("traded_* columns: traded picks only (subset set by the account's capacity -- the $1,000 account "
               "skipped picks when its book was full); n_traded is printed per bin")


def emit(line=""):
    print(line, flush=True)
    SECTION.append(line)


def table(df, floatfmt="{:.4f}"):
    out = df.to_string(float_format=lambda v: floatfmt.format(v))
    emit("```")
    emit(out)
    emit("```")


def quintile(p):
    """1..5 from the average rank, so ties share a bin."""
    r = pd.Series(np.asarray(p, dtype=float)).rank(method="average").to_numpy()
    n = len(r)
    return np.minimum(((r - 1) / n * 5).astype(int), 4) + 1


def load_trades():
    tr = {}
    for q in QS:
        for fee in FEES:
            path = os.path.join(TRADE_DIR, f"trades_q{q}_stopnone_fee{fee}.parquet")
            t = pd.read_parquet(path)
            assert (t["stop"] == "none").all() and (t["fee_mode"] == fee).all() and (t["q"] == q).all()
            t["net_over_notional"] = t["net"] / t["notional"]
            tr[(q, fee)] = t.set_index("event_id")
            emit(f"[HORIZONS] trades q={q} fee={fee}: {len(t):,} trades from {os.path.basename(path)}; "
                 f"exit_reason counts {t['exit_reason'].value_counts().to_dict()}")
    return tr


def build_frame():
    t0 = time.time()
    df, events = S1H.load_data()
    folds = H.build_folds(events)
    s1g_report = json.load(open(os.path.join(LOG_DIR, "s1g_report.json")))
    block_df, _ = S1H.compute_picks(df, s1g_report)       # asserts per-fold n against s1g_report.json
    fits = {(k, h): S1H.fit_and_apply(df, folds, k, h) for k in range(1, S1H.N_FOLDS) for h in HORIZONS}
    for h in HORIZONS:
        df[f"iso_{h}h"] = np.nan
        for k in range(1, S1H.N_FOLDS):
            df.loc[df["fold"] == k, f"iso_{h}h"] = fits[(k, h)]["iso_pred"]
    scored = df[df["fold"].between(1, S1H.N_FOLDS - 1)].copy()
    assert scored.index.equals(block_df.index)
    for q in QS:
        scored[S1H.pick_col(q)] = block_df.loc[scored.index, S1H.pick_col(q)]
    mtm = events["minutes_to_mu"]
    scored["minutes_to_mu"] = mtm.loc[scored["event_id"].to_numpy()].to_numpy()
    assert scored["iso_10h"].notna().all() and scored["iso_2h"].notna().all() and scored["iso_5h"].notna().all()
    emit(f"[HORIZONS] frame built: {len(scored):,} test-month events (folds 1-{S1H.N_FOLDS-1}) [{time.time()-t0:.0f}s]")
    return scored


def reach_cols(sub):
    return dict(n=len(sub), reach_2h=sub["reach_2h"].mean(), reach_5h=sub["reach_5h"].mean(),
                reach_10h=sub["reach_10h"].mean())


def mtm_cols(sub):
    m = sub.loc[sub["reach_10h"] == 1, "minutes_to_mu"].dropna()
    return dict(n_reach=len(m), mtm_median=m.median() if len(m) else np.nan, mtm_mean=m.mean() if len(m) else np.nan)


def trade_cols(sub, trades):
    ids = sub["event_id"].to_numpy()
    t = trades.loc[trades.index.intersection(ids)]
    return dict(n_traded=len(t), traded_hold_min=t["holding_minutes"].mean() if len(t) else np.nan,
                traded_net_over_notional=t["net_over_notional"].mean() if len(t) else np.nan)


def main():
    t_start = time.time()
    import master_manifest as MF
    for name in ("s1_profit1_horizons.py", "s1h_recalibration.py", "harness.py"):
        emit(f"[HORIZONS] sha256 {name}: {MF.sha(os.path.join(HERE, name))}")
    emit(f"[HORIZONS] start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC; test months only "
         f"(folds 1-{S1H.N_FOLDS-1}); no vault row read")
    scored = build_frame()
    trades = load_trades()

    # cross-check: the corrected p_10h of every traded pick == the trade log's p_cal_10h
    for (q, fee), t in trades.items():
        picks = scored[scored[S1H.pick_col(q)]].set_index("event_id")
        assert t.index.isin(picks.index).all(), f"q={q} fee={fee}: a trade is not among Rule A's picks"
        d = np.abs(picks.loc[t.index, "iso_10h"].to_numpy() - t["p_cal_10h"].to_numpy())
        emit(f"[HORIZONS] cross-check q={q} fee={fee}: {len(t):,} traded picks, max |iso_10h - p_cal_10h| = {d.max():.3e}")
        assert d.max() < 1e-9, f"q={q} fee={fee}: corrected p_10h differs from the trade log's p_cal_10h"

    receipts = SECTION[:]        # the [HORIZONS] receipt lines printed so far (shas, trade counts, cross-checks)
    SECTION.clear()              # the section starts AT the marker; receipts go inside it as a fenced block
    emit(MARKER + " Do the 2 h and 5 h predictions show which picks revert fast? (DESCRIPTIVE ONLY)")
    emit("")
    emit("Descriptive only; the test months were already used for the cut-off and the calibration; no exit rule "
         "or filter chosen; any lead needs fresh data.")
    emit("")
    emit("Test months only (folds 1-7). Picks: Rule A on raw p_10h. Probabilities: "
         "isotonic-corrected (S1-H). Quintiles from average rank over all picks of that q (ties share a bin). "
         "Trades: base HL-PROFIT1 logs, stop none, open cap 10, net / notional per traded pick. " + TRADED_NOTE + ". Script "
         "research/model/s1_profit1_horizons.py; log research/model/logs/s1/s1_profit1_horizons.log.")
    emit("")
    emit("Receipts (script shas, trade counts, cross-checks), copied from the log:")
    emit("```")
    SECTION.extend(receipts)     # already printed to the log once; not re-printed
    emit("```")
    emit("")

    for q in QS:
        picks = scored[scored[S1H.pick_col(q)]].copy()
        for h in HORIZONS:
            picks[f"qt_{h}h"] = quintile(picks[f"iso_{h}h"])
        emit(f"### q = {q}: {len(picks):,} picks; distinct corrected levels p_2h/p_5h/p_10h = "
             f"{picks['iso_2h'].nunique()}/{picks['iso_5h'].nunique()}/{picks['iso_10h'].nunique()}")
        emit("")

        # ---- Q1
        emit(f"#### Q1 (q={q}): does each horizon rank its own outcome? (quintiles of corrected p_h; actual reach_h)")
        for h in HORIZONS:
            rows = []
            for b in range(1, 6):
                s = picks[picks[f"qt_{h}h"] == b]
                rows.append(dict(quintile=b, n=len(s), actual_reach=s[f"reach_{h}h"].mean() if len(s) else np.nan,
                                 mean_corrected_p=s[f"iso_{h}h"].mean() if len(s) else np.nan))
            emit(f"h = {h} h")
            table(pd.DataFrame(rows).set_index("quintile"))
        emit("")

        # ---- Q2 (p_2h and p_5h, same tables)
        for h in (2, 5):
            for fee in FEES:
                rows = []
                for b in range(1, 6):
                    s = picks[picks[f"qt_{h}h"] == b]
                    row = dict(quintile=b, **reach_cols(s), **mtm_cols(s), **trade_cols(s, trades[(q, fee)]))
                    rows.append(row)
                emit(f"#### Q2 (q={q}): speed by corrected p_{h}h quintile, fee={fee} (mtm = minutes_to_mu among "
                     f"those reaching within 10 h; traded_* = traded picks only, subset set by the account's capacity)")
                table(pd.DataFrame(rows).set_index("quintile"))
        emit("")

        # ---- Q3
        for hs in (2, 5):
            for fee in FEES:
                rows = []
                for b in range(1, 6):
                    qq = picks[picks["qt_10h"] == b]
                    med = qq[f"iso_{hs}h"].median()
                    for name, s in ((f"p_{hs}h > med", qq[qq[f"iso_{hs}h"] > med]),
                                    (f"p_{hs}h <= med", qq[qq[f"iso_{hs}h"] <= med])):
                        rows.append(dict(p10_quintile=b, split=name, median_p=med, **reach_cols(s),
                                         **mtm_cols(s), **trade_cols(s, trades[(q, fee)])))
                emit(f"#### Q3 (q={q}): inside each corrected-p_10h quintile, split by corrected p_{hs}h vs the "
                     f"median of that quintile's own p_{hs}h (above = strictly greater), fee={fee}; traded_* = traded picks "
                     f"only, subset set by the account's capacity")
                table(pd.DataFrame(rows).set_index(["p10_quintile", "split"]))
        emit("")

        # ---- Q4
        for fee in FEES:
            t = trades[(q, fee)]
            tp = picks.set_index("event_id").loc[t.index]
            for hx, thr in ((2, 120), (5, 300)):
                open_x = t["holding_minutes"] > thr
                emit(f"#### Q4 (q={q}, fee={fee}): traded picks still open at {hx} h (holding > {thr} min): "
                     f"{int(open_x.sum()):,} of {len(t):,} = {open_x.mean():.4f} (traded picks only, subset set by the "
                     f"account's capacity)")
                rows = []
                for b in range(1, 6):
                    m = (tp[f"qt_{hx}h"] == b).to_numpy()
                    tt, oo = t[m], open_x[m]
                    still, gone = tt[oo], tt[~oo]
                    rows.append(dict(
                        quintile=b, n_traded=len(tt), share_open=oo.mean() if len(tt) else np.nan,
                        open_n=len(still),
                        open_exit_mu=(still["exit_reason"] == "mu").mean() if len(still) else np.nan,
                        open_hold_min=still["holding_minutes"].mean() if len(still) else np.nan,
                        open_net_over_notional=still["net_over_notional"].mean() if len(still) else np.nan,
                        gone_n=len(gone),
                        gone_net_over_notional=gone["net_over_notional"].mean() if len(gone) else np.nan))
                emit(f"split by corrected p_{hx}h quintile")
                table(pd.DataFrame(rows).set_index("quintile"))
                emit(f"exit reasons of the still-open ones: {t[open_x]['exit_reason'].value_counts().to_dict()}")
        emit("")

    # one canonical string (leading blank line + trailing newline) is written to the section file AND appended to
    # NUMBERS.md -- byte-identical, as for the other HL-PROFIT1 sections; marker guard against double append.
    canonical_text = "\n" + "\n".join(SECTION) + "\n"
    os.makedirs(os.path.dirname(SECTION_OUT), exist_ok=True)
    open(SECTION_OUT, "w").write(canonical_text)
    print(f"[HORIZONS] section file written: {SECTION_OUT}", flush=True)
    existing = open(NUMBERS_MD).read()
    if MARKER in existing:
        print(f"[HORIZONS] NUMBERS.md already has {MARKER} -- not appending again", flush=True)
    else:
        with open(NUMBERS_MD, "a") as f:
            f.write(canonical_text)
        assert open(NUMBERS_MD).read().endswith(canonical_text), "NUMBERS.md tail != canonical section text"
        assert open(SECTION_OUT).read() == canonical_text
        print(f"[HORIZONS] NUMBERS.md appended (byte-identical to the section file): {NUMBERS_MD}", flush=True)
    print(f"[HORIZONS] done [{time.time()-t_start:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
