"""HL-WALLET1 Part 2: wallet features at t = 0 for build 4's coin-level events and their matched control links.

    python -u research/dislocation_model/hl5_features.py [--days N] > research/dislocation_model/logs/hl5_features.log

INPUT. The build 5 tables (datasets/wallet5/{D}_wallet_bin.parquet = T1 per wallet, coin, 5-minute bin; {D}_wallet_day.parquet = T2;
{D}_vault.parquet = T3) and build 4's ev_events.parquet / ev_pairs.parquet (event bar label T, push sign d, coin). t = 0 is T + 30 min.
WINDOWS (build 4's), in minutes before t = 0: P1 [-60,0), P2 [-360,-60), P3 [-1440,-360), C6 [-360,0), C24 [-1440,0). All are
multiples of 5 minutes, so every window is a whole number of T1 bins and uses only bins < t = 0.

PUSHING SIDE. d > 0 (the coin dislocated up): the pushing side is the TAKER BUYS; d < 0: the taker sells. "Pushing-side notional" of a wallet
in a window = its taker_buy_usd (d > 0) or taker_sell_usd (d < 0) summed over the window's bins, on the flow table's on-book / one-taker rule
(T1's taker columns). The window's denominator is the sum of that over wallets (push_total).

CONC_EXACT (window sums, per wallet, then across wallets):
  top1_share, top3_share  largest / three largest wallets' share of push_total
  hhi                     sum of squared shares
  n_wallets               wallets with pushing-side notional > 0
  persistent_share        share of push_total from the coin's 10 largest taker wallets (buy + sell taker notional) by the trailing 7 UTC days
                          that END BEFORE the trigger's day (day of the bar label T); NaN when fewer than 3 of those 7 days exist in the archive
  twap_share              T1 twap_usd (both sides) / taker notional (both sides) in the window; NaN before 2025-07-27 08:00 (twap is NaN there)
SKILL (T2, UTC days strictly before the trigger's day):
  skill_w = (trailing 30-day sum of closed_pnl_usd / sum of volume_usd) x n_fills_30 / (n_fills_30 + 5000)  [K = 5000, fixed by the brief],
            NaN with < 5 active days in the 30. The 30 days are D-30..D-1 for a trigger on day D.
  skill_mean     pushing-notional-weighted mean skill over pushing wallets with a defined skill   (skill_cov = their share of push_total)
  bottom_share / top_share   share of push_total from wallets whose skill is <= the 10th / >= the 90th percentile of skill across the wallets
                 ACTIVE ON DAY D-1 with a defined skill (deciles from day D-1's activity, skill from days < D)
  prior_forced_share   share of push_total from wallets with >= 1 own liquidation (n_forced_events) in D-30..D-1
BACKSTOP (T3 + T1):
  backstop_share   sum over the backstop candidates (every wallet that absorbed backstop-liquidation USD in the window; 4 wallets, T3) of the
                   side OPPOSITE to the push of T1 absorbed_{sell,buy}_usd, / push_total
  descriptive (in the log, not features): forced USD on the pushing side (forced_short_usd for d > 0, forced_long_usd for d < 0, all wallets,
                   on-book) against what the candidates absorbed.
A window that reaches before the first complete bin (2025-05-25 14:35), or overlaps a missing minute of build 2 stage 2 (114), gives NaN for
every feature. A window with push_total == 0 gives NaN shares and n_wallets 0.

OUTPUT. datasets/hl5_features.npz: ev (n_events, 5 windows, NFEAT), pr (n_links, 5, NFEAT), feature names, window names. Float32.
"""
import json, os, sys, time
from multiprocessing import Pool
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

DIR = os.path.join(paths.DATASETS, "wallet5")
OUT = os.path.join(paths.DATASETS, "hl5_features.npz")
EVENTS = os.path.join(paths.DATASETS, "ev_events.parquet")
PAIRS = os.path.join(paths.DATASETS, "ev_pairs.parquet")
MISSING = os.path.join(paths.RESEARCH, "hyperliquid", "logs", "build5_missing_minutes.parquet")
WINS = {"P1": (60, 0), "P2": (360, 60), "P3": (1440, 360), "C6": (360, 0), "C24": (1440, 0)}   # (start, end) minutes before t = 0
WN = list(WINS)
FEATS = ["top1", "top3", "hhi", "nw", "pers", "twap", "skill_mean", "skill_cov", "bot", "topd", "prior_forced", "backstop",
         "push_total", "forced_push", "absorbed_opp"]
