"""Colours, fonts and layout constants shared by every screen (no game logic here)."""
from __future__ import annotations
from dataclasses import dataclass

import pygame

# --- layout (pixels) ---
CELL = 36                 # one board cell
HUD_H = 172               # height of the HUD strip above the board
PANEL_W = 420             # width of the AI side panel to the right of the board
LINE_H = 14               # line spacing inside panel cards
CARD_HEADER_H = 22        # title row of a panel card

# --- colours ---
BG = (8, 10, 22)
PANEL_BG = (13, 16, 32)
CARD_BG = (21, 25, 48)
CARD_EDGE = (44, 50, 86)
GRID_LINE = (34, 38, 62)
TEXT = (230, 230, 240)
DIM = (130, 130, 160)
GOLD = (240, 200, 60)
RED = (220, 40, 50)
CYAN = (80, 220, 255)
GREEN = (110, 200, 130)
PURPLE = (150, 70, 200)
ORANGE = (240, 140, 50)
HP_COLOR = (210, 60, 70)
POWER_COLOR = (240, 200, 60)

LOG_COLORS = {            # event log text colour per category (see ui/log_view.py)
    "damage": (235, 90, 100), "kill": (240, 150, 60), "rescue": (110, 200, 130),
    "mind_flayer": (190, 120, 240), "ability": (80, 220, 255), "win": (240, 200, 60),
    "loss": (235, 90, 100), "other": (200, 200, 215),
}

FRIEND_COLORS = {
    "Mike": (90, 160, 255),
    "Dustin": (240, 200, 60),
    "Lucas": (110, 200, 120),
    "Will": (200, 140, 255),
}
FRIEND_ORDER = ("Mike", "Dustin", "Lucas", "Will")

FONT_NAMES = "consolas,dejavusansmono,monospace"


@dataclass
class Fonts:
    title: pygame.font.Font      # screen titles
    big: pygame.font.Font        # "ESCAPED!" banner
    body: pygame.font.Font       # normal text
    small: pygame.font.Font      # panel text
    tiny: pygame.font.Font       # captions


def load_fonts() -> Fonts:
    """Create the fonts once pygame is initialised."""
    def mk(size: int, bold: bool = False) -> pygame.font.Font:
        return pygame.font.SysFont(FONT_NAMES, size, bold=bold)
    return Fonts(title=mk(40, True), big=mk(48, True), body=mk(18), small=mk(14), tiny=mk(12))
