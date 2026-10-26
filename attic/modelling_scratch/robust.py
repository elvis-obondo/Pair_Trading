"""v_0 with a robust volatility estimator, and the measurement-error ceiling.

Squared returns are a pathological variance estimator under nu = 2.709 -- the
fourth moment barely exists. |d| and bipower are not. 2a-i already showed this
once (|d| lag-1 ACF 0.283 against d^2's 0.109) and it was never carried across
to the v_0 predictor.

A. verify the estimator-noise table by simulation (not taken on faith)
B. re-fit v_0 with 2*log mean|d| and with bipower variation
C. attenuation ceiling -- what R2 a 1-minute-precision estimator would reach
"""
import sys, warnings
sys.path.insert(0,"/Users/elvisobondo/Pair_Trading/research")
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
NU=2.709; MU1=np.sqrt(2/np.pi)

# ---------------- A ----------------
print("="*86); print("A  sd of the log-variance estimate, simulated from t(2.709), unit variance")
print("="*86)
rg=np.random.default_rng(1); REP=20000
print(f"{'observations':>13}{'squared':>11}{'absolute':>11}{'bipower':>10}{'abs/sq':>9}")
NOISE={}
for nn in (20,48,96,335,1440):
    d=rg.standard_t(NU,(REP,nn))*np.sqrt((NU-2)/NU)
    sq=np.log(np.maximum((d**2).mean(1),1e-30))
    ab=2*np.log(np.maximum(np.abs(d).mean(1),1e-30))
    bp=np.log(np.maximum((np.abs(d[:,1:])*np.abs(d[:,:-1])).mean(1),1e-30))
    NOISE[nn]=(sq.std(),ab.std(),bp.std())
    print(f"{nn:>13}{sq.std():>11.3f}{ab.std():>11.3f}{bp.std():>10.3f}{sq.std()/ab.std():>9.2f}x")
print(f"  30x more observations (48 -> 1440): squared {NOISE[48][0]/NOISE[1440][0]:.1f}x noise cut, "
      f"absolute {NOISE[48][1]/NOISE[1440][1]:.1f}x, ideal sqrt(30) = 5.5x")

# ---------------- B ----------------
D="/private/tmp/claude-501/-Users-elvisobondo-Pair-Trading/0189ea06-e901-4d24-83ff-b7b3c5ca8f65/scratchpad/disloc"
z=np.load(D+".npz"); W=z["windows"].astype(float); Y=z["outcomes"].astype(float)
M=pd.read_parquet(D+"_meta.parquet"); day=M.day.to_numpy()
tr=day<np.datetime64("2026-07-18"); te=~tr
dW=np.diff(W,axis=1); dF=np.diff(Y,axis=1)
LOG=lambda x: np.log(np.maximum(x,1e-12))
def est(d,kind):
    if kind=="sq": return LOG((d**2).mean(1))
    if kind=="abs": return 2*LOG(np.abs(d).mean(1))
    return LOG((np.abs(d[:,1:])*np.abs(d[:,:-1])).mean(1))-2*np.log(MU1)
# TARGET also gets the robust estimator: log mean(d^2) over 20 steps has
# simulated sd 0.93, so a noisy target caps R2 on its own.
TGT={k:est(dF,k) for k in ("sq","abs","bip")}
print("\n"+"="*86); print("B  v_0 predictor, held-out R2 (fit period only)"); print("="*86)
def r2(cols,tgt):
    A=np.column_stack([np.ones(tr.sum())]+[c[tr] for c in cols])
    cc=np.linalg.lstsq(A,tgt[tr],rcond=None)[0]
    p=np.column_stack([np.ones(te.sum())]+[c[te] for c in cols])@cc
    y=tgt[te]; return 1-((y-p)**2).sum()/((y-y.mean())**2).sum(), p
BEST=None
for tk,tn in (("sq","squared"),("abs","absolute")):
    print(f"\n  target = log post-entry variance from {tn} returns")
    print(f"  {'predictor':<34}{'48':>9}{'96':>9}{'335':>9}{'all three':>12}")
    for pk,pn in (("sq","squared returns (current)"),("abs","absolute returns"),
                  ("bip","bipower variation")):
        P={k:est(dW[:,-k:],pk) for k in (48,96,335)}
        vals=[r2([P[k]],TGT[tk])[0] for k in (48,96,335)]
        allr,pred=r2([P[48],P[96],P[335]],TGT[tk])
        print(f"  {pn:<34}"+"".join(f"{100*v:>8.2f}%" for v in vals)+f"{100*allr:>11.2f}%")
        if tk=="abs" and (BEST is None or allr>BEST[0]): BEST=(allr,pk,P,pred)
print(f"\n  current baseline was 27.44 / 27.14 / 21.65 / 29.95 (squared, squared target)")

# ---------------- C ----------------
print("\n"+"="*86); print("C  measurement-error ceiling"); print("="*86)
pk=BEST[1]; P48=est(dW[:,-48:],pk)
r2_obs,_=r2([P48],TGT["abs"])
vx=P48[te].var(); vy=TGT["abs"][te].var()
j={"sq":0,"abs":1,"bip":2}[pk]
nx=NOISE[48][j]**2; ny=NOISE[20][1]**2
sx=max(vx-nx,1e-9); sy=max(vy-ny,1e-9)
print(f"  best single predictor: {pk}, 48 bars.  held-out R2 {100*r2_obs:.2f}%")
print(f"  var(predictor) {vx:.3f} = signal {sx:.3f} + estimation noise {nx:.3f}"
      f"   -> {100*nx/vx:.0f}% of the predictor's spread is noise")
print(f"  var(target)    {vy:.3f} = signal {sy:.3f} + estimation noise {ny:.3f}"
      f"   -> {100*ny/vy:.0f}% of the target's spread is noise")
r2_true=r2_obs*(vx/sx)*(vy/sy)
print(f"\n  R2 signal-to-signal, both attenuations removed: {100*min(r2_true,1):.1f}%")
nx1=NOISE[1440][j]**2
r2_1m=r2_true*(sx/(sx+nx1))
print(f"  R2 a 1-minute-precision predictor would reach (target noise still"
      f" removed): {100*min(r2_1m,1):.1f}%")
print(f"  R2 observable against the SAME noisy 20-step target at 1-minute precision: "
      f"{100*min(r2_1m*(sy/vy),1):.1f}%")
print(f"\n  the build's gain on the predictor side: {100*(sx/(sx+nx1) - sx/vx):.1f}pp of"
      f" signal-to-signal R2 recovered by better measurement alone")
