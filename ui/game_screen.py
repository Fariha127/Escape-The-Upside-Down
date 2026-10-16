"""Basic Phase-1 renderer. Reads GameState, never mutates it (except via TurnManager on input)."""
from __future__ import annotations
import pygame

from game.actions import Action
from game.board import Terrain
from game.state import GameState, Winner

CELL = 40
HUD_H = 60
BG = (8, 10, 22)
COLORS = {
    Terrain.FLOOR: (22, 26, 44), Terrain.WALL: (4, 4, 10),
    Terrain.VINE: (60, 14, 24), Terrain.HAZARD: (110, 40, 10),
}
GRID_LINE = (34, 38, 62)
RED = (220, 40, 50)

KEYMAP = {
    pygame.K_UP: Action.MOVE_UP, pygame.K_w: Action.MOVE_UP,
    pygame.K_DOWN: Action.MOVE_DOWN, pygame.K_s: Action.MOVE_DOWN,
    pygame.K_LEFT: Action.MOVE_LEFT, pygame.K_a: Action.MOVE_LEFT,
    pygame.K_RIGHT: Action.MOVE_RIGHT, pygame.K_d: Action.MOVE_RIGHT,
    pygame.K_SPACE: Action.WAIT,
}


def window_size(state: GameState):
    return state.board.width * CELL, state.board.height * CELL + HUD_H


def _marker(surf, pos, color, letter, font, shape="circle"):
    cx, cy = pos[0] * CELL + CELL // 2, pos[1] * CELL + CELL // 2 + HUD_H
    if shape == "circle":
        pygame.draw.circle(surf, color, (cx, cy), CELL // 2 - 5)
    else:
        pygame.draw.rect(surf, color, (cx - 14, cy - 14, 28, 28), border_radius=4)
    t = font.render(letter, True, (0, 0, 0))
    surf.blit(t, t.get_rect(center=(cx, cy)))


def draw(surf: pygame.Surface, state: GameState, font, big_font) -> None:
    surf.fill(BG)
    b = state.board
    for y in range(b.height):
        for x in range(b.width):
            r = pygame.Rect(x * CELL, y * CELL + HUD_H, CELL, CELL)
            pygame.draw.rect(surf, COLORS[b.terrain_at((x, y))], r)
            pygame.draw.rect(surf, GRID_LINE, r, 1)
    for c in state.corrupted:
        pygame.draw.rect(surf, (120, 0, 120), (c[0] * CELL + 3, c[1] * CELL + HUD_H + 3, CELL - 6, CELL - 6), 2)
    _marker(surf, state.portal_pos, (80, 200, 255) if state.portal_active else (40, 80, 110), "P", font, "square")
    for name, p in state.friend_positions.items():
        if name not in state.rescued:
            _marker(surf, p, (240, 200, 60), name[0], font)
    for d in state.living_demogorgons():
        _marker(surf, d.pos, (170, 60, 60), "G", font, "square")
    _marker(surf, state.vecna.pos, (140, 0, 20), "V", font, "square")
    _marker(surf, state.eleven_pos, (240, 240, 240), "E", font)

    hp = "".join("♥" if i < state.eleven_hp else "·" for i in range(5))
    line = f"HP {state.eleven_hp}  Power {state.eleven_power}  Rescued {len(state.rescued)}/4  Turn {state.turn}"
    surf.blit(font.render(line, True, (230, 230, 240)), (10, 8))
    surf.blit(font.render("WASD/Arrows: move   Space: wait   R: restart", True, (130, 130, 160)), (10, 34))
    if state.game_over:
        msg = "ESCAPED!" if state.winner == Winner.ELEVEN else "ELEVEN FAILED"
        t = big_font.render(msg, True, RED)
        surf.blit(t, t.get_rect(center=(surf.get_width() // 2, surf.get_height() // 2)))
