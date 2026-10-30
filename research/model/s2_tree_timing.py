"""HL-MODEL1 S2 Step 1: boosted-tree sizing on fold 7, full data, on AWS (brief's Step 1).

    python -u research/model/s2_tree_timing.py > research/model/logs/s2_tree_timing.log

Fold 7 (the largest), full data, one machine. Builds the Dataset, times 200 trees at the grid's
richest setting (num_leaves=255, min_data_in_leaf=1,000 -- T4's larger-tree setting, a conservative
per-tree timing upper bound), times one validation P(reach within 10h) predict at 200 trees, and
projects the full 8-fold run.

MEMORY ROUTE (T5 / NUMBERS.md [HL-MODEL1-B5]): LightGBM's own binned training store is the memory wall,
not a transient raw hazard-row array (~71.75 GB for fold 7's train set alone, measured there by
arithmetic only -- this script is the first actual run that confirms it). The hazard-row raw matrix
itself (fold 7's ~65.7M rows x 1,092 cols) would be ~287 GB in float32 and is never materialised here:
the Dataset is built through an `lgb.Sequence` whose __getitem__ looks up each hazard row's EVENT
position in the resident event-level matrix (~17.4 GB for fold 7's train set) and appends the step value
on the fly -- exactly the construction NUMBERS.md proposed.

BIN EDGES AT EVENT LEVEL (T5), checker's fix round 1: an `EventRefSequence` wraps fold 7's train
EVENT-level matrix directly (one row per event, no hazard expansion), with a synthetic step column
cycling 1..20 so every step value is present in the bin-edge sample. A `lgb.Dataset` built from it
(`ref_set`, never trained on -- its label is an unused placeholder) is passed as `reference=` to the
hazard-row train Dataset, which copies its bin mapper instead of binning from the hazard rows themselves
(LightGBM 4.7's `reference=` mechanism, `basic.py Dataset.__init_from_ref_dataset`, confirmed by the
checker from the same code path `val_set` already relied on for its own reference to `train_set`).

Degenerate columns are dropped on fold 7's RAW TRAIN event rows (drop_degenerate_for_fold, same rule as
S1's R8c). `feature_pre_filter=False` (checker's fix round 1): the default (True) silently drops columns
LightGBM judges unsplittable at `min_data_in_leaf`, which would make the single Dataset build invalid for
grid settings other than the one it was built with (T4's grid changes min_data_in_leaf) and would hide
drops on top of the logged degenerate count. ticker_a/ticker_b are marked LightGBM categorical features
using the harness's existing FIXED sorted(coins.csv) integer codes (B5 Step 2) directly -- T6's per-fold
"unseen level" remap is a Step 2 scoring concern, not needed for a timing-only Dataset build.

`force_row_wise=True` is set explicitly (checker's fix round 1, minor 5): LightGBM's docs pair
`deterministic=True` with an explicit row-wise/col-wise choice, since the automatic pick can otherwise
vary run to run and skew timing. `num_threads` is set to the assumed PHYSICAL core count (logical count
// 2, logged), not the logical/vCPU count LightGBM's own docs warn against using on a hyperthreaded box.

Projection is arithmetic on this one measured fold/setting (fold 7 is the largest, the standard
conservative per-fold upper bound used by b4_rsf_feasibility.py and s1_gram_timing.py), not a second
measurement. Per-tree train cost and Dataset build cost are scaled linearly by hazard-row count for the
refit (train+val, more rows than the grid's train-only fits). Checkpoint predicts (T4: validation lift
read every 100 trees, 20 checkpoints per fit) assume each checkpoint RE-PREDICTS FROM SCRATCH at that
tree count (checker's fix round 1, blocking 3) -- the conservative/upper-bound route (cost grows
linearly with tree count: checkpoint k costs k*100/200 of the measured 200-tree predict, summing to
105x per fit, not 20x). Step 2 may instead accumulate raw scores incrementally between checkpoints
(cheaper, ~10x per fit) -- not decided here; this projection reports the conservative route and says so.
Per-fold load and hazard-row-build time (measured, both folds' worth) and a stated flat allowance for
scoring/bootstrap are added to the per-fold total. The proposed machine size scales the measured TRAIN
peak RSS by the larger of B5's refit/train binned-store ratio (90.82/71.75) and this run's own
train+val hazard-row ratio, for headroom at the refit scale this script does not itself measure.
"""
import gc
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402
from b5_profile import rss_gb, clear_peak_rss  # noqa: E402

