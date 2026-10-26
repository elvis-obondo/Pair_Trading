"""How much does the spread actually revert, and is it stable?

The ceiling test turned up a level shift: mean 10-hour change in the entry's
own direction was -0.0164 sigma over the fit period's 667 days and -0.3354 over
the held-out 79. If that is real, the gross reversion this project is built on
is not a constant -- it is a recent-period effect. Measured by month, with a
day-clustered band, at every horizon.

Negative = the spread moved BACK toward the mean (reversion). The entry is at
|z|>=3, so a mean change of -0.33 means a third of a sigma of reversion.
"""
import numpy as np, pandas as pd
D="/private/tmp/claude-501/-Users-elvisobondo-Pair-Trading/0189ea06-e901-4d24-83ff-b7b3c5ca8f65/scratchpad/disloc"
z=np.load(D+".npz"); Y=z["outcomes"].astype(float)
M=pd.read_parquet(D+"_meta.parquet")
s=np.sign(Y[:,0]); s[s==0]=1.0
day=M.day.to_numpy(); mon=M.day.dt.to_period("M").astype(str).to_numpy()

def band(v,d,B=400,seed=3):
    """day-clustered CI on the mean of v"""
    du=np.unique(d); pos={x:np.flatnonzero(d==x) for x in du}
    rb=np.random.default_rng(seed); out=np.empty(B)
    for i in range(B):
        sel=np.concatenate([pos[x] for x in rb.choice(du,len(du),replace=True)])
        out[i]=v[sel].mean()
    return np.percentile(out,2.5),np.percentile(out,97.5)

print("mean change in the entry's own direction, sigma (negative = reverting)")
print(f"{'horizon':>8} {'all 746d':>10} {'95% CI':>18} {'median':>8}")
for h,lab in ((1,"0.5h"),(2,"1.0h"),(4,"2.0h"),(10,"5.0h"),(20,"10.0h")):
    v=(Y[:,h]-Y[:,0])*s
    lo,hi=band(v,day)
    print(f"{lab:>8} {v.mean():>10.4f}  [{lo:>+7.4f},{hi:>+7.4f}] {np.median(v):>8.4f}")

v20=(Y[:,20]-Y[:,0])*s
print(f"\n10-hour reversion by month (n, mean sigma, 95% CI)")
rows=[]
for mm in sorted(pd.unique(mon)):
    k=mon==mm
    if k.sum()<150: continue
    lo,hi=band(v20[k],day[k],B=200)
    rows.append((mm,k.sum(),v20[k].mean(),lo,hi))
for mm,n,mu_,lo,hi in rows:
    bar="#"*int(max(0,-mu_)*30)
    print(f"  {mm}  n{n:>6}  {mu_:>+8.4f}  [{lo:>+7.4f},{hi:>+7.4f}]  {bar}")

firsthalf=np.array([r[2] for r in rows[:len(rows)//2]])
second=np.array([r[2] for r in rows[len(rows)//2:]])
print(f"\nfirst half of the months: mean {firsthalf.mean():+.4f}   "
      f"second half: {second.mean():+.4f}")
neg=sum(1 for r in rows if r[4]<0)
print(f"months whose CI excludes zero on the reverting side: {neg} of {len(rows)}")
