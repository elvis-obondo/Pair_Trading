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
EXTFEAT = os.path.join(DATASETS, "extfeat.npz")         # 41 external + 21 window features
WAVE = os.path.join(DATASETS, "wave_full.npz")          # full-universe dislocation share

# The prefix mkdisloc writes to: it appends ".npz" and "_meta.parquet".
DISLOC_PREFIX = os.path.join(DATASETS, "disloc")
