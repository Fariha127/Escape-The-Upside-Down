"""Batch experiment runner: helpers, one tiny real game, result files."""
import csv
import os

import pytest

import config
from experiments import run_batch as rb


def tiny_job(seed=1, **fields):
    job = {"experiment": "t", "setting": "tiny", "seed": seed, "eleven_sims": 10, "mf_sims": 10, "vecna_depth": 2}
    job.update(fields)
    return job


# ------------------------------------------------------------------ helpers
def test_overrides_change_and_restore_config_values():
    before = (config.MF_CORRUPT_DURATION, config.RNG_SEED)
    with rb.overrides({"MF_CORRUPT_DURATION": 7, "RNG_SEED": 5}):
        assert (config.MF_CORRUPT_DURATION, config.RNG_SEED) == (7, 5)
    assert (config.MF_CORRUPT_DURATION, config.RNG_SEED) == before


def test_overrides_restore_even_after_an_error_and_reject_unknown_names():
    before = config.MF_CORRUPT_DURATION
    with pytest.raises(RuntimeError):
        with rb.overrides({"MF_CORRUPT_DURATION": 9}):
            raise RuntimeError("boom")
    assert config.MF_CORRUPT_DURATION == before
    with pytest.raises(AttributeError):
        with rb.overrides({"NO_SUCH_SETTING": 1}):
            pass


def test_parse_value_follows_the_type_of_the_config_value():
    assert rb.parse_value("MF_CORRUPT_DURATION", "3") == 3 and isinstance(rb.parse_value("MF_CORRUPT_DURATION", "3"), int)
    assert isinstance(rb.parse_value("MCTS_EXPLORATION", "1.5"), float)
    assert rb.parse_value("VECNA_USE_ALPHA_BETA", "false") is False and rb.parse_value("VECNA_USE_ALPHA_BETA", "true") is True
    with pytest.raises(SystemExit):
        rb.parse_value("NO_SUCH_SETTING", "1")


def test_wilson_interval_is_sane():
    assert rb.wilson(0, 0) == (0.0, 0.0)
    lo, hi = rb.wilson(10, 20)
    assert lo < 0.5 < hi and 0 <= lo and hi <= 1
    lo0, hi0 = rb.wilson(0, 20)
    assert lo0 == 0.0 and 0 < hi0 < 0.2
    lo1, hi1 = rb.wilson(20, 20)
    assert hi1 == 1.0 and 0.8 < lo1 < 1


def test_every_setting_plays_the_same_seeds():
    class A:
        games, seed_start, eleven_sims, mf_sims = 3, 100, None, None
    jobs = rb.build_jobs("x", [("a", {}), ("b", {"mf_sims": 5})], A)
    assert [(j["setting"], j["seed"]) for j in jobs] == [("a", 100), ("a", 101), ("a", 102),
                                                         ("b", 100), ("b", 101), ("b", 102)]
    assert jobs[3]["mf_sims"] == 5 and jobs[0]["mf_sims"] is None


def test_summary_counts_wins_errors_and_keeps_the_given_order():
    def row(setting, win, error=""):
        return {"setting": setting, "error": error, "eleven_win": win, "turns": 50, "rescued": 2, "mf_woke": 1,
                "mf_defeated": win, "eleven_mcts_avg_ms": 3.0, "mf_mcts_avg_ms": 1.0, "mf_mcts_searches": 4,
                "minimax_avg_ms": 0.5, "game_seconds": 1.0}
    rows = [row("b", 1), row("a", 0), row("a", 1), row("a", 1, error="crash"), row("b", 0)]
    out = rb.summarise(rows, ["a", "b"])
    assert [r["setting"] for r in out] == ["a", "b"]
    a = out[0]
    assert (a["games"], a["errors"], a["wins"], a["win_rate"]) == (2, 1, 1, 0.5)
    assert out[1]["games"] == 2 and out[1]["wins"] == 1


# ------------------------------------------------------------------ one real game
def test_a_game_row_is_complete_and_consistent():
    before = (config.RNG_SEED, config.MF_CORRUPT_DURATION)
    row = rb.run_job(tiny_job(seed=3))
    assert (config.RNG_SEED, config.MF_CORRUPT_DURATION) == before
    assert row["error"] == ""
    for field in rb.GAME_FIELDS:
        assert field in row, field
    assert row["winner"] in ("ELEVEN", "ENEMIES") and row["eleven_win"] == int(row["winner"] == "ELEVEN")
    assert 1 <= row["turns"] <= config.MAX_TURNS and 0 <= row["rescued"] <= 4
    assert row["astar_searches"] > 0 and row["minimax_searches"] > 0 and row["eleven_mcts_searches"] > 0
    assert row["eleven_mcts_sims"] == 10 * row["eleven_mcts_searches"]          # counters come from the real searches
    assert row["mf_mcts_sims"] == 10 * row["mf_mcts_searches"]


def test_the_same_seed_gives_the_same_game():
    a, b = rb.run_job(tiny_job(seed=4)), rb.run_job(tiny_job(seed=4))
    for field in ("winner", "turns", "hp", "power", "rescued", "astar_nodes", "minimax_visited", "eleven_mcts_nodes"):
        assert a[field] == b[field], field


def test_mind_flayer_off_never_searches():
    row = rb.run_job(tiny_job(seed=2, mind_flayer=False))
    assert row["error"] == "" and row["mf_mcts_searches"] == 0


def test_a_crashing_game_becomes_an_error_row_not_a_crash():
    row = rb.run_job(tiny_job(overrides={"NO_SUCH_SETTING": 1}))
    assert "NO_SUCH_SETTING" in row["error"] and "eleven_win" not in row


# ------------------------------------------------------------------ experiments and files
def make_args(tmp_path, **kw):
    argv = ["smoke", "--out", str(tmp_path), "--tag", "test"]
    for k, v in kw.items():
        argv += [f"--{k.replace('_', '-')}", str(v)]
    return rb.parse_args(argv)


def test_smoke_writes_three_files(tmp_path):
    rb.exp_smoke(make_args(tmp_path))
    names = sorted(os.listdir(tmp_path))
    assert names == ["smoke_test_games.csv", "smoke_test_meta.json", "smoke_test_summary.csv"]
    with open(tmp_path / "smoke_test_games.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2 and {r["seed"] for r in rows} == {"1000", "1001"}


def test_minimax_experiment_alpha_beta_agrees_with_plain(tmp_path):
    args = rb.parse_args(["minimax", "--games", "1", "--every", "25", "--depths", "2,3", "--out", str(tmp_path),
                          "--tag", "mm"])
    rows = rb.exp_minimax(args)
    assert rows
    plain = [r for r in rows if r["mode"] == "plain"]
    ab = [r for r in rows if r["mode"] == "alpha_beta"]
    assert len(plain) == len(ab)
    for p, a in zip(plain, ab):
        assert (p["action"], p["score"]) == (a["action"], a["score"])
        assert a["nodes_visited"] <= p["nodes_visited"]
    with open(tmp_path / "minimax_mm_summary.csv", newline="") as f:
        summary = list(csv.DictReader(f))
    assert [r["depth"] for r in summary] == ["2", "3"]
    assert all(r["same_move_and_score"] == f"{r['positions']}/{r['positions']}" for r in summary)


def test_sweep_needs_a_param_and_values(tmp_path):
    with pytest.raises(SystemExit):
        rb.exp_sweep(rb.parse_args(["sweep", "--out", str(tmp_path)]))