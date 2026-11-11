"""The Mind Flayer's brain: Monte Carlo Tree Search over map actions (corrupt a cell, summon a
creature, wait). It knows where Eleven is (it has no body, it sees the whole map).

    Selection     UCB1 with config.MCTS_EXPLORATION
    Expansion     one untried Mind Flayer action, applied to a CLONE of the parent's state
    Simulation    random Mind Flayer actions until MF_HORIZON turns have been simulated
    Backprop      reward-to-go from each node's own edge, scaled by MCTS_REWARD_SCALE

Each tree edge is one Mind Flayer action followed by one simulated turn: upkeep, then Eleven and the
enemies move. Eleven is modelled by a stand-in policy (the same idea as in ai/sim.py): final attack
if possible, rescue if in range, otherwise one step toward her objective (nearest unrescued friend,
then the open portal, then the nearest Demogorgon to farm power) along walking distances that respect
corrupted cells. Demogorgons and Vecna use ai/sim.enemy_phase.

Rewards come from config.MIND_FLAYER_REWARDS:
    KILL_ELEVEN      Eleven reaches 0 HP                    DAMAGE_ELEVEN   per HP she loses
    BLOCK_ROUTE      the corrupted cell lies on her route   TRAP_ELEVEN     she can enter <= 1 neighbour cell
    FORCE_AWAY       her walking distance to the objective grew
    ELEVEN_ESCAPES   she wins                               DEFEATED        her final attack beats the Mind Flayer

Candidate actions are limited so the tree stays small: corrupt the first cells of her route or a cell
next to her, summon a creature 2-4 steps from her, or wait. The live state is only read."""
from __future__ import annotations
import math
import random
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import config
from ai.distance_table import UNREACHABLE, distance_table, walk_distance
from ai.goals import nearest_demogorgon
from ai.metrics import Metrics
from ai.sim import enemy_phase, upkeep
from characters import friends as friend_rules
from characters import mind_flayer as mf_rules
from game.actions import Action, MOVE_DELTAS
from game.board import Pos, Terrain
from game.mind_flayer_rules import (CORRUPT, SPAWN, WAIT, MFAction, apply_mf_action, can_corrupt,
                                    can_spawn, is_acting)
from game.rules import apply_eleven_action, can_attack, can_eleven_enter, check_win_loss
from game.state import GameState, Winner

R = config.MIND_FLAYER_REWARDS


# ---------------------------------------------------------------- the stand-in Eleven
@dataclass
class Plan:
    """Where the modelled Eleven is heading and the walking distance from every cell to it."""
    target: Optional[Pos]
    dist: Dict[Pos, int]
    sig: Tuple = ()

    def distance_from(self, cell: Pos) -> Optional[int]:
        return self.dist.get(cell) if self.target is not None else None


def _signature(state: GameState) -> Tuple:
    return (frozenset(state.corrupted), len(state.rescued), state.portal_active, state.mind_flayer.defeated)


def model_target(state: GameState) -> Optional[Pos]:
    friends = [p for n, p in state.friend_positions.items() if n not in state.rescued]
    if friends:
        return min(friends, key=lambda p: (walk_distance(state.board, state.eleven_pos, p), p))
    if state.portal_active:
        return state.portal_pos
    mf = state.mind_flayer
    if mf.active and not mf.defeated:
        d = nearest_demogorgon(state)
        if d is not None:
            return d.pos
    return None


def _bfs_map(state: GameState, target: Pos) -> Dict[Pos, int]:
    """Walking distances to `target` over cells that are not walls or corrupted (characters ignored)."""
    dist = {target: 0}
    q = deque([target])
    while q:
        cur = q.popleft()
        for n in state.board.neighbors4(cur):
            if n not in dist and n not in state.corrupted:
                dist[n] = dist[cur] + 1
                q.append(n)
    return dist


def make_plan(state: GameState) -> Plan:
    target = model_target(state)
    if target is None:
        return Plan(None, {}, _signature(state))
    dist = _bfs_map(state, target) if state.corrupted else distance_table(state.board).get(target, {})
    return Plan(target, dist, _signature(state))


def ensure_plan(state: GameState, plan: Plan) -> Plan:
    """Reuse a plan while corruption, rescues and the portal are unchanged (distances depend only on those)."""
    return plan if plan.sig == _signature(state) else make_plan(state)


