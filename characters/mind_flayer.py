"""Mind Flayer: inactive until Will is rescued; then a map-control enemy (MCTS in Phase 7).

DESIGN DECISION: the Mind Flayer has no board position. It is an omnipresent entity that acts
on the map (corrupt cells, spawn creatures), so the final psychic attack needs no adjacency,
only: Mind Flayer active + Will rescued + enough power."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

import config
from game.board import Pos

if TYPE_CHECKING:
    from game.state import GameState


@dataclass
class MindFlayer:
    active: bool = False
    defeated: bool = False
    known_eleven_pos: Optional[Pos] = None
    spawn_cooldown: int = 0         # turns until it may summon again (stored +1, ticked in upkeep)

    def clone(self) -> "MindFlayer":
        return MindFlayer(self.active, self.defeated, self.known_eleven_pos, self.spawn_cooldown)


def activate(state: "GameState") -> bool:
    """Wake the Mind Flayer and give it Eleven's current location."""
    mf = state.mind_flayer
    if mf.active or mf.defeated:
        return False
    mf.active = True
    mf.known_eleven_pos = state.eleven_pos
    state.log("THE MIND FLAYER HAS AWAKENED")
    return True


def can_final_attack(state: "GameState") -> bool:
    mf = state.mind_flayer
    return (mf.active and not mf.defeated and "Will" in state.rescued
            and state.eleven_power >= config.FINAL_POWER_REQUIREMENT)


def final_attack(state: "GameState") -> bool:
    """Eleven's final psychic attack: defeats the Mind Flayer and unlocks the portal."""
    if not can_final_attack(state):
        return False
    if config.FINAL_ATTACK_CONSUMES_POWER:
        state.eleven_power -= config.FINAL_POWER_REQUIREMENT
    state.mind_flayer.defeated = True
    state.portal_active = True
    state.log("The Mind Flayer is defeated! The portal opens.")
    return True