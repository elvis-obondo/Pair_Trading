"""Rebuild the wave feature across ALL 22,366 pairs, not a 1.8% sample.

Then re-score the VOLATILITY target only. Direction is closed and does not need
re-running: it failed on all three feature sets including the combined one, and
a noisy feature cannot explain a learner scoring worse than its own shuffled null.
"""
import sys, os, time, warnings
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import universe_panel, rolling_spread as rs
warnings.filterwarnings("ignore")
import paths
S=paths.DATASETS+"/"
M=pd.read_parquet(S+"disloc_meta.parquet"); J=M.bar_index.to_numpy(int)
panel=universe_panel.drop_forming_bars(universe_panel.load_panel())
V=panel.to_numpy(float); cols=list(panel.columns); ixc={c:i for i,c in enumerate(cols)}
ok=np.isfinite(V); first=np.array([ok[:,i].argmax() for i in range(V.shape[1])])
pr=universe_panel.tradeable_pairs(cols)
cnt3=np.zeros(len(V)); cntf=np.zeros(len(V)); used=0
t0=time.time()
for q,(a,b) in enumerate(pr):
    i1,i2=ixc[a],ixc[b]; f=max(first[i1],first[i2])
    if len(V)-f<500: continue
    r=rs.rolling_spread_stats(V[f:,i1],V[f:,i2],0.5)
    g=np.isfinite(r.z)
    if not g.any(): continue
    cntf[f:][g]+=1; cnt3[f:][g&(np.abs(r.z)>=3.0)]+=1; used+=1
    if q%4000==0: print(f"  {q}/{len(pr)} pairs, {time.time()-t0:.0f}s",flush=True)
wave=np.where(cntf>0,cnt3/np.maximum(cntf,1),np.nan)
print(f"[WAVE] {used:,} of {len(pr):,} pairs ({time.time()-t0:.0f}s); "
      f"median live pairs per bar {np.median(cntf[cntf>0]):,.0f}")
print(f"[WAVE] dislocated share at entry bars: median {np.nanmedian(wave[J]):.4f} "
      f"p5 {np.nanpercentile(wave[J],5):.4f} p95 {np.nanpercentile(wave[J],95):.4f}")
np.savez_compressed(S+"wave_full.npz",wave=wave,cntf=cntf)

f=np.load(S+"extfeat.npz"); EXT=f["EXT"].copy(); WIN=f["WIN"]; names=list(f["names"])
iw=names.index("wave"); iw4=names.index("wave_mean4"); inl=names.index("n_live_pairs")
old=EXT[:,iw].copy()
EXT[:,iw]=np.nan_to_num(wave[J],nan=0)
EXT[:,iw4]=np.nan_to_num(np.array([np.nanmean(wave[j-3:j+1]) for j in J]),nan=0)
EXT[:,inl]=cntf[J]
print(f"[WAVE] corr(sampled wave, full wave) = {np.corrcoef(old,EXT[:,iw])[0,1]:.4f}\n")

z=np.load(S+"disloc.npz"); Y=z["outcomes"].astype(np.float64)
day=M.day.to_numpy(); CUT=np.datetime64("2026-07-18"); fitm=day<CUT; te=~fitm
fd=np.sort(np.unique(day[fitm])); vcut=fd[int(0.8*len(fd))]
trm=fitm&(day<vcut); vam=fitm&(day>=vcut)
dF=np.diff(Y,axis=1); VOLT=2*np.log(np.maximum(np.abs(dF).mean(1),1e-12))
from sklearn.ensemble import HistGradientBoostingRegressor as HR
P=dict(max_iter=200,early_stopping=False,learning_rate=0.05,max_leaf_nodes=15,
       l2_regularization=1.0,min_samples_leaf=50,random_state=0)
def fit(X,y):
    m=HR(**P).fit(X[trm],y[trm])
    sv=list(m.staged_predict(X[vam])); st=list(m.staged_predict(X[te]))
    b=int(np.argmin([((y[vam]-p)**2).sum() for p in sv])); p=st[b]; yy=y[te]
    return 1-((yy-p)**2).sum()/((yy-yy.mean())**2).sum(), p
dte=day[te]; du=np.unique(dte); pos={d:np.flatnonzero(dte==d) for d in du}
rb=np.random.default_rng(5)
BOOT=[np.concatenate([pos[d] for d in rb.choice(du,len(du),replace=True)]) for _ in range(300)]
BOTH=np.column_stack([EXT,WIN])
R={}
for nm,X in (("EXTERNAL",EXT),("WINDOW (control)",WIN),("EXT + WINDOW",BOTH)):
    R[nm]=fit(X,VOLT); print(f"  {nm:<18} held-out R2 {100*R[nm][0]:>7.2f}%",flush=True)
yte=VOLT[te]; pb=R["EXT + WINDOW"][1]; pw=R["WINDOW (control)"][1]
d=np.empty(len(BOOT))
for i,ix in enumerate(BOOT):
    r=lambda p:1-((yte[ix]-p[ix])**2).sum()/((yte[ix]-yte[ix].mean())**2).sum()
    d[i]=r(pb)-r(pw)
dif=R["EXT + WINDOW"][0]-R["WINDOW (control)"][0]
lo,hi=np.percentile(d,2.5),np.percentile(d,97.5)
print(f"\n  EXT+WINDOW minus WINDOW = {100*dif:+.2f}pp  95% day-clustered on the DIFFERENCE "
      f"[{100*lo:+.2f},{100*hi:+.2f}]pp")
print(f"  gate >3pp and CI>0:  {'PASS' if (dif>0.03 and lo>0) else 'FAIL'}")
print(f"  (before the rebuild: +2.04pp [+0.49,+3.95], EXTERNAL alone 26.05%)")
