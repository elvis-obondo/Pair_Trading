"""HL-MASTER1 G4: coin and time context at t = 0, both units. Features only.

    python -u research/dataset/master_g4.py > research/dataset/logs/master_g4.log

t0 = entry_time + 30 min. m0 = the 1-minute bar labelled T + 29 (the trigger bar's close). Per leg (pair unit: a_ = leg A, b_ = leg B; coin unit: a_ = the coin; there is no b_):
  coin_code             index of the ticker in the sorted list of research/hyperliquid/coins.csv (234 coins; 204 appear in events)
  listing_date          min(first day in asset_ctxs, first day with a trade in our flow table); listing_src records which (0 = asset_ctxs, 1 = trade day earlier); listing_left_censored = 1 if the
                        asset_ctxs date is within 3 days of 2023-05-20; listing_age_days = (t0 - 00:00 of the listing date) / 1 day.  [gap-fill A: asset_ctxs gaps would make a listing late]
  liq_7d, liq_30d       mean DAILY taker notional (USD, both sides, flow table) over the 7 / 30 UTC days ending the day BEFORE the UTC day of T; NaN with fewer than 3 / 10 days of data
  liq_rank_7d/30d       percentile rank (0..1) of that value among coins with a value on that day (past only)
  traded_share_24h      share of the 1,440 minutes ending at m0 with a trade (mins_since_trade = 0; a missing row counts as no trade)
  mins_since_trade      mins_since_trade of the 1m bar m0 (NaN if the row is missing)
  log_price             log of the 1m close at m0 (NaN if missing)
  ret_7d, ret_30d       log price at m0 minus log price 10,080 / 43,200 minutes earlier (NaN if either end is NaN)
  rv_24h, rv_7d         sd (ddof 1) of 1-minute log returns over the 1,440 / 10,080 minutes ending at m0 (NaN minutes excluded; NaN if fewer than 70% of the window's returns are usable or the window starts before the grid)
  rv_24h_rel90          rv_24h divided by the median of rv_24h sampled at the same minute on each of the previous 90 days (needs >= 30 usable samples)
  static, outside the as-of rule (hindsight, one snapshot): sector (CoinGecko, fixed priority rule), max_leverage, tier1_max_leverage, size_decimals, margin_table_id, cg_status
Pair-only: d_<col> = a_ - b_ for log_price, ret_7d, ret_30d, rv_24h, rv_7d, rv_24h_rel90, traded_share_24h, listing_age_days, liq_rank_7d/30d; liq_logratio_7d/30d = log(liq_a / liq_b);
same_sector (1/0; NaN if either leg 'unmapped').
Time (on t0): utc_hour, hour_sin, hour_cos, weekday (Mon = 0), weekend (Sat/Sun), mins_since_top_hour (0 or 30), sess_asia (00-08 UTC), sess_europe (07-16), sess_us (13-22) (overlapping by design),
near_seam = 1 if a build 2 missing minute (114) lies in [t0 - 24 h, t0). No calendar date, month or trend column.
OUTPUT: research/datasets/master/work/{pair,coin}/g4.parquet
"""
import os, sys, time
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research"))
sys.path.insert(0, os.path.join(ROOT, "research", "dislocation_model"))
import paths
import flowfeat as ff
import evmarket as em
from adapters.hyperliquid_futures import bar_file

WORK = os.path.join(paths.DATASETS, "master", "work")
CTX = os.path.join(paths.DATASETS, "ctxs")
STATIC = os.path.join(ROOT, "research", "dataset", "static")
COINS_CSV = os.path.join(ROOT, "research", "hyperliquid", "coins.csv")
MISSING = os.path.join(ROOT, "research", "hyperliquid", "logs", "build5_missing_minutes.parquet")
MIN_PER_DAY = 1440
LEG_NUM = ["log_price", "ret_7d", "ret_30d", "rv_24h", "rv_7d", "rv_24h_rel90", "traded_share_24h", "mins_since_trade", "listing_age_days", "liq_7d", "liq_30d", "liq_rank_7d", "liq_rank_30d"]
LEG_ALL = ["coin_code", "listing_src", "listing_left_censored"] + LEG_NUM
DIFFS = ["log_price", "ret_7d", "ret_30d", "rv_24h", "rv_7d", "rv_24h_rel90", "traded_share_24h", "listing_age_days", "liq_rank_7d", "liq_rank_30d"]
STATIC_COLS = ["sector", "max_leverage", "tier1_max_leverage", "size_decimals", "margin_table_id", "cg_status"]
EPOCH = pd.Timestamp("1970-01-01")


