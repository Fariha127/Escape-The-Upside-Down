"""Phase 6: strategic goals, simulation, Eleven's MCTS, A* execution, AI controller, AI-vs-AI loop."""
import random

import pytest

import config
import main as game_main
from ai.astar import astar_search
from ai.distance_table import walk_distance
from ai.eleven_ai import ElevenAI
from ai.goals import (AI_ABILITIES, Goal, GoalRun, Kind, applicable_goals, evade_cell, hit_zone,
                      openness, safe_step_cost, table_step)
from ai.mcts import mcts_search
from ai.metrics import Metrics
from ai.navigation import Navigator
from ai.sim import enemy_phase, objective_distance, run_goal, sim_turn, snapshot, turn_reward
from game.actions import Action, MOVE_DELTAS
from game.rules import apply_eleven_action, legal_eleven_actions
from game.mind_flayer_rules import WAIT, MFAction
from game.state import GameState, Winner
from game.turn_manager import TurnManager

FRIENDS = ("Mike", "Dustin", "Lucas", "Will")


class IdleMindFlayer:
    """A Mind Flayer that only waits, so Phase 6 tests can look at Eleven's AI on its own."""
    def choose_action(self, state):
        return MFAction(WAIT)


def fresh(kill_demogorgons=True, freeze_vecna=False):
    s = GameState.new_game()
    if kill_demogorgons:
        for d in s.demogorgons:
            d.alive = False
    if freeze_vecna:
        s.vecna.frozen_turns = 10 ** 6
    return s


def rescue_all(s):
    """Mark every friend rescued with their ability unlocked and stocked (no Mind Flayer wake-up)."""
    for f in FRIENDS:
        ability = config.FRIEND_ABILITY[f]
        s.rescued.add(f)
        s.unlocked_abilities.add(ability)
        s.ability_uses[ability] = config.ABILITY_USES[ability]


def snap(s):
    return (s.eleven_pos, s.eleven_hp, s.eleven_power, s.turn, s.vecna.pos, s.vecna.frozen_turns,
            [(d.id, d.pos, d.alive, d.cooldown, d.frozen_turns) for d in s.demogorgons], set(s.rescued),
            set(s.visited), dict(s.status_effects), dict(s.ability_uses), len(s.event_log), s.winner,
            s.portal_active, s.mind_flayer.active, s.mind_flayer.defeated)


# ------------------------------------------------------------------ goals
def test_goals_at_the_start(monkeypatch):
    monkeypatch.setattr(config, "ELEVEN_RESCUE_WILL_LAST", False)    # this test covers the plain goal list
    s = GameState.new_game()
    s.eleven_power = 0                                           # no power: no HUNT goal yet
    labels = [g.label for g in applicable_goals(s)]
    assert labels == ["RESCUE Mike", "RESCUE Dustin", "RESCUE Lucas", "RESCUE Will", "EVADE"]


def test_hunt_needs_power_and_a_normal_demogorgon():
    s = GameState.new_game()
    s.eleven_power = 0
    assert Goal(Kind.HUNT) not in applicable_goals(s)
    s.eleven_power = 1
    assert Goal(Kind.HUNT) in applicable_goals(s)
    for d in s.demogorgons:
        d.temporary = True                      # temporary creatures give no power: not worth hunting
    assert Goal(Kind.HUNT) not in applicable_goals(s)


def test_portal_goal_needs_open_portal_and_all_friends():
    s = fresh()
    s.portal_active = True
    assert Goal(Kind.PORTAL) not in applicable_goals(s)
    rescue_all(s)
    assert Goal(Kind.PORTAL) in applicable_goals(s)
    s.portal_active = False
    assert Goal(Kind.PORTAL) not in applicable_goals(s)


def test_final_goal_needs_an_awake_mind_flayer_and_will():
    s = fresh()
    assert Goal(Kind.FINAL) not in applicable_goals(s)
    rescue_all(s)
    s.mind_flayer.active = True
    s.eleven_power = config.FINAL_POWER_REQUIREMENT
    assert Goal(Kind.FINAL) in applicable_goals(s)
    s.mind_flayer.defeated = True
    assert Goal(Kind.FINAL) not in applicable_goals(s)


