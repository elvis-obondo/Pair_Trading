"""Leak hunt on the three passing cells.

Hypothesis: v_0 (and the tree, and the flipped reversion probability) predict
FULL only because they predict TRAVEL DISTANCE, and travelling far makes both
full retracement and a large adverse move more likely. If so the same predictors
score just as well on the mirror-image target and carry no directional edge.

ADVERSE = the spread widened by at least |z_entry| at some point in 10h, i.e.
retracement <= -1.0 -- the exact mirror of FULL.
"""
import sys, warnings
sys.path.insert(0,"/Users/elvisobondo/Pair_Trading/research")
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier as HC
from sklearn.metrics import roc_auc_score
warnings.filterwarnings("ignore")
S="/private/tmp/claude-501/-Users-elvisobondo-Pair-Trading/0189ea06-e901-4d24-83ff-b7b3c5ca8f65/scratchpad/"
z=np.load(S+"disloc.npz"); Y=z["outcomes"].astype(np.float64)
M=pd.read_parquet(S+"disloc_meta.parquet"); day=M.day.to_numpy()
e=Y[:,0]; s=np.sign(e); s[s==0]=1
RET=(e[:,None]-Y)*s[:,None]/np.abs(e)[:,None]
FULL=(RET[:,1:].max(1)>=1.0).astype(int)
ADV =(RET[:,1:].min(1)<=-1.0).astype(int)
BIG =((RET[:,1:].max(1)>=1.0)|(RET[:,1:].min(1)<=-1.0)).astype(int)
CUT=np.datetime64("2026-07-18"); tr=day<CUT; te=~tr
fd=np.sort(np.unique(day[tr])); vc=fd[int(0.8*len(fd))]
trm=tr&(day<vc); vam=tr&(day>=vc)
print(f"base rates (all 60,000):  FULL {100*FULL.mean():.1f}%   ADVERSE {100*ADV.mean():.1f}%"
      f"   EITHER {100*BIG.mean():.1f}%")
f2=np.load(S+"extfeat.npz"); BOTH=np.column_stack([f2["EXT"],f2["WIN"]])
# v_0 multiplier, rebuilt exactly as elsewhere
dW=np.diff(z["windows"].astype(float)*s[:,None],axis=1); dF=np.diff(Y,axis=1)
LOG=lambda x:np.log(np.maximum(x,1e-12))
PRE=np.column_stack([LOG((dW[:,-k:]**2).mean(1)) for k in (48,96,335)])
rv=2*LOG(np.abs(dF).mean(1))
A=np.column_stack([np.ones(tr.sum()),PRE[tr]]); c=np.linalg.lstsq(A,rv[tr],rcond=None)[0]
v0=np.exp(np.column_stack([np.ones(len(Y)),PRE])@c)
P=dict(max_iter=200,early_stopping=False,learning_rate=0.05,max_leaf_nodes=15,
       l2_regularization=1.0,min_samples_leaf=50,random_state=0)
def tree(y):
    m=HC(**P).fit(BOTH[trm],y[trm])
    sv=list(m.staged_decision_function(BOTH[vam])); st=list(m.staged_decision_function(BOTH[te]))
    b=int(np.argmax([roc_auc_score(y[vam],q.ravel()) for q in sv]))
    return roc_auc_score(y[te],st[b].ravel())
print(f"\n{'predictor':<30}{'FULL':>9}{'ADVERSE':>10}{'EITHER':>9}{'gap':>8}")
for nm,p in (("v_0 volatility prediction",v0),):
    r=[roc_auc_score(t[te],p[te]) for t in (FULL,ADV,BIG)]
    print(f"{nm:<30}{r[0]:>9.4f}{r[1]:>10.4f}{r[2]:>9.4f}{r[0]-r[1]:>8.4f}")
r=[tree(t) for t in (FULL,ADV,BIG)]
print(f"{'boosted tree, 62 features':<30}{r[0]:>9.4f}{r[1]:>10.4f}{r[2]:>9.4f}{r[0]-r[1]:>8.4f}")
print(f"\nIf FULL and ADVERSE score alike, the signal is TRAVEL DISTANCE, not direction.")
print(f"EITHER (did it move far at all) is the target that signal is really answering.")