def minute_of(t):
    """ff minute index of a timestamp (the grid starts at the window's first minute)."""
    t = pd.to_datetime(t)
    if isinstance(t, pd.Series):
        if t.dt.tz is not None:
            t = t.dt.tz_localize(None)
    elif getattr(t, "tz", None) is not None:
        t = t.tz_localize(None)
    return ff.minute_index(t)


def roll_sum(x, w):
    """Trailing window sums ending at each index (inclusive) of length w, NaN-safe via cumulative sums; returns (sum, count of finite)."""
    f = np.isfinite(x)
    cs = np.concatenate([[0.0], np.cumsum(np.where(f, x, 0.0))])
    cn = np.concatenate([[0], np.cumsum(f)])
    i = np.arange(len(x))
    lo = np.maximum(i + 1 - w, 0)
    return cs[i + 1] - cs[lo], cn[i + 1] - cn[lo]


def coin_arrays(lc, mst):
    """Dense per-minute arrays of one coin and the trailing statistics derived from them (pure: raw arrays in, arrays out)."""
    tr = (mst == 0).astype(float)
    r = np.full(len(lc), np.nan)
    r[1:] = lc[1:] - lc[:-1]
    out = dict(lc=lc, mst=mst)
    for nm, w in (("24", 1440), ("7", 10080)):
        s1, n1 = roll_sum(r, w)
        s2, _ = roll_sum(r * r, w)
        full = np.arange(len(lc)) >= w                                      # the window must lie inside the grid (no partial windows at the start)
        out["sd" + nm] = np.where(full & (n1 >= 0.7 * w), np.sqrt(np.maximum(s2 - s1 * s1 / np.maximum(n1, 1), 0) / np.maximum(n1 - 1, 1)), np.nan)
    out["ts"] = roll_sum(tr, 1440)[0]
    return out


def liq_tables(daily, code, ndays, ncoin):
    """Past-only liquidity (mean daily taker notional over the 7 / 30 days BEFORE each day index) and its cross-sectional percentile rank."""
    L7 = np.full((ndays, ncoin), np.nan)
    L30 = np.full((ndays, ncoin), np.nan)
    for c, arr in daily.items():
        a = np.nan_to_num(arr)
        ok = np.isfinite(arr).astype(float)
        cs, cn = np.concatenate([[0], np.cumsum(a)]), np.concatenate([[0], np.cumsum(ok)])
        i = np.arange(ndays)
        for W, M, out in ((7, 3, L7), (30, 10, L30)):
            hi, lo = i, np.maximum(i - W, 0)
            n = cn[hi] - cn[lo]
            out[:, code[c]] = np.where(n >= M, (cs[hi] - cs[lo]) / np.maximum(n, 1), np.nan)
    R7 = pd.DataFrame(L7).rank(axis=1, pct=True).to_numpy()
    R30 = pd.DataFrame(L30).rank(axis=1, pct=True).to_numpy()
    return L7, L30, R7, R30


