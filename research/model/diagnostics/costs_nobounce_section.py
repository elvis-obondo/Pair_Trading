"""Writes the COSTS1 no-bounce section (markdown) from logs/costs1/costs_nobounce.json. Every number is read from the json (written by costs_nobounce.py, log
diagnostics/costs_nobounce.log); nothing is typed by hand. Words only describe what the columns are.
    python research/model/diagnostics/costs_nobounce_section.py
"""
import hashlib
import json
import os
import re

MODEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C1 = os.path.join(MODEL, "logs", "costs1") + os.sep
J = json.load(open(C1 + "costs_nobounce.json"))
SRC = hashlib.sha256(open(C1 + "costs_nobounce.json", "rb").read()).hexdigest()[:12]
FB, CO = "ctxs + G8 fallback", "ctxs only"
TIERS = ["least liquid third", "middle third", "most liquid third"]
RUNS = [(s, mo, fee) for s in ("vault", "test") for mo in (10, 20) for fee in ("maker", "taker")]
L = []
# per-run cost decomposition of costs_analysis on the matched filled trades, read from the log lines the main script printed
DEC = {}
_cur = None
for ln in open(os.path.join(MODEL, "diagnostics", "costs_nobounce.log")):
    m = re.search(r"---- (\w+ open\d+ \w+):", ln)
    if m:
        _cur = m.group(1)
    m = re.search(r"\[ctxs \+ G8 fallback\] RECEIPT B - C .* mean entry cost \(two legs summed\) ([\d.]+) bp, exit ([\d.]+) bp, mean per leg-fill ([\d.]+) bp", ln)
    if m and _cur:
        DEC[_cur] = (float(m.group(1)), float(m.group(2)), float(m.group(3)))
assert len(DEC) == 8, DEC.keys()


def p(x, d=1):
    return "n/a" if x is None else f"{100 * x:.{d}f}%"


def usd(x):
    return f"${x:,.2f}"


def add(s=""):
    L.append(s)


add("# COSTS1 - no-bounce check: the close vs mid gap")
add(f"Source: logs/costs1/costs_nobounce.json (sha256 {SRC}), written by diagnostics/costs_nobounce.py; the log is diagnostics/costs_nobounce.log. Rules: costs1_rules.md section 10. This section is written by diagnostics/costs_nobounce_section.py; no number is typed by hand.")
add()
h = J["vault"]["reprice"]["headline|" + FB]
hc = J["vault"]["reprice"]["headline|" + CO]
add("## Headline cell")
add(f"Vault, q 1% / no stop / taker / open10. With the G8 table mid as a labelled fallback where the ctxs mid is missing, {h['n']:,} trades have all four mids ({p(h['coverage'])} coverage). On those trades the close-based gross is {usd(h['gross_close'])} and the mid-to-mid gross is {usd(h['gross_mid'])}. **Gross ratio {p(h['gross_ratio'])}. Band: {h['band']}.**")
add(f"Net after fees on the same trades: close-based {usd(h['net_A'])}, mid-to-mid {usd(h['net_B'])} (net ratio {p(h['net_B'] / h['net_A'])}). Fees do not change, so the net ratio moves more than the gross ratio.")
add(f"Ctxs mid only (no band; coverage {p(hc['coverage'])}, {hc['n']:,} trades, skewed to the earlier days): gross ratio {p(hc['gross_ratio'])}, close gross {usd(hc['gross_close'])}, mid gross {usd(hc['gross_mid'])}.")
ra = J["vault"]["reprice"]["vault open10 taker"]
fr_, st_ = ra[FB + "|ALL TIERS fresh"], ra[FB + "|ALL TIERS stale"]
g8v = J["vault"]["g8_check"]["ALL"]
add(f"How not to over-read the headline: the {p(h['gross_ratio'])} mixes fresh and stale trades ({fr_['n']:,} fresh at a gross ratio of {p(fr_['gross_ratio'])}, {st_['n']:,} stale at {p(st_['gross_ratio'])}). The ctxs-only {p(hc['gross_ratio'])} is a different, earlier set of trades, not the same trades with another mid. The two mid sources disagree by more than 1 bp on {p(1 - g8v['within1'])} of the vault minutes where both exist, but on the same trades they give the same gross ratio (source-sensitivity table below).")
add()
add("## Source-sensitivity line (print only; no change to the headline or the bands)")
add("The same trades, two mid sources: only trades that have BOTH a ctxs mid and a G8 table mid at all four stamps (entry and exit, both legs). Gross ratio = mid-to-mid gross / saved close-based gross on those trades. The last two columns are the gap between the two mids at those stamps, in bp. Written by diagnostics/costs_nobounce_sources.py (log costs_nobounce_sources.log).")
SRCJ = json.load(open(C1 + "costs_nobounce_sources.json"))
add("| run | trades with both mids / all | gross ratio, ctxs mid | gross ratio, G8 mid | median abs gap, bp | p90 abs gap, bp |")
add("|---|---|---|---|---|---|")
for s_, mo_, fee_ in RUNS:
    r_ = SRCJ[f"{s_} open{mo_} {fee_}"]
    add(f"| {s_} open{mo_} {fee_} | {r_['n_both']:,} / {r_['n']:,} ({p(r_['share'])}) | {p(r_['ratio_ctxs'])} | {p(r_['ratio_g8'])} | {r_['diff_median_bp']:.3f} | {r_['diff_p90_bp']:.3f} |")
