"""The gate is closed to Eleven until the Mind Flayer is defeated."""
import config
import pygame
from ai.navigation import Navigator
from game import rules
from game.actions import Action
from game.board_gen import generate_board
from game.state import GameState, Winner
from game.turn_manager import TurnManager
from ui.session import GameSession


def next_to_gate():
    s = GameState.new_game()
    s.eleven_pos = (s.gate_pos[0] - 1, s.gate_pos[1])
    return s


def test_cannot_step_on_closed_gate():
    s = next_to_gate()
    assert not rules.can_eleven_enter(s, s.gate_pos)
    assert Action.MOVE_RIGHT not in rules.legal_eleven_actions(s)
    assert not rules.apply_eleven_action(s, Action.MOVE_RIGHT)
    assert s.eleven_pos != s.gate_pos


def test_can_step_on_gate_after_mind_flayer_defeated_and_friends_rescued():
    s = next_to_gate()
    s.mind_flayer.defeated = True
    s.rescued.update(s.friend_positions)
    assert rules.can_eleven_enter(s, s.gate_pos)
    assert Action.MOVE_RIGHT in rules.legal_eleven_actions(s)


def test_gate_stays_closed_while_a_friend_is_missing():
    s = next_to_gate()
    s.mind_flayer.defeated = True
    assert not rules.can_eleven_enter(s, s.gate_pos)
    tm = TurnManager(s)
    tm.step(Action.MOVE_RIGHT)
    assert s.eleven_pos != s.gate_pos and s.winner == Winner.NONE


def test_enemies_are_not_affected():
    s = GameState.new_game()
    assert not s.is_blocked(s.gate_pos)


def test_astar_does_not_route_through_closed_gate():
    s = next_to_gate()
    far = (s.gate_pos[0] + 1, s.gate_pos[1])
    action, result = Navigator().next_action(s, far)
    assert s.gate_pos not in (result.path or [])


def test_generated_boards_keep_routes_without_the_gate():
    for seed in range(15):
        b = generate_board(seed)
        reach = b.reachable_from(b.eleven_start)
        assert b.gate in reach

def test_walking_into_the_closed_gate_shows_a_message():
    session = GameSession()
    s = session.state
    s.eleven_pos = (s.gate_pos[0] - 1, s.gate_pos[1])
    session.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d))
    assert s.eleven_pos != s.gate_pos
    assert "gate is closed" in session.message
