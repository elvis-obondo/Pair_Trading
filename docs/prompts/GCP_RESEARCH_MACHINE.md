# Builder prompt: Google Cloud research machine (runs alongside build 2)

User decision 2026-10-14: research tests run on a Google Cloud machine, not the
laptop (8.6 GB RAM is too small for some planned tests; laptop disk is tight).
Use the Google trial credits while they last. The laptop stays the place to
plan, write prompts and read results. Do exactly this; nothing else.

## Facts (re-check)

- GCP project `project-0671be06-e22a-44d8-83c`, account
  `elvisodangaobondo@gmail.com` (NOT elvisobondo31, which owns an unused
  project). `gcloud` at `/opt/homebrew/bin/gcloud`. The old `pairs-trading` VM
  was deleted today; the project and billing account remain.
- Free trial: max 8 vCPUs running at once; credits expire ~2026-11-08.
- Build-2 outputs land in `s3://pair-trading-hl-289869684922/` (AWS
  ap-northeast-1). AWS → internet egress ~$0.11/GB.
- Python deps: `requirements.txt` at the repo root; laptop venv `.venv`.

## Build

1. **Machine:** `e2-highmem-8` (8 vCPU, 64 GB), zone `us-central1-a`, Ubuntu
   22.04 LTS, 100 GB pd-balanced boot disk, name `pt-research`. No public
   services; ssh via `gcloud compute ssh` only.
2. **Idle auto-stop:** a cron job on the machine that stops it (`sudo
   shutdown -h now` = STOP for GCE, not delete) after 30 minutes with no
   process from the research venv running and load average < 0.5. Log each
   decision to `/var/log/pt-idle.log`. Test it once: confirm the machine
   stops on its own.
3. **Environment:** Python matching the laptop's version, venv from
   `requirements.txt`; verify imports of the research modules.
4. **Code sync:** `scripts/gcp_run.sh` on the laptop:
   `gcp_run.sh "<command>"` starts the machine if stopped, rsyncs the repo
   (exclude `.venv`, `attic/`, `user_data/data/`, `research/datasets/`,
   `__pycache__`), runs the command under `nohup` with its log in
   `research/**/logs/`, and `gcp_run.sh pull` rsyncs logs, NUMBERS.md diffs
   and small outputs back. One script, documented in its header.
5. **Data:** create AWS IAM user `pt-gcp-reader` with read-only access to
   `pair-trading-hl-289869684922` only; put its key on the machine (never in
   the repo). The machine pulls build-2 outputs straight from S3 into
   `user_data/data/hyperliquid/` and `research/hyperliquid/flow/`. Copy the
   ctx files (`user_data/data/hyperliquid/ctx/`) up from the laptop, saved
   compressed (zstd feather/parquet).
6. **Redirect build 2's download:** D1's "bring down to the laptop" step now
   targets this machine, not the laptop. Part E (dislocation set) runs on
   this machine via `gcp_run.sh`. The laptop keeps only the 30m bars (small)
   for quick looks.
7. **Free laptop space** (user agreed): upload `attic/okx_data/` and
   `attic/okx_datasets/` to `s3://pair-trading-hl-289869684922/attic/`,
   verify by object count and total bytes, then delete the laptop copies.
   Re-save laptop ctx files compressed, or delete them once they are on the
   machine. Report free space before and after.
8. **Billing guard:** GCP budget alert on the project at $50/month to
   `elvisodangaobondo@gmail.com`. Add to `docs/HYPERLIQUID_HANDOFF.md`
   decisions: "2026-11-01 reminder — GCP trial credits end ~2026-11-08:
   upgrade GCP or move `pt-research` to AWS."

## Rules for every test run on it

- Load only what the test needs (per coin, per column, event windows); no
  whole flow table in memory.
- Default sample stays the 60,000-event set; full set only to confirm.
- The machine must be stopped when not running a test; after each run check
  `gcloud compute instances list` shows it TERMINATED (stopped) within 30 min.

## Review and receipts

- Send Code Checker ("Code Checker 2"; check `ListAgents`) the idle-stop
  script, `gcp_run.sh`, and the IAM policy before using them; the S3 upload
  receipts before deleting laptop copies.
- Do not interrupt build 2's running D1; this setup is independent.
- Log: `research/hyperliquid/logs/gcp_setup.log`. Final report plain and
  short: machine details, idle-stop test result, cost per hour, laptop free
  space before/after, checker verdict.
