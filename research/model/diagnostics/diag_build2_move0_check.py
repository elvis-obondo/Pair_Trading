import sys, os
sys.path.insert(0, "/Users/elvisobondo/Pair_Trading/research/model")
os.chdir("/Users/elvisobondo/Pair_Trading")
import numpy as np
import pandas as pd
import s1_profit1 as S
import warnings
warnings.filterwarnings("ignore")

picks = S.load_picks_and_pcal()
top1 = picks[picks["pick_0.01"]].copy()
event_ids = top1["event_id"].to_numpy()
geo = S.load_geometry_and_labels(event_ids)

coins = sorted(set(geo["ticker_a"]) | set(geo["ticker_b"]))
no_data = S.ensure_build2_1m_cached(coins)
print("coins without build2 1m:", no_data)
dense_price, price_diag = S.build_dense_price(coins)

paths, coverage_rows, status = S.compute_move_paths(top1, geo, dense_price)
from collections import Counter
print(Counter(status.values()))
