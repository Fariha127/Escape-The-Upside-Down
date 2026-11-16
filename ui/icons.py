"""Friend portraits and ability icons, friend pictures (from assets) and ability icons drawn in code."""
from __future__ import annotations
from typing import Dict, Optional, Tuple

import pygame

import config
from ui import emoji, sprites, theme

MF_TILE_BG = (255, 255, 255)             # white, so the dark Mind Flayer picture can be seen
MF_ASLEEP_ALPHA = 130                    # the picture is faded while the Mind Flayer is still asleep
MF_DEFEATED_ALPHA = 70
MF_PAD = 4
MF_LOOM_ALPHA = 25                      # how strongly the looming Mind Flayer shows over the board (0-255)
MF_LOOM_TINT = (190, 30, 60)             # added to the dark picture so it glows red on the dark board
MF_LOOM_WIDTH = 0.9                      # picture width as a share of the board width
MF_LOOM_DROP = 60                        # how far below the top of the board the picture starts (pixels)
MF_BORDER_ALPHA = 150
MF_BORDER_W = 5
_loom_cache: Dict[Tuple[int, int], Optional[pygame.Surface]] = {}
THUMB_BG, THUMB_EDGE = (46, 52, 88), (84, 94, 146)   # tile behind a small character picture
_thumb_cache: Dict[Tuple[str, int], Optional[pygame.Surface]] = {}
_mf_cache: Dict[Tuple[int, int], Optional[pygame.Surface]] = {}

HEART_STEP = 17                          # distance between two hearts in the HUD
UNRESCUED_LIFT = 70                      # added to the grey picture of a friend who is not rescued yet (brighter)
UNRESCUED_TILE_BG = (78, 84, 122)        # lighter tile behind that grey picture

def draw_portrait(surf: pygame.Surface, rect: pygame.Rect, name: str, rescued: bool, font) -> None:
    """A rounded tile with the friend's picture (or a simple face-like badge and the initial if there is no picture).
    Unrescued friends are shown in grey; rescued ones are shown in their own colour."""
    color = theme.FRIEND_COLORS.get(name, theme.GOLD) if rescued else (60, 62, 84)
    pygame.draw.rect(surf, theme.CARD_BG if rescued else UNRESCUED_TILE_BG, rect, border_radius=6)
    pic = sprites.load(name.lower()) if config.SPRITES_ENABLED else None
    if pic is not None:                   # the friend's picture; grey until they are rescued
        if not rescued:
            pic = pygame.transform.grayscale(pic)
            pic.fill((UNRESCUED_LIFT, UNRESCUED_LIFT, UNRESCUED_LIFT, 0), special_flags=pygame.BLEND_RGB_ADD)
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




def draw_mind_flayer_card(surf: pygame.Surface, rect: pygame.Rect, awake: bool, defeated: bool, edge=None) -> None:
    """The Mind Flayer's picture on a white tile (it has no board cell). Faded while asleep or defeated,
    full colour with a red border while awake. Does nothing if assets/characters/mind_flayer.png is missing."""
    key = (rect.width, rect.height)
    if key not in _mf_cache:
        _mf_cache[key] = None
        path = sprites.ASSET_DIR / "mind_flayer.png"
        if path.is_file():
            try:
                src = pygame.image.load(str(path)).convert_alpha()
                k = min((rect.width - 2 * MF_PAD) / src.get_width(), (rect.height - 2 * MF_PAD) / src.get_height())
                _mf_cache[key] = pygame.transform.smoothscale(
                    src, (max(1, int(src.get_width() * k)), max(1, int(src.get_height() * k))))
            except (pygame.error, OSError):
                pass
    pic = _mf_cache[key]
    if pic is None or not config.SPRITES_ENABLED:
        return
    pygame.draw.rect(surf, MF_TILE_BG, rect, border_radius=6)
    shown = pic.copy()
    if defeated:
        shown.set_alpha(MF_DEFEATED_ALPHA)
    elif not awake:
        shown.set_alpha(MF_ASLEEP_ALPHA)
    surf.blit(shown, shown.get_rect(center=rect.center))
    edge = edge or (theme.RED if awake and not defeated else theme.CARD_EDGE)
    pygame.draw.rect(surf, edge, rect, 2, border_radius=6)



