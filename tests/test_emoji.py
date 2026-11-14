"""Colourful icons: every icon draws, faded when disabled, buttons and the HUD draw with them."""
import pygame
import pytest

from ui import emoji, game_screen, theme
from ui.session import GameSession
from ui.widgets import Button


@pytest.mark.parametrize("name", sorted(emoji.ICONS))
def test_every_icon_draws_something(name):
    pygame.init()
    surf = pygame.Surface((40, 40))
    emoji.draw(surf, name, (20, 20), 30)
    assert any(surf.get_at((x, y))[:3] != (0, 0, 0) for x in range(40) for y in range(40))


def test_disabled_icon_is_fainter():
    pygame.init()
    on, off = pygame.Surface((40, 40)), pygame.Surface((40, 40))
    emoji.draw(on, "speed", (20, 20), 30, True)
    emoji.draw(off, "speed", (20, 20), 30, False)
    assert sum(on.get_at((20, 20))[:3]) > sum(off.get_at((20, 20))[:3])


def test_unknown_icon_name_is_ignored():
    pygame.init()
    emoji.draw(pygame.Surface((10, 10)), "nope", (5, 5), 8)


def test_button_with_icon_draws():
    pygame.init()
    pygame.font.init()
    surf = pygame.Surface((200, 60))
    Button(pygame.Rect(10, 10, 96, 28), "Step", "step", icon="step").draw(surf, theme.load_fonts().body)


def test_game_screen_draws_with_icons_and_pictures():
    pygame.font.init()
    s = GameSession(ai_mode=True)
    s.state.rescued.add("Mike")
    surf = pygame.Surface((1400, 760))
    game_screen.draw(surf, s.state, s.tm, theme.load_fonts(), s.overlay())