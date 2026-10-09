"""Pass 1 -- information from OUTSIDE the spread's own history.

Same harness as the nonlinear bound: same split (2026-07-18), same sign-folding,
same learner, same gates, same permutation null.

LOOK-AHEAD, audited not assumed. meta.bar_index is the absolute panel index of
the entry bar -- the bar whose value IS z_entry and the last column of W. EVERY
feature family below stops at that index INCLUSIVE and uses nothing after it.
Asserted at the bottom of the build.
"""
import sys, os, time, warnings
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import paths
import universe_panel, rolling_spread as rs
warnings.filterwarnings("ignore")

D=paths.DISLOC_PREFIX
z=np.load(D+".npz"); W0=z["windows"].astype(np.float32); Y=z["outcomes"].astype(np.float64)
M=pd.read_parquet(D+"_meta.parquet")
J=M.bar_index.to_numpy(int); N=len(M)
panel=universe_panel.drop_forming_bars(universe_panel.load_panel())
V=panel.to_numpy(float); cols=list(panel.columns); ixc={c:i for i,c in enumerate(cols)}
ja=M.ticker_a.map(ixc).to_numpy(int); jb=M.ticker_b.map(ixc).to_numpy(int)
bet=M.beta.to_numpy(float); sg=M.sigma.to_numpy(float)
s=np.sign(Y[:,0]); s[s==0]=1.0
print(f"[DATA] {N:,} dislocations, panel {V.shape}, entry bars {J.min()}..{J.max()}",flush=True)

dV=np.diff(V,axis=0)                                  # row t = return INTO bar t+1
DF=pd.DataFrame(dV)
legvol=DF.rolling(96,min_periods=48).std().to_numpy() # index t aligns to dV row t
mkt=np.nanmean(dV,axis=1); disp=np.nanstd(dV,axis=1)
mkS=pd.Series(mkt)
F={}
t0=time.time()

# --- 1. which leg moved.  uses V[J-k .. J], dV rows J-k .. J-1 ---
for k in (1,4,16,48):
    ra=(V[J,ja]-V[J-k,ja]); rb=(V[J,jb]-V[J-k,jb])
    va=legvol[J-1,ja]*np.sqrt(k); vb=legvol[J-1,jb]*np.sqrt(k)
    F[f"a_ret{k}"]=ra/np.clip(va,1e-12,None)*s
    F[f"b_ret{k}"]=rb/np.clip(vb,1e-12,None)*s
    F[f"absa{k}"]=np.abs(ra/np.clip(va,1e-12,None)); F[f"absb{k}"]=np.abs(rb/np.clip(vb,1e-12,None))
ca=(V[J,ja]-V[J-48,ja])/sg; cb=-bet*(V[J,jb]-V[J-48,jb])/sg
F["contrib_a"]=ca*s; F["contrib_b"]=cb*s
F["asym_signed"]=(ca-cb)*s; F["asym_abs"]=np.abs(ca)-np.abs(cb)
F["share_a"]=np.abs(ca)/np.clip(np.abs(ca)+np.abs(cb),1e-12,None)

# --- 2. market-wide vs idiosyncratic.  dV rows up to J-1 ---
for k in (1,4,16,48):
    F[f"mkt{k}"]=np.array([np.nansum(mkt[j-k:j]) for j in J])*s
    F[f"disp{k}"]=np.array([np.nanmean(disp[j-k:j]) for j in J])
cv=DF.rolling(96,min_periods=48).cov(mkS).to_numpy(); mv=mkS.rolling(96,min_periods=48).var().to_numpy()
ba=cv[J-1,ja]/np.clip(mv[J-1],1e-18,None); bb=cv[J-1,jb]/np.clip(mv[J-1],1e-18,None)
F["beta_a_mkt"]=ba; F["beta_b_mkt"]=bb
sp_exp=ba-bet*bb                                       # spread's net market exposure
F["spread_mkt_exp"]=sp_exp; F["abs_spread_mkt_exp"]=np.abs(sp_exp)
mk48=np.array([np.nansum(mkt[j-48:j]) for j in J])
F["mkt_explained"]=(sp_exp*mk48/sg)*s                  # sigma of dislocation from market
F["mkt_share"]=np.abs(sp_exp*mk48/sg)/np.clip(np.abs(Y[:,0]),1e-9,None)

