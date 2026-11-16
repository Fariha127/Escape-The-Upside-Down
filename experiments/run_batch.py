"""Batch experiments for the report: plays many games without a window and saves the results as CSV.

Run from the project folder (the one that contains config.py):

    python experiments/run_batch.py smoke                          # 2 tiny games, checks that everything works
    python experiments/run_batch.py minimax --games 10             # Alpha-Beta vs plain Minimax, depths 2 to 5
    python experiments/run_batch.py mcts --games 20                # Eleven MCTS: 50, 150, 300, 600 simulations
    python experiments/run_batch.py mf-budget --games 20           # Mind Flayer MCTS: 25, 75, 150, 300 simulations
    python experiments/run_batch.py mf-effect --games 20           # Mind Flayer on versus off
    python experiments/run_batch.py sweep --param MF_CORRUPT_DURATION --values 1,2,3 --games 20

Useful options: --games N | --seed-start 1000 | --workers 4 | --tag mytest | --out experiments/results
                --eleven-sims N | --mf-sims N (budgets for the settings that do not sweep them)

How the numbers are produced
  * Every game is a full AI-vs-AI game with the normal rules and the normal AIs (A* for the
    Demogorgons, Minimax + Alpha-Beta for Vecna, MCTS for Eleven and the Mind Flayer).
  * All settings of one experiment use the SAME seeds (seed-start, seed-start + 1, ...), so the
    comparison between settings is paired and fair. The seed changes config.RNG_SEED, which seeds
    every MCTS search. The map and the rules are fixed, so games with different seeds are similar
    but not identical: report win rates as "x of N games" with the confidence interval printed here.
  * Config values are changed only while a game runs and are restored afterwards.
  * Each experiment writes <name>_<tag>_games.csv (one row per game or search), <name>_<tag>_summary.csv
    and <name>_<tag>_meta.json (the config values and the date, so the run can be reproduced).
  * Nothing here estimates anything: counters come from ai/metrics.py (real search runs)."""
from __future__ import annotations

import argparse
import contextlib
import csv
import inspect
import json
import math
import os
import platform
import sys
import time
import traceback
from collections import OrderedDict
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config  # noqa: E402
from ai.eleven_ai import ElevenAI  # noqa: E402
from ai.metrics import Metrics  # noqa: E402
from ai.mind_flayer_ai import MindFlayerAI  # noqa: E402
from ai.minimax import minimax_search  # noqa: E402
from ai.vecna_ai import VecnaAI  # noqa: E402
from game.actions import Action  # noqa: E402
from game.mind_flayer_rules import WAIT, MFAction  # noqa: E402
from game.state import GameState, Winner  # noqa: E402
from game.turn_manager import TurnManager  # noqa: E402

DEFAULT_OUT = os.path.join(ROOT, "experiments", "results")

GAME_FIELDS = [
    "experiment", "setting", "seed", "error",
    "eleven_win", "winner", "turns", "hp", "power", "rescued", "mf_woke", "mf_defeated", "game_seconds",
    "astar_searches", "astar_nodes",
    "minimax_searches", "minimax_visited", "minimax_evaluated", "minimax_pruned", "minimax_avg_ms",
    "eleven_mcts_searches", "eleven_mcts_sims", "eleven_mcts_nodes", "eleven_mcts_avg_ms",
    "mf_mcts_searches", "mf_mcts_sims", "mf_mcts_nodes", "mf_mcts_avg_ms",
]


# ---------------------------------------------------------------- helpers
@contextlib.contextmanager
def overrides(values):
    """Set config values for the duration of the block and restore them afterwards."""
    old = {}
    for name, value in values.items():
        if not hasattr(config, name):
            raise AttributeError(f"config.py has no setting called {name}")
        old[name] = getattr(config, name)
        setattr(config, name, value)
    try:
        yield
    finally:
        for name, value in old.items():
            setattr(config, name, value)


def parse_value(name, text):
    """Turn the text of --values into the same type as the current config value."""
    if not hasattr(config, name):
        raise SystemExit(f"config.py has no setting called {name}")
    current = getattr(config, name)
    if isinstance(current, bool):
        return text.strip().lower() in ("1", "true", "yes", "on")
    if isinstance(current, int):
        return int(text)
    if isinstance(current, float):
        return float(text)
    raise SystemExit(f"{name} is not a number or on/off value, so it cannot be swept here")


