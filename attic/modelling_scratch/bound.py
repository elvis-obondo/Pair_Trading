"""The ceiling on describing the spread, measured on 746 days instead of 35.

The CRPS decomposition left the CENTRE as the only lever that can move the
score, and the 95% gate needs the centre to explain ~9.75% of the variance of
the 10-hour change. On 2,538 dislocations over 35 days the held-out R2 had a
+/-2.5% error bar, so that question was unanswerable. This asks it on 60,000
over 746 days.

Honest throughout: climatology is pooled from the FIT period only and applied
to held out; every regression is trained on the fit period and scored on held
out; the split is by calendar time so no day appears in both.
"""
import numpy as np, pandas as pd
D="/private/tmp/claude-501/-Users-elvisobondo-Pair-Trading/0189ea06-e901-4d24-83ff-b7b3c5ca8f65/scratchpad/disloc"
z=np.load(D+".npz"); W=z["windows"].astype(float); Y=z["outcomes"].astype(float)
M=pd.read_parquet(D+"_meta.parquet")
N=len(M); y0=Y[:,0]
day=M.day.to_numpy()
days=np.sort(pd.unique(day))

# split so 70% of DISLOCATIONS are before the cut (volume is back-loaded as
# tickers list, so 70% of DAYS would leave only 36% of the data to fit on)
cum=np.searchsorted(np.sort(day),days,side="right")/N
CUT=days[np.searchsorted(cum,0.70)]
tr=day<CUT; te=~tr
print(f"[SPLIT] cut {pd.Timestamp(CUT).date()}   fit {tr.sum():,} ({100*tr.mean():.0f}%)   "
      f"held-out {te.sum():,} ({100*te.mean():.0f}%)   "
      f"days {len(np.unique(day[tr]))}/{len(np.unique(day[te]))}")

def crps(E,y):
    NS=E.shape[1]; t1=np.abs(E-y[:,None]).mean(1)
    Es=np.sort(E,1); j=np.arange(1,NS+1)
    return t1-0.5*(2.0/NS**2)*((2*j-NS-1)*Es).sum(1)

rng=np.random.default_rng(11)
for h,lab in ((1,"0.5h"),(2,"1.0h"),(4,"2.0h"),(20,"10.0h")):
    chg=Y[:,h]-y0
    pool=chg[tr]                                    # climatology from the fit period ONLY
    E=y0[te][:,None]+rng.choice(pool-pool.mean(),size=(te.sum(),200),replace=True)
    cl=crps(E,Y[te,h]).mean()
    print(f"[CLIMATOLOGY {lab:>5}]  CRPS {cl:.3f} sigma   held-out change sd {chg[te].std():.3f}"
          f"   fit-period sd {pool.std():.3f}")
    if h==20: CL20=cl

# ---- features, all observable at the entry bar ----
sg=M.sigma.to_numpy(float); bt=M.beta.to_numpy(float)
dW=np.diff(W,axis=1)
feat={
 "z_entry":     y0,
 "abs_z":       np.abs(y0),
 "r2":          M.r2.to_numpy(float),
 "abs_beta":    np.abs(bt),
 "log_sigma":   np.log(np.clip(sg,1e-12,None)),
 "w_sd":        W.std(1),
 "w_mean":      W.mean(1),
 "w_range":     W.max(1)-W.min(1),
 "slope_48":    (W[:,-1]-W[:,-48])/48.0,
 "slope_96":    (W[:,-1]-W[:,-96])/96.0,
 "slope_336":   (W[:,-1]-W[:,0])/336.0,
 "step_sd":     dW.std(1),
 "step_sd_48":  dW[:,-48:].std(1),
 "two_ruler":   dW.std(1)/np.clip(W.std(1),1e-9,None),
 "vol_ratio":   dW[:,-48:].std(1)/np.clip(dW.std(1),1e-9,None),
 "step_ac1":    np.array([np.corrcoef(dW[i,:-1],dW[i,1:])[0,1] for i in range(0,N)]),
 "frac_above":  (W>0).mean(1),
 "time_above3": (np.abs(W)>=3.0).mean(1),
}
X=np.column_stack([np.nan_to_num(v,nan=0.0,posinf=0.0,neginf=0.0) for v in feat.values()])
# sign-fold: a dislocation at -3 is the mirror of one at +3, so fold every
# feature into the entry's own direction. Without this the pooled fit has to
# learn each sign separately and halves its own power.
s=np.sign(y0); s[s==0]=1.0
SIGNED={"z_entry","w_mean","slope_48","slope_96","slope_336","w_sd","step_ac1"}
for j,k in enumerate(feat):
    if k in {"z_entry","w_mean","slope_48","slope_96","slope_336"}: X[:,j]*=s
CHG=(Y[:,20]-y0)*s                                  # change in the entry's own direction
mn=X[tr].mean(0); sd=np.where(X[tr].std(0)>0,X[tr].std(0),1.0)
Xs=(X-mn)/sd

def r2(cols):
    A=np.column_stack([np.ones(tr.sum()),Xs[tr][:,cols]])
    c=np.linalg.lstsq(A,CHG[tr],rcond=None)[0]
    p=np.column_stack([np.ones(te.sum()),Xs[te][:,cols]])@c
    yo=CHG[te]
    return 1-((yo-p)**2).sum()/((yo-yo.mean())**2).sum()

names=list(feat)
print("\n=== held-out R2 of the 10h change, single feature (trained on fit period) ===")
sc=sorted(((r2([i]),k) for i,k in enumerate(names)),reverse=True)
for v,k in sc: print(f"  {k:<13}{100*v:>8.3f}%")

allr=r2(list(range(len(names))))
print(f"\nall {len(names)} features together, HELD OUT: {100*allr:.3f}%")

# day-clustered band on the full-feature number
dtr=np.unique(day[tr]); rb=np.random.default_rng(7); bs=[]
for _ in range(200):
    pick=rb.choice(dtr,len(dtr),replace=True)
    sel=np.concatenate([np.flatnonzero(day==d) for d in pick])
    A=np.column_stack([np.ones(len(sel)),Xs[sel]])
    c=np.linalg.lstsq(A,CHG[sel],rcond=None)[0]
    p=np.column_stack([np.ones(te.sum()),Xs[te]])@c
    yo=CHG[te]; bs.append(1-((yo-p)**2).sum()/((yo-yo.mean())**2).sum())
bs=np.array(bs)
print(f"   day-clustered 200 resamples: [{100*np.percentile(bs,5):.3f}%, {100*np.percentile(bs,95):.3f}%]")
print(f"\ngate needs 9.75%  ->  CRPS would be 94.6% of climatology")
print(f"what {100*allr:.2f}% buys: CRPS ~ {100*np.sqrt(max(1-allr,0)):.1f}% of climatology")
