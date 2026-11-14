import pygame
import os

class SoundManager:
    def __init__(self):
        self.enabled = True
        self.sounds = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
        except Exception as e:
            print(f"Audio init warning: {e}")
            self.enabled = False
            
    def _load_sound(self, rel_path: str):
        if not self.enabled or rel_path in self.sounds:
            return self.sounds.get(rel_path)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(base_dir, rel_path)
        if os.path.exists(full_path):
            try:
                snd = pygame.mixer.Sound(full_path)
                snd.set_volume(0.6)
                self.sounds[rel_path] = snd
                return snd
            except Exception as e:
                print(f"Could not load sound {full_path}: {e}")
        return None

    def play(self, name: str):
        if not self.enabled:
            return
        sound_map = {
            "click": "resources/sounds/ui_click_01.ogg",
            "menu_open": "resources/sounds/ui_click_06.ogg",
            "back": "resources/sounds/ui_click_03.ogg",
            "button_down": "resources/sounds/shell_button_down.ogg",
            "button_up": "resources/sounds/shell_button_up.ogg",
            "button": "resources/sounds/shell_button_down.ogg",
            "eat": "resources/sounds/eat.ogg",
            "jump": "resources/sounds/jump.ogg",
            "cheer": "resources/sounds/cheer.ogg",
            "cheer_success": "resources/sounds/cheer_success.ogg",
            "sad": "resources/sounds/sad.ogg",
            "angry": "resources/sounds/angry.ogg",
            "shock": "resources/sounds/shock.ogg",
            "blush": "resources/sounds/blush.ogg",
            "refuse": "resources/sounds/refuse.ogg",
            "clean": "resources/sounds/swoosh_01.ogg",
            "complete": "resources/sounds/task_complete.ogg",
            "hatch": "resources/sounds/task_complete_02.ogg",
        }
        rel_path = sound_map.get(name, name)
        if rel_path:
            snd = self._load_sound(rel_path)
            if snd:
                try:
                    snd.play()
                except Exception:
                    pass