def wilson(wins, n, z=1.96):
    """95% confidence interval for a win rate (Wilson score interval)."""
    if n == 0:
        return 0.0, 0.0
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def mean(values):
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def new_state(seed):
    """A fresh game. If this version of GameState.new_game accepts a seed, it is passed on."""
    params = inspect.signature(GameState.new_game).parameters
    if "seed" in params:
        return GameState.new_game(seed=seed)
    return GameState.new_game()


class IdleMindFlayer:
    """Mind Flayer that only waits (used by the 'mind flayer off' setting)."""
    def choose_action(self, state):
        return MFAction(WAIT)


def _stats_row(m: Metrics):
    astar_calls = sum(s.calls for s in m.astar.values())
    astar_nodes = sum(s.nodes_explored for s in m.astar.values())
    mm = m.minimax
    el = m.mcts.get("eleven")
    mf = m.mcts.get("mind_flayer")
    return {
        "astar_searches": astar_calls, "astar_nodes": astar_nodes,
        "minimax_searches": mm.calls, "minimax_visited": mm.nodes_visited,
        "minimax_evaluated": mm.nodes_evaluated, "minimax_pruned": mm.branches_pruned,
        "minimax_avg_ms": round(mm.avg_time_ms, 4),
        "eleven_mcts_searches": el.calls if el else 0, "eleven_mcts_sims": el.simulations if el else 0,
        "eleven_mcts_nodes": el.nodes_created if el else 0,
        "eleven_mcts_avg_ms": round(el.avg_time_ms, 4) if el else 0,
        "mf_mcts_searches": mf.calls if mf else 0, "mf_mcts_sims": mf.simulations if mf else 0,
        "mf_mcts_nodes": mf.nodes_created if mf else 0,
        "mf_mcts_avg_ms": round(mf.avg_time_ms, 4) if mf else 0,
    }


# ---------------------------------------------------------------- one game
def play_game(job):
    """Play one full AI-vs-AI game and return one result row (a dict)."""
    values = dict(job.get("overrides", {}))
    values["RNG_SEED"] = job["seed"]
    with overrides(values):
        m = Metrics()
        state = new_state(job["seed"])
        if job.get("mind_flayer", True):
            mf_ai = MindFlayerAI(m, job.get("mf_sims"))
        else:
            mf_ai = IdleMindFlayer()
        tm = TurnManager(state, metrics=m, mind_flayer_ai=mf_ai,
                         vecna_ai=VecnaAI(m, job.get("vecna_depth"), job.get("alpha_beta")))
        eleven = ElevenAI(m, job.get("eleven_sims"))
        t0 = time.perf_counter()
        guard = config.MAX_TURNS + 10                    # a game always ends by itself; this only protects the batch
        while not state.game_over and guard > 0:
            guard -= 1
            choice = eleven.choose_turn(state)
            if not tm.step(choice.action, choice.target, choice.bonus_action):
                if not tm.step(choice.action, choice.target):
                    tm.step(Action.WAIT)
        seconds = time.perf_counter() - t0
        row = {
            "experiment": job["experiment"], "setting": job["setting"], "seed": job["seed"], "error": "",
            "eleven_win": int(state.winner == Winner.ELEVEN), "winner": state.winner.name if state.winner else "",
            "turns": state.turn, "hp": state.eleven_hp, "power": state.eleven_power,
            "rescued": len(state.rescued),
            "mf_woke": int(state.mind_flayer.active or state.mind_flayer.defeated),
            "mf_defeated": int(state.mind_flayer.defeated), "game_seconds": round(seconds, 3),
        }
        row.update(_stats_row(m))
        return row


def run_job(job):
    """Pool-friendly wrapper: a crashing game becomes a row with an error instead of stopping the batch."""
    try:
        return play_game(job)
    except Exception:                                    # noqa: BLE001
        last = traceback.format_exc().strip().splitlines()[-1]
        return {"experiment": job["experiment"], "setting": job["setting"], "seed": job["seed"], "error": last}


