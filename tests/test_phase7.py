"""Phase 7: Mind Flayer rules (corrupt / summon), its MCTS, turn wiring, final battle."""
import random

import pytest

import config
import main as game_main
from ai.astar import find_path
from ai.eleven_ai import ElevenAI
from ai.distance_table import walk_distance
from ai.metrics import Metrics
from ai.mind_flayer_ai import (MindFlayerAI, candidate_actions, free_neighbour_count, make_plan, mf_search,
                               mf_step, model_eleven_action, route_cells)
from ai.sim import upkeep
from characters.mind_flayer import MindFlayer
from game.actions import Action
from game.mind_flayer_rules import (CORRUPT, SPAWN, WAIT, MFAction, apply_mf_action, can_corrupt, can_spawn,
                                    is_acting)
from game.rules import apply_eleven_action, can_eleven_enter, can_enemy_enter, legal_eleven_actions
from game.state import GameState, Winner
from game.turn_manager import TurnManager

R = config.MIND_FLAYER_REWARDS


def awake(kill_demogorgons=True, freeze_vecna=True):
    """A game where Will is rescued, the Mind Flayer is awake and (by default) the old enemies are out."""
    s = GameState.new_game()
    if kill_demogorgons:
        for d in s.demogorgons:
            d.alive = False
    if freeze_vecna:
        s.vecna.frozen_turns = 10 ** 6
    s.rescued.add("Will")
    s.unlocked_abilities.add("FREEZE")
    s.ability_uses["FREEZE"] = config.ABILITY_USES["FREEZE"]
    s.mind_flayer.active = True
    return s


class Scripted:
    """Mind Flayer controller that plays a fixed list of actions, then waits."""
    def __init__(self, *actions):
        self.actions = list(actions)

    def choose_action(self, state):
        return self.actions.pop(0) if self.actions else MFAction(WAIT)


def snap(s):
    return (s.eleven_pos, s.eleven_hp, s.eleven_power, s.turn, s.vecna.pos, s.vecna.frozen_turns,
            [(d.id, d.pos, d.alive, d.temporary, d.cooldown, d.frozen_turns) for d in s.demogorgons],
            set(s.rescued), dict(s.status_effects), dict(s.corrupted), len(s.event_log), s.winner,
            s.portal_active, s.mind_flayer.active, s.mind_flayer.defeated, s.mind_flayer.spawn_cooldown)


# ------------------------------------------------------------------ the character
def test_mind_flayer_clone_copies_the_spawn_cooldown():
    mf = MindFlayer(active=True, spawn_cooldown=3)
    c = mf.clone()
    assert c.spawn_cooldown == 3 and c.active
    c.spawn_cooldown = 0
    assert mf.spawn_cooldown == 3


# ------------------------------------------------------------------ corrupt rules
def test_only_an_awake_mind_flayer_can_act():
    s = awake()
    assert is_acting(s) and can_corrupt(s, (2, 1))
    s.mind_flayer.active = False
    assert not is_acting(s) and not can_corrupt(s, (2, 1)) and not apply_mf_action(s, MFAction(WAIT))
    s.mind_flayer.active, s.mind_flayer.defeated = True, True
    assert not is_acting(s) and not apply_mf_action(s, MFAction(CORRUPT, (2, 1)))
    s2 = awake()
    s2.winner = Winner.ENEMIES
    assert not is_acting(s2)


def test_corrupt_restrictions():
    s = awake(kill_demogorgons=False)
    assert not can_corrupt(s, s.eleven_pos)                     # Eleven's cell
    assert not can_corrupt(s, s.vecna.pos)                      # Vecna's cell
    assert not can_corrupt(s, s.demogorgons[0].pos)             # a Demogorgon's cell
    assert not can_corrupt(s, s.portal_pos)                     # never the portal
    assert not can_corrupt(s, (0, 0))                           # wall
    assert can_corrupt(s, (2, 1))
    assert apply_mf_action(s, MFAction(CORRUPT, (2, 1)))
    assert not can_corrupt(s, (2, 1))                           # already corrupted
    for c in [(3, 1), (4, 1), (1, 2)]:
        apply_mf_action(s, MFAction(CORRUPT, c))
    assert len(s.corrupted) == config.MF_MAX_CORRUPTED
    assert not can_corrupt(s, (1, 3))                           # cap reached


