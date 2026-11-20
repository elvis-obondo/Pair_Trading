"""HL-TARGET2 label build (rules: research/model/s2_target_rules.md governs; the planner's go and the user's "lets just update the dataset label", 2026-11-20).
y = net bp per trade at book mids, taker costs, exit at mu or minute 600; one row per event (search and vault), every event keeps a status row.

ORDER (fixed, in the code):
  1. AVAILABILITY STAGE: mids, trigger_k, exit_k, status, gap runs and flags, sources. NO gross, return or y is computed or printed here.
  2. HARD STOPS on the TEST-MONTH events (denominator: all test-month events): per-leg gap_flag > 10%, 60-minute exit-cap drops > 1%. A stop writes NO label and exits with code 2.
  3. Only if both stops pass: y components (gross, fees, half-spread, funding), the missing-data counts, the receipts, then the two output files.
This script never prints y, gross_bp or any return. Step B reads y.
Needs: the slim G8 table (s2_g8_slim.py), the local ctxs mid cache, cleaned closes (receipt R1 only), fundinghist cache.
Usage: python s2_target_build.py > s2_target_build.log
       python s2_target_build.py --trial > s2_target_trial.log   (planner / user: "trial first": the same code on the events of 4 days only, output to logs/s2/trial/, hard stops judged on the trial's test-month events)
"""
import hashlib
import json
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.dirname(HERE)
sys.path.insert(0, MODEL)
sys.path.insert(0, HERE)
assert os.environ.get("PROFIT1_VAULT", "") != "1"
import harness as H  # noqa: E402
import vault_loader as VL  # noqa: E402
import s2_target_lib as L  # noqa: E402
import costs_nobounce as NB  # noqa: E402  (tiers, epoch_min, load_arrays for receipt R1)

warnings.filterwarnings("ignore", category=RuntimeWarning)
T = os.path.join(MODEL, "logs", "profit1") + os.sep
C1 = os.path.join(MODEL, "logs", "costs1") + os.sep
S2 = os.path.join(MODEL, "logs", "s2") + os.sep
TIERS = NB.TIERS
NO_SPREAD = 4
STATUS_NAMES = dict(L.STATUS_NAMES)
STATUS_NAMES[NO_SPREAD] = "no_spread"
D0 = pd.Timestamp("2025-06-01", tz="UTC")
N_DAYS = (pd.Timestamp("2026-10-15", tz="UTC") - D0).days          # 501 days: 2025-06-01 .. 2026-10-14
BASE = int(D0.value // 60_000_000_000)                              # epoch minute of the axis start
N_MIN = N_DAYS * 1440
N_H = N_MIN // 60
CHUNK = 5000
# G8 archive gaps: DATASET_DICTIONARY.md G8 section, 21 days entirely absent
ABSENT = (["2025-10-%02d" % d for d in range(17, 23)] + ["2025-11-%02d" % d for d in range(18, 26)] + ["2026-07-08"] + ["2026-07-%02d" % d for d in range(12, 18)])
TRIAL = "--trial" in sys.argv
TRIAL_DAYS = ["2025-09-15", "2026-01-15", "2026-04-08", "2026-09-15"]     # G8-only search day, two test-month days (ctxs era; all test months are), one vault day
T0 = time.time()


def log(m):
    print(m, flush=True)


def pct(x):
    return f"{100 * x:.1f}%"


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:12]


# ------------------------------------------------------------------ events
def load_events():
    cols = ["ticker_a", "ticker_b", "z", "beta", "alpha", "mu", "sigma"]
    S = H.load_search_events(columns=cols).reset_index(drop=True)
    V = VL.load_vault_event_dates().reset_index(drop=True)          # events.parquet geometry; labels.parquet is never opened
    nb = json.load(open(C1 + "costs_nobounce.json"))
    assert len(S) == 5378429 and len(V) == 1280088, f"event counts differ from the sizing log: {len(S):,} / {len(V):,}"
    S["side"], V["side"] = 0, 1
    keep = ["event_id", "side", "t0", "ticker_a", "ticker_b", "z", "beta", "alpha", "mu", "sigma"]
    E = pd.concat([S[keep], V[keep]], ignore_index=True)
    assert E["event_id"].is_unique
    E["test"] = (E["side"] == 0) & (E["t0"] >= H.TEST_BLOCK_STARTS[1]) & (E["t0"] < H.GAP_DAY)
    n_test = int(E["test"].sum())
    assert n_test == nb["test"]["lost|all events|ALL TIERS"]["n"], f"test-month events {n_test:,} != COSTS1 no-bounce test events"
    E["month"] = E["t0"].dt.strftime("%Y-%m")
    E["t0m"] = NB.epoch_min(E["t0"]) - BASE
    assert E["t0m"].min() >= 0 and E["t0m"].max() + L.KW + 1 < N_MIN
    log(f"[S2BUILD] events: search {len(S):,} (test months {n_test:,}), vault {len(V):,}; axis {N_DAYS} days {D0.date()} .. 2026-10-14, {N_MIN:,} minutes")
    return E


