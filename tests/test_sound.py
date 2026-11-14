"""Sound effects: which sound belongs to which change, and that the tones are generated."""
import config
from game.state import GameState
from ui import sound
from ui.session import GameSession


def snap(**kw):
    base = dict(pos=(1, 1), hp=10, rescued=0, kills=0, mind_flayer_defeated=False, game_over=False, eleven_won=False)
    base.update(kw)
    return sound.Snapshot(**base)


def test_nothing_changed_makes_no_sound():
    assert sound.events_between(snap(), snap()) == []


def test_move_hit_rescue_attack():
    assert sound.events_between(snap(), snap(pos=(2, 1))) == ["move"]
    assert "hit" in sound.events_between(snap(), snap(hp=5))
    assert "rescue" in sound.events_between(snap(), snap(rescued=1))
    assert "attack" in sound.events_between(snap(), snap(kills=1))


def test_mind_flayer_defeat_and_game_end():
    assert "portal" in sound.events_between(snap(), snap(mind_flayer_defeated=True))
    assert sound.events_between(snap(), snap(game_over=True, eleven_won=True))[-1] == "win"
    assert sound.events_between(snap(), snap(game_over=True))[-1] == "lose"


def test_every_tone_renders_samples():
    for name in sound.TONES:
        data = sound.render(name)
        assert len(data) > 0 and len(data) % 2 == 0


def test_snapshot_reads_the_state():
    s = GameState.new_game()
    snp = sound.snapshot(s)
    assert snp.pos == s.eleven_pos and snp.hp == s.eleven_hp and not snp.game_over


def test_session_plays_without_an_audio_device(monkeypatch):
    monkeypatch.setattr(config, "SOUND_ENABLED", True)
    session = GameSession()
    monkeypatch.setattr(session.sound, "_start", lambda: False)    # pretend there is no sound card
    session.ai_one_turn()                                           # must not raise