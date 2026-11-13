"""Phase 4: combat, rescue (+power bonus), hazards, abilities, Radar A* report, full-turn integration."""
import random

import pytest

import config
from abilities import radar, teleport
from ai.radar_scan import scan
from characters.demogorgon import Demogorgon
from game.actions import Action, MOVE_DELTAS
from game.rules import (apply_eleven_action, attack_target, demogorgon_hit, legal_eleven_actions,
                        vecna_hit)
from game.state import GameState, Winner
from game.turn_manager import TurnManager


def fresh(kill_demogorgons=True):
    """New game; by default all Demogorgons are removed so each test controls its own enemies.
    Vecna has no behaviour until Phase 5, so he stays put at (1, 13)."""
    s = GameState.new_game()
    if kill_demogorgons:
        for d in s.demogorgons:
            d.alive = False
    return s, TurnManager(s)


def add_demogorgon(s, pos, temporary=False):
    d = Demogorgon(max((x.id for x in s.demogorgons), default=-1) + 1, pos, temporary=temporary)
    s.demogorgons.append(d)
    return d


def unlock(s, ability, friend):
    s.rescued.add(friend)
    s.unlocked_abilities.add(ability)
    s.ability_uses[ability] = config.ABILITY_USES[ability]


# ------------------------------------------------------------------ attack
def test_attack_costs_one_and_gains_three():
    s, tm = fresh()
    s.eleven_power = 2
    d = add_demogorgon(s, (2, 1))
    assert Action.ATTACK in legal_eleven_actions(s)
    assert apply_eleven_action(s, Action.ATTACK)
    assert not d.alive
    assert s.eleven_power == 2 - config.DEMOGORGON_ATTACK_COST + config.DEMOGORGON_REWARD  # net +2


def test_attack_needs_power():
    s, _ = fresh()
    s.eleven_power = 0
    add_demogorgon(s, (2, 1))
    assert Action.ATTACK not in legal_eleven_actions(s)
    assert not apply_eleven_action(s, Action.ATTACK)


def test_attack_needs_adjacent_target():
    s, _ = fresh()
    s.eleven_power = 5
    add_demogorgon(s, (5, 1))
    assert attack_target(s) is None
    assert Action.ATTACK not in legal_eleven_actions(s)


def test_attack_power_is_capped():
    s, _ = fresh()
    s.eleven_power = config.MAX_POWER
    add_demogorgon(s, (2, 1))
    apply_eleven_action(s, Action.ATTACK)
    assert s.eleven_power == config.MAX_POWER


def test_temporary_creature_gives_no_power():
    s, _ = fresh()
    s.eleven_power = 2
    d = add_demogorgon(s, (2, 1), temporary=True)
    apply_eleven_action(s, Action.ATTACK)
    assert not d.alive
    assert s.eleven_power == 2 - config.DEMOGORGON_ATTACK_COST   # net -1: no farming


def test_no_power_farming_with_only_normal_demogorgons():
    """Total power obtainable from kills is bounded by the number of normal Demogorgons."""
    s = GameState.new_game()
    normal = [d for d in s.demogorgons if not d.temporary]
    assert len(normal) <= config.MAX_NORMAL_DEMOGORGONS


# ------------------------------------------------------------------ Demogorgon damage + cooldown
def test_demogorgon_hit_damage_then_cooldown():
    s, tm = fresh()
    d = add_demogorgon(s, (2, 1))
    tm.step(Action.WAIT)
    assert s.eleven_hp == config.MAX_HP - config.DEMOGORGON_DAMAGE
    tm.step(Action.WAIT)                       # cooldown turn: no damage
    assert s.eleven_hp == config.MAX_HP - config.DEMOGORGON_DAMAGE
    tm.step(Action.WAIT)                       # cooldown over: hits again
    assert s.eleven_hp == config.MAX_HP - 2 * config.DEMOGORGON_DAMAGE


def test_demogorgon_on_cooldown_cannot_hit():
    s, _ = fresh()
    d = add_demogorgon(s, (2, 1))
    d.cooldown = 1
    assert not demogorgon_hit(s, d)
    assert s.eleven_hp == config.MAX_HP


