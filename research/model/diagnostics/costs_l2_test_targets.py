"""COSTS1 20-file test pull list (checker E2; widened 2026-11-14 to every minute of the comparison window, see the rules file's VALIDATION paragraph). 10 (coin, day, hour) pairs x two adjacent
folder hours = 20 files; every file asks for minutes 2..59 of hour H and minutes 0, 1 of hour H+1 (60 coin-minutes per coin-day, 600 in all; minutes 0, 1 of H are not asked because their
file H-1 is not pulled), so the data show which folder supplies a boundary minute, how snapshot offsets look, and give 600 books x 2 sides x 7 sizes to compare with the curve.
Coverage: a k-prefixed coin (kPEPE), thin and liquid coins (ZRO, W, LINEA, ADA), days on both sides of the cadence change (2026-01-15, 2026-03-01 full cadence;
2026-04-15 unknown; 2026-08-01 and 2026-09-15 vault days; 2026-09-15 is the pilot's low-cadence day).
    python -u research/model/diagnostics/costs_l2_test_targets.py > research/model/diagnostics/costs_l2_test_targets.log
"""
import os

import pandas as pd

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "costs1", "l2_targets_test20.parquet")
PAIRS = [("kPEPE", "20260115", 10), ("ADA", "20260115", 10), ("ZRO", "20260301", 13), ("kPEPE", "20260301", 13), ("ADA", "20260415", 7), ("ZRO", "20260415", 7),
         ("kPEPE", "20260801", 20), ("W", "20260801", 20), ("ADA", "20260915", 9), ("LINEA", "20260915", 9)]
# ---- ADDED 2026-11-14 (planner ruling), a rule fixed before it was run: least-liquid coin-days. Per period (vault, test months): the least-liquid-third coins (tier mapping of
# logs/costs1/costs_analysis_conservative.json) ranked by their number of trades in the four priority runs of that period (a trade counts for both legs; ties: coin name ascending);
# the top 3 coins; for each, ONE coin-day = the UTC entry day on which that coin has the most trades in the period (ties: earliest day), and on that day the entry hour H (0..22, so that H+1
# is the same day) with the most entry trades of the coin (ties: earliest hour); files H and H+1 as above, same 60 minutes. A coin already in the fixed list on the same day is still added (the rule is not changed by outcome).
import json
T_ = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
tiers = json.load(open(os.path.join(T_, "costs1", "costs_analysis_conservative.json")))["tier_coins"]
EXTRA = []
for per, sfxs in (("vault", ["_vault_open10", "_vault_open20"]), ("test", ["", "_open20"])):
    fr = []
    for sfx in sfxs:
        for fee in ("maker", "taker"):
            d = pd.read_parquet(os.path.join(T_, "profit1", f"trades_q0.01_stopnone_fee{fee}{sfx}.parquet"), columns=["ticker_a", "ticker_b", "t0"])
            d["t0"] = pd.to_datetime(d["t0"], utc=True)
            fr.append(pd.concat([d[["ticker_a", "t0"]].rename(columns={"ticker_a": "coin"}), d[["ticker_b", "t0"]].rename(columns={"ticker_b": "coin"})]))
    D = pd.concat(fr, ignore_index=True)
    D["day"], D["hour"] = D["t0"].dt.strftime("%Y%m%d"), D["t0"].dt.hour
    least = set(tiers[per]["least liquid third"])
    cnt = D[D["coin"].isin(least)].groupby("coin").size().reset_index(name="n").sort_values(["n", "coin"], ascending=[False, True])
    for coin in cnt["coin"].head(3):
        dc = D[D["coin"] == coin].groupby("day").size().reset_index(name="n").sort_values(["n", "day"], ascending=[False, True])
        day = dc["day"].iloc[0]
        hc = D[(D["coin"] == coin) & (D["day"] == day) & (D["hour"] <= 22)].groupby("hour").size().reset_index(name="n").sort_values(["n", "hour"], ascending=[False, True])
        hour = int(hc["hour"].iloc[0])
        EXTRA.append((coin, day, hour))
        print(f"[TEST20] least-liquid rule, {per}: coin {coin} ({int(cnt.set_index('coin').loc[coin, 'n']):,} trades in the period's four priority runs), day {day} ({int(dc['n'].iloc[0])} trades that day), hour {hour} ({int(hc['hour'].eq(hour).sum() and hc.loc[hc['hour'] == hour, 'n'].iloc[0])} trades)")
PAIRS = PAIRS + EXTRA
rows = []
for coin, day, h in PAIRS:
    h0 = int((pd.Timestamp(day, tz="UTC") - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(hours=1)) + h
    mins = sorted({h0 * 60 + k for k in range(2, 60)} | {(h0 + 1) * 60, (h0 + 1) * 60 + 1})      # minutes 2..59 of hour H and 0, 1 of H+1 (60 minutes): every minute is asked from BOTH files, the extractor keeps the minimum exchange time
    for hh in (h, h + 1):
        rows.append(dict(coin=coin, day=day, hour=hh, minutes=mins, n_minutes=len(mins)))
T = pd.DataFrame(rows)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
T.to_parquet(OUT, index=False)
print(f"[TEST20] {len(T)} files, wrote {OUT}")
print(T[["coin", "day", "hour", "n_minutes"]].to_string())
