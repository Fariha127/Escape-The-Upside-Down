"""Static board: terrain only. Immutable after creation, so it is SHARED (not copied)
between cloned GameStates. Dynamic things (corruption, characters) live in GameState."""
from __future__ import annotations
from collections import deque
from enum import IntEnum
from typing import Dict, Iterable, List, Tuple

Pos = Tuple[int, int]


class Terrain(IntEnum):
    FLOOR = 0
    WALL = 1
    VINE = 2     # walkable, cosmetic for now
    HAZARD = 3   # walkable; damage rule added in a later phase


# ASCII legend: # wall . floor v vine h hazard | E Eleven M Mike D Dustin L Lucas
# W Will G Demogorgon V Vecna P Portal   (entity markers sit on floor)
_TERRAIN_CHARS = {"#": Terrain.WALL, "v": Terrain.VINE, "h": Terrain.HAZARD}
FRIEND_CHARS = {"M": "Mike", "D": "Dustin", "L": "Lucas", "W": "Will"}

DEFAULT_MAP = [
    "###############",
    "#E...#...G.#.M#",
    "#.vv.#.###.#.v#",
    "#....G.#...#..#",
    "##.#####.#.##.#",
    "#..h...#.G.#..#",
    "#.###.#...#.#.#",
    "#.D..v#.#.#.L.#",
    "#.####.v#...#.#",
    "#....#.G.h#...#",
    "#.##.#.#####.##",
    "#.#..G.......W#",
    "#.#.##.####.#.#",
    "#V..#.G.h...P.#",
    "###############",
]


class Board:
    def __init__(self, lines: List[str]):
        self.height = len(lines)
        self.width = len(lines[0])
        if any(len(r) != self.width for r in lines):
            raise ValueError("Map rows must all have the same width")
        terrain = []
        self.eleven_start: Pos = (-1, -1)
        self.vecna_start: Pos = (-1, -1)
        self.portal: Pos = (-1, -1)
        self.friend_positions: Dict[str, Pos] = {}
        self.demogorgon_starts: List[Pos] = []
        for y, row in enumerate(lines):
            trow = []
            for x, ch in enumerate(row):
                trow.append(_TERRAIN_CHARS.get(ch, Terrain.FLOOR))
                if ch == "E": self.eleven_start = (x, y)
                elif ch == "V": self.vecna_start = (x, y)
                elif ch == "P": self.portal = (x, y)
                elif ch == "G": self.demogorgon_starts.append((x, y))
                elif ch in FRIEND_CHARS: self.friend_positions[FRIEND_CHARS[ch]] = (x, y)
            terrain.append(tuple(trow))
        self.terrain = tuple(terrain)

    @classmethod
    def default(cls) -> "Board":
        return cls(DEFAULT_MAP)

    # --- queries ---
    def in_bounds(self, p: Pos) -> bool:
        return 0 <= p[0] < self.width and 0 <= p[1] < self.height

    def terrain_at(self, p: Pos) -> Terrain:
        return self.terrain[p[1]][p[0]]

    def is_walkable(self, p: Pos) -> bool:
        """Static walkability only (bounds + not wall). Dynamic blockers are GameState's job."""
        return self.in_bounds(p) and self.terrain_at(p) != Terrain.WALL

    def neighbors4(self, p: Pos) -> Iterable[Pos]:
        """Four-directional neighbours (no diagonals) that are statically walkable."""
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            n = (p[0] + dx, p[1] + dy)
            if self.is_walkable(n):
                yield n

    def reachable_from(self, start: Pos) -> set:
        """BFS flood fill over static terrain (used only for map validation)."""
        seen, q = {start}, deque([start])
        while q:
            cur = q.popleft()
            for n in self.neighbors4(cur):
                if n not in seen:
                    seen.add(n); q.append(n)
        return seen

    def validate(self) -> None:
        """Raise ValueError unless the map is playable: all objectives reachable from Eleven."""
        if self.eleven_start == (-1, -1) or self.portal == (-1, -1) or self.vecna_start == (-1, -1):
            raise ValueError("Map needs E, V and P markers")
        if set(self.friend_positions) != set(FRIEND_CHARS.values()):
            raise ValueError("Map needs all four friends (M, D, L, W)")
        reach = self.reachable_from(self.eleven_start)
        targets = {"portal": self.portal, "vecna": self.vecna_start,
                   **self.friend_positions,
                   **{f"demogorgon{i}": p for i, p in enumerate(self.demogorgon_starts)}}
        unreachable = [n for n, p in targets.items() if p not in reach]
        if unreachable:
            raise ValueError(f"Unreachable objectives: {unreachable}")
