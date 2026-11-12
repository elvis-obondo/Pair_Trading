"""HL-VAULT1 (brief docs/prompts/HL_VAULT1_RUN.md): the ONLY module that may read a vault-period row
(t0 >= harness.VAULT_START). harness.py's own load_search_events excludes these by construction and
asserts it; this module is the other half -- read ONLY from here, nowhere else.

Two levels, matching the brief's own staging:
- load_vault_event_dates(): events.parquet ONLY (ticker_a/ticker_b/entry_time/t0/event_id/geometry) --
  NO join to labels.parquet, so no label_gap/reach_Xh/outcome/net/gross column ever passes through this
  function. This is what the brief's step 1 ("coverage check ... no vault labels or outcomes read") is
  allowed to call.
- load_vault_events(columns=None): the full events+labels merge, mirroring harness.load_search_events's
  own join but with the inverted date filter (t0 >= VAULT_START instead of t0 < SEARCH_END). Reads
  label_gap/reach_Xh/outcome/net/gross/etc. Per the brief, "only from step 3 on" -- the coverage check
  (step 1) must not call this.

Both read through master_manifest.open_version (sha256-verified against the frozen v1 manifest, same as
every other model-input read in this codebase) and assert every returned row's t0 >= VAULT_START, so a
bug here that accidentally widened the date filter would hard-fail immediately rather than silently leak
search-period rows into a vault-only computation.
"""
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research", "dataset"))
import master_manifest as MF  # noqa: E402 -- this itself prepends research/dislocation_model to
                               # sys.path, which also holds an unrelated harness.py, so HERE must be
                               # (re-)inserted AFTER this import to make sure "import harness" below
                               # resolves to research/model/harness.py, not that one.
sys.path.insert(0, HERE)
import harness as H  # noqa: E402

UNIT = H.UNIT
VERSION = H.VERSION
VAULT_START = H.VAULT_START


def _schema_columns(name):
    import pyarrow.parquet as pq
    return set(pq.read_schema(os.path.join(MF.WORK, UNIT, name)).names)


def load_vault_event_dates():
    """events.parquet only, t0 >= VAULT_START, to the natural end of v1's data (no upper cutoff --
    v1 was frozen with a fixed end date already). Columns: event_id, ticker_a, ticker_b, t0, z, beta,
    alpha, mu, sigma -- geometry only, no label_gap/reach/outcome/net/gross (those live in labels.parquet,
    never opened by this function). Safe for step 1's coverage check."""
    cols = ["event_id", "ticker_a", "ticker_b", "entry_time", "z", "beta", "alpha", "mu", "sigma"]
    ev = MF.open_version(VERSION, UNIT, "events.parquet", columns=cols)
    ev["t0"] = pd.to_datetime(ev["entry_time"], utc=True) + pd.Timedelta(minutes=30)
    n_total = len(ev)
    vault = ev[ev["t0"] >= VAULT_START].copy()
    print(f"[VAULT_LOADER] load_vault_event_dates: {n_total:,} total pair events -> {len(vault):,} "
          f"with t0 >= VAULT_START ({VAULT_START})")
    assert (vault["t0"] >= VAULT_START).all(), "load_vault_event_dates returned a row before VAULT_START"
    return vault.set_index("event_id", drop=False)


def load_vault_events(columns=None):
    """events.parquet + labels.parquet merged, t0 >= VAULT_START -- mirrors harness.load_search_events's
    own join exactly, with the inverted date filter. Per the brief, callable only from step 3 on (scoring
    the vault with the saved model); step 1's coverage check must use load_vault_event_dates() instead,
    which never touches labels.parquet."""
    need = set(columns or []) | {"event_id", "label_gap", "reach_10h", "chance_10h", "minutes_to_mu"}
    events_cols = {c for c in need if c in _schema_columns("events.parquet")} | {"event_id", "entry_time"}
    ev = MF.open_version(VERSION, UNIT, "events.parquet", columns=sorted(events_cols))
    labels_cols = {c for c in need if c in _schema_columns("labels.parquet")} | \
        {"event_id", "label_gap", "reach_10h", "chance_10h", "minutes_to_mu"}
    lb = MF.open_version(VERSION, UNIT, "labels.parquet", columns=sorted(labels_cols))
    df = ev.merge(lb, on="event_id", how="inner", validate="one_to_one")
    df["t0"] = pd.to_datetime(df["entry_time"], utc=True) + pd.Timedelta(minutes=30)

    n_total = len(df)
    df = df[df["t0"] >= VAULT_START].copy()
    n_vault = len(df)
    n_label_gap = int((df["label_gap"] != 0).sum())
    print(f"[VAULT_LOADER] load_vault_events: {n_total:,} merged rows -> {n_vault:,} with t0 >= "
          f"VAULT_START -> {n_vault - n_label_gap:,} usable (label_gap=0), {n_label_gap:,} label_gap=1")

    assert (df["t0"] >= VAULT_START).all(), "load_vault_events returned a row before VAULT_START"
    return df.set_index("event_id", drop=False)


if __name__ == "__main__":
    dates = load_vault_event_dates()
    print(f"[VAULT_LOADER] self-check: {len(dates):,} vault event dates, "
          f"{dates['t0'].min()} to {dates['t0'].max()}, "
          f"{dates['ticker_a'].nunique() + dates['ticker_b'].nunique()} raw ticker mentions")
