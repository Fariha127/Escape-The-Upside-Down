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
    assert "gate" in sound.events_between(snap(), snap(mind_flayer_defeated=True))
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
    session.ai_one_turn()  
    

def test_mind_flayer_waking_has_its_own_sound():
    assert "mind_flayer" in sound.events_between(snap(), snap(mind_flayer_awake=True))
    assert "mind_flayer" not in sound.events_between(snap(mind_flayer_awake=True), snap(mind_flayer_awake=True))                                         # must not raise



def test_each_hit_source_has_its_own_sound():
    assert sound.hit_sounds(["[T3] Eleven takes 1 damage from Demogorgon 2 (HP 4)"]) == ["hit_demogorgon"]
    assert sound.hit_sounds(["[T3] Eleven takes 2 damage from Vecna (HP 3)"]) == ["hit_vecna"]
    assert sound.hit_sounds(["[T3] Eleven takes 1 damage from a hazard (HP 4)"]) == ["hit"]
    both = ["[T3] Eleven takes 1 damage from Demogorgon 2 (HP 4)", "[T3] Eleven takes 2 damage from Vecna (HP 2)"]
    assert sound.hit_sounds(both) == ["hit_demogorgon", "hit_vecna"]           # Vecna last = the one played
    assert sound.events_between(snap(), snap(hp=5), ["[T1] Eleven takes 2 damage from Vecna (HP 5)"]) == ["hit_vecna"]


def test_all_sounds_are_different_tones():
    tones = {n: tuple(sound.TONES[n]) for n in ("attack", "rescue", "hit", "hit_demogorgon", "hit_vecna", "win", "lose")}
    assert len(set(tones.values())) == len(tones)


def test_a_wav_file_replaces_the_generated_tone(tmp_path, monkeypatch):
    import array
    import wave
    monkeypatch.setattr(sound, "SOUND_DIR", tmp_path)
    with wave.open(str(tmp_path / "rescue.wav"), "wb") as w:                  # 5 s, stereo, 44.1 kHz
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(array.array("h", [8000, 8000] * (44100 * 5)).tobytes())
    data = sound.render("rescue")
    seconds = len(data) / 2 / config.SOUND_SAMPLE_RATE
    assert abs(seconds - config.SOUND_FILE_MAX_SECONDS) < 0.05                # cut to the maximum length
    samples = array.array("h", data)
    assert abs(samples[-1]) < abs(samples[len(samples) // 2])                  # fades out at the end


def test_missing_or_broken_wav_keeps_the_generated_tone(tmp_path, monkeypatch):
    monkeypatch.setattr(sound, "SOUND_DIR", tmp_path)
    (tmp_path / "attack.wav").write_bytes(b"not a wav file")
    assert sound.render("attack") == sound.render("attack")
    assert len(sound.render("attack")) == 2 * int(config.SOUND_SAMPLE_RATE * 0.05) + 2 * int(config.SOUND_SAMPLE_RATE * 0.08)