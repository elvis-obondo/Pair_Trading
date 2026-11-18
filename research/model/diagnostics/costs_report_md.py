"""COSTS1 Word report, step 1: build one markdown file from saved outputs. Every number is read from a json, a log
or a section file written by a script; no result number is typed here. Step 2 (costs_docx_render.js) turns the markdown
into the .docx.
  python3 research/model/diagnostics/costs_report_md.py
Output: research/model/logs/costs1/costs_report.md   (log: diagnostics/costs_report_md.log)
"""
import json, re, hashlib, pathlib
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[3]
C1 = ROOT / "research/model/logs/costs1"
DG = ROOT / "research/model/diagnostics"
OUT = C1 / "costs_report.md"

J = lambda n: json.load(open(C1 / n))
cons, cal = J("costs_analysis_conservative.json"), J("costs_analysis_calibrated.json")
val, legs, nb, pt = J("costs_validate.json"), J("costs_legs.json"), J("costs_nobounce.json"), J("process_times.json")
rd = lambda p: pathlib.Path(p).read_text(errors="ignore")
L_AN, L_AC, L_VAL, L_T2 = (rd(DG / n) for n in ["costs_analysis.log", "costs_analysis_calibrated.log", "costs_validate.log", "costs_t2.log"])

money = lambda x, d=2: ("-$" if x < 0 else "$") + f"{abs(x):,.{d}f}"
pct = lambda x, d=1: f"{x*100:.{d}f}%"
num = lambda x, d=2: f"{x:,.{d}f}"
md = []
A = md.append


def table(headers, rows):
    A("| " + " | ".join(headers) + " |")
    A("|" + "|".join(["---"] * len(headers)) + "|")
    for r in rows:
        A("| " + " | ".join(str(x) for x in r) + " |")
    A("")


def logline(text, pattern):
    for ln in text.splitlines():
        if re.search(pattern, ln):
            return re.sub(r"^\[[^\]]+\]\s*", "", ln).strip()
    raise SystemExit(f"pattern not found: {pattern}")


def loglines(text, pattern):
    return [re.sub(r"^\[[^\]]+\]\s*", "", ln).strip() for ln in text.splitlines() if re.search(pattern, ln)]


def embed(path, skip_titles=(), drop_first_h1=True):
    """Embed a section file, headings pushed one level down; sections whose '## title' starts with a skip prefix are cut."""
    out, skipping = [], False
    for i, ln in enumerate(rd(path).splitlines()):
        if i == 0 and drop_first_h1 and ln.startswith("# "):
            continue
        if ln.startswith("## "):
            skipping = any(ln[3:].startswith(s) for s in skip_titles)
        if skipping:
            continue
        out.append("#" + ln if ln.startswith("#") else ln)
    return out


RUNS = ["vault open10 maker", "vault open10 taker", "vault open20 maker", "vault open20 taker",
        "test open10 maker", "test open10 taker", "test open20 maker", "test open20 taker"]
CFG = cons["configs"]

# ---------------------------------------------------------------- title and verdict
A("# HL-COSTS1: does the edge survive realistic execution costs?")
A("")
A("## 1. Verdict")
A("")
vl, vc = cons["verdict"], cal["verdict"]
A(f"**Verdict letter ({vl['letter']}): the edge does not survive.** Under the table-based straight-line curve, none of the four vault headline nets is above zero "
  f"({', '.join(f'{k} {money(v)}' for k, v in vl['nets'].items())}). Under the calibrated variant the letter is also ({vc['letter']}) "
  f"({', '.join(f'{k} {money(v)}' for k, v in vc['nets'].items())}).")
A("")
A("Letters: (a) survives broadly = all four vault headline nets above zero and at least 75% of the sensitivity cells of each above zero; "
  "(c) does not survive = none of the four above zero; (b) survives only in named coins or sizes = anything else. The rule was fixed before any result. "
  "The letter is a label, not a recommendation to change the plan.")