def test_death_ends_game_in_enemy_win():
    s, tm = fresh()
    s.eleven_hp = 1
    add_demogorgon(s, (2, 1))
    tm.step(Action.WAIT)
    assert s.eleven_hp == 0
    assert s.winner == Winner.ENEMIES and s.game_over


def test_vecna_hit_deals_two_and_frozen_vecna_cannot():
    s, _ = fresh()
    assert vecna_hit(s)
    assert s.eleven_hp == config.MAX_HP - config.VECNA_DAMAGE
    s.vecna.frozen_turns = 1
    assert not vecna_hit(s)
    assert s.eleven_hp == config.MAX_HP - config.VECNA_DAMAGE


# ------------------------------------------------------------------ hazards
def test_entering_hazard_costs_hp_but_standing_does_not():
    s, tm = fresh()
    s.eleven_pos = (2, 5)          # hazard is at (3, 5)
    s.visited.add((2, 5))
    tm.step(Action.MOVE_RIGHT)
    assert s.eleven_pos == (3, 5)
    assert s.eleven_hp == config.MAX_HP - config.HAZARD_DAMAGE
    tm.step(Action.WAIT)
    assert s.eleven_hp == config.MAX_HP - config.HAZARD_DAMAGE


# ------------------------------------------------------------------ rescue
def test_rescue_requires_range():
    s, _ = fresh()
    assert Action.RESCUE not in legal_eleven_actions(s)
    assert not apply_eleven_action(s, Action.RESCUE)


def test_rescue_unlocks_ability_with_uses():
    s, tm = fresh()
    s.eleven_pos = (1, 7)          # Dustin is at (2, 7)
    assert Action.RESCUE in legal_eleven_actions(s)
    assert tm.step(Action.RESCUE)
    assert "Dustin" in s.rescued
    assert "RADAR" in s.unlocked_abilities
    assert s.ability_uses["RADAR"] == config.ABILITY_USES["RADAR"]


def test_rescuing_will_awakens_mind_flayer():
    s, tm = fresh()
    s.eleven_pos = (12, 11)        # Will is at (13, 11)
    assert not s.mind_flayer.active
    tm.step(Action.RESCUE)
    assert s.mind_flayer.active
    assert any("THE MIND FLAYER HAS AWAKENED" in line for line in s.event_log)


# ------------------------------------------------------------------ radar
def bfs_steps(s, start, goal):
    """Independent shortest-path length (plain BFS) used to check the A* numbers.
    Only walls and corruption block: Radar measures walking distance, other characters are ignored."""
    from collections import deque
    blocked = set(s.corrupted)
    dist, q = {start: 0}, deque([start])
    while q:
        cur = q.popleft()
        if cur == goal:
            return dist[cur]
        for n in s.board.neighbors4(cur):
            if n not in dist and n not in blocked and n not in s.corrupted:
                dist[n] = dist[cur] + 1
                q.append(n)
    return None


def test_radar_unavailable_until_dustin_rescued():
    s, _ = fresh()
    assert Action.USE_RADAR not in legal_eleven_actions(s)


def test_radar_scan_matches_independent_shortest_paths():
    s, _ = fresh()
    add_demogorgon(s, (4, 1))
    add_demogorgon(s, (9, 5))
    readings = scan(s)
    assert len(readings) == len(s.living_demogorgons()) + 1          # every enemy incl. Vecna
    by_label = {r.label: r for r in readings}
    for d in s.living_demogorgons():
        assert by_label[f"Demogorgon {d.id}"].steps == bfs_steps(s, d.pos, s.eleven_pos)
    assert by_label["Vecna"].steps == bfs_steps(s, s.vecna.pos, s.eleven_pos)
    steps = [r.steps for r in readings]
    assert steps == sorted(steps)                                    # nearest first


def test_radar_still_reads_a_distance_when_enemies_box_eleven_in():
    s, _ = fresh()
    s.eleven_pos = (1, 7)
    add_demogorgon(s, (1, 6))
    add_demogorgon(s, (1, 8))                       # Eleven's corridor is blocked on both sides
    far = add_demogorgon(s, (6, 3))
    by_label = {r.label: r for r in scan(s)}
    assert by_label[f"Demogorgon {far.id}"].steps == bfs_steps(s, far.pos, s.eleven_pos) is not None
    assert all(r.steps is not None for r in by_label.values())


