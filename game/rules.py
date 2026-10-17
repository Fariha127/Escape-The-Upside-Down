"""Pure game rules for Eleven's low-level actions. No rendering, no AI.
Later phases extend legal_actions()/apply_eleven_action() with attack/rescue/abilities."""
from __future__ import annotations
from typing import List

from game.actions import Action, MOVE_DELTAS
from game.state import GameState, Pos


def move_target(state: GameState, action: Action) -> Pos:
    dx, dy = MOVE_DELTAS[action]
    return (state.eleven_pos[0] + dx, state.eleven_pos[1] + dy)


def can_eleven_enter(state: GameState, p: Pos) -> bool:
    """Walls, map edges, corrupted cells and cells occupied by enemies are not enterable."""
    return not state.is_blocked(p) and p not in state.enemy_positions()


def can_enemy_enter(state: GameState, p: Pos) -> bool:
    """Same collision rule for every enemy: no walls/corruption, no other character's cell."""
    return (not state.is_blocked(p) and p not in state.enemy_positions()
            and p != state.eleven_pos)


def legal_eleven_actions(state: GameState) -> List[Action]:
    """Only legal actions are returned. WAIT is always legal while the game is running."""
    if state.game_over:
        return []
    actions = [a for a in MOVE_DELTAS if can_eleven_enter(state, move_target(state, a))]
    actions.append(Action.WAIT)
    return actions


def apply_eleven_action(state: GameState, action: Action) -> bool:
    """Mutates `state` (callers pass a clone when simulating). Returns False if illegal."""
    if action not in legal_eleven_actions(state):
        return False
    if action in MOVE_DELTAS:
        state.eleven_pos = move_target(state, action)
        state.visited.add(state.eleven_pos)
    return True  # WAIT: nothing to do


def check_win_loss(state: GameState) -> None:
    """Win needs ALL conditions (reaching the portal alone is not enough). Loss: HP<=0 or turn cap."""
    from game.state import Winner
    if state.game_over:
        return
    if state.eleven_hp <= 0:
        state.winner = Winner.ENEMIES
        state.log("Eleven has fallen.")
        return
    all_friends = len(state.rescued) == len(state.friend_positions)
    if all_friends and state.mind_flayer.defeated and state.eleven_pos == state.portal_pos:
        state.winner = Winner.ELEVEN
        state.log("Eleven escaped through the portal!")
        return
    if state.turn + 1 >= state.max_turns:
        state.winner = Winner.ENEMIES
        state.log("Turn limit reached - Eleven failed to escape.")
