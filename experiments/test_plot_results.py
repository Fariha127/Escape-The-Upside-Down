"""Chart script: makes the PNG files from small hand-written summary CSVs (no games are played)."""
import csv
import os

import pytest

pytest.importorskip("matplotlib")
from experiments import plot_results as pr  # noqa: E402


def write(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def win_rows(*settings):
    return [{"setting": s, "games": 10, "win_rate": 0.8, "ci95_low": 0.49, "ci95_high": 0.94,
             "eleven_search_ms": 5.0 * (i + 1), "mf_search_ms": 1.0 * (i + 1)} for i, s in enumerate(settings)]


def test_split_name_handles_plain_and_date_tags():
    assert pr.split_name("x/mcts_final_summary.csv") == ("mcts", "final")
    assert pr.split_name("x/mf-effect_20261116_184506_summary.csv") == ("mf-effect", "20261116_184506")
    assert pr.split_name("x/sweep_mf_corrupt_duration_t_summary.csv") == ("sweep_mf_corrupt_duration", "t")


def test_budget_is_read_from_the_setting_name():
    assert pr.budget_of("eleven_150_sims") == 150 and pr.budget_of("mind_flayer_on") is None


def test_every_chart_kind_is_written(tmp_path):
    write(tmp_path / "mcts_t_summary.csv", win_rows("eleven_50_sims", "eleven_150_sims"))
    write(tmp_path / "mf-budget_t_summary.csv", win_rows("mf_25_sims", "mf_75_sims"))
    write(tmp_path / "sweep_mf_corrupt_duration_t_summary.csv", win_rows("MF_CORRUPT_DURATION=1", "MF_CORRUPT_DURATION=2"))
    write(tmp_path / "minimax_t_summary.csv", [
        {"depth": d, "positions": 4, "plain_visited": 50.0 * d, "ab_visited": 20.0 * d, "visited_saved_pct": 60.0,
         "plain_ms": 1.0 * d, "ab_ms": 0.5 * d, "same_move_and_score": "4/4"} for d in (2, 3)])
    out = tmp_path / "plots"
    assert pr.make_all(str(tmp_path), str(out)) == 6
    names = sorted(os.listdir(out))
    assert names == ["minimax_t.png", "time_mcts_t.png", "time_mf-budget_t.png", "winrate_mcts_t.png",
                     "winrate_mf-budget_t.png", "winrate_sweep_mf_corrupt_duration_t.png"]
    assert all(os.path.getsize(out / n) > 1000 for n in names)


def test_tag_filter_and_empty_folder(tmp_path):
    write(tmp_path / "mcts_a_summary.csv", win_rows("eleven_50_sims", "eleven_150_sims"))
    assert pr.make_all(str(tmp_path), str(tmp_path / "p"), tag="b") == 0
    assert pr.make_all(str(tmp_path / "nothing"), str(tmp_path / "p2")) == 0