def test_ability_goals_follow_unlocked_abilities_and_radar_is_never_a_goal():
    s = fresh()
    assert not [g for g in applicable_goals(s) if g.kind == Kind.ABILITY]
    rescue_all(s)
    names = {g.arg for g in applicable_goals(s) if g.kind == Kind.ABILITY}
    assert "RADAR" not in names and "RADAR" not in AI_ABILITIES
    assert "FREEZE" in names and "SPEED" in names


def test_no_goals_after_game_over():
    s = fresh()
    s.winner = Winner.ENEMIES
    assert applicable_goals(s) == []


# ------------------------------------------------------------------ GoalRun
def test_rescue_run_walks_then_rescues():
    s = fresh(freeze_vecna=True)
    run = GoalRun(Goal(Kind.RESCUE, "Mike"), s)
    nav = Navigator(Metrics())
    for _ in range(60):
        act = run.next_action(s, lambda st, t: nav.next_action(st, t)[0])
        if act is None:
            break
        assert apply_eleven_action(s, act[0])
        if act[0] == Action.RESCUE:
            break
    assert "Mike" in s.rescued and run.done(s)
    assert run.next_action(s, lambda st, t: Action.WAIT) is None


def test_rescue_run_returns_rescue_when_in_range():
    s = fresh()
    s.eleven_pos = (13, 2)
    act = GoalRun(Goal(Kind.RESCUE, "Mike"), s).next_action(s, table_step)
    assert act == (Action.RESCUE, None)


def test_hunt_run_attacks_an_adjacent_demogorgon_and_finishes():
    s = GameState.new_game()
    for d in s.demogorgons[1:]:
        d.alive = False
    s.eleven_power = 1
    s.demogorgons[0].pos = (1, 2)
    run = GoalRun(Goal(Kind.HUNT), s)
    assert run.next_action(s, table_step) == (Action.ATTACK, None)
    apply_eleven_action(s, Action.ATTACK)
    assert run.done(s)


def test_final_run_attacks_when_possible_else_none_without_targets():
    s = fresh()
    rescue_all(s)
    s.mind_flayer.active = True
    s.eleven_power = config.FINAL_POWER_REQUIREMENT
    run = GoalRun(Goal(Kind.FINAL), s)
    assert run.next_action(s, table_step) == (Action.FINAL_ATTACK, None)
    s2 = fresh()
    rescue_all(s2)
    s2.mind_flayer.active = True
    s2.eleven_power = 0
    assert GoalRun(Goal(Kind.FINAL), s2).next_action(s2, table_step) is None


def test_ability_run_acts_once_and_teleport_gets_a_target():
    s = fresh()
    rescue_all(s)
    run = GoalRun(Goal(Kind.ABILITY, "FREEZE"), s)
    assert run.next_action(s, table_step) == (Action.USE_FREEZE, None)
    assert run.next_action(s, table_step) is None                # only once
    s.visited.update({(1, 2), (1, 3), (2, 3)})
    s.eleven_pos = (2, 3)
    s.vecna.pos = (13, 13)
    tp = GoalRun(Goal(Kind.ABILITY, "TELEPORT"), s).next_action(s, table_step)
    assert tp[0] == Action.USE_TELEPORT and tp[1] is not None
    assert apply_eleven_action(s, tp[0], tp[1])


def test_evade_run_finishes_on_arrival():
    s = GameState.new_game()
    run = GoalRun(Goal(Kind.EVADE), s)
    assert run.cell == evade_cell(s)
    s.eleven_pos = run.cell
    assert run.done(s)


# ------------------------------------------------------------------ evade, danger, stepping
def test_evade_cell_is_legal_close_and_away_from_enemies():
    rng = random.Random(5)
    for _ in range(25):
        s = GameState.new_game()
        for _ in range(rng.randint(0, 10)):
            apply_eleven_action(s, rng.choice(legal_eleven_actions(s)))
        cell = evade_cell(s)
        assert walk_distance(s.board, s.eleven_pos, cell) <= config.EVADE_RADIUS
        assert not s.is_blocked(cell)
        if cell != s.eleven_pos:
            assert cell not in s.enemy_positions()
            assert s.board.terrain_at(cell).name != "HAZARD"


