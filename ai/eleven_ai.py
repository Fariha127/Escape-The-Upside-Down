"""Eleven's AI controller: MCTS picks a strategic goal, real A* walks toward it.

Each turn:
  1. Decide whether to re-plan: no goal yet, goal finished, goal older than ELEVEN_REPLAN_TURNS,
     Eleven lost HP since the plan was made, or an enemy just came within ELEVEN_DANGER_DISTANCE.
  2. If so, run MCTS (ai/mcts.py) on clones of the state and keep the best goal.
  3. Turn the goal into this turn's concrete action. Movement uses the real A* Navigator
     (hazard-aware, characters are obstacles). While Speed is active a second move is added.
The live state is only read here: the TurnManager applies the returned TurnChoice."""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

import config
from abilities import speed, teleport
from ai.distance_table import walk_distance
from ai.goals import Goal, GoalRun, Kind, safe_step_cost, table_step
from ai.mcts import MCTSResult, mcts_search
from ai.metrics import Metrics
from ai.navigation import Navigator
from game.actions import Action, MOVE_DELTAS
from game.board import Pos
from game.rules import apply_eleven_action


@dataclass
class TurnChoice:
    action: Action
    target: Optional[Pos] = None            # Teleport destination
    bonus_action: Optional[Action] = None   # Speed's second move
    goal: Optional[Goal] = None
    replanned: bool = False                 # True if MCTS ran this turn


def _enemy_danger(state) -> bool:
    cells = [d.pos for d in state.living_demogorgons()] + [state.vecna.pos]
    return any(walk_distance(state.board, c, state.eleven_pos) <= config.ELEVEN_DANGER_DISTANCE for c in cells)


class ElevenAI:
    def __init__(self, metrics: Optional[Metrics] = None, simulations: Optional[int] = None):
        self.metrics = metrics or Metrics()
        self.simulations = simulations
        self.nav = Navigator(self.metrics)
        self.run: Optional[GoalRun] = None
        self.goal_age = 0
        self._hp_at_plan = 0
        self._danger_at_plan = False
        self.last_result: Optional[MCTSResult] = None
        self._stuck = False                     # last turn the goal gave no move: re-plan next turn
        self.pos_history: List[Pos] = []

    def _is_looping(self) -> bool:
        """True if Eleven has repeated positions in a 2-step (A-B-A-B) or 3-step cycle."""
        h = self.pos_history
        if len(h) >= 4 and h[-1] == h[-3] and h[-2] == h[-4] and h[-1] != h[-2]:
            return True
        if len(h) >= 6 and h[-3:] == h[-6:-3] and len(set(h[-3:])) > 1:
            return True
        return False

    # ---- planning ----
    def _needs_replan(self, state) -> bool:
        if self.run is None or self.run.done(state) or self._stuck:
            return True
        if self._is_looping():
            return True
        if self.goal_age >= config.ELEVEN_REPLAN_TURNS:
            return True
        if state.eleven_hp < self._hp_at_plan:
            return True
        return _enemy_danger(state) and not self._danger_at_plan

    def _plan(self, state) -> None:
        looping = self._is_looping()
        # Breakout: if stuck in a loop and Teleport is available to a safe visited cell, use it immediately
        if looping and "TELEPORT" in state.unlocked_abilities and state.ability_uses.get("TELEPORT", 0) > 0:
            safe_dest = teleport.best_safe_cell(state)
            if safe_dest is not None:
                self.run = GoalRun(Goal(Kind.ABILITY, "TELEPORT"), state)
                self.goal_age = 0
                self._hp_at_plan = state.eleven_hp
                self._danger_at_plan = _enemy_danger(state)
                self._stuck = False
                self.pos_history.clear()
                return

        result = mcts_search(state, self.simulations)
        self.metrics.record_mcts("eleven", result)
        self.last_result = result

        # Goal hysteresis: if currently active goal is unfinished and we aren't looping,
        # prefer sticking with it unless the alternative has a decisive advantage (> 8% visits)
        chosen_goal = result.goal
        if not looping and self.run is not None and not self.run.done(state) and not self._stuck:
            current_label = self.run.goal.label
            summary_dict = {item[0]: item[1] for item in result.root}
            current_visits = summary_dict.get(current_label, 0)
            if current_visits > 0 and (result.visits - current_visits) <= int(0.08 * result.simulations):
                chosen_goal = self.run.goal

        self.run = GoalRun(chosen_goal, state)
        self.goal_age = 0
        self._hp_at_plan = state.eleven_hp
        self._danger_at_plan = _enemy_danger(state)
        self._stuck = False
        if looping:
            self.pos_history.clear()

    # ---- the turn ----
    def _step_fn(self, state, target: Pos) -> Action:
        """Real A* step toward `target` (hazards, enemy hit zones, and recent footprint cost extra).
        If characters block every route (a Demogorgon sitting in a corridor), fall back to one greedy
        step along the static walking distances so Eleven keeps moving instead of freezing;
        with no free step she waits."""
        recent = [self.pos_history[-2]] if len(self.pos_history) >= 2 else []
        action, result = self.nav.next_action(state, target, safe_step_cost(state, recent_positions=recent))
        if result.found:
            return action
        return table_step(state, target)

    def choose_turn(self, state) -> TurnChoice:
        self.pos_history.append(state.eleven_pos)
        limit = getattr(config, "ELEVEN_RECENT_POS_LIMIT", 8)
        if len(self.pos_history) > limit:
            self.pos_history.pop(0)

        replanned = self._needs_replan(state)
        if replanned:
            self._plan(state)
        act = self.run.next_action(state, self._step_fn)
        if act is None:                                   # goal impossible right now: hold, re-plan next turn
            self._stuck = True
            self.goal_age += 1
            return TurnChoice(Action.WAIT, goal=self.run.goal, replanned=replanned)
        action, target = act
        self._stuck = action == Action.WAIT           # e.g. every route is blocked by characters
        bonus = None
        if speed.is_active(state) and action in MOVE_DELTAS and config.SPEED_MOVES_PER_TURN > 1:
            trial = state.clone()
            if apply_eleven_action(trial, action):
                second = self.run.next_action(trial, self._step_fn)
                if second is not None and second[0] in MOVE_DELTAS:
                    bonus = second[0]
        self.goal_age += 1
        return TurnChoice(action, target, bonus, self.run.goal, replanned)