A("")
cells = ", ".join(f"{k}: {v[0]} of {v[1]}" for k, v in vl["cells"].items())
A(f"Sensitivity cells with a positive net (vault, conservative curve): {cells}.")
A("")
A("### 1.1 Conclusion")
A("")
assert all(CFG[r]["head"]["net"] < 0 for r in RUNS), "a costed net is not negative: conclusion text must change"
A("Conclusion: **(c) does not survive.** At the saved sizes and signals, costs take the edge below zero in all four vault configurations and in all four test-month configurations. "
  "Costs are reported, not optimised around: no q, stop, timeout or pick was changed in this analysis. The conclusion rests on these caveats:")
A("")
t20 = cons["beyond_versions"]["test open20 maker"]
T20 = pd.read_parquet(C1 / "l2_targets_test20.parquet")
n_files, n_cd = len(T20), len(T20[["coin", "day"]].drop_duplicates())
tier_legs = ", ".join(re.findall(r"tier (least liquid third|middle third|most liquid third), S<=1000: legs below \d+ of ([\d,]+)", L_VAL) and
                      [f"{t} {n}" for t, n in re.findall(r"tier (least liquid third|middle third|most liquid third), S<=1000: legs below \d+ of ([\d,]+)", L_VAL)])
proxy_rows = re.findall(r"^\[COSTS\]   ((?:vault|test) open\d+ (?:maker|taker)): lookups ([\d,]+):.*?trades touching a proxy lookup ([\d.]+)%", L_AN, re.M)
pr = [float(x[2]) for x in proxy_rows]
for t in [
    f"The curve is not conservative. Validation trigger T4 fired: the table curve is below the exact book walk on {pct(val['share_below_le1000'])} of validation legs at sizes up to $1,000 and on {pct(val['share_below_all'])} of all validation legs (limit 5%).",
    f"Beyond-book legs cannot be priced from the table. Test open20 maker is {money(t20['without_beyond'])} without those trades and {money(t20['headline_remainder'])} with them.",
    f"The validation sample is small: {n_files} files, {n_cd} coin-days. Validation legs at sizes up to $1,000 by tier: {tier_legs}.",
    "Maker queue position is not observed. The strict and lenient fill rules are a range, not a point estimate.",
    f"Some prices rest on the no-book proxy. Share of trades touching a proxy lookup, by run: {pct(min(pr)/100)} to {pct(max(pr)/100)} across the eight headline runs (printed per run in costs_analysis.log, BOOK SOURCES).",
]:
    A("- " + t)
A("")
A("### 1.2 Results by configuration")
A("")
A("Equity is $1,000 plus the cumulative daily net with sizing held as saved. It can go below zero, so a drawdown above 100% of the start is possible. "
  "Drawdown is shown in dollars and as a share of the $1,000 start.")
A("")
rows = []
for r in RUNS:
    c = CFG[r]
    rows.append([r, money(c["zero"]["net"]), money(c["head"]["net"]), f"{c['zero']['pf']:.2f} / {c['head']['pf']:.2f}",
                 f"{c['zero']['sharpe']:.2f} / {c['head']['sharpe']:.2f}",
                 f"{money(c['zero']['mdd_usd'])} ({pct(c['zero']['mdd_usd']/1000)} of start) / {money(c['head']['mdd_usd'])} ({pct(c['head']['mdd_usd']/1000)} of start)",
                 f"{c['n_filled']:,} of {c['n_saved']:,}", f"{c['cells_pos']} of {c['cells_n']}",
                 f"{c['be_zero']:.2f} / {c['be_model']:.2f}"])
table(["run", "net zero-cost", "net with costs", "profit factor (zero / costed)", "Sharpe (zero / costed)",
       "max drawdown (zero-cost / costed)", "filled of saved", "positive cells", "break-even bp (arithmetic / model)"], rows)
