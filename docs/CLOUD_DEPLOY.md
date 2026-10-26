> **VM DELETED 2026-10-14** (instance `pairs-trading` and its 20 GB boot disk, us-central1-a). Why: OKX was dropped and research moved to Hyperliquid (HL-BUILD1/2), so the OKX paper book, the scanner cron and the OI collector had already been stopped that day; deleting the VM ends the GCP billing. The final ledger (2,043 rows) is in `research/from_vm/scanner_trades.csv`, and the whole VM tree (trading_data including monitor_ticks, logs, state, OI) is in `attic/vm_final/vm_final_20261014.tar.gz` (gitignored, sha256 781b1004...578c65a). The Artifact Registry repo `pairs-trading` (231 MB) was left in place. Everything below is history.

# Cloud deployment record — pairs-trading VM

> **PARTIALLY RETIRED — read this first, 2026-09-12.**
>
> The instance, the gcloud commands, the ssh access and the `trading_data/` bind-mount
> pattern are all still current and still how the VM works.
>
> What changed: the container no longer runs `nautilus/run_trading.py` (deleted). It
> runs `research/stop_monitor.py` as a long-lived service plus a 30-minute cron cycle
> for the scanner — see `docker-compose.trading.yml` and `scripts/vm_scan_cycle.sh`.
> The e2-micro sizing note below is also superseded: the scanner does not fit on 1GB.

Live since 2026-08-16, last updated 2026-08-17. This is the actual deployment
record (GCP, not Oracle — see "Why GCP, not Oracle" below), with the real
values in place so this doubles as the runbook for redeploying, migrating, or
debugging. See `attic/docs/HANDOFF.md` for the wider system context.

## Current deployment

- **Provider**: Google Cloud, project `project-0671be06-e22a-44d8-83c`
  (account `elvisodangaobondo@gmail.com` — note this is a *different* Google
  account than `elvisobondo31@gmail.com`, which owns a separate, unused
  project `delta-crane-464102-a1`. Use the right `gcloud config set account`
  if working across both.)
- **Instance**: `pairs-trading`, zone `us-central1-a`, machine type
  `e2-micro` (always-free tier, 1 shared vCPU / 1GB RAM, x86_64), Ubuntu
  22.04 LTS, 20GB boot disk.
- **Access**: `gcloud compute ssh pairs-trading
  --project=project-0671be06-e22a-44d8-83c --zone=us-central1-a` — key
  management is automatic (gcloud generated `~/.ssh/google_compute_engine`
  on first use), no manual key juggling needed.
- **Code location on the VM**: `~/Pair_Trading/` — source only (`nautilus/`,
  `research/`, `user_data/normalized/manifest.json`), not the data folders.
- **Runtime data**: `~/Pair_Trading/trading_data/` on the VM — bind-mounted
  into the container, survives rebuilds/recreates. Contains
  `paper_trades.csv` (the ledger — reset to empty on 2026-08-17 by explicit
  request; prior history archived at
  `research/paper_trades_archive_20260817_105807.csv`, see `attic/docs/HANDOFF.md`),
  `paper_trade_heartbeat.log`, and `paper_live/` (bar cache — must have
  `MIN_BARS`+ history per ticker or the strategy can't evaluate signals, see
  the MIN_BARS incident below).

## Why GCP, not Oracle

Original plan was Oracle Cloud Free Tier (better specs — 4 OCPU/24GB ARM,
genuinely free forever). Blocked immediately on `Out of capacity for shape
VM.Standard.A1.Flex in availability domain AD-2` — Oracle's Ampere free-tier
pool is heavily contended and this is a common, sometimes multi-day outage,
not a one-off. Switched to GCP's `e2-micro` always-free tier instead (less
generous specs, but no capacity rationing). Nothing in the deploy is
Oracle-specific except the shape/image names, so re-migrating to Oracle later
if capacity frees up is a normal redeploy, not a rebuild.

## How it was actually built (in order, with the real failures)

