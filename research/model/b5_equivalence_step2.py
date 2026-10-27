"""HL-MODEL1 B5 Step 2, step (i): bitwise before/after on the CURRENT 1,093-column input list (planner
ruling 2026-10-27: run this BEFORE the input-list revision that drops a_coin_code/b_coin_code, so the
equivalence proof is clean against the list B2/B3/B4 already passed on).

    python -u research/model/b5_equivalence_step2.py > research/model/logs/b5_equivalence_step2.log

Compares OLD (research/model/_frozen_harness_pre_b5step2.py, a byte-identical git snapshot of harness.py
at commit 955469b, sha256 c06484599c879d050f30af898aaf078f754266208f29f3a82c2580f51c75548a -- NOT a
hand-retyped copy, extracted on the laptop with `git show` and verified against that sha before this
script was written; the VM has no .git directory (excluded from scripts/gcp_run.sh's sync), so it travels
up as a plain file like any other script and is DELETED from the laptop repo once this step passes --
checker's point, round 1: a parallel copy of harness.py is an accumulation git already keeps at 955469b,
so it does not persist as a committed file) against NEW (research/model/harness.py, with B5 Step 2's
three changes: MF.verify cached per process and keyed to the MANIFEST.json sha (asserted on every later
call, not trusted blindly -- checker's fix, round 1), per-file reads run in a thread pool, and
ticker_a/ticker_b mapped through a fixed sorted(coins.csv) code instead of per-call pd.factorize).

SCOPE (checker's point, round 1): only load_features, load_fold_features, _verify_once and _coin_code_map
are new or changed -- confirmed by a direct diff against the committed c0648459 version before this script
was written. build_folds, load_search_events, score_fold, day_block_bootstrap, build_hazard_rows,
check_inputs, assert_search_only and every date/fold constant are byte-identical, so they are NOT
independently re-tested here; B5's step (iv) (the B3 proof rerun) is what covers them.

PROOF 1: every non-ticker column of load_features's output is IDENTICAL (via columns_match, below) between
OLD and NEW, on fold 7 (largest) and fold 0 (smallest), using each fold's train+val+test ids combined.
PROOF 2: the two ticker columns are NOT required to match OLD (old codes are per-call factorize, with no
stable meaning across calls or folds) -- instead: (a) NEW's codes are checked against an INDEPENDENTLY
computed ground truth (sorted(coins.csv) index of the raw ticker string, read directly from events.parquet,
not through either load_features implementation), and against a_coin_code/b_coin_code (g4.parquet, read
directly); (b) a PARTITION check (checker's point, round 1): grouping rows by OLD's factorize code and by
NEW's fixed code must give the SAME partition of rows (every old-code group maps to exactly one new-code
group and vice versa) -- OLD's codes differ in VALUE from NEW's by construction (factorize is call-
arbitrary), but both must agree on WHICH rows share a ticker; (c) the null count of ticker_a/ticker_b in
the tested ids is logged and must be 0 (explains why the old factorize's -1-for-null code never arises
here).
PROOF 3: load_fold_features(fold, cols) (the new 'load each fold once' helper) gives EXACTLY the same
X_train/X_val/X_test (via columns_match) as calling load_features three times separately on
fold['train_ids'], ['val_ids'], ['test_ids'].
PROOF 4 (verify-once): (a) MF.verify is called 0 times on 2 more load_features calls after a warm-up call
(cached per process); (b) FAILING VARIANT (checker's point, round 1: a dead counter would also "pass" at
0): _VERIFIED_FILES is cleared and load_features is called once more -- the counter must then read the
real per-file count (15, the group files the full 1,093-column list touches), proving the counter itself
is alive; (c) FAILING VARIANT for the manifest-sha keying (checker's blocking fix, round 1): one cached
manifest sha in _VERIFIED_FILES is corrupted, and the next load_features call for that file must RAISE
(AssertionError), proving a stale cached verify is caught, not trusted.

BROKEN VARIANT, shared comparison function (checker's point, round 1: PROOF 1 had none, and PROOF 3 should
reuse the same logic): columns_match() backs PROOF 1 and PROOF 3; a copy of a real X with ONE cell changed
in a non-ticker column must make columns_match report that column as mismatched.
BROKEN VARIANT, ticker tamper (checker's point, round 1: the original picked the alphabetically-first coin,
which may not appear in the tested ids at all -- picks the MOST FREQUENT ticker_a in the tested ids
instead, logs how many rows it affects, and asserts that count is > 0): a tampered ticker-code map (that
coin's code shifted by +1) must make PROOF 2's ground-truth check FAIL.

CACHE-STATE NOTE (checker's point, round 1): any load_s printed here is NOT a valid before/after speed
comparison -- NEW always runs right after OLD has just warmed the page cache for the exact same files and
columns. The real before/after timing table, with matched cache states, is Step 3's job.

MEMORY (checker's round-2 OOM finding): fold 7's X_old/X_new are 23.4 GB EACH. The first version of this
script returned them from proof_1_and_2 into main()'s locals, which stayed alive through proof_3 (which
itself builds up to 4 more full-size matrices) -- about 94 GB plus baseline on a 62 GB VM with no swap,
an OOM kill partway through fold 7. Fixed: proof_1_and_2 and proof_3 each `del` their own matrices and
gc.collect() before returning; only (all_ids, ev) -- small -- survive into main(). VmHWM is reset
(clear_peak_rss) before each proof and read after, so the receipt shows the real peak per proof, not a
lifetime high-water mark (same /proc/self/clear_refs methodology as b5_profile.py, reused via import, not
redefined).
"""
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as NEW  # noqa: E402
import _frozen_harness_pre_b5step2 as OLD  # noqa: E402
from b5_profile import rss_gb, clear_peak_rss  # noqa: E402 -- checker-approved memory helpers, reused not redefined

