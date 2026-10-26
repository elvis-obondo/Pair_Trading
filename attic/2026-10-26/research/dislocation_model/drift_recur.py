"""Does the calibration drift recur? Climatology only, at three historical cuts.

    .venv/bin/python research/dislocation_model/drift_recur.py 2>&1 \
        | tee research/dislocation_model/logs/drift_recur_30m.log

THE QUESTION. At the one cut tested so far (2026-07-18) the envelope's coverage
gap was small near the cut and grew with distance from it -- tripling by 10 hours
out, and worse in the back 40 days of the held-out block than the front 39. The
sign never flipped: MAE over-covered in both halves, MFE under-covered in both.
Does that shape show up at other points in this project's history, or was
2026-07-18 to 2026-10-04 an unusual stretch of calendar?

NAMES, NOT RUN NUMBERS. "Run 2" already means three different things in this
project's notes -- the deferred 1-minute rerun, the held-out-halves analysis, and
now this. So nothing here is numbered:

    HALVES ANALYSIS   envelope.py --stage run2. Split the held-out block at
                      2026-08-26, fit isotonic recalibration on the first half,
                      test it on the second. Its numbers are quoted below.
    1-MINUTE RERUN    envelope.py --target-source 1m. Deferred: only 1 of 212
                      instruments reaches back to 2024-09-18.
    RECURRENCE TRACK  this script. Different history, climatology only.

WHY CLIMATOLOGY ALONE IS ENOUGH. Climatology has zero capacity -- it is one
unconditional empirical quantile vector, fitted once and held fixed -- and it
reproduced the whole pattern the conditional models showed: the same near/far
ordering, the same growth with horizon, the same signs. So the drift is a
property of the envelope's LEVEL moving away from a fixed training window, not of
any model's fit. Testing recurrence therefore needs the cheap model repeated at
several points in history, not the expensive ones repeated once. Nothing here
refits Linear QR, QTREE or kNN, and no new model type exists.

THIS IS A SEPARATE TRACK ON DIFFERENT HISTORY, NOT ANOTHER TOUCH OF THE BLOCK.
Every cut's test window ends strictly before 2026-07-18. That is asserted twice:
per cut, on the last day of its far half, and once globally, on the number of
rows scored at or after the boundary, which must be zero. The held-out block is
not read by this script at all. The halves analysis's numbers appear below only
as QUOTED context, copied from NUMBERS.md -- they are not recomputed.

WHAT DECIDES IT, STATED BEFORE THE NUMBERS ARE SEEN. See VERDICT_RULE below.
A recurring shape means the drift is structural and an adaptive correction is
worth building. An inconsistent one means the original finding was specific to
that calendar stretch and periodic refitting on a fixed schedule is enough.

THE THREE CUTS DIFFER IN PRECISION BY A FACTOR OF FOUR AND THE RULE ACCOUNTS FOR
IT. The earliest cut can only train on what little history precedes it, and its
test halves are correspondingly thin -- roughly 1,100 and 1,600 episodes against
4,600 and 6,300 at the latest cut. Coverage at the 5th percentile on 1,100 rows
carries a standard error near 0.65pp before day clustering widens it, against an
effect of about 2pp. A cut whose far-minus-near interval is wider than the whole
effect cannot vote on whether the effect is there, so it is labelled UNDERPOWERED
and excluded from the per-cut majority. Its cells are still printed and still
counted in the pooled tally, and if the pooled and the decisive-only tallies
disagree the verdict is MIXED by rule rather than by preference.

THE 30 CELLS ARE NOT INDEPENDENT, and the thresholds are not p-values. MAE and
MFE are measured on the same episodes, and the five horizons are running maxima
so the 10-hour target contains the 30-minute one. The binomial figure printed
with the verdict says how strict a threshold is against coin-flipping, nothing
more. The decisive cuts are the closest thing here to independent replication.

UNITS. Everything that counts days counts UNIQUE EPISODE DAYS, never calendar
days. The history spans 747 calendar days and carries 746 episode days -- one
calendar day has no episode on it -- and an earlier version of this file derived
the earliest cut in calendar days while asserting a minimum in episode days. It
aborted on the first cut: 2025-05-26 has 249 episode days before it, not 250.
Both ends of the window are now derived by indexing the sorted unique days.
"""
import argparse
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

