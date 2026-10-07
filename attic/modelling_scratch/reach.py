"""Is 9.75% R2 on the 10-hour change reachable by anything we can measure?

The decomposition leaves the centre as the only lever and the gate needs
~9.75% of the variance of the 10h change. This asks the upper bound a different
way: fit the change on every entry-time feature available, in-sample, with no
penalty. In-sample R2 with 15 features on 2,538 rows is an OPTIMISTIC ceiling,
not an estimate -- if even that is far under 9.75% the gate is out of reach.

Reported with a day-clustered out-of-sample R2 alongside, since in-sample R2
with this many features is inflated by roughly k/n.
"""
exec(open("centre.py").read().split('print("\\n=== centre error')[0])

md=m.iloc[keep].reset_index(drop=True)
day=pd.to_datetime(md.opened_at).dt.floor("D").to_numpy()
sgv=md.sigma_at_entry.to_numpy(float); btv=md.beta_at_entry.to_numpy(float)

feat={
 "z_entry":      md.z_at_entry.to_numpy(float),
 "abs_z":        np.abs(md.z_at_entry.to_numpy(float)),
 "y0":           y0,
 "abs_y0":       np.abs(y0),
 "r2":           md.r2_at_entry.to_numpy(float),
 "abs_beta":     np.abs(btv),
 "log_sigma":    np.log(np.clip(sgv,1e-9,None)),
 "neutrality":   np.abs(md.net_exposure_frac.to_numpy(float)),
 "theta":        md.theta_at_entry.to_numpy(float),
 "log_notional": np.log(np.clip(md.gross_notional.to_numpy(float),1e-9,None)),
 # path shape in the fitted window, all pre-entry
 "w_sd":         W.std(1),
 "w_slope":      (W[:,-1]-W[:,-48])/48.0,
 "w_mean":       W.mean(1),
 "w_range":      W.max(1)-W.min(1),
 "step_sd":      np.diff(W,axis=1).std(1),
}
a,gd=ACT[20]; chg=(a-y0)[gd]
X=np.column_stack([np.nan_to_num(v[gd],nan=0.0,posinf=0.0,neginf=0.0) for v in feat.values()])
X=(X-X.mean(0))/np.where(X.std(0)>0,X.std(0),1.0)
d=day[gd]; days=np.unique(d)
print(f"n {gd.sum()}  features {X.shape[1]}  days {len(days)}  change sd {chg.std():.3f}\n")

def r2_of(Xs,ys,Xo,yo):
    A=np.column_stack([np.ones(len(Xs)),Xs])
    c=np.linalg.lstsq(A,ys,rcond=None)[0]
    p=np.column_stack([np.ones(len(Xo)),Xo])@c
    return 1-((yo-p)**2).sum()/((yo-yo.mean())**2).sum()

print("single feature, in-sample R2 of the 10h change")
for i,k in enumerate(feat):
    print(f"  {k:<14}{100*r2_of(X[:,[i]],chg,X[:,[i]],chg):>7.2f}%")

print(f"\nall {X.shape[1]} together, in-sample (an optimistic ceiling): "
      f"{100*r2_of(X,chg,X,chg):>.2f}%")

rng=np.random.default_rng(4); accs=[]
for rep in range(20):
    sh=rng.permutation(days); cut=int(0.7*len(days))
    tr=np.isin(d,sh[:cut]); te=~tr
    accs.append(r2_of(X[tr],chg[tr],X[te],chg[te]))
accs=np.array(accs)
print(f"held-out, 70/30 by DAY, 20 splits: median {100*np.median(accs):>.2f}%  "
      f"[{100*np.percentile(accs,10):.2f}%, {100*np.percentile(accs,90):.2f}%]")
print(f"\ngate needs 9.75%")
