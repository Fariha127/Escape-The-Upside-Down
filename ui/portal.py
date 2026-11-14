"""The portal, drawn in code (no picture file needed). Drawing only.

Closed: a dark stone ring with cracks and a dim, still centre. Open: a glowing ring with a swirling bright
centre that turns slowly. Both are drawn at high resolution and scaled down so the edges are smooth."""
from __future__ import annotations
import math
from typing import Dict, Tuple

import pygame

import config
from ui import theme
from ui.theme import CELL

SS = 4                                  # draw this many times bigger, then scale down
SWIRL_ARMS = 3
SWIRL_STEPS = 26
FRAMES = 16                             # open portal: number of turning positions kept in the cache
CLOSED_STONE = (70, 74, 86)
CLOSED_CRACK = (28, 30, 38)
CLOSED_CENTRE = (18, 28, 44)
CLOSED_GLOW = (60, 110, 150)
OPEN_GLOW = theme.CYAN
OPEN_CORE = (230, 252, 255)

_cache: Dict[Tuple[bool, int], pygame.Surface] = {}


def _closed(size: int) -> pygame.Surface:
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    c, r = size // 2, size // 2 - 3 * SS
    pygame.draw.circle(s, (*CLOSED_GLOW, 50), (c, c), r + 2 * SS)
    pygame.draw.circle(s, CLOSED_STONE, (c, c), r)
    pygame.draw.circle(s, CLOSED_CENTRE, (c, c), int(r * 0.66))
    pygame.draw.circle(s, (*CLOSED_GLOW, 120), (c, c), int(r * 0.66), SS)
    for a in (35, 115, 200, 285):                                   # cracks across the stone ring
        rad = math.radians(a)
        p1 = (c + math.cos(rad) * r * 0.70, c + math.sin(rad) * r * 0.70)
        p2 = (c + math.cos(rad + 0.10) * r * 0.86, c + math.sin(rad + 0.10) * r * 0.86)
        p3 = (c + math.cos(rad - 0.05) * r * 0.99, c + math.sin(rad - 0.05) * r * 0.99)
        pygame.draw.lines(s, CLOSED_CRACK, False, [p1, p2, p3], max(1, SS // 2))
    pygame.draw.circle(s, CLOSED_CRACK, (c, c), r, SS // 2 + 1)
    return s


def _open(size: int, phase: float) -> pygame.Surface:
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    c, r = size // 2, size // 2 - 3 * SS
    for k, alpha in ((3, 40), (2, 70), (1, 110)):                    # soft glow around the ring
        pygame.draw.circle(s, (*OPEN_GLOW, alpha), (c, c), r + k * SS)
    pygame.draw.circle(s, (10, 40, 70), (c, c), r)
    for arm in range(SWIRL_ARMS):                                    # swirl arms turning with `phase`
        pts = []
        for i in range(SWIRL_STEPS):
            t = i / (SWIRL_STEPS - 1)
            ang = phase + arm * 2 * math.pi / SWIRL_ARMS + t * 2.6
            rad = r * (0.95 - 0.85 * t)
            pts.append((c + math.cos(ang) * rad, c + math.sin(ang) * rad))
        pygame.draw.lines(s, (*OPEN_GLOW, 230), False, pts, SS * 2)
    pygame.draw.circle(s, (*OPEN_CORE, 255), (c, c), int(r * 0.22))
    pygame.draw.circle(s, OPEN_GLOW, (c, c), r, SS)
    return s


def draw(surf: pygame.Surface, centre: Tuple[float, float], open_: bool, now_ms: int = 0) -> None:
    """Draw the portal on the cell centred at `centre`."""
    frame = int(now_ms / config.PORTAL_TURN_MS) % FRAMES if open_ and config.ANIM_ENABLED else 0
    key = (open_, frame)
    if key not in _cache:
        big = _open(CELL * SS, 2 * math.pi * frame / FRAMES) if open_ else _closed(CELL * SS)
        _cache[key] = pygame.transform.smoothscale(big, (CELL, CELL))
    surf.blit(_cache[key], _cache[key].get_rect(center=(int(centre[0]), int(centre[1]))))