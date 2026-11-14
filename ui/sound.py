"""Sound effects, generated in code (no audio files). Purely a UI add-on: it only listens to what changed
in the GameState after a turn and never touches the game rules or the AIs.

If the computer has no audio device the mixer cannot start and every call quietly does nothing."""
from __future__ import annotations
import math
import struct
from dataclasses import dataclass
from typing import Dict, List, Tuple

import config

# name -> list of (frequency Hz, seconds). A frequency of 0 is a short pause.
TONES: Dict[str, List[Tuple[int, float]]] = {
    "move": [(330, 0.04)],
    "attack": [(520, 0.05), (260, 0.08)],
    "rescue": [(523, 0.08), (659, 0.08), (784, 0.12)],
    "hit": [(180, 0.10), (120, 0.14)],
    "mind_flayer": [(400, 0.10), (300, 0.10), (200, 0.10), (100, 0.20)],
    "portal": [(392, 0.10), (523, 0.10), (659, 0.10), (784, 0.20)],
    "win": [(523, 0.12), (659, 0.12), (784, 0.12), (1047, 0.30)],
    "lose": [(392, 0.20), (330, 0.20), (262, 0.20), (196, 0.40)],
}


@dataclass(frozen=True)
class Snapshot:
    """The few numbers a sound depends on, taken before and after a turn."""
    pos: tuple
    hp: int
    rescued: int
    kills: int
    mind_flayer_defeated: bool
    game_over: bool
    eleven_won: bool
    mind_flayer_awake: bool = False


def snapshot(state) -> Snapshot:
    return Snapshot(state.eleven_pos, state.eleven_hp, len(state.rescued),
                    sum(1 for d in state.demogorgons if not d.alive),
                    state.mind_flayer.defeated, state.game_over, state.winner.name == "ELEVEN",
                    state.mind_flayer.active)


def events_between(a: Snapshot, b: Snapshot) -> List[str]:
    """Sound names for what happened between two snapshots (most important last)."""
    out: List[str] = []
    if b.pos != a.pos:
        out.append("move")
    if b.kills > a.kills:
        out.append("attack")
    if b.rescued > a.rescued:
        out.append("rescue")
    if b.hp < a.hp:
        out.append("hit")
    if b.mind_flayer_awake and not a.mind_flayer_awake:
        out.append("mind_flayer")
    if b.mind_flayer_defeated and not a.mind_flayer_defeated:
        out.append("portal")
    if b.game_over and not a.game_over:
        out.append("win" if b.eleven_won else "lose")
    return out


def render(name: str) -> bytes:
    """16-bit mono samples for one effect (a sine wave with a short fade so it does not click)."""
    rate = config.SOUND_SAMPLE_RATE
    samples: List[int] = []
    for freq, seconds in TONES[name]:
        n = int(rate * seconds)
        for i in range(n):
            fade = min(1.0, i / (n * 0.1 + 1), (n - i) / (n * 0.3 + 1))
            value = math.sin(2 * math.pi * freq * i / rate) * fade if freq else 0.0
            samples.append(int(value * 32767 * config.SOUND_VOLUME))
    return struct.pack(f"<{len(samples)}h", *samples)


class SoundPlayer:
    """Plays the effects. `enabled` can be switched at any time (Settings)."""

    def __init__(self) -> None:
        self.enabled = config.SOUND_ENABLED
        self._sounds: Dict[str, object] = {}
        self._ready = False

    def _start(self) -> bool:
        if self._ready:
            return True
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=config.SOUND_SAMPLE_RATE, size=-16, channels=1)
            self._sounds = {n: pygame.mixer.Sound(buffer=render(n)) for n in TONES}
            self._ready = True
        except Exception:                      # no audio device: stay silent
            self.enabled = False
        return self._ready

    def play(self, names: List[str]) -> None:
        if not (self.enabled and names and self._start()):
            return
        # a moving turn only plays the "move" tick when nothing more important happened
        names = [n for n in names if n != "move"] or names
        self._sounds[names[-1]].play()