def model_eleven_action(state: GameState, plan: Plan) -> Action:
    if mf_rules.can_final_attack(state):
        return Action.FINAL_ATTACK
    if friend_rules.rescuable_friends(state):
        return Action.RESCUE
    if plan.target is None:
        return Action.WAIT
    unrescued = len(state.rescued) < len(state.friend_positions)
    if not unrescued and not state.portal_active and can_attack(state):
        return Action.ATTACK
    here = plan.dist.get(state.eleven_pos)
    if here is None:
        return Action.WAIT
    best, best_key = Action.WAIT, None
    for a, (dx, dy) in MOVE_DELTAS.items():
        n = (state.eleven_pos[0] + dx, state.eleven_pos[1] + dy)
        d = plan.dist.get(n)
        if d is None or d >= here or not can_eleven_enter(state, n):
            continue
        key = (d, state.board.terrain_at(n) == Terrain.HAZARD)
        if best_key is None or key < best_key:
            best, best_key = a, key
    return best


def route_cells(state: GameState, plan: Plan, length: int) -> List[Pos]:
    """The first `length` cells of Eleven's expected shortest route to her objective."""
    cells: List[Pos] = []
    cur = state.eleven_pos
    d = plan.distance_from(cur)
    while d is not None and d > 0 and len(cells) < length:
        nxt = None
        for dx, dy in MOVE_DELTAS.values():
            n = (cur[0] + dx, cur[1] + dy)
            dn = plan.dist.get(n)
            if dn is not None and dn < d:
                nxt = n
                break
        if nxt is None:
            break
        cells.append(nxt)
        cur, d = nxt, plan.dist[nxt]
    return cells


def free_neighbour_count(state: GameState) -> int:
    return sum(1 for n in state.board.neighbors4(state.eleven_pos) if can_eleven_enter(state, n))


# ---------------------------------------------------------------- candidate actions
def candidate_actions(state: GameState, plan: Plan) -> List[MFAction]:
    """Corrupt the first cells of her route or a cell beside her, summon 2-4 steps away, or wait.
    Every returned action is legal; the order is fixed so searches are deterministic."""
    cells: List[Pos] = []
    for c in route_cells(state, plan, config.MF_ROUTE_LOOKAHEAD):
        if can_corrupt(state, c) and c not in cells:
            cells.append(c)
    for n in state.board.neighbors4(state.eleven_pos):
        if can_corrupt(state, n) and n not in cells:
            cells.append(n)
    actions = [MFAction(CORRUPT, c) for c in cells[:config.MF_MAX_CORRUPT_CANDIDATES]]
    if state.mind_flayer.spawn_cooldown == 0:
        near = distance_table(state.board).get(state.eleven_pos, {})
        spots = sorted((d, c) for c, d in near.items()
                       if config.MF_SPAWN_MIN_DISTANCE <= d <= config.MF_SPAWN_MAX_DISTANCE and can_spawn(state, c))
        actions += [MFAction(SPAWN, c) for _, c in spots[:config.MF_SPAWN_CANDIDATES]]
    actions.append(MFAction(WAIT))
    return actions


# ---------------------------------------------------------------- one simulated step
def mf_step(state: GameState, action: MFAction, plan: Plan) -> Tuple[float, Plan]:
    """Apply `action` on `state` (a CLONE), then simulate the rest of the turn: upkeep, Eleven's
    modelled move, enemy moves. Returns (unscaled reward, plan for the new state)."""
    hp0 = state.eleven_hp
    defeated0 = state.mind_flayer.defeated
    d0 = plan.distance_from(state.eleven_pos)
    reward = 0.0
    if action.kind == CORRUPT and action.cell in route_cells(state, plan, config.MF_ROUTE_LOOKAHEAD):
        reward += R["BLOCK_ROUTE"]
    apply_mf_action(state, action)
    upkeep(state)
    check_win_loss(state)
    if not state.game_over:
        state.turn += 1
        plan = ensure_plan(state, plan)
        apply_eleven_action(state, model_eleven_action(state, plan))
        if state.eleven_hp > 0:
            enemy_phase(state)
        check_win_loss(state)
    plan = ensure_plan(state, plan)
    reward += R["DAMAGE_ELEVEN"] * max(0, hp0 - state.eleven_hp)
    if state.eleven_hp <= 0:
        reward += R["KILL_ELEVEN"]
    elif state.winner == Winner.ELEVEN:
        reward += R["ELEVEN_ESCAPES"]
    elif state.mind_flayer.defeated and not defeated0:
        reward += R["DEFEATED"]
    if not state.game_over:
        if free_neighbour_count(state) <= config.MF_TRAP_FREE_NEIGHBOURS:
            reward += R["TRAP_ELEVEN"]
        d1 = plan.distance_from(state.eleven_pos)
        if d0 is not None and d1 is not None and d1 > d0:
            reward += R["FORCE_AWAY"]
    return reward, plan


