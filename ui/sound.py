"""Sound effects, generated in code (no audio files). Purely a UI add-on: it only listens to what changed
in the GameState after a turn and never touches the game rules or the AIs.

If the computer has no audio device the mixer cannot start and every call quietly does nothing."""
from __future__ import annotations
import array
import math
import struct
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import config

# name -> list of (frequency Hz, seconds). A frequency of 0 is a short pause.
TONES: Dict[str, List[Tuple[int, float]]] = {
    "move": [(330, 0.04)],
    "attack": [(520, 0.05), (260, 0.08)],
    "rescue": [(523, 0.08), (659, 0.08), (784, 0.12)],
    "hit": [(260, 0.06), (200, 0.08)],                          # hurt by something else (a hazard)
    "hit_demogorgon": [(180, 0.10), (120, 0.14)],
    "hit_vecna": [(90, 0.12), (70, 0.12), (55, 0.22)],         # deeper and heavier than the Demogorgon's hit
    "mind_flayer": [(400, 0.10), (300, 0.10), (200, 0.10), (100, 0.20)],
    "gate": [(392, 0.10), (523, 0.10), (659, 0.10), (784, 0.20)],
    "win": [(523, 0.12), (659, 0.12), (784, 0.12), (1047, 0.30)],
    "lose": [(392, 0.20), (330, 0.20), (262, 0.20), (196, 0.40)],
}

# A sound can also come from a file: put assets/sounds/<name>.wav (a normal .wav) with one of the names in TONES
# and it is used instead of the generated tone. A missing or unreadable file just keeps the generated tone.
SOUND_DIR = Path(__file__).resolve().parent.parent / "assets" / "sounds"
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
    log_len: int = 0                 # how many event log lines existed (to find the new ones)


def snapshot(state) -> Snapshot:
    return Snapshot(state.eleven_pos, state.eleven_hp, len(state.rescued),
                    sum(1 for d in state.demogorgons if not d.alive),
                    state.mind_flayer.defeated, state.game_over, state.winner.name == "ELEVEN",
                    state.mind_flayer.active, len(state.event_log))


def hit_sounds(new_log: Sequence[str]) -> List[str]:
    """Which hit sounds to play, read from the new "Eleven takes N damage from <who>" log lines. Vecna comes last
    (the last sound is the one played)."""
    out: List[str] = []
    for line in new_log:
        if "damage from Demogorgon" in line and "hit_demogorgon" not in out:
            out.append("hit_demogorgon")
    if any("damage from Vecna" in line for line in new_log):
        out.append("hit_vecna")
    return out or ["hit"]


def events_between(a: Snapshot, b: Snapshot, new_log: Sequence[str] = ()) -> List[str]:
    """Sound names for what happened between two snapshots (most important last)."""
    out: List[str] = []
    if b.pos != a.pos:
        out.append("move")
    if b.kills > a.kills:
        out.append("attack")
    if b.rescued > a.rescued:
        out.append("rescue")
    if b.hp < a.hp:
        out.extend(hit_sounds(new_log))
    if b.mind_flayer_awake and not a.mind_flayer_awake:
        out.append("mind_flayer")
    if b.mind_flayer_defeated and not a.mind_flayer_defeated:
        out.append("gate")
    if b.game_over and not a.game_over:
        out.append("win" if b.eleven_won else "lose")
    return out

def load_wav(path: Path) -> Optional[bytes]:
    """A .wav file as 16-bit mono samples at SOUND_SAMPLE_RATE, cut to SOUND_FILE_MAX_SECONDS with a fade-out.
    Returns None if the file is missing or is not a plain 16-bit .wav."""
    try:
        with wave.open(str(path), "rb") as w:
            channels, width, src_rate, frames = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
            if width != 2 or channels < 1 or src_rate < 1:
                return None
            raw = array.array("h")
            raw.frombytes(w.readframes(min(frames, int(src_rate * config.SOUND_FILE_MAX_SECONDS))))
    except (OSError, EOFError, wave.Error):
        return None
    mono = [sum(raw[i:i + channels]) / channels for i in range(0, len(raw) - channels + 1, channels)]
    if not mono:
        return None
    rate = config.SOUND_SAMPLE_RATE
    count = int(len(mono) * rate / src_rate)
    out: List[int] = []
    fade = max(1, int(rate * config.SOUND_FILE_FADE_SECONDS))
    for i in range(count):
        pos = i * src_rate / rate                         # linear resampling to the mixer's rate
        j = min(int(pos), len(mono) - 1)
        nxt = mono[min(j + 1, len(mono) - 1)]
        value = mono[j] + (nxt - mono[j]) * (pos - j)
        value *= min(1.0, (count - i) / fade)             # fade out at the end
        out.append(int(max(-32767, min(32767, value * config.SOUND_VOLUME))))
    return struct.pack(f"<{len(out)}h", *out) if out else None


def render(name: str) -> bytes:
    """16-bit mono samples: from assets/sounds/<name>.wav if present, otherwise a generated sine tone."""
    from_file = load_wav(SOUND_DIR / f"{name}.wav")
    if from_file:
        return from_file
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
            init = pygame.mixer.get_init()      # (freq, format, channels) or None
            if init != (config.SOUND_SAMPLE_RATE, -16, 1):
                pygame.mixer.quit()
                pygame.mixer.init(frequency=config.SOUND_SAMPLE_RATE, size=-16, channels=1, buffer=1024)
            self._sounds = {n: pygame.mixer.Sound(buffer=render(n)) for n in TONES}
            self._ready = True
        except Exception as err:               # no audio device or a broken sound: stay silent, but say why
            print(f"Sound is off: {type(err).__name__}: {err}")
            self.enabled = False
        return self._ready

    def play(self, names: List[str]) -> None:
        if not (self.enabled and names and self._start()):
            return
        # a moving turn only plays the "move" tick when nothing more important happened
        names = [n for n in names if n != "move"] or names
        self._sounds[names[-1]].play()