add("In the later vault months only the G8 mid exists, so the headline gross ratio (with fallback) against the ratios on the both-mids trades cannot be split between 'later period' and 'G8 source'. The overlap shows the source does not move the ratio, so the period is the likelier cause, but that is not tested here.")
_vm = [m_["ratio"] for (s_, mo_, fee_) in RUNS if s_ == "vault" for k_, m_ in SRCJ[f"{s_} open{mo_} {fee_}"]["monthly"].items() if k_ in ("2026-07", "2026-08", "2026-09") and m_["ratio"] is not None]
_oc = SRCJ["vault open10 taker"]["monthly"]["2026-10"]
add(f"The period-sensitivity table below shows it: the vault's July to September gross ratios run {p(min(_vm))} to {p(max(_vm))} across the four runs, and the drop sits in October (vault open10 taker: close gross {usd(_oc['close_gross'])}, mid gross {usd(_oc['mid_gross'])}, {p(_oc['share_any_g8'])} of the trades with a G8 stamp). The period is still confounded with the G8 source.")
add("On the same trades the two sources give the same gross ratio. So the gap between the headline (ctxs + fallback) and the ctxs-only figure points to which trades are in the set (the ctxs-only set is the earlier trades), not to which mid is used.")
add()
add("## Period-sensitivity line (print only; no change to the headline or the bands)")
add("Gross ratio (mid-to-mid gross / close-based gross, ctxs + G8 fallback, trades with all four mids) by entry month, for each of the eight runs, with the trade counts and the mid source used. 'Source' = share of the matched trades whose four mids all come from the ctxs cache / share with at least one stamp taken from the G8 table. n/m = not meaningful: the month's close gross is zero or negative or under 5% of the run's close gross. Dollars are kept. Written by diagnostics/costs_nobounce_sources.py.")
add("| run | month | trades matched / all | close gross | mid gross | gross ratio | source: all ctxs / some G8 |")
add("|---|---|---|---|---|---|---|")
for s_, mo_, fee_ in RUNS:
    r_ = SRCJ[f"{s_} open{mo_} {fee_}"]
    tot_ = J[s_]["reprice"][f"{s_} open{mo_} {fee_}"][FB + "|ALL TIERS"]["gross_close"]
    for mth_, m_ in r_["monthly"].items():
        nm_ = m_["ratio"] is None or m_["close_gross"] <= 0 or m_["close_gross"] < 0.05 * tot_
        add(f"| {s_} open{mo_} {fee_} | {mth_} | {m_['n_matched']:,} / {m_['n']:,} | {usd(m_['close_gross'])} | {usd(m_['mid_gross'])} | {'n/m' if nm_ else p(m_['ratio'])} | {p(m_['share_all_ctxs'])} / {p(m_['share_any_g8'])} |")
