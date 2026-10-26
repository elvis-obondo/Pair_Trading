"""Model-free bound on every linear predictor using the entry window.

No SDE, no parameters, no fitting problem. Decides whether item 5 is worth
doing. Target: change from entry to horizon h in entry-sigma units.

THE AGREED SPLIT, used everywhere: 2026-07-18, which is 70% of DISLOCATIONS
(not 70% of days -- volume is back-loaded as tickers list).

Ridge, penalty chosen on the LAST 20% of fit-period days, held out by time.
The held-out set is never touched for tuning. Run unfolded and sign-folded;
the two must agree or something is wrong.

R2 reported two ways:
  vs held-out mean  -- textbook out-of-sample R2, the headline
  vs fit-period mean of the target -- what the features add once the level
                       shift between periods is charged to the baseline
Interval: day-clustered bootstrap of the HELD-OUT days, model fixed -- the
sampling interval of the score, which is what "excludes zero" refers to.
CRPS equivalent = sqrt(1 - R2).
"""
import numpy as np, pandas as pd
D="/private/tmp/claude-501/-Users-elvisobondo-Pair-Trading/0189ea06-e901-4d24-83ff-b7b3c5ca8f65/scratchpad/disloc"
z=np.load(D+".npz"); W=z["windows"].astype(float); Y=z["outcomes"].astype(float)
M=pd.read_parquet(D+"_meta.parquet"); day=M.day.to_numpy()

CUT=np.datetime64("2026-07-18")
tr=day<CUT; te=~tr
dtr=np.sort(np.unique(day[tr])); dte=np.sort(np.unique(day[te]))
vcut=dtr[int(0.8*len(dtr))]                 # validation = last 20% of FIT days
sub=day[tr]<vcut
print(f"[SPLIT] cut {CUT}   fit {tr.sum():,} ({len(dtr)}d)   held out {te.sum():,} ({len(dte)}d)")
print(f"[TUNE ] validation = fit days from {vcut} ({(~sub).sum():,} rows); held-out never touched\n")

LAMS=(1e0,1e1,1e2,1e3,1e4,1e5,1e6,1e7)
def ridge(Xtr,ytr,Xte,msk):
    """fit on Xtr[msk], pick lambda on Xtr[~msk], refit on all of Xtr, predict Xte"""
    mn,sd=Xtr.mean(0),np.where(Xtr.std(0)>1e-12,Xtr.std(0),1.0)
    A=(Xtr-mn)/sd; B=(Xte-mn)/sd
    As,ys=A[msk],ytr[msk]; Av,yv=A[~msk],ytr[~msk]
    G=As.T@As; g=As.T@(ys-ys.mean()); I=np.eye(A.shape[1])
    best=(None,np.inf)
    for lam in LAMS:
        w=np.linalg.solve(G+lam*I,g); p=Av@w+ys.mean()
        e=((yv-p)**2).sum()
        if e<best[1]: best=(lam,e)
    lam=best[0]
    w=np.linalg.solve(A.T@A+lam*I,A.T@(ytr-ytr.mean()))
    return B@w+ytr.mean(), lam

rb=np.random.default_rng(11)
pos={d:np.flatnonzero(day[te]==d) for d in dte}
BOOT=[rb.choice(dte,len(dte),replace=True) for _ in range(400)]

def score(p,yte,ytr):
    r2h=1-((yte-p)**2).sum()/((yte-yte.mean())**2).sum()
    r2f=1-((yte-p)**2).sum()/((yte-ytr.mean())**2).sum()
    bs=np.empty(len(BOOT))
    for i,pick in enumerate(BOOT):
        s=np.concatenate([pos[d] for d in pick])
        bs[i]=1-((yte[s]-p[s])**2).sum()/((yte[s]-yte[s].mean())**2).sum()
    return r2h,r2f,np.percentile(bs,2.5),np.percentile(bs,97.5)

HOR=[(1,"0.5h"),(2,"1h"),(4,"2h"),(10,"5h"),(20,"10h")]
for fold in (False,True):
    s=np.sign(Y[:,0]); s[s==0]=1.0
    if not fold: s=np.ones(len(Y))
    Wf=W*s[:,None]
    VAR={"a z_entry only":Wf[:,-1:],
         "b 336 window bars":Wf,
         "c 335 differences":np.diff(Wf,axis=1)}
    print("="*96)
    print("SIGN-FOLDED" if fold else "UNFOLDED")
    print("="*96)
    print(f"{'variant':<20}{'h':>5}{'R2 vs held mean':>17}{'95% CI':>20}"
          f"{'R2 vs fit mean':>16}{'CRPS %clim':>12}{'lam':>7}")
    for name,X in VAR.items():
        for h,lab in HOR:
            y=(Y[:,h]-Y[:,0])*s
            p,lam=ridge(X[tr],y[tr],X[te],sub)
            r2h,r2f,lo,hi=score(p,y[te],y[tr])
            crps=100*np.sqrt(max(1-r2h,0.0))
            print(f"{name if lab=='0.5h' else '':<20}{lab:>5}{100*r2h:>16.3f}%"
                  f"  [{100*lo:>+6.2f},{100*hi:>+6.2f}]{100*r2f:>15.3f}%"
                  f"{crps:>11.1f}%{lam:>7.0e}")
        print(flush=True)