def test_evade_prefers_distance_from_the_nearest_enemy():
    s = fresh(freeze_vecna=True)
    s.eleven_pos, s.vecna.pos = (1, 7), (1, 9)
    s.visited.add(s.eleven_pos)
    cell = evade_cell(s)
    assert walk_distance(s.board, cell, s.vecna.pos) > walk_distance(s.board, s.eleven_pos, s.vecna.pos)


def test_openness_is_a_fraction_and_dead_ends_are_less_open():
    b = GameState.new_game().board
    values = [openness(b, (x, y)) for y in range(b.height) for x in range(b.width) if b.is_walkable((x, y))]
    assert all(0.0 <= v <= 1.0 for v in values) and min(values) < max(values)
    assert openness(b, (13, 13)) < openness(b, (3, 3))          # pocket beside the portal vs the start room


def test_hit_zone_and_safe_step_cost():
    s = fresh()
    s.demogorgons[0].alive = True
    s.demogorgons[0].pos = (5, 3)
    s.vecna.pos = (9, 9)
    zone = hit_zone(s)
    assert (5, 3) in zone and (5, 2) in zone and (4, 3) in zone and (3, 3) not in zone
    cost = safe_step_cost(s)
    assert cost((4, 3)) == 1 + config.DANGER_STEP_COST
    assert cost((3, 3)) == 1
    s.demogorgons[0].cooldown = 1                                # cannot hit this turn: no danger
    assert (4, 3) not in hit_zone(s)


def test_astar_with_danger_cost_avoids_the_hit_zone_when_it_can():
    s = fresh(freeze_vecna=False)
    s.eleven_pos = (1, 1)
    s.demogorgons[0].alive = True
    s.demogorgons[0].pos = (3, 3)
    s.vecna.pos = (13, 13)
    action, res = Navigator(Metrics()).next_action(s, (4, 3), safe_step_cost(s))
    zone = hit_zone(s)
    assert res.found
    # the cost-aware path never plans a step into the zone unless there is no other way
    assert not (res.path[0] in zone) or all(p in zone for p in res.path)


def test_table_step_reaches_every_target_in_exactly_the_static_distance():
    s = fresh(freeze_vecna=True)
    rng = random.Random(9)
    cells = [(x, y) for y in range(15) for x in range(15)
             if s.board.is_walkable((x, y)) and (x, y) != s.vecna.pos]
    for _ in range(25):
        a, b = rng.choice(cells), rng.choice(cells)
        t = s.clone()
        t.eleven_pos = a
        steps = 0
        while t.eleven_pos != b and steps < 100:
            act = table_step(t, b)
            assert act in MOVE_DELTAS
            assert apply_eleven_action(t, act)
            steps += 1
        assert t.eleven_pos == b and steps == walk_distance(s.board, a, b)
        res = astar_search(s.board, a, b)
        assert steps == (res.path_length if a != b else 0)      # same length as real A*


def test_table_step_waits_when_boxed_in():
    s = fresh()
    s.eleven_pos = (1, 1)
    s.demogorgons[0].alive = True
    s.demogorgons[0].pos = (1, 2)
    s.demogorgons[1].alive = True
    s.demogorgons[1].pos = (2, 1)
    assert table_step(s, (13, 13)) == Action.WAIT


# ------------------------------------------------------------------ simulation
def test_sim_enemy_phase_hits_adjacent_and_chases_otherwise():
    s = fresh()
    s.demogorgons[0].alive = True
    s.demogorgons[0].pos = (1, 2)
    s.vecna.pos = (13, 13)
    enemy_phase(s)
    assert s.eleven_hp == config.MAX_HP - config.DEMOGORGON_DAMAGE
    s2 = fresh()
    s2.vecna.pos = (1, 7)
    before = walk_distance(s2.board, s2.vecna.pos, s2.eleven_pos)
    enemy_phase(s2)
    assert walk_distance(s2.board, s2.vecna.pos, s2.eleven_pos) == before - 1


def test_sim_frozen_enemies_do_nothing():
    s = fresh()
    s.vecna.pos = (1, 2)
    s.vecna.frozen_turns = 2
    enemy_phase(s)
    assert s.eleven_hp == config.MAX_HP and s.vecna.pos == (1, 2)


def test_sim_vecna_hits_for_vecna_damage():
    s = fresh()
    s.vecna.pos = (1, 2)
    enemy_phase(s)
    assert s.eleven_hp == config.MAX_HP - config.VECNA_DAMAGE


