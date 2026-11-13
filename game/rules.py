"""Pure game rules for Eleven's actions. No rendering, no AI.

`apply_eleven_action` is the ONE place an Eleven action changes the state, so the live game, Minimax
and MCTS simulations all share exactly the same rules. Immediate effects (damage, power, rescue)
resolve inside it; the TurnManager then runs the environment checks of step 3."""
from __future__ import annotations
from typing import List, Optional

import config
from abilities import freeze, radar, speed, teleport
from characters import eleven as eleven_stats
from characters import friends as friend_rules
from characters import mind_flayer as mf_rules
from characters.demogorgon import Demogorgon, power_reward
from game.actions import Action, MOVE_DELTAS
from game.board import Terrain
from game.state import GameState, Pos


def move_target(state: GameState, action: Action) -> Pos:
    dx, dy = MOVE_DELTAS[action]
    return (state.eleven_pos[0] + dx, state.eleven_pos[1] + dy)


def portal_closed_to_eleven(state: GameState, p: Pos) -> bool:
    """The portal cell cannot be entered by Eleven until the Mind Flayer is defeated."""
    return p == state.portal_pos and not state.mind_flayer.defeated


def can_eleven_enter(state: GameState, p: Pos) -> bool:
    """Walls, map edges, corrupted cells, enemies and the still-closed portal are not enterable."""
    return (not state.is_blocked(p) and p not in state.enemy_positions()
            and not portal_closed_to_eleven(state, p))


def can_enemy_enter(state: GameState, p: Pos) -> bool:
    """Same collision rule for every enemy: no walls/corruption, no other character's cell."""
    return (not state.is_blocked(p) and p not in state.enemy_positions()
            and p != state.eleven_pos)


# ---------------- combat helpers ----------------
def damage_eleven(state: GameState, amount: int, source: str) -> int:
    """Single entry point for HP loss (Demogorgon, Vecna, hazard). Returns HP actually lost."""
    dealt = eleven_stats.take_damage(state, amount)
    if dealt:
        state.log(f"Eleven takes {dealt} damage from {source} (HP {state.eleven_hp})")
    return dealt


def demogorgon_hit(state: GameState, d: Demogorgon) -> bool:
    """A Demogorgon hits Eleven if it is allowed to. Cooldown is stored +1 because the upkeep step
    ticks it once at the end of this same turn, so the Demogorgon really skips DEMOGORGON_COOLDOWN
    following turns."""
    if not d.can_attack:
        return False
    damage_eleven(state, config.DEMOGORGON_DAMAGE, f"Demogorgon {d.id}")
    d.cooldown = config.DEMOGORGON_COOLDOWN + 1
    return True


def vecna_hit(state: GameState) -> bool:
    """Vecna's strike (used by his Phase 5 controller). Vecna is never killed or removed."""
    if state.vecna.is_frozen:
        return False
    damage_eleven(state, config.VECNA_DAMAGE, "Vecna")
    return True


def attack_target(state: GameState) -> Optional[Demogorgon]:
    """Demogorgon Eleven would hit: living, within ATTACK_RANGE, lowest id first."""
    near = [d for d in state.living_demogorgons()
            if abs(d.pos[0] - state.eleven_pos[0]) + abs(d.pos[1] - state.eleven_pos[1]) <= config.ATTACK_RANGE]
    return min(near, key=lambda d: d.id) if near else None


def can_attack(state: GameState) -> bool:
    return attack_target(state) is not None and state.eleven_power >= config.DEMOGORGON_ATTACK_COST


def do_attack(state: GameState) -> bool:
    """Cost 1 power, kill the target, gain its reward (+3 normal / 0 temporary), capped at MAX_POWER."""
    target = attack_target(state)
    if target is None or not eleven_stats.spend_power(state, config.DEMOGORGON_ATTACK_COST):
        return False
    target.alive = False
    gained = eleven_stats.gain_power(state, power_reward(target))
    state.log(f"Eleven defeats Demogorgon {target.id} (+{gained} power)")
    return True


def _enter_cell(state: GameState, p: Pos) -> None:
    """Move Eleven to p. Entering a hazard cell costs HAZARD_DAMAGE HP."""
    state.eleven_pos = p
    state.visited.add(p)
    if state.board.terrain_at(p) == Terrain.HAZARD:
        damage_eleven(state, config.HAZARD_DAMAGE, "a hazard")


# ---------------- legal actions ----------------
def legal_eleven_actions(state: GameState) -> List[Action]:
    """Only legal actions are returned. WAIT is always legal while the game is running."""
    if state.game_over:
        return []
    actions = [a for a in MOVE_DELTAS if can_eleven_enter(state, move_target(state, a))]
    if can_attack(state):
        actions.append(Action.ATTACK)
    if friend_rules.rescuable_friends(state):
        actions.append(Action.RESCUE)
    if "RADAR" in state.unlocked_abilities and state.ability_uses.get("RADAR", 0) > 0:
        actions.append(Action.USE_RADAR)
    if "SPEED" in state.unlocked_abilities and state.ability_uses.get("SPEED", 0) > 0 \
            and not speed.is_active(state):
        actions.append(Action.USE_SPEED)
    if "TELEPORT" in state.unlocked_abilities and state.ability_uses.get("TELEPORT", 0) > 0 \
            and teleport.safe_cells(state):
        actions.append(Action.USE_TELEPORT)
    if "FREEZE" in state.unlocked_abilities and state.ability_uses.get("FREEZE", 0) > 0:
        actions.append(Action.USE_FREEZE)
    if mf_rules.can_final_attack(state):
        actions.append(Action.FINAL_ATTACK)
    actions.append(Action.WAIT)
    return actions


def apply_eleven_action(state: GameState, action: Action, target: Optional[Pos] = None) -> bool:
    """Mutates `state` (callers pass a clone when simulating). Returns False if illegal.
    `target` is only used by USE_TELEPORT (the destination cell)."""
    if action not in legal_eleven_actions(state):
        return False
    if action in MOVE_DELTAS:
        _enter_cell(state, move_target(state, action))
    elif action == Action.ATTACK:
        return do_attack(state)
    elif action == Action.RESCUE:
        if not friend_rules.rescue_friend(state, friend_rules.rescuable_friends(state)[0]):
            return False
        gained = eleven_stats.gain_power(state, config.RESCUE_POWER_BONUS)
        state.log(f"Rescue bonus: +{gained} power")
        return True
    elif action == Action.USE_RADAR:
        return radar.use(state)
    elif action == Action.USE_SPEED:
        return speed.use(state)
    elif action == Action.USE_TELEPORT:
        return teleport.use(state, target)
    elif action == Action.USE_FREEZE:
        return freeze.use(state)
    elif action == Action.FINAL_ATTACK:
        return mf_rules.final_attack(state)
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