def test_radar_scan_is_read_only():
    s, _ = fresh(kill_demogorgons=False)
    before = (s.eleven_pos, [d.pos for d in s.demogorgons], s.vecna.pos, s.turn)
    scan(s)
    assert (s.eleven_pos, [d.pos for d in s.demogorgons], s.vecna.pos, s.turn) == before


def test_radar_report_shows_for_its_duration_and_uses_decrease():
    s, tm = fresh()
    add_demogorgon(s, (4, 1))
    unlock(s, "RADAR", "Dustin")
    assert tm.radar_readings == []
    assert tm.step(Action.USE_RADAR)
    assert s.ability_uses["RADAR"] == config.ABILITY_USES["RADAR"] - 1
    assert radar.is_active(s) and len(tm.radar_readings) == len(s.living_demogorgons()) + 1
    for _ in range(config.RADAR_DURATION - 1):
        tm.step(Action.WAIT)
        assert tm.radar_readings
    tm.step(Action.WAIT)
    assert not radar.is_active(s) and tm.radar_readings == []


def test_radar_numbers_come_from_recorded_astar_runs():
    s, tm = fresh()
    unlock(s, "RADAR", "Dustin")
    tm.step(Action.USE_RADAR)
    st = tm.metrics.astar["radar"]
    assert st.calls == len(tm.radar_readings) == 1                  # only Vecna is alive
    assert st.nodes_explored == sum(r.nodes_explored for r in tm.radar_readings) > 0


def test_radar_runs_out_after_its_uses():
    s, tm = fresh()
    unlock(s, "RADAR", "Dustin")
    for _ in range(config.ABILITY_USES["RADAR"]):
        assert tm.step(Action.USE_RADAR)
    assert Action.USE_RADAR not in legal_eleven_actions(s)
    assert not tm.step(Action.USE_RADAR)


# ------------------------------------------------------------------ speed
def test_speed_gives_extra_move_for_its_duration():
    s, tm = fresh()
    unlock(s, "SPEED", "Lucas")
    assert tm.step(Action.USE_SPEED)
    bonus_turns = 0
    moves = [(Action.MOVE_RIGHT, Action.MOVE_RIGHT), (Action.MOVE_LEFT, Action.MOVE_LEFT)] * 3
    start = s.eleven_pos
    for first, second in moves:
        if not tm.can_bonus_move():
            break
        before = s.eleven_pos
        assert tm.step(first, bonus_action=second)
        assert abs(s.eleven_pos[0] - before[0]) == 2
        bonus_turns += 1
    assert bonus_turns == config.ABILITY_DURATIONS["SPEED"]
    assert not tm.can_bonus_move()


def test_bonus_move_rejected_without_speed_and_changes_nothing():
    s, tm = fresh()
    before = (s.eleven_pos, s.turn)
    assert not tm.step(Action.MOVE_RIGHT, bonus_action=Action.MOVE_RIGHT)
    assert (s.eleven_pos, s.turn) == before


def test_bonus_move_must_be_legal_and_is_all_or_nothing():
    s, tm = fresh()
    unlock(s, "SPEED", "Lucas")
    tm.step(Action.USE_SPEED)
    s.eleven_pos = (1, 1)
    before = (s.eleven_pos, s.turn)
    assert not tm.step(Action.MOVE_RIGHT, bonus_action=Action.MOVE_UP)   # (2,1) then wall at (2,0)
    assert (s.eleven_pos, s.turn) == before


def test_bonus_only_after_a_move():
    s, tm = fresh()
    unlock(s, "SPEED", "Lucas")
    tm.step(Action.USE_SPEED)
    s.eleven_power = 3
    add_demogorgon(s, (2, 1))
    assert not tm.step(Action.ATTACK, bonus_action=Action.MOVE_DOWN)


def test_speed_cannot_be_stacked_while_active():
    s, tm = fresh()
    s.ability_uses["SPEED"] = 5
    s.unlocked_abilities.add("SPEED")
    tm.step(Action.USE_SPEED)
    assert Action.USE_SPEED not in legal_eleven_actions(s)


