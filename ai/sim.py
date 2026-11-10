"""Fast simulation of whole turns for Eleven's MCTS (always on clones, never on the live state).

DESIGN DECISIONS (documented for the README)
  * Eleven's side uses the exact same rules as the real game (rules.apply_eleven_action).
  * To keep 300 simulations fast, the ENEMIES are modelled by a cheap stand-in policy inside the
    search: every Demogorgon and Vecna hits Eleven when adjacent, otherwise steps to the free
    neighbour that is closest to her by static walking distance. The real game still uses A* for
    Demogorgons and Minimax for Vecna; only the search's model of them is simplified.
  * The Mind Flayer is not modelled here (it arrives in Phase 7).
  * Rewards come from config.ELEVEN_REWARDS: events (rescue, kill, power, HP loss, death, escape,
    Mind Flayer defeat), a per-turn VECNA_DANGER penalty when Vecna is close, and a small PROGRESS
    term for cells gained toward the nearest objective, so far-away goals still get a gradient
    inside a short simulation."""
from __future__ import annotations
from typing import Optional, Tuple

import config
from abilities import speed
from ai.distance_table import UNREACHABLE, walk_distance
from ai.goals import GoalRun, StepFn, table_step
from game.actions import Action, MOVE_DELTAS
from game.rules import apply_eleven_action, can_enemy_enter, check_win_loss, demogorgon_hit, vecna_hit
from game.state import GameState, Winner

R = config.ELEVEN_REWARDS


def _chase_step(state: GameState, pos):
    """Free neighbour of `pos` that is closest to Eleven (None if no neighbour is closer)."""
    here = walk_distance(state.board, pos, state.eleven_pos)
    best, best_d = None, here
    for dx, dy in MOVE_DELTAS.values():
        n = (pos[0] + dx, pos[1] + dy)
        if can_enemy_enter(state, n):
            d = walk_distance(state.board, n, state.eleven_pos)
            if d < best_d:
                best, best_d = n, d
    return best


def _adjacent(a, b) -> bool:
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) <= 1


def enemy_phase(state: GameState) -> None:
    """Stand-in enemy policy (see module docstring). Skips frozen enemies, like the real game."""
    for d in sorted(state.living_demogorgons(), key=lambda x: x.id):
        if d.is_frozen:
            continue
        if _adjacent(d.pos, state.eleven_pos):
            demogorgon_hit(state, d)
        else:
            n = _chase_step(state, d.pos)
            if n is not None:
                d.pos = n
        if state.eleven_hp <= 0:
            return
    v = state.vecna
    if not v.is_frozen and state.eleven_hp > 0:
        if abs(v.pos[0] - state.eleven_pos[0]) + abs(v.pos[1] - state.eleven_pos[1]) <= config.VECNA_ATTACK_RANGE:
            vecna_hit(state)
        else:
            n = _chase_step(state, v.pos)
            if n is not None:
                v.pos = n


def upkeep(state: GameState) -> None:
    """Same timer ticks as TurnManager._update_timers."""
    state.status_effects = {k: v - 1 for k, v in state.status_effects.items() if v - 1 > 0}
    state.corrupted = {c: t - 1 for c, t in state.corrupted.items() if t - 1 > 0}
    for d in state.demogorgons:
        d.cooldown = max(0, d.cooldown - 1)
        d.frozen_turns = max(0, d.frozen_turns - 1)
    state.vecna.frozen_turns = max(0, state.vecna.frozen_turns - 1)


def sim_turn(state: GameState, action: Action, target=None, bonus: Optional[Action] = None) -> None:
    """One full simulated turn: Eleven, enemies, upkeep, win/loss, turn counter."""
    apply_eleven_action(state, action, target)
    if bonus is not None:
        apply_eleven_action(state, bonus)
    if state.eleven_hp > 0:
        enemy_phase(state)
    upkeep(state)
    check_win_loss(state)
    if not state.game_over:
        state.turn += 1


# ---------------------------------------------------------------- rewards
def snapshot(state: GameState) -> Tuple:
    return (len(state.rescued), len(state.living_demogorgons()), state.eleven_power, state.eleven_hp,
            state.mind_flayer.defeated)


def turn_reward(before: Tuple, state: GameState) -> float:
    """Unscaled reward for the events of one turn (before = snapshot taken before the turn)."""
    rescued, alive, power, hp, mf_done = before
    r = R["RESCUE_FRIEND"] * (len(state.rescued) - rescued)
    r += R["DEFEAT_DEMOGORGON"] * max(0, alive - len(state.living_demogorgons()))
    r += R["GAIN_POWER"] * max(0, state.eleven_power - power)
    r += R["LOSE_HP"] * max(0, hp - state.eleven_hp)
    if state.mind_flayer.defeated and not mf_done:
        r += R["DEFEAT_MIND_FLAYER"]
    if state.winner == Winner.ELEVEN:
        r += R["ESCAPE"]
    elif state.eleven_hp <= 0:
        r += R["DEATH"]
    elif state.game_over:                           # turn limit
        r += config.UTILITY_LOSS
    elif walk_distance(state.board, state.vecna.pos, state.eleven_pos) <= config.ELEVEN_DANGER_DISTANCE:
        r += R["VECNA_DANGER"]
    return r


def objective_distance(state: GameState) -> Optional[int]:
    """Walking distance to Eleven's current main objective: the nearest unrescued friend, else the
    portal once it is open. None when there is nothing to walk to."""
    targets = [p for n, p in state.friend_positions.items() if n not in state.rescued]
    if not targets and state.portal_active:
        targets = [state.portal_pos]
    if not targets:
        return None
    d = min(walk_distance(state.board, state.eleven_pos, t) for t in targets)
    return None if d >= UNREACHABLE else d


def progress_reward(start: GameState, end: GameState) -> float:
    """PROGRESS per cell gained toward the nearest objective. Only counted when Eleven had an
    objective both before and after (a rescue or the portal opening changes the objective, and
    those events are already rewarded by themselves)."""
    if start.rescued != end.rescued or end.game_over:
        return 0.0
    d0, d1 = objective_distance(start), objective_distance(end)
    if d0 is None or d1 is None:
        return 0.0
    return R["PROGRESS"] * (d0 - d1)


# ---------------------------------------------------------------- running a goal
def run_goal(state: GameState, run: GoalRun, max_turns: int, step_fn: StepFn = table_step) -> Tuple[float, int]:
    """Carry out `run` on `state` (a CLONE, mutated) for up to max_turns turns.
    Returns (unscaled reward, turns simulated). At least one turn always passes."""
    start = state.clone()
    reward, turns = 0.0, 0
    while turns < max_turns and not state.game_over:
        act = run.next_action(state, step_fn)
        if act is None:
            break
        action, target = act
        before = snapshot(state)
        bonus = None
        if speed.is_active(state) and action in MOVE_DELTAS and config.SPEED_MOVES_PER_TURN > 1:
            trial = state.clone()
            apply_eleven_action(trial, action)
            second = run.next_action(trial, step_fn)
            if second is not None and second[0] in MOVE_DELTAS:
                bonus = second[0]
        sim_turn(state, action, target, bonus)
        reward += turn_reward(before, state)
        turns += 1
    if turns == 0 and not state.game_over:           # goal already finished: still let a turn pass
        before = snapshot(state)
        sim_turn(state, Action.WAIT)
        reward += turn_reward(before, state)
        turns = 1
    return reward + progress_reward(start, state), turns