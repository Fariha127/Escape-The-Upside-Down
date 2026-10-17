"""Measurements collected from REAL algorithm runs (nothing here is estimated or random).
Minimax / MCTS counters are added in the phases that implement them."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ai.astar import AStarResult


@dataclass
class AStarStats:
    calls: int = 0               # real A* searches executed
    nodes_explored: int = 0
    total_time_ms: float = 0.0
    cache_hits: int = 0          # turns where a still-valid cached path was reused (no search)
    last: Optional["AStarResult"] = None

    @property
    def avg_time_ms(self) -> float:
        return self.total_time_ms / self.calls if self.calls else 0.0


class Metrics:
    """One recorder per game. `role` is e.g. 'demogorgon' or 'eleven'."""

    def __init__(self) -> None:
        self.astar: Dict[str, AStarStats] = {}

    def _stats(self, role: str) -> AStarStats:
        return self.astar.setdefault(role, AStarStats())

    def record_astar(self, role: str, result: "AStarResult") -> None:
        s = self._stats(role)
        s.calls += 1
        s.nodes_explored += result.nodes_explored
        s.total_time_ms += result.time_ms
        s.last = result

    def record_cache_hit(self, role: str) -> None:
        self._stats(role).cache_hits += 1
