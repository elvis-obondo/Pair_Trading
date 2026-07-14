import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from pair_analysis import analyze_top_pairs

if __name__ == "__main__":
    summary = analyze_top_pairs(start_date="2026-01-01")

    tradeable = summary[
        (summary["half_life_days"].between(0, 7)) &
        (summary["hurst"] < 0.5) &
        (summary["coint_stability"] >= 0.39) &
        (summary["beta_cv"] < 0.3)
    ]

    print("\n=== Tradeable Candidates ===")
    if tradeable.empty:
        print("None found.")
    else:
        print(tradeable[["ticker_a", "ticker_b", "half_life_days", "hurst", "coint_stability", "beta_cv"]].to_string(index=False))
        print(f"\nTotal: {len(tradeable)} pair(s)")