A("Headline cell: maker runs use the strict fill rule, waiting window 5 minutes, impact multiplier 1; taker runs use multiplier 1. "
  "Profit factor, Sharpe and drawdown come from daily realised P&L by exit day. Sharpe is the daily mean over the daily standard deviation, annualised with the square root of 365.")
A("")
A("### 1.3 The beyond-book trades and the curve artefact")
A("")
bv = cons["beyond_versions"]
rows = [[r, bv[r]["n_beyond"], money(bv[r]["headline_remainder"]), money(bv[r]["section8_whole"]), money(bv[r]["without_beyond"])] for r in RUNS]
table(["run", "trades with a beyond-book leg", "headline (curve remainder)", "whole leg at last level", "net without those trades"], rows)
t20 = bv["test open20 maker"]
vl_line = logline(L_VAL, r"BEYOND-BOOK LEGS")
vl2 = logline(L_VAL, r"headline \(remainder at last level\)")
A(f"**Reference number for test open20 maker: {money(t20['without_beyond'])}** (without the {t20['n_beyond']} trades that have a beyond-book leg). "
  f"The headline {money(t20['headline_remainder'])} is affected by the curve artefact on beyond-book legs and is labelled as such. Validation on the 20 raw files: {vl_line}. {vl2}.")
A("")
A("### 1.4 The curve wording")
A("")
A("Validation T4: " + logline(L_VAL, r"T4 FIRES").replace("'conservative'", "conservative"))
A("")
A("The curve is a straight line from the half-spread to the 1,000-dollar slippage point plus depth bands. It is called the table-based straight-line curve in this report, not conservative. "
  "On validation legs the curve sits below the exact book walk more often than the 5% limit, so the word conservative was withdrawn.")
A("")
A("### 1.5 Maker exit fee finding")
A("")
mef = cons["maker_exit_fee"]
A(logline(L_AN, "MAKER-EXIT FEE FINDING").replace("MAKER-EXIT FEE FINDING: ", ""))
A("")
A("This finding applies to the saved zero-cost maker nets (the reference columns), which charged the maker fee on stop and timeout exits. The costed headline numbers in 1.2 already charge the taker fee on every exit that is not a mu exit (costs_analysis.py, the exit branch: only maker runs with exit reason mu use the limit order and the maker fee; every other exit is a taker fill with the taker fee). So the headline costed nets do include this fee and are not changed by it; the saved zero-cost nets are the ones that fall by the amounts in the table.")
A("")
rows = [[r, f"{v['n']:,}", money(v["extra"]), money(v["net"]), pct(v["pct"]), f"{v['be0']:.2f}", f"{v['be1']:.2f}"] for r, v in mef.items()]
table(["run", "stop or timeout exits", "extra fee if charged as taker", "saved net (zero-cost)", "extra as share of net", "break-even bp (as saved)", "break-even bp (with the fee)"], rows)