import lightgbm as lgb  # noqa: E402

N_FOLDS = 8
FITS_PER_FOLD = 4          # T4 grid: num_leaves {63,255} x min_data_in_leaf {1000,10000}
MAX_TREES = 2000           # T4 cap per fit (early stopping makes this an upper bound)
CHECKPOINT_EVERY = 100     # T4: validation lift read every 100 trees
N_TREES_TIME = 200         # Step 1: time 200 trees at the richest setting
NUM_LEAVES = 255
MIN_DATA_IN_LEAF = 1000
LEARNING_RATE = 0.05
MAX_BIN = 255
FEATURE_FRACTION = 0.3
LAMBDA_L2 = 1.0
SEED = 0
N_LOGICAL = os.cpu_count() or 1
N_THREADS = max(1, N_LOGICAL // 2)   # assumed physical cores (logical/2, hyperthreaded) -- logged below
HOURS_GATE = 24.0
B5_REFIT_RATIO = 90.82 / 71.75   # NUMBERS.md [HL-MODEL1-B5]: refit (train+val) vs train-only binned store
SCORING_ALLOWANCE_S = 300.0     # stated flat allowance (A, not measured): gate + M1-M6 metrics per fold

# S1's own bid (aws_s1_probe_launch_cmd.txt / aws_s1_run_launch_cmds.txt) for ap-northeast-1; us-east-2
# figure is this session's own spot-price lookup for the same instance type -- both logged as an
# assumption fed into the projection below, not re-verified by a live AWS price-history call here.
SPOT_PRICE_PER_HOUR = {"ap-northeast-1 r7i.16xlarge": 3.00, "us-east-2 r7i.16xlarge": 2.20}


class HazardSequence(lgb.Sequence):
    """Feeds LightGBM hazard rows in batches from the resident EVENT-level matrix (no raw hazard-row
    array is ever materialised): __getitem__ looks up each requested hazard row's event position and
    appends its step value as the last column. batch_size only controls lgb's internal read chunking."""

    def __init__(self, X_event, row_event_pos, row_step, batch_size=524_288):
        self.X_event = X_event
        self.row_event_pos = row_event_pos
        self.row_step = row_step.astype(np.float32).reshape(-1, 1)
        self.batch_size = batch_size

    def __getitem__(self, idx):
        # LightGBM's own Sequence sampling requires float64 ("not double" otherwise) -- cast happens
        # only on the BATCH actually requested, never on the whole resident event matrix.
        pos = self.row_event_pos[idx]
        feat = self.X_event[pos].astype(np.float64, copy=False)
        step = self.row_step[idx].astype(np.float64, copy=False)
        if feat.ndim == 1:
            return np.concatenate([feat, step.ravel()])
        return np.hstack([feat, step])

    def __len__(self):
        return len(self.row_event_pos)


class EventRefSequence(lgb.Sequence):
    """One row per EVENT (no hazard expansion), with a synthetic step column cycling 1..20 so every step
    value is present in the bin-edge sample -- checker's fix round 1: T5's bin edges come from the fold's
    fit EVENT rows, not from the hazard rows. Used only to build a reference Dataset whose bin mapper the
    real hazard-row Dataset copies (lgb.Dataset reference=); never trained on directly."""

    def __init__(self, X_event, batch_size=524_288):
        self.X_event = X_event
        n = X_event.shape[0]
        self.step = ((np.arange(n) % H.N_STEPS) + 1).astype(np.float64).reshape(-1, 1)
        self.batch_size = batch_size

    def __getitem__(self, idx):
        feat = self.X_event[idx].astype(np.float64, copy=False)
        step = self.step[idx]
        if feat.ndim == 1:
            return np.concatenate([feat, step.ravel()])
        return np.hstack([feat, step])

    def __len__(self):
        return self.X_event.shape[0]


def main():
    t0 = time.time()
    import master_manifest as MF
    for name in ("s2_tree_timing.py", "harness.py", "inputs_v1_pair.csv"):
        print(f"[S2-TREE] sha256 {name}: {MF.sha(os.path.join(HERE, name))}", flush=True)
    cache_info = H._cache_info()
    cache_sha = cache_info.get("cache_sha256", "NO VALID CACHE") if cache_info else "NO VALID CACHE"
    print(f"[S2-TREE] cache manifest cache_sha256: {cache_sha} "
          f"(must be bd5dc2549374d0a80c8b042425e34119289b17b753a49213ac28c1831c6ca544)", flush=True)
    gs = os.path.join(os.path.dirname(HERE), "dataset", "GIT_STATE.json")
    git_head, git_dirty = ("unavailable", "unavailable")
    if os.path.exists(gs):
        G = MF.json.load(open(gs))
        git_head, git_dirty = G.get("head", "unavailable"), len(G.get("porcelain", []))
    print(f"[S2-TREE] git_head {git_head} ({git_dirty} uncommitted paths); "
          f"start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC; pid {os.getpid()}; "
          f"lightgbm {lgb.__version__}; logical_cpus={N_LOGICAL} num_threads={N_THREADS} "
          f"(assumed physical = logical/2)", flush=True)

    clear_peak_rss()
    rss0, _ = rss_gb()
    events = H.load_search_events()
    folds = H.build_folds(events)
    fold = folds[7]
    in_cols = cache_info["columns"]
    assert len(in_cols) == 1091, f"expected 1,091 IN columns, cache has {len(in_cols)}"
    print(f"[S2-TREE] fold 7: n_train={len(fold['train_ids']):,} n_val={len(fold['val_ids']):,} "
          f"n_test={len(fold['test_ids']):,}  [{time.time()-t0:.0f}s]", flush=True)

    t_load = time.time()
    X_train, X_val, X_test, cols = H.load_fold_features_cached(fold, in_cols)
    n_test_events = X_test.shape[0]
    del X_test
    gc.collect()
    load_s = time.time() - t_load
    rss_load, hwm_load = rss_gb()
    print(f"[S2-TREE] loaded event-level train {X_train.shape}, val {X_val.shape} in {load_s:.1f}s "
          f"({X_train.nbytes/1e9:.2f}+{X_val.nbytes/1e9:.2f} GB); rss={rss_load:.2f}GB VmHWM={hwm_load:.2f}GB "
          f"[{time.time()-t0:.0f}s]", flush=True)

    train_df = pd.DataFrame(X_train, columns=cols, copy=False)
    kept_cols, dropped_cols = H.drop_degenerate_for_fold(train_df, cols)
    del train_df
    gc.collect()
    keep_idx = [cols.index(c) for c in kept_cols]
    X_train = np.ascontiguousarray(X_train[:, keep_idx])
    X_val = np.ascontiguousarray(X_val[:, keep_idx])
    gc.collect()
    print(f"[S2-TREE] after degenerate drop: {len(kept_cols)} of {len(cols)} columns kept "
          f"({len(dropped_cols)} dropped)  [{time.time()-t0:.0f}s]", flush=True)

    cat_idx = [i for i, c in enumerate(kept_cols) if c in ("ticker_a", "ticker_b")]
    feature_name = kept_cols + ["step"]
    n_feat = len(feature_name)
    print(f"[S2-TREE] {n_feat} features (incl. step); categorical: {[kept_cols[i] for i in cat_idx]}  "
          f"[{time.time()-t0:.0f}s]", flush=True)

    t_hazard = time.time()
    train_events = events.loc[fold["train_ids"]]
    val_events = events.loc[fold["val_ids"]]
    hazard_train = H.build_hazard_rows(train_events)
    hazard_val = H.build_hazard_rows(val_events)
    pos_train = {eid: i for i, eid in enumerate(fold["train_ids"])}
    pos_val = {eid: i for i, eid in enumerate(fold["val_ids"])}
    row_event_pos_train = hazard_train["event_id"].map(pos_train).to_numpy()
    row_step_train = hazard_train["step"].to_numpy()
    row_label_train = hazard_train["label"].to_numpy()
    row_event_pos_val = hazard_val["event_id"].map(pos_val).to_numpy()
    row_step_val = hazard_val["step"].to_numpy()
    row_label_val = hazard_val["label"].to_numpy()
    n_train_hazard = len(row_label_train)
    n_val_hazard = len(row_label_val)
    hazard_s = time.time() - t_hazard
    print(f"[S2-TREE] hazard rows: train={n_train_hazard:,} val={n_val_hazard:,} built in {hazard_s:.1f}s  "
          f"[{time.time()-t0:.0f}s]", flush=True)

    train_seq = HazardSequence(X_train, row_event_pos_train, row_step_train)
    val_seq = HazardSequence(X_val, row_event_pos_val, row_step_val)
    ref_seq = EventRefSequence(X_train)

    params = dict(objective="binary", num_leaves=NUM_LEAVES, min_data_in_leaf=MIN_DATA_IN_LEAF,
                  learning_rate=LEARNING_RATE, max_bin=MAX_BIN, feature_fraction=FEATURE_FRACTION,
                  lambda_l2=LAMBDA_L2, bagging_fraction=1.0, bagging_freq=0, feature_pre_filter=False,
                  force_row_wise=True, deterministic=True, seed=SEED, num_threads=N_THREADS, verbose=-1)
    print(f"[S2-TREE] params: {params}  [{time.time()-t0:.0f}s]", flush=True)

    # T5 (checker's fix round 1): bin edges from fold 7's train EVENT rows, not from the hazard rows.
    # ref_set is never trained on -- its label is an unused placeholder, only its bin mapper is used, via
    # reference= on the real hazard-row train Dataset below. Timed and peak-measured as its own block
    # (checker's fix round 2, minor 1): ref_set stays resident once train_set references it, so its
    # binned store counts toward every later peak too -- conservative, which is fine.
    clear_peak_rss()
    t_ref = time.time()
    ref_label = np.zeros(X_train.shape[0], dtype=np.int8)
    ref_set = lgb.Dataset(ref_seq, label=ref_label, feature_name=feature_name,
                           categorical_feature=cat_idx, params=params, free_raw_data=False)
    ref_set.construct()
    ref_s = time.time() - t_ref
    rss_ref, hwm_ref = rss_gb()
    print(f"[S2-TREE] event-level reference Dataset constructed ({X_train.shape[0]:,} event rows, "
          f"bin edges only): {ref_s:.1f}s; rss={rss_ref:.2f}GB VmHWM={hwm_ref:.2f}GB  "
          f"[{time.time()-t0:.0f}s]", flush=True)

    clear_peak_rss()
    t_build = time.time()
    train_set = lgb.Dataset(train_seq, label=row_label_train, feature_name=feature_name,
                             categorical_feature=cat_idx, reference=ref_set, params=params,
                             free_raw_data=False)
    train_set.construct()
    build_s = time.time() - t_build
    rss_build, hwm_build = rss_gb()
    print(f"[S2-TREE] Dataset.construct() on fold 7 TRAIN ({n_train_hazard:,} hazard rows): {build_s:.1f}s; "
          f"num_feature={train_set.num_feature()} (kept_cols+step={n_feat}); "
          f"rss={rss_build:.2f}GB VmHWM={hwm_build:.2f}GB  [{time.time()-t0:.0f}s]", flush=True)

    val_set = lgb.Dataset(val_seq, label=row_label_val, feature_name=feature_name,
                           categorical_feature=cat_idx, reference=train_set, params=params,
                           free_raw_data=False)
    val_set.construct()
    print(f"[S2-TREE] val Dataset constructed ({n_val_hazard:,} hazard rows)  [{time.time()-t0:.0f}s]",
          flush=True)

    clear_peak_rss()
    t_train = time.time()
    booster = lgb.train(params, train_set, num_boost_round=N_TREES_TIME,
                         valid_sets=[val_set], callbacks=[lgb.log_evaluation(period=50)])
    train_s = time.time() - t_train
    rss_train, hwm_train = rss_gb()
    s_per_tree = train_s / N_TREES_TIME
    print(f"[S2-TREE] trained {N_TREES_TIME} trees: {train_s:.1f}s ({s_per_tree:.4f}s/tree); "
          f"rss={rss_train:.2f}GB VmHWM={hwm_train:.2f}GB  [{time.time()-t0:.0f}s]", flush=True)

    clear_peak_rss()
    t_pred = time.time()
    n_val_events = X_val.shape[0]
    steps_mat = np.tile(np.arange(1, H.N_STEPS + 1, dtype=np.float32), n_val_events).reshape(-1, 1)
    X_val_rep = np.repeat(X_val, H.N_STEPS, axis=0)
    X_val_pred = np.hstack([X_val_rep, steps_mat])
    del X_val_rep
    gc.collect()
    h = booster.predict(X_val_pred, num_iteration=N_TREES_TIME)
    h = h.reshape(n_val_events, H.N_STEPS)
    p10h = 1.0 - np.prod(1.0 - h, axis=1)
    pred_s = time.time() - t_pred
    _, hwm_pred = rss_gb()
    print(f"[S2-TREE] validation P(reach within 10h) predict ({n_val_events:,} events x {H.N_STEPS} steps "
          f"= {X_val_pred.shape[0]:,} rows) at {N_TREES_TIME} trees: {pred_s:.1f}s; mean p10h={p10h.mean():.4f}; "
          f"VmHWM_this_block={hwm_pred:.2f}GB  [{time.time()-t0:.0f}s]", flush=True)
    del X_val_pred
    gc.collect()

    # checker's fix round 1, blocking 4: clear_peak_rss() resets VmHWM between blocks, so the single
    # post-hoc read here only ever covered the LAST block (predict). The real overall peak is the max of
    # every block's own labelled peak, each already printed above.
    hwm_overall = max(hwm_load, hwm_ref, hwm_build, hwm_train, hwm_pred)
    print(f"[S2-TREE] overall peak RSS this run (max of load={hwm_load:.2f}, ref_dataset={hwm_ref:.2f}, "
          f"build={hwm_build:.2f}, train={hwm_train:.2f}, predict={hwm_pred:.2f} GB): {hwm_overall:.2f}GB "
          f"(rss at process start: {rss0:.2f}GB)", flush=True)

    # ---- Projection (arithmetic on this one measurement; fold 7 is the largest, used as a conservative
    # per-fold upper bound, same convention as b4_rsf_feasibility.py / s1_gram_timing.py) ----
    n_refit_hazard = n_train_hazard + n_val_hazard   # approximation: train+val hazard-row count
    refit_row_ratio = n_refit_hazard / n_train_hazard
    n_checkpoints = MAX_TREES // CHECKPOINT_EVERY

    build_s_grid = build_s                                  # one Dataset build serves all 4 grid fits
    build_s_refit = build_s * refit_row_ratio                # refit's bigger train+val Dataset
    grid_train_s = FITS_PER_FOLD * MAX_TREES * s_per_tree     # upper bound: no early stop
    # checker's fix round 1, blocking 3: each checkpoint RE-PREDICTS FROM SCRATCH at that tree count
    # (the conservative/upper-bound route) -- cost grows linearly with tree count, so checkpoint k costs
    # k*CHECKPOINT_EVERY/N_TREES_TIME x the measured 200-tree predict, summing to 105x per fit (not 20x).
    # Step 2 may instead accumulate raw scores incrementally between checkpoints (cheaper, ~10x/fit) --
    # not decided here; this projection reports the conservative route.
    checkpoint_multiplier = sum(k * CHECKPOINT_EVERY / N_TREES_TIME for k in range(1, n_checkpoints + 1))
    grid_predict_s = FITS_PER_FOLD * checkpoint_multiplier * pred_s
    refit_train_s = MAX_TREES * s_per_tree * refit_row_ratio
    refit_predict_s = pred_s * (n_test_events / n_val_events)   # final test predict, scaled by event count

    ref_s_grid = ref_s                       # one event-level reference build for the grid (train only)
    ref_s_refit = ref_s * refit_row_ratio    # refit needs its OWN reference built from train+val events
    per_fold_s = (load_s + hazard_s + ref_s_grid + ref_s_refit + build_s_grid + build_s_refit
                  + grid_train_s + grid_predict_s + refit_train_s + refit_predict_s + SCORING_ALLOWANCE_S)
    total_s_1machine = N_FOLDS * per_fold_s
    total_h_1machine = total_s_1machine / 3600.0
    total_h_2machine = total_h_1machine / 2.0   # folds split across 2 machines; same total compute, half the wall time

    print(f"[S2-TREE] PROJECTION per fold (upper bound, no early stopping, conservative re-predict route): "
          f"load[{load_s:.0f}s] + hazard_build[{hazard_s:.0f}s] + "
          f"ref_dataset[grid {ref_s_grid:.0f}s + refit {ref_s_refit:.0f}s] + "
          f"dataset_build[grid {build_s_grid:.0f}s + refit {build_s_refit:.0f}s] + "
          f"grid_train[{FITS_PER_FOLD}x{MAX_TREES} trees = {grid_train_s:.0f}s] + "
          f"grid_predict[{FITS_PER_FOLD}x{n_checkpoints} checkpoints, {checkpoint_multiplier:.0f}x/fit "
          f"= {grid_predict_s:.0f}s] + "
          f"refit_train[{MAX_TREES} trees x {refit_row_ratio:.3f} row-ratio = {refit_train_s:.0f}s] + "
          f"refit_predict[{refit_predict_s:.0f}s] + scoring_allowance[{SCORING_ALLOWANCE_S:.0f}s, A, not "
          f"measured] = {per_fold_s:.0f}s/fold", flush=True)
    print(f"[S2-TREE] PROJECTION all 8 folds (fold 7's size as the per-fold upper bound): "
          f"{total_s_1machine:.0f}s = {total_h_1machine:.2f}h on 1 machine; "
          f"{total_h_2machine:.2f}h on 2 machines (same total compute, split in half)", flush=True)

    for region_machine, price in SPOT_PRICE_PER_HOUR.items():
        cost_1 = total_h_1machine * price
        cost_2 = total_h_2machine * price * 2   # 2 machines running in parallel, each billed its own hours
        print(f"[S2-TREE] PROJECTION cost at {region_machine} (${price:.2f}/h spot, A: assumption, not a "
              f"live price-history call): "
              f"1 machine ~${cost_1:.0f} over {total_h_1machine:.2f}h; "
              f"2 machines ~${cost_2:.0f} total over {total_h_2machine:.2f}h wall-clock each "
              f"({'FEASIBLE' if total_h_2machine <= HOURS_GATE else 'STOP: exceeds 24h on 2 machines'} "
              f"within {HOURS_GATE:.0f}h)", flush=True)

    # Machine proposal: scale the measured TRAIN peak by the larger of B5's refit/train binned-store
    # ratio (90.82/71.75 GB, NUMBERS.md [HL-MODEL1-B5]) and this run's own train+val hazard-row ratio --
    # Step 1 only measures the train-only store, and the refit (train+val, full data) is the real peak.
    size_ratio = max(B5_REFIT_RATIO, refit_row_ratio)
    projected_refit_peak = hwm_overall * size_ratio
    CANDIDATE_RAM_GB = 512.0
    USABLE_RAM_GB = 460.0   # candidate RAM minus OS/other-process headroom (checker's fix round 2, minor 2)
    fits = projected_refit_peak <= USABLE_RAM_GB
    print(f"[S2-TREE] MACHINE PROPOSAL: measured train-only peak {hwm_overall:.2f}GB x "
          f"{size_ratio:.3f} (max of B5's refit/train ratio {B5_REFIT_RATIO:.3f} and this fold's own "
          f"train+val hazard-row ratio {refit_row_ratio:.3f}) = ~{projected_refit_peak:.1f}GB projected "
          f"refit-scale peak, against r7i.16xlarge's {CANDIDATE_RAM_GB:.0f} GiB RAM "
          f"({USABLE_RAM_GB:.0f} GiB usable headroom): "
          f"{'FITS' if fits else 'DOES NOT FIT -- needs a bigger machine or a smaller scope'}. "
          f"r7i.16xlarge is the same type S1 already uses (64 vCPU / 32 physical cores); "
          f"Tokyo (ap-northeast-1) spot first, us-east-2 as the stated fallback (brief).", flush=True)

    print(f"[S2-TREE] all done  [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
