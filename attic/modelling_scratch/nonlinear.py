"""The last loophole: can a NONLINEAR reading of the entry window find direction?

The 30-cell bound covered linear readings. Every SDE parameterisation is a far
MORE constrained function class than a boosted tree, so if gradient boosting
finds nothing here, no parameter we could add will either.

DISCIPLINE, auditable:
  split 2026-07-18, identical to every other test this phase
  the learner is fitted on the first 80% of FIT days
  the number of boosting iterations is chosen on the last 20% of FIT days
  THE HELD-OUT SET IS TOUCHED ONCE, at scoring time, and never for tuning
  sign-folded is primary: the window and the target are multiplied by
  sign(z_entry) and every engineered feature is derived FROM the folded window,
  so the learner sees one direction instead of two

PERMUTATION NULL: a flexible learner's held-out R2 is systematically negative
and the real number cannot be read without knowing by how much. The identical
pipeline is rerun on shuffled targets -- 15 row-wise and 15 whole-day shuffles,
the latter respecting the day clustering -- to get the null distribution.
"""
import sys, time, warnings
sys.path.insert(0,"/Users/elvisobondo/Pair_Trading/research")
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
warnings.filterwarnings("ignore")

D="/private/tmp/claude-501/-Users-elvisobondo-Pair-Trading/0189ea06-e901-4d24-83ff-b7b3c5ca8f65/scratchpad/disloc"
z=np.load(D+".npz"); W0=z["windows"].astype(np.float32); Y=z["outcomes"].astype(np.float64)
M=pd.read_parquet(D+"_meta.parquet"); day=M.day.to_numpy()
CUT=np.datetime64("2026-07-18"); fitm=day<CUT; te=~fitm
fdays=np.sort(np.unique(day[fitm])); vcut=fdays[int(0.8*len(fdays))]
trm=fitm&(day<vcut); vam=fitm&(day>=vcut)
print(f"[SPLIT] train {trm.sum():,} (<{vcut})   val {vam.sum():,}   HELD OUT {te.sum():,} (>={CUT})")
print(f"[SPLIT] held-out used ONCE, for scoring only; iterations chosen on val\n")

def build(fold):
    s=np.sign(Y[:,0]).astype(np.float32); s[s==0]=1
    if not fold: s=np.ones(len(Y),np.float32)
    Wf=W0*s[:,None]
    dWf=np.diff(Wf,axis=1)
    f={"z":Wf[:,-1],"absz":np.abs(Wf[:,-1]),"r2":M.r2.to_numpy(np.float32),
       "absb":np.abs(M.beta.to_numpy(np.float32)),
       "lsig":np.log(np.clip(M.sigma.to_numpy(np.float32),1e-12,None)),
       "wsd":Wf.std(1),"wmean":Wf.mean(1),"wrange":Wf.max(1)-Wf.min(1),
       "sl48":(Wf[:,-1]-Wf[:,-48])/48,"sl96":(Wf[:,-1]-Wf[:,-96])/96,
       "sl336":(Wf[:,-1]-Wf[:,0])/336,"ssd":dWf.std(1),"ssd48":dWf[:,-48:].std(1),
       "two":dWf.std(1)/np.clip(Wf.std(1),1e-9,None),
       "vr":dWf[:,-48:].std(1)/np.clip(dWf.std(1),1e-9,None),
       "ac1":np.array([np.corrcoef(dWf[i,:-1],dWf[i,1:])[0,1] for i in range(len(Wf))],np.float32),
       "fa":(Wf>0).mean(1),"ta3":(np.abs(Wf)>=3).mean(1)}
    E=np.nan_to_num(np.column_stack(list(f.values())).astype(np.float32),nan=0,posinf=0,neginf=0)
    return Wf, E, s
print("[BUILD] features...",flush=True)
WF,EF,SF=build(True); WU,EU,SU=build(False)