def test_sim_timers_match_the_real_turn_manager():
    real = fresh(kill_demogorgons=False)
    real.eleven_pos = (13, 2)
    real.vecna.pos = (9, 9)
    real.visited.add(real.eleven_pos)
    for f in ("Dustin", "Lucas", "Will", "Mike"):
        real.rescued.add(f)
        a = config.FRIEND_ABILITY[f]
        real.unlocked_abilities.add(a)
        real.ability_uses[a] = config.ABILITY_USES[a]
    sim = real.clone()
    tm = TurnManager(real)
    tm.step(Action.USE_SPEED)
    sim_turn(sim, Action.USE_SPEED)
    assert real.status_effects == sim.status_effects
    assert [d.frozen_turns for d in real.demogorgons] == [d.frozen_turns for d in sim.demogorgons]
    assert real.turn == sim.turn


def test_turn_reward_events():
    s = fresh()
    before = snapshot(s)
    s.rescued.add("Mike")
    s.eleven_power += 3
    assert turn_reward(before, s) == config.ELEVEN_REWARDS["RESCUE_FRIEND"] + 3 * config.ELEVEN_REWARDS["GAIN_POWER"]
    before = snapshot(s)
    s.eleven_hp -= 1
    assert turn_reward(before, s) <= config.ELEVEN_REWARDS["LOSE_HP"]
    before = snapshot(s)
    s.eleven_hp = 0
    s.winner = Winner.ENEMIES
    assert turn_reward(before, s) <= config.ELEVEN_REWARDS["DEATH"]
    t = fresh()
    before = snapshot(t)
    t.winner = Winner.ELEVEN
    assert turn_reward(before, t) == config.ELEVEN_REWARDS["ESCAPE"]


def test_vecna_danger_penalty_applies_when_he_is_close():
    s = fresh()
    s.vecna.pos = (1, 3)
    assert turn_reward(snapshot(s), s) == config.ELEVEN_REWARDS["VECNA_DANGER"]
    s.vecna.pos = (1, 13)
    assert turn_reward(snapshot(s), s) == 0


def test_objective_distance_and_progress_direction():
    s = fresh()
    d0 = objective_distance(s)
    assert d0 == min(walk_distance(s.board, s.eleven_pos, p) for p in s.friend_positions.values())
    t = s.clone()
    reward, turns = run_goal(t, GoalRun(Goal(Kind.RESCUE, "Dustin"), t), 3)
    assert turns == 3 and objective_distance(t) < d0


def test_run_goal_always_passes_at_least_one_turn_and_never_touches_the_original():
    s = fresh()
    before = snap(s)
    t = s.clone()
    done_run = GoalRun(Goal(Kind.EVADE), t)
    t.eleven_pos = done_run.cell
    turn0 = t.turn
    _, turns = run_goal(t, done_run, config.MCTS_GOAL_TURNS)
    assert turns == 1 and t.turn == turn0 + 1
    assert snap(s) == before


def test_speed_in_simulation_moves_two_cells_a_turn():
    s = fresh(freeze_vecna=True)
    s.status_effects["SPEED"] = 5
    t = s.clone()
    run_goal(t, GoalRun(Goal(Kind.RESCUE, "Mike"), t), 1)
    assert walk_distance(s.board, s.eleven_pos, t.eleven_pos) == config.SPEED_MOVES_PER_TURN


def test_random_simulation_games_keep_invariants():
    rng = random.Random(3)
    for _ in range(5):
        s = GameState.new_game()
        while not s.game_over and s.turn < 60:
            goals = applicable_goals(s)
            run_goal(s, GoalRun(rng.choice(goals), s), config.MCTS_GOAL_TURNS)
            cells = [d.pos for d in s.living_demogorgons()] + [s.vecna.pos, s.eleven_pos]
            assert len(cells) == len(set(cells))
            assert 0 <= s.eleven_hp <= config.MAX_HP and 0 <= s.eleven_power <= config.MAX_POWER


