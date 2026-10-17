import random
from collections import deque

import config
from ai.astar import astar_search, find_path, step_to_action, manhattan, hazard_aware_cost
from ai.metrics import Metrics
from ai.navigation import Navigator
from ai.demogorgon_ai import DemogorgonAI
from game.actions import Action
from game.board import Board, Terrain
from game.rules import apply_eleven_action, legal_eleven_actions
from game.state import GameState
from game.turn_manager import TurnManager

OPEN = Board(["#######", "#.....#", "#.....#", "#.....#", "#.....#", "#.....#", "#######"])
WALLED = Board(["#######", "#..#..#", "#..#..#", "#.....#", "#..#..#", "#..#..#", "#######"])  # gap at (3,3)
SPLIT = Board(["#######", "#..#..#", "#..#..#", "#..#..#", "#######"])                         # two rooms


def bfs_dist(board, start):
    dist, q = {start: 0}, deque([start])
    while q:
        c = q.popleft()
        for n in board.neighbors4(c):
            if n not in dist:
                dist[n] = dist[c] + 1; q.append(n)
    return dist


# ---------------- A* correctness ----------------
def test_open_grid_path_is_manhattan_and_four_directional():
    r = astar_search(OPEN, (1, 1), (5, 4))
    assert r.found and r.path_length == manhattan((1, 1), (5, 4)) == 7 and r.cost == 7
    prev = (1, 1)
    for cell in r.path:
        assert manhattan(prev, cell) == 1          # no diagonal / no teleport steps
        prev = cell
    assert r.path[-1] == (5, 4) and (1, 1) not in r.path


def test_path_avoids_walls_and_uses_the_gap():
    r = astar_search(WALLED, (1, 1), (5, 1))
    assert r.found and (3, 3) in r.path
    assert all(WALLED.terrain_at(c) != Terrain.WALL for c in r.path)
    assert r.path_length == 8                      # 2 down, 4 right, 2 up


def test_unreachable_target_handled():
    r = astar_search(SPLIT, (1, 1), (5, 1))
    assert r.found is False and r.path == [] and r.nodes_explored > 0


def test_target_inside_wall_is_unreachable_without_search():
    r = astar_search(OPEN, (1, 1), (0, 0))
    assert not r.found and r.nodes_explored == 0


def test_start_equals_goal():
    r = astar_search(OPEN, (2, 2), (2, 2))
    assert r.found and r.path == [] and r.cost == 0


def test_blocked_cells_are_respected_but_goal_start_exempt():
    r = astar_search(OPEN, (1, 1), (3, 1), blocked={(2, 1)})
    assert r.found and (2, 1) not in r.path and r.path_length == 4
    r = astar_search(OPEN, (1, 1), (2, 1), blocked={(2, 1), (1, 1)})   # goal+start exempt
    assert r.found and r.path == [(2, 1)]
    r = astar_search(OPEN, (1, 1), (5, 5), blocked={(2, 1), (1, 2)})   # start boxed in
    assert not r.found


def test_astar_is_optimal_vs_bfs_on_default_map():
    b = Board.default(); rng = random.Random(config.RNG_SEED)
    cells = [(x, y) for y in range(b.height) for x in range(b.width) if b.is_walkable((x, y))]
    for _ in range(60):
        s, g = rng.choice(cells), rng.choice(cells)
        dist = bfs_dist(b, s)
        r = astar_search(b, s, g)
        if g in dist:
            assert r.found and r.cost == dist[g] == r.path_length
        else:
            assert not r.found


def test_nodes_explored_never_exceeds_reachable_cells_and_stats_populated():
    b = Board.default()
    r = astar_search(b, b.eleven_start, b.portal)
    assert 0 < r.nodes_explored <= len(b.reachable_from(b.eleven_start))
    assert r.time_ms >= 0 and r.goal == b.portal and r.start == b.eleven_start


