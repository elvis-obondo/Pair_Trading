# attic/2026-10-26: cleanup after HL-MASTER1 version 1

Moved, not deleted, on 2026-10-26, after version 1 of the master dataset was frozen
(s3://pair-trading-hl-289869684922/master/versions/v1/). Deleting anything here is a
separate decision for a separate day, the same rule as the rest of attic/.

**Rule used:** a file stayed in place only if the version 1 code needs it. That means
it is imported, directly or indirectly, by research/dataset/* or research/hyperliquid/*.
Everything else moved here. The findings these files produced are recorded in
research/dislocation_model/NUMBERS.md (with log receipts in research/dislocation_model/logs/,
which stayed in place) and in docs/HYPERLIQUID_HANDOFF.md.

- `research/dislocation_model/`: earlier study scripts, including the OKX-era reach/why/meta-label
  studies, delayed*, the HL build 3/4/5 test scripts, mkdisloc.py (the origin of the
  adaptive-trigger rule now in master_events.py), and rolling.py / rolling_window.py (the
  rolling walk-forward design is in docs/prompts/HL_BUILD6_FULL_POPULATION.md; the next
  model harness should be rebuilt on the v1 tables).
- `research/okx_system/`: the retired OKX paper-trading system (scanner, stop monitor, sizing,
  backtests, sweeps) and their validators, plus open_positions.json.
- `research/okx_outputs/`, `exit_study/`, `rank_experiment/`, `from_vm/`, `scan_history/`, `backups/`:
  local data and outputs. These are on disk only and gitignored.
- `research/retired_nautilus_paper/`, `live_archive/`, `markdowns/`: old notes and archives.
- `scripts/`: the old trading-VM, launchd, release and book scripts. The research-machine
  scripts (gcp_*.sh) stayed in place.
- `top/`: Docker and freqtrade compose files, the dashboard, the APE/DOGE note, old logs/
  and backups/ (gitignored), and the empty trading_data/.

Not moved: user_data/ (it holds the gitignored OKX config with keys; leave it in place).