def add_tiers(E, cj):
    out = np.full(len(E), "no tier", dtype=object)
    for side, sname in ((0, "test"), (1, "vault")):
        m = (E["side"] == side).to_numpy()
        e = E[m]
        coins = sorted(set(e["ticker_a"]) | set(e["ticker_b"]))
        runs = [pd.read_parquet(f"{T}trades_q0.01_stopnone_fee{fee}{NB.SFX[(sname, mo)]}.parquet", columns=["t0", "exit_time"]) for mo in (10, 20) for fee in ("maker", "taker")]
        rng = (min(int(NB.epoch_min(r["t0"]).min()) for r in runs), max(int(NB.epoch_min(r["exit_time"]).max()) for r in runs))
        tier_of = NB.build_tiers(sname, coins, cj["tier_coins"][sname], rng)
        o = {n: i for i, n in enumerate(TIERS)}
        ta, tb = e["ticker_a"].map(tier_of), e["ticker_b"].map(tier_of)
        out[m] = [min((a, b), key=lambda x: o[x]) if isinstance(a, str) and isinstance(b, str) else "no tier" for a, b in zip(ta, tb)]
    E["tier"] = out
    return E


# ------------------------------------------------------------------ price matrices
def load_matrices(coins):
    cid = {c: i for i, c in enumerate(coins)}
    nc = len(coins)
    ML = np.full((nc, N_MIN), np.nan)                 # log real mid; ctxs primary, G8 fallback
    SRC = np.zeros((nc, N_MIN), np.uint8)             # 0 none, 1 ctxs, 2 G8
    HS = np.full((nc, N_MIN), np.nan, np.float32)     # half-spread bp from G8 (NaN: no row, or crossed, or no spread)
    CR = np.zeros((nc, N_MIN), bool)                  # G8 row crossed
    present = set()
    g8 = sorted(f for f in os.listdir(S2 + "g8_slim") if f.endswith(".parquet"))
    nrow = 0
    for f in g8:
        d = pq.read_table(S2 + "g8_slim/" + f).to_pandas()
        day = f[:8]
        present.add(day)
        ci = d["coin"].map(cid)
        q = d["minute"].to_numpy().astype(np.int64) - BASE
        ok = ci.notna().to_numpy() & (q >= 0) & (q < N_MIN)
        ci_, q_, d = ci.to_numpy()[ok].astype(np.int64), q[ok], d[ok]
        mid = d["mid"].to_numpy(float)
        good = mid > 0
        ML[ci_[good], q_[good]] = np.log(mid[good])
        SRC[ci_[good], q_[good]] = 2
        sp = d["spread_bp"].to_numpy(float)
        cr = d["crossed"].to_numpy() == 1
        CR[ci_[cr], q_[cr]] = True
        gs = ~cr & np.isfinite(sp) & (sp >= 0)
        HS[ci_[gs], q_[gs]] = (sp[gs] / 2).astype(np.float32)
        nrow += len(d)
    log(f"[S2BUILD] G8 slim: {len(g8)} day files, {nrow:,} rows used; first {g8[0][:8]}, last {g8[-1][:8]}; finite G8 mids {int((SRC == 2).sum()):,}, usable half-spreads {int(np.isfinite(HS).sum()):,}, crossed {int(CR.sum()):,}")
    days = [(D0 + pd.Timedelta(days=i)).strftime("%Y%m%d") for i in range(N_DAYS)]
    absent_day = np.array([d not in present for d in days])
    known = {a.replace("-", "") for a in ABSENT}
    assert known <= {d for d, a in zip(days, absent_day) if a}, "a day listed as absent from the G8 archive has a slim file"
    extra = sorted({d for d, a in zip(days, absent_day) if a} - known)
    log(f"[S2BUILD] days on the axis with no G8 slim file: {int(absent_day.sum())} (the 21 known absent days{'; plus ' + str(len(extra)) + ' more: ' + ', '.join(extra[:12]) if extra else ''})")
    man = json.load(open(S2 + "g8_slim_manifest.json"))
    assert extra == [] and man["days"] == 496 and len(g8) == 496, f"the G8 slim table is incomplete: {len(g8)} files, manifest {man['days']}, unexpected missing days {extra}"   # a partial slim must never read as G8-absent days
    absent_minute = np.repeat(absent_day, 1440)
    n_ctx = n_off = 0
    cdays = sorted(f for f in os.listdir(T + "ctxs_cache") if f.endswith(".parquet"))
    for f in cdays:
        p = pd.read_parquet(T + "ctxs_cache/" + f, columns=["time", "coin", "mid_px"])
        off = (p["time"].dt.second != 0) | (p["time"].dt.microsecond != 0)
        n_off += int(off.sum())
        p = p[~off]
        q = NB.epoch_min(p["time"]) - BASE
        c_ = p["coin"].astype(str).map(cid)
        ok = c_.notna().to_numpy() & (q >= 0) & (q < N_MIN)
        ci_, q_ = c_.to_numpy()[ok].astype(np.int64), q[ok]
        assert not pd.Series(ci_ * 10 ** 8 + q_).duplicated().any(), f"duplicate (coin, stamp) in ctxs {f}"
        mv = p["mid_px"].to_numpy(float)[ok]
        good = mv > 0
        ML[ci_[good], q_[good]] = np.log(mv[good])
        SRC[ci_[good], q_[good]] = 1
        n_ctx += int(good.sum())
    log(f"[S2BUILD] ctxs cache: {len(cdays)} day files ({cdays[0][:8]} .. {cdays[-1][:8]}), usable mids {n_ctx:,}, off-minute rows dropped {n_off:,}; merged real mids {int((SRC > 0).sum()):,} (ctxs {int((SRC == 1).sum()):,}, G8 only {int((SRC == 2).sum()):,})")
    mon = (D0 + pd.to_timedelta(np.arange(N_DAYS), unit="D"))
    mon_idx = (((mon.year - 2025) * 12 + mon.month - 6).to_numpy()).astype(np.int16)
    mon_of_minute = np.repeat(mon_idx, 1440)
    nmon = int(mon_idx.max()) + 1
    med = np.full((nc, nmon), np.nan)
    for mi in range(nmon):
        sl = np.flatnonzero(mon_of_minute == mi)
        med[:, mi] = np.nanmedian(HS[:, sl[0]:sl[-1] + 1], axis=1)
    log(f"[S2BUILD] coin-month median half-spread table {med.shape}; coin-months with no usable row {int(np.isnan(med).sum())} of {med.size}")
    return cid, ML, SRC, HS, CR, absent_minute, mon_of_minute, med


