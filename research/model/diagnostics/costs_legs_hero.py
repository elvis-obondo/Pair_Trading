"""COSTS1 hero / culprit check (rules: research/model/costs1_rules.md section 12, fixed before this code).
Does the pre-entry beta-adjusted mover label (and, as a second label, the larger-notional leg) point to the leg that makes or loses the money?
Existing data only: the saved trades and the per-leg grosses of costs_legs.py (build_run). No model, no pull, no engine change. Print-only.

DECISION RULES (copied from section 12; the rules file governs)
  SCOPE      eight headline runs; CLOSE version (all trades) and MID version (trades with all four mids, ctxs + G8 fallback); ALL and by liquidity tier.
             Classification by closes in both versions. FIRST leg = mover (label 1) or larger leg (label 2); SECOND = hedge or smaller. Unclassified trades are left out of that label's table and counted.
             Trade gross = first + second leg gross of the version.
  PER (run, version, label, group)
             share of classified trades where first-leg gross > 0 and where second-leg gross > 0 (flat = not > 0);
             WINNERS (trade gross > 0): HERO share = first-leg gross > second-leg gross (strict; ties counted);
             LOSERS (trade gross < 0): CULPRIT share = first-leg gross < second-leg gross (strict; ties counted);
             mean first-leg and second-leg gross in winners and in losers; trades with trade gross exactly 0 counted; shares with a denominator under 30 trades print as n/m.
  READING    per run, both versions, both labels (ALL): hero share minus culprit share in percentage points, with the two shares. No intervals, no significance statement.
  RECEIPTS   classified + unclassified = trades in the set; first + second = trade gross over the classified trades; first-leg total (ALL, close and mid) equals the costs_legs.json split total (1e-6) with the same leg count.
"""
import hashlib
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import costs_legs as LG  # noqa: E402

N = LG.N
C1, TIERS = N.C1, N.TIERS
MIN_N = 30
LABELS = [("mover", "mover_b", "mover vs hedge (beta-adjusted, HEADLINE)", "mover", "hedge"), ("larger", "larger", "larger vs smaller leg", "larger", "smaller")]
OUT = {}
LEGJ = json.load(open(C1 + "costs_legs.json"))


def log(m):
    print(m, flush=True)


def ps(x, n):
    return f"n/m (n {n})" if n < MIN_N else f"{100 * x:.1f}%"


def dstr(c):
    return "n/m" if c["diff_pp"] is None else f"{c['diff_pp']:+.1f} pp"


def usd(x):
    return "n/a" if x is None or not np.isfinite(x) else (f"-${abs(x):,.3f}" if x < 0 else f"${x:,.3f}")


def hero_cells(R, version, col, key, lab):
    ok = np.ones(len(R), bool) if version == "close" else R["have_m"].to_numpy()
    ga = (R["ga_c"] if version == "close" else R["ga_m"]).to_numpy()
    gb = (R["gb_c"] if version == "close" else R["gb_m"]).to_numpy()
    sel = R[col].to_numpy()                      # 0 = leg A is the first leg, 1 = leg B, -1 = unclassified / equal
    first = np.where(sel == 0, ga, np.where(sel == 1, gb, np.nan))
    second = np.where(sel == 0, gb, np.where(sel == 1, ga, np.nan))
    cls = ok & (sel >= 0)
    out = {}
    for gname, gm in [("ALL", np.ones(len(R), bool))] + [(t, (R["tier"] == t).to_numpy()) for t in TIERS]:
        m = cls & gm
        n_set = int((ok & gm).sum())
        unc = int((ok & gm & (sel < 0)).sum())
        assert int(m.sum()) + unc == n_set, "classified + unclassified != trades in the set"
        tg = first + second
        w, l = m & (tg > 0), m & (tg < 0)
        zero = int((m & (tg == 0)).sum())
        assert int(w.sum()) + int(l.sum()) + zero == int(m.sum())
        c = dict(n_set=n_set, n_cls=int(m.sum()), unclassified=unc, zero_gross=zero,
                 p_first_pos=float((first[m] > 0).mean()) if m.any() else None, p_second_pos=float((second[m] > 0).mean()) if m.any() else None,
                 n_w=int(w.sum()), hero=float((first[w] > second[w]).mean()) if w.any() else None, hero_ties=int((first[w] == second[w]).sum()),
                 n_l=int(l.sum()), culprit=float((first[l] < second[l]).mean()) if l.any() else None, culprit_ties=int((first[l] == second[l]).sum()),
                 mean_first_w=float(first[w].mean()) if w.any() else None, mean_second_w=float(second[w].mean()) if w.any() else None,
                 mean_first_l=float(first[l].mean()) if l.any() else None, mean_second_l=float(second[l].mean()) if l.any() else None,
                 first_total=float(first[m].sum()), second_total=float(second[m].sum()), trade_gross=float(tg[m].sum()))
        assert abs(c["first_total"] + c["second_total"] - c["trade_gross"]) < 1e-6
        c["diff_pp"] = None if (c["hero"] is None or c["culprit"] is None or c["n_w"] < MIN_N or c["n_l"] < MIN_N) else 100 * (c["hero"] - c["culprit"])
        out[gname] = c
    # receipt against the section 11 split totals (ALL)
    sp = [r for r in LEGJ[key]["splits"] if r["version"] == version and r["group"] == "ALL" and r["split"] == lab]
    assert len(sp) == 1
    sp = sp[0]
    a = out["ALL"]
    assert abs(a["first_total"] - sp["a_total"]) < 1e-6 and a["n_cls"] == sp["a_legs"], f"first-leg total does not equal costs_legs.json ({key} {version} {lab}): {a['first_total']} vs {sp['a_total']}"
    return out


