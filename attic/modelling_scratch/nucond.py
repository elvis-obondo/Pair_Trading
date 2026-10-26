"""nu re-fitted CONDITIONAL on v_0, then the scorecard at 2,000 draws.

nu=2.689 was fitted on the pooled unconditional increment pool, which contains
between-episode volatility heterogeneity -- the very thing v_0 now models. So
stacking them double-counts. Standardising each dislocation's increments by
sqrt of its own v_0 multiplier strips that heterogeneity out and leaves the
genuine within-increment tail.

Everything here is fitted on the FIT period only. 2,000 draws instead of 200:
outside-all is a tail event and 200 draws puts its floor at 2/201 = 0.995%,
which is the same size as the effect we are steering by. At 2,000 the floor is
~0.1%. Day-clustered interval on outside-all throughout -- it is the metric the
phase is steered by and it has never carried one.
"""
import sys, time, warnings
sys.path.insert(0,"/Users/elvisobondo/Pair_Trading/research")
import numpy as np, pandas as pd
from scipy import stats
warnings.filterwarnings("ignore")

KR,KD,QL,QX,R,QRD,QDR = 0.0850,-0.0200,0.4880,0.4750,0.0980,0.0379,0.0912
HOR,NS,CH = 20,2000,600
T=np.array([[1-QRD,QRD],[QDR,1-QDR]])
D="/private/tmp/claude-501/-Users-elvisobondo-Pair-Trading/0189ea06-e901-4d24-83ff-b7b3c5ca8f65/scratchpad/disloc"
z=np.load(D+".npz"); W=z["windows"].astype(float); Y=z["outcomes"].astype(float)
M=pd.read_parquet(D+"_meta.parquet"); day=M.day.to_numpy()
tr=day<np.datetime64("2026-07-18"); te=~tr
dW=np.diff(W,axis=1); dF=np.diff(Y,axis=1)

PRE=np.column_stack([np.log(np.maximum((dW[:,-k:]**2).mean(1),1e-12)) for k in (48,96,335)])
rvPost=np.log(np.maximum((dF**2).mean(1),1e-12))
A=np.column_stack([np.ones(tr.sum()),PRE[tr]])
c=np.linalg.lstsq(A,rvPost[tr],rcond=None)[0]
pred=np.column_stack([np.ones(len(W)),PRE])@c
mult=np.exp(pred-np.log(np.mean(np.exp(pred[tr]))))

# ---- nu, unconditional vs conditional, BOTH on the fit period ----
rg=np.random.default_rng(0)
unc=dF[tr].ravel(); con=(dF[tr]/np.sqrt(mult[tr])[:,None]).ravel()
su=rg.choice(unc,300_000,replace=False); sc=rg.choice(con,300_000,replace=False)
nu_u,_,s_u=stats.t.fit(su,floc=0.0)
nu_c,_,s_c=stats.t.fit(sc,floc=0.0)
print(f"[nu] UNCONDITIONAL, fit period : nu {nu_u:.3f}  scale {s_u:.4f}")
print(f"[nu] CONDITIONAL on v_0        : nu {nu_c:.3f}  scale {s_c:.4f}")
print(f"     nu moves {nu_u:.3f} -> {nu_c:.3f} ({100*(nu_c-nu_u)/nu_u:+.1f}%) once between-episode")
print(f"     heterogeneity is removed from the pool -- thinner, as expected\n")
print(f"[v_0] held-out multiplier mean {mult[te].mean():.3f}  p95/p5 "
      f"{np.percentile(mult[te],95)/np.percentile(mult[te],5):.1f}x\n")

Wte,Yte=W[te],Y[te]; m=mult[te]; n=te.sum(); dte=day[te]
a=Yte[:,HOR]; y0=Yte[:,0]; chg=a-y0
CE=y0[:,None]+np.random.default_rng(11).choice(chg-chg.mean(),size=(n,200),replace=True)
def crps(E,y):
    q=E.shape[1]; t1=np.abs(E-y[:,None]).mean(1)
    Es=np.sort(E,1); j=np.arange(1,q+1)
    return t1-0.5*(2.0/q**2)*((2*j-q-1)*Es).sum(1)
CL=crps(CE,a).mean()
real=[np.percentile(np.abs(dF[te]),q) for q in (50,90,99,99.9)]+[np.abs(dF[te]).max()]
LBL=["median","1 in 10","1 in 100","1 in 1,000","largest"]