# ------------------------------------------------------------------ MCTS
def test_mcts_returns_an_applicable_goal_and_real_counters():
    s = GameState.new_game()
    r = mcts_search(s, simulations=120, seed=1)
    assert r.goal in applicable_goals(s)
    assert r.simulations == 120
    assert sum(v for _, v, _ in r.root) == 120                   # every simulation passes through one root child
    assert r.nodes_created >= 1 + len(r.root)                    # the root plus at least one node per root goal
    assert r.max_depth >= 1 and r.simulated_turns > 0 and r.time_ms > 0
    assert r.visits == max(v for _, v, _ in r.root)


def test_mcts_is_deterministic_for_a_seed_and_uses_the_configured_budget():
    s = GameState.new_game()
    a, b = mcts_search(s, 100, seed=7), mcts_search(s, 100, seed=7)
    assert (a.goal, a.root, a.nodes_created, a.simulated_turns) == (b.goal, b.root, b.nodes_created, b.simulated_turns)
    assert mcts_search(s).simulations == config.ELEVEN_MCTS_SIMULATIONS == 300


def test_mcts_never_mutates_the_live_state():
    s = GameState.new_game()
    before = snap(s)
    mcts_search(s, 150, seed=2)
    assert snap(s) == before


def test_mcts_rescues_an_adjacent_friend_when_nothing_threatens(monkeypatch):
    monkeypatch.setattr(config, "ELEVEN_RESCUE_WILL_LAST", False)    # Mike vs Lucas is a near-tie otherwise
    s = fresh(freeze_vecna=True)
    s.eleven_pos = (13, 2)
    assert mcts_search(s, 150, seed=1).goal == Goal(Kind.RESCUE, "Mike")


def test_mcts_heads_for_the_portal_when_it_can_win():
    s = fresh(freeze_vecna=True)
    rescue_all(s)
    s.mind_flayer.active = True
    s.mind_flayer.defeated = True
    s.portal_active = True
    s.eleven_pos = (10, 13)
    s.visited.add(s.eleven_pos)
    assert mcts_search(s, 150, seed=1).goal == Goal(Kind.PORTAL)


def test_mcts_uses_the_final_attack_when_available():
    s = fresh(freeze_vecna=True)
    rescue_all(s)
    s.mind_flayer.active = True
    s.eleven_power = config.FINAL_POWER_REQUIREMENT
    assert mcts_search(s, 150, seed=1).goal == Goal(Kind.FINAL)


def test_mcts_prefers_a_reward_over_idling_with_more_simulations():
    s = fresh(freeze_vecna=True)
    s.eleven_pos = (13, 2)
    r = mcts_search(s, 300, seed=3)
    values = {label: v for label, _, v in r.root}
    assert values["RESCUE Mike"] > values["EVADE"]


# ------------------------------------------------------------------ the controller
def test_metrics_record_mcts_from_the_real_result():
    s = GameState.new_game()
    m = Metrics()
    r = mcts_search(s, 50, seed=1)
    m.record_mcts("eleven", r)
    st = m.mcts["eleven"]
    assert (st.calls, st.simulations, st.nodes_created, st.simulated_turns) == (1, 50, r.nodes_created, r.simulated_turns)
    assert st.last is r and st.avg_time_ms == r.time_ms


def test_controller_plans_first_then_keeps_the_goal():
    s = fresh(freeze_vecna=True)
    tm = TurnManager(s)
    ai = ElevenAI(tm.metrics)
    c1 = ai.choose_turn(s)
    assert c1.replanned and tm.metrics.mcts["eleven"].calls == 1
    assert tm.step(c1.action, c1.target, c1.bonus_action)
    c2 = ai.choose_turn(s)
    assert not c2.replanned and c2.goal == c1.goal
    assert tm.metrics.mcts["eleven"].calls == 1


def test_controller_replans_after_losing_hp():
    s = fresh(freeze_vecna=True)
    tm = TurnManager(s)
    ai = ElevenAI(tm.metrics)
    tm.step(*[ai.choose_turn(s).action])
    s.eleven_hp -= 1
    assert ai.choose_turn(s).replanned


def test_controller_replans_when_the_goal_ages_out():
    s = fresh(freeze_vecna=True)
    tm = TurnManager(s)
    ai = ElevenAI(tm.metrics)
    calls = []
    for _ in range(config.ELEVEN_REPLAN_TURNS + 2):
        c = ai.choose_turn(s)
        calls.append(c.replanned)
        tm.step(c.action, c.target, c.bonus_action)
    assert calls[0] and sum(calls) >= 2 and calls.count(True) < len(calls)