NF = len(FEATS)
BIN_MS = 300_000
K_SHRINK = 5000.0
TRAIL_SKILL, TRAIL_PERS, MIN_ACTIVE, MIN_PERS_DAYS = 30, 7, 5, 3
TWAP_FROM = pd.Timestamp("2025-07-27 08:00", tz="UTC")
DATA_START = pd.Timestamp("2025-05-25 14:35", tz="UTC")        # first complete 5-minute bin
LAST_DAY = "2026-10-13"


def day_str(d):
    return d.strftime("%Y%m%d")


def ms_of(ts):
    return ((pd.to_datetime(ts, utc=True) - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(milliseconds=1)).to_numpy().astype(np.int64)


def load_t1(day):
    p = os.path.join(DIR, f"{day_str(day)}_wallet_bin.parquet")
    if not os.path.exists(p):
        return None
    return pd.read_parquet(p, columns=["wallet", "coin", "bin", "taker_buy_usd", "taker_sell_usd", "twap_usd",
                                       "forced_long_usd", "forced_short_usd", "absorbed_buy_usd", "absorbed_sell_usd"])


def load_t2(day):
    p = os.path.join(DIR, f"{day_str(day)}_wallet_day.parquet")
    if not os.path.exists(p):
        return None
    return pd.read_parquet(p, columns=["wallet", "volume_usd", "closed_pnl_usd", "n_forced_events", "n_fills"])


def candidates():
    """Every wallet with absorbed backstop USD in any T3 day (the backstop candidates)."""
    ws = set()
    for f in sorted(os.listdir(DIR)):
        if f.endswith("_vault.parquet"):
            x = pd.read_parquet(os.path.join(DIR, f), columns=["wallet", "absorbed_backstop_usd"])
            ws |= set(x.wallet[x.absorbed_backstop_usd > 0])
    return sorted(ws)


def hole_bin_ms():
    mm = pd.read_parquet(MISSING)
    ms = ms_of(mm["minute"] if "minute" in mm else mm.iloc[:, 0])
    return np.unique((ms // BIN_MS) * BIN_MS)


def window_features(w, d, bins_ok, cols, pers_set, skill, cuts, forced30, cand_mask, nw_ids):
    """Features of one window from its T1 slice. `cols` are the slice's arrays; wallet ids are ints."""
    out = np.full(NF, np.nan, np.float32)
    if not bins_ok:
        return out
    wid = cols["wallet"]
    buy, sell = cols["buy"], cols["sell"]
    push = buy if d > 0 else sell
    tot_both = float(buy.sum() + sell.sum())
    pt = float(push.sum())
    out[FEATS.index("push_total")] = pt
    forced = cols["fshort"] if d > 0 else cols["flong"]
    out[FEATS.index("forced_push")] = float(forced.sum())
    opp = cols["abs_sell"] if d > 0 else cols["abs_buy"]
    out[FEATS.index("absorbed_opp")] = float(opp[cand_mask[wid]].sum()) if len(wid) else 0.0
    if pt <= 0:
        out[FEATS.index("nw")] = 0.0
        return out
    # per-wallet pushing sums
    uw, inv = np.unique(wid, return_inverse=True)
    sw = np.bincount(inv, weights=push)
    pos = sw > 0
    sh = sw / pt
    s_sorted = np.sort(sh)[::-1]
    out[0] = s_sorted[0]
    out[1] = s_sorted[:3].sum()
    out[2] = float((sh ** 2).sum())
    out[3] = float(pos.sum())
    if pers_set is not None:
        out[4] = float(sw[np.isin(uw, pers_set)].sum() / pt)
    tw = cols["twap"]
    if not np.isnan(tw).any() and tot_both > 0:
        out[5] = float(tw.sum() / tot_both)
    sk = skill[uw]
    have = np.isfinite(sk) & pos
    if have.any():
        out[6] = float((sk[have] * sw[have]).sum() / sw[have].sum())
    out[7] = float(sw[have].sum() / pt)
    if cuts is not None:
        lo, hi = cuts
        out[8] = float(sw[np.isfinite(sk) & (sk <= lo)].sum() / pt)
        out[9] = float(sw[np.isfinite(sk) & (sk >= hi)].sum() / pt)
    out[10] = float(sw[forced30[uw] > 0].sum() / pt)
    out[11] = out[FEATS.index("absorbed_opp")] / pt
    return out


def process_chunk(args):
    """Rows (events or links) whose trigger day lies in [a, b): all five windows for each."""
    a, b, rows = args
    t0 = time.time()
    days_need = pd.date_range(a - pd.Timedelta(days=TRAIL_SKILL + 1), b - pd.Timedelta(days=1), freq="D", tz="UTC")
    # T2 for the skill state and the day-(D-1) activity
    t2 = {}
    for d in days_need:
        x = load_t2(d)
        if x is not None:
            t2[d] = x
    allw = pd.Index(pd.unique(pd.concat([x.wallet for x in t2.values()], ignore_index=True)))
    nw_ids = len(allw)
    cand = candidates()
    cand_mask = np.zeros(nw_ids + 1, bool)
    ci = allw.get_indexer(cand)
    cand_mask[ci[ci >= 0]] = True
    T2i = {d: (allw.get_indexer(x.wallet), x.volume_usd.to_numpy(float), x.closed_pnl_usd.to_numpy(float),
               x.n_forced_events.to_numpy(float), x.n_fills.to_numpy(float)) for d, x in t2.items()}
    holes = hole_bin_ms()
    res = np.full((len(rows), len(WN), NF), np.nan, np.float32)
    rdays = rows["day"].to_numpy()
    t0v = ms_of(rows["T"]) + 30 * 60_000
    cur = None
    sk_state = None
    for D in pd.date_range(a, b - pd.Timedelta(days=1), freq="D", tz="UTC"):
        ridx = np.flatnonzero(rdays == np.datetime64(D.tz_localize(None)))
        if len(ridx) == 0:
            continue
        # rolling 30-day state for day D: sum over D-30..D-1
        vol = np.zeros(nw_ids); pnl = np.zeros(nw_ids); nf = np.zeros(nw_ids); fo = np.zeros(nw_ids); act = np.zeros(nw_ids)
        for k in range(1, TRAIL_SKILL + 1):
            dd = D - pd.Timedelta(days=k)
            if dd in T2i:
                ix, v, p, f, n = T2i[dd]
                np.add.at(vol, ix, v); np.add.at(pnl, ix, p); np.add.at(fo, ix, f); np.add.at(nf, ix, n); np.add.at(act, ix, 1.0)
        with np.errstate(invalid="ignore", divide="ignore"):
            skill = np.where((act >= MIN_ACTIVE) & (vol > 0), pnl / vol * nf / (nf + K_SHRINK), np.nan)
        prev = D - pd.Timedelta(days=1)
        cuts = None
        if prev in T2i:
            ixp = T2i[prev][0]
            sp = skill[ixp]
            sp = sp[np.isfinite(sp)]
            if len(sp) >= 100:
                cuts = (float(np.percentile(sp, 10)), float(np.percentile(sp, 90)))
        # T1 of D-1 and D (windows reach at most 24 h before t0 <= D+1 00:00)
        fr = [load_t1(D - pd.Timedelta(days=1)), load_t1(D)]
        T1 = pd.concat([f for f in fr if f is not None], ignore_index=True)
        wid = allw.get_indexer(T1.wallet)
        assert (wid >= 0).all(), "T1 wallet missing from T2 (T2 covers every wallet that fills)"
        coin_codes, coin_names = pd.factorize(T1.coin.astype(str))
        T1b = T1.bin
        binms = ms_of(T1b)
        # persistent set per coin: 7 trailing days ending before D
        pers = {}
        have_days = 0
        parts = []
        for k in range(1, TRAIL_PERS + 1):
            dd = D - pd.Timedelta(days=k)
            x = load_t1(dd) if dd >= pd.Timestamp("2025-05-25", tz="UTC") else None
            if x is not None:
                have_days += 1
                xx = x[["wallet", "coin", "taker_buy_usd", "taker_sell_usd"]]
                xx = xx.assign(n=xx.taker_buy_usd + xx.taker_sell_usd)
                parts.append(xx.groupby(["coin", "wallet"], observed=True).n.sum().reset_index())
        if have_days >= MIN_PERS_DAYS:
            pp = pd.concat(parts).groupby(["coin", "wallet"], observed=True).n.sum().reset_index()
            pp["coin"] = pp.coin.astype(str)
            pp["r"] = pp.groupby("coin").n.rank(ascending=False, method="first")
            pp = pp[pp.r <= 10]
            pp["wid"] = allw.get_indexer(pp.wallet)
            pers = {c: g.wid[g.wid >= 0].to_numpy() for c, g in pp.groupby("coin")}
        else:
            pers = None
        order = np.lexsort((binms, coin_codes))
        key = coin_codes[order].astype(np.int64) * (1 << 42) + binms[order] // BIN_MS
        cols_all = {"wallet": wid[order], "buy": T1.taker_buy_usd.to_numpy(float)[order], "sell": T1.taker_sell_usd.to_numpy(float)[order],
                    "twap": T1.twap_usd.to_numpy(float)[order], "flong": T1.forced_long_usd.to_numpy(float)[order],
                    "fshort": T1.forced_short_usd.to_numpy(float)[order], "abs_buy": T1.absorbed_buy_usd.to_numpy(float)[order],
                    "abs_sell": T1.absorbed_sell_usd.to_numpy(float)[order]}
        cmap = {c: i for i, c in enumerate(coin_names)}
        for r in ridx:
            row = rows.iloc[r]
            c = row["coin"]
            t0ms = int(t0v[r])
            for wi, wname in enumerate(WN):
                bw, ew = WINS[wname]
                lo_ms, hi_ms = t0ms - bw * 60_000, t0ms - ew * 60_000
                ok = lo_ms >= int(DATA_START.value // 10**6)
                if ok:
                    hb = holes[(holes >= lo_ms) & (holes < hi_ms)]
                    ok = len(hb) == 0
                if c not in cmap:
                    cc = {k: np.zeros(0) for k in cols_all}
                    cc["wallet"] = np.zeros(0, int)
                else:
                    ci_ = cmap[c]
                    i0 = np.searchsorted(key, ci_ * (1 << 42) + lo_ms // BIN_MS)
                    i1 = np.searchsorted(key, ci_ * (1 << 42) + hi_ms // BIN_MS)
                    cc = {k: v[i0:i1] for k, v in cols_all.items()}
                ps = pers.get(c) if pers is not None else None
                res[r, wi] = window_features(wname, row["d"], ok, cc, ps, skill, cuts, fo, cand_mask, nw_ids)
        print(f"  [{a.date()}..{b.date()}] day {D.date()} rows {len(ridx)}  [{time.time() - t0:.0f}s]", flush=True)
    return res


def main():
    t0 = time.time()
    EV = pd.read_parquet(EVENTS)
    PR = pd.read_parquet(PAIRS)
    ndays = int(sys.argv[sys.argv.index("--days") + 1]) if "--days" in sys.argv else None
    rows = pd.concat([EV[["coin", "T", "d"]].assign(kind=0, idx=np.arange(len(EV))),
                      PR[["coin", "T", "d"]].assign(kind=1, idx=np.arange(len(PR)))], ignore_index=True)
    rows["T"] = pd.to_datetime(rows["T"], utc=True)
    rows["day"] = rows["T"].dt.tz_convert("UTC").dt.floor("D").dt.tz_localize(None)
    first = pd.Timestamp("2025-05-25", tz="UTC")
    last = pd.Timestamp(LAST_DAY, tz="UTC") + pd.Timedelta(days=1)
    if ndays:
        last = first + pd.Timedelta(days=ndays)
        rows = rows[rows.day < last.tz_localize(None)].reset_index(drop=True)
    nchunk = int(os.environ.get("NCHUNK", 16))
    edges = pd.date_range(first, last, periods=nchunk + 1).floor("D")
    jobs = []
    for a, b in zip(edges[:-1], edges[1:]):
        if b <= a:
            continue
        m = (rows.day >= a.tz_localize(None)) & (rows.day < b.tz_localize(None))
        jobs.append((a, b, rows[m]))
    print(f"[HL5-FEATURES] {len(rows):,} rows ({int((rows.kind == 0).sum()):,} events, {int((rows.kind == 1).sum()):,} links), {len(jobs)} chunks, "
          f"{len(WN)} windows x {NF} features", flush=True)
    with Pool(int(os.environ.get("NPROC", 6))) as pool:
        outs = pool.map(process_chunk, jobs)
    ev = np.full((len(EV), len(WN), NF), np.nan, np.float32)
    pr = np.full((len(PR), len(WN), NF), np.nan, np.float32)
    for (a, b, rws), res in zip(jobs, outs):
        k0 = rws.kind.to_numpy() == 0
        ev[rws.idx.to_numpy()[k0]] = res[k0]
        pr[rws.idx.to_numpy()[~k0]] = res[~k0]
    np.savez_compressed(OUT, ev=ev, pr=pr, feats=np.array(FEATS), windows=np.array(WN), cand=np.array(candidates()))
    print(f"[WROTE] {OUT}  [{time.time() - t0:.0f}s]")
    nan = np.isnan(ev[:, :, 0]).mean(0)
    print("  NaN share of events per window (top1): " + ", ".join(f"{w} {x:.4f}" for w, x in zip(WN, nan)))
    for f in range(NF):
        v = ev[:, WN.index("P1"), f]
        print(f"  {FEATS[f]:<13} P1: finite {np.isfinite(v).mean():.4f}  median {np.nanmedian(v):.4g}  p10 {np.nanpercentile(v, 10):.4g}  p90 {np.nanpercentile(v, 90):.4g}")


if __name__ == "__main__":
    main()
