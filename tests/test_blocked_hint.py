"""The hint a human sees when every arrow key is rejected (Eleven boxed in by a corrupted cell and Vecna)."""
import config
from game.actions import MOVE_DELTAS
from game.rules import legal_eleven_actions
from game.state import GameState
from ui.session import blocked_hint


def boxed_in():
    s = GameState.new_game()
    for d in s.demogorgons:
        d.alive = False
    s.eleven_pos = (1, 1)
    s.vecna.pos = (1, 2)                                   # one exit: Vecna stands on it
    s.corrupted = {(2, 1): config.MF_CORRUPT_DURATION + 1}  # the other exit: corrupted
    return s


def test_hint_appears_when_eleven_cannot_move_and_mentions_space():
    s = boxed_in()
    assert not [a for a in legal_eleven_actions(s) if a in MOVE_DELTAS]
    hint = blocked_hint(s)
    assert hint.startswith("Blocked") and "Space" in hint and "3 freeze" in hint


def test_hint_is_empty_when_a_move_exists():
    s = boxed_in()
    s.vecna.pos = (5, 5)                                   # her exit is free again
    assert blocked_hint(s) == ""


def test_hint_drops_used_abilities_and_never_changes_the_state():
    s = boxed_in()
    s.ability_uses = {k: 0 for k in s.ability_uses}
    before = (s.eleven_pos, dict(s.corrupted), s.turn, len(s.event_log))
    hint = blocked_hint(s)
    assert "freeze" not in hint and "teleport" not in hint and "Space" in hint
    assert before == (s.eleven_pos, dict(s.corrupted), s.turn, len(s.event_log))