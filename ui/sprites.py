"""Character pictures for the board. Drawing only.

If assets/characters/<name>.png exists, the board shows that picture (scaled to one cell, standing on a soft
shadow). If a file is missing, the old letter marker is used for that character, so the game always works.
Names: eleven, vecna, demogorgon, mike, dustin, lucas, will, portal. A Mind Flayer creature reuses
demogorgon with a purple tint."""
from __future__ import annotations
from pathlib import Path
from typing import Dict, Optional, Tuple

import pygame

import config
from ui.theme import CELL

ASSET_DIR = Path(__file__).resolve().parent.parent / "assets" / "characters"
FIT_W, FIT_H = CELL - 2, CELL - 2          # the picture is scaled to fit inside this box
SHADOW_ALPHA = 110
TINT_PURPLE = (190, 120, 255)              # multiplied into the picture for temporary creatures

_cache: Dict[Tuple[str, Optional[tuple]], Optional[pygame.Surface]] = {}


def load(name: str, tint: Optional[tuple] = None) -> Optional[pygame.Surface]:
    """The scaled picture for `name`, or None if there is no file for it."""
    key = (name, tint)
    if key not in _cache:
        path = ASSET_DIR / f"{name}.png"
        pic = None
        if path.is_file():
            try:
                src = pygame.image.load(str(path)).convert_alpha()
                scale = min(FIT_W / src.get_width(), FIT_H / src.get_height())
                pic = pygame.transform.smoothscale(src, (max(1, int(src.get_width() * scale)),
                                                         max(1, int(src.get_height() * scale))))
                if tint:
                    pic.fill((*tint, 255), special_flags=pygame.BLEND_RGBA_MULT)
            except (pygame.error, OSError):
                pic = None
        _cache[key] = pic
    return _cache[key]


def draw(surf: pygame.Surface, name: str, centre: Tuple[float, float], tint: Optional[tuple] = None) -> bool:
    """Draw the character on the cell centred at `centre`. Returns False if it has no picture."""
    if not config.SPRITES_ENABLED:
        return False
    pic = load(name, tint)
    if pic is None:
        return False
    cx, cy = centre
    foot = int(cy + CELL // 2 - 2)
    shadow = pygame.Surface((CELL - 8, 8), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, SHADOW_ALPHA), shadow.get_rect())
    surf.blit(shadow, (int(cx) - shadow.get_width() // 2, foot - 6))
    surf.blit(pic, pic.get_rect(midbottom=(int(cx), foot)))
    return True