# ------------------------------------------------------------------ teleport
def test_teleport_goes_to_a_chosen_visited_safe_cell():
    s, tm = fresh()
    unlock(s, "TELEPORT", "Mike")
    for a in (Action.MOVE_DOWN, Action.MOVE_DOWN):
        tm.step(a)
    assert s.eleven_pos == (1, 3)
    assert (1, 1) in teleport.safe_cells(s)
    assert tm.step(Action.USE_TELEPORT, target=(1, 1))
    assert s.eleven_pos == (1, 1)
    assert s.ability_uses["TELEPORT"] == config.ABILITY_USES["TELEPORT"] - 1


def test_teleport_rejects_unvisited_and_unsafe_cells_without_using_the_ability():
    s, tm = fresh()
    unlock(s, "TELEPORT", "Mike")
    tm.step(Action.MOVE_DOWN)
    uses = s.ability_uses["TELEPORT"]
    assert not tm.step(Action.USE_TELEPORT, target=(5, 5))     # never visited
    assert not tm.step(Action.USE_TELEPORT, target=None)       # no destination given
    add_demogorgon(s, (2, 1))                                  # now (1,1) is next to an enemy
    assert not teleport.is_safe_cell(s, (1, 1))
    assert not apply_eleven_action(s.clone(), Action.USE_TELEPORT, (1, 1))
    assert s.ability_uses["TELEPORT"] == uses


def test_teleport_never_targets_hazard_cells():
    s, _ = fresh()
    s.visited.add((3, 5))
    assert not teleport.is_safe_cell(s, (3, 5))


def test_ai_teleport_choice_is_safe_and_farthest_from_enemies():
    s, tm = fresh()
    unlock(s, "TELEPORT", "Mike")
    for a in (Action.MOVE_DOWN, Action.MOVE_DOWN, Action.MOVE_DOWN):
        tm.step(a)
    best = teleport.best_safe_cell(s)
    assert best in teleport.safe_cells(s)
    dist = teleport.enemy_distance_map(s)
    assert all(dist[best] >= dist[c] for c in teleport.safe_cells(s))
    assert best == (1, 1)          # Vecna is at (1, 13): the start cell is farthest away


def test_teleport_unavailable_without_a_safe_cell():
    s, _ = fresh()
    unlock(s, "TELEPORT", "Mike")
    assert teleport.best_safe_cell(s) is None      # only the current cell is visited
    assert Action.USE_TELEPORT not in legal_eleven_actions(s)


# ------------------------------------------------------------------ freeze
def test_freeze_stops_enemies_for_exactly_its_duration():
    s, tm = fresh()
    unlock(s, "FREEZE", "Will")
    add_demogorgon(s, (2, 1))
    assert tm.step(Action.USE_FREEZE)
    assert s.vecna.frozen_turns > 0 or config.ABILITY_DURATIONS["FREEZE"] == 1
    for _ in range(config.ABILITY_DURATIONS["FREEZE"] - 1):
        tm.step(Action.WAIT)
    assert s.eleven_hp == config.MAX_HP            # frozen for the whole duration
    tm.step(Action.WAIT)
    assert s.eleven_hp == config.MAX_HP - config.DEMOGORGON_DAMAGE


def test_freeze_has_a_single_use():
    s, tm = fresh()
    unlock(s, "FREEZE", "Will")
    assert tm.step(Action.USE_FREEZE)
    assert Action.USE_FREEZE not in legal_eleven_actions(s)


# ------------------------------------------------------------------ final attack + win
def test_final_attack_requirements_and_effect():
    s, tm = fresh()
    s.rescued.add("Will")
    s.mind_flayer.active = True
    s.eleven_power = config.FINAL_POWER_REQUIREMENT - 1
    assert Action.FINAL_ATTACK not in legal_eleven_actions(s)
    s.eleven_power = config.FINAL_POWER_REQUIREMENT
    assert Action.FINAL_ATTACK in legal_eleven_actions(s)
    assert tm.step(Action.FINAL_ATTACK)
    assert s.mind_flayer.defeated and s.portal_active
    assert s.eleven_power == 0


