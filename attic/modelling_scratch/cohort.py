"""The full-retracement cohort: is the OU parameter right about the wrong episodes?

retracement(t) = (e - z_t)*s/|e|, e = Y[:,0], s = sign(e). 1.0 = back at the mean.
  FULL    max retracement over 20 steps >= 1.0
  PARTIAL not FULL, ended reverted (final retracement > 0)
  NONE    not FULL, ended no better than entry

Model's implied curve is 1-(1-k)^t at k = 0.0850 per 30-min step (the exact
discrete form; 1-exp(-kt) is its continuous approximation and differs by ~4%).
"""
import sys, time, warnings
sys.path.insert(0,"/Users/elvisobondo/Pair_Trading/research")
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from sklearn.ensemble import HistGradientBoostingClassifier as HC
from sklearn.metrics import roc_auc_score
warnings.filterwarnings("ignore")
S="/private/tmp/claude-501/-Users-elvisobondo-Pair-Trading/0189ea06-e901-4d24-83ff-b7b3c5ca8f65/scratchpad/"
exec(open(S+"mixture.py").read().split("def run(nu,mix)")[0])
NU=2.709; K=0.0850

e=Y[:,0]; sg_=np.sign(e); sg_[sg_==0]=1
RET=(e[:,None]-Y)*sg_[:,None]/np.abs(e)[:,None]          # (60000,21) all dislocations
mx=RET[:,1:].max(1); fin=RET[:,20]
FULL=mx>=1.0; PART=(~FULL)&(fin>0); NONE=(~FULL)&(fin<=0)
grp=np.where(FULL,0,np.where(PART,1,2))
print(f"[ALL 60,000]  reverted at all {100*(fin>0).mean():.1f}%   reached half "
      f"{100*(mx>=0.5).mean():.1f}%   FULL {100*FULL.mean():.1f}%")
print(f"[ALL 60,000]  FULL {FULL.sum():,}  PARTIAL {PART.sum():,}  NONE {NONE.sum():,}")
hit=lambda m,thr: np.array([np.argmax(RET[i,1:]>=thr)+1 for i in np.flatnonzero(m)])
print(f"[ALL] median time to half among those reaching it: {np.median(hit(mx>=0.5,0.5))*0.5:.1f}h")
print(f"[ALL] median time to FULL among those reaching it: {np.median(hit(FULL,1.0))*0.5:.1f}h\n")

# ---- model, configuration E', held out ----
gte=grp[te]; eT=e[te]; sT=sg_[te]; RT=RET[te]
MP=np.empty((n,HOR+1)); prevp=np.empty(n); cmod=np.empty(n)
ERR={1:np.empty(n),HOR:np.empty(n)}; SDv={1:np.empty(n),HOR:np.empty(n)}; outs=np.empty(n,bool)
for lo in range(0,n,CH):
    hi=min(lo+CH,n); k=hi-lo; sl=slice(lo,hi); rng=np.random.default_rng(1000+lo)
    mi=(np.repeat(m[sl][:,None],NS,1)*np.exp(rng.normal(0,SD,(k,NS))-RV/2)).astype(np.float32)
    vL,vX,vR=QL*mi,QX*mi,R*mi
    dr=lambda v:(rng.standard_t(NU,(k,NS))*np.sqrt(v*(NU-2)/NU)).astype(np.float32)
    reg=(rng.random((k,NS))>p[0][sl][:,None]).astype(np.int8)
    Ls=np.where(reg==0,L[0][sl][:,None],L[1][sl][:,None]).astype(np.float32)
    Xs=np.where(reg==0,X[0][sl][:,None],X[1][sl][:,None]).astype(np.float32)
    cur=Ls+Xs+dr(vR); MP[sl,0]=cur.mean(1)
    for s_ in range(1,HOR+1):
        sw=rng.random((k,NS)); stay=np.where(reg==0,1-T[0,1],1-T[1,0])
        reg=np.where(sw<stay,reg,1-reg)
        Ls=Ls+dr(vL); kk=np.where(reg==0,KR,KD).astype(np.float32); Xs=Xs*(1-kk)+dr(vX)
        cur=Ls+Xs+dr(vR); MP[sl,s_]=cur.mean(1)
        if s_ in (1,HOR): ERR[s_][sl]=Yte[sl,s_]-cur.mean(1); SDv[s_][sl]=cur.std(1)
    mv=(cur-eT[sl][:,None])*sT[sl][:,None]
    prevp[sl]=(mv<0).mean(1)
    rk=(cur<Yte[sl,HOR][:,None]).mean(1); outs[sl]=(rk<=1.0/NS)|(rk>=1-1.0/NS)
    cmod[sl]=crps(cur.astype(np.float64),Yte[sl,HOR])
