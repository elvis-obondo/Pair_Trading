"""2a -- three model-free tests before any 1-minute build. Held out, 2026-07-18.

i   does volatility cluster inside the window at all
ii  does pre-entry volatility predict post-entry volatility   <- the gate, 5%
iii the selection artifact: how much elevation is our own entry rule
"""
import sys, time
sys.path.insert(0,"/Users/elvisobondo/Pair_Trading/research")
import numpy as np, pandas as pd
import universe_panel, rolling_spread as rs

D="/private/tmp/claude-501/-Users-elvisobondo-Pair-Trading/0189ea06-e901-4d24-83ff-b7b3c5ca8f65/scratchpad/disloc"
z=np.load(D+".npz"); W=z["windows"].astype(float); Y=z["outcomes"].astype(float)
M=pd.read_parquet(D+"_meta.parquet"); day=M.day.to_numpy()
CUT=np.datetime64("2026-07-18"); tr=day<CUT; te=~tr
dte=np.sort(np.unique(day[te]))
print(f"[SPLIT] fit {tr.sum():,}  held out {te.sum():,} over {len(dte)} days\n")

dF=np.diff(Y,axis=1)            # (n,20) forecast-window increments
dW=np.diff(W,axis=1)            # (n,335) entry-window increments

def dayci(stat,idx,B=300,seed=5):
    """day-clustered interval on a statistic computed from row indices"""
    dd=day[idx]; du=np.unique(dd); pos={x:idx[dd==x] for x in du}
    rb=np.random.default_rng(seed); out=np.empty(B)
    for i in range(B):
        out[i]=stat(np.concatenate([pos[x] for x in rb.choice(du,len(du),replace=True)]))
    return np.percentile(out,2.5),np.percentile(out,97.5)

# ---------------- 2a-i ----------------
print("="*94); print("2a-i  does volatility cluster inside the window?"); print("="*94)
def acf(X,lags,demean_row):
    A=X.copy()
    if demean_row: A=A-A.mean(1,keepdims=True)
    out=[]
    for L in lags:
        a=A[:,:-L].ravel(); b=A[:,L:].ravel()
        out.append(np.corrcoef(a,b)[0,1])
    return np.array(out)
LAGS=list(range(1,11))
ix=np.flatnonzero(te)
for nm,X in (("forecast window, 20 steps",dF[te]),("entry window, 335 steps",dW[te])):
    sq=X**2; ab=np.abs(X)
    print(f"\n  {nm}")
    print(f"    {'lag':>4}" + "".join(f"{l:>7}" for l in LAGS))
    for lab,A,dm in (("sq pooled",sq,False),("sq within",sq,True),
                     ("|d| pooled",ab,False),("|d| within",ab,True)):
        v=acf(A,LAGS,dm)
        print(f"    {lab:<11}" + "".join(f"{x:>7.3f}" for x in v))
    lo,hi=dayci(lambda s: acf((np.abs(dF[s]) if 'forecast' in nm else np.abs(dW[s])),[1],False)[0], ix)
    print(f"    |d| pooled lag-1 day-clustered 95%: [{lo:+.3f}, {hi:+.3f}]")

# ---------------- 2a-ii ----------------
print("\n"+"="*94); print("2a-ii  does pre-entry volatility predict post-entry volatility?"); print("="*94)
rvPost=np.log(np.maximum((dF**2).mean(1),1e-12))
PRE={k:np.log(np.maximum((dW[:,-k:]**2).mean(1),1e-12)) for k in (48,96,335)}
def fitscore(cols):
    A=np.column_stack([np.ones(tr.sum())]+[PRE[k][tr] for k in cols])
    c=np.linalg.lstsq(A,rvPost[tr],rcond=None)[0]
    p=np.column_stack([np.ones(te.sum())]+[PRE[k][te] for k in cols])@c
    y=rvPost[te]
    return 1-((y-p)**2).sum()/((y-y.mean())**2).sum(), p, c
print(f"  target: log post-entry realised variance over the 20 forecast steps")
print(f"  {'predictor':<28}{'held-out R2':>13}{'95% CI (day-clustered)':>26}")
for cols,nm in (([48],"log RV last 48 bars"),([96],"log RV last 96 bars"),
                ([335],"log RV all 335 bars"),([48,96,335],"all three together")):
    r2,p,c=fitscore(cols)
    pm={k:v for k,v in zip(cols,[PRE[k] for k in cols])}
    def st(s):
        A=np.column_stack([np.ones(len(s))]+[PRE[k][s] for k in cols])
        cc=np.linalg.lstsq(A,rvPost[s],rcond=None)[0]
        q=np.column_stack([np.ones(te.sum())]+[PRE[k][te] for k in cols])@cc
        y=rvPost[te]; return 1-((y-q)**2).sum()/((y-y.mean())**2).sum()
    lo,hi=dayci(st,np.flatnonzero(tr),B=120)
    print(f"  {nm:<28}{100*r2:>12.2f}%     [{100*lo:>6.2f}%, {100*hi:>6.2f}%]")
