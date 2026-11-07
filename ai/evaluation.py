"""Vecna's view of a game state. Positive = good for Vecna (bad for Eleven).

Terminal states return exactly +/-UTILITY (50). Every NON-terminal state stays strictly inside
(-49 .. +49), so a real win/loss always outranks any heuristic estimate."""
from __future__ import annotations
from typing import Optional

import config
from ai.distance_table import UNREACHABLE, walk_distance

NON_TERMINAL_LIMIT = config.UTILITY_WIN - 1        # 49


def terminal_value(state) -> Optional[float]:
    """+50 if Eleven is dead, -50 if she has won, otherwise None (the game goes on).
    The turn limit is not modelled: turns do not advance inside a search."""
    if state.eleven_hp <= 0:
        return float(-config.UTILITY_LOSS)                 # Eleven's loss is Vecna's win
    if (len(state.rescued) == len(state.friend_positions) and state.mind_flayer.defeated
            and state.eleven_pos == state.portal_pos):
        return float(-config.UTILITY_WIN)
    return None


def _closeness(distance: int) -> float:
    """1.0 when distance is 0, falling linearly to 0.0 at VECNA_EVAL_DISTANCE_CAP."""
    if distance >= UNREACHABLE:
        return 0.0
    return 1.0 - min(distance, config.VECNA_EVAL_DISTANCE_CAP) / config.VECNA_EVAL_DISTANCE_CAP


def evaluate_for_vecna(state) -> float:
    """Heuristic value of a non-terminal state from Vecna's side:
         + HP_LOST   per HP Eleven has lost
         + PROXIMITY scaled by how close Vecna is to Eleven (walking distance)
         - RESCUED   per rescued friend
         - PORTAL_PROGRESS scaled by how close Eleven is to the OPEN portal."""
    w = config.VECNA_EVAL_WEIGHTS
    score = w["HP_LOST"] * (config.MAX_HP - state.eleven_hp)
    score += w["PROXIMITY"] * _closeness(walk_distance(state.board, state.vecna.pos, state.eleven_pos))
    score -= w["RESCUED"] * len(state.rescued)
    if state.portal_active:
        score -= w["PORTAL_PROGRESS"] * _closeness(walk_distance(state.board, state.eleven_pos, state.portal_pos))
    return max(-NON_TERMINAL_LIMIT, min(NON_TERMINAL_LIMIT, float(score)))