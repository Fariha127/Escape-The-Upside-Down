"""Basic renderer. Reads GameState, never mutates it (except via TurnManager on input).
Everything on the board is always visible; Radar adds a ring and an A* step count to each enemy."""
from __future__ import annotations
import pygame

from game.actions import Action
from game.board import Terrain
from game.state import GameState, Winner

CELL = 40
HUD_H = 270
BG = (8, 10, 22)
COLORS = {
    Terrain.FLOOR: (22, 26, 44), Terrain.WALL: (4, 4, 10),
    Terrain.VINE: (60, 14, 24), Terrain.HAZARD: (110, 40, 10),
}
GRID_LINE = (34, 38, 62)
RED = (220, 40, 50)
GOLD = (240, 200, 60)

KEYMAP = {
    pygame.K_UP: Action.MOVE_UP, pygame.K_w: Action.MOVE_UP,
    pygame.K_DOWN: Action.MOVE_DOWN, pygame.K_s: Action.MOVE_DOWN,
    pygame.K_LEFT: Action.MOVE_LEFT, pygame.K_a: Action.MOVE_LEFT,
    pygame.K_RIGHT: Action.MOVE_RIGHT, pygame.K_d: Action.MOVE_RIGHT,
    pygame.K_SPACE: Action.WAIT,
}
# Phase 4 action keys (human play). Moves and Space are in KEYMAP above.
ACTION_KEYS = {
    pygame.K_e: Action.ATTACK, pygame.K_f: Action.RESCUE,
    pygame.K_1: Action.USE_RADAR, pygame.K_2: Action.USE_SPEED,
    pygame.K_3: Action.USE_TELEPORT, pygame.K_4: Action.USE_FREEZE,
    pygame.K_x: Action.FINAL_ATTACK,
}
ABILITY_ORDER = (("RADAR", "1 Radar"), ("SPEED", "2 Speed"), ("TELEPORT", "3 Teleport"), ("FREEZE", "4 Freeze"))


def window_size(state: GameState):
    return state.board.width * CELL, state.board.height * CELL + HUD_H


def cell_at(state: GameState, mouse_pos):
    """Grid cell under a mouse position, or None if outside the board."""
    x, y = mouse_pos[0] // CELL, (mouse_pos[1] - HUD_H) // CELL
    return (x, y) if state.board.in_bounds((x, y)) and mouse_pos[1] >= HUD_H else None


def _centre(pos):
    return pos[0] * CELL + CELL // 2, pos[1] * CELL + CELL // 2 + HUD_H