# ---------------------------------------------------------------- assumptions
A("## 2. Assumptions")
A("")
for t in [
    "Signals, picks, sizes, exit times and exit reasons are exactly as saved. Only fills and costs are re-priced. Slippage in the saved runs is zero.",
    "Entry is priced at the close of label t0-1; exit at the close of label exit_time-1 (engine convention). Fees are the run's own fee mode: maker 0.015%, taker 0.045%.",
    "Costs come from the G8 table (the first snapshot of each coin-minute) through a straight-line curve: half-spread at size 0, the 1,000-dollar slippage point, and the 10, 25 and 50 bp depth bands. Beyond the last point the remainder is priced at the last level (an estimate, not a bound).",
    "No-book proxy: legs on a missing day, a missing minute, a crossed book or a NaN field are priced at half the ctxs impact spread. It is a weak proxy and the share of trades using it is printed.",
    "Maker fills: limit at the best bid or ask, waiting window 5 minutes (1 and 15 as sensitivity), strict and lenient fill rules as the range. No queue position is observed. A leg unfilled at the end of the window is crossed as taker; both legs unfilled means the trade is missed and its slot is not refilled.",
    "Equity is rebuilt from per-trade nets in exit order. Compounding, sizing and freed slots are not re-fed.",
    "Liquidity tiers are terciles of each coin's median daily traded notional; a trade takes its less liquid leg's tier.",
    "G8 days missing from the archive: " + re.search(r"days with a missing file \d+.*", logline(L_AN, "EXTRACT RECEIPT")).group(0).split("; ")[-1] + ". They are absent from the raw archive itself.",
    "BTC data in the one-leg check: the 30-minute BTC.feather (user_data/normalized/BTC.feather). BTC is not in the cleaned 1-minute price set and there is no 1-minute BTC in the cache. The BTC price is up to 30 minutes old at both ends, which blurs slopes toward zero. No rerun was done.",
    "No-bounce check: the matched comparator tests the close only on minutes where the mid exists. That comparator was decided after a smoke run on a sample of events (a missing mid minute can only hide a crossing, so the mid reach was biased low). The run order is in section 6.",
    "Leverage caps are today's snapshot, not historical limits. Nothing is simulated with different caps.",
]:
    A("- " + t)
A("")
A(logline(L_AN, r"tiers vault"))
A("")
A(logline(L_AN, r"tiers test"))
A("")

# ---------------------------------------------------------------- results by tier
A("## 3. Results by liquidity tier")
A("")
A("Columns: trades saved, trades filled, zero-cost net, costed net. A trade takes its less liquid leg's tier.")
A("")
G = cons["groups"]
for r in RUNS:
    A(f"**{r}**")
    A("")
    table(["tier", "saved", "filled", "net zero-cost", "net with costs"], [[g[0], f"{int(g[1]):,}", f"{int(g[2]):,}", money(g[3]), money(g[4])] for g in G[f"{r} | liquidity tier"]])
    pos = [g for g in G[f"{r} | liquidity tier"] if g[4] > 0]
tot_pos = sum(1 for r in RUNS for g in G[f"{r} | liquidity tier"] if g[4] > 0)
A(f"Tier cells with a positive costed net: {tot_pos} of {len(RUNS) * 3}. "
  "A positive tier cell is a hypothesis for later, not a result; no group was chosen.")
A("")
A("### 3.1 Larger-leg size")
A("")
for r in RUNS:
    A(f"**{r}**")
    A("")
    table(["larger-leg size", "saved", "filled", "net zero-cost", "net with costs"], [[g[0], f"{int(g[1]):,}", f"{int(g[2]):,}", money(g[3]), money(g[4])] for g in G[f"{r} | larger-leg size"]])

# ---------------------------------------------------------------- answers
A("### 3.2 Positive cells across the cuts")
A("")
cuts = ["liquidity tier", "larger-leg size", "leverage"]
pos_cells = [(r, c, g) for r in RUNS for c in cuts for g in G[f"{r} | {c}"] if g[4] > 0]
tot_cells = sum(len(G[f"{r} | {c}"]) for r in RUNS for c in cuts)
runs_pos = sorted(set(r for r, _, _ in pos_cells))
A(f"{len(pos_cells)} of {tot_cells} cells across the tier, size and leverage cuts have a positive costed net. They are in: {', '.join(runs_pos)}. "
  f"Cells with a positive net hold {min(int(g[2]) for _, _, g in pos_cells)} to {max(int(g[2]) for _, _, g in pos_cells)} filled trades. No group was chosen; no correction was made for the number of cells.")