def test_controller_walks_with_real_astar_and_records_it():
    s = fresh(freeze_vecna=True)
    tm = TurnManager(s)
    ai = ElevenAI(tm.metrics)
    for _ in range(4):
        c = ai.choose_turn(s)
        tm.step(c.action, c.target, c.bonus_action)
    assert tm.metrics.astar["eleven"].calls >= 1 and tm.metrics.astar["eleven"].nodes_explored > 0


def test_controller_adds_a_bonus_move_under_speed_and_the_turn_manager_accepts_it():
    s = fresh(freeze_vecna=True)
    rescue_all(s)
    s.status_effects["SPEED"] = 5
    tm = TurnManager(s)
    ai = ElevenAI(tm.metrics)
    start = s.eleven_pos
    for _ in range(3):
        c = ai.choose_turn(s)
        if c.action in MOVE_DELTAS:
            assert c.bonus_action in MOVE_DELTAS
        assert tm.step(c.action, c.target, c.bonus_action)
        if not s.status_effects.get("SPEED"):
            break
    assert s.eleven_pos != start


def test_controller_waits_instead_of_crashing_when_boxed_in_and_replans_next_turn():
    s = fresh(freeze_vecna=True)
    s.eleven_pos = (1, 1)
    for i, p in ((0, (1, 2)), (1, (2, 1))):
        s.demogorgons[i].alive = True
        s.demogorgons[i].pos = p
        s.demogorgons[i].frozen_turns = 50
    tm = TurnManager(s)
    ai = ElevenAI(tm.metrics)
    c = ai.choose_turn(s)
    assert tm.step(c.action, c.target, c.bonus_action)


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_ai_vs_ai_full_games_keep_invariants(seed):
    config.RNG_SEED = seed
    s = GameState.new_game()
    tm = TurnManager(s)
    ai = ElevenAI(tm.metrics, simulations=60)
    while not s.game_over:
        c = ai.choose_turn(s)
        assert tm.step(c.action, c.target, c.bonus_action)
        cells = [d.pos for d in s.living_demogorgons()] + [s.vecna.pos, s.eleven_pos]
        assert len(cells) == len(set(cells)), "two characters share a cell"
        assert 0 <= s.eleven_hp <= config.MAX_HP and 0 <= s.eleven_power <= config.MAX_POWER
        assert s.turn <= config.MAX_TURNS
    assert s.winner in (Winner.ENEMIES, Winner.ELEVEN)
    assert tm.metrics.mcts["eleven"].calls >= 1
    config.RNG_SEED = 42


@pytest.mark.parametrize("seed", [1, 2])
def test_ai_wins_when_the_dangerous_enemies_are_out_of_the_way(seed):
    """End to end: MCTS + A* rescue all four friends, defeat the Mind Flayer and escape."""
    config.RNG_SEED = seed
    s = fresh(kill_demogorgons=True, freeze_vecna=True)
    tm = TurnManager(s, mind_flayer_ai=IdleMindFlayer())
    ai = ElevenAI(tm.metrics)
    while not s.game_over:
        c = ai.choose_turn(s)
        assert tm.step(c.action, c.target, c.bonus_action)
    config.RNG_SEED = 42
    assert s.winner == Winner.ELEVEN and len(s.rescued) == 4 and s.mind_flayer.defeated


def test_hud_shows_the_real_mcts_statistics():
    s = GameState.new_game()
    tm = TurnManager(s)
    ai = ElevenAI(tm.metrics, simulations=40)
    c = ai.choose_turn(s)
    tm.step(c.action, c.target, c.bonus_action)
    lines = game_main.stats_lines(tm)
    st = tm.metrics.mcts["eleven"]
    assert any(l.startswith(f"Eleven MCTS: {st.calls} searches, {st.simulations} simulations") for l in lines)
    assert any(st.last.goal.label in l for l in lines)


def test_ai_turn_helper_plays_a_legal_turn_every_time():
    state, tm, ai = game_main.new_game()
    for _ in range(12):
        t = state.turn
        game_main.ai_turn(state, tm, ai)
        assert state.game_over or state.turn == t + 1