add()
add("## The eight priority runs (q 1% / no stop), ctxs + G8 fallback")
add("Gross ratio = mid-to-mid gross / close-based gross on the trades with all four mids. Fresh = all four closes had a trade in their minute; stale = at least one close was an older trade. A = saved net (close, zero cost). B = mid-to-mid net (same fees and funding). C = costed net with the book spread and depth model already reported (conservative curve). Only the vault taker open10 cell carries a band; the others carry no label.")
add()
add("| run | trades matched / all | close gross | mid gross | gross ratio | gross ratio, fresh | gross ratio, stale | net A | net B | net C | ctxs-only gross ratio |")
add("|---|---|---|---|---|---|---|---|---|---|---|")
for s, mo, fee in RUNS:
    r = J[s]["reprice"][f"{s} open{mo} {fee}"]
    a = r[FB + "|ALL TIERS"]
    f_ = r[FB + "|ALL TIERS fresh"]
    st = r[FB + "|ALL TIERS stale"]
    c = r[CO + "|ALL TIERS"]
    add(f"| {s} open{mo} {fee} | {a['n']:,} / {r['n']:,} | {usd(a['gross_close'])} | {usd(a['gross_mid'])} | {p(a['gross_ratio'])} | {p(f_['gross_ratio'])} | {p(st['gross_ratio'])} | {usd(a['A'])} | {usd(a['B'])} | {usd(a['C'])} | {p(c['gross_ratio'])} |")
add()
add("### Gross ratio by liquidity tier (ctxs + G8 fallback)")
add("n/m = not meaningful: the tier's close gross is zero or negative, or under 5% of the run's close gross, so the ratio sits on a near-zero denominator. The dollars are kept.")
add("| run | least liquid | middle | most liquid |")
add("|---|---|---|---|")
for s, mo, fee in RUNS:
    r = J[s]["reprice"][f"{s} open{mo} {fee}"]
    cells = []
    for t in TIERS:
        k = FB + "|" + t
        if k not in r:
            cells.append("n/a")
            continue
        nm = r[k]["gross_close"] <= 0 or r[k]["gross_close"] < 0.05 * r[FB + "|ALL TIERS"]["gross_close"]
        cells.append(f"{'n/m' if nm else p(r[k]['gross_ratio'])} (n {r[k]['n']:,}, close gross {usd(r[k]['gross_close'])}, mid gross {usd(r[k]['gross_mid'])})")
    add(f"| {s} open{mo} {fee} | " + " | ".join(cells) + " |")
add()
add("### B - C, per fill")
add("B minus C over twice the notional of the filled matched trades, in bp, as a check that the gap between B and C is the spread and depth cost (fees can differ; plus-minus 1 minute and proxy rows are priced off the close). The cost decomposition of costs_analysis for the same trades is in the log next to each line.")
add("| run | B - C bp per fill (ctxs + G8 fallback) | costs_analysis mean cost per leg-fill, bp (same trades) |")
add("|---|---|---|")
for s, mo, fee in RUNS:
    r = J[s]["reprice"][f"{s} open{mo} {fee}"]
    add(f"| {s} open{mo} {fee} | {r[FB + '|B_minus_C_bp_per_fill']:.2f} | {DEC[f'{s} open{mo} {fee}'][2]:.2f} |")
_gap = {}
for s_, mo_, fee_ in RUNS:
    if fee_ == "taker":
        _gap.setdefault(s_, []).append(abs(J[s_]["reprice"][f"{s_} open{mo_} {fee_}"][FB + "|B_minus_C_bp_per_fill"] - DEC[f"{s_} open{mo_} {fee_}"][2]))
