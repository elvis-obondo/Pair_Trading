"""COSTS1 analysis: does the edge survive realistic execution costs? Re-costs the SAVED trades of the priority runs (q 1% / no stop / maker and taker, max_open 10 and 20; vault
tags vault_open10 / vault_open20, test months base / open20) with the G8 order-book table rows pulled on EC2 (logs/costs1/g8/g8_rows.parquet). ANALYSIS ONLY: no AWS call, no engine run,
no tuning of q, stops or timeout. The decision rules are in research/model/costs1_rules.md (sections 0-8, fixed before any result); this file implements them. Where the rules left a
convention open, it is fixed HERE (listed below) and every such choice is labelled in the log.

    python -u research/model/diagnostics/costs_analysis.py [--scale PATH] [--tag NAME] > research/model/diagnostics/costs_analysis.log

CONVENTIONS FIXED IN THIS FILE (not in the rules file)
  K1  Book lookup for (coin, minute m): own minute; else m-1; else m+1 (m-1 first: it is information from before the fill). A row with crossed = 1 or a NaN mid is not usable.
      Prices of a fill on a table row from m (own) are relative to that row's mid; on a +-1 row or on the no-book proxy they are relative to the ENGINE'S reference close at minute m
      (cleaned close of label m-1), because a neighbour row's mid carries a minute of drift. Maker limits use the row's own best bid / ask (+-1 rows included); on the proxy the limit is ref x (1 -+ proxy bp).
  K2  Impact multiplier m scales only the part of the taker cost above the half-spread: cost = half_spread + m x (curve - half_spread). The no-book proxy is scaled by m as a whole.
  K3  A fill time is the START of the bar label f (minute f of the wall clock); a cross at the end of a W-minute window is at minute t0 + W (entry) / exit + W (exit).
      A trade is MISSED if both entry legs stay unfilled over W, or if the later entry fill minute >= the saved exit minute.
  K4  Funding is left as saved (not re-timed for a later entry or a later maker exit). The saved exit date is kept for the daily series (a maker exit that fills up to W minutes later is not moved).
  K5  Liquidity tier: terciles of each coin's median daily traded notional (build2 1-minute cache column notional, days of the period's window on which the coin traded), over the coins that
      appear in the period's priority runs (the coin set of the period). A trade takes its less liquid leg's tier. Receipt: the vault maker open10 zero-cost share of net in the least liquid third is
      printed beside Part C's 82.9%.
  K6  Tick = smallest positive absolute step between consecutive 1-minute closes of the coin in the calendar month of the event (build2 cache; an estimate). No tick: strict = lenient (counted).
  K7  Daily series: calendar days from the first entry day to the last saved exit day, realised net by saved exit day (K4), zeros on idle days. Sharpe = mean/std(ddof 1) x sqrt(365); drawdown on
      equity = 1000 + cumulative daily net, as a fraction of the running peak; profit factor = sum of positive trade nets / |sum of negative trade nets|. Same function on the zero-cost saved trades.
      The engine's own (marked-account) figures are NOT reproduced here (R4: reference only); they are in the S1 reports.
  K8  Proxy for a leg without a usable book = 0.5 x (impact_ask - impact_bid) / mid of the coin at that wall-clock minute (ctxs cache); when the ctxs row is missing the coin's median of that
      quantity over the pulled minutes (counted as 'proxy fallback'). Cause of every proxy leg is printed: day file missing / minute absent / crossed / NaN field.
  K9  Calibrated variant (--scale PATH, JSON {"edges": [...], "ratio": [...]}, from the 20-file validation): the curve cost c of a with-book fill is multiplied by ratio[bucket of S]. Absent = conservative curve.
  K10 Headline cell (R1): maker runs strict, W = 5, impact multiplier 1; taker runs multiplier 1. Sensitivity cells: maker 3 W x 2 rules x 3 multipliers = 18; taker 3 multipliers = 3.
"""
import json
import math
import os
import sys
import time
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.dirname(HERE)
sys.path.insert(0, MODEL)
assert os.environ.get("PROFIT1_VAULT", "") != "1"
import harness as H  # noqa: E402
import vault_loader as VL  # noqa: E402

T = os.path.join(MODEL, "logs", "profit1") + os.sep
C1 = os.path.join(MODEL, "logs", "costs1") + os.sep
FEE_M, FEE_T = 0.00015, 0.00045
WS, RULES, MULTS = (1, 5, 15), ("lenient", "strict"), (0.5, 1.0, 2.0)
HEAD = dict(W=5, rule="strict", mult=1.0)
VAULT_FIRST_DAY = "20260713"
RUNS = [(s, mo, fee) for s in ("vault", "test") for mo in (10, 20) for fee in ("maker", "taker")]
SFX = {("vault", 10): "_vault_open10", ("vault", 20): "_vault_open20", ("test", 10): "", ("test", 20): "_open20"}
TIERS = ["least liquid third", "middle third", "most liquid third"]
BMODE = ["remainder"]      # beyond-book pricing: "remainder" = HEADLINE (planner ruling 2026-11-14, rules section 1 wording: the stored levels are walked at their prices, only the REMAINDER is priced at the last stored level);
#                           "whole" = rules section 8 as written (the WHOLE leg at the last stored level), printed beside it
T0 = time.time()
TIMES = {}
RES = {"notes": {}}


def log(m):
    print(m, flush=True)


def lap(name, t):
    TIMES[name] = round(time.time() - t, 1)
    log(f"[COSTS] timing: {name} took {TIMES[name]:.1f}s")


