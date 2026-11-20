"""HL-TARGET2 synthetic proofs for s2_target_lib.py and the build's ordering. Each proof has a BROKEN variant that must fail (so the proof can fail). No data file is read.
Run: python s2_target_tests.py > s2_target_tests.log   (prints PASS lines; any assertion error is a failure)
"""
import hashlib
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import s2_target_lib as L  # noqa: E402

KW = L.KW


def log(m):
    print(m, flush=True)


def win(n=1, a=3.0, b=0.0):
    """n identical windows: leg a at log level a, leg b at b (beta = 1, alpha = mu = 0, sigma = 1, s = +1 -> P = a - b)"""
    return np.full((n, KW), a), np.full((n, KW), b)


ONE = (np.array([1.0]), np.array([1.0]), np.array([0.0]), np.array([0.0]), np.array([1.0]))     # s, beta, alpha, mu, sigma


def test_fill_limit():
    W = np.full((1, 20), np.nan)
    W[0, 0] = 5.0
    W[0, 8] = 7.0
    f = L.ffill_limited(W, 5)[0]
    assert np.allclose(f[0:6], 5.0) and np.isnan(f[6]) and np.isnan(f[7]) and f[8] == 7.0, f
    broken = L.ffill_limited(W, 7)[0]
    assert np.isfinite(broken[6]), "broken variant (limit 7) should fill minute 6"
    log("PASS fill limit: 5 missing minutes after a real mid are filled, the 6th and 7th are not (broken variant, limit 7, fills them)")


def test_exit_price_is_real_and_not_later_than_needed():
    # leg b has no real mid at k = 4 and 5; leg a drops through mu at k = 4 (real). Filled b = old value -> trigger at 4; exit stamp must be the first minute with BOTH real (k = 6), not the filled minute 4.
    A, B = win(1, 3.0, 0.0)
    A[0, 4:] = -1.0
    B[0, 4:6] = np.nan
    B[0, 6:] = 0.5
    o = L.scan_paths(A, B, *ONE)
    assert o["status"][0] == L.OK and o["trigger_k"][0] == 4 and o["exit_k"][0] == 6, o
    # broken variant: exit at the trigger minute (filled price) would be k = 4
    assert o["exit_k"][0] != o["trigger_k"][0]
    log("PASS exit price: trigger on the filled path at k=4, exit stamp is the first minute with both REAL mids (k=6); a filled minute never supplies the exit price (broken variant 'exit at the trigger' = 4 differs)")


def test_exit_cap_and_status():
    A, B = win(4, 3.0, 0.0)
    A[:, 4:] = -1.0
    B[0, 4:4 + 61] = np.nan             # no real b for 61 minutes after the trigger -> cap
    B[1, 4:4 + 60] = np.nan             # real again exactly 60 minutes after the trigger -> ok
    A[2, 0] = np.nan                    # entry missing
    B[3, 600] = np.nan                  # control
    o = L.scan_paths(A, B, np.ones(4), np.ones(4), np.zeros(4), np.zeros(4), np.ones(4))
    assert o["status"][0] == L.NO_EXIT_CAP, o["status"]
    assert o["status"][1] == L.OK and o["exit_k"][1] == 64, (o["status"][1], o["exit_k"][1])
    assert o["status"][2] == L.NO_ENTRY and o["trigger_k"][2] == -1 and not o["gap_flag"][2]
    assert o["status"][3] == L.OK
    log("PASS exit cap: 61 minutes without both real mids after the trigger -> no_exit_mid_cap; exactly 60 -> ok at k=64; entry mid missing -> no_entry_mid")


