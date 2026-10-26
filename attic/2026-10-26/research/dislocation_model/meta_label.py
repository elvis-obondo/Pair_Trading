"""META-LABEL Step 0: can a skip / half-size rule be tested on stored trades?

    .venv/bin/python research/dislocation_model/meta_label.py 2>&1 \
        | tee research/dislocation_model/logs/meta_label_step0.log

THE LEDGER (user's choice, Option 1): research/exit_study/grid_run/grid_w2_s050.csv
-- 2-day window, 0.5-sigma stop, 10 slots, 35 days to 2026-09-21. The three
6-month ledgers behind the 12,597-trade figure no longer exist (META-LABEL,
NUMBERS.md).

STEP 0 CHECKS, each reported; the brief says stop if any fails:
  A. Generated after the one-bar entry fix (c287477)? The fix's own invariants
     are re-checked on the trades: no more than 10 open at any instant, no pair
     open twice at once, and hours_held able to read 0 (the bug floored it at
     0.5). Fails -> stop.
  B. Liquidation: did this ledger's engine apply it? From the code history, not
     from the file: liquidation entered the engine in 440d658, after this
     ledger was written. Reported, not a stop.
  C. Match trades to episodes: same pair (order-free), closest episode entry.
     A ledger opened_at is the entry bar's CLOSE (post-fix); an episode's
     entry_time is the entry bar's OPEN label. So the SAME decision bar shows as
     an offset of exactly -1 bar (episode label = opened_at - 30 min). MATCHED =
     that exact bar. Anything else is a different dislocation, whose features
     are not this trade's features. Offsets are reported in full.
  D. Leakage buckets: clean >= 2026-07-18, validation 2026-05-01..07-17,
     contaminated < 2026-05-01. Fewer than 500 clean matched -> stop.
  E. Slot contention: the share of 30-minute bars with all 10 slots full. The
     ledger records only TAKEN trades, so candidates turned away for full slots
     or the one-per-ticker rule cannot be counted from it; said so, not guessed.
  F. (added by the user) The tail classifier's AUC on its TRAINING episodes
     against held-out, per horizon -- how much it overfits.

The flag-share comparison and Step 1 need matched trades and run only if C/D
pass.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

import paths
from envelope import HLABEL, HORIZONS
from tail_classifier import LOGIT_PUBLISHED, logit_model, setup

LEDGER = os.path.join(paths.RESEARCH, "exit_study", "grid_run", "grid_w2_s050.csv")
CLEAN = pd.Timestamp("2026-07-18")
VAL0 = pd.Timestamp("2026-05-01")
MIN_CLEAN = 500


def main():
    t0 = time.time()
    L = pd.read_csv(LEDGER, low_memory=False)
    L["t_open"] = pd.to_datetime(L.opened_at)
    L["t_close"] = pd.to_datetime(L.closed_at)
    print("=" * 112)
    print("META-LABEL STEP 0 -- can the skip rule be tested on stored trades?")
    print("=" * 112)
    print(f"  ledger: {os.path.relpath(LEDGER, paths.RESEARCH)}  {len(L):,} trades, "
          f"{L.t_open.min()} -> {L.t_open.max()}")
    cfg = {c: L[c].iloc[0] for c in L.columns if c.startswith("cfg_")}
    print("  stamps: " + ", ".join(f"{k[4:]}={v}" for k, v in cfg.items()))
    print()

    # ---- A. the entry fix ----
    print("A. GENERATED AFTER THE ONE-BAR ENTRY FIX?")
    ev = sorted([(t, 1) for t in L.t_open] + [(t, -1) for t in L.t_close],
                key=lambda x: (x[0], x[1]))       # closes before opens at a tie
    cur = mx = 0
    for _, s in ev:
        cur += s
        mx = max(mx, cur)
    key = [tuple(sorted(x)) for x in zip(L.ticker_a, L.ticker_b)]
    L["key"] = key
    dup = 0
    for _, g in L.sort_values("t_open").groupby("key"):
        o, c = g.t_open.to_numpy(), g.t_close.to_numpy()
        dup += int((o[1:] < c[:-1]).sum())
    hmin = float(L.hours_held.min())
    print(f"   max concurrent open {mx} (cap {cfg['cfg_slots']}); pair open twice at once "
          f"{dup}; min hours_held {hmin:.2f} (the bug floored it at 0.50)")
    print("   file written 2026-09-27 19:52, the fix committed 19:50; carries the cfg_*")
    print("   stamp columns that same fix introduced")
    if mx > cfg["cfg_slots"] or dup > 0 or hmin >= 0.5:
        raise SystemExit("[META] STOP -- the ledger fails the entry-fix invariants.")
    print("   -> PASS: post-fix")
    print()

    # ---- B. liquidation ----
    print("B. DID THIS LEDGER'S ENGINE APPLY LIQUIDATION?")
    print("   NO. Liquidation entered run_portfolio_backtest in commit 440d658 (2026-09-27")
    print("   21:27), after this ledger was written; that commit says the grid_run ledgers")
    print("   'predate all of the above' and booked stops at a 1.005x fill, not the measured")
    print("   1.04x. Any damage measured on these trades is a FLOOR.")
    print()

    # ---- C. matching ----
    print("C. MATCH TRADES TO EPISODES (same pair, closest entry)")
    M = pd.read_parquet(paths.META)
    M["t"] = pd.to_datetime(M.entry_time)
    M["key"] = [tuple(sorted(x)) for x in zip(M.ticker_a, M.ticker_b)]
    groups = {k: g for k, g in M.groupby("key")}
    off = np.full(len(L), np.nan)
    eid = np.full(len(L), -1)
    for i, (k, t) in enumerate(zip(L.key, L.t_open)):
        g = groups.get(k)
        if g is None:
            continue
        d = (g.t - t).dt.total_seconds().to_numpy() / 1800.0
        j = int(np.argmin(np.abs(d + 1.0)))           # nearest to the exact bar (-1)
        off[i], eid[i] = d[j], g.index[j]
    no_pair = int(np.isnan(off).sum())
    exact = off == -1.0
    print(f"   trades on a pair with NO episode in disloc_meta: {no_pair:,} of {len(L):,} "
          f"(the set samples {M.key.nunique():,} pairs, <=20 episodes each)")
    a = np.abs(off[~np.isnan(off)] + 1.0)
    print(f"   distance from the exact decision bar, trades on a sampled pair "
          f"({int((~np.isnan(off)).sum()):,}):")
    for b in (0, 1, 2, 4, 48, 336):
        print(f"     within {b:>3} bars: {int((a <= b).sum()):>5}")
    vc = pd.Series(off[~np.isnan(off)]).round(0).value_counts().sort_index()
    print("   raw offset (episode label - opened_at, bars), -4..+4: "
          + ", ".join(f"{int(k)}:{int(v)}" for k, v in vc.loc[-4:4].items()))
    print(f"   MATCHED (exact decision bar): {int(exact.sum()):,} of {len(L):,} "
          f"= {100*exact.mean():.1f}%;  unmatched, excluded: {int((~exact).sum()):,}")
    print()

    # ---- D. buckets ----
    print("D. LEAKAGE BUCKETS, matched trades")
    tm = L.t_open[exact]
    clean = int((tm >= CLEAN).sum())
    val = int(((tm >= VAL0) & (tm < CLEAN)).sum())
    cont = int((tm < VAL0).sum())
    print(f"   clean (>= 2026-07-18) {clean:,};  validation {val:,};  contaminated {cont:,}")
    print(f"   all {len(L):,} trades fall in the clean window: "
          f"{bool((L.t_open >= CLEAN).all())}")
    print()

    # ---- E. slot contention ----
    print("E. SLOT CONTENTION")
    grid = pd.date_range(L.t_open.min().floor("30min"), L.t_close.max().ceil("30min"),
                         freq="30min")
    o = np.searchsorted(np.sort(L.t_open.to_numpy()), grid.to_numpy(), side="right")
    c = np.searchsorted(np.sort(L.t_close.to_numpy()), grid.to_numpy(), side="right")
    n_open = o - c
    full = n_open >= cfg["cfg_slots"]
    print(f"   30-minute bars in span {len(grid):,}; all {cfg['cfg_slots']} slots full on "
          f"{int(full.sum()):,} = {100*full.mean():.1f}%;  median open {np.median(n_open):.0f}")
    print("   candidates turned away (full slots / one-per-ticker): NOT IN THIS LEDGER. It")
    print("   records taken trades only, so the turned-away count, and how many the")
    print("   classifier would have approved, cannot be measured from it.")
    print()

    # ---- F. classifier overfit ----
    print("F. TAIL CLASSIFIER, AUC on its training episodes vs held out")
    S = setup(t0, "  (classifier setup: same population, split and labels as TAIL-CLASSIFIER)")
    X, sp, labels = S["X"], S["sp"], S["labels"]
    for k in HORIZONS:
        m, mu, sd = logit_model(X, labels[k], sp)
        sc = m.decision_function((X - mu) / sd)
        a_tr = roc_auc_score(labels[k][sp.train], sc[sp.train])
        a_te = roc_auc_score(labels[k][sp.test], sc[sp.test])
        if round(a_te, 4) != LOGIT_PUBLISHED[k]:
            raise SystemExit("[META] classifier does not reproduce TAIL-CLASSIFIER.")
        print(f"   {HLABEL[k]:<5} train {a_tr:.4f}   held out {a_te:.4f}   "
              f"train - held out {a_tr - a_te:+.4f}")
    mh = float(L.hours_held.median())
    hz = min(HORIZONS, key=lambda k: abs(k * 0.5 - mh))
    print(f"   median hold in this ledger {mh:.2f}h -> nearest horizon {HLABEL[hz]}")
    print()

    print("=" * 112)
    print("STEP 0 VERDICT")
    print("=" * 112)
    if clean < MIN_CLEAN:
        print(f"  STOP. {clean} clean matched trades, fewer than {MIN_CLEAN}. The episode set")
        print(f"  samples pairs, so {no_pair:,} of {len(L):,} trades have no episode to match.")
        print("  Step 1 is not run. Nothing in the registry or live system was touched.")
    else:
        print("  Step 0 passes; Step 1 is the next stage (not in this script yet).")
    print(f"  [{time.time()-t0:.0f}s]")
    print("=" * 112)


# ------------------------------------------------------------ Step 0b + Step 1
FIT_BARS = 336          # mkdisloc's window: bars [i-335, i]
FLAG_SHARE = 0.20       # TAIL-REFINE: top 20% by classifier score, cut-off on train
K_HOLD = 1              # 0.5h -- the median hold in this ledger is 0.50h
N_NULL = 1000
N_BOOT = 1000


def entry_bar_features(L):
    """The tail classifier's six features for every trade, at its own entry bar.

    No new feature logic. Geometry exactly as mkdisloc builds an episode:
    rolling_spread_stats over the pair's joint finite panel region, read at the
    entry bar; the 336-bar sigma-unit window from that frozen geometry, stored
    as float32 the way disloc.npz stores it. Then envfeat.build (vol_48,
    vratio, vol_slope, sandwich, off_mark) and vol1m.trailing_features
    (vol_48_1m) on those inputs -- the same code that built the training rows.

    ENTRY BAR. A post-fix ledger's opened_at is the entry bar's CLOSE; the bar's
    label is opened_at - 30 min. Every input stops at that bar (envfeat audits
    max index touched; trailing_features asserts +29 minutes, the bar's close).

    Returns (F (n, 6) in tail_classifier.FEATURES order, cause per trade with
    "" for complete, M_like, W, audit).
    """
    import universe_panel
    import rolling_spread as rs
    import envfeat
    from envelope import RAW_BAR_DIR
    from vol1m import trailing_features
    from tail_classifier import FEATURES

    panel = universe_panel.drop_forming_bars(universe_panel.load_panel())
    pidx = pd.to_datetime(panel.index)
    cols = list(panel.columns)
    ixc = {c: k for k, c in enumerate(cols)}
    V = panel.to_numpy(float)
    ok = np.isfinite(V)
    first = ok.argmax(axis=0)
    n = len(L)
    cause = np.array([""] * n, dtype=object)
    lab = L.t_open - pd.Timedelta(minutes=30)
    J = pidx.get_indexer(lab)
    geo = np.full((n, 5), np.nan)            # beta, alpha, mu, sigma, z
    W = np.full((n, FIT_BARS), np.nan, np.float32)
    cause[J < 0] = "entry bar not in panel"
    for (a, b), g in L.groupby(["ticker_a", "ticker_b"]).groups.items():
        g = np.asarray(g)
        if a not in ixc or b not in ixc:
            cause[g] = "ticker not in panel"
            continue
        ja, jb = ixc[a], ixc[b]
        f = max(first[ja], first[jb])
        st = rs.rolling_spread_stats(V[f:, ja], V[f:, jb], 0.5)
        for r in g:
            if cause[r]:
                continue
            i = J[r] - f
            if i < FIT_BARS - 1:
                cause[r] = "under 336 bars of history"
                continue
            be, al, mu, sg, zz = (st.beta[i], st.alpha[i], st.mu[i], st.sigma[i], st.z[i])
            if not (np.isfinite([be, al, mu, sg, zz]).all() and sg > 0):
                cause[r] = "geometry not finite"
                continue
            lo = i - FIT_BARS + 1
            w = (V[f + lo:f + i + 1, ja] - be * V[f + lo:f + i + 1, jb] - al - mu) / sg
            if not np.isfinite(w).all():
                cause[r] = "window not finite"
                continue
            geo[r] = (be, al, mu, sg, zz)
            W[r] = w.astype(np.float32)
    good = cause == ""
    M_like = pd.DataFrame(dict(
        ticker_a=L.ticker_a.to_numpy(), ticker_b=L.ticker_b.to_numpy(),
        entry_time=lab.to_numpy(), bar_index=np.where(J < 0, 0, J),
        beta=geo[:, 0], alpha=geo[:, 1], mu=geo[:, 2], sigma=geo[:, 3],
        z_at_entry=geo[:, 4]))
    F = np.full((n, len(FEATURES)), np.nan)
    gi = np.flatnonzero(good)
    X5, names, audit = envfeat.build(verbose=False, W=W[gi], M=M_like.iloc[gi].reset_index(drop=True))
    if int((audit["touch"] > audit["entry"]).sum()) != 0:
        raise SystemExit("[META] envfeat read past the entry bar.")
    for j, nm in enumerate(names):
        F[gi, FEATURES.index(nm)] = X5[:, j].astype(np.float64)
    bad5 = ~np.isfinite(F[gi][:, [FEATURES.index(nm) for nm in names]]).all(1)
    cause[gi[bad5]] = "a window/sandwich/off_mark input missing"
    # 1-minute volatility: only trades whose two legs have a 1m file
    has1m = np.array([os.path.exists(os.path.join(RAW_BAR_DIR, f"{t}_USDT_USDT-1m-futures.feather"))
                      for t in cols])
    h = {c: has1m[k] for c, k in ixc.items()}
    g2 = np.array([r for r in np.flatnonzero(cause == "")
                   if h[L.ticker_a.iloc[r]] and h[L.ticker_b.iloc[r]]], int)
    cause[np.setdiff1d(np.flatnonzero(cause == ""), g2)] = "no 1-minute file for a leg"
    R = trailing_features(M_like, g2, W.astype(np.float64), F[g2, FEATURES.index("vol_48")])
    if R["max_off"] != 29 or not R["rep_ratio"] < 1.0:
        raise SystemExit(f"[META] 1m path check failed: max_off {R['max_off']}, "
                         f"reproduction {R['rep_ratio']:.3f} of budget.")
    F[g2, FEATURES.index("vol_48_1m")] = R["vol"]
    cause[g2[~np.isfinite(R["vol"])]] = "no valid 1-minute steps"
    audit.update(rep_ratio=R["rep_ratio"], max_off_1m=R["max_off"], recomp=R["recomp"],
                 n_envfeat=len(gi), nmiss_1m=R["nmiss"])
    return F, cause, M_like, W, audit


def boot_days(day, n=N_BOOT, seed=5):
    du = np.unique(day)
    pos = {d: np.flatnonzero(day == d) for d in du}
    rb = np.random.default_rng(seed)
    return [np.concatenate([pos[d] for d in rb.choice(du, len(du), replace=True)])
            for _ in range(n)]


def arm_stats(r, w, keep):
    """mean R per trade taken, total R, trades taken, win rate; w = size multiplier."""
    rr = (r * w)[keep]
    return np.array([rr.mean(), rr.sum(), keep.sum(), (rr > 0).mean()])


def step1():
    """Step 0b (features at every trade's entry bar) and Step 1 (the arms).

    STEP 0b CHECK: on the trades matched to an episode at their exact decision
    bar, the six features must equal the episode's -- the five envfeat columns
    bit-for-bit in float32 (both come from float32 windows through the same
    code) and vol_48_1m to 1e-12 (both float64 from the same 1-minute path).
    Any difference: stop. Fewer than 500 complete trades: stop.

    STEP 1, all complete trades (all in the clean window). The 0.5h classifier
    (median hold 0.50h), refitted deterministically and required to reproduce
    TAIL-CLASSIFIER's 0.7150. Flag = score above the 80th percentile of its
    TRAIN scores (TAIL-REFINE; never tuned on trades).
      ALL   every trade at 1x
      SKIP  flagged trades dropped; freed slots not backfilled
      HALF  flagged trades at 0.5x
    Paired differences against ALL with day-clustered intervals (trade entry
    day, 1,000 resamples). Random null, 1,000 draws: SKIP drops, and HALF
    halves, the SAME NUMBER of trades chosen at random.

    THE READING RULE, fixed in the brief: an arm that does not beat the random
    null on TOTAL R (real total above the null's 95th percentile) is shelved.
    One that beats it is reported and stops there; the full backtest is a
    separate decision. Slots are full 86.5% of the time, so this can rule the
    rule OUT, never in.
    """
    from tail_classifier import FEATURES, LOGIT_PUBLISHED, logit_model, setup
    t0 = time.time()
    L = pd.read_csv(LEDGER, low_memory=False)
    L["t_open"] = pd.to_datetime(L.opened_at)
    print("=" * 112)
    print("META-LABEL STEP 0b + STEP 1 -- skip / half-size flagged trades, grid_w2_s050.csv")
    print("=" * 112)
    print("  STATED BEFORE ANY NUMBER:")
    print("  - all 10 slots are full 86.5% of the time: this can rule the rule OUT, never IN")
    print("  - stops are booked at 1.005x, so the stop-overshoot leak is NOT in this ledger")
    print("  - no liquidation is applied by the engine that wrote it")
    print("  - 17 Aug - 21 Sep is the previously identified favourable window")
    print()

    # ---- Step 0b ----
    F, cause, M_like, W, audit = entry_bar_features(L)
    complete = cause == ""
    print("STEP 0b -- the six features at every trade's own entry bar")
    print(f"  envfeat max index touched > entry bar: 0 (asserted); 1-minute reads stop at "
          f"+{audit['max_off_1m']} min (the entry bar's close); 1m path vs 30m window at "
          f"the marks {audit['rep_ratio']:.3f} of the float32 budget")
    print(f"  complete feature rows: {int(complete.sum()):,} of {len(L):,}")
    for c, nn in pd.Series(cause[~complete]).value_counts().items():
        print(f"    missing -- {c}: {nn:,}")

    # reproduction on the exactly matched trades
    Mt = pd.read_parquet(paths.META)
    Mt["t"] = pd.to_datetime(Mt.entry_time)
    key = {(a, b, t): i for i, (a, b, t) in enumerate(zip(Mt.ticker_a, Mt.ticker_b, Mt.t))}
    lab = L.t_open - pd.Timedelta(minutes=30)
    eid = np.array([key.get((a, b, t), -1) for a, b, t in zip(L.ticker_a, L.ticker_b, lab)])
    fz = np.load(paths.ENVFEAT, allow_pickle=False)
    names5 = [str(x) for x in fz["names"]]
    v48 = np.load(os.path.join(paths.DATASETS, "vol48_1m.npz"))
    vpos = {r: k for k, r in enumerate(v48["rows"])}
    m = np.flatnonzero((eid >= 0) & complete)
    w5 = w1 = 0.0
    n1 = 0
    for r in m:
        e = eid[r]
        for j, nm in enumerate(names5):
            a32 = np.float32(F[r, FEATURES.index(nm)])
            w5 = max(w5, abs(float(a32) - float(fz["X"][e, j])))
        if e in vpos:
            n1 += 1
            w1 = max(w1, abs(F[r, FEATURES.index("vol_48_1m")] - v48["vol_48_1m"][vpos[e]]))
    print(f"  REPRODUCTION on trades matched to an episode at the exact decision bar "
          f"(same pair order): {len(m)}")
    print(f"    five envfeat features, float32: max diff {w5:.3e};  vol_48_1m "
          f"({n1} in the 1m set): max diff {w1:.3e}")
    if len(m) == 0 or w5 > 0.0 or w1 > 1e-12:
        raise SystemExit("[META] STOP -- the entry-bar function does not reproduce the "
                         "episode features.")
    if complete.sum() < MIN_CLEAN:
        raise SystemExit(f"[META] STOP -- {int(complete.sum())} complete trades, under {MIN_CLEAN}.")
    print("  -> PASS")
    print(f"  [{time.time()-t0:.0f}s]")
    print()

    # ---- the classifier and the flag ----
    S = setup(t0, "  classifier setup (TAIL-CLASSIFIER population, split, labels)")
    X, sp, labels = S["X"], S["sp"], S["labels"]
    mdl, mu, sd = logit_model(X, labels[K_HOLD], sp)
    sc = mdl.decision_function((X - mu) / sd)
    auc = roc_auc_score(labels[K_HOLD][sp.test], sc[sp.test])
    if round(auc, 4) != LOGIT_PUBLISHED[K_HOLD]:
        raise SystemExit("[META] the 0.5h classifier does not reproduce TAIL-CLASSIFIER.")
    cut = float(np.quantile(sc[sp.train], 1 - FLAG_SHARE))
    T = L[complete].reset_index(drop=True)
    tsc = mdl.decision_function((F[complete] - mu) / sd)
    flag = tsc > cut
    r = T.r.to_numpy(float)
    day = T.t_open.dt.floor("D").to_numpy()
    print()
    print("THE FLAG -- 0.5h classifier (reproduces AUC 0.7150), cut-off = 80th pct of TRAIN")
    print(f"  flagged share: trades {flag.mean():.3f} ({int(flag.sum()):,} of {len(T):,});  "
          f"episodes -- train {(sc[sp.train] > cut).mean():.3f}, validation "
          f"{(sc[sp.val] > cut).mean():.3f}, held out {(sc[sp.test] > cut).mean():.3f}")
    print(f"  R of flagged trades: mean {r[flag].mean():+.3f}, total {r[flag].sum():+.1f}, "
          f"win {(r[flag] > 0).mean():.3f};  unflagged: mean {r[~flag].mean():+.3f}, "
          f"total {r[~flag].sum():+.1f}, win {(r[~flag] > 0).mean():.3f}")
    print(f"  exits, flagged vs unflagged: " + "; ".join(
        f"{k} {(T.exit_reason[flag] == k).mean():.2f}/{(T.exit_reason[~flag] == k).mean():.2f}"
        for k in T.exit_reason.value_counts().index))
    print()

    # ---- arms ----
    ones = np.ones(len(T))
    allk = np.ones(len(T), bool)
    arms = {"ALL": (ones, allk), "SKIP": (ones, ~flag),
            "HALF": (np.where(flag, 0.5, 1.0), allk)}
    st = {a: arm_stats(r, *v) for a, v in arms.items()}
    boot = boot_days(day)
    bd = {a: np.array([arm_stats(r[ix], v[0][ix], v[1][ix]) - arm_stats(r[ix], ones[ix], allk[ix])
                       for ix in boot]) for a, v in arms.items() if a != "ALL"}
    print("=" * 112)
    print("STEP 1 -- the arms against taking every trade (day-clustered paired 95% intervals)")
    print("=" * 112)
    lbl = ["mean R per trade", "total R", "trades", "win rate"]
    print(f"  {'':<18}{'ALL':>10}{'SKIP':>10}{'HALF':>10}   SKIP - ALL [95% CI]"
          f"            HALF - ALL [95% CI]")
    for q, nm in enumerate(lbl):
        fmt = (lambda x: f"{x:+.4f}") if q in (0,) else (lambda x: f"{x:+.1f}") if q == 1 \
            else (lambda x: f"{x:.0f}") if q == 2 else (lambda x: f"{x:.3f}")
        cells = []
        for a in ("SKIP", "HALF"):
            d = st[a][q] - st["ALL"][q]
            lo, hi = np.percentile(bd[a][:, q], [2.5, 97.5])
            cells.append(f"{fmt(d):>9} [{fmt(lo)}, {fmt(hi)}]")
        print(f"  {nm:<18}{fmt(st['ALL'][q]):>10}{fmt(st['SKIP'][q]):>10}{fmt(st['HALF'][q]):>10}"
              f"   {cells[0]:<28}{cells[1]}")
    print("  (median overshoot ratio is not reported: every stop in this ledger is booked")
    print("   at exactly 1.005x, so it carries no information)")
    print()

    # ---- random null ----
    rng = np.random.default_rng(20261012)
    nf = int(flag.sum())
    nul = {"SKIP": [], "HALF": []}
    for _ in range(N_NULL):
        pick = np.zeros(len(T), bool)
        pick[rng.choice(len(T), nf, replace=False)] = True
        nul["SKIP"].append(arm_stats(r, ones, ~pick))
        nul["HALF"].append(arm_stats(r, np.where(pick, 0.5, 1.0), allk))
    print("=" * 112)
    print(f"RANDOM NULL -- the same {nf:,} trades chosen at random, {N_NULL:,} draws")
    print("=" * 112)
    verdict = {}
    for a in ("SKIP", "HALF"):
        nv = np.array(nul[a])
        for q, nm in ((0, "mean R"), (1, "total R")):
            pct = 100.0 * (nv[:, q] < st[a][q]).mean()
            p5, p50, p95 = np.percentile(nv[:, q], [5, 50, 95])
            print(f"  {a:<5}{nm:<8} real {st[a][q]:+.4f}   null p5 {p5:+.4f}  median {p50:+.4f}"
                  f"  p95 {p95:+.4f}   real sits at the {pct:.1f}th percentile")
        verdict[a] = st[a][1] > np.percentile(nv[:, 1], 95)
    print()
    print("=" * 112)
    print("READING RULE -- fixed in the brief")
    print("=" * 112)
    for a in ("SKIP", "HALF"):
        print(f"  {a}: {'BEATS the random null on total R -- reported; the full backtest is a separate decision' if verdict[a] else 'does NOT beat the random null on total R -- SHELVED'}")
    print("  Slots full 86.5% of the time: a pass could only rule the idea in for a full")
    print("  backtest; a fail rules it out. Nothing in the registry or live system touched.")
    print(f"  [{time.time()-t0:.0f}s]")
    print("=" * 112)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("step0", "step1"), default="step0",
                    help="step0 = the Step 0 checks (episode matching). step1 = "
                         "features at every trade's entry bar, then the arms.")
    if ap.parse_args().stage == "step1":
        step1()
    else:
        main()
