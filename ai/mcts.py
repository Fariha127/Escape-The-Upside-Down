"""Monte Carlo Tree Search for Eleven. It chooses a STRATEGIC GOAL (rescue Mike, evade, hunt, ...);
A* then walks to it (ai/eleven_ai.py).

    Selection     UCB1:  Q/N + c * sqrt(ln(N_parent) / N)      c = config.MCTS_EXPLORATION (1.41)
    Expansion     one untried goal, executed on a CLONE of the parent's state
    Simulation    random goals until MCTS_ROLLOUT_DEPTH simulated turns have passed (or the game ends)
    Backprop      every node on the path receives the reward-to-go from its own edge onward

DESIGN DECISIONS (documented for the README)
  * One tree edge = one goal executed for up to MCTS_GOAL_TURNS turns (ai/sim.run_goal).
  * Rewards are divided by MCTS_REWARD_SCALE so Q stays near 1 and UCB1's constant keeps its meaning.
  * The simulation is deterministic except for the random rollout goals, which come from a
    random.Random seeded by the caller, so the same position and seed always give the same result.
  * The live state is only read; every simulated move happens on clones.
  * Counters are real: simulations, nodes created, deepest tree level, simulated turns, time."""
from __future__ import annotations
import math
import random
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import config
from ai.goals import Goal, GoalRun, applicable_goals
from ai.sim import run_goal
from game.state import GameState


@dataclass
class MCTSResult:
    goal: Goal                                   # selected goal (most visited root child)
    value: float                                 # its mean reward (scaled)
    visits: int                                  # its visit count
    simulations: int
    nodes_created: int
    max_depth: int                               # deepest tree level reached (root = 0)
    simulated_turns: int                         # all game turns simulated (tree edges + rollouts)
    time_ms: float
    root: List[Tuple[str, int, float]] = field(default_factory=list)   # (goal label, visits, mean value)


class _Node:
    __slots__ = ("state", "goal", "parent", "children", "untried", "visits", "total",
                 "edge_reward", "turns", "depth")

    def __init__(self, state: GameState, goal: Optional[Goal], parent: Optional["_Node"],
                 edge_reward: float, turns: int, depth: int):
        self.state, self.goal, self.parent = state, goal, parent
        self.children: List["_Node"] = []
        self.untried: List[Goal] = applicable_goals(state)
        self.visits, self.total = 0, 0.0
        self.edge_reward, self.turns, self.depth = edge_reward, turns, depth

    def is_leaf_for_search(self) -> bool:
        return self.state.game_over or self.turns >= config.MCTS_ROLLOUT_DEPTH


def _ucb_child(node: _Node) -> _Node:
    log_n = math.log(node.visits)
    return max(node.children,
               key=lambda c: c.total / c.visits + config.MCTS_EXPLORATION * math.sqrt(log_n / c.visits))


def _rollout(state: GameState, turns_used: int, rng: random.Random) -> Tuple[float, int]:
    """Random goals until the turn budget is spent. Returns (unscaled reward, turns simulated)."""
    reward, turns = 0.0, 0
    while turns_used + turns < config.MCTS_ROLLOUT_DEPTH and not state.game_over:
        goals = applicable_goals(state)
        if not goals:
            break
        run = GoalRun(rng.choice(goals), state)
        budget = min(config.MCTS_GOAL_TURNS, config.MCTS_ROLLOUT_DEPTH - turns_used - turns)
        r, t = run_goal(state, run, budget)
        reward += r
        turns += t
    return reward, turns


def mcts_search(state: GameState, simulations: Optional[int] = None, seed: Optional[int] = None) -> MCTSResult:
    """Choose Eleven's next goal. `state` is only read."""
    sims = config.ELEVEN_MCTS_SIMULATIONS if simulations is None else simulations
    rng = random.Random(config.RNG_SEED + state.turn if seed is None else seed)
    scale = config.MCTS_REWARD_SCALE
    t0 = time.perf_counter()
    root = _Node(state.clone(), None, None, 0.0, 0, 0)
    nodes, max_depth, sim_turns = 1, 0, 0

    for _ in range(sims):
        node = root
        # 1. selection
        while not node.untried and node.children and not node.is_leaf_for_search():
            node = _ucb_child(node)
        # 2. expansion
        if node.untried and not node.is_leaf_for_search():
            goal = node.untried.pop(rng.randrange(len(node.untried)))
            child_state = node.state.clone()
            reward, turns = run_goal(child_state, GoalRun(goal, child_state), config.MCTS_GOAL_TURNS)
            child = _Node(child_state, goal, node, reward, node.turns + turns, node.depth + 1)
            node.children.append(child)
            node = child
            nodes += 1
            sim_turns += turns
            max_depth = max(max_depth, node.depth)
        # 3. simulation (random goals from the new leaf)
        leaf_state = node.state.clone()
        roll_reward, roll_turns = _rollout(leaf_state, node.turns, rng)
        sim_turns += roll_turns
        # 4. backpropagation of reward-to-go
        path: List[_Node] = []
        n = node
        while n is not None:
            path.append(n)
            n = n.parent
        path.reverse()                                   # root ... leaf
        togo = roll_reward
        for n in reversed(path[1:]):
            togo += n.edge_reward
            n.visits += 1
            n.total += togo / scale
        root.visits += 1

    if not root.children:                                # no goal could be tried (should not happen)
        raise RuntimeError("MCTS found no applicable goal")
    best = max(root.children, key=lambda c: (c.visits, c.total / c.visits))
    summary = sorted(((c.goal.label, c.visits, c.total / c.visits) for c in root.children),
                     key=lambda t: -t[1])
    return MCTSResult(best.goal, best.total / best.visits, best.visits, sims, nodes, max_depth,
                      sim_turns, (time.perf_counter() - t0) * 1000.0, summary)