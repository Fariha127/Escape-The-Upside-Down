"""Random board generator. The wall layout of the default map is fixed (so every board is a known-good maze);
only the PLACEMENTS change: portal, the four friends, the Demogorgons and the hazard cells. Eleven and Vecna
keep their corners. Every rule uses static walking distance and comes from config.py, and the result is
checked with Board.validate() (everything reachable). The same seed always gives the same board."""
from __future__ import annotations
import random
from collections import deque
from typing import Dict, List, Optional

import config
from game.board import DEFAULT_MAP, FRIEND_CHARS, Board, Pos

_ENTITY_CHARS = set("EVPGMDLW")
_FRIEND_CHAR = {name: ch for ch, name in FRIEND_CHARS.items()}
_DIST: Optional[Dict[Pos, Dict[Pos, int]]] = None
_LAYOUT: Optional[List[List[str]]] = None


def _layout() -> List[List[str]]:
    """The default map with every character, entity and hazard removed (walls and vines stay)."""
    global _LAYOUT
    if _LAYOUT is None:
        _LAYOUT = [["." if (c in _ENTITY_CHARS or c == "h") else c for c in row] for row in DEFAULT_MAP]
    return _LAYOUT


def _fixed_starts() -> Dict[str, Pos]:
    """Eleven and Vecna keep the positions they have on the default map."""
    out = {}
    for y, row in enumerate(DEFAULT_MAP):
        for x, c in enumerate(row):
            if c in ("E", "V"):
                out[c] = (x, y)
    return out


def _distances() -> Dict[Pos, Dict[Pos, int]]:
    """Walking distance between every pair of floor cells (plain BFS, computed once: the walls never change)."""
    global _DIST
    if _DIST is None:
        lay = _layout()
        cells = [(x, y) for y, row in enumerate(lay) for x, c in enumerate(row) if c != "#"]
        _DIST = {}
        for s in cells:
            dist, q = {s: 0}, deque([s])
            while q:
                cx, cy = q.popleft()
                for n in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if n not in dist and lay[n[1]][n[0]] != "#":
                        dist[n] = dist[(cx, cy)] + 1
                        q.append(n)
            _DIST[s] = dist
    return _DIST


def _bfs_avoiding(cell: Pos, start: Pos) -> Dict[Pos, int]:
    """Walking distances from `start` when `cell` is walled off."""
    lay = _layout()
    dist, q = {start: 0}, deque([start])
    while q:
        cx, cy = q.popleft()
        for n in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
            if n != cell and n not in dist and lay[n[1]][n[0]] != "#":
                dist[n] = dist[(cx, cy)] + 1
                q.append(n)
    return dist


def _detour_ok(cell: Pos, nodes: List[Pos]) -> bool:
    """True if walling off `cell` adds at most BOARD_HAZARD_MAX_DETOUR steps between any two of `nodes`."""
    d = _distances()
    for a in nodes:
        around = _bfs_avoiding(cell, a)
        for b in nodes:
            if b not in around or around[b] - d[a][b] > config.BOARD_HAZARD_MAX_DETOUR:
                return False
    return True


def _try_place(rng: random.Random, count: int) -> Optional[Dict[str, object]]:
    d = _distances()
    starts = _fixed_starts()
    eleven, vecna = starts["E"], starts["V"]
    cells = sorted(d[eleven])                       # every floor cell reachable from Eleven, in a fixed order
    used = {eleven, vecna}

    def pick(ok, also=None) -> Optional[Pos]:
        options = [c for c in cells if c not in used and ok(c)]
        if also is None:
            return rng.choice(options) if options else None
        rng.shuffle(options)                         # `also` is the slow check: try cells in random order
        return next((c for c in options if also(c)), None)

    portal = pick(lambda c: d[eleven][c] >= config.BOARD_PORTAL_MIN_DIST)
    if portal is None:
        return None
    used.add(portal)
    friends: Dict[str, Pos] = {}
    for name in FRIEND_CHARS.values():
        p = pick(lambda c: d[eleven][c] >= config.BOARD_FRIEND_MIN_DIST_ELEVEN
                 and d[vecna][c] >= config.BOARD_FRIEND_MIN_DIST_VECNA
                 and all(d[c][f] >= config.BOARD_FRIEND_SPACING for f in friends.values()))
        if p is None:
            return None
        friends[name] = p
        used.add(p)
    objects = list(friends.values()) + [portal]
    demogorgons: List[Pos] = []
    for _ in range(count):
        p = pick(lambda c: d[eleven][c] >= config.BOARD_DEMOGORGON_MIN_DIST_ELEVEN
                 and all(d[c][g] >= config.BOARD_DEMOGORGON_SPACING for g in demogorgons)
                 and all(d[c][o] >= config.BOARD_DEMOGORGON_MIN_DIST_OBJECT for o in objects))
        if p is None:
            return None
        demogorgons.append(p)
        used.add(p)
    hazards: List[Pos] = []
    for _ in range(config.BOARD_HAZARD_COUNT):
        p = pick(lambda c: d[eleven][c] >= config.BOARD_HAZARD_MIN_DIST_ELEVEN,
                 also=lambda c: _detour_ok(c, [eleven, vecna] + objects))
        if p is None:
            return None
        hazards.append(p)
        used.add(p)
    return {"portal": portal, "friends": friends, "demogorgons": demogorgons, "hazards": hazards}


def generate_board(seed: int, demogorgons: Optional[int] = None) -> Board:
    """A valid board for this seed (same seed -> same board). Falls back to the default map if no placement
    satisfying the rules is found within BOARD_MAX_TRIES (not expected: the tests check hundreds of seeds)."""
    count = config.DEMOGORGON_COUNT if demogorgons is None else demogorgons
    count = max(0, min(count, config.MAX_NORMAL_DEMOGORGONS))
    rng = random.Random(seed)
    for _ in range(config.BOARD_MAX_TRIES):
        plan = _try_place(rng, count)
        if plan is None:
            continue
        rows = [row[:] for row in _layout()]
        starts = _fixed_starts()
        for key, (x, y) in starts.items():
            rows[y][x] = key
        rows[plan["portal"][1]][plan["portal"][0]] = "P"
        for name, (x, y) in plan["friends"].items():
            rows[y][x] = _FRIEND_CHAR[name]
        for x, y in plan["demogorgons"]:
            rows[y][x] = "G"
        for x, y in plan["hazards"]:
            rows[y][x] = "h"
        board = Board(["".join(r) for r in rows])
        board.validate()
        return board
    return Board.default()
