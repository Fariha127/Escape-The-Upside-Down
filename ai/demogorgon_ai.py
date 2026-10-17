"""Demogorgon controller: pursue Eleven along the shortest path found by A*.

Path re-use: a Demogorgon keeps its last path. It is re-used only while still valid
(same target cell, remaining cells unblocked/unoccupied). When Eleven moves, the target
changes, so a fresh A* search runs. Cache hits are counted separately and are never
reported as searches."""
from __future__ import annotations
from typing import Dict, List, Optional, Tuple

from ai.astar import find_path, step_to_action
from ai.metrics import Metrics
from game.actions import Action
from game.board import Pos

ROLE = "demogorgon"


class DemogorgonAI:
    def __init__(self, metrics: Optional[Metrics] = None):
        self.metrics = metrics or Metrics()
        # demogorgon id -> (position the path started from, path from that position)
        self._cache: Dict[int, Tuple[Pos, List[Pos]]] = {}

    # ---- common interface ----
    def choose_action(self, state, d) -> Action:
        """Return a MOVE_* toward Eleven, ATTACK if already adjacent, or WAIT if no path."""
        target = state.eleven_pos
        path = self._reusable_path(state, d, target)
        if path is not None:
            self.metrics.record_cache_hit(ROLE)
        else:
            result = find_path(state, d.pos, target)
            self.metrics.record_astar(ROLE, result)
            path = result.path if result.found else []
        self._cache[d.id] = (d.pos, path)
        if not path:
            return Action.WAIT
        if path[0] == target:
            return Action.ATTACK            # adjacent: the last step would be onto Eleven
        return step_to_action(d.pos, path[0])

    # ---- helpers ----
    def _reusable_path(self, state, d, target: Pos) -> Optional[List[Pos]]:
        entry = self._cache.get(d.id)
        if entry is None:
            return None
        prev_pos, prev_path = entry
        if d.pos == prev_pos:
            cand = prev_path
        elif prev_path and d.pos == prev_path[0]:
            cand = prev_path[1:]             # it advanced exactly one step along the path
        else:
            return None
        if not cand or cand[-1] != target:
            return None
        others = state.enemy_positions() - {d.pos}
        for cell in cand[:-1]:
            if state.is_blocked(cell) or cell in others or cell == state.eleven_pos:
                return None
        return cand

    def current_paths(self, state) -> Dict[int, List[Pos]]:
        """Remaining path of each living Demogorgon (for the debug overlay)."""
        out: Dict[int, List[Pos]] = {}
        for d in state.living_demogorgons():
            entry = self._cache.get(d.id)
            if not entry:
                continue
            prev_pos, path = entry
            if d.pos == prev_pos:
                out[d.id] = list(path)
            elif path and d.pos == path[0]:
                out[d.id] = path[1:]
        return out
