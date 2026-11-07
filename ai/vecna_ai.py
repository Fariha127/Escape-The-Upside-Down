"""Vecna's controller: picks his action with Minimax + Alpha-Beta and records the real statistics."""
from __future__ import annotations
from typing import Optional

from ai.metrics import Metrics
from ai.minimax import MinimaxResult, minimax_search
from game.actions import Action


class VecnaAI:
    def __init__(self, metrics: Optional[Metrics] = None, depth: Optional[int] = None,
                 use_alpha_beta: Optional[bool] = None):
        self.metrics = metrics or Metrics()
        self.depth = depth
        self.use_alpha_beta = use_alpha_beta
        self.last_result: Optional[MinimaxResult] = None

    def choose_action(self, state) -> Action:
        result = minimax_search(state, self.depth, self.use_alpha_beta)
        self.metrics.record_minimax(result)
        self.last_result = result
        return result.action