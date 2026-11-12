"""HL-VAULT1 step 4 (brief docs/prompts/HL_VAULT1_RUN.md): the vault's picks (Rule A) and p_cal (isotonic).
Fixed rules, no tuning. Runs on the laptop. Reads: the saved vault predictions (step 3), fold 7's SAVED test
predictions, the pooled test-fold predictions with their search-period outcomes (S1-H's own loader), and --
only AFTER the picks and p_cal are fixed and saved -- the vault's label_gap flag.

    python -u research/model/s1_vault_picks.py > research/model/logs/s1/s1_vault_picks.log

Rule A (as every fold in S1-G/S1-H): the cut-off for q in {1%, 0.5%, 0.1%} is np.quantile(prev, 1 - q) where
prev = the PREVIOUS block's saved test raw p_10h; for the vault the previous block is fold 7
(fold7_test_predictions.csv). A vault event is a pick for q if its raw p_10h >= that cut-off. No vault
prediction enters the cut-off. Validation of the method: the same computation for fold 7 itself (cut-off from
fold 6) must reproduce S1-G's saved per-fold n in s1g_report.json (assert).

p_cal: isotonic regression (S1-H's own s1h_recalibration.fit_isotonic) of reach_10h on raw p_10h, fitted on
the pooled saved test predictions of POOL_FOLDS, keeping a fit event only if t0 + 10 h GUARD VAULT_START
(S1-H's look-ahead guard: its outcome was known before the vault opened). n_fit, n_dropped, pool folds and the
tied-group count are printed. No vault row is in the fit; the vault's own outcomes are never read here.

STAGES (each printed with counts, the way harness.load_search_events prints them):
  A. all 1,280,088 vault events: predictions -> pick flags and p_cal_10h -> saved with its sha256
     (s1_vault_picks_all.parquet). Nothing in stage A depends on any label.
  B. only now: vault_loader.load_vault_events -> keep event_id/t0/label_gap and nothing else (no outcome
     column is touched) -> apply harness.load_search_events' rules to the vault rows: date filter
     (t0 >= VAULT_START; the gap day is before VAULT_START so it is absent by construction -- asserted),
     then label_gap == 0 -> the usable picks table s1_vault_picks.parquet, saved with its sha256.
Settings are written to s1_vault_picks_settings.json before stage B starts.
"""
import hashlib
import json
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402
import s1h_recalibration as S1H  # noqa: E402

LOG_DIR = os.path.join(HERE, "logs", "s1")
PRED_FILE = os.path.join(LOG_DIR, "vault_pull3", "s1_vault_predictions.parquet")
EXPECTED_PRED_SHA = "ede424aac78a849c4288f223ad8e3750a0bbc343b1bdaad1ec2a657efdb689a7"
ALL_OUT = os.path.join(LOG_DIR, "s1_vault_picks_all.parquet")
USABLE_OUT = os.path.join(LOG_DIR, "s1_vault_picks.parquet")
SETTINGS_OUT = os.path.join(LOG_DIR, "s1_vault_picks_settings.json")
QS = S1H.QS
# Fixed here, before any vault label is read. Planner's ruling (2026-11-12): S1-H's own recipe literally --
# folds 0-7 (fold 0 included, as in S1-H's expanding pool) and the guard t0 + 10 h <= VAULT_START; the
# brief's text ("folds 1-7", "<") was imprecise.
POOL_FOLDS = tuple(range(0, 8))
GUARD_INCLUSIVE = True        # t0 + 10 h <= VAULT_START (S1-H's own); False -> strict <