add(f"For taker runs B - C differs from the leg cost by {min(_gap['vault']):.1f} to {max(_gap['vault']):.1f} bp in the vault and {min(_gap['test']):.1f} to {max(_gap['test']):.1f} bp in test. For maker runs B - C is about twice the leg cost, because C also includes maker legs that were crossed as taker after the window, taker exits for timeouts and the adverse selection of the fills. The second column is read from the log of costs_nobounce.py (the costs_analysis decomposition on the same matched filled trades).")
add()
add("## Entry stretch: |z| from closes vs from mids (sigma)")
add("Gap share = sum(|z| - |z_mid|) / sum(|z|) on events that have the entry mid of both legs. Fresh = both entry closes had a trade in that minute; only that stratum's gap may be called bounce (an upper bound, see notes). Stale gap is stale price.")
add("| period | set | events | mean abs z | mean abs z_mid | gap share | gap share, fresh | gap share, stale | no stretch in mid terms |")
add("|---|---|---|---|---|---|---|---|---|")
for s in ("vault", "test"):
    for g in ("all events", "q1% picks"):
        a = J[s][f"stretch|{g}|ALL TIERS"]
        f_ = J[s][f"stretch_fresh|{g}|ALL TIERS|fresh"]
        st = J[s][f"stretch_fresh|{g}|ALL TIERS|stale"]
        add(f"| {s} | {g} | {a['n']:,} | {a['mean_z']:.3f} | {a['mean_zmid']:.3f} | {p(a['bounce_share'])} | {p(f_['gap_share'])} | {p(st['gap_share'])} | {p(a['share_no_stretch'])} |")
add()
add("Picks by tier (gap share, fresh / stale):")
add("| period | tier | picks | gap share | fresh | stale |")
add("|---|---|---|---|---|---|")
for s in ("vault", "test"):
    for t in TIERS:
        a = J[s][f"stretch|q1% picks|{t}"]
        f_ = J[s][f"stretch_fresh|q1% picks|{t}|fresh"]
        st = J[s][f"stretch_fresh|q1% picks|{t}|stale"]
        add(f"| {s} | {t} | {a['n']:,} | {p(a['bounce_share'])} | {p(f_['gap_share'])} | {p(st['gap_share'])} |")
add()
add("## Reversion in mid terms")
add("Reach = the spread got back to mu within the horizon. The close is tested only on the minutes where the mid exists (same-minutes comparator, decided after a smoke run found the missing minutes bias the mid reach down); the close on all minutes is the last column. Mean gross move in sigma at the horizon, close (same minute) and mid. Events already through mu at entry in mid terms count as not reached.")
add("| period | set | horizon | events | reach close (same minutes) | reach mid | reach close (all minutes) | gross move close | gross move mid | events through mu at entry (mid) |")
add("|---|---|---|---|---|---|---|---|---|---|")
for s in ("vault", "test"):
    for g in ("q1% picks", "all events"):
        for hh in (120, 300, 600):
            r = J[s][f"rev|{g}|ALL TIERS|{hh}"]
            add(f"| {s} | {g} | {hh // 60} h | {r['n']:,} | {p(r['reach_close'])} | {p(r['reach_mid'])} | {p(r['reach_close_all_minutes'])} | {r['mv_close']:.3f} | {r['mv_mid']:.3f} | {p(r['through_at_entry'])} |")
add()
add("Picks, 10 h, by tier:")
add("| period | tier | picks | reach close (same minutes) | reach mid | gross move close | gross move mid |")
add("|---|---|---|---|---|---|---|")
for s in ("vault", "test"):
    for t in TIERS:
        r = J[s][f"rev|q1% picks|{t}|600"]
        add(f"| {s} | {t} | {r['n']:,} | {p(r['reach_close'])} | {p(r['reach_mid'])} | {r['mv_close']:.3f} | {r['mv_mid']:.3f} |")
