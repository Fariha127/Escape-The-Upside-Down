"""Mike's Teleport: jump to a previously visited, safe cell.

Who picks the destination: a human clicks one of `safe_cells`; the AI uses
`best_safe_cell` (the safe cell whose nearest enemy is farthest away by BFS walking distance).
Both go through the same validation in game.rules."""
from __future__ import annotations
from collections import deque
from typing import Dict, List, Optional, TYPE_CHECKING

import config
from game.board import Pos, Terrain

if TYPE_CHECKING:
    from game.state import GameState

NAME = "TELEPORT"


def _manhattan(a: Pos, b: Pos) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def is_safe_cell(state: "GameState", p: Pos) -> bool:
    """Visited, enterable, not a hazard, not Eleven's own cell, far enough from every enemy."""
    if p not in state.visited or p == state.eleven_pos:
        return False
    if state.is_blocked(p) or p in state.enemy_positions():
        return False
    if state.board.terrain_at(p) == Terrain.HAZARD:
        return False
    return all(_manhattan(p, e) >= config.TELEPORT_SAFE_DISTANCE for e in state.enemy_positions())


def safe_cells(state: "GameState") -> List[Pos]:
    return sorted(p for p in state.visited if is_safe_cell(state, p))


def enemy_distance_map(state: "GameState") -> Dict[Pos, int]:
    """Multi-source BFS walking distance from the nearest enemy (walls and corruption block)."""
    dist: Dict[Pos, int] = {}
    q = deque()
    for e in state.enemy_positions():
        dist[e] = 0
        q.append(e)
    while q:
        cur = q.popleft()
        for n in state.board.neighbors4(cur):
            if n not in dist and n not in state.corrupted:
                dist[n] = dist[cur] + 1
                q.append(n)
    return dist


def best_safe_cell(state: "GameState") -> Optional[Pos]:
    """AI choice: maximise the walking distance to the nearest enemy (ties: lowest coordinates).
    This is a BFS distance calculation, not an A* search, so it is not counted in A* stats."""
    cells = safe_cells(state)
    if not cells:
        return None
    dist = enemy_distance_map(state)
    far = 10 ** 6   # unreachable by any enemy = safest
    return max(cells, key=lambda p: (dist.get(p, far), -p[0], -p[1]))


def use(state: "GameState", target: Optional[Pos]) -> bool:
    if NAME not in state.unlocked_abilities or state.ability_uses.get(NAME, 0) <= 0:
        return False
    if target is None or not is_safe_cell(state, target):
        return False
    state.ability_uses[NAME] -= 1
    state.eleven_pos = target
    state.log(f"Teleport to {target}")
    return True