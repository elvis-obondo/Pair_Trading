"""Planner's request (2026-11-12): the additive CD-cap counters in s1_newton.py (n_cd_capped, n_cd_calls) must not
change any fit. Loads the OLD s1_newton.py straight from git (commit 98c74c9, before the edit) and the CURRENT file,
runs both on the same synthetic hazard problems (several lam / l1_ratio / warm-start combos, including a case where
the inner CD cap is hit), and asserts BITWISE-identical w, b, obj_final, rel_change, n_iter, n_calls, converged.
    python research/model/diagnostics/newton_counter_identity.py > research/model/diagnostics/newton_counter_identity.log
"""
import hashlib
import importlib.util
import os
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(MODEL))
sys.path.insert(0, MODEL)

OLD_COMMIT = "98c74c9"
old_src = subprocess.run(["git", "-C", ROOT, "show", f"{OLD_COMMIT}:research/model/s1_newton.py"], capture_output=True,
                         text=True, check=True).stdout
tmp = tempfile.mkdtemp()
old_path = os.path.join(tmp, "s1_newton_old.py")
open(old_path, "w").write(old_src)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


OLD = load("s1_newton_old", old_path)
NEW = load("s1_newton_new", os.path.join(MODEL, "s1_newton.py"))
print(f"[IDENT] old s1_newton.py = git {OLD_COMMIT}, sha256 {hashlib.sha256(old_src.encode()).hexdigest()}")
print(f"[IDENT] new s1_newton.py = working file, sha256 {hashlib.sha256(open(os.path.join(MODEL, 's1_newton.py'), 'rb').read()).hexdigest()}")


def problem(seed, n_ev, p, n_steps=20):
    rng = np.random.default_rng(seed)
    w_true = np.zeros(p)
    w_true[:5] = rng.normal(0, 0.8, 5)
    pos, st, lab, X = [], [], [], []
    for e in range(n_ev):
        x = rng.normal(size=p)
        eta = x @ w_true - 2.5
        for t in range(1, n_steps + 1):
            hit = rng.random() < 1 / (1 + np.exp(-eta))
            pos.append(e); st.append(t); X.append(x); lab.append(int(hit))
            if hit:
                break
    return (np.array(X, dtype=np.float32), np.array(pos), np.array(st), np.array(lab), n_ev)


cases = []
for seed, n_ev, p in ((1, 600, 40), (2, 1500, 80)):
    P = problem(seed, n_ev, p)
    for lam, l1 in ((5.0, 1.0), (50.0, 0.5), (0.5, 0.0), (20.0, 0.9)):
        cases.append((f"seed{seed} n_ev={n_ev} p={p} lam={lam} l1={l1} cold", P, dict(lam=lam, l1_ratio=l1)))
    cases.append((f"seed{seed} cd_max_sweeps=2 (cap hit) lam=5 l1=1.0", P, dict(lam=5.0, l1_ratio=1.0, cd_max_sweeps=2)))
    w0 = np.zeros(p); w0[:3] = 0.1
    cases.append((f"seed{seed} warm start lam=20 l1=0.9", P, dict(lam=20.0, l1_ratio=0.9, w0=w0, b0=np.full(20, -3.0))))

n_cap_seen = 0
for name, (X, pos, st, lab, n_ev), kw in cases:
    a = OLD.fit_hazard_elastic_net_newton(X, pos, st, lab, n_ev, **kw)
    b = NEW.fit_hazard_elastic_net_newton(X, pos, st, lab, n_ev, **kw)
    for k in ("w", "b"):
        assert np.array_equal(a[k], b[k]), f"{name}: {k} differs"
    for k in ("obj_final", "rel_change", "n_iter", "n_calls", "converged"):
        assert a[k] == b[k], f"{name}: {k} differs ({a[k]} vs {b[k]})"
    assert set(b) - set(a) == {"n_cd_capped", "n_cd_calls"} and set(a) - set(b) == set()
    assert b["n_cd_calls"] == b["n_iter"]
    n_cap_seen += b["n_cd_capped"]
    print(f"[IDENT] {name}: bitwise identical w,b,obj_final={a['obj_final']:.10f},rel_change,n_iter={a['n_iter']},"
          f"converged={a['converged']}; new counters n_cd_capped={b['n_cd_capped']} n_cd_calls={b['n_cd_calls']}")
assert n_cap_seen > 0, "no case exercised the capped branch"
print(f"[IDENT] PASSED: {len(cases)} cases, all bitwise identical; the capped branch was exercised "
      f"(total capped outer steps across cases = {n_cap_seen})")