def test_heuristic_prunes_search_compared_to_zero_heuristic():
    b = Board.default()
    informed = astar_search(b, b.eleven_start, b.portal)
    dijkstra = astar_search(b, b.eleven_start, b.portal, heuristic=lambda a, c: 0)
    assert informed.cost == dijkstra.cost and informed.nodes_explored <= dijkstra.nodes_explored


def test_step_costs_cause_detour_around_hazard():
    b = Board(["#######", "#.....#", "#..h..#", "#.....#", "#######"])
    costly = lambda p: 10 if b.terrain_at(p) == Terrain.HAZARD else 1
    plain = astar_search(b, (1, 2), (5, 2))
    aware = astar_search(b, (1, 2), (5, 2), step_cost=costly)
    assert (3, 2) in plain.path and plain.cost == 4          # straight through the hazard
    assert (3, 2) not in aware.path and aware.cost == 6      # 2 extra steps beats cost 10


def test_hazard_aware_cost_uses_config():
    b = Board(["#####", "#.h.#", "#####"])
    cost = hazard_aware_cost(b)
    assert cost((2, 1)) == config.ASTAR_HAZARD_COST and cost((1, 1)) == 1
    assert config.ASTAR_HAZARD_COST >= 1                      # keeps Manhattan admissible


def test_step_to_action():
    assert step_to_action((2, 2), (2, 1)) == Action.MOVE_UP
    assert step_to_action((2, 2), (2, 3)) == Action.MOVE_DOWN
    assert step_to_action((2, 2), (1, 2)) == Action.MOVE_LEFT
    assert step_to_action((2, 2), (3, 2)) == Action.MOVE_RIGHT
    try:
        step_to_action((2, 2), (3, 3)); assert False
    except ValueError:
        pass


# ---------------- find_path on a GameState ----------------
def test_find_path_treats_characters_and_corruption_as_obstacles():
    s = GameState.new_game()
    assert find_path(s, (1, 1), (1, 3)).path_length == 2
    s.demogorgons[0].pos = (1, 2)
    r = find_path(s, (1, 1), (1, 3))
    assert (1, 2) not in r.path and r.path_length == 4
    s.demogorgons[0].pos = (9, 1)
    s.corrupted[(1, 2)] = 3; s.corrupted[(2, 2)] = 3
    r = find_path(s, (1, 1), (1, 3))
    assert not {(1, 2), (2, 2)} & set(r.path) and r.path_length == 6
    s.corrupted[(2, 1)] = 3                      # Eleven fully boxed in
    assert not find_path(s, (1, 1), (1, 3)).found


def test_find_path_does_not_mutate_state():
    s = GameState.new_game(); before = s.clone()
    find_path(s, (1, 1), (13, 13))
    assert s.eleven_pos == before.eleven_pos and s.corrupted == before.corrupted
    assert [d.pos for d in s.demogorgons] == [d.pos for d in before.demogorgons]


# ---------------- Demogorgon behaviour ----------------
def single_demogorgon_state():
    s = GameState.new_game()
    s.demogorgons = [s.demogorgons[0]]            # one Demogorgon at (9,1)
    return s


def test_demogorgon_closes_in_by_one_cell_per_turn_then_attacks():
    s = single_demogorgon_state(); tm = TurnManager(s); b = s.board
    d = s.demogorgons[0]
    for _ in range(60):
        before = bfs_dist(b, d.pos)[s.eleven_pos]
        tm.step(Action.WAIT)
        after = bfs_dist(b, d.pos)[s.eleven_pos]
        assert after == (before - 1 if before > 1 else 1)
        if after == 1:
            break
    assert manhattan(d.pos, s.eleven_pos) == 1
    assert tm.demogorgon_ai.choose_action(s, d) == Action.ATTACK
    pos = d.pos; tm.step(Action.WAIT); assert d.pos == pos     # stays adjacent


def test_frozen_demogorgon_does_not_move():
    s = single_demogorgon_state(); tm = TurnManager(s); d = s.demogorgons[0]
    d.frozen_turns = 2; start = d.pos
    tm.step(Action.WAIT); tm.step(Action.WAIT)
    assert d.pos == start
    tm.step(Action.WAIT); assert d.pos != start