A("")
table(["run", "cut", "group", "filled", "net with costs"], [[r, c, (f"{g[0]:g}x" if c == "leverage" else g[0]), f"{int(g[2]):,}", money(g[4])] for r, c, g in pos_cells])
A("## 4. Answers to the two questions")
A("")
A("### 4.1 (a) Volume versus depth")
A("")
A("Question: does a leg's size relative to the coin's traded notional in the entry minute explain the walk cost beyond the half-spread? Fit: walk (bp) = intercept + slope x sqrt(leg / minute notional), on taker entry legs with a book in their own minute.")
A("")
vf = cons["volume_fit"]
table(["period", "legs fitted", "intercept (bp)", "slope", "R squared", "rank correlation", "share of legs above 10% of minute notional"],
      [[p, f"{vf[p]['n']:,}", f"{vf[p]['intercept']:.2f}", f"{vf[p]['slope']:.2f}", f"{vf[p]['r2']:.3f}", f"{vf[p]['rho']:.3f}", pct(vf[p]["share_above_10pct"])] for p in ["vault", "test"]])
for ln in loglines(L_AN, r"^\[COSTS\]   (vault|test): legs with a minute notional|^\[COSTS\]      (least|middle|most) (liquid )?third: n [\d,]+, slope"):
    A(("- " if re.match(r"(vault|test):", ln) else "    - ") + ln)
A("")
A(f"Reading: the fit explains little of the variation (R squared at most {max(vf[p]['r2'] for p in vf):.3f}); the rank correlation of {min(vf[p]['rho'] for p in vf):.2f} to {max(vf[p]['rho'] for p in vf):.2f} shows a weak positive link; most legs are large against the minute's volume ({pct(min(vf[p]['share_above_10pct'] for p in vf))} to {pct(max(vf[p]['share_above_10pct'] for p in vf))} are above 10% of the minute's traded notional).")
A("")
A("### 4.2 (b) Leverage groups")
A("")
A("Trades and net by the coin's maximum leverage (today's snapshot). Leverage changes sizing, not signals; nothing is simulated.")
A("")
for r in RUNS:
    A(f"**{r}**")
    A("")
    table(["max leverage", "saved", "filled", "net zero-cost", "net with costs"], [[f"{g[0]:g}x", f"{int(g[1]):,}", f"{int(g[2]):,}", money(g[3]), money(g[4])] for g in G[f"{r} | leverage"]])

# ---------------------------------------------------------------- validation
A("## 5. Validation of the curve (T1 to T4)")
A("")
A(f"The {n_files} raw L2 files of the validation sample ({n_cd} coin-days). The G8 table row is recomputed from the raw book and the curve is compared with the exact book walk at seven sizes.")
A("")
for lab, pat in [("Sample", r"ASKED vs FOUND"), ("Reproduction (i)", r"\(i\)\] REPRODUCTION"), ("T1", r"\[VALID T1\]"), ("T3", r"\[VALID T3\]"), ("T4", r"\[VALID T4\] curve below")]:
    A(f"- {lab}: " + logline(L_VAL, pat))
A("- T2: " + logline(L_T2, r"sign flips"))
A("")
assert (val["T1"], val["T3"], val["T4"]) == (False, False, True) and "letter differs: False" in L_T2 and "sign flips in []" in L_T2, "trigger text must change"
A("T1 (overstatement), T2 (verdict flip) and T3 (reproduction) do not fire. T4 (understatement) fires. A fired trigger means " + re.search(r"the full [\d,]+-file raw pull", L_VAL).group(0) + " would be asked of the user, with the cost range printed. "
  "That pull has not been asked and is the user's and the planner's decision. The verdict letter and every sign are unchanged between the conservative and the calibrated variant.")
A("")
A("Curve minus exact book walk, by size (a negative value means the curve is below the exact walk):")
A("")
rows = []
for s, v in val["by_S"].items():
    rows.append([f"${int(s):,}", f"{v['n']:,}", f"{v['mean']:.3f}", f"{v['median']:.3f}", f"{v['p90']:.3f}", f"{v['mn']:.3f}", pct(v["share_below"])])
table(["size S", "legs", "mean overstatement (bp)", "median", "p90", "min (negative = understatement)", "share curve below exact"], rows)

