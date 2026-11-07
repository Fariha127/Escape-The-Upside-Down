"""Lucas's Speed: Eleven may move SPEED_MOVES_PER_TURN cells per turn for SPEED_DURATION turns."""
from __future__ import annotations
from typing import TYPE_CHECKING

import config

if TYPE_CHECKING:
    from game.state import GameState

NAME = "SPEED"


def is_active(state: "GameState") -> bool:
    return state.status_effects.get(NAME, 0) > 0


def use(state: "GameState") -> bool:
    """Spend one use. Stored as DURATION + 1 so the end-of-turn tick does not eat a turn."""
    if NAME not in state.unlocked_abilities or state.ability_uses.get(NAME, 0) <= 0:
        return False
    state.ability_uses[NAME] -= 1
    state.status_effects[NAME] = config.ABILITY_DURATIONS[NAME] + 1
    state.log("Speed: Eleven can move twice per turn")
    return True