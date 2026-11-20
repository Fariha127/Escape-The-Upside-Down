"""Tests for loop prevention in Eleven's AI (recency penalty, cycle detection, goal hysteresis)."""
import pytest
import config
from abilities import teleport
from ai.eleven_ai import ElevenAI
from ai.goals import Goal, GoalRun, Kind, safe_step_cost
from ai.navigation import Navigator
from ai.metrics import Metrics
from game.actions import Action
from game.state import GameState
from game.turn_manager import TurnManager


def test_safe_step_cost_penalizes_recent_positions():
    s = GameState.new_game()
    s.demogorgons = []  # no enemies
    p_prev = (1, 1)
    p_curr = (1, 2)
    cost_normal = safe_step_cost(s)(p_prev)
    cost_penalized = safe_step_cost(s, recent_positions=[p_prev])(p_prev)
    assert cost_penalized == cost_normal + config.RECENT_STEP_PENALTY


def test_is_looping_detects_2_cycle_and_3_cycle():
    ai = ElevenAI()
    assert not ai._is_looping()

    # Linear walk: no loop
    ai.pos_history = [(1, 1), (1, 2), (1, 3), (1, 4)]
    assert not ai._is_looping()

    # 2-cycle loop: A -> B -> A -> B
    ai.pos_history = [(1, 1), (1, 2), (1, 1), (1, 2)]
    assert ai._is_looping()

    # 3-cycle loop: A -> B -> C -> A -> B -> C
    ai.pos_history = [(1, 1), (1, 2), (1, 3), (1, 1), (1, 2), (1, 3)]
    assert ai._is_looping()


def test_loop_triggers_replan():
    s = GameState.new_game()
    tm = TurnManager(s)
    ai = ElevenAI(tm.metrics)
    ai.choose_turn(s)  # plan once
    ai.pos_history = [(1, 1), (1, 2), (1, 1), (1, 2)]
    assert ai._is_looping()
    assert ai._needs_replan(s)


def test_looping_with_teleport_triggers_breakout(monkeypatch):
    s = GameState.new_game()
    s.eleven_pos = (1, 2)
    s.visited.add((1, 1))
    s.visited.add((1, 2))
    s.visited.add((5, 5))
    s.unlocked_abilities.add("TELEPORT")
    s.ability_uses["TELEPORT"] = 1
    # Move enemies far away from (5,5)
    s.vecna.pos = (13, 13)
    for d in s.demogorgons:
        d.pos = (12, 12)

    ai = ElevenAI(simulations=20)
    ai.pos_history = [(1, 1), (1, 2), (1, 1)]
    choice = ai.choose_turn(s)
    assert choice.action == Action.USE_TELEPORT
    assert choice.target is not None
    assert not ai._is_looping()  # history cleared after breakout
