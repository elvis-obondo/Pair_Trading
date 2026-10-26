"""Phase: increment distribution. Item 1 -- fat tails (nu), one parameter.

The seven are PINNED at E0's values and not refitted. nu is fitted directly to
the observed 30-minute increments, which we see 1.2M of, rather than added to
the window likelihood.

Split: the agreed one, 2026-07-18. Everything below is HELD OUT.
"""
import sys, warnings
sys.path.insert(0,"/Users/elvisobondo/Pair_Trading/research")
import numpy as np, pandas as pd
from scipy import stats, optimize
warnings.filterwarnings("ignore")

KR,KD,QL,QX,R,QRD,QDR = 0.0850,-0.0200,0.4880,0.4750,0.0980,0.0379,0.0912
T=np.array([[1-QRD,QRD],[QDR,1-QDR]])
HOR,NS=20,200
D="/private/tmp/claude-501/-Users-elvisobondo-Pair-Trading/0189ea06-e901-4d24-83ff-b7b3c5ca8f65/scratchpad/disloc"
z=np.load(D+".npz"); W=z["windows"].astype(float); Y=z["outcomes"].astype(float)
M=pd.read_parquet(D+"_meta.parquet"); day=M.day.to_numpy()
te=day>=np.datetime64("2026-07-18")
Wte,Yte,Mte=W[te],Y[te],M[te].reset_index(drop=True)
print(f"[DATA] held out {te.sum():,} dislocations x {HOR} steps = {te.sum()*HOR:,} real 30-minute moves\n")

QS=[50,90,99,99.9]
def qtab(x):
    a=np.abs(x); return [np.percentile(a,q) for q in QS]+[a.max()]
LBL=["median","1 in 10","1 in 100","1 in 1,000","largest"]

# ---------------- A. reality ----------------
d=np.diff(Yte,axis=1)                      # (n,20) real 30-minute moves, sigma units
dflat=d.ravel()
real=qtab(dflat)

# ---------------- B. the model as it stands ----------------
def filt(Y_,ks,qL,qX,r,T,innov=False):
    n,Tn=Y_.shape
    L=[np.zeros(n),np.zeros(n)]; X=[np.zeros(n),np.zeros(n)]
    P0=10.0
    PLL=[np.full(n,P0),np.full(n,P0)]; PLX=[np.zeros(n),np.zeros(n)]
    PXX=[np.ones(n),np.ones(n)]
    pr=T[1,0]/(T[0,1]+T[1,0]); p=[np.full(n,pr),np.full(n,1-pr)]
    IN=[]
    for t in range(Tn):
        y=Y_[:,t]; bl={}
        for i in range(2):
            for j in range(2):
                dd=1.0-ks[j]; Xp=X[i]*dd; Lp=L[i]
                A=PLL[i]+qL; B=PLX[i]*dd; C=PXX[i]*dd*dd+qX
                Sv=A+2*B+C+r; v=y-(Lp+Xp)
                if innov and i==0 and j==0: IN.append(v/np.sqrt(Sv))
                HL=A+B; HX=B+C; KL=HL/Sv; KX=HX/Sv
                bl[(i,j)]=dict(L=Lp+KL*v,X=Xp+KX*v,PLL=A-KL*HL,PLX=B-KL*HX,PXX=C-KX*HX,
                               w=p[i]*T[i,j]*np.exp(-0.5*(v*v/Sv))/np.sqrt(2*np.pi*Sv))
        tot=np.maximum(sum(bl[(i,j)]["w"] for i in range(2) for j in range(2)),1e-300)
        nn=[sum(bl[(i,j)]["w"] for i in range(2)) for j in range(2)]
        for j in range(2):
            pj=np.maximum(nn[j],1e-300)
            Lj=sum(bl[(i,j)]["w"]*bl[(i,j)]["L"] for i in range(2))/pj
            Xj=sum(bl[(i,j)]["w"]*bl[(i,j)]["X"] for i in range(2))/pj
            PLLj=sum(bl[(i,j)]["w"]*(bl[(i,j)]["PLL"]+(bl[(i,j)]["L"]-Lj)**2) for i in range(2))/pj
            PXXj=sum(bl[(i,j)]["w"]*(bl[(i,j)]["PXX"]+(bl[(i,j)]["X"]-Xj)**2) for i in range(2))/pj
            PLXj=sum(bl[(i,j)]["w"]*(bl[(i,j)]["PLX"]+(bl[(i,j)]["L"]-Lj)*(bl[(i,j)]["X"]-Xj)) for i in range(2))/pj
            L[j],X[j],PLL[j],PLX[j],PXX[j]=Lj,Xj,PLLj,PLXj,PXXj
            p[j]=pj/tot
    return (L,X,p,np.array(IN).T) if innov else (L,X,p)

