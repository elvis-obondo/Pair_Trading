"""Where is the remaining miscalibration, and is it reachable?

Configuration C (nu = 2.709 unconditional + v_0), 2,000 draws, held out.
Bucket by volatility two ways; the GAP between them is the prize available from
better volatility forecasting of any kind, the 1-minute build included.

  PREDICTED  (the v_0 multiplier)        -- a real forecast
  REALISED   (post-entry realised vol)   -- uses future information, a
                                            DIAGNOSTIC and not a forecast

Flat coverage across predicted deciles => v_0 is adequate for what it predicts.
Flat across REALISED deciles => heterogeneity is not what is left, and the
1-minute build will not find it.

The 'largest move' row now carries its sample-size correction inline. Model
moves outnumber real ones 50x here, and the max of a fat-tailed sample grows as
n^(1/nu), so the raw ratio has pointed the wrong way twice. Corrected =
observed / (n_model/n_real)^(1/nu).
"""
import sys, time, warnings
sys.path.insert(0,"/Users/elvisobondo/Pair_Trading/research")
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")

KR,KD,QL,QX,R,QRD,QDR = 0.0850,-0.0200,0.4880,0.4750,0.0980,0.0379,0.0912
NU,HOR,NS,CH,STRIDE = 2.709,20,2000,600,40
T=np.array([[1-QRD,QRD],[QDR,1-QDR]])
D="/private/tmp/claude-501/-Users-elvisobondo-Pair-Trading/0189ea06-e901-4d24-83ff-b7b3c5ca8f65/scratchpad/disloc"
z=np.load(D+".npz"); W=z["windows"].astype(float); Y=z["outcomes"].astype(float)
M=pd.read_parquet(D+"_meta.parquet"); day=M.day.to_numpy()
tr=day<np.datetime64("2026-07-18"); te=~tr
dW=np.diff(W,axis=1); dF=np.diff(Y,axis=1)
PRE=np.column_stack([np.log(np.maximum((dW[:,-k:]**2).mean(1),1e-12)) for k in (48,96,335)])
rvPost=2*np.log(np.maximum(np.abs(dF).mean(1),1e-12))  # ABSOLUTE-return target: less noisy at n=20
A=np.column_stack([np.ones(tr.sum()),PRE[tr]])
c=np.linalg.lstsq(A,rvPost[tr],rcond=None)[0]
pred=np.column_stack([np.ones(len(W)),PRE])@c
mult=np.exp(pred-np.log(np.mean(np.exp(pred[tr]))))
Wte,Yte=W[te],Y[te]; m=mult[te]; n=te.sum(); dte=day[te]
qL,qX,r=QL*m,QX*m,R*m

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

t0=time.time(); L,X,p=filt(Wte,qL,qX,r)
ERR={1:np.empty(n),HOR:np.empty(n)}; SD={1:np.empty(n),HOR:np.empty(n)}
outs=np.empty(n,bool); keep=[]
for lo in range(0,n,CH):
    hi=min(lo+CH,n); k=hi-lo; sl=slice(lo,hi); rng=np.random.default_rng(1000+lo)
    def dr(var): return (rng.standard_t(NU,(k,NS))*np.sqrt(var[sl]*(NU-2)/NU)[:,None]).astype(np.float32)
    reg=(rng.random((k,NS))>p[0][sl][:,None]).astype(np.int8)
    Ls=np.where(reg==0,L[0][sl][:,None],L[1][sl][:,None]).astype(np.float32)
    Xs=np.where(reg==0,X[0][sl][:,None],X[1][sl][:,None]).astype(np.float32)
    prev=Ls+Xs+dr(r); ds=[]
    for s_ in range(1,HOR+1):
        sw=rng.random((k,NS)); stay=np.where(reg==0,1-T[0,1],1-T[1,0])
        reg=np.where(sw<stay,reg,1-reg)
        Ls=Ls+dr(qL); kk=np.where(reg==0,KR,KD).astype(np.float32); Xs=Xs*(1-kk)+dr(qX)
        cur=Ls+Xs+dr(r); ds.append(np.abs(cur-prev)[:,::STRIDE])
        if s_ in (1,HOR):
            ERR[s_][sl]=Yte[sl,s_]-cur.mean(1); SD[s_][sl]=cur.std(1)
        prev=cur
    rk=(cur<Yte[sl,HOR][:,None]).mean(1)
    outs[sl]=(rk<=1.0/NS)|(rk>=1-1.0/NS); keep.append(np.concatenate(ds).ravel())