def epoch_min(ts):
    return ((pd.to_datetime(ts, utc=True) - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(minutes=1)).to_numpy().astype("int64")


def day_of(minute):
    return pd.Timestamp(int(minute) * 60, unit="s").strftime("%Y%m%d")


# ------------------------------------------------------------------ extract receipt, G8 table, targets
def receipt():
    txt = open(C1 + "g8/extract.log").read().strip().split("\n")
    done = [x for x in txt if x.startswith("[G8X] done")]
    assert done and txt[-1].startswith("[G8X] exit status 0"), "extract.log does not end with the [G8X] done line and exit status 0: refusing to read g8_rows.parquet"
    first = [x for x in txt if x.startswith("[G8X] wanted (coin, minute) pairs")][0]
    n_log = int(first.split("pairs")[1].split(";")[0].replace(",", ""))
    tg = pd.read_parquet(C1 + "l2_targets_priority.parquet")
    pairs = pd.DataFrame({"coin": np.repeat(tg["coin"].to_numpy(), tg["n_minutes"].to_numpy()), "minute": np.concatenate([np.asarray(m, dtype=np.int64) for m in tg["minutes"]])}).drop_duplicates()
    assert n_log == len(pairs), f"logged wanted pairs {n_log} != targets' unique pairs {len(pairs)}"
    missing_days = sorted(x.split("]")[1].split(":")[0].strip() for x in txt if "day file MISSING" in x)
    log(f"[COSTS] EXTRACT RECEIPT: {done[0]}; logged wanted pairs {n_log:,} = targets' unique pairs {len(pairs):,}; day files missing: {len(missing_days)} {missing_days}")
    return pairs, missing_days


def load_g8(pairs):
    G = pd.read_parquet(C1 + "g8/g8_rows.parquet")
    coins = sorted(pairs["coin"].unique())
    cid = {c: i for i, c in enumerate(coins)}
    G["cid"] = G["coin"].map(cid).astype(np.int64)
    assert not G.duplicated(["cid", "minute"]).any()
    key = G["cid"].to_numpy() * 10 ** 8 + G["minute"].to_numpy()
    o = np.argsort(key)
    G = G.iloc[o].reset_index(drop=True)
    cols = {c: G[c].to_numpy(dtype=np.float64) for c in ["mid", "spread_bp", "crossed", "snap_off_s", "slip_buy_1k", "slip_sell_1k", "bid_d10", "bid_d25", "bid_d50", "ask_d10", "ask_d25", "ask_d50", "book_reach_bid_bp", "book_reach_ask_bp"]}
    return cid, key[o], cols, G


class Books:
    def __init__(self, cid, keys, cols, missing_days, pairs, ctx_half, ctx_med):
        self.cid, self.keys, self.c, self.md = cid, keys, cols, set(missing_days)
        self.ctx_half, self.ctx_med = ctx_half, ctx_med
        self.cache = {}
        self.proxy_fallback = 0

    def row(self, ci, m):
        k = ci * 10 ** 8 + m
        j = int(np.searchsorted(self.keys, k))
        return j if j < len(self.keys) and self.keys[j] == k else -1

    def usable(self, j):
        return j >= 0 and self.c["crossed"][j] == 0.0 and np.isfinite(self.c["mid"][j]) and np.isfinite(self.c["spread_bp"][j])

    def get(self, ci, m):
        """-> (row or -1, source 0 own / 1 pm1 / 2 proxy, cause for proxy: day / absent / crossed / nan)"""
        key = (ci, m)
        r = self.cache.get(key)
        if r is not None:
            return r
        j = self.row(ci, m)
        if self.usable(j):
            r = (j, 0, "")
        else:
            cause = ("day" if day_of(m) in self.md else "absent") if j < 0 else ("crossed" if self.c["crossed"][j] == 1.0 else "nan")
            r = (-1, 2, cause)
            for dm in (-1, 1):
                j2 = self.row(ci, m + dm)
                if self.usable(j2):
                    r = (j2, 1, "")
                    break
        self.cache[key] = r
        return r

    def proxy_bp(self, ci, m):
        v = self.ctx_half.get((ci, m))
        if v is None:
            self.proxy_fallback += 1
            v = self.ctx_med.get(ci, 0.0)
        return v


def curve_bp(c, j, buy, S, scale):
    """Conservative piecewise-linear cost (bp vs mid) of a leg of USD S on the hit side; returns (bp, beyond_book)."""
    sp = c["spread_bp"][j]
    pts = [(1000.0, c["slip_buy_1k"][j] if buy else c["slip_sell_1k"][j])]
    side = "ask" if buy else "bid"
    for e in (10, 25, 50):
        pts.append((c[f"{side}_d{e}"][j], float(e)))
    xs, ys = [0.0], [sp / 2]
    for x, y in sorted((p for p in pts if np.isfinite(p[0]) and np.isfinite(p[1]))):
        if x > xs[-1]:
            xs.append(float(x))
            ys.append(float(y))
    ys = np.maximum.accumulate(ys)
    if S <= xs[-1]:
        v, beyond = float(np.interp(S, xs, ys)), False
    else:
        reach = max(float(ys[-1]), float(c["book_reach_ask_bp" if buy else "book_reach_bid_bp"][j]))
        beyond = True
        if BMODE[0] == "whole":
            v = reach
        else:                                          # first xs[-1] USD at the curve's average cost there, the remainder at the last stored level
            v = (xs[-1] * float(ys[-1]) + (S - xs[-1]) * reach) / S
    if scale is not None and not beyond:
        v *= scale["ratio"][int(np.searchsorted(scale["edges"], S, side="right"))]
    return v, beyond


# ------------------------------------------------------------------ prices and bars
class Prices:
    def __init__(self, side, coins):
        d = "cleaned_vault" if side == "vault" else "cleaned"
        self.p = {}
        for c in coins:
            f_ = f"{T}{d}/price/{c}.parquet"
            if not os.path.exists(f_):
                continue
            df = pd.read_parquet(f_, columns=["label", "log_close"])
            m = df["label"].to_numpy().astype("datetime64[m]").astype(np.int64)
            lo = int(m.min())
            a = np.full(int(m.max()) - lo + 1, np.nan)
            a[m - lo] = df["log_close"].to_numpy(float)
            self.p[c] = (lo, a)

    def logpx(self, coin, label_min):
        if coin not in self.p:
            return np.nan
        lo, a = self.p[coin]
        k = label_min - lo
        return a[k] if 0 <= k < len(a) else np.nan


class Bars:
    def __init__(self, coins):
        self.b = {}
        self.tick = {}
        for c in coins:
            df = pd.read_feather(f"{T}build2_1m_cache/{c}-1m.feather", columns=["date", "high", "low", "close", "notional"])
            m = pd.to_datetime(df["date"], utc=True).dt.tz_localize(None).to_numpy().astype("datetime64[m]").astype(np.int64)
            lo = int(m.min())
            n = int(m.max()) - lo + 1
            arrs = {}
            for k in ("high", "low", "close", "notional"):
                a = np.full(n, np.nan)
                a[m - lo] = df[k].to_numpy(float)
                arrs[k] = a
            self.b[c] = (lo, arrs)
            cl = arrs["close"]
            d = np.abs(np.diff(cl))
            ok = np.isfinite(d) & (d > 0)
            ts = pd.to_datetime((lo + np.arange(1, n))[ok] * 60, unit="s").strftime("%Y%m")
            g = pd.Series(d[ok]).groupby(np.asarray(ts)).min()
            self.tick[c] = g.to_dict()

    def win(self, coin, key, m0, n):
        lo, arrs = self.b[coin]
        a = arrs[key]
        out = np.full(n, np.nan)
        for k in range(n):
            i = m0 + k - lo
            if 0 <= i < len(a):
                out[k] = a[i]
        return out


def first_fill(hi, lo, limit, buy, tick, rule):
    """index of the first bar filled (99 if none), and the index of the first NaN bar (99 if none)"""
    nanpos = np.flatnonzero(~np.isfinite(hi) | ~np.isfinite(lo))
    if buy:
        cond = lo <= (limit if rule == "lenient" else limit - tick)
    else:
        cond = hi >= (limit if rule == "lenient" else limit + tick)
    f = np.flatnonzero(cond)
    return (int(f[0]) if len(f) else 99), (int(nanpos[0]) if len(nanpos) else 99)


# ------------------------------------------------------------------ the re-costing of one run
class RunData:
    def __init__(self, side, mo, fee, geo, px, bars, books):
        self.side, self.mo, self.fee = side, mo, fee
        d = pd.read_parquet(f"{T}trades_q0.01_stopnone_fee{fee}{SFX[(side, mo)]}.parquet").reset_index(drop=True)
        assert d["event_id"].is_unique
        g = geo.reindex(d["event_id"])
        assert g["beta"].notna().all() and g["z"].notna().all()
        d["beta"], d["z"] = g["beta"].to_numpy(), g["z"].to_numpy()
        for k in ("reach_10h", "minutes_to_mu", "gross_none"):
            d[k] = g[k].to_numpy()
        self.d = d
        n = len(d)
        ident = d["gross_pnl"] - d["entry_fee"] - d["exit_fee"] - d["entry_slip"] - d["exit_slip"] - d["funding_paid"] + d["funding_received"]
        assert float((ident - d["net"]).abs().max()) < 1e-9, "saved net != gross - fees - slips - funding_paid + funding_received"
        assert float(d["entry_slip"].abs().max()) == 0.0 and float(d["exit_slip"].abs().max()) == 0.0, "saved slippage is not zero"
        assert set(d["exit_reason"]).issubset({"mu", "stop", "timeout", "liquidation"}), set(d["exit_reason"])
        log(f"[COSTS] run {side} open{mo} {fee}: saved net identity holds (max diff {float((ident - d['net']).abs().max()):.1e}); entry/exit slippage all 0; exit reasons {d['exit_reason'].value_counts().to_dict()}")
        b = np.abs(d["beta"].to_numpy())
        self.la = d["notional"].to_numpy() / (1 + b)
        self.lb = d["notional"].to_numpy() * b / (1 + b)
        z, beta = d["z"].to_numpy(), d["beta"].to_numpy()
        self.dira = np.where(z >= 0, -1.0, 1.0)
        self.dirb = np.where(z >= 0, 1.0, -1.0) * np.where(beta >= 0, 1.0, -1.0)
        self.t0m, self.exm = epoch_min(d["t0"]), epoch_min(d["exit_time"])
        self.cids = [d["ticker_a"].map(books.cid).to_numpy(), d["ticker_b"].map(books.cid).to_numpy()]
        self.coins = [d["ticker_a"].to_numpy(), d["ticker_b"].to_numpy()]
        # engine reference prices and exit leg USD
        self.refin = np.zeros((n, 2))
        self.refout = np.zeros((n, 2))
        for leg in (0, 1):
            for i in range(n):
                self.refin[i, leg] = px.logpx(self.coins[leg][i], self.t0m[i] - 1)
                self.refout[i, leg] = px.logpx(self.coins[leg][i], self.exm[i] - 1)
        assert np.isfinite(self.refin).all() and np.isfinite(self.refout).all(), "missing cleaned price at a saved fill"
        mv = self.refout - self.refin
        self.lax, self.lbx = self.la * np.exp(mv[:, 0]), self.lb * np.exp(mv[:, 1])
        self.refin, self.refout = np.exp(self.refin), np.exp(self.refout)
        gross = self.la * self.dira * (np.exp(mv[:, 0]) - 1) + self.lb * self.dirb * (np.exp(mv[:, 1]) - 1)
        self.gross_err = np.abs(gross - d["gross_pnl"].to_numpy())
        log(f"[COSTS] run {side} open{mo} {fee}: {n:,} trades; gross reproduced from cleaned prices: max abs diff ${self.gross_err.max():.2e}, trades off by > $1e-6: {int((self.gross_err > 1e-6).sum())}")
        assert (self.gross_err > 1e-4).sum() == 0, "saved gross not reproduced"
        self.px, self.bars, self.books = px, bars, books


def side_of(buy):
    return "buy" if buy else "sell"


def taker_leg(R, books, i, leg, minute, S, buy, mult, scale, ref, fit=None):
    """one taker fill; returns p_fill, source (0 own, 1 pm1, 2 proxy), beyond, cause, cost_bp.
    fit (labelled ALTERNATIVE, never the headline): {'ic','sl'} of the volume fit; a beyond-book leg is then priced at half-spread + m x (ic + sl x sqrt(S / minute notional)), floored at the last-level price."""
    ci = int(R.cids[leg][i])
    j, src, cause = books.get(ci, minute)
    if j >= 0:
        c = books.c
        v, beyond = curve_bp(c, j, buy, S, scale)
        sp2 = c["spread_bp"][j] / 2
        if beyond and fit is not None:
            nt = R.bars.win(R.coins[leg][i], "notional", minute, 1)[0]
            if np.isfinite(nt) and nt > 0:
                v = max(v, sp2 + fit["ic"] + fit["sl"] * math.sqrt(S / nt))      # alternative estimate, labelled; cost never below the lower-bound price
        bp = sp2 + mult * (v - sp2)
        base = c["mid"][j] if src == 0 else ref
    else:
        bp, beyond = mult * books.proxy_bp(ci, minute), False
        base = ref
    p = base * (1 + bp / 1e4) if buy else base * (1 - bp / 1e4)
    return p, src, beyond, cause, bp


def maker_limit(R, books, i, leg, minute, buy, ref):
    """passive limit: buy at best bid, sell at best ask; (limit, src, cause)"""
    ci = int(R.cids[leg][i])
    j, src, cause = books.get(ci, minute)
    if j >= 0:
        c = books.c
        half = c["spread_bp"][j] / 2
        return c["mid"][j] * (1 - half / 1e4 if buy else 1 + half / 1e4), src, cause
    h = books.proxy_bp(ci, minute)
    return ref * (1 - h / 1e4 if buy else 1 + h / 1e4), 2, cause


def tick_of(bars, coin, minute):
    return bars.tick[coin].get(day_of(minute)[:6], 0.0)


def prep_windows(R):
    """first-fill indexes of every entry leg and every exit leg for both rules over a 15-bar window (W up to 15)"""
    books, bars = R.books, R.bars
    n = len(R.d)
    R.ent = {}
    R.ext = {}
    nzero_tick = 0
    for i in range(n):
        for leg in (0, 1):
            coin = R.coins[leg][i]
            dirn = (R.dira, R.dirb)[leg][i]
            # entry: buy if dir > 0
            buy = dirn > 0
            lim, src, cause = maker_limit(R, books, i, leg, int(R.t0m[i]), buy, R.refin[i, leg])
            hi, lo = bars.win(coin, "high", int(R.t0m[i]), 15), bars.win(coin, "low", int(R.t0m[i]), 15)
            tk = tick_of(bars, coin, int(R.t0m[i]))
            nzero_tick += tk == 0.0
            ntw = bars.win(coin, "notional", int(R.t0m[i]), 15)
            R.ent[(i, leg)] = dict(limit=lim, src=src, cause=cause, buy=buy, tick=tk, ntw=ntw, **{r: first_fill(hi, lo, lim, buy, tk, r) for r in RULES})
            # exit: passive side is opposite of the entry side: entry buy -> exit sell
            buy_x = not buy
            limx, srcx, causex = maker_limit(R, books, i, leg, int(R.exm[i]), buy_x, R.refout[i, leg])
            hix, lox = bars.win(coin, "high", int(R.exm[i]), 15), bars.win(coin, "low", int(R.exm[i]), 15)
            tkx = tick_of(bars, coin, int(R.exm[i]))
            ntx = bars.win(coin, "notional", int(R.exm[i]), 15)
            R.ext[(i, leg)] = dict(limit=limx, src=srcx, cause=causex, buy=buy_x, tick=tkx, ntw=ntx, **{r: first_fill(hix, lox, limx, buy_x, tkx, r) for r in RULES})
    log(f"[COSTS] windows prepared for {R.side} open{R.mo} {R.fee}: legs with tick unknown (strict = lenient): {nzero_tick}")


def evaluate(R, W, rule, mult, scale, fit=None):
    """Re-cost every trade of the run in one cell. Returns a DataFrame with one row per saved trade."""
    books = R.books
    d = R.d
    maker = R.fee == "maker"
    out = []
    saved_gross = d["gross_pnl"].to_numpy()
    fpaid, frecv = d["funding_paid"].to_numpy(), d["funding_received"].to_numpy()
    reasons = d["exit_reason"].to_numpy()
    for i in range(len(d)):
        legs_usd = (R.la[i], R.lb[i])
        legs_x = (R.lax[i], R.lbx[i])
        dirs = (R.dira[i], R.dirb[i])
        gain_in = gain_x = fee_in = fee_x = 0.0
        proxy_cause, beyond_any, nan_legs = [], False, 0
        uses = []                                       # (source, cause) of EVERY book lookup this trade rests on: maker limits too (checker F2)
        ent_fill_min, ent_kind, p_fill_in = [None, None], ["", ""], [0.0, 0.0]
        cost_bp_in = [0.0, 0.0]
        missed = ""
        if maker:
            fm = []
            for leg in (0, 1):
                e = R.ent[(i, leg)]
                f, nanp = e[rule]
                filled = f < W
                if nanp < W:
                    nan_legs += 1
                fm.append(int(R.t0m[i]) + f if filled else None)
                p_fill_in[leg] = e["limit"] if filled else None
            if fm[0] is None and fm[1] is None:
                missed = "both_unfilled"
            else:
                for leg in (0, 1):
                    S, dirn = legs_usd[leg], dirs[leg]
                    e = R.ent[(i, leg)]
                    uses.append((e["src"], e["cause"]))
                    if fm[leg] is not None:
                        ent_kind[leg], ent_fill_min[leg] = "maker", fm[leg]
                        fee_in += S * FEE_M
                    else:
                        mcross = int(R.t0m[i]) + W
                        p, src, beyond, cause, bp = taker_leg(R, books, i, leg, mcross, S, dirn > 0, mult, scale, R.refin[i, leg], fit)
                        p_fill_in[leg], ent_kind[leg], ent_fill_min[leg] = p, "cross", mcross
                        cost_bp_in[leg] = bp
                        fee_in += S * FEE_T
                        beyond_any |= beyond
                        uses.append((src, cause))
                if max(ent_fill_min) >= int(R.exm[i]):
                    missed = "late_fill"
        else:
            for leg in (0, 1):
                S, dirn = legs_usd[leg], dirs[leg]
                p, src, beyond, cause, bp = taker_leg(R, books, i, leg, int(R.t0m[i]), S, dirn > 0, mult, scale, R.refin[i, leg], fit)
                p_fill_in[leg], ent_kind[leg], ent_fill_min[leg], cost_bp_in[leg] = p, "taker", int(R.t0m[i]), bp
                fee_in += S * FEE_T
                beyond_any |= beyond
                uses.append((src, cause))
        if missed:
            row = dict(i=i, filled=False, missed=missed, net=0.0, nan_legs=nan_legs)
            if missed == "late_fill":
                # S2 (planner ruling): net stays 0 in the headline; ARITHMETIC BOUND (labelled): the legs that had filled at their limit BEFORE the saved exit minute must be unwound as a taker at the
                # exit-minute book, priced as the model prices a taker exit (curve + taker fee) plus the maker fee already paid on that leg's entry. Price drift of the unhedged leg is NOT included.
                n_f, unwind = 0, 0.0
                for leg in (0, 1):
                    if ent_fill_min[leg] is not None and ent_kind[leg] == "maker" and ent_fill_min[leg] < int(R.exm[i]):
                        n_f += 1
                        Sx = (R.lax[i], R.lbx[i])[leg]
                        _, _, _, _, bp = taker_leg(R, books, i, leg, int(R.exm[i]), Sx, dirs[leg] < 0, mult, scale, R.refout[i, leg], fit)
                        unwind += Sx * (FEE_T + bp / 1e4) + legs_usd[leg] * FEE_M
                row.update(late_legs=n_f, late_unwind=unwind)
            out.append(row)
            continue
        for leg in (0, 1):
            gain_in += dirs[leg] * legs_usd[leg] * (R.refin[i, leg] - p_fill_in[leg]) / R.refin[i, leg]
        # exit
        x_kind = ["", ""]
        cost_bp_x = [0.0, 0.0]
        for leg in (0, 1):
            S, dirn = legs_x[leg], dirs[leg]
            buy_x = dirn < 0
            use_maker = maker and reasons[i] == "mu"
            if use_maker:
                e = R.ext[(i, leg)]
                f, nanp = e[rule]
                filled = f < W
                uses.append((e["src"], e["cause"]))
                if nanp < W:
                    nan_legs += 1
                if filled:
                    p, kind, fee_x = e["limit"], "maker", fee_x + S * FEE_M
                    x_kind[leg] = kind
                    gain_x += dirn * S * (p - R.refout[i, leg]) / R.refout[i, leg]
                    continue
                mx = int(R.exm[i]) + W
                p, src, beyond, cause, bp = taker_leg(R, books, i, leg, mx, S, buy_x, mult, scale, R.refout[i, leg], fit)
                x_kind[leg] = "cross"
            else:
                p, src, beyond, cause, bp = taker_leg(R, books, i, leg, int(R.exm[i]), S, buy_x, mult, scale, R.refout[i, leg], fit)
                x_kind[leg] = "taker"
            cost_bp_x[leg] = bp
            fee_x += S * FEE_T
            beyond_any |= beyond
            uses.append((src, cause))
            gain_x += dirn * S * (p - R.refout[i, leg]) / R.refout[i, leg]
        proxy_cause = [c for (s_, c) in uses if s_ == 2]
        net = saved_gross[i] + gain_in + gain_x - fee_in - fee_x - fpaid[i] + frecv[i]
        # two-leg risk: the earlier-filled leg's move (bp, position-signed) from its fill to the later fill minute
        gap, move_bp = 0, np.nan
        if maker and ent_fill_min[0] is not None and ent_fill_min[1] is not None and ent_fill_min[0] != ent_fill_min[1]:
            gap = abs(ent_fill_min[0] - ent_fill_min[1])
            early = 0 if ent_fill_min[0] < ent_fill_min[1] else 1
            tlate = max(ent_fill_min)
            lp = R.px.logpx(R.coins[early][i], tlate - 1)
            move_bp = dirs[early] * (math.exp(lp) / p_fill_in[early] - 1) * 1e4
        out.append(dict(i=i, filled=True, missed="", net=net, gain_in=gain_in, gain_x=gain_x, fee_in=fee_in, fee_x=fee_x, n_proxy=len(proxy_cause), proxy_causes=",".join(proxy_cause), n_uses=len(uses), n_own=sum(1 for s_, _ in uses if s_ == 0), n_pm1=sum(1 for s_, _ in uses if s_ == 1), beyond=beyond_any,
                        nan_legs=nan_legs, gap=gap, move_bp=move_bp, ent_a=ent_kind[0], ent_b=ent_kind[1], x_a=x_kind[0], x_b=x_kind[1], cost_in=cost_bp_in[0] + cost_bp_in[1], cost_x=cost_bp_x[0] + cost_bp_x[1]))
    r = pd.DataFrame(out).set_index("i").reindex(range(len(d)))
    for col, dflt in (("missed", ""), ("late_legs", 0), ("late_unwind", 0.0), ("n_proxy", 0), ("n_uses", 0), ("n_own", 0), ("n_pm1", 0), ("beyond", False), ("proxy_causes", ""), ("nan_legs", 0), ("gap", 0)):
        if col not in r.columns:
            r[col] = dflt
    r["filled"] = r["filled"].fillna(False).astype(bool)
    r["net"] = r["net"].fillna(0.0)
    return r


# ------------------------------------------------------------------ metrics
def daily_metrics(d, net, days):
    ex = pd.to_datetime(d["exit_time"], utc=True).dt.floor("D").dt.tz_localize(None)
    s = pd.Series(np.asarray(net, float), index=ex).groupby(level=0).sum().reindex(days, fill_value=0.0)
    eq = 1000.0 + s.cumsum()
    peak = np.maximum.accumulate(np.concatenate([[1000.0], eq.to_numpy()]))[1:]
    mdd = float(((peak - eq.to_numpy()) / peak).max())
    mdd_usd = float((peak - eq.to_numpy()).max())
    sd = float(s.std(ddof=1))
    sh = float(s.mean() / sd * math.sqrt(365)) if sd > 0 else float("nan")
    n = np.asarray(net, float)
    pf = float(n[n > 0].sum() / abs(n[n < 0].sum())) if (n < 0).any() else float("inf")
    return dict(net=float(n.sum()), pf=pf, sharpe=sh, mdd=mdd, mdd_usd=mdd_usd)


def window_days(d):
    return pd.date_range(pd.to_datetime(d["t0"], utc=True).dt.floor("D").min().tz_localize(None), pd.to_datetime(d["exit_time"], utc=True).dt.floor("D").max().tz_localize(None), freq="D")


def fmt(x, nd=2):
    return "n/a" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:,.{nd}f}"