PASS = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    PASS.append(cond)
    print(f"[B5-EQUIV] {name}: {status}" + (f" -- {detail}" if detail else ""), flush=True)
    return cond


def load_in_cols():
    import csv
    rows = list(csv.DictReader(open(os.path.join(HERE, "inputs_v1_pair.csv"))))
    return [r["column"] for r in rows if r["in_out"] == "IN"]


def columns_match(X_a, X_b, in_cols, skip=("ticker_a", "ticker_b")):
    """Shared by PROOF 1, PROOF 3 and the broken variant (checker's point, round 1): every column NOT in
    `skip` must be bitwise identical (np.array_equal, equal_nan=True), same dtype. Returns (ok, [bad cols])."""
    if X_a.dtype != X_b.dtype:
        return False, ["<dtype mismatch>"]
    mismatches = [c for j, c in enumerate(in_cols) if c not in skip
                  and not np.array_equal(X_a[:, j], X_b[:, j], equal_nan=True)]
    return len(mismatches) == 0, mismatches


def ground_truth_ticker_codes(event_ids):
    """Independent of BOTH load_features implementations: reads ticker_a/ticker_b and a_coin_code/
    b_coin_code directly from parquet via master_manifest, computes sorted(coins.csv) codes by hand."""
    import master_manifest as MF
    import pandas as pd
    ev = MF.open_version(NEW.VERSION, NEW.UNIT, "events.parquet", columns=["event_id", "ticker_a", "ticker_b"])
    g4 = MF.open_version(NEW.VERSION, NEW.UNIT, "g4.parquet", columns=["event_id", "a_coin_code", "b_coin_code"])
    ev = ev.set_index("event_id").loc[event_ids]
    g4 = g4.set_index("event_id").loc[event_ids]
    coins_all = sorted(pd.read_csv(NEW.COINS_CSV).coin.tolist())
    code_map = {c: i for i, c in enumerate(coins_all)}
    gt_a = ev["ticker_a"].map(code_map).to_numpy(dtype=np.float32)
    gt_b = ev["ticker_b"].map(code_map).to_numpy(dtype=np.float32)
    return ev, gt_a, gt_b, g4["a_coin_code"].to_numpy(dtype=np.float32), g4["b_coin_code"].to_numpy(dtype=np.float32)


