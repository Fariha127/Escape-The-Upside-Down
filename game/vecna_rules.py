"""Vecna's legal actions and how they change the state (shared by the live game and the Minimax search).

Vecna acts once per turn: step to a free neighbouring cell, hit Eleven when she is within range
(-VECNA_DAMAGE HP, no cooldown because the spec gives none), or wait. He is never killed."""
from __future__ import annotations
from typing import List

import config
from game.actions import Action, MOVE_DELTAS
from game.rules import can_enemy_enter, vecna_hit
from game.state import GameState


def _distance_to_eleven(state: GameState) -> int:
    v, e = state.vecna.pos, state.eleven_pos
    return abs(v[0] - e[0]) + abs(v[1] - e[1])


def can_vecna_attack(state: GameState) -> bool:
    return (not state.vecna.is_frozen and state.eleven_hp > 0
            and _distance_to_eleven(state) <= config.VECNA_ATTACK_RANGE)


def legal_vecna_actions(state: GameState) -> List[Action]:
    """ATTACK (if in range), MOVE_* into free cells, WAIT. A frozen Vecna can only wait."""
    if state.vecna.is_frozen:
        return [Action.WAIT]
    actions = [Action.ATTACK] if can_vecna_attack(state) else []
    for a, (dx, dy) in MOVE_DELTAS.items():
        if can_enemy_enter(state, (state.vecna.pos[0] + dx, state.vecna.pos[1] + dy)):
            actions.append(a)
    actions.append(Action.WAIT)
    return actions


def apply_vecna_action(state: GameState, action: Action) -> bool:
    """Mutates `state` (callers pass a clone when simulating). Returns False if illegal."""
    if action not in legal_vecna_actions(state):
        return False
    if action in MOVE_DELTAS:
        dx, dy = MOVE_DELTAS[action]
        state.vecna.pos = (state.vecna.pos[0] + dx, state.vecna.pos[1] + dy)
    elif action == Action.ATTACK:
        return vecna_hit(state)
    return True      # WAIT