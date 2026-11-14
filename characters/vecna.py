"""Vecna: strategic enemy. Never permanently killed in normal play. AI (Minimax + Alpha-Beta)."""
from __future__ import annotations
from dataclasses import dataclass

from game.board import Pos


@dataclass
class Vecna:
    pos: Pos
    frozen_turns: int = 0

    def clone(self) -> "Vecna":
        return Vecna(self.pos, self.frozen_turns)

    @property
    def is_frozen(self) -> bool:
        return self.frozen_turns > 0
