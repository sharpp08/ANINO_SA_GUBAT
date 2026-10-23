"""
ANINO SA GUBAT: Mga Bulong ng Dilim
Main game loop and entry point.
"""
import os
import sys
import math
import json
import pygame

from settings import *
from player import Player
from map_system import GameMap
from enemies import EnemyManager
from renderer import Renderer
from audio_synth import audio_mgr
from asset_generator import (
    generate_all_textures, generate_all_weapons,
    generate_all_enemies, generate_all_pickups, generate_crosshair
)

# ─── Game States ─────────────────────────────────────────────────────────────
STATE_MENU     = 'menu'
STATE_PLAYING  = 'playing'
STATE_PAUSED   = 'paused'
STATE_GAMEOVER = 'gameover'
STATE_WIN      = 'win'


# ─── HUD helpers ─────────────────────────────────────────────────────────────
def safe_set_relative_mouse(enabled):
    try:
        pygame.mouse.set_relative_mode(enabled)
    except Exception:
        pass


def draw_bar(surf, x, y, w, h, value, max_val, fg, bg=(30, 30, 30)):
    pygame.draw.rect(surf, bg, (x, y, w, h))
    filled = int(w * max(0, value) / max_val)
    if filled > 0:
        pygame.draw.rect(surf, fg, (x, y, filled, h))
    pygame.draw.rect(surf, (80, 80, 80), (x, y, w, h), 1)


def draw_hud(surf, player, font_sm, font_tiny):
    sw, sh = surf.get_size()
    pad = 8

    # ── Health & Armor ────────────────────────────────────────────────────
    draw_bar(surf, pad, sh - 52, 120, 8, player.health, PLAYER_MAX_HEALTH, HEALTH_GREEN)
    hp_txt = font_tiny.render(f"HP {int(player.health)}", True, WHITE)
    surf.blit(hp_txt, (pad, sh - 64))

    # ── Stamina ───────────────────────────────────────────────────────────
    draw_bar(surf, pad + 130, sh - 52, 80, 8, player.stamina, STAMINA_MAX, (50, 180, 120))
    stm_txt = font_tiny.render(f"STM {int(player.stamina)}", True, (160, 240, 180))
    surf.blit(stm_txt, (pad + 130, sh - 64))

    # ── Sanity ────────────────────────────────────────────────────────────
    draw_bar(surf, pad + 130, sh - 22, 80, 6, player.sanity, SANITY_MAX, SANITY_PURPLE)
    san_txt = font_tiny.render(f"SAN {int(player.sanity)}%", True, (210, 160, 255))
    surf.blit(san_txt, (pad + 130, sh - 33))

    if player.armor > 0:
        draw_bar(surf, pad, sh - 38, 120, 6, player.armor, PLAYER_MAX_ARMOR, (100, 160, 255))
        arm_txt = font_tiny.render(f"AP {int(player.armor)}", True, (180, 210, 255))
        surf.blit(arm_txt, (pad, sh - 49))

    # ── Flashlight ───────────────────────────────────────────────────────
    batt_col = (220, 220, 50) if player.flashlight_battery > 30 else HEALTH_RED
    draw_bar(surf, pad, sh - 22, 80, 6, player.flashlight_battery,
             FLASHLIGHT_MAX_BATTERY, batt_col)
    fl_lbl = font_tiny.render("BATT", True, (180, 180, 180))
    surf.blit(fl_lbl, (pad, sh - 33))

    # ── Ammo ─────────────────────────────────────────────────────────────
    weapon_names = ['BOLO', 'SHOTGUN', 'REVOLVER']
    wname = weapon_names[player.current_weapon]
    w_txt = font_sm.render(wname, True, GOLD)
    surf.blit(w_txt, (sw - 130, sh - 65))

    if player.current_weapon == 1:
        ammo_str = f"{player.shotgun_mag} / {player.ammo_shotgun}"
    elif player.current_weapon == 2:
        ammo_str = f"{player.revolver_mag} / {player.ammo_revolver}"
    else:
        ammo_str = "---"
    a_txt = font_sm.render(ammo_str, True, AMMO_YELLOW)
    surf.blit(a_txt, (sw - 130, sh - 48))

    if player.reloading:
        r_txt = font_tiny.render("RELOADING...", True, (255, 200, 50))
        surf.blit(r_txt, (sw - 130, sh - 30))

    # ── Faith / Salt / Garlic ────────────────────────────────────────────
    draw_bar(surf, pad, sh - 80, 100, 8, player.faith_energy,
             FAITH_ENERGY_MAX, FAITH_BLUE)
    fe_lbl = font_tiny.render(f"FAITH {int(player.faith_energy)}", True, (150, 180, 255))
    surf.blit(fe_lbl, (pad, sh - 92))

    items_txt = font_tiny.render(
        f"SALT:{player.salt_count}  GARLIC:{player.garlic_count}  PAGES:{player.bible_pages}",
        True, (200, 200, 200))
    surf.blit(items_txt, (pad, sh - 108))

    # ── Ward slots ───────────────────────────────────────────────────────
    ward_labels = ['1:Light', '2:Shield', '3:Banish', '4:Bind', '5:Final']
    wx = sw // 2 - 160
    for i, lbl in enumerate(ward_labels):
        unlocked = player.wards_unlocked[i]
        on_cd    = player.ward_cooldowns[i] > 0
        if unlocked:
            col = (220, 180, 50) if not on_cd else (80, 80, 80)
        else:
            col = (50, 50, 50)
        slot_bg = pygame.Surface((60, 18), pygame.SRCALPHA)
        slot_bg.fill((0, 0, 0, 100))
        surf.blit(slot_bg, (wx + i * 65, sh - 24))
        w_lbl = font_tiny.render(lbl, True, col)
        surf.blit(w_lbl, (wx + i * 65 + 2, sh - 22))
        if on_cd:
            cd_txt = font_tiny.render(f"{player.ward_cooldowns[i]:.0f}s", True, (180, 80, 80))
            surf.blit(cd_txt, (wx + i * 65 + 2, sh - 10))


