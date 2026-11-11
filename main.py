"""Escape the Upside Down - entry point (Phase 6: Eleven's MCTS + A*, AI-vs-AI mode). Run: python main.py

Human controls: WASD/arrows move | Space wait | E attack adjacent Demogorgon | F rescue a friend in range
1 Radar | 2 Speed | 3 Teleport (then click a highlighted cell, Esc cancels) | 4 Freeze | X final attack
Speed: after the first move the game asks for a second move (Space = skip it).

AI controls: T switch AI-vs-AI on/off | N the AI plays ONE turn (also works in human mode)
In AI-vs-AI mode: Space pause/resume | + / - speed (0.5x 1x 2x 4x)
Always: P show paths | R restart | Esc cancel"""
import pygame

import config
from abilities import teleport
from ai.eleven_ai import ElevenAI
from game import rules
from game.actions import Action, MOVE_DELTAS
from game.state import GameState
from game.turn_manager import TurnManager
from ui import game_screen


def new_game():
    state = GameState.new_game()
    tm = TurnManager(state)
    return state, tm, ElevenAI(tm.metrics)


def ai_turn(state, tm, ai) -> None:
    """Let Eleven's AI play one full turn (MCTS picks the goal when needed, A* walks)."""
    choice = ai.choose_turn(state)
    if not tm.step(choice.action, choice.target, choice.bonus_action):
        if not tm.step(choice.action, choice.target):     # drop an illegal Speed bonus
            tm.step(Action.WAIT)                          # never stall the game


def stats_lines(tm):
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
    mc = tm.metrics.mcts.get("eleven")
    if mc and mc.calls:
        last = mc.last
        out.append(f"Eleven MCTS: {mc.calls} searches, {mc.simulations} simulations, avg {mc.avg_time_ms:.1f} ms")
        out.append(f"  last: {last.goal.label} ({last.visits}/{last.simulations} visits, value {last.value:+.2f}), "
                   f"{last.nodes_created} nodes, depth {last.max_depth}")
    return out


def main() -> None:
    pygame.init()
    state, tm, ai = new_game()
    screen = pygame.display.set_mode(game_screen.window_size(state))
    pygame.display.set_caption("Escape the Upside Down")
    font = pygame.font.SysFont("consolas,dejavusansmono,monospace", 18)
    small = pygame.font.SysFont("consolas,dejavusansmono,monospace", 13)
    big = pygame.font.SysFont("consolas,dejavusansmono,monospace", 48, bold=True)
    show_paths = False
    picking_teleport = False      # waiting for the human to click a destination
    pending_first_move = None     # Speed: first move chosen, waiting for the second
    ai_mode = False              # AI-vs-AI: Eleven is played by the AI
    paused = False
    speed_idx = config.AI_SPEEDS.index(1) if 1 in config.AI_SPEEDS else 0
    last_ai_tick = 0
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
                    state, tm, ai = new_game()
                    picking_teleport, pending_first_move, message = False, None, ""
                elif e.key == pygame.K_p:
                    show_paths = not show_paths
                elif e.key == pygame.K_ESCAPE:
                    picking_teleport, pending_first_move, message = False, None, ""
                elif e.key == pygame.K_t:
                    ai_mode = not ai_mode
                    picking_teleport, pending_first_move = False, None
                    paused, last_ai_tick = False, pygame.time.get_ticks()
                    message = "AI-vs-AI ON" if ai_mode else "Human control"
                elif state.game_over:
                    pass
                elif e.key == pygame.K_n:                    # the AI plays one turn
                    picking_teleport, pending_first_move = False, None
                    ai_turn(state, tm, ai)
                elif ai_mode:
                    if e.key == pygame.K_SPACE:
                        paused = not paused
                        last_ai_tick = pygame.time.get_ticks()
                    elif e.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                        speed_idx = min(len(config.AI_SPEEDS) - 1, speed_idx + 1)
                    elif e.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                        speed_idx = max(0, speed_idx - 1)
                elif picking_teleport:
                    message = "Click a highlighted cell to teleport (Esc cancels)"
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

        # AI-vs-AI clock: one AI turn every AI_TURN_DELAY_MS / speed
        now = pygame.time.get_ticks()
        if ai_mode and not paused and not state.game_over:
            if now - last_ai_tick >= config.AI_TURN_DELAY_MS / config.AI_SPEEDS[speed_idx]:
                ai_turn(state, tm, ai)
                last_ai_tick = now

        overlay = {"stats": stats_lines(tm), "message": message, "radar": tm.radar_readings}
        if ai_mode:
            overlay["ai_status"] = f"AI-vs-AI {config.AI_SPEEDS[speed_idx]}x" + (" PAUSED" if paused else "")
        if ai.run is not None and not state.game_over:
            overlay["goal"] = ai.run.goal.label
            if ai.run.target is not None:
                overlay["goal_target"] = ai.run.target
        if picking_teleport:
            overlay["teleport_cells"] = teleport.safe_cells(state)
        if show_paths:
            overlay["demogorgon_paths"] = tm.demogorgon_ai.current_paths(state)
            if ai.nav.last_result:
                overlay["eleven_path"] = ai.nav.last_result.path
        game_screen.draw(screen, state, font, big, small, overlay)
        pygame.display.flip()
        clock.tick(30)
    pygame.quit()


if __name__ == "__main__":
    main()