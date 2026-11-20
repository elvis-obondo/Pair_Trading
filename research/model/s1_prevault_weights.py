"""S1 pre-vault model: which feature groups does it rely on? (planner order 2026-11-20, user-approved quick lookup; print-only.)
Reads ONLY the saved model (logs/s1/s1_prevault_model.json, s1_prevault_model_w.npy) and the v1 column map (inputs_v1_pair.csv through s1_report.load_column_group_map,
the map the pruning rule uses). No refit, no data read, no outcome column.

SCALE. The saved weights apply to the model's own preprocessed matrix (s1_preprocess.apply_preprocessing): numeric columns are clipped and standardised with the saved
mean and sd (so a weight is per 1 SD of the fit set), missing indicators and coin one-hots are 0/1 switches (a weight is per switch, not per SD; the SD of a 0/1 column is at most 0.5,
so a per-SD weight would be smaller than shown). Nothing is rescaled. The 20 step terms b (one per half-hour of the 10 h) are the hazard model's time terms and are NOT features.
SIGN. p_h = 1 - prod over steps (1 - sigmoid(x.w + b_k)) (s1_run.compute_p_h): a positive weight raises the per-step chance of reaching mu, i.e. makes a revert more likely.
GROUPS. Numeric columns: s1_report.load_column_group_map (events, G2, G2B, G3, ..., G9; G5 and G6 merge their a/b/net/shape files). Missing indicators and coin one-hots are their own rows.
NOTE. Elastic-net weights on correlated features split credit between them: the shares are descriptive, not causal. A group-removal refit would be the causal version and is NOT done here.
"""
import hashlib
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import s1_report as SR  # noqa: E402  (imports harness only; reads the column CSV; no vault loader)

LOG = os.path.join(HERE, "logs", "s1")
OUT_JSON, OUT_MD = os.path.join(LOG, "s1_prevault_weights.json"), os.path.join(LOG, "s1_prevault_weights_section.md")

GLOSS = {
    "threshold": "the trigger size: the 99th percentile of the pair's previous 96 |z|, which today's |z| crossed",
    "vol_48": "mean absolute 30-minute step of the standardised spread over the last 48 bars",
    "sigma": "the spread's rolling sd (log-price units) at entry",
    "sandwich": "how far the spread's within-bar extreme ran past its close, in sigma, averaged over 96 bars",
    "sigma_sym": "spread sd over the 96-bar window using the entry bar's beta (leg-order symmetric)",
    "ps_efficiency": "net move of the folded 1-minute spread over the last 60 minutes divided by the sum of the absolute 1-minute steps (1 = a straight line, near 0 = choppy)",
    "trig_sym": "1 if the leg-order-symmetric |z| is above its own threshold and the previous bar was not above its own threshold",
    "abs_beta": "the size of the hedge ratio |beta|",
    "rank90_idx_abs_ret_7d_seg": "where the market index's absolute 7-day return sits against its previous 90 days (share of past samples below it)",
    "z_ratio": "|leg-order-symmetric z| divided by |z|",
    "ps_mins_since_big_step__isnan": "1 when ps_mins_since_big_step is missing (a sparse column)",
    "rank90_idx_rv_24h_seg": "where the market index's 24-hour realised volatility sits against its previous 90 days",
    "sign_beta": "the sign of the hedge ratio beta",
    "mins_since_trade_a": "minutes since leg A last traded",
    "mins_since_trade_b": "minutes since leg B last traded",
    "n_other_triggers_same_bar": "number of other triggers of the same unit on the same 30-minute bar",
    "n_triggers_prev_24h": "number of earlier triggers of the same unit in the previous 24 hours",
    "ret_idx_7d__isnan": "1 when the market index's 7-day return is missing",
    "rv_btc_24h": "BTC 24-hour realised volatility",
    "threshold_sym": "99th percentile of the leg-order-symmetric |z| over the previous 96 bars",
    "sess_europe": "1 during the European session (07-16 UTC)",
    "rv_eth_1h": "ETH 1-hour realised volatility",
    "corr_1m_24h": "correlation of the two legs' 1-minute returns over 24 hours",
    "vol_slope": "sd of the last 16 spread steps over the sd of the 32 steps before",
    "volratio_idx_seg": "the market index's 24-hour volatility divided by its 7-day volatility, from 30-minute returns",
}


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()[:12]


