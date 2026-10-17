"""Friends: rescuing one unlocks its ability. Rescuing Will also awakens the Mind Flayer."""
from __future__ import annotations
from typing import TYPE_CHECKING

import config

if TYPE_CHECKING:
    from game.state import GameState

FRIEND_NAMES = ("Mike", "Dustin", "Lucas", "Will")


def ability_for(friend: str) -> str:
    return config.FRIEND_ABILITY[friend]


def manhattan(a, b) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def can_rescue(state: "GameState", friend: str) -> bool:
    """Valid only if the friend exists, is not rescued yet, and Eleven is within RESCUE_RANGE."""
    if friend not in state.friend_positions or friend in state.rescued or state.game_over:
        return False
    return manhattan(state.eleven_pos, state.friend_positions[friend]) <= config.RESCUE_RANGE


def rescuable_friends(state: "GameState") -> list:
    return [f for f in FRIEND_NAMES if can_rescue(state, f)]


def rescue_friend(state: "GameState", friend: str) -> bool:
    """Mark friend rescued, unlock + stock their ability, and awaken the Mind Flayer for Will."""
    if not can_rescue(state, friend):
        return False
    from characters import mind_flayer  # local import: avoids a circular import at load time
    state.rescued.add(friend)
    ability = ability_for(friend)
    state.unlocked_abilities.add(ability)
    state.ability_uses[ability] = config.ABILITY_USES[ability]
    state.log(f"Rescued {friend} - unlocked {ability}")
    if friend == "Will":
        mind_flayer.activate(state)
    return True
