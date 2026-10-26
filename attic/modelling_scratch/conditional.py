"""Is there a SUBSET where this model works?

Configuration E' (mixture rescaled to preserve level, nu = 2.709), 2,000 draws,
held out, same split.

THE TRAP, avoided: selecting cases where the model predicted reversion AND the
spread reverted, then scoring there, conditions on the outcome and the model
looks good by construction. Cuts 1 and 2 condition only on what the model knew
AT ENTRY. Cut 3 conditions on the outcome and is labelled a DIAGNOSTIC.

Climatology is recomputed WITHIN each bucket from that bucket's own outcomes.
Pooled climatology would rig every comparison.
"""
import sys, time, warnings
sys.path.insert(0,"/Users/elvisobondo/Pair_Trading/research")
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
exec(open("/private/tmp/claude-501/-Users-elvisobondo-Pair-Trading/0189ea06-e901-4d24-83ff-b7b3c5ca8f65/scratchpad/mixture.py").read().split("def run(nu,mix)")[0])
NU=2.709
s=np.sign(Yte[:,0]); s[s==0]=1.0
entry=Yte[:,0]; fin=Yte[:,HOR]
act=(fin-entry)*s                       # actual signed move, entry's own direction

ERR={1:np.empty(n),HOR:np.empty(n)}; SDv={1:np.empty(n),HOR:np.empty(n)}
outs=np.empty(n,bool); cmod=np.empty(n); prev_p=np.empty(n); cdisp=np.empty(n)
t0=time.time()
for lo in range(0,n,CH):
    hi=min(lo+CH,n); k=hi-lo; sl=slice(lo,hi); rng=np.random.default_rng(1000+lo)
    mi=(np.repeat(m[sl][:,None],NS,1)*np.exp(rng.normal(0,SD,(k,NS))-RV/2)).astype(np.float32)
    vL,vX,vR=QL*mi,QX*mi,R*mi
    dr=lambda v:(rng.standard_t(NU,(k,NS))*np.sqrt(v*(NU-2)/NU)).astype(np.float32)
    reg=(rng.random((k,NS))>p[0][sl][:,None]).astype(np.int8)
    Ls=np.where(reg==0,L[0][sl][:,None],L[1][sl][:,None]).astype(np.float32)
    Xs=np.where(reg==0,X[0][sl][:,None],X[1][sl][:,None]).astype(np.float32)
    cur=Ls+Xs+dr(vR)
    for s_ in range(1,HOR+1):
        sw=rng.random((k,NS)); stay=np.where(reg==0,1-T[0,1],1-T[1,0])
        reg=np.where(sw<stay,reg,1-reg)
        Ls=Ls+dr(vL); kk=np.where(reg==0,KR,KD).astype(np.float32); Xs=Xs*(1-kk)+dr(vX)
        cur=Ls+Xs+dr(vR)
        if s_ in (1,HOR): ERR[s_][sl]=Yte[sl,s_]-cur.mean(1); SDv[s_][sl]=cur.std(1)
    mv=(cur-entry[sl][:,None])*s[sl][:,None]
    prev_p[sl]=(mv<0).mean(1)                    # predicted reversion probability
    cdisp[sl]=mv.mean(1)                         # forecast centre displacement
    rk=(cur<fin[sl][:,None]).mean(1)
    outs[sl]=(rk<=1.0/NS)|(rk>=1-1.0/NS)
    cmod[sl]=crps(cur.astype(np.float64),fin[sl])
print(f"[E'] {time.time()-t0:.0f}s.  predicted reversion prob: mean {prev_p.mean():.3f} "
      f"sd {prev_p.std():.3f} range [{prev_p.min():.2f},{prev_p.max():.2f}]")
print(f"     forecast centre displacement: mean {cdisp.mean():+.3f} sd {cdisp.std():.3f}")
print(f"     actual signed move: mean {act.mean():+.3f}  reversion rate {100*(act<0).mean():.1f}%\n")

