"""Same ceiling test, with the right baseline.

Every R2 in bound.py came back negative with a floor near -0.56%, which is the
fit period's MEAN 10-hour change differing from the held-out period's. That is
a level shift, not a lack of signal, and it penalises the intercept and every
feature equally. So score each model against an INTERCEPT-ONLY model trained
the same way: R2_rel = 1 - SSE_model / SSE_intercept. That isolates what the
features add, which is the quantity the gate is about.
"""
exec(open("bound.py").read().split("def r2(cols)")[0])

ytr, yte = CHG[tr], CHG[te]
c0 = ytr.mean()
SSE0 = ((yte-c0)**2).sum()
print(f"\n[LEVEL SHIFT] mean 10h change in the entry's direction: "
      f"fit {ytr.mean():+.4f}  held-out {yte.mean():+.4f}   "
      f"(this is the -0.56% floor, and it is a real regime difference)")
print(f"[BASELINE] intercept-only, trained on fit, R2 vs held-out mean: "
      f"{100*(1-SSE0/((yte-yte.mean())**2).sum()):.3f}%")

def rel(cols):
    A=np.column_stack([np.ones(tr.sum()),Xs[tr][:,cols]])
    c=np.linalg.lstsq(A,ytr,rcond=None)[0]
    p=np.column_stack([np.ones(te.sum()),Xs[te][:,cols]])@c
    return 1-((yte-p)**2).sum()/SSE0

names=list(feat)
print("\n=== what each feature ADDS out of sample, 10h change (vs intercept-only) ===")
for v,k in sorted(((rel([i]),k) for i,k in enumerate(names)),reverse=True):
    print(f"  {k:<13}{100*v:>8.3f}%")
allr=rel(list(range(len(names))))
print(f"\nall {len(names)} together, HELD OUT: {100*allr:.3f}%")

dtr=np.unique(day[tr]); rb=np.random.default_rng(7); bs=[]
pos={d:np.flatnonzero(day==d) for d in dtr}
for _ in range(200):
    sel=np.concatenate([pos[d] for d in rb.choice(dtr,len(dtr),replace=True)])
    A=np.column_stack([np.ones(len(sel)),Xs[sel]])
    c=np.linalg.lstsq(A,CHG[sel],rcond=None)[0]
    p=np.column_stack([np.ones(te.sum()),Xs[te]])@c
    bs.append(1-((yte-p)**2).sum()/SSE0)
bs=np.array(bs)
print(f"   day-clustered 200 resamples: [{100*np.percentile(bs,5):.3f}%, {100*np.percentile(bs,95):.3f}%]")
print(f"\ngate needs 9.75%.  {100*allr:.2f}% buys CRPS ~ {100*np.sqrt(max(1-allr,1e-9)):.1f}% of climatology.")