def draw(rng,shape,nu,var):
    """mean 0, variance `var`; Gaussian if nu is None, else Student-t"""
    if nu is None: return rng.normal(0,np.sqrt(var),shape)
    return rng.standard_t(nu,shape)*np.sqrt(var*(nu-2)/nu)

def simulate(L,X,p,nu=None,seed=3):
    rng=np.random.default_rng(seed); n=len(L[0])
    reg=(rng.random((n,NS))>p[0][:,None]).astype(int)
    Ls=np.where(reg==0,L[0][:,None],L[1][:,None]).astype(float)
    Xs=np.where(reg==0,X[0][:,None],X[1][:,None]).astype(float)
    path=np.empty((n,NS,HOR+1))
    path[:,:,0]=Ls+Xs+draw(rng,(n,NS),nu,R)
    for s_ in range(1,HOR+1):
        sw=rng.random((n,NS))
        stay=np.where(reg==0,1-T[0,1],1-T[1,0]); reg=np.where(sw<stay,reg,1-reg)
        Ls=Ls+draw(rng,(n,NS),nu,QL)
        k=np.where(reg==0,KR,KD); Xs=Xs*(1-k)+draw(rng,(n,NS),nu,QX)
        path[:,:,s_]=Ls+Xs+draw(rng,(n,NS),nu,R)
    return path

L,X,p,INN=filt(Wte,[KR,KD],QL,QX,R,T,innov=True)

# ---------------- C. fit nu ----------------
sub=np.random.default_rng(0).choice(dflat,300_000,replace=False)
nu_raw,_,s_raw=stats.t.fit(sub,floc=0.0)
ll_t=stats.t.logpdf(sub,nu_raw,0,s_raw).sum()
ll_n=stats.norm.logpdf(sub,0,sub.std()).sum()
print(f"[FIT] Student-t on RAW increments      nu {nu_raw:.3f}  scale {s_raw:.4f}")
print(f"[FIT] Gaussian on the same            sd {sub.std():.4f}")
print(f"      log-lik  t {ll_t:,.0f}   gaussian {ll_n:,.0f}   t better by {ll_t-ll_n:,.0f}\n")

isub=np.random.default_rng(1).choice(INN.ravel(),300_000,replace=False)
isub=isub[np.isfinite(isub)]
nu_in,_,s_in=stats.t.fit(isub,floc=0.0)
print(f"[FIT] Student-t on FILTER ONE-STEP INNOVATIONS   nu {nu_in:.3f}  scale {s_in:.4f}")
print(f"      nu moves {nu_raw:.3f} -> {nu_in:.3f} once the reverting pull and drift are removed\n")

# ---------------- D. is the extreme tail real? ----------------
print("="*88); print("TAIL VALIDITY -- is a 50-sigma 30-minute move market behaviour or a bad print?"); print("="*88)
fl=np.abs(d).ravel(); top=np.argsort(fl)[-40:][::-1]
ri,si=np.unravel_index(top,d.shape)
rows=[]
for r_,s_ in zip(ri,si):
    m=Mte.iloc[r_]
    rows.append((f"{m.ticker_a}/{m.ticker_b}", str(pd.Timestamp(m.entry_time).date()),
                 int(s_), abs(d[r_,s_]), m.sigma, abs(d[r_,s_])*m.sigma))