md=np.concatenate(keep)
print(f"[C] nu {NU} + v_0, {NS} draws, {time.time()-t0:.0f}s\n")

real=np.abs(dF[te]); nr=real.size; nm=md.size
print(f"{'move size':<12}{'model':>9}{'real':>9}{'raw':>8}{'corrected':>11}")
for q,l in zip((50,90,99,99.9),("median","1 in 10","1 in 100","1 in 1,000")):
    a_,b_=np.percentile(md,q),np.percentile(real,q)
    print(f"{l:<12}{a_:>9.2f}{b_:>9.2f}{a_/b_:>7.2f}x{'  (matched)':>11}")
corr=(nm/nr)**(1.0/NU)
print(f"{'largest':<12}{md.max():>9.2f}{real.max():>9.2f}{md.max()/real.max():>7.2f}x"
      f"{md.max()/real.max()/corr:>10.2f}x")
print(f"   n_model {nm:,} vs n_real {nr:,} = {nm/nr:.0f}x  ->  expected growth "
      f"{corr:.2f}x at nu={NU}; the corrected figure is the one to read\n")

du=np.unique(dte); pos={d:np.flatnonzero(dte==d) for d in du}
rb=np.random.default_rng(5); BOOT=[rb.choice(du,len(du),replace=True) for _ in range(300)]
def rows(key,label,note):
    dec=pd.qcut(key,10,labels=False)
    print("="*96); print(f"{label}   {note}"); print("="*96)
    print(f"{'decile':>7}{'n':>7}{'cover 0.5h':>12}{'cover 10h':>11}{'band 0.5h':>11}"
          f"{'band 10h':>10}{'outside':>9}{'95% day-clustered':>20}")
    for b in range(10):
        s=np.flatnonzero(dec==b)
        c1=100*np.mean(np.abs(ERR[1][s]/SD[1][s])<=1.645)
        c2=100*np.mean(np.abs(ERR[HOR][s]/SD[HOR][s])<=1.645)
        b1=np.std(ERR[1][s])/SD[1][s].mean(); b2=np.std(ERR[HOR][s])/SD[HOR][s].mean()
        o=100*outs[s].mean()
        bs=np.empty(len(BOOT)); sset=set(s.tolist())
        for i,pick in enumerate(BOOT):
            idx=np.concatenate([pos[d] for d in pick])
            idx=idx[np.isin(idx,s)]
            bs[i]=100*outs[idx].mean() if len(idx) else np.nan
        print(f"{b+1:>7}{len(s):>7}{c1:>11.1f}%{c2:>10.1f}%{b1:>11.2f}{b2:>10.2f}"
              f"{o:>8.2f}%   [{np.nanpercentile(bs,2.5):>5.2f}, {np.nanpercentile(bs,97.5):>5.2f}]")
    print(f"  spread across deciles: cover 10h "
          f"{max(100*np.mean(np.abs(ERR[HOR][dec==b]/SD[HOR][dec==b])<=1.645) for b in range(10)) - min(100*np.mean(np.abs(ERR[HOR][dec==b]/SD[HOR][dec==b])<=1.645) for b in range(10)):.1f}pp,"
          f"  outside {max(100*outs[dec==b].mean() for b in range(10)) - min(100*outs[dec==b].mean() for b in range(10)):.2f}pp\n",flush=True)

rows(m,"BY PREDICTED VOLATILITY (the v_0 multiplier)","a real forecast")
rows(rvPost[te],"BY REALISED POST-ENTRY VOLATILITY","DIAGNOSTIC -- uses future information, not a forecast")
