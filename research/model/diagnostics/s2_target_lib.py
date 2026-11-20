"""HL-TARGET2 label library (rules: research/model/s2_target_rules.md, which governs). Pure functions on arrays; no file is read here.
Used by s2_target_build.py (the build) and s2_target_tests.py (synthetic proofs, each with a broken variant that must fail).

Path windows: A, B = log real mid of leg a / leg b at stamps t0+k, k = 0..660 (NaN = no real mid). Width 661: the trigger scan uses k <= 600, the exit-price search k <= trigger + 60.
"""
import numpy as np

K_TRIG = 600          # last path minute that can trigger (the 10 h horizon)
KW = K_TRIG + 61      # window width 0..660
FILL_MAX = 5          # forward-fill of the PATH mid, at most this many consecutive missing minutes
EXIT_CAP = 60         # exit price search: first real mid at or after the trigger, at most this many minutes later
FEE_BP = 4.5          # taker fee per fill per leg, bp of the leg value
GAP_FLAG_MIN = 6      # flagged when a missing run is longer than 5 (>= 6)
RUN_EDGES = [1, 2, 3, 6, 11, 31]
RUN_NAMES = ["1", "2", "3-5", "6-10", "11-30", "31+"]
STOP_FLAG_SHARE = 0.10   # hard stop: share of TEST-MONTH events with gap_flag (per-leg) above this
STOP_CAP_SHARE = 0.01    # hard stop: share of TEST-MONTH events dropped by the 60-minute exit cap above this

OK, NO_ENTRY, NO_EXIT, NO_EXIT_CAP = 0, 1, 2, 3
STATUS_NAMES = {OK: "ok", NO_ENTRY: "no_entry_mid", NO_EXIT: "no_exit_mid", NO_EXIT_CAP: "no_exit_mid_cap"}
REASON_MU, REASON_TIMEOUT = 1, 2


class StopBuild(Exception):
    """a hard stop of the rules fired: report to the planner, build no label"""


def ffill_limited(W, lim=FILL_MAX):
    """forward-fill NaN with the last real value of the same row, for at most `lim` consecutive missing minutes after it. Uses only values at stamps <= k for output k."""
    m = W.shape[1]
    ar = np.arange(m)[None, :]
    last = np.maximum.accumulate(np.where(np.isfinite(W), ar, -1), axis=1)
    out = np.take_along_axis(W, np.maximum(last, 0), axis=1)
    return np.where((last >= 0) & (ar - last <= lim), out, np.nan)


def bucket_counts(lengths):
    lengths = np.asarray(lengths)
    if not len(lengths):
        return np.zeros(len(RUN_EDGES), np.int64)
    return np.bincount(np.searchsorted(RUN_EDGES, lengths, side="right") - 1, minlength=len(RUN_EDGES)).astype(np.int64)


def gap_scan(miss, kend):
    """miss: (n, KW) bool, True = no real mid. Runs of consecutive True over path minutes 1..kend (per row). Returns (longest run per row, run-length bucket counts).
    A run that reaches kend is closed at kend (it counts only up to kend)."""
    n = miss.shape[0]
    cur = np.zeros(n, np.int64)
    mx = np.zeros(n, np.int64)
    runs = np.zeros(len(RUN_EDGES), np.int64)
    for k in range(1, miss.shape[1]):
        active = k <= kend
        m = miss[:, k] & active
        ended = (cur > 0) & ~m
        if ended.any():
            runs += bucket_counts(cur[ended])
        cur = np.where(m, cur + 1, 0)
        mx = np.maximum(mx, cur)
    tail = cur > 0
    if tail.any():
        runs += bucket_counts(cur[tail])
    return mx, runs


