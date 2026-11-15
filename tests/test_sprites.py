"""Character pictures: used when a file exists, letter markers when it does not; the sheet splitter."""
import sys
from pathlib import Path

import pygame
import pytest

import config
from ui import game_screen, sprites, theme
from ui.session import GameSession

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import split_sprites  # noqa: E402


@pytest.fixture(autouse=True)
def clear_cache():
    sprites._cache.clear()
    yield
    sprites._cache.clear()


def make_png(path, size=(40, 60), color=(200, 50, 50, 255)):
    pygame.init()
    pygame.display.set_mode((1, 1))
    s = pygame.Surface(size, pygame.SRCALPHA)
    s.fill(color)
    pygame.image.save(s, str(path))


def test_missing_file_means_no_picture(tmp_path, monkeypatch):
    monkeypatch.setattr(sprites, "ASSET_DIR", tmp_path)
    assert sprites.load("eleven") is None
    pygame.init()
    assert sprites.draw(pygame.Surface((100, 100)), "eleven", (50, 50)) is False


def test_picture_is_scaled_into_one_cell_and_drawn(tmp_path, monkeypatch):
    monkeypatch.setattr(sprites, "ASSET_DIR", tmp_path)
    make_png(tmp_path / "eleven.png")
    pic = sprites.load("eleven")
    assert pic.get_width() <= theme.CELL and pic.get_height() <= theme.CELL
    surf = pygame.Surface((100, 100))
    assert sprites.draw(surf, "eleven", (50, 50)) is True
    assert surf.get_at((50, 55))[:3] != (0, 0, 0)


def test_switch_turns_pictures_off(tmp_path, monkeypatch):
    monkeypatch.setattr(sprites, "ASSET_DIR", tmp_path)
    make_png(tmp_path / "eleven.png")
    monkeypatch.setattr(config, "SPRITES_ENABLED", False)
    assert sprites.draw(pygame.Surface((100, 100)), "eleven", (50, 50)) is False


def test_board_draws_with_and_without_pictures(tmp_path, monkeypatch):
    monkeypatch.setattr(sprites, "ASSET_DIR", tmp_path)
    for name in ("eleven", "vecna", "demogorgon", "mike", "dustin", "lucas", "will", "portal"):
        make_png(tmp_path / f"{name}.png")
    pygame.font.init()
    session = GameSession(ai_mode=True)
    session.ai_one_turn()
    s = session.state
    before = (s.turn, s.eleven_pos, s.eleven_hp)
    surf = pygame.Surface((1000, 720))
    fonts = theme.load_fonts()
    game_screen.draw_board(surf, s, fonts, session.overlay())          # all pictures
    monkeypatch.setattr(sprites, "ASSET_DIR", tmp_path / "nothing")
    sprites._cache.clear()
    game_screen.draw_board(surf, s, fonts, session.overlay())          # all letters
    assert (s.turn, s.eleven_pos, s.eleven_hp) == before


def test_splitter_finds_figures_in_reading_order_and_merges_specks():
    pygame.init()
    sheet = pygame.Surface((300, 200), pygame.SRCALPHA)
    for x, y in ((10, 10), (200, 10), (10, 120)):                       # three figures
        pygame.draw.rect(sheet, (255, 0, 0, 255), (x, y, 40, 50))
    sheet.set_at((52, 12), (255, 0, 0, 255))                            # a speck next to the first figure
    boxes = split_sprites.characters(sheet)
    assert len(boxes) == 3
    assert [b[0] for b in boxes] == [10, 200, 10] and boxes[0][2] == 52



def test_mind_flayer_card_is_white_and_needs_the_picture(tmp_path, monkeypatch):
    from ui import icons
    monkeypatch.setattr(sprites, "ASSET_DIR", tmp_path)
    icons._mf_cache.clear()
    pygame.init()
    rect = pygame.Rect(10, 10, 100, 50)
    surf = pygame.Surface((130, 80))
    icons.draw_mind_flayer_card(surf, rect, False, False)           # no file: nothing drawn
    assert surf.get_at((15, 15))[:3] == (0, 0, 0)
    make_png(tmp_path / "mind_flayer.png", (200, 100), (0, 0, 0, 255))
    icons._mf_cache.clear()
    icons.draw_mind_flayer_card(surf, rect, True, False)
    assert surf.get_at((13, 13))[:3] == (255, 255, 255)             # white tile around the dark picture
    assert sum(surf.get_at((60, 35))[:3]) < 30                      # the dark picture itself
    icons._mf_cache.clear()



def test_mind_flayer_looms_over_the_board_only_when_awake(tmp_path, monkeypatch):
    from ui import icons
    monkeypatch.setattr(sprites, "ASSET_DIR", tmp_path)
    make_png(tmp_path / "mind_flayer.png", (200, 100), (0, 0, 0, 255))
    icons._loom_cache.clear()
    pygame.font.init()
    session = GameSession(ai_mode=True)
    s = session.state
    fonts = theme.load_fonts()
    asleep, awake = pygame.Surface((1000, 720)), pygame.Surface((1000, 720))
    game_screen.draw_board(asleep, s, fonts, session.overlay())
    s.mind_flayer.active = True
    before = (s.turn, s.eleven_pos, s.eleven_hp)
    game_screen.draw_board(awake, s, fonts, session.overlay())
    assert pygame.image.tostring(asleep, "RGB") != pygame.image.tostring(awake, "RGB")
    assert (s.turn, s.eleven_pos, s.eleven_hp) == before
    icons._loom_cache.clear()