def filt(Y_,qL,qX,r):
    nn_,Tn=Y_.shape; ks=[KR,KD]
    L=[np.zeros(nn_),np.zeros(nn_)]; X=[np.zeros(nn_),np.zeros(nn_)]
    PLL=[np.full(nn_,10.0),np.full(nn_,10.0)]; PLX=[np.zeros(nn_),np.zeros(nn_)]
    PXX=[np.ones(nn_),np.ones(nn_)]
    pr=T[1,0]/(T[0,1]+T[1,0]); p=[np.full(nn_,pr),np.full(nn_,1-pr)]
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
        nnw=[sum(bl[(i,j)]["w"] for i in range(2)) for j in range(2)]
        for j in range(2):
            pj=np.maximum(nnw[j],1e-300)
            Lj=sum(bl[(i,j)]["w"]*bl[(i,j)]["L"] for i in range(2))/pj
            Xj=sum(bl[(i,j)]["w"]*bl[(i,j)]["X"] for i in range(2))/pj
            PLLj=sum(bl[(i,j)]["w"]*(bl[(i,j)]["PLL"]+(bl[(i,j)]["L"]-Lj)**2) for i in range(2))/pj
            PXXj=sum(bl[(i,j)]["w"]*(bl[(i,j)]["PXX"]+(bl[(i,j)]["X"]-Xj)**2) for i in range(2))/pj
            PLXj=sum(bl[(i,j)]["w"]*(bl[(i,j)]["PLX"]+(bl[(i,j)]["L"]-Lj)*(bl[(i,j)]["X"]-Xj)) for i in range(2))/pj
            L[j],X[j],PLL[j],PLX[j],PXX[j]=Lj,Xj,PLLj,PLXj,PXXj
            p[j]=pj/tot
    return L,X,p

def card(tag,qL,qX,r,nu):
    t0=time.time(); L,X,p=filt(Wte,qL,qX,r)
    outs=np.empty(n,bool); cm=np.empty(n); b={1:[],HOR:[]}; keep=[]
    for lo in range(0,n,CH):
        hi=min(lo+CH,n); k=hi-lo; sl=slice(lo,hi)
        rng=np.random.default_rng(1000+lo)
        def dr(var):
            if nu is None: return (rng.normal(0,1,(k,NS))*np.sqrt(var[sl])[:,None]).astype(np.float32)
            return (rng.standard_t(nu,(k,NS))*np.sqrt(var[sl]*(nu-2)/nu)[:,None]).astype(np.float32)
        reg=(rng.random((k,NS))>p[0][sl][:,None]).astype(np.int8)
        Ls=np.where(reg==0,L[0][sl][:,None],L[1][sl][:,None]).astype(np.float32)
        Xs=np.where(reg==0,X[0][sl][:,None],X[1][sl][:,None]).astype(np.float32)
        prev=Ls+Xs+dr(r); dsub=[]
        for s_ in range(1,HOR+1):
            sw=rng.random((k,NS))
            stay=np.where(reg==0,1-T[0,1],1-T[1,0]); reg=np.where(sw<stay,reg,1-reg)
            Ls=Ls+dr(qL)
            kk=np.where(reg==0,KR,KD).astype(np.float32); Xs=Xs*(1-kk)+dr(qX)
            cur=Ls+Xs+dr(r)
            dsub.append(np.abs(cur-prev)[:, ::40])
            if s_ in (1,HOR):
                aa=Yte[sl,s_]; mn=cur.mean(1); sd=cur.std(1)
                b[s_].append((aa-mn,sd))
            prev=cur
        rk=(cur<Yte[sl,HOR][:,None]).mean(1)
        outs[sl]=(rk<=1.0/NS)|(rk>=1-1.0/NS)
        cm[sl]=crps(cur.astype(np.float64),Yte[sl,HOR])
        keep.append(np.concatenate(dsub).ravel())
    md=np.concatenate(keep)
    mq=[np.percentile(md,q) for q in (50,90,99,99.9)]+[md.max()]
    du=np.unique(dte); pos={d:np.flatnonzero(dte==d) for d in du}
    rb=np.random.default_rng(5); bs=np.empty(400)
    for i in range(400):
        s=np.concatenate([pos[d] for d in rb.choice(du,len(du),replace=True)])
        bs[i]=100*outs[s].mean()
    o=100*outs.mean()
    print(f"\n--- {tag}  ({time.time()-t0:.0f}s, {NS} draws) ---")
    print(f"  {'move size':<12}{'model':>9}{'real':>9}{'ratio':>8}")
    for i,l in enumerate(LBL): print(f"  {l:<12}{mq[i]:>9.2f}{real[i]:>9.2f}{mq[i]/real[i]:>8.2f}x")
    print(f"  outside all {NS} draws  {o:.2f}%   day-clustered 95% "
          f"[{np.percentile(bs,2.5):.2f}%, {np.percentile(bs,97.5):.2f}%]   floor {100*2/(NS+1):.2f}%")
    for s_,lab in ((1,"0.5h"),(HOR,"10h")):
        er=np.concatenate([x[0] for x in b[s_]]); sd=np.concatenate([x[1] for x in b[s_]])
        print(f"  band {lab} {np.std(er)/sd.mean():.2f}x  cover {100*np.mean(np.abs(er/sd)<=1.645):.1f}%")
    print(f"  CRPS {cm.mean():.3f} vs climatology {CL:.3f} = {100*cm.mean()/CL:.1f}%", flush=True)

one=np.ones(n)
print("="*80); print(f"SCORECARD at {NS} draws"); print("="*80)
card("A baseline gaussian, seven pinned",QL*one,QX*one,R*one,None)
card(f"B nu unconditional {nu_u:.3f}",QL*one,QX*one,R*one,nu_u)
card(f"C nu unconditional {nu_u:.3f} + v_0",QL*m,QX*m,R*m,nu_u)
card(f"D nu CONDITIONAL {nu_c:.3f} + v_0",QL*m,QX*m,R*m,nu_c)
