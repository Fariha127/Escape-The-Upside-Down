"""Escape the Upside Down - entry point (Phase 5: Vecna plays with Minimax + Alpha-Beta). Run: python main.py

Human controls: WASD/arrows move | Space wait | E attack adjacent Demogorgon | F rescue a friend in range
1 Radar | 2 Speed | 3 Teleport (then click a highlighted cell, Esc cancels) | 4 Freeze | X final attack
P show A* paths | N Eleven auto-steps toward nearest friend via A* (test aid only;
real target choice by MCTS arrives in Phase 6) | R restart.
Speed: after the first move the game asks for a second move (Space = skip it)."""
import pygame

from abilities import teleport
from ai.astar import manhattan
from ai.navigation import Navigator
from game import rules
from game.actions import Action, MOVE_DELTAS
from game.state import GameState
from game.turn_manager import TurnManager
from ui import game_screen


def new_game():
    state = GameState.new_game()
    tm = TurnManager(state)
    return state, tm, Navigator(tm.metrics)


def stats_lines(tm, nav):
    """Stat lines for the HUD, straight from the recorded search statistics (nothing is estimated)."""
    out = []
    for role, label in (("demogorgon", "Demogorgon A*"), ("eleven", "Eleven A*"), ("radar", "Radar A*")):
        st = tm.metrics.astar.get(role)
        if not st:
            continue
        reused = f", {st.cache_hits} reused" if st.cache_hits else ""
        out.append(f"{label}: {st.calls} searches, {st.nodes_explored} nodes, avg {st.avg_time_ms:.2f} ms{reused}")
    mm = tm.metrics.minimax
    if mm.calls:
        last = mm.last
        mode = "AB" if last.alpha_beta else "plain"
        out.append(f"Vecna Minimax {mode} d{last.depth}: {mm.calls} searches, "
                   f"{mm.nodes_evaluated} evaluated, {mm.branches_pruned} pruned")
        out.append(f"  last: {last.action.value} score {last.score:.1f}, {last.nodes_evaluated} evaluated, "
                   f"{last.branches_pruned} pruned, {last.time_ms:.2f} ms")
    return out


def main() -> None:
    pygame.init()
    state, tm, nav = new_game()
    screen = pygame.display.set_mode(game_screen.window_size(state))
    pygame.display.set_caption("Escape the Upside Down")
    font = pygame.font.SysFont("consolas,dejavusansmono,monospace", 18)
    small = pygame.font.SysFont("consolas,dejavusansmono,monospace", 13)
    big = pygame.font.SysFont("consolas,dejavusansmono,monospace", 48, bold=True)
    show_paths = False
    picking_teleport = False      # waiting for the human to click a destination
    pending_first_move = None     # Speed: first move chosen, waiting for the second
    message = ""
    clock = pygame.time.Clock()
    running = True
    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.MOUSEBUTTONDOWN and picking_teleport and not state.game_over:
                cell = game_screen.cell_at(state, e.pos)
                if cell in teleport.safe_cells(state):
                    tm.step(Action.USE_TELEPORT, target=cell)
                    picking_teleport, message = False, ""
                else:
                    message = "Not a valid Teleport cell - click a highlighted cell or press Esc"
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_r:
                    state, tm, nav = new_game()
                    picking_teleport, pending_first_move, message = False, None, ""
                elif e.key == pygame.K_p:
                    show_paths = not show_paths
                elif e.key == pygame.K_ESCAPE:
                    picking_teleport, pending_first_move, message = False, None, ""
                elif state.game_over:
                    pass
                elif picking_teleport:
                    message = "Click a highlighted cell to teleport (Esc cancels)"
                elif e.key == pygame.K_n:
                    friends = [p for n, p in state.friend_positions.items() if n not in state.rescued]
                    if friends:
                        target = min(friends, key=lambda p: manhattan(p, state.eleven_pos))
                        action, _ = nav.next_action(state, target)
                        tm.step(action)
                elif pending_first_move is not None:        # Speed: choose the second move
                    second = game_screen.KEYMAP.get(e.key)
                    if second in MOVE_DELTAS:
                        if tm.step(pending_first_move, bonus_action=second):
                            pending_first_move, message = None, ""
                        else:
                            message = "Second move blocked - pick another direction or Space to skip"
                    elif second == Action.WAIT:
                        tm.step(pending_first_move)
                        pending_first_move, message = None, ""
                elif e.key in game_screen.ACTION_KEYS:
                    action = game_screen.ACTION_KEYS[e.key]
                    if action == Action.USE_TELEPORT:
                        if action in rules.legal_eleven_actions(state):
                            picking_teleport, message = True, "Click a highlighted cell to teleport (Esc cancels)"
                        else:
                            message = "Teleport unavailable (needs Mike rescued and a safe visited cell)"
                    elif not tm.step(action):
                        message = f"{action.value} is not possible right now"
                    else:
                        message = ""
                elif e.key in game_screen.KEYMAP:
                    action = game_screen.KEYMAP[e.key]
                    if action in MOVE_DELTAS and tm.can_bonus_move() and action in rules.legal_eleven_actions(state):
                        pending_first_move, message = action, "Speed: pick the second move (Space = skip)"
                    elif not tm.step(action):                # illegal moves are ignored
                        pass
                    else:
                        message = ""
        overlay = {"stats": stats_lines(tm, nav), "message": message, "radar": tm.radar_readings}
        if picking_teleport:
            overlay["teleport_cells"] = teleport.safe_cells(state)
        if show_paths:
            overlay["demogorgon_paths"] = tm.demogorgon_ai.current_paths(state)
            if nav.last_result:
                overlay["eleven_path"] = nav.last_result.path
        game_screen.draw(screen, state, font, big, small, overlay)
        pygame.display.flip()
        clock.tick(30)
    pygame.quit()


if __name__ == "__main__":
    main()