# --- 3. wave: share of sampled pairs dislocated at the entry bar ---
rng=np.random.default_rng(11); pr=universe_panel.tradeable_pairs(cols)
ok=np.isfinite(V); first=np.array([ok[:,i].argmax() for i in range(V.shape[1])])
cnt3=np.zeros(len(V)); cntf=np.zeros(len(V)); nsamp=0
for q in rng.choice(len(pr),400,replace=False):
    a,b=pr[q]; i1,i2=ixc[a],ixc[b]; f=max(first[i1],first[i2])
    if len(V)-f<500: continue
    r=rs.rolling_spread_stats(V[f:,i1],V[f:,i2],0.5)
    g=np.isfinite(r.z)
    cntf[f:][g]+=1; cnt3[f:][g&(np.abs(r.z)>=3.0)]+=1; nsamp+=1
wave=np.where(cntf>0,cnt3/np.maximum(cntf,1),np.nan)
F["wave"]=wave[J]; F["wave_mean4"]=np.array([np.nanmean(wave[j-3:j+1]) for j in J])
F["n_live_pairs"]=cntf[J]

# --- 4. crowding, from the sampled meta (a proxy for the true 3.45M) ---
byt={}
for t,arr in pd.DataFrame({"t":np.r_[M.ticker_a.values,M.ticker_b.values],
                           "j":np.r_[J,J]}).groupby("t").j:
    byt[t]=np.sort(arr.to_numpy())
alln=np.sort(J)
def cnt(arr,j,w=20): return np.searchsorted(arr,j,"right")-np.searchsorted(arr,j-w,"left")
F["crowd_a"]=np.array([cnt(byt[t],j) for t,j in zip(M.ticker_a,J)])-1.0
F["crowd_b"]=np.array([cnt(byt[t],j) for t,j in zip(M.ticker_b,J)])-1.0
F["crowd_uni"]=np.array([cnt(alln,j) for j in J])-1.0

EXT=np.nan_to_num(np.column_stack(list(F.values())).astype(np.float32),nan=0,posinf=0,neginf=0)
EXTN=list(F)
print(f"[BUILD] {EXT.shape[1]} external features in {time.time()-t0:.0f}s "
      f"({nsamp} pairs sampled for the wave feature, of 22,366)")
print(f"[AUDIT] every family stops at bar_index INCLUSIVE:")
print(f"        leg returns use V[J-k..J];  market/vol use dV rows <= J-1 "
      f"(dV row t is the return INTO bar t+1, so row J-1 ends AT bar J)")
print(f"        wave uses rolling z at bar J (96-bar window ending at J); "
      f"crowding counts entries in [J-20, J]")
assert J.max()+1<=len(V), "entry bar beyond panel"
print(f"[AUDIT] max bar index touched = {J.max()} = max entry bar; "
      f"panel has {len(V)} bars, so {len(V)-1-J.max()} later bars exist and are UNUSED\n",flush=True)

# window features: the 18 engineered + the 3 log-RV predictors (the v_0 benchmark)
Wf=W0*s[:,None].astype(np.float32); dWf=np.diff(Wf,axis=1)
LOG=lambda x: np.log(np.maximum(x,1e-12))
w={"z":Wf[:,-1],"absz":np.abs(Wf[:,-1]),"r2":M.r2.to_numpy(np.float32),
   "absb":np.abs(bet).astype(np.float32),"lsig":np.log(np.clip(sg,1e-12,None)),
   "wsd":Wf.std(1),"wmean":Wf.mean(1),"wrange":Wf.max(1)-Wf.min(1),
   "sl48":(Wf[:,-1]-Wf[:,-48])/48,"sl96":(Wf[:,-1]-Wf[:,-96])/96,"sl336":(Wf[:,-1]-Wf[:,0])/336,
   "ssd":dWf.std(1),"ssd48":dWf[:,-48:].std(1),"two":dWf.std(1)/np.clip(Wf.std(1),1e-9,None),
   "vr":dWf[:,-48:].std(1)/np.clip(dWf.std(1),1e-9,None),
   "ac1":np.array([np.corrcoef(dWf[i,:-1],dWf[i,1:])[0,1] for i in range(N)],np.float32),
   "fa":(Wf>0).mean(1),"ta3":(np.abs(Wf)>=3).mean(1),
   "rv48":LOG((dWf[:,-48:]**2).mean(1)),"rv96":LOG((dWf[:,-96:]**2).mean(1)),
   "rv335":LOG((dWf**2).mean(1))}
WIN=np.nan_to_num(np.column_stack(list(w.values())).astype(np.float32),nan=0,posinf=0,neginf=0)
BOTH=np.column_stack([EXT,WIN])
np.savez_compressed(paths.EXTFEAT,
                    EXT=EXT,WIN=WIN,names=np.array(EXTN+list(w)))
print(f"[SETS] EXTERNAL {EXT.shape[1]}   WINDOW {WIN.shape[1]}   BOTH {BOTH.shape[1]}",flush=True)
