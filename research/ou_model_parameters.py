from data_loader import get_price_levels
from ou_model import fit_ou
import pandas as pd

df = get_price_levels()
cutoff = df.index.max() - pd.Timedelta(days=30)
df = df[df.index >= cutoff]

pa = df["AVAX"].dropna().values

pb = df["LINK"].dropna().values

p = fit_ou(pa, pb)
print(f"theta: {p.theta:.6f} per hour")
print(f"mu:    {p.mu:.6f}")
print(f"sigma: {p.sigma:.6f}")
print(f"implied half-life: {round(0.693 / p.theta / 24, 2)} days")