"""Phase 5: Vecna's Minimax + Alpha-Beta, evaluation bounds, real statistics, TurnManager wiring."""
import math
import random

import pytest

import config
from abilities import teleport
from ai.astar import astar_search
from ai.distance_table import UNREACHABLE, walk_distance
from ai.evaluation import NON_TERMINAL_LIMIT, evaluate_for_vecna, terminal_value
from ai.minimax import ELEVEN_MODELLED, minimax_search
from ai.vecna_ai import VecnaAI
from characters.demogorgon import Demogorgon
from game.actions import Action, MOVE_DELTAS
from game.rules import apply_eleven_action, legal_eleven_actions
from game.state import GameState, Winner
from game.turn_manager import TurnManager
from game.vecna_rules import apply_vecna_action, can_vecna_attack, legal_vecna_actions


def fresh(kill_demogorgons=True):
    s = GameState.new_game()
    if kill_demogorgons:
        for d in s.demogorgons:
            d.alive = False
    return s, TurnManager(s)


def free_cells(s):
    return [(x, y) for y in range(s.board.height) for x in range(s.board.width)
            if s.board.is_walkable((x, y)) and (x, y) not in s.enemy_positions() and (x, y) != s.eleven_pos]


def random_state(rng):
    """A mid-game-looking position: Eleven wandered a little, Vecna dropped on a random free cell."""
    s = GameState.new_game()
    for _ in range(rng.randint(0, 12)):
        apply_eleven_action(s, rng.choice(legal_eleven_actions(s)))
    s.eleven_hp = rng.randint(1, config.MAX_HP)
    s.vecna.pos = rng.choice(free_cells(s))
    return s


def brute_force_value(s, depth, maximizing):
    """Plain recursive minimax written independently of ai.minimax (no pruning, no ordering)."""
    tv = terminal_value(s)
    if tv is not None:
        return tv
    if depth == 0:
        return evaluate_for_vecna(s)
    if maximizing:
        vals = []
        for a in legal_vecna_actions(s):
            c = s.clone()
            apply_vecna_action(c, a)
            vals.append(brute_force_value(c, depth - 1, False))
        return max(vals)
    vals = []
    for a in [x for x in legal_eleven_actions(s) if x in ELEVEN_MODELLED]:
        c = s.clone()
        apply_eleven_action(c, a)
        vals.append(brute_force_value(c, depth - 1, True))
    return min(vals) if vals else evaluate_for_vecna(s)


def snapshot(s):
    return (s.eleven_pos, s.eleven_hp, s.eleven_power, s.turn, s.vecna.pos, s.vecna.frozen_turns,
            [(d.id, d.pos, d.alive, d.cooldown) for d in s.demogorgons], set(s.rescued),
            set(s.visited), dict(s.status_effects), dict(s.ability_uses), len(s.event_log),
            dict(s.corrupted), s.winner)


# ------------------------------------------------------------------ correctness of the search
@pytest.mark.parametrize("seed", range(8))
def test_search_value_matches_brute_force_minimax(seed):
    s = random_state(random.Random(seed))
    for ab in (True, False):
        r = minimax_search(s, depth=3, use_alpha_beta=ab)
        assert r.score == brute_force_value(s, 3, True)


def test_alpha_beta_matches_plain_minimax_and_prunes():
    rng = random.Random(11)
    ab_eval = plain_eval = ab_pruned = plain_pruned = 0
    for _ in range(40):
        s = random_state(rng)
        a = minimax_search(s, 4, True)
        p = minimax_search(s, 4, False)
        assert (a.action, a.score) == (p.action, p.score)       # pruning never changes the answer
        assert a.nodes_evaluated <= p.nodes_evaluated
        ab_eval += a.nodes_evaluated
        plain_eval += p.nodes_evaluated
        ab_pruned += a.branches_pruned
        plain_pruned += p.branches_pruned
    assert plain_pruned == 0
    assert ab_pruned > 0 and ab_eval < plain_eval


def test_default_depth_is_the_configured_depth():
    s, _ = fresh()
    r = minimax_search(s)
    assert r.depth == config.MINIMAX_DEPTH == 4
    assert r.alpha_beta == config.VECNA_USE_ALPHA_BETA