import paths
from envelope import (DIRECTIONS, HLABEL, HORIZONS, QUANTILES, build_targets_1m,
                      build_targets_30m, day_boot, gap_ci)

# ------------------------------------------------------------------ design
# The cut dates are DERIVED, not chosen, so there is no room for date shopping.
# Two hard constraints fix the feasible window and the spacing fixes the rest:
#
#   earliest cut = the 251st unique episode day        -> exactly 250 days of train
#   latest   cut = the 80th-from-last day before the protected block
#   spacing      = 150 days, the brief's figure
#
# At 150-day spacing that window holds exactly THREE cuts. A fourth would need
# 450 days of window -- three gaps of 150 -- against the ~338 available, and
# would land roughly four months past the latest admissible cut. Four cuts DO
# fit at 112-day spacing; 113 misses by a single day. But 112 is not "roughly
# 150 days apart", and buying the room back on the train side would break the
# 250-day minimum. Three cuts at 150 days is the only arrangement that honours
# both stated numbers, so that is what this runs. The exact figures are computed
# and printed at run time rather than written here, because this comment was
# wrong once already: it claimed a fourth cut was "one day short of fitting",
# which is true of 113-day spacing and is 112 days off for 150.
PROTECTED = np.datetime64("2026-07-18")   # harness.CUT: the block already scored
MIN_TRAIN_DAYS = 250      # unique episode days, not calendar days
HALF_DAYS = 40            # near half and far half, 40 episode days each
SPACING_DAYS = 150
N_CUTS = 3
MIN_HALF_ROWS = 1000      # below this a q05 coverage number cannot be computed at all

# Quoted from NUMBERS.md (the HALVES analysis, lines 571-572 and 580-587), pooled
# over both populations and all four models. NOT recomputed -- this script never
# reads the protected block. Printed so the new cuts are read against the number
# they are being compared to, and used as the effect size the power screen needs.
HALVES_NEAR_GAP_PP = 1.06   # first half, 8,200 rows / 39 days
HALVES_FAR_GAP_PP = 3.05    # second half, 9,864 rows / 40 days
HALVES_EFFECT_PP = HALVES_FAR_GAP_PP - HALVES_NEAR_GAP_PP
HALVES_SIGNS = "MAE over-covers, MFE under-covers, both halves, magnitude grows"
HALVES_BY_HORIZON = "near half 0.86 -> 1.29pp, far half 1.35 -> 4.33pp (0.5h to 10h)"

VERDICT_RULE = """
  A CELL is (cut, direction, horizon): 3 x 2 x 5 = 30 cells.

  ORDERS      far-half gap > near-half gap (point estimates)
  ORDERS*     the far-minus-near interval excludes zero on the high side
  SIGN SAME   near and far signed bias share a sign
  AS BEFORE   MAE over-covers and MFE under-covers, as at 2026-07-18
  GROWS       the gap at 10h exceeds the gap at 0.5h, per (cut, direction, half)

  A cut is DECISIVE if the median width of its ten far-minus-near intervals is
  at or under the effect being chased ({eff:.2f}pp, from the halves analysis).
  Wider than that and the cut cannot resolve the effect either way, so it is
  UNDERPOWERED: printed and pooled, but it does not vote on the majority.

  RECURS                requires ALL FOUR of:
                          ORDERS    in >= 70% of all 30 cells
                          ORDERS    in >= 70% of DECISIVE cells
                          SIGN SAME in >= 70% of all 30 cells
                          ORDERS    in >= 7 of 10 cells at a majority of
                                    DECISIVE cuts, and >= 2 decisive cuts exist
  CALENDAR-SPECIFIC     if ORDERS <= 50% of decisive cells (no better than a
                          coin flip) OR the MAE/MFE sign pattern flips between
                          cuts
  UNDERPOWERED          if fewer than 2 cuts are decisive -- the design cannot
                          deliver a majority and no verdict is claimed
  MIXED                 anything else, including pooled and decisive-only
                          tallies landing on opposite sides of 70%. Report as
                          mixed and prefer the simpler fix: periodic refitting
                          on a fixed schedule, no adaptive machinery.
"""