MPR=(eT[:,None]-MP)*sT[:,None]/np.abs(eT)[:,None]        # model centre, retracement units
cdisp=(MP[:,HOR]-eT)*sT

def clim(sub,seed=11):
    ch=(Yte[sub,HOR]-eT[sub])
    E=eT[sub][:,None]+np.random.default_rng(seed).choice(ch-ch.mean(),size=(len(sub),200),replace=True)
    return crps(E,Yte[sub,HOR]).mean()
print("="*118); print("PER GROUP, held out (18,064), configuration E'"); print("="*118)
print(f"{'group':<9}{'n':>7}{'share':>8}{'centre disp':>13}{'pred rev p':>13}{'CRPS/clim':>11}"
      f"{'band.5h':>9}{'cov.5h':>8}{'band10h':>9}{'cov10h':>8}{'out':>7}{'|z|':>7}{'r2':>7}{'v_0':>7}")
r2v=M.r2.to_numpy()[te]; absz=np.abs(eT)
for g,nm in ((0,"FULL"),(1,"PARTIAL"),(2,"NONE")):
    sub=np.flatnonzero(gte==g)
    print(f"{nm:<9}{len(sub):>7}{100*len(sub)/n:>7.1f}%"
          f"{cdisp[sub].mean():>8.3f}±{cdisp[sub].std():<4.2f}"
          f"{prevp[sub].mean():>8.3f}±{prevp[sub].std():<4.3f}"
          f"{100*cmod[sub].mean()/clim(sub):>10.1f}%"
          f"{np.std(ERR[1][sub])/SDv[1][sub].mean():>9.2f}"
          f"{100*np.mean(np.abs(ERR[1][sub]/SDv[1][sub])<=1.645):>7.1f}%"
          f"{np.std(ERR[HOR][sub])/SDv[HOR][sub].mean():>9.2f}"
          f"{100*np.mean(np.abs(ERR[HOR][sub]/SDv[HOR][sub])<=1.645):>7.1f}%"
          f"{100*outs[sub].mean():>6.2f}%{np.median(absz[sub]):>7.2f}"
          f"{np.median(r2v[sub]):>7.3f}{np.median(m[sub]):>7.2f}")
print(f"\n  the clincher: predicted reversion probability is "
      f"{' / '.join(f'{prevp[gte==g].mean():.3f}' for g in (0,1,2))} for FULL / PARTIAL / NONE",flush=True)

# ---- retracement curves ----
t=np.arange(21); mcurve=1-(1-K)**t
print("\n"+"="*118); print("MEDIAN RETRACEMENT PATH vs the model's k=0.0850 curve (all 60,000)"); print("="*118)
print(f"{'hours':>7}"+"".join(f"{v:>9.1f}" for v in t[::4]*0.5))
print(f"{'model':>7}"+"".join(f"{mcurve[i]:>9.3f}" for i in range(0,21,4)))
for g,nm in ((0,"FULL"),(1,"PARTIAL"),(2,"NONE")):
    md=np.median(RET[grp==g],axis=0)
    print(f"{nm:>7}"+"".join(f"{md[i]:>9.3f}" for i in range(0,21,4)))
pop=np.median(RET,axis=0)
print(f"{'ALL':>7}"+"".join(f"{pop[i]:>9.3f}" for i in range(0,21,4)))
mm=np.median(MPR,axis=0)
print(f"{'E-centre':>7}"+"".join(f"{mm[i]:>9.3f}" for i in range(0,21,4)))

plt.figure(figsize=(9,5.5))
for g,nm,c in ((0,"FULL (18.9%)","#2b6cb0"),(1,"PARTIAL","#38a169"),(2,"NONE","#c53030")):
    plt.plot(t*0.5,np.median(RET[grp==g],axis=0),color=c,lw=2,label=f"measured median, {nm}")