def test_timeout_and_no_exit():
    A, B = win(2, 3.0, 0.0)                # never reaches mu
    B[1, 596:] = np.nan                    # b missing from 596: filled for 5 minutes (596..600 -> k=596 real? 596 missing) -> filled until 600 only if <= 5 after last real (595)
    o = L.scan_paths(A, B, np.ones(2), np.ones(2), np.zeros(2), np.zeros(2), np.ones(2))
    assert o["status"][0] == L.OK and o["exit_reason"][0] == L.REASON_TIMEOUT and o["trigger_k"][0] == 600 and o["exit_k"][0] == 600
    assert o["status"][1] in (L.OK, L.NO_EXIT_CAP) and o["trigger_k"][1] == 600       # filled at 600 (5th missing minute) -> timeout trigger; exit price needs a real mid within 60
    B2 = B.copy()
    B2[1, 595:] = np.nan                   # 6th missing minute at 600 is not filled -> no timeout trigger
    o2 = L.scan_paths(A, B2, np.ones(2), np.ones(2), np.zeros(2), np.zeros(2), np.ones(2))
    assert o2["status"][1] == L.NO_EXIT and o2["trigger_k"][1] == -1, o2["status"]
    log("PASS timeout: no mu in 600 minutes -> trigger 600 (reason timeout); a mid filled at 600 (5th missing minute) still triggers; a 6th missing minute at 600 -> no_exit_mid")


def test_flags_leg_vs_union():
    A, B = win(1, 3.0, 0.0)
    A[0, 10:] = -1.0
    A[0, 1:5] = np.nan                      # a missing 1..4
    B[0, 5:9] = np.nan                      # b missing 5..8 -> union run 1..8, per-leg longest 4
    o = L.scan_paths(A, B, *ONE)
    assert o["status"][0] == L.OK and o["trigger_k"][0] == 10
    assert o["max_gap_len_leg"][0] == 4 and not o["gap_flag"][0], o
    assert o["max_gap_len_union"][0] == 8 and o["gap_flag_union"][0], o
    A2, B2 = A.copy(), B.copy()
    A2[0, 1:7] = np.nan                     # a missing 6 minutes -> per-leg flag
    o2 = L.scan_paths(A2, B2, *ONE)
    assert o2["max_gap_len_leg"][0] >= 6 and o2["gap_flag"][0]
    # broken variant: a flag built from the union would flag the first event
    assert o["gap_flag_union"][0] != o["gap_flag"][0]
    log("PASS flags: a 1-4 and b 5-8 missing -> per-leg longest 4 (not flagged), union 8 (flagged, sensitivity only); a 6-minute own gap is flagged (broken variant 'flag = union' disagrees on the first event)")


def test_gap_scan_stops_at_kend():
    miss = np.zeros((2, KW), bool)
    miss[:, 8:15] = True
    mx, runs = L.gap_scan(miss, np.array([10, 20]))
    assert mx[0] == 3 and mx[1] == 7, mx          # row 0: run 8..10 counted up to kend only
    log("PASS gap scan: a run is counted only up to k_x (run 8..14, k_x = 10 -> 3; k_x = 20 -> 7)")


def fuzz(n=30000, seed=1):
    rng = np.random.default_rng(seed)
    A = np.cumsum(rng.normal(0, 0.05, (n, KW)), axis=1) + 3.0
    B = np.cumsum(rng.normal(0, 0.05, (n, KW)), axis=1)
    for X in (A, B):
        miss = rng.random((n, KW)) < 0.04
        burst = rng.random((n, 1)) < 0.2
        st = rng.integers(0, KW - 12, (n, 1))
        ln = rng.integers(1, 12, (n, 1))
        k = np.arange(KW)[None, :]
        miss |= burst & (k >= st) & (k < st + ln)
        X[miss] = np.nan
    A[rng.random(n) < 0.03, 0] = np.nan
    return A, B


