"""Friend portraits and ability icons, friend pictures (from assets) and ability icons drawn in code."""
from __future__ import annotations

import pygame

import config
from ui import emoji, sprites, theme

UNRESCUED_SHADE = (60, 60, 85)           # multiplied into a friend's picture until they are rescued


def draw_portrait(surf: pygame.Surface, rect: pygame.Rect, name: str, rescued: bool, font) -> None:
    """A rounded tile with a simple face-like badge and the friend's initial.
    Unrescued friends are greyed out; rescued ones are shown in their own colour."""
    color = theme.FRIEND_COLORS.get(name, theme.GOLD) if rescued else (60, 62, 84)
    pygame.draw.rect(surf, theme.CARD_BG, rect, border_radius=6)
    pic = sprites.load(name.lower()) if config.SPRITES_ENABLED else None
    if pic is not None:                   # the friend's picture; dark until they are rescued
        if not rescued:
            pic = pic.copy()
            pic.fill((*UNRESCUED_SHADE, 255), special_flags=pygame.BLEND_RGBA_MULT)
        surf.blit(pic, pic.get_rect(midbottom=(rect.centerx, rect.bottom - 3)))
        pygame.draw.rect(surf, color if rescued else theme.CARD_EDGE, rect, 2, border_radius=6)
        return
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
    """One ability symbol: Speed = lightning bolt, Teleport = purple portal, Freeze = snowflake."""
    usable = unlocked and uses > 0
    pygame.draw.rect(surf, (30, 70, 90) if active else theme.CARD_BG, rect, border_radius=6)
    emoji.draw(surf, ability.lower(), rect.center, rect.width - 10, usable)
    edge = theme.CYAN if active else (theme.CARD_EDGE if usable else (40, 44, 70))
    pygame.draw.rect(surf, edge, rect, 2 if active else 1, border_radius=6)
    if not unlocked:                      # locked: small cross-out
        pygame.draw.line(surf, (90, 60, 70), rect.topleft, rect.bottomright, 2)