plt.plot(t*0.5,pop,color="0.35",lw=2,ls="--",label="measured median, ALL 60,000")
plt.plot(t*0.5,mcurve,color="black",lw=2.2,ls=":",label="model  1-(1-0.0850)^t")
plt.plot(t*0.5,mm,color="darkorange",lw=1.8,ls="-.",label="model forecast centre (E')")
plt.axhline(1.0,color="0.7",lw=1); plt.axhline(0,color="0.7",lw=1)
plt.xlabel("hours after entry"); plt.ylabel("retracement  (1.0 = back at the mean)")
plt.title("Does the OU decay describe the reverting subset?",fontsize=11)
plt.legend(fontsize=8); plt.tight_layout(); plt.savefig(S+"cohort.png",dpi=130)
print(f"\nwrote cohort.png",flush=True)

# ---- can anything pick FULL out in advance? ----
print("\n"+"="*118); print("PREDICTING 'FULL' IN ADVANCE  (base rate 18.9%, a harder target than 56%)"); print("="*118)
yF=FULL.astype(int)
f2=np.load(S+"extfeat.npz"); BOTH=np.column_stack([f2["EXT"],f2["WIN"]])
du=np.unique(dte); pos={d:np.flatnonzero(dte==d) for d in du}
rb=np.random.default_rng(5)
BOOT=[np.concatenate([pos[d] for d in rb.choice(du,len(du),replace=True)]) for _ in range(300)]
def auc_ci(pred,yy):
    o=np.empty(len(BOOT))
    for i,ix in enumerate(BOOT):
        try: o[i]=roc_auc_score(yy[ix],pred[ix])
        except Exception: o[i]=np.nan
    return np.nanpercentile(o,2.5),np.nanpercentile(o,97.5)
fd=np.sort(np.unique(day[tr])); vcut=fd[int(0.8*len(fd))]
trm=tr&(day<vcut); vam=tr&(day>=vcut)
P=dict(max_iter=200,early_stopping=False,learning_rate=0.05,max_leaf_nodes=15,
       l2_regularization=1.0,min_samples_leaf=50)
def tree(X,y,seed=0):
    mo=HC(**P,random_state=seed).fit(X[trm],y[trm])
    sv=list(mo.staged_decision_function(X[vam])); st=list(mo.staged_decision_function(X[te]))
    b=int(np.argmax([roc_auc_score(y[vam],q.ravel()) for q in sv]))
    return roc_auc_score(y[te],st[b].ravel()), st[b].ravel()
cells=0; print(f"{'predictor':<34}{'AUC':>9}{'95% day-clustered':>22}{'gate':>7}")
for nm,pv in (("model reversion probability",prevp),("|z| at entry",absz),
              ("v_0 volatility prediction",m)):
    a=roc_auc_score(yF[te],pv); a=max(a,1-a); pv2=pv if roc_auc_score(yF[te],pv)>=0.5 else -pv
    lo,hi=auc_ci(pv2,yF[te]); cells+=1
    print(f"{nm:<34}{a:>9.4f}  [{lo:>7.4f},{hi:>7.4f}]{'PASS' if (a>0.55 and lo>0.5) else 'fail':>7}")
a,pr_=tree(BOTH,yF); lo,hi=auc_ci(pr_,yF[te]); cells+=1
print(f"{'boosted tree, 62 features':<34}{a:>9.4f}  [{lo:>7.4f},{hi:>7.4f}]"
      f"{'PASS' if (a>0.55 and lo>0.5) else 'fail':>7}")
print(f"\n[CELLS] {cells}; expected false positives at a 95% interval: {cells*0.05:.1f}")
nd=[]
for k2 in range(15):
    r=np.random.default_rng(300+k2); dmap={d:v for d,v in zip(fd,r.permutation(fd))}
    yp=yF.copy()
    for d in fd:
        A=np.flatnonzero((day==d)&tr); B=np.flatnonzero(day==dmap[d])
        if len(A) and len(B): yp[A]=yF[r.choice(B,len(A),replace=True)]
    nd.append(tree(BOTH,yp,seed=k2)[0])
nd=np.array(nd)
print(f"[NULL ] day-shuffle: mean {nd.mean():.4f} [{nd.min():.4f},{nd.max():.4f}]   "
      f"REAL {a:.4f}   {'OUTSIDE' if a>nd.max() else 'inside'} the null")
