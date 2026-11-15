"""The Gate opens when the Mind Flayer is defeated AND every friend is rescued, in either order."""
import config
from characters import friends, mind_flayer
from game import rules
from game.state import GameState


def ready_for_final_attack():
    s = GameState.new_game()
    s.rescued.add("Will")
    s.mind_flayer.active = True
    s.eleven_power = config.FINAL_POWER_REQUIREMENT
    return s


def test_defeating_the_mind_flayer_alone_does_not_open_the_gate():
    s = ready_for_final_attack()
    assert mind_flayer.final_attack(s)
    assert s.mind_flayer.defeated and not s.gate_active
    assert not rules.gate_is_open(s)
    assert "Rescue the remaining friends" in s.event_log[-1]


def test_last_rescue_opens_the_gate_after_the_mind_flayer_is_defeated():
    s = ready_for_final_attack()
    mind_flayer.final_attack(s)
    others = [n for n in s.friend_positions if n not in s.rescued]
    for name in others:
        s.eleven_pos = s.friend_positions[name]
        assert not s.gate_active
        assert friends.rescue_friend(s, name)
    assert s.gate_active and rules.gate_is_open(s)
    assert any("The Gate opens!" in line for line in s.event_log)


def test_final_attack_opens_the_gate_when_all_friends_are_already_rescued():
    s = ready_for_final_attack()
    s.rescued.update(s.friend_positions)
    assert mind_flayer.final_attack(s)
    assert s.gate_active and rules.gate_is_open(s)


def test_gate_flag_survives_a_clone():
    s = ready_for_final_attack()
    s.rescued.update(s.friend_positions)
    mind_flayer.final_attack(s)
    assert s.clone().gate_active