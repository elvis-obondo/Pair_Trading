"""v_0 as a PREDICTIVE DISTRIBUTION rather than a point estimate.

The model plugs v_0's mean in as if exact, but v_0 explains only 32.6% of log
post-entry variance -- two thirds of the multiplier is unknown and the model
pretends otherwise. Integrate over it instead: per simulated PATH,

    log m ~ Normal( prediction_i , fit-period residual variance )

This widens each episode in proportion to the forecast's own uncertainty, with
no need to identify which episodes turn violent. Note it also removes a Jensen
bias: E[exp(log RV)] > exp(E[log RV]), so the point estimate was systematically
under-scaling variance. Both effects are real; the realised mean multiplier is
reported so the level change is visible rather than hidden.

  C  nu 2.709 + point estimate   (current best)
  E  nu 2.709 + mixture
  F  nu 3.087 + mixture          (the honest conditional nu, which the mixture
                                  should now let work -- 2.709 was a stand-in
                                  for exactly this unmodelled scale variation)
"""
import sys, time, warnings
sys.path.insert(0,"/Users/elvisobondo/Pair_Trading/research")
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
KR,KD,QL,QX,R,QRD,QDR = 0.0850,-0.0200,0.4880,0.4750,0.0980,0.0379,0.0912
HOR,NS,CH,STRIDE = 20,2000,600,40
T=np.array([[1-QRD,QRD],[QDR,1-QDR]])
D="/private/tmp/claude-501/-Users-elvisobondo-Pair-Trading/0189ea06-e901-4d24-83ff-b7b3c5ca8f65/scratchpad/disloc"
z=np.load(D+".npz"); W=z["windows"].astype(float); Y=z["outcomes"].astype(float)
M=pd.read_parquet(D+"_meta.parquet"); day=M.day.to_numpy()
tr=day<np.datetime64("2026-07-18"); te=~tr
dW=np.diff(W,axis=1); dF=np.diff(Y,axis=1)
LOG=lambda x: np.log(np.maximum(x,1e-12))
PRE=np.column_stack([LOG((dW[:,-k:]**2).mean(1)) for k in (48,96,335)])
rvPost=2*LOG(np.abs(dF).mean(1))                     # absolute-return target
A=np.column_stack([np.ones(tr.sum()),PRE[tr]])
cf=np.linalg.lstsq(A,rvPost[tr],rcond=None)[0]
pred=np.column_stack([np.ones(len(W)),PRE])@cf
resid=rvPost[tr]-pred[tr]; RV=resid.var(); SD=np.sqrt(RV)
base=np.log(np.mean(np.exp(pred[tr])))
mult=np.exp(pred-base)
y=rvPost[te]; pp=pred[te]
print(f"[v_0] held-out R2 {1-((y-pp)**2).sum()/((y-y.mean())**2).sum():.4f}")
print(f"[v_0] fit-period residual variance {RV:.3f} -> log-sd {SD:.3f}, "
      f"multiplier spread exp(+/-sd) = {np.exp(SD):.2f}x either way")
print(f"[v_0] Jensen factor exp(var/2) = {np.exp(RV/2):.2f}x -- the mixture's mean "
      f"variance is that much above the point estimate's\n")

Wte,Yte=W[te],Y[te]; m=mult[te]; n=te.sum(); dte=day[te]
a=Yte[:,HOR]; y0=Yte[:,0]; chg=a-y0
CE=y0[:,None]+np.random.default_rng(11).choice(chg-chg.mean(),size=(n,200),replace=True)
def crps(E,yy):
    q=E.shape[1]; t1=np.abs(E-yy[:,None]).mean(1)
    Es=np.sort(E,1); j=np.arange(1,q+1)
    return t1-0.5*(2.0/q**2)*((2*j-q-1)*Es).sum(1)
CL=crps(CE,a).mean()
realq=np.abs(dF[te])

def filt(Y_,qL,qX,r):
    nn_,Tn=Y_.shape; ks=[KR,KD]
    L=[np.zeros(nn_),np.zeros(nn_)]; X=[np.zeros(nn_),np.zeros(nn_)]
    PLL=[np.full(nn_,10.0),np.full(nn_,10.0)]; PLX=[np.zeros(nn_),np.zeros(nn_)]
    PXX=[np.ones(nn_),np.ones(nn_)]
    pr=T[1,0]/(T[0,1]+T[1,0]); p=[np.full(nn_,pr),np.full(nn_,1-pr)]
    for t in range(Tn):
        yy=Y_[:,t]; bl={}
        for i in range(2):
            for j in range(2):
                dd=1.0-ks[j]; Xp=X[i]*dd; Lp=L[i]
                Aa=PLL[i]+qL; B=PLX[i]*dd; C=PXX[i]*dd*dd+qX
                Sv=Aa+2*B+C+r; v=yy-(Lp+Xp)
                HL=Aa+B; HX=B+C; KL=HL/Sv; KX=HX/Sv
                bl[(i,j)]=dict(L=Lp+KL*v,X=Xp+KX*v,PLL=Aa-KL*HL,PLX=B-KL*HX,PXX=C-KX*HX,
                               w=p[i]*T[i,j]*np.exp(-0.5*(v*v/Sv))/np.sqrt(2*np.pi*Sv))
        tot=np.maximum(sum(bl[(i,j)]["w"] for i in range(2) for j in range(2)),1e-300)
        nw=[sum(bl[(i,j)]["w"] for i in range(2)) for j in range(2)]
        for j in range(2):
            pj=np.maximum(nw[j],1e-300)
            Lj=sum(bl[(i,j)]["w"]*bl[(i,j)]["L"] for i in range(2))/pj
            Xj=sum(bl[(i,j)]["w"]*bl[(i,j)]["X"] for i in range(2))/pj
            PLLj=sum(bl[(i,j)]["w"]*(bl[(i,j)]["PLL"]+(bl[(i,j)]["L"]-Lj)**2) for i in range(2))/pj
            PXXj=sum(bl[(i,j)]["w"]*(bl[(i,j)]["PXX"]+(bl[(i,j)]["X"]-Xj)**2) for i in range(2))/pj
            PLXj=sum(bl[(i,j)]["w"]*(bl[(i,j)]["PLX"]+(bl[(i,j)]["L"]-Lj)*(bl[(i,j)]["X"]-Xj)) for i in range(2))/pj
            L[j],X[j],PLL[j],PLX[j],PXX[j]=Lj,Xj,PLLj,PLXj,PXXj
            p[j]=pj/tot
    return L,X,p
