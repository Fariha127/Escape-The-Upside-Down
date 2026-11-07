"""Will's Freeze: all Demogorgons and Vecna skip their actions for FREEZE duration turns."""
from __future__ import annotations
from typing import TYPE_CHECKING

import config

if TYPE_CHECKING:
    from game.state import GameState

NAME = "FREEZE"


def use(state: "GameState") -> bool:
    """Spend one use. frozen_turns is decremented in the upkeep step, and enemies act BEFORE
    upkeep, so frozen_turns == duration skips exactly `duration` enemy phases."""
    if NAME not in state.unlocked_abilities or state.ability_uses.get(NAME, 0) <= 0:
        return False
    state.ability_uses[NAME] -= 1
    turns = config.ABILITY_DURATIONS[NAME]
    for d in state.living_demogorgons():
        d.frozen_turns = turns
    state.vecna.frozen_turns = turns
    state.log(f"Freeze: enemies frozen for {turns} turns")
    return True