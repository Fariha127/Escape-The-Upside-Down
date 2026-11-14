"""Keep the tests deterministic: the UI picks a new random seed per game and writes it to config.RNG_SEED,
so every test starts with the fixed seed and the default map; the original values are restored afterwards."""
import pytest

import config


@pytest.fixture(autouse=True)
def fixed_seed_for_tests():
    seed, per_game, rboard = config.RNG_SEED, config.RANDOM_SEED_PER_GAME, config.RANDOM_BOARD_PER_GAME
    config.RANDOM_SEED_PER_GAME = False
    config.RANDOM_BOARD_PER_GAME = False
    config.RNG_SEED = 42
    sound_on, config.SOUND_ENABLED = config.SOUND_ENABLED, False   # tests never play audio
    yield
    config.SOUND_ENABLED = sound_on
    config.RNG_SEED, config.RANDOM_SEED_PER_GAME, config.RANDOM_BOARD_PER_GAME = seed, per_game, rboard
