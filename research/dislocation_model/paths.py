"""Where the dislocation datasets live. One definition, imported by everything.

The datasets are large (93MB) and .gitignore'd. REBUILD.md carries the exact
command that regenerates each one from the panel; the recipe is what is in git,
the bytes only need to be on disk.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
RESEARCH = os.path.dirname(HERE)
DATASETS = os.path.join(RESEARCH, "datasets")

DISLOC = os.path.join(DATASETS, "disloc.npz")           # 60,000 x 336 windows + 21 outcomes
META = os.path.join(DATASETS, "disloc_meta.parquet")    # one row per dislocation
ENVFEAT = os.path.join(DATASETS, "envfeat.npz")         # 60,000 x 5 environment features

# EXTFEAT (41 external + 21 window) and WAVE were removed 2026-10-09 with
# external.py and wave_full.py, now in attic/research/. They were built against a
# 212-ticker / 36,172-bar panel; the panel loads 214 / 36,215, so they were stale
# as well as superseded. Do not re-add a constant for a file nothing writes.

# The prefix mkdisloc writes to: it appends ".npz" and "_meta.parquet".
DISLOC_PREFIX = os.path.join(DATASETS, "disloc")