# ------------------------------------------------------------------ metrics
def bias_ci(y, pred, boot):
    """SIGNED calibration bias: mean(actual - nominal) over the 5 levels, in pp.

    Positive = the envelope OVER-covers, i.e. it is too wide. gap_ci takes the
    absolute value and so cannot tell an over-wide envelope from a too-narrow
    one; the brief asks for the sign, and this is it. Same day-clustered
    resamples as the gap, so the two columns of a row are consistent.
    """
    hits = y[:, None] <= pred
    q = np.asarray(QUANTILES)
    pt = 100.0 * float((hits.mean(0) - q).mean())
    n_over = int((hits.mean(0) > q).sum())   # how many of the 5 levels, not just the mean
    draws = np.empty(len(boot))
    for r, ix in enumerate(boot):
        draws[r] = 100.0 * (hits[ix].mean(0) - q).mean()
    return pt, float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5)), n_over


def gap_diff_ci(y_n, pred_n, boot_n, y_f, pred_f, boot_f):
    """Far-half gap minus near-half gap, with a day-clustered interval.

    The verdict rests on an ORDERING, so the ordering gets its own interval
    rather than being eyeballed from two overlapping ones. The halves are
    disjoint DAY sets, so the two resamples are independent and differencing
    them replicate by replicate is legitimate -- this is not a paired test and
    is not treated as one. The width of this interval is also what the power
    screen reads to decide whether a cut may vote.
    """
    q = np.asarray(QUANTILES)

    def _gap(y, pred, ix):
        h = (y[:, None] <= pred)[ix]
        return 100.0 * np.abs(h.mean(0) - q).mean()

    hn = y_n[:, None] <= pred_n
    hf = y_f[:, None] <= pred_f
    pt = (100.0 * np.abs(hf.mean(0) - q).mean()
          - 100.0 * np.abs(hn.mean(0) - q).mean())
    n = min(len(boot_n), len(boot_f))
    draws = np.empty(n)
    for r in range(n):
        draws[r] = _gap(y_f, pred_f, boot_f[r]) - _gap(y_n, pred_n, boot_n[r])
    return float(pt), float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


# ------------------------------------------------------------------ cuts
def derive_cuts(day):
    """The cut dates, from the constraints. Returns (cuts, earliest, latest, du).

    BOTH ENDS ARE INDEXED OFF THE SORTED UNIQUE EPISODE DAYS. Deriving either in
    calendar days and checking it in episode days is what made the first version
    abort: the history has one calendar day with no episode on it, so calendar
    arithmetic overstates the available train history by a day.
    """
    du = np.sort(np.unique(day)).astype("datetime64[D]")
    if len(du) <= MIN_TRAIN_DAYS + 2 * HALF_DAYS:
        raise SystemExit(f"[DESIGN] only {len(du)} episode days in the history.")
    earliest = du[MIN_TRAIN_DAYS]        # exactly MIN_TRAIN_DAYS days precede it
    pre = du[du < PROTECTED.astype("datetime64[D]")]
    latest = pre[-2 * HALF_DAYS]         # exactly 2*HALF_DAYS days from here to the block
    cuts = [earliest + np.timedelta64(SPACING_DAYS * i, "D") for i in range(N_CUTS)]
    if cuts[-1] > latest:
        need = SPACING_DAYS * (N_CUTS - 1)
        have = int((latest - earliest).astype(int))
        raise SystemExit(
            f"[DESIGN] {N_CUTS} cuts at {SPACING_DAYS}-day spacing need {need} days of "
            f"window; {earliest} to {latest} is {have}. The last cut would land "
            f"{cuts[-1]}, {int((cuts[-1] - latest).astype(int))} days past the latest "
            f"admissible one. Reduce N_CUTS or SPACING_DAYS.")
    return cuts, earliest, latest, du


