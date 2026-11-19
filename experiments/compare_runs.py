"""Compare two game-level CSV files game by game on matching seeds.

Usage:
    python experiments/compare_runs.py <file1.csv> <file2.csv>
"""
from __future__ import annotations

import csv
import sys


def load_games(path: str) -> dict[tuple[str, str], dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {(row.get("setting", ""), row["seed"]): row for row in reader}


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: python experiments/compare_runs.py <file1.csv> <file2.csv>")
        return 1

    f1, f2 = sys.argv[1], sys.argv[2]
    games1 = load_games(f1)
    games2 = load_games(f2)

    all_keys = sorted(
        set(games1.keys()) & set(games2.keys()),
        key=lambda k: (k[0], int(k[1]) if k[1].isdigit() else k[1]),
    )

    compare_cols = [
        "winner",
        "eleven_win",
        "turns",
        "hp",
        "power",
        "rescued",
        "mf_woke",
        "mf_defeated",
    ]

    diff_count = 0
    for key in all_keys:
        r1 = games1[key]
        r2 = games2[key]
        diffs = [
            f"{col}: {r1[col]} vs {r2[col]}"
            for col in compare_cols
            if col in r1 and col in r2 and r1[col] != r2[col]
        ]
        if diffs:
            diff_count += 1
            print(f"Game seed={key[1]} ({key[0]}): diff [{', '.join(diffs)}]")

    missing1 = set(games2.keys()) - set(games1.keys())
    missing2 = set(games1.keys()) - set(games2.keys())
    if missing1:
        print(f"Missing in {f1}: {len(missing1)} games")
        diff_count += len(missing1)
    if missing2:
        print(f"Missing in {f2}: {len(missing2)} games")
        diff_count += len(missing2)

    print(f"compared: {len(all_keys)}")
    print(f"different: {diff_count}")
    return 0 if diff_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
