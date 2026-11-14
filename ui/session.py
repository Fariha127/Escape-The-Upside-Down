"""One running game (Human vs AI or AI vs AI): input handling, the AI-vs-AI clock and the overlay data.

The GameSession never draws. It owns the GameState / TurnManager / ElevenAI and only changes the game
through TurnManager.step, exactly like the old main loop did. Human and AI turns use the same engine."""
from __future__ import annotations
import random
from typing import Dict, List, Optional, Tuple

import pygame

import config
from abilities import teleport
from ai.eleven_ai import ElevenAI
from game import rules
from game.actions import Action, MOVE_DELTAS
from game.board import Pos
from game.board_gen import generate_board
from game.state import GameState
from game.turn_manager import TurnManager
from ui import animation, game_screen, sound


FIXED_SEED = config.RNG_SEED          # the seed used when RANDOM_SEED_PER_GAME is off
SEED_RANGE = 1_000_000


def pick_seed() -> int:
    """Seed for a new game: a fresh one, or the fixed one when the setting is off. The AIs read
    config.RNG_SEED at search time, so setting it here makes the whole game reproducible from the number."""
    return random.randrange(SEED_RANGE) if config.RANDOM_SEED_PER_GAME else FIXED_SEED


def new_game(board=None) -> Tuple[GameState, TurnManager, ElevenAI]:
    """A fresh game (default map unless a board is given). The AI shares the turn manager's Metrics
    so its searches are recorded."""
    state = GameState.new_game(board)
    tm = TurnManager(state)
    return state, tm, ElevenAI(tm.metrics)


def ai_turn(state: GameState, tm: TurnManager, ai: ElevenAI) -> None:
    """Let Eleven's AI play one full turn (MCTS picks the goal when needed, A* walks)."""
    choice = ai.choose_turn(state)
    if not tm.step(choice.action, choice.target, choice.bonus_action):
        if not tm.step(choice.action, choice.target):     # drop an illegal Speed bonus
            tm.step(Action.WAIT)                          # never stall the game


