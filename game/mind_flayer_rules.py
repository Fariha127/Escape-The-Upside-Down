"""Mind Flayer actions and how they change the state (shared by the live game and its MCTS simulations).

The Mind Flayer has no board position. Once Will is rescued it acts once per turn (after Vecna):
  * CORRUPT a cell: for MF_CORRUPT_DURATION full turns nobody can enter it (Eleven, Demogorgons, Vecna)
  * SPAWN a temporary Demogorgon (it never gives power; at most MAX_TEMP_CREATURES alive; cooldown)
  * WAIT

DESIGN DECISIONS
  * Cells with a character on them, the portal cell and cells already corrupted cannot be corrupted,
    and at most MF_MAX_CORRUPTED cells are corrupted at once. Corruption expires, and Eleven always acts
    first in a turn, so she always gets a chance to cross a cell the turn it clears: no permanent walls.
  * Timers are stored +1 because the upkeep step ticks once in the same turn the action was taken."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

import config
from characters.demogorgon import spawn_temporary
from game.board import Pos
from game.rules import can_enemy_enter
from game.state import GameState

CORRUPT = "CORRUPT"
SPAWN = "SPAWN"
WAIT = "WAIT"


@dataclass(frozen=True)
class MFAction:
    kind: str
    cell: Optional[Pos] = None

    @property
    def label(self) -> str:
        return f"{self.kind} {self.cell}" if self.cell is not None else self.kind


def is_acting(state: GameState) -> bool:
    mf = state.mind_flayer
    return mf.active and not mf.defeated and not state.game_over


def can_corrupt(state: GameState, cell: Pos) -> bool:
    return (is_acting(state) and state.board.is_walkable(cell) and cell not in state.corrupted
            and len(state.corrupted) < config.MF_MAX_CORRUPTED
            and cell != state.eleven_pos and cell not in state.enemy_positions()
            and cell != state.portal_pos)


def can_spawn(state: GameState, cell: Pos) -> bool:
    live_temps = sum(1 for d in state.demogorgons if d.alive and d.temporary)
    return (is_acting(state) and state.mind_flayer.spawn_cooldown == 0
            and live_temps < config.MAX_TEMP_CREATURES and can_enemy_enter(state, cell))


def apply_mf_action(state: GameState, action: MFAction) -> bool:
    """Mutates `state` (callers pass a clone when simulating). Returns False if illegal."""
    if action.kind == WAIT:
        return is_acting(state)
    if action.kind == CORRUPT:
        if action.cell is None or not can_corrupt(state, action.cell):
            return False
        state.corrupted[action.cell] = config.MF_CORRUPT_DURATION + 1
        state.log(f"Mind Flayer corrupts {action.cell}")
        return True
    if action.kind == SPAWN:
        if action.cell is None or not can_spawn(state, action.cell):
            return False
        if not spawn_temporary(state, action.cell):
            return False
        state.mind_flayer.spawn_cooldown = config.MF_SPAWN_COOLDOWN + 1
        state.log(f"Mind Flayer summons a creature at {action.cell}")
        return True
    return False