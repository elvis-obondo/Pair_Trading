"""Item 2b -- v_0 only. Per-dislocation variance multiplier from the entry window.

Baseline: the seven PINNED at E0 plus nu = 2.689. Nothing is refitted.

v_0 = exp(predicted log post-entry realised variance), predicted from log RV
over the last 48 / 96 / 335 window bars, regression fitted on the FIT period
only. The multiplier scales qL, qX and r for that dislocation, centred on the
FIT period's own mean so no held-out information sets the level -- the realised
held-out mean multiplier is reported so the centring can be checked.

Scaling all three covariances by one common factor leaves the Kalman gain
unchanged, so the state ESTIMATE and therefore the forecast CENTRE are
untouched. This is purely a redistribution of dispersion across dislocations.
"""
import sys, warnings
sys.path.insert(0,"/Users/elvisobondo/Pair_Trading/research")
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")

KR,KD,QL,QX,R,QRD,QDR = 0.0850,-0.0200,0.4880,0.4750,0.0980,0.0379,0.0912
NU, HOR, NS = 2.689, 20, 200
T=np.array([[1-QRD,QRD],[QDR,1-QDR]])
D="/private/tmp/claude-501/-Users-elvisobondo-Pair-Trading/0189ea06-e901-4d24-83ff-b7b3c5ca8f65/scratchpad/disloc"
z=np.load(D+".npz"); W=z["windows"].astype(float); Y=z["outcomes"].astype(float)
M=pd.read_parquet(D+"_meta.parquet"); day=M.day.to_numpy()
tr=day<np.datetime64("2026-07-18"); te=~tr
dW=np.diff(W,axis=1); dF=np.diff(Y,axis=1)

# ---- v_0 ----
PRE=np.column_stack([np.log(np.maximum((dW[:,-k:]**2).mean(1),1e-12)) for k in (48,96,335)])
rvPost=np.log(np.maximum((dF**2).mean(1),1e-12))
A=np.column_stack([np.ones(tr.sum()),PRE[tr]])
c=np.linalg.lstsq(A,rvPost[tr],rcond=None)[0]
pred=np.column_stack([np.ones(len(W)),PRE])@c
base=np.log(np.mean(np.exp(pred[tr])))          # centred on the FIT period only
mult=np.exp(pred-base)
Wte,Yte=W[te],Y[te]; m=mult[te]
print(f"[v_0] regression on {tr.sum():,} fit rows, applied to {te.sum():,} held out")
print(f"      held-out multiplier: mean {m.mean():.3f}  median {np.median(m):.3f}  "
      f"p5 {np.percentile(m,5):.3f}  p95 {np.percentile(m,95):.3f}  "
      f"ratio p95/p5 {np.percentile(m,95)/np.percentile(m,5):.1f}x")
print(f"      (mean near 1.000 means the centring holds out of sample)\n")