# ---------------------------------------------------------------- time
A("## 6. How long each piece took")
A("")
tm = cons["TIMES"]
tc = cal["TIMES"]
tot_c = logline(L_AN, r"total run time")
rows = [["G8 extraction on EC2 Tokyo (log)", logline(rd(C1 / "g8/extract.log"), r"\[G8X\] done").split(" in ")[-1].replace("s", " s")]]
rows += [[f"costs_analysis, conservative: {k}", f"{v:.1f} s"] for k, v in tm.items()]
rows += [[f"costs_analysis, calibrated: {k}", f"{v:.1f} s"] for k, v in tc.items()]
rows += [["costs_analysis, conservative: total", tot_c.split(";")[0].replace("total run time ", "").replace("s", " s")]]
rows += [["costs_validate (20 raw files)", "not timed in its log"]]
rows += [["no-bounce script (both periods, every event)", logline(rd(DG / "costs_nobounce.log"), r"total \d+s").split("total ")[-1].replace("s", " s")]]
rows += [["one-leg script (eight runs)", logline(rd(DG / "costs_legs.log"), r"total \d+s").split("total ")[-1].replace("s", " s")]]
table(["piece", "time"], rows)
A("Process order of the no-bounce check, from the transcript's own timestamps (UTC): "
  f"checker review of the rules (no code) {pt['checker_review_no_code']}; planner rulings {pt['planner_rulings']}; "
  f"first smoke run (event level) {pt['first_smoke_event_level']}; smoke run with the vault trade table {pt['smoke_with_vault_trade_table']}. "
  "The smoke runs printed vault trade numbers before review. The builder states that no rule was changed because of the trade numbers; the order of events rests on the timestamps and that statement.")
A("")

# ---------------------------------------------------------------- embedded parts
A("## 7. Entry delay: engine-change write-up (text only, nothing run)")
A("")
md.extend(embed(C1 / "costs_entry_delay_writeup.md", drop_first_h1=True))
A("")
A("## 8. No-bounce check: close vs mid gap")
A("")
md.extend(embed(C1 / "costs_nobounce_section.md"))
A("")
A("## 9. One-leg check: is the profit mostly generated by one leg?")
A("")
A("Left out here to keep the report readable: the raw-version mover split, and all splits in mid prices. They are in logs/costs1/costs_legs_section.md.")
A("")
md.extend(embed(C1 / "costs_legs_section.md", skip_titles=("Split: mover vs hedge (raw)", "Split: long vs short (mid", "Split: mover vs hedge (beta-adjusted, HEADLINE) (mid", "Split: mover vs hedge (raw) (mid", "Split: larger vs smaller leg (mid", "Long vs short on opposite-direction pairs only (mid")))
A("")

# ---------------------------------------------------------------- sources
A("## 10. Where every number comes from")
A("")
files = ["costs_analysis_conservative.json", "costs_analysis_calibrated.json", "costs_validate.json", "costs_legs.json", "costs_nobounce.json",
         "costs_nobounce_section.md", "costs_legs_section.md", "costs_entry_delay_writeup.md", "process_times.json"]
for f in files:
    A(f"- logs/costs1/{f} (sha256 {hashlib.sha256((C1 / f).read_bytes()).hexdigest()[:12]})")
for f in ["costs_analysis.log", "costs_analysis_calibrated.log", "costs_validate.log", "costs_t2.log", "costs_nobounce.log", "costs_legs.log"]:
    A(f"- diagnostics/{f}")
A("- Scripts: diagnostics/costs_analysis.py, costs_validate.py, costs_nobounce.py, costs_nobounce_sources.py, costs_legs.py, costs_legs_section.py, costs_nobounce_section.py, costs_delay_writeup.py, costs_report_md.py; rules: costs1_rules.md.")
A("")
OUT.write_text("\n".join(md) + "\n")
print(f"[REPORT] wrote {OUT} ({len(md)} lines); sha256 {hashlib.sha256(OUT.read_bytes()).hexdigest()[:12]}")