def _marker(surf, pos, color, letter, font, shape="circle"):
    cx, cy = _centre(pos)
    if shape == "circle":
        pygame.draw.circle(surf, color, (cx, cy), CELL // 2 - 5)
    else:
        pygame.draw.rect(surf, color, (cx - 14, cy - 14, 28, 28), border_radius=4)
    t = font.render(letter, True, (0, 0, 0))
    surf.blit(t, t.get_rect(center=(cx, cy)))


def _draw_path(surf, path, color, radius=4):
    for cell in path:
        pygame.draw.circle(surf, color, _centre(cell), radius)


def _status_text(state: GameState) -> str:
    parts = [f"{k} {v}t" for k, v in sorted(state.status_effects.items())]
    return ("Active: " + ", ".join(parts)) if parts else ""


def draw(surf: pygame.Surface, state: GameState, font, big_font, small_font=None, overlay=None) -> None:
    """overlay (optional): {'demogorgon_paths': {id: [cells]}, 'eleven_path': [cells], 'stats': [text lines],
    'teleport_cells': [cells], 'radar': [RadarReading], 'message': str,
    'ai_status': str, 'goal': str, 'goal_target': cell} - every number comes from real runs."""
    overlay = overlay or {}
    sf = small_font or font
    surf.fill(BG)
    b = state.board
    for y in range(b.height):
        for x in range(b.width):
            r = pygame.Rect(x * CELL, y * CELL + HUD_H, CELL, CELL)
            pygame.draw.rect(surf, COLORS[b.terrain_at((x, y))], r)
            pygame.draw.rect(surf, GRID_LINE, r, 1)
    for c in state.corrupted:
        pygame.draw.rect(surf, (120, 0, 120), (c[0] * CELL + 3, c[1] * CELL + HUD_H + 3, CELL - 6, CELL - 6), 2)
    for cell in overlay.get("teleport_cells", []):
        pygame.draw.rect(surf, (80, 220, 255), (cell[0] * CELL + 2, cell[1] * CELL + HUD_H + 2, CELL - 4, CELL - 4), 3)
    for path in overlay.get("demogorgon_paths", {}).values():
        _draw_path(surf, path, (200, 70, 70), 3)
    _draw_path(surf, overlay.get("eleven_path", []), (80, 220, 255), 5)
    gt = overlay.get("goal_target")
    if gt is not None:                        # the cell Eleven's current goal is walking to
        cx, cy = _centre(gt)
        pygame.draw.polygon(surf, (80, 220, 255), [(cx, cy - 17), (cx + 17, cy), (cx, cy + 17), (cx - 17, cy)], 2)
    _marker(surf, state.portal_pos, (80, 200, 255) if state.portal_active else (40, 80, 110), "P", font, "square")
    for name, p in state.friend_positions.items():
        if name not in state.rescued:
            _marker(surf, p, GOLD, name[0], font)
    for d in state.living_demogorgons():
        # purple = temporary Mind Flayer creature (gives no power)
        _marker(surf, d.pos, (150, 70, 200) if d.temporary else (170, 60, 60), "G", font, "square")
    _marker(surf, state.vecna.pos, (140, 0, 20), "V", font, "square")
    _marker(surf, state.eleven_pos, (240, 240, 240), "E", font)

    readings = overlay.get("radar", [])
    for rd in readings:                       # Radar: ring + real A* step count above each enemy
        cx, cy = _centre(rd.pos)
        pygame.draw.circle(surf, GOLD, (cx, cy), CELL // 2 - 1, 2)
        label = sf.render(str(rd.steps) if rd.steps is not None else "-", True, GOLD)
        surf.blit(label, label.get_rect(center=(cx, cy - CELL // 2 - 2)))

    line = f"HP {state.eleven_hp}  Power {state.eleven_power}  Rescued {len(state.rescued)}/4  Turn {state.turn}"
    surf.blit(font.render(line, True, (230, 230, 240)), (10, 8))
    mf = "DEFEATED" if state.mind_flayer.defeated else ("ACTIVE" if state.mind_flayer.active else "inactive")
    ms = font.render(f"Mind Flayer: {mf}", True, RED if mf == "ACTIVE" else (130, 130, 160))
    surf.blit(ms, (10, 30))
    ab = "  ".join(f"{label} x{state.ability_uses.get(key, 0)}" for key, label in ABILITY_ORDER
                   if key in state.unlocked_abilities) or "no abilities yet (rescue friends)"
    surf.blit(sf.render(ab + "   " + _status_text(state), True, GOLD), (10, 54))
    status = " | ".join(t for t in (overlay.get("ai_status"),
                                    ("Goal: " + overlay["goal"]) if overlay.get("goal") else "") if t)
    if status:
        label = sf.render(status, True, (80, 220, 255))
        surf.blit(label, (surf.get_width() - label.get_width() - 10, 34))
    for i, keys in enumerate(("WASD move  Space wait  E attack  F rescue  1-4 abilities  X final",
                              "T AI-vs-AI  N AI 1 turn  Space pause  +/- speed  P paths  R restart")):
        surf.blit(sf.render(keys, True, (130, 130, 160)), (10, 72 + 14 * i))
    if readings:
        text = "Radar A* steps: " + "  ".join(f"{r.short}={r.steps if r.steps is not None else '-'}" for r in readings)
        surf.blit(sf.render(text, True, GOLD), (10, 102))
    if overlay.get("message"):
        surf.blit(sf.render(overlay["message"], True, (255, 255, 255)), (10, 118))
    for i, text in enumerate(overlay.get("stats", [])):
        surf.blit(sf.render(text, True, (150, 200, 160)), (10, 134 + 13 * i))
    if state.game_over:
        msg = "ESCAPED!" if state.winner == Winner.ELEVEN else "ELEVEN FAILED"
        t = big_font.render(msg, True, RED)
        surf.blit(t, t.get_rect(center=(surf.get_width() // 2, surf.get_height() // 2)))