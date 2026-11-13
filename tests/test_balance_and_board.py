"""Balance: Eleven rescues Will (who wakes the Mind Flayer) last."""
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


# ------------------------------------------------------------------ a new seed for every game
def trajectory(seed, turns=25):
    """Eleven's positions over the first turns of an AI game with this seed."""
    import config as cfg
    cfg.RNG_SEED = seed
    state, tm, ai = new_game()
    out = []
    for _ in range(turns):
        if state.game_over:
            break
        ai_turn(state, tm, ai)
        out.append((state.eleven_pos, state.eleven_hp, state.eleven_power))
    return out


def test_same_seed_gives_the_same_game():
    assert trajectory(7) == trajectory(7)


def test_different_seeds_give_different_games():
    assert any(trajectory(1) != trajectory(s) for s in (2, 3, 4, 5))


def test_each_new_session_game_gets_its_own_seed(monkeypatch):
    from ui.session import GameSession
    monkeypatch.setattr(config, "RANDOM_SEED_PER_GAME", True)
    s = GameSession(ai_mode=True)
    seeds = {s.seed}
    for _ in range(5):
        s.restart()
        assert config.RNG_SEED == s.seed            # the AIs read this value when they search
        seeds.add(s.seed)
    assert len(seeds) > 1
    assert s.overlay()["seed"] == s.seed


def test_fixed_seed_setting_always_uses_the_same_seed(monkeypatch):
    from ui.session import FIXED_SEED, GameSession
    monkeypatch.setattr(config, "RANDOM_SEED_PER_GAME", False)
    s = GameSession()
    s.restart()
    assert s.seed == FIXED_SEED == config.RNG_SEED


def test_results_show_the_seed():
    from game.turn_manager import TurnManager
    from ui.stats_view import build_results
    s = GameState.new_game()
    rows = dict(build_results(s, TurnManager(s), seed=123).rows)
    assert rows["Game seed"] == "123"
    assert "Game seed" not in dict(build_results(s, TurnManager(s)).rows)


def test_settings_screen_toggles_the_seed_mode(monkeypatch):
    import pygame
    from ui.menu_screens import SettingsScreen
    from ui.theme import Fonts  # noqa: F401
    monkeypatch.setattr(config, "RANDOM_SEED_PER_GAME", True)

    class Dummy:
        speed_idx = 0
    scr = SettingsScreen((960, 712), Dummy())
    btn = next(b for b in scr.buttons if b.id == "seed")
    assert "new each game" in btn.label
    scr.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=btn.rect.center, button=1))
    assert config.RANDOM_SEED_PER_GAME is False and "fixed" in btn.label


# ------------------------------------------------------------------ random board (placements change, walls do not)
from game.board import DEFAULT_MAP, FRIEND_CHARS, Board, Terrain
from game.board_gen import generate_board

SEEDS = range(300)


def wd(b, a, c):
    from ai.distance_table import walk_distance
    return walk_distance(b, a, c)


def test_same_seed_gives_the_same_board_and_other_seeds_differ():
    a, b = generate_board(5), generate_board(5)
    assert (a.terrain, a.portal, a.friend_positions, a.demogorgon_starts) == \
           (b.terrain, b.portal, b.friend_positions, b.demogorgon_starts)
    assert any(generate_board(s).portal != a.portal or generate_board(s).demogorgon_starts != a.demogorgon_starts
               for s in range(6, 12))


def test_walls_never_change_and_eleven_and_vecna_keep_their_corners():
    default = Board.default()
    for s in SEEDS:
        b = generate_board(s)
        walls = [[b.terrain_at((x, y)) == Terrain.WALL for x in range(b.width)] for y in range(b.height)]
        assert walls == [[default.terrain_at((x, y)) == Terrain.WALL for x in range(b.width)] for y in range(b.height)]
        assert b.eleven_start == default.eleven_start and b.vecna_start == default.vecna_start


def test_every_board_is_valid_and_has_the_configured_counts():
    for s in SEEDS:
        b = generate_board(s)
        b.validate()                                                   # all objectives reachable
        assert len(b.demogorgon_starts) == config.DEMOGORGON_COUNT
        assert set(b.friend_positions) == set(FRIEND_CHARS.values())
        hazards = [(x, y) for y in range(b.height) for x in range(b.width) if b.terrain_at((x, y)) == Terrain.HAZARD]
        assert len(hazards) == config.BOARD_HAZARD_COUNT


