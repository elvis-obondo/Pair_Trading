"""DELAYED DECISION v3: the first d minutes as 10-minute blocks.

    OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 .venv/bin/python -u \
        research/dislocation_model/delayed3.py --stage blocks > .../logs/delayed3_blocks.log 2>&1
    OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 .venv/bin/python -u \
        research/dislocation_model/delayed3.py --stage models > .../logs/delayed3.log 2>&1

Same question, target (reach_d), populations, split and chance bar as DELAYED;
t0 = initial detection, d = decision point (t0 + 30 / + 60 min); mu and sigma
frozen at t0. Reuses delayed_paths.npz, delayed2_refresh.npz,
delayed2.build_sets / fit_sets (the DELAYED and DELAYED-V2 sets, refitted by the
same code) and the 1-minute path machinery.

STEP 1 -- BLOCK FEATURES. Block k covers minutes 10(k-1)+1 .. 10k after t0's
close (3 blocks at d = 30, 6 at d = 60); seg[0] = 0 (t0's close).
  blk_move_k   seg[10k] - seg[10(k-1)]
  blk_pos_k    need - seg[10k]
  blk_vol_k    log sd (ddof 1) of the block's ten 1-minute seg changes (the first
               is the step into the block)
  blk_range_k  max - min of seg over the block's ten minutes
  blk_adv_k    max(-seg) over the block's ten minutes (deepest adverse; negative
               if the block never went against the trade)
  blk_voldom_k, blk_voloth_k  log( the leg's summed 1-minute volume over the
               block / its median 10-minute block sum over the 7 days ending at
               t0's close ); blocks and baseline need 80% traded minutes.
               Dominant = whyfeat's 12-bar dominant leg (market factor
               recomputed, as in DELAYED).
  blk_btc_k    BTC's 1-minute log close change over the block (close at minute
               10k minus close at minute 10(k-1); missing if either is).
GATE (stop on failure), on each d's still-open rows: sum of blk_move_1..n equals
seg[d] - seg[0] (the brief's identity; tolerance 1e-12, floating-point
summation; reported), and blk_pos_n equals delayed_paths' dist_now exactly.
Corrected 2026-10-13 with the user's approval: the first run compared against
seg[d] and stopped at 4.69e-07, which is |seg[0]| (the t0 close rebuilt from
1-minute prices differs from the float32 z_at_entry by ~1e-7). max |seg[0]|
is printed beside the gate. LOOK-AHEAD: block k reads minutes up to
10k only; the maximum minute read is reported per family and must be <= 60.
Missing -> TRAIN median (counted by cause). Separation on TRAIN: single-feature
AUC of every block feature, block by block.

STEP 2 -- MODELS at each d (train of the still-open; every setting on val by log
loss): position bar (L1, as before); full v1 and full v2 (delayed2.build_sets +
fit_sets, refitted; GATE (user-approved form): every refitted tree of
position, full v1 and full v2 must reproduce DELAYED-V2's logged val log loss
to 5e-6, and their L1 fits to 1e-4, because DELAYED-V2's liblinear was
unseeded (~1e-5 run-to-run wobble); delayed.fit_l1 is seeded from now on); blocks (position + all block features); everything
(full v2 + all block features); GRU. Blocks and everything: logistic L1 and
LightGBM depths 1, 2, 3, 4, 6, num_leaves 2^d, min_data_in_leaf over
{20, 50, 100, 400, 1000, 2000} (fit_sets). A tree-only set "GRU inputs" (kept
+ dist_now + all block features) is fitted for "GRU - best tree on the same
inputs".
  GRU (torch, CPU only; free memory checked and reported first): 1 layer, 16
  units, reading blocks 1..n in order, 8 standardised features per step; the
  final hidden state is concatenated with t0's kept set (24) and dist_now,
  then one linear output (sigmoid). Adam lr 1e-3, batch 512, BCE, up to 200
  epochs, early stopping on val loss (patience 10, best weights restored); 5
  seeds (0..4). Gap filled: the "GRU" model is the 5-seed mean of predicted
  probabilities (one model); each seed's val loss and held-out flag share are
  reported as mean and range. Parameter count printed.
  Gap filled: blocks and everything are each represented by their lowest-val-
  log-loss model (L1 or a tree); "the best block-based model" is the lowest
  val log loss among the blocks representative, the everything representative
  and the GRU.

STEP 3 -- SCORING, held out, HO1 and HO2, d = 30 and 60. Counts table (flagged,
correct flags, wrong flags, reverters missed, share correct) at top 20%,
catch 50% and catch 80% for position, full v1, full v2, blocks, everything,
GRU. Flag share / hit rate at 50/80/90% catch and top-20% hit, every fitted
model. Paired day-clustered 95% intervals on flag share at 80% catch: best
block-based - position (THE TEST); everything - full v2; GRU - best tree on
the same inputs; plus same-learner diagnostics (L1 vs L1, best tree vs best
tree) for blocks and everything against position, with any disagreement with
the gating test going to the user. Grouped permutation importance (held out,
20 shuffles, log-loss skill points, per-half intervals) for the best
block-based model: each block feature type across blocks; early blocks
(ending at or before d/2: block 1 at d = 30, blocks 1-3 at d = 60) against
late blocks; the t0 kept set; dist_now. Chance bar for its top 20%.

READING RULES (the brief's, fixed; "clears" = the 95% interval excludes zero):
  FOUND SOMETHING: best block-based - position, flag share at 80% catch,
    interval wholly below zero in BOTH HO1 and HO2, at d = 30 or 60.
  REGIME-DEPENDENT: clears in exactly one half.
  Also stated: everything - full v2 with its verdict; whether the GRU beats the
  trees (GRU - best tree on the same inputs, both halves; the GRU side is a
  5-seed ensemble, the tree a single deterministic model).
  If the GRU is the best block-based model, its diagnostics (added after
  review) are GRU - best position tree and GRU - best tree on the same inputs.
Nothing after minute d. No stop. Nothing written to the registry or the live
system.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

import harness
import paths
from envelope import HO_BOUNDARY, day_boot, load_1m_series, one_min_paths
from reachmu import assemble_features, flag_share, logloss_rows, population, reach_group, top_set
from delayed import DS, OUT as DPATHS
from delayed2 import KEPT, REFRESH, build_sets, fit_sets

BLOCKS_OUT = os.path.join(paths.DATASETS, "delayed3_blocks.npz")
NB = 6
TYPES = ("move", "pos", "vol", "range", "adv", "voldom", "voloth", "btc")
MIN7 = 7 * 24 * 60
N_SHUF = 20
SEED = 20261013
CATCH = (0.5, 0.8, 0.9)
# DELAYED-V2 val log losses (logs/delayed2.log), the refit gate. Trees are
# deterministic: exact to the 5-dp print (5e-6). Logistic L1 used unseeded
# liblinear in DELAYED-V2 (~1e-5 wobble), so L1 rows get 1e-4 (user-approved).
V2_TREES = {30: {"position d1": 0.47942, "position d2": 0.47923, "position d3": 0.47950, "position d4": 0.48013,
                 "position d6": 0.48088, "full v1 d1": 0.47591, "full v1 d2": 0.47661, "full v1 d3": 0.47674,
                 "full v1 d4": 0.47696, "full v1 d6": 0.47760, "full v2 d1": 0.47643, "full v2 d2": 0.47670,
                 "full v2 d3": 0.47698, "full v2 d4": 0.47746, "full v2 d6": 0.47760},
            60: {"position d1": 0.45467, "position d2": 0.45479, "position d3": 0.45492, "position d4": 0.45523,
                 "position d6": 0.45527, "full v1 d1": 0.45195, "full v1 d2": 0.45181, "full v1 d3": 0.45192,
                 "full v1 d4": 0.45234, "full v1 d6": 0.45245, "full v2 d1": 0.45150, "full v2 d2": 0.45079,
                 "full v2 d3": 0.45089, "full v2 d4": 0.45101, "full v2 d6": 0.45202}}
V2_L1 = {30: {"position L1": 0.48428, "full v1 L1": 0.47686, "full v2 L1": 0.47589},
         60: {"position L1": 0.45830, "full v1 L1": 0.45203, "full v2 L1": 0.45054}}


# ===================================================================== blocks
def stage_blocks():
    import universe_panel
    from whyfeat import load_1m_volume, market_factor
    t0 = time.time()
    Y, meta, rows = population()
    D = np.load(DPATHS)
    e = Y[rows, 0]
    s = np.sign(e)
    s[s == 0] = 1.0
    need = np.abs(e)
    series = load_1m_series(sorted(set(meta.ticker_a.iloc[rows]) | set(meta.ticker_b.iloc[rows])), False)
    P, _ = one_min_paths(meta, rows, series)
    del series
    seg = (-(P - e[:, None]) * s[:, None])[:, :NB * 10 + 1]     # minutes 0..60; column m = minute m
    del P
    n = len(rows)
    F = {f"blk_{t}_{k}": np.full(n, np.nan) for t in TYPES for k in range(1, NB + 1)}
    for k in range(1, NB + 1):
        a, b = 10 * (k - 1), 10 * k
        blk = seg[:, a + 1:b + 1]                                # minutes a+1..b
        F[f"blk_move_{k}"] = seg[:, b] - seg[:, a]
        F[f"blk_pos_{k}"] = need - seg[:, b]
        with np.errstate(invalid="ignore", divide="ignore"):
            sdv = np.std(np.diff(seg[:, a:b + 1], axis=1), axis=1, ddof=1)
            F[f"blk_vol_{k}"] = np.where(sdv > 0, np.log(sdv), np.nan)
        F[f"blk_range_{k}"] = blk.max(1) - blk.min(1)
        F[f"blk_adv_{k}"] = (-blk).max(1)
    read_path = NB * 10
    print(f"  path blocks built from seg minutes 0..{read_path}   [{time.time()-t0:.0f}s]", flush=True)
    # gate
    for d in DS:
        o = D[f"open_{d}"]
        nb = d // 10
        sm = np.sum(np.column_stack([F[f"blk_move_{k}"] for k in range(1, nb + 1)]), axis=1)
        err = float(np.max(np.abs(sm[o] - (seg[o, d] - seg[o, 0]))))
        s0 = float(np.max(np.abs(seg[o, 0])))
        exact = bool(np.array_equal(F[f"blk_pos_{nb}"][o], D[f"dist_now_{d}"][o]))
        print(f"  GATE d={d}: sum of blk_move = seg[d] - seg[0], max |diff| {err:.2e} (<= 1e-12);  "
              f"blk_pos_{nb} == dist_now exactly: {exact};  max |seg[0]| {s0:.2e} (the float32 rounding of the "
              f"stored z_at_entry against the float64 1-minute rebuild; not a block error)")
        if err > 1e-12 or not exact:
            raise SystemExit("[DELAY3] STOP -- the blocks do not add up to the DELAYED path features.")
    del seg
    # dominance (whyfeat, 12-bar), as in DELAYED
    panel = universe_panel.drop_forming_bars(universe_panel.load_panel())
    cols = list(panel.columns)
    ixc = {c: j for j, c in enumerate(cols)}
    _, resid, _, _, _, _ = market_factor(panel.to_numpy(float))
    J = meta.bar_index.to_numpy(int)[rows]
    ja = meta.ticker_a.map(ixc).to_numpy(int)[rows]
    jb = meta.ticker_b.map(ixc).to_numpy(int)[rows]
    beta = meta.beta.to_numpy(float)[rows]
    I = J[:, None] + np.arange(-11, 1)[None, :]
    ra, rb = resid[I, ja[:, None]], resid[I, jb[:, None]]
    domA = np.abs(ra.sum(1)) >= np.abs(-beta * rb.sum(1))
    undef = ~(np.isfinite(ra).all(1) & np.isfinite(rb).all(1))
    del resid
    print(f"  dominance recomputed; undefined {int(undef.sum()):,}   [{time.time()-t0:.0f}s]", flush=True)
    lastm = pd.to_datetime(meta.entry_time.to_numpy()[rows]).to_numpy().astype("datetime64[m]") + np.timedelta64(29, "m")
    ta, tb = meta.ticker_a.to_numpy()[rows], meta.ticker_b.to_numpy()[rows]
    VA = {(leg, k): np.full(n, np.nan) for leg in ("a", "b") for k in range(1, NB + 1)}
    btc = {k: np.full(n, np.nan) for k in range(1, NB + 1)}
    maxread = -10 ** 9
    for tk in sorted(set(ta) | set(tb) | {"BTC"}):
        tz, vol, lc = load_1m_volume(tk)
        endo_all = ((lastm - tz) / np.timedelta64(1, "m")).astype(np.int64)
        for leg, tt in (("a", ta), ("b", tb)):
            rr = np.flatnonzero(tt == tk)
            if not len(rr):
                continue
            endo = endo_all[rr]
            Bi = endo[:, None] + np.arange(-MIN7 + 1, 1)[None, :]
            okb = (Bi >= 0) & (Bi < len(vol))
            vb = np.where(okb, vol[np.clip(Bi, 0, len(vol) - 1)], np.nan).reshape(len(rr), MIN7 // 10, 10)
            bs = np.where(np.isfinite(vb).sum(2) >= 8, np.nansum(vb, 2), np.nan)
            with np.errstate(invalid="ignore"):
                med = np.nanmedian(bs, 1)
            for k in range(1, NB + 1):
                Wi = endo[:, None] + np.arange(10 * (k - 1) + 1, 10 * k + 1)[None, :]
                okw = (Wi >= 0) & (Wi < len(vol))
                vw = np.where(okw, vol[np.clip(Wi, 0, len(vol) - 1)], np.nan)
                maxread = max(maxread, int((Wi.max(1) - endo).max()))
                with np.errstate(invalid="ignore", divide="ignore"):
                    ws = np.where(np.isfinite(vw).sum(1) >= 8, np.nansum(vw, 1), np.nan)
                    r_ = ws / med
                    VA[(leg, k)][rr] = np.where(r_ > 0, np.log(r_), np.nan)
        if tk == "BTC":
            for k in range(1, NB + 1):
                i1 = endo_all + 10 * k
                i0 = endo_all + 10 * (k - 1)
                ok = (i0 >= 0) & (i1 < len(lc))
                btc[k] = np.where(ok, lc[np.clip(i1, 0, len(lc) - 1)] - lc[np.clip(i0, 0, len(lc) - 1)], np.nan)
                maxread = max(maxread, 10 * k)
    print(f"  volume and BTC blocks built; latest minute read = t0 close + {maxread} (must be <= {NB * 10})   "
          f"[{time.time()-t0:.0f}s]", flush=True)
    if maxread > NB * 10:
        raise SystemExit("[DELAY3] STOP -- a block reads past minute 60.")
    for k in range(1, NB + 1):
        a_, b_ = VA[("a", k)], VA[("b", k)]
        F[f"blk_voldom_{k}"] = np.where(undef, np.nan, np.where(domA, a_, b_))
        F[f"blk_voloth_{k}"] = np.where(undef, np.nan, np.where(domA, b_, a_))
        F[f"blk_btc_{k}"] = btc[k]
    np.savez_compressed(BLOCKS_OUT, rows=rows, undef=undef, read_path=read_path, read_vol=maxread, **F)
    print(f"  [WROTE] {os.path.relpath(BLOCKS_OUT, paths.RESEARCH)}   [{time.time()-t0:.0f}s]")


# ======================================================================= GRU
def gru_fit(Xseq, Xst, y, tr, va, seed):
    import torch
    torch.manual_seed(seed)
    np.random.seed(seed)

    class Net(torch.nn.Module):
        def __init__(self, nf, ns):
            super().__init__()
            self.gru = torch.nn.GRU(nf, 16, num_layers=1, batch_first=True)
            self.out = torch.nn.Linear(16 + ns, 1)

        def forward(self, q, st):
            _, h = self.gru(q)
            return self.out(torch.cat([h[-1], st], 1)).squeeze(1)
    net = Net(Xseq.shape[2], Xst.shape[1])
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    lossf = torch.nn.BCEWithLogitsLoss()
    T = lambda a: torch.tensor(a, dtype=torch.float32)
    qtr, stt, ytr = T(Xseq[tr]), T(Xst[tr]), T(y[tr])
    qva, sva, yva = T(Xseq[va]), T(Xst[va]), T(y[va])
    g = torch.Generator().manual_seed(seed)
    best, best_state, bad, ep_best = np.inf, None, 0, 0
    for ep in range(200):
        net.train()
        perm = torch.randperm(len(ytr), generator=g)
        for i in range(0, len(perm), 512):
            b = perm[i:i + 512]
            opt.zero_grad()
            lossf(net(qtr[b], stt[b]), ytr[b]).backward()
            opt.step()
        net.eval()
        with torch.no_grad():
            vl = float(lossf(net(qva, sva), yva))
        if vl < best - 1e-6:
            best, bad, ep_best = vl, 0, ep + 1
            best_state = {k: v.clone() for k, v in net.state_dict().items()}
        else:
            bad += 1
            if bad >= 10:
                break
    net.load_state_dict(best_state)
    net.eval()

    def predict(qs, sts):
        with torch.no_grad():
            return torch.sigmoid(net(T(qs), T(sts))).numpy().astype(float)
    npar = sum(p.numel() for p in net.parameters())
    return predict, best, ep_best, npar


# ===================================================================== models
def stage_models():
    import subprocess
    import lightgbm  # noqa: F401  -- must be LOADED before torch: torch first segfaults LightGBM (libomp)
    t0 = time.time()
    Y, meta, rows = population()
    D = np.load(DPATHS)
    R = np.load(REFRESH)
    BZ = np.load(BLOCKS_OUT)
    if not (np.array_equal(D["rows"], rows) and np.array_equal(R["rows"], rows) and np.array_equal(BZ["rows"], rows)):
        raise SystemExit("[DELAY3] row alignment differs.")
    day = meta.day.to_numpy()[rows]
    e = Y[rows, 0]
    sp = harness.Split(day, e)
    names, X0, _ = assemble_features(meta, rows, e, sp.train)
    kcols = [j for j, nm in enumerate(names) if reach_group(nm) in KEPT]
    kn = [names[j] for j in kcols]
    ix0 = {nm: j for j, nm in enumerate(names)}
    print("=" * 120)
    print("DELAYED DECISION v3 -- the first d minutes as 10-minute blocks (t0 = initial detection, d = decision point)")
    print("=" * 120)
    print(f"  {sp.describe()}")
    print(f"  look-ahead: path blocks read minutes 0..{int(BZ['read_path'])}, volume/BTC up to t0 close + "
          f"{int(BZ['read_vol'])}; at each d only blocks 1..d/10 are used")
    verdicts = {}
    for d in DS:
        nb = d // 10
        print()
        print("#" * 120)
        print(f"DECISION POINT d = t0 + {d} min ({nb} blocks)")
        print("#" * 120)
        openm = D[f"open_{d}"]
        rr = np.flatnonzero(openm)
        y = D[f"reach_{d}"].astype(int)[rr]
        tr, va, te = sp.train[rr], sp.val[rr], sp.test[rr]
        dd = day[rr]
        halves = {"HO1": np.flatnonzero(te & (dd < HO_BOUNDARY)), "HO2": np.flatnonzero(te & (dd >= HO_BOUNDARY))}
        B_ = build_sets(D, R, X0, kcols, kn, ix0, d, rr, tr, y)
        sets = {k_: B_["sets"][k_] for k_ in ("position", "full v1", "full v2")}
        tfp = B_["tfp"]
        bn = [f"blk_{t}_{k}" for k in range(1, nb + 1) for t in TYPES]
        braw = {nm: BZ[nm][rr].astype(float) for nm in bn}
        und = BZ["undef"][rr]
        print("  STEP 1 -- block features; coverage and missing by cause (still open)")
        for nm in bn:
            v = braw[nm]
            nm_ = int((~np.isfinite(v)).sum())
            if nm_:
                c_ = int((~np.isfinite(v) & und).sum())
                print(f"    {nm:<16} missing {nm_:>5}  (dominant leg undefined {c_}, volume/BTC/range missing {nm_ - c_})")
        Bm = np.column_stack([braw[nm] for nm in bn])
        for j in range(Bm.shape[1]):
            m = ~np.isfinite(Bm[:, j])
            Bm[m, j] = np.nanmedian(Bm[tr, j])
        from sklearn.metrics import roc_auc_score
        yt = y[tr]
        print("    SEPARATION on TRAIN still-open: single-feature AUC by block (k = 1..n)")
        for t in TYPES:
            cells = []
            for k in range(1, nb + 1):
                v = braw[f"blk_{t}_{k}"][tr]
                m = np.isfinite(v)
                cells.append(f"{roc_auc_score(yt[m], v[m]):.3f}")
            print(f"      {t:<8} " + "  ".join(cells))
        Xp, np_ = sets["position"]
        Xv2, nv2 = sets["full v2"]
        XK = X0[rr][:, kcols]
        sets["blocks"] = (np.column_stack([Xp, Bm]), np_ + bn)
        sets["everything"] = (np.column_stack([Xv2, Bm]), nv2 + bn)
        sets["GRU inputs"] = (np.column_stack([XK, tfp["dist_now"], Bm]), kn + ["dist_now"] + bn)
        print("  STEP 2 -- models (train; settings on val by log loss)")
        score, vll, fns = fit_sets({k_: v for k_, v in sets.items() if k_ != "GRU inputs"}, y, tr, va, t0, no_trees=())
        s2, v2_, f2 = fit_sets({"GRU inputs": sets["GRU inputs"]}, y, tr, va, t0, no_trees=())
        for k_ in [k_ for k_ in s2 if k_.endswith("L1")]:
            s2.pop(k_), v2_.pop(k_), f2.pop(k_)
        score.update(s2), vll.update(v2_), fns.update(f2)
        rep = {sn: min([k_ for k_ in vll if k_.startswith(sn + " ")], key=lambda k_: vll[k_])
               for sn in ("full v1", "full v2", "blocks", "everything")}
        rep["position"] = "position L1"
        btree = {sn: min([k_ for k_ in vll if k_.startswith(sn + " d")], key=lambda k_: vll[k_])
                 for sn in ("position", "blocks", "everything", "GRU inputs")}
        bad = [(nm, round(vll[nm], 6), ref) for nm, ref in V2_TREES[d].items() if abs(vll[nm] - ref) > 5e-6 + 1e-12]
        bad += [(nm, round(vll[nm], 6), ref) for nm, ref in V2_L1[d].items() if abs(vll[nm] - ref) > 1e-4]
        mt = max(abs(vll[nm] - ref) for nm, ref in V2_TREES[d].items())
        ml = max(abs(vll[nm] - ref) for nm, ref in V2_L1[d].items())
        print(f"    GATE -- refit reproduces DELAYED-V2's val log loss: 15 trees within 5e-6 (max |diff| {mt:.1e}), "
              f"3 L1 within 1e-4 (max |diff| {ml:.1e}): {'PASS' if not bad else 'FAIL ' + str(bad)}")
        if bad:
            raise SystemExit("[DELAY3] STOP -- full v1 / full v2 refit does not reproduce DELAYED-V2.")
        # GRU (torch imported here, after lightgbm; safe across the d loop, tested)
        import torch
        torch.set_num_threads(4)
        vm = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout.splitlines()
        pg = 16384 if "16384" in vm[0] else 4096
        free = sum(int(l.split(":")[1].strip().rstrip(".")) for l in vm
                   if l.startswith(("Pages free", "Pages inactive", "Pages speculative"))) * pg / 1e9
        print(f"    GRU -- free + inactive memory {free:.2f} GB; CPU only, torch {torch.__version__}, "
              f"{torch.get_num_threads()} threads")
        seq = np.stack([np.column_stack([Bm[:, bn.index(f"blk_{t}_{k}")] for t in TYPES]) for k in range(1, nb + 1)], 1)
        sm_, ss_ = seq[tr].mean(0), seq[tr].std(0)
        ss_[ss_ == 0] = 1.0
        seqz = (seq - sm_) / ss_
        st = np.column_stack([XK, tfp["dist_now"]])
        tm_, ts_ = st[tr].mean(0), st[tr].std(0)
        ts_[ts_ == 0] = 1.0
        stz = (st - tm_) / ts_
        preds, gstats = [], []
        for sd in range(5):
            pr, vl, ep, npar = gru_fit(seqz, stz, y, tr, va, sd)
            p_all = pr(seqz, stz)
            preds.append(pr)
            gstats.append((sd, logloss_rows(y[va], p_all[va]).mean(), ep, p_all))
            print(f"      seed {sd}: best epoch {ep}, val log loss {gstats[-1][1]:.5f}   [{time.time()-t0:.0f}s]", flush=True)
        print(f"      parameters: {npar:,}")

        def gru_fn(M_, preds=preds, nk=len(kn), nb=nb):
            st_ = (M_[:, :nk + 1] - tm_) / ts_
            q_ = np.stack([np.column_stack([M_[:, nk + 1 + bn.index(f"blk_{t}_{k}")] for t in TYPES])
                           for k in range(1, nb + 1)], 1)
            q_ = (q_ - sm_) / ss_
            return np.mean([p(q_, st_) for p in preds], axis=0)
        Xg, ng = sets["GRU inputs"]
        score["GRU"] = gru_fn(Xg)
        vll["GRU"] = logloss_rows(y[va], score["GRU"][va]).mean()
        fns["GRU"] = gru_fn
        rep["GRU"] = "GRU"
        print(f"      GRU (5-seed mean of probabilities): val log loss {vll['GRU']:.5f}")
        bbm = min((rep["blocks"], rep["everything"], "GRU"), key=lambda k_: vll[k_])
        bbm_set = "blocks" if bbm == rep["blocks"] else "everything" if bbm == rep["everything"] else "GRU inputs"
        print(f"    -> representatives: blocks = {rep['blocks']}, everything = {rep['everything']}, full v1 = "
              f"{rep['full v1']}, full v2 = {rep['full v2']}; BEST BLOCK-BASED (val) = {bbm}; best trees: "
              + ", ".join(f"{k_} {v}" for k_, v in btree.items()))

        # ---- scoring
        print("  STEP 3 -- scoring, held out only")
        hboot = {hn: day_boot(dd[ixh]) for hn, ixh in halves.items()}
        main_models = [("position", "position L1"), ("full v1", rep["full v1"]), ("full v2", rep["full v2"]),
                       ("blocks", rep["blocks"]), ("everything", rep["everything"]), ("GRU", "GRU")]
        for hn, ixh in halves.items():
            yh = y[ixh]
            R_ = int(yh.sum())
            print(f"    {hn}: still open {len(ixh):,}, reverters {R_:,} ({yh.mean():.4f})")
            print(f"      COUNTS  {'model':<22}{'setting':<10}{'flagged':>8}{'correct':>9}{'wrong':>8}{'missed':>8}{'share correct':>15}")
            for lbl, mn in main_models:
                sc = score[mn][ixh]
                o = np.argsort(-sc, kind="stable")
                for st_lbl, k_ in (("top 20%", int(round(0.2 * len(o)))),
                                   ("catch 50%", int(round(flag_share(sc, yh, 0.5)[0] * len(o)))),
                                   ("catch 80%", int(round(flag_share(sc, yh, 0.8)[0] * len(o))))):
                    c_ = int(yh[o[:k_]].sum())
                    print(f"              {lbl + ' (' + mn + ')':<22}{st_lbl:<10}{k_:>8,}{c_:>9,}{k_ - c_:>8,}{R_ - c_:>8,}{c_ / k_:>15.3f}")
            print(f"      {'model':<18}" + "".join(f"{f'catch {int(100*c)}%: flag / hit':>28}" for c in CATCH) + f"{'top20 hit':>11}")
            print(f"      {'random':<18}" + "".join(f"{f'{c:.3f} / {yh.mean():.3f}':>28}" for c in CATCH) + f"{yh.mean():>11.3f}")
            for mn in score:
                sc = score[mn][ixh]
                cat = [flag_share(sc, yh, c)[:2] for c in CATCH]
                tag = "   <- " + [k_ for k_, v in rep.items() if v == mn][0] if mn in rep.values() else ""
                print(f"      {mn:<18}" + "".join(f"{f'{a:.3f} / {b:.3f}':>28}" for a, b in cat)
                      + f"{yh[top_set(sc, 0.2)].mean():>11.3f}{tag}")
            fl = [flag_share(g_[3][ixh], yh, 0.8)[0] for g_ in gstats]
            print(f"      GRU seeds: val log loss mean {np.mean([g_[1] for g_ in gstats]):.5f} "
                  f"[{min(g_[1] for g_ in gstats):.5f}, {max(g_[1] for g_ in gstats):.5f}];  flag share at 80% catch "
                  f"mean {np.mean(fl):.4f} [{min(fl):.4f}, {max(fl):.4f}]")

        def paired(a, b, hn):
            ixh = halves[hn]
            yh, sa, sb = y[ixh], score[a][ixh], score[b][ixh]
            f = lambda sc, yy: flag_share(sc, yy, 0.8)[0]
            dr = [f(sa[i_], yh[i_]) - f(sb[i_], yh[i_]) for i_ in hboot[hn]]
            return (f(sa, yh) - f(sb, yh), *np.percentile(dr, [2.5, 97.5]))
        tests = (("best block-based - position  [THE TEST]", bbm, "position L1"),
                 ("everything - full v2", rep["everything"], rep["full v2"]),
                 ("GRU - best tree on the same inputs", "GRU", btree["GRU inputs"]),
                 ("GRU - best position tree  [diag]", "GRU", btree["position"]),
                 ("blocks L1 - position L1  [diag]", "blocks L1", "position L1"),
                 ("best blocks tree - best position tree  [diag]", btree["blocks"], btree["position"]),
                 ("everything L1 - position L1  [diag]", "everything L1", "position L1"),
                 ("best everything tree - best position tree  [diag]", btree["everything"], btree["position"]),
                 ("everything L1 - full v2 L1  [diag]", "everything L1", "full v2 L1"),
                 ("best everything tree - best full v2 tree  [diag]", btree["everything"],
                  min([k_ for k_ in vll if k_.startswith("full v2 d")], key=lambda k_: vll[k_])))
        print("    PAIRED flag share at 80% catch, day-clustered 95% (A minus B; - = A needs fewer flags)")
        P_ = {}
        for lbl, a, b in tests:
            cells = []
            for hn in halves:
                r_ = paired(a, b, hn)
                P_[(lbl, hn)] = r_
                cells.append(f"{hn} {r_[0]:+.4f} [{r_[1]:+.4f},{r_[2]:+.4f}]" + ("*" if r_[2] < 0 else "!" if r_[1] > 0 else " "))
            print(f"      {lbl:<52}({a} vs {b})")
            print("        " + "   ".join(cells))
        clr = {lbl: [hn for hn in halves if P_[(lbl, hn)][2] < 0] for lbl, _, _ in tests}
        fam = "GRU" if bbm == "GRU" else "blocks" if bbm_set == "blocks" else "everything"
        dg = (("GRU - best position tree  [diag]", "GRU - best tree on the same inputs") if fam == "GRU" else
              (f"{fam} L1 - position L1  [diag]", f"best {fam} tree - best position tree  [diag]"))
        agree = all((len(clr[x]) == 2) == (len(clr["best block-based - position  [THE TEST]"]) == 2) for x in dg)
        print(f"    THE TEST clears in: {', '.join(clr['best block-based - position  [THE TEST]']) or 'neither'};  "
              f"diagnostics ({fam}): " + "; ".join(f"{x.replace('  [diag]', '')}: {', '.join(clr[x]) or 'neither'}" for x in dg)
              + ("" if agree else "   <- DISAGREES with the gating test: goes to the user"))
        dg2 = ("everything L1 - full v2 L1  [diag]", "best everything tree - best full v2 tree  [diag]")
        agree2 = all((len(clr[x]) == 2) == (len(clr["everything - full v2"]) == 2) for x in dg2)
        print(f"    everything - full v2 clears in: {', '.join(clr['everything - full v2']) or 'neither'};  diagnostics: "
              + "; ".join(f"{x.replace('  [diag]', '')}: {', '.join(clr[x]) or 'neither'}" for x in dg2)
              + ("" if agree2 else "   <- DISAGREES with the gating test: goes to the user"))
        # chance bar
        ch = D[f"chance_{d}"][rr]
        print(f"    CHANCE BAR (reading only), {bbm}'s top 20%")
        for hn, ixh in halves.items():
            yh, chh, sc = y[ixh], ch[ixh], score[bbm][ixh]
            g_ = lambda s_, y_, c_: y_[top_set(s_, 0.2)].mean() - c_[top_set(s_, 0.2)].mean()
            lo, hi = np.percentile([g_(sc[i_], yh[i_], chh[i_]) for i_ in hboot[hn]], [2.5, 97.5])
            tp = top_set(sc, 0.2)
            print(f"      {hn}: top 20% real {yh[tp].mean():.4f} vs chance {chh[tp].mean():.4f}, gap "
                  f"{g_(sc, yh, chh):+.4f} [{lo:+.4f}, {hi:+.4f}]")
        # importance
        Xb, nbn = sets[bbm_set]
        early = [k for k in range(1, nb + 1) if 10 * k <= d / 2]
        gidx = {f"type {t}": [nbn.index(f"blk_{t}_{k}") for k in range(1, nb + 1)] for t in TYPES}
        gidx["early blocks " + ",".join(map(str, early))] = [nbn.index(f"blk_{t}_{k}") for t in TYPES for k in early]
        late = [k for k in range(1, nb + 1) if k not in early]
        gidx["late blocks " + ",".join(map(str, late))] = [nbn.index(f"blk_{t}_{k}") for t in TYPES for k in late]
        tk_ = [nbn.index(nm) for nm in kn if nm in nbn]
        if tk_:
            gidx["t0 features (kept set)"] = tk_
        gidx["dist_now"] = [nbn.index("dist_now")]
        print(f"    IMPORTANCE, held out, {bbm}; {N_SHUF} shuffles; log-loss skill points lost; per-half 95%")
        teix = np.flatnonzero(te)
        lc = logloss_rows(y[teix], np.full(len(teix), y[tr].mean()))
        fn = fns[bbm]
        base_l = logloss_rows(y[teix], fn(Xb[teix]))
        pos = {"held out": np.arange(len(teix))}
        for hn, ixh in halves.items():
            pos[hn] = np.flatnonzero(np.isin(teix, ixh))
        for gi, (g_, js) in enumerate(gidx.items()):
            acc = np.zeros(len(teix))
            for s_ in range(N_SHUF):
                perm = np.random.default_rng([SEED, d, gi, s_]).permutation(len(teix))
                Xq = Xb[teix].copy()
                Xq[:, js] = Xb[teix][perm][:, js]
                acc += logloss_rows(y[teix], fn(Xq)) - base_l
            acc /= N_SHUF
            cells = []
            for bn_, p_ in pos.items():
                bt = day_boot(dd[teix][p_])
                a_, c_ = acc[p_], lc[p_]
                lo, hi = np.percentile([100 * a_[i_].mean() / c_[i_].mean() for i_ in bt], [2.5, 97.5])
                cells.append(f"{bn_} {100*a_.mean()/c_.mean():+.4f} [{lo:+.4f},{hi:+.4f}]{'+' if lo > 0 else ' '}")
            print(f"      {g_:<26}" + "   ".join(cells))
        verdicts[d] = clr
        print(f"  [{time.time()-t0:.0f}s]", flush=True)

    print()
    print("=" * 120)
    print("READING RULES")
    print("=" * 120)
    for lbl, nm in (("best block-based - position  [THE TEST]", "FOUND SOMETHING (best block-based - position, both halves)"),
                    ("everything - full v2", "EVERYTHING BEATS FULL V2 (both halves)"),
                    ("GRU - best tree on the same inputs", "GRU BEATS THE TREES (both halves)")):
        both = [d for d in DS if len(verdicts[d][lbl]) == 2]
        one = [f"d={d} ({verdicts[d][lbl][0]} only)" for d in DS if len(verdicts[d][lbl]) == 1]
        print(f"  {nm}: {'YES at d=' + ', '.join(map(str, both)) if both else 'NO'}"
              + (f";  regime-dependent: {', '.join(one)}" if one else ""))
    print("  Nothing after minute d. No stop. Nothing written to the registry or the live system.")
    print(f"  [{time.time()-t0:.0f}s]")
    print("=" * 120)


if __name__ == "__main__":
    st = sys.argv[sys.argv.index("--stage") + 1] if "--stage" in sys.argv else "models"
    {"blocks": stage_blocks, "models": stage_models}[st]()
