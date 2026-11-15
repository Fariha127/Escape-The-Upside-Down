"""F11 / Alt+Enter switch full screen; the game keeps working afterwards."""
import pygame

from main import App


def test_f11_toggles_full_screen_and_drawing_still_works():
    app = App()
    assert app.fullscreen is False
    app.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F11, mod=0))
    assert app.fullscreen is True
    app.draw()
    app.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=pygame.KMOD_ALT))
    assert app.fullscreen is False
    app.draw()
    assert app.running