def main():
    t00 = time.time()
    log(f"[HERO] script sha256 {hashlib.sha256(open(__file__, 'rb').read()).hexdigest()[:12]}; rules: costs1_rules.md section 12 (rules file sha256 {hashlib.sha256(open(N.MODEL + '/costs1_rules.md', 'rb').read()).hexdigest()[:12]})")
    G = pd.read_parquet(C1 + "g8/g8_rows.parquet", columns=["coin", "minute", "mid", "spread_bp", "crossed"]).drop_duplicates(["coin", "minute"]).set_index(["coin", "minute"])
    Gmid, Gsp, Gcr = G["mid"], G["spread_bp"], G["crossed"]
    bt = LG.btc_prices()
    T = N.T
    for side in ("vault", "test"):
        ev = N.load_events(side)
        ids = set()
        for mo in (10, 20):
            for fee in ("maker", "taker"):
                ids |= set(pd.read_parquet(f"{T}trades_q0.01_stopnone_fee{fee}{N.SFX[(side, mo)]}.parquet", columns=["event_id"])["event_id"])
        geo = ev[ev["event_id"].isin(ids)].set_index("event_id")
        coins = sorted(set(geo["ticker_a"]) | set(geo["ticker_b"]))
        base = int(geo["t0m"].min()) - 65
        n_min = int(geo["t0m"].max()) + N.K + 2 - base
        cid, CL, ML, MS = N.load_arrays(side, coins, base, n_min)
        for mo in (10, 20):
            for fee in ("maker", "taker"):
                key = f"{side} open{mo} {fee}"
                R, maxerr = LG.build_run(side, mo, fee, geo, cid, CL, ML, MS, base, Gmid, Gsp, Gcr, bt)
                log(f"[HERO] ==== {key}: trades {len(R):,}; legs sum to the saved gross (max abs diff ${maxerr:.1e}); trades with all four mids {int(R['have_m'].sum()):,}")
                OUT[key] = {}
                for version in ("close", "mid"):
                    for lname, col, lab, a_n, b_n in LABELS:
                        cells = hero_cells(R, version, col, key, lab)
                        OUT[key][f"{version}|{lname}"] = cells
                        for g, c in cells.items():
                            log(f"[HERO]   [{version:5s}] {lname:6s} {g:20s}: trades {c['n_set']:,} (classified {c['n_cls']:,}, unclassified {c['unclassified']:,}, gross 0 {c['zero_gross']:,}); "
                                f"{a_n} gross>0 {ps(c['p_first_pos'] or 0, c['n_cls'])}, {b_n} gross>0 {ps(c['p_second_pos'] or 0, c['n_cls'])}; winners {c['n_w']:,}: hero {ps(c['hero'] or 0, c['n_w'])} (ties {c['hero_ties']:,}), "
                                f"mean {a_n} {usd(c['mean_first_w'])}, mean {b_n} {usd(c['mean_second_w'])}; losers {c['n_l']:,}: culprit {ps(c['culprit'] or 0, c['n_l'])} (ties {c['culprit_ties']:,}), mean {a_n} {usd(c['mean_first_l'])}, mean {b_n} {usd(c['mean_second_l'])}; "
                                f"hero minus culprit {dstr(c)}")
        del CL, ML, MS
    OUT["_meta"] = dict(min_n=MIN_N, rules="costs1_rules.md section 12")
    json.dump(OUT, open(C1 + "costs_legs_hero.json", "w"), indent=1, default=float)
    write_section()
    log(f"[HERO] wrote logs/costs1/costs_legs_hero.json and costs_legs_hero_section.md; total {time.time() - t00:.0f}s")


