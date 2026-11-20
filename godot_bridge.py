"""Local UDP bridge between the authoritative Pygame game and the Godot renderer.

Protocol v1: Godot -> Python input packets on 127.0.0.1:4244;
Python -> Godot state snapshots on 127.0.0.1:4243.
Gameplay remains in the existing Python classes. This module only translates input
and serializes read-only presentation state.
"""
import json
import math
import socket
import time


KEYS = {
    "w": "K_w", "a": "K_a", "s": "K_s", "d": "K_d",
    "shift": "K_LSHIFT", "ctrl": "K_LCTRL", "f": "K_f",
    "e": "K_e", "g": "K_g", "h": "K_h", "v": "K_v", "c": "K_c",
    "1": "K_1", "2": "K_2", "3": "K_3", "4": "K_4", "5": "K_5",
    "q": "K_q", "tab": "K_TAB", "r": "K_r", "escape": "K_ESCAPE",
    "m": "K_m", "f11": "K_F11", "f3": "K_F3", "s_key": "K_s",
    "enter": "K_RETURN", "i": "K_i"
}


class _PressedView:
    def __init__(self, base, remote, pygame):
        self.base, self.remote, self.pygame = base, remote, pygame

    def __getitem__(self, key):
        try:
            return bool(self.base[key]) or key in self.remote
        except (IndexError, TypeError):
            return key in self.remote