def leg_at(A, m, dayix, t0s, cl, ld, src_c, cens_c, liq):
    """Features of one coin at event minutes m (array), UTC day indices dayix, decision times t0s (Series). Uses only A[...] at indices <= m and liq rows < dayix."""
    L7, L30, R7, R30 = liq
    o = {}
    o["coin_code"] = np.full(len(m), cl, float)
    o["listing_src"] = np.full(len(m), src_c, float)
    o["listing_left_censored"] = np.full(len(m), cens_c, float)
    lc = A["lc"]
    o["log_price"] = lc[m]
    o["ret_7d"] = np.where(m - 10080 >= 0, lc[m] - lc[np.clip(m - 10080, 0, None)], np.nan)
    o["ret_30d"] = np.where(m - 43200 >= 0, lc[m] - lc[np.clip(m - 43200, 0, None)], np.nan)
    o["rv_24h"], o["rv_7d"] = A["sd24"][m], A["sd7"][m]
    samp = m[:, None] - MIN_PER_DAY * np.arange(1, 91)[None, :]
    v = np.where(samp >= 0, A["sd24"][np.clip(samp, 0, None)], np.nan)
    with np.errstate(invalid="ignore", all="ignore"):
        med = np.where(np.isfinite(v).sum(1) >= 30, np.nanmedian(np.where(np.isfinite(v), v, np.nan), axis=1), np.nan)
        o["rv_24h_rel90"] = A["sd24"][m] / med
    o["traded_share_24h"] = A["ts"][m] / 1440.0
    o["mins_since_trade"] = A["mst"][m]
    o["listing_age_days"] = ((t0s - ld) / pd.Timedelta(days=1)).to_numpy(float) if pd.notna(ld) else np.full(len(m), np.nan)
    o["liq_7d"], o["liq_30d"] = L7[dayix, cl], L30[dayix, cl]
    o["liq_rank_7d"], o["liq_rank_30d"] = R7[dayix, cl], R30[dayix, cl]
    return o


def time_cols(t0s, hole_min):
    h = t0s.dt.hour.to_numpy()
    t0m = minute_of(t0s)
    lo = np.searchsorted(hole_min, t0m - 1440, side="left")
    hi = np.searchsorted(hole_min, t0m, side="left")
    wd = t0s.dt.dayofweek.to_numpy()
    return {"utc_hour": h.astype(np.int8), "hour_sin": np.sin(2 * np.pi * h / 24).astype(np.float32), "hour_cos": np.cos(2 * np.pi * h / 24).astype(np.float32),
            "weekday": wd.astype(np.int8), "weekend": (wd >= 5).astype(np.int8), "mins_since_top_hour": t0s.dt.minute.to_numpy().astype(np.int8),
            "sess_asia": ((h >= 0) & (h < 8)).astype(np.int8), "sess_europe": ((h >= 7) & (h < 16)).astype(np.int8), "sess_us": ((h >= 13) & (h < 22)).astype(np.int8),
            "near_seam": (hi > lo).astype(np.int8)}


def pair_columns(Ga, Gb, sa, sb):
    """Pair-only columns from the two legs' feature dicts (arrays) and sector labels: differences, log liquidity ratios, same_sector."""
    o = {f"d_{c}": (Ga[c] - Gb[c]) for c in DIFFS}
    with np.errstate(divide="ignore", invalid="ignore"):
        o["liq_logratio_7d"] = np.log(Ga["liq_7d"] / Gb["liq_7d"])
        o["liq_logratio_30d"] = np.log(Ga["liq_30d"] / Gb["liq_30d"])
    um = (sa == "unmapped") | (sb == "unmapped")
    o["same_sector"] = np.where(um, np.nan, (sa == sb).astype(float))
    return o


def listing_table():
    """first asset_ctxs day per coin."""
    first_ctx = {}
    for f in sorted(os.listdir(CTX)):
        if not f.endswith(".parquet") or f.startswith("_"):
            continue
        d = pd.Timestamp(f[:8])
        for c in pd.read_parquet(os.path.join(CTX, f), columns=["coin"]).coin.unique():
            first_ctx.setdefault(str(c), d)
    return first_ctx


