"""HL-MASTER1 label receipts (descriptive, no model): outcome shares and net returns per stop, by unit.

    python -u research/dataset/master_label_summary.py > research/dataset/logs/master_label_summary.log
"""
import os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "research", "dislocation_model"))
import paths

for unit in ("pair", "coin"):
    d = os.path.join(paths.DATASETS, "master", "work", unit)
    L = pd.read_parquet(os.path.join(d, "labels.parquet"))
    E = pd.read_parquet(os.path.join(d, "events.parquet"), columns=["event_id", "z", "entry_time"])
    ok = L.label_gap == 0
    print(f"== {unit}: {len(L):,} events, label_gap {int((~ok).sum()):,} ({100 * (~ok).mean():.2f}%)")
    print(f"   reach 2h/5h/10h {L.reach_2h[ok].mean():.4f} / {L.reach_5h[ok].mean():.4f} / {L.reach_10h[ok].mean():.4f}; mean chance {L.chance_2h[ok].mean():.4f} / {L.chance_5h[ok].mean():.4f} / {L.chance_10h[ok].mean():.4f}")
    print(f"   adverse (widened by >= |z| within 10 h) {L.adverse[ok].mean():.4f}; median minutes_to_mu of reachers {L.minutes_to_mu.median():.0f}; mfe median {L.mfe_sigma[ok].median():.3f}, mae median {L.mae_sigma[ok].median():.3f} sigma")
    print(f"   fee_sigma taker median {L.fee_sigma_taker[ok].median():.4f}, p5 {L.fee_sigma_taker[ok].quantile(.05):.4f}, p95 {L.fee_sigma_taker[ok].quantile(.95):.4f}; maker median {L.fee_sigma_maker[ok].median():.4f}")
    print(f"   {'stop':<6}{'mu first':>10}{'stopped':>10}{'neither':>10}{'gross mean':>12}{'net taker mean':>16}{'net taker median':>18}{'net maker mean':>16}{'net maker median':>18}")
    for s in ("0p5", "1p0", "2p0", "none"):
        o = L[f"outcome_{s}"][ok]
        print(f"   {s:<6}{(o == 1).mean():>10.4f}{(o == -1).mean():>10.4f}{(o == 0).mean():>10.4f}{L[f'gross_{s}'][ok].mean():>+12.4f}{L[f'net_{s}_taker'][ok].mean():>+16.4f}"
              f"{L[f'net_{s}_taker'][ok].median():>+18.4f}{L[f'net_{s}_maker'][ok].mean():>+16.4f}{L[f'net_{s}_maker'][ok].median():>+18.4f}")
    m = pd.to_datetime(E.entry_time).dt.to_period("M")
    t = L.assign(m=m.values)[ok.values].groupby("m").agg(n=("event_id", "size"), reach=("reach_10h", "mean"), chance=("chance_10h", "mean"), net1=("net_1p0_taker", "mean"), gap=("label_gap", "mean"))
    print("   by month (reach_10h, mean chance_10h, mean net_1p0_taker):")
    print(t.round(4).to_string())
    full = L.groupby(m.values).label_gap.mean()
    print("   label_gap share by month: " + ", ".join(f"{k} {v:.4f}" for k, v in full.items()))
