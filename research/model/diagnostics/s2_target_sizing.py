"""S2 target, STEP A sizing (planner order 2026-11-20). Prints what the label build would have to read and how big it is. No label is built, no price path is read, no outcome is read.
Reads: the search event list (harness.load_search_events: events + labels files, usable events as S1 used; the search side is open), the vault event list from vault_loader.load_vault_event_dates
(events.parquet geometry only, never labels.parquet), saved COSTS1 json for ctxs coverage numbers, the 11 local G8 day files (size/row/completeness sample), the local ctxs and fundinghist caches (file names and time ranges only).
Output: diagnostics/s2_target_sizing.log (this script's stdout). Every number in the sizing report to the planner comes from this log.
"""
import glob
import json
import os
import shutil
import sys

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.dirname(HERE)
sys.path.insert(0, MODEL)
import harness as H  # noqa: E402
import vault_loader as VL  # noqa: E402

C1 = os.path.join(MODEL, "logs", "costs1") + os.sep
P1 = os.path.join(MODEL, "logs", "profit1") + os.sep
# G8 archive gaps: DATASET_DICTIONARY.md G8 section, 'Order-book archive gaps': 21 days entirely absent
ABSENT = (["2025-10-%02d" % d for d in range(17, 23)] + ["2025-11-%02d" % d for d in range(18, 26)] + ["2026-07-08"] + ["2026-07-%02d" % d for d in range(12, 18)])
G8_DAYS_TABLES = 496   # same section: '517 days in the extraction index: 496 day tables, 21 days entirely absent'


def log(m):
    print(m, flush=True)


def pct(a, b):
    return f"{100 * a / b:.1f}%"