class GameSession:
    """State of one play-through plus the UI-side flags (pause, speed, paths, teleport picking)."""

    def __init__(self, ai_mode: bool = False):
        self.ai_mode = ai_mode                 # True: Eleven is played by the AI (AI vs AI)
        self.show_paths = ai_mode              # A* paths + Vecna's last choice (P toggles)
        self.paused = False
        self.speed_idx = config.AI_SPEEDS.index(1) if 1 in config.AI_SPEEDS else 0
        self.message = ""
        self.request: Optional[str] = None     # "menu" / "results" -> the screen manager reacts
        self.game_over_at: Optional[int] = None
        self._last_ai_tick = 0
        self.sound = sound.SoundPlayer()
        self.animator = animation.Animator()
        self.restart()

    # ------------------------------------------------------------------ lifecycle
    def restart(self) -> None:
        self.seed = pick_seed()
        config.RNG_SEED = self.seed
        board = generate_board(self.seed) if config.RANDOM_BOARD_PER_GAME else None   # same seed -> same board
        self.state, self.tm, self.ai = new_game(board)
        self.picking_teleport = False          # waiting for the human to click a destination
        self.pending_first_move: Optional[Action] = None   # Speed: first move chosen, waiting for the second
        self.message = ""
        self.request = None
        self.game_over_at = None
        self.vecna_last: Optional[dict] = None  # Vecna's last real Minimax choice (None if he did not search)
        self.log_offset = 0                    # event log: lines scrolled back from the newest (0 = following)
        self._log_len = 0
        self._last_ai_tick = pygame.time.get_ticks()

    @property
    def speed(self) -> float:
        return config.AI_SPEEDS[self.speed_idx]

    # ------------------------------------------------------------------ playing turns
    def _play(self, fn) -> bool:
        """Run one or more engine steps and remember Vecna's search if he made one this turn."""
        mm = self.tm.metrics.minimax
        calls, before = mm.calls, self.state.vecna.pos
        before_snap = sound.snapshot(self.state)
        ok = fn()
        self.sound.play(sound.events_between(before_snap, sound.snapshot(self.state)))
        if mm.calls > calls:
            self.vecna_last = {"from": before, "to": self.state.vecna.pos, "action": mm.last.action,
                               "score": mm.last.score}
        elif ok is not False and self.state.turn:   # a turn passed without a Vecna search (frozen / game over)
            self.vecna_last = None
        self._follow_log()
        if self.state.game_over and self.game_over_at is None:
            self.game_over_at = pygame.time.get_ticks()
            self.picking_teleport, self.pending_first_move = False, None
        return ok is not False

    # ------------------------------------------------------------------ event log scrolling
    def log_capacity(self) -> int:
        return game_screen.log_capacity(self.state, game_screen.window_size(self.state)[1])

    def _follow_log(self) -> None:
        """New events arrive: if the player scrolled back, keep the same lines on screen."""
        n = len(self.state.event_log)
        if self.log_offset > 0:
            self.log_offset += n - self._log_len
        self._log_len = n
        self.scroll_log(0)

    def scroll_log(self, lines: int) -> None:
        """Scroll the event log back (+) or forward (-); 0 only re-clamps. Never changes the game."""
        most = max(0, len(self.state.event_log) - self.log_capacity())
        self.log_offset = min(max(0, self.log_offset + lines), most)

    def human_step(self, action: Action, target: Optional[Pos] = None,
                   bonus: Optional[Action] = None) -> bool:
        return self._play(lambda: self.tm.step(action, target, bonus))

    def ai_one_turn(self) -> None:
        self.picking_teleport, self.pending_first_move = False, None
        self._play(lambda: ai_turn(self.state, self.tm, self.ai))

    def update(self, now_ms: int) -> None:
        """AI-vs-AI clock: one AI turn every AI_TURN_DELAY_MS / speed."""
        if self.ai_mode and not self.paused and not self.state.game_over:
            if now_ms - self._last_ai_tick >= config.AI_TURN_DELAY_MS / self.speed:
                self.ai_one_turn()
                self._last_ai_tick = now_ms

    # ------------------------------------------------------------------ on-screen commands (buttons)
    def command(self, cmd: str) -> None:
        if cmd == "menu":
            self.request = "menu"
        elif cmd == "restart":
            self.restart()
        elif cmd == "paths":
            self.show_paths = not self.show_paths
        elif cmd == "toggle_ai":
            self.ai_mode = not self.ai_mode
            self.picking_teleport, self.pending_first_move = False, None
            self.paused, self._last_ai_tick = False, pygame.time.get_ticks()
            self.message = "AI-vs-AI ON" if self.ai_mode else "Human control"
        elif cmd == "results":
            if self.state.game_over:
                self.request = "results"
        elif self.state.game_over:
            return
        elif cmd == "step":
            self.ai_one_turn()
        elif cmd == "pause" and self.ai_mode:
            self.paused = not self.paused
            self._last_ai_tick = pygame.time.get_ticks()
        elif cmd == "faster":
            self.speed_idx = min(len(config.AI_SPEEDS) - 1, self.speed_idx + 1)
        elif cmd == "slower":
            self.speed_idx = max(0, self.speed_idx - 1)

    # ------------------------------------------------------------------ events
    def handle_event(self, e: pygame.event.Event) -> None:
        s, tm = self.state, self.tm
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.picking_teleport and not s.game_over:
            cell = game_screen.cell_at(s, e.pos)
            if cell is not None and cell in teleport.safe_cells(s):
                self.human_step(Action.USE_TELEPORT, cell)
                self.picking_teleport, self.message = False, ""
            elif cell is not None:
                self.message = "Not a valid Teleport cell - click a highlighted cell or press Esc"
            return
        if e.type != pygame.KEYDOWN:
            return
        key = e.key
        if key == pygame.K_r:
            self.restart()
        elif key == pygame.K_p:
            self.show_paths = not self.show_paths
        elif key == pygame.K_m:
            self.request = "menu"
        elif key == pygame.K_PAGEUP:
            self.scroll_log(max(1, self.log_capacity() - 1))
        elif key == pygame.K_PAGEDOWN:
            self.scroll_log(-max(1, self.log_capacity() - 1))
        elif key == pygame.K_END:
            self.log_offset = 0
        elif key == pygame.K_ESCAPE:
            self.picking_teleport, self.pending_first_move, self.message = False, None, ""
        elif key == pygame.K_t:
            self.command("toggle_ai")
        elif s.game_over:
            if key == pygame.K_RETURN:
                self.request = "results"
        elif key == pygame.K_n:                                 # the AI plays one turn
            self.ai_one_turn()
        elif self.ai_mode:
            if key == pygame.K_SPACE:
                self.command("pause")
            elif key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                self.command("faster")
            elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                self.command("slower")
        elif self.picking_teleport:
            self.message = "Click a highlighted cell to teleport (Esc cancels)"
        elif self.pending_first_move is not None:               # Speed: choose the second move
            second = game_screen.KEYMAP.get(key)
            if second in MOVE_DELTAS:
                if self.human_step(self.pending_first_move, bonus=second):
                    self.pending_first_move, self.message = None, ""
                else:
                    self.message = "Second move blocked - pick another direction or Space to skip"
            elif second == Action.WAIT:
                self.human_step(self.pending_first_move)
                self.pending_first_move, self.message = None, ""
        elif key in game_screen.ACTION_KEYS:
            action = game_screen.ACTION_KEYS[key]
            if action == Action.USE_TELEPORT:
                if action in rules.legal_eleven_actions(s):
                    self.picking_teleport, self.message = True, "Click a highlighted cell to teleport (Esc cancels)"
                else:
                    self.message = "Teleport unavailable (needs Mike rescued and a safe visited cell)"
            elif not self.human_step(action):
                self.message = f"{action.value} is not possible right now"
            else:
                self.message = ""
        elif key in game_screen.KEYMAP:
            action = game_screen.KEYMAP[key]
            if action in MOVE_DELTAS and tm.can_bonus_move() and action in rules.legal_eleven_actions(s):
                self.pending_first_move, self.message = action, "Speed: pick the second move (Space = skip)"             
            elif self.human_step(action):
                self.message = ""
            elif action in MOVE_DELTAS and rules.portal_closed_to_eleven(s, rules.move_target(s, action)):
                self.message = "The portal is closed - defeat the Mind Flayer first"
            # other illegal moves are ignored

    # ------------------------------------------------------------------ what the renderer shows
    def status_text(self) -> str:
        if self.ai_mode:
            return f"AI-vs-AI {self.speed}x" + (" PAUSED" if self.paused else "")
        return "Human vs AI"

    def overlay(self) -> Dict:
        """Everything the renderer needs besides the state. Every value is read from a real run."""
        o: Dict = {"message": self.message, "radar": self.tm.radar_readings,
                   "status": self.status_text(), "show_paths": self.show_paths,
                   "ai_mode": self.ai_mode, "seed": self.seed, "log_offset": self.log_offset}
        now = pygame.time.get_ticks()
        self.animator.update(self.state, now, animation.slide_duration_ms(self.ai_mode, self.speed))
        o["anim"], o["now"] = self.animator, now
        ai = self.ai
        if ai.run is not None and not self.state.game_over:
            o["goal"] = ai.run.goal.label
            if ai.run.target is not None:
                o["goal_target"] = ai.run.target
        if self.picking_teleport:
            o["teleport_cells"] = teleport.safe_cells(self.state)
        if self.show_paths:
            o["demogorgon_paths"] = self.tm.demogorgon_ai.current_paths(self.state)
            if ai.nav.last_result:
                o["eleven_path"] = ai.nav.last_result.path
            if self.vecna_last:
                o["vecna_choice"] = self.vecna_last
        return o