def split_at(day, entry_time, cut):
    """train / near half / far half for one cut, by DAY not by row.

    Halves are HALF_DAYS unique episode days each, taken in order from the cut,
    so a quiet week does not silently become a short half. The far half's last
    day is checked against the protected block here, at construction.
    """
    train = day < cut
    after = np.sort(np.unique(day[day >= cut]))
    need = 2 * HALF_DAYS
    if len(after) < need:
        raise SystemExit(f"[{cut}] only {len(after)} episode days follow the cut, "
                         f"{need} needed.")
    after = after.astype("datetime64[D]")          # printed; ns precision is unreadable
    near_days, far_days = after[:HALF_DAYS], after[HALF_DAYS:need]
    if far_days[-1] >= PROTECTED:
        raise SystemExit(
            f"[{cut}] far half reaches {far_days[-1]}, inside the protected block "
            f"(>= {PROTECTED}). This script must not touch the block already scored. "
            f"Move the cut earlier.")
    n_train_days = int(len(np.unique(day[train])))
    if n_train_days < MIN_TRAIN_DAYS:
        raise SystemExit(
            f"[{cut}] only {n_train_days} episode days of train, {MIN_TRAIN_DAYS} "
            f"required. If the derivation says otherwise, the two are in different "
            f"units -- see derive_cuts.")
    near = np.isin(day, near_days)
    far = np.isin(day, far_days)
    for nm, m in (("near", near), ("far", far)):
        if int(m.sum()) < MIN_HALF_ROWS:
            raise SystemExit(
                f"[{cut}] {nm} half has {int(m.sum()):,} rows, under the "
                f"{MIN_HALF_ROWS:,} needed to compute a q05 coverage number.")

    # Train rows whose outcome window crosses the cut. Bars are labelled by OPEN
    # time and a 30m bar labelled T closes at T+30, so outcome j is the bar
    # labelled entry + j*30m and the last observed close at the longest horizon
    # is entry + (20+1)*30m = entry + 10.5h.
    last_close = entry_time + (max(HORIZONS) + 1) * np.timedelta64(30, "m")
    crossing = int((train & (last_close > cut)).sum())

    return dict(cut=cut, train=train, near=near, far=far,
                near_days=near_days, far_days=far_days, n_train_days=n_train_days,
                crossing=crossing)


def q05_se_pp(n):
    """Binomial standard error of a 5% coverage estimate on n rows, in pp.

    Day clustering widens the real interval beyond this, so it is a FLOOR on the
    noise, printed next to each half's row count. The point is the comparison
    with the effect size, not the number itself.
    """
    return 100.0 * math.sqrt(0.05 * 0.95 / n)


