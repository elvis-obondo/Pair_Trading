"""COSTS1 validation of the G8-table curve against the raw 20-level books of the 32 test files (rules section 8, VALIDATION and ESCALATION). LOCAL: reads files only; no AWS call.

    python -u research/model/diagnostics/costs_validate.py BOOKS_ALL.parquet G8_DIR > research/model/diagnostics/costs_validate.log
    python -u research/model/diagnostics/costs_validate.py --t2 logs/costs1/costs_analysis_conservative.json logs/costs1/costs_analysis_calibrated.json

BOOKS_ALL = the merged raw books from the EC2 pull (build9_l2_books.py --merge; 60 coin-minutes asked per coin-day: minutes 2..59 of hour H and 0, 1 of hour H+1; 16 coin-days = 960).
G8_DIR = a folder holding the G8 day files {day}_l2.parquet of the 11 test days (20260115, 20260301, 20260320, 20260408, 20260415, 20260422, 20260801, 20260915, 20261005, 20261008, 20261009; copied from s3://pair-trading-hl-<acct>/build8/full/).
The pull is 32 files: the 20 of the original list plus 12 from the least-liquid rule (planner ruling 2026-11-14, rule in costs_l2_test_targets.py and the rules file).

DECISION RULES (rules file section 8, fixed before any result; nothing is chosen after seeing numbers):
  (i)  REPRODUCTION: every raw book is run through the G8 extractor's own snap_row (research/hyperliquid/build8_l2.py) and compared with the G8 table row of the same (coin, minute),
       every column of that table; a row is equal if every field is equal within 1e-6 relative (NaN equal to NaN). T3 fires if the share of equal rows is below 99.9%.
       Rows in the pull with no G8 row, and rows whose snap_off_s differs (a different snapshot), are listed, and counted as not equal.
  (ii) EXACT WALK vs CURVE: for S in {50, 100, 250, 500, 1000, 2500, 5000} USD, on both sides, the exact walk of the raw book (build8_l2.slip, bp versus mid, NaN when the 20 levels hold less)
       is compared with the CURVE built from the G8 row (costs_analysis.curve_bp, headline rule, no scale), where both are defined and the curve is not beyond-book.
       overstatement = curve - exact (bp). Printed by S and by liquidity tier (the tier of the period from costs_analysis_conservative.json) and by coin: n, mean, median, p90, min.
  T1 (OVERSTATEMENT) fires if the mean overstatement at S = 250 or at S = 500 exceeds 1.0 bp, or the median exceeds 1.0 bp at any S <= 1000.
  T4 (UNDERSTATEMENT) fires if the curve is below the exact walk by more than 0.01 bp for more than 5% of the legs, counted separately for S <= 1000 and for all S.
  T2 (VERDICT FLIP) is evaluated by --t2 after the calibrated run: the calibrated variant scales the curve by the median exact/curve ratio per size bucket (edges 100, 500, 1000 USD; bucket of S by
       numpy searchsorted(edges, S, 'right')); T2 fires if the sign of any of the four vault headline nets, or the verdict letter, differs between the conservative and the calibrated run.
  Writes logs/costs1/costs_scale_calibrated.json {"edges": [100, 500, 1000], "ratio": [r0, r1, r2, r3]} (input of costs_analysis.py --scale) and logs/costs1/costs_validate.json.
  Sample (stated): 16 coin-days (10 fixed: kPEPE, ADA, ZRO, W, LINEA on 5 days; 6 from the least-liquid rule: HMSTR, NOT, TNSR in the vault; HMSTR, YZY, BOME in the test months), 960 books; the log prints the tier mix
  of the sample (books and legs by tier) and the tier lines; tier cells stay small and the result is evidence about the curve's behaviour, not a tight estimate.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.dirname(HERE)
sys.path.insert(0, MODEL)
sys.path.insert(0, os.path.join(os.path.dirname(MODEL), "hyperliquid"))
C1 = os.path.join(MODEL, "logs", "costs1") + os.sep
SIZES = [50, 100, 250, 500, 1000, 2500, 5000]
EDGES = [100, 500, 1000]
TIERS = ["least liquid third", "middle third", "most liquid third"]


def log(m):
    print(m, flush=True)


def t2(a, b):
    A, B = json.load(open(a)), json.load(open(b))
    va, vb = A["verdict"], B["verdict"]
    flips = [n for n in va["nets"] if (va["nets"][n] > 0) != (vb["nets"][n] > 0)]
    fire = bool(flips) or va["letter"] != vb["letter"]
    log(f"[VALID T2] conservative: letter ({va['letter']}), nets { {n: round(v, 2) for n, v in va['nets'].items()} }")
    log(f"[VALID T2] calibrated: letter ({vb['letter']}), nets { {n: round(v, 2) for n, v in vb['nets'].items()} }; scale {B.get('scale')}")
    log(f"[VALID T2] sign flips in {flips}; letter differs: {va['letter'] != vb['letter']}  ->  T2 {'FIRES' if fire else 'does not fire'}")
    for k in A["configs"]:
        log(f"[VALID T2]   {k}: headline net conservative ${A['configs'][k]['head']['net']:,.2f} vs calibrated ${B['configs'][k]['head']['net']:,.2f}")


def main():
    if sys.argv[1] == "--t2":
        return t2(sys.argv[2], sys.argv[3])
    books_path, g8_dir = sys.argv[1], sys.argv[2]
    import build8_l2 as B8
    assert os.environ.get("PROFIT1_VAULT", "") != "1"
    import diagnostics.costs_analysis as CA
    B = pd.read_parquet(books_path)
    log(f"[VALID] raw books {len(B):,} coin-minutes; coins {sorted(B['coin'].unique())}; days {sorted(B['src_day'].unique())}")
    B["day"] = pd.to_datetime(B["minute"] * 60, unit="s", utc=True).dt.strftime("%Y%m%d")
    # V2: asked vs found per coin-day, and which folder hour supplied the minutes found
    T20 = pd.read_parquet(C1 + "l2_targets_test20.parquet")
    asked = {}
    for t in T20.itertuples():
        for m in t.minutes:
            asked[(t.coin, t.day, int(m))] = None
    asked_df = pd.DataFrame(list(asked.keys()), columns=["coin", "day", "minute"])
    got = set(zip(B["coin"], B["minute"].astype(int)))
    asked_df["found"] = [(c, m) in got for c, m in zip(asked_df["coin"], asked_df["minute"])]
    log(f"[VALID] ASKED vs FOUND (unique coin-minutes asked from the {len(T20)} files, {len(asked_df):,}; found {int(asked_df['found'].sum()):,}; the T3 denominator is the found rows):")
    for (c, d), g in asked_df.groupby(["coin", "day"]):
        log(f"[VALID]   {c} {d}: asked {len(g)}, found {int(g['found'].sum())}, missing {int((~g['found']).sum())}" + (f" (minutes of hour {sorted(set(int(m) % 60 for m in g.loc[~g['found'], 'minute']))})" if (~g["found"]).any() else ""))
    if "src_rel_hour" in B.columns:
        log(f"[VALID] folder that supplied the kept row (folder hour - own hour; 0 own hour, 1 next folder, -1 previous): {B['src_rel_hour'].value_counts().sort_index().to_dict()}; "
            f"for the minutes 0 and 1 of hour H+1: {B[(B['minute'] % 60).isin([0, 1])]['src_rel_hour'].value_counts().sort_index().to_dict()}")
    G = pd.concat([pd.read_parquet(os.path.join(g8_dir, f"{d}_l2.parquet")) for d in sorted(B["day"].unique())], ignore_index=True)
    G = G[G["coin"].isin(B["coin"].unique())]
    Gk = G.set_index(["coin", "minute"])
    # ---------------- (i) reproduction
    fields = B8.COLS
    n_equal, bad = 0, []
    snap_rows = []
    for r in B.itertuples():
        bids = [{"px": repr(float(p)), "sz": repr(float(s))} for p, s in zip(r.bid_px, r.bid_sz) if np.isfinite(p)]
        asks = [{"px": repr(float(p)), "sz": repr(float(s))} for p, s in zip(r.ask_px, r.ask_sz) if np.isfinite(p)]
        row = B8.snap_row({"levels": [bids, asks]}, float(r.snap_off_s))
        snap_rows.append(row)
        key = (r.coin, r.minute)
        if key not in Gk.index:
            bad.append((r.coin, r.minute, "no G8 row"))
            continue
        g = Gk.loc[key]
        diff = []
        for f in fields:
            a, b = float(row[f]), float(g[f])
            if np.isnan(a) and np.isnan(b):
                continue
            if np.isnan(a) != np.isnan(b) or abs(a - b) > 1e-6 * max(abs(a), abs(b), 1e-12):
                diff.append(f)
        if diff:
            bad.append((r.coin, r.minute, ",".join(diff)))
        else:
            n_equal += 1
    share = n_equal / len(B)
    log(f"[VALID (i)] REPRODUCTION: {n_equal:,} of {len(B):,} raw rows equal the G8 row in every table field (1e-6 relative): {share:.3%}; T3 {'FIRES' if share < 0.999 else 'does not fire'} (threshold 99.9%)")
    for c, m, f in bad[:40]:
        log(f"[VALID (i)]   not equal: {c} minute {m} (minute of hour {m % 60}, {pd.Timestamp(m * 60, unit='s').strftime('%Y-%m-%d %H:%M')}): {f}")
    if bad:
        mh = pd.Series([m % 60 for _, m, _ in bad]).value_counts().sort_index().to_dict()
        log(f"[VALID (i)] {len(bad)} rows not equal; by minute of hour {mh}")
    # ---------------- (ii) exact walk vs curve
    tier_json = json.load(open(C1 + "costs_analysis_conservative.json"))["tier_coins"]
    tier_of = {per: {c: t for t, cs in d.items() for c in cs} for per, d in tier_json.items()}
    cols = {c: G[c].to_numpy(dtype=np.float64) for c in ["spread_bp", "slip_buy_1k", "slip_sell_1k", "bid_d10", "bid_d25", "bid_d50", "ask_d10", "ask_d25", "ask_d50", "book_reach_bid_bp", "book_reach_ask_bp", "mid"]}
    gidx = {(c, int(m)): i for i, (c, m) in enumerate(zip(G["coin"], G["minute"]))}
    recs = []
    for r, row in zip(B.itertuples(), snap_rows):
        j = gidx.get((r.coin, int(r.minute)))
        if j is None or not np.isfinite(cols["mid"][j]) or not np.isfinite(row["mid"]):
            continue
        per = "vault" if r.day >= "20260713" else "test"
        tier = tier_of[per].get(r.coin, "unmapped")
        for side, buy, px, sz in (("buy", True, r.ask_px, r.ask_sz), ("sell", False, r.bid_px, r.bid_sz)):
            pxs, szs = np.array([p for p in px if np.isfinite(p)]), np.array([s for s in sz if np.isfinite(s)])
            for S in SIZES:
                ex = B8.slip(pxs, szs, row["mid"], float(S), buy)
                cu, beyond = CA.curve_bp(cols, j, buy, float(S), None)
                recs.append(dict(coin=r.coin, day=r.day, minute=int(r.minute), side=side, S=S, exact=ex, curve=cu, beyond_curve=beyond, tier=tier, j=j, buy=buy))
    V = pd.DataFrame(recs)
    log(f"[VALID (ii)] legs (row x side x size) {len(V):,}; exact walk beyond the 20 levels (NaN) {int(V['exact'].isna().sum()):,} ({V['exact'].isna().mean():.1%}); curve beyond-book {int(V['beyond_curve'].sum()):,} ({V['beyond_curve'].mean():.1%})")
    for S in SIZES:
        v = V[V["S"] == S]
        log(f"[VALID (ii)]   S={S}: exact beyond 20 levels {v['exact'].isna().mean():.1%}; curve beyond-book {v['beyond_curve'].mean():.1%}")
    log("[VALID] TIER MIX of the sample (books = coin-minutes; legs = books x 2 sides x 7 sizes): " + "; ".join(f"{t}: {int((V['tier'] == t).sum() // (2 * len(SIZES)))} books, {int((V['tier'] == t).sum())} legs, coins {sorted(V.loc[V['tier'] == t, 'coin'].unique())}" for t in TIERS + ["unmapped"] if (V['tier'] == t).any()))
    # print-only (planner 2026-11-14): the beyond-book legs (curve beyond-book, S >= 2,500), headline remainder rule and section 8 as written, against the exact walk of the same legs
    BL = V[V["beyond_curve"] & V["exact"].notna()].copy()
    CA.BMODE[0] = "whole"
    BL["curve_whole"] = [CA.curve_bp(cols, int(j), bool(b), float(S), None)[0] for j, b, S in zip(BL["j"], BL["buy"], BL["S"])]
    CA.BMODE[0] = "remainder"
    log(f"[VALID (ii)] BEYOND-BOOK LEGS (curve beyond-book; exact walk defined for all of them): {len(BL):,} legs; sizes {BL['S'].value_counts().sort_index().to_dict()}")
    for nm, col in (("headline (remainder at last level)", "curve"), ("section 8 as written (whole leg at last level)", "curve_whole")):
        d_ = BL[col] - BL["exact"]
        log(f"[VALID (ii)]   {nm}: curve - exact, bp: mean {d_.mean():.3f}, median {d_.median():.3f}, p90 {d_.quantile(0.9):.3f}, min {d_.min():.3f}, max {d_.max():.3f}; curve below exact by > 0.01 bp: {(d_ < -0.01).mean():.1%}; mean exact {BL['exact'].mean():.2f} bp, mean curve {BL[col].mean():.2f} bp")
        for S in sorted(BL["S"].unique()):
            e_ = d_[BL["S"] == S]
            log(f"[VALID (ii)]      S={S}: n {len(e_)}, mean {e_.mean():.3f}, median {e_.median():.3f}, below exact {(e_ < -0.01).mean():.1%}")
        for tier in TIERS:
            e_ = d_[BL["tier"] == tier]
            if len(e_):
                log(f"[VALID (ii)]      tier {tier}: n {len(e_)}, mean {e_.mean():.3f}, median {e_.median():.3f}, below exact {(e_ < -0.01).mean():.1%}")
    W = V[V["exact"].notna() & ~V["beyond_curve"]].copy()
    W["over"] = W["curve"] - W["exact"]
    log(f"[VALID (ii)] legs where both are defined: {len(W):,} of {len(V):,}")
    rows = {}
    for S in SIZES:
        v = W[W["S"] == S]["over"]
        rows[S] = dict(n=int(len(v)), mean=float(v.mean()), median=float(v.median()), p90=float(v.quantile(0.9)), mn=float(v.min()), share_below=float((v < -0.01).mean()))
        log(f"[VALID (ii)] OVERSTATEMENT (curve - exact, bp) S={S}: n {len(v):,}, mean {v.mean():.3f}, median {v.median():.3f}, p90 {v.quantile(0.9):.3f}, min {v.min():.3f}; curve below exact by > 0.01 bp: {(v < -0.01).mean():.1%}")
    for tier in TIERS + ["unmapped"]:
        for S in (250, 500, 1000):
            v = W[(W["S"] == S) & (W["tier"] == tier)]["over"]
            if len(v):
                log(f"[VALID (ii)]   tier {tier}, S={S}: n {len(v)}, mean {v.mean():.3f}, median {v.median():.3f}, p90 {v.quantile(0.9):.3f}, below exact {(v < -0.01).mean():.1%}")
    for coin, g in W.groupby("coin"):
        log(f"[VALID (ii)]   coin {coin} (all S): n {len(g)}, mean {g['over'].mean():.3f}, median {g['over'].median():.3f}, mean exact {g['exact'].mean():.2f} bp, mean curve {g['curve'].mean():.2f} bp")
        for S in (250, 500):
            v = g[g["S"] == S]["over"]
            if len(v):
                log(f"[VALID (ii)]      coin {coin}, S={S}: n {len(v)}, mean {v.mean():.3f}, median {v.median():.3f}, p90 {v.quantile(0.9):.3f}, below exact {(v < -0.01).mean():.1%}")
    # ---------------- T1, T3, T4
    t1 = any(rows[S]["mean"] > 1.0 for S in (250, 500)) or any(rows[S]["median"] > 1.0 for S in SIZES if S <= 1000)
    low = W[W["S"] <= 1000]
    sh_low, sh_all = float((low["over"] < -0.01).mean()), float((W["over"] < -0.01).mean())
    t4 = sh_low > 0.05 or sh_all > 0.05
    # T4 detail (rule: share AND mean shortfall by S and by tier): shortfall = exact - curve (bp) on the legs where the curve is below the exact walk by more than 0.01 bp
    for S in SIZES:
        v = W[(W["S"] == S) & (W["over"] < -0.01)]
        log(f"[VALID T4]   S={S}: legs below {len(v):,} of {int((W['S'] == S).sum()):,} ({len(v)/max(int((W['S'] == S).sum()), 1):.1%}); mean shortfall {(-v['over']).mean() if len(v) else 0.0:.3f} bp, worst {(-v['over']).max() if len(v) else 0.0:.3f} bp")
    for tier in TIERS + ["unmapped"]:
        for nm, sub in (("S<=1000", W[(W["tier"] == tier) & (W["S"] <= 1000)]), ("all S", W[W["tier"] == tier])):
            if len(sub):
                v = sub[sub["over"] < -0.01]
                log(f"[VALID T4]   tier {tier}, {nm}: legs below {len(v):,} of {len(sub):,} ({len(v)/len(sub):.1%}); mean shortfall {(-v['over']).mean() if len(v) else 0.0:.3f} bp, worst {(-v['over']).max() if len(v) else 0.0:.3f} bp")
    log(f"[VALID T1] mean overstatement S=250 {rows[250]['mean']:.3f} bp, S=500 {rows[500]['mean']:.3f} bp (limit 1.0); medians S<=1000 " + ", ".join(f"{S}: {rows[S]['median']:.3f}" for S in SIZES if S <= 1000) + f"  ->  T1 {'FIRES' if t1 else 'does not fire'}")
    log(f"[VALID T3] reproduction {share:.3%} (limit 99.9%)  ->  T3 {'FIRES' if share < 0.999 else 'does not fire'}")
    log(f"[VALID T4] curve below exact by > 0.01 bp: S<=1000 {sh_low:.1%} of {len(low):,} legs, all S {sh_all:.1%} of {len(W):,} legs (limit 5%)  ->  T4 {'FIRES' if t4 else 'does not fire'}"
        + ("; the word 'conservative' is withdrawn for the table-based straight-line curve" if t4 else ""))
    # ---------------- calibrated scale: median exact / curve per bucket
    W["bucket"] = np.searchsorted(EDGES, W["S"].to_numpy(), side="right")
    ratio = []
    for b in range(4):
        v = W[(W["bucket"] == b) & (W["curve"] > 0)]
        r = float((v["exact"] / v["curve"]).median()) if len(v) else 1.0
        ratio.append(r)
        log(f"[VALID] calibration bucket {b} (S from {([0] + EDGES)[b]} USD): n {len(v)}, median exact/curve {r:.3f}")
    json.dump(dict(edges=EDGES, ratio=ratio), open(C1 + "costs_scale_calibrated.json", "w"))
    json.dump(dict(reproduction_share=share, n_rows=len(B), n_bad=len(bad), by_S=rows, T1=bool(t1), T3=bool(share < 0.999), T4=bool(t4), share_below_le1000=sh_low, share_below_all=sh_all, ratio=ratio), open(C1 + "costs_validate.json", "w"), indent=1)
    fired = [n for n, f in (("T1", t1), ("T3", share < 0.999), ("T4", t4)) if f]
    log(f"[VALID] TRIGGERS fired so far: {fired or 'none'} (T2 needs the calibrated costs_analysis run and --t2). A fired trigger means: ask the user for the full 88,405-file raw pull (cost range laptop $1.46-$3.20, EC2 $0.17-$0.36 plus instance time).")


if __name__ == "__main__":
    main()