def load_funding(coins):
    FR = np.full((len(coins), N_H), np.nan)
    has = np.zeros(len(coins), bool)
    hb = BASE // 60
    for i, c in enumerate(coins):
        f = T + f"fundinghist_cache/{c}.parquet"
        if not os.path.exists(f):
            continue
        d = pd.read_parquet(f, columns=["time", "fundingRate"])
        d["time"] = pd.to_datetime(d["time"], utc=True).dt.floor("h")
        d = d.drop_duplicates("time")
        h = (NB.epoch_min(d["time"]) // 60 - hb)
        ok = (h >= 0) & (h < N_H)
        FR[i, h[ok]] = d["fundingRate"].to_numpy(float)[ok]
        has[i] = True
    CS = np.zeros((len(coins), N_H + 1))
    CM = np.zeros((len(coins), N_H + 1), np.int32)
    CS[:, 1:] = np.cumsum(np.nan_to_num(FR), axis=1)
    CM[:, 1:] = np.cumsum(np.isnan(FR), axis=1)
    log(f"[S2BUILD] funding: {int(has.sum())} of {len(coins)} coins have a fundinghist file; coins without: {[c for c, h_ in zip(coins, has) if not h_]}")
    return CS, CM, has


# ------------------------------------------------------------------ stage 1
def geometry(E):
    z = E["z"].to_numpy(float)
    beta = E["beta"].to_numpy(float)
    s = np.where(z >= 0, 1.0, -1.0)
    dir_a = np.where(z >= 0, -1.0, 1.0)
    dir_b = np.where(z >= 0, 1.0, -1.0) * np.where(beta >= 0, 1.0, -1.0)
    wa = 1.0 / (1.0 + np.abs(beta))
    return s, dir_a, dir_b, wa, 1.0 - wa


def stage1(E, cid, ML, SRC):
    """availability stage on every event, grouped so the run-length distributions are per period. Returns a dict of arrays (length len(E)) and run buckets per period."""
    n = len(E)
    ia = E["ticker_a"].map(cid).to_numpy().astype(np.int64)
    ib = E["ticker_b"].map(cid).to_numpy().astype(np.int64)
    t0m = E["t0m"].to_numpy()
    s, *_ = geometry(E)
    beta, alpha, mu, sigma = (E[c].to_numpy(float) for c in ("beta", "alpha", "mu", "sigma"))
    R = dict(status=np.zeros(n, np.int8), trigger_k=np.zeros(n, np.int32), exit_k=np.zeros(n, np.int32), exit_reason=np.zeros(n, np.int8),
             max_gap_len_leg=np.zeros(n, np.int32), gap_flag=np.zeros(n, bool), max_gap_len_union=np.zeros(n, np.int32), gap_flag_union=np.zeros(n, bool),
             n_filled=np.zeros(n, np.int32), z0_mid=np.zeros(n), src_in_a=np.zeros(n, np.uint8), src_in_b=np.zeros(n, np.uint8),
             src_out_a=np.zeros(n, np.uint8), src_out_b=np.zeros(n, np.uint8))
    test = E["test"].to_numpy()
    side = E["side"].to_numpy()
    periods = {"search test months": test, "search other months": (side == 0) & ~test, "vault": side == 1}
    runs = {}
    ar = np.arange(L.KW)[None, :]
    for pname, pm in periods.items():
        idx = np.flatnonzero(pm)
        rl, ru = np.zeros(len(L.RUN_EDGES), np.int64), np.zeros(len(L.RUN_EDGES), np.int64)
        t = time.time()
        for i0 in range(0, len(idx), CHUNK):
            ix = idx[i0:i0 + CHUNK]
            cols = t0m[ix][:, None] + ar
            A, B = ML[ia[ix][:, None], cols], ML[ib[ix][:, None], cols]
            o = L.scan_paths(A, B, s[ix], beta[ix], alpha[ix], mu[ix], sigma[ix])
            rl += o.pop("runs_leg")
            ru += o.pop("runs_union")
            for k_, v in o.items():
                R[k_][ix] = v
            R["src_in_a"][ix] = SRC[ia[ix], t0m[ix]]
            R["src_in_b"][ix] = SRC[ib[ix], t0m[ix]]
            okx = o["status"] == L.OK
            if okx.any():
                jx = ix[okx]
                R["src_out_a"][jx] = SRC[ia[jx], t0m[jx] + o["exit_k"][okx]]
                R["src_out_b"][jx] = SRC[ib[jx], t0m[jx] + o["exit_k"][okx]]
            if (i0 // CHUNK) % 100 == 0:
                log(f"[S2BUILD]   stage 1 {pname}: {min(i0 + CHUNK, len(idx)):,} / {len(idx):,} events, {time.time() - t:.0f}s")
        runs[pname] = (rl, ru)
    return R, runs


def poison_receipt(E, cid, ML, R, n=20000):
    """RECEIPT (checker fix 5): overwrite EVERY mid stamped after k_trig (set to NaN) and re-run the trigger scan on a seeded sample of events: trigger_k and exit_reason must be unchanged."""
    rng = np.random.default_rng(20261120)
    cand = np.flatnonzero((R["status"] == L.OK) | (R["status"] == L.NO_EXIT_CAP))
    ix = np.sort(rng.choice(cand, size=min(n, len(cand)), replace=False))
    ia = E["ticker_a"].map(cid).to_numpy()[ix].astype(np.int64)
    ib = E["ticker_b"].map(cid).to_numpy()[ix].astype(np.int64)
    cols = E["t0m"].to_numpy()[ix][:, None] + np.arange(L.KW)[None, :]
    A, B = ML[ia[:, None], cols], ML[ib[:, None], cols]
    s, *_ = geometry(E.iloc[ix])
    g = E.iloc[ix]
    args = (s, g["beta"].to_numpy(float), g["alpha"].to_numpy(float), g["mu"].to_numpy(float), g["sigma"].to_numpy(float))
    o = L.scan_paths(A, B, *args, kmax_visible=R["trigger_k"][ix])
    same_t = int((o["trigger_k"] == R["trigger_k"][ix]).sum())
    same_r = int((o["exit_reason"] == R["exit_reason"][ix]).sum())
    log(f"[S2BUILD] RECEIPT poison (mids stamped after k_trig overwritten with NaN): sample {len(ix):,} events (seeded); trigger_k unchanged on {same_t:,}, exit_reason unchanged on {same_r:,}")
    assert same_t == len(ix) and same_r == len(ix), "the trigger depends on mids stamped after it"


# ------------------------------------------------------------------ reports (no y anywhere)
def groups_of(df):
    P = [("search ALL", (df["side"] == 0).to_numpy()), ("search test months", df["test"].to_numpy()), ("search other months", ((df["side"] == 0) & ~df["test"]).to_numpy()), ("vault", (df["side"] == 1).to_numpy())]
    for nm, m in P:
        yield "period", nm, m
    for mth in sorted(df["month"].unique()):
        for sd, sn in ((0, "search"), (1, "vault")):
            m = ((df["month"] == mth) & (df["side"] == sd)).to_numpy()
            if m.any():
                yield "month", f"{mth} {sn}", m
    for tr in TIERS + ["no tier"]:
        for nm, pm in P[1:]:
            m = pm & (df["tier"] == tr).to_numpy()
            if m.any():
                yield "tier", f"{nm} | {tr}", m


class Sel:
    """column access under a mask without copying the frame"""
    def __init__(self, df, m):
        self.df, self.m = df, m

    def __getitem__(self, c):
        return self.df[c].to_numpy()[self.m]


def line1(d, n):
    st = d["status"]
    ent = st != L.NO_ENTRY
    ok = st == L.OK
    ne, no = max(int(ent.sum()), 1), max(int(ok.sum()), 1)
    sc = " ".join(f"{STATUS_NAMES[k]} {int((st == k).sum()):,}" for k in (L.OK, L.NO_ENTRY, L.NO_EXIT, L.NO_EXIT_CAP))
    sa, sb, oa, ob = d["src_in_a"], d["src_in_b"], d["src_out_a"], d["src_out_b"]
    both_ctxs = int(((sa == 1) & (sb == 1) & ent).sum())
    anyg8 = int((((sa == 2) | (sb == 2)) & ent).sum())
    differ = int((((sa != oa) | (sb != ob)) & ok).sum())
    gf, gu, nf, z0 = d["gap_flag"], d["gap_flag_union"], d["n_filled"], d["z0_mid"]
    cap = int((st == L.NO_EXIT_CAP).sum())
    return (f"n {n:,}; {sc}; entry src both ctxs {pct(both_ctxs / ne)}, any G8 {pct(anyg8 / ne)} (of {ne:,} with entry mids); entry vs exit source differs {pct(differ / no)} of ok; "
            f"cap drops {cap:,} ({pct(cap / max(n, 1))} of n); gap_flag per-leg {int(gf.sum()):,} ({pct(gf.sum() / max(n, 1))} of n, {pct(gf.sum() / ne)} of with-entry); "
            f"union {int(gu.sum()):,} ({pct(gu.sum() / max(n, 1))}); mean n_filled (ok) {nf[ok].mean() if ok.any() else float('nan'):.2f}; z0_mid <= 0 {pct((z0[ent] <= 0).mean()) if ent.any() else 'n/a'} of with-entry")


def line2(d, n):
    st = d["status"]
    s2 = d["hs_mode_n"] >= 0
    n2 = max(int(s2.sum()), 1)
    hi, hsft = d["hs_imputed"][s2], d["hs_n_shift"][s2]
    return (f"events with a cost stage {int(s2.sum()):,}; no_spread drops {int((st == NO_SPREAD).sum()):,}; with >= 1 shifted (+-1 min) half-spread {pct((hsft > 0).sum() / n2)}; "
            f"with >= 1 median-imputed {pct((hi > 0).sum() / n2)} (first cause: day file absent {pct((hi == 1).sum() / n2)}, minute absent {pct((hi == 2).sum() / n2)}, crossed {pct((hi == 3).sum() / n2)}); "
            f"funding_missing (a leg without a file) {pct(d['funding_missing'][s2].sum() / n2)}; events with >= 1 missing funding hour {pct((d['funding_hours_missing'][s2] > 0).sum() / n2)}")


def report(df, fn, title):
    log(f"[S2BUILD] ===== {title} =====")
    for kind, nm, m in groups_of(df):
        log(f"[S2BUILD] [{kind}] {nm}: " + fn(Sel(df, m), int(m.sum())))


# ------------------------------------------------------------------ stage 2
def stage2(E, R, cid, ML, SRC, HS, CR, absent_minute, mon_of_minute, med, CS, CM, has):
    n = len(E)
    ia = E["ticker_a"].map(cid).to_numpy().astype(np.int64)
    ib = E["ticker_b"].map(cid).to_numpy().astype(np.int64)
    t0m = E["t0m"].to_numpy()
    s, dir_a, dir_b, wa, wb = geometry(E)
    names = ["gross_bp", "wxa", "wxb", "hsa_in", "hsb_in", "hsa_out", "hsb_out", "fee_in_bp", "fee_out_bp", "funding_bp", "y_taker"]
    Y = {k: np.full(n, np.nan) for k in names}
    Y["hs_imputed"] = np.zeros(n, np.int8)
    Y["hs_n_shift"] = np.zeros(n, np.int8)
    Y["hs_mode_n"] = np.full(n, -1, np.int8)                  # -1: no stage-2 row (status not ok)
    Y["funding_missing"] = np.zeros(n, bool)
    Y["funding_hours_missing"] = np.zeros(n, np.int32)
    status = R["status"].copy()
    leg_stamps = {k: 0 for k in ("own", "shift", "median", "none")}
    causes = {1: 0, 2: 0, 3: 0}
    okidx = np.flatnonzero(status == L.OK)
    t = time.time()
    for i0 in range(0, len(okidx), 20000):
        ix = okidx[i0:i0 + 20000]
        q0, qx = t0m[ix], t0m[ix] + R["exit_k"][ix]
        la0, lb0, lax, lbx = ML[ia[ix], q0], ML[ib[ix], q0], ML[ia[ix], qx], ML[ib[ix], qx]
        assert np.isfinite(la0).all() and np.isfinite(lb0).all() and np.isfinite(lax).all() and np.isfinite(lbx).all(), "an entry or exit price is not a real mid"
        g, wxa, wxb = L.gross_bp(wa[ix], wb[ix], dir_a[ix], dir_b[ix], la0, lax, lb0, lbx)
        hs = {}
        modes = []
        for nm, ci, q in (("hsa_in", ia[ix], q0), ("hsb_in", ib[ix], q0), ("hsa_out", ia[ix], qx), ("hsb_out", ib[ix], qx)):
            v, mode, cause = L.lookup_hs(HS, CR, ci, q, mon_of_minute, med, absent_minute)
            hs[nm] = v
            modes.append((mode, cause))
        mode_all = np.stack([m for m, _ in modes], 1)
        cause_all = np.stack([c for _, c in modes], 1)
        for k_, code in (("own", 0), ("shift", 1), ("median", 2), ("none", 3)):
            leg_stamps[k_] += int((mode_all == code).sum())
        for c_ in (1, 2, 3):
            causes[c_] += int(((mode_all == 2) & (cause_all == c_)).sum())
        no_sp = (mode_all == 3).any(1)
        first_imp = np.where((mode_all == 2).any(1), cause_all[np.arange(len(ix)), np.argmax(mode_all == 2, axis=1)], 0)
        fee_in = L.FEE_BP * (wa[ix] + wb[ix])
        fee_out = L.FEE_BP * (wxa + wxb)
        hs_in = wa[ix] * hs["hsa_in"] + wb[ix] * hs["hsb_in"]
        hs_out = wxa * hs["hsa_out"] + wxb * hs["hsb_out"]
        h1 = q0 // 60 + 1                       # axis start is a multiple of 60 minutes: q // 60 is the hour index; boundaries H with floor_hour(t0) < H <= exit stamp
        h2 = qx // 60
        f, mh = L.funding_bp(CS, CM, has, ia[ix], ib[ix], h1, h2, wa[ix], wb[ix], dir_a[ix], dir_b[ix])
        y = g - fee_in - fee_out - hs_in - hs_out + f
        for k_, v in (("gross_bp", g), ("wxa", wxa), ("wxb", wxb), ("fee_in_bp", fee_in), ("fee_out_bp", fee_out), ("funding_bp", f), *hs.items()):
            Y[k_][ix] = v
        Y["y_taker"][ix] = np.where(no_sp, np.nan, y)
        Y["hs_imputed"][ix] = first_imp
        Y["hs_n_shift"][ix] = (mode_all == 1).sum(1)
        Y["hs_mode_n"][ix] = 0
        Y["funding_missing"][ix] = ~(has[ia[ix]] & has[ib[ix]])
        Y["funding_hours_missing"][ix] = mh
        status[ix[no_sp]] = NO_SPREAD
    log(f"[S2BUILD] stage 2 done in {time.time() - t:.0f}s; half-spread leg-stamps (4 per ok event): own {leg_stamps['own']:,}, shifted +-1 min {leg_stamps['shift']:,}, coin-month median {leg_stamps['median']:,} (cause at own stamp: day file absent {causes[1]:,}, minute absent {causes[2]:,}, crossed {causes[3]:,}), none -> no_spread {leg_stamps['none']:,}")
    return Y, status


# ------------------------------------------------------------------ receipts
def load_runs(side):
    return {(mo, fee): pd.read_parquet(f"{T}trades_q0.01_stopnone_fee{fee}{NB.SFX[(side, mo)]}.parquet") for mo in (10, 20) for fee in ("maker", "taker")}


def receipt_R1(E):
    """R1 (needs no label, runs BEFORE the price matrices are built): with CLOSE prices at the saved stamps the label formulas (lib.gross_bp, weights, directions) reproduce the saved gross_pnl
    of the eight COSTS1 headline runs to 1e-4 dollars. It reproduces saved numbers only; no new outcome is read."""
    geo = E.set_index("event_id")
    for side in ("test", "vault"):
        runs = load_runs(side)
        coins = sorted({c for d in runs.values() for c in set(d["ticker_a"]) | set(d["ticker_b"])})
        base = int(min(NB.epoch_min(d["t0"]).min() for d in runs.values())) - 1
        n_min = int(max(NB.epoch_min(d["exit_time"]).max() for d in runs.values())) + 3 - base
        cid_s, CL, ML_s, MS = NB.load_arrays(side, coins, base, n_min)
        del ML_s, MS
        for (mo, fee), d in runs.items():
            g = geo.loc[d["event_id"]]
            _, dir_a, dir_b, wa, wb = geometry(g)
            t0m_, exm = NB.epoch_min(d["t0"]), NB.epoch_min(d["exit_time"])
            ia_, ib_ = d["ticker_a"].map(cid_s).to_numpy().astype(np.int64), d["ticker_b"].map(cid_s).to_numpy().astype(np.int64)
            gb, _, _ = L.gross_bp(wa, wb, dir_a, dir_b, CL[ia_, t0m_ - base], CL[ia_, exm - base], CL[ib_, t0m_ - base], CL[ib_, exm - base])
            err = np.abs(gb * d["notional"].to_numpy() / 1e4 - d["gross_pnl"].to_numpy())
            log(f"[S2BUILD] RECEIPT R1 {side} open{mo} {fee}: {len(d):,} trades; label formula on CLOSE prices vs saved gross_pnl: max abs diff ${np.nanmax(err):.2e} ({int(np.isnan(err).sum())} NaN)")
            assert np.nanmax(err) < 1e-4, "R1: the label formulas do not reproduce the saved gross"
        del CL


def receipt_R2(labels):
    """R2 (TEST runs only; the vault runs wait, vault discipline): this build's exit stamp vs the saved close exit minute, and this build's funding_bp vs the saved funding. Printed, not asserted.
    Prints exit minutes and funding only; no y or gross of this build."""
    lab_all = labels.set_index("event_id")
    for (mo, fee), d in load_runs("test").items():
        lab = lab_all.reindex(d["event_id"])
        okm = (lab["status"] == L.OK).to_numpy()
        if not okm.any():
            log(f"[S2BUILD] RECEIPT R2 test open{mo} {fee}: no trade of this run has a label in this build's event set")
            continue
        saved_k = ((NB.epoch_min(d["exit_time"]) - NB.epoch_min(d["t0"])))[okm]
        dk = lab["exit_k"].to_numpy()[okm] - saved_k
        qs = np.percentile(dk, [5, 25, 50, 75, 95])
        sf = (d["funding_received"] - d["funding_paid"]).to_numpy()[okm] / d["notional"].to_numpy()[okm] * 1e4
        df_ = lab["funding_bp"].to_numpy()[okm] - sf
        fq = np.nanpercentile(df_, [5, 25, 50, 75, 95])
        log(f"[S2BUILD] RECEIPT R2 test open{mo} {fee}: {int(okm.sum()):,} trades with a label; exit minute (this build minus saved close exit) quantiles 5/25/50/75/95 {qs.tolist()}, equal on {pct((dk == 0).mean())}; "
            f"funding_bp (this build minus saved funding in bp of notional) quantiles 5/25/50/75/95 {[round(float(x), 3) for x in fq]}, equal within 1e-9 on {pct((np.abs(df_) < 1e-9).mean())}; saved exit reason mu {pct((d['exit_reason'].to_numpy()[okm] == 'mu').mean())}, this build mu {pct((lab['exit_reason'].to_numpy()[okm] == L.REASON_MU).mean())}")


def main():
    log(f"[S2BUILD] script sha256 {sha(__file__)}; lib {sha(HERE + '/s2_target_lib.py')}; rules s2_target_rules.md sha256 {sha(MODEL + '/s2_target_rules.md')}; slim manifest {json.load(open(S2 + 'g8_slim_manifest.json'))}")
    cj = json.load(open(C1 + "costs_analysis_conservative.json"))
    E = load_events()
    E = add_tiers(E, cj)
    receipt_R1(E)
    if TRIAL:
        E = E[E["t0"].dt.strftime("%Y-%m-%d").isin(TRIAL_DAYS)].reset_index(drop=True)
        log(f"[S2BUILD] TRIAL: events of {TRIAL_DAYS} only: {len(E):,} (search test {int(E['test'].sum()):,}, search other {int(((E['side'] == 0) & ~E['test']).sum()):,}, vault {int((E['side'] == 1).sum()):,}); output to logs/s2/trial/")
        assert E["test"].sum() > 0 and (E["side"] == 1).any() and ((E["side"] == 0) & ~E["test"]).any()
    coins = sorted(set(E["ticker_a"]) | set(E["ticker_b"]))
    log(f"[S2BUILD] coins {len(coins)}")
    cid, ML, SRC, HS, CR, absent_minute, mon_of_minute, med = load_matrices(coins)
    # ---- 1. availability stage (no gross, return or y)
    R, runs = stage1(E, cid, ML, SRC)
    A1 = E[["event_id", "side", "test", "month", "tier"]].copy()
    for k_, v in R.items():
        A1[k_] = v
    report(A1, line1, "AVAILABILITY STAGE (path scan only: status, gaps, flags, sources; no gross, return or y)")
    for pname, (rl, ru) in runs.items():
        tl, tu = int(rl.sum()), int(ru.sum())
        log(f"[S2BUILD] GAP-RUN LENGTHS {pname}: per-leg runs {tl:,}: " + ", ".join(f"{n} {pct(int(v) / max(tl, 1))}" for n, v in zip(L.RUN_NAMES, rl)) + f"; union runs {tu:,}: " + ", ".join(f"{n} {pct(int(v) / max(tu, 1))}" for n, v in zip(L.RUN_NAMES, ru)))
    # absent G8 days: events whose window touches them
    t0m, side = E["t0m"].to_numpy(), E["side"].to_numpy()
    st = R["status"]
    for a in ABSENT:
        d0 = int((pd.Timestamp(a, tz="UTC").value // 60_000_000_000) - BASE)
        tch = (t0m <= d0 + 1439) & (t0m + L.KW - 1 >= d0)
        log(f"[S2BUILD] G8-absent day {a}: events whose window touches it: search {int((tch & (side == 0)).sum()):,} (ok {int((tch & (side == 0) & (st == L.OK)).sum()):,}), vault {int((tch & (side == 1)).sum()):,} (ok {int((tch & (side == 1) & (st == L.OK)).sum()):,})")
    poison_receipt(E, cid, ML, R)
    # ---- 2. hard stops (test months; per-leg gap_flag; denominator all test-month events)
    tm = E["test"].to_numpy()
    n_test = int(tm.sum())
    n_cap = int((tm & (st == L.NO_EXIT_CAP)).sum())
    n_flag = int((tm & R["gap_flag"]).sum())
    ne = int((tm & (st != L.NO_ENTRY)).sum())
    log(f"[S2BUILD] HARD STOP CHECK (test months, {n_test:,} events): cap drops {n_cap:,} = {100 * n_cap / n_test:.3f}% of all (limit 1%; {100 * n_cap / ne:.3f}% of the {ne:,} with entry mids); per-leg gap_flag {n_flag:,} = {100 * n_flag / n_test:.3f}% of all (limit 10%; {100 * n_flag / ne:.3f}% of with-entry); union flag (sensitivity) {int((tm & R['gap_flag_union']).sum()):,} = {100 * (tm & R['gap_flag_union']).sum() / n_test:.3f}%")
    try:
        L.check_stops(n_test, n_cap, n_flag)
    except L.StopBuild as e:
        log(f"[S2BUILD] HARD STOP: {e}. NO LABEL BUILT. Numbers go to the planner.")
        sys.exit(2)
    log("[S2BUILD] both hard stops passed; y components are computed from here on")
    # ---- 3. y components (never printed)
    Y, status = stage2(E, R, cid, ML, SRC, HS, CR, absent_minute, mon_of_minute, med, *load_funding(coins))
    out = E[["event_id", "side", "t0", "month", "tier", "test"]].copy()
    out["status"] = status
    for k_ in ("trigger_k", "exit_k", "exit_reason", "src_in_a", "src_in_b", "src_out_a", "src_out_b", "max_gap_len_leg", "gap_flag", "max_gap_len_union", "gap_flag_union", "n_filled", "z0_mid"):
        out[k_] = R[k_]
    wa, wb = geometry(E)[3:]
    out["wa"], out["wb"] = wa, wb
    for k_, v in Y.items():
        out[k_] = v
    A2 = A1.copy()
    A2["status"] = status
    for k_ in ("hs_mode_n", "hs_n_shift", "hs_imputed", "funding_missing", "funding_hours_missing"):
        A2[k_] = Y[k_]
    report(A2, line2, "MISSING-DATA COUNTS of the cost stage (half-spread and funding; counts only, no y)")
    st_all = out["status"].to_numpy()
    log("[S2BUILD] FINAL STATUS COUNTS: " + "; ".join(f"{p}: " + ", ".join(f"{STATUS_NAMES[k]} {int(((st_all == k) & m).sum()):,}" for k in (L.OK, L.NO_ENTRY, L.NO_EXIT, L.NO_EXIT_CAP, NO_SPREAD)) for p, m in (("search", side == 0), ("vault", side == 1))))
    ns = np.flatnonzero(st_all == NO_SPREAD)
    if len(ns):
        ia_n = E["ticker_a"].map(cid).to_numpy()[ns].astype(np.int64)
        ib_n = E["ticker_b"].map(cid).to_numpy()[ns].astype(np.int64)
        mi = mon_of_minute[E["t0m"].to_numpy()[ns]]
        cn = {i: c for c, i in cid.items()}
        tmask = E["test"].to_numpy()[ns]
        cnt = {}
        for ci_ in (ia_n, ib_n):
            bad = np.isnan(med[ci_, mi])
            for c_, m_, sd_, tt_ in zip(ci_[bad], mi[bad], side[ns][bad], tmask[bad]):
                k_ = (int(sd_), bool(tt_), cn[int(c_)], int(m_))
                cnt[k_] = cnt.get(k_, 0) + 1
        for sd_, tt_, nm_ in ((0, True, "search test months"), (0, False, "search other months"), (1, False, "vault")):
            rows = sorted(((c, m, n) for (s_, t_, c, m), n in cnt.items() if s_ == sd_ and t_ == tt_), key=lambda r: (r[1], r[0]))
            log(f"[S2BUILD] NO_SPREAD CAUSE {nm_}: {sum(n for _, _, n in rows):,} coin-leg hits in {len(rows)} coin-months (a leg whose coin has no usable G8 half-spread row anywhere in the calendar month of the event; month index from 2025-06 = 0): " + "; ".join(f"{c} m{m}: {n}" for c, m, n in rows))
    # ---- receipts
    ok_ = (out["status"] == L.OK).to_numpy()
    y2 = (out["gross_bp"] - out["fee_in_bp"] - out["fee_out_bp"] - (out["wa"] * out["hsa_in"] + out["wb"] * out["hsb_in"]) - (out["wxa"] * out["hsa_out"] + out["wxb"] * out["hsb_out"]) + out["funding_bp"]).to_numpy()
    idn = np.abs(y2[ok_] - out["y_taker"].to_numpy()[ok_])
    n_nan = int(np.isnan(out["y_taker"].to_numpy()[ok_]).sum())
    fee_ok = bool(np.allclose(out["fee_in_bp"].to_numpy()[ok_], 4.5))
    w_ok = bool(np.allclose(out["wa"] + out["wb"], 1.0))
    log(f"[S2BUILD] RECEIPT identity: the stored components reproduce the label on {int(ok_.sum()):,} ok events: max abs diff {np.nanmax(idn):.2e} bp (values are not printed); entry fee = 4.5 bp on all: {fee_ok}; wa + wb = 1 on all: {w_ok}; ok events with a NaN label: {n_nan}")
    assert np.nanmax(idn) < 1e-9
    if (out["side"] == 0).any():
        receipt_R2(out)
    # ---- write (search file now; the vault file is written too and is NOT read by any step before the planner calls the vault scoring)
    odir = S2 + ("trial/" if TRIAL else "")
    os.makedirs(odir, exist_ok=True)
    for sd, nm in ((0, "s2_labels_search.parquet"), (1, "s2_labels_vault.parquet")):
        o = out[out["side"] == sd].reset_index(drop=True)
        for c in o.columns:
            if o[c].dtype == np.float64 and c not in ("gross_bp", "y_taker", "funding_bp"):
                o[c] = o[c].astype(np.float32)
        o.to_parquet(odir + nm, index=False)
        log(f"[S2BUILD] wrote {odir.replace(MODEL + os.sep, '')}{nm}: {len(o):,} rows, {os.path.getsize(odir + nm) / 1e6:.0f} MB, sha256 {sha(odir + nm)}")
        r = pd.read_parquet(odir + nm)
        rk = (r["status"] == L.OK).to_numpy()
        yr = (r["gross_bp"] - r["fee_in_bp"] - r["fee_out_bp"] - (r["wa"] * r["hsa_in"] + r["wb"] * r["hsb_in"]) - (r["wxa"] * r["hsa_out"] + r["wxb"] * r["hsb_out"]) + r["funding_bp"]).to_numpy()
        dd = np.abs(yr[rk] - r["y_taker"].to_numpy()[rk])
        log(f"[S2BUILD] RECEIPT identity on the WRITTEN file {nm} (read back, float32 columns): ok events {int(rk.sum()):,}, max abs diff {np.nanmax(dd) if rk.any() else 0.0:.2e} bp (tolerance 1e-3; values not printed)")
        assert (not rk.any()) or np.nanmax(dd) < 1e-3
        del r
    log(f"[S2BUILD] no label value or return was printed by this script. total {time.time() - T0:.0f}s")


if __name__ == "__main__":
    main()
