import config
from game.actions import Action
from game.board import Board, Terrain
from game.rules import legal_eleven_actions, apply_eleven_action, check_win_loss
from game.state import GameState, Winner
from game.turn_manager import TurnManager


def test_default_map_valid_and_sized():
    b = Board.default()
    b.validate()
    assert (b.width, b.height) == (config.GRID_SIZE, config.GRID_SIZE)
    assert len(b.demogorgon_starts) == 6


def test_border_is_walled_and_unreachable_detected():
    b = Board.default()
    assert all(b.terrain_at((x, 0)) == Terrain.WALL for x in range(b.width))
    bad = Board(["#####", "#E#P#", "#V#.#", "#####", "#####"])
    try:
        bad.validate(); assert False
    except ValueError:
        pass


def test_cannot_walk_through_walls_or_off_map():
    s = GameState.new_game()          # Eleven at (1,1): wall above and left
    acts = legal_eleven_actions(s)
    assert Action.MOVE_UP not in acts and Action.MOVE_LEFT not in acts
    assert Action.MOVE_RIGHT in acts and Action.MOVE_DOWN in acts and Action.WAIT in acts
    assert apply_eleven_action(s, Action.MOVE_UP) is False
    assert s.eleven_pos == (1, 1)


def test_movement_is_four_directional_and_tracks_visited():
    s = GameState.new_game()
    apply_eleven_action(s, Action.MOVE_RIGHT)
    assert s.eleven_pos == (2, 1) and (2, 1) in s.visited


def test_enemies_and_corruption_block_movement():
    s = GameState.new_game()
    s.demogorgons[0].pos = (2, 1)
    assert Action.MOVE_RIGHT not in legal_eleven_actions(s)
    s.demogorgons[0].pos = (9, 1)
    s.corrupted[(2, 1)] = 3
    assert Action.MOVE_RIGHT not in legal_eleven_actions(s)


def test_clone_is_independent():
    s = GameState.new_game()
    c = s.clone()
    c.eleven_pos = (3, 3); c.eleven_hp = 1
    c.demogorgons[0].alive = False; c.rescued.add("Mike"); c.corrupted[(5, 5)] = 2
    c.visited.add((9, 9)); c.vecna.pos = (1, 1); c.mind_flayer.active = True
    assert s.eleven_pos == (1, 1) and s.eleven_hp == config.MAX_HP
    assert s.demogorgons[0].alive and not s.rescued and not s.corrupted
    assert (9, 9) not in s.visited and s.vecna.pos != (1, 1) and not s.mind_flayer.active
    assert c.board is s.board   # immutable board shared


def test_illegal_action_does_not_advance_turn():
    s = GameState.new_game(); tm = TurnManager(s)
    assert tm.step(Action.MOVE_UP) is False and s.turn == 0


def test_turn_advances_on_legal_action():
    s = GameState.new_game(); tm = TurnManager(s)
    assert tm.step(Action.MOVE_RIGHT) and s.turn == 1 and s.eleven_pos == (2, 1)


def test_timers_tick_down():
    s = GameState.new_game(); tm = TurnManager(s)
    s.corrupted[(5, 5)] = 2; s.status_effects["SPEED"] = 1
    tm.step(Action.WAIT)
    assert s.corrupted == {(5, 5): 1} and "SPEED" not in s.status_effects


def test_loss_on_zero_hp_and_turn_limit():
    s = GameState.new_game(); s.eleven_hp = 0
    check_win_loss(s); assert s.winner == Winner.ENEMIES
    s = GameState.new_game(); s.max_turns = 3; tm = TurnManager(s)
    for _ in range(3): tm.step(Action.WAIT)
    assert s.winner == Winner.ENEMIES and s.turn == 2
    assert tm.step(Action.WAIT) is False          # no turns after game over


def test_portal_alone_is_not_victory():
    s = GameState.new_game(); s.eleven_pos = s.portal_pos
    check_win_loss(s); assert s.winner == Winner.NONE
    s.rescued = set(s.friend_positions); s.mind_flayer.defeated = True
    check_win_loss(s); assert s.winner == Winner.ELEVEN
