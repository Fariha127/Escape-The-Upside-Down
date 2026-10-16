"""Single turn engine shared by Human-vs-AI and AI-vs-AI (only Eleven's controller differs).

The 14-step turn from the spec is laid out as explicit methods. Steps whose features arrive in
later phases are clearly marked placeholders that do nothing yet (no fake behaviour)."""
from __future__ import annotations

from game.actions import Action
from game.rules import apply_eleven_action, check_win_loss
from game.state import GameState, Phase


class TurnManager:
    def __init__(self, state: GameState):
        self.state = state

    def step(self, eleven_action: Action) -> bool:
        """Run one full turn. Returns False (and changes nothing) if Eleven's action is illegal."""
        s = self.state
        if s.game_over:
            return False

        # 1-2. Eleven acts
        s.phase = Phase.ELEVEN
        if not apply_eleven_action(s, eleven_action):
            return False
        # 3. rescue / combat / interactions            -> Phase 4
        self._resolve_eleven_interactions()

        # 4-5. Demogorgons (A*)                        -> Phase 3
        s.phase = Phase.DEMOGORGONS
        self._demogorgon_phase()
        # 6-8. Vecna (Minimax + Alpha-Beta)            -> Phase 5
        s.phase = Phase.VECNA
        self._vecna_phase()
        # 9-10. Mind Flayer (MCTS), only if active     -> Phase 7
        s.phase = Phase.MIND_FLAYER
        self._mind_flayer_phase()

        # 11-12. cooldowns, status effects, corruption timers
        s.phase = Phase.UPKEEP
        self._update_timers()
        # 13. win / loss
        check_win_loss(s)
        # 14. advance counter
        if s.game_over:
            s.phase = Phase.GAME_OVER
        else:
            s.turn += 1
            s.phase = Phase.ELEVEN
        return True

    # ---- placeholders (implemented in later phases) ----
    def _resolve_eleven_interactions(self) -> None: pass
    def _demogorgon_phase(self) -> None: pass
    def _vecna_phase(self) -> None: pass
    def _mind_flayer_phase(self) -> None: pass

    # ---- implemented now ----
    def _update_timers(self) -> None:
        s = self.state
        s.status_effects = {k: v - 1 for k, v in s.status_effects.items() if v - 1 > 0}
        s.corrupted = {c: t - 1 for c, t in s.corrupted.items() if t - 1 > 0}
        for d in s.demogorgons:
            d.cooldown = max(0, d.cooldown - 1)
            d.frozen_turns = max(0, d.frozen_turns - 1)
        s.vecna.frozen_turns = max(0, s.vecna.frozen_turns - 1)
