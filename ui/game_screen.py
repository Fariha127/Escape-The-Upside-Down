"""In-game renderer: board, HUD strip (bars, friend portraits, ability icons) and the AI side panel.

Reads GameState and the overlay dict from GameSession; never mutates the game.
Everything on the board is always visible; Radar adds a ring and an A* step count to each enemy.
Every number shown comes from the state or from the recorded search statistics (ui/stats_view.py)."""
from __future__ import annotations
from typing import Dict, List, Optional

import pygame

import config
from game.actions import Action
from game.board import Terrain
from game.state import GameState, Winner
from ui import theme
from ui.icons import draw_ability_icon, draw_portrait
from ui.stats_view import stats_sections
from ui.theme import CELL, HUD_H, PANEL_W
from ui.widgets import Button, draw_bar, draw_text

COLORS = {
    Terrain.FLOOR: (22, 26, 44), Terrain.WALL: (4, 4, 10),
    Terrain.VINE: (60, 14, 24), Terrain.HAZARD: (110, 40, 10),
}

KEYMAP = {
    pygame.K_UP: Action.MOVE_UP, pygame.K_w: Action.MOVE_UP,
    pygame.K_DOWN: Action.MOVE_DOWN, pygame.K_s: Action.MOVE_DOWN,
    pygame.K_LEFT: Action.MOVE_LEFT, pygame.K_a: Action.MOVE_LEFT,
    pygame.K_RIGHT: Action.MOVE_RIGHT, pygame.K_d: Action.MOVE_RIGHT,
    pygame.K_SPACE: Action.WAIT,
}
# Action keys for human play. Moves and Space are in KEYMAP above.
ACTION_KEYS = {
    pygame.K_e: Action.ATTACK, pygame.K_f: Action.RESCUE,
    pygame.K_1: Action.USE_RADAR, pygame.K_2: Action.USE_SPEED,
    pygame.K_3: Action.USE_TELEPORT, pygame.K_4: Action.USE_FREEZE,
    pygame.K_x: Action.FINAL_ATTACK,
}
ABILITY_ORDER = (("RADAR", "1"), ("SPEED", "2"), ("TELEPORT", "3"), ("FREEZE", "4"))


# ---------------------------------------------------------------- geometry
def window_size(state: GameState):
    return state.board.width * CELL + PANEL_W, max(state.board.height * CELL + HUD_H, 690)


def board_width(state: GameState) -> int:
    return state.board.width * CELL


def cell_at(state: GameState, mouse_pos):
    """Grid cell under a mouse position, or None if outside the board."""
    x, y = mouse_pos[0] // CELL, (mouse_pos[1] - HUD_H) // CELL
    if mouse_pos[0] < 0 or mouse_pos[1] < HUD_H:
        return None
    return (x, y) if state.board.in_bounds((x, y)) else None


def _centre(pos):
    return pos[0] * CELL + CELL // 2, pos[1] * CELL + CELL // 2 + HUD_H


def control_buttons(state: GameState, ai_mode: bool, paused: bool) -> List[Button]:
    """The on-screen command buttons in the AI panel (same layout for drawing and for click tests)."""
    x0, y0, w, h, gap = board_width(state) + 12, 34, 96, 28, 6
    over = state.game_over

    def b(col, row, label, id_, **kw):
        return Button(pygame.Rect(x0 + col * (w + gap), y0 + row * (h + gap), w, h), label, id_, **kw)
    return [
        b(0, 0, "Resume" if paused else "Pause", "pause", enabled=ai_mode and not over,
          active=ai_mode and paused),
        b(1, 0, "Step", "step", enabled=not over),
        b(2, 0, "Slower", "slower", enabled=ai_mode and not over),
        b(3, 0, "Faster", "faster", enabled=ai_mode and not over),
        b(0, 1, "AI plays", "toggle_ai", active=ai_mode),
        b(1, 1, "Paths", "paths"),
        b(2, 1, "Restart", "restart"),
        b(3, 1, "Menu", "menu"),
    ]