def main():
    assert len(ABSENT) == 21
    S = H.load_search_events(columns=["ticker_a", "ticker_b"])
    S = S.reset_index(drop=True) if "event_id" in S.columns else S.reset_index()
    V = VL.load_vault_event_dates().reset_index(drop=True)
    for nm, E in (("search (usable, as S1)", S), ("vault (events.parquet, no labels read)", V)):
        log(f"[SIZING] events {nm}: {len(E):,}; t0 {E['t0'].min()} .. {E['t0'].max()}; coins {len(set(E['ticker_a']) | set(E['ticker_b']))}")
    coins = sorted(set(S["ticker_a"]) | set(S["ticker_b"]) | set(V["ticker_a"]) | set(V["ticker_b"]))
    log(f"[SIZING] coins over all events: {len(coins)}")
    nb = json.load(open(C1 + "costs_nobounce.json"))
    log(f"[SIZING] test months (folds 1-7) events from the saved no-bounce json: {nb['test']['lost|all events|ALL TIERS']['n']:,}")
    allt = pd.concat([S[["t0"]].assign(side="search"), V[["t0"]].assign(side="vault")], ignore_index=True)
    allt["month"] = allt["t0"].dt.strftime("%Y-%m")
    log("[SIZING] events by month (search | vault): " + "; ".join(f"{m} {int(((allt.month == m) & (allt.side == 'search')).sum()):,}|{int(((allt.month == m) & (allt.side == 'vault')).sum()):,}" for m in sorted(allt.month.unique())))
    # ctxs cache range (file names only)
    days = sorted(os.path.basename(f)[:8] for f in glob.glob(P1 + "ctxs_cache/*.parquet"))
    first_ctxs = pd.Timestamp(days[0], tz="UTC")
    last_ctxs = pd.Timestamp(days[-1], tz="UTC") + pd.Timedelta(days=1)
    log(f"[SIZING] local ctxs cache: {len(days)} day files, {days[0]} .. {days[-1]}")
    for nm, E in (("search", S), ("vault", V)):
        pre = int((E["t0"] < first_ctxs).sum())
        post = int((E["t0"] + pd.Timedelta(minutes=600) >= last_ctxs).sum())
        log(f"[SIZING] {nm}: events with t0 before the first ctxs day {pre:,} of {len(E):,} ({pct(pre, len(E))}): their mids can come from the G8 table only; events whose 10 h window runs past the last ctxs day: {post:,}")
    # absent G8 days: events whose 10 h window touches one
    ab = [pd.Timestamp(d, tz="UTC") for d in ABSENT]
    for nm, E in (("search", S), ("vault", V)):
        t0, t1 = E["t0"], E["t0"] + pd.Timedelta(minutes=600)
        touch = np.zeros(len(E), bool)
        for d in ab:
            touch |= ((t0 < d + pd.Timedelta(days=1)) & (t1 >= d)).to_numpy()
        no_ctxs = (E["t0"] < first_ctxs).to_numpy()
        log(f"[SIZING] {nm}: events whose 10 h window touches one of the 21 days absent from the G8 archive: {int(touch.sum()):,} ({pct(int(touch.sum()), len(E))}); of those with no ctxs mid either (t0 before the first ctxs day): {int((touch & no_ctxs).sum()):,}")
    # ctxs-only coverage measured by COSTS1 (no-bounce json), read from the file
    for side in ("test", "vault"):
        r = nb[side]["lost|all events|ALL TIERS"]
        log(f"[SIZING] COSTS1 no-bounce (ctxs mid only, as measured there): {side}: events {r['n']:,}; entry mid missing for at least one leg {r['lost']:,} ({pct(r['lost'], r['n'])}); of the {r['matched']:,} with both entry mids, {r['with_missing_path_minute']:,} ({pct(r['with_missing_path_minute'], r['matched'])}) miss a mid in at least one minute of the 10 h path")
    # G8 day files: size and completeness sample (the 11 local validation days)
    gf = sorted(glob.glob(C1 + "g8_validate_days/*_l2.parquet"))
    rows = []
    for f in gf:
        pf = pq.ParquetFile(f)
        d = pq.read_table(f, columns=["coin", "minute", "mid", "crossed"]).to_pandas()
        n_coin = d["coin"].nunique()
        cells = n_coin * 1440
        rows.append(dict(day=os.path.basename(f)[:8], mb=os.path.getsize(f) / 1e6, rows=pf.metadata.num_rows, coins=n_coin, share=pf.metadata.num_rows / cells, mid_ok=float((d["mid"] > 0).mean()), crossed=float((d["crossed"] == 1).mean())))
    R = pd.DataFrame(rows)
    log("[SIZING] G8 day files (local sample of 11): " + "; ".join(f"{r.day} {r.mb:.1f} MB, {r.rows:,} rows, {r.coins} coins, rows/cells {100 * r.share:.1f}%, mid>0 {100 * r.mid_ok:.1f}%, crossed {100 * r.crossed:.2f}%" for r in R.itertuples()))
    mb = float(R["mb"].mean())
    log(f"[SIZING] G8 full table estimate (ESTIMATE: mean file size of the 11-day sample x {G8_DAYS_TABLES} day tables): {mb * G8_DAYS_TABLES / 1e3:.1f} GB to read; slim copy needs coin, minute, mid, spread_bp, crossed only")
    n_days = (pd.Timestamp("2026-10-14", tz="UTC") - pd.Timestamp("2025-06-01", tz="UTC")).days + 1
    mat = len(coins) * n_days * 1440 * 8 / 1e9
    log(f"[SIZING] in-memory per-coin-minute matrix over {n_days} days x {len(coins)} coins: float64 {mat:.2f} GB per matrix (log mid; a second for half-spread; a ctxs and a G8 version are merged into one)")
    # funding history: file names and time ranges
    fh = sorted(glob.glob(P1 + "fundinghist_cache/*.parquet"))
    have = {os.path.basename(f)[:-8] for f in fh}
    lo = min(pd.read_parquet(f, columns=["time"])["time"].min() for f in fh)
    hi = max(pd.read_parquet(f, columns=["time"])["time"].max() for f in fh)
    miss = [c for c in coins if c not in have]
    log(f"[SIZING] local fundinghist cache: {len(fh)} coins, rows' time {lo} .. {hi}; event coins without a funding file: {len(miss)} {miss[:12]}")
    # availability on the 11 local sample days: events whose whole 10 h window lies inside the sample day (t0 before 14:00 UTC)
    sample_availability(S, V, coins)
    depth_check()
    # disk
    du = shutil.disk_usage(MODEL)
    log(f"[SIZING] local disk: free {du.free / 1e9:.1f} GB of {du.total / 1e9:.1f} GB")
    n_ev = len(S) + len(V)
    log(f"[SIZING] output size (ESTIMATE): {n_ev:,} events x about 28 columns x 4-8 bytes = {n_ev * 28 * 6 / 1e9:.1f} GB in memory, about a third of that as parquet")
    log(f"[SIZING] gathers for the path scan (ESTIMATE basis): {n_ev:,} events x 600 minutes x 2 legs = {n_ev * 600 * 2 / 1e9:.1f} billion; COSTS1 no-bounce streamed {nb['test']['lost|all events|ALL TIERS']['n'] + nb['vault']['lost|all events|ALL TIERS']['n']:,} events (both periods, close and mid paths) in 176 s (costs_nobounce.log, 'total 176s'); scaled linearly to {n_ev:,} events: {176 * n_ev / (nb['test']['lost|all events|ALL TIERS']['n'] + nb['vault']['lost|all events|ALL TIERS']['n']):.0f} s (ESTIMATE, one path instead of two but extra funding and half-spread lookups)")


