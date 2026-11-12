"""HL-VAULT1 step 3 (brief docs/prompts/HL_VAULT1_RUN.md): score the vault with the SAVED pre-vault model.
First code path that touches vault rows. It touches FEATURES ONLY: the event list comes from
vault_loader.load_vault_event_dates() (events.parquet: ids/tickers/geometry, no labels.parquet), the features
from the cached IN-matrix by event_id, and nothing here reads label_gap, reach_*, minutes_to_mu, net, gross or
any other outcome column. `vault_loader.load_vault_events()` (the labels join) is NOT called here; step 4 calls
it AFTER this script's predictions file is saved. So label_gap handling is not applied here: ALL vault events
are scored (the count must equal the coverage check's), and step 4 applies harness's own label_gap == 0 rule
when it joins labels.

    python -u research/model/s1_vault_score.py > research/model/logs/s1/s1_vault_score.log

Checks (all printed, any failure = hard abort before anything is saved):
  1. the model JSON and weights file are loaded by sha256 (EXPECTED_* constants = the shas reported at the end
     of step 2b and checked by the checker); the saved model's out_cols/b/w lengths agree.
  2. preprocessing uses the SAVED stats (clip_lo/clip_hi/mean/sd/ticker levels/nan-indicator list from the
     model JSON) via s1_preprocess.apply_preprocessing -- fit_preprocessing is never called; the output
     column list equals the model's out_cols.
  3. the number of vault events equals the coverage check's count, PARSED from its log (not typed).
  4. every scored event has t0 >= VAULT_START; event_ids unique; predictions finite and in [0, 1];
     p_2h <= p_5h <= p_10h for every event (cumulative hazard is monotone in the horizon).
Scores in chunks (CHUNK events at a time) so memory stays bounded. Output: research/model/logs/s1/
s1_vault_predictions.parquet (event_id, p_2h, p_5h, p_10h) plus its sha256 printed.
"""
import hashlib
import json
import os
import re
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import vault_loader as VL  # noqa: E402  (also puts research/model first on sys.path again)
import harness as H  # noqa: E402
import s1_run as S1R  # noqa: E402 -- only compute_p_h / OUT_DIR / SEED are used
from s1_preprocess import apply_preprocessing, TICKER_COLS  # noqa: E402

