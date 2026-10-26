"""R2 of the model's predicted change against the realised change.

The gate needs ~9.75% at 10 hours. This measures what each fit delivers.
Signed: a negative R2 column means the direction is anti-predictive.
"""
exec(open("centre.py").read().split('print("\\n=== centre error')[0])

FITS=[
 ("E0  unfitted      ", 0.0850,-0.0200,0.4880,0.4750,0.0980,0.0379,0.0912),
 ("E1  D from C      ", 1.0000, 0.0061,0.2347,0.5783,0.0000,0.1291,0.0147),
 ("E3  g pinned 0    ", 1.0000, 0.0051,0.2825,0.5354,0.0000,0.1497,0.0163),
 ("E2.0 random       ", 1.0000, 0.0044,0.2268,0.5845,0.0000,0.1130,0.0138),
 ("E2.1 random       ", 0.6413,-0.1110,0.6770,0.0059,0.1458,0.0111,0.0620),
 ("E2.2 random       ", 1.0000,-0.0005,0.0684,0.9164,0.0120,0.2097,0.0044),
 ("E2.3 random       ", 1.0000, 0.0041,0.2292,0.5877,0.0000,0.1126,0.0137),
]
print(f"{'fit':<20}{'h':>6} {'corr':>8} {'R2 %':>8} {'beta':>8} {'pred sd':>8} {'MAE':>8} {'put MAE':>8}")
for name,kr,kd,qL,qX,r,qrd,qdr in FITS:
    T=np.array([[1-qrd,qrd],[qdr,1-qdr]])
    out=simulate([kr,kd],qL,qX,max(r,1e-9),T)
    for s_ in (1,20):
        a,gd=ACT[s_]; chg=(a-y0)[gd]
        pred=(out[s_].mean(1)-y0)[gd]
        cr=np.corrcoef(pred,chg)[0,1]
        b=np.cov(chg,pred)[0,1]/np.var(pred)
        print(f"{name if s_==1 else '':<20}{s_*0.5:>5.1f}h {cr:>8.4f} {np.sign(cr)*cr*cr*100:>7.2f}% "
              f"{b:>8.3f} {pred.std():>8.4f} {np.abs(chg-pred).mean():>8.4f} {np.abs(chg).mean():>8.4f}")
    print(flush=True)