def test_depth_one_is_a_one_move_lookahead():
    s, _ = fresh()
    s.vecna.pos, s.eleven_pos = (3, 3), (1, 3)
    r = minimax_search(s, depth=1)
    best = -math.inf
    for a in legal_vecna_actions(s):
        c = s.clone()
        apply_vecna_action(c, a)
        tv = terminal_value(c)
        best = max(best, tv if tv is not None else evaluate_for_vecna(c))
    assert r.score == best


def test_search_is_deterministic():
    s = random_state(random.Random(3))
    a, b = minimax_search(s), minimax_search(s)
    assert (a.action, a.score, a.nodes_visited, a.nodes_evaluated, a.branches_pruned) == \
           (b.action, b.score, b.nodes_visited, b.nodes_evaluated, b.branches_pruned)


def test_search_never_mutates_the_live_state():
    s = random_state(random.Random(4))
    before = snapshot(s)
    minimax_search(s)
    assert snapshot(s) == before


# ------------------------------------------------------------------ behaviour
def test_vecna_takes_a_kill_when_eleven_is_in_reach():
    s, _ = fresh()
    s.eleven_pos, s.vecna.pos = (1, 1), (1, 2)
    s.eleven_hp = config.VECNA_DAMAGE
    r = minimax_search(s)
    assert r.action == Action.ATTACK
    assert r.score == -config.UTILITY_LOSS                       # +50: Eleven's loss is Vecna's win


def test_vecna_hits_an_adjacent_eleven_in_a_real_turn():
    s, tm = fresh()
    s.eleven_pos, s.vecna.pos = (1, 1), (1, 2)
    assert tm.step(Action.WAIT)
    assert s.eleven_hp == config.MAX_HP - config.VECNA_DAMAGE
    assert tm.vecna_ai.last_result.action == Action.ATTACK


def test_vecna_closes_the_distance():
    s, _ = fresh()                                               # Vecna (1,13), Eleven (1,1)
    before = walk_distance(s.board, s.vecna.pos, s.eleven_pos)
    r = minimax_search(s)
    c = s.clone()
    apply_vecna_action(c, r.action)
    assert walk_distance(c.board, c.vecna.pos, c.eleven_pos) < before


def test_eleven_cannot_attack_vecna():
    s, _ = fresh()
    s.eleven_pos, s.vecna.pos = (1, 1), (1, 2)
    s.eleven_power = 5
    assert Action.ATTACK not in legal_eleven_actions(s)


def test_frozen_vecna_does_not_search_move_or_hit():
    s, tm = fresh()
    s.eleven_pos, s.vecna.pos = (1, 1), (1, 2)
    s.vecna.frozen_turns = 2
    assert legal_vecna_actions(s) == [Action.WAIT] and not can_vecna_attack(s)
    tm.step(Action.WAIT)
    assert s.eleven_hp == config.MAX_HP and s.vecna.pos == (1, 2)
    assert tm.metrics.minimax.calls == 0


def test_vecna_actions_respect_collisions_and_walls():
    rng = random.Random(8)
    for _ in range(30):
        s = random_state(rng)
        for a in legal_vecna_actions(s):
            if a in MOVE_DELTAS:
                dx, dy = MOVE_DELTAS[a]
                dest = (s.vecna.pos[0] + dx, s.vecna.pos[1] + dy)
                assert s.board.is_walkable(dest) and dest != s.eleven_pos
                assert dest not in s.enemy_positions()


def test_attack_requires_range():
    s, _ = fresh()
    s.eleven_pos, s.vecna.pos = (1, 1), (4, 1)
    assert Action.ATTACK not in legal_vecna_actions(s)
    s.vecna.pos = (1, 2)
    assert Action.ATTACK in legal_vecna_actions(s)


# ------------------------------------------------------------------ evaluation
def test_terminal_values_are_exactly_plus_minus_fifty():
    s, _ = fresh()
    assert terminal_value(s) is None
    s.eleven_hp = 0
    assert terminal_value(s) == 50
    s2, _ = fresh()
    s2.rescued.update(s2.friend_positions)
    s2.mind_flayer.defeated = True
    s2.eleven_pos = s2.portal_pos
    assert terminal_value(s2) == -50


