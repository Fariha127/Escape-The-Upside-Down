"""Phase 9 balance: Eleven rescues Will (who wakes the Mind Flayer) last."""
import re

import pytest

import config
from ai.goals import Goal, Kind, applicable_goals
from game.state import GameState
from ui.session import ai_turn, new_game


def rescue_goals(s):
    return [g.arg for g in applicable_goals(s) if g.kind == Kind.RESCUE]


def test_will_is_not_offered_while_other_friends_are_unrescued():
    s = GameState.new_game()
    assert rescue_goals(s) == ["Mike", "Dustin", "Lucas"]


def test_will_is_offered_once_the_other_three_are_rescued():
    s = GameState.new_game()
    s.rescued.update({"Mike", "Dustin"})
    assert rescue_goals(s) == ["Lucas"]
    s.rescued.add("Lucas")
    assert rescue_goals(s) == ["Will"]


def test_switch_off_restores_every_friend_as_a_goal(monkeypatch):
    monkeypatch.setattr(config, "ELEVEN_RESCUE_WILL_LAST", False)
    assert rescue_goals(GameState.new_game()) == ["Mike", "Dustin", "Lucas", "Will"]


def test_will_goal_never_blocks_other_goals():
    s = GameState.new_game()
    kinds = {g.kind for g in applicable_goals(s)}
    assert Kind.EVADE in kinds and Kind.RESCUE in kinds


@pytest.mark.parametrize("seed", [5000, 5001, 5002, 5003])
def test_in_real_games_will_is_rescued_after_the_other_friends(seed, monkeypatch):
    monkeypatch.setattr(config, "RNG_SEED", seed)
    state, tm, ai = new_game()
    while not state.game_over:
        ai_turn(state, tm, ai)
    order = [m.group(1) for l in state.event_log if (m := re.search(r"Rescued (\w+)", l))]
    if "Will" in order:
        assert order[-1] == "Will", order