L,X,p=filt(Wte,QL*m,QX*m,R*m)          # filter always on the point estimate

def run(nu,mix):
    ERR={1:np.empty(n),HOR:np.empty(n)}; SDv={1:np.empty(n),HOR:np.empty(n)}
    outs=np.empty(n,bool); cm=np.empty(n); keep=[]; mm=[]
    for lo in range(0,n,CH):
        hi=min(lo+CH,n); k=hi-lo; sl=slice(lo,hi); rng=np.random.default_rng(1000+lo)
        mi=np.repeat(m[sl][:,None],NS,1)
        if mix: mi=mi*np.exp(rng.normal(0,SD,(k,NS)))
        mi=mi.astype(np.float32); mm.append(mi.mean())
        vL,vX,vR=QL*mi,QX*mi,R*mi
        dr=lambda v:(rng.standard_t(nu,(k,NS))*np.sqrt(v*(nu-2)/nu)).astype(np.float32)
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
def ci(ind,sub=None):
    out=np.empty(len(BOOT))
    for i,pick in enumerate(BOOT):
        idx=np.concatenate([pos[d] for d in pick])
        if sub is not None: idx=idx[np.isin(idx,sub)]
        out[i]=100*ind[idx].mean() if len(idx) else np.nan
    return np.nanpercentile(out,2.5),np.nanpercentile(out,97.5)

decR=pd.qcut(rvPost[te],10,labels=False); decP=pd.qcut(m,10,labels=False)
RES={}
print("="*104)
print(f"{'cfg':<28}{'mean m':>8}{'outside':>9}{'95% CI':>16}{'band .5h':>10}{'band 10h':>10}"
      f"{'cov 10h':>9}{'D10 cov':>9}{'D10 out':>9}{'CRPS':>8}")
for tag,nu,mix in (("C  nu 2.709 + point",2.709,False),("E  nu 2.709 + MIXTURE",2.709,True),
                   ("F  nu 3.087 + MIXTURE",3.087,True)):
    t0=time.time(); ERR,SDv,outs,cm,md,mbar=run(nu,mix)
    s10=np.flatnonzero(decR==9)
    o=100*outs.mean(); lo_,hi_=ci(outs)
    b1=np.std(ERR[1])/SDv[1].mean(); b2=np.std(ERR[HOR])/SDv[HOR].mean()
    c2=100*np.mean(np.abs(ERR[HOR]/SDv[HOR])<=1.645)
    d10c=100*np.mean(np.abs(ERR[HOR][s10]/SDv[HOR][s10])<=1.645); d10o=100*outs[s10].mean()
    RES[tag]=(ERR,SDv,outs,md)
    print(f"{tag:<28}{mbar:>8.2f}{o:>8.2f}%  [{lo_:>5.2f},{hi_:>5.2f}]{b1:>10.2f}{b2:>10.2f}"
          f"{c2:>8.1f}%{d10c:>8.1f}%{d10o:>8.2f}%{100*cm.mean()/CL:>7.1f}%",flush=True)

best=max(RES,key=lambda t:-abs(RES[t][2].mean()*100-0.0999)) if False else None
for tag in RES:
    ERR,SDv,outs,md=RES[tag]
    print(f"\n{'='*104}\n{tag} -- matched quantiles\n{'='*104}")
    for q,l in zip((50,90,99,99.9),("median","1 in 10","1 in 100","1 in 1,000")):
        print(f"  {l:<12}{np.percentile(md,q):>8.2f}{np.percentile(realq,q):>8.2f}"
              f"{np.percentile(md,q)/np.percentile(realq,q):>8.2f}x")
    for nm,dec in (("PREDICTED",decP),("REALISED (diagnostic)",decR)):
        print(f"  by {nm}: ", end="")
        cov=[100*np.mean(np.abs(ERR[HOR][dec==b]/SDv[HOR][dec==b])<=1.645) for b in range(10)]
        ou=[100*outs[dec==b].mean() for b in range(10)]
        print("cov10h "+" ".join(f"{v:.0f}" for v in cov)+f"  | spread {max(cov)-min(cov):.1f}pp"
              f"  | outside D1 {ou[0]:.2f}% D10 {ou[9]:.2f}%")
