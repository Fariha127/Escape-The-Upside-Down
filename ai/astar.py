"""A* Search on the 4-connected grid.

    f(n) = g(n) + h(n)          h(n) = |x1-x2| + |y1-y2|   (Manhattan distance)

Manhattan distance never overestimates on a 4-directional grid whose step cost is >= 1
(admissible and consistent), so the returned path is optimal.

DESIGN DECISIONS (documented for the README)
  * Impassable: walls, map edges, Mind-Flayer-corrupted cells.
  * Other characters (Demogorgons, Vecna, Eleven) are treated as OBSTACLES, consistently for
    every caller. The start cell and the goal cell are always exempt (a Demogorgon's goal IS
    Eleven's cell; the final step onto it means "attack", not "move").
  * Uniform step cost 1 by default; callers may supply a step_cost(cell) function (>= 1).
  * Ties in f are broken by smaller h, then by insertion order -> fully deterministic.
"""
from __future__ import annotations
import heapq
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, FrozenSet, Iterable, List, Optional, Set

from game.actions import Action, MOVE_DELTAS
from game.board import Board, Pos, Terrain


def manhattan(a: Pos, b: Pos) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


@dataclass
class AStarResult:
    """Everything the AI panel / metrics need, taken from the real search."""
    start: Pos
    goal: Pos
    found: bool
    path: List[Pos] = field(default_factory=list)   # excludes start, includes goal
    cost: float = 0
    nodes_explored: int = 0                          # nodes expanded (moved to the closed set)
    time_ms: float = 0.0

    @property
    def path_length(self) -> int:
        return len(self.path)

    @property
    def first_step(self) -> Optional[Pos]:
        return self.path[0] if self.path else None


def astar_search(board: Board, start: Pos, goal: Pos,
                 blocked: Iterable[Pos] = frozenset(),
                 step_cost: Optional[Callable[[Pos], float]] = None,
                 heuristic: Callable[[Pos, Pos], float] = manhattan) -> AStarResult:
    """Pure A* over a Board. `blocked` cells are impassable (start/goal are exempt)."""
    t0 = time.perf_counter()
    blocked = blocked if isinstance(blocked, (set, frozenset)) else set(blocked)

    def finish(found: bool, path: List[Pos], cost: float, nodes: int) -> AStarResult:
        return AStarResult(start, goal, found, path, cost, nodes, (time.perf_counter() - t0) * 1000.0)

    if start == goal:
        return finish(True, [], 0, 0)
    if not board.is_walkable(goal):
        return finish(False, [], 0, 0)

    g: Dict[Pos, float] = {start: 0}
    came_from: Dict[Pos, Pos] = {}
    closed: Set[Pos] = set()
    counter = 0
    h0 = heuristic(start, goal)
    open_heap = [(h0, h0, counter, start)]       # (f, h, insertion order, cell)
    nodes = 0

    while open_heap:
        _, _, _, cur = heapq.heappop(open_heap)
        if cur in closed:                         # stale heap entry (lazy deletion)
            continue
        closed.add(cur)
        nodes += 1
        if cur == goal:
            path = [cur]
            while path[-1] in came_from:
                path.append(came_from[path[-1]])
            path.pop()                            # remove start
            path.reverse()
            return finish(True, path, g[goal], nodes)
        for n in board.neighbors4(cur):
            if n in closed or (n in blocked and n != goal):
                continue
            ng = g[cur] + (step_cost(n) if step_cost else 1)
            if ng < g.get(n, float("inf")):
                g[n] = ng
                came_from[n] = cur
                counter += 1
                hn = heuristic(n, goal)
                heapq.heappush(open_heap, (ng + hn, hn, counter, n))
    return finish(False, [], 0, nodes)


def find_path(state, start: Pos, goal: Pos,
              step_cost: Optional[Callable[[Pos], float]] = None,
              extra_blocked: Iterable[Pos] = ()) -> AStarResult:
    """A* using the live rules of a GameState: corruption + characters are obstacles.
    Read-only: never modifies `state`."""
    blocked: Set[Pos] = set(state.corrupted)
    blocked |= state.enemy_positions()
    blocked.add(state.eleven_pos)
    blocked |= set(extra_blocked)
    return astar_search(state.board, start, goal, blocked, step_cost)


def hazard_aware_cost(board: Board) -> Callable[[Pos], float]:
    """Step-cost function that makes hazard cells less attractive (used for Eleven)."""
    import config
    return lambda p: config.ASTAR_HAZARD_COST if board.terrain_at(p) == Terrain.HAZARD else 1


_DELTA_TO_ACTION = {d: a for a, d in MOVE_DELTAS.items()}


def step_to_action(frm: Pos, to: Pos) -> Action:
    """Convert one grid step into a MOVE_* action."""
    delta = (to[0] - frm[0], to[1] - frm[1])
    if delta not in _DELTA_TO_ACTION:
        raise ValueError(f"{frm} -> {to} is not a single 4-directional step")
    return _DELTA_TO_ACTION[delta]