def test_corrupt_blocks_everyone_and_astar():
    s = awake(kill_demogorgons=False)
    cell = (2, 1)
    assert can_eleven_enter(s, cell) and can_enemy_enter(s, cell)
    assert apply_mf_action(s, MFAction(CORRUPT, cell))
    assert s.corrupted[cell] == config.MF_CORRUPT_DURATION + 1
    assert not can_eleven_enter(s, cell) and not can_enemy_enter(s, cell)
    res = find_path(s, s.eleven_pos, (4, 1))
    assert cell not in res.path
    assert any("corrupts" in e for e in s.event_log)


def test_corruption_lasts_exactly_the_configured_number_of_turns():
    s = awake()
    tm = TurnManager(s, mind_flayer_ai=Scripted(MFAction(CORRUPT, (2, 1))))
    cell = (2, 1)
    tm.step(Action.WAIT)
    blocked_turns = 0
    while cell in s.corrupted:
        assert not can_eleven_enter(s, cell)             # still blocked when Eleven acts next
        blocked_turns += 1
        tm.step(Action.WAIT)
    assert blocked_turns == config.MF_CORRUPT_DURATION
    assert can_eleven_enter(s, cell)


def test_illegal_mind_flayer_actions_change_nothing():
    s = awake()
    before = snap(s)
    assert not apply_mf_action(s, MFAction(CORRUPT, s.eleven_pos))
    assert not apply_mf_action(s, MFAction(CORRUPT, None))
    assert not apply_mf_action(s, MFAction(SPAWN, (0, 0)))
    assert not apply_mf_action(s, MFAction("DANCE", (2, 1)))
    assert snap(s) == before


# ------------------------------------------------------------------ summon rules
def test_spawn_creates_a_temporary_creature_and_starts_the_cooldown():
    s = awake()
    assert can_spawn(s, (4, 1))
    assert apply_mf_action(s, MFAction(SPAWN, (4, 1)))
    temps = [d for d in s.demogorgons if d.alive and d.temporary]
    assert len(temps) == 1 and temps[0].pos == (4, 1)
    assert s.mind_flayer.spawn_cooldown == config.MF_SPAWN_COOLDOWN + 1
    assert not can_spawn(s, (3, 1))                             # cooldown
    assert any("summons" in e for e in s.event_log)


def test_spawn_cooldown_ticks_down_in_the_real_turn_and_in_simulations():
    s = awake()
    tm = TurnManager(s, mind_flayer_ai=Scripted(MFAction(SPAWN, (4, 1))))
    tm.step(Action.WAIT)
    assert s.mind_flayer.spawn_cooldown == config.MF_SPAWN_COOLDOWN
    for _ in range(config.MF_SPAWN_COOLDOWN):
        tm.step(Action.WAIT)
    assert s.mind_flayer.spawn_cooldown == 0
    sim = awake()
    sim.mind_flayer.spawn_cooldown = 3
    upkeep(sim)
    assert sim.mind_flayer.spawn_cooldown == 2


def test_spawn_respects_the_creature_cap_and_free_cells():
    s = awake()
    cells = [(4, 1), (4, 2), (4, 3), (3, 3)]
    for c in cells[:config.MAX_TEMP_CREATURES]:
        s.mind_flayer.spawn_cooldown = 0
        assert apply_mf_action(s, MFAction(SPAWN, c))
    s.mind_flayer.spawn_cooldown = 0
    assert not can_spawn(s, cells[config.MAX_TEMP_CREATURES])    # cap
    s2 = awake()
    assert not can_spawn(s2, s2.eleven_pos) and not can_spawn(s2, s2.vecna.pos)
    apply_mf_action(s2, MFAction(CORRUPT, (2, 1)))
    assert not can_spawn(s2, (2, 1))


def test_summoned_creature_gives_no_power_when_killed():
    s = awake()
    s.eleven_pos = (4, 2)
    apply_mf_action(s, MFAction(SPAWN, (4, 1)))
    s.eleven_power = 5
    assert apply_eleven_action(s, Action.ATTACK)
    assert s.eleven_power == 4                                   # paid the attack, gained nothing


# ------------------------------------------------------------------ turn wiring
def test_mind_flayer_sleeps_until_will_is_rescued():
    s = GameState.new_game()
    tm = TurnManager(s)
    for _ in range(3):
        tm.step(Action.WAIT)
    assert "mind_flayer" not in tm.metrics.mcts and not s.corrupted