def partition_matches(old_codes, new_codes):
    """checker's point, round 1: OLD (factorize) and NEW (fixed) codes must induce the SAME partition of
    rows, even though the VALUES differ by construction. True iff old_codes[i]==old_codes[j] <=>
    new_codes[i]==new_codes[j] for all i, j -- checked by grouping: every distinct old code must map to
    exactly one distinct new code, and vice versa."""
    import pandas as pd
    df = pd.DataFrame({"old": old_codes, "new": new_codes})
    old_to_new = df.groupby("old")["new"].nunique()
    new_to_old = df.groupby("new")["old"].nunique()
    return bool((old_to_new == 1).all()) and bool((new_to_old == 1).all())


def proof_1_and_2(fold, in_cols, label):
    f = fold
    all_ids = np.concatenate([f["train_ids"], f["val_ids"], f["test_ids"]])
    t0 = time.time()
    X_old, cols_old = OLD.load_features(all_ids, in_cols)
    t_old = time.time() - t0
    t0 = time.time()
    X_new, cols_new = NEW.load_features(all_ids, in_cols)
    t_new = time.time() - t0
    print(f"[B5-EQUIV] {label}: n={len(all_ids):,} n_cols={len(in_cols)} "
          f"old_load_s={t_old:.1f} new_load_s={t_new:.1f} "
          f"(CACHE-BIASED, not a before/after timing -- NEW ran right after OLD warmed the page cache for "
          f"these exact columns; Step 3 does the real timing with matched cache states)", flush=True)
    check(f"{label}: column order identical", cols_old == cols_new)

    ok1, bad1 = columns_match(X_old, X_new, in_cols)
    check(f"{label}: PROOF 1 -- every non-ticker column identical OLD vs NEW ({len(in_cols)-2} columns)",
          ok1, f"mismatches: {bad1}" if bad1 else "")

    ev, gt_a, gt_b, a_coin_code, b_coin_code = ground_truth_ticker_codes(all_ids)
    n_null_a, n_null_b = int(ev["ticker_a"].isna().sum()), int(ev["ticker_b"].isna().sum())
    check(f"{label}: PROOF 2c -- null ticker_a/ticker_b count is 0", n_null_a == 0 and n_null_b == 0,
          f"null_a={n_null_a} null_b={n_null_b}")

    j_a, j_b = in_cols.index("ticker_a"), in_cols.index("ticker_b")
    ok_a_gt = np.array_equal(X_new[:, j_a], gt_a)
    ok_b_gt = np.array_equal(X_new[:, j_b], gt_b)
    ok_a_g4 = np.array_equal(X_new[:, j_a], a_coin_code)
    ok_b_g4 = np.array_equal(X_new[:, j_b], b_coin_code)
    check(f"{label}: PROOF 2a -- NEW ticker_a matches independent sorted(coins.csv) ground truth", ok_a_gt)
    check(f"{label}: PROOF 2a -- NEW ticker_b matches independent sorted(coins.csv) ground truth", ok_b_gt)
    check(f"{label}: PROOF 2a -- NEW ticker_a matches a_coin_code (g4.parquet)", ok_a_g4)
    check(f"{label}: PROOF 2a -- NEW ticker_b matches b_coin_code (g4.parquet)", ok_b_g4)

    part_a = partition_matches(X_old[:, j_a], X_new[:, j_a])
    part_b = partition_matches(X_old[:, j_b], X_new[:, j_b])
    check(f"{label}: PROOF 2b -- OLD and NEW ticker_a induce the SAME row partition (same rows grouped "
          f"as the same ticker, even though code VALUES differ)", part_a)
    check(f"{label}: PROOF 2b -- OLD and NEW ticker_b induce the SAME row partition", part_b)
    # checker's OOM finding: X_old and X_new (23.4 GB each on fold 7) must NOT survive into proof_3, which
    # builds up to 4 more matrices of the same size -- drop them here, return only what's small (ids, ev).
    del X_old, X_new
    import gc
    gc.collect()
    return all_ids, ev