def test_placements_follow_the_distance_rules_and_never_overlap():
    for s in SEEDS:
        b = generate_board(s)
        e, v = b.eleven_start, b.vecna_start
        friends = list(b.friend_positions.values())
        gs = b.demogorgon_starts
        cells = [e, v, b.portal] + friends + gs
        assert len(set(cells)) == len(cells)                           # nothing shares a cell
        assert wd(b, e, b.portal) >= config.BOARD_PORTAL_MIN_DIST
        for f in friends:
            assert wd(b, e, f) >= config.BOARD_FRIEND_MIN_DIST_ELEVEN and wd(b, v, f) >= config.BOARD_FRIEND_MIN_DIST_VECNA
            assert all(wd(b, f, o) >= config.BOARD_FRIEND_SPACING for o in friends if o != f)
        for g in gs:
            assert wd(b, e, g) >= config.BOARD_DEMOGORGON_MIN_DIST_ELEVEN
            assert all(wd(b, g, o) >= config.BOARD_DEMOGORGON_SPACING for o in gs if o != g)
            assert all(wd(b, g, o) >= config.BOARD_DEMOGORGON_MIN_DIST_OBJECT for o in friends + [b.portal])
        for y in range(b.height):
            for x in range(b.width):
                if b.terrain_at((x, y)) == Terrain.HAZARD:
                    assert wd(b, e, (x, y)) >= config.BOARD_HAZARD_MIN_DIST_ELEVEN
                    assert (x, y) not in cells


@pytest.mark.parametrize("count", [0, 3, 6, 10, 99])
def test_demogorgon_count_is_respected_and_capped(count):
    b = generate_board(1, demogorgons=count)
    assert len(b.demogorgon_starts) <= config.MAX_NORMAL_DEMOGORGONS
    if count <= 6:
        assert len(b.demogorgon_starts) == count


def test_default_map_is_unchanged():
    assert Board.default().demogorgon_starts == [(5, 3), (7, 9), (6, 13)]
    assert len(DEFAULT_MAP) == 15


def test_session_uses_the_generated_board_for_its_seed(monkeypatch):
    from ui.session import GameSession
    monkeypatch.setattr(config, "RANDOM_SEED_PER_GAME", True)
    monkeypatch.setattr(config, "RANDOM_BOARD_PER_GAME", True)
    s = GameSession()
    b = generate_board(s.seed)
    assert s.state.board.demogorgon_starts == b.demogorgon_starts and s.state.portal_pos == b.portal
    monkeypatch.setattr(config, "RANDOM_BOARD_PER_GAME", False)
    s.restart()
    assert s.state.board.demogorgon_starts == Board.default().demogorgon_starts


def test_a_full_ai_game_runs_on_generated_boards():
    from ui.session import GameSession
    for seed in (11, 12, 13):
        config.RNG_SEED = seed
        state, tm, ai = new_game(generate_board(seed))
        while not state.game_over:
            ai_turn(state, tm, ai)
        assert state.turn <= config.MAX_TURNS


def test_hazards_can_always_be_walked_around_cheaply():
    """Walling off any hazard cell adds at most BOARD_HAZARD_MAX_DETOUR steps between Eleven, Vecna, the friends
    and the portal (checked with a separate BFS, not the generator's own helper)."""
    from collections import deque

    def bfs(b, start, blocked):
        dist, q = {start: 0}, deque([start])
        while q:
            cur = q.popleft()
            for n in b.neighbors4(cur):
                if n != blocked and n not in dist:
                    dist[n] = dist[cur] + 1
                    q.append(n)
        return dist

    for s in range(60):
        b = generate_board(s)
        nodes = [b.eleven_start, b.vecna_start, b.portal] + list(b.friend_positions.values())
        for y in range(b.height):
            for x in range(b.width):
                if b.terrain_at((x, y)) != Terrain.HAZARD:
                    continue
                for a in nodes:
                    free, walled = bfs(b, a, None), bfs(b, a, (x, y))
                    assert all(o in walled and walled[o] - free[o] <= config.BOARD_HAZARD_MAX_DETOUR for o in nodes)
