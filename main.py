"""
ANINO SA GUBAT: Mga Bulong ng Dilim
Main game loop and entry point.
"""
import os
import sys
import math
import random
import json
import pygame

from settings import *
from player import Player
from map_system import GameMap
from enemies import EnemyManager
from renderer import Renderer
from radar import Radar
from audio_synth import audio_mgr
from cinematic import Cinematic
from asset_generator import (
    generate_all_textures, generate_all_weapons,
    generate_all_enemies, generate_all_pickups, generate_crosshair
)

# ─── Game States ─────────────────────────────────────────────────────────────
STATE_MENU     = 'menu'
STATE_INTRO    = 'intro'
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
    pad = 12

    # ── Left Column (Faith, Items, HP, AP, STM, BATT) stacked cleanly with zero overlap ──
    current_y = sh - 46
    font_h = font_tiny.get_height()

    # 1. Flashlight Battery (bottom of left stack)
    batt_col = (220, 220, 50) if player.flashlight_battery > 30 else HEALTH_RED
    fl_lbl = font_tiny.render(f"BATT {int(player.flashlight_battery)}%", True, (180, 180, 180))
    surf.blit(fl_lbl, (pad, current_y - font_h))
    draw_bar(surf, pad + 70, current_y - font_h + 3, 110, 6, player.flashlight_battery, FLASHLIGHT_MAX_BATTERY, batt_col)
    current_y -= (font_h + 12)

    # 2. Stamina
    stm_lbl = font_tiny.render(f"STM {int(player.stamina)}", True, (160, 240, 180))
    surf.blit(stm_lbl, (pad, current_y - font_h))
    draw_bar(surf, pad + 70, current_y - font_h + 3, 110, 6, player.stamina, STAMINA_MAX, (50, 180, 120))
    current_y -= (font_h + 12)

    # 3. Armor (if > 0)
    if player.armor > 0:
        arm_lbl = font_tiny.render(f"AP {int(player.armor)}", True, (180, 210, 255))
        surf.blit(arm_lbl, (pad, current_y - font_h))
        draw_bar(surf, pad + 70, current_y - font_h + 3, 110, 6, player.armor, PLAYER_MAX_ARMOR, (100, 160, 255))
        current_y -= (font_h + 12)

    # 4. HP
    hp_lbl = font_tiny.render(f"HP {int(player.health)}", True, WHITE)
    surf.blit(hp_lbl, (pad, current_y - font_h))
    draw_bar(surf, pad + 70, current_y - font_h + 3, 110, 6, player.health, PLAYER_MAX_HEALTH, HEALTH_GREEN)
    current_y -= (font_h + 12)

    # 5. Items (Salt, Garlic, Pages)
    items_txt = font_tiny.render(f"SALT:{player.salt_count} GARLIC:{player.garlic_count} PAGES:{player.bible_pages}", True, (200, 200, 200))
    surf.blit(items_txt, (pad, current_y - font_h))
    current_y -= (font_h + 12)

    # 6. Faith
    fe_lbl = font_tiny.render(f"FAITH {int(player.faith_energy)}", True, (150, 180, 255))
    surf.blit(fe_lbl, (pad, current_y - font_h))
    draw_bar(surf, pad + 70, current_y - font_h + 3, 110, 6, player.faith_energy, FAITH_ENERGY_MAX, FAITH_BLUE)

    # ── Right Column (Weapon & Ammo Panel) ───────────────────────────────────
    panel_w, panel_h = 140, 65
    px = sw - panel_w - 12
    py = sh - panel_h - 46
    panel_bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    panel_bg.fill((10, 10, 15, 200))
    pygame.draw.rect(panel_bg, (80, 80, 90), (0, 0, panel_w, panel_h), 1, border_radius=4)
    surf.blit(panel_bg, (px, py))

    weapon_names = ['BOLO', 'SHOTGUN', 'REVOLVER']
    wname = weapon_names[player.current_weapon]
    w_txt = font_sm.render(wname, True, GOLD)
    surf.blit(w_txt, (px + 10, py + 8))

    if player.current_weapon == 1:
        ammo_str = f"MAG: {player.shotgun_mag}/{SHOTGUN_MAG_SIZE} ({player.ammo_shotgun})"
    elif player.current_weapon == 2:
        ammo_str = f"MAG: {player.revolver_mag}/{REVOLVER_MAG_SIZE} ({player.ammo_revolver})"
    else:
        ammo_str = "DUR: 3/3"
    a_txt = font_tiny.render(ammo_str, True, AMMO_YELLOW)
    surf.blit(a_txt, (px + 10, py + 30))

    if player.reloading:
        r_txt = font_tiny.render("RELOADING...", True, (255, 200, 50))
        surf.blit(r_txt, (px + 10, py + 46))

    # ── Center Bottom (Ward slots - centered horizontally, never clipped) ───
    ward_labels = ['1:Light', '2:Shield', '3:Banish', '4:Bind', '5:Final']
    slot_widths = [font_tiny.size(lbl)[0] + 16 for lbl in ward_labels]
    total_w = sum(slot_widths) + (len(ward_labels) - 1) * 6
    wx = sw // 2 - total_w // 2
    current_x = wx
    for i, lbl in enumerate(ward_labels):
        sw_w = slot_widths[i]
        unlocked = player.wards_unlocked[i]
        on_cd    = player.ward_cooldowns[i] > 0
        is_light_on = (i == 0 and player.flashlight_on and player.flashlight_battery > 0)

        if is_light_on:
            col = (255, 230, 100)
            border_col = (255, 215, 0)
        elif unlocked and not on_cd:
            col = (220, 180, 50)
            border_col = (100, 100, 100)
        elif unlocked:
            col = (120, 120, 120)
            border_col = (60, 60, 60)
        else:
            col = (50, 50, 50)
            border_col = (30, 30, 30)

        slot_bg = pygame.Surface((sw_w, 22), pygame.SRCALPHA)
        if is_light_on:
            slot_bg.fill((60, 50, 20, 220))
        else:
            slot_bg.fill((0, 0, 0, 180))
        surf.blit(slot_bg, (current_x, sh - 28))

        if is_light_on:
            pygame.draw.rect(surf, border_col, (current_x, sh - 28, sw_w, 22), 2)

        w_lbl = font_tiny.render(lbl, True, col)
        surf.blit(w_lbl, (current_x + 8, sh - 26))
        if on_cd:
            cd_txt = font_tiny.render(f"{player.ward_cooldowns[i]:.0f}s", True, (180, 80, 80))
            surf.blit(cd_txt, (current_x + 8, sh - 16))
        current_x += sw_w + 6