def test_fuzz_invariants():
    A, B = fuzz()
    n = len(A)
    args = (np.ones(n), np.ones(n), np.zeros(n), np.zeros(n), np.ones(n))
    o = L.scan_paths(A, B, *args)
    both = np.isfinite(A) & np.isfinite(B)
    ok = o["status"] == L.OK
    assert ok.sum() > 1000 and (o["status"] == L.NO_ENTRY).sum() > 100
    kx, tk = o["exit_k"][ok], o["trigger_k"][ok]
    assert (both[ok][np.arange(ok.sum()), kx]).all(), "an exit stamp without two real mids"
    assert (kx >= tk).all() and (kx - tk <= 60).all()
    for j in np.flatnonzero(ok)[:3000]:
        k0, k1 = o["trigger_k"][j], o["exit_k"][j]
        assert not both[j, k0:k1].any(), "an earlier real minute was skipped"
    log(f"PASS fuzz (30,000 random windows with gaps; {int(ok.sum()):,} ok): every exit stamp has two real mids, exit_k - trigger_k in 0..60, no earlier real minute skipped")
    # poison: overwrite all mids stamped after k_trig -> trigger and reason unchanged
    cand = ok | (o["status"] == L.NO_EXIT_CAP)
    p = L.scan_paths(A[cand], B[cand], *(a[cand] for a in args), kmax_visible=o["trigger_k"][cand])
    assert (p["trigger_k"] == o["trigger_k"][cand]).all() and (p["exit_reason"] == o["exit_reason"][cand]).all()
    log(f"PASS poison receipt on {int(cand.sum()):,} windows: with every mid after k_trig overwritten, trigger_k and exit_reason are unchanged")
    # BROKEN variant: a trigger from a BACKWARD fill (uses the next real mid) must fail the same poison test on some rows
    def leaky_trigger(A_, B_):
        Ar = np.flip(L.ffill_limited(np.flip(A_, 1)), 1)
        Br = np.flip(L.ffill_limited(np.flip(B_, 1)), 1)
        P = Ar - Br
        hit = P[:, 1:L.K_TRIG + 1] <= 0
        return np.where(hit.any(1), hit.argmax(1) + 1, L.K_TRIG)
    base = leaky_trigger(A[cand], B[cand])
    kv = o["trigger_k"][cand]
    late = np.arange(KW)[None, :] > kv[:, None]
    pois = leaky_trigger(np.where(late, np.nan, A[cand]), np.where(late, np.nan, B[cand]))
    assert (pois != base).any(), "the poison test cannot detect a leaky (backward-filled) trigger"
    log(f"PASS poison test has teeth: a backward-filled trigger changes on {int((pois != base).sum()):,} of the same windows when later mids are overwritten")


def test_stops():
    L.check_stops(1000, 10, 100)                       # exactly 1% and exactly 10%: no stop (rule: MORE than)
    for args, what in (((1000, 11, 0), "cap"), ((1000, 0, 101), "flag")):
        try:
            L.check_stops(*args)
        except L.StopBuild as e:
            assert what in str(e) or ("cap" in str(e) if what == "cap" else "gap_flag" in str(e))
        else:
            raise AssertionError(f"the {what} stop did not fire")
    log("PASS stops: 1.1% cap drops -> StopBuild; 10.1% per-leg flags -> StopBuild; exactly 1% / 10% pass")
    src = open(os.path.join(HERE, "s2_target_build.py")).read()
    i_stop = src.index("L.check_stops(n_test, n_cap, n_flag)")
    i_y = src.index("Y, status = stage2(")
    assert i_stop < i_y, "the stop check must come before any y component"
    assert "n_flag = int((tm & R[\"gap_flag\"]).sum())" in src and "n_flag = int((tm & R[\"gap_flag_union" not in src, "the stop must read the per-leg flag"
    assert "sys.exit(2)" in src[i_stop:i_stop + 400]
    no_y_print = [m.group(0) for m in re.finditer(r"log\(f?\"[^\n]*(?:y_taker|gross_bp)[^\n]*", src)]
    assert not no_y_print, f"a log line mentions y_taker or gross_bp: {no_y_print}"
    log("PASS build order: check_stops (per-leg gap_flag, sys.exit(2) on a stop) comes before stage2 (the first y component); no log line prints y_taker or gross_bp")


