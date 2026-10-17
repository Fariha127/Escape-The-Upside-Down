"""Central GameState. Designed for fast, safe cloning (Minimax/MCTS must never touch live state).

Cloning rule: the immutable Board is shared by reference; everything else is copied."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set

import config
from game.board import Board, Pos
from characters.demogorgon import Demogorgon
from characters.mind_flayer import MindFlayer
from characters.vecna import Vecna


class Phase(Enum):
    ELEVEN = "ELEVEN"
    DEMOGORGONS = "DEMOGORGONS"
    VECNA = "VECNA"
    MIND_FLAYER = "MIND_FLAYER"
    UPKEEP = "UPKEEP"
    GAME_OVER = "GAME_OVER"


class Winner(Enum):
    NONE = "NONE"
    ELEVEN = "ELEVEN"
    ENEMIES = "ENEMIES"


@dataclass
class GameState:
    board: Board                                   # shared, immutable
    eleven_pos: Pos
    eleven_hp: int
    eleven_power: int
    demogorgons: List[Demogorgon]
    vecna: Vecna
    mind_flayer: MindFlayer
    friend_positions: Dict[str, Pos]               # unrescued friends stay at their cell
    rescued: Set[str] = field(default_factory=set)
    unlocked_abilities: Set[str] = field(default_factory=set)
    ability_uses: Dict[str, int] = field(default_factory=dict)
    status_effects: Dict[str, int] = field(default_factory=dict)   # name -> turns remaining
    visited: Set[Pos] = field(default_factory=set)
    corrupted: Dict[Pos, int] = field(default_factory=dict)        # cell -> turns remaining
    portal_pos: Pos = (-1, -1)
    portal_active: bool = False
    turn: int = 0
    phase: Phase = Phase.ELEVEN
    winner: Winner = Winner.NONE
    max_turns: int = config.MAX_TURNS
    event_log: List[str] = field(default_factory=list)   # human-readable events this game

    # ---------- construction ----------
    @classmethod
    def new_game(cls, board: Optional[Board] = None) -> "GameState":
        board = board or Board.default()
        board.validate()
        return cls(
            board=board,
            eleven_pos=board.eleven_start,
            eleven_hp=config.MAX_HP,
            eleven_power=config.START_POWER,
            demogorgons=[Demogorgon(i, p) for i, p in enumerate(board.demogorgon_starts)],
            vecna=Vecna(board.vecna_start),
            mind_flayer=MindFlayer(),
            friend_positions=dict(board.friend_positions),
            visited={board.eleven_start},
            portal_pos=board.portal,
        )

    # ---------- cloning ----------
    def clone(self) -> "GameState":
        """Deep-enough copy. Board is shared because it is never mutated."""
        return GameState(
            board=self.board,
            eleven_pos=self.eleven_pos,
            eleven_hp=self.eleven_hp,
            eleven_power=self.eleven_power,
            demogorgons=[d.clone() for d in self.demogorgons],
            vecna=self.vecna.clone(),
            mind_flayer=self.mind_flayer.clone(),
            friend_positions=dict(self.friend_positions),
            rescued=set(self.rescued),
            unlocked_abilities=set(self.unlocked_abilities),
            ability_uses=dict(self.ability_uses),
            status_effects=dict(self.status_effects),
            visited=set(self.visited),
            corrupted=dict(self.corrupted),
            portal_pos=self.portal_pos,
            portal_active=self.portal_active,
            turn=self.turn,
            phase=self.phase,
            winner=self.winner,
            max_turns=self.max_turns,
            event_log=list(self.event_log),
        )

    # ---------- queries ----------
    @property
    def game_over(self) -> bool:
        return self.winner != Winner.NONE

    def living_demogorgons(self) -> List[Demogorgon]:
        return [d for d in self.demogorgons if d.alive]

    def enemy_positions(self) -> Set[Pos]:
        """Cells occupied by hostile characters. DESIGN DECISION: characters are obstacles
        for movement (nobody can stand on another character's cell); attacks target adjacent cells."""
        cells = {d.pos for d in self.demogorgons if d.alive}
        cells.add(self.vecna.pos)
        return cells

    def is_blocked(self, p: Pos) -> bool:
        """True if p cannot be entered right now: wall/out-of-bounds or Mind Flayer corruption."""
        return (not self.board.is_walkable(p)) or p in self.corrupted

    def log(self, msg: str) -> None:
        self.event_log.append(f"[T{self.turn}] {msg}")
