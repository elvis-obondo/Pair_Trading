"""The 2x2: does v_0's mixture work through its LEVEL or its SHAPE?

  C   point estimate, mean variance 1.06       level 1.06, no shape
  G   uniform Jensen factor, no mixture        level 1.46, no shape
  E'  mixture / exp(var/2), mean 1.06          level 1.06, shape
  E   mixture as-is                            level 1.46, shape

If G reproduces the decile-10 gain and E' does not, the mechanism is a scalar
and the fix is "multiply v_0 by its Jensen factor". If E' carries most of it,
the shape is doing real work.
"""
import sys, time, warnings
sys.path.insert(0,"/Users/elvisobondo/Pair_Trading/research")
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
exec(open("/private/tmp/claude-501/-Users-elvisobondo-Pair-Trading/0189ea06-e901-4d24-83ff-b7b3c5ca8f65/scratchpad/mixture.py").read().split("def run(nu,mix)")[0])
NU=2.709; JF=np.exp(RV/2)

def run(level,shape):
    ERR={1:np.empty(n),HOR:np.empty(n)}; SDv={1:np.empty(n),HOR:np.empty(n)}
    outs=np.empty(n,bool); cm=np.empty(n); keep=[]; mm=[]
    for lo in range(0,n,CH):
        hi=min(lo+CH,n); k=hi-lo; sl=slice(lo,hi); rng=np.random.default_rng(1000+lo)
        mi=np.repeat(m[sl][:,None],NS,1)*level
        if shape: mi=mi*np.exp(rng.normal(0,SD,(k,NS))-RV/2)
        mi=mi.astype(np.float32); mm.append(mi.mean())
        vL,vX,vR=QL*mi,QX*mi,R*mi
        dr=lambda v:(rng.standard_t(NU,(k,NS))*np.sqrt(v*(NU-2)/NU)).astype(np.float32)
        reg=(rng.random((k,NS))>p[0][sl][:,None]).astype(np.int8)
        Ls=np.where(reg==0,L[0][sl][:,None],L[1][sl][:,None]).astype(np.float32)
        Xs=np.where(reg==0,X[0][sl][:,None],X[1][sl][:,None]).astype(np.float32)
        prev=Ls+Xs+dr(vR); ds=[]
        for s_ in range(1,HOR+1):
            sw=rng.random((k,NS)); stay=np.where(reg==0,1-T[0,1],1-T[1,0])
            reg=np.where(sw<stay,reg,1-reg)
            Ls=Ls+dr(vL); kk=np.where(reg==0,KR,KD).astype(np.float32); Xs=Xs*(1-kk)+dr(vX)
            cur=Ls+Xs+dr(vR); ds.append(np.abs(cur-prev)[:,::STRIDE])
            if s_ in (1,HOR): ERR[s_][sl]=Yte[sl,s_]-cur.mean(1); SDv[s_][sl]=cur.std(1)
            prev=cur
        rk=(cur<Yte[sl,HOR][:,None]).mean(1)
        outs[sl]=(rk<=1.0/NS)|(rk>=1-1.0/NS)
        cm[sl]=crps(cur.astype(np.float64),Yte[sl,HOR]); keep.append(np.concatenate(ds).ravel())
    return ERR,SDv,outs,cm,np.concatenate(keep),float(np.mean(mm))

du=np.unique(dte); pos={d:np.flatnonzero(dte==d) for d in du}
rb=np.random.default_rng(5); BOOT=[rb.choice(du,len(du),replace=True) for _ in range(300)]
decR=pd.qcut(rvPost[te],10,labels=False)
s10=np.flatnonzero(decR==9); s19=np.flatnonzero(decR<9)
print(f"Jensen factor exp(var/2) = {JF:.3f}\n")
print("="*112)
print(f"{'cfg':<34}{'mean m':>8}{'outside':>9}{'95% CI':>15}{'D10 cov':>9}{'D10 out':>9}"
      f"{'D1-9 cov':>10}{'D1-9 out':>10}{'band10h':>9}{'CRPS':>8}")
ROW={}
for tag,lev,sh in (("C   level 1.06, no shape",1.0,False),("G   level 1.46, NO SHAPE",JF,False),
                   ("E'  level 1.06, SHAPE",1.0,True),("E   level 1.46, SHAPE",JF,True)):
    ERR,SDv,outs,cm,md,mbar=run(lev,sh)
    cov=lambda s:100*np.mean(np.abs(ERR[HOR][s]/SDv[HOR][s])<=1.645)
    o=100*outs.mean()
    bs=np.empty(len(BOOT))
    for i,pick in enumerate(BOOT):
        idx=np.concatenate([pos[d] for d in pick]); bs[i]=100*outs[idx].mean()
    ROW[tag]=(cov(s10),100*outs[s10].mean(),cov(s19),100*outs[s19].mean(),md)
    print(f"{tag:<34}{mbar:>8.2f}{o:>8.2f}%  [{np.percentile(bs,2.5):>4.2f},{np.percentile(bs,97.5):>4.2f}]"
          f"{cov(s10):>8.1f}%{100*outs[s10].mean():>8.2f}%{cov(s19):>9.1f}%{100*outs[s19].mean():>9.2f}%"
          f"{np.std(ERR[HOR])/SDv[HOR].mean():>9.2f}{100*cm.mean()/CL:>7.1f}%",flush=True)

print("\n"+"="*112); print("2x2 READ  (decile 10 coverage, target ~90%)"); print("="*112)
g=lambda t:ROW[t][0]
print(f"{'':<22}{'no shape':>12}{'SHAPE':>10}{'shape effect':>15}")
print(f"{'level 1.06':<22}{g('C   level 1.06, no shape'):>11.1f}%{g(chr(69)+chr(39)+'  level 1.06, SHAPE'):>9.1f}%"
      f"{g(chr(69)+chr(39)+'  level 1.06, SHAPE')-g('C   level 1.06, no shape'):>+14.1f}pp")
print(f"{'level 1.46':<22}{g('G   level 1.46, NO SHAPE'):>11.1f}%{g('E   level 1.46, SHAPE'):>9.1f}%"
      f"{g('E   level 1.46, SHAPE')-g('G   level 1.46, NO SHAPE'):>+14.1f}pp")
print(f"{'level effect':<22}{g('G   level 1.46, NO SHAPE')-g('C   level 1.06, no shape'):>+10.1f}pp"
      f"{g('E   level 1.46, SHAPE')-g(chr(69)+chr(39)+'  level 1.06, SHAPE'):>+9.1f}pp")
o10=lambda t:ROW[t][1]
print(f"\n{'decile 10 outside-all':<22}{'no shape':>12}{'SHAPE':>10}")
print(f"{'level 1.06':<22}{o10('C   level 1.06, no shape'):>11.2f}%{o10(chr(69)+chr(39)+'  level 1.06, SHAPE'):>9.2f}%")
print(f"{'level 1.46':<22}{o10('G   level 1.46, NO SHAPE'):>11.2f}%{o10('E   level 1.46, SHAPE'):>9.2f}%")
print(f"\nnine-decile cost (coverage, target ~90%; higher = over-covered)")
for t in ROW: print(f"  {t:<34}{ROW[t][2]:>7.1f}%   outside {ROW[t][3]:.2f}%")
