"""Eleven's physical navigation (the 'HOW' half of MCTS + A*).

Phase 6: MCTS chooses a strategic target ('rescue Mike', 'go to portal', ...).
This class then converts that target into one concrete MOVE_* action using A*."""
from __future__ import annotations
from typing import Optional, Tuple

from ai.astar import AStarResult, find_path, hazard_aware_cost, step_to_action
from ai.metrics import Metrics
from game.actions import Action
from game.board import Pos

ROLE = "eleven"


class Navigator:
    def __init__(self, metrics: Optional[Metrics] = None):
        self.metrics = metrics or Metrics()
        self.last_result: Optional[AStarResult] = None

    def next_action(self, state, target: Pos, step_cost=None) -> Tuple[Action, AStarResult]:
        """One step toward `target`. Returns (WAIT, result) when already there or unreachable.
        step_cost: optional cost function (>= 1); the default makes hazard cells costlier."""
        closed = [] if state.mind_flayer.defeated else [state.portal_pos]   # Eleven cannot walk through it yet
        result = find_path(state, state.eleven_pos, target, step_cost=step_cost or hazard_aware_cost(state.board),
                           extra_blocked=closed)
        self.metrics.record_astar(ROLE, result)
        self.last_result = result
        if not result.found or not result.path:
            return Action.WAIT, result
        return step_to_action(state.eleven_pos, result.path[0]), result