def sample_availability(S, V, coins):
    """Print-only, no price used: is a usable mid there at every minute of an event's 10 h window? usable = G8 mid > 0 ('G8 alone'), ctxs mid_px > 0 ('ctxs alone'), either.
    Events: search and vault events with t0 on a sample day before 14:00 UTC (the whole window lies inside the day). A pair-minute is missing when either leg's mid is missing.
    Gap = a run of consecutive missing pair-minutes in path minutes 1..600; 'flagged' = some gap longer than 5 minutes (the planner's rule is tested on 1..exit; the full window is the upper bound)."""
    cid = {c: i for i, c in enumerate(coins)}
    E = pd.concat([S[["t0", "ticker_a", "ticker_b"]], V[["t0", "ticker_a", "ticker_b"]]], ignore_index=True)
    E["day"] = E["t0"].dt.strftime("%Y%m%d")
    E["mod"] = (E["t0"].dt.hour * 60 + E["t0"].dt.minute)
    E = E[E["mod"] <= 839]
    acc = {k: dict(n=0, entry_miss=0, any_gap=0, flagged=0, flagged_leg=0, miss_min=0, runs=np.zeros(6, dtype=np.int64)) for k in ("G8 alone", "ctxs alone", "either")}
    edges = [1, 2, 3, 6, 11, 31]    # buckets: 1, 2, 3-5, 6-10, 11-30, 31+
    nm = ["1", "2", "3-5", "6-10", "11-30", "31+"]
    days_used = []
    for f in sorted(glob.glob(C1 + "g8_validate_days/*_l2.parquet")):
        day = os.path.basename(f)[:8]
        ev = E[E["day"] == day]
        cf = P1 + f"ctxs_cache/{day}.parquet"
        if ev.empty or not os.path.exists(cf):
            continue
        d0 = int(pd.Timestamp(day, tz="UTC").value // 60_000_000_000)
        g = pq.read_table(f, columns=["coin", "minute", "mid"]).to_pandas()
        g = g[(g["mid"] > 0) & (g["minute"] >= d0) & (g["minute"] < d0 + 1440)]
        c = pd.read_parquet(cf, columns=["time", "coin", "mid_px"])
        off = (c["time"].dt.second != 0) | (c["time"].dt.microsecond != 0)
        c = c[~off & (c["mid_px"] > 0)]
        cm = (c["time"].astype("int64") // 60_000_000_000 if str(c["time"].dtype).endswith("ns, UTC]") else c["time"].dt.tz_convert("UTC").astype("datetime64[ns, UTC]").astype("int64") // 60_000_000_000)
        c = c.assign(minute=cm.to_numpy())
        c = c[(c["minute"] >= d0) & (c["minute"] < d0 + 1440)]
        A = {k: np.zeros((len(coins), 1440), bool) for k in acc}
        for key, tab in (("G8 alone", g), ("ctxs alone", c)):
            ci = tab["coin"].astype(str).map(cid)
            ok = ci.notna().to_numpy()
            A[key][ci.to_numpy()[ok].astype(np.int64), (tab["minute"].to_numpy() - d0)[ok]] = True
        A["either"] = A["G8 alone"] | A["ctxs alone"]
        ia, ib = ev["ticker_a"].map(cid).to_numpy().astype(np.int64), ev["ticker_b"].map(cid).to_numpy().astype(np.int64)
        m0 = ev["mod"].to_numpy()
        idx = m0[:, None] + np.arange(601)[None, :]
        for key in acc:
            pair = A[key][ia[:, None], idx] & A[key][ib[:, None], idx]
            miss = ~pair[:, 1:]
            cur = np.zeros(len(ev), np.int64)
            mx = np.zeros(len(ev), np.int64)
            runs = np.zeros(6, dtype=np.int64)
            for k in range(600):
                mk = miss[:, k]
                ended = (cur > 0) & ~mk
                if ended.any():
                    runs += np.bincount(np.searchsorted(edges, cur[ended], side="right") - 1, minlength=6)
                cur = np.where(mk, cur + 1, 0)
                mx = np.maximum(mx, cur)
            tail = cur > 0
            if tail.any():
                runs += np.bincount(np.searchsorted(edges, cur[tail], side="right") - 1, minlength=6)
            mxl = np.zeros(len(ev), np.int64)           # longest run of ONE leg's own missing minutes (the planner's per-leg flag)
            for ix in (ia, ib):
                missl = ~A[key][ix[:, None], idx][:, 1:]
                curl = np.zeros(len(ev), np.int64)
                for k in range(600):
                    curl = np.where(missl[:, k], curl + 1, 0)
                    mxl = np.maximum(mxl, curl)
            a = acc[key]
            a["flagged_leg"] += int((mxl > 5).sum())
            a["n"] += len(ev)
            a["entry_miss"] += int((~pair[:, 0]).sum())
            a["any_gap"] += int((mx > 0).sum())
            a["flagged"] += int((mx > 5).sum())
            a["miss_min"] += int(miss.sum())
            a["runs"] += runs
        days_used.append(day)
    log(f"[SIZING] AVAILABILITY on the {len(days_used)} sample days {days_used} (events with t0 before 14:00 UTC so the 10 h window lies inside the day; a pair-minute is missing if either leg has no usable mid; no price read)")
    for key, a in acc.items():
        tot_runs = int(a["runs"].sum())
        log(f"[SIZING]   {key:10s}: events {a['n']:,}; entry mid missing {pct(a['entry_miss'], a['n'])}; mean missing path minutes per event {a['miss_min'] / a['n']:.1f} of 600; events with at least one missing path minute {pct(a['any_gap'], a['n'])}; events with a gap longer than 5 minutes: PER-LEG flag (headline, either leg's own run) {pct(a['flagged_leg'], a['n'])}, union flag (sensitivity) {pct(a['flagged'], a['n'])} (full-window upper bound); gap runs (union) {tot_runs:,} by length: " + ", ".join(f"{n} {pct(int(v), max(tot_runs, 1))}" for n, v in zip(nm, a["runs"])))
    log("[SIZING]   NOTE: this sample is 2026-01 to 2026-10 days only. G8 coverage in 2025-06 to 2025-11 (the only source for 2,269,015 search events) is NOT measured here: it is printed by the build's availability stage before any label (rules section 3).")


def depth_check():
    """Print-only, saved files only: is depth impact small next to the half-spread? Taker runs: B - C per fill (no-bounce section table; B - C is the spread-and-depth cost of the re-priced trades)
    against the G8 half-spread per fill of the same runs (costs_legs.json: half-spread dollars over the fill notional = saved taker fees / 0.00045)."""
    import re
    tab = {}
    for ln in open(C1 + "costs_nobounce_section.md"):
        m = re.match(r"\| ((?:vault|test) open\d+ taker) \| ([\d.]+) \| ([\d.]+) \|", ln)
        if m:
            tab[m.group(1)] = (float(m.group(2)), float(m.group(3)))
    legs = json.load(open(C1 + "costs_legs.json"))
    log("[SIZING] DEPTH CHECK (taker runs; saved files only): run | B - C bp per fill (no-bounce section) | costs_analysis mean cost per leg-fill bp | G8 half-spread bp per fill (costs_legs.json) | B - C minus half-spread")
    for r, (bc, ca) in tab.items():
        c = legs[r]["costs"]["ALL|larger vs smaller leg"]["cells"]
        hs = sum(v["half_spread"] for v in c.values())
        fees = sum(v["fees"] for v in c.values())
        hs_bp = hs / (fees / 0.00045) * 1e4
        log(f"[SIZING]   {r}: B - C {bc:.2f} bp | costs_analysis {ca:.2f} bp | half-spread {hs_bp:.2f} bp | B - C minus half-spread {bc - hs_bp:+.2f} bp ({(bc - hs_bp) / bc:.0%} of B - C)")
    log("[SIZING]   READING: this is a residual, not a bound. B - C is on the matched trade set and the half-spread on the trades that have a G8 row (different trade sets); B - C also includes the close-priced proxy rows and the +-1 minute rows.")


if __name__ == "__main__":
    main()
