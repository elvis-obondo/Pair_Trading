"""Step 2 scope check (docs/prompts/REPO_CLEANUP.md, "Step 2 approval"/"Step 2 narrowed"): before
deleting items 3 (OKX data) and 4 (the freqtrade/OKX trading mechanism), list exactly what they cover
and prove nothing in the Hyperliquid research path uses it. Deletes nothing -- read-only.

    python3 -u scripts/step2_okx_trading_scope.py > research/dataset/logs/step2_okx_trading_scope.log
"""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(cmd, cwd=ROOT):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True).stdout


def git_grep(needle, paths):
    out = subprocess.run(["git", "grep", "-n", "-F", needle, "--"] + paths, cwd=ROOT,
                          capture_output=True, text=True)
    return [l for l in out.stdout.splitlines() if l]


def size(path):
    full = os.path.join(ROOT, path)
    if os.path.isfile(full):
        return os.path.getsize(full)
    total = 0
    for dp, _, fns in os.walk(full):
        for fn in fns:
            fp = os.path.join(dp, fn)
            if os.path.isfile(fp):
                total += os.path.getsize(fp)
    return total


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}B"
        n /= 1024
    return f"{n:.1f}TB"


HL_PATHS = ["research", "scripts/gcp_run.sh", "scripts/gcp_provision.sh", "scripts/gcp_idle_stop.sh",
            "docs/prompts/HL_BUILD1_BARS_AND_DISLOCATIONS.md", "docs/prompts/HL_BUILD2_TRADES_TO_BARS_AND_FLOW.md",
            "docs/prompts/HL_BUILD3_FLOW_FEATURES_H1_H2_H3.md", "docs/prompts/HL_BUILD4_COIN_LEVEL_EVENT_STUDY.md",
            "docs/prompts/HL_BUILD4B_ROLLING_RERUN.md", "docs/prompts/HL_BUILD5_WALLET_TABLE.md",
            "docs/prompts/HL_BUILD6_FULL_POPULATION.md", "docs/prompts/HL_BUILD7_MASTER_DATASET.md"]


def check(label, path, needle=None):
    needle = needle or os.path.basename(path.rstrip("/"))
    hits = git_grep(needle, HL_PATHS)
    print(f"[STEP2-SCOPE] {label}: `{path}` | {human(size(path))} | "
          f"`git grep -n -F \"{needle}\"` over the Hyperliquid path -> {len(hits)} hit(s)")
    for h in hits:
        print(f"[STEP2-SCOPE]     HL-PATH HIT: {h}")
    return hits


def main():
    print("[STEP2-SCOPE] === Item 3: OKX data ===")
    for p in ("attic/okx_data", "attic/vm_final"):
        check("item-3 candidate", p)
    other_okx = run(["find", ".", "-iname", "*okx_datasets*", "-not", "-path", "./.git/*"])
    print(f"[STEP2-SCOPE] attic/okx_datasets (297MB per research/hyperliquid/logs/build1_a2_files.log, "
          f"already S3-verified per gcp_setup.log) present on THIS machine: "
          f"{'yes' if other_okx.strip() else 'no -- not found locally, nothing more to delete here'}")

    print("[STEP2-SCOPE] === Item 4: freqtrade/OKX trading mechanism ===")
    for p, needle in (("user_data/config.json", "config.json"),
                       ("user_data/config_backfill.json", "config_backfill.json"),
                       ("user_data/config_slow.json", "config_slow.json"),
                       ("user_data/strategies/sample_strategy.py", "sample_strategy"),
                       ("user_data/hyperopts/sample_hyperopt_loss.py", "sample_hyperopt_loss"),
                       ("user_data/notebooks/strategy_analysis_example.ipynb", "strategy_analysis_example"),
                       (".github/scripts/wake_streamlit.py", "wake_streamlit")):
        check("item-4 candidate (freqtrade-only, no HL hit expected)", p, needle)
    for p in ("user_data/backtest_results", "user_data/freqaimodels", "user_data/hyperopt_results",
              "user_data/logs", "user_data/plot"):
        print(f"[STEP2-SCOPE] item-4 candidate (empty freqtrade scaffold dir): `{p}` | "
              f"{human(size(p))} | {len(os.listdir(os.path.join(ROOT, p)))} entries")

    print("[STEP2-SCOPE] === user_data/data and user_data/normalized: NOT item-4 candidates ===")
    for p, needle in (("user_data/data", "user_data/data"), ("user_data/normalized", "user_data/normalized")):
        hits = check("LIVE HYPERLIQUID DATA -- excluded from item 4", p, needle)
        print(f"[STEP2-SCOPE]   -> {len(hits)} Hyperliquid-path reference(s) found; KEEP, not OKX/trading-only.")

    print("[STEP2-SCOPE] === Dockerfile.trading / docker-compose*.yml / APE_DOGE_Spread_Trade.docx ===")
    for fn in ("Dockerfile.trading", "docker-compose.trading.yml", "docker-compose.yml",
               "APE_DOGE_Spread_Trade.docx"):
        exists = os.path.exists(os.path.join(ROOT, fn))
        print(f"[STEP2-SCOPE] `{fn}` present: {exists}")

    print("[STEP2-SCOPE] === logs/scanner.*.log (untracked, top-level) ===")
    for fn in ("logs/scanner.err.log", "logs/scanner.out.log"):
        full = os.path.join(ROOT, fn)
        print(f"[STEP2-SCOPE] `{fn}` present: {os.path.exists(full)}, "
              f"{human(size(fn)) if os.path.exists(full) else '-'}")
    print("[STEP2-SCOPE] ALL DONE")


if __name__ == "__main__":
    main()
