"""Single turn engine shared by Human-vs-AI and AI-vs-AI (only Eleven's controller differs).

The 14-step turn from the spec is laid out as explicit methods. The Mind Flayer phase asks its MCTS
controller (ai/mind_flayer_ai.py) for one action per turn once Will is rescued."""
from __future__ import annotations

from typing import List, Optional

import config
from abilities import radar, speed
from ai.demogorgon_ai import DemogorgonAI
from ai.metrics import Metrics
from ai.mind_flayer_ai import MindFlayerAI
from ai.radar_scan import RadarReading, scan
from ai.vecna_ai import VecnaAI
from game.actions import Action, MOVE_DELTAS
from game.board import Pos
from game.rules import apply_eleven_action, can_enemy_enter, check_win_loss, demogorgon_hit
from game.state import GameState, Phase
from game.mind_flayer_rules import apply_mf_action, is_acting
from game.vecna_rules import apply_vecna_action


class TurnManager:
    def __init__(self, state: GameState, metrics: Optional[Metrics] = None,
                 demogorgon_ai: Optional[DemogorgonAI] = None,
                 vecna_ai: Optional[VecnaAI] = None,
                 mind_flayer_ai: Optional[MindFlayerAI] = None):
        self.state = state
        self.metrics = metrics or Metrics()
        self.demogorgon_ai = demogorgon_ai or DemogorgonAI(self.metrics)
        self.vecna_ai = vecna_ai or VecnaAI(self.metrics)
        self.mind_flayer_ai = mind_flayer_ai or MindFlayerAI(self.metrics)
        self.radar_readings: List[RadarReading] = []   # current Radar report (empty when Radar is off)

    def can_bonus_move(self) -> bool:
        """True while Speed is active, i.e. Eleven may add a second move to this turn."""
        return speed.is_active(self.state) and config.SPEED_MOVES_PER_TURN > 1

    def step(self, eleven_action: Action, target: Optional[Pos] = None,
             bonus_action: Optional[Action] = None) -> bool:
        """Run one full turn. Returns False (and changes nothing) if Eleven's action is illegal.

        target:       destination cell, only for USE_TELEPORT (a human clicks it, the AI computes it).
        bonus_action: Speed's extra move. Only a MOVE_* after a MOVE_*, only while Speed is active.
                      The whole pair is validated on a clone first, so an illegal bonus changes nothing."""
        s = self.state
        if s.game_over:
            return False
        if not self._eleven_actions_valid(eleven_action, target, bonus_action):
            return False

        # 1-2. Eleven acts (movement, attack, rescue, ability); effects resolve immediately in rules
        s.phase = Phase.ELEVEN
        apply_eleven_action(s, eleven_action, target)
        if bonus_action is not None:
            apply_eleven_action(s, bonus_action)
        # 3. interactions: everything already resolved above; a dead Eleven ends the turn before enemies act
        self._resolve_eleven_interactions()

        if s.eleven_hp > 0:
            # 4-5. Demogorgons (A*)
            s.phase = Phase.DEMOGORGONS
            self._demogorgon_phase()
            # 6-8. Vecna (Minimax + Alpha-Beta)
            s.phase = Phase.VECNA
            self._vecna_phase()
            # 9-10. Mind Flayer (MCTS), only if active
            s.phase = Phase.MIND_FLAYER
            self._mind_flayer_phase()

        # 11-12. cooldowns, status effects, corruption timers
        s.phase = Phase.UPKEEP
        self._update_timers()
        self._update_radar()
        # 13. win / loss
        check_win_loss(s)
        # 14. advance counter
        if s.game_over:
            s.phase = Phase.GAME_OVER
        else:
            s.turn += 1
            s.phase = Phase.ELEVEN
        return True

    def _eleven_actions_valid(self, action: Action, target: Optional[Pos],
                              bonus_action: Optional[Action]) -> bool:
        """Dry run on a clone so an illegal action or bonus move never half-applies."""
        trial = self.state.clone()
        if not apply_eleven_action(trial, action, target):
            return False
        if bonus_action is None:
            return True
        if not (self.can_bonus_move() and action in MOVE_DELTAS and bonus_action in MOVE_DELTAS):
            return False
        return apply_eleven_action(trial, bonus_action)

    # ---- steps 9-10: Mind Flayer (MCTS) ----
    def _mind_flayer_phase(self) -> None:
        """Once awake (Will rescued) and not yet defeated, the Mind Flayer plans with a real MCTS on
        clones of the state, then corrupts a cell, summons a creature or waits on the live state."""
        s = self.state
        if s.eleven_hp <= 0 or not is_acting(s):
            return
        s.mind_flayer.known_eleven_pos = s.eleven_pos
        apply_mf_action(s, self.mind_flayer_ai.choose_action(s))

    # ---- step 3 ----
    def _resolve_eleven_interactions(self) -> None:
        """Rescue, attack, ability and hazard effects already resolved inside apply_eleven_action
        (so simulations share the rules). Nothing is left to do here yet."""

    # ---- Radar report (after the timers tick, so it shows for RADAR_DURATION turns) ----
    def _update_radar(self) -> None:
        """While Radar is active, run one real A* search per enemy; otherwise clear the report."""
        self.radar_readings = scan(self.state, self.metrics) if radar.is_active(self.state) else []

    # ---- steps 6-8: Vecna (Minimax + Alpha-Beta) ----
    def _vecna_phase(self) -> None:
        """Vecna plans with a real depth-limited Minimax search on clones of the state, then acts
        (move, hit or wait) on the live state. A frozen Vecna skips the turn and runs no search."""
        s = self.state
        if s.eleven_hp <= 0 or s.vecna.is_frozen:
            return
        action = self.vecna_ai.choose_action(s)
        apply_vecna_action(s, action)

    # ---- steps 4-5: Demogorgons (A*) ----
    def _demogorgon_phase(self) -> None:
        """Demogorgons act one at a time in id order, so each sees earlier moves (consistent
        collisions). Frozen ones skip. ATTACK hits Eleven unless the Demogorgon is on cooldown."""
        s = self.state
        for d in sorted(s.living_demogorgons(), key=lambda x: x.id):
            if d.is_frozen:
                continue
            action = self.demogorgon_ai.choose_action(s, d)
            if action in MOVE_DELTAS:
                dx, dy = MOVE_DELTAS[action]
                dest = (d.pos[0] + dx, d.pos[1] + dy)
                if can_enemy_enter(s, dest):
                    d.pos = dest
            elif action == Action.ATTACK:
                demogorgon_hit(s, d)
            if s.eleven_hp <= 0:
                break

    # ---- steps 11-12 ----
    def _update_timers(self) -> None:
        s = self.state
        s.status_effects = {k: v - 1 for k, v in s.status_effects.items() if v - 1 > 0}
        s.corrupted = {c: t - 1 for c, t in s.corrupted.items() if t - 1 > 0}
        for d in s.demogorgons:
            d.cooldown = max(0, d.cooldown - 1)
            d.frozen_turns = max(0, d.frozen_turns - 1)
        s.vecna.frozen_turns = max(0, s.vecna.frozen_turns - 1)
        s.mind_flayer.spawn_cooldown = max(0, s.mind_flayer.spawn_cooldown - 1)