# ------------------------------------------------------------------ run
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-source", choices=("30m", "1m"), default="30m")
    args = ap.parse_args()
    t0 = time.time()

    z = np.load(paths.DISLOC)
    Y = z["outcomes"].astype(np.float64)
    meta = pd.read_parquet(paths.META)
    day = meta.day.to_numpy()
    entry_time = meta.entry_time.to_numpy()

    print("=" * 118)
    print(f"DRIFT RECURRENCE -- climatology only, {N_CUTS} historical cuts, "
          f"target source {args.target_source}")
    print("=" * 118)
    print(f"  {len(meta):,} episodes, {len(np.unique(day)):,} episode days, "
          f"{pd.Timestamp(day.min()).date()} to {pd.Timestamp(day.max()).date()}")
    print("  POPULATION: ALL only. Trending is a refinement and is not needed to")
    print("  answer a recurrence question.")
    print("  MODELS: Climatology only -- one unconditional empirical quantile vector")
    print("  per (cut, direction, horizon), fitted on EVERYTHING before the cut.")
    print("  Nothing from the halves analysis is refitted and no new model type exists.")
    print()
    print("  NOTE ON THE FIT RULE. The halves analysis fitted climatology on the TRAIN")
    print("  block only -- the first 80% of fit days -- so that it had exactly the data")
    print("  the conditional models had. There are no conditional models here, so there")
    print("  is nothing to match and the brief's rule applies: everything before the")
    print("  cut. That gives this track MORE fit data per cut than that baseline had,")
    print("  which if anything biases it AGAINST finding drift.")
    print()

    if args.target_source == "30m":
        targets, _ = build_targets_30m(Y)
        print("  30-MINUTE CLOSES. The true envelope is strictly worse; the worst point")
        print("  inside a bar is never observed. The bias is the same at every cut, so a")
        print("  comparison ACROSS cuts is unaffected -- which is all this script does.")
    else:
        targets, _ = build_targets_1m(Y, meta)
    print()

    cuts, earliest, latest, du = derive_cuts(day)
    window = int((latest - earliest).astype(int))
    print("=" * 118)
    print("CUT POINTS -- derived from the constraints, not chosen")
    print("=" * 118)
    print(f"  earliest admissible cut  {earliest}   "
          f"(episode day #{MIN_TRAIN_DAYS+1}: exactly {MIN_TRAIN_DAYS} precede it)")
    print(f"  latest   admissible cut  {latest}   "
          f"({2*HALF_DAYS} episode days from here to {PROTECTED})")
    print(f"  window {window} days, spacing {SPACING_DAYS} days -> {N_CUTS} cuts.")
    # One more cut than N_CUTS means N_CUTS gaps, so N_CUTS*SPACING_DAYS of window.
    # Spelled out because this line claimed "one day short" when it was 112 days off.
    nxt = earliest + np.timedelta64(SPACING_DAYS * N_CUTS, "D")
    fits = window // N_CUTS
    print(f"  {N_CUTS+1} cuts at this spacing would need {N_CUTS} gaps of "
          f"{SPACING_DAYS} = {SPACING_DAYS*N_CUTS} days of window against "
          f"{window} available,")
    print(f"  landing the last at {nxt}, {int((nxt - latest).astype(int))} days past "
          f"the latest admissible cut.")
    print(f"  {N_CUTS+1} cuts DO fit at {fits}-day spacing; {fits+1} misses by "
          f"{(fits+1)*N_CUTS - window} day(s). Neither is 'roughly "
          f"{SPACING_DAYS} days apart'.")
    print()

    blocks = [split_at(day, entry_time, c) for c in cuts]
    print(f"  {'cut':<12}{'train days':>11}{'train rows':>11}"
          f"{'near half':>24}{'far half':>24}{'near/far rows':>16}{'q05 SE pp':>12}")
    for b in blocks:
        nn, nf = int(b["near"].sum()), int(b["far"].sum())
        print(f"  {str(b['cut']):<12}{b['n_train_days']:>11,}{int(b['train'].sum()):>11,}"
              f"{str(b['near_days'][0])+'..'+str(b['near_days'][-1]):>24}"
              f"{str(b['far_days'][0])+'..'+str(b['far_days'][-1]):>24}"
              f"{f'{nn:,}/{nf:,}':>16}"
              f"{f'{q05_se_pp(nn):.2f}/{q05_se_pp(nf):.2f}':>12}")
    print(f"  q05 SE is the binomial floor on the noise in a single coverage number.")
    print(f"  Day clustering widens the real interval. The effect being chased is")
    print(f"  {HALVES_EFFECT_PP:.2f}pp, so read the earliest cut's column against that.")
    print()

    # ---- the guarantee that matters most, checked globally ----
    tw = [b["near"] | b["far"] for b in blocks]
    used = np.zeros(len(day), bool)
    for m in tw:
        used |= m
    n_protected = int((used & (day >= PROTECTED)).sum())
    print(f"  PROTECTED BLOCK AUDIT: rows scored here with day >= {PROTECTED}: "
          f"{n_protected}  (must be 0)")
    if n_protected:
        raise SystemExit("[ABORT] a cut's test window overlaps the block already scored.")
    overlap = sum(int((tw[i] & tw[j]).sum())
                  for i in range(len(tw)) for j in range(i + 1, len(tw)))
    print(f"  CUT OVERLAP AUDIT: rows shared between any two cuts' test windows: "
          f"{overlap}  (must be 0 at {SPACING_DAYS}-day spacing with "
          f"{2*HALF_DAYS}-day windows)")
    print()

    # ---- outcome overlap: measured, not argued ----
    print("  TRAIN/TEST OUTCOME OVERLAP, measured. An episode entered in the last hours")
    print("  before a cut has a 10.5-hour outcome window that reaches past it, so its")
    print("  target is partly shaped by near-half conditions. That contaminates the")
    print("  climatology estimate TOWARD the near half, which would shrink the near gap")
    print("  and inflate far-minus-near -- the exact direction of the hypothesis. So it")
    print("  is counted rather than reasoned away. Being unconditional does not make a")
    print("  sample estimate immune; it is the SIZE below that makes it immaterial.")
    for b in blocks:
        ntr = int(b["train"].sum())
        print(f"    {str(b['cut']):<12}{b['crossing']:>6} of {ntr:>7,} train rows "
              f"cross the cut   {100*b['crossing']/ntr:>6.3f}%")
    print("  No embargo is applied. At this magnitude it cannot move a quantile. For a")
    print("  CONDITIONAL model the same shortcut would not be safe -- the licence here")
    print("  is the count, not the model class.")
    print()
    print("  The HALVES ANALYSIS numbers, QUOTED from NUMBERS.md and not recomputed:")
    print(f"    cut 2026-07-18   near half {HALVES_NEAR_GAP_PP:.2f}pp   "
          f"far half {HALVES_FAR_GAP_PP:.2f}pp   effect {HALVES_EFFECT_PP:.2f}pp")
    print(f"    {HALVES_SIGNS}")
    print(f"    by horizon: {HALVES_BY_HORIZON}")
    print()

    # ---- the one table ----
    print("=" * 118)
    print("THE GAP TABLE -- mean |actual - nominal| over the 5 quantile points, in pp")
    print("=" * 118)
    print("  Day-clustered 95% intervals throughout: resample DAYS with replacement,")
    print("  not rows. Episodes share days and move together on market-wide news.")
    print("  sign: OVER = envelope too wide (actual coverage above nominal), UNDER =")
    print("  too narrow. The bracketed count is how many of the 5 levels miss that")
    print("  way, so a clean mean cannot hide a mixed pattern.")
    print("  far-near carries its own interval because the verdict rests on the")
    print("  ORDERING, not on either gap alone, and its WIDTH is what the power screen")
    print("  reads to decide whether a cut may vote.")
    print()
    hdr = (f"  {'cut':<12}{'dir':<5}{'h':>5}"
           f"{'near gap':>9}{'[95% CI]':>18}"
           f"{'far gap':>9}{'[95% CI]':>18}"
           f"{'far-near':>10}{'[95% CI]':>18}"
           f"{'near sign':>13}{'far sign':>13}")
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))

    rows = []
    for b in blocks:
        boot_n = day_boot(day[b["near"]])
        boot_f = day_boot(day[b["far"]])
        for direction in DIRECTIONS:
            for k in HORIZONS:
                y = targets[(direction, k)]
                qv = np.quantile(y[b["train"]], QUANTILES)     # climatology, fixed
                yn, yf = y[b["near"]], y[b["far"]]
                pn = np.tile(qv, (len(yn), 1))
                pf = np.tile(qv, (len(yf), 1))

                gn, gnl, gnh = gap_ci(yn, pn, boot_n)
                gf, gfl, gfh = gap_ci(yf, pf, boot_f)
                dd, ddl, ddh = gap_diff_ci(yn, pn, boot_n, yf, pf, boot_f)
                bn, _, _, on = bias_ci(yn, pn, boot_n)
                bf, _, _, of = bias_ci(yf, pf, boot_f)

                rows.append(dict(cut=str(b["cut"]), direction=direction, k=k,
                                 gn=gn, gf=gf, dd=dd, ddl=ddl, ddh=ddh,
                                 width=ddh - ddl, bn=bn, bf=bf, on=on, of=of))
                sn = f"{'OVER' if bn > 0 else 'UNDER'}[{on}/5]"
                sf = f"{'OVER' if bf > 0 else 'UNDER'}[{of}/5]"
                print(f"  {str(b['cut']):<12}{direction:<5}{HLABEL[k]:>5}"
                      f"{gn:>9.2f}{f'[{gnl:.2f},{gnh:.2f}]':>18}"
                      f"{gf:>9.2f}{f'[{gfl:.2f},{gfh:.2f}]':>18}"
                      f"{dd:>+10.2f}{f'[{ddl:+.2f},{ddh:+.2f}]':>18}"
                      f"{sn:>13}{sf:>13}", flush=True)
        print("  " + "-" * (len(hdr) - 2))
    print(f"  [{time.time()-t0:.0f}s]")
    print()

    # ---- precision screen, before any tally is read ----
    print("=" * 118)
    print("PRECISION -- which cuts are entitled to vote")
    print("=" * 118)
    print(f"  A cut is DECISIVE if the median width of its ten far-minus-near intervals")
    print(f"  is at or under {HALVES_EFFECT_PP:.2f}pp, the effect size from the halves")
    print(f"  analysis. Wider than the effect means the cut cannot resolve it either way.")
    print()
    print(f"  {'cut':<12}{'near/far rows':>16}{'median CI width':>18}{'status':>16}")
    decisive = {}
    for b in blocks:
        w = float(np.median([r["width"] for r in rows if r["cut"] == str(b["cut"])]))
        ok = w <= HALVES_EFFECT_PP
        decisive[str(b["cut"])] = ok
        nn, nf = int(b["near"].sum()), int(b["far"].sum())
        print(f"  {str(b['cut']):<12}{f'{nn:,}/{nf:,}':>16}{w:>16.2f}pp"
              f"{('DECISIVE' if ok else 'UNDERPOWERED'):>16}")
    n_dec = sum(decisive.values())
    print(f"  {n_dec} of {len(blocks)} cuts decisive.")
    print()

    # ---- verdict ----
    print("=" * 118)
    print("VERDICT ON RECURRENCE")
    print("=" * 118)
    print("  The rule, stated in the module docstring BEFORE any of the above was run:")
    print(VERDICT_RULE.format(eff=HALVES_EFFECT_PP))

    n = len(rows)
    orders = [r["dd"] > 0 for r in rows]
    orders_ci = [r["ddl"] > 0 for r in rows]
    sign_same = [np.sign(r["bn"]) == np.sign(r["bf"]) for r in rows]
    as_before = [(r["bn"] > 0 and r["bf"] > 0) if r["direction"] == "MAE"
                 else (r["bn"] < 0 and r["bf"] < 0) for r in rows]
    is_dec = [decisive[r["cut"]] for r in rows]

    # growth with horizon, per cut and half
    grows = []
    growth_lines = []
    for b in blocks:
        for direction in DIRECTIONS:
            for half in ("near", "far"):
                key = "gn" if half == "near" else "gf"
                g = [r[key] for r in rows
                     if r["cut"] == str(b["cut"]) and r["direction"] == direction]
                ok = g[-1] > g[0]
                grows.append(ok)
                growth_lines.append((str(b["cut"]), direction, half, g, ok))

    def tally(name, flags, subset=None):
        f = list(flags) if subset is None else [x for x, k in zip(flags, subset) if k]
        print(f"  {name:<36}{sum(f):>4} of {len(f):<4}{100*sum(f)/len(f):>7.1f}%")
        return sum(f) / len(f)

    print("  ALL CELLS")
    fr_ord = tally("ORDERS  far gap > near gap", orders)
    tally("ORDERS* interval excludes zero", orders_ci)
    fr_sign = tally("SIGN SAME  near and far agree", sign_same)
    tally("AS BEFORE  MAE over / MFE under", as_before)
    tally("GROWS  10h gap > 0.5h gap", grows)
    print()
    print("  DECISIVE CELLS ONLY")
    if n_dec:
        fr_ord_dec = tally("ORDERS  far gap > near gap", orders, is_dec)
        tally("ORDERS* interval excludes zero", orders_ci, is_dec)
        tally("SIGN SAME  near and far agree", sign_same, is_dec)
        tally("AS BEFORE  MAE over / MFE under", as_before, is_dec)
    else:
        fr_ord_dec = float("nan")
        print("  none -- every cut's interval is wider than the effect.")
    print()

    k_ord = sum(orders)
    p_chance = sum(math.comb(n, j) for j in range(k_ord, n + 1)) / 2 ** n
    print(f"  Against coin-flipping, {k_ord} of {n} or better has probability "
          f"{p_chance:.4f}. THIS IS NOT A P-VALUE: the 30 cells")
    print(f"  are not independent -- MAE and MFE share episodes and the horizons are")
    print(f"  nested running maxima. It says only how strict the 70% threshold is.")
    print()

    print("  GROWTH WITH HORIZON -- the other half of the shape. At 2026-07-18 the gap")
    print(f"  barely moved on the near half and more than tripled on the far one:")
    print(f"  {HALVES_BY_HORIZON}. Quoted, not recomputed.")
    print()
    print(f"  {'cut':<12}{'dir':<5}{'half':>6}" +
          "".join(f"{HLABEL[k]:>9}" for k in HORIZONS) + f"{'10h/0.5h':>11}{'grows':>8}")
    for cut, direction, half, g, ok in growth_lines:
        ratio = g[-1] / g[0] if g[0] > 0 else float("nan")
        print(f"  {cut:<12}{direction:<5}{half:>6}" +
              "".join(f"{v:>9.2f}" for v in g) +
              f"{ratio:>10.2f}x{('yes' if ok else 'NO'):>8}")
    print()

    print(f"  {'cut':<12}{'status':>14}{'ORDERS':>9}{'SIGN SAME':>12}"
          f"{'AS BEFORE':>12}{'votes yes':>12}")
    votes = []
    for b in blocks:
        c = str(b["cut"])
        ix = [i for i, r in enumerate(rows) if r["cut"] == c]
        o = sum(orders[i] for i in ix)
        s = sum(sign_same[i] for i in ix)
        a = sum(as_before[i] for i in ix)
        if decisive[c]:
            v = o >= 7
            votes.append(v)
            vs = "YES" if v else "no"
        else:
            vs = "abstains"
        print(f"  {c:<12}{('DECISIVE' if decisive[c] else 'UNDERPOWERED'):>14}"
              f"{f'{o}/{len(ix)}':>9}{f'{s}/{len(ix)}':>12}{f'{a}/{len(ix)}':>12}{vs:>12}")
    print()

    # the sign pattern must not flip BETWEEN cuts
    flips = []
    for direction in DIRECTIONS:
        signs = set()
        for b in blocks:
            sub = [r for r in rows if r["cut"] == str(b["cut"])
                   and r["direction"] == direction]
            over = sum(1 for r in sub if r["bf"] > 0)
            signs.add("over" if over > len(sub) / 2 else "under")
        if len(signs) > 1:
            flips.append(direction)
        print(f"  {direction} modal far-half sign across the {len(blocks)} cuts: "
              f"{', '.join(sorted(signs))}"
              f"{'   <- FLIPS between cuts' if len(signs) > 1 else ''}")
    print()

    majority = n_dec >= 2 and sum(votes) > n_dec / 2
    pooled_ok = fr_ord >= 0.70
    dec_ok = n_dec >= 2 and fr_ord_dec >= 0.70
    recurs = pooled_ok and dec_ok and fr_sign >= 0.70 and majority
    specific = (n_dec >= 2 and fr_ord_dec <= 0.50) or bool(flips)
    disagree = n_dec >= 2 and (pooled_ok != (fr_ord_dec >= 0.70))

    if n_dec < 2:
        verdict = "UNDERPOWERED -- NO VERDICT"
        reading = ("Fewer than two cuts can resolve the effect, so the design cannot\n"
                   "  deliver a majority and no claim about recurrence is made. Either\n"
                   "  accept cuts later in history only, or accept a smaller effect size\n"
                   "  as the thing being tested. Do not read the pooled tally as an answer.")
    elif specific:
        verdict = "CALENDAR-SPECIFIC"
        reading = ("The 2026-07-18 finding looks specific to that stretch. A simpler fix\n"
                   "  -- periodic refitting on a fixed schedule, no adaptive machinery --\n"
                   "  is probably enough.")
    elif disagree:
        verdict = "MIXED -- pooled and decisive-only tallies disagree"
        reading = ("The thin cut and the precise cuts point different ways, which is the\n"
                   "  case the precision screen exists to catch. Prefer the simpler fix:\n"
                   "  periodic refitting on a fixed schedule.")
    elif recurs:
        verdict = "RECURS"
        reading = ("The drift is a structural property of the envelope's level moving\n"
                   "  away from ANY fixed training window, not a feature of one calendar\n"
                   "  stretch. An adaptive correction is worth building.")
    else:
        verdict = "MIXED"
        reading = ("The shape appears but not reliably enough to call structural. Prefer\n"
                   "  the simpler fix: periodic refitting on a fixed schedule. An adaptive\n"
                   "  correction is not justified by this table.")

    print(f"  VERDICT: {verdict}")
    print(f"  {reading}")
    print()
    print("  NO PASS/FAIL AND NO SKILL NUMBER. Climatology has nothing to be scored")
    print("  against but itself, and the screen in the first envelope run is a binary")
    print("  that cannot separate a 1pp gap from a 5pp one. This table is the output.")
    print()
    print(f"  [{time.time()-t0:.0f}s]  next: paste the gap table into NUMBERS.md, "
          f"rows tagged by cut date")
    print("=" * 118)


if __name__ == "__main__":
    main()