# ─── Menu screens ─────────────────────────────────────────────────────────────
def draw_menu(surf, font_lg, font_sm, font_tiny):
    surf.fill((5, 5, 15))
    sw, sh = surf.get_size()
    title = font_lg.render("ANINO SA GUBAT", True, SACRED_GOLD)
    sub   = font_sm.render("Mga Bulong ng Dilim", True, (200, 180, 130))
    surf.blit(title, (sw // 2 - title.get_width() // 2, sh // 4))
    surf.blit(sub,   (sw // 2 - sub.get_width() // 2,   sh // 4 + 48))

    options = ["ENTER  -  New Game", "L  -  Load Game", "ESC  -  Quit"]
    for i, opt in enumerate(options):
        t = font_sm.render(opt, True, WHITE)
        surf.blit(t, (sw // 2 - t.get_width() // 2, sh // 2 + i * 40))

    tip = font_tiny.render("A survival horror game set in Philippine mythology", True, GRAY)
    surf.blit(tip, (sw // 2 - tip.get_width() // 2, sh - 30))


def draw_paused(surf, font_lg, font_sm):
    overlay = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 140))
    surf.blit(overlay, (0, 0))
    sw, sh = surf.get_size()
    t = font_lg.render("PAUSED", True, WHITE)
    surf.blit(t, (sw // 2 - t.get_width() // 2, sh // 2 - 60))
    for i, line in enumerate(["ESC  -  Resume", "S  -  Save", "M  -  Main Menu"]):
        lt = font_sm.render(line, True, (200, 200, 200))
        surf.blit(lt, (sw // 2 - lt.get_width() // 2, sh // 2 + i * 36))


def draw_gameover(surf, font_lg, font_sm):
    surf.fill((10, 0, 0))
    sw, sh = surf.get_size()
    t = font_lg.render("YOU DIED", True, BLOOD_RED)
    surf.blit(t, (sw // 2 - t.get_width() // 2, sh // 2 - 60))
    for i, line in enumerate(["R  -  Respawn at Checkpoint", "M  -  Main Menu"]):
        lt = font_sm.render(line, True, (200, 150, 150))
        surf.blit(lt, (sw // 2 - lt.get_width() // 2, sh // 2 + i * 40))


def draw_win(surf, font_lg, font_sm, chapter):
    surf.fill((5, 10, 5))
    sw, sh = surf.get_size()
    t = font_lg.render(f"CHAPTER {chapter} COMPLETE", True, SACRED_GOLD)
    surf.blit(t, (sw // 2 - t.get_width() // 2, sh // 2 - 60))
    lt = font_sm.render("ENTER  -  Continue   M  -  Menu", True, WHITE)
    surf.blit(lt, (sw // 2 - lt.get_width() // 2, sh // 2 + 30))


# ─── Save / Load ─────────────────────────────────────────────────────────────
def save_game(player, chapter, slot=0):
    os.makedirs(SAVE_DIR, exist_ok=True)
    path = os.path.join(SAVE_DIR, f"save_{slot}.json")
    data = {'chapter': chapter, 'player': player.get_state()}
    try:
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        return False


def load_game(slot=0):
    path = os.path.join(SAVE_DIR, f"save_{slot}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


# ─── Game class ───────────────────────────────────────────────────────────────
class Game:
    def __init__(self):
        pygame.init()
        flags = pygame.FULLSCREEN if FULLSCREEN else 0
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), flags)
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()

        self.internal = pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT))

        self.font_lg   = pygame.font.SysFont('consolas', 32, bold=True)
        self.font_sm   = pygame.font.SysFont('consolas', 18)
        self.font_tiny = pygame.font.SysFont('consolas', 13)

        textures      = generate_all_textures()
        weapon_spr    = generate_all_weapons()
        enemy_spr     = generate_all_enemies()
        pickup_spr    = generate_all_pickups()
        crosshair_spr = generate_crosshair(16)

        self.game_map      = GameMap()
        self.enemy_manager = EnemyManager()
        self.player        = Player()
        self.renderer      = Renderer(self.internal, textures, weapon_spr, enemy_spr, pickup_spr)
        self.renderer.crosshair = crosshair_spr

        self.state   = STATE_MENU
        self.chapter = 1
        self.effects = []
        self.notif   = ''
        self.notif_t = 0.0

        pygame.mouse.set_visible(False)

    # ── Level loading ─────────────────────────────────────────────────────
    def load_chapter(self, chapter_num):
        self.chapter = chapter_num
        self.game_map.load_chapter(chapter_num)
        sx, sy = self.game_map.player_start
        self.player = Player(sx, sy, self.game_map.player_start_angle)
        self.player.current_chapter = chapter_num
        self.player.set_checkpoint(sx, sy)
        self.enemy_manager.spawn_enemies(self.game_map.enemies)
        self.effects = []

    def start_new_game(self):
        self.load_chapter(1)
        self.state = STATE_PLAYING
        safe_set_relative_mouse(True)

    def load_saved_game(self):
        data = load_game()
        if data is None:
            self.notify("No save file found!")
            return
        chapter = data.get('chapter', 1)
        self.load_chapter(chapter)
        self.player.load_state(data['player'])
        self.state = STATE_PLAYING
        safe_set_relative_mouse(True)
        self.notify("Game loaded.")

    def notify(self, text, duration=2.5):
        self.notif   = text
        self.notif_t = duration

    # ── Playing input ─────────────────────────────────────────────────────
    def handle_playing_events(self, event):
        p = self.player
        if event.type == pygame.KEYDOWN:
            k = event.key
            if k == pygame.K_ESCAPE:
                self.state = STATE_PAUSED
                safe_set_relative_mouse(False)
            elif k == pygame.K_F3:
                self.renderer.show_debug = not self.renderer.show_debug
            elif k == pygame.K_r:
                p.start_reload()
            elif k == pygame.K_f:
                p.flashlight_on = not p.flashlight_on
            elif k == pygame.K_e:
                self._interact()
            elif k == pygame.K_g:
                self._use_salt()
            elif k == pygame.K_h:
                self._use_garlic()
            elif k == pygame.K_1:
                p.switch_weapon(0)
            elif k == pygame.K_2:
                p.switch_weapon(1)
            elif k == pygame.K_3:
                p.switch_weapon(2)
            elif k == pygame.K_q:
                self._cast_selected_ward()
            elif k == pygame.K_TAB:
                p.selected_ward = (p.selected_ward + 1) % 5
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._fire()

    def _fire(self):
        p  = self.player
        wi = p.fire_weapon()
        if wi:
            self.renderer.trigger_muzzle_flash()
            if wi['type'] in ('shotgun', 'revolver', 'bolo'):
                audio_mgr.play(wi['type'])
            hits = self.enemy_manager.apply_weapon_hit(p.x, p.y, p.angle, wi)
            if hits:
                self.renderer.trigger_screen_shake(4)

    def _use_salt(self):
        if self.player.use_salt():
            self.enemy_manager.add_salt_zone(self.player.x, self.player.y)
            self.notify("Salt circle placed!")

    def _use_garlic(self):
        if self.player.use_garlic():
            self.enemy_manager.add_garlic_zone(self.player.x, self.player.y)
            self.notify("Garlic thrown!")

    def _cast_selected_ward(self):
        p = self.player
        ward = p.cast_ward(p.selected_ward)
        if ward:
            affected = self.enemy_manager.apply_ward(p.x, p.y, ward, radius=5.0)
            self.renderer.trigger_ward_effect(ward['type'])
            self.renderer.trigger_screen_shake(3)
            self.notify(f"{ward['name']}! ({len(affected)} hit)")

    def _interact(self):
        p = self.player
        look_x = p.x + math.cos(p.angle) * 1.2
        look_y = p.y + math.sin(p.angle) * 1.2
        if self.game_map.open_door(look_x, look_y):
            audio_mgr.play('door')
            self.notify("Door opened.")
        for cp in self.game_map.checkpoints:
            dx = cp['x'] - p.x
            dy = cp['y'] - p.y
            if math.sqrt(dx*dx + dy*dy) < 1.5:
                p.set_checkpoint(cp['x'], cp['y'])
                self.notify("Checkpoint saved!")
                break

    # ── Update (playing) ──────────────────────────────────────────────────
    def update_playing(self, dt, mouse_dx, mouse_dy):
        p   = self.player
        keys = pygame.key.get_pressed()
        p.update(dt, keys, mouse_dx, mouse_dy, self.game_map)

        # Footstep audio on movement
        if abs(p.bob_amount) > 1.8 and random.random() < 0.12:
            audio_mgr.play('footstep', volume=0.4 if not p.is_sprinting else 0.8)

        # Enemy AI with stealth sensing and sanity proximity
        self.enemy_manager.update(dt, p.x, p.y, self.game_map, player=self.player)

        # Enemy attacks
        dmg = self.enemy_manager.check_attacks(p.x, p.y)
        if dmg > 0:
            p.take_damage(dmg)
            self.renderer.trigger_screen_shake(6)

        # Auto-collect pickups
        for pickup in self.game_map.get_nearby_pickups(p.x, p.y):
            if p.pickup_item(pickup):
                pickup['active'] = False
                audio_mgr.play('pickup')
                self.notify(f"Picked up {pickup['type'].replace('_', ' ').title()}")

        # Check level exit
        if self.game_map.exit_pos:
            ex, ey = self.game_map.exit_pos
            dx = ex - p.x
            dy = ey - p.y
            if math.sqrt(dx*dx + dy*dy) < 1.2:
                self.state = STATE_WIN

        # Death check
        if not p.alive:
            self.state = STATE_GAMEOVER
            safe_set_relative_mouse(False)

        # Notification timer
        if self.notif_t > 0:
            self.notif_t -= dt

    # ── Render ────────────────────────────────────────────────────────────
    def render(self, dt):
        alive_enemies = self.enemy_manager.get_alive_enemies()

        if self.state == STATE_PLAYING:
            self.renderer.render_frame(
                self.player, self.game_map, alive_enemies, self.effects, dt)
            draw_hud(self.internal, self.player, self.font_sm, self.font_tiny)

            # Notification
            if self.notif_t > 0:
                nt = self.font_tiny.render(self.notif, True, SACRED_GOLD)
                self.internal.blit(nt, (8, 8))

        elif self.state == STATE_PAUSED:
            self.renderer.render_frame(
                self.player, self.game_map, alive_enemies, self.effects, dt)
            draw_hud(self.internal, self.player, self.font_sm, self.font_tiny)
            draw_paused(self.internal, self.font_lg, self.font_sm)

        elif self.state == STATE_MENU:
            draw_menu(self.internal, self.font_lg, self.font_sm, self.font_tiny)

        elif self.state == STATE_GAMEOVER:
            draw_gameover(self.internal, self.font_lg, self.font_sm)

        elif self.state == STATE_WIN:
            draw_win(self.internal, self.font_lg, self.font_sm, self.chapter)

        # Scale to screen
        pygame.transform.scale(self.internal, (SCREEN_WIDTH, SCREEN_HEIGHT), self.screen)
        pygame.display.flip()

    # ── Main loop ─────────────────────────────────────────────────────────
    def run(self):
        running   = True
        mouse_dx  = 0
        mouse_dy  = 0

        while running:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            mouse_dx = 0
            mouse_dy = 0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif self.state == STATE_MENU:
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_RETURN:
                            self.start_new_game()
                        elif event.key == pygame.K_l:
                            self.load_saved_game()
                        elif event.key == pygame.K_ESCAPE:
                            running = False

                elif self.state == STATE_PLAYING:
                    if event.type == pygame.MOUSEMOTION:
                        mouse_dx += event.rel[0]
                        mouse_dy += event.rel[1]
                    self.handle_playing_events(event)

                elif self.state == STATE_PAUSED:
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            self.state = STATE_PLAYING
                            safe_set_relative_mouse(True)
                        elif event.key == pygame.K_s:
                            ok = save_game(self.player, self.chapter)
                            self.notify("Saved!" if ok else "Save failed.")
                            self.state = STATE_PLAYING
                            safe_set_relative_mouse(True)
                        elif event.key == pygame.K_m:
                            self.state = STATE_MENU
                            safe_set_relative_mouse(False)

                elif self.state == STATE_GAMEOVER:
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_r:
                            self.player.respawn()
                            self.state = STATE_PLAYING
                            safe_set_relative_mouse(True)
                        elif event.key == pygame.K_m:
                            self.state = STATE_MENU

                elif self.state == STATE_WIN:
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_RETURN:
                            next_ch = self.chapter + 1
                            if next_ch <= 2:
                                self.load_chapter(next_ch)
                                self.state = STATE_PLAYING
                                safe_set_relative_mouse(True)
                            else:
                                self.state = STATE_MENU
                        elif event.key == pygame.K_m:
                            self.state = STATE_MENU

            if self.state == STATE_PLAYING:
                self.update_playing(dt, mouse_dx, mouse_dy)

            self.render(dt)

        pygame.quit()
        sys.exit()


# ─── Entry point ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    Game().run()
