"""Eleven loses when she is boxed in with no way out for STUCK_TURNS_LIMIT turns in a row."""
import config
from game.rules import is_eleven_trapped, check_win_loss
from game.state import GameState, Winner


def boxed_in():
    """Eleven with all four neighbour cells blocked, no power to attack and no teleport left."""
    s = GameState.new_game()
    x, y = s.eleven_pos
    s.eleven_power = 0
    s.ability_uses["TELEPORT"] = 0
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        s.corrupted[(x + dx, y + dy)] = 99
    return s


def test_open_start_is_not_trapped():
    assert not is_eleven_trapped(GameState.new_game())


def test_boxed_in_eleven_is_trapped():
    assert is_eleven_trapped(boxed_in())


def test_loses_after_limit_turns_in_a_row():
    s = boxed_in()
    for i in range(config.STUCK_TURNS_LIMIT - 1):
        check_win_loss(s)
        assert not s.game_over
        s.turn += 1
    check_win_loss(s)
    assert s.winner == Winner.ENEMIES and "trapped" in s.event_log[-1]


def test_counter_resets_when_a_way_out_appears():
    s = boxed_in()
    check_win_loss(s)
    assert s.stuck_turns == 1
    fresh = GameState.new_game()
    fresh.stuck_turns = 2
    check_win_loss(fresh)
    assert fresh.stuck_turns == 0 and not fresh.game_over


def test_clone_keeps_counter():
    s = GameState.new_game()
    s.stuck_turns = 2
    assert s.clone().stuck_turns == 2