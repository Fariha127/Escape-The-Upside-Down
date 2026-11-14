"""Small reusable drawing helpers: text, bars, buttons, word wrap."""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple

import pygame

from ui import emoji, theme


def draw_text(surf: pygame.Surface, font: pygame.font.Font, text: str, pos: Tuple[int, int],
              color=theme.TEXT, anchor: str = "topleft") -> pygame.Rect:
    """Render text with the given rect anchor ('topleft', 'center', 'topright', ...)."""
    img = font.render(text, True, color)
    rect = img.get_rect(**{anchor: pos})
    surf.blit(img, rect)
    return rect


def wrap_text(font: pygame.font.Font, text: str, width: int) -> List[str]:
    """Greedy word wrap so a paragraph fits in `width` pixels."""
    lines: List[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for word in paragraph.split():
            trial = f"{current} {word}".strip()
            if current and font.size(trial)[0] > width:
                lines.append(current)
                current = word
            else:
                current = trial
        lines.append(current)
    return lines


def draw_bar(surf: pygame.Surface, rect: pygame.Rect, value: float, maximum: float, color,
             back=(30, 34, 58), edge=theme.CARD_EDGE) -> None:
    """Horizontal filled bar (value/maximum)."""
    pygame.draw.rect(surf, back, rect, border_radius=4)
    if maximum > 0 and value > 0:
        w = max(2, int(rect.width * min(1.0, value / maximum)))
        pygame.draw.rect(surf, color, (rect.x, rect.y, w, rect.height), border_radius=4)
    pygame.draw.rect(surf, edge, rect, 1, border_radius=4)

ICON_PAD = 4                  # space around a button's icon
@dataclass
class Button:
    """A clickable rectangle. `id` is what the owning screen reacts to."""
    rect: pygame.Rect
    label: str
    id: str
    enabled: bool = True
    active: bool = False          # drawn highlighted (e.g. a toggle that is ON)
    hint: str = ""                # small key hint shown under/next to the label
    icon: str = ""                # name of a colourful icon from ui/emoji.py, drawn left of the label

    def hit(self, pos) -> bool:
        return self.enabled and self.rect.collidepoint(pos)

    def draw(self, surf: pygame.Surface, font: pygame.font.Font, mouse_pos=None,
             focused: bool = False) -> None:
        hover = mouse_pos is not None and self.rect.collidepoint(mouse_pos) and self.enabled
        if not self.enabled:
            fill, edge, text = (24, 27, 44), (40, 44, 70), (80, 80, 100)
        elif self.active:
            fill, edge, text = (30, 70, 90), theme.CYAN, theme.TEXT
        elif hover or focused:
            fill, edge, text = (40, 46, 84), theme.CYAN, theme.TEXT
        else:
            fill, edge, text = theme.CARD_BG, theme.CARD_EDGE, theme.TEXT
        pygame.draw.rect(surf, fill, self.rect, border_radius=6)
        pygame.draw.rect(surf, edge, self.rect, 2 if (hover or focused) else 1, border_radius=6)
        label = f"{self.label} [{self.hint}]" if self.hint else self.label
        if self.icon:
            size = self.rect.height - 2 * ICON_PAD
            emoji.draw(surf, self.icon, (self.rect.x + ICON_PAD + size // 2, self.rect.centery), size, self.enabled)
            draw_text(surf, font, label, (self.rect.x + ICON_PAD + size + (self.rect.width - ICON_PAD - size) // 2,
                                          self.rect.centery), text, "center")
        else:
            draw_text(surf, font, label, self.rect.center, text, "center")

def button_at(buttons: List[Button], pos) -> Optional[Button]:
    """The enabled button under `pos`, if any."""
    for b in buttons:
        if b.hit(pos):
            return b
    return None
