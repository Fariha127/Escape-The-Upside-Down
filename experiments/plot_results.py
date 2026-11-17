"""Charts for the report, drawn from the CSV files that run_batch.py writes.

Run from the project folder (needs matplotlib: pip install matplotlib):

    python experiments/plot_results.py                      # every *_summary.csv in experiments/results
    python experiments/plot_results.py --tag final          # only the files made with --tag final
    python experiments/plot_results.py --results some/folder --out some/other/folder

Charts (PNG, 200 dpi, saved in <results>/plots):
  winrate_<name>.png   win rate of Eleven per setting, with the 95% confidence interval as error bars
                       (mcts, mf-budget, mf-effect and every sweep)
  minimax_<tag>.png    Alpha-Beta against plain Minimax per depth: nodes visited (log scale) and time
  time_<name>.png      average search time against the simulation budget (mcts and mf-budget)

Every number in a chart is read from a CSV written by a real run. Nothing is estimated here."""
from __future__ import annotations

import argparse
import csv
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_RESULTS = os.path.join(ROOT, "experiments", "results")

try:
    import matplotlib
    matplotlib.use("Agg")                      # draw to files, no window needed
    import matplotlib.pyplot as plt
except ImportError:                            # pragma: no cover
    sys.exit("matplotlib is not installed. Run:  pip install matplotlib")

BLUE = "#2f6fb0"        # one color for "the thing measured"
ORANGE = "#d9822b"      # the comparison color (plain Minimax, or the second series)
GREY = "#5a5a5a"


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(text, default=0.0):
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def split_name(path):
    """'.../sweep_mf_corrupt_duration_final_summary.csv' -> ('sweep_mf_corrupt_duration', 'final')."""
    stem = os.path.basename(path)[: -len("_summary.csv")]
    stamp = re.search(r"_(\d{8}_\d{6})$", stem)           # the default tag is the date and time
    if stamp:
        return stem[: stamp.start()], stamp.group(1)
    name, _, tag = stem.rpartition("_")
    return name or stem, tag


def style(ax, title, xlabel, ylabel):
    ax.set_title(title, fontsize=12, loc="left", color="#222")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.25)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def save(fig, path):
    fig.tight_layout(rect=(0, 0.04, 1, 1))              # leave a strip at the bottom for the footnote
    fig.savefig(path, dpi=200)
    plt.close(fig)
    print("wrote", path)


# ---------------------------------------------------------------- win rate with error bars
def plot_winrate(rows, name, tag, out_dir):
    labels = [r["setting"] for r in rows]
    rate = [num(r["win_rate"]) for r in rows]
    low = [max(0.0, rate[i] - num(rows[i]["ci95_low"])) for i in range(len(rows))]
    high = [max(0.0, num(rows[i]["ci95_high"]) - rate[i]) for i in range(len(rows))]
    games = [int(num(r["games"])) for r in rows]
    fig, ax = plt.subplots(figsize=(max(5.5, 1.3 * len(rows) + 2.5), 4.2))
    xs = range(len(rows))
    ax.bar(xs, rate, color=BLUE, width=0.55, yerr=[low, high], capsize=5, ecolor=GREY)
    for x, r, n, h in zip(xs, rate, games, high):
        ax.text(x, min(1.0, r + h) + 0.02, f"{r * 100:.0f}%  (n={n})", ha="center", fontsize=9, color="#222")
    ax.set_xticks(list(xs))
    ax.set_xticklabels([l.replace("_", " ") for l in labels], rotation=0 if len(rows) <= 4 else 20,
                       ha="center" if len(rows) <= 4 else "right")
    ax.set_ylim(0, 1.12)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["0%", "25%", "50%", "75%", "100%"])
    style(ax, f"Eleven win rate: {name.replace('_', ' ')}", "", "Win rate")
    fig.text(0.01, 0.01, "Bars: win rate. Lines: 95% confidence interval (Wilson). Same seeds in every setting.",
             fontsize=8, color=GREY)
    save(fig, os.path.join(out_dir, f"winrate_{name}_{tag}.png"))