def test_rescuing_will_wakes_it_and_it_plans_in_the_same_turn():
    s = GameState.new_game()
    for d in s.demogorgons:
        d.alive = False
    s.vecna.frozen_turns = 10 ** 6
    s.eleven_pos = (12, 11)                                      # Will is at (13, 11)
    tm = TurnManager(s)
    assert not s.mind_flayer.active
    assert tm.step(Action.RESCUE)
    assert s.mind_flayer.active and "Will" in s.rescued
    assert tm.metrics.mcts["mind_flayer"].calls == 1
    assert s.mind_flayer.known_eleven_pos == (12, 11)


def test_no_search_when_defeated_or_eleven_is_dead():
    s = awake()
    s.mind_flayer.defeated = True
    tm = TurnManager(s)
    tm.step(Action.WAIT)
    assert "mind_flayer" not in tm.metrics.mcts
    s2 = awake(freeze_vecna=False)
    s2.eleven_pos, s2.vecna.pos, s2.eleven_hp = (1, 1), (1, 2), 1
    tm2 = TurnManager(s2)
    tm2.step(Action.WAIT)
    assert s2.eleven_hp == 0 and "mind_flayer" not in tm2.metrics.mcts


def test_final_attack_defeats_it_and_it_stops_acting():
    s = awake()
    s.eleven_power = config.FINAL_POWER_REQUIREMENT
    tm = TurnManager(s)
    assert tm.step(Action.FINAL_ATTACK)
    assert s.mind_flayer.defeated and s.portal_active
    calls = tm.metrics.mcts.get("mind_flayer").calls if "mind_flayer" in tm.metrics.mcts else 0
    tm.step(Action.WAIT)
    tm.step(Action.WAIT)
    after = tm.metrics.mcts.get("mind_flayer").calls if "mind_flayer" in tm.metrics.mcts else 0
    assert after == calls


def test_final_battle_end_to_end_win():
    s = awake()
    for f in ("Mike", "Dustin", "Lucas"):
        s.rescued.add(f)
    s.eleven_pos = (11, 13)
    s.visited.add(s.eleven_pos)
    s.eleven_power = config.FINAL_POWER_REQUIREMENT
    tm = TurnManager(s, mind_flayer_ai=Scripted())
    assert tm.step(Action.FINAL_ATTACK) and s.mind_flayer.defeated
    assert tm.step(Action.MOVE_RIGHT)
    assert s.winner == Winner.ELEVEN and s.game_over


def test_the_portal_cannot_be_corrupted_so_the_win_cannot_be_walled_off():
    s = awake()
    for cell in [(11, 13), (13, 13), s.portal_pos]:
        assert (cell == s.portal_pos) != can_corrupt(s, cell) or cell != s.portal_pos


# ------------------------------------------------------------------ model, route, candidates
def test_model_eleven_priorities():
    s = awake()
    plan = make_plan(s)
    s.eleven_power = config.FINAL_POWER_REQUIREMENT
    assert model_eleven_action(s, plan) == Action.FINAL_ATTACK
    s2 = awake()
    s2.eleven_pos = (13, 2)                                      # next to Mike
    assert model_eleven_action(s2, make_plan(s2)) == Action.RESCUE
    s3 = awake()
    s3.rescued.update(s3.friend_positions)
    s3.mind_flayer.defeated = True
    s3.portal_active = False
    assert model_eleven_action(s3, make_plan(s3)) == Action.WAIT      # nothing left to aim at


def test_model_eleven_steps_closer_to_her_objective():
    s = awake()
    plan = make_plan(s)
    here = plan.distance_from(s.eleven_pos)
    a = model_eleven_action(s, plan)
    c = s.clone()
    assert apply_eleven_action(c, a)
    assert plan.distance_from(c.eleven_pos) == here - 1


def test_plan_respects_corruption():
    s = awake()
    target_plan = make_plan(s)
    base = target_plan.distance_from(s.eleven_pos)
    route = route_cells(s, target_plan, 3)
    apply_mf_action(s, MFAction(CORRUPT, route[0]))
    new_plan = make_plan(s)
    assert route[0] not in new_plan.dist or new_plan.target == route[0]
    assert new_plan.distance_from(s.eleven_pos) is None or new_plan.distance_from(s.eleven_pos) >= base


def test_route_cells_are_a_connected_shortest_path():
    s = awake()
    plan = make_plan(s)
    route = route_cells(s, plan, config.MF_ROUTE_LOOKAHEAD)
    assert 1 <= len(route) <= config.MF_ROUTE_LOOKAHEAD
    prev, d = s.eleven_pos, plan.distance_from(s.eleven_pos)
    for cell in route:
        assert abs(cell[0] - prev[0]) + abs(cell[1] - prev[1]) == 1
        assert plan.dist[cell] == d - 1
        prev, d = cell, d - 1


