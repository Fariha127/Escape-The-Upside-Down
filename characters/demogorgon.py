"""Demogorgon: melee pursuer. Its movement AI (A*) arrives in Phase 3."""
from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING

import config
from game.board import Pos

if TYPE_CHECKING:
    from game.state import GameState


@dataclass
class Demogorgon:
    id: int
    pos: Pos
    alive: bool = True
    cooldown: int = 0          # turns it cannot damage Eleven after a hit
    frozen_turns: int = 0
    temporary: bool = False    # Mind-Flayer spawn. NEVER gives power (anti-farming rule).

    def clone(self) -> "Demogorgon":
        return Demogorgon(self.id, self.pos, self.alive, self.cooldown, self.frozen_turns, self.temporary)

    @property
    def is_frozen(self) -> bool:
        return self.frozen_turns > 0

    @property
    def can_attack(self) -> bool:
        return self.alive and self.cooldown == 0 and not self.is_frozen


def power_reward(d: Demogorgon) -> int:
    """Power gained by killing `d`. Temporary creatures give 0 -> power cannot be farmed."""
    return 0 if d.temporary else config.DEMOGORGON_REWARD


def spawn_temporary(state: "GameState", pos: Pos) -> bool:
    """Mind Flayer summon. Fails if the cell is blocked/occupied or the cap is reached."""
    live_temps = sum(1 for d in state.demogorgons if d.alive and d.temporary)
    if live_temps >= config.MAX_TEMP_CREATURES:
        return False
    if state.is_blocked(pos) or pos in state.enemy_positions() or pos == state.eleven_pos:
        return False
    new_id = max((d.id for d in state.demogorgons), default=-1) + 1
    state.demogorgons.append(Demogorgon(new_id, pos, temporary=True))
    return True
