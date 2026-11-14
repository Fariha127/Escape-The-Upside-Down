"""Smooth movement and short flashes. UI only: it watches the GameState between frames and never changes it.

Every piece (Eleven "E", Vecna "V", each Demogorgon "D<i>") keeps the cell it was last drawn at. When the
real state moves it to another cell, the piece slides there over a short time. A drop in Eleven's HP or a
Demogorgon dying starts a flash. Nothing here is a game number: it only decides where to draw."""
from __future__ import annotations
from typing import Dict, List, Optional, Tuple

import config

Cell = Tuple[int, int]


def slide_duration_ms(ai_mode: bool, speed: float) -> int:
    """Length of a slide for the current mode; 0 means do not animate (off, or too fast to see)."""
    if not config.ANIM_ENABLED:
        return 0
    ms = float(config.ANIM_SLIDE_MS)
    if ai_mode:
        ms = min(ms, config.AI_TURN_DELAY_MS / speed * config.ANIM_TURN_FRACTION)
    return int(ms) if ms >= config.ANIM_MIN_MS else 0


def _pieces(state) -> Dict[str, Cell]:
    out = {"E": state.eleven_pos, "V": state.vecna.pos}
    for d in state.demogorgons:
        if d.alive:
            out[f"D{d.id}"] = d.pos
    return out


class Animator:
    def __init__(self) -> None:
        self._last: Dict[str, Cell] = {}
        self._slides: Dict[str, Tuple[Cell, Cell, int, int]] = {}    # key -> (from, to, start_ms, length_ms)
        self.flashes: List[Tuple[str, Cell, int]] = []               # (kind, cell, start_ms)
        self._hp: Optional[int] = None
        self._dead: Optional[set] = None
        self._state_id: Optional[int] = None

    def update(self, state, now_ms: int, slide_ms: int) -> None:
        """Call once per frame with the current state."""
        if id(state) != self._state_id:                      # new game: forget everything
            self.__init__()
            self._state_id = id(state)
        now_pieces = _pieces(state)
        for key, cell in now_pieces.items():
            old = self._last.get(key)
            if old is not None and old != cell and slide_ms > 0:
                dist = abs(old[0] - cell[0]) + abs(old[1] - cell[1])
                if dist <= config.ANIM_MAX_SLIDE_CELLS:
                    self._slides[key] = (old, cell, now_ms, slide_ms)
        self._last = now_pieces
        if self._hp is not None and state.eleven_hp < self._hp and config.ANIM_ENABLED:
            self.flashes.append(("hit", state.eleven_pos, now_ms))
        self._hp = state.eleven_hp
        dead = {d.id for d in state.demogorgons if not d.alive}
        if self._dead is not None and config.ANIM_ENABLED:
            for d in state.demogorgons:
                if d.id in dead - self._dead:
                    self.flashes.append(("kill", d.pos, now_ms))
        self._dead = dead
        self.flashes = [f for f in self.flashes if now_ms - f[2] < config.ANIM_FLASH_MS]
        self._slides = {k: v for k, v in self._slides.items() if now_ms - v[2] < v[3]}

    def cell_pos(self, key: str, cell: Cell, now_ms: int) -> Tuple[float, float]:
        """Where to draw a piece (in cell units): its cell, or part of the way from the previous one."""
        s = self._slides.get(key)
        if s is None:
            return cell
        frm, to, start, length = s
        t = min(1.0, max(0.0, (now_ms - start) / length))
        t = t * t * (3 - 2 * t)                              # ease in/out
        return frm[0] + (to[0] - frm[0]) * t, frm[1] + (to[1] - frm[1]) * t

    def flash_strength(self, start_ms: int, now_ms: int) -> float:
        """1.0 at the start of a flash, fading to 0."""
        return max(0.0, 1.0 - (now_ms - start_ms) / config.ANIM_FLASH_MS)