def log(msg):
    print(msg, flush=True)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def main():
    t0 = time.time()
    import master_manifest as MF
    for name in ("s1_vault_picks.py", "s1h_recalibration.py", "harness.py", "vault_loader.py"):
        log(f"[VAULTPICKS] sha256 {name}: {MF.sha(os.path.join(HERE, name))}")
    log(f"[VAULTPICKS] start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC; POOL_FOLDS={POOL_FOLDS} "
        f"guard={'<=' if GUARD_INCLUSIVE else '<'}")

    # ---- inputs ----
    sp = sha256_file(PRED_FILE)
    log(f"[VAULTPICKS] vault predictions sha256 {sp} (expected {EXPECTED_PRED_SHA})")
    assert sp == EXPECTED_PRED_SHA
    pred = pd.read_parquet(PRED_FILE)
    log(f"[VAULTPICKS] stage A input: {len(pred):,} vault predictions (event_id unique: {pred['event_id'].is_unique})")
    assert pred["event_id"].is_unique

    df, events = S1H.load_data()      # all 8 folds' saved test predictions + search-period outcomes
    s1g_report = json.load(open(os.path.join(LOG_DIR, "s1g_report.json")))

    # ---- Rule A cut-offs from fold 7's saved test raw p_10h ----
    prev = df.loc[df["fold"] == 7, "p_10h"].to_numpy()
    cut = {q: float(np.quantile(prev, 1 - q)) for q in QS}
    log(f"[VAULTPICKS] Rule A: previous block = fold 7 ({len(prev):,} saved test events); cut-offs "
        + ", ".join(f"q={q}: {cut[q]:.10f}" for q in QS))
    # method validation: fold 7's own picks from fold 6's cut-off reproduce S1-G's saved n
    cutoff_table = s1g_report["g7_tighter_cutoffs"]["cutoff_table"]
    p6 = df.loc[df["fold"] == 6, "p_10h"].to_numpy()
    p7 = df.loc[df["fold"] == 7, "p_10h"].to_numpy()
    for q in QS:
        n_here = int((p7 >= float(np.quantile(p6, 1 - q))).sum())
        n_saved = cutoff_table[str(q)]["per_fold"]["7"]["n"]
        log(f"[VAULTPICKS] method check q={q}: fold 7 picks from fold 6's cut-off = {n_here:,}, S1-G saved n = {n_saved:,}")
        assert n_here == n_saved

    # ---- p_cal: isotonic on the pooled saved test predictions, S1-H's guard ----
    pool = df[df["fold"].isin(POOL_FOLDS)]
    end = pool["t0"] + pd.Timedelta(hours=10)
    keep = (end <= H.VAULT_START) if GUARD_INCLUSIVE else (end < H.VAULT_START)
    fit = pool[keep]
    p_fit, y_fit = fit["p_10h"].to_numpy(), fit["reach_10h"].to_numpy()
    iso = S1H.fit_isotonic(p_fit, y_fit)
    tied = S1H.isotonic_tied_groups(iso, p_fit)
    log(f"[VAULTPICKS] p_cal fit: pool folds {POOL_FOLDS}: n_pool={len(pool):,} n_dropped(guard)={len(pool)-len(fit):,} "
        f"n_fit={len(fit):,} tied_groups={tied} distinct_levels={len(np.unique(iso.predict(np.unique(p_fit))))}")
    log("[VAULTPICKS] iso_at_grid (raw p=0.1..0.9): " +
        ", ".join(f"{g/10:.1f}:{float(iso.predict([g/10.0])[0]):.4f}" for g in range(1, 10)))
    assert fit["t0"].max() + pd.Timedelta(hours=10) <= H.VAULT_START

    # ---- stage A: picks and p_cal for all vault events, no label involved ----
    out = pred.copy()
    out["p_cal_10h"] = iso.predict(out["p_10h"].to_numpy())
    for q in QS:
        out[f"pick_{q}"] = out["p_10h"].to_numpy() >= cut[q]
    n_sat = int(((out["p_cal_10h"] == 0.0) | (out["p_cal_10h"] == 1.0)).sum())
    log(f"[VAULTPICKS] stage A: {len(out):,} vault events scored; p_cal_10h saturated at 0 or 1 for {n_sat:,}; picks "
        + ", ".join(f"q={q}: {int(out[f'pick_{q}'].sum()):,}" for q in QS))
    log(f"[VAULTPICKS] stage A: p_10h mean {out['p_10h'].mean():.4f}; mean p_cal_10h of picks "
        + ", ".join(f"q={q}: {out.loc[out[f'pick_{q}'], 'p_cal_10h'].mean():.4f}" for q in QS))
    out = out.sort_values("event_id").reset_index(drop=True)
    out.to_parquet(ALL_OUT, index=False)
    sa = sha256_file(ALL_OUT)
    log(f"[VAULTPICKS] stage A saved {ALL_OUT}: {len(out):,} rows sha256 {sa}")
    settings = dict(vault_predictions_sha256=sp, pool_folds=list(POOL_FOLDS), guard_inclusive=GUARD_INCLUSIVE,
                    n_pool=int(len(pool)), n_dropped=int(len(pool) - len(fit)), n_fit=int(len(fit)),
                    cutoffs={str(q): cut[q] for q in QS}, cutoff_source="fold 7 saved test raw p_10h",
                    n_fold7_test=int(len(prev)), tied_groups=tied, stage_a_sha256=sa,
                    script_sha256=MF.sha(os.path.join(HERE, "s1_vault_picks.py")))
    json.dump(settings, open(SETTINGS_OUT, "w"), indent=1)
    log(f"[VAULTPICKS] settings written BEFORE stage B: {SETTINGS_OUT}")

    # ---- stage B: only now the labels' label_gap flag, harness.load_search_events' rules ----
    import vault_loader as VL
    full = VL.load_vault_events()
    ev = full[["event_id", "t0", "label_gap"]].reset_index(drop=True)   # loader indexes by event_id AND keeps the column
    del full                                   # no outcome column is kept or used
    n_total = len(ev)
    ev = ev[ev["t0"] >= H.VAULT_START]
    on_gap_day = (ev["t0"] >= H.GAP_DAY) & (ev["t0"] < H.GAP_DAY + pd.Timedelta(days=1))
    assert not on_gap_day.any(), "a vault row on the gap day"
    n_after_date = len(ev)
    n_label_gap = int((ev["label_gap"] != 0).sum())
    ev = ev[ev["label_gap"] == 0]
    log(f"[VAULTPICKS] stage B (harness rules on vault rows): {n_total:,} merged vault rows -> {n_after_date:,} after the "
        f"date/gap-day filter -> {len(ev):,} after dropping {n_label_gap:,} label_gap=1 rows")
    assert set(ev["event_id"]).issubset(set(out["event_id"])), "a usable vault event has no prediction"
    assert n_after_date == len(out), "vault row count differs between the predictions and the labels join"
    usable = out[out["event_id"].isin(ev["event_id"])].merge(ev[["event_id", "t0"]], on="event_id", validate="one_to_one")
    assert len(usable) == len(ev)
    usable = usable.sort_values("event_id").reset_index(drop=True)
    for q in QS:
        log(f"[VAULTPICKS] stage B: q={q}: picks {int(usable[f'pick_{q}'].sum()):,} of {len(usable):,} usable "
            f"(stage A had {int(out[f'pick_{q}'].sum()):,} of {len(out):,}); mean p_cal_10h of picks "
            f"{usable.loc[usable[f'pick_{q}'], 'p_cal_10h'].mean():.4f}")
    months = usable["t0"].dt.strftime("%Y-%m")
    for q in QS:
        log(f"[VAULTPICKS] picks per UTC month q={q}: " +
            ", ".join(f"{m}: {int(n):,}" for m, n in usable.loc[usable[f'pick_{q}']].groupby(months)["event_id"].count().items()))
    usable.to_parquet(USABLE_OUT, index=False)
    log(f"[VAULTPICKS] stage B saved {USABLE_OUT}: {len(usable):,} rows sha256 {sha256_file(USABLE_OUT)}  [{time.time()-t0:.0f}s]")


if __name__ == "__main__":
    main()
