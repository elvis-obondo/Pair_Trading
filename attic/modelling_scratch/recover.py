"""Phase 2 item 3: synthetic recovery of the 7 parameters.

Generate from a KNOWN truth, screen with the same 3-sigma rule, fit with the
existing fitter, compare estimates to truth. The roadmap's threshold, declared
before any result is read: a parameter counts as FITTED when the median estimate
lands within 20% of truth; otherwise it is PINNED and the pinned value recorded.

Fitting is in RAW units with raw parameters so truth is exactly recoverable.
Three truths, three replications each.
"""
import sys, time
sys.path.insert(0,"/Users/elvisobondo/Pair_Trading/research")
import numpy as np
from scipy.optimize import minimize
exec(open("/private/tmp/claude-501/-Users-elvisobondo-Pair-Trading/0189ea06-e901-4d24-83ff-b7b3c5ca8f65/scratchpad/oracle.py").read().split("TRUTHS=[")[0])

sig=lambda z:1/(1+np.exp(-z))
inv=lambda p:np.log(p/(1-p))

def pack(kr,kd,qL,qX,r,qrd,qdr):
    return np.array([inv(kr),np.log(qL),np.log(qX),np.log(r),kd,
                     inv(qrd/0.5),inv(qdr/0.5)])
def unpack(th):
    kr=sig(th[0]); qL,qX,r=np.exp(th[1]),np.exp(th[2]),np.exp(th[3])
    kd=th[4]; qrd=sig(th[5])*0.5; qdr=sig(th[6])*0.5
    return kr,kd,qL,qX,r,qrd,qdr

def loglik(W,ks,qL,qX,r,T):
    n,Tn=W.shape
    L=[np.zeros(n),np.zeros(n)]; X=[np.zeros(n),np.zeros(n)]
    P0=np.var(W)*10
    PLL=[np.full(n,P0)]*1+[np.full(n,P0)]; PLX=[np.zeros(n),np.zeros(n)]
    PXX=[np.full(n,np.var(W)),np.full(n,np.var(W))]
    pr=T[1,0]/(T[0,1]+T[1,0]); p=[np.full(n,pr),np.full(n,1-pr)]
    ll=np.zeros(n)
    for t in range(Tn):
        y=W[:,t]; bl={}
        for i in range(2):
            for j in range(2):
                d=1.0-ks[j]; Xp=X[i]*d; Lp=L[i]
                A=PLL[i]+qL; B=PLX[i]*d; C=PXX[i]*d*d+qX
                Sv=A+2*B+C+r; v=y-(Lp+Xp)
                HL=A+B; HX=B+C; KL=HL/Sv; KX=HX/Sv
                bl[(i,j)]=dict(L=Lp+KL*v,X=Xp+KX*v,PLL=A-KL*HL,PLX=B-KL*HX,PXX=C-KX*HX,
                               w=p[i]*T[i,j]*np.exp(-0.5*(v*v/Sv))/np.sqrt(2*np.pi*Sv))
        tot=np.maximum(sum(bl[(i,j)]["w"] for i in range(2) for j in range(2)),1e-300)
        ll+=np.log(tot)
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
    return ll.sum()

def fit(W,th0,maxiter=2500):
    n=len(W)
    def nll(th):
        kr,kd,qL,qX,r,qrd,qdr=unpack(th)
        if not (-1<kd<1) or qL<=0 or qX<=0 or r<=0: return 1e15
        T=np.array([[1-qrd,qrd],[qdr,1-qdr]])
        v=loglik(W,[kr,kd],qL,qX,r,T)
        return 1e15 if not np.isfinite(v) else -v/n
    th=np.array(th0,float); prev=np.inf
    for _ in range(3):
        o=minimize(nll,th,method="Nelder-Mead",
                   options={"maxiter":maxiter,"maxfev":maxiter,"xatol":1e-5,"fatol":1e-5})
        th=o.x
        if prev-o.fun<1e-4: break
        prev=o.fun
    return th,o.fun

NAMES=["k_revert","k_diverge","qL","qX","r","q_rd","q_dr"]
TRUTHS=[
 ("E0's vector",            (0.0850,-0.0200,0.4880,0.4750,0.0980,0.0379,0.0912)),
 ("strong, drifting mean",  (0.1500,-0.0100,0.3000,0.5000,0.0100,0.0200,0.1500)),
 ("weak reverter",          (0.0200,-0.0050,0.2000,0.5000,0.0500,0.0300,0.1000)),
]
NREP=3
for label,truth in TRUTHS:
    print("="*92); print(f"TRUTH  {label}"); print("="*92,flush=True)
    print("  "+"  ".join(f"{k}={v:.4f}" for k,v in zip(NAMES,truth)),flush=True)
    ests=[]
    for rep in range(NREP):
        S=generate(*truth,nser=400,T=9000,seed=100+rep)
        W,Y,sg=screen(S,want=1500)
        t0=time.time()
        # started from a NEUTRAL vector, not from truth -- starting at truth
        # would only show the optimiser does not run away, not that it finds it
        th0=pack(0.05,-0.005,0.2,0.3,0.05,0.05,0.05)
        th,f_=fit(W,th0)
        e=unpack(th); ests.append(e)
        print(f"  rep{rep}  n={len(W)}  {time.time()-t0:.0f}s  nll {f_:.4f}")
        print("        "+"  ".join(f"{k}={v:.4f}" for k,v in zip(NAMES,e)),flush=True)
    E=np.array(ests)
    print(f"\n  {'param':<11}{'truth':>9}{'median est':>12}{'err %':>9}   verdict")
    for j,k in enumerate(NAMES):
        med=np.median(E[:,j]); t=truth[j]
        err=100*(med-t)/abs(t) if t!=0 else np.nan
        print(f"  {k:<11}{t:>9.4f}{med:>12.4f}{err:>8.1f}%   "
              f"{'FITTED' if abs(err)<=20 else 'PINNED/MISSED'}")
    print(flush=True)
