"""Eleven's stat rules. Her data lives on GameState (position, hp, power, ...);
these helpers are the only sanctioned ways to change hp/power so caps are always respected."""
from __future__ import annotations
from typing import TYPE_CHECKING

import config

if TYPE_CHECKING:
    from game.state import GameState


def take_damage(state: "GameState", amount: int) -> int:
    """Reduce HP (floored at 0). Returns the damage actually dealt."""
    dealt = min(amount, state.eleven_hp)
    state.eleven_hp -= dealt
    return dealt


def gain_power(state: "GameState", amount: int) -> int:
    """Add power, capped at MAX_POWER. Returns the amount actually gained."""
    gained = max(0, min(amount, config.MAX_POWER - state.eleven_power))
    state.eleven_power += gained
    return gained


def spend_power(state: "GameState", amount: int) -> bool:
    """Spend power; fails (no change) if Eleven cannot afford it."""
    if state.eleven_power < amount:
        return False
    state.eleven_power -= amount
    return True


def has_ability(state: "GameState", ability: str) -> bool:
    """Unlocked AND at least one use left."""
    return ability in state.unlocked_abilities and state.ability_uses.get(ability, 0) > 0