def proof_3(fold, in_cols, label):
    f = fold
    X_train_once, X_val_once, X_test_once, cols = NEW.load_fold_features(f, in_cols)
    X_train_sep, _ = NEW.load_features(f["train_ids"], in_cols)
    X_val_sep, _ = NEW.load_features(f["val_ids"], in_cols)
    X_test_sep, _ = NEW.load_features(f["test_ids"], in_cols)
    ok_train, bad_train = columns_match(X_train_once, X_train_sep, in_cols, skip=())
    ok_val, bad_val = columns_match(X_val_once, X_val_sep, in_cols, skip=())
    ok_test, bad_test = columns_match(X_test_once, X_test_sep, in_cols, skip=())
    check(f"{label}: PROOF 3 -- load_fold_features == 3 separate load_features calls, bitwise "
          f"(ALL columns including ticker, since both sides go through the SAME new ticker code -- not "
          f"OLD vs NEW here)", ok_train and ok_val and ok_test,
          f"bad cols: train={bad_train} val={bad_val} test={bad_test}")
    # checker's OOM finding: don't let these 6 matrices (up to 4 full-fold-sized) survive past this function.
    del X_train_once, X_val_once, X_test_once, X_train_sep, X_val_sep, X_test_sep
    import gc
    gc.collect()


def broken_variant_columns_match():
    """checker's point, round 1: PROOF 1 had no broken variant, and PROOF 3 should share it. A copy of a
    real matrix with ONE cell changed in a non-ticker column must make columns_match report THAT column."""
    rng = np.random.default_rng(0)
    cols = ["a", "ticker_a", "b", "ticker_b", "c"]
    X = rng.random((10, 5)).astype(np.float32)
    X_bad = X.copy()
    X_bad[3, 2] += 1.0  # column "b", one cell
    ok, bad = columns_match(X, X_bad, cols)
    check("BROKEN VARIANT -- columns_match (shared by PROOF 1 and PROOF 3) catches one changed cell",
          (not ok) and bad == ["b"], f"reported bad cols: {bad}")


def proof_4(fold, in_cols):
    """(a) normal pass: 0 MF.verify calls on 2 more load_features calls after a warm-up call.
    (b) FAILING VARIANT: clear _VERIFIED_FILES, call once more -- the counter must read the real per-file
        count (proves it is not a dead counter that would also read 0).
    (c) FAILING VARIANT for the manifest-sha keying: corrupt one cached sha, the next call for that file
        must RAISE."""
    import functools
    NEW._VERIFIED_FILES.clear()
    NEW.load_features(fold["train_ids"], in_cols)  # warm-up: populates _VERIFIED_FILES
    n_files_touched = len(NEW._VERIFIED_FILES)
    calls = {"n": 0}
    orig_verify = NEW.MF.verify

    @functools.wraps(orig_verify)
    def counting_verify(*a, **kw):
        calls["n"] += 1
        return orig_verify(*a, **kw)

    NEW.MF.verify = counting_verify
    try:
        NEW.load_features(fold["val_ids"], in_cols)
        NEW.load_features(fold["test_ids"], in_cols)
        check("PROOF 4a -- MF.verify called 0 times on 2 more load_features calls after warm-up",
              calls["n"] == 0, f"actual calls: {calls['n']}")

        calls["n"] = 0
        NEW._VERIFIED_FILES.clear()
        NEW.load_features(fold["train_ids"], in_cols)
        check(f"PROOF 4b (failing variant) -- after clearing the cache, MF.verify IS called again, "
              f"{n_files_touched} times (not a dead counter)", calls["n"] == n_files_touched,
              f"actual calls: {calls['n']}, expected {n_files_touched}")
    finally:
        NEW.MF.verify = orig_verify

    # (c) manifest-sha staleness must be CAUGHT, not trusted
    some_key = next(iter(NEW._VERIFIED_FILES))
    good_sha = NEW._VERIFIED_FILES[some_key]
    NEW._VERIFIED_FILES[some_key] = "0" * 64  # deliberately wrong
    raised = False
    try:
        NEW.load_features(fold["train_ids"], in_cols)
    except AssertionError as e:
        raised = "stale verify" in str(e)
    finally:
        NEW._VERIFIED_FILES[some_key] = good_sha  # restore
    check("PROOF 4c (failing variant) -- a corrupted cached manifest sha makes the next load_features "
          "call RAISE (stale verify caught, not trusted)", raised)


