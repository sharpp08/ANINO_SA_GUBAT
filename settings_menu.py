"""Atmospheric, keyboard-and-mouse settings screen for ANINO SA GUBAT."""
import math
import pygame
import settings as cfg


class SettingsMenu:
    CATEGORIES = ("VIDEO", "AUDIO", "CONTROLS", "GAMEPLAY", "ACCESSIBILITY", "BACK")
    RED = (133, 30, 29)
    PALE = (220, 215, 198)
    MUTED = (139, 139, 128)

    def __init__(self, initial=None):
        self.values = cfg.load_settings()
        if initial:
            self.values.update(initial)
        self.category = 0
        self.row = 0
        self.dirty = False
        self.notice = ""
        self.notice_until = 0
        self.waiting_for_key = None
        self.previous_values = dict(self.values)
        self.rows = self._build_rows()

    def _build_rows(self):
        return {
            "VIDEO": [
                ("Fullscreen", "fullscreen", "toggle", None), ("VSync", "vsync", "toggle", None),
                ("Resolution", "resolution", "choice", ["1280 x 720", "1600 x 900", "1920 x 1080"]),
                ("Preset Quality", "quality_tier", "choice", ["low", "medium", "high"]),
                ("FPS Limit", "fps_limit", "choice", ["30", "45", "60", "90", "120", "unlimited"]),
                ("Brightness", "brightness", "slider", (50, 150)), ("Field of View", "fov", "slider", (60, 100)),
                ("Fog Effects", "enable_fog", "toggle", None), ("Particles", "enable_particles", "toggle", None),
            ],
            "AUDIO": [
                ("Master Volume", "master_volume", "volume", (0, 100)), ("Music Volume", "music_volume", "volume", (0, 100)),
                ("Sound Effects", "sfx_volume", "volume", (0, 100)), ("Ambient Volume", "ambient_volume", "volume", (0, 100)),
                ("Enemy Sounds", "enemy_volume", "volume", (0, 100)),
            ],
            "CONTROLS": [
                ("Move Forward", "forward", "bind", None), ("Move Backward", "backward", "bind", None),
                ("Move Left", "strafe_left", "bind", None), ("Move Right", "strafe_right", "bind", None),
                ("Interact", "interact", "bind", None), ("Sprint", "sprint", "bind", None),
                ("Crouch", "crouch", "bind", None), ("Flashlight", "flashlight", "bind", None),
                ("Reload", "reload", "bind", None), ("Use Salt", "salt", "bind", None),
                ("Use Garlic", "garlic", "bind", None), ("Use Rosary", "rosary", "bind", None),
                ("Use Cross", "cross", "bind", None), ("Ward Menu", "ward_menu", "bind", None),
                ("Ward Slot 1", "ward_1", "bind", None), ("Ward Slot 2", "ward_2", "bind", None),
                ("Ward Slot 3", "ward_3", "bind", None), ("Ward Slot 4", "ward_4", "bind", None),
                ("Ward Slot 5", "ward_5", "bind", None), ("Pause", "pause", "bind", None),
                ("Mouse Sensitivity", "mouse_sensitivity", "slider", (10, 100)),
                ("Invert Mouse Y", "invert_mouse_y", "toggle", None), ("Reset Controls", "reset_controls", "action", None),
            ],
            "GAMEPLAY": [
                ("Sanity System", "enable_sanity", "toggle", None), ("Camera Shake", "enable_camera_shake", "toggle", None),
                ("Sprint Behavior", "sprint_toggle", "choice", ["hold", "toggle"]),
                ("Crouch Behavior", "crouch_toggle", "choice", ["hold", "toggle"]), ("HUD Visibility", "hud_visible", "toggle", None),
            ],
            "ACCESSIBILITY": [
                ("High Contrast UI", "high_contrast_ui", "toggle", None), ("Reduce Camera Shake", "reduce_camera_shake", "toggle", None),
                ("Reduce Flashing", "reduce_flashing", "toggle", None), ("UI Scale", "ui_scale", "choice", ["90%", "100%", "110%", "125%", "150%"]),
            ],
        }

    def _category(self):
        return self.CATEGORIES[self.category]

    def _items(self):
        return self.rows.get(self._category(), [])

    def _value(self, key, kind):
        if key in ("forward", "backward", "strafe_left", "strafe_right", "interact",
                   "sprint", "crouch", "flashlight", "reload", "salt", "garlic",
                   "rosary", "cross", "ward_menu", "ward_1", "ward_2", "ward_3", "ward_4", "ward_5", "pause"):
            return self.values.get("controls", cfg.CONTROLS).get(key, cfg.CONTROLS.get(key, ""))
        value = self.values.get(key)
        if value is None:
            defaults = {
                "master_volume": 70, "music_volume": 40, "sfx_volume": 80,
                "ambient_volume": 70, "enemy_volume": 80, "ui_volume": 70,
                "mouse_sensitivity": 50, "brightness": 55, "fov": 80,
                "fps_limit": "60", "quality_tier": "medium", "resolution": "1280 x 720",
                "texture_quality": "medium", "anti_aliasing": "FXAA", "anisotropic": "8x",
                "shadow_quality": "medium", "shadow_resolution": "medium",
                "brightness": 100, "fov": 75, "fps_limit": "60",
                "ambient_volume": 70, "enemy_volume": 80, "ui_scale": "100%",
            }
            return defaults.get(key, False if kind == "toggle" else "")
        if kind in ("volume",):
            return round(float(value) * 100) if isinstance(value, (int, float)) and value <= 1 else int(value)
        if key == "mouse_sensitivity" and isinstance(value, (int, float)) and value < 1:
            return max(10, min(100, round(value / 0.002 * 50)))
        if key == "brightness" and isinstance(value, (int, float)) and value <= 2:
            return round(value * 100)
        return value

    def _set_value(self, key, value):
        if key in ("forward", "backward", "strafe_left", "strafe_right", "interact",
                   "sprint", "crouch", "flashlight", "reload", "salt", "garlic",
                   "rosary", "cross", "ward_menu", "ward_1", "ward_2", "ward_3", "ward_4", "ward_5"):
            controls = dict(self.values.get("controls", cfg.DEFAULT_CONTROLS))
            controls[key] = value
            self.values["controls"] = controls
        elif key in ("master_volume", "music_volume", "sfx_volume", "ambient_volume", "enemy_volume", "ui_volume"):
            self.values[key] = value / 100.0
        elif key == "mouse_sensitivity":
            self.values[key] = value / 50.0 * 0.002
        elif key == "brightness":
            self.values[key] = value / 100.0
        else:
            self.values[key] = value
        self.dirty = True

    def _change(self, direction):
        items = self._items()
        if not items:
            return
        label, key, kind, data = items[self.row]
        current = self._value(key, kind)
        if kind == "toggle":
            self._set_value(key, not bool(current))
        elif kind in ("choice",):
            choices = data
            try:
                index = choices.index(str(current).lower() if key in ("quality_tier", "difficulty", "enemy_aggression", "enemy_spawn_rate", "subtitle_size", "colorblind_mode") else current)
            except ValueError:
                index = 0
            self._set_value(key, choices[(index + direction) % len(choices)])
        elif kind in ("slider", "volume"):
            low, high = data
            step = 1 if high <= 100 else 5
            self._set_value(key, max(low, min(high, int(current) + direction * step)))
        elif kind == "action":
            self.values["controls"] = dict(cfg.DEFAULT_CONTROLS)
            self.dirty = True
            self._message("Controls reset")

    def _message(self, text):
        self.notice = text
        self.notice_until = pygame.time.get_ticks() + 1800

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if self.waiting_for_key:
                action = self.waiting_for_key
                self.waiting_for_key = None
                if event.key != pygame.K_ESCAPE:
                    name = pygame.key.name(event.key)
                    controls = self.values.get("controls", cfg.CONTROLS)
                    conflict = next((other for other, bound in controls.items()
                                     if other != action and bound == name), None)
                    if conflict:
                        self._message(f"Already assigned to {conflict.upper()}")
                    else:
                        self._set_value(action, name)
                return "stay"
            if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                return "back"
            if event.key == pygame.K_F5:
                return "apply"
            if event.key == pygame.K_F6:
                self.values = self._default_values()
                self.dirty = True
                self.waiting_for_key = None
                self._message("Defaults restored • press F5 to keep")
            elif event.key in (pygame.K_UP, pygame.K_w):
                self.row = (self.row - 1) % max(1, len(self._items()))
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.row = (self.row + 1) % max(1, len(self._items()))
            elif event.key in (pygame.K_LEFT, pygame.K_a):
                self._change(-1)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self._change(1)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                items = self._items()
                if items:
                    _, key, kind, _ = items[self.row]
                    if kind == "bind":
                        self.waiting_for_key = key
                        self._message("Press a key to bind • ESC cancels")
                    elif kind in ("toggle", "action"):
                        self._change(1)
                    elif kind in ("choice", "slider", "volume"):
                        self._change(1)
            elif event.key == pygame.K_TAB:
                self.category = (self.category + 1) % (len(self.CATEGORIES) - 1)
                self.row = 0
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            # Coordinates are supplied in internal-surface space by the game.
            if mx < 150 and 112 <= my <= 286:
                index = int((my - 112) // 29)
                if 0 <= index < len(self.CATEGORIES):
                    if self.CATEGORIES[index] == "BACK":
                        return "back"
                    self.category = index
                    self.row = 0
            elif mx >= 300 and 82 <= my <= 298:
                index = int((my - 82) // 18)
                if 0 <= index < len(self._items()):
                    visible_start = max(0, min(self.row - 10, max(0, len(self._items()) - 12)))
                    self.row = visible_start + index
                    _, key, kind, _ = self._items()[self.row]
                    if kind == "bind":
                        self.waiting_for_key = key
                        self._message("Press a key to bind • ESC cancels")
                    else:
                        self._change(1)
            elif my > 320 and mx >= 520:
                return "apply"
            elif my > 320 and 300 <= mx < 520:
                self.values = self._default_values()
                self.dirty = True
                self.waiting_for_key = None
                self._message("Defaults restored • press APPLY to keep")
            elif my > 320 and mx < 300:
                return "back"
        return "stay"

    def _default_values(self):
        defaults = cfg.load_settings(path="__anino_defaults_missing__.json")
        defaults.update({
            "fullscreen": cfg.FULLSCREEN, "vsync": True, "resolution": "1280 x 720",
            "quality_tier": "medium", "fps_limit": "60", "brightness": 1.0, "fov": 75,
            "master_volume": cfg.MASTER_VOLUME, "music_volume": cfg.MUSIC_VOLUME,
            "sfx_volume": cfg.SFX_VOLUME, "ambient_volume": 0.7, "enemy_volume": 0.8,
            "enable_fog": True, "enable_particles": True, "enable_sanity": True,
            "enable_camera_shake": True, "mouse_sensitivity": cfg.PLAYER_ROT_SPEED,
            "invert_mouse_y": False, "sprint_toggle": "hold", "crouch_toggle": "hold",
            "hud_visible": True, "high_contrast_ui": False, "reduce_camera_shake": False,
            "reduce_flashing": False, "ui_scale": "100%", "controls": dict(cfg.DEFAULT_CONTROLS),
        })
        return defaults

    def apply(self, on_apply=None):
        cfg.CONTROLS.update(self.values.get("controls", {}))
        cfg.save_settings(self.values)
        self.previous_values = dict(self.values)
        self.dirty = False
        if on_apply:
            on_apply(self.values)
        self._message("Settings applied")

    def draw(self, surf, font_lg, font_sm, font_tiny):
        sw, sh = surf.get_size()
        high_contrast = bool(self.values.get("high_contrast_ui", False))
        text_color = (255, 255, 255) if high_contrast else self.PALE
        muted_color = (205, 205, 205) if high_contrast else (160, 161, 153)
        t = pygame.time.get_ticks() / 1000.0
        # Foggy forest treatment with a charcoal veil.
        surf.fill((9, 14, 17))
        for i in range(8):
            y = int(sh * (.28 + i * .085) + math.sin(t * .24 + i) * 5)
            fog = pygame.Surface((sw, 24), pygame.SRCALPHA)
            pygame.draw.ellipse(fog, (112, 126, 125, 13), (-35, 0, sw + 70, 24))
            surf.blit(fog, (0, y))
        for side in (0, 1):
            x = 8 if side == 0 else sw - 20
            pygame.draw.polygon(surf, (4, 7, 8), [(x, sh), (x + 18, sh), (x + 4, 80), (x - 8, 70)])
        # Left navigation.
        title = font_lg.render("ANINO", True, (125, 28, 26))
        surf.blit(title, (18, 18))
        logo = font_tiny.render("SA GUBAT", True, (170, 55, 43))
        surf.blit(logo, (20, 49))
        for i, name in enumerate(self.CATEGORIES):
            y = 112 + i * 29
            active = i == self.category
            if active:
                pygame.draw.polygon(surf, self.RED, [(12, y), (122, y), (135, y + 10), (119, y + 20), (12, y + 20)])
            img = font_sm.render(name, True, text_color if active else muted_color)
            surf.blit(img, (20, y + 2))
        # Settings panel.
        panel = pygame.Surface((298, 250), pygame.SRCALPHA)
        panel.fill((7, 9, 12, 224))
        pygame.draw.rect(panel, (91, 39, 39, 210), panel.get_rect(), 1)
        surf.blit(panel, (322, 54))
        heading = font_tiny.render(self._category() + " SETTINGS", True, (196, 185, 162))
        surf.blit(heading, (336, 62))
        items = self._items()
        visible_start = max(0, min(self.row - 10, max(0, len(items) - 12)))
        for visible, (label, key, kind, data) in enumerate(items[visible_start:visible_start + 12]):
            idx = visible_start + visible
            y = 82 + visible * 18
            selected = idx == self.row
            if selected:
                pygame.draw.rect(surf, (58, 25, 26), (330, y - 1, 282, 17))
            txt = font_tiny.render(label.upper(), True, text_color if selected else muted_color)
            surf.blit(txt, (336, y + 2))
            value = self._value(key, kind)
            if kind in ("slider", "volume"):
                low, high = data
                pct = max(0, min(1, (float(value) - low) / (high - low)))
                pygame.draw.rect(surf, (35, 39, 40), (500, y + 6, 82, 5))
                pygame.draw.rect(surf, self.RED, (500, y + 6, int(82 * pct), 5))
                val_img = font_tiny.render(str(int(value)), True, (218, 207, 188))
                surf.blit(val_img, (586 - val_img.get_width(), y + 1))
            else:
                if kind == "toggle":
                    shown = "ON" if value else "OFF"
                elif kind == "bind":
                    shown = "PRESS KEY" if self.waiting_for_key == key else str(value).upper()
                elif kind == "action":
                    shown = "RESET"
                else:
                    shown = str(value).upper()
                val_img = font_tiny.render(shown[:13], True, (203, 194, 176))
                surf.blit(val_img, (586 - val_img.get_width(), y + 2))
                pygame.draw.line(surf, (95, 35, 36), (500, y + 16), (586, y + 16), 1)
        pygame.draw.line(surf, (83, 37, 37), (338, 310), (604, 310), 1)
        reset = font_tiny.render("RESET", True, (196, 187, 170))
        apply = font_tiny.render("APPLY", True, (230, 220, 205))
        surf.blit(reset, (346, 326))
        surf.blit(apply, (565, 326))
        hint = "ARROWS: SELECT / CHANGE   ENTER: EDIT   F5: APPLY   F6: RESET   ESC: BACK"
        hint_img = font_tiny.render(hint, True, (112, 112, 103))
        surf.blit(hint_img, (18, sh - 17))
        if self.notice and pygame.time.get_ticks() < self.notice_until:
            n = font_tiny.render(self.notice, True, (220, 183, 133))
            surf.blit(n, (338, 294))
