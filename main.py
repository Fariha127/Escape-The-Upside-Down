"""Escape the Upside Down - entry point (Phase 8: menu, HUD, AI panel, results screen). Run: python main.py

The screens live in ui/. This file only creates the window and switches between them.

Human controls: WASD/arrows move | Space wait | E attack adjacent Demogorgon | F rescue a friend in range
1 Radar | 2 Speed | 3 Teleport (then click a highlighted cell, Esc cancels) | 4 Freeze | X final attack
Speed: after the first move the game asks for a second move (Space = skip it).

AI controls: T switch AI-vs-AI on/off | N the AI plays ONE turn (also works in human mode)
In AI-vs-AI mode: Space pause/resume | + / - speed (0.5x 1x 2x 4x) | on-screen buttons do the same
Always: P show paths (A*, Eleven's goal, Vecna's last choice) | R restart | M menu | Esc cancel"""
import pygame

import config
from ui import game_screen, theme
from ui.menu_screens import (MenuScreen, SettingsScreen, TextScreen, algorithm_blocks, howto_blocks)
from ui.results_screen import ResultsScreen
from ui.session import GameSession, ai_turn, new_game  # noqa: F401  (new_game / ai_turn re-exported for the tests)
from ui.stats_view import build_results, stats_lines  # noqa: F401  (stats_lines re-exported for the tests)


class Settings:
    """Menu settings shared by the screens."""

    def __init__(self) -> None:
        self.speed_idx = config.AI_SPEEDS.index(1) if 1 in config.AI_SPEEDS else 0


class App:
    """Screen manager: menu -> game -> results, plus the info pages."""

    def __init__(self) -> None:
        pygame.init()
        probe = GameSession().state
        self.size = game_screen.window_size(probe)
        self.surface = pygame.display.set_mode(self.size)
        pygame.display.set_caption("Escape the Upside Down")
        self.fonts = theme.load_fonts()
        self.settings = Settings()
        self.session = None            # GameSession while a game exists
        self.screen = MenuScreen(self.size)
        self.mode = "menu"             # menu | game | results | info
        self.running = True

    # ---------------------------------------------------------------- navigation
    def go(self, target: str) -> None:
        if target == "menu":
            self.session, self.mode, self.screen = None, "menu", MenuScreen(self.size)
        elif target in ("human", "ai"):
            self.session = GameSession(ai_mode=(target == "ai"))
            self.session.speed_idx = self.settings.speed_idx
            self.mode = "game"
        elif target == "howto":
            self.mode, self.screen = "info", TextScreen(self.size, "How to Play", howto_blocks())
        elif target == "algos":
            self.mode, self.screen = "info", TextScreen(self.size, "AI Algorithms", algorithm_blocks())
        elif target == "settings":
            self.mode, self.screen = "info", SettingsScreen(self.size, self.settings)
        elif target == "results":
            self.mode = "results"
            self.screen = ResultsScreen(self.size, build_results(self.session.state, self.session.tm, self.session.seed))
        elif target == "again":
            ai = self.session.ai_mode
            self.go("ai" if ai else "human")
        elif target == "board":
            self.mode = "game"
        elif target == "quit":
            self.running = False

    # ---------------------------------------------------------------- frame
    def handle(self, e: pygame.event.Event) -> None:
        if e.type == pygame.QUIT:
            self.running = False
        elif self.mode == "game":
            s = self.session
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                btn = next((b for b in game_screen.control_buttons(s.state, s.ai_mode, s.paused) if b.hit(e.pos)), None)
                if btn:
                    s.command(btn.id)
                else:
                    s.handle_event(e)
            else:
                s.handle_event(e)
            if s.request:
                req, s.request = s.request, None
                self.go(req)
        else:
            req = self.screen.handle_event(e)
            if req:
                self.go(req)

    def draw(self) -> None:
        mouse = pygame.mouse.get_pos()
        if self.mode == "game":
            s = self.session
            s.update(pygame.time.get_ticks())
            game_screen.draw(self.surface, s.state, s.tm, self.fonts, s.overlay(),
                             game_screen.control_buttons(s.state, s.ai_mode, s.paused), mouse)
        else:
            self.screen.draw(self.surface, self.fonts, mouse)
        pygame.display.flip()

    def run(self) -> None:
        clock = pygame.time.Clock()
        while self.running:
            for e in pygame.event.get():
                self.handle(e)
            self.draw()
            clock.tick(30)
        pygame.quit()


def main() -> None:
    App().run()


if __name__ == "__main__":
    main()
