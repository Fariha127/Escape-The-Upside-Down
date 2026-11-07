"""Radar report: the REAL A* path length from every enemy to Eleven.

Nothing here is estimated: each number is the length of a path returned by a real A* search,
and every search is recorded in the Metrics under the role "radar".

DESIGN DECISION: Radar measures walking distance through the map, so only walls and corrupted
cells block the search. Other characters standing in the way are ignored (otherwise two enemies
in a corridor would make every other enemy read "no path"). This differs on purpose from the
movement A* used by Demogorgons, where characters are obstacles."""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

from ai.astar import astar_search
from ai.metrics import Metrics
from game.board import Pos

ROLE = "radar"


@dataclass
class RadarReading:
    label: str                 # e.g. "Demogorgon 2", "Vecna"
    short: str                 # e.g. "G2", "V" (for the HUD)
    pos: Pos
    steps: Optional[int]       # A* path length to Eleven, None if the map has no route
    nodes_explored: int        # A* nodes expanded for this reading

    def text(self) -> str:
        if self.steps is None:
            return f"{self.label}: no path"
        return f"{self.label}: {self.steps} {'step' if self.steps == 1 else 'steps'}"


def scan(state, metrics: Optional[Metrics] = None) -> List[RadarReading]:
    """One A* search per living enemy, from the enemy to Eleven. Read-only on `state`.
    Result is sorted nearest first (unreachable enemies last)."""
    enemies = [(f"{'Creature' if d.temporary else 'Demogorgon'} {d.id}",
                f"{'C' if d.temporary else 'G'}{d.id}", d.pos)
               for d in sorted(state.living_demogorgons(), key=lambda x: x.id)]
    enemies.append(("Vecna", "V", state.vecna.pos))
    blocked = set(state.corrupted)
    readings: List[RadarReading] = []
    for label, short, pos in enemies:
        result = astar_search(state.board, pos, state.eleven_pos, blocked)
        if metrics is not None:
            metrics.record_astar(ROLE, result)
        readings.append(RadarReading(label, short, pos, result.path_length if result.found else None,
                                     result.nodes_explored))
    return sorted(readings, key=lambda r: (r.steps is None, r.steps if r.steps is not None else 0))