def breakeven_bp(net, notional):
    return float(net / (2 * notional) * 1e4) if notional > 0 else float("nan")


# ------------------------------------------------------------------ main
def main():
    args = sys.argv[1:]
    opt = lambda k, dflt=None: args[args.index(k) + 1] if k in args else dflt
    scale = json.load(open(opt("--scale"))) if opt("--scale") else None
    tag = opt("--tag", "conservative" if scale is None else "calibrated")
    log(f"[COSTS] variant: {tag}; scale {'none (the conservative straight-line curve)' if scale is None else scale}")
    RES["variant"], RES["scale"] = tag, scale
    t = time.time()
    pairs, missing_days = receipt()
    cid, keys, cols, G = load_g8(pairs)
    log(f"[COSTS] G8 rows {len(G):,}; snap_off_s by period (R5): " + "; ".join(f"{nm} median {G.loc[m, 'snap_off_s'].median():.2f}s, p90 {G.loc[m, 'snap_off_s'].quantile(0.9):.2f}s" for nm, m in
                                                                              (("test months", (G["minute"] // 1440) < (pd.Timestamp('2026-07-13').value // 60_000_000_000 // 1440)), ("vault", (G["minute"] // 1440) >= (pd.Timestamp('2026-07-13').value // 60_000_000_000 // 1440)))))
    # ctxs proxy lookups for the wanted minutes
    wanted = set(zip(pairs["coin"].map(cid), pairs["minute"]))
    wk = np.array(sorted(c * 10 ** 8 + m for c, m in wanted), dtype=np.int64)
    ctx_half = {}
    days = sorted(os.path.splitext(f)[0] for f in os.listdir(T + "ctxs_cache"))
    for dday in days:
        p = pd.read_parquet(f"{T}ctxs_cache/{dday}.parquet", columns=["time", "coin", "mid_px", "impact_bid_px", "impact_ask_px"])
        p = p[p["coin"].isin(cid)]
        tt = pd.to_datetime(p["time"], utc=True)
        ok = (tt.dt.second == 0) & (tt.dt.microsecond == 0)
        p, tt = p[ok], tt[ok]
        bid, ask, mid = (p[k].to_numpy(float) for k in ("impact_bid_px", "impact_ask_px", "mid_px"))
        good = (bid > 0) & (ask > bid) & (mid > 0)
        m = epoch_min(tt)
        k = p["coin"].map(cid).to_numpy().astype(np.int64) * 10 ** 8 + m
        sel = good & np.isin(k, wk)
        for kk, v in zip(k[sel], 0.5 * (ask - bid)[sel] / mid[sel] * 1e4):
            ctx_half[(int(kk // 10 ** 8), int(kk % 10 ** 8))] = float(v)
    ctx_med = pd.Series(list(ctx_half.values())).groupby(np.array([k[0] for k in ctx_half])).median().to_dict()
    log(f"[COSTS] ctxs proxy rows loaded for wanted minutes: {len(ctx_half):,} of {len(wanted):,} wanted (coin, minute) pairs")
    books = Books(cid, keys, cols, missing_days, pairs, ctx_half, ctx_med)
    lap("load extract, G8 table and ctxs proxy", t)

    t = time.time()
    # geometry
    gv = VL.load_vault_events(columns=["beta", "z", "reach_10h", "minutes_to_mu", "gross_none"]).reset_index(drop=True).set_index("event_id")
    gt = H.load_search_events(columns=["beta", "z", "reach_10h", "minutes_to_mu", "gross_none"]).reset_index(drop=True).set_index("event_id")
    geo = {"vault": gv, "test": gt}
    coins = sorted(cid)
    prices = {s: Prices(s, coins) for s in ("vault", "test")}
    bars = Bars(coins)
    lap("load geometry, cleaned prices and 1-minute bars", t)

    t = time.time()
    RUN = {}
    for (side, mo, fee) in RUNS:
        RUN[(side, mo, fee)] = RunData(side, mo, fee, geo[side], prices[side], bars, books)
    lap("prepare runs (legs, reference prices, gross receipt)", t)

    # liquidity tiers (K5)
    tier = {}
    for side in ("vault", "test"):
        cs = sorted({c for (s, mo, fee), R in RUN.items() if s == side for leg in (0, 1) for c in R.coins[leg]})
        d0 = min(R.d["t0"].min() for (s, _, _), R in RUN.items() if s == side)
        d1 = max(R.d["exit_time"].max() for (s, _, _), R in RUN.items() if s == side)
        a, b = int(epoch_min(pd.Series([d0]))[0] // 1440), int(epoch_min(pd.Series([d1]))[0] // 1440)
        med = {}
        for c in cs:
            lo, arrs = bars.b[c]
            nt = arrs["notional"]
            mins = lo + np.arange(len(nt))
            dd = mins // 1440
            sel = (dd >= a) & (dd <= b) & np.isfinite(nt)
            s_ = pd.Series(nt[sel]).groupby(dd[sel]).sum()
            s_ = s_[s_ > 0]
            med[c] = float(s_.median()) if len(s_) else np.nan
        ser = pd.Series(med).dropna()
        terc = pd.qcut(ser.rank(method="first"), 3, labels=TIERS)
        tier[side] = terc.to_dict()
        log(f"[COSTS] tiers {side}: {len(ser)} coins; median daily traded notional by tier: " + ", ".join(f"{k} ${ser[terc == k].median():,.0f}" for k in TIERS))
    for (side, mo, fee), R in RUN.items():
        o = {n: i for i, n in enumerate(TIERS)}
        R.d["tier"] = [min((tier[side].get(a), tier[side].get(b)), key=lambda x: o.get(x, 9)) if tier[side].get(a) and tier[side].get(b) else None for a, b in zip(R.d["ticker_a"], R.d["ticker_b"])]
        R.d["big_leg"] = np.maximum(R.la, R.lb)
        R.d["leg_bucket"] = pd.cut(R.d["big_leg"], [0, 100, 250, 1000, 1e9], labels=["< $100", "$100-250", "$250-1,000", "> $1,000"], right=False)
        R.d["missing_day"] = [(day_of(a) in set(missing_days)) or (day_of(b) in set(missing_days)) for a, b in zip(R.t0m, R.exm)]
    RES["tier_coins"] = {s: {k: sorted(c for c, v in tier[s].items() if v == k) for k in TIERS} for s in tier}

    # receipts: zero-cost break-evens (Part C) and tier share
    PC = json.load(open(MODEL + "/logs/s1/s1_vault_docx_partc.json"))
    partc = {}
    for sec in PC["sections"]:
        for tb in sec.get("tables", []):
            for per, pl in (("vault", "Vault, max_open "), ("test", "Test months, max_open ")):
                if tb["title"].startswith(pl) and "net PnL with extra slippage per fill" in tb["title"]:
                    mo = int(tb["title"].split("max_open ")[1].split(":")[0])
                    ci = tb["columns"].index("break-even extra slippage (bp per fill)")
                    for r in tb["rows"]:
                        if r[0] == "0.01" and r[1] == "no stop":
                            partc[(per, mo, r[2])] = (float(r[ci]), f"sections[{PC['sections'].index(sec)}] table '{tb['title']}' row q 0.01 / no stop / {r[2]}, column 'break-even extra slippage (bp per fill)'")
    assert len(partc) == 8, partc.keys()
    tier_ref = None
    for sec in PC["sections"]:
        for tb in sec.get("tables", []):
            if tb["title"].startswith("Vault, q 1% / no stop / maker fees, open10: by coin liquidity tier"):
                ci = tb["columns"].index("share of run net")
                tier_ref = (float(tb["rows"][0][ci].rstrip("%")) / 100, f"table '{tb['title'][:70]}...' row '{tb['rows'][0][0]}' column 'share of run net'")
    assert tier_ref is not None
    log(f"[COSTS] RECEIPT references read from research/model/logs/s1/s1_vault_docx_partc.json (script_sha256 {PC.get('script_sha256', 'n/a')[:12]}): break-evens and tier share below; keys printed with each")
    log("[COSTS] RECEIPT (Part C arithmetic, zero-cost saved trades): break-even extra slippage bp per fill = sum(net) / (2 x sum(notional)) x 1e4")
    for k, R in RUN.items():
        be = breakeven_bp(R.d["net"].sum(), R.d["notional"].sum())
        log(f"[COSTS]   {k[0]} open{k[1]} {k[2]}: {be:.2f} bp (Part C {partc[k][0]:.2f}; {partc[k][1]})  {'OK' if abs(be - partc[k][0]) < 0.006 else 'DIFFERS'}")
        assert abs(be - partc[k][0]) < 0.01, "break-even receipt differs from Part C"
    Rv = RUN[("vault", 10, "maker")]
    tsh = Rv.d.groupby("tier")["net"].sum() / Rv.d["net"].sum()
    log(f"[COSTS] RECEIPT tier share of zero-cost net, vault maker open10: least liquid {tsh.get(TIERS[0], 0):.1%} (Part C {tier_ref[0]:.1%}; {tier_ref[1]}), middle {tsh.get(TIERS[1], 0):.1%}, most liquid {tsh.get(TIERS[2], 0):.1%}")

    # ---- (a) volume vs depth (computed BEFORE the grid: its fitted line is the labelled alternative price of beyond-book legs, rules R3 / section 6a)
    log("[COSTS] (a) VOLUME vs DEPTH: legs vs the coin's traded notional in the entry minute, and the walk (curve above half-spread) on sqrt(leg / minute notional) for taker entry legs with an own-minute book")
    FIT = {}
    for side in ("vault", "test"):
        R = RUN[(side, 10, "taker")]
        xs, ys, tr = [], [], []
        shares = []
        for i in range(len(R.d)):
            for leg in (0, 1):
                coin = R.coins[leg][i]
                nt = bars.win(coin, "notional", int(R.t0m[i]), 1)[0]
                S = (R.la, R.lb)[leg][i]
                if np.isfinite(nt) and nt > 0:
                    shares.append(S / nt)
                j, src, _ = books.get(int(R.cids[leg][i]), int(R.t0m[i]))
                if j >= 0 and src == 0 and np.isfinite(nt) and nt > 0:
                    v, beyond = curve_bp(books.c, j, (R.dira, R.dirb)[leg][i] > 0, S, scale)
                    if not beyond:
                        xs.append(math.sqrt(S / nt))
                        ys.append(v - books.c["spread_bp"][j] / 2)
                        tr.append(tier[side].get(coin))
        xs, ys = np.array(xs), np.array(ys)
        sl, ic = np.polyfit(xs, ys, 1)
        r2 = float(np.corrcoef(xs, ys)[0, 1] ** 2)
        rho = float(pd.Series(xs).rank().corr(pd.Series(ys).rank()))
        sh = np.array(shares)
        log(f"[COSTS]   {side}: legs with a minute notional {len(sh):,}; leg / minute notional median {np.median(sh):.2f}, share of legs above 10% of the minute's notional {float((sh > 0.1).mean()):.1%}, above 100% {float((sh > 1).mean()):.1%}; "
            f"fit on {len(xs):,} legs with a book walk: walk_bp = {ic:.2f} + {sl:.2f} x sqrt(leg/notional), R^2 {r2:.3f}, rank correlation {rho:.3f}")
        for trn in TIERS:
            m = np.array([t_ == trn for t_ in tr])
            if m.sum() > 20:
                s2, i2 = np.polyfit(xs[m], ys[m], 1)
                log(f"[COSTS]      {trn}: n {int(m.sum()):,}, slope {s2:.2f}, R^2 {float(np.corrcoef(xs[m], ys[m])[0, 1] ** 2):.3f}, rank corr {float(pd.Series(xs[m]).rank().corr(pd.Series(ys[m]).rank())):.3f}")
        FIT[side] = dict(ic=float(ic), sl=float(sl))
        RES.setdefault("volume_fit", {})[side] = dict(slope=float(sl), intercept=float(ic), r2=r2, rho=rho, n=int(len(xs)), share_above_10pct=float((sh > 0.1).mean()))


    # windows for maker runs; evaluation grid
    t = time.time()
    for k, R in RUN.items():
        prep_windows(R)
    lap("prepare maker/exit fill windows (all 8 runs)", t)
    log("[COSTS] RECEIPT S1: share of first-fill bars (W = 5) in which the coin's traded notional is 0 or the bar is missing (a bar with no trades cannot fill an order; the rule is NOT changed), entry and exit windows, by run (= period) and rule")
    for k, R in RUN.items():
        if k[2] != "maker":
            continue
        for rule in RULES:
            z0 = nanb = tot_ = 0
            for key in (R.ent, R.ext):
                for (i, leg), e in key.items():
                    f = e[rule][0]
                    if f < 5:
                        tot_ += 1
                        v = e["ntw"][f]
                        z0 += bool(np.isfinite(v) and v == 0.0)
                        nanb += bool(not np.isfinite(v))
            log(f"[COSTS]   {k[0]} open{k[1]} {rule}: {tot_:,} first-fill bars; notional = 0 in {z0/max(tot_,1):.2%}, bar notional missing in {nanb/max(tot_,1):.2%}")
    grid = {}
    t = time.time()
    for k, R in RUN.items():
        cells = [(W, r, m) for W in WS for r in RULES for m in MULTS] if k[2] == "maker" else [(0, "taker", m) for m in MULTS]
        for (W, r, m) in cells:
            grid[(k, W, r, m)] = evaluate(R, W, r, m, scale)
        log(f"[COSTS] grid for {k[0]} open{k[1]} {k[2]}: {len(cells)} cells done")
    lap("evaluate the sensitivity grid (all runs)", t)
    RES["TIMES"] = TIMES

    def head_key(k):
        return (k, HEAD["W"], HEAD["rule"], HEAD["mult"]) if k[2] == "maker" else (k, 0, "taker", 1.0)

    # ---- per-config results table
    rows, RES["configs"] = [], {}
    for k, R in RUN.items():
        d = R.d
        hr = grid[head_key(k)]
        wdays = window_days(d)
        z = daily_metrics(d, d["net"].to_numpy(), wdays)
        h = daily_metrics(d, hr["net"].to_numpy(), wdays)
        nfill = int(hr["filled"].sum())
        cells = [x for x in grid if x[0] == k]
        pos = sum(float(grid[x]["net"].sum()) > 0 for x in cells)
        nets = [float(grid[x]["net"].sum()) for x in cells]
        be_zero = breakeven_bp(d["net"].sum(), d["notional"].sum())
        notional_f = float(d["notional"].to_numpy()[hr["filled"].to_numpy()].sum())
        be_model = breakeven_bp(hr["net"].sum(), notional_f)
        cost_per_fill = float((d["net"].sum() - hr["net"].sum()) / (2 * d["notional"].sum()) * 1e4)
        c = dict(n_saved=len(d), n_filled=nfill, miss_share=1 - nfill / len(d), zero=z, head=h, net_per_filled=h["net"] / max(nfill, 1), net_per_saved=h["net"] / len(d),
                 cells_pos=int(pos), cells_n=len(cells), cell_net_min=min(nets), cell_net_max=max(nets), be_zero=be_zero, be_model=be_model, cost_bp_per_fill_implied=cost_per_fill)
        RES["configs"][f"{k[0]} open{k[1]} {k[2]}"] = c
        rows.append((k, c))
        log(f"[COSTS] HEADLINE {k[0]} open{k[1]} {k[2]} ({'strict, W=5, multiplier 1' if k[2]=='maker' else 'taker, multiplier 1'}; {tag}): zero-cost net ${z['net']:,.2f} (PF {fmt(z['pf'])}, Sharpe {fmt(z['sharpe'])}, max drawdown ${z['mdd_usd']:,.2f} = {z['mdd_usd']/1000:.1%} of the $1,000 start) -> "
            f"with costs net ${h['net']:,.2f} (PF {fmt(h['pf'])}, Sharpe {fmt(h['sharpe'])}, max drawdown ${h['mdd_usd']:,.2f} = {h['mdd_usd']/1000:.1%} of the $1,000 start; equity = $1,000 + cumulative daily net with sizing held as saved, so it can go below zero and a drawdown above 100% of the start is possible); filled {nfill:,} of {len(d):,} ({nfill/len(d):.1%}); net per filled trade ${c['net_per_filled']:.3f}, per saved-set trade ${c['net_per_saved']:.3f}; "
            f"break-even extra slippage: zero-cost arithmetic {be_zero:.2f} bp, under this model {fmt(be_model)} bp; implied average cost {cost_per_fill:.2f} bp per fill; "
            f"net positive in {pos} of {len(cells)} sensitivity cells; cell net range ${min(nets):,.2f} to ${max(nets):,.2f}")

    # ---- sensitivity grid print
    for k, R in RUN.items():
        log(f"[COSTS] SENSITIVITY {k[0]} open{k[1]} {k[2]}: net $ by cell (zero-cost ${R.d['net'].sum():,.2f})")
        for x in sorted(a for a in grid if a[0] == k):
            r = grid[x]
            log(f"[COSTS]   W={x[1]:>2} {x[2]:>7} mult {x[3]}: net ${r['net'].sum():>10,.2f}, filled {r['filled'].mean():.1%}")

    # ---- ALTERNATIVE (labelled, planner ruling): beyond-book legs priced by the fitted volume line instead of the last stored level; never the headline
    log("[COSTS] ALTERNATIVE for beyond-book legs (rules section 6a, R3; planner ruling 2026-11-13): fitted line walk = intercept + slope x sqrt(leg / minute notional) of the same period, floored at the last-level price. Headline unchanged.")
    RES["alt_fit"] = {}
    for k, R in RUN.items():
        hk = head_key(k)
        alt = evaluate(R, hk[1], hk[2], hk[3], scale, FIT[k[0]])
        h0 = grid[hk]
        RES["alt_fit"][f"{k[0]} open{k[1]} {k[2]}"] = dict(net_headline=float(h0["net"].sum()), net_fit=float(alt["net"].sum()), n_beyond_trades=int(h0["beyond"].fillna(False).astype(bool).sum()))
        log(f"[COSTS]   {k[0]} open{k[1]} {k[2]}: trades with a beyond-book leg {int(h0['beyond'].fillna(False).astype(bool).sum()):,} of {int(h0['filled'].sum()):,} filled; headline net ${h0['net'].sum():,.2f} (last-level price) vs ALTERNATIVE (fitted line) ${alt['net'].sum():,.2f}")

    # ---- beyond-book rule: HEADLINE = remainder at the last stored level (section 1 wording, planner ruling 2026-11-14); section 8 as written (whole leg at the last level) printed beside it
    log("[COSTS] BEYOND-BOOK RULE (planner ruling 2026-11-14; resolves the inconsistency between rules sections 1 and 8): HEADLINE walks the stored levels at their prices and prices only the REMAINDER at the last stored level (an ESTIMATE (not a bound: in-book levels beyond the last curve point are priced too high, depth beyond the 20 levels too low)); "
        "section 8 as written prices the WHOLE leg at the last stored level and is printed beside it, together with the net without trades that have a beyond-book leg")
    RES["beyond_versions"] = {}
    for k, R in RUN.items():
        hk = head_key(k)
        BMODE[0] = "whole"
        whole = evaluate(R, hk[1], hk[2], hk[3], scale)
        BMODE[0] = "remainder"
        h0 = grid[hk]
        bmask = h0["beyond"].fillna(False).astype(bool).to_numpy() & h0["filled"].to_numpy()
        RES["beyond_versions"][f"{k[0]} open{k[1]} {k[2]}"] = dict(headline_remainder=float(h0["net"].sum()), section8_whole=float(whole["net"].sum()), without_beyond=float(h0["net"].to_numpy()[~bmask].sum()), n_beyond=int(bmask.sum()))
        log(f"[COSTS]   {k[0]} open{k[1]} {k[2]}: HEADLINE (remainder at last level) ${h0['net'].sum():,.2f}; section 8 as written (whole leg at last level) ${whole['net'].sum():,.2f}; without the {int(bmask.sum())} trades that have a beyond-book leg ${h0['net'].to_numpy()[~bmask].sum():,.2f} (zero-cost net of the same trades ${R.d['net'].to_numpy()[~bmask].sum():,.2f})")

    # ---- missing / proxy shares and removal lines
    log("[COSTS] BOOK SOURCES (headline cells, filled trades): EVERY book lookup a trade rests on counts: maker limits (entry, and exit for mu exits) and every taker / crossing fill. Source = own minute / adjacent minute (+-1, the +1 row is a book from after the fill) / no-book proxy, with the proxy's cause; by run (= period) and tier")
    for k, R in RUN.items():
        hr = grid[head_key(k)]
        f = hr[hr["filled"]]
        causes = Counter(c for s_ in f["proxy_causes"].fillna("") for c in s_.split(",") if c)
        nuse = int(f["n_uses"].sum())
        log(f"[COSTS]   {k[0]} open{k[1]} {k[2]}: lookups {nuse:,}: own minute {int(f['n_own'].sum()):,} ({f['n_own'].sum()/max(nuse,1):.1%}), adjacent minute {int(f['n_pm1'].sum()):,} ({f['n_pm1'].sum()/max(nuse,1):.1%}), proxy {int(f['n_proxy'].sum()):,} ({f['n_proxy'].sum()/max(nuse,1):.1%}) by cause {dict(causes)}; "
            f"trades touching a proxy lookup {(f['n_proxy'] > 0).mean():.1%}; trades on the 7 missing days {float(R.d['missing_day'].mean()):.1%}; trades with a beyond-book leg {f['beyond'].mean():.1%}; legs with a NaN/missing bar in a fill window {int(hr['nan_legs'].sum())}")
        for tr in TIERS:
            ff = f[R.d.loc[f.index, "tier"].to_numpy() == tr]
            nu = max(int(ff["n_uses"].sum()), 1)
            log(f"[COSTS]      tier {tr}: {len(ff):,} filled trades; lookups own {ff['n_own'].sum()/nu:.1%}, adjacent {ff['n_pm1'].sum()/nu:.1%}, proxy {ff['n_proxy'].sum()/nu:.1%}; trades touching a proxy lookup {fmt((ff['n_proxy'] > 0).mean() * 100 if len(ff) else float('nan'), 1)}%")
        for nm, mask in (("excluding trades that touch a proxy lookup", (hr["n_proxy"].fillna(0) == 0) | ~hr["filled"]), ("excluding trades with a beyond-book leg", ~hr["beyond"].fillna(False).astype(bool) | ~hr["filled"])):
            sel_saved = mask.to_numpy()
            dd = R.d[sel_saved]
            log(f"[COSTS]      {nm}: {int(sel_saved.sum()):,} of {len(R.d):,} saved trades kept; zero-cost net ${dd['net'].sum():,.2f} -> with costs ${hr['net'][sel_saved].sum():,.2f}")

    # ---- missed trades by cause and adverse selection
    log("[COSTS] MISSED TRADES and ADVERSE SELECTION (maker runs; headline W=5 and both rules)")
    for k, R in RUN.items():
        if k[2] != "maker":
            continue
        for rule in RULES:
            hr = grid[(k, 5, rule, 1.0)]
            causes = hr.loc[~hr["filled"], "missed"].value_counts().to_dict()
            fl = hr["filled"].to_numpy()
            line = f"[COSTS]   {k[0]} open{k[1]} {rule} W=5: filled {fl.mean():.1%}; missed {dict(causes)}; "
            for col, nm in (("reach_10h", "reach within 10 h"), ("minutes_to_mu", "minutes to mu (reached trades)"), ("gross_none", "saved gross (sigma, no stop)")):
                a, b = R.d.loc[fl, col].dropna(), R.d.loc[~fl, col].dropna()
                line += f"{nm}: filled {a.mean():.3f} (n {len(a)}, se {a.std()/math.sqrt(max(len(a),1)):.3f}) vs missed {b.mean() if len(b) else float('nan'):.3f} (n {len(b)}, se {b.std()/math.sqrt(max(len(b),1)) if len(b)>1 else float('nan'):.3f}); "
            log(line)
    log("[COSTS] LATE-FILL TRADES (maker runs, headline cell W=5 strict): net stays 0 in the headline (planner ruling). A late-fill trade is one whose later entry fill comes at or after the saved exit minute. "
        "COUNTING IT AS 0 FLATTERS THE MAKER SIDE: if a leg had already filled at its limit before the exit minute, a real unwind costs money. LABELLED ARITHMETIC BOUND (does not change the headline): "
        "sum over those trades of each already-filled leg's taker unwind at the exit-minute book as this model prices it (curve + 0.045% fee) plus the maker fee already paid on its entry; price drift of the unhedged leg is not included.")
    RES["late_fill"] = {}
    for k, R in RUN.items():
        if k[2] != "maker":
            continue
        hr = grid[head_key(k)]
        lf = hr[hr["missed"] == "late_fill"]
        withleg = lf[lf["late_legs"].fillna(0) > 0]
        bound = float(withleg["late_unwind"].sum())
        net_h = float(hr["net"].sum())
        RES["late_fill"][f"{k[0]} open{k[1]}"] = dict(n=int(len(lf)), n_with_filled_leg=int(len(withleg)), bound=bound, net_headline=net_h)
        log(f"[COSTS]   {k[0]} open{k[1]} maker: late-fill trades {len(lf):,} of {len(R.d):,} ({len(lf)/len(R.d):.1%}); with at least one leg already filled before the exit minute {len(withleg):,}; arithmetic bound on the unwind cost ${bound:,.2f}; "
            f"headline net ${net_h:,.2f} -> ${net_h - bound:,.2f} with the bound applied (labelled, not the headline)")
    # fill rates by tier and period
    log("[COSTS] FILL RATES (leg level, entry, headline W=5, by rule and tier)")
    for k, R in RUN.items():
        if k[2] != "maker":
            continue
        for rule in RULES:
            tot = {tr: [0, 0] for tr in TIERS}
            allc = [0, 0]
            for i in range(len(R.d)):
                for leg in (0, 1):
                    e = R.ent[(i, leg)]
                    f, nanp = e[rule]
                    ok = f < 5
                    tr = tier[k[0]].get(R.coins[leg][i])
                    allc[0] += ok
                    allc[1] += 1
                    if tr:
                        tot[tr][0] += ok
                        tot[tr][1] += 1
            log(f"[COSTS]   {k[0]} open{k[1]} {rule}: legs filled within 5 min {allc[0]/allc[1]:.1%} overall; " + "; ".join(f"{tr} {v[0]/max(v[1],1):.1%}" for tr, v in tot.items()))

    # ---- two-leg risk
    log("[COSTS] TWO-LEG RISK (headline maker cells, filled trades where the legs fill in different minutes): gap and the earlier leg's position-signed move to the later fill (bp)")
    for k, R in RUN.items():
        if k[2] != "maker":
            continue
        hr = grid[head_key(k)]
        f = hr[hr["filled"]]
        g = f[f["gap"] > 0]
        mv = g["move_bp"].dropna()
        log(f"[COSTS]   {k[0]} open{k[1]}: {len(g):,} of {len(f):,} filled trades ({len(g)/max(len(f),1):.1%}) have a gap; gap minutes mean {g['gap'].mean():.2f}, p50 {g['gap'].median():.0f}, p90 {g['gap'].quantile(0.9):.0f}; "
            f"move bp mean {mv.mean():.2f}, p50 {mv.median():.2f}, p90 {mv.quantile(0.9):.2f}, worst {mv.min():.2f}")

    # ---- decomposition of costs and (ref - mid) check
    log("[COSTS] DECOMPOSITION (headline cells): mean cost bp per filled trade leg-fill, entry and exit; and the (ref - mid) check, position-signed, on own-minute entry rows, by tier")
    for k, R in RUN.items():
        hr = grid[head_key(k)]
        f = hr[hr["filled"]]
        log(f"[COSTS]   {k[0]} open{k[1]} {k[2]}: mean entry cost (two legs summed) {f['cost_in'].mean():.2f} bp, mean exit cost {f['cost_x'].mean():.2f} bp; mean gains vs reference: entry ${f['gain_in'].mean():.4f}, exit ${f['gain_x'].mean():.4f}; "
            f"fees entry ${f['fee_in'].mean():.4f}, exit ${f['fee_x'].mean():.4f} per trade")
        if k[2] == "taker":
            res = defaultdict(list)
            for i in range(len(R.d)):
                for leg in (0, 1):
                    j, src, _ = books.get(int(R.cids[leg][i]), int(R.t0m[i]))
                    if src == 0:
                        dirn = (R.dira, R.dirb)[leg][i]
                        res[R.d["tier"].iloc[i]].append(dirn * (books.c["mid"][j] - R.refin[i, leg]) / R.refin[i, leg] * 1e4)
            log("[COSTS]      (mid - ref) signed to position at own-minute entry rows, bp: " + "; ".join(f"{tr}: mean {np.mean(v):.2f}, se {np.std(v)/math.sqrt(len(v)):.2f}, n {len(v):,}" for tr, v in res.items() if v))

    # ---- OUTLIERS (checker A): trades whose summed leg cost is above 200 bp, headline cells; the only source for any figure quoted about them
    log("[COSTS] OUTLIERS (headline cells, filled trades): trades with entry cost + exit cost (two legs each, bp) above 200; net of those and of the rest; how many are beyond-book; the 5 worst trades; trades whose loss exceeds their own notional")
    RES["outliers"] = {}
    for k, R in RUN.items():
        hr = grid[head_key(k)]
        f = hr[hr["filled"]].copy()
        f["pair"] = (R.d["ticker_a"] + "-" + R.d["ticker_b"]).reindex(f.index)
        f["notional"] = R.d["notional"].reindex(f.index)
        f["big_leg"] = R.d["big_leg"].reindex(f.index)
        f["t0s"] = R.d["t0"].reindex(f.index).dt.strftime("%Y-%m-%d")
        f["cost_sum"] = f["cost_in"] + f["cost_x"]
        big = f["cost_sum"] > 200
        beyond = f["beyond"].fillna(False).astype(bool)
        loss_gt = f["net"] < -f["notional"]
        worst = f.sort_values("net").head(5)
        tot = float(hr["net"].sum())
        RES["outliers"][f"{k[0]} open{k[1]} {k[2]}"] = dict(n_big=int(big.sum()), net_big=float(f.loc[big, "net"].sum()), n_rest=int((~big).sum()), net_rest=float(f.loc[~big, "net"].sum()), n_big_beyond=int((big & beyond).sum()), n_loss_gt_notional=int(loss_gt.sum()))
        log(f"[COSTS]   {k[0]} open{k[1]} {k[2]}: {int(big.sum()):,} of {len(f):,} filled trades above 200 bp, net ${f.loc[big, 'net'].sum():,.2f}; the other {int((~big).sum()):,} net ${f.loc[~big, 'net'].sum():,.2f}; beyond-book among the big ones {int((big & beyond).sum())}; "
            f"all trades with a beyond-book leg {int(beyond.sum())}, net ${f.loc[beyond, 'net'].sum():,.2f}, net without them ${f.loc[~beyond, 'net'].sum():,.2f}; trades with a loss larger than their own notional {int(loss_gt.sum())}")
        log("[COSTS]      5 worst: " + "; ".join(f"{r.pair} {r.t0s} net ${r.net:,.2f} ({r.net / tot:.1%} of run net), notional ${r.notional:,.0f}, larger leg ${r.big_leg:,.0f}, entry cost {r.cost_in:,.0f} bp, exit cost {r.cost_x:,.0f} bp, beyond-book {bool(r.beyond)}" for r in worst.itertuples()))

    # ---- by tier, leg size, coin, pair, leverage (headline)
    def group_table(k, R, hr, col, name, series=None):
        s = series if series is not None else R.d[col]
        out = []
        for gname, ii in s.groupby(s, observed=True).indices.items():
            zero = float(R.d["net"].to_numpy()[ii].sum())
            new = float(hr["net"].to_numpy()[ii].sum())
            out.append((gname, len(ii), int(hr["filled"].to_numpy()[ii].sum()), zero, new))
        return out

    RES["groups"] = {}
    log("[COSTS] GROUPS (headline cells): rows = group, saved trades, filled trades, zero-cost net $, net with costs $, share of run net with costs")
    for k, R in RUN.items():
        hr = grid[head_key(k)]
        tot_new = float(hr["net"].sum())
        for col, nm in (("tier", "liquidity tier"), ("leg_bucket", "larger-leg size"), ("leverage", "leverage")):
            tab = group_table(k, R, hr, col, nm)
            RES["groups"][f"{k[0]} open{k[1]} {k[2]} | {nm}"] = [list(map(lambda v: v if not isinstance(v, (np.floating, np.integer)) else float(v), r)) for r in tab]
            log(f"[COSTS]   {k[0]} open{k[1]} {k[2]} by {nm}: " + "; ".join(f"{g}: n {n:,}, filled {nf:,}, zero ${z:,.2f}, costed ${w:,.2f} ({w/tot_new:.1%})" for g, n, nf, z, w in sorted(tab, key=lambda r: str(r[0]))))
        # by coin (a trade counts for both legs) and by pair
        cs = defaultdict(lambda: [0, 0, 0.0, 0.0])
        for i in range(len(R.d)):
            for leg in (0, 1):
                c = R.coins[leg][i]
                cs[c][0] += 1
                cs[c][1] += bool(hr["filled"].iloc[i])
                cs[c][2] += R.d["net"].iloc[i]
                cs[c][3] += hr["net"].iloc[i]
        ct = pd.DataFrame(cs, index=["n", "filled", "zero", "costed"]).T.sort_values("costed", ascending=False)
        pt = pd.DataFrame(dict(pair=R.d["ticker_a"] + "-" + R.d["ticker_b"], zero=R.d["net"], costed=hr["net"].to_numpy(), filled=hr["filled"].to_numpy())).groupby("pair").agg(n=("zero", "size"), filled=("filled", "sum"), zero=("zero", "sum"), costed=("costed", "sum")).sort_values("costed", ascending=False)
        RES["groups"][f"{k[0]} open{k[1]} {k[2]} | coin"] = ct.reset_index().values.tolist()
        RES["groups"][f"{k[0]} open{k[1]} {k[2]} | pair"] = pt.reset_index().values.tolist()
        log(f"[COSTS]   {k[0]} open{k[1]} {k[2]} by coin: {len(ct)} coins, {int((ct['costed'] > 0).sum())} with net > 0 after costs (zero-cost: {int((ct['zero'] > 0).sum())}); best 5 {', '.join(f'{c} ${v:,.2f}' for c, v in ct['costed'].head(5).items())}; worst 5 {', '.join(f'{c} ${v:,.2f}' for c, v in ct['costed'].tail(5).items())}")
        log(f"[COSTS]   {k[0]} open{k[1]} {k[2]} by pair: {len(pt)} pairs, {int((pt['costed'] > 0).sum())} with net > 0 after costs (zero-cost: {int((pt['zero'] > 0).sum())}); best 5 {', '.join(f'{c} ${v:,.2f}' for c, v in pt['costed'].head(5).items())}; worst 5 {', '.join(f'{c} ${v:,.2f}' for c, v in pt['costed'].tail(5).items())}")
        sh = R.d.groupby("leverage").size() / len(R.d)
        log(f"[COSTS]   {k[0]} open{k[1]} {k[2]} leverage shares: " + ", ".join(f"{int(a)}x {b:.1%}" for a, b in sh.items()))

    # ---- maker-exit-fee finding
    log("[COSTS] MAKER-EXIT FEE FINDING: saved maker runs charged the maker fee on every non-liquidation exit; stops and timeouts cannot rest as a limit order. Effect = exit leg USD x (0.045% - 0.015%) on exits with reason stop or timeout; nothing else changed; no run edited.")
    RES["maker_exit_fee"] = {}
    for k, R in RUN.items():
        if k[2] != "maker":
            continue
        m = R.d["exit_reason"].isin(["stop", "timeout"]).to_numpy()
        extra = float(((R.lax + R.lbx) * (FEE_T - FEE_M))[m].sum())
        net0 = float(R.d["net"].sum())
        be0, be1 = breakeven_bp(net0, R.d["notional"].sum()), breakeven_bp(net0 - extra, R.d["notional"].sum())
        RES["maker_exit_fee"][f"{k[0]} open{k[1]}"] = dict(n=int(m.sum()), extra=extra, net=net0, pct=extra / net0 if net0 else float("nan"), be0=be0, be1=be1)
        log(f"[COSTS]   {k[0]} open{k[1]} maker: {int(m.sum()):,} of {len(R.d):,} exits are stop/timeout; extra fee ${extra:,.2f}; saved net ${net0:,.2f} -> ${net0 - extra:,.2f} ({extra/net0:.1%} of the net); break-even {be0:.2f} -> {be1:.2f} bp")

    # ---- verdict (vault, four priority configurations)
    vk = [("vault", 10, "maker"), ("vault", 20, "maker"), ("vault", 10, "taker"), ("vault", 20, "taker")]

    def verdict_of(removal):
        out = {}
        for k in vk:
            cells = [x for x in grid if x[0] == k]

            def net_of(x):
                r = grid[x]
                if not removal:
                    return float(r["net"].sum())
                keep = ((r["n_proxy"].fillna(0) == 0) | ~r["filled"]).to_numpy()
                return float(r["net"].to_numpy()[keep].sum())
            nets = {x: net_of(x) for x in cells}
            out[f"{k[1]} {k[2]}"] = dict(head=nets[head_key(k)], cells_pos=sum(v > 0 for v in nets.values()), cells_n=len(cells))
        allpos = all(h["head"] > 0 for h in out.values())
        cells_ok = all(h["cells_pos"] >= math.ceil(0.75 * h["cells_n"]) for h in out.values())
        nonepos = not any(h["head"] > 0 for h in out.values())
        return out, allpos, cells_ok, nonepos, ("a" if (allpos and cells_ok) else ("c" if nonepos else "b"))

    heads_, allpos, cells_ok, nonepos, letter = verdict_of(False)
    RES["verdict"] = dict(letter=letter, tag=tag, allpos=allpos, cells_ok=cells_ok, nets={n: h["head"] for n, h in heads_.items()}, cells={n: [h["cells_pos"], h["cells_n"]] for n, h in heads_.items()})
    log(f"[COSTS] VERDICT LETTER ({tag}; vault, four priority configs): all four headline nets > 0: {allpos}; at least 75% of cells > 0 in each: {cells_ok}; none > 0: {nonepos}  ->  ({letter}). "
        + "; ".join(f"{n}: net ${h['head']:,.2f}, positive in {h['cells_pos']} of {h['cells_n']} cells" for n, h in heads_.items()))
    hr_, a2, c2, n2, letter_r = verdict_of(True)
    RES["verdict_removed"] = dict(letter=letter_r, nets={n: h["head"] for n, h in hr_.items()}, cells={n: [h["cells_pos"], h["cells_n"]] for n, h in hr_.items()})
    log(f"[COSTS] LABELLED LINE next to the letter, it does not replace it: SAME RULE with every trade that touches a no-book proxy lookup removed (per cell): all four headline nets > 0: {a2}; at least 75% of cells > 0 in each: {c2}; none > 0: {n2}  ->  ({letter_r}). "
        + "; ".join(f"{n}: net ${h['head']:,.2f}, positive in {h['cells_pos']} of {h['cells_n']} cells" for n, h in hr_.items()))
    if letter == "b":
        pos = []
        for k in vk:
            for key in (f"{k[0]} open{k[1]} {k[2]} | liquidity tier", f"{k[0]} open{k[1]} {k[2]} | larger-leg size"):
                for r in RES["groups"][key]:
                    if r[4] > 0:
                        pos.append(f"{k[1]} {k[2]} | {key.split('| ')[1]} {r[0]}: n {r[1]}, net ${r[4]:,.2f}")
            ct = RES["groups"][f"{k[0]} open{k[1]} {k[2]} | coin"]
            pos.append(f"{k[1]} {k[2]} | coins with net > 0: {sum(1 for r in ct if r[4] > 0)} of {len(ct)}")
        log("[COSTS] (b) groups with net > 0 under costs (listed, none chosen): " + " | ".join(pos))
    # answer sentences (R1)
    for k, R in RUN.items():
        c = RES["configs"][f"{k[0]} open{k[1]} {k[2]}"]
        log(f"[COSTS] ANSWER {k[0]} open{k[1]} {k[2]}: net positive in {c['cells_pos']} of {c['cells_n']} sensitivity cells; headline net ${c['head']['net']:,.2f}")
    # saved per-trade headline results for the report script
    for k, R in RUN.items():
        hr = grid[head_key(k)].copy()
        out = R.d[["event_id", "ticker_a", "ticker_b", "t0", "exit_time", "exit_reason", "notional", "leverage", "net", "tier", "big_leg", "missing_day"]].copy()
        out = pd.concat([out, hr.drop(columns=["missed"]).add_prefix("c_").reset_index(drop=True), hr[["missed"]].reset_index(drop=True)], axis=1)
        out["leg_bucket"] = R.d["leg_bucket"].astype(str).to_numpy()
        out.to_parquet(f"{C1}costs_headline_{tag}_{k[0]}_open{k[1]}_{k[2]}.parquet", index=False)
    json.dump({kk: vv for kk, vv in RES.items()}, open(f"{C1}costs_analysis_{tag}.json", "w"), indent=1, default=lambda o: float(o) if isinstance(o, (np.floating, np.integer)) else str(o))
    log(f"[COSTS] wrote {C1}costs_analysis_{tag}.json and the per-trade headline parquets; proxy fallbacks (ctxs row missing) used {books.proxy_fallback:,} times")
    log(f"[COSTS] total run time {time.time() - T0:.0f}s; timings {TIMES}")


if __name__ == "__main__":
    main()