# ─── Menu screens ─────────────────────────────────────────────────────────────
def draw_menu(surf, font_lg, font_sm, font_tiny):
    surf.fill((5, 5, 15))
    sw, sh = surf.get_size()
    title = font_lg.render("ANINO SA GUBAT", True, SACRED_GOLD)
    sub   = font_sm.render("Mga Bulong ng Dilim", True, (200, 180, 130))
    surf.blit(title, (sw // 2 - title.get_width() // 2, sh // 4))
    surf.blit(sub,   (sw // 2 - sub.get_width() // 2,   sh // 4 + 48))

    options = ["ENTER  -  New Game", "L  -  Load Game", "F11  -  Toggle Fullscreen", "ESC  -  Quit"]
    for i, opt in enumerate(options):
        t = font_sm.render(opt, True, WHITE)
        surf.blit(t, (sw // 2 - t.get_width() // 2, sh // 2 + i * 36))

    tip = font_tiny.render("A survival horror game set in Philippine mythology", True, GRAY)
    surf.blit(tip, (sw // 2 - tip.get_width() // 2, sh - 30))


def draw_paused(surf, font_lg, font_sm):
    overlay = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 140))
    surf.blit(overlay, (0, 0))
    sw, sh = surf.get_size()
    t = font_lg.render("PAUSED", True, WHITE)
    surf.blit(t, (sw // 2 - t.get_width() // 2, sh // 2 - 80))
    for i, line in enumerate(["ESC  -  Resume", "S  -  Save", "F11  -  Toggle Fullscreen", "M  -  Main Menu"]):
        lt = font_sm.render(line, True, (200, 200, 200))
        surf.blit(lt, (sw // 2 - lt.get_width() // 2, sh // 2 - 20 + i * 32))


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


# ─── Startup Loading Animation ───────────────────────────────────────────────
def draw_loading_step(screen, clock, font_lg, font_sm, step_text, progress):
    sw, sh = screen.get_size()
    clock.tick(60)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

    screen.fill((5, 5, 12))
    
    # Title
    title = font_lg.render("ANINO SA GUBAT", True, (212, 175, 55))
    screen.blit(title, (sw // 2 - title.get_width() // 2, sh // 3 - 40))
    
    sub = font_sm.render("Mga Bulong ng Dilim", True, (180, 160, 110))
    screen.blit(sub, (sw // 2 - sub.get_width() // 2, sh // 3 + 10))
    
    # Loading bar container
    bar_w, bar_h = 500, 16
    bx = sw // 2 - bar_w // 2
    by = sh // 2 + 60
    pygame.draw.rect(screen, (30, 30, 45), (bx, by, bar_w, bar_h), border_radius=4)
    
    # Progress fill
    fill_w = int(bar_w * progress)
    if fill_w > 0:
        pygame.draw.rect(screen, (212, 175, 55), (bx, by, fill_w, bar_h), border_radius=4)
    pygame.draw.rect(screen, (100, 90, 60), (bx, by, bar_w, bar_h), 1, border_radius=4)
    
    # Step description
    txt = font_sm.render(step_text, True, (220, 220, 220))
    screen.blit(txt, (sw // 2 - txt.get_width() // 2, by + 30))
    
    # Percentage
    pct_txt = font_sm.render(f"{int(progress * 100)}%", True, (150, 140, 100))
    screen.blit(pct_txt, (sw // 2 - pct_txt.get_width() // 2, by + 65))
    
    pygame.display.flip()


# ─── Game class ───────────────────────────────────────────────────────────────
class Game:
    def __init__(self):
        pygame.init()
        print(f"[{BUILD_VERSION}] Starting ANINO SA GUBAT...")
        flags = pygame.FULLSCREEN if FULLSCREEN else 0
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), flags)
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()

        self.internal = pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT))

        self.font_lg   = pygame.font.SysFont('consolas', 32, bold=True)
        self.font_sm   = pygame.font.SysFont('consolas', 18)
        self.font_tiny = pygame.font.SysFont('consolas', 13)

        draw_loading_step(self.screen, self.clock, self.font_lg, self.font_sm, "Initializing Display & Subsystems...", 0.1)

        draw_loading_step(self.screen, self.clock, self.font_lg, self.font_sm, "Generating Procedural Textures & Sprites...", 0.3)
        textures      = generate_all_textures()

        draw_loading_step(self.screen, self.clock, self.font_lg, self.font_sm, "Forging Weapons & Tools...", 0.5)
        weapon_spr    = generate_all_weapons()

        draw_loading_step(self.screen, self.clock, self.font_lg, self.font_sm, "Summoning Forest Entities & AI...", 0.7)
        enemy_spr     = generate_all_enemies()

        draw_loading_step(self.screen, self.clock, self.font_lg, self.font_sm, "Preparing Items & Relics...", 0.85)
        pickup_spr    = generate_all_pickups()
        crosshair_spr = generate_crosshair(16)

        draw_loading_step(self.screen, self.clock, self.font_lg, self.font_sm, "Entering the Forest...", 1.0)

        self.game_map      = GameMap()
        self.enemy_manager = EnemyManager()
        self.player        = Player()
        self.renderer      = Renderer(self.internal, textures, weapon_spr, enemy_spr, pickup_spr)
        self.renderer.crosshair = crosshair_spr
        self.renderer.clock = self.clock
        self.cinematic     = Cinematic(self.internal)
        self.radar         = Radar()

        self.state   = STATE_MENU
        self.intro_to_menu = False      # True: after the intro, go back to the menu
        self.chapter = 1
        self.level_enemy_total = 0
        self.effects = []
        self.notif   = ''
        self.notif_t = 0.0
    def toggle_fullscreen(self):
        global FULLSCREEN
        FULLSCREEN = not FULLSCREEN
        flags = pygame.FULLSCREEN if FULLSCREEN else 0
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), flags)
        self.notify("Fullscreen: ON" if FULLSCREEN else "Fullscreen: OFF")


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
        self.level_enemy_total = len(self.enemy_manager.enemies)
        self.renderer.level_enemy_total = self.level_enemy_total
        # Spawn report: shows in the console if enemies/pickups spawn in bad places
        print(f"[CHAPTER {chapter_num}] enemies={self.level_enemy_total} "
              f"pickups={len(getattr(self.game_map, 'pickups', []))} "
              f"trees={len(getattr(self.game_map, 'trees', []))} start=({sx:.1f},{sy:.1f})")
        for e in self.enemy_manager.enemies:
            solid = False
            try:
                solid = self.game_map.is_solid(e.x, e.y)
            except Exception:
                pass
            d = math.hypot(e.x - sx, e.y - sy)
            print(f"    enemy {e.type:12s} pos=({e.x:.1f},{e.y:.1f}) dist={d:.1f}"
                  + ("  <-- INSIDE A WALL!" if solid else ""))
        if self.level_enemy_total == 0:
            print(f"[WARNING] Chapter {chapter_num} has NO enemies - it can only be completed by reaching the exit.")

    def max_chapter(self):
        return getattr(self.game_map, 'max_chapters', 2)

    def advance_chapter(self):
        """Go to the next chapter, or show the win screen after the last one."""
        next_ch = self.chapter + 1
        if next_ch <= self.max_chapter():
            print(f"[CHAPTER LOAD] Loading Chapter {next_ch}...")
            try:
                carried = self.player.get_state()      # keep health, ammo, items, wards
                self.load_chapter(next_ch)
                carried.pop('x', None); carried.pop('y', None); carried.pop('angle', None)
                carried.pop('checkpoint_x', None); carried.pop('checkpoint_y', None)
                self.player.load_state({**self.player.get_state(), **carried})
                self.player.current_chapter = next_ch
                self.player.alive = True
                self.state = STATE_PLAYING
                self.notify(f"Entering Chapter {next_ch}...", 3.0)
                return
            except Exception:
                import traceback
                print(f"[ERROR] Could not load chapter {next_ch}:")
                traceback.print_exc()
        print("[VICTORY] No more chapters - showing win screen.")
        self.state = STATE_WIN
        safe_set_relative_mouse(False)

    def start_new_game(self):
        self.state = STATE_INTRO
        self.intro_to_menu = False
        self.cinematic.reset()
        safe_set_relative_mouse(False)

    def load_saved_game(self):
        data = load_game()
        if data is None:
            self.notify("No save file found!")
            return
        chapter = data.get('chapter', 1)
        self.load_chapter(chapter)
        self.player.load_state(data.get('player', {}))
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
            elif k == pygame.K_F11:
                self.toggle_fullscreen()
            elif k == pygame.K_F3:
                self.renderer.show_debug = not self.renderer.show_debug
            elif k == pygame.K_F4:
                self.renderer.debug_f4 = not getattr(self.renderer, 'debug_f4', False)
                self.notify(f"Debug Mode F4 (Raw Scene): {'ON' if self.renderer.debug_f4 else 'OFF'}")
            elif k == pygame.K_m:
                self.notify("Radar: ON" if self.radar.toggle() else "Radar: OFF")
            elif k == pygame.K_F6:
                # DEBUG: teleport 4 tiles from the nearest living enemy, facing it
                alive = self.enemy_manager.get_alive_enemies()
                if alive:
                    e = min(alive, key=lambda en: en.distance_to(p.x, p.y))
                    for step in range(16):
                        a = step * math.pi / 8
                        nx = e.x + math.cos(a) * 4.0
                        ny = e.y + math.sin(a) * 4.0
                        if not self.game_map.is_solid(nx, ny):
                            p.x, p.y = nx, ny
                            p.angle = math.atan2(e.y - ny, e.x - nx)
                            self.notify(f"DEBUG: teleported near {e.type}")
                            break
            elif k == pygame.K_F7:
                # DEBUG: defeat every enemy to test chapter progression
                for e in self.enemy_manager.enemies:
                    e.take_damage(99999)
                self.notify("DEBUG: all enemies defeated")
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
                if p.flashlight_battery > 0:
                    p.flashlight_on = not p.flashlight_on
                    try:
                        audio_mgr.play('flashlight_click')
                    except Exception:
                        pass
                else:
                    self.notify("Flashlight battery is dead!")
            elif k == pygame.K_2:
                p.selected_ward = 1
                self._cast_selected_ward()
            elif k == pygame.K_3:
                p.selected_ward = 2
                self._cast_selected_ward()
            elif k == pygame.K_q:
                self._cast_selected_ward()
            elif k == pygame.K_TAB:
                p.selected_ward = (p.selected_ward + 1) % 5
        if event.type == pygame.MOUSEWHEEL:
            if event.y > 0:
                p.current_weapon = (p.current_weapon - 1) % 3
            elif event.y < 0:
                p.current_weapon = (p.current_weapon + 1) % 3
            try:
                audio_mgr.play('click')
            except Exception:
                pass
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._fire()

    def _fire(self):
        p  = self.player
        wi = p.fire_weapon()
        if wi:
            self.renderer.trigger_muzzle_flash()
            if wi['type'] in ('shotgun', 'revolver', 'bolo'):
                audio_mgr.play(wi['type'])
                if wi['type'] in ('shotgun', 'revolver'):
                    self.renderer.emit_casing(self.renderer.w // 2 + 60, self.renderer.h - 30, random.uniform(40, 90), random.uniform(-110, -60))
                    self.renderer.emit_smoke(self.renderer.w // 2, self.renderer.h // 2, random.uniform(-10, 10), random.uniform(-30, -10))
                    self.renderer.camera_shake.add(0.3, 0.25)
            hits = self.enemy_manager.apply_weapon_hit(p.x, p.y, p.angle, wi)
            if hits:
                self.renderer.trigger_screen_shake(4)
                for h in hits:
                    self.renderer.emit_blood(self.renderer.w // 2, self.renderer.h // 2, 10)

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
        
        # Chase scream audio: trigger scream for enemies that entered chase state
        for enemy in self.enemy_manager.enemies:
            if enemy.alive and enemy.just_entered_chase:
                enemy.just_entered_chase = False
                try:
                    audio_mgr.play_spatial(
                        'creature_call',
                        p.x, p.y, p.angle,
                        enemy.x, enemy.y,
                        base_volume=0.8,
                        max_dist=enemy.detect_range * 1.5
                    )
                except Exception:
                    pass

        # Enemy attacks
        dmg = self.enemy_manager.check_attacks(p.x, p.y)
        if dmg > 0:
            p.take_damage(dmg)
            
            # Trigger jumpscare if player dies from enemy attack
            if not p.alive:
                try:
                    from jumpscare import get_jumpscare_manager
                    jumpscare_mgr = get_jumpscare_manager()
                    stun_duration = jumpscare_mgr.trigger()
                    # Stun player for the duration (if still alive or just died)
                    if stun_duration:
                        p.stunned = True
                        p.stun_timer = stun_duration
                except Exception:
                    pass
        
        # Jumpscare sequence update (runs ~1.2s after trigger)
        try:
            from jumpscare import get_jumpscare_manager
            jumpscare_mgr = get_jumpscare_manager()
            jumpscare_mgr.update(dt)
            # Keep player stunned during jumpscare playback
            if jumpscare_mgr.is_playing():
                p.stunned = True
                p.stun_timer = 0.8
        except Exception:
            pass

        # Auto-collect pickups
        for pickup in self.game_map.get_nearby_pickups(p.x, p.y):
            if p.pickup_item(pickup):
                pickup['active'] = False
                audio_mgr.play('pickup')
                self.notify(f"Picked up {pickup['type'].replace('_', ' ').title()}")

        # Check level completion (all enemies defeated OR exit reached)
        total = getattr(self, 'level_enemy_total', 0)
        alive_now = len(self.enemy_manager.get_alive_enemies())
        all_enemies_defeated = total > 0 and alive_now == 0
        exit_reached = False
        if self.game_map.exit_pos:
            ex, ey = self.game_map.exit_pos
            if math.sqrt((ex - p.x)**2 + (ey - p.y)**2) < 1.2:
                exit_reached = True

        if all_enemies_defeated or exit_reached:
            print(f"[CHAPTER COMPLETE] Chapter {self.chapter} cleared! "
                  f"(enemies defeated: {all_enemies_defeated}, exit reached: {exit_reached})")
            self.notify(f"CHAPTER {self.chapter} CLEARED!", 3.0)
            self.advance_chapter()
            return

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
            self.radar.draw(self.internal, self.player, alive_enemies, self.game_map,
                            self.font_tiny, pygame.time.get_ticks())

            # Notification
            if self.notif_t > 0:
                nt = self.font_tiny.render(self.notif, True, SACRED_GOLD)
                self.internal.blit(nt, (8, 8))

        elif self.state == STATE_PAUSED:
            self.renderer.render_frame(
                self.player, self.game_map, alive_enemies, self.effects, dt)
            draw_hud(self.internal, self.player, self.font_sm, self.font_tiny)
            self.radar.draw(self.internal, self.player, alive_enemies, self.game_map,
                            self.font_tiny, pygame.time.get_ticks())
            draw_paused(self.internal, self.font_lg, self.font_sm)

        elif self.state == STATE_MENU:
            draw_menu(self.internal, self.font_lg, self.font_sm, self.font_tiny)

        elif self.state == STATE_INTRO:
            self.cinematic.render()

        elif self.state == STATE_GAMEOVER:
            draw_gameover(self.internal, self.font_lg, self.font_sm)

        elif self.state == STATE_WIN:
            draw_win(self.internal, self.font_lg, self.font_sm, self.chapter)
        
        # Jumpscare rendering (plays on top of scene during death sequence)
        try:
            from jumpscare import get_jumpscare_manager
            jumpscare_mgr = get_jumpscare_manager()
            if jumpscare_mgr.is_playing():
                jumpscare_mgr.render(self.internal)
        except Exception:
            pass

        # GPU post-processing shaders (ModernGL horror lighting, fog, post-process)
        # Only during gameplay, and the result is copied back into the SAME surface:
        # the renderer and cinematic hold a reference to self.internal, so it must
        # never be rebound to a new Surface object.
        if (self.state in (STATE_PLAYING, STATE_PAUSED)
                and hasattr(self.renderer, 'shader_renderer')
                and self.renderer.shader_renderer.enabled):
            time_sec = pygame.time.get_ticks() / 1000.0
            fl_on = 1 if (self.player.flashlight_on and self.player.flashlight_battery > 0) else 0
            sup_int = 1.0 if (self.player.damage_flash > 0 or self.player.sanity < 30) else 0.0
            shaded = self.renderer.shader_renderer.render(
                self.internal, time_sec, flashlight_on=fl_on, supernatural_intensity=sup_int, fog_density=1.0
            )
            if shaded is not self.internal:
                self.internal.blit(shaded, (0, 0))

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

            prev_state = self.state
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    running = False

                elif self.state == STATE_MENU:
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_RETURN:
                            self.start_new_game()
                        elif event.key == pygame.K_i:
                            self.state = STATE_INTRO
                            self.intro_to_menu = True
                            self.cinematic.reset()
                            safe_set_relative_mouse(False)
                        elif event.key == pygame.K_l:
                            self.load_saved_game()
                        elif event.key == pygame.K_ESCAPE:
                            running = False
                        elif event.key == pygame.K_F11:
                            self.toggle_fullscreen()

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
                        elif event.key == pygame.K_F11:
                            self.toggle_fullscreen()
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
                            if self.chapter + 1 <= self.max_chapter():
                                self.advance_chapter()
                                if self.state == STATE_PLAYING:
                                    safe_set_relative_mouse(True)
                            else:
                                self.state = STATE_MENU
                        elif event.key == pygame.K_m:
                            self.state = STATE_MENU

            entered_intro = (prev_state != STATE_INTRO and self.state == STATE_INTRO)

            if self.state == STATE_INTRO:
                # The key that STARTED the intro (Enter / I) must not also skip it.
                intro_events = [] if entered_intro else events
                finished = self.cinematic.update(dt, intro_events)
                if finished:
                    if self.intro_to_menu:
                        self.intro_to_menu = False
                        self.state = STATE_MENU
                    else:
                        self.load_chapter(1)
                        self.state = STATE_PLAYING
                        safe_set_relative_mouse(True)

            elif self.state == STATE_PLAYING:
                self.update_playing(dt, mouse_dx, mouse_dy)

            self.render(dt)

        pygame.quit()
        sys.exit()


# ─── Entry point ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)
    try:
        Game().run()
    except Exception as e:
        crash_log_path = os.path.join(base_dir, 'crash.log')
        import traceback
        tb = traceback.format_exc()
        try:
            with open(crash_log_path, 'w') as f:
                f.write(tb)
        except Exception:
            pass
        print(f"[FATAL CRASH] {e}\nTraceback saved to {crash_log_path}")
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, f"An error occurred:\n{e}\n\nTraceback saved to crash.log", "ANINO SA GUBAT - Fatal Error", 16)
        except Exception:
            pass
        sys.exit(1)
