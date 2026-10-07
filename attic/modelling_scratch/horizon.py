"""What does the holding horizon cost or buy? Descriptive, all 60,000, 746 days.

SIGN CONVENTION: positive = moved TOWARD the mean. move(h) = -(z_h - z_0)*sign(z_0).
So the recorded 0.112 sigma of reversion at 10h appears as +0.112.

EXCURSIONS ARE MEASURED ON 30-MINUTE CLOSES. The true worst point inside a bar
is strictly worse than what is reported here, so every adverse excursion below
is a LOWER BOUND on the pain actually sat through. That matters for a stop
question specifically.

Nothing is fitted. Held-out is not used -- this is what happened, not a claim.
"""
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
S="/private/tmp/claude-501/-Users-elvisobondo-Pair-Trading/0189ea06-e901-4d24-83ff-b7b3c5ca8f65/scratchpad/"
z=np.load(S+"disloc.npz"); Y=z["outcomes"].astype(float)
M=pd.read_parquet(S+"disloc_meta.parquet"); day=M.day.to_numpy()
e=Y[:,0]; s=np.sign(e); s[s==0]=1
MOVE=-(Y-e[:,None])*s[:,None]                      # (60000,21) positive = toward the mean
RET=MOVE/np.abs(e)[:,None]                         # retracement units, 1.0 = at the mean
N=len(Y); COST=(0.105,0.143)
du=np.unique(day); pos={d:np.flatnonzero(day==d) for d in du}
rb=np.random.default_rng(5)
BOOT=[np.concatenate([pos[d] for d in rb.choice(du,len(du),replace=True)]) for _ in range(300)]
print(f"[DATA] all {N:,} dislocations, {len(du)} days, 2024-09-18 to 2026-10-04")
print(f"[SIGN] positive = toward the mean.  [COST] round trip {COST[0]}-{COST[1]} sigma")
print(f"[CAVEAT] excursions are 30-minute CLOSES -- true adverse excursions are worse\n")

print("="*132)
print(f"{'h':>5}{'mean':>8}{'95% day-clustered':>19}{'median':>8}{'p25':>7}{'p75':>7}{'p5':>8}{'p95':>8}"
      f"{'%rev':>7}{'%full':>7}{'ADV med':>9}{'ADV p90':>9}{'FAV med':>9}{'FAV p90':>9}{'mean/ADV':>10}")
print("="*132)
rows=[]
for h in range(1,21):
    mv=MOVE[:,h]
    adv=np.maximum(-MOVE[:,1:h+1].min(1),0.0)      # worst against you, positive
    fav=np.maximum( MOVE[:,1:h+1].max(1),0.0)      # best in your favour
    full=(RET[:,1:h+1].max(1)>=1.0).mean()
    b=np.array([MOVE[ix,h].mean() for ix in BOOT])
    am=np.median(adv)
    rows.append((h*0.5,mv.mean(),np.percentile(b,2.5),np.percentile(b,97.5),np.median(mv),
                 am,np.percentile(adv,90),np.median(fav),np.percentile(fav,90),
                 mv.mean()/am if am>0 else np.nan))
    print(f"{h*0.5:>5.1f}{mv.mean():>8.3f}  [{np.percentile(b,2.5):>6.3f},{np.percentile(b,97.5):>6.3f}]"
          f"{np.median(mv):>8.3f}{np.percentile(mv,25):>7.2f}{np.percentile(mv,75):>7.2f}"
          f"{np.percentile(mv,5):>8.2f}{np.percentile(mv,95):>8.2f}"
          f"{100*(mv>0).mean():>6.1f}%{100*full:>6.1f}%"
          f"{am:>9.3f}{np.percentile(adv,90):>9.2f}{np.median(fav):>9.3f}{np.percentile(fav,90):>9.2f}"
          f"{mv.mean()/am if am>0 else np.nan:>10.3f}")
R=np.array(rows)
k=int(np.nanargmax(R[:,9]))
print(f"\n[RATIO] mean signed move / median adverse excursion peaks at {R[k,0]:.1f}h "
      f"at {R[k,9]:.3f}; at 10.0h it is {R[-1,9]:.3f}")
print(f"[BAR]   mean move clears the {COST[0]}-{COST[1]} cost band at: "
      f"{[f'{r[0]:.1f}h' for r in rows if r[1]>COST[1]] or 'NO HORIZON'}")
print(f"[NOTE]  the traded sample's recorded +0.28 sigma gross is not reproduced here "
      f"(0.112 at 10h). Different populations -- the traded set passed ranking and slot\n"
      f"        allocation over a different period. The gap is real and unexplained; not chased in this pass.")

x=R[:,0]
plt.figure(figsize=(10,6))
plt.fill_between(x,-R[:,6],R[:,8],color="0.88",label="p90 adverse / p90 favourable excursion")
plt.fill_between(x,-R[:,5],R[:,7],color="0.75",label="median adverse / median favourable excursion")
plt.plot(x,R[:,1],color="#2b6cb0",lw=2.4,label="mean signed move (held to h)")
plt.fill_between(x,R[:,2],R[:,3],color="#2b6cb0",alpha=.3,label="95% day-clustered on the mean")
plt.plot(x,R[:,4],color="#38a169",lw=2,ls="--",label="median signed move")
plt.axhspan(COST[0],COST[1],color="crimson",alpha=.25)
plt.axhline(COST[0],color="crimson",lw=1); plt.axhline(COST[1],color="crimson",lw=1)
plt.text(0.3,COST[1]+0.03,"round-trip cost band 0.105-0.143 sigma",color="crimson",fontsize=8)
plt.axhline(0,color="0.4",lw=1)
plt.xlabel("holding horizon, hours"); plt.ylabel("sigma, positive = toward the mean")
plt.title("What the horizon costs and buys, 60,000 dislocations over 746 days",fontsize=11)
plt.legend(fontsize=8,loc="upper left"); plt.tight_layout(); plt.savefig(S+"horizon.png",dpi=130)
print("\nwrote horizon.png")
