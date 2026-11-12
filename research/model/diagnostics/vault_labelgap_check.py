"""HL-VAULT1 read-only check (checker's request, 2026-11-12): why does the vault have 0 label_gap=1 events
(the search period had 27,049, 0.50%)? Reads events.parquet (entry_time, tickers) and ONLY the label_gap /
label_nan_minutes columns of labels.parquet -- no outcome column -- plus each coin's last 1-minute bar from the
build2 1m cache (the series v1's labels were built on). Changes nothing; no pick is touched.

HOW v1 SETS label_gap (cited): research/dataset/master_labels.py:9 (docstring: "If ANY of the 601 minutes is NaN
(an archive hole or a missing minute) every label of the event is NaN and label_gap = 1") and :80-89
(`nanmin = np.isnan(P).sum(1); gap = nanmin > 0`; label_gap = gap); the window comes from
research/dislocation_model/envelope.py:345-351 (_window: "n values from arr at integer offset off, NaN-padded
outside the array"), so a window that runs PAST the end of a coin's series is NaN-padded and the event gets
label_gap = 1. An end-of-data event is therefore NOT labelled as complete.

    python -u research/model/diagnostics/vault_labelgap_check.py > research/model/diagnostics/vault_labelgap_check.log
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.dirname(HERE)
sys.path.insert(0, MODEL)
import vault_loader as VL  # noqa: E402
import harness as H  # noqa: E402
import master_manifest as MF  # noqa: E402

CACHE = os.path.join(MODEL, "logs", "profit1", "build2_1m_cache")
PICKS = os.path.join(MODEL, "logs", "s1", "s1_vault_picks.parquet")


def main():
    ev = VL.load_vault_event_dates()                       # events.parquet only
    lab = MF.open_version(H.VERSION, H.UNIT, "labels.parquet", columns=["event_id", "label_gap", "label_nan_minutes"])
    lab_all = lab.copy()
    lab = lab[lab["event_id"].isin(ev["event_id"])].set_index("event_id").loc[ev["event_id"]]
    print(f"[LGCHECK] vault events {len(ev):,}; label_gap value counts (vault): {lab['label_gap'].value_counts().to_dict()}; "
          f"label_nan_minutes value counts (vault): {lab['label_nan_minutes'].value_counts().to_dict()}")
    # search period for comparison: all rows of labels.parquet with an event_id below the vault's
    n_all = len(lab_all)
    print(f"[LGCHECK] whole v1 labels.parquet: {n_all:,} rows; label_gap value counts: "
          f"{lab_all['label_gap'].value_counts().to_dict()}")

    coins = sorted(set(ev["ticker_a"]) | set(ev["ticker_b"]))
    end = {}
    for c in coins:
        d = pd.read_feather(os.path.join(CACHE, f"{c}-1m.feather"), columns=["date"])
        end[c] = pd.to_datetime(d["date"], utc=True).max()
    last_global = max(end.values())
    print(f"[LGCHECK] {len(coins)} vault coins; last 1-minute bar over all of them: {last_global}; "
          f"earliest per-coin last bar: {min(end.values())} ({min(end, key=end.get)})")
    # the label window for event j is minutes entry_time+29 .. entry_time+29+600 (master_labels.py:3, :62-66)
    entry = pd.to_datetime(ev["entry_time"], utc=True)
    win_end = entry + pd.Timedelta(minutes=29 + 600)
    leg_end = np.minimum(ev["ticker_a"].map(end).to_numpy(dtype="datetime64[ns]"),
                         ev["ticker_b"].map(end).to_numpy(dtype="datetime64[ns]"))
    past_leg = win_end.to_numpy(dtype="datetime64[ns]") > leg_end
    past_global = win_end > last_global
    print(f"[LGCHECK] latest vault event: entry_time {entry.max()}, t0 {ev['t0'].max()}, its label window ends {win_end.max()}")
    print(f"[LGCHECK] (a) vault events whose 601-minute window ends after the last bar of the global series: "
          f"{int(past_global.sum()):,}; after the last bar of either of their own two legs: {int(past_leg.sum()):,}; "
          f"t0 + 10 h > last global bar: {int((ev['t0'] + pd.Timedelta(hours=10) > last_global).sum()):,}")
    picks = pd.read_parquet(PICKS, columns=["event_id", "pick_0.01", "pick_0.005", "pick_0.001"]).set_index("event_id")
    flag = pd.Series(past_leg, index=ev["event_id"].to_numpy())
    for q in (0.01, 0.005, 0.001):
        pk = picks.index[picks[f"pick_{q}"]]
        print(f"[LGCHECK] (a) picks q={q}: {len(pk):,}; of them with a window past either leg's last bar: {int(flag.loc[pk].sum()):,}")
    # distribution of how much margin the latest events have
    margin = (leg_end - win_end.to_numpy(dtype="datetime64[ns]")) / np.timedelta64(1, "m")
    print(f"[LGCHECK] margin (minutes between the window end and the nearer leg's last bar): min {np.min(margin):.0f}, "
          f"q01 {np.quantile(margin, 0.01):.0f}, median {np.median(margin):.0f}")
    print(f"[LGCHECK] events by entry month: " + ", ".join(f"{m}: {n:,}" for m, n in
          entry.dt.strftime('%Y-%m').value_counts().sort_index().items()))
    print(f"[LGCHECK] last day of events.parquet in the vault: {entry.max().date()}; "
          f"events on the last 3 UTC days: " + ", ".join(f"{d}: {n:,}" for d, n in
          entry.dt.date.value_counts().sort_index().tail(3).items()))


if __name__ == "__main__":
    main()