def main():
    out = []
    P = out.append
    j = json.load(open(os.path.join(LOG, "s1_prevault_model.json")))
    w = np.load(os.path.join(LOG, "s1_prevault_model_w.npy"))
    b = np.array(j["b"])
    oc = j["out_cols"]
    n_num, n_ind = len(j["final_numeric"]), len(j["nan_indicator_cols"])
    assert len(w) == len(oc) == n_num + n_ind + sum(len(v) for v in j["ticker_levels"].values()) and len(b) == 20
    gmap = SR.load_column_group_map()
    cat = []
    for i, c in enumerate(oc):
        if i < n_num:
            assert c in gmap, f"numeric column {c} not in the v1 group map"
            cat.append(gmap[c])
        elif i < n_num + n_ind:
            cat.append("missing indicators")
        else:
            cat.append("coin one-hots")
    nz = w != 0
    P(f"[WEIGHTS] script sha256 {sha(__file__)}; model json {sha(os.path.join(LOG, 's1_prevault_model.json'))}, w {sha(os.path.join(LOG, 's1_prevault_model_w.npy'))}")
    P(f"[WEIGHTS] output columns {len(w):,} = {n_num:,} standardised numeric + {n_ind:,} missing indicators + {len(w) - n_num - n_ind:,} coin one-hots; non-zero weights {int(nz.sum())} (asserted 192: {int(nz.sum()) == 192}); lam {j['settings']['lam']:.6g}, l1_ratio {j['settings']['l1_ratio']}")
    assert int(nz.sum()) == 192
    P(f"[WEIGHTS] SCALE: numeric weights are per 1 SD of the fit set (the model's own standardised scale, nothing rescaled); missing-indicator and coin weights are per 0/1 switch")
    P(f"[WEIGHTS] TIME TERMS (not features): 20 half-hour step intercepts b = " + ", ".join(f"{x:.3f}" for x in b))
    tot = float(np.abs(w).sum())
    P(f"[WEIGHTS] total sum |w| over all {len(w):,} columns: {tot:.4f}")
    SW = ("missing indicators", "coin one-hots")
    tot_num = float(sum(np.abs(w[i]) for i in range(len(w)) if cat[i] not in SW))
    P(f"[WEIGHTS] sum |w| over the numeric groups only (per-SD scale): {tot_num:.4f}; missing indicators and coin one-hots are per 0/1 switch, NOT per SD, and not comparable with the numeric groups")
    groups = [g for g in sorted(set(cat), key=lambda s: (s in ("missing indicators", "coin one-hots"), s))]
    rows = []
    for g in groups:
        m = np.array([c == g for c in cat])
        idx = np.nonzero(m & nz)[0]
        sa = float(np.abs(w[m]).sum())
        pos = idx[np.argmax(w[idx])] if (idx.size and w[idx].max() > 0) else None
        neg = idx[np.argmin(w[idx])] if (idx.size and w[idx].min() < 0) else None
        rows.append(dict(group=g, features=int(m.sum()), nonzero=int((m & nz).sum()), sum_abs=sa, share=sa / tot, share_numeric=None if g in SW else sa / tot_num,
                         top_pos=None if pos is None else (oc[pos], float(w[pos])), top_neg=None if neg is None else (oc[neg], float(w[neg]))))
        P(f"[WEIGHTS] GROUP {g:18s}: features {int(m.sum()):>5,}, non-zero {int((m & nz).sum()):>3}, sum|w| {sa:7.4f}, share of all {100 * sa / tot:5.1f}%, share among numeric groups only {'n/a (per switch, not per SD; not comparable)' if g in SW else f'{100 * sa / tot_num:5.1f}%'}, largest positive {rows[-1]['top_pos']}, largest negative {rows[-1]['top_neg']}")
    n_coin_nz = int((np.array([c == "coin one-hots" for c in cat]) & nz).sum())
    P(f"[WEIGHTS] coin one-hots hold two sets (leg A {len(j['ticker_levels']['ticker_a'])} levels, leg B {len(j['ticker_levels']['ticker_b'])} levels); non-zero coin weights: {n_coin_nz}" + ("" if n_coin_nz == 0 else "; their names carry a numeric coin code that this script does not map to a ticker"))
    assert abs(sum(r["share"] for r in rows) - 1) < 1e-9 and abs(sum(r["share_numeric"] for r in rows if r["share_numeric"] is not None) - 1) < 1e-9 and sum(r["nonzero"] for r in rows) == 192
    order = np.argsort(-np.abs(w))[:25]
    top = []
    for rk, i in enumerate(order, 1):
        c = oc[i]
        raw = c.replace("__isnan", "")
        g = cat[i]
        gtxt = g if g not in ("missing indicators",) else f"missing indicator of a {gmap.get(raw, '?')} column"
        base = GLOSS[c]
        meaning = f"higher value: {'MORE' if w[i] > 0 else 'LESS'} likely to revert ({base})" if not c.endswith("__isnan") else f"when 1: {'MORE' if w[i] > 0 else 'LESS'} likely to revert ({base})"
        top.append(dict(rank=rk, name=c, group=gtxt, w=float(w[i]), sign="+" if w[i] > 0 else "-", meaning=meaning))
        P(f"[WEIGHTS] TOP {rk:2d}: {c:34s} {gtxt:30s} w {w[i]:+.4f}  {meaning}")
    P(f"[WEIGHTS] top 25 hold {100 * np.abs(w[order]).sum() / tot:.1f}% of the total |w|; top 10 hold {100 * np.abs(w[order[:10]]).sum() / tot:.1f}%")
    json.dump(dict(groups=rows, top25=top, b=b.tolist(), total_abs=tot, n_nonzero=int(nz.sum())), open(OUT_JSON, "w"), indent=1)

    md = ["# S1 pre-vault model: which feature groups it relies on", "",
          f"Source: logs/s1/s1_prevault_weights.json, written by s1_prevault_weights.py (log: logs/s1/s1_prevault_weights.log). Model: s1_prevault_model.json (sha {sha(os.path.join(LOG, 's1_prevault_model.json'))}) and s1_prevault_model_w.npy (sha {sha(os.path.join(LOG, 's1_prevault_model_w.npy'))}). No refit and no data read.", "",
          f"Scale. Numeric weights are on the model's own standardised scale (per 1 SD of the fit set; nothing was rescaled). Missing-indicator and coin weights are per 0/1 switch, not per SD; the SD of a 0/1 column is at most 0.5, so their per-SD weights would be smaller than shown. The {len(b)} step intercepts (one per half-hour of the 10 h) are the time terms and are not counted as features: " + ", ".join(f"{x:.3f}" for x in b) + ".", "",
          "Sign. A positive weight raises the per-step chance of reaching mu, so a higher value of that feature makes a revert more likely; a negative weight makes it less likely.", "",
          f"{int(nz.sum())} of {len(w):,} weights are non-zero. Total sum of |w| = {tot:.4f}.", "",
          "## Feature groups", "", "| group | columns in group | non-zero | sum of abs w | share of total abs w (all columns) | share among numeric groups only | largest positive | largest negative |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        f = lambda t: "none" if t is None else f"{t[0]} ({t[1]:+.4f})"
        sn = "n/a" if r["share_numeric"] is None else f"{100 * r['share_numeric']:.1f}%"
        nm = r["group"] + (" (per switch, not per SD; not comparable)" if r["share_numeric"] is None else "")
        md.append(f"| {nm} | {r['features']:,} | {r['nonzero']} | {r['sum_abs']:.4f} | {100 * r['share']:.1f}% | {sn} | {f(r['top_pos'])} | {f(r['top_neg'])} |")
    md += ["", "## Top 25 columns by absolute weight", "", "| rank | column | group | weight | what it is, and what a higher value does |", "|---|---|---|---|---|"]
    for t in top:
        md.append(f"| {t['rank']} | {t['name']} | {t['group']} | {t['w']:+.4f} | {t['meaning']} |")
    md += ["", f"The top 25 hold {100 * np.abs(w[order]).sum() / tot:.1f}% of the total abs w; the top 10 hold {100 * np.abs(w[order[:10]]).sum() / tot:.1f}%.", "",
           "## Note", "Elastic-net weights on correlated features split credit between them, so these shares are descriptive, not causal. A group-removal refit would be the causal version and is not part of this. The coin one-hot row holds two sets (leg A and leg B); its non-zero count is stated in the table. The one-line meanings come from the dataset dictionary and the build scripts (master_g5.py, master_g9a.py, master_g4.py). The group map is the v1 dataset's own (the one the pruning rule uses); G5 and G6 merge their a, b, net and shape files. Missing indicators and coin one-hots are shown as their own rows, not folded into the raw column's group."]
    open(OUT_MD, "w").write("\n".join(md) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
