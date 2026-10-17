"""Escape the Upside Down - Phase 3 entry point. Run: python main.py

Phase 3 debug keys:  N = Eleven auto-steps toward the nearest friend using A*  (test aid only;
real target choice by MCTS arrives in Phase 6)   P = show/hide A* paths   R = restart."""
import pygame

from ai.astar import manhattan
from ai.navigation import Navigator
from game.actions import Action
from game.state import GameState
from game.turn_manager import TurnManager
from ui import game_screen


def new_game():
    state = GameState.new_game()
    tm = TurnManager(state)
    return state, tm, Navigator(tm.metrics)


def stats_lines(tm, nav):
    """Two short lines per A* user, straight from the recorded search statistics."""
    out = []
    for role, label in (("demogorgon", "Demogorgon A*"), ("eleven", "Eleven A*")):
        st = tm.metrics.astar.get(role)
        if not st:
            continue
        last = st.last
        out.append(f"{label}: {st.calls} searches, {st.nodes_explored} nodes, {st.cache_hits} reused")
        res = f"path {last.path_length}" if last.found else "no path"
        out.append(f"  last: {res}, {last.nodes_explored} nodes, {last.time_ms:.2f} ms")
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
    clock = pygame.time.Clock()
    running = True
    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_r:
                    state, tm, nav = new_game()
                elif e.key == pygame.K_p:
                    show_paths = not show_paths
                elif e.key == pygame.K_n and not state.game_over:
                    friends = [p for n, p in state.friend_positions.items() if n not in state.rescued]
                    if friends:
                        target = min(friends, key=lambda p: manhattan(p, state.eleven_pos))
                        action, _ = nav.next_action(state, target)
                        tm.step(action)
                elif e.key in game_screen.KEYMAP:
                    tm.step(game_screen.KEYMAP[e.key])  # illegal moves are ignored
        overlay = {"stats": stats_lines(tm, nav)}
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
