"""Rerun of the main table with the CI bug fixed, plus the leak check.

BUG in nonlinear.py: ci() indexed the FULL-LENGTH target array with held-out-
relative indices, so every interval compared held-out predictions against
unrelated dislocations' labels. Fixed here by slicing y to the held-out set
before bootstrapping. Point estimates and the permutation null were unaffected.

LEAK CHECK: the unfolded reversion label is "the spread fell", which sign(z_entry)
predicts on its own -- a 3-sigma dislocation above the mean tends to come down.
A sign-only baseline is scored alongside so the learner's unfolded AUC can be
read against it instead of against 0.50.
"""
import sys, time, warnings
sys.path.insert(0,"/Users/elvisobondo/Pair_Trading/research")
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
warnings.filterwarnings("ignore")
exec(open("/private/tmp/claude-501/-Users-elvisobondo-Pair-Trading/0189ea06-e901-4d24-83ff-b7b3c5ca8f65/scratchpad/nonlinear.py").read().split("def score(")[0])

def score(X,y,clf,seed=0):
    P=dict(max_iter=200,early_stopping=False,learning_rate=0.05,max_leaf_nodes=15,
           l2_regularization=1.0,min_samples_leaf=50,random_state=seed)
    if clf:
        m=HistGradientBoostingClassifier(**P).fit(X[trm],y[trm])
        sv=list(m.staged_decision_function(X[vam])); st=list(m.staged_decision_function(X[te]))
        b=int(np.argmax([roc_auc_score(y[vam],p.ravel()) for p in sv]))
        return roc_auc_score(y[te],st[b].ravel()), st[b].ravel(), b
    m=HistGradientBoostingRegressor(**P).fit(X[trm],y[trm])
    sv=list(m.staged_predict(X[vam])); st=list(m.staged_predict(X[te]))
    b=int(np.argmin([((y[vam]-p)**2).sum() for p in sv]))
    p=st[b]; yy=y[te]
    return 1-((yy-p)**2).sum()/((yy-yy.mean())**2).sum(), p, b

dte=day[te]; du=np.unique(dte); pos={d:np.flatnonzero(dte==d) for d in du}
rb=np.random.default_rng(5); BOOT=[rb.choice(du,len(du),replace=True) for _ in range(300)]
def ci(pred,yte,clf):
    """yte is ALREADY sliced to the held-out set -- that was the bug"""
    o=np.empty(len(BOOT))
    for i,pk in enumerate(BOOT):
        idx=np.concatenate([pos[d] for d in pk])
        try:
            o[i]=roc_auc_score(yte[idx],pred[idx]) if clf else \
                 1-((yte[idx]-pred[idx])**2).sum()/((yte[idx]-yte[idx].mean())**2).sum()
        except Exception: o[i]=np.nan
    return np.nanpercentile(o,2.5),np.nanpercentile(o,97.5)

HOR=[(1,"0.5h"),(2,"1h"),(4,"2h"),(10,"5h"),(20,"10h")]
t0=time.time()
for fold,(Wx,Ex,Sx) in (("SIGN-FOLDED (primary)",(WF,EF,SF)),("unfolded",(WU,EU,SU))):
    print("="*110); print(fold); print("="*110)
    print(f"{'features':<14}{'target':<11}{'h':>6}{'score':>10}{'95% day-clustered':>22}"
          f"{'iters':>7}{'sign-only':>11}{'gate':>7}")
    for fn,X in (("336 raw bars",Wx),("18 engineered",Ex)):
        for tn,clf in (("regression",False),("reversion",True)):
            for h,hl in HOR:
                yv=(Y[:,h]-Y[:,0])*Sx
                y=(yv<0).astype(int) if clf else yv
                v,pred,bi=score(X,y,clf); lo,hi=ci(pred,y[te],clf)
                if clf:
                    sa=roc_auc_score(y[te],-np.sign(Y[te,0]))
                    ok="PASS" if (v>0.55 and lo>0.50) else "fail"
                    sb=f"{sa:>11.4f}"
                else:
                    ok="PASS" if (v>0.01 and lo>0.0) else "fail"; sb=f"{'':>11}"
                print(f"{fn:<14}{tn:<11}{hl:>6}{v:>10.4f}  [{lo:>7.4f},{hi:>7.4f}]{bi:>7}{sb}{ok:>7}",flush=True)
    print()
print(f"[{time.time()-t0:.0f}s]")
