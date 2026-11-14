"""Small colourful emoji-style icons for buttons and ability slots, drawn in code (no image or font files).

Each icon is drawn on a big canvas and scaled down, so the edges are smooth. Names: play, pause, step,
slower, faster, ai, paths, restart, menu, speed, teleport, freeze."""
from __future__ import annotations
import math
from typing import Callable, Dict, Tuple

import pygame

SS = 64                                    # canvas size the icons are drawn on
DISABLED_ALPHA = 80
OUTLINE = (30, 30, 50)

_cache: Dict[Tuple[str, int], pygame.Surface] = {}


def _poly(s, color, pts, edge=OUTLINE):
    pygame.draw.polygon(s, color, pts)
    pygame.draw.polygon(s, edge, pts, 3)


def _play(s):
    _poly(s, (60, 200, 100), [(18, 8), (18, 56), (56, 32)])


def _pause(s):
    for x in (14, 36):
        pygame.draw.rect(s, (255, 190, 40), (x, 10, 15, 44), border_radius=5)
        pygame.draw.rect(s, OUTLINE, (x, 10, 15, 44), 3, border_radius=5)


def _step(s):
    _poly(s, (70, 160, 255), [(8, 10), (8, 54), (40, 32)])
    pygame.draw.rect(s, (70, 160, 255), (44, 10, 12, 44), border_radius=4)
    pygame.draw.rect(s, OUTLINE, (44, 10, 12, 44), 3, border_radius=4)


def _slower(s):
    _poly(s, (255, 150, 50), [(32, 12), (32, 52), (6, 32)])
    _poly(s, (255, 150, 50), [(58, 12), (58, 52), (32, 32)])


def _faster(s):
    _poly(s, (170, 225, 60), [(6, 12), (6, 52), (32, 32)])
    _poly(s, (170, 225, 60), [(32, 12), (32, 52), (58, 32)])


def _ai(s):
    pygame.draw.line(s, OUTLINE, (32, 6), (32, 16), 4)
    pygame.draw.circle(s, (255, 70, 70), (32, 8), 6)
    pygame.draw.rect(s, (120, 200, 255), (8, 16, 48, 40), border_radius=10)
    pygame.draw.rect(s, OUTLINE, (8, 16, 48, 40), 3, border_radius=10)
    for x in (22, 42):
        pygame.draw.circle(s, (255, 230, 80), (x, 33), 7)
        pygame.draw.circle(s, OUTLINE, (x, 33), 3)
    pygame.draw.rect(s, OUTLINE, (22, 46, 20, 4), border_radius=2)


def _paths(s):
    for i in range(6):                                           # dotted route
        t = i / 5
        pygame.draw.circle(s, (255, 170, 40), (int(10 + 26 * t), int(54 - 20 * math.sin(t * 3))), 4)
    pygame.draw.circle(s, (235, 60, 60), (46, 20), 13)
    pygame.draw.polygon(s, (235, 60, 60), [(35, 26), (57, 26), (46, 46)])
    pygame.draw.circle(s, (255, 255, 255), (46, 20), 5)


def _restart(s):
    pygame.draw.arc(s, OUTLINE, pygame.Rect(8, 8, 48, 48), math.radians(40), math.radians(330), 13)
    pygame.draw.arc(s, (80, 210, 120), pygame.Rect(10, 10, 44, 44), math.radians(40), math.radians(330), 9)
    _poly(s, (80, 210, 120), [(46, 4), (58, 20), (36, 20)])


def _menu(s):
    for y, c in ((12, (255, 120, 120)), (26, (255, 200, 80)), (40, (110, 200, 255))):
        pygame.draw.rect(s, c, (8, y, 48, 11), border_radius=5)
        pygame.draw.rect(s, OUTLINE, (8, y, 48, 11), 2, border_radius=5)


def _speed(s):
    pts = [(38, 2), (12, 36), (28, 36), (22, 62), (52, 26), (34, 26)]
    _poly(s, (255, 215, 40), pts, (210, 110, 20))


def _teleport(s):
    for r, c in ((29, (110, 60, 200)), (22, (170, 90, 240)), (14, (230, 150, 255)), (7, (255, 255, 255))):
        pygame.draw.circle(s, c, (32, 32), r)
    pygame.draw.circle(s, OUTLINE, (32, 32), 29, 3)
    for a in (30, 150, 270):                                     # little sparkles
        rad = math.radians(a)
        pygame.draw.circle(s, (255, 240, 120), (int(32 + math.cos(rad) * 22), int(32 + math.sin(rad) * 22)), 3)


def _freeze(s):
    ice, white = (90, 200, 255), (235, 250, 255)
    for k in range(3):
        a = math.pi * k / 3
        dx, dy = math.cos(a) * 28, math.sin(a) * 28
        pygame.draw.line(s, ice, (32 - dx, 32 - dy), (32 + dx, 32 + dy), 6)
    for k in range(6):                                           # small branches near each tip
        a = math.pi * k / 3
        bx, by = 32 + math.cos(a) * 18, 32 + math.sin(a) * 18
        for side in (-1, 1):
            b = a + side * 0.8
            pygame.draw.line(s, ice, (bx, by), (bx + math.cos(b) * 8, by + math.sin(b) * 8), 4)
    pygame.draw.circle(s, white, (32, 32), 8)


ICONS: Dict[str, Callable[[pygame.Surface], None]] = {
    "play": _play, "pause": _pause, "step": _step, "slower": _slower, "faster": _faster, "ai": _ai,
    "paths": _paths, "restart": _restart, "menu": _menu, "speed": _speed, "teleport": _teleport,
    "freeze": _freeze,
}


def get(name: str, size: int) -> pygame.Surface:
    """The icon `name` scaled to size x size pixels (cached)."""
    key = (name, size)
    if key not in _cache:
        big = pygame.Surface((SS, SS), pygame.SRCALPHA)
        ICONS[name](big)
        _cache[key] = pygame.transform.smoothscale(big, (size, size))
    return _cache[key]


def draw(surf: pygame.Surface, name: str, centre: Tuple[int, int], size: int, enabled: bool = True) -> None:
    """Draw the icon centred at `centre`; faded when `enabled` is False."""
    if name not in ICONS:
        return
    img = get(name, size)
    if not enabled:
        img = img.copy()
        img.set_alpha(DISABLED_ALPHA)
    surf.blit(img, img.get_rect(center=centre))