import config
from characters import eleven, friends, mind_flayer
from characters.demogorgon import power_reward, spawn_temporary
from game.state import GameState


def fresh():
    return GameState.new_game()


# ---------- Eleven stats ----------
def test_damage_floors_at_zero():
    s = fresh()
    assert eleven.take_damage(s, 2) == 2 and s.eleven_hp == config.MAX_HP - 2
    assert eleven.take_damage(s, 99) == config.MAX_HP - 2 and s.eleven_hp == 0


def test_power_is_capped_and_spend_checked():
    s = fresh()
    s.eleven_power = 0
    assert eleven.gain_power(s, 99) == config.MAX_POWER and s.eleven_power == config.MAX_POWER
    assert eleven.gain_power(s, 5) == 0
    s.eleven_power = 0
    assert eleven.spend_power(s, 1) is False and s.eleven_power == 0
    s.eleven_power = 3
    assert eleven.spend_power(s, 1) and s.eleven_power == 2


# ---------- Friends / rescue ----------
def test_cannot_rescue_from_far_away():
    s = fresh()
    assert friends.can_rescue(s, "Dustin") is False
    assert friends.rescue_friend(s, "Dustin") is False and not s.rescued


def test_rescue_in_range_unlocks_ability_with_configured_uses():
    s = fresh()
    s.eleven_pos = (3, 7)                       # adjacent to Dustin at (2,7)
    assert friends.rescuable_friends(s) == ["Dustin"]
    assert friends.rescue_friend(s, "Dustin")
    assert "Dustin" in s.rescued and "RADAR" in s.unlocked_abilities
    assert s.ability_uses["RADAR"] == config.ABILITY_USES["RADAR"]
    assert friends.rescue_friend(s, "Dustin") is False          # no double rescue
    assert eleven.has_ability(s, "RADAR")
    s.ability_uses["RADAR"] = 0
    assert not eleven.has_ability(s, "RADAR")


def test_each_friend_maps_to_right_ability():
    assert {f: friends.ability_for(f) for f in friends.FRIEND_NAMES} == {
        "Mike": "TELEPORT", "Dustin": "RADAR", "Lucas": "SPEED", "Will": "FREEZE"}


def test_rescuing_other_friends_does_not_wake_mind_flayer():
    s = fresh(); s.eleven_pos = (3, 7)
    friends.rescue_friend(s, "Dustin")
    assert not s.mind_flayer.active


# ---------- Mind Flayer ----------
def test_rescuing_will_awakens_mind_flayer_with_eleven_location():
    s = fresh(); s.eleven_pos = (12, 11)        # next to Will at (13,11)
    assert friends.rescue_friend(s, "Will")
    assert s.mind_flayer.active and s.mind_flayer.known_eleven_pos == (12, 11)
    assert any("AWAKENED" in e for e in s.event_log)
    assert mind_flayer.activate(s) is False     # cannot awaken twice


def test_final_attack_requirements():
    s = fresh()
    assert not mind_flayer.can_final_attack(s)                      # inactive
    s.eleven_pos = (12, 11); friends.rescue_friend(s, "Will")
    s.eleven_power = config.FINAL_POWER_REQUIREMENT - 1
    assert not mind_flayer.can_final_attack(s) and mind_flayer.final_attack(s) is False
    assert not s.mind_flayer.defeated and not s.portal_active
    s.eleven_power = config.FINAL_POWER_REQUIREMENT + 1
    assert mind_flayer.final_attack(s)
    assert s.mind_flayer.defeated and s.portal_active and s.eleven_power == 1


def test_cannot_fight_mind_flayer_without_will_even_if_active():
    s = fresh(); s.mind_flayer.active = True; s.eleven_power = 10
    assert not mind_flayer.can_final_attack(s)


# ---------- Demogorgons ----------
def test_temporary_creatures_give_no_power_normal_give_reward():
    s = fresh()
    assert power_reward(s.demogorgons[0]) == config.DEMOGORGON_REWARD
    assert spawn_temporary(s, (2, 3))
    temp = s.demogorgons[-1]
    assert temp.temporary and power_reward(temp) == 0


def test_spawn_rejects_invalid_cells_and_respects_cap():
    s = fresh()
    assert not spawn_temporary(s, (0, 0))                   # wall
    assert not spawn_temporary(s, s.eleven_pos)             # Eleven's cell
    assert not spawn_temporary(s, s.demogorgons[0].pos)     # occupied
    s.corrupted[(2, 3)] = 2
    assert not spawn_temporary(s, (2, 3))                   # corrupted
    s.corrupted.clear()
    cells = [(1, 3), (2, 3), (3, 3)]
    for c in cells: assert spawn_temporary(s, c)
    assert not spawn_temporary(s, (4, 3))                   # cap reached
    assert sum(d.temporary for d in s.demogorgons) == config.MAX_TEMP_CREATURES


def test_demogorgon_attack_state():
    d = fresh().demogorgons[0]
    assert d.can_attack
    d.cooldown = 1; assert not d.can_attack
    d.cooldown = 0; d.frozen_turns = 2; assert not d.can_attack and d.is_frozen


def test_clone_keeps_character_flags_independent():
    s = fresh(); spawn_temporary(s, (2, 3)); s.vecna.frozen_turns = 2
    c = s.clone()
    c.demogorgons[-1].alive = False; c.vecna.frozen_turns = 0
    s.eleven_pos = (12, 11); friends.rescue_friend(s, "Will")
    assert s.demogorgons[-1].alive and s.vecna.frozen_turns == 2
    assert c.mind_flayer.active is False