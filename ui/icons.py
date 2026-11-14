"""Friend portraits and ability icons, drawn from shapes in code (no image files)."""
from __future__ import annotations
import math

import pygame

from ui import theme


def draw_portrait(surf: pygame.Surface, rect: pygame.Rect, name: str, rescued: bool, font) -> None:
    """A rounded tile with a simple face-like badge and the friend's initial.
    Unrescued friends are greyed out; rescued ones are shown in their own colour."""
    color = theme.FRIEND_COLORS.get(name, theme.GOLD) if rescued else (60, 62, 84)
    pygame.draw.rect(surf, theme.CARD_BG, rect, border_radius=6)
    cx, cy = rect.center
    pygame.draw.circle(surf, color, (cx, cy + 2), rect.width // 2 - 5)
    eye = (10, 10, 20)
    pygame.draw.circle(surf, eye, (cx - 5, cy - 1), 2)
    pygame.draw.circle(surf, eye, (cx + 5, cy - 1), 2)
    letter = font.render(name[0], True, (10, 10, 20) if rescued else (100, 100, 120))
    surf.blit(letter, letter.get_rect(center=(cx, cy + 8)))
    pygame.draw.rect(surf, color if rescued else theme.CARD_EDGE, rect, 2, border_radius=6)


def draw_ability_icon(surf: pygame.Surface, rect: pygame.Rect, ability: str, unlocked: bool,
                      active: bool, uses: int) -> None:
    """One ability symbol: Speed = chevrons, Teleport = portal ring, Freeze = snowflake."""
    usable = unlocked and uses > 0
    color = theme.CYAN if usable else (70, 72, 96)
    pygame.draw.rect(surf, (30, 70, 90) if active else theme.CARD_BG, rect, border_radius=6)
    cx, cy = rect.center
    r = rect.width // 2 - 7
    if ability == "SPEED":
        for off in (-6, 4):
            pygame.draw.lines(surf, color, False,
                              [(cx + off - 5, cy - r + 2), (cx + off + 3, cy), (cx + off - 5, cy + r - 2)], 3)
    elif ability == "TELEPORT":
        pygame.draw.circle(surf, color, (cx, cy), r, 2)
        pygame.draw.circle(surf, color, (cx, cy), r // 2, 2)
        pygame.draw.circle(surf, color, (cx, cy), 2)
    elif ability == "FREEZE":
        for k in range(3):
            a = math.pi * k / 3
            dx, dy = math.cos(a) * r, math.sin(a) * r
            pygame.draw.line(surf, color, (cx - dx, cy - dy), (cx + dx, cy + dy), 2)
    edge = theme.CYAN if active else (theme.CARD_EDGE if usable else (40, 44, 70))
    pygame.draw.rect(surf, edge, rect, 2 if active else 1, border_radius=6)
    if not unlocked:                      # locked: small cross-out
        pygame.draw.line(surf, (90, 60, 70), rect.topleft, rect.bottomright, 2)
