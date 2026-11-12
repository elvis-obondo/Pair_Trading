"""HL-VAULT1 follow-up (planner/user, 2026-11-12): isotonic maps for 2 h and 5 h on the vault, so the vault's calibration at
2/5/10 h is comparable with S1-H's test-month columns. REPORTED, NOT GATED; no setting of steps 4-5 changes (the sealed
picks file, its sha and every backtest stay as they are; the new calibrated columns go in a NEW file).

    python -u research/model/s1_vault_iso_2h5h.py > research/model/logs/s1/s1_vault_iso_2h5h.log

Decision rules, fixed here before anything is run:
  I1. Fit (S1-H's own recipe, per horizon h in {2, 5}): pool = the saved per-fold test predictions of folds 0-7
      (s1h_recalibration.load_data, search period only); a fit event is kept only if t0 + h hours <= VAULT_START
      (S1-H's guard, which uses the horizon's own h; the 10 h map used h = 10). The count that the 10 h guard
      (t0 + 10 h) would have kept is also logged, for the record. Map = s1h_recalibration.fit_isotonic (increasing,
      out_of_bounds clip, y in [0, 1]) of reach_{h}h on raw p_{h}h. No vault row is in either fit.
  I2. Stage A (no vault label read): apply both maps to the vault's p_2h and p_5h (the sealed picks file, sha-checked),
      save s1_vault_iso_2h5h.parquet (event_id, p_cal_2h, p_cal_5h) with its sha256, and write the settings JSON.
  I3. Stage B (vault labels through vault_loader, as in step 6): per horizon h in {2, 5, 10}: the vault's own deciles of
      raw p_h (np.quantile cut-offs, np.digitize, as S1-H's R3), plus all events, the vault's own top 1% by p_h (the same
      seeded masks as step 6; asserted equal to step 6's saved counts and means) and the Rule A picks q = 1%, 0.5%,
      0.1%. Columns: n, mean raw p, mean calibrated p (2 h and 5 h: the new maps; 10 h: the existing p_cal_10h), actual
      reach rate. Beside them the S1-H test-month numbers read from s1h_report.json (R3 deciles mean_iso and
      actual_reach; R4 pooled picks mean_iso and actual). Log loss and Brier of raw vs calibrated on all vault events,
      next to S1-H's pooled R2 numbers. Count of calibrated values at exactly 0 or 1, and how many of those the label
      contradicts (S1-H's checker fix 3).
  I4. The test-month side is the per-fold out-of-fold predictions with an expanding isotonic map per fold; the vault
      side is the single pre-vault refit with a map fitted on folds 0-7. Different fits; the section says so.
  I5. NUMBERS.md gets the section only with NUMGEN_APPEND=1 (after the checker has read the log).
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
assert os.environ.get("PROFIT1_VAULT", "") != "1", "PROFIT1_VAULT must be unset: the numbers generator reads it at import"
import s1_vault_report as VR  # noqa: E402 -- top_k_mask, SEED, the picks path and sha (module has no side effects on import)
import vault_loader as VL  # noqa: E402

ROOT = VR.ROOT
LOG_DIR = VR.LOG_DIR
NUMBERS_DIR = VR.NUMBERS_DIR
NUMBERS_MD = VR.NUMBERS_MD
OUT_PARQUET = os.path.join(LOG_DIR, "s1_vault_iso_2h5h.parquet")
SETTINGS_OUT = os.path.join(LOG_DIR, "s1_vault_iso_2h5h_settings.json")
REPORT_OUT = os.path.join(LOG_DIR, "s1_vault_iso_2h5h.json")
SECTION_OUT = os.path.join(NUMBERS_DIR, "s1_vault_iso_2h5h_section.md")
MARKER = "## [HL-VAULT1 iso25]"
FIT_HORIZONS = (2, 5)
HORIZONS = (2, 5, 10)
QS = VR.QS


def log(msg):
    print(msg, flush=True)


def stage_a(picks):
    df, _ = S1H.load_data()                                     # folds 0-7 saved test predictions + search outcomes
    log(f"[VISO] pooled test-fold predictions: {len(df):,} rows, folds {sorted(df['fold'].unique())}")
    maps, settings = {}, {}
    for h in FIT_HORIZONS:
        end = df["t0"] + pd.Timedelta(hours=h)
        keep = end <= H.VAULT_START
        keep10 = (df["t0"] + pd.Timedelta(hours=10)) <= H.VAULT_START
        fit = df[keep]
        assert fit["t0"].max() + pd.Timedelta(hours=h) <= H.VAULT_START
        iso = S1H.fit_isotonic(fit[f"p_{h}h"].to_numpy(), fit[f"reach_{h}h"].to_numpy())
        tied = S1H.isotonic_tied_groups(iso, fit[f"p_{h}h"].to_numpy())
        levels = len(np.unique(iso.predict(np.unique(fit[f"p_{h}h"].to_numpy()))))
        grid = {f"{g/10:.1f}": float(iso.predict([g / 10.0])[0]) for g in range(1, 10)}
        log(f"[VISO] h={h}h fit: n_pool={len(df):,} n_dropped(guard t0+{h}h <= VAULT_START)={int((~keep).sum()):,} "
            f"n_fit={len(fit):,} (10 h guard would keep {int(keep10.sum()):,}) tied_groups={tied} distinct_levels={levels}")
        log(f"[VISO] h={h}h iso_at_grid (raw p=0.1..0.9): " + ", ".join(f"{k}:{v:.4f}" for k, v in grid.items()))
        maps[h] = iso
        settings[str(h)] = dict(n_pool=int(len(df)), n_dropped=int((~keep).sum()), n_fit=int(len(fit)),
                                n_fit_if_10h_guard=int(keep10.sum()), tied_groups=int(tied), distinct_levels=int(levels),
                                iso_at_grid=grid)
    out = picks[["event_id"]].copy()
    for h in FIT_HORIZONS:
        out[f"p_cal_{h}h"] = maps[h].predict(picks[f"p_{h}h"].to_numpy())
        n_sat = int(((out[f"p_cal_{h}h"] == 0.0) | (out[f"p_cal_{h}h"] == 1.0)).sum())
        log(f"[VISO] stage A h={h}h: {len(out):,} vault events calibrated; saturated at 0 or 1: {n_sat:,}; mean p_cal "
            f"{out[f'p_cal_{h}h'].mean():.4f}")
    out = out.sort_values("event_id").reset_index(drop=True)
    out.to_parquet(OUT_PARQUET, index=False)
    sha = VR.sha256(OUT_PARQUET)
    settings["stage_a_sha256"] = sha
    settings["script_sha256"] = VR.sha256(__file__)
    json.dump(settings, open(SETTINGS_OUT, "w"), indent=1)
    log(f"[VISO] stage A saved {OUT_PARQUET}: {len(out):,} rows sha256 {sha}; settings written BEFORE stage B: {SETTINGS_OUT}")
    return out, settings


def log_loss_brier(p, y):
    return S1H.log_loss(p, y), S1H.brier(p, y)


def stage_b(df, h_rep, step6):
    rng = np.random.default_rng(VR.SEED)                          # same draws, same order as step 6's main()
    top1 = {h: VR.top_k_mask(df[f"p_{h}h"].to_numpy(), 0.01, rng) for h in HORIZONS}
    lines = [f"{MARKER} VAULT (opened once, {VR.VAULT_OPENED}): isotonic maps for 2 h and 5 h on the vault, calibration at "
             f"2/5/10 h next to S1-H's test months (script s1_vault_iso_2h5h.py)", "",
             "Reported, not gated. The 2 h and 5 h maps are fitted on the pooled test-fold predictions of folds 0-7 with "
             "S1-H's guard at the horizon's own length (t0 + h <= vault start), the 10 h map is the existing p_cal_10h of step 4. "
             "Test-month columns are s1h_report.json (isotonic maps fitted per fold on earlier folds, scored on that fold's "
             "out-of-fold predictions); the vault is scored by the single pre-vault refit with one map fitted on folds 0-7. "
             "Different fits, so the two sides are not the same model. Deciles are the vault's own (cut-offs from the vault's "
             "raw p); the test deciles are the test months' own.", ""]
    out = {}
    for h in HORIZONS:
        p, y = df[f"p_{h}h"].to_numpy(), df[f"reach_{h}h"].to_numpy()
        pc = df[f"p_cal_{h}h"].to_numpy()
        n_sat = int(((pc == 0.0) | (pc == 1.0)).sum())
        n_contra = int((((pc == 0.0) & (y == 1)) | ((pc == 1.0) & (y == 0))).sum())
        ll_raw, br_raw = log_loss_brier(p, y)
        ll_cal, br_cal = log_loss_brier(pc, y)
        r2 = h_rep["r2_error_scores"][str(h)]["pooled"]
        log(f"[VISO] h={h}h all vault events: logloss raw {ll_raw:.4f} cal {ll_cal:.4f}; brier raw {br_raw:.4f} cal {br_cal:.4f}; "
            f"calibrated at 0 or 1: {n_sat:,} (label-contradicted {n_contra:,}); S1-H pooled test: logloss raw {r2['logloss_raw']:.4f} "
            f"iso {r2['logloss_iso']:.4f}, brier raw {r2['brier_raw']:.4f} iso {r2['brier_iso']:.4f}")
        r3 = h_rep["r3_calibration_deciles"][str(h)]["bins"]
        cuts = np.quantile(p, np.arange(1, 10) / 10.0)
        bidx = np.digitize(p, cuts)
        rows = []
        for b in range(10):
            m = bidx == b
            rows.append(dict(bucket=f"decile {b}", n=int(m.sum()), raw=float(p[m].mean()), cal=float(pc[m].mean()),
                             actual=float(y[m].mean()), t_raw=r3[str(b)]["mean_raw"], t_cal=r3[str(b)]["mean_iso"],
                             t_actual=r3[str(b)]["actual_reach"]))
        sets = [("all vault events", np.ones(len(df), dtype=bool)), (f"own top 1% by p_{h}h", top1[h])]
        sets += [(f"Rule A picks q={q}", df[f"pick_{q}"].to_numpy()) for q in QS]
        for label, m in sets:
            row = dict(bucket=label, n=int(m.sum()), raw=float(p[m].mean()), cal=float(pc[m].mean()),
                       actual=float(y[m].mean()), t_raw=None, t_cal=None, t_actual=None)
            if label.startswith("Rule A"):
                pooled = h_rep["r4_picks"][label.split("=")[1]]["pooled"]
                row["t_raw"], row["t_cal"], row["t_actual"] = (pooled[f"mean_raw_{h}h"], pooled[f"mean_iso_{h}h"],
                                                                 pooled[f"actual_{h}h"])
            rows.append(row)
            # consistency with step 6's saved raw numbers for the same set (same n, mean raw p, actual)
            ref = [r for r in step6[str(h)] if r["bucket"] == label]
            assert len(ref) == 1, label
            assert ref[0]["n"] == row["n"] and abs(ref[0]["pred"] - row["raw"]) < 1e-12 and abs(ref[0]["actual"] - row["actual"]) < 1e-12, \
                f"h={h} {label}: differs from step 6's saved numbers"
        f = lambda v: "n/a" if v is None else f"{v:.4f}"
        lines += [f"**{h} h** -- all vault events: log loss raw {ll_raw:.4f}, calibrated {ll_cal:.4f}; Brier raw {br_raw:.4f}, "
                  f"calibrated {br_cal:.4f}. S1-H pooled test months: log loss raw {r2['logloss_raw']:.4f}, isotonic "
                  f"{r2['logloss_iso']:.4f}; Brier raw {r2['brier_raw']:.4f}, isotonic {r2['brier_iso']:.4f}. Calibrated values "
                  f"at exactly 0 or 1 on the vault: {n_sat:,}, contradicted by the label: {n_contra:,}.", "",
                  "| bucket | n | mean raw p | mean calibrated p | actual reach | actual - calibrated | test mean raw | test mean calibrated | test actual |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            lines.append(f"| {r['bucket']} | {r['n']:,} | {r['raw']:.4f} | {r['cal']:.4f} | {r['actual']:.4f} | "
                         f"{r['actual'] - r['cal']:+.4f} | {f(r['t_raw'])} | {f(r['t_cal'])} | {f(r['t_actual'])} |")
            log(f"[VISO] calib h={h} {r['bucket']}: n={r['n']:,} raw {r['raw']:.4f} cal {r['cal']:.4f} actual {r['actual']:.4f}")
        lines.append("")
        out[str(h)] = dict(rows=rows, n_sat=n_sat, n_contradicted=n_contra, logloss_raw=ll_raw, logloss_cal=ll_cal,
                           brier_raw=br_raw, brier_cal=br_cal)
    return lines, out


def main():
    t0 = time.time()
    log(f"[VISO] sha256 s1_vault_iso_2h5h.py {VR.sha256(__file__)}; start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC")
    got = VR.sha256(VR.PICKS)
    log(f"[VISO] picks file sha256 {got} (expected {VR.EXPECTED_PICKS_SHA})")
    assert got == VR.EXPECTED_PICKS_SHA
    picks = pd.read_parquet(VR.PICKS)
    cal_a, settings = stage_a(picks)                              # stage A: no vault label read
    # ---- stage B: vault labels, as in step 6 ----
    df = VR.load_vault_table()                                    # asserts sha, row counts, label_gap, NaNs
    df = df.merge(cal_a, on="event_id", validate="one_to_one")
    df["p_cal_2h"] = df["p_cal_2h"].astype(float)
    df["p_cal_5h"] = df["p_cal_5h"].astype(float)
    df["p_cal_10h"] = df["p_cal_10h"].astype(float)
    assert len(df) == len(picks) and df[["p_cal_2h", "p_cal_5h", "p_cal_10h"]].notna().all().all()
    h_rep = json.load(open(os.path.join(LOG_DIR, "s1h_report.json")))
    step6 = {h: rows for h, rows in json.load(open(os.path.join(LOG_DIR, "s1_vault_report.json")))["calibration"].items()}
    lines, res = stage_b(df, h_rep, step6)
    json.dump(dict(settings=settings, calibration=res), open(REPORT_OUT, "w"), indent=2, default=str)
    text = "\n" + "\n".join(lines) + "\n"
    open(SECTION_OUT, "w").write(text)
    log(f"[VISO] section written: {SECTION_OUT} (sha256 {VR.sha256(SECTION_OUT)})")
    existing = open(NUMBERS_MD).read()
    if MARKER in existing:
        log(f"[VISO] NUMBERS.md already has {MARKER!r} -- not appending again")
    elif os.environ.get("NUMGEN_APPEND", "") != "1":
        log("[VISO] NUMGEN_APPEND not set: NUMBERS.md NOT appended (checker reviews the log first)")
    else:
        with open(NUMBERS_MD, "a") as f:
            f.write(text)
        log(f"[VISO] NUMBERS.md appended: {NUMBERS_MD}")
    assert open(SECTION_OUT).read() == text
    log(f"[VISO] done  [{time.time()-t0:.0f}s]")


if __name__ == "__main__":
    main()