def test_path_cache_reused_until_eleven_moves():
    s = single_demogorgon_state(); tm = TurnManager(s)
    for _ in range(4): tm.step(Action.WAIT)
    st = tm.metrics.astar["demogorgon"]
    assert st.calls == 1 and st.cache_hits == 3          # searched once, reused three times
    tm.step(Action.MOVE_RIGHT)                            # Eleven moved -> target changed
    assert st.calls == 2


def test_cached_path_gets_replanned_when_blocked():
    s = single_demogorgon_state(); tm = TurnManager(s); d = s.demogorgons[0]
    tm.step(Action.WAIT)
    nxt = tm.demogorgon_ai.current_paths(s)[d.id][0]
    s.corrupted[nxt] = 5                                   # Mind Flayer blocks the next cell
    calls = tm.metrics.astar["demogorgon"].calls
    tm.step(Action.WAIT)
    assert tm.metrics.astar["demogorgon"].calls == calls + 1 and d.pos != nxt


def test_demogorgon_waits_when_no_path_exists():
    s = single_demogorgon_state(); d = s.demogorgons[0]       # at (9,1)
    s.corrupted[(8, 1)] = 5; s.corrupted[(10, 1)] = 5          # walled in by corruption
    ai = DemogorgonAI(Metrics())
    assert ai.choose_action(s, d) == Action.WAIT
    assert ai.metrics.astar["demogorgon"].last.found is False


def test_paths_never_route_through_other_characters():
    s = GameState.new_game(); tm = TurnManager(s)
    rival, waiter = s.demogorgons[0], s.demogorgons[1]
    s.demogorgons = [rival, waiter]
    s.demogorgons[0].pos = (4, 1); s.demogorgons[1].pos = (3, 3)
    # Characters are obstacles: path planning must never route through another character.
    r = find_path(s, waiter.pos, s.eleven_pos)
    assert (rival.pos not in r.path)


def test_no_collisions_over_random_game():
    s = GameState.new_game(); tm = TurnManager(s); rng = random.Random(config.RNG_SEED)
    for _ in range(120):
        if s.game_over: break
        tm.step(rng.choice(legal_eleven_actions(s)))
        cells = [d.pos for d in s.living_demogorgons()] + [s.vecna.pos, s.eleven_pos]
        assert len(cells) == len(set(cells))               # nobody shares a cell
        assert all(s.board.is_walkable(c) for c in cells)  # nobody inside a wall


def test_real_stats_recorded_for_every_search():
    s = GameState.new_game(); tm = TurnManager(s)
    for _ in range(5): tm.step(Action.WAIT if s.turn % 2 else Action.MOVE_RIGHT)
    st = tm.metrics.astar["demogorgon"]
    assert st.calls > 0 and st.nodes_explored >= st.calls and st.last is not None
    assert st.total_time_ms > 0 and st.avg_time_ms == st.total_time_ms / st.calls


# ---------------- Eleven navigation ----------------
def test_navigator_walks_the_shortest_path_to_target():
    s = GameState.new_game(); s.demogorgons = []; target = s.friend_positions["Lucas"]
    nav = Navigator(Metrics()); expected = None; steps = 0
    while s.eleven_pos != target and steps < 100:
        action, res = nav.next_action(s, target)
        expected = expected if expected is not None else res.path_length
        assert action in legal_eleven_actions(s)
        assert apply_eleven_action(s, action); steps += 1
    assert s.eleven_pos == target and steps == expected
    assert nav.next_action(s, target)[0] == Action.WAIT      # already there
    assert nav.metrics.astar["eleven"].calls == steps + 1


def test_navigator_waits_when_unreachable():
    s = GameState.new_game(); s.corrupted[(2, 1)] = 5; s.corrupted[(1, 2)] = 5
    action, res = Navigator().next_action(s, s.portal_pos)
    assert action == Action.WAIT and not res.found
