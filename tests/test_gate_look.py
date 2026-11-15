"""The gate picture: drawn in code, open and closed look different, and drawing changes no game state."""
import pygame

from ui import gate
from ui.session import GameSession
from ui import game_screen, theme


def _drawn(open_, now=0):
    pygame.init()
    surf = pygame.Surface((80, 80))
    gate.draw(surf, (40, 40), open_, now)
    return pygame.image.tostring(surf, "RGB")


def test_open_and_closed_look_different():
    assert _drawn(True) != _drawn(False)


def test_open_gate_turns_over_time():
    assert _drawn(True, 0) != _drawn(True, 140)


def test_board_draws_gate_without_changing_state():
    pygame.font.init()
    s = GameSession(ai_mode=True)
    before = (s.state.turn, s.state.eleven_pos)
    game_screen.draw_board(pygame.Surface((1000, 720)), s.state, theme.load_fonts(), s.overlay())
    assert (s.state.turn, s.state.eleven_pos) == before