def test_hs_lookup():
    nc, nm = 2, 3000
    HS = np.full((nc, nm), np.nan, np.float32)
    CR = np.zeros((nc, nm), bool)
    HS[0, 100] = 2.0                         # own
    HS[0, 199] = 3.0
    HS[0, 201] = 9.0                         # both neighbours of 200 exist: -1 wins (earlier)
    HS[0, 301] = 4.0                         # only +1 of 300
    CR[0, 500] = True                        # crossed at 500; no neighbours -> median
    mon = np.zeros(nm, np.int16)
    med = np.array([[5.0], [np.nan]])
    absent = np.zeros(nm, bool)
    absent[700:] = True
    q = np.array([100, 200, 300, 500, 800, 100])
    ci = np.array([0, 0, 0, 0, 0, 1])
    v, mode, cause = L.lookup_hs(HS, CR, ci, q, mon, med, absent)
    assert v[:5].tolist() == [2.0, 3.0, 4.0, 5.0, 5.0], v
    assert mode.tolist() == [0, 1, 1, 2, 2, 3], mode
    assert cause.tolist() == [0, 2, 2, 3, 1, 2], cause
    assert np.isnan(v[5])
    log("PASS half-spread lookup: own / earlier neighbour wins a tie / later neighbour / coin-month median with cause crossed and day-absent / none (NaN) for a coin-month without a row")


def test_funding_and_gross():
    hrs = 30
    FR = np.full((1, hrs), np.nan)
    FR[0, 3], FR[0, 4], FR[0, 6] = 0.001, 0.002, 0.004          # hour 5 missing
    CS = np.zeros((1, hrs + 1))
    CM = np.zeros((1, hrs + 1), np.int32)
    CS[:, 1:] = np.cumsum(np.nan_to_num(FR), axis=1)
    CM[:, 1:] = np.cumsum(np.isnan(FR), axis=1)
    has = np.array([True])
    ia = ib = np.array([0])
    f, mh = L.funding_bp(CS, CM, has, ia, ib, np.array([3]), np.array([6]), np.array([0.5]), np.array([0.5]), np.array([-1.0]), np.array([1.0]))
    # leg a short pays -(-1) x rate x 0.5 ... flow = -dir x rate x w: a: +1 x 0.007 x 0.5, b: -1 x 0.007 x 0.5 -> cancel to 0 (same coin both legs, opposite dir)
    assert abs(f[0]) < 1e-9 and mh[0] == 2, (f, mh)
    f2, _ = L.funding_bp(CS, CM, np.array([True]), ia, ib, np.array([3]), np.array([4]), np.array([1.0]), np.array([0.0]), np.array([1.0]), np.array([1.0]))
    assert abs(f2[0] - (-1e4 * (0.001 + 0.002))) < 1e-9, f2          # long leg pays the positive rate
    f3, _ = L.funding_bp(CS, CM, np.array([False]), ia, ib, np.array([3]), np.array([4]), np.array([1.0]), np.array([0.0]), np.array([1.0]), np.array([1.0]))
    assert f3[0] == 0.0
    g, wxa, wxb = L.gross_bp(0.5, 0.5, -1.0, 1.0, 0.0, np.log(1.01), 0.0, np.log(1.01))
    assert abs(g - 0.0) < 1e-9 and abs(wxa - 0.505) < 1e-12
    g2, _, _ = L.gross_bp(0.5, 0.5, -1.0, 1.0, 0.0, np.log(1.01), 0.0, np.log(1.03))
    assert abs(g2 - 1e4 * 0.5 * (0.03 - 0.01)) < 1e-6, g2
    log("PASS funding and gross arithmetic: boundaries h1..h2 inclusive, missing hours counted and paid nothing, long leg pays a positive rate, no file -> 0; two-leg gross and exit weights as in rules section 4")


if __name__ == "__main__":
    log(f"[S2TESTS] sha256 lib {hashlib.sha256(open(HERE + '/s2_target_lib.py', 'rb').read()).hexdigest()[:12]} build {hashlib.sha256(open(HERE + '/s2_target_build.py', 'rb').read()).hexdigest()[:12]} tests {hashlib.sha256(open(__file__, 'rb').read()).hexdigest()[:12]}")
    for fn in (test_fill_limit, test_exit_price_is_real_and_not_later_than_needed, test_exit_cap_and_status, test_timeout_and_no_exit, test_flags_leg_vs_union, test_gap_scan_stops_at_kend, test_fuzz_invariants, test_stops, test_hs_lookup, test_funding_and_gross):
        fn()
    log("[S2TESTS] all proofs passed")