def filt(Y_,qL,qX,r):
    n,Tn=Y_.shape
    L=[np.zeros(n),np.zeros(n)]; X=[np.zeros(n),np.zeros(n)]
    PLL=[np.full(n,10.0),np.full(n,10.0)]; PLX=[np.zeros(n),np.zeros(n)]
    PXX=[np.ones(n),np.ones(n)]
    pr=T[1,0]/(T[0,1]+T[1,0]); p=[np.full(n,pr),np.full(n,1-pr)]
    ks=[KR,KD]
    for t in range(Tn):
        y=Y_[:,t]; bl={}
        for i in range(2):
            for j in range(2):
                dd=1.0-ks[j]; Xp=X[i]*dd; Lp=L[i]
                Aa=PLL[i]+qL; B=PLX[i]*dd; C=PXX[i]*dd*dd+qX
                Sv=Aa+2*B+C+r; v=y-(Lp+Xp)
                HL=Aa+B; HX=B+C; KL=HL/Sv; KX=HX/Sv
                bl[(i,j)]=dict(L=Lp+KL*v,X=Xp+KX*v,PLL=Aa-KL*HL,PLX=B-KL*HX,PXX=C-KX*HX,
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
    return L,X,p

def drw(rng,n,nu,var):
    if nu is None: return rng.normal(0,1,(n,NS))*np.sqrt(var)[:,None]
    return rng.standard_t(nu,(n,NS))*np.sqrt(var*(nu-2)/nu)[:,None]

def sim(L,X,p,qL,qX,r,nu,seed=3):
    rng=np.random.default_rng(seed); n=len(L[0])
    reg=(rng.random((n,NS))>p[0][:,None]).astype(int)
    Ls=np.where(reg==0,L[0][:,None],L[1][:,None]).astype(float)
    Xs=np.where(reg==0,X[0][:,None],X[1][:,None]).astype(float)
    P=np.empty((n,NS,HOR+1)); P[:,:,0]=Ls+Xs+drw(rng,n,nu,r)
    for s_ in range(1,HOR+1):
        sw=rng.random((n,NS))
        stay=np.where(reg==0,1-T[0,1],1-T[1,0]); reg=np.where(sw<stay,reg,1-reg)
        Ls=Ls+drw(rng,n,nu,qL)
        k=np.where(reg==0,KR,KD); Xs=Xs*(1-k)+drw(rng,n,nu,qX)
        P[:,:,s_]=Ls+Xs+drw(rng,n,nu,r)
    return P

def crps(E,y):
    q=E.shape[1]; t1=np.abs(E-y[:,None]).mean(1)
    Es=np.sort(E,1); j=np.arange(1,q+1)
    return t1-0.5*(2.0/q**2)*((2*j-q-1)*Es).sum(1)

real=[np.percentile(np.abs(dF[te]),q) for q in (50,90,99,99.9)]+[np.abs(dF[te]).max()]
LBL=["median","1 in 10","1 in 100","1 in 1,000","largest"]
a=Yte[:,HOR]; y0=Yte[:,0]; chg=a-y0
CE=y0[:,None]+np.random.default_rng(11).choice(chg-chg.mean(),size=(len(y0),NS),replace=True)
CL=crps(CE,a).mean()
n=te.sum(); one=np.ones(n)

def card(tag,qL,qX,r,nu):
    L,X,p=filt(Wte,qL,qX,r)
    P=sim(L,X,p,qL,qX,r,nu)
    mq=[np.percentile(np.abs(np.diff(P,axis=2)),q) for q in (50,90,99,99.9)]+[np.abs(np.diff(P,axis=2)).max()]
    E=P[:,:,HOR]; rk=(E<a[:,None]).mean(1)
    outs=100*np.mean((rk<=0.005)|(rk>=0.995))
    row=[]
    for s_ in (1,HOR):
        aa=Yte[:,s_]; mn=P[:,:,s_].mean(1); sd=P[:,:,s_].std(1)
        row.append((np.std(aa-mn)/sd.mean(),100*np.mean(np.abs((aa-mn)/sd)<=1.645)))
    cm=crps(E,a).mean()
    print(f"\n--- {tag} ---")
    print(f"  {'move size':<12}{'model':>9}{'real':>9}{'ratio':>8}")
    for i,l in enumerate(LBL): print(f"  {l:<12}{mq[i]:>9.2f}{real[i]:>9.2f}{mq[i]/real[i]:>8.2f}x")
    print(f"  outside all {NS} draws  {outs:>5.2f}%   (GATE <2%)  {'PASS' if outs<2 else 'FAIL'}")
    print(f"  band 0.5h {row[0][0]:.2f}x cover {row[0][1]:.1f}%    band 10h {row[1][0]:.2f}x cover {row[1][1]:.1f}%")
    print(f"  CRPS {cm:.3f} vs climatology {CL:.3f} = {100*cm/CL:.1f}%")

print("="*78); print("SCORECARD"); print("="*78)
card("BASELINE  gaussian, seven pinned",QL*one,QX*one,R*one,None)
card("nu = 2.689",QL*one,QX*one,R*one,NU)
card("nu = 2.689  +  v_0",QL*m,QX*m,R*m,NU)
card("v_0 alone, gaussian",QL*m,QX*m,R*m,None)
