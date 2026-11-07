"""HL-MODEL1 S1-G: small follow-up pass, run after the main G1-G7 run finished (so G3's ~41-minute
preprocessing is never repeated). Two user amendments land here, both reusing the exact same pick sets
(recomputed via S.compute_picks and cross-checked against S1-F's saved per-fold n/c_k, same as the main
run):

1. Size in sigma (2026-11-07, G7 amendment): patches G7's distance_by_q to report median+quartiles of
   |z| and |z|-threshold (the main script's updated _distance_to_mu), keeping |z| x sigma JSON-only.
2. G8 (2026-11-07, new item, corrected same day to "distance vs the model's probability, not vs
   reversion"): |z| decile bins (folds 1-7 pooled, edges printed); per bin, for all events and for each
   q's picks on the SAME edges: n and the model's p_10h (mean/median/q25/q75), with actual reach_10h as
   a side column only. No chance_10h, no picks-minus-rest column (dropped per the correction).

Both write into the same already-saved research/model/logs/s1/s1g_report.json: distance_by_q (patched
again here, idempotent -- same numbers as the first run of this script) and a new top-level
g8_distance_vs_probability key.

    python -u research/model/s1g_distance_patch.py > research/model/logs/s1/s1g_distance_patch.log
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import s1g_top1_deep as S  # noqa: E402

LOG_DIR = S.LOG_DIR


def main():
    t0 = time.time()
    import master_manifest as MF
    for name in ("s1g_distance_patch.py", "s1g_top1_deep.py"):
        print(f"[S1G-PATCH] sha256 {name}: {MF.sha(os.path.join(HERE, name))}", flush=True)
    print(f"[S1G-PATCH] start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} UTC; pid {os.getpid()}",
          flush=True)

    df, events = S.load_data()
    s1f_report = json.load(open(os.path.join(LOG_DIR, "s1f_report.json")))
    block_df, _ = S.compute_picks(df, s1f_report)
    print(f"[S1G-PATCH] pick sets recomputed and cross-checked (same as the main run)  "
          f"[{time.time()-t0:.0f}s]", flush=True)

    report_path = os.path.join(LOG_DIR, "s1g_report.json")
    out = json.load(open(report_path))
    old_distance = out["g7_tighter_cutoffs"]["distance_by_q"]
    print(f"[S1G-PATCH] old distance_by_q keys (pre-amendment, |z|xsigma only): "
          f"{list(old_distance.get(str(S.TIGHT_QS[0]), old_distance.get(S.TIGHT_QS[0], {})).get('picks', {}).keys())}",
          flush=True)

    new_distance = {}
    for q in S.TIGHT_QS:
        col = S.pick_col(q)
        picks = block_df[block_df[col]]
        rest = block_df[~block_df[col]]
        new_distance[q] = {"picks": S._distance_to_mu(picks), "rest": S._distance_to_mu(rest)}
        print(f"[S1G-PATCH] q={q}: picks median |z|={new_distance[q]['picks']['abs_z']['median']:.4f} "
              f"median |z|-threshold={new_distance[q]['picks']['abs_z_minus_threshold']['median']:.4f} "
              f"(JSON-only |z|xsigma median={new_distance[q]['picks']['abs_z_times_sigma_json_only']['median']:.6f})",
              flush=True)

    out["g7_tighter_cutoffs"]["distance_by_q"] = new_distance

    g8 = S.g8_distance_vs_probability(block_df)
    out["g8_distance_vs_probability"] = g8
    print(f"[S1G-PATCH] G8 computed  [{time.time()-t0:.0f}s]", flush=True)

    with open(report_path, "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(f"[S1G-PATCH] rewrote {report_path} with the sigma-based distance_by_q and g8_distance_vs_probability "
          f"[{time.time()-t0:.0f}s]", flush=True)
    print("[S1G-PATCH] ALL DONE", flush=True)


if __name__ == "__main__":
    main()