r2all,_,call=fitscore([48,96,335])
print(f"\n  GATE: proceed to the 1-minute build only if this is above 5%  ->  "
      f"{100*r2all:.2f}%  {'PASS' if r2all>0.05 else 'FAIL'}")

# ---------------- 2a-iii ----------------
print("\n"+"="*94); print("2a-iii  selection artifact: how much elevation is our own entry rule?"); print("="*94)
def forward_rv(v,i,sg):
    d=np.diff(v[i:i+21])/sg
    return np.log(max((d**2).mean(),1e-12))

panel=universe_panel.drop_forming_bars(universe_panel.load_panel())
idx=pd.to_datetime(panel.index); V=panel.to_numpy(float); cols=list(panel.columns)
ixc={c:j for j,c in enumerate(cols)}
ok=np.isfinite(V); first=np.array([ok[:,j].argmax() for j in range(V.shape[1])])
lo_t=idx.searchsorted(pd.Timestamp(CUT))
Mte=M[te].reset_index(drop=True)
pairs=Mte[["ticker_a","ticker_b"]].drop_duplicates().values
rng=np.random.default_rng(3); ctrl=[]
t0=time.time()
for a,b in pairs:
    ja,jb=ixc[a],ixc[b]; f=max(first[ja],first[jb])
    if len(V)-f < 400: continue
    r=rs.rolling_spread_stats(V[f:,ja],V[f:,jb],0.5)
    zz=r.z; sp=r.spread
    good=np.isfinite(zz)&np.isfinite(r.sigma)&(r.sigma>0)
    lo_i=max(lo_t-f,336)
    cand=np.flatnonzero(good)&0
    cand=np.flatnonzero(good)
    cand=cand[(cand>=lo_i)&(cand+20<=len(zz)-1)&(np.abs(zz[cand])<3.0)]
    if len(cand)==0: continue
    for i in rng.choice(cand,min(5,len(cand)),replace=False):
        ctrl.append(forward_rv(sp,i,r.sigma[i]))
ctrl=np.array(ctrl)
print(f"  {len(pairs)} held-out pairs -> {len(ctrl):,} control bars (|z|<3, same pairs, same period), {time.time()-t0:.0f}s")

# constant-volatility synthetic: the pure selection artifact
ns,T_=3000,3000
S=np.cumsum(np.random.default_rng(9).normal(0,1,(ns,T_)),axis=1)
sd_,sc_=[],[]
for i in range(ns):
    s=pd.Series(S[i]); mu=s.rolling(96).mean().to_numpy(); sg=s.rolling(96).std().to_numpy()
    v=s.to_numpy()
    with np.errstate(invalid="ignore"): zz=np.where(sg>0,(v-mu)/sg,np.nan)
    g=np.isfinite(zz)
    h=np.zeros(len(zz),bool); h[1:]=g[1:]&g[:-1]&(np.abs(zz[1:])>=3)&(np.abs(zz[:-1])<3)
    c=np.flatnonzero(h); c=c[(c>=336)&(c+20<=len(zz)-1)]
    for i2 in c[:2]: sd_.append(forward_rv(v,i2,sg[i2]))
    cc=np.flatnonzero(g); cc=cc[(cc>=336)&(cc+20<=len(zz)-1)&(np.abs(zz[cc])<3)]
    if len(cc): 
        for i2 in np.random.default_rng(i).choice(cc,min(2,len(cc)),replace=False):
            sc_.append(forward_rv(v,i2,sg[i2]))
sd_,sc_=np.array(sd_),np.array(sc_)

rdis=rvPost[te]
print(f"\n  {'':<34}{'dislocation':>13}{'control':>10}{'elevation':>11}")
print(f"  {'REAL  log post-entry RV (mean)':<34}{rdis.mean():>13.3f}{ctrl.mean():>10.3f}"
      f"{rdis.mean()-ctrl.mean():>11.3f}")
print(f"  {'SYNTHETIC constant vol':<34}{sd_.mean():>13.3f}{sc_.mean():>10.3f}"
      f"{sd_.mean()-sc_.mean():>11.3f}")
real_el=rdis.mean()-ctrl.mean(); sel_el=sd_.mean()-sc_.mean()
print(f"\n  total elevation {real_el:.3f} log-var = {np.exp(real_el):.2f}x variance")
print(f"  of which the 3-sigma entry rule alone explains {sel_el:.3f} = {np.exp(sel_el):.2f}x")
print(f"  REMAINDER for xi and eta: {real_el-sel_el:+.3f} log-var = {np.exp(real_el-sel_el):.2f}x variance")