# ---------------------------------------------------------------- board pieces
def _marker(surf, pos, color, letter, font, shape="circle"):
    cx, cy = _centre(pos)
    half = CELL // 2 - 5
    if shape == "circle":
        pygame.draw.circle(surf, color, (cx, cy), half)
    else:
        pygame.draw.rect(surf, color, (cx - half + 1, cy - half + 1, 2 * half - 2, 2 * half - 2), border_radius=4)
    t = font.render(letter, True, (0, 0, 0))
    surf.blit(t, t.get_rect(center=(cx, cy)))


def _draw_path(surf, path, color, radius=4):
    for cell in path:
        pygame.draw.circle(surf, color, _centre(cell), radius)


def _arrow(surf, a, b, color, width=3):
    """Line from cell a to cell b with a small arrow head at b."""
    pa, pb = pygame.Vector2(_centre(a)), pygame.Vector2(_centre(b))
    pygame.draw.line(surf, color, pa, pb, width)
    d = pb - pa
    if d.length() > 0:
        d = d.normalize()
        left, right = d.rotate(150) * 9, d.rotate(-150) * 9
        pygame.draw.polygon(surf, color, [pb, pb + left, pb + right])


def draw_board(surf: pygame.Surface, state: GameState, fonts: theme.Fonts, overlay: Dict) -> None:
    b = state.board
    for y in range(b.height):
        for x in range(b.width):
            r = pygame.Rect(x * CELL, y * CELL + HUD_H, CELL, CELL)
            pygame.draw.rect(surf, COLORS[b.terrain_at((x, y))], r)
            pygame.draw.rect(surf, theme.GRID_LINE, r, 1)
    for c in state.corrupted:
        pygame.draw.rect(surf, (120, 0, 120), (c[0] * CELL + 3, c[1] * CELL + HUD_H + 3, CELL - 6, CELL - 6), 2)
    for cell in overlay.get("teleport_cells", []):
        pygame.draw.rect(surf, theme.CYAN, (cell[0] * CELL + 2, cell[1] * CELL + HUD_H + 2, CELL - 4, CELL - 4), 3)
    for path in overlay.get("demogorgon_paths", {}).values():
        _draw_path(surf, path, (200, 70, 70), 3)
    _draw_path(surf, overlay.get("eleven_path", []), theme.CYAN, 5)
    gt = overlay.get("goal_target")
    if gt is not None:                          # the cell Eleven's current goal is walking to
        cx, cy = _centre(gt)
        r = CELL // 2 - 3
        pygame.draw.polygon(surf, theme.CYAN, [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], 2)
    f = fonts.body
    _marker(surf, state.portal_pos, theme.CYAN if state.portal_active else (40, 80, 110), "P", f, "square")
    for name, p in state.friend_positions.items():
        if name not in state.rescued:
            _marker(surf, p, theme.FRIEND_COLORS.get(name, theme.GOLD), name[0], f)
    for d in state.living_demogorgons():
        # purple = temporary Mind Flayer creature (gives no power)
        _marker(surf, d.pos, theme.PURPLE if d.temporary else (170, 60, 60), "G", f, "square")
    _marker(surf, state.vecna.pos, (140, 0, 20), "V", f, "square")
    _marker(surf, state.eleven_pos, (240, 240, 240), "E", f)

    vc = overlay.get("vecna_choice")            # Vecna's last real Minimax choice
    if vc:
        if vc["action"] == Action.ATTACK:
            _arrow(surf, vc["to"], state.eleven_pos, (255, 90, 90))
        elif vc["from"] != vc["to"]:
            _arrow(surf, vc["from"], vc["to"], (255, 90, 90))
        label = f"{vc['action'].value} {vc['score']:+.0f}"
        cx, cy = _centre(vc["to"])
        draw_text(surf, fonts.tiny, label, (cx, cy - CELL // 2 - 1), (255, 140, 140), "center")

    for rd in overlay.get("radar", []):         # Radar: ring + real A* step count above each enemy
        cx, cy = _centre(rd.pos)
        pygame.draw.circle(surf, theme.GOLD, (cx, cy), CELL // 2 - 1, 2)
        draw_text(surf, fonts.small, str(rd.steps) if rd.steps is not None else "-",
                  (cx, cy - CELL // 2 - 2), theme.GOLD, "center")


# ---------------------------------------------------------------- HUD strip
def _status_text(state: GameState) -> str:
    parts = [f"{k} {v}t" for k, v in sorted(state.status_effects.items())]
    return ("Active: " + ", ".join(parts)) if parts else ""


def draw_hud(surf: pygame.Surface, state: GameState, fonts: theme.Fonts, overlay: Dict) -> None:
    w = board_width(state)
    pygame.draw.rect(surf, theme.PANEL_BG, (0, 0, w, HUD_H))
    # bars
    draw_text(surf, fonts.small, "HP", (10, 9), theme.DIM)
    draw_bar(surf, pygame.Rect(42, 8, 190, 16), state.eleven_hp, config.MAX_HP, theme.HP_COLOR)
    draw_text(surf, fonts.small, f"{state.eleven_hp}/{config.MAX_HP}", (240, 9))
    draw_text(surf, fonts.small, "PWR", (10, 31), theme.DIM)
    draw_bar(surf, pygame.Rect(42, 30, 190, 16), state.eleven_power, config.MAX_POWER, theme.POWER_COLOR)
    draw_text(surf, fonts.small, f"{state.eleven_power}/{config.MAX_POWER}", (240, 31))
    # turn + Mind Flayer
    draw_text(surf, fonts.body, f"Turn {state.turn}/{state.max_turns}", (w - 10, 6), theme.TEXT, "topright")
    mf = "DEFEATED" if state.mind_flayer.defeated else ("AWAKE" if state.mind_flayer.active else "asleep")
    draw_text(surf, fonts.small, f"Mind Flayer: {mf}", (w - 10, 30),
              theme.RED if mf == "AWAKE" else theme.DIM, "topright")
    # friend portraits
    draw_text(surf, fonts.tiny, "FRIENDS", (10, 54), theme.DIM)
    for i, name in enumerate(theme.FRIEND_ORDER):
        draw_portrait(surf, pygame.Rect(10 + i * 46, 68, 40, 40), name, name in state.rescued, fonts.small)
    # ability icons
    draw_text(surf, fonts.tiny, "ABILITIES  [key] uses left", (214, 54), theme.DIM)
    for i, (key, hotkey) in enumerate(ABILITY_ORDER):
        rect = pygame.Rect(214 + i * 78, 68, 40, 40)
        unlocked = key in state.unlocked_abilities
        uses = state.ability_uses.get(key, 0)
        draw_ability_icon(surf, rect, key, unlocked, state.status_effects.get(key, 0) > 0, uses)
        label = f"[{hotkey}] x{uses}" if unlocked else f"[{hotkey}] locked"
        draw_text(surf, fonts.tiny, label, (rect.centerx, rect.bottom + 3), theme.TEXT if unlocked else theme.DIM,
                  "midtop")
    # status lines
    status = _status_text(state)
    if status:
        draw_text(surf, fonts.tiny, status, (10, 128), theme.GOLD)
    line = overlay.get("message") or ""
    if line:
        draw_text(surf, fonts.small, line, (w - 10, 126), (255, 255, 255), "topright")
    draw_text(surf, fonts.tiny, "WASD move  Space wait  E attack  F rescue  X final attack", (10, HUD_H - 32), theme.DIM)
    draw_text(surf, fonts.tiny, "1-4 abilities (3: click a cell)  Esc cancel", (10, HUD_H - 16), theme.DIM)


# ---------------------------------------------------------------- AI side panel
def _fit(font, text: str, width: int) -> str:
    """Cut a line with '...' so it never runs outside its card."""
    if font.size(text)[0] <= width:
        return text
    while text and font.size(text + "...")[0] > width:
        text = text[:-1]
    return text + "..."


def draw_panel(surf: pygame.Surface, state: GameState, tm, fonts: theme.Fonts, overlay: Dict,
               buttons: List[Button], mouse_pos=None) -> None:
    x0 = board_width(state)
    pygame.draw.rect(surf, theme.PANEL_BG, (x0, 0, PANEL_W, surf.get_height()))
    pygame.draw.line(surf, theme.CARD_EDGE, (x0, 0), (x0, surf.get_height()), 2)
    draw_text(surf, fonts.body, "AI PANEL", (x0 + 12, 8), theme.CYAN)
    draw_text(surf, fonts.small, overlay.get("status", ""), (x0 + PANEL_W - 12, 10), theme.GOLD, "topright")
    for btn in buttons:
        btn.draw(surf, fonts.small, mouse_pos)
    draw_text(surf, fonts.tiny, "Space pause  N step  -/+ speed  P paths  R new  M menu",
              (x0 + 12, 104), theme.DIM)
    goal = overlay.get("goal")
    if overlay.get("seed") is not None:
        draw_text(surf, fonts.tiny, f"seed {overlay['seed']}", (x0 + PANEL_W - 12, 124), theme.DIM, "topright")
    draw_text(surf, fonts.small, (f"Eleven's goal: {goal}" if goal else
               ("Eleven's goal: -" if overlay.get("ai_mode") else "Eleven's goal: - (human control)")),
              (x0 + 12, 122), theme.CYAN if goal else theme.DIM)

    y = 146
    inner = PANEL_W - 28
    sections = stats_sections(tm)
    card_h = (surf.get_height() - y - 8 - 6 * (len(sections) - 1)) // len(sections)
    for sec in sections:
        rect = pygame.Rect(x0 + 10, y, PANEL_W - 20, card_h)
        pygame.draw.rect(surf, theme.CARD_BG, rect, border_radius=6)
        pygame.draw.rect(surf, theme.CARD_EDGE, rect, 1, border_radius=6)
        draw_text(surf, fonts.small, sec.title, (rect.x + 8, rect.y + 5), theme.GOLD if sec.has_data else theme.DIM)
        ly = rect.y + 24
        for text in sec.lines:
            if ly + 14 > rect.bottom:
                break
            draw_text(surf, fonts.tiny, _fit(fonts.tiny, text, inner), (rect.x + 8, ly),
                      theme.GREEN if sec.has_data else theme.DIM)
            ly += 15
        y += card_h + 6


# ---------------------------------------------------------------- whole frame
def draw(surf: pygame.Surface, state: GameState, tm, fonts: theme.Fonts, overlay: Optional[Dict] = None,
         buttons: Optional[List[Button]] = None, mouse_pos=None) -> None:
    """overlay: {'demogorgon_paths': {id: [cells]}, 'eleven_path': [cells], 'teleport_cells': [cells],
    'radar': [RadarReading], 'message': str, 'status': str, 'goal': str, 'goal_target': cell,
    'vecna_choice': {'from','to','action','score'}} - every number comes from real runs."""
    overlay = overlay or {}
    surf.fill(theme.BG)
    draw_board(surf, state, fonts, overlay)
    draw_hud(surf, state, fonts, overlay)
    if buttons is None:
        buttons = control_buttons(state, bool(overlay.get("goal")), False)
    draw_panel(surf, state, tm, fonts, overlay, buttons, mouse_pos)
    if state.game_over:
        shade = pygame.Surface((board_width(state), surf.get_height() - HUD_H), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 130))
        surf.blit(shade, (0, HUD_H))
        msg = "ESCAPED!" if state.winner == Winner.ELEVEN else "ELEVEN FAILED"
        cx = board_width(state) // 2
        cy = HUD_H + state.board.height * CELL // 2
        draw_text(surf, fonts.title, msg, (cx, cy), theme.CYAN if state.winner == Winner.ELEVEN else theme.RED, "center")
        draw_text(surf, fonts.small, "Press Enter for the results   R restart   M menu", (cx, cy + 40),
                  theme.TEXT, "center")
