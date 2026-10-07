"""Phase 2, items 3/5/6: what can the model do when the fitter is PERFECT?

Every fit in exp.log came from an optimiser that collapses to k_revert=1, r=0 --
a model that copies the last observation. Its centre is stays-put by
construction, so its R2 measures the optimiser, not the model class. This
removes the optimiser entirely: generate from a KNOWN truth, screen it with the
same 3-sigma rule, and score the filter handed the TRUE parameters.

The oracle is an upper bound on every fitter. If the oracle cannot reach 95% of
climatology, no amount of fitter work can, and the model class is the problem.
If it can, the fitter is the problem and the real-data result so far says
nothing about the model.

Selection is reproduced, not assumed (item 6): the synthetic series goes through
the same 96-bar rolling geometry and the same fresh |z|>=3 crossing, so
whatever the entry rule does to the sample happens here too.

Filtering runs in RAW units with the true raw parameters, and only the forecast
and the outcome are divided by sigma_at_entry for scoring. Normalising first
would make the truth per-row (qL/sigma^2) and the oracle would no longer be
exact.
"""
import sys, time
sys.path.insert(0,"/Users/elvisobondo/Pair_Trading/research")
import numpy as np, pandas as pd

FIT_BARS, HOR, EW, NS = 336, 20, 96, 200

def generate(kr,kd,qL,qX,r,qrd,qdr,nser=400,T=16000,seed=0):
    """Latent drifting mean + regime-switching OU deviation, observed with noise."""
    rng=np.random.default_rng(seed)
    L=np.zeros(nser); X=rng.normal(0,np.sqrt(qX/max(1-(1-kr)**2,1e-6)),nser)
    reg=(rng.random(nser)<qrd/(qrd+qdr)).astype(int)
    out=np.empty((nser,T),np.float32)
    for t in range(T):
        sw=rng.random(nser)
        stay=np.where(reg==0,1-qrd,1-qdr); reg=np.where(sw<stay,reg,1-reg)
        L=L+rng.normal(0,np.sqrt(qL),nser)
        k=np.where(reg==0,kr,kd)
        X=X*(1-k)+rng.normal(0,np.sqrt(qX),nser)
        out[:,t]=L+X+rng.normal(0,np.sqrt(r),nser)
    return out

def screen(S,want=4000):
    """Same entry rule as the real generator: 96-bar rolling mu/sigma, fresh |z|>=3."""
    Wl,Yl,sgl=[],[],[]
    for i in range(len(S)):
        s=pd.Series(S[i].astype(float))
        mu=s.rolling(EW).mean().to_numpy(); sd=s.rolling(EW).std().to_numpy()
        v=s.to_numpy()
        with np.errstate(invalid="ignore",divide="ignore"):
            z=np.where(sd>0,(v-mu)/sd,np.nan)
        fin=np.isfinite(z)
        hit=np.zeros(len(z),bool)
        hit[1:]=fin[1:]&fin[:-1]&(np.abs(z[1:])>=3.0)&(np.abs(z[:-1])<3.0)
        c=np.flatnonzero(hit); c=c[(c>=FIT_BARS-1)&(c+HOR<=len(z)-1)]
        for j in c:
            Wl.append(v[j-FIT_BARS+1:j+1]); Yl.append(v[j:j+HOR+1]); sgl.append(sd[j])
        if len(Wl)>=want: break
    return np.array(Wl),np.array(Yl),np.array(sgl)

def run(Y,ks,qL,qX,r,T,state=False):
    n,Tn=Y.shape; R=2
    L=[np.zeros(n) for _ in range(R)]; X=[np.zeros(n) for _ in range(R)]
    P0=np.var(Y)*10
    PLL=[np.full(n,P0) for _ in range(R)]; PLX=[np.zeros(n) for _ in range(R)]
    PXX=[np.full(n,np.var(Y)) for _ in range(R)]
    pr=T[1,0]/(T[0,1]+T[1,0]); p=[np.full(n,pr),np.full(n,1-pr)]
    for t in range(Tn):
        y=Y[:,t]; bl={}
        for i in range(R):
            for j in range(R):
                d=1.0-ks[j]; Xp=X[i]*d; Lp=L[i]
                A=PLL[i]+qL; B=PLX[i]*d; C=PXX[i]*d*d+qX
                Sv=A+2*B+C+r; v=y-(Lp+Xp)
                HL=A+B; HX=B+C; KL=HL/Sv; KX=HX/Sv
                bl[(i,j)]=dict(L=Lp+KL*v,X=Xp+KX*v,PLL=A-KL*HL,PLX=B-KL*HX,PXX=C-KX*HX,
                               w=p[i]*T[i,j]*np.exp(-0.5*(v*v/Sv))/np.sqrt(2*np.pi*Sv))
        tot=np.maximum(sum(bl[(i,j)]["w"] for i in range(R) for j in range(R)),1e-300)
        nn=[sum(bl[(i,j)]["w"] for i in range(R)) for j in range(R)]
        for j in range(R):
            pj=np.maximum(nn[j],1e-300)
            Lj=sum(bl[(i,j)]["w"]*bl[(i,j)]["L"] for i in range(R))/pj
            Xj=sum(bl[(i,j)]["w"]*bl[(i,j)]["X"] for i in range(R))/pj
            PLLj=sum(bl[(i,j)]["w"]*(bl[(i,j)]["PLL"]+(bl[(i,j)]["L"]-Lj)**2) for i in range(R))/pj
            PXXj=sum(bl[(i,j)]["w"]*(bl[(i,j)]["PXX"]+(bl[(i,j)]["X"]-Xj)**2) for i in range(R))/pj
            PLXj=sum(bl[(i,j)]["w"]*(bl[(i,j)]["PLX"]+(bl[(i,j)]["L"]-Lj)*(bl[(i,j)]["X"]-Xj)) for i in range(R))/pj
            L[j],X[j],PLL[j],PLX[j],PXX[j]=Lj,Xj,PLLj,PLXj,PXXj
            p[j]=pj/tot
    return L,X,p

def forecast(W,ks,qL,qX,r,T,seed=3):
    L,X,p=run(W,ks,qL,qX,r,T)
    rng=np.random.default_rng(seed); n=len(W)
    u=rng.random((n,NS)); reg=(u>p[0][:,None]).astype(int)
    Ls=np.where(reg==0,L[0][:,None],L[1][:,None]).astype(float)
    Xs=np.where(reg==0,X[0][:,None],X[1][:,None]).astype(float)
    out={}
    for s_ in range(1,HOR+1):
        sw=rng.random((n,NS))
        stay=np.where(reg==0,1-T[0,1],1-T[1,0]); reg=np.where(sw<stay,reg,1-reg)
        Ls=Ls+rng.normal(0,np.sqrt(qL),(n,NS))
        k=np.where(reg==0,ks[0],ks[1]); Xs=Xs*(1-k)+rng.normal(0,np.sqrt(qX),(n,NS))
        if s_ in (1,20): out[s_]=Ls+Xs+rng.normal(0,np.sqrt(r),(n,NS))
    return out

def crps(E,y):
    M=E.shape[1]; t1=np.abs(E-y[:,None]).mean(1)
    Es=np.sort(E,1); j=np.arange(1,M+1)
    return t1-0.5*(2.0/M**2)*((2*j-M-1)*Es).sum(1)

def halflife(k): return f"{-0.5*np.log(2)/np.log(1-k):.1f}h" if 0<k<1 else "diverging"

TRUTHS=[
 ("E0's vector (the project's own)", 0.0850,-0.0200,0.4880,0.4750,0.0980,0.0379,0.0912),
 ("strong reverter, quiet mean",     0.1500,-0.0100,0.0100,0.5000,0.0100,0.0200,0.1500),
 ("strong reverter, drifting mean",  0.1500,-0.0100,0.3000,0.5000,0.0100,0.0200,0.1500),
 ("weak reverter",                   0.0200,-0.0050,0.2000,0.5000,0.0500,0.0300,0.1000),
]
print(f"{'truth':<34}{'half-life':>10}{'n':>7}{'clim':>8}{'ORACLE':>9}{'% clim':>8}"
      f"{'ctr R2':>8}{'band':>7}{'cover':>7}")
for name,kr,kd,qL,qX,r,qrd,qdr in TRUTHS:
    t0=time.time()
    S=generate(kr,kd,qL,qX,r,qrd,qdr)
    W,Y,sg=screen(S)
    if len(W)<500: print(f"{name:<34} only {len(W)} triggers"); continue
    T=np.array([[1-qrd,qrd],[qdr,1-qdr]])
    out=forecast(W,[kr,kd],qL,qX,r,T)
    y0=Y[:,0]; a=Y[:,HOR]
    chgs=(a-y0)/sg                                   # in sigma units, as real
    rng=np.random.default_rng(11)
    CE=(y0[:,None]+rng.choice(chgs-chgs.mean(),size=(len(W),NS),replace=True)*sg[:,None])
    cl=crps(CE/sg[:,None],a/sg).mean()
    E=out[HOR]
    oc=crps(E/sg[:,None],a/sg).mean()
    mc=E.mean(1)
    R2=np.corrcoef((mc-y0)/sg,chgs)[0,1]**2
    sd=E.std(1); band=np.nanstd((a-mc)/sg)/ (sd/sg).mean()
    cov=(np.abs((a-mc)/sd)<=1.645).mean()*100
    print(f"{name:<34}{halflife(kr):>10}{len(W):>7}{cl:>8.3f}{oc:>9.3f}"
          f"{100*oc/cl:>7.1f}%{100*R2:>7.2f}%{band:>7.2f}{cov:>6.1f}%", flush=True)