def scan_paths(A, B, s, beta, alpha, mu, sigma, kmax_visible=None):
    """AVAILABILITY STAGE (no gross, no return, no y): entry check, trigger, exit stamp, status, gap runs and flags.
    A, B: (n, KW) log real mids. s = +1 if z >= 0 else -1. Trigger = first k in 1..600 with s*Pf[k] <= 0 on the forward-filled path Pf, else k = 600 (timeout) if both filled mids exist at 600.
    Exit stamp = first k_x in [trig, trig + 60] where BOTH legs have a REAL mid. The filled path decides the trigger only; the exit price is read at k_x from the real mids.
    kmax_visible (receipt only): if given, mids stamped after this per-row k are NOT used (set NaN), to prove the trigger does not depend on later mids."""
    n = A.shape[0]
    if kmax_visible is not None:
        late = np.arange(KW)[None, :] > kmax_visible[:, None]
        A = np.where(late, np.nan, A)
        B = np.where(late, np.nan, B)
    realA, realB = np.isfinite(A), np.isfinite(B)
    both = realA & realB
    Af, Bf = ffill_limited(A), ffill_limited(B)
    P = s[:, None] * ((Af - beta[:, None] * Bf - alpha[:, None] - mu[:, None]) / sigma[:, None])
    entry_ok = both[:, 0]
    hit = P[:, 1:K_TRIG + 1] <= 0                         # NaN compares False
    has_hit = hit.any(1)
    trig = np.where(has_hit, hit.argmax(1) + 1, K_TRIG)
    reason = np.where(has_hit, REASON_MU, REASON_TIMEOUT)
    trig_ok = has_hit | np.isfinite(P[:, K_TRIG])
    k = np.arange(KW)[None, :]
    win = both & (k >= trig[:, None]) & (k <= trig[:, None] + EXIT_CAP)
    has_x = win.any(1)
    kx = np.where(has_x, win.argmax(1), -1)
    status = np.where(~entry_ok, NO_ENTRY, np.where(~trig_ok, NO_EXIT, np.where(~has_x, NO_EXIT_CAP, OK))).astype(np.int8)
    kend = np.where(status == OK, kx, np.where(status == NO_EXIT_CAP, np.minimum(trig + EXIT_CAP, KW - 1), np.where(status == NO_EXIT, K_TRIG, 0)))
    trig = np.where((status == NO_ENTRY) | (status == NO_EXIT), -1, trig)       # no trigger exists for these
    mxA, rA = gap_scan(~realA, kend)
    mxB, rB = gap_scan(~realB, kend)
    mxU, rU = gap_scan(~both, kend)
    leg = np.maximum(mxA, mxB)
    in_trig = (k >= 1) & (k <= np.where(trig > 0, trig, 0)[:, None])
    n_filled = ((np.isfinite(Af) & ~realA) & in_trig).sum(1) + ((np.isfinite(Bf) & ~realB) & in_trig).sum(1)
    z0 = P[:, 0]
    return dict(status=status, trigger_k=trig.astype(np.int32), exit_k=np.where(status == OK, kx, -1).astype(np.int32), exit_reason=np.where(trig < 0, 0, reason).astype(np.int8),
                max_gap_len_leg=leg.astype(np.int32), gap_flag=(leg >= GAP_FLAG_MIN) & (status != NO_ENTRY),
                max_gap_len_union=mxU.astype(np.int32), gap_flag_union=(mxU >= GAP_FLAG_MIN) & (status != NO_ENTRY),
                n_filled=n_filled.astype(np.int32), z0_mid=z0, runs_leg=rA + rB, runs_union=rU)


def check_stops(n_test, n_cap, n_flag):
    """the two hard stops, on TEST-MONTH events (denominator: all test-month events). Raises StopBuild; the build writes no label after it."""
    msgs = []
    if n_test and n_cap / n_test > STOP_CAP_SHARE:
        msgs.append(f"60-minute exit-cap drops {n_cap:,} of {n_test:,} test-month events = {100 * n_cap / n_test:.2f}% > {100 * STOP_CAP_SHARE:.0f}%")
    if n_test and n_flag / n_test > STOP_FLAG_SHARE:
        msgs.append(f"per-leg gap_flag {n_flag:,} of {n_test:,} test-month events = {100 * n_flag / n_test:.2f}% > {100 * STOP_FLAG_SHARE:.0f}%")
    if msgs:
        raise StopBuild("; ".join(msgs))


def lookup_hs(HS, CR, ci, q, month_idx_of_minute, med, absent_minute):
    """half-spread (bp) of coin ci at minute index q. HS: float32 (coin, minute) half-spread, NaN = no usable G8 row (absent or crossed). CR: bool crossed row.
    Order: own minute; else the minute before; else the minute after (nearest within +-1, closer first, earlier on a tie); else the coin's median over the same calendar month; else NaN (event dropped, no_spread).
    Returns hs, mode (0 own, 1 shifted +-1, 2 median, 3 none), cause (0 none; 1 day file absent, 2 minute absent, 3 crossed: cause at the OWN stamp)."""
    v0, vm, vp = HS[ci, q], HS[ci, q - 1], HS[ci, q + 1]
    own = np.isfinite(v0)
    shifted = ~own & (np.isfinite(vm) | np.isfinite(vp))
    val = np.where(own, v0, np.where(np.isfinite(vm), vm, vp))
    md = med[ci, month_idx_of_minute[q]]
    use_med = ~own & ~shifted & np.isfinite(md)
    val = np.where(use_med, md, val)
    mode = np.where(own, 0, np.where(shifted, 1, np.where(use_med, 2, 3))).astype(np.int8)
    cause = np.where(own, 0, np.where(absent_minute[q], 1, np.where(CR[ci, q], 3, 2))).astype(np.int8)
    return val.astype(np.float64), mode, cause


def gross_bp(wa, wb, dir_a, dir_b, la0, la1, lb0, lb1):
    """two-leg gross at the given log prices (entry 0, exit 1), bp of N = 1; also the exit leg weights"""
    ra, rb = np.exp(la1 - la0) - 1.0, np.exp(lb1 - lb0) - 1.0
    return 1e4 * (wa * dir_a * ra + wb * dir_b * rb), wa * (1.0 + ra), wb * (1.0 + rb)


def funding_bp(CS, CM, has_file, ia, ib, h1, h2, wa, wb, dir_a, dir_b):
    """funding, bp of N. CS[c, j] = sum of the hourly rates of hour index < j (missing hours count 0), CM likewise counts missing hours. Boundaries H with h1 <= H <= h2.
    flow = -dir x rate x entry leg value, summed over legs and hours (positive = received). A coin without a file gives 0 for that leg."""
    out = np.zeros(len(ia))
    miss_h = np.zeros(len(ia), np.int64)
    for ci, w, d in ((ia, wa, dir_a), (ib, wb, dir_b)):
        sr = CS[ci, h2 + 1] - CS[ci, h1]
        mh = CM[ci, h2 + 1] - CM[ci, h1]
        f = has_file[ci]
        out += np.where(f, -d * sr * w, 0.0)
        miss_h += np.where(f, mh, 0)
    return 1e4 * out, miss_h