def score(X,y,clf,seed=0):
    """fit on train, pick iterations on val, predict held out ONCE"""
    P=dict(max_iter=200,early_stopping=False,learning_rate=0.05,max_leaf_nodes=15,
           l2_regularization=1.0,min_samples_leaf=50,random_state=seed)
    if clf:
        m=HistGradientBoostingClassifier(**P).fit(X[trm],y[trm])
        sv=list(m.staged_decision_function(X[vam])); st=list(m.staged_decision_function(X[te]))
        best=int(np.argmax([roc_auc_score(y[vam],p.ravel()) for p in sv]))
        return roc_auc_score(y[te],st[best].ravel()), st[best].ravel(), best
    m=HistGradientBoostingRegressor(**P).fit(X[trm],y[trm])
    sv=list(m.staged_predict(X[vam])); st=list(m.staged_predict(X[te]))
    best=int(np.argmin([((y[vam]-p)**2).sum() for p in sv]))
    p=st[best]; yy=y[te]
    return 1-((yy-p)**2).sum()/((yy-yy.mean())**2).sum(), p, best

dte=day[te]; du=np.unique(dte); pos={d:np.flatnonzero(dte==d) for d in du}
rb=np.random.default_rng(5); BOOT=[rb.choice(du,len(du),replace=True) for _ in range(300)]
def ci(pred,y,clf):
    o=np.empty(len(BOOT))
    for i,pk in enumerate(BOOT):
        idx=np.concatenate([pos[d] for d in pk])
        try: o[i]=roc_auc_score(y[idx],pred[idx]) if clf else 1-((y[idx]-pred[idx])**2).sum()/((y[idx]-y[idx].mean())**2).sum()
        except Exception: o[i]=np.nan
    return np.nanpercentile(o,2.5),np.nanpercentile(o,97.5)

HOR=[(1,"0.5h"),(2,"1h"),(4,"2h"),(10,"5h"),(20,"10h")]
t0=time.time()
for fold,(Wx,Ex,Sx) in (("SIGN-FOLDED (primary)",(WF,EF,SF)),("unfolded",(WU,EU,SU))):
    print("="*104); print(fold); print("="*104)
    print(f"{'features':<14}{'target':<10}{'h':>6}{'score':>10}{'95% day-clustered':>22}{'iters':>7}{'CRPS equiv':>12}")
    for fn,X in (("336 raw bars",Wx),("18 engineered",Ex)):
        for tn,clf in (("regression",False),("reversion",True)):
            for h,hl in HOR:
                yv=(Y[:,h]-Y[:,0])*Sx
                y=(yv<0).astype(int) if clf else yv
                v,pred,bi=score(X,y,clf); lo,hi=ci(pred,y,clf)
                ce="" if clf else f"{100*np.sqrt(max(1-v,0)):>11.1f}%"
                print(f"{fn:<14}{tn:<10}{hl:>6}{v:>10.4f}  [{lo:>7.4f},{hi:>7.4f}]{bi:>7}{ce}",flush=True)
    print()

print("="*104); print("PERMUTATION NULL at 10h, sign-folded -- identical pipeline, shuffled targets")
print("="*104,flush=True)
for fn,X in (("336 raw bars",WF),("18 engineered",EF)):
    for tn,clf in (("regression",False),("reversion",True)):
        yv=(Y[:,20]-Y[:,0])*SF; y0=(yv<0).astype(int) if clf else yv
        real,_,_=score(X,y0,clf)
        nulls={"row":[],"day":[]}
        for k in range(15):
            r=np.random.default_rng(100+k)
            yp=y0.copy(); idx=np.flatnonzero(fitm); yp[idx]=y0[r.permutation(idx)]
            nulls["row"].append(score(X,yp,clf,seed=k)[0])
            dmap={d:v for d,v in zip(fdays,r.permutation(fdays))}
            src=np.array([dmap.get(d,d) for d in day])
            yp2=y0.copy()
            for d in fdays:
                a=np.flatnonzero((day==d)&fitm); b=np.flatnonzero(day==dmap[d])
                if len(a) and len(b): yp2[a]=y0[r.choice(b,len(a),replace=True)]
            nulls["day"].append(score(X,yp2,clf,seed=k)[0])
        for kind in ("row","day"):
            a=np.array(nulls[kind])
            print(f"  {fn:<14}{tn:<11}{kind}-shuffle null: mean {a.mean():>8.4f}  "
                  f"[{a.min():>8.4f},{a.max():>8.4f}]   REAL {real:>8.4f}   "
                  f"{'OUTSIDE' if real>a.max() else 'inside'} the null",flush=True)
print(f"\n[{time.time()-t0:.0f}s]  gates: regression R2 > +1% with CI excluding 0 and outside null;"
      f"  classification AUC > 0.55 with CI excluding 0.50 and outside null")