class GodotBridge:
    def __init__(self, host="127.0.0.1", receive_port=4244, target_port=4243):
        self.host = host
        self.receive_port = receive_port
        self.target_port = target_port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setblocking(False)
        self.socket.bind((host, receive_port))
        self.remote_keys = set()
        self.remote_buttons = set()
        self.last_send = 0.0
        self.sequence = 0
        self.last_map_key = None
        self.last_world_send = 0.0
        self.world_revision = 0
        self.last_game_state = "menu"
        self.last_packet_time = 0.0
        print(f"[GODOT BRIDGE] UDP input :{receive_port}, state target :{target_port}")

    def key_state_view(self, base, pygame):
        return _PressedView(base, self.remote_keys, pygame)

    def poll_events(self, pygame):
        latest = None
        while True:
            try:
                packet, _addr = self.socket.recvfrom(65507)
            except BlockingIOError:
                break
            except OSError as exc:
                print(f"[GODOT BRIDGE] receive error: {exc}")
                break
            try:
                data = json.loads(packet.decode("utf-8"))
                if isinstance(data, dict) and data.get("protocol") == 1 and data.get("type") == "input":
                    latest = data
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue

        if latest is None:
            return []

        self.last_packet_time = time.monotonic()
        events = []
        new_keys = set(str(k).lower() for k in latest.get("keys", []) if isinstance(k, str))
        for name in sorted(new_keys - self.remote_keys):
            key_name = KEYS.get(name)
            if key_name:
                events.append(pygame.event.Event(pygame.KEYDOWN, {"key": getattr(pygame, key_name), "repeat": False}))
        for name in sorted(self.remote_keys - new_keys):
            key_name = KEYS.get(name)
            if key_name:
                events.append(pygame.event.Event(pygame.KEYUP, {"key": getattr(pygame, key_name)}))
        self.remote_keys = new_keys

        dx, dy = latest.get("mouse_delta", [0, 0])[:2]
        try:
            dx, dy = float(dx), float(dy)
        except (TypeError, ValueError):
            dx = dy = 0.0
        if dx or dy:
            events.append(pygame.event.Event(pygame.MOUSEMOTION, {
                "pos": (0, 0), "rel": (int(round(dx)), int(round(dy))), "buttons": (0, 0, 0)
            }))

        buttons = set()
        raw_buttons = latest.get("mouse_buttons", [])
        if isinstance(raw_buttons, list) and raw_buttons and bool(raw_buttons[0]):
            buttons.add(1)
        for button in buttons - self.remote_buttons:
            events.append(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (0, 0), "button": button}))
        self.remote_buttons = buttons

        commands = latest.get("commands", [])
        if isinstance(commands, list):
            if "start_game" in commands:
                key = pygame.K_m if self.last_game_state == "gameover" else pygame.K_RETURN
                events.append(pygame.event.Event(pygame.KEYDOWN, {"key": key, "repeat": False}))
            if "resume_game" in commands:
                events.append(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_ESCAPE, "repeat": False}))
        return events

    @staticmethod
    def _number(value, default=0.0):
        try:
            result = float(value)
            return result if math.isfinite(result) else default
        except (TypeError, ValueError):
            return default

    def _trees_for(self, game_map, px, py):
        trees = getattr(game_map, "trees", []) or []
        nearest = []
        for tree in trees:
            if not isinstance(tree, dict):
                continue
            x, y = self._number(tree.get("x")), self._number(tree.get("y"))
            nearest.append((abs(x - px) + abs(y - py), {
                "x": x, "y": y, "type": str(tree.get("type", "tree")),
                "scale": self._number(tree.get("scale"), 1.0),
                "radius": self._number(tree.get("radius"), 0.35),
                "tint": int(tree.get("tint", 220))
            }))
        nearest.sort(key=lambda item: item[0])
        return [item[1] for item in nearest[:350]]

    def build_state(self, game):
        p = game.player
        gm = game.game_map
        enemies = []
        for index, enemy in enumerate(getattr(game.enemy_manager, "enemies", [])):
            if not getattr(enemy, "alive", True) and getattr(enemy, "death_t", 99.0) > 2.0:
                continue
            enemies.append({
                "id": str(id(enemy)), "type": str(getattr(enemy, "type", "aswang")),
                "x": self._number(getattr(enemy, "x", 0)),
                "y": self._number(getattr(enemy, "y", 0)),
                "angle": self._number(getattr(enemy, "facing_angle", 0)),
                "health": self._number(getattr(enemy, "health", 0)),
                "max_health": self._number(getattr(enemy, "max_health", 1), 1),
                "alive": bool(getattr(enemy, "alive", True)),
                "animation": str(getattr(enemy, "animation_state", "idle")),
                "flight_lift": self._number(getattr(enemy, "flight_lift", 0))
            })

        map_key = (int(getattr(game, "chapter", 1)), id(gm), len(getattr(gm, "trees", []) or []))
        world = None
        now = time.monotonic()
        if map_key != self.last_map_key or now - self.last_world_send >= 1.5:
            self.world_revision += 1
            world = {
                "chapter": map_key[0],
                "revision": self.world_revision,
                "width": int(getattr(gm, "width", 64)),
                "height": int(getattr(gm, "height", 64)),
                "trees": self._trees_for(gm, p.x, p.y)
            }
            self.last_map_key = map_key
            self.last_world_send = now

        pickups = []
        for index, pickup in enumerate(getattr(gm, "pickups", []) or []):
            if isinstance(pickup, dict) and pickup.get("active", True):
                pickups.append({
                    "id": str(index), "type": str(pickup.get("type", "item")),
                    "x": self._number(pickup.get("x")), "y": self._number(pickup.get("y"))
                })

        self.last_game_state = str(getattr(game, "state", "menu"))
        state = {
            "protocol": 1, "type": "state", "sequence": self.sequence,
            "game_state": str(getattr(game, "state", "menu")),
            "chapter": int(getattr(game, "chapter", 1)),
            "player": {
                "x": self._number(p.x), "y": self._number(p.y),
                "angle": self._number(p.angle), "pitch": self._number(p.pitch),
                "health": self._number(p.health), "max_health": self._number(getattr(p, "max_health", 100), 100),
                "stamina": self._number(p.stamina), "sanity": self._number(p.sanity),
                "flashlight_on": bool(p.flashlight_on),
                "flashlight_battery": self._number(p.flashlight_battery),
                "is_crouching": bool(p.is_crouching), "is_sprinting": bool(p.is_sprinting),
                "weapon": int(p.current_weapon),
                "shotgun_mag": int(p.shotgun_mag), "shotgun_reserve": int(p.ammo_shotgun),
                "revolver_mag": int(p.revolver_mag), "revolver_reserve": int(p.ammo_revolver),
                "salt": int(p.salt_count), "garlic": int(p.garlic_count),
                "pages": int(p.pages_this_chapter),
                "survival_time": self._number(p.survival_time_left)
            },
            "enemies": enemies,
            "pickups": pickups,
            "notification": str(getattr(game, "notif", "")) if getattr(game, "notif_t", 0) > 0 else ""
        }
        if world is not None:
            state["world"] = world
        return state

    def send_state(self, game):
        now = time.monotonic()
        if now - self.last_send < 1.0 / 20.0:
            return
        self.last_send = now
        self.sequence += 1
        try:
            payload = json.dumps(self.build_state(game), separators=(",", ":"), ensure_ascii=True).encode("utf-8")
            if len(payload) <= 60000:
                self.socket.sendto(payload, (self.host, self.target_port))
            else:
                print(f"[GODOT BRIDGE] Snapshot too large ({len(payload)} bytes); skipped")
        except (OSError, TypeError, ValueError) as exc:
            print(f"[GODOT BRIDGE] state send failed: {exc}")

    def close(self):
        try:
            self.socket.close()
        except OSError:
            pass