1. **Instance creation** — done via `gcloud`, not the console (console was
   having issues that session). Auth needed a fresh `gcloud auth login` first
   (session had expired). Then:
   ```
   gcloud services enable compute.googleapis.com --project=project-0671be06-e22a-44d8-83c
   gcloud compute instances create pairs-trading \
     --project=project-0671be06-e22a-44d8-83c --zone=us-central1-a \
     --machine-type=e2-micro --image-family=ubuntu-2204-lts \
     --image-project=ubuntu-os-cloud --boot-disk-size=20GB
   ```
2. **Docker install** — first attempt used Ubuntu's default apt repo, which
   doesn't have `docker-compose-plugin` (that's Docker's own repo, not
   Ubuntu's) — failed with `E: Unable to locate package docker-compose-plugin`.
   Second attempt tried adding Docker's official repo inline via
   `gcloud compute ssh --command="..."`, but the `$VERSION_CODENAME` variable
   got mangled by the local→ssh→remote shell quoting layers and landed
   literally in `/etc/apt/sources.list.d/docker.list` as the string
   `$VERSION_CODENAME` instead of `jammy`. Fixed by writing the install as a
   real script file and `scp`-ing it over instead of fighting nested
   quoting — much more reliable for anything non-trivial than inline
   `--command` strings. **Lesson: for any multi-line or variable-heavy remote
   command, write a script and copy it over rather than inlining it.**
3. **Code transfer** — `gcloud compute scp --recurse` for `nautilus/` and
   `research/`, plain `scp` for `requirements.txt`, `Dockerfile.trading`,
   `docker-compose.trading.yml`, and `user_data/normalized/manifest.json`.
   No `rsync` needed since only specific small paths were copied, not the
   whole repo. `.env` copied separately, `chmod 600`'d on arrival.
4. **First build** — succeeded (~17 min on the single shared vCPU, mostly
   `pip install`). `nautilus_trader==1.228.0` installed from a prebuilt
   `manylinux` wheel — the arch risk flagged pre-deploy (would nautilus have
   a wheel for the target arch?) turned out to be moot since GCP's default
   is x86_64, which has far better wheel coverage than the arm64 Oracle would
   have been.
5. **`docker logs` showed nothing** despite the container clearly being
   healthy (`docker stats` showed real CPU/memory/network activity). Root
   cause: Python fully-buffers stdout when it isn't an interactive TTY, which
   is always true inside a container — nautilus's log lines were sitting in
   a buffer instead of reaching `docker logs`. Fixed by adding
   `ENV PYTHONUNBUFFERED=1` to `Dockerfile.trading` — deliberately placed
   *after* the `pip install` layer (not before it) so the change doesn't
   invalidate/re-run the expensive dependency-install layer on rebuild.
6. **Rebuild** — all layers up to and including `pip install` came from
   cache (rebuild took under a second for everything except the final `ENV`/
   `COPY` layers). Confirmed clean startup in the logs: `Ledger read: no
   unresolved open position for RLS-USDT-SWAP.OKX/ZK-USDT-SWAP.OKX.
   next_trade_num=4, equity=70.4707` — matching the laptop's state exactly.
   Also confirmed the bind-mounted `paper_live/` cache survives container
   recreation: on this rebuild, `DataObserver` found its own previously
   persisted bars and skipped the OKX historical gap-fill entirely.
7. **Laptop process killed** (`kill -9`) once the cloud container's health
   was fully verified — ledger continuity confirmed, logs flowing, no
   errors. Exactly one process now runs this pair.

## Incident: MIN_BARS cold-start gap (2026-08-17)

**Symptom**: switched the live pair to GALA/UMA, came back ~21 hours later —
still no trades, `in_trade=False` throughout. Not obviously broken: container
healthy, no errors, bars flowing every 30 minutes without gaps.

