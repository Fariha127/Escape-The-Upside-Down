"""Static walking distances between every pair of walkable cells (plain BFS, computed once).

Used only by evaluation functions (Vecna's Minimax) so that millions of lookups cost O(1).
Characters and corruption are ignored on purpose: this measures the map, not the current traffic.
The cache is keyed by the terrain itself, so every Board with the same map shares one table."""
from __future__ import annotations
from collections import deque
from typing import Dict, Tuple

from game.board import Board, Pos

UNREACHABLE = 10 ** 6

_CACHE: Dict[Tuple, Dict[Pos, Dict[Pos, int]]] = {}


def distance_table(board: Board) -> Dict[Pos, Dict[Pos, int]]:
    table = _CACHE.get(board.terrain)
    if table is None:
        table = {}
        cells = [(x, y) for y in range(board.height) for x in range(board.width) if board.is_walkable((x, y))]
        for start in cells:
            dist, q = {start: 0}, deque([start])
            while q:
                cur = q.popleft()
                for n in board.neighbors4(cur):
                    if n not in dist:
                        dist[n] = dist[cur] + 1
                        q.append(n)
            table[start] = dist
        _CACHE[board.terrain] = table
    return table


def walk_distance(board: Board, a: Pos, b: Pos) -> int:
    """Shortest walking distance a -> b over static terrain (UNREACHABLE if there is none)."""
    return distance_table(board).get(a, {}).get(b, UNREACHABLE)