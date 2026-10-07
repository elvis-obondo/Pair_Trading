"""Score the external features through the nonlinear harness. Same everything."""
import sys, time, warnings
sys.path.insert(0,"/Users/elvisobondo/Pair_Trading/research")
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor as HR, HistGradientBoostingClassifier as HC
from sklearn.metrics import roc_auc_score
warnings.filterwarnings("ignore")
S="/private/tmp/claude-501/-Users-elvisobondo-Pair-Trading/0189ea06-e901-4d24-83ff-b7b3c5ca8f65/scratchpad/"
z=np.load(S+"disloc.npz"); Y=z["outcomes"].astype(np.float64); W0=z["windows"].astype(np.float64)
M=pd.read_parquet(S+"disloc_meta.parquet"); day=M.day.to_numpy()
f=np.load(S+"extfeat.npz"); EXT=f["EXT"]; WIN=f["WIN"]; BOTH=np.column_stack([EXT,WIN])
CUT=np.datetime64("2026-07-18"); fitm=day<CUT; te=~fitm
fd=np.sort(np.unique(day[fitm])); vcut=fd[int(0.8*len(fd))]
trm=fitm&(day<vcut); vam=fitm&(day>=vcut)
sgn=np.sign(Y[:,0]); sgn[sgn==0]=1
dF=np.diff(Y,axis=1); VOLT=2*np.log(np.maximum(np.abs(dF).mean(1),1e-12))
print(f"[SPLIT] train {trm.sum():,}  val {vam.sum():,}  HELD OUT {te.sum():,}; held-out scored once")
print(f"[SETS]  EXTERNAL {EXT.shape[1]}  WINDOW {WIN.shape[1]}  BOTH {BOTH.shape[1]}\n")
P=dict(max_iter=200,early_stopping=False,learning_rate=0.05,max_leaf_nodes=15,
       l2_regularization=1.0,min_samples_leaf=50)
def fit(X,y,clf,seed=0):
    if clf:
        m=HC(**P,random_state=seed).fit(X[trm],y[trm])
        sv=list(m.staged_decision_function(X[vam])); st=list(m.staged_decision_function(X[te]))
        b=int(np.argmax([roc_auc_score(y[vam],p.ravel()) for p in sv]))
        return roc_auc_score(y[te],st[b].ravel()), st[b].ravel()
    m=HR(**P,random_state=seed).fit(X[trm],y[trm])
    sv=list(m.staged_predict(X[vam])); st=list(m.staged_predict(X[te]))
    b=int(np.argmin([((y[vam]-p)**2).sum() for p in sv]))
    p=st[b]; yy=y[te]
    return 1-((yy-p)**2).sum()/((yy-yy.mean())**2).sum(), p
dte=day[te]; du=np.unique(dte); pos={d:np.flatnonzero(dte==d) for d in du}
rb=np.random.default_rng(5); BOOT=[np.concatenate([pos[d] for d in rb.choice(du,len(du),replace=True)]) for _ in range(300)]
def ci(pred,yte,clf,ref=None):
    o=np.empty(len(BOOT))
    for i,ix in enumerate(BOOT):
        try:
            if clf: o[i]=roc_auc_score(yte[ix],pred[ix])
            else:
                r=lambda p:1-((yte[ix]-p[ix])**2).sum()/((yte[ix]-yte[ix].mean())**2).sum()
                o[i]=r(pred)-(r(ref) if ref is not None else 0.0)
        except Exception: o[i]=np.nan
    return np.nanpercentile(o,2.5),np.nanpercentile(o,97.5)
SETS=[("EXTERNAL",EXT),("WINDOW (control)",WIN),("EXT + WINDOW",BOTH)]
HOR=[(1,"0.5h"),(2,"1h"),(4,"2h"),(10,"5h"),(20,"10h")]
cells=0; hits=[]
t0=time.time()
for tn,clf in (("REGRESSION  signed change",False),("CLASSIFICATION  reverted",True)):
    print("="*100); print(tn); print("="*100)
    print(f"{'features':<18}{'h':>6}{'score':>10}{'95% day-clustered':>22}{'gate':>7}")
    for sn,X in SETS:
        for h,hl in HOR:
            yv=(Y[:,h]-Y[:,0])*sgn; y=(yv<0).astype(int) if clf else yv
            v,p=fit(X,y,clf); lo,hi=ci(p,y[te],clf); cells+=1
            ok=(v>0.55 and lo>0.50) if clf else (v>0.01 and lo>0.0)
            if ok: hits.append(f"{tn.split()[0]} {sn} {hl} = {v:.4f}")
            print(f"{sn:<18}{hl:>6}{v:>10.4f}  [{lo:>7.4f},{hi:>7.4f}]{'PASS' if ok else 'fail':>7}")
    print(flush=True)
print("="*100); print("VOLATILITY  log post-entry realised variance"); print("="*100)
pr={}
for sn,X in SETS:
    v,p=fit(X,VOLT,False); pr[sn]=(v,p); cells+=1
    print(f"  {sn:<18} held-out R2 {100*v:>7.2f}%")
dv,(vb,pb)=None,pr["EXT + WINDOW"]; vw,pw=pr["WINDOW (control)"]
lo,hi=ci(pb,VOLT[te],False,ref=pw)
ok=(vb-vw>0.03 and lo>0.0)
print(f"\n  EXT+WINDOW minus WINDOW = {100*(vb-vw):+.2f}pp   95% day-clustered on the DIFFERENCE "
      f"[{100*lo:+.2f},{100*hi:+.2f}]pp   gate >3pp and CI>0:  {'PASS' if ok else 'FAIL'}")
if ok: hits.append(f"VOLATILITY incremental {100*(vb-vw):+.2f}pp")
print(f"\n[CELLS] {cells} scored; at a 95% interval expect {cells*0.05:.1f} false positives by chance")
print(f"[HITS ] {len(hits)}: {hits if hits else 'none'}\n",flush=True)
print("="*100); print("PERMUTATION NULL -- EXTERNAL, 10h; day-shuffle is the one that matters"); print("="*100,flush=True)
for tn,clf,yb in (("regression",False,(Y[:,20]-Y[:,0])*sgn),("reversion",True,None),("volatility",False,VOLT)):
    y0=((Y[:,20]-Y[:,0])*sgn<0).astype(int) if clf else yb
    real,_=fit(EXT,y0,clf); nr=[]; nd=[]
    for k in range(15):
        r=np.random.default_rng(200+k); idx=np.flatnonzero(fitm)
        yp=y0.copy(); yp[idx]=y0[r.permutation(idx)]; nr.append(fit(EXT,yp,clf,seed=k)[0])
        dmap={d:v for d,v in zip(fd,r.permutation(fd))}; yp2=y0.copy()
        for d in fd:
            a=np.flatnonzero((day==d)&fitm); b=np.flatnonzero(day==dmap[d])
            if len(a) and len(b): yp2[a]=y0[r.choice(b,len(a),replace=True)]
        nd.append(fit(EXT,yp2,clf,seed=k)[0])
    for nm,arr in (("DAY-shuffle",np.array(nd)),("row-shuffle",np.array(nr))):
        print(f"  {tn:<11}{nm}: null mean {arr.mean():>8.4f} [{arr.min():>8.4f},{arr.max():>8.4f}]"
              f"   REAL {real:>8.4f}   {'OUTSIDE' if real>arr.max() else 'inside'}",flush=True)
print(f"\n[{time.time()-t0:.0f}s]")
