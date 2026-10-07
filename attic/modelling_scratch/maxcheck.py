"""Verify the sample-size correction on the 'largest move' row.

Model max is over 18,064 x 200 x 20 = 72,256,000 draws; real max over
18,064 x 20 = 361,280. The maximum of a fat-tailed sample grows as n^(1/nu),
so the two are not like-for-like. Measure the ratio directly instead of
trusting the asymptotic formula.
"""
import numpy as np
n_real, mult = 361_280, 200
for nu in (2.523, 2.689, 3.000):
    rng=np.random.default_rng(7)
    sc=np.sqrt((nu-2)/nu)
    small,big=[],[]
    for rep in range(5):
        mx=np.empty(mult)
        for c in range(mult):
            mx[c]=np.abs(rng.standard_t(nu,n_real)*sc).max()
        small.append(np.median(mx)); big.append(mx.max())
    ratio=np.mean(big)/np.mean(small)
    print(f"nu {nu:.3f}   max over {n_real:,} = {np.mean(small):6.1f}   "
          f"max over {n_real*mult:,} = {np.mean(big):8.1f}   "
          f"measured ratio {ratio:5.2f}x   n^(1/nu) = {mult**(1/nu):5.2f}x")