def test_final_attack_needs_awake_mind_flayer():
    s, _ = fresh()
    s.rescued.add("Will")
    s.eleven_power = config.MAX_POWER
    assert Action.FINAL_ATTACK not in legal_eleven_actions(s)


def test_win_needs_all_conditions():
    s, tm = fresh()
    s.eleven_pos = (11, 13)
    s.visited.add((11, 13))
    tm.step(Action.MOVE_RIGHT)                     # the portal is closed until the Mind Flayer is defeated
    assert s.eleven_pos != s.portal_pos and s.winner == Winner.NONE


def test_win_when_all_conditions_met():
    s, tm = fresh()
    s.rescued.update(s.friend_positions)
    s.mind_flayer.defeated = True
    s.eleven_pos = (11, 13)
    tm.step(Action.MOVE_RIGHT)
    assert s.winner == Winner.ELEVEN


# ------------------------------------------------------------------ rescue power bonus
def test_rescue_gives_power_bonus():
    s, tm = fresh()
    s.eleven_pos = (1, 7)          # Dustin is at (2, 7)
    s.eleven_power = 0
    tm.step(Action.RESCUE)
    assert s.eleven_power == config.RESCUE_POWER_BONUS


def test_rescue_bonus_is_capped():
    s, tm = fresh()
    s.eleven_pos = (1, 7)
    s.eleven_power = config.MAX_POWER - 1
    tm.step(Action.RESCUE)
    assert s.eleven_power == config.MAX_POWER


def test_failed_rescue_gives_no_bonus():
    s, tm = fresh()
    before = s.eleven_power
    assert not tm.step(Action.RESCUE)
    assert s.eleven_power == before


def test_rescuing_everyone_makes_the_final_attack_reachable_without_kills():
    """Fixes the power deadlock: start 0, attack costs 1, so power must come from somewhere else."""
    assert 4 * config.RESCUE_POWER_BONUS >= config.FINAL_POWER_REQUIREMENT
    s, tm = fresh()
    for stand in ((1, 7), (11, 7), (12, 1), (12, 11)):      # Dustin, Lucas, Mike, Will
        s.eleven_pos = stand
        assert tm.step(Action.RESCUE)
    assert len(s.rescued) == 4 and s.mind_flayer.active
    assert s.eleven_power >= config.FINAL_POWER_REQUIREMENT
    assert Action.FINAL_ATTACK in legal_eleven_actions(s)


# ------------------------------------------------------------------ safety + integration
def test_simulation_on_clone_does_not_touch_live_state():
    s, _ = fresh()
    s.eleven_power = 5
    add_demogorgon(s, (2, 1))
    c = s.clone()
    apply_eleven_action(c, Action.ATTACK)
    assert s.eleven_power == 5 and s.living_demogorgons()


def test_illegal_action_changes_nothing():
    s, tm = fresh()
    before = (s.turn, s.eleven_pos, s.eleven_hp, s.eleven_power)
    assert not tm.step(Action.RESCUE)
    assert not tm.step(Action.ATTACK)
    assert not tm.step(Action.USE_FREEZE)
    assert (s.turn, s.eleven_pos, s.eleven_hp, s.eleven_power) == before


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_random_playthrough_keeps_invariants(seed):
    """150-turn random games with every rule active must never crash or break an invariant."""
    rng = random.Random(seed)
    s = GameState.new_game()
    tm = TurnManager(s)
    s.eleven_power = 6
    for friend, ability in config.FRIEND_ABILITY.items():
        unlock(s, ability, friend)
    while not s.game_over:
        acts = legal_eleven_actions(s)
        action = rng.choice(acts)
        target = None
        if action == Action.USE_TELEPORT:
            target = teleport.best_safe_cell(s)
        assert tm.step(action, target=target)
        assert 0 <= s.eleven_hp <= config.MAX_HP
        assert 0 <= s.eleven_power <= config.MAX_POWER
        cells = [d.pos for d in s.living_demogorgons()] + [s.vecna.pos, s.eleven_pos]
        assert len(cells) == len(set(cells)), "two characters share a cell"
        assert s.turn <= config.MAX_TURNS
    assert s.winner in (Winner.ENEMIES, Winner.ELEVEN)