"""Phase 8: menu, HUD, AI panel, overlays, results screen. Headless (SDL dummy driver).

The UI only READS the game, so these tests check that (a) every screen renders, (b) the numbers on screen
equal the numbers the real searches recorded, (c) the session drives the same TurnManager as before."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

import config
from game.actions import Action
from game.state import GameState, Winner
from main import App
from ui import game_screen, theme
from ui.session import GameSession
from ui.stats_view import build_results, demogorgons_defeated, stats_lines, stats_sections, turns_played


@pytest.fixture(scope="module")
def app():
    a = App()
    yield a
    pygame.quit()


def key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k)


def click(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)


def play_ai(session, turns):
    for _ in range(turns):
        if session.state.game_over:
            break
        session.ai_one_turn()


def finish(session, limit=400):
    while not session.state.game_over and limit:
        session.ai_one_turn()
        limit -= 1
    assert session.state.game_over


# ------------------------------------------------------------------ every screen renders
def test_every_screen_renders(app):
    for target in ("menu", "howto", "algos", "settings"):
        app.go(target)
        app.draw()
    app.go("human")
    app.draw()
    play_ai(app.session, 5)
    app.draw()
    app.go("ai")
    app.session.show_paths = True
    play_ai(app.session, 30)
    app.draw()
    finish(app.session)
    app.draw()
    app.go("results")
    app.draw()
    app.go("menu")


def test_window_fits_board_and_panel(app):
    state = GameState.new_game()
    w, h = game_screen.window_size(state)
    assert w == state.board.width * theme.CELL + theme.PANEL_W
    assert h >= state.board.height * theme.CELL + theme.HUD_H


def test_cell_at_ignores_hud_and_panel():
    state = GameState.new_game()
    assert game_screen.cell_at(state, (5, 5)) is None                      # HUD strip
    assert game_screen.cell_at(state, (theme.CELL * 15 + 5, theme.HUD_H + 5)) is None   # AI panel
    assert game_screen.cell_at(state, (5, theme.HUD_H + 5)) == (0, 0)
    assert game_screen.cell_at(state, (theme.CELL * 3 + 1, theme.HUD_H + theme.CELL * 2 + 1)) == (3, 2)


def test_drawing_never_changes_the_game(app):
    app.go("ai")
    s = app.session
    play_ai(s, 15)
    before = (s.state.eleven_pos, s.state.eleven_hp, s.state.eleven_power, s.state.turn,
              list(s.state.event_log), s.tm.metrics.minimax.calls)
    s.show_paths = True
    for _ in range(3):
        app.surface.fill((0, 0, 0))
        game_screen.draw(app.surface, s.state, s.tm, app.fonts, s.overlay(),
                         game_screen.control_buttons(s.state, s.ai_mode, s.paused))
    after = (s.state.eleven_pos, s.state.eleven_hp, s.state.eleven_power, s.state.turn,
             list(s.state.event_log), s.tm.metrics.minimax.calls)
    assert before == after
    app.go("menu")


# ------------------------------------------------------------------ the numbers come from real runs
def test_panel_sections_match_recorded_metrics(app):
    app.go("ai")
    s = app.session
    play_ai(s, 40)
    m = s.tm.metrics
    secs = {sec.title: sec for sec in stats_sections(s.tm)}
    vec = secs["Vecna: Minimax"]
    assert vec.has_data
    assert f"{m.minimax.calls} searches" in vec.lines[0]
    assert f"total {m.minimax.nodes_evaluated} evaluated, {m.minimax.branches_pruned} pruned" in vec.lines[1]
    assert m.minimax.last.action.value in vec.lines[2]
    el = secs["Eleven: MCTS goal"]
    mc = m.mcts["eleven"]
    assert f"{mc.calls} searches, {mc.simulations} simulations" in el.lines[0]
    astar = secs["A* pathfinding"]
    assert any(f"{m.astar['demogorgon'].calls} searches, {m.astar['demogorgon'].nodes_explored} nodes" in l
               for l in astar.lines)
    app.go("menu")


def test_panel_says_no_search_yet_instead_of_inventing_numbers():
    state = GameState.new_game()
    from game.turn_manager import TurnManager
    tm = TurnManager(state)
    secs = stats_sections(tm)
    assert [s.has_data for s in secs] == [False, False, False, False]
    assert all(s.lines == ["no search yet"] for s in secs)
    assert stats_lines(tm) == []


def test_results_use_the_real_metrics_and_state(app):
    app.go("ai")
    s = app.session
    finish(s)
    r = build_results(s.state, s.tm)
    rows = dict(r.rows)
    ai = dict(r.ai_rows)
    m = s.tm.metrics
    assert rows["Turns played"] == f"{turns_played(s.state)} / {config.MAX_TURNS}"
    assert rows["Friends rescued"] == f"{len(s.state.rescued)} / 4"
    assert rows["Final HP"] == str(s.state.eleven_hp) and rows["Final power"] == str(s.state.eleven_power)
    assert rows["Winner"] == ("Eleven" if s.state.winner == Winner.ELEVEN else "Enemies")
    assert f"{m.mcts['eleven'].simulations} simulations in {m.mcts['eleven'].calls} searches" in ai["Eleven MCTS"]
    assert f"{m.minimax.nodes_evaluated} nodes evaluated, {m.minimax.branches_pruned} pruned" in ai["Vecna Minimax"]
    total = sum(st.nodes_explored for st in m.astar.values())
    assert ai["A* total"].startswith(f"{total} nodes explored")
    assert r.eleven_won == (s.state.winner == Winner.ELEVEN)
    app.go("menu")


def test_results_for_each_ending():
    from game.turn_manager import TurnManager
    s = GameState.new_game()
    tm = TurnManager(s)
    assert build_results(s, tm).headline == "GAME IN PROGRESS"
    assert dict(build_results(s, tm).ai_rows)["Vecna Minimax"] == "did not run"
    s.eleven_hp = 0
    s.winner = Winner.ENEMIES
    assert build_results(s, tm).headline == "ELEVEN FELL"
    s.eleven_hp = 3
    assert build_results(s, tm).headline == "TURN LIMIT REACHED"
    s.winner = Winner.ELEVEN
    assert build_results(s, tm).headline == "ELEVEN ESCAPED!"


def test_demogorgon_count_ignores_temporary_creatures():
    s = GameState.new_game()
    s.demogorgons[0].alive = False
    s.demogorgons[1].alive = False
    assert demogorgons_defeated(s) == 2
    from game.mind_flayer_rules import MFAction, SPAWN, apply_mf_action
    s.mind_flayer.active = True
    cell = next(p for p in [(2, 1), (3, 1), (1, 2), (2, 2)] if s.board.is_walkable(p) and p != s.eleven_pos)
    apply_mf_action(s, MFAction(SPAWN, cell))
    temp = [d for d in s.demogorgons if d.temporary]
    assert temp
    temp[0].alive = False
    assert demogorgons_defeated(s) == 2          # a killed temporary creature does not count


# ------------------------------------------------------------------ session behaves like the old main loop
def test_session_keys_move_eleven_and_restart():
    s = GameSession()
    start = s.state.eleven_pos
    legal = [a for a in (Action.MOVE_RIGHT, Action.MOVE_DOWN) if a in
             __import__("game.rules", fromlist=["x"]).legal_eleven_actions(s.state)]
    k = {Action.MOVE_RIGHT: pygame.K_d, Action.MOVE_DOWN: pygame.K_s}[legal[0]]
    s.handle_event(key(k))
    assert s.state.turn == 1 and s.state.eleven_pos != start
    s.handle_event(key(pygame.K_r))
    assert s.state.turn == 0 and s.state.eleven_pos == start


def test_session_illegal_move_is_ignored():
    s = GameSession()
    s.handle_event(key(pygame.K_w))             # Eleven starts at the top edge
    assert s.state.turn == 0


def test_ai_mode_pause_speed_and_step():
    s = GameSession(ai_mode=True)
    s.handle_event(key(pygame.K_SPACE))
    assert s.paused
    t = s.state.turn
    s.update(10 ** 9)
    assert s.state.turn == t                    # paused: the clock does nothing
    s.command("step")
    assert s.state.turn == t + 1                # Step works while paused
    s.handle_event(key(pygame.K_SPACE))
    assert not s.paused
    s.speed_idx = 0
    s.handle_event(key(pygame.K_PLUS))
    assert s.speed == config.AI_SPEEDS[1]
    for _ in range(10):
        s.command("faster")
    assert s.speed == config.AI_SPEEDS[-1]
    for _ in range(10):
        s.command("slower")
    assert s.speed == config.AI_SPEEDS[0]


def test_ai_clock_plays_a_turn_after_the_delay():
    s = GameSession(ai_mode=True)
    s._last_ai_tick = 0
    s.update(int(config.AI_TURN_DELAY_MS / s.speed) + 1)
    assert s.state.turn == 1


def test_toggle_ai_and_menu_request():
    s = GameSession()
    s.handle_event(key(pygame.K_t))
    assert s.ai_mode
    s.handle_event(key(pygame.K_t))
    assert not s.ai_mode
    s.handle_event(key(pygame.K_m))
    assert s.request == "menu"


def test_enter_opens_results_only_when_the_game_is_over():
    s = GameSession(ai_mode=True)
    s.handle_event(key(pygame.K_RETURN))
    assert s.request is None
    finish(s)
    s.handle_event(key(pygame.K_RETURN))
    assert s.request == "results"
    t = s.state.turn
    s.command("step")                           # nothing happens after the game ended
    assert s.state.turn == t


def test_vecna_choice_overlay_is_the_real_last_search():
    s = GameSession(ai_mode=True)
    s.show_paths = True
    play_ai(s, 6)
    mm = s.tm.metrics.minimax
    assert mm.calls > 0
    vc = s.overlay().get("vecna_choice")
    assert vc is not None
    assert vc["action"] == mm.last.action and vc["score"] == mm.last.score
    assert vc["to"] == s.state.vecna.pos


def test_overlay_has_no_paths_when_hidden():
    s = GameSession(ai_mode=True)
    play_ai(s, 6)
    s.show_paths = False
    o = s.overlay()
    assert "demogorgon_paths" not in o and "eleven_path" not in o and "vecna_choice" not in o
    assert o["status"].startswith("AI-vs-AI")
    assert GameSession().overlay()["status"] == "Human vs AI"


def test_control_buttons_enabled_states():
    state = GameState.new_game()
    human = {b.id: b for b in game_screen.control_buttons(state, False, False)}
    assert not human["pause"].enabled and not human["faster"].enabled and human["step"].enabled
    ai = {b.id: b for b in game_screen.control_buttons(state, True, True)}
    assert ai["pause"].enabled and ai["pause"].label == "Resume" and ai["pause"].active
    state.winner = Winner.ENEMIES
    over = {b.id: b for b in game_screen.control_buttons(state, True, False)}
    assert not over["step"].enabled and over["restart"].enabled and over["menu"].enabled


# ------------------------------------------------------------------ app navigation
def test_menu_navigation_by_keyboard_and_mouse(app):
    app.go("menu")
    app.handle(key(pygame.K_DOWN))
    app.handle(key(pygame.K_RETURN))
    assert app.mode == "game" and app.session.ai_mode
    app.handle(key(pygame.K_m))
    assert app.mode == "menu"
    first = app.screen.buttons[0]
    app.handle(click(first.rect.center))
    assert app.mode == "game" and not app.session.ai_mode
    app.go("menu")
    algos = next(b for b in app.screen.buttons if b.id == "algos")
    app.handle(click(algos.rect.center))
    assert app.mode == "info"
    app.handle(key(pygame.K_ESCAPE))
    assert app.mode == "menu"


def test_panel_buttons_are_clickable(app):
    app.go("ai")
    s = app.session
    pause = next(b for b in game_screen.control_buttons(s.state, s.ai_mode, s.paused) if b.id == "pause")
    app.handle(click(pause.rect.center))
    assert s.paused
    step = next(b for b in game_screen.control_buttons(s.state, s.ai_mode, s.paused) if b.id == "step")
    app.handle(click(step.rect.center))
    assert s.state.turn == 1
    app.go("menu")


def test_results_screen_flow(app):
    app.go("ai")
    finish(app.session)
    app.handle(key(pygame.K_RETURN))
    assert app.mode == "results"
    app.handle(key(pygame.K_ESCAPE))
    assert app.mode == "game"
    app.handle(key(pygame.K_RETURN))
    app.handle(key(pygame.K_r))                 # play again keeps the mode
    assert app.mode == "game" and app.session.ai_mode and app.session.state.turn == 0
    app.go("menu")


def test_settings_toggle_alpha_beta_and_speed(app, monkeypatch):
    monkeypatch.setattr(config, "VECNA_USE_ALPHA_BETA", True)
    app.go("settings")
    ab = next(b for b in app.screen.buttons if b.id == "ab")
    app.handle(click(ab.rect.center))
    assert config.VECNA_USE_ALPHA_BETA is False
    app.handle(click(ab.rect.center))
    assert config.VECNA_USE_ALPHA_BETA is True
    before = app.settings.speed_idx
    speed = next(b for b in app.screen.buttons if b.id == "speed")
    app.handle(click(speed.rect.center))
    assert app.settings.speed_idx == (before + 1) % len(config.AI_SPEEDS)
    app.settings.speed_idx = before
    app.go("menu")


def test_plain_minimax_shows_up_in_the_panel(app, monkeypatch):
    monkeypatch.setattr(config, "VECNA_USE_ALPHA_BETA", False)
    s = GameSession(ai_mode=True)
    play_ai(s, 6)
    vec = {sec.title: sec for sec in stats_sections(s.tm)}["Vecna: Minimax"]
    assert vec.lines[0].startswith("plain, depth")
    assert s.tm.metrics.minimax.branches_pruned == 0
