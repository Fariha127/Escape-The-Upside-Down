"""The portal is closed to Eleven until the Mind Flayer is defeated."""
import config
from ai.navigation import Navigator
from game import rules
from game.actions import Action
from game.board_gen import generate_board
from game.state import GameState, Winner
from game.turn_manager import TurnManager


def next_to_portal():
    s = GameState.new_game()
    s.eleven_pos = (s.portal_pos[0] - 1, s.portal_pos[1])
    return s


def test_cannot_step_on_closed_portal():
    s = next_to_portal()
    assert not rules.can_eleven_enter(s, s.portal_pos)
    assert Action.MOVE_RIGHT not in rules.legal_eleven_actions(s)
    assert not rules.apply_eleven_action(s, Action.MOVE_RIGHT)
    assert s.eleven_pos != s.portal_pos


def test_can_step_on_portal_after_mind_flayer_defeated():
    s = next_to_portal()
    s.mind_flayer.defeated = True
    assert rules.can_eleven_enter(s, s.portal_pos)
    assert Action.MOVE_RIGHT in rules.legal_eleven_actions(s)


def test_win_still_needs_all_friends():
    s = next_to_portal()
    s.mind_flayer.defeated = True
    tm = TurnManager(s)
    tm.step(Action.MOVE_RIGHT)
    assert s.eleven_pos == s.portal_pos and s.winner == Winner.NONE


def test_enemies_are_not_affected():
    s = GameState.new_game()
    assert not s.is_blocked(s.portal_pos)


def test_astar_does_not_route_through_closed_portal():
    s = next_to_portal()
    far = (s.portal_pos[0] + 1, s.portal_pos[1])
    action, result = Navigator().next_action(s, far)
    assert s.portal_pos not in (result.path or [])


def test_generated_boards_keep_routes_without_the_portal():
    for seed in range(15):
        b = generate_board(seed)
        reach = b.reachable_from(b.eleven_start)
        assert b.portal in reach