def test_non_terminal_evaluation_stays_within_49():
    rng = random.Random(21)
    for _ in range(300):
        s = random_state(rng)
        if rng.random() < 0.5:
            s.rescued = set(rng.sample(sorted(s.friend_positions), rng.randint(0, 4)))
        s.portal_active = rng.random() < 0.5
        if terminal_value(s) is None:
            assert abs(evaluate_for_vecna(s)) <= NON_TERMINAL_LIMIT == 49


def test_evaluation_prefers_what_a_vecna_would_want():
    s, _ = fresh()
    s.vecna.pos, s.eleven_pos = (1, 13), (1, 1)
    base = evaluate_for_vecna(s)
    hurt = s.clone(); hurt.eleven_hp -= 1
    assert evaluate_for_vecna(hurt) > base                       # less Eleven HP
    close = s.clone(); close.vecna.pos = (1, 2)
    assert evaluate_for_vecna(close) > base                      # Vecna nearer Eleven
    helped = s.clone(); helped.rescued.add("Dustin")
    assert evaluate_for_vecna(helped) < base                     # Eleven made progress
    near_portal = s.clone(); near_portal.portal_active = True
    far = evaluate_for_vecna(near_portal)
    near_portal.eleven_pos = (11, 13)
    assert evaluate_for_vecna(near_portal) < far                 # open portal within reach is bad for Vecna


def test_distance_table_matches_astar_and_is_symmetric():
    s, _ = fresh()
    rng = random.Random(2)
    cells = free_cells(s)
    for _ in range(40):
        a, b = rng.choice(cells), rng.choice(cells)
        res = astar_search(s.board, a, b)
        assert walk_distance(s.board, a, b) == (res.path_length if a != b else 0)
        assert walk_distance(s.board, a, b) == walk_distance(s.board, b, a)
    assert walk_distance(s.board, (0, 0), (1, 1)) == UNREACHABLE        # wall cell


# ------------------------------------------------------------------ statistics are real
def test_recorded_statistics_come_from_the_real_search():
    s, tm = fresh()
    before = s.clone()                                           # Eleven waits, so Vecna sees this state
    tm.step(Action.WAIT)
    m = tm.metrics.minimax
    ref = minimax_search(before)
    assert m.calls == 1 and m.last is not None
    assert (m.last.action, m.last.score, m.last.depth) == (ref.action, ref.score, ref.depth)
    assert (m.nodes_visited, m.nodes_evaluated, m.branches_pruned) == \
           (ref.nodes_visited, ref.nodes_evaluated, ref.branches_pruned)
    assert m.nodes_evaluated > 0 and m.total_time_ms > 0


def test_statistics_accumulate_over_turns_and_one_search_per_vecna_turn():
    s, tm = fresh()
    for _ in range(4):
        tm.step(Action.WAIT)
    m = tm.metrics.minimax
    assert m.calls == 4
    assert m.nodes_evaluated >= 4 and m.nodes_visited >= m.nodes_evaluated


def test_vecna_ai_records_into_its_metrics():
    s, _ = fresh()
    ai = VecnaAI()
    action = ai.choose_action(s)
    assert action == ai.last_result.action
    assert ai.metrics.minimax.calls == 1


def test_plain_minimax_mode_prunes_nothing():
    s, _ = fresh()
    ai = VecnaAI(depth=4, use_alpha_beta=False)
    ai.choose_action(s)
    assert ai.last_result.branches_pruned == 0 and not ai.last_result.alpha_beta


# ------------------------------------------------------------------ full games
@pytest.mark.parametrize("seed", [4, 5, 6])
def test_random_games_with_vecna_keep_invariants(seed):
    rng = random.Random(seed)
    s = GameState.new_game()
    tm = TurnManager(s)
    while not s.game_over:
        action = rng.choice(legal_eleven_actions(s))
        assert tm.step(action, target=teleport.best_safe_cell(s) if action == Action.USE_TELEPORT else None)        
        assert s.board.is_walkable(s.vecna.pos)
        cells = [d.pos for d in s.living_demogorgons()] + [s.vecna.pos, s.eleven_pos]
        assert len(cells) == len(set(cells)), "two characters share a cell"
        assert 0 <= s.eleven_hp <= config.MAX_HP
        assert s.turn <= config.MAX_TURNS
    assert s.winner in (Winner.ENEMIES, Winner.ELEVEN)
    assert tm.metrics.minimax.calls > 0