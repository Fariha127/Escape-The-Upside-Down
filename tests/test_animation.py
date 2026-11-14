"""Animations are drawing-only: where a piece is drawn between two cells, and when flashes start."""
import config
from game.state import GameState
from ui import animation
from ui.session import GameSession


def test_piece_slides_between_cells_then_arrives():
    s = GameState.new_game()
    a = animation.Animator()
    a.update(s, 0, 100)
    start = s.eleven_pos
    s.eleven_pos = (start[0] + 1, start[1])
    a.update(s, 1000, 100)
    x, y = a.cell_pos("E", s.eleven_pos, 1050)
    assert start[0] < x < s.eleven_pos[0] and y == start[1]
    a.update(s, 1200, 100)
    assert a.cell_pos("E", s.eleven_pos, 1200) == s.eleven_pos


def test_no_slide_when_duration_is_zero_or_jump_is_long():
    s = GameState.new_game()
    a = animation.Animator()
    a.update(s, 0, 0)
    s.eleven_pos = (s.eleven_pos[0] + 1, s.eleven_pos[1])
    a.update(s, 10, 0)
    assert a.cell_pos("E", s.eleven_pos, 11) == s.eleven_pos
    a.update(s, 20, 100)
    s.eleven_pos = (s.eleven_pos[0] + config.ANIM_MAX_SLIDE_CELLS + 3, s.eleven_pos[1])    # teleport-like jump
    a.update(s, 30, 100)
    assert a.cell_pos("E", s.eleven_pos, 31) == s.eleven_pos


def test_hit_and_kill_start_flashes_that_expire():
    s = GameState.new_game()
    a = animation.Animator()
    a.update(s, 0, 100)
    s.eleven_hp -= 5
    s.demogorgons[0].alive = False
    a.update(s, 10, 100)
    assert {k for k, _, _ in a.flashes} == {"hit", "kill"}
    assert a.flash_strength(10, 10) == 1.0
    a.update(s, 10 + config.ANIM_FLASH_MS + 1, 100)
    assert a.flashes == []


def test_slide_is_skipped_when_ai_is_too_fast(monkeypatch):
    assert animation.slide_duration_ms(False, 1) == config.ANIM_SLIDE_MS
    monkeypatch.setattr(config, "AI_TURN_DELAY_MS", 100)
    assert animation.slide_duration_ms(True, 4) == 0
    monkeypatch.setattr(config, "ANIM_ENABLED", False)
    assert animation.slide_duration_ms(False, 1) == 0


def test_session_overlay_and_drawing_work_with_animation():
    import pygame
    from ui import game_screen, theme
    session = GameSession(ai_mode=True)
    pygame.font.init()
    surf = pygame.Surface((1100, 700))
    fonts = theme.load_fonts()
    for _ in range(25):
        session.ai_one_turn()
        o = session.overlay()
        game_screen.draw_board(surf, session.state, fonts, o)