# ---------------------------------------------------------------- summaries and files
def summarise(rows, order=None):
    """One summary row per setting. `order` is the list of setting names as the experiment defined them
    (games can finish in any order when several workers run, so the table must not depend on that)."""
    groups = OrderedDict((name, []) for name in (order or []))
    for r in rows:
        groups.setdefault(r["setting"], []).append(r)
    groups = OrderedDict((k, v) for k, v in groups.items() if v)
    out = []
    for setting, rs in groups.items():
        ok = [r for r in rs if not r["error"]]
        wins = sum(r["eleven_win"] for r in ok)
        lo, hi = wilson(wins, len(ok))
        out.append(OrderedDict([
            ("setting", setting), ("games", len(ok)), ("errors", len(rs) - len(ok)), ("wins", wins),
            ("win_rate", round(wins / len(ok), 3) if ok else 0.0),
            ("ci95_low", round(lo, 3)), ("ci95_high", round(hi, 3)),
            ("avg_turns", round(mean(r["turns"] for r in ok), 1)),
            ("avg_rescued", round(mean(r["rescued"] for r in ok), 2)),
            ("mf_woke_rate", round(mean(r["mf_woke"] for r in ok), 3)),
            ("mf_defeated_rate", round(mean(r["mf_defeated"] for r in ok), 3)),
            ("eleven_search_ms", round(mean(r["eleven_mcts_avg_ms"] for r in ok), 2)),
            ("mf_search_ms", round(mean(r["mf_mcts_avg_ms"] for r in ok if r["mf_mcts_searches"]), 2)),
            ("minimax_ms", round(mean(r["minimax_avg_ms"] for r in ok), 3)),
            ("game_seconds", round(mean(r["game_seconds"] for r in ok), 1)),
        ]))
    return out


def print_table(rows, columns=None):
    if not rows:
        print("(no rows)")
        return
    columns = columns or list(rows[0].keys())
    widths = [max(len(str(c)), *(len(str(r[c])) for r in rows)) for c in columns]
    print("  ".join(str(c).ljust(w) for c, w in zip(columns, widths)))
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print("  ".join(str(r[c]).ljust(w) for c, w in zip(columns, widths)))


def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def write_meta(path, args, extra=None):
    snapshot = {}
    for name in dir(config):
        if name.isupper():
            value = getattr(config, name)
            snapshot[name] = list(value) if isinstance(value, tuple) else value
    meta = {"date": datetime.now().isoformat(timespec="seconds"), "python": platform.python_version(),
            "command": " ".join(sys.argv), "config": snapshot}
    meta.update(extra or {})
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, default=str)


def make_paths(args, name):
    os.makedirs(args.out, exist_ok=True)
    tag = args.tag or datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = os.path.join(args.out, f"{name}_{tag}")
    return stem + "_games.csv", stem + "_summary.csv", stem + "_meta.json"


# ---------------------------------------------------------------- running a list of jobs
def run_jobs(jobs, workers, games_path):
    """Run the jobs (in parallel when workers > 1); every finished game is written to the CSV at once,
    so an interrupted batch keeps what it has."""
    rows = []
    total = len(jobs)
    started = time.perf_counter()
    with open(games_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=GAME_FIELDS, extrasaction="ignore")
        writer.writeheader()

        def accept(row, i):
            rows.append(row)
            writer.writerow(row)
            f.flush()
            if row["error"]:
                note = "ERROR " + row["error"]
            else:
                note = ("WIN " if row["eleven_win"] else "LOSS") + f" turns {row['turns']} ({row['game_seconds']:.1f}s)"
            print(f"[{i}/{total}] {row['setting']} seed {row['seed']}: {note}", flush=True)

        if workers > 1:
            import multiprocessing
            with multiprocessing.Pool(workers) as pool:
                for i, row in enumerate(pool.imap_unordered(run_job, jobs), 1):
                    accept(row, i)
        else:
            for i, job in enumerate(jobs, 1):
                accept(run_job(job), i)
    print(f"finished {total} games in {time.perf_counter() - started:.0f} s")
    return rows