def draw_mind_flayer_looming(surf: pygame.Surface, board_rect: pygame.Rect) -> None:
    """While the Mind Flayer is awake: its picture looms over the board in dark red and the board gets a red
    edge. It has no cell of its own (it acts from the Upside Down), so this is only drawing, no game rule."""
    edge = pygame.Surface(board_rect.size, pygame.SRCALPHA)
    pygame.draw.rect(edge, (*theme.RED, MF_BORDER_ALPHA), edge.get_rect(), MF_BORDER_W)
    key = (board_rect.width, board_rect.height)
    if key not in _loom_cache:
        _loom_cache[key] = None
        path = sprites.ASSET_DIR / "mind_flayer.png"
        if path.is_file():
            try:
                src = pygame.image.load(str(path)).convert_alpha()
                k = min(board_rect.width * MF_LOOM_WIDTH / src.get_width(), board_rect.height / src.get_height())
                pic = pygame.transform.smoothscale(
                    src, (max(1, int(src.get_width() * k)), max(1, int(src.get_height() * k))))
                pic.fill((*MF_LOOM_TINT, 0), special_flags=pygame.BLEND_RGBA_ADD)
                pic.set_alpha(MF_LOOM_ALPHA)
                _loom_cache[key] = pic
            except (pygame.error, OSError):
                pass
    pic = _loom_cache[key]
    if pic is not None and config.SPRITES_ENABLED:
        surf.blit(pic, pic.get_rect(midtop=(board_rect.centerx, board_rect.top + MF_LOOM_DROP)))
    surf.blit(edge, board_rect.topleft)



def draw_hearts(surf: pygame.Surface, topleft: Tuple[int, int], value: int, maximum: int, color, empty,
                step: int = HEART_STEP, size: int = 7) -> None:
    """A row of hearts: `value` filled, the rest empty (one heart per HP point)."""
    x0, y0 = topleft
    for k in range(maximum):
        c = color if k < value else empty
        cx = x0 + k * step + size
        pygame.draw.circle(surf, c, (cx - size // 2, y0 + size // 2 + 1), size // 2 + 1)
        pygame.draw.circle(surf, c, (cx + size // 2, y0 + size // 2 + 1), size // 2 + 1)
        pygame.draw.polygon(surf, c, [(cx - size - 1, y0 + size // 2 + 3), (cx + size + 1, y0 + size // 2 + 3),
                                      (cx, y0 + size * 2 + 1)])

def draw_thumb(surf: pygame.Surface, name: Optional[str], topright: Tuple[int, int], width: int, height: int) -> None:
    """A small character picture on a tile (for the title row of a panel card). name None = the Mind Flayer on its
    white tile. Does nothing if the picture file is missing."""
    rect = pygame.Rect(0, 0, width, height)
    rect.topright = topright
    if not config.SPRITES_ENABLED:
        return
    if name is None:
        draw_mind_flayer_card(surf, rect, True, False, edge=theme.CARD_EDGE)
        return
    key = (name, height)
    if key not in _thumb_cache:
        pic = sprites.load(name)
        if pic is not None:
            k = (height - 2) / pic.get_height()
            pic = pygame.transform.smoothscale(pic, (max(1, int(pic.get_width() * k)), height - 2))
        _thumb_cache[key] = pic
    pic = _thumb_cache[key]
    if pic is None:
        return
    pygame.draw.rect(surf, THUMB_BG, rect, border_radius=5)
    pygame.draw.rect(surf, THUMB_EDGE, rect, 1, border_radius=5)
    surf.blit(pic, pic.get_rect(center=rect.center))
