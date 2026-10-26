"""What the 95% gate demands of the centre, done properly.

A centre is a predictor of the 10-hour CHANGE with correlation rho to it.
Optimally scaled, it leaves residual sd = sd*sqrt(1-rho^2), so the forecast's
R2 is rho^2. Build such a centre for a grid of rho, score it, read off the
rho^2 that reaches 95%. Then measure the model centre's real rho^2.
"""
import sys
sys.path.insert(0,"/Users/elvisobondo/Pair_Trading/research")
import numpy as np, pandas as pd
import universe_panel

BARS, STEPS = 336, 20
R="/Users/elvisobondo/Pair_Trading/research/exit_study/"
m=pd.read_parquet(R+"paths_meta.parquet"); S=np.load(R+"paths.npz")["spreads"]
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
W=np.array(W); keep=np.array(keep); N=len(keep); y0=W[:,-1]

def crps(E,y):
    NS=E.shape[1]; t1=np.abs(E-y[:,None]).mean(1)
    Es=np.sort(E,1); j=np.arange(1,NS+1)
    return t1-0.5*(2.0/NS**2)*((2*j-NS-1)*Es).sum(1)
def actual(s_):
    okh=(s_*30<ln[keep])
    a=np.where(okh,(S[np.clip(st[keep]+s_*30,0,len(S)-1)]-mu[keep])/sg[keep],np.nan)
    return a,np.isfinite(a)

rng=np.random.default_rng(11)
for s_ in (1,20):
    a,gd=actual(s_); chg=(a-y0)[gd]; n=gd.sum(); sd=chg.std()
    ce=y0[gd][:,None]+rng.choice(chg-chg.mean(),size=(n,200),replace=True)
    cl=crps(ce,a[gd]).mean()
    print(f"\n--- {s_*0.5:.1f}h  climatology CRPS {cl:.3f} sigma  change sd {sd:.3f}  n {n} ---")
    print(f"{'R2 of centre':>13} {'resid sd':>9} {'CRPS':>8} {'% of clim':>10}")
    z=(chg-chg.mean())/sd
    for r2 in (0.0,0.01,0.02,0.05,0.0975,0.15,0.25,0.50,1.0):
        rho=np.sqrt(r2)
        u=rng.standard_normal(n); sig=rho*z+np.sqrt(1-r2)*u
        # optimally scaled predictor of chg from sig
        b=np.cov(chg,sig)[0,1]/np.var(sig) if r2>0 else 0.0
        ctr=y0[gd]+chg.mean()+b*(sig-sig.mean())
        res=chg-(chg.mean()+b*(sig-sig.mean()))
        E=ctr[:,None]+rng.choice(res-res.mean(),size=(n,200),replace=True)
        c=crps(E,a[gd]).mean()
        print(f"{r2*100:>12.2f}% {res.std():>9.3f} {c:>8.3f} {100*c/cl:>9.1f}%")