def load_daily(coins_all, ndays, day0):
    daily, first_trade = {}, {}
    for c in coins_all:
        p = os.path.join(ff.FLOW_DIR, f"{c}.parquet")
        if not os.path.exists(p):
            continue
        fl = pd.read_parquet(p, columns=["date", "taker_buy_usd", "taker_sell_usd"])
        dt = pd.to_datetime(fl["date"])
        if dt.dt.tz is not None:
            dt = dt.dt.tz_localize(None)
        tn = (fl.taker_buy_usd + fl.taker_sell_usd).to_numpy(float)
        day = ((dt.dt.floor("D") - day0) // pd.Timedelta(days=1)).to_numpy()
        inr = (day >= 0) & (day < ndays)
        s = np.zeros(ndays)
        np.add.at(s, day[inr & np.isfinite(tn)], tn[inr & np.isfinite(tn)])
        cnt = np.zeros(ndays)
        np.add.at(cnt, day[inr & (tn > 0)], 1)
        daily[c] = np.where(cnt > 0, s, np.nan)
        pos = np.flatnonzero(tn > 0)
        first_trade[c] = dt.iloc[pos[0]].floor("D") if len(pos) else pd.NaT
    return daily, first_trade


def read_coin_minutes(c):
    b1 = pd.read_feather(bar_file(c, "1m"), columns=["date", "close", "mins_since_trade"])
    ix = ff.minute_index(b1["date"].dt.tz_localize(None))
    ok = (ix >= 0) & (ix < ff.N)
    lc = np.full(ff.N, np.nan)
    lc[ix[ok]] = np.log(b1["close"].to_numpy(float)[ok])
    mst = np.full(ff.N, np.nan)
    mst[ix[ok]] = b1["mins_since_trade"].to_numpy(float)[ok]
    return lc, mst


class Context:
    def __init__(self):
        self.coins_all = sorted(pd.read_csv(COINS_CSV).coin.tolist())
        self.code = {c: i for i, c in enumerate(self.coins_all)}
        self.meta = pd.read_csv(os.path.join(STATIC, "hl_meta_snapshot.csv")).set_index("coin")
        self.sect = pd.read_csv(os.path.join(STATIC, "coingecko_sector_snapshot.csv")).set_index("coin")
        self.ndays = int(np.ceil(ff.N / MIN_PER_DAY)) + 2
        self.day0 = ff.GRID0.floor("D")
        first_ctx = listing_table()
        self.daily, first_trade = load_daily(self.coins_all, self.ndays, self.day0)
        self.liq = liq_tables(self.daily, self.code, self.ndays, len(self.coins_all))
        self.lst, self.src, self.cens, self.changed = {}, {}, {}, []
        for c in self.coins_all:
            a, b = first_ctx.get(c, pd.NaT), first_trade.get(c, pd.NaT)
            if pd.notna(a) and pd.notna(b) and b < a:
                self.lst[c], self.src[c] = b, 1
                self.changed.append((c, str(a.date()), str(b.date())))
            else:
                self.lst[c], self.src[c] = (a if pd.notna(a) else b), 0
            self.cens[c] = int(pd.notna(a) and (a - pd.Timestamp("2023-05-20")).days <= 3)
        hole = pd.read_parquet(MISSING)
        hole = hole["minute"] if "minute" in hole else hole.iloc[:, 0]
        self.hole_min = np.sort(minute_of(hole))

    def event_keys(self, E):
        m0 = minute_of(pd.to_datetime(E.entry_time) + pd.Timedelta(minutes=29))
        t0s = pd.to_datetime(E.entry_time) + pd.Timedelta(minutes=30)
        dayix = ((pd.to_datetime(E.entry_time).dt.floor("D") - self.day0) // pd.Timedelta(days=1)).to_numpy()
        return m0, t0s.reset_index(drop=True), dayix

    def legs(self, E, col, A_by_coin):
        """Per-leg feature arrays for the events E (column `col` holds the coin names), using the coin arrays A_by_coin."""
        m0, t0s, dayix = self.event_keys(E)
        out = {k: np.full(len(E), np.nan) for k in LEG_ALL}
        for c in sorted(set(E[col])):
            sel = np.flatnonzero((E[col] == c).to_numpy())
            o = leg_at(A_by_coin[c], m0[sel], dayix[sel], t0s.iloc[sel], self.code[c], self.lst[c], self.src[c], self.cens[c], self.liq)
            for k, v in o.items():
                out[k][sel] = v
        return out


def static_cols(ctx, names, lg):
    o = {}
    o[f"{lg}_sector"] = names.map(ctx.sect.sector).fillna("unmapped").to_numpy()
    o[f"{lg}_cg_status"] = names.map(ctx.sect.status).fillna("unmapped").to_numpy()
    for sc in ("max_leverage", "tier1_max_leverage", "size_decimals", "margin_table_id"):
        o[f"{lg}_{sc}"] = names.map(ctx.meta[sc]).to_numpy(float)
    return o


def main():
    t0 = time.time()
    ctx = Context()
    print(f"[G4] context: {len(ctx.coins_all)} coins, daily taker notional for {len(ctx.daily)}, listing dates; first trade earlier than the asset_ctxs date for {len(ctx.changed)} coins"
          + (": " + ", ".join(f"{c} ({a} -> {b})" for c, a, b in ctx.changed[:25]) if ctx.changed else "") + f"; left-censored {sum(ctx.cens.values())}  [{time.time() - t0:.0f}s]", flush=True)
    units = {u: pd.read_parquet(os.path.join(WORK, u, "events.parquet"), columns=["event_id", "ticker_a", "ticker_b", "entry_time"]) for u in ("pair", "coin")}
    needed = sorted(set(units["pair"].ticker_a) | set(units["pair"].ticker_b) | set(units["coin"].ticker_a))
    A_by = {}
    for k, c in enumerate(needed):
        A_by[c] = coin_arrays(*read_coin_minutes(c))
        if (k + 1) % 40 == 0:
            print(f"  coin arrays {k + 1}/{len(needed)}  [{time.time() - t0:.0f}s]", flush=True)
    for u, E in units.items():
        G = {"event_id": E.event_id.to_numpy()}
        legs = {"a": ctx.legs(E, "ticker_a", A_by)}
        names = {"a": E.ticker_a}
        if u == "pair":
            legs["b"] = ctx.legs(E, "ticker_b", A_by)
            names["b"] = E.ticker_b
        for lg, d in legs.items():
            for k, v in d.items():
                G[f"{lg}_{k}"] = v.astype(np.float64 if k in ("liq_7d", "liq_30d") else np.float32)
            G.update(static_cols(ctx, names[lg], lg))
        if u == "pair":
            pc = pair_columns(legs["a"], legs["b"], G["a_sector"], G["b_sector"])
            G.update({k: v.astype(np.float32) for k, v in pc.items()})
        _, t0s, _ = ctx.event_keys(E)
        G.update(time_cols(t0s, ctx.hole_min))
        G = pd.DataFrame(G)
        G.to_parquet(os.path.join(WORK, u, "g4.parquet"), index=False)
        print(f"[G4 {u}] {len(G):,} rows x {len(G.columns) - 1} columns  [{time.time() - t0:.0f}s]")
        for c_ in G.columns[1:]:
            v = G[c_]
            if v.dtype == object:
                print(f"  {c_:<26} categories: " + ", ".join(f"{k} {n}" for k, n in v.value_counts().head(8).items()))
            else:
                x = v.to_numpy(float)
                f = np.isfinite(x)
                print(f"  {c_:<26} NaN {100 * np.isnan(x).mean():6.2f}%  median {np.median(x[f]) if f.any() else np.nan:+.4g}  p5 {np.percentile(x[f], 5) if f.any() else np.nan:+.4g}  p95 {np.percentile(x[f], 95) if f.any() else np.nan:+.4g}")
        m = pd.to_datetime(E.entry_time).dt.to_period("M")
        print("  NaN share by month (a_ret_30d, a_rv_24h_rel90, a_liq_30d, a_rv_7d):")
        print(G.assign(m=m.values).groupby("m")[["a_ret_30d", "a_rv_24h_rel90", "a_liq_30d", "a_rv_7d"]].agg(lambda s: s.isna().mean()).round(4).to_string())
        assert ((G.a_traded_share_24h.dropna() >= 0) & (G.a_traded_share_24h.dropna() <= 1)).all()
        assert ((G.a_liq_rank_7d.dropna() >= 0) & (G.a_liq_rank_7d.dropna() <= 1)).all()
        assert (G.a_listing_age_days.dropna() >= 0).all(), "a coin traded before its listing date"


if __name__ == "__main__":
    main()
