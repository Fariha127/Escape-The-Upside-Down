"""Turns state.event_log into coloured, scrollable lines for the event log panel. Read-only: it only parses the
text the game already wrote ("[T12] Eleven takes 1 damage from Vecna (HP 4)"); nothing is added or invented."""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

_LINE = re.compile(r"^\[T(\d+)\]\s*(.*)$")


@dataclass(frozen=True)
class LogEntry:
    turn: Optional[int]      # None if the line has no "[T<n>]" prefix
    text: str
    category: str            # damage | kill | rescue | mind_flayer | ability | win | loss | other


def classify(text: str) -> str:
    """Category of one log message, used only to pick its colour."""
    if "escaped through the portal" in text or "Mind Flayer is defeated" in text:
        return "win"
    if "has fallen" in text or "Turn limit reached" in text:
        return "loss"
    if text.startswith("Eleven takes"):
        return "damage"
    if "defeats Demogorgon" in text:
        return "kill"
    if text.startswith("Rescue"):
        return "rescue"
    if "Mind Flayer" in text or "MIND FLAYER" in text:
        return "mind_flayer"
    if text.startswith(("Freeze", "Speed", "Radar", "Teleport")):
        return "ability"
    return "other"


def parse(line: str) -> LogEntry:
    m = _LINE.match(line)
    text = m.group(2) if m else line
    return LogEntry(int(m.group(1)) if m else None, text, classify(text))


def visible_entries(event_log: List[str], capacity: int, offset: int = 0) -> Tuple[List[LogEntry], int, int]:
    """The `capacity` entries to show, oldest first (the newest is the last line).

    offset = how many entries the view is scrolled back from the newest (0 = following the newest).
    Returns (entries, older, newer): how many entries are hidden above and below the view."""
    capacity = max(1, capacity)
    offset = min(max(0, offset), max(0, len(event_log) - capacity))
    end = len(event_log) - offset
    start = max(0, end - capacity)
    return [parse(l) for l in event_log[start:end]], start, offset