def broken_variant_ticker(fold, in_cols, all_ids, ev):
    """checker's point, round 1: the tampered coin must actually be PRESENT in the tested ids, or the
    tamper changes nothing and this check would misfire. Uses the MOST FREQUENT ticker_a in all_ids."""
    some_coin = ev["ticker_a"].value_counts().idxmax()
    n_affected = int((ev["ticker_a"] == some_coin).sum())
    check(f"BROKEN VARIANT setup -- tampered coin {some_coin!r} is present in the tested ids",
          n_affected > 0, f"affects {n_affected} rows")

    NEW._COIN_CODE = None
    good_map = dict(NEW._coin_code_map())
    tampered = dict(good_map)
    tampered[some_coin] = tampered[some_coin] + 1  # deliberately wrong
    NEW._COIN_CODE = tampered
    try:
        X_bad, cols = NEW.load_features(all_ids, in_cols)
        _, gt_a, _, _, _ = ground_truth_ticker_codes(all_ids)
        j_a = cols.index("ticker_a")
        caught = not np.array_equal(X_bad[:, j_a], gt_a)
        del X_bad
        import gc
        gc.collect()
    finally:
        NEW._COIN_CODE = None  # restore: rebuilt clean on next call
    check("BROKEN VARIANT -- tampered coin-code map makes PROOF 2a's ground-truth check FAIL as expected",
          caught, f"tampered coin: {some_coin}, {n_affected} rows affected")


def main():
    t_main0 = time.time()
    import master_manifest as MF
    print(f"[B5-EQUIV] sha256 {os.path.basename(__file__)}: {MF.sha(os.path.abspath(__file__))}", flush=True)
    print(f"[B5-EQUIV] sha256 harness.py (NEW): {MF.sha(os.path.join(HERE, 'harness.py'))}", flush=True)
    print(f"[B5-EQUIV] sha256 _frozen_harness_pre_b5step2.py (OLD): "
          f"{MF.sha(os.path.join(HERE, '_frozen_harness_pre_b5step2.py'))} "
          f"(must equal c06484599c879d050f30af898aaf078f754266208f29f3a82c2580f51c75548a)", flush=True)
    print(f"[B5-EQUIV] sha256 inputs_v1_pair.csv: {MF.sha(os.path.join(HERE, 'inputs_v1_pair.csv'))} "
          f"(current 1,093-column list -- step (i), before the a_/b_coin_code revision)", flush=True)
    gs = os.path.join(os.path.dirname(HERE), "dataset", "GIT_STATE.json")
    git_head, git_dirty = ("unavailable", "unavailable")
    if os.path.exists(gs):
        G = MF.json.load(open(gs))
        git_head, git_dirty = G.get("head", "unavailable"), len(G.get("porcelain", []))
    print(f"[B5-EQUIV] git_head {git_head} ({git_dirty} uncommitted paths); "
          f"start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC; pid {os.getpid()}", flush=True)

    in_cols = load_in_cols()
    print(f"[B5-EQUIV] {len(in_cols)} IN columns", flush=True)

    events = NEW.load_search_events()
    folds = NEW.build_folds(events)

    broken_variant_columns_match()

    last_ids, last_ev = None, None
    for k, label in ((7, "fold7"), (0, "fold0")):
        clear_peak_rss()
        rss_before, _ = rss_gb()
        all_ids, ev = proof_1_and_2(folds[k], in_cols, label)
        _, hwm_1_2 = rss_gb()
        print(f"[B5-EQUIV] {label} PROOF 1+2 memory: rss_before={rss_before:.2f}GB "
              f"VmHWM_this_block={hwm_1_2:.2f}GB", flush=True)

        clear_peak_rss()
        rss_before, _ = rss_gb()
        proof_3(folds[k], in_cols, label)
        _, hwm_3 = rss_gb()
        print(f"[B5-EQUIV] {label} PROOF 3 memory: rss_before={rss_before:.2f}GB "
              f"VmHWM_this_block={hwm_3:.2f}GB", flush=True)
        last_ids, last_ev = all_ids, ev

    proof_4(folds[0], in_cols)
    broken_variant_ticker(folds[0], in_cols, last_ids, last_ev)

    print(f"[B5-EQUIV] all done [{time.time()-t_main0:.0f}s]: {sum(PASS)}/{len(PASS)} checks PASS", flush=True)
    if not all(PASS):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
