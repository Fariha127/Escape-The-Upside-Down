"""Event log panel: parsing and colours of state.event_log, scrolling, layout. Headless (SDL dummy driver).
The panel only READS the log the game wrote; these tests check it shows exactly that."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

import config
from game.state import GameState
from main import App
from ui import game_screen, theme
from ui.log_view import LogEntry, classify, parse, visible_entries
from ui.session import GameSession


@pytest.fixture(scope="module")
def app():
    a = App()
    yield a
    pygame.quit()


def key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k)


def play(session, turns):
    for _ in range(turns):
        if session.state.game_over:
            break
        session.ai_one_turn()


def play_until_events(session, count):
    """Play until the log has at least `count` events (a full default-map game logs about 19; the card shows 9)."""
    while len(session.state.event_log) < count and not session.state.game_over:
        session.ai_one_turn()
    assert len(session.state.event_log) >= count


# ------------------------------------------------------------------ parsing and colours
def test_parse_splits_turn_and_text():
    assert parse("[T12] Eleven takes 1 damage from Vecna (HP 4)") == \
        LogEntry(12, "Eleven takes 1 damage from Vecna (HP 4)", "damage")
    assert parse("no prefix here") == LogEntry(None, "no prefix here", "other")
    assert parse("[T3]") == LogEntry(3, "", "other")


@pytest.mark.parametrize("text,category", [
    ("Eleven takes 2 damage from Vecna (HP 3)", "damage"),
    ("Eleven defeats Demogorgon 4 (+3 power)", "kill"),
    ("Rescued Mike - unlocked TELEPORT", "rescue"),
    ("Rescue bonus: +4 power", "rescue"),
    ("THE MIND FLAYER HAS AWAKENED", "mind_flayer"),
    ("Mind Flayer corrupts (3, 4)", "mind_flayer"),
    ("Mind Flayer summons a creature at (2, 2)", "mind_flayer"),
    ("The Mind Flayer is defeated! The portal opens.", "win"),
    ("Freeze: enemies frozen for 2 turns", "ability"),
    ("Speed: Eleven can move twice per turn", "ability"),
    ("Radar: scanning enemy distances", "ability"),
    ("Teleport to (1, 1)", "ability"),
    ("Eleven escaped through the portal!", "win"),
    ("Eleven has fallen.", "loss"),
    ("Turn limit reached - Eleven failed to escape.", "loss"),
    ("something unexpected", "other"),
])
def test_every_known_message_has_its_category(text, category):
    assert classify(text) == category
    assert category in theme.LOG_COLORS


def test_every_message_in_real_games_gets_a_category():
    """Plays full games and checks that no logged message falls into 'other' (a new message type would show up here)."""
    from ui.session import ai_turn, new_game
    from game.board_gen import generate_board
    seen = set()
    for seed in (1, 2, 3, 4, 5, 6):
        config.RNG_SEED = seed
        state, tm, ai = new_game(generate_board(seed))
        while not state.game_over:
            ai_turn(state, tm, ai)
        for line in state.event_log:
            e = parse(line)
            assert e.turn is not None, line
            assert e.category != "other", line
            seen.add(e.category)
    assert {"damage", "kill", "rescue", "mind_flayer", "ability"} <= seen


# ------------------------------------------------------------------ which lines are visible
LOG = [f"[T{i}] event {i}" for i in range(20)]


def test_newest_events_are_shown_last():
    entries, older, newer = visible_entries(LOG, 5)
    assert [e.text for e in entries] == [f"event {i}" for i in range(15, 20)]
    assert (older, newer) == (15, 0)


def test_scrolling_back_and_clamping():
    entries, older, newer = visible_entries(LOG, 5, offset=7)
    assert [e.turn for e in entries] == [8, 9, 10, 11, 12] and (older, newer) == (8, 7)
    assert visible_entries(LOG, 5, offset=999)[0][0].turn == 0       # cannot scroll past the oldest
    assert visible_entries(LOG, 5, offset=-4)[0][-1].turn == 19      # negative = newest
    short = visible_entries(LOG[:3], 5, offset=2)
    assert len(short[0]) == 3 and short[1:] == (0, 0)                 # fewer lines than the card holds
    assert visible_entries([], 5) == ([], 0, 0)


# ------------------------------------------------------------------ layout
def test_panel_cards_and_log_fit_inside_the_window_without_overlap():
    state = GameState.new_game()
    w, h = game_screen.window_size(state)
    cards, log = game_screen.panel_layout(state, h)
    rects = cards + [log]
    for r in rects:
        assert r.left >= game_screen.board_width(state) and r.right <= w and r.top >= 0 and r.bottom <= h
    for i, a in enumerate(rects):
        for b in rects[i + 1:]:
            assert not a.colliderect(b)
    assert game_screen.log_capacity(state, h) >= 6                  # room for a useful number of lines


# ------------------------------------------------------------------ session scrolling
def test_session_scrolling_keys_and_clamp():
    s = GameSession(ai_mode=True)
    play_until_events(s, s.log_capacity() + 8)
    cap, n = s.log_capacity(), len(s.state.event_log)
    assert n > cap and s.log_offset == 0
    s.handle_event(key(pygame.K_PAGEUP))
    assert s.log_offset == cap - 1
    for _ in range(50):
        s.handle_event(key(pygame.K_PAGEUP))
    assert s.log_offset == n - cap                                    # clamped at the oldest
    s.handle_event(key(pygame.K_PAGEDOWN))
    assert s.log_offset == n - cap - (cap - 1)
    s.handle_event(key(pygame.K_END))
    assert s.log_offset == 0
    s.scroll_log(-5)
    assert s.log_offset == 0


def test_scrolled_view_stays_put_when_new_events_arrive():
    s = GameSession(ai_mode=True)
    play_until_events(s, s.log_capacity() + 3)
    assert not s.state.game_over
    s.scroll_log(2)
    cap = s.log_capacity()
    before = [e.text for e in visible_entries(s.state.event_log, cap, s.log_offset)[0]]
    for _ in range(40):
        before_len = len(s.state.event_log)
        s.ai_one_turn()
        if len(s.state.event_log) > before_len:
            break
    assert len(s.state.event_log) > before_len, "test needs a new event"
    after = [e.text for e in visible_entries(s.state.event_log, cap, s.log_offset)[0]]
    assert after == before


def test_restart_resets_the_log_view():
    s = GameSession(ai_mode=True)
    play_until_events(s, s.log_capacity() + 5)
    s.scroll_log(4)
    assert s.log_offset == 4
    s.handle_event(key(pygame.K_r))
    assert s.log_offset == 0 and s.state.event_log == []


def test_scrolling_never_changes_the_game():
    s = GameSession(ai_mode=True)
    play(s, 40)
    snap = (s.state.turn, s.state.eleven_pos, s.state.eleven_hp, list(s.state.event_log))
    for k in (pygame.K_PAGEUP, pygame.K_PAGEUP, pygame.K_PAGEDOWN, pygame.K_END):
        s.handle_event(key(k))
    assert snap == (s.state.turn, s.state.eleven_pos, s.state.eleven_hp, list(s.state.event_log))


# ------------------------------------------------------------------ drawing and the app
def test_overlay_carries_the_scroll_offset():
    s = GameSession(ai_mode=True)
    play_until_events(s, s.log_capacity() + 6)
    s.scroll_log(5)
    assert s.overlay()["log_offset"] == s.log_offset == 5


def test_panel_draws_the_real_last_event(app, monkeypatch):
    """The last visible entry on screen is the last line of state.event_log (checked via the drawn text calls)."""
    app.go("ai")
    s = app.session
    play(s, 60)
    drawn = []
    real = game_screen.draw_text
    monkeypatch.setattr(game_screen, "draw_text", lambda surf, font, text, *a, **k: (drawn.append(text), real(surf, font, text, *a, **k))[1])
    app.draw()
    last = parse(s.state.event_log[-1])
    assert f"T{last.turn}" in drawn and any(t.startswith(last.text[:20]) for t in drawn)
    app.go("menu")


def test_mouse_wheel_scrolls_only_over_the_panel(app, monkeypatch):
    app.go("ai")
    s = app.session
    play_until_events(s, s.log_capacity() + 8)
    x_panel = game_screen.board_width(s.state) + 50
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (x_panel, 600))
    app.handle(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=1))
    assert s.log_offset == 3
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (100, 400))     # over the board: ignored
    app.handle(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=1))
    assert s.log_offset == 3
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (x_panel, 600))
    app.handle(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-5))
    assert s.log_offset == 0
    app.go("menu")


def test_every_screen_still_renders_with_a_long_log(app):
    app.go("ai")
    s = app.session
    while not s.state.game_over:
        s.ai_one_turn()
    s.scroll_log(3)
    app.draw()
    app.go("results")
    app.draw()
    app.go("menu")