def test_candidate_actions_are_legal_ordered_and_capped():
    rng = random.Random(4)
    for _ in range(15):
        s = awake(kill_demogorgons=False, freeze_vecna=False)
        for _ in range(rng.randint(0, 8)):
            apply_eleven_action(s, rng.choice(legal_eleven_actions(s)))
        plan = make_plan(s)
        acts = candidate_actions(s, plan)
        assert acts[-1] == MFAction(WAIT) and acts == candidate_actions(s, plan)
        corrupts = [a for a in acts if a.kind == CORRUPT]
        spawns = [a for a in acts if a.kind == SPAWN]
        assert len(corrupts) <= config.MF_MAX_CORRUPT_CANDIDATES and len(spawns) <= config.MF_SPAWN_CANDIDATES
        for a in corrupts:
            assert can_corrupt(s, a.cell)
        for a in spawns:
            d = walk_distance(s.board, s.eleven_pos, a.cell)
            assert can_spawn(s, a.cell) and config.MF_SPAWN_MIN_DISTANCE <= d <= config.MF_SPAWN_MAX_DISTANCE
    s = awake()
    assert candidate_actions(s, make_plan(s))[0].cell == route_cells(s, make_plan(s), 1)[0]   # blocks her next step


def test_no_summon_candidates_during_the_cooldown():
    s = awake()
    s.mind_flayer.spawn_cooldown = 2
    assert not [a for a in candidate_actions(s, make_plan(s)) if a.kind == SPAWN]


# ------------------------------------------------------------------ rewards
def test_blocking_her_route_pays_more_than_waiting():
    s = awake()
    plan = make_plan(s)
    nxt = route_cells(s, plan, 1)[0]
    r_block, _ = mf_step(s.clone(), MFAction(CORRUPT, nxt), plan)
    r_wait, _ = mf_step(s.clone(), MFAction(WAIT), plan)
    assert r_block >= r_wait + R["BLOCK_ROUTE"]


def test_trapping_a_weak_eleven_next_to_vecna_pays_the_kill_reward():
    s = awake(freeze_vecna=False)
    s.eleven_pos, s.vecna.pos, s.eleven_hp = (1, 1), (1, 2), 1
    plan = make_plan(s)
    reward, _ = mf_step(s.clone(), MFAction(CORRUPT, (2, 1)), plan)   # no way out: Vecna hits
    assert reward >= R["KILL_ELEVEN"] + R["DAMAGE_ELEVEN"]


def test_being_defeated_costs_the_mind_flayer():
    s = awake()
    s.eleven_power = config.FINAL_POWER_REQUIREMENT
    c = s.clone()
    reward, _ = mf_step(c, MFAction(WAIT), make_plan(c))
    assert c.mind_flayer.defeated and reward <= R["DEFEATED"] + R["TRAP_ELEVEN"] + R["FORCE_AWAY"]


def test_free_neighbour_count():
    s = awake()
    s.eleven_pos = (1, 1)
    assert free_neighbour_count(s) == 2
    apply_mf_action(s, MFAction(CORRUPT, (2, 1)))
    assert free_neighbour_count(s) == 1


def test_forcing_her_away_is_rewarded():
    s = awake()
    plan = make_plan(s)
    nxt = route_cells(s, plan, 1)[0]
    c = s.clone()
    reward, new_plan = mf_step(c, MFAction(CORRUPT, nxt), plan)
    d0 = plan.distance_from(s.eleven_pos)
    d1 = new_plan.distance_from(c.eleven_pos)
    if d1 is not None and d1 > d0:
        assert reward >= R["BLOCK_ROUTE"] + R["FORCE_AWAY"]


# ------------------------------------------------------------------ MCTS
def test_mcts_counters_are_real():
    s = awake(kill_demogorgons=False, freeze_vecna=False)
    r = mf_search(s, simulations=100, seed=1)
    assert r.simulations == 100
    assert sum(v for _, v, _ in r.root) == 100
    assert r.visits == max(v for _, v, _ in r.root)
    assert r.nodes_created >= 1 + len(r.root) and r.max_depth >= 1 and r.simulated_turns > 0 and r.time_ms > 0
    assert r.action.label == r.root[0][0] == r.label


