"""Two panels: the band can be anything and CRPS does not move; and what a
10-hour outcome actually looks like."""
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

# nine fits from exp.log: (label, 10h band ratio, CRPS % of climatology)
F=[("E0 unfitted",1.22,99.4),("E1",1.33,100.3),("E3",1.31,100.1),
   ("E2.0",1.33,100.5),("E2.1",0.95,105.6),("E2.2",1.02,100.4),
   ("E2.3",1.32,100.5),("E2.4",0.38,101.4)]
z=np.load("disloc.npz"); Y=z["outcomes"].astype(float)
s=np.sign(Y[:,0]); s[s==0]=1.0; v=(Y[:,20]-Y[:,0])*s

fig,ax=plt.subplots(1,2,figsize=(12,4.6))
b=np.array([x[1] for x in F]); c=np.array([x[2] for x in F])
ax[0].axhline(100,color="0.6",lw=1)
ax[0].axhline(95,color="crimson",lw=1.2,ls="--")
ax[0].axvline(1.0,color="0.6",lw=1,ls=":")
ax[0].scatter(b,c,s=70,color="#2b6cb0",zorder=3)
for lab,bb,cc in F:
    ax[0].annotate(lab,(bb,cc),textcoords="offset points",xytext=(6,4),fontsize=8)
ax[0].set_xlabel("10-hour band ratio  (1.0 = honest, >1 too narrow, <1 too wide)")
ax[0].set_ylabel("CRPS, % of climatology  (lower is better)")
ax[0].set_title("Calibration can be anything. The score does not move.",fontsize=10)
ax[0].text(0.42,95.6,"the gate: 95%",color="crimson",fontsize=8)
ax[0].set_ylim(93,107)

ax[1].hist(np.clip(v,-12,12),bins=120,color="#2b6cb0",alpha=.85)
ax[1].axvline(0,color="0.4",lw=1)
ax[1].axvline(v.mean(),color="crimson",lw=1.5)
ax[1].axvline(np.median(v),color="darkorange",lw=1.5)
ax[1].set_xlabel("10-hour change in the entry's own direction, sigma  (negative = reverted)")
ax[1].set_ylabel("dislocations")
ax[1].set_title(f"60,000 dislocations, 746 days: median {np.median(v):.2f}, mean {v.mean():.2f}",fontsize=10)
ax[1].legend([plt.Line2D([],[],color="crimson"),plt.Line2D([],[],color="darkorange")],
             [f"mean {v.mean():.3f}",f"median {np.median(v):.3f}"],fontsize=8)
plt.tight_layout(); plt.savefig("phase2.png",dpi=130)
print("wrote phase2.png")