OUT_DIR = S1R.OUT_DIR
MODEL_JSON = os.path.join(OUT_DIR, "s1_prevault_model.json")
MODEL_W = os.path.join(OUT_DIR, "s1_prevault_model_w.npy")
COVERAGE_LOG = os.path.join(OUT_DIR, "s1_vault_coverage_check.log")
PRED_OUT = os.path.join(OUT_DIR, "s1_vault_predictions.parquet")
# shas of the step-2b outputs as reported (round 4, instance i-0eb1f51d55a4103b4) and checked by the checker
EXPECTED_MODEL_JSON_SHA = "c30bbfa6fd7ccf8bc0559625eb30aaf2e144d994f4ac33f4c77cb412a3bd0cda"
EXPECTED_MODEL_W_SHA = "8af9ee742dff542ff34f61611ab0cb771a867b1b604d8acc7b400c3e471a27f5"
CHUNK = 100_000
REQUIRED_FILES = ("s1_prevault_model.json", "s1_prevault_model_w.npy", "s1_vault_coverage_check.log")


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
    for name in ("s1_vault_score.py", "vault_loader.py", "harness.py", "s1_preprocess.py", "s1_run.py"):
        log(f"[VAULTSCORE] sha256 {name}: {MF.sha(os.path.join(HERE, name))}")
    log(f"[VAULTSCORE] start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC; features only, no label/outcome column read")

    missing = [f for f in REQUIRED_FILES if not os.path.exists(os.path.join(OUT_DIR, f))]
    assert not missing, f"missing required file(s) in {OUT_DIR}: {missing}"
    # 1. model by sha
    sj, sw = sha256_file(MODEL_JSON), sha256_file(MODEL_W)
    log(f"[VAULTSCORE] model json sha256 {sj} (expected {EXPECTED_MODEL_JSON_SHA})")
    log(f"[VAULTSCORE] model w    sha256 {sw} (expected {EXPECTED_MODEL_W_SHA})")
    assert sj == EXPECTED_MODEL_JSON_SHA and sw == EXPECTED_MODEL_W_SHA, "saved model does not match the reviewed shas"
    model = json.load(open(MODEL_JSON))
    w = np.load(MODEL_W)
    b = np.array(model["b"])
    assert len(w) == len(model["out_cols"]) and len(b) == H.N_STEPS
    log(f"[VAULTSCORE] model: n_features={len(w)} n_nonzero={int((w != 0).sum())} n_steps={len(b)} "
        f"lam={model['settings']['lam']:.6g} l1_ratio={model['settings']['l1_ratio']} "
        f"fit n_events={model['settings']['n_events']:,}")

    # 2. SAVED stats (never refit)
    stats = dict(
        fit_cols=model["fit_cols"], final_numeric=model["final_numeric"],
        clip_lo=np.array(model["clip_lo"]), clip_hi=np.array(model["clip_hi"]),
        mean=np.array(model["mean"]), sd=np.array(model["sd"]),
        nan_indicator_cols=model["nan_indicator_cols"], ticker_levels=model["ticker_levels"])
    in_cols = H._cache_info()["columns"]
    assert len(in_cols) == 1091 and list(in_cols) == stats["fit_cols"], "cache columns != the model's fit_cols"

    # 3. the vault event list: events.parquet only
    vault = VL.load_vault_event_dates()
    ids = vault["event_id"].to_numpy()
    cov = open(COVERAGE_LOG).read()
    m = re.search(r"\[VAULTCOV\] vault window: .*?, ([\d,]+) pair events total", cov)
    n_cov = int(m.group(1).replace(",", ""))
    log(f"[VAULTSCORE] vault events {len(ids):,}; coverage check's count (parsed from its log) {n_cov:,}")
    assert len(ids) == n_cov, "vault event count != the coverage check's"
    assert len(np.unique(ids)) == len(ids)
    assert (vault["t0"] >= H.VAULT_START).all()
    ids = np.sort(ids)

    # 3b. record (report only, no effect on any score) how many vault events carry a coin the model never saw:
    # apply_preprocessing gives an unseen coin an all-zero one-hot (A6's "unseen" level).
    codes, _ = H.load_features_cached(ids, list(TICKER_COLS))
    names = vault.loc[ids]
    for j, leg in enumerate(("ticker_a", "ticker_b")):
        seen = np.isin(codes[:, j], np.array(stats["ticker_levels"][leg]))
        unseen_coins = sorted(names.loc[~seen, leg].unique())
        log(f"[VAULTSCORE] unseen {leg}: {int((~seen).sum()):,} of {len(ids):,} vault events have a {leg} coin not in the "
            f"model's levels; coins: {unseen_coins}")
    both = ~(np.isin(codes[:, 0], np.array(stats["ticker_levels"]["ticker_a"])) &
             np.isin(codes[:, 1], np.array(stats["ticker_levels"]["ticker_b"])))
    log(f"[VAULTSCORE] events with at least one unseen leg: {int(both.sum()):,} of {len(ids):,}")
    del codes

    # 4. score in chunks
    preds = {"p_2h": [], "p_5h": [], "p_10h": []}
    for i in range(0, len(ids), CHUNK):
        chunk = ids[i:i + CHUNK]
        X, out_cols = apply_preprocessing(chunk, in_cols, stats)
        assert out_cols == model["out_cols"], "preprocessed column list != the model's out_cols"
        preds["p_2h"].append(S1R.compute_p_h(w, b, X, 4))
        preds["p_5h"].append(S1R.compute_p_h(w, b, X, 10))
        preds["p_10h"].append(S1R.compute_p_h(w, b, X, H.N_STEPS))
        del X
        log(f"[VAULTSCORE] scored {min(i + CHUNK, len(ids)):,} / {len(ids):,}  [{time.time()-t0:.0f}s]")
    out = pd.DataFrame({"event_id": ids, **{k: np.concatenate(v) for k, v in preds.items()}})
    for c in ("p_2h", "p_5h", "p_10h"):
        assert np.isfinite(out[c]).all() and out[c].between(0, 1).all(), f"{c}: non-finite or outside [0,1]"
    assert (out["p_2h"] <= out["p_5h"] + 1e-12).all() and (out["p_5h"] <= out["p_10h"] + 1e-12).all()
    log("[VAULTSCORE] sanity: all predictions finite, in [0,1], and p_2h <= p_5h <= p_10h for every event")
    log("[VAULTSCORE] prediction summary (predictions only, no outcomes): "
        + "; ".join(f"{c} mean={out[c].mean():.4f} q50={out[c].quantile(.5):.4f} q99={out[c].quantile(.99):.4f} "
                    f"max={out[c].max():.4f}" for c in ("p_2h", "p_5h", "p_10h")))
    os.makedirs(OUT_DIR, exist_ok=True)
    out.to_parquet(PRED_OUT, index=False)
    log(f"[VAULTSCORE] saved {PRED_OUT}: {len(out):,} rows, sha256 {sha256_file(PRED_OUT)}  [{time.time()-t0:.0f}s]")


if __name__ == "__main__":
    main()