def test_mcts_is_deterministic_and_uses_the_configured_budget():
    s = awake(kill_demogorgons=False, freeze_vecna=False)
    a, b = mf_search(s, 80, seed=5), mf_search(s, 80, seed=5)
    assert (a.action, a.root, a.nodes_created, a.simulated_turns) == (b.action, b.root, b.nodes_created, b.simulated_turns)
    assert mf_search(s).simulations == config.MINDFLAYER_MCTS_SIMULATIONS == 150


def test_mcts_never_mutates_the_live_state():
    s = awake(kill_demogorgons=False, freeze_vecna=False)
    apply_mf_action(s, MFAction(CORRUPT, (2, 1)))
    before = snap(s)
    mf_search(s, 100, seed=3)
    assert snap(s) == before


def test_mcts_blocks_the_cell_beside_a_cornered_eleven():
    """Weak Eleven in a corner with Vecna two cells away: the search corrupts the cell next to her."""
    for seed in (1, 2, 3):
        s = awake(freeze_vecna=False)
        s.eleven_pos, s.vecna.pos, s.eleven_hp = (1, 1), (1, 3), 1
        assert mf_search(s, 150, seed=seed).action == MFAction(CORRUPT, (1, 2))


def test_mcts_does_something_useful_instead_of_waiting():
    s = awake()
    assert mf_search(s, 150, seed=2).action.kind in (CORRUPT, SPAWN)


def test_controller_records_the_real_statistics():
    s = awake()
    ai = MindFlayerAI(Metrics(), simulations=60)
    action = ai.choose_action(s)
    st = ai.metrics.mcts["mind_flayer"]
    assert action == ai.last_result.action
    assert (st.calls, st.simulations) == (1, 60)
    assert st.nodes_created == ai.last_result.nodes_created and st.last is ai.last_result


def test_hud_shows_the_mind_flayer_line():
    s = awake()
    tm = TurnManager(s, mind_flayer_ai=MindFlayerAI(simulations=40))
    tm.mind_flayer_ai.metrics = tm.metrics
    tm.step(Action.WAIT)
    lines = game_main.stats_lines(tm)
    st = tm.metrics.mcts["mind_flayer"]
    assert any(l.startswith(f"Mind Flayer MCTS: {st.calls} searches, {st.simulations} simulations") for l in lines)
    assert any(st.last.label in l for l in lines)


# ------------------------------------------------------------------ whole games
def check_invariants(s):
    cells = [d.pos for d in s.living_demogorgons()] + [s.vecna.pos, s.eleven_pos]
    assert len(cells) == len(set(cells)), "two characters share a cell"
    assert not (set(cells) & set(s.corrupted)), "a character stands on a corrupted cell"
    assert len(s.corrupted) <= config.MF_MAX_CORRUPTED
    assert sum(1 for d in s.demogorgons if d.alive and d.temporary) <= config.MAX_TEMP_CREATURES
    assert 0 <= s.eleven_hp <= config.MAX_HP and 0 <= s.eleven_power <= config.MAX_POWER
    assert s.portal_pos not in s.corrupted and s.turn <= config.MAX_TURNS


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_random_games_with_an_awake_mind_flayer_keep_invariants(seed):
    rng = random.Random(seed)
    s = awake(kill_demogorgons=False, freeze_vecna=False)
    tm = TurnManager(s, mind_flayer_ai=MindFlayerAI(simulations=40))
    tm.mind_flayer_ai.metrics = tm.metrics
    while not s.game_over:
        assert tm.step(rng.choice(legal_eleven_actions(s)))
        check_invariants(s)
    assert s.winner in (Winner.ENEMIES, Winner.ELEVEN)


@pytest.mark.parametrize("seed", [1, 2])
def test_ai_vs_ai_with_the_mind_flayer_keeps_invariants(seed):
    config.RNG_SEED = seed
    s = GameState.new_game()
    tm = TurnManager(s, mind_flayer_ai=MindFlayerAI(simulations=40))
    tm.mind_flayer_ai.metrics = tm.metrics
    ai = ElevenAI(tm.metrics, simulations=40)
    while not s.game_over:
        c = ai.choose_turn(s)
        assert tm.step(c.action, c.target, c.bonus_action)
        check_invariants(s)
    config.RNG_SEED = 42
    assert s.winner in (Winner.ENEMIES, Winner.ELEVEN)
    if s.mind_flayer.active:
        assert tm.metrics.mcts["mind_flayer"].calls >= 1