"""The restructured AI panel: key caps, goal bar, card pictures and the event log dots draw without errors and
without changing the game."""
import pygame

from ui import game_screen, icons, sprites, theme
from ui.session import GameSession


def _frame(session, fonts):
    w, h = game_screen.window_size(session.state)
    surf = pygame.Surface((w, h))
    game_screen.draw(surf, session.state, session.tm, fonts, session.overlay(), mouse_pos=(0, 0))
    return surf


def test_panel_draws_before_and_after_some_turns_without_changing_the_game():
    pygame.font.init()
    session = GameSession(ai_mode=True)
    fonts = theme.load_fonts()
    _frame(session, fonts)
    for _ in range(15):
        session.ai_one_turn()
    s = session.state
    before = (s.turn, s.eleven_pos, s.eleven_hp, list(s.event_log))
    _frame(session, fonts)
    assert (s.turn, s.eleven_pos, s.eleven_hp, list(s.event_log)) == before


def test_keycaps_stay_inside_the_panel():
    pygame.font.init()
    fonts = theme.load_fonts()
    surf = pygame.Surface((theme.PANEL_W, 40))
    game_screen._keycaps(surf, fonts, 12, 5)
    assert all(surf.get_at((x, y))[:3] == (0, 0, 0) for x in range(theme.PANEL_W - 6, theme.PANEL_W)
               for y in range(40))


def test_goal_bar_cuts_a_very_long_goal():
    pygame.font.init()
    fonts = theme.load_fonts()
    surf = pygame.Surface((theme.PANEL_W, 40))
    rect = pygame.Rect(10, 6, theme.PANEL_W - 20, game_screen.GOAL_BAR_H)
    game_screen._goal_bar(surf, fonts, rect, {"goal": "RESCUE " + "Will " * 40, "seed": 12345, "ai_mode": True})


def test_thumb_without_picture_draws_nothing(tmp_path, monkeypatch):
    pygame.init()
    monkeypatch.setattr(sprites, "ASSET_DIR", tmp_path)
    icons._thumb_cache.clear()
    surf = pygame.Surface((80, 40))
    icons.draw_thumb(surf, "vecna", (70, 5), 44, 20)
    assert surf.get_at((50, 15))[:3] == (0, 0, 0)
    icons._thumb_cache.clear()
