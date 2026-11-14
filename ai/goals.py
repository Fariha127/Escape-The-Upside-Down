"""Strategic goals: the 'WHAT' that Eleven's MCTS chooses between (A* then supplies the 'HOW').

A Goal is a high-level intention such as "rescue Mike" or "evade". A GoalRun executes one goal
one turn at a time: it turns the goal into a concrete low-level action (a MOVE_* from a path
planner, ATTACK, RESCUE, an ability, FINAL_ATTACK). The path planner is passed in as `step_fn`,
so the real game can use real A* (ai/navigation.py) while MCTS simulations use a fast
table-based planner (ai/sim.py). Both go through the same GoalRun, so they agree on what a goal means.

DESIGN DECISIONS
  * Goals: RESCUE <friend>, HUNT (kill the nearest normal Demogorgon for power), EVADE (walk to the
    safest nearby cell), PORTAL (only once every friend is rescued and the portal is open),
    FINAL (final psychic attack, or farm power until it is possible), USE <ability>.
  * A GoalRun returns None when its goal is finished or no longer possible."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Callable, List, Optional, Tuple

import config
from abilities import teleport
from ai.distance_table import UNREACHABLE, distance_table, walk_distance
from characters import friends as friend_rules
from characters import mind_flayer as mf_rules
from game.actions import Action, MOVE_DELTAS
from game.board import Pos, Terrain
from game.rules import can_attack, can_eleven_enter, legal_eleven_actions


class Kind(Enum):
    RESCUE = "RESCUE"
    HUNT = "HUNT"
    EVADE = "EVADE"
    PORTAL = "PORTAL"
    FINAL = "FINAL"
    ABILITY = "USE"


@dataclass(frozen=True)
class Goal:
    kind: Kind
    arg: Optional[str] = None          # friend name (RESCUE) or ability name (ABILITY)

    @property
    def label(self) -> str:
        return f"{self.kind.value} {self.arg}" if self.arg else self.kind.value


# Abilities the AI may choose
AI_ABILITIES = ("FREEZE", "SPEED", "TELEPORT")
_ABILITY_ACTION = {"FREEZE": Action.USE_FREEZE, "SPEED": Action.USE_SPEED, "TELEPORT": Action.USE_TELEPORT}

StepFn = Callable[[object, Pos], Action]       # (state, target cell) -> one MOVE_* (or WAIT if stuck)


def normal_demogorgons(state) -> list:
    """Living Demogorgons that give power when killed (temporary creatures give none)."""
    return [d for d in state.living_demogorgons() if not d.temporary]


def nearest_demogorgon(state):
    cands = normal_demogorgons(state)
    if not cands:
        return None
    return min(cands, key=lambda d: (walk_distance(state.board, state.eleven_pos, d.pos), d.id))


def applicable_goals(state) -> List[Goal]:
    """Goals that make sense right now (a fixed order, so searches are deterministic)."""
    if state.game_over:
        return []
    goals = [Goal(Kind.RESCUE, f) for f in friend_rules.FRIEND_NAMES
             if f in state.friend_positions and f not in state.rescued]
    if config.ELEVEN_RESCUE_WILL_LAST:
        # Rescuing Will wakes the Mind Flayer, so MCTS is only offered "rescue Will" once every other
        # friend is saved (MCTS still chooses freely among the remaining goals).
        others_left = any(g.arg != "Will" for g in goals)
        goals = [g for g in goals if not (g.arg == "Will" and others_left)]
    if state.eleven_power >= config.DEMOGORGON_ATTACK_COST and normal_demogorgons(state):
        goals.append(Goal(Kind.HUNT))
    goals.append(Goal(Kind.EVADE))
    if state.portal_active and len(state.rescued) == len(state.friend_positions):
        goals.append(Goal(Kind.PORTAL))
    if mf_rules.can_final_attack(state) or (
            state.mind_flayer.active and not state.mind_flayer.defeated and "Will" in state.rescued
            and state.eleven_power < config.FINAL_POWER_REQUIREMENT
            and state.eleven_power >= config.DEMOGORGON_ATTACK_COST and normal_demogorgons(state)):
        goals.append(Goal(Kind.FINAL))
    legal = set(legal_eleven_actions(state))
    if not config.ELEVEN_ABILITIES_ONLY_IN_DANGER or enemy_near(state, config.ELEVEN_ABILITY_DANGER_DISTANCE):
        for a in AI_ABILITIES:
            if _ABILITY_ACTION[a] in legal:
                goals.append(Goal(Kind.ABILITY, a))
    return goals

def enemy_near(state, distance: int) -> bool:
    """True when a living enemy (Vecna or a Demogorgon) is within `distance` walking steps of Eleven."""

    enemies = [state.vecna.pos] + [
        d.pos for d in state.living_demogorgons()
    ]

    return any(
        walk_distance(state.board, state.eleven_pos, p) <= distance
        for p in enemies
    )
_OPEN_CACHE: dict = {}
OPEN_LOOKAHEAD = 3          # "openness" of a cell = number of cells within this many steps (dead ends score low)
OPEN_MAX = 2 * OPEN_LOOKAHEAD * (OPEN_LOOKAHEAD + 1)       # cells in a full diamond (24), excluding the centre


def openness(board, cell: Pos) -> float:
    """0..1: how open the surroundings of `cell` are (static terrain). A dead-end pocket scores low."""
    table = _OPEN_CACHE.setdefault(board.terrain, {})
    if cell not in table:
        reach = distance_table(board).get(cell, {})
        table[cell] = min(1.0, (sum(1 for d in reach.values() if 0 < d <= OPEN_LOOKAHEAD)) / OPEN_MAX)
    return table[cell]


def evade_cell(state) -> Pos:
    """Safest cell within EVADE_RADIUS. Safety = walking distance from the nearest enemy (capped, so
    'far enough' is equally good) + an openness bonus (EVADE_OPEN_WEIGHT), so dead-end pockets lose
    to open areas. Ties: the shortest trip for Eleven, then lowest coords.
    Hazard cells and occupied cells are never chosen."""
    near = distance_table(state.board).get(state.eleven_pos, {})
    enemy_dist = teleport.enemy_distance_map(state)
    cap = 2 * config.EVADE_RADIUS
    best, best_key = state.eleven_pos, None
    for cell, d in near.items():
        if d > config.EVADE_RADIUS or state.is_blocked(cell):
            continue
        if cell != state.eleven_pos and (cell in state.enemy_positions()
                                         or state.board.terrain_at(cell) == Terrain.HAZARD):
            continue
        safety = min(enemy_dist.get(cell, UNREACHABLE), cap) + config.EVADE_OPEN_WEIGHT * openness(state.board, cell)
        key = (-round(safety, 6), d, cell)
        if best_key is None or key < best_key:
            best, best_key = cell, key
    return best


class GoalRun:
    """One goal being carried out. Create it, then call next_action(state, step_fn) once per turn."""

    def __init__(self, goal: Goal, state):
        self.goal = goal
        self.started_turn = state.turn
        self.start_hunt_count = len(normal_demogorgons(state))
        self.cell: Optional[Pos] = evade_cell(state) if goal.kind == Kind.EVADE else None
        self.used = False                              # ABILITY / FINAL: acted once
        self.target: Optional[Pos] = None              # cell currently being walked to (for the overlay)

    # ---- is it finished? ----
    def done(self, state) -> bool:
        k = self.goal.kind
        if state.game_over:
            return True
        if k == Kind.RESCUE:
            return self.goal.arg in state.rescued
        if k == Kind.HUNT:
            return len(normal_demogorgons(state)) < self.start_hunt_count
        if k == Kind.EVADE:
            return state.eleven_pos == self.cell
        if k == Kind.FINAL:
            return state.mind_flayer.defeated
        if k == Kind.ABILITY:
            return self.used
        return False                                   # PORTAL: ends when the game does

    # ---- one concrete action ----
    def next_action(self, state, step_fn: StepFn) -> Optional[Tuple[Action, Optional[Pos]]]:
        """(action, teleport_target) for this turn, or None if the goal is finished or impossible."""
        if self.done(state):
            return None
        k, arg = self.goal.kind, self.goal.arg
        if k == Kind.RESCUE:
            if friend_rules.can_rescue(state, arg):
                return Action.RESCUE, None
            return self._walk(state, step_fn, state.friend_positions[arg])
        if k in (Kind.HUNT, Kind.FINAL):
            if k == Kind.FINAL and mf_rules.can_final_attack(state):
                self.used = True
                return Action.FINAL_ATTACK, None
            if state.eleven_power < config.DEMOGORGON_ATTACK_COST:
                return None
            target = nearest_demogorgon(state)
            if target is None:
                return None
            if can_attack(state):
                return Action.ATTACK, None
            return self._walk(state, step_fn, target.pos)
        if k == Kind.EVADE:
            return self._walk(state, step_fn, self.cell)
        if k == Kind.PORTAL:
            return self._walk(state, step_fn, state.portal_pos)
        if k == Kind.ABILITY:
            action = _ABILITY_ACTION[arg]
            if action not in legal_eleven_actions(state):
                return None
            self.used = True
            return action, (teleport.best_safe_cell(state) if arg == "TELEPORT" else None)
        return None

    def _walk(self, state, step_fn: StepFn, target: Pos):
        self.target = target
        return step_fn(state, target), None


def hit_zone(state) -> set:
    """Cells where an enemy standing next to Eleven could hit her this coming enemy phase:
    every cell within attack range of a Demogorgon that can attack, or of an unfrozen Vecna."""
    zone = set()
    sources = [(d.pos, 1) for d in state.living_demogorgons() if d.can_attack]
    if not state.vecna.is_frozen:
        sources.append((state.vecna.pos, config.VECNA_ATTACK_RANGE))
    for (x, y), r in sources:
        for dx in range(-r, r + 1):
            for dy in range(-(r - abs(dx)), r - abs(dx) + 1):
                zone.add((x + dx, y + dy))
    return zone


def safe_step_cost(state):
    """A* step cost for Eleven: hazards cost more, and so do cells inside an enemy's hit zone."""
    zone = hit_zone(state)
    board = state.board

    def cost(p: Pos) -> float:
        c = config.ASTAR_HAZARD_COST if board.terrain_at(p) == Terrain.HAZARD else 1
        return c + (config.DANGER_STEP_COST if p in zone else 0)
    return cost


def table_step(state, target: Pos) -> Action:
    """Fast stand-in for A* used only INSIDE simulations: step to the neighbour with the smallest
    static walking distance to the target (hazards and enemy hit zones count extra, like Eleven's A* step costs).
    On this map it takes the same number of steps as A* (the distance table is checked against A* in the tests)."""
    here = walk_distance(state.board, state.eleven_pos, target)
    zone = hit_zone(state)
    best, best_cost = Action.WAIT, float("inf")
    for a, (dx, dy) in MOVE_DELTAS.items():
        n = (state.eleven_pos[0] + dx, state.eleven_pos[1] + dy)
        if not can_eleven_enter(state, n):
            continue
        d = walk_distance(state.board, n, target)
        if d >= UNREACHABLE:
            continue
        cost = d + (config.ASTAR_HAZARD_COST - 1 if state.board.terrain_at(n) == Terrain.HAZARD else 0)
        cost += config.DANGER_STEP_COST if n in zone else 0
        if d < here and cost < best_cost:
            best, best_cost = a, cost
    return best