# ---------------------------------------------------------------- minimax: Alpha-Beta savings
def plot_minimax(rows, tag, out_dir):
    depths = [int(num(r["depth"])) for r in rows]
    plain_v = [num(r["plain_visited"]) for r in rows]
    ab_v = [num(r["ab_visited"]) for r in rows]
    saved = [num(r["visited_saved_pct"]) for r in rows]
    plain_t = [num(r["plain_ms"]) for r in rows]
    ab_t = [num(r["ab_ms"]) for r in rows]
    xs = list(range(len(rows)))
    w = 0.38
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.5, 4.4))
    a1.bar([x - w / 2 for x in xs], plain_v, w, color=ORANGE, label="Plain Minimax")
    a1.bar([x + w / 2 for x in xs], ab_v, w, color=BLUE, label="Alpha-Beta")
    for x, v, s in zip(xs, ab_v, saved):
        a1.text(x + w / 2, v * 1.15, f"-{s:.0f}%", ha="center", fontsize=9, color=BLUE)
    a1.set_yscale("log")
    a1.set_xticks(xs)
    a1.set_xticklabels([f"depth {d}" for d in depths])
    a1.legend(frameon=False)
    style(a1, "Nodes visited per search", "", "Nodes (log scale)")
    a2.bar([x - w / 2 for x in xs], plain_t, w, color=ORANGE, label="Plain Minimax")
    a2.bar([x + w / 2 for x in xs], ab_t, w, color=BLUE, label="Alpha-Beta")
    a2.set_xticks(xs)
    a2.set_xticklabels([f"depth {d}" for d in depths])
    a2.legend(frameon=False)
    style(a2, "Time per search", "", "Milliseconds")
    fig.text(0.01, 0.01, f"Same real positions for both modes. Same move and score in every position: "
             f"{', '.join(r['same_move_and_score'] for r in rows)} (per depth).", fontsize=8, color=GREY)
    save(fig, os.path.join(out_dir, f"minimax_{tag}.png"))


# ---------------------------------------------------------------- search time per budget
def budget_of(setting):
    m = re.search(r"(\d+)_sims", setting)
    return int(m.group(1)) if m else None


def plot_time(rows, name, tag, column, who, out_dir):
    points = [(budget_of(r["setting"]), num(r[column])) for r in rows if budget_of(r["setting"]) is not None]
    if len(points) < 2:
        return
    points.sort()
    fig, ax = plt.subplots(figsize=(5.8, 4.2))
    ax.plot([p[0] for p in points], [p[1] for p in points], marker="o", color=BLUE, linewidth=2)
    for b, t in points:
        ax.annotate(f"{t:.1f} ms", (b, t), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=9)
    ax.set_xticks([p[0] for p in points])
    ax.set_ylim(bottom=0)
    style(ax, f"{who} MCTS: time per search", "Simulations per search", "Average milliseconds")
    save(fig, os.path.join(out_dir, f"time_{name}_{tag}.png"))


# ---------------------------------------------------------------- driver
def make_all(results, out_dir, tag=None):
    os.makedirs(out_dir, exist_ok=True)
    files = sorted(glob.glob(os.path.join(results, "*_summary.csv")))
    made = 0
    for path in files:
        name, file_tag = split_name(path)
        if tag and file_tag != tag:
            continue
        rows = read_csv(path)
        if not rows:
            continue
        if "win_rate" in rows[0]:
            plot_winrate(rows, name, file_tag, out_dir)
            made += 1
            if name == "mcts":
                plot_time(rows, name, file_tag, "eleven_search_ms", "Eleven", out_dir)
                made += 1
            elif name == "mf-budget":
                plot_time(rows, name, file_tag, "mf_search_ms", "Mind Flayer", out_dir)
                made += 1
        elif "plain_visited" in rows[0]:
            plot_minimax(rows, file_tag, out_dir)
            made += 1
    if not made:
        print(f"no matching *_summary.csv files in {results} (run python experiments/run_batch.py first)")
    return made


def main(argv=None):
    p = argparse.ArgumentParser(description="Charts from the batch experiment CSV files.")
    p.add_argument("--results", default=DEFAULT_RESULTS, help="folder with the *_summary.csv files")
    p.add_argument("--out", default=None, help="folder for the PNG files (default: <results>/plots)")
    p.add_argument("--tag", default=None, help="only files made with this --tag")
    args = p.parse_args(argv)
    make_all(args.results, args.out or os.path.join(args.results, "plots"), args.tag)


if __name__ == "__main__":
    main()