def write_section():
    d = OUT
    runs = [k for k in d if not k.startswith("_")]
    md = []
    A = md.append
    A("# COSTS1 - hero / culprit check: does the pre-entry mover label point to the leg that drives the trade?")
    A(f"Source: logs/costs1/costs_legs_hero.json, written by diagnostics/costs_legs_hero.py; the log is diagnostics/costs_legs_hero.log. Rules: costs1_rules.md section 12. Every number is printed by the script. Print-only: no selection, no tuning, no significance statement (trades overlap in time).")
    A("")
    A("What the labels are. Mover = the leg whose beta-weighted 60-minute return before the entry moved the spread more (beta-adjusted headline). Larger = the leg with the larger notional at entry. Both use only information before the entry. Hedge and smaller are the other leg. Classification uses closes in both versions; the mid version covers the trades with all four mids.")
    A("")
    A("\"Hero\" and \"culprit\" are names for two shares, not a claim about cause. The beta-adjusted mover is the leg with the larger dollar 60-minute move before the entry: la |r_a| against lb |r_b|, since lb = la |beta|.")
    A("")
    cov = []
    for r in runs:
        a, b = d[r]["close|mover"]["ALL"]["n_set"], d[r]["mid|mover"]["ALL"]["n_set"]
        cov.append(f"{r} {b:,} of {a:,} ({100 * b / a:.1f}%)")
    A("The close version uses all trades; the mid version only trades with all four mids. Trades in the mid set, by run: " + "; ".join(cov) + ".")
    A("")
    A("Hero share = among winning trades (trade gross > 0), the share where the first leg (mover or larger) made strictly more than the second. Culprit share = among losing trades (trade gross < 0), the share where the first leg lost strictly more than the second. Ties are counted in the log and the json. A share on fewer than 30 trades prints as n/m.")
    A("")
    A("## Reading, run by run (ALL tiers; hero share minus culprit share, in percentage points)")
    A("How to read it. The difference, not either share, is the reading. Both shares near 50%: on these trades the label does not separate the legs. Difference positive: the first leg more often makes the larger gross when the trade wins than it makes the smaller gross when the trade loses. Both shares high with a difference near zero: the first leg is the bigger swinger in either direction. For the larger-notional label, size alone can push both shares above 50%, so 50% is not a baseline for it. A positive difference can also come from one leg having more drift (for example long vs short); this table cannot separate that. These are numbers on these trades, with no intervals and no significance statement.")
    A("")
    for r in runs:
        parts = []
        for version in ("close", "mid"):
            for lname, _, _, a_n, _ in LABELS:
                c = d[r][f"{version}|{lname}"]["ALL"]
                if c["diff_pp"] is None:
                    parts.append(f"{version} {lname}: n/m")
                else:
                    parts.append(f"{version} {lname}: hero {100 * c['hero']:.1f}% (n {c['n_w']:,}) minus culprit {100 * c['culprit']:.1f}% (n {c['n_l']:,}) = {c['diff_pp']:+.1f} pp")
        A(f"- **{r}**: " + "; ".join(parts) + ".")
    A("")
    for version in ("close", "mid"):
        for lname, _, _, a_n, b_n in LABELS:
            A(f"## {version.capitalize()} prices, label: {a_n} vs {b_n}")
            A(f"Columns: classified trades (unclassified in brackets); share of trades where the {a_n} leg made money; share where the {b_n} leg made money; winners and hero share; losers and culprit share; hero minus culprit (percentage points); mean leg gross in winners ({a_n} / {b_n}); mean leg gross in losers ({a_n} / {b_n}).")
            A("")
            A(f"| run | group | trades (unclassified) | {a_n} gross>0 | {b_n} gross>0 | winners | hero | losers | culprit | hero - culprit | winners: mean {a_n} / {b_n} | losers: mean {a_n} / {b_n} |")
            A("|" + "|".join(["---"] * 12) + "|")
            for r in runs:
                for g, c in d[r][f"{version}|{lname}"].items():
                    dp = dstr(c)
                    A(f"| {r} | {g} | {c['n_cls']:,} ({c['unclassified']:,}) | {ps(c['p_first_pos'] or 0, c['n_cls'])} | {ps(c['p_second_pos'] or 0, c['n_cls'])} | {c['n_w']:,} | {ps(c['hero'] or 0, c['n_w'])} | {c['n_l']:,} | {ps(c['culprit'] or 0, c['n_l'])} | {dp} | {usd(c['mean_first_w'])} / {usd(c['mean_second_w'])} | {usd(c['mean_first_l'])} / {usd(c['mean_second_l'])} |")
            A("")
    A("## Receipts")
    A("Asserted by the script: classified + unclassified = trades in the set; winners + losers + zero-gross = classified; first-leg + second-leg gross = trade gross over the classified trades; the first-leg total (ALL, close and mid, both labels) equals the costs_legs.json split total to 1e-6 with the same leg count.")
    open(C1 + "costs_legs_hero_section.md", "w").write("\n".join(md) + "\n")


if __name__ == "__main__":
    main()
