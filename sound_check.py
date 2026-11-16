import time
import pygame
import config
from ui import sound

print("SOUND_ENABLED:", config.SOUND_ENABLED, " volume:", config.SOUND_VOLUME)
pygame.mixer.init(frequency=config.SOUND_SAMPLE_RATE, size=-16, channels=1)
print("mixer started:", pygame.mixer.get_init())
for name in list(sound.TONES):
    try:
        data = sound.render(name)
        pygame.mixer.Sound(buffer=data)
        print("ok  ", name, len(data) // 2 / config.SOUND_SAMPLE_RATE, "s", "(file)" if (sound.SOUND_DIR / f"{name}.wav").is_file() else "(tone)")
    except Exception as err:
        print("FAIL", name, type(err).__name__, err)
print("playing the Mind Flayer sound now ...")
pygame.mixer.Sound(buffer=sound.render("mind_flayer")).play()
time.sleep(3.5)
print("done")