**Diagnosis**: `PairsTradingActor.on_bar` ([pairs_actor.py:361](../nautilus/pairs_actor.py#L361))
refuses to evaluate any entry signal until both legs have `MIN_BARS=720` bars
(15 days at 30-min resolution) in the nautilus cache — unconditional, no
exception. The heartbeat log showed `bars_a` climbing from 328→342 over 7
hours, exactly 1 bar per 30 minutes — meaning nothing was topping up the
count except the live feed itself. At 342/720 with growth capped at 1/30min,
that's **~7.9 more days** before the strategy could even attempt a first
signal.

**Root cause**: `DataObserver.on_start` ([data_cache.py](../nautilus/data_cache.py))
prefers local history over an OKX request, but issues exactly one
`request_bars` call for the full gap on cold start — no loop, no pagination.
OKX's historical-bar endpoint returned only 300 candles for that call
(confirmed in the logs: `Received <Bar[300]>` for both legs on the original
GALA/UMA cold start). The remaining ~420 bars needed for `MIN_BARS` could
only be filled one at a time, live. This wasn't a problem on the laptop
(always had the full canonical feather dataset on disk, so `_load_seed_bars`
never needed the OKX fallback at all) or during the original Oracle→GCP
migration for RLS/ZK specifically (its ledger carried over, so it looked
"resumed" — but its bar cache was just as thin; it likely never actually
reached `MIN_BARS` in its one day live before the switch to GALA/UMA,
meaning it may never have evaluated a real signal either).

**Fix applied**: pulled the VM's partial `paper_live` cache down, merged it
with the laptop's full local canonical feather history for GALA and UMA
(`pd.concat` + `drop_duplicates(subset="date", keep="last")`, no data lost),
pushed the merged file back into `trading_data/paper_live/` (via `sudo mv` —
the container runs as root, so bind-mounted files it creates are root-owned
and a plain `scp` overwrite gets `Permission denied`), and restarted. Next
startup log: `Seeded 3022 local bars for UMA` — well past 720, signal
evaluation unblocked immediately.

**Made permanent**: this exact merge-and-transfer is now automatic inside
`scripts/check_vm.sh switch` (step 4/6), using `scripts/merge_bar_history.py`
for the merge logic. Every future pair switch gets full history seeded
before the container restarts — this class of bug shouldn't recur. The
underlying 300-candle cap / no-pagination gap in `data_cache.py` itself is
still unpatched though (see `attic/docs/HANDOFF.md` Known gaps) — the workaround
only helps when the laptop already has that ticker's canonical feather
downloaded.

## Ongoing operations

**Check on it**: `scripts/check_vm.sh status` (or `logs [N]`, `follow`,
`ledger [N]`, `heartbeat [N]`, `pull`, `ssh` — see that script's header
comment for the full list). Wraps the repetitive `gcloud --project/--zone`
flags so you're not retyping them.

**Pair rotation**: `scripts/check_vm.sh switch TICKER_A TICKER_B ["stats
string"]` does the whole procedure in one command — validates both tickers
are futures instruments, checks the *current* pair specifically for an open
position (asks before abandoning one), edits `run_trading.py` locally, seeds
the VM with full bar history for the new pair (see the incident writeup
above), pushes the code, rebuilds, restarts, and prints the startup log so
you can confirm it came up clean. Manual equivalent, if ever needed:
1. Check for an open position: `scripts/check_vm.sh ledger`.
2. Edit `TICKER_A`/`TICKER_B` (+ `LAST_SELECTED_DATE`/`LAST_SELECTED_STATS`)
   in `nautilus/run_trading.py` **locally**.
3. `gcloud compute scp nautilus/run_trading.py pairs-trading:~/Pair_Trading/nautilus/run_trading.py --project=project-0671be06-e22a-44d8-83c --zone=us-central1-a`
4. `gcloud compute ssh pairs-trading --project=project-0671be06-e22a-44d8-83c --zone=us-central1-a --command="cd ~/Pair_Trading && docker compose -f docker-compose.trading.yml up -d --build"`
5. Verify the "Ledger read: no unresolved open position" line in
   `docker logs pairs-trading`.

**Data refresh** (`scripts/update_data.sh` + the macOS LaunchAgent) stays on
the laptop — only needed for re-running the pair-selection scan
(`research/run_all.py`), which is analysis work still done locally. The VM
only runs whichever pair was already selected; it doesn't need the 269-ticker
historical dataset.

**e2-micro is genuinely small** (1 shared vCPU, 1GB RAM). Fine for this one
process, but don't add anything else heavy to this instance without bumping
the machine type — check `docker stats` if anything seems sluggish.