add()
add("## Does p still rank in mid terms")
add("10-hour reach rate by quintile of raw p_10h (1 = lowest), close (same minutes) vs mid, and the lift at the top 1% (reach of the q 1% picks / reach of all events). Test months pool the predictions of different fold models.")
add("| period | q1 close / mid | q2 | q3 | q4 | q5 | lift top 1%, close | lift top 1%, mid |")
add("|---|---|---|---|---|---|---|---|")
for s in ("vault", "test"):
    rk = J[s]["ranking"]
    qs = rk["quintiles"]
    add(f"| {s} | " + " | ".join(f"{p(x['close'])} / {p(x['mid'])}" for x in qs) + f" | {rk['lift_close']:.2f}x | {rk['lift_mid']:.2f}x |")
add()
add("## Coverage and the two mids")
add("Share of events without the entry mid of both legs (ctxs cache), by month:")
add("| period | month | events | no mid |")
add("|---|---|---|---|")
for s in ("vault", "test"):
    for k in sorted(k for k in J[s] if k.startswith("lost_month|") and k.endswith("|ALL")):
        r = J[s][k]
        add(f"| {s} | {k.split('|')[1]} | {r['n']:,} | {p(r['lost_share'])} |")
add()
add("Trades with all four mids, ctxs only vs with the G8 fallback (all four run files):")
add("| run | trades | coverage, ctxs only | coverage, with fallback |")
add("|---|---|---|---|")
for s, mo, fee in RUNS:
    r = J[s]["reprice"][f"{s} open{mo} {fee}"]
    add(f"| {s} open{mo} {fee} | {r['n']:,} | {p(r['cover_ctxs'])} | {p(r['cover_fallback'])} |")
add()
add("ctxs mid vs G8 table mid on the (coin, minute) pairs both have, in bp:")
add("| period | tier | pairs | median | p90 | p99 | share within 1 bp |")
add("|---|---|---|---|---|---|---|")
for s in ("vault", "test"):
    for t in ["ALL"] + TIERS:
        r = J[s]["g8_check"][t]
        add(f"| {s} | {t} | {r['n']:,} | {r['p50']:.3f} | {r['p90']:.2f} | {r['p99']:.2f} | {p(r['within1'])} |")
add()
add("Receipts: close-based reach and time to mu recomputed by the script equal labels.parquet on every event of both periods (counts in the log); the saved gross is reproduced from the cleaned closes on every trade of the eight runs; the close |z| equals the saved |z|.")
add()
add("## Notes (what the numbers are and are not)")
add("- The signal is still built from closes. A signal built from mids is NOT tested here.")
add("- The engine's close is the last trade, which can be older than the mid snapshot. 'Fresh' means a trade in that minute, not at the end of it, so a fresh close can still be up to 59 seconds older than the mid. The fresh stratum's gap is therefore an upper bound on bounce, and the stale stratum's gap is stale price.")
add("- The ctxs mid and the G8 table mid disagree by more than 1 bp on a large share of minutes (table above). Either one is a few seconds after the bar's last trade. The fallback mixes the two sources inside some trades. Results with the fallback and without it differ, and the ctxs-only set leans to the earlier months.")
PT = json.load(open(C1 + "process_times.json"))
add(f"- The same-minutes close comparator was decided after a smoke run of about 3,000 vault events. Process, from this session's own transcript timestamps (UTC, diagnostics/costs_process_times.py): the planner's rulings on the G8 fallback, the gross-ratio bands and the 'close vs mid gap' label reached the builder at {PT['planner_rulings']}; the first smoke run (event-level statistics only, no trade table) first appears in the transcript at {PT['first_smoke_event_level']}; the smoke run that first printed the vault trade table (it ran the rewritten reprice()) first appears in the transcript at {PT['smoke_with_vault_trade_table']}. The rulings came first. The 25% and 75% band values were in the original brief.")
add("- Test-month quintiles pool the predictions of different fold models.")
add("- Findings are reported, not acted on. No pick, exit or parameter was changed.")
open(C1 + "costs_nobounce_section.md", "w").write("\n".join(L) + "\n")
print(f"[NOBOUNCE-SECTION] wrote logs/costs1/costs_nobounce_section.md ({len(L)} lines) from costs_nobounce.json sha256 {SRC}")