# ---------------------------------------------------------------- MCTS
@dataclass
class MFResult:
    action: MFAction
    value: float
    visits: int
    simulations: int
    nodes_created: int
    max_depth: int
    simulated_turns: int
    time_ms: float
    root: List[Tuple[str, int, float]] = field(default_factory=list)   # (action label, visits, mean value)

    @property
    def label(self) -> str:
        return self.action.label


class _Node:
    __slots__ = ("state", "plan", "action", "parent", "children", "untried", "visits", "total",
                 "edge_reward", "turns", "depth")

    def __init__(self, state: GameState, plan: Plan, action: Optional[MFAction], parent: Optional["_Node"],
                 edge_reward: float, turns: int, depth: int):
        self.state, self.plan, self.action, self.parent = state, plan, action, parent
        self.children: List["_Node"] = []
        self.untried: List[MFAction] = [] if self.is_terminal() else candidate_actions(state, plan)
        self.visits, self.total = 0, 0.0
        self.edge_reward, self.turns, self.depth = edge_reward, turns, depth

    def is_terminal(self) -> bool:
        return not is_acting(self.state)

    def is_leaf_for_search(self) -> bool:
        return self.is_terminal() or self.turns >= config.MF_HORIZON


def _ucb_child(node: _Node) -> _Node:
    log_n = math.log(node.visits)
    return max(node.children,
               key=lambda c: c.total / c.visits + config.MCTS_EXPLORATION * math.sqrt(log_n / c.visits))


def _rollout(state: GameState, plan: Plan, turns_used: int, rng: random.Random) -> Tuple[float, int]:
    reward, turns = 0.0, 0
    while turns_used + turns < config.MF_HORIZON and is_acting(state):
        action = rng.choice(candidate_actions(state, plan))
        r, plan = mf_step(state, action, plan)
        reward += r
        turns += 1
    return reward, turns


def mf_search(state: GameState, simulations: Optional[int] = None, seed: Optional[int] = None) -> MFResult:
    """Choose the Mind Flayer's action for this turn. `state` is only read."""
    sims = config.MINDFLAYER_MCTS_SIMULATIONS if simulations is None else simulations
    rng = random.Random(config.RNG_SEED + 7919 + state.turn if seed is None else seed)
    scale = config.MCTS_REWARD_SCALE
    t0 = time.perf_counter()
    root_state = state.clone()
    root = _Node(root_state, make_plan(root_state), None, None, 0.0, 0, 0)
    nodes, max_depth, sim_turns = 1, 0, 0

    for _ in range(sims):
        node = root
        while not node.untried and node.children and not node.is_leaf_for_search():
            node = _ucb_child(node)
        if node.untried and not node.is_leaf_for_search():
            action = node.untried.pop(rng.randrange(len(node.untried)))
            child_state = node.state.clone()
            reward, child_plan = mf_step(child_state, action, node.plan)
            child = _Node(child_state, child_plan, action, node, reward, node.turns + 1, node.depth + 1)
            node.children.append(child)
            node = child
            nodes += 1
            sim_turns += 1
            max_depth = max(max_depth, node.depth)
        leaf_state = node.state.clone()
        roll_reward, roll_turns = _rollout(leaf_state, node.plan, node.turns, rng)
        sim_turns += roll_turns
        path: List[_Node] = []
        n = node
        while n is not None:
            path.append(n)
            n = n.parent
        path.reverse()
        togo = roll_reward
        for n in reversed(path[1:]):
            togo += n.edge_reward
            n.visits += 1
            n.total += togo / scale
        root.visits += 1

    if not root.children:
        return MFResult(MFAction(WAIT), 0.0, 0, sims, nodes, 0, sim_turns, (time.perf_counter() - t0) * 1000.0)
    best = max(root.children, key=lambda c: (c.visits, c.total / c.visits))
    summary = sorted(((c.action.label, c.visits, c.total / c.visits) for c in root.children), key=lambda t: -t[1])
    return MFResult(best.action, best.total / best.visits, best.visits, sims, nodes, max_depth, sim_turns,
                    (time.perf_counter() - t0) * 1000.0, summary)


class MindFlayerAI:
    """Controller used by the TurnManager: runs the search and records its real statistics."""

    def __init__(self, metrics: Optional[Metrics] = None, simulations: Optional[int] = None):
        self.metrics = metrics or Metrics()
        self.simulations = simulations
        self.last_result: Optional[MFResult] = None

    def choose_action(self, state: GameState) -> MFAction:
        result = mf_search(state, self.simulations)
        self.metrics.record_mcts("mind_flayer", result)
        self.last_result = result
        return result.action