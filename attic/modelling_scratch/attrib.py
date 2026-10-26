"""Is the 0.28 vs 0.112 gap PERIOD or SELECTION?

The traded sample ran 2026-08-26 to 2026-09-29 and recorded +0.28 sigma gross.
The unselected set over 746 days gives 0.112. Measure the UNSELECTED
dislocations inside that same window -- if they also give ~0.28 the gap is the
period; if they give ~0.112 the gap is selection.

Descriptive. Positive = toward the mean.
"""
import numpy as np, pandas as pd
S="/private/tmp/claude-501/-Users-elvisobondo-Pair-Trading/0189ea06-e901-4d24-83ff-b7b3c5ca8f65/scratchpad/"
z=np.load(S+"disloc.npz"); Y=z["outcomes"].astype(float)
M=pd.read_parquet(S+"disloc_meta.parquet"); day=pd.to_datetime(M.day).to_numpy()
e=Y[:,0]; s=np.sign(e); s[s==0]=1
mv=-(Y[:,20]-e)*s
def band(sub,B=400,seed=5):
    d=day[sub]; du=np.unique(d); pos={x:sub[d==x] for x in du}
    rb=np.random.default_rng(seed); o=np.empty(B)
    for i in range(B):
        o[i]=mv[np.concatenate([pos[x] for x in rb.choice(du,len(du),replace=True)])].mean()
    return np.percentile(o,2.5),np.percentile(o,97.5)
A=np.datetime64("2026-08-26"); B_=np.datetime64("2026-09-29")
win=np.flatnonzero((day>=A)&(day<=B_)); allx=np.arange(len(mv))
held=np.flatnonzero(day>=np.datetime64("2026-07-18"))
print(f"{'window':<34}{'n':>8}{'days':>7}{'mean':>9}{'95% day-clustered':>21}{'median':>9}")
for nm,ix in (("full history, 746 days",allx),("held-out slice, from 2026-07-18",held),
              ("TRADED WINDOW 2026-08-26..09-29",win)):
    lo,hi=band(ix)
    print(f"{nm:<34}{len(ix):>8,}{len(np.unique(day[ix])):>7}{mv[ix].mean():>9.3f}"
          f"  [{lo:>7.3f},{hi:>7.3f}]{np.median(mv[ix]):>9.3f}")
w=mv[win].mean(); lo,hi=band(win)
print(f"\n  traded figure 0.28   unselected same window {w:.3f}  "
      f"full history 0.112")
print(f"  distance to 0.28: {abs(w-0.28):.3f}   distance to 0.112: {abs(w-0.112):.3f}")
print(f"  0.28 {'INSIDE' if lo<=0.28<=hi else 'OUTSIDE'} the window's interval; "
      f"0.112 {'INSIDE' if lo<=0.112<=hi else 'OUTSIDE'} it")
print(f"\n  VERDICT: {'PERIOD -- the window itself was favourable' if abs(w-0.28)<abs(w-0.112) else 'SELECTION -- the window alone does not explain it'}")
print(f"\n  month by month, unselected, mean signed move at 10h:")
for m_,g in pd.DataFrame({"m":pd.to_datetime(M.day).dt.to_period("M").astype(str),"v":mv}).groupby("m"):
    if len(g)<300: continue
    print(f"    {m_}  n{len(g):>6}  {g.v.mean():>+7.3f}")
