"""Escape the Upside Down - Phase 1 entry point: a walkable Upside Down map. Run: python main.py"""
import pygame

from game.state import GameState
from game.turn_manager import TurnManager
from ui import game_screen


def main() -> None:
    pygame.init()
    state = GameState.new_game()
    screen = pygame.display.set_mode(game_screen.window_size(state))
    pygame.display.set_caption("Escape the Upside Down")
    font = pygame.font.SysFont("consolas,dejavusansmono,monospace", 18)
    big = pygame.font.SysFont("consolas,dejavusansmono,monospace", 48, bold=True)
    tm = TurnManager(state)
    clock = pygame.time.Clock()
    running = True
    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_r:
                    state = GameState.new_game(); tm = TurnManager(state)
                elif e.key in game_screen.KEYMAP:
                    tm.step(game_screen.KEYMAP[e.key])  # illegal moves are simply ignored
        game_screen.draw(screen, state, font, big)
        pygame.display.flip()
        clock.tick(30)
    pygame.quit()


if __name__ == "__main__":
    main()