du=np.unique(dte); pos={d:np.flatnonzero(dte==d) for d in du}
rb=np.random.default_rng(5); BOOT=[rb.choice(du,len(du),replace=True) for _ in range(300)]
def ci(ind,sub):
    o=np.empty(len(BOOT))
    for i,pick in enumerate(BOOT):
        idx=np.concatenate([pos[d] for d in pick]); idx=idx[np.isin(idx,sub)]
        o[i]=100*ind[idx].mean() if len(idx) else np.nan
    return np.nanpercentile(o,2.5),np.nanpercentile(o,97.5)

def clim_within(sub,seed=11):
    """climatology built from THIS bucket's own 10h changes -- never pooled"""
    ch=(fin-entry)[sub]
    E=entry[sub][:,None]+np.random.default_rng(seed).choice(ch-ch.mean(),size=(len(sub),200),replace=True)
    return crps(E,fin[sub]).mean()

def table(dec,title,note,extra_actual=True):
    print("="*126); print(title); print(f"  {note}"); print("="*126)
    print(f"{'bkt':>4}{'n':>7}{'pred rev':>10}{'ACTUAL rev':>12}{'95% CI':>16}"
          f"{'CRPS/clim':>11}{'band .5h':>10}{'cov .5h':>9}{'band 10h':>10}{'cov 10h':>9}"
          f"{'out':>7}{'mean act':>10}{'med act':>9}")
    for b in sorted(pd.unique(dec[~pd.isna(dec)])):
        sub=np.flatnonzero(dec==b)
        lo_,hi_=ci((act<0).astype(float),sub)
        cl=clim_within(sub); cmv=cmod[sub].mean()
        print(f"{int(b)+1:>4}{len(sub):>7}{prev_p[sub].mean():>10.3f}"
              f"{100*(act[sub]<0).mean():>11.1f}%  [{lo_:>5.1f},{hi_:>5.1f}]"
              f"{100*cmv/cl:>10.1f}%"
              f"{np.std(ERR[1][sub])/SDv[1][sub].mean():>10.2f}"
              f"{100*np.mean(np.abs(ERR[1][sub]/SDv[1][sub])<=1.645):>8.1f}%"
              f"{np.std(ERR[HOR][sub])/SDv[HOR][sub].mean():>10.2f}"
              f"{100*np.mean(np.abs(ERR[HOR][sub]/SDv[HOR][sub])<=1.645):>8.1f}%"
              f"{100*outs[sub].mean():>6.2f}%{act[sub].mean():>10.3f}{np.median(act[sub]):>9.3f}")
    print(flush=True)

table(pd.qcut(prev_p,10,labels=False,duplicates="drop"),
      "CUT 1 -- by the model's PREDICTED REVERSION PROBABILITY (known at entry)",
      "the key column is CRPS/clim: if the confident deciles beat climatology by more, there is conditional skill")
table(pd.qcut(cdisp,10,labels=False,duplicates="drop"),
      "CUT 2 -- by the model's PREDICTED MOVE (forecast centre displacement, known at entry)",
      "bucket 1 = strongest predicted reversion, bucket 10 = strongest predicted divergence; read 'mean act' for monotonicity")
table(pd.Series(np.where(act<0,0,1)),
      "CUT 3 -- by whether the spread ACTUALLY REVERTED",
      "DIAGNOSTIC ONLY -- uses future information, cannot support any claim of predictive skill. bucket 1 = reverted, bucket 2 = did not")

c=np.corrcoef(cdisp,act)[0,1]
print(f"[CUT 2] corr(predicted move, actual move) = {c:+.4f}   R2 {100*c*c:.3f}%")
print(f"[CUT 1] corr(predicted reversion prob, reverted) = "
      f"{np.corrcoef(prev_p,(act<0).astype(float))[0,1]:+.4f}")