def build_jobs(experiment, settings, args):
    """settings: list of (label, job fields). Every setting plays the same seeds."""
    jobs = []
    for label, fields in settings:
        for i in range(args.games):
            job = {"experiment": experiment, "setting": label, "seed": args.seed_start + i,
                   "eleven_sims": args.eleven_sims, "mf_sims": args.mf_sims}
            job.update(fields)
            jobs.append(job)
    return jobs


def run_game_experiment(name, settings, args):
    games_path, summary_path, meta_path = make_paths(args, name)
    jobs = build_jobs(name, settings, args)
    print(f"{name}: {len(settings)} settings x {args.games} games = {len(jobs)} games, workers {args.workers}")
    rows = run_jobs(jobs, args.workers, games_path)
    summary = summarise(rows, [label for label, _ in settings])
    write_csv(summary_path, summary, list(summary[0].keys()) if summary else ["setting"])
    write_meta(meta_path, args, {"settings": [label for label, _ in settings]})
    print()
    print_table(summary, ["setting", "games", "errors", "win_rate", "ci95_low", "ci95_high", "avg_turns",
                          "avg_rescued", "mf_defeated_rate", "eleven_search_ms", "mf_search_ms", "game_seconds"])
    print(f"\nfiles:\n  {games_path}\n  {summary_path}\n  {meta_path}")
    return rows


# ---------------------------------------------------------------- the experiments
def exp_mcts(args):
    sims = args.sims or [50, 150, 300, 600]
    return run_game_experiment("mcts", [(f"eleven_{n}_sims", {"eleven_sims": n}) for n in sims], args)


def exp_mf_budget(args):
    sims = args.sims or [25, 75, 150, 300]
    return run_game_experiment("mf-budget", [(f"mf_{n}_sims", {"mf_sims": n}) for n in sims], args)


def exp_mf_effect(args):
    return run_game_experiment("mf-effect", [("mind_flayer_off", {"mind_flayer": False}),
                                             ("mind_flayer_on", {"mind_flayer": True})], args)


def exp_sweep(args):
    if not args.param or not args.values:
        raise SystemExit("sweep needs --param NAME and --values a,b,c (example: --param MF_CORRUPT_DURATION --values 1,2,3)")
    values = [parse_value(args.param, v) for v in args.values.split(",")]
    settings = [(f"{args.param}={v}", {"overrides": {args.param: v}}) for v in values]
    return run_game_experiment("sweep_" + args.param.lower(), settings, args)


def exp_smoke(args):
    """Two tiny games: proves the batch runner, the CSV writing and the summary all work."""
    args.games, args.out = 2, args.out
    args.eleven_sims, args.mf_sims = 15, 15
    return run_game_experiment("smoke", [("tiny", {"vecna_depth": 2})], args)


def collect_positions(args):
    """Play a few quick games and keep a copy of the state every few turns (positions for the Minimax test)."""
    positions = []
    for g in range(args.games):
        seed = args.seed_start + g
        with overrides({"RNG_SEED": seed}):
            m = Metrics()
            state = new_state(seed)
            tm = TurnManager(state, metrics=m)
            eleven = ElevenAI(m, 40)
            guard = config.MAX_TURNS + 10
            while not state.game_over and guard > 0:
                guard -= 1
                if state.turn % args.every == 0 and not state.vecna.is_frozen:
                    positions.append((seed, state.turn, state.clone()))
                choice = eleven.choose_turn(state)
                if not tm.step(choice.action, choice.target, choice.bonus_action):
                    if not tm.step(choice.action, choice.target):
                        tm.step(Action.WAIT)
    return positions


