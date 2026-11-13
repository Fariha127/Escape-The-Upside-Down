"""Game-over summary. Built by ui.stats_view.build_results from the final GameState and the Metrics only."""
from __future__ import annotations
from typing import Optional

import pygame

from ui import theme
from ui.menu_screens import Screen
from ui.stats_view import Results
from ui.widgets import Button, button_at, draw_text


class ResultsScreen(Screen):
    def __init__(self, size, results: Results):
        self.size, self.results = size, results
        w, h = size
        y = h - 64
        self.buttons = [
            Button(pygame.Rect(w // 2 - 305, y, 190, 40), "Play again", "again", hint="R"),
            Button(pygame.Rect(w // 2 - 95, y, 190, 40), "View board", "board", hint="Esc"),
            Button(pygame.Rect(w // 2 + 115, y, 190, 40), "Main menu", "menu", hint="M"),
        ]

    def handle_event(self, e) -> Optional[str]:
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            b = button_at(self.buttons, e.pos)
            return b.id if b else None
        if e.type == pygame.KEYDOWN:
            return {pygame.K_r: "again", pygame.K_m: "menu", pygame.K_ESCAPE: "board",
                    pygame.K_RETURN: "again"}.get(e.key)
        return None

    def draw(self, surf, fonts, mouse_pos=None):
        surf.fill(theme.BG)
        r, w = self.results, surf.get_width()
        draw_text(surf, fonts.title, r.headline, (w // 2, 48), theme.CYAN if r.eleven_won else theme.RED, "center")
        y = 100
        col_a, col_b = 90, 320
        draw_text(surf, fonts.body, "Game summary", (col_a, y), theme.GOLD)
        y += 30
        for label, value in r.rows:
            draw_text(surf, fonts.small, label, (col_a, y), theme.DIM)
            draw_text(surf, fonts.small, value, (col_b, y), theme.TEXT)
            y += 22
        y += 18
        draw_text(surf, fonts.body, "AI search statistics (from real runs)", (col_a, y), theme.GOLD)
        y += 30
        for label, value in r.ai_rows:
            draw_text(surf, fonts.small, label, (col_a, y), theme.DIM)
            draw_text(surf, fonts.small, value, (col_b, y), theme.GREEN)
            y += 22
        for b in self.buttons:
            b.draw(surf, fonts.body, mouse_pos)
