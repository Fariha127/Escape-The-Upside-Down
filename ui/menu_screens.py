"""Main menu, How to Play, AI Algorithms and Settings screens. No game logic: they only report what the
player chose. Every number on the AI Algorithms page is read from config.py."""
from __future__ import annotations
from typing import List, Optional

import pygame

import config
from ui import theme
from ui.widgets import Button, button_at, draw_text, wrap_text

TITLE = "Escape the Upside Down"


class Screen:
    """Base class: handle_event returns a request string ("human", "ai", "howto", ...) or None."""

    def handle_event(self, e: pygame.event.Event) -> Optional[str]:
        return None

    def update(self, now_ms: int) -> None:
        pass

    def draw(self, surf: pygame.Surface, fonts: theme.Fonts, mouse_pos=None) -> None:
        pass


def _backdrop(surf: pygame.Surface, fonts: theme.Fonts, title: str) -> None:
    surf.fill(theme.BG)
    w = surf.get_width()
    for i in range(0, w, 60):                     # faint vertical "vines"
        pygame.draw.line(surf, (14, 12, 28), (i, 0), (i + 30, surf.get_height()), 2)
    draw_text(surf, fonts.title, title, (w // 2, 50), theme.RED, "center")


class MenuScreen(Screen):
    ITEMS = (("Human vs AI", "human"), ("AI vs AI", "ai"), ("How to Play", "howto"),
             ("AI Algorithms", "algos"), ("Settings", "settings"), ("Quit", "quit"))

    def __init__(self, size):
        self.size = size
        self.focus = 0
        w, h = size
        bw, bh, gap = 320, 48, 12
        x = (w - bw) // 2
        y0 = 190
        self.buttons: List[Button] = [Button(pygame.Rect(x, y0 + i * (bh + gap), bw, bh), label, id_)
                                      for i, (label, id_) in enumerate(self.ITEMS)]

    def handle_event(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            b = button_at(self.buttons, e.pos)
            return b.id if b else None
        if e.type == pygame.MOUSEMOTION:
            for i, b in enumerate(self.buttons):
                if b.rect.collidepoint(e.pos):
                    self.focus = i
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_DOWN, pygame.K_s):
                self.focus = (self.focus + 1) % len(self.buttons)
            elif e.key in (pygame.K_UP, pygame.K_w):
                self.focus = (self.focus - 1) % len(self.buttons)
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                return self.buttons[self.focus].id
            elif e.key == pygame.K_1:
                return "human"
            elif e.key == pygame.K_2:
                return "ai"
        return None

    def draw(self, surf, fonts, mouse_pos=None):
        _backdrop(surf, fonts, TITLE)
        w = surf.get_width()
        draw_text(surf, fonts.small, "Rescue Mike, Dustin, Lucas and Will, defeat the Mind Flayer, reach the portal.",
                  (w // 2, 112), theme.DIM, "center")
        draw_text(surf, fonts.small, "A game that shows AI search algorithms at work: A*, Minimax + Alpha-Beta, MCTS.",
                  (w // 2, 134), theme.DIM, "center")
        for i, b in enumerate(self.buttons):
            b.draw(surf, fonts.body, mouse_pos, focused=(i == self.focus))
        draw_text(surf, fonts.tiny, "Up/Down + Enter, or click.  1 = Human vs AI, 2 = AI vs AI",
                  (w // 2, surf.get_height() - 24), theme.DIM, "center")


class TextScreen(Screen):
    """A scrollable-free page of headed paragraphs with a Back button."""

    def __init__(self, size, title: str, blocks):
        self.size, self.title, self.blocks = size, title, blocks
        w, h = size
        self.back = Button(pygame.Rect(w // 2 - 80, h - 56, 160, 36), "Back", "menu", hint="Esc")

    def handle_event(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.back.hit(e.pos):
            return "menu"
        if e.type == pygame.KEYDOWN and e.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_BACKSPACE):
            return "menu"
        return None

    def draw(self, surf, fonts, mouse_pos=None):
        _backdrop(surf, fonts, self.title)
        w = surf.get_width()
        x, y, width = 50, 100, w - 100
        for heading, body in self.blocks:
            draw_text(surf, fonts.body, heading, (x, y), theme.GOLD)
            y += 24
            for line in wrap_text(fonts.small, body, width):
                draw_text(surf, fonts.small, line, (x + 10, y), theme.TEXT)
                y += 17
            y += 10
        self.back.draw(surf, fonts.body, mouse_pos)


def howto_blocks():
    return [
        ("Goal", "Eleven must rescue all 4 friends, defeat the Mind Flayer with the final attack, and then stand on "
                 f"the portal. She loses if her HP reaches 0 or after {config.MAX_TURNS} turns."),
        ("Moving", "WASD or the arrow keys move one cell (never diagonally). Space waits. Walls, other characters "
                   "and cells corrupted by the Mind Flayer block you. Entering a hazard cell costs "
                   f"{config.HAZARD_DAMAGE} HP."),
        ("Fighting", f"E attacks an adjacent Demogorgon: it costs {config.DEMOGORGON_ATTACK_COST} power and gives "
                     f"{config.DEMOGORGON_REWARD}. A Demogorgon hit costs {config.DEMOGORGON_DAMAGE} HP, Vecna's hit "
                     f"{config.VECNA_DAMAGE} HP. Vecna cannot be killed."),
        ("Friends", f"F rescues a friend within {config.RESCUE_RANGE} cell. Each rescue gives "
                    f"{config.RESCUE_POWER_BONUS} power and an ability: Dustin Radar (1), Lucas Speed (2), "
                    "Mike Teleport (3, then click a highlighted cell), Will Freeze (4). Rescuing Will wakes the "
                    "Mind Flayer."),
        ("Final attack", f"X needs the Mind Flayer awake and at least {config.FINAL_POWER_REQUIREMENT} power. It "
                         "defeats the Mind Flayer and opens the portal."),
        ("AI controls", "T switches AI vs AI on/off, N lets the AI play one turn, Space pauses, + and - change "
                        "speed, P shows A* paths and Vecna's last Minimax choice, R restarts, M returns to the menu."),
    ]


def algorithm_blocks():
    return [
        ("Eleven: MCTS + A*", f"MCTS ({config.ELEVEN_MCTS_SIMULATIONS} simulations, UCB1 constant "
                              f"{config.MCTS_EXPLORATION}) chooses a strategic goal: rescue a friend, hunt a "
                              "Demogorgon, evade, go to the portal, prepare the final attack or use an ability. "
                              "A* then walks the path to that goal."),
        ("Demogorgons: A*", "Each Demogorgon runs A* with a Manhattan-distance heuristic to chase Eleven and "
                            "re-plans when another character blocks its path."),
        ("Vecna: Minimax + Alpha-Beta", f"Depth {config.MINIMAX_DEPTH}: Vecna is MAX, Eleven is MIN. Alpha-Beta "
                                        "skips branches that cannot change the result. The panel shows nodes "
                                        "evaluated and branches pruned."),
        ("Mind Flayer: MCTS", f"Wakes when Will is rescued. {config.MINDFLAYER_MCTS_SIMULATIONS} simulations pick "
                              "one action per turn: corrupt a cell, summon a temporary creature or wait. "
                              "It has no position on the board."),
        ("About the numbers", "Everything in the AI panel and on the results screen is counted during real "
                              "searches. Nothing is estimated or random."),
    ]


class SettingsScreen(Screen):
    """Only options that already exist in config.py: the starting AI-vs-AI speed and Alpha-Beta on/off for Vecna."""

    def __init__(self, size, settings):
        self.size, self.settings = size, settings
        w, h = size
        self.buttons = [
            Button(pygame.Rect(w // 2 - 190, 170, 380, 44), "", "speed"),
            Button(pygame.Rect(w // 2 - 190, 230, 380, 44), "", "ab"),
            Button(pygame.Rect(w // 2 - 190, 290, 380, 44), "", "seed"),
            Button(pygame.Rect(w // 2 - 80, h - 56, 160, 36), "Back", "menu", hint="Esc"),
        ]
        self._refresh()

    def _refresh(self) -> None:
        self.buttons[0].label = f"AI-vs-AI start speed: {config.AI_SPEEDS[self.settings.speed_idx]}x"
        self.buttons[1].label = "Vecna Alpha-Beta: " + ("ON" if config.VECNA_USE_ALPHA_BETA else "OFF (plain Minimax)")
        self.buttons[2].label = ("Game seed: new each game" if config.RANDOM_SEED_PER_GAME
                                 else f"Game seed: fixed ({config.RNG_SEED})")

    def _click(self, id_: str) -> Optional[str]:
        if id_ == "speed":
            self.settings.speed_idx = (self.settings.speed_idx + 1) % len(config.AI_SPEEDS)
        elif id_ == "ab":
            config.VECNA_USE_ALPHA_BETA = not config.VECNA_USE_ALPHA_BETA
        elif id_ == "seed":
            config.RANDOM_SEED_PER_GAME = not config.RANDOM_SEED_PER_GAME
        elif id_ == "menu":
            return "menu"
        self._refresh()
        return None

    def handle_event(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            b = button_at(self.buttons, e.pos)
            return self._click(b.id) if b else None
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                return "menu"
            if e.key == pygame.K_1:
                return self._click("speed")
            if e.key == pygame.K_2:
                return self._click("ab")
            if e.key == pygame.K_3:
                return self._click("seed")
        return None

    def draw(self, surf, fonts, mouse_pos=None):
        _backdrop(surf, fonts, "Settings")
        for b in self.buttons:
            b.draw(surf, fonts.body, mouse_pos)
        w = surf.get_width()
        draw_text(surf, fonts.tiny, "Click a row to change it (keys 1-3). All are values from config.py.",
                  (w // 2, 360), theme.DIM, "center")
