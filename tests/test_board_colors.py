from game.board import Terrain
from ui import game_screen


def test_vine_is_drawn_like_floor():
    assert game_screen.COLORS[Terrain.VINE] == game_screen.COLORS[Terrain.FLOOR]


def test_hazard_is_still_distinct():
    assert game_screen.COLORS[Terrain.HAZARD] != game_screen.COLORS[Terrain.FLOOR]