def exp_minimax(args):
    """Alpha-Beta against plain Minimax on the same real positions, for several depths."""
    games_path, summary_path, meta_path = make_paths(args, "minimax")
    depths = args.depths or [2, 3, 4, 5]
    print(f"minimax: collecting positions from {args.games} games (one every {args.every} turns) ...", flush=True)
    positions = collect_positions(args)
    print(f"minimax: {len(positions)} positions x depths {depths} x 2 modes")
    fields = ["seed", "turn", "depth", "mode", "action", "score", "nodes_visited", "nodes_evaluated",
              "branches_pruned", "time_ms"]
    rows = []
    with open(games_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for seed, turn, state in positions:
            for depth in depths:
                for mode, use_ab in (("plain", False), ("alpha_beta", True)):
                    r = minimax_search(state, depth, use_ab)
                    row = {"seed": seed, "turn": turn, "depth": depth, "mode": mode, "action": r.action.value,
                           "score": round(r.score, 4), "nodes_visited": r.nodes_visited,
                           "nodes_evaluated": r.nodes_evaluated, "branches_pruned": r.branches_pruned,
                           "time_ms": round(r.time_ms, 4)}
                    rows.append(row)
                    writer.writerow(row)
    summary = []
    for depth in depths:
        plain = [r for r in rows if r["depth"] == depth and r["mode"] == "plain"]
        ab = [r for r in rows if r["depth"] == depth and r["mode"] == "alpha_beta"]
        same = sum(1 for p, a in zip(plain, ab) if p["action"] == a["action"] and p["score"] == a["score"])
        pv, av = mean(r["nodes_visited"] for r in plain), mean(r["nodes_visited"] for r in ab)
        pt, at = mean(r["time_ms"] for r in plain), mean(r["time_ms"] for r in ab)
        summary.append(OrderedDict([
            ("depth", depth), ("positions", len(plain)),
            ("plain_visited", round(pv, 1)), ("ab_visited", round(av, 1)),
            ("visited_saved_pct", round(100 * (1 - av / pv), 1) if pv else 0.0),
            ("plain_evaluated", round(mean(r["nodes_evaluated"] for r in plain), 1)),
            ("ab_evaluated", round(mean(r["nodes_evaluated"] for r in ab), 1)),
            ("ab_pruned", round(mean(r["branches_pruned"] for r in ab), 1)),
            ("plain_ms", round(pt, 3)), ("ab_ms", round(at, 3)),
            ("speedup", round(pt / at, 2) if at else 0.0),
            ("same_move_and_score", f"{same}/{len(plain)}"),
        ]))
    write_csv(summary_path, summary, list(summary[0].keys()) if summary else ["depth"])
    write_meta(meta_path, args, {"depths": depths, "positions": len(positions)})
    print()
    print_table(summary)
    print(f"\nfiles:\n  {games_path}\n  {summary_path}\n  {meta_path}")
    return rows


EXPERIMENTS = {
    "smoke": exp_smoke, "minimax": exp_minimax, "mcts": exp_mcts,
    "mf-budget": exp_mf_budget, "mf-effect": exp_mf_effect, "sweep": exp_sweep,
}


def int_list(text):
    return [int(x) for x in text.split(",") if x.strip()]


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Batch experiments for Escape the Upside Down (see the top of this file).")
    p.add_argument("experiment", choices=sorted(EXPERIMENTS))
    p.add_argument("--games", type=int, default=20, help="games per setting (minimax: games used to collect positions)")
    p.add_argument("--seed-start", type=int, default=1000, help="first game seed; game i uses seed-start + i")
    p.add_argument("--workers", type=int, default=1, help="games played in parallel (1 = one at a time)")
    p.add_argument("--eleven-sims", type=int, default=None, help="Eleven MCTS simulations (default: config)")
    p.add_argument("--mf-sims", type=int, default=None, help="Mind Flayer MCTS simulations (default: config)")
    p.add_argument("--sims", type=int_list, default=None, help="list for mcts / mf-budget, for example 50,150,300")
    p.add_argument("--depths", type=int_list, default=None, help="minimax depths, for example 2,3,4,5")
    p.add_argument("--every", type=int, default=8, help="minimax: keep a position every N turns")
    p.add_argument("--param", default=None, help="sweep: the config setting to change, for example MF_CORRUPT_DURATION")
    p.add_argument("--values", default=None, help="sweep: comma separated values, for example 1,2,3")
    p.add_argument("--tag", default=None, help="name added to the file names (default: date and time)")
    p.add_argument("--out", default=DEFAULT_OUT, help="folder for the CSV files")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    EXPERIMENTS[args.experiment](args)


if __name__ == "__main__":
    main()