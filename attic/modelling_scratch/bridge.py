"""The bridge: does the real window carry the 7.68% the oracle gets on synthetic?

The oracle reaches centre R2 7.68% on data generated from E0's vector. My
real-data test found <0.1%. One of them is wrong about the real world, and the
weak link is mine -- 18 summary features instead of the path.

A Kalman filter's state estimate is LINEAR in the observations, so the oracle's
centre is a linear function of the 336-bar window. A ridge regression on the
whole window therefore UPPER-BOUNDS what any correctly-fitted filter of this
class can extract. Run it on synthetic first: if it recovers ~7.68% there, the
method is sound and its number on real data is the answer.

Sign-folded (a dislocation at -3 is the mirror of one at +3) and scored out of
sample -- by calendar day on real data, by held-out series on synthetic.
"""
import sys, time
sys.path.insert(0,"/Users/elvisobondo/Pair_Trading/research")
import numpy as np, pandas as pd
exec(open("/private/tmp/claude-501/-Users-elvisobondo-Pair-Trading/0189ea06-e901-4d24-83ff-b7b3c5ca8f65/scratchpad/oracle.py").read().split("TRUTHS=[")[0])

def ridge_r2(Xtr,ytr,Xte,yte,lams=(1,10,100,1e3,1e4,1e5,1e6)):
    """Ridge on standardised columns; penalty picked on a slice of TRAIN only."""
    mn,sd=Xtr.mean(0),np.where(Xtr.std(0)>0,Xtr.std(0),1.0)
    A=(Xtr-mn)/sd; B=(Xte-mn)/sd
    cut=int(0.8*len(A)); best=(None,-9e9)
    G=A[:cut].T@A[:cut]; g=A[:cut].T@(ytr[:cut]-ytr[:cut].mean())
    for lam in lams:
        w=np.linalg.solve(G+lam*np.eye(A.shape[1]),g)
        p=A[cut:]@w+ytr[:cut].mean(); yv=ytr[cut:]
        s=1-((yv-p)**2).sum()/((yv-ytr[:cut].mean())**2).sum()
        if s>best[1]: best=(lam,s)
    lam=best[0]
    w=np.linalg.solve(A.T@A+lam*np.eye(A.shape[1]),A.T@(ytr-ytr.mean()))
    p=B@w+ytr.mean()
    # scored against the intercept-only model trained the same way, so a level
    # shift between periods is not charged to the features
    return 1-((yte-p)**2).sum()/((yte-ytr.mean())**2).sum(), lam

# ---------- 1. validate on synthetic, where the answer is known ----------
print("=== synthetic, E0's vector: does a ridge on the window find the oracle's 7.68%? ===")
kr,kd,qL,qX,r,qrd,qdr=0.0850,-0.0200,0.4880,0.4750,0.0980,0.0379,0.0912
S=generate(kr,kd,qL,qX,r,qrd,qdr,nser=800,T=16000,seed=1)
W,Y,sg=screen(S,want=12000)
s=np.sign((Y[:,0]-W[:,:EW].mean(1))); s[s==0]=1.0
Xw=(W-W[:,-1:])/sg[:,None]*s[:,None]          # window relative to the entry bar, sigma units, folded
yy=(Y[:,HOR]-Y[:,0])/sg*s
n=len(W); tr=np.arange(n)<int(.7*n); te=~tr
v,lam=ridge_r2(Xw[tr],yy[tr],Xw[te],yy[te])
print(f"  n {n}   ridge on 336 bars, held out: {100*v:.2f}%   (lambda {lam:g})")
T=np.array([[1-qrd,qrd],[qdr,1-qdr]])
o=forecast(W[te],[kr,kd],qL,qX,r,T)
orc=np.corrcoef((o[HOR].mean(1)-Y[te,0])/sg[te],yy[te]*s[te]*s[te])[0,1]**2
print(f"  oracle filter on the same held-out rows:  {100*orc:.2f}%")
print(f"  -> the ridge {'RECOVERS' if v>0.6*orc else 'MISSES'} the oracle's signal\n")

# ---------- 2. the same ridge on real data ----------
print("=== real, 60,000 dislocations over 746 days ===")
D="/private/tmp/claude-501/-Users-elvisobondo-Pair-Trading/0189ea06-e901-4d24-83ff-b7b3c5ca8f65/scratchpad/disloc"
z=np.load(D+".npz"); RW=z["windows"].astype(float); RY=z["outcomes"].astype(float)
M=pd.read_parquet(D+"_meta.parquet"); day=M.day.to_numpy()
days=np.sort(pd.unique(day)); cum=np.searchsorted(np.sort(day),days,side="right")/len(M)
CUT=days[np.searchsorted(cum,0.70)]
rs=np.sign(RY[:,0]); rs[rs==0]=1.0
RX=(RW-RW[:,-1:])*rs[:,None]                  # already in entry-sigma units
ry=(RY[:,HOR]-RY[:,0])*rs
rtr=day<CUT; rte=~rtr
v2,lam2=ridge_r2(RX[rtr],ry[rtr],RX[rte],ry[rte])
print(f"  n {len(M)}   fit {rtr.sum():,} / held out {rte.sum():,} by calendar day")
print(f"  ridge on 336 bars, held out: {100*v2:.2f}%   (lambda {lam2:g})")

dtr=np.unique(day[rtr]); pos={d:np.flatnonzero(day==d) for d in dtr}
rb=np.random.default_rng(7); bs=[]
for _ in range(60):
    sel=np.concatenate([pos[d] for d in rb.choice(dtr,len(dtr),replace=True)])
    bs.append(ridge_r2(RX[sel],ry[sel],RX[rte],ry[rte])[0])
bs=np.array(bs)
print(f"  day-clustered 60 resamples: [{100*np.percentile(bs,5):.2f}%, {100*np.percentile(bs,95):.2f}%]")
print(f"\n  gate needs 9.75%.  oracle on E0's vector got 7.68% on synthetic.")