tp=pd.DataFrame(rows,columns=["pair","entry_date","step","move_sigma","sigma","move_logpx"])
print(tp.head(12).to_string(index=False))
legs=pd.Series([t for p_ in tp.pair for t in p_.split("/")]).value_counts()
print(f"\n  40 largest moves span {tp.pair.nunique()} pairs, {tp.entry_date.nunique()} dates")
print(f"  most frequent legs: {dict(legs.head(6))}")
print(f"  implied LOG-PRICE move (sigma units x sigma): median {tp.move_logpx.median():.3f}, "
      f"max {tp.move_logpx.max():.3f}")
print(f"  -> a log move of 0.69 is a 2x price change in 30 minutes")

SUSPECT=set(legs[legs>=3].index)
keep=np.array([not (set(f"{a}/{b}".split('/')) & SUSPECT)
               for a,b in zip(Mte.ticker_a,Mte.ticker_b)])
dk=np.diff(Yte[keep],axis=1).ravel()
print(f"\n  excluding every dislocation touching {sorted(SUSPECT)} "
      f"({(~keep).sum():,} of {len(keep):,} dislocations):")
rk=qtab(dk)
print(f"    {'':12}{'all':>10}{'ex-suspect':>12}")
for i,l in enumerate(LBL):
    print(f"    {l:<12}{real[i]:>10.2f}{rk[i]:>12.2f}")
nu_k,_,_=stats.t.fit(np.random.default_rng(2).choice(dk,200_000,replace=False),floc=0.0)
print(f"    nu refitted without them: {nu_k:.3f}  (was {nu_raw:.3f})")

# ---------------- E. scorecard ----------------
def scorecard(tag,nu):
    P=simulate(L,X,p,nu=nu)
    md=np.diff(P,axis=2).ravel()
    mq=qtab(md)
    a=Yte[:,HOR]; E=P[:,:,HOR]
    rk=(E<a[:,None]).mean(1)
    outside=100*np.mean((rk<=0.005)|(rk>=0.995))
    out={}
    for s_,lab in ((1,"0.5h"),(HOR,"10h")):
        aa=Yte[:,s_]; mn=P[:,:,s_].mean(1); sd=P[:,:,s_].std(1)
        out[lab]=(np.std(aa-mn)/sd.mean(), 100*np.mean(np.abs((aa-mn)/sd)<=1.645))
    y0=Yte[:,0]; chg=a-y0
    rng=np.random.default_rng(11)
    CE=y0[:,None]+rng.choice(chg-chg.mean(),size=(len(y0),NS),replace=True)
    def crps(Ee,yy):
        m=Ee.shape[1]; t1=np.abs(Ee-yy[:,None]).mean(1)
        Es=np.sort(Ee,1); j=np.arange(1,m+1)
        return t1-0.5*(2.0/m**2)*((2*j-m-1)*Es).sum(1)
    cl=crps(CE,a).mean(); cm=crps(E,a).mean()
    print(f"\n--- {tag} ---")
    print(f"  {'move size':<12}{'model':>9}{'real':>9}{'ratio':>8}")
    for i,l in enumerate(LBL):
        print(f"  {l:<12}{mq[i]:>9.2f}{real[i]:>9.2f}{mq[i]/real[i]:>8.2f}x")
    print(f"  outside all {NS} draws  {outside:>5.2f}%   (target <2%)")
    print(f"  band 0.5h {out['0.5h'][0]:.2f}x cover {out['0.5h'][1]:.1f}%   "
          f"band 10h {out['10h'][0]:.2f}x cover {out['10h'][1]:.1f}%")
    print(f"  CRPS {cm:.3f} vs climatology {cl:.3f} = {100*cm/cl:.1f}%")
    return mq,outside

print("\n"+"="*88); print("SCORECARD"); print("="*88)
scorecard("BASELINE  Gaussian, seven pinned at E0",None)
for nu in (nu_raw,nu_in,3.0):
    scorecard(f"nu = {nu:.3f}",nu)
