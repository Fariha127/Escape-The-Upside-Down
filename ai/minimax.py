"""Minimax with Alpha-Beta pruning for Vecna.

    MAX = Vecna      MIN = Eleven      depth counted in plies (depth 4 = Vecna, Eleven, Vecna, Eleven)

DESIGN DECISIONS (documented for the README)
  * Only Vecna and Eleven alternate. Demogorgons stay where they are (static obstacles) and the
    Mind Flayer is not modelled.
  * Eleven's modelled replies: step, ATTACK, RESCUE, WAIT. Abilities and the final attack are not
    modelled (Teleport needs a target; they matter little for Vecna's short-range tactics).
  * Every node works on state.clone(); the live state is never touched.
  * Counters (all real): nodes_visited = every node entered; nodes_evaluated = leaves scored by the
    evaluation function or a terminal test; branches_pruned = sibling moves skipped by cutoffs
    (always 0 with Alpha-Beta off).
  * Move ordering (attack first, then closing in / fleeing) only changes how much is pruned,
    never the value returned. Ties go to the first move in that fixed order, so results are
    deterministic and identical with and without Alpha-Beta."""
from __future__ import annotations
import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import config
from ai.distance_table import walk_distance
from ai.evaluation import evaluate_for_vecna, terminal_value
from game.actions import Action, MOVE_DELTAS
from game.rules import apply_eleven_action, legal_eleven_actions
from game.state import GameState
from game.vecna_rules import apply_vecna_action, legal_vecna_actions

# Eleven replies the search considers (everything else is left out on purpose, see above)
ELEVEN_MODELLED = (Action.ATTACK, Action.RESCUE, *MOVE_DELTAS, Action.WAIT)


@dataclass
class MinimaxResult:
    action: Action                       # Vecna's selected move
    score: float                         # exact minimax value of that move
    depth: int
    alpha_beta: bool
    nodes_visited: int = 0
    nodes_evaluated: int = 0
    branches_pruned: int = 0
    time_ms: float = 0.0
    # value returned for each root move. Exact for the chosen move; with Alpha-Beta the other moves
    # only carry a bound (their true value is <= this number).
    root_values: Dict[str, float] = field(default_factory=dict)


class _Counters:
    __slots__ = ("visited", "evaluated", "pruned")

    def __init__(self) -> None:
        self.visited = self.evaluated = self.pruned = 0


def _order_vecna(state: GameState, actions: List[Action]) -> List[Action]:
    """ATTACK first, then moves that end closest to Eleven, WAIT last (stable for ties)."""
    def key(a: Action):
        if a == Action.ATTACK:
            return (0, 0)
        if a == Action.WAIT:
            return (2, 0)
        dx, dy = MOVE_DELTAS[a]
        dest = (state.vecna.pos[0] + dx, state.vecna.pos[1] + dy)
        return (1, walk_distance(state.board, dest, state.eleven_pos))
    return sorted(actions, key=key)


def _eleven_actions(state: GameState) -> List[Action]:
    """Eleven's modelled replies, best-for-Eleven first: ATTACK, RESCUE, then moves that end
    farthest from Vecna, WAIT last."""
    legal = [a for a in legal_eleven_actions(state) if a in ELEVEN_MODELLED]

    def key(a: Action):
        if a == Action.ATTACK:
            return (0, 0)
        if a == Action.RESCUE:
            return (0, 1)
        if a == Action.WAIT:
            return (2, 0)
        dx, dy = MOVE_DELTAS[a]
        dest = (state.eleven_pos[0] + dx, state.eleven_pos[1] + dy)
        return (1, -walk_distance(state.board, dest, state.vecna.pos))
    return sorted(legal, key=key)


def _children(state: GameState, maximizing: bool):
    """(action, child_state) pairs in search order. Each child is an independent clone."""
    actions = _order_vecna(state, legal_vecna_actions(state)) if maximizing else _eleven_actions(state)
    for a in actions:
        child = state.clone()
        if maximizing:
            apply_vecna_action(child, a)
        else:
            apply_eleven_action(child, a)
        yield a, child


def _search(state: GameState, depth: int, maximizing: bool, alpha: float, beta: float,
            use_ab: bool, c: _Counters) -> float:
    c.visited += 1
    tv = terminal_value(state)
    if tv is not None:
        c.evaluated += 1
        return tv
    if depth == 0:
        c.evaluated += 1
        return evaluate_for_vecna(state)
    children = list(_children(state, maximizing))
    if not children:                                   # no legal reply: score the position as it is
        c.evaluated += 1
        return evaluate_for_vecna(state)
    if maximizing:
        value = -math.inf
        for i, (_, child) in enumerate(children):
            value = max(value, _search(child, depth - 1, False, alpha, beta, use_ab, c))
            alpha = max(alpha, value)
            if use_ab and alpha >= beta:
                c.pruned += len(children) - i - 1
                break
        return value
    value = math.inf
    for i, (_, child) in enumerate(children):
        value = min(value, _search(child, depth - 1, True, alpha, beta, use_ab, c))
        beta = min(beta, value)
        if use_ab and alpha >= beta:
            c.pruned += len(children) - i - 1
            break
    return value


def minimax_search(state: GameState, depth: Optional[int] = None,
                   use_alpha_beta: Optional[bool] = None) -> MinimaxResult:
    """Choose Vecna's move. `state` is only read: every simulated move happens on a clone."""
    depth = config.MINIMAX_DEPTH if depth is None else depth
    use_ab = config.VECNA_USE_ALPHA_BETA if use_alpha_beta is None else use_alpha_beta
    t0 = time.perf_counter()
    c = _Counters()
    c.visited += 1                                     # the root node
    best_action, best_value = Action.WAIT, -math.inf
    alpha, beta = -math.inf, math.inf
    root_values: Dict[str, float] = {}
    children = list(_children(state, True))
    for i, (action, child) in enumerate(children):
        v = _search(child, depth - 1, False, alpha, beta, use_ab, c)
        root_values[action.value] = v
        if v > best_value:                             # strict: ties keep the earlier (better ordered) move
            best_action, best_value = action, v
        alpha = max(alpha, best_value)
    return MinimaxResult(best_action, best_value, depth, use_ab, c.visited, c.evaluated, c.pruned,
                         (time.perf_counter() - t0) * 1000.0, root_values)