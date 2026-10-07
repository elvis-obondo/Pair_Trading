"""Is it the centre or the spread?

CRPS = how good your centre is + how honest your spread is. The eight fits in
exp.log move those two in OPPOSITE directions, so this decomposes them.

For each logged fit, four forecasts on the same dislocations:
  model      model centre, model spread
  mix_mc     model centre, CLIMATOLOGY spread
  mix_cm     "stays put" centre, model spread
  clim       "stays put" centre, climatology spread
Plus the centre error itself (MAE in sigma) against "stays put", by horizon,
and the best CRPS any forecast centred on "stays put" can reach (optimal
Gaussian width) -- the ceiling if the centre carries nothing.
"""
import sys
sys.path.insert(0,"/Users/elvisobondo/Pair_Trading/research")
import numpy as np, pandas as pd
import universe_panel

BARS, DT_H, STEPS, NSUB = 336, 0.5, 20, 10
R_META="/Users/elvisobondo/Pair_Trading/research/exit_study/"
m=pd.read_parquet(R_META+"paths_meta.parquet"); S=np.load(R_META+"paths.npz")["spreads"]
panel=universe_panel.load_panel(); panel.index=pd.to_datetime(panel.index)
if panel.index.tz is not None: panel.index=panel.index.tz_convert("UTC").tz_localize(None)
opened=pd.to_datetime(m.opened_at)
mu=m.mu_at_entry.to_numpy(float); sg=m.sigma_at_entry.to_numpy(float)
bt=m.beta_at_entry.to_numpy(float); al=m.alpha_at_entry.to_numpy(float)
st=m.path_start.to_numpy(int); ln=m.path_len.to_numpy(int)
pos=panel.index.searchsorted(opened.to_numpy(), side="left")
W,keep=[],[]
for i in range(len(m)):
    ta,tb,j=m.ticker_a.iloc[i],m.ticker_b.iloc[i],pos[i]
    if ta not in panel.columns or tb not in panel.columns or j<BARS: continue
    a=panel[ta].to_numpy(float)[j-BARS:j]; b=panel[tb].to_numpy(float)[j-BARS:j]
    if not (np.isfinite(a).all() and np.isfinite(b).all()): continue
    W.append((a-bt[i]*b-al[i]-mu[i])/sg[i]); keep.append(i)
W=np.array(W); keep=np.array(keep); N=len(keep)
print(f"[INFO] {N} windows x {BARS} bars",flush=True)

def fX(X,k,g=0.0): return X*(1.0-k)
def dfX(X,k,g=0.0): return np.full_like(X,1.0-k)

def run(Y,ks,qL,qX,r,T,state=False):
    n,Tn=Y.shape; R=len(ks)
    L=[np.zeros(n) for _ in range(R)]; X=[np.zeros(n) for _ in range(R)]
    PLL=[np.full(n,10.) for _ in range(R)]; PLX=[np.zeros(n) for _ in range(R)]
    PXX=[np.ones(n) for _ in range(R)]
    pr=T[1,0]/(T[0,1]+T[1,0]); p=[np.full(n,pr),np.full(n,1-pr)]
    ll=np.zeros(n)
    for t in range(Tn):
        y=Y[:,t]; bl={}
        for i in range(R):
            for j in range(R):
                Xp=fX(X[i],ks[j]); d=dfX(X[i],ks[j]); Lp=L[i]
                A=PLL[i]+qL; B=PLX[i]*d; C=PXX[i]*d*d+qX
                Sv=A+2*B+C+r; v=y-(Lp+Xp)
                HL=A+B; HX=B+C; KL=HL/Sv; KX=HX/Sv
                bl[(i,j)]=dict(L=Lp+KL*v, X=Xp+KX*v,
                               PLL=A-KL*HL, PLX=B-KL*HX, PXX=C-KX*HX,
                               w=p[i]*T[i,j]*np.exp(-0.5*(v*v/Sv))/np.sqrt(2*np.pi*Sv))
        tot=np.maximum(sum(bl[(i,j)]["w"] for i in range(R) for j in range(R)),1e-300)
        ll+=np.log(tot)
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
    return (L,X,p) if state else ll.sum()

def simulate(ks,qL,qX,r,T,seed=3,NS=200):
    L,X,p=run(W,ks,qL,qX,r,T,state=True)
    rng=np.random.default_rng(seed)
    u=rng.random((N,NS)); reg=(u>p[0][:,None]).astype(int)
    Ls=np.where(reg==0,L[0][:,None],L[1][:,None]).astype(float)
    Xs=np.where(reg==0,X[0][:,None],X[1][:,None]).astype(float)
    out={}
    for s_ in range(1,STEPS+1):
        sw=rng.random((N,NS))
        stay=np.where(reg==0,1-T[0,1],1-T[1,0]); reg=np.where(sw<stay,reg,1-reg)
        Ls=Ls+rng.normal(0,np.sqrt(qL),(N,NS))
        Xn=np.where(reg==0,fX(Xs,ks[0]),fX(Xs,ks[1]))
        Xs=Xn+rng.normal(0,np.sqrt(qX),(N,NS))
        if s_ in (1,2,4,STEPS): out[s_]=(Ls+Xs+rng.normal(0,np.sqrt(r),(N,NS))).copy()
    return out

def crps(E,y):
    NS=E.shape[1]; t1=np.abs(E-y[:,None]).mean(1)
    Es=np.sort(E,1); j=np.arange(1,NS+1)
    return t1-0.5*(2.0/NS**2)*((2*j-NS-1)*Es).sum(1)

def actual(s_):
    okh=(s_*30<ln[keep])
    a=np.where(okh,(S[np.clip(st[keep]+s_*30,0,len(S)-1)]-mu[keep])/sg[keep],np.nan)
    return a,np.isfinite(a)

y0=W[:,-1]
ACT={s_:actual(s_) for s_ in (1,2,4,STEPS)}
_rng=np.random.default_rng(11)
# climatology spread per horizon: pooled historical change over THAT horizon
CLIM={}
for s_,(a,gd) in ACT.items():
    chg=(a-y0)[gd]
    CLIM[s_]=(chg, y0[:,None]+_rng.choice(chg,size=(N,200),replace=True))

print("\n=== centre error, MAE in sigma (lower is better) ===")
print(f"{'horizon':>8} {'stays put':>10} {'clim CRPS':>10} {'chg sd':>8} {'best-sd':>8} {'best CRPS':>10}")
BEST={}
for s_ in (1,2,4,STEPS):
    a,gd=ACT[s_]; chg,ce=CLIM[s_]
    cl=crps(ce[gd],a[gd]).mean()
    # best Gaussian centred on stays-put: optimise sd
    err=(a-y0)[gd]
    g=np.random.default_rng(5).normal(0,1,(gd.sum(),400))
    bs,bc=None,np.inf
    for sd in np.linspace(0.2*chg.std(),2.0*chg.std(),40):
        c=crps(y0[gd][:,None]+sd*g,a[gd]).mean()
        if c<bc: bc,bs=c,sd
    BEST[s_]=(cl,bc)
    print(f"{s_*0.5:>7.1f}h {np.abs(err).mean():>10.4f} {cl:>10.3f} {chg.std():>8.3f} {bs:>8.3f} {bc:>10.3f}")

FITS=[
 ("E0  unfitted      ", 0.0850,-0.0200,0.4880,0.4750,0.0980,0.0379,0.0912),
 ("E1  D from C      ", 1.0000, 0.0061,0.2347,0.5783,0.0000,0.1291,0.0147),
 ("E3  g pinned 0    ", 1.0000, 0.0051,0.2825,0.5354,0.0000,0.1497,0.0163),
 ("E2.0 random       ", 1.0000, 0.0044,0.2268,0.5845,0.0000,0.1130,0.0138),
 ("E2.1 random       ", 0.6413,-0.1110,0.6770,0.0059,0.1458,0.0111,0.0620),
 ("E2.2 random       ", 1.0000,-0.0005,0.0684,0.9164,0.0120,0.2097,0.0044),
 ("E2.3 random       ", 1.0000, 0.0041,0.2292,0.5877,0.0000,0.1126,0.0137),
]
print("\n=== CRPS as % of climatology, by what you swap in ===")
print("  model  = model centre + model spread      mix_mc = model centre + clim spread")
print("  mix_cm = stays-put centre + model spread  (clim = 100.0 by definition)\n")
print(f"{'fit':<20}{'h':>6} {'ctr MAE':>8} {'model':>7} {'mix_mc':>7} {'mix_cm':>7}")
for name,kr,kd,qL,qX,r,qrd,qdr in FITS:
    T=np.array([[1-qrd,qrd],[qdr,1-qdr]])
    out=simulate([kr,kd],qL,qX,max(r,1e-9),T)
    for s_ in (1,2,4,STEPS):
        a,gd=ACT[s_]; chg,ce=CLIM[s_]; cl=BEST[s_][0]
        E=out[s_]; mc=E.mean(1)
        c_model=crps(E[gd],a[gd]).mean()
        c_mc=crps(mc[gd][:,None]+(ce[gd]-y0[gd][:,None]),a[gd]).mean()
        c_cm=crps(y0[gd][:,None]+(E[gd]-mc[gd][:,None]),a[gd]).mean()
        print(f"{name if s_==1 else '':<20}{s_*0.5:>5.1f}h {np.abs(a[gd]-mc[gd]).mean():>8.4f}"
              f" {100*c_model/cl:>6.1f}% {100*c_mc/cl:>6.1f}% {100*c_cm/cl:>6.1f}%")
    print(flush=True)
