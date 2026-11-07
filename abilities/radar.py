"""Dustin's Radar: for RADAR_DURATION turns the game shows each enemy's real A* path distance
to Eleven (the report itself is produced by ai/radar_scan.py)."""
from __future__ import annotations
from typing import TYPE_CHECKING

import config

if TYPE_CHECKING:
    from game.state import GameState

NAME = "RADAR"


def is_active(state: "GameState") -> bool:
    return state.status_effects.get(NAME, 0) > 0


def use(state: "GameState") -> bool:
    """Spend one use and start the report. The status is stored as DURATION + 1 because the
    upkeep step at the end of this same turn ticks it down once (so it lasts DURATION full turns)."""
    if NAME not in state.unlocked_abilities or state.ability_uses.get(NAME, 0) <= 0:
        return False
    state.ability_uses[NAME] -= 1
    state.status_effects[NAME] = config.RADAR_DURATION + 1
    state.log("Radar: scanning enemy distances")
    return True