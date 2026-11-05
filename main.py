"""
ANINO SA GUBAT: Mga Bulong ng Dilim
Main game loop and entry point.
"""
import gc
import os
import sys
import math
import random
import pygame

import settings as _settings_mod
# Apply the quality preset from settings.json before any module copies resolution-dependent values
_settings_mod.apply_quality_preset(_settings_mod.load_settings().get('quality_tier', _settings_mod.QUALITY_TIER))
from settings import *
from player import Player
from map_system import GameMap
from enemies import EnemyManager
from renderer import Renderer
import renderer as _renderer_mod
from perf_governor import PerfGovernor
from gl_present import GLPresenter
import shader_renderer as _shader_mod
from time import perf_counter as _perf_counter
from radar import Radar
from audio_synth import audio_mgr, FRENZY_AMBIENCE_VOLUME
from menu_music import MenuMusic
from enemy_audio import enemy_audio_mgr
from cinematic import Cinematic
from objective import next_objective, nearest_page, relative_bearing, direction_word
from page_arrow import PageArrow
from settings_menu import SettingsMenu
from asset_generator import (
    generate_all_textures, generate_all_weapons,
    generate_all_enemies, generate_all_pickups, generate_crosshair
)

# ─── Game States ─────────────────────────────────────────────────────────────
STATE_MENU     = 'menu'
STATE_INTRO    = 'intro'
STATE_PLAYING  = 'playing'
STATE_PAUSED   = 'paused'
STATE_SETTINGS = 'settings'
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


def _outlined(surf, text, x, y, color, font, edge=1):
    """Blit text with a 1px dark outline so it stays readable against the world,
    rain, grade and bloom. The outline is alpha-blended onto the UI layer, so it
    only touches pixels behind the glyph (no halos over other HUD panels)."""
    img = font.render(text, True, color)
    dark = font.render(text, True, (6, 8, 10, 235))
    for dx in (-edge, 0, edge):
        for dy in (-edge, 0, edge):
            if dx or dy:
                surf.blit(dark, (x + dx, y + dy))
    surf.blit(img, (x, y))
    return img


def draw_hud(surf, player, font_sm, font_hud, font_items=None):
    """Compact edge HUD: two-row survival strip, concise inventory, weapon and ward chips.

    All text carries a subtle dark outline (see _outlined) so the panel is legible
    over bright muzzle flashes, sunrise and the grade pass. The whole panel is drawn
    onto the UI overlay layer, which the GPU presenter composites AFTER every
    post-processing stage, so nothing here is ever blurred by the scene."""
    sw, sh = surf.get_size()
    font = font_hud
    panel = pygame.Surface((210, 48), pygame.SRCALPHA)
    panel.fill((5, 8, 11, 225))          # deep panel: bold text needs contrast, not just outline
    pygame.draw.rect(panel, (70, 82, 78, 190), panel.get_rect(), 1, border_radius=3)
    x0, y0 = 7, sh - 52
    surf.blit(panel, (x0, y0))

    def mini_stat(col, row, label, value, maximum, color):
        x = x0 + 7 + col * 67
        y = y0 + 4 + row * 21
        _outlined(surf, label, x, y, color, font)
        bw = 48
        pygame.draw.rect(surf, (24, 29, 29), (x, y + 11, bw, 4))
        ratio = max(0.0, min(1.0, float(value) / max(1.0, float(maximum))))
        if ratio > 0:
            pygame.draw.rect(surf, color, (x, y + 11, max(1, int(bw * ratio)), 4))

    hp_col = HEALTH_GREEN if player.health > 30 else HEALTH_RED
    batt_col = (220, 210, 75) if player.flashlight_battery > 30 else HEALTH_RED
    sanity_ratio = max(0.0, min(1.0, player.sanity / SANITY_MAX))
    sanity_col = (150, 80, 200) if sanity_ratio > .60 else ((220, 155, 55) if sanity_ratio > .30 else (230, 55, 55))
    mini_stat(0, 0, "HP", player.health, PLAYER_MAX_HEALTH, hp_col)
    mini_stat(1, 0, "STM", player.stamina, STAMINA_MAX, (80, 205, 135))
    mini_stat(2, 0, "BAT", player.flashlight_battery, FLASHLIGHT_MAX_BATTERY, batt_col)
    mini_stat(0, 1, "SAN", player.sanity, SANITY_MAX, sanity_col)
    mini_stat(1, 1, "FAITH", player.faith_energy, FAITH_ENERGY_MAX, (130, 160, 245))
    mini_stat(2, 1, "ARM" if player.armor > 0 else "ARM --", player.armor, PLAYER_MAX_ARMOR, (110, 165, 235) if player.armor > 0 else (105, 110, 115))

    pages_needed = PAGES_REQUIRED_CH1 if player.current_chapter == 1 else PAGES_REQUIRED_CH2
    ros = f"{player.rosary_cooldown:.0f}s" if player.rosary_cooldown > 0 else "RDY"
    crs = f"{player.cross_cooldown:.0f}s" if player.cross_cooldown > 0 else "RDY"
    # Fixed label/value columns (monospace): two spaces between groups, one inside,
    # zero-padded counts so every group parses as a fixed-width chunk.
    items_font = font_items or font
    groups = (("SALT", f"{player.salt_count:02d}"),
              ("GAR", f"{player.garlic_count:02d}"),
              ("PG", f"{player.pages_this_chapter}/{pages_needed}"),
              ("ROS", ros), ("CRS", crs))
    items = "  ".join(f"{label} {val}" for label, val in groups)
    _outlined(surf, items, x0 + 2, sh - 65, (205, 205, 190), items_font)

    pw, ph = 104, 37
    px, py = sw - pw - 7, sh - ph - 7
    pygame.draw.rect(surf, (5, 8, 11, 190), (px, py, pw, ph), border_radius=3)
    pygame.draw.rect(surf, (85, 78, 58), (px, py, pw, ph), 1, border_radius=3)
    weapon_names = ("BOLO", "SHOTGUN", "REVOLVER")
    wname = weapon_names[player.current_weapon] if 0 <= player.current_weapon < len(weapon_names) else "WEAPON"
    _outlined(surf, wname, px + 6, py + 4, GOLD, font, edge=0)
    if player.current_weapon == 1:
        ammo = f"{player.shotgun_mag}/{SHOTGUN_MAG_SIZE}  +{player.ammo_shotgun}"
    elif player.current_weapon == 2:
        ammo = f"{player.revolver_mag}/{REVOLVER_MAG_SIZE}  +{player.ammo_revolver}"
    else:
        ammo = "DURABILITY 3/3"
    _outlined(surf, ammo, px + 6, py + 18, AMMO_YELLOW, font, edge=0)
    if player.reloading:
        _outlined(surf, "RELOAD", px + 65, py + 4, (255, 190, 65), font, edge=0)

    labels = ("1 LIT", "2 SHD", "3 BAN", "4 BND", "5 FIN")
    slot_w, slot_h, gap = 32, 18, 3      # 2px+ padding around 11 px labels
    total = len(labels) * slot_w + (len(labels) - 1) * gap
    sx, sy = (sw - total) // 2, sh - slot_h - 3
    for i, label in enumerate(labels):
        unlocked = player.wards_unlocked[i]
        cooldown = player.ward_cooldowns[i] > 0
        active_light = (i == 0 and player.flashlight_on and player.flashlight_battery > 0)
        color = ((255, 225, 110) if active_light else
                 (205, 180, 105) if unlocked and not cooldown else
                 (115, 115, 115) if unlocked else (65, 65, 65))
        rect = pygame.Rect(sx + i * (slot_w + gap), sy, slot_w, slot_h)
        pygame.draw.rect(surf, (8, 10, 12, 185), rect, border_radius=2)
        pygame.draw.rect(surf, (145, 115, 65) if active_light else (65, 70, 68), rect, 1, border_radius=2)
        shown = f"{i+1} {int(player.ward_cooldowns[i])}" if cooldown else label
        img = font.render(shown, True, color)
        surf.blit(img, (rect.x + (slot_w - img.get_width()) // 2, rect.y + (slot_h - img.get_height()) // 2))


# ─── Menu screens ─────────────────────────────────────────────────────────────
def draw_menu(surf, font_lg, font_sm, font_tiny):
    """Draw an atmospheric, animated title screen inspired by a haunted Philippine forest."""
    sw, sh = surf.get_size()
    t = pygame.time.get_ticks() / 1000.0
    surf.fill((4, 7, 11))

    # Distant moon and layered forest silhouettes.
    moon_x, moon_y = int(sw * .79), int(sh * .25)
    moon_r = max(15, int(min(sw, sh) * .105))
    pygame.draw.circle(surf, (38, 43, 43), (moon_x, moon_y), moon_r + 9)
    pygame.draw.circle(surf, (125, 119, 91), (moon_x, moon_y), moon_r)
    pygame.draw.circle(surf, (92, 91, 76), (moon_x - moon_r // 3, moon_y - moon_r // 4), max(2, moon_r // 7))
    pygame.draw.circle(surf, (102, 98, 80), (moon_x + moon_r // 3, moon_y + moon_r // 3), max(2, moon_r // 9))

    pygame.draw.polygon(surf, (11, 19, 20), [
        (0, int(sh * .48)), (int(sw * .16), int(sh * .34)),
        (int(sw * .31), int(sh * .49)), (int(sw * .48), int(sh * .37)),
        (int(sw * .66), int(sh * .50)), (int(sw * .83), int(sh * .36)),
        (sw, int(sh * .48)), (sw, sh), (0, sh)])
    pygame.draw.polygon(surf, (7, 13, 15), [
        (0, int(sh * .62)), (int(sw * .18), int(sh * .46)),
        (int(sw * .35), int(sh * .63)), (int(sw * .55), int(sh * .47)),
        (int(sw * .73), int(sh * .64)), (int(sw * .9), int(sh * .48)),
        (sw, int(sh * .61)), (sw, sh), (0, sh)])

    # A ruined wooden shrine gate sits in the moonlit clearing.
    gx, gy = int(sw * .77), int(sh * .60)
    gate_w, gate_h = int(sw * .22), int(sh * .34)
    post_w = max(4, gate_w // 18)
    pygame.draw.rect(surf, (28, 27, 24), (gx - gate_w // 2, gy - gate_h, post_w, gate_h))
    pygame.draw.rect(surf, (28, 27, 24), (gx + gate_w // 2 - post_w, gy - gate_h, post_w, gate_h))
    pygame.draw.rect(surf, (43, 35, 28), (gx - gate_w // 2 - 9, gy - gate_h, gate_w + 18, max(5, sh // 45)))
    pygame.draw.rect(surf, (35, 29, 25), (gx - gate_w // 2 - 15, gy - gate_h + 7, gate_w + 30, max(4, sh // 65)))
    pygame.draw.line(surf, (53, 39, 29), (gx - gate_w // 2, gy - gate_h // 2),
                     (gx + gate_w // 2, gy - gate_h // 2), 2)

    # Twisted balete-like trees frame both sides of the screen.
    for side, base_x in ((-1, int(sw * .035)), (1, int(sw * .965))):
        trunk_w = max(12, int(sw * .045))
        lean = int(sw * .055) * side
        pygame.draw.polygon(surf, (5, 9, 10), [
            (base_x - trunk_w, sh), (base_x + trunk_w, sh),
            (base_x + lean + trunk_w // 2, int(sh * .28)),
            (base_x + lean - trunk_w // 2, int(sh * .24))])
        for branch in range(4):
            y = int(sh * (.34 + branch * .12))
            end_x = base_x - side * int(sw * (.10 + branch * .015))
            pygame.draw.line(surf, (6, 10, 11),
                             (base_x + lean // 2, y + int(sh * .08)),
                             (end_x, y - int(sh * .08)), max(2, sw // 180))
            pygame.draw.line(surf, (6, 10, 11), (end_x, y - int(sh * .08)),
                             (end_x - side * int(sw * .035), y - int(sh * .15)),
                             max(2, sw // 220))

    # Slow drifting mist.
    fog = pygame.Surface((sw, sh), pygame.SRCALPHA)
    for i in range(4):
        y = int(sh * (.56 + i * .085) + math.sin(t * .32 + i * 1.7) * sh * .018)
        alpha = 18 + int(9 * (0.5 + 0.5 * math.sin(t * .45 + i)))
        pygame.draw.ellipse(fog, (115, 126, 119, alpha),
                            (int(sw * (-.12 + i * .08)), y, int(sw * 1.15), max(8, int(sh * .10))))
    surf.blit(fog, (0, 0))
    pygame.draw.polygon(surf, (3, 6, 7), [
        (0, int(sh * .88)), (int(sw * .18), int(sh * .82)),
        (int(sw * .36), int(sh * .91)), (int(sw * .58), int(sh * .84)),
        (int(sw * .79), int(sh * .92)), (sw, int(sh * .84)), (sw, sh), (0, sh)])

    # Left-side shadow veil keeps the title and controls readable.
    veil = pygame.Surface((sw, sh), pygame.SRCALPHA)
    pygame.draw.rect(veil, (2, 5, 8, 185), (0, 0, int(sw * .57), sh))
    surf.blit(veil, (0, 0))

    margin = max(22, int(sw * .075))
    eyebrow = font_tiny.render("A PHILIPPINE FOLK HORROR EXPERIENCE", True, (151, 126, 82))
    surf.blit(eyebrow, (margin, int(sh * .16)))
    title = font_lg.render("ANINO SA GUBAT", True, (218, 190, 125))
    shadow = font_lg.render("ANINO SA GUBAT", True, (25, 18, 14))
    title_y = int(sh * .23)
    surf.blit(shadow, (margin + 2, title_y + 3))
    surf.blit(title, (margin, title_y))
    pygame.draw.line(surf, (126, 87, 48), (margin, title_y + title.get_height() + 8),
                     (margin + int(sw * .37), title_y + title.get_height() + 8), 2)
    subtitle = font_sm.render("Mga Bulong ng Dilim", True, (184, 166, 130))
    surf.blit(subtitle, (margin, title_y + title.get_height() + 18))
    whisper = font_tiny.render('"Huwag kang lilingon."', True, (126, 119, 104))
    surf.blit(whisper, (margin, title_y + title.get_height() + 43))

    # Keyboard menu panel, preserving the existing game controls.
    panel_x, panel_y = margin, int(sh * .57)
    panel_w, panel_h = min(int(sw * .43), 330), min(int(sh * .34), 124)
    panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    panel.fill((5, 8, 10, 205))
    pygame.draw.rect(panel, (82, 66, 45, 190), (0, 0, panel_w, panel_h), 1)
    surf.blit(panel, (panel_x, panel_y))

    menu_rows = [
        ("ENTER", "BEGIN YOUR NIGHT", True),
        ("F11", "TOGGLE FULLSCREEN", True),
        ("ESC", "LEAVE THE FOREST", True),
    ]
    row_h = max(19, min(25, (panel_h - 10) // len(menu_rows)))
    for i, (key, label, enabled) in enumerate(menu_rows):
        y = panel_y + 6 + i * row_h
        key_img = font_tiny.render(key, True, (224, 190, 120) if enabled else (85, 83, 76))
        label_img = font_tiny.render(label, True, (218, 214, 198) if enabled else (93, 91, 85))
        key_w = max(38, key_img.get_width() + 12)
        pygame.draw.rect(surf, (28, 24, 19) if enabled else (15, 16, 16),
                         (panel_x + 8, y, key_w, row_h - 3), 1)
        surf.blit(key_img, (panel_x + 8 + (key_w - key_img.get_width()) // 2, y + 2))
        surf.blit(label_img, (panel_x + key_w + 18, y + 2))
        if i == 0:
            pulse = 0.5 + 0.5 * math.sin(t * 2.2)
            marker_col = (int(130 + pulse * 75), int(83 + pulse * 35), 45)
            pygame.draw.rect(surf, marker_col, (panel_x + 2, y + 2, 2, row_h - 7))

    footer = font_tiny.render("S  SETTINGS   •   THE TREES ARE LISTENING", True, (105, 105, 92))
    surf.blit(footer, (margin, sh - footer.get_height() - 9))


def draw_paused(surf, font_lg, font_sm):
    overlay = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 140))
    surf.blit(overlay, (0, 0))
    sw, sh = surf.get_size()
    _lines = [("PAUSED", sh // 2 - 80, WHITE, font_lg)]
    _lines += [(line, sh // 2 - 20 + i * 32, (200, 200, 200), font_sm)
               for i, line in enumerate(["ESC  -  Resume", "S  -  Settings",
                                         "F11  -  Toggle Fullscreen", "M  -  Main Menu"])]
    for text, y, color, fnt in _lines:
        _img = fnt.render(text, True, color)
        _outlined(surf, text, sw // 2 - _img.get_width() // 2, y, color, fnt)


def draw_gameover(surf, font_lg, font_sm):
    surf.fill((10, 0, 0))
    sw, sh = surf.get_size()
    t = font_lg.render("YOU DIED", True, BLOOD_RED)
    _outlined(surf, "YOU DIED", sw // 2 - t.get_width() // 2, sh // 2 - 60, BLOOD_RED, font_lg)
    for i, line in enumerate(["M  -  Return to Main Menu"]):
        lt = font_sm.render(line, True, (200, 150, 150))
        _outlined(surf, line, sw // 2 - lt.get_width() // 2, sh // 2 + i * 40, (200, 150, 150), font_sm)


def draw_win(surf, font_lg, font_sm, chapter, final=False):
    surf.fill((5, 10, 5))
    sw, sh = surf.get_size()
    if final:
        # Survival ending after collecting all five pages and reaching sunrise.
        t = font_lg.render("YOU SURVIVED UNTIL 7:00 AM", True, SACRED_GOLD)
        _outlined(surf, "YOU SURVIVED UNTIL 7:00 AM", sw // 2 - t.get_width() // 2, sh // 2 - 70, SACRED_GOLD, font_lg)
        sub = font_sm.render("You found all five Bible pages and endured the night.", True, WHITE)
        _outlined(surf, "You found all five Bible pages and endured the night.",
                  sw // 2 - sub.get_width() // 2, sh // 2 - 10, WHITE, font_sm)
        lt = font_sm.render("ENTER  -  Main Menu", True, (200, 200, 200))
        _outlined(surf, "ENTER  -  Main Menu", sw // 2 - lt.get_width() // 2, sh // 2 + 40, (200, 200, 200), font_sm)
        return
    t = font_lg.render(f"CHAPTER {chapter} COMPLETE", True, SACRED_GOLD)
    _outlined(surf, f"CHAPTER {chapter} COMPLETE", sw // 2 - t.get_width() // 2, sh // 2 - 60, SACRED_GOLD, font_lg)
    lt = font_sm.render("ENTER  -  Continue   M  -  Menu", True, WHITE)
    _outlined(surf, "ENTER  -  Continue   M  -  Menu", sw // 2 - lt.get_width() // 2, sh // 2 + 30, WHITE, font_sm)


def draw_top_hud(surf, player, game_map, font, arrow, t_ms):
    """Compact top-centre panel: Bible pages, sunrise clock and a compass arrow to the next goal.

    The arrow points at the nearest uncollected Bible page (the exit once enough pages are
    held): up = straight ahead, right = the target is on your right.
    Returns the y of the panel's bottom edge so notifications can sit just below it.
    """
    sw = surf.get_width()
    needed = PAGES_REQUIRED_CH1 if player.current_chapter == 1 else PAGES_REQUIRED_CH2
    have = min(needed, getattr(player, 'pages_this_chapter', 0))
    left = max(0, getattr(player, 'survival_time_left', 420.0))
    line1 = f"PAGES {have}/{needed}   SUNRISE {int(left // 60):02d}:{int(left % 60):02d}"

    obj = next_objective(player.x, player.y, game_map.pickups, game_map.exit_pos,
                         have, needed, REQUIRE_PAGES_FOR_EXIT)
    line2 = None
    rel = 0.0
    if obj is not None:
        rel = relative_bearing(player.x, player.y, player.angle, obj['x'], obj['y'])
        what = 'NEAREST PAGE' if obj['kind'] == 'page' else 'EXIT'
        line2 = f"{what} {int(obj['dist'])}m {direction_word(rel).upper()}"

    img1 = font.render(line1, True, SACRED_GOLD)
    img2 = font.render(line2, True, WHITE) if line2 else None
    arrow_w = arrow.size + 4 if line2 else 0
    text_w = max(img1.get_width(), img2.get_width() if img2 else 0)
    th = img1.get_height()
    pad = 4
    lead = 4  # roomier gap between the pages/sunrise line and the objective line
    panel_w = arrow_w + text_w + pad * 2
    panel_h = max(arrow.size if line2 else 0, th * (2 if img2 else 1) + lead) + pad * 2
    x0 = sw // 2 - panel_w // 2
    y0 = 4

    # Slightly deeper panel + 1px border so the objective strip stands out against
    # the tree line at the top of the viewport.
    bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    bg.fill((10, 10, 15, 220))
    pygame.draw.rect(bg, (90, 100, 95, 150), (0, 0, panel_w, panel_h), 1)
    surf.blit(bg, (x0, y0))

    tx = x0 + pad + arrow_w
    ty = y0 + (panel_h - (th * (2 if img2 else 1) + lead)) // 2
    _outlined(surf, line1, tx, ty, SACRED_GOLD, font, edge=0)
    if img2:
        _outlined(surf, line2, tx, ty + th + lead, WHITE, font, edge=0)
        arrow.draw(surf, x0 + pad + arrow.size // 2, y0 + panel_h // 2, rel, t_ms)
    return y0 + panel_h


# ─── Startup Loading Animation ───────────────────────────────────────────────
_GL_PRESENT_HOOK = None   # set by Game when the OpenGL window is active (see Game._install_present_hook)


def draw_loading_step(screen, clock, font_lg, font_sm, step_text, progress):
    """Render a brief animated ritual-style loading scene."""
    sw, sh = screen.get_size()
    progress = max(0.0, min(1.0, float(progress)))
    started = pygame.time.get_ticks()
    duration_ms = 520

    while pygame.time.get_ticks() - started < duration_ms:
        now = pygame.time.get_ticks()
        t = now / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        # Cold midnight gradient.
        for y in range(0, sh, 4):
            k = y / max(1, sh)
            col = (int(5 + 5*k), int(8 + 5*k), int(13 + 4*k))
            pygame.draw.rect(screen, col, (0, y, sw, 4))

        # Distant moon, half-hidden by the canopy.
        mx, my = int(sw * .78), int(sh * .25)
        mr = max(18, int(min(sw, sh) * .085))
        pygame.draw.circle(screen, (25, 34, 34), (mx, my), mr + 12)
        pygame.draw.circle(screen, (91, 91, 76), (mx, my), mr)
        pygame.draw.circle(screen, (69, 73, 64), (mx - mr//3, my - mr//4), max(3, mr//7))

        # Dense, layered forest silhouettes.
        pygame.draw.polygon(screen, (12, 22, 23), [
            (0, int(sh*.53)), (int(sw*.15), int(sh*.34)), (int(sw*.29), int(sh*.55)),
            (int(sw*.46), int(sh*.37)), (int(sw*.63), int(sh*.56)),
            (int(sw*.82), int(sh*.35)), (sw, int(sh*.54)), (sw, sh), (0, sh)])
        pygame.draw.polygon(screen, (5, 11, 13), [
            (0, int(sh*.68)), (int(sw*.2), int(sh*.48)), (int(sw*.38), int(sh*.7)),
            (int(sw*.59), int(sh*.49)), (int(sw*.78), int(sh*.7)),
            (sw, int(sh*.5)), (sw, sh), (0, sh)])

        # Jagged trunks and reaching branches frame the ritual.
        for side, x in ((-1, int(sw*.035)), (1, int(sw*.965))):
            lean = int(sw*.055) * side
            tw = max(14, int(sw*.04))
            pygame.draw.polygon(screen, (3, 7, 8), [
                (x-tw, sh), (x+tw, sh), (x+lean+tw//2, int(sh*.19)),
                (x+lean-tw//2, int(sh*.22))])
            for j in range(4):
                yy = int(sh*(.29+j*.13))
                ex = x - side*int(sw*(.09+j*.025))
                pygame.draw.line(screen, (4, 8, 9),
                    (x+lean//2, yy+int(sh*.08)), (ex, yy-int(sh*.07)), max(2, sw//220))

        # Floating mist ribbons with a slow sideways drift.
        mist = pygame.Surface((sw, sh), pygame.SRCALPHA)
        for i in range(5):
            yy = int(sh*(.55+i*.075) + math.sin(t*.55+i*1.4)*sh*.018)
            xx = int(sw*(-.2 + ((t*.025+i*.17) % 1.0)))
            pygame.draw.ellipse(mist, (119, 132, 125, 16+i*3),
                (xx, yy, int(sw*.82), max(12, int(sh*.055))))
        screen.blit(mist, (0, 0))

        # A pulsing blood-red summoning circle.
        cx, cy = int(sw*.73), int(sh*.70)
        radius = int(min(sw, sh)*(.115 + .004*math.sin(t*3.0)))
        glow = pygame.Surface((sw, sh), pygame.SRCALPHA)
        for ring in range(3):
            rr = radius + ring*8
            pygame.draw.circle(glow, (142, 28, 27, max(8, 42-ring*12)), (cx, cy), rr, 2)
        pygame.draw.circle(glow, (165, 39, 34, 150), (cx, cy), radius, 2)
        pygame.draw.polygon(glow, (155, 39, 34, 115), [
            (cx, cy-radius+5), (cx+int(radius*.86), cy+radius//2),
            (cx-int(radius*.86), cy+radius//2)], 2)
        for i in range(12):
            a = (math.tau*i/12) + t*.12
            x1 = cx + int(math.cos(a)*(radius+5))
            y1 = cy + int(math.sin(a)*(radius+5))
            x2 = cx + int(math.cos(a)*(radius+15))
            y2 = cy + int(math.sin(a)*(radius+15))
            pygame.draw.line(glow, (180, 48, 38, 150), (x1,y1), (x2,y2), 2)
        screen.blit(glow, (0, 0))

        # A pair of faint eyes flicker between the trees.
        flicker = int(70 + 45*(.5+.5*math.sin(t*7.3)))
        eye_x, eye_y = int(sw*.88), int(sh*.57)
        pygame.draw.circle(screen, (flicker, 20, 17), (eye_x, eye_y), 3)
        pygame.draw.circle(screen, (flicker, 20, 17), (eye_x+13, eye_y), 3)

        # Dark parchment panel for readable loading text.
        panel_x, panel_y = int(sw*.075), int(sh*.16)
        # Give the progress description and bottom warning separate rows.
        # At the old .52h panel height, both text baselines landed at almost
        # the same y-coordinate on the 640x360 internal canvas.
        panel_w, panel_h = int(sw*.54), int(sh*.64)
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((2, 5, 8, 218))
        pygame.draw.rect(panel, (91, 54, 43, 170), (0, 0, panel_w, panel_h), 1)
        screen.blit(panel, (panel_x, panel_y))

        eyebrow = font_sm.render("THE FOREST IS WAKING", True, (153, 77, 63))
        screen.blit(eyebrow, (panel_x+24, panel_y+22))
        title = font_lg.render("ANINO SA GUBAT", True, (205, 180, 132))
        screen.blit(title, (panel_x+22, panel_y+58))
        subtitle = font_sm.render("Mga Bulong ng Dilim", True, (145, 137, 117))
        screen.blit(subtitle, (panel_x+25, panel_y+58+title.get_height()+5))

        # Ritual progress track, segmented like sealed runes.
        bar_x, bar_y = panel_x+25, panel_y+int(panel_h*.62)
        bar_w, bar_h = panel_w-50, max(12, int(sh*.018))
        pygame.draw.rect(screen, (25, 23, 23), (bar_x, bar_y, bar_w, bar_h))
        pygame.draw.rect(screen, (105, 65, 54), (bar_x, bar_y, bar_w, bar_h), 1)
        filled = int((bar_w-4)*progress)
        if filled > 0:
            pygame.draw.rect(screen, (125, 35, 31), (bar_x+2, bar_y+2, filled, bar_h-4))
            pulse_x = bar_x + 2 + filled
            pygame.draw.line(screen, (226, 105, 73), (pulse_x, bar_y-3),
                             (pulse_x, bar_y+bar_h+3), 2)
        for i in range(1, 10):
            tick_x = bar_x + int(bar_w*i/10)
            pygame.draw.line(screen, (67, 51, 46), (tick_x, bar_y), (tick_x, bar_y+bar_h), 1)

        # Keep the description and percentage in separate horizontal regions.
        # Long loading labels (for example, "Summoning the forest entities...")
        # previously extended underneath the percentage on the same line.
        pct = font_sm.render(f"{int(progress*100):02d}%", True, (177, 86, 69))
        desc_max_w = max(40, bar_w - pct.get_width() - 14)
        desc_text = str(step_text)
        while desc_text and font_sm.size(desc_text + "...")[0] > desc_max_w:
            desc_text = desc_text[:-1]
        if desc_text != str(step_text):
            desc_text = desc_text.rstrip() + "..."
        desc = font_sm.render(desc_text, True, (203, 194, 174))
        text_y = bar_y+bar_h+17
        screen.blit(desc, (bar_x, text_y))
        screen.blit(pct, (bar_x+bar_w-pct.get_width(), text_y))

        warning = font_sm.render("DO NOT ANSWER WHEN IT CALLS YOUR NAME", True, (105, 91, 79))
        screen.blit(warning, (panel_x+25, panel_y+panel_h-30))

        if _GL_PRESENT_HOOK is not None:
            _GL_PRESENT_HOOK(screen)      # GPU presentation path: upload this frame to the GL window
        pygame.display.flip()
        clock.tick(30)

    # Leave the final frame visible after the short animation.
    return


# ─── Game class ───────────────────────────────────────────────────────────────
class Game:
    def __init__(self):
        pygame.init()
        print(f"[{BUILD_VERSION}] Starting ANINO SA GUBAT...")
        
        # Phase 3 Runtime Diagnostics
        import sys, os, settings, map_system, renderer, asset_generator
        print(f"[DIAGNOSTICS] Python Executable: {sys.executable}")
        print(f"[DIAGNOSTICS] Entry Point: {__file__}")
        print(f"[DIAGNOSTICS] CWD: {os.getcwd()}")
        print(f"[DIAGNOSTICS] Settings module: {settings.__file__}")
        print(f"[DIAGNOSTICS] MapSystem module: {map_system.__file__}")
        print(f"[DIAGNOSTICS] Renderer module: {renderer.__file__}")
        print(f"[DIAGNOSTICS] AssetGen module: {asset_generator.__file__}")
        test_gm = map_system.GameMap(1)
        print(f"[DIAGNOSTICS] Map Dimensions: width={test_gm.width}, height={test_gm.height}")
        print(f"[DIAGNOSTICS] Trees Generated (Chapter 1): {len(test_gm.trees)}")
        print(f"[DIAGNOSTICS] Undergrowth Generated: {len(test_gm.undergrowth)}")

        # Avoid half-refresh VSync throttling (often exactly 30 FPS on 60 Hz displays).
        # The main loop already applies a 60 FPS software cap, so presentation stays paced
        # without forcing the GPU to wait for every monitor refresh.
        self.vsync_enabled = bool((getattr(_settings_mod, 'RUNTIME_SETTINGS', None) or {}).get('vsync', False))
        self.gl_presenter = None
        # GC policy state: the cyclic collector is enabled by default (Python's normal
        # state) until load_chapter() primes + disables it for gameplay.
        self._gc_enabled_now = True
        self._gc_menu_secs = 0.0
        self.screen = self._set_display_mode()
        self._install_present_hook()
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()

        # .convert() matches the surface to the display's pixel format so all
        # blits onto this surface use the fast SDL blitter instead of the slow
        # software fallback.  This is the single biggest pygame optimisation.
        try:
            self.internal = pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT)).convert()
        except Exception:
            self.internal = pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT))

        _rt = (getattr(_settings_mod, 'RUNTIME_SETTINGS', None) or {})
        self._ui_scale = self._read_ui_scale(_rt.get('ui_scale', '100%'))
        self._high_contrast = bool(_rt.get('high_contrast_ui', False))
        self._hud_visible = bool(_rt.get('hud_visible', True))
        self._make_fonts()                                       # UI type scale (respects ui_scale / high_contrast_ui)

        draw_loading_step(self.screen, self.clock, self.font_lg, self.font_sm, "Initializing Display & Subsystems...", 0.1)

        draw_loading_step(self.screen, self.clock, self.font_lg, self.font_sm, "Generating Procedural Textures & Sprites...", 0.3)
        textures      = generate_all_textures()
        # Convert to display pixel format so every blit uses SDL's fast blitter
        # instead of the slow software fallback (biggest pygame perf win).
        textures = {k: v.convert() for k, v in textures.items()}

        draw_loading_step(self.screen, self.clock, self.font_lg, self.font_sm, "Forging Weapons & Tools...", 0.5)
        weapon_spr    = generate_all_weapons()
        weapon_spr = {k: (v.convert_alpha() if v is not None else v) for k, v in weapon_spr.items()}

        draw_loading_step(self.screen, self.clock, self.font_lg, self.font_sm, "Summoning Forest Entities & AI...", 0.7)
        enemy_spr     = generate_all_enemies()
        for _states in enemy_spr.values():
            for s, spr in _states.items():
                _states[s] = spr.convert_alpha()

        draw_loading_step(self.screen, self.clock, self.font_lg, self.font_sm, "Preparing Items & Relics...", 0.85)
        pickup_spr    = {k: v.convert_alpha() for k, v in generate_all_pickups().items()}
        crosshair_spr = generate_crosshair(16).convert_alpha()

        draw_loading_step(self.screen, self.clock, self.font_lg, self.font_sm, "Entering the Forest...", 1.0)

        self.game_map      = GameMap()
        self.enemy_manager = EnemyManager()
        self.player        = Player()
        self.renderer      = Renderer(self.internal, textures, weapon_spr, enemy_spr, pickup_spr)
        # Live GPU wall rendering is an explicit opt-in while the migration bridge is validated.
        _gpu_world_cfg = (getattr(_settings_mod, 'RUNTIME_SETTINGS', None) or {}).get('gpu_world_rendering', False)
        _gpu_world_env = os.environ.get('ANINO_GPU_WALLS')
        if _gpu_world_env in ('0', '1'):
            _gpu_world_cfg = (_gpu_world_env == '1')
        if _gpu_world_cfg:
            _presenter = getattr(self, 'gl_presenter', None)
            if _presenter is not None and getattr(_presenter, 'ctx', None) is not None:
                self.renderer.attach_gpu_wall_pass(_presenter.ctx)
            else:
                print("[GPU WORLD] Requested but OpenGL presentation is unavailable; CPU walls remain active.")
        self.renderer.crosshair = crosshair_spr
        self.renderer.clock = self.clock
        # Quality-preserving performance monitor: reports slow frame work without shedding effects.
        self.perf = PerfGovernor(self.renderer, _renderer_mod, _settings_mod,
                                 enabled=bool((getattr(_settings_mod, 'RUNTIME_SETTINGS', None) or {}).get('adaptive_perf', True)))
        self._loop_t0 = _perf_counter()
        self._work_ms = 0.0
        self.cinematic     = Cinematic(self.internal)
        self.radar         = Radar()

        self.state   = STATE_MENU
        self.intro_to_menu = False      # True: after the intro, go back to the menu
        self.chapter = 1
        self.level_enemy_total = 0
        self.effects = []
        self.notif   = ''
        self.notif_t = 0.0
        self.survival_spawn_timer = 18.0
        self.survival_spawn_count = 0
        self.pages_complete_notified = False
        self.sunrise_missed_notified = False
        # Graphics quality manager for runtime switching
        self._graphics_mgr = None
        self._try_init_graphics_manager()
        self.settings_menu = SettingsMenu()
        self.settings_return_state = STATE_MENU
        self.menu_music = MenuMusic()
        self.target_fps = FPS

    @staticmethod
    def _read_ui_scale(value):
        """'90%'..'150%' (settings ui_scale) -> 0.9..1.5 multiplier; clamped and forgiving."""
        try:
            return max(0.9, min(1.5, float(str(value).strip().rstrip('%')) / 100.0))
        except (ValueError, TypeError):
            return 1.0

    def _make_fonts(self):
        """(Re)build the UI type scale.

        ``ui_scale`` grows every size proportionally; ``high_contrast_ui`` adds bold
        weight so text holds up over any scene lighting. Sizes are on the 640x360
        internal canvas: 8-10 px glyphs were unreadable once upscaled 2x to 720p.
        """
        s = self._ui_scale

        def f(size, bold=False):
            return pygame.font.SysFont('consolas', max(6, int(round(size * s))), bold=bold or self._high_contrast)

        self.font_lg = f(32, True)
        self.font_sm = f(18)
        self.font_tiny = f(13)
        self.font_micro = f(12)        # objective / radar / notification / item row
        self.font_hud = f(11, True)    # dense in-game status labels (bold tier)
        self.page_arrow = PageArrow(max(16, int(round(24 * s))))

    def _apply_settings(self, values):
        """Apply settings that affect live game systems."""
        global FULLSCREEN, SCREEN_WIDTH, SCREEN_HEIGHT, PLAYER_ROT_SPEED
        resolution = values.get("resolution", "1280 x 720")
        try:
            SCREEN_WIDTH, SCREEN_HEIGHT = [int(part.strip()) for part in resolution.split("x")]
        except (ValueError, AttributeError):
            SCREEN_WIDTH, SCREEN_HEIGHT = 1280, 720
        requested_fullscreen = bool(values.get("fullscreen", FULLSCREEN))
        display_changed = (requested_fullscreen != FULLSCREEN or self.screen.get_size() != (SCREEN_WIDTH, SCREEN_HEIGHT)
                           or bool(values.get("vsync", False)) != getattr(self, "vsync_enabled", False))
        FULLSCREEN = requested_fullscreen
        if display_changed:
            self.screen = self._set_display_mode()
        self.target_fps = 240 if str(values.get("fps_limit", "60")).lower() == "unlimited" else int(values.get("fps_limit", 60))
        self.vsync_enabled = bool(values.get("vsync", False))
        tier = str(values.get("quality_tier", "medium")).lower()
        if self._graphics_mgr is not None and tier in ("low", "medium", "high"):
            try:
                self._graphics_mgr.apply_tier(tier)
            except Exception as exc:
                print(f"[SETTINGS] Quality apply failed: {exc}")
        new_scale = self._read_ui_scale(values.get("ui_scale", "100%"))
        new_hc = bool(values.get("high_contrast_ui", False))
        self._hud_visible = bool(values.get("hud_visible", True))
        if new_scale != self._ui_scale or new_hc != self._high_contrast:
            self._ui_scale, self._high_contrast = new_scale, new_hc
            self._make_fonts()
        try:
            import player as player_module
            player_module.PLAYER_ROT_SPEED = float(values.get("mouse_sensitivity", 0.002))
        except Exception:
            pass
        try:
            master = max(0.0, min(1.0, float(values.get("master_volume", 0.7))))
            music = max(0.0, min(1.0, float(values.get("music_volume", 0.4))))
            sfx = max(0.0, min(1.0, float(values.get("sfx_volume", 0.8))))
            # Keep the procedural audio engine in sync with the live sliders.
            # The intro score and cinematic cues use SoundManager channels, not
            # pygame.mixer.music, so changing only the music stream leaves them
            # with stale/default gains.
            audio_mgr.master_volume = master
            audio_mgr.music_volume = music
            audio_mgr.sfx_volume = sfx
            audio_mgr.ambient_volume = max(0.0, min(1.0, float(values.get("ambient_volume", 0.7))))
            audio_mgr.enemy_volume = max(0.0, min(1.0, float(values.get("enemy_volume", 0.8))))
            pygame.mixer.music.set_volume(master * music)
            self.menu_music.set_volume(master * music)
            for channel_index in range(4, pygame.mixer.get_num_channels()):
                pygame.mixer.Channel(channel_index).set_volume(master * sfx)
        except Exception:
            pass

    def _open_settings(self, return_state):
        self.settings_return_state = return_state
        self.settings_menu = SettingsMenu()
        self.state = STATE_SETTINGS
        safe_set_relative_mouse(False)

    def _try_init_graphics_manager(self):
        """Initialize graphics manager after renderer is created."""
        try:
            from graphics_manager import get_graphics_manager
            self._graphics_mgr = get_graphics_manager(self.renderer)
        except Exception as e:
            print(f"[QUALITY] Could not init GraphicsManager: {e}")

    def _cycle_quality(self, direction):
        """Cycle quality tier up or down."""
        if self._graphics_mgr is None:
            return
        tiers = ['low', 'medium', 'high']
        idx = tiers.index(self._graphics_mgr.tier)
        if direction == 'next':
            idx = (idx + 1) % len(tiers)
        else:
            idx = (idx - 1) % len(tiers)
        new_tier = tiers[idx]
        if self._graphics_mgr.apply_tier(new_tier):
            self.notify(f"Quality: {new_tier.upper()}")
            # Save the preference
            try:
                import settings as _s
                _s.QUALITY_TIER = new_tier
                _s.save_settings(_s.load_settings())
            except Exception:
                pass
    def _vsync_flag(self):
        """Optional VSync; disabled by default because missed 60 Hz deadlines halve presentation to 30 FPS."""
        try:
            rate = pygame.display.get_current_refresh_rate()
        except Exception:
            rate = 0
        return 1 if getattr(self, "vsync_enabled", True) and 55 <= rate <= 65 else 0

    def _gpu_present_wanted(self):
        env = os.environ.get('ANINO_GPU_PRESENT')
        if env in ('0', '1'):
            return env == '1'
        return bool((getattr(_settings_mod, 'RUNTIME_SETTINGS', None) or {}).get('gpu_present', True))

    def _close_gl(self):
        renderer = getattr(self, 'renderer', None)
        if renderer is not None and hasattr(renderer, 'close_gpu_wall_pass'):
            renderer.close_gpu_wall_pass()
        gp = getattr(self, 'gl_presenter', None)
        if gp is not None:
            gp.close()
        self.gl_presenter = None

    def _install_present_hook(self):
        global _GL_PRESENT_HOOK
        _GL_PRESENT_HOOK = self._present_raw

    def _present_raw(self, surface):
        """Used by loading screens that draw straight onto self.screen."""
        gp = getattr(self, 'gl_presenter', None)
        if gp is not None:
            try:
                gp.present(surface, post=False)
            except Exception as exc:
                print(f"[GPU] present failed during loading ({exc}); falling back to 2D.")
                self._fallback_to_2d()

    def _fallback_to_2d(self):
        self._close_gl()
        self._use_legacy_gpu_post_fallback()
        self.screen = self._set_display_mode_2d()

    @staticmethod
    def _shader_skip(skip):
        _shader_mod.ShaderRenderer.SKIP = bool(skip)

    @staticmethod
    def _legacy_gpu_post_wanted():
        """The old offscreen shader reads its framebuffer back to the CPU every frame.

        Keep that expensive compatibility path opt-in. The normal OpenGL presenter is
        readback-free; if it cannot initialize, the software renderer is the safe default.
        Set ANINO_GPU_POST=1 only when deliberately testing the legacy post-process.
        """
        return os.environ.get('ANINO_GPU_POST') == '1'

    def _use_legacy_gpu_post_fallback(self):
        enabled = self._legacy_gpu_post_wanted()
        self._shader_skip(not enabled)
        if enabled:
            print("[GPU] Legacy post-process enabled by ANINO_GPU_POST=1 (framebuffer readback may reduce FPS).")

    def _set_display_mode(self):
        """Open the window: OpenGL presentation if it verifies, else the 2D SCALED window."""
        self._close_gl()
        if self._gpu_present_wanted():
            try:
                GLPresenter.open_window((SCREEN_WIDTH, SCREEN_HEIGHT), FULLSCREEN, self._vsync_flag())
                presenter = GLPresenter()
                if presenter.attach(pygame.display.get_surface()):
                    self.gl_presenter = presenter
                    # Reattach the opt-in world pass when the display/context is recreated.
                    _gpu_world_cfg = (getattr(_settings_mod, 'RUNTIME_SETTINGS', None) or {}).get('gpu_world_rendering', False)
                    _gpu_world_env = os.environ.get('ANINO_GPU_WALLS')
                    if _gpu_world_env in ('0', '1'):
                        _gpu_world_cfg = (_gpu_world_env == '1')
                    _renderer = getattr(self, 'renderer', None)
                    if _gpu_world_cfg and _renderer is not None:
                        _renderer.attach_gpu_wall_pass(presenter.ctx)
                    # The old offscreen readback shader would duplicate the work (and open a
                    # second GL context), so the GPU presenter replaces it.
                    self._shader_skip(True)
                    # Software canvas for loading screens (they draw straight to "screen").
                    return pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT)).convert()
                presenter.close()
            except Exception as exc:
                print(f"[GPU] could not open the OpenGL window ({type(exc).__name__}: {exc}).")
        self._use_legacy_gpu_post_fallback()
        return self._set_display_mode_2d()

    def _set_display_mode_2d(self):
        """Create a low-resolution logical display that SDL scales to the monitor.

        The software renderer already draws at INTERNAL_WIDTH x INTERNAL_HEIGHT.
        Using that same size for the SCALED display lets SDL perform the final
        GPU-side upscale. A normal Surface.blit() does not resize its source, so
        the display surface and internal render surface must have matching sizes.
        """
        flags = pygame.FULLSCREEN if FULLSCREEN else 0
        size = (INTERNAL_WIDTH, INTERNAL_HEIGHT)
        vsync = self._vsync_flag()
        try:
            return pygame.display.set_mode(size, flags | pygame.SCALED, vsync=vsync)
        except Exception:
            try:
                return pygame.display.set_mode(size, flags | pygame.SCALED)
            except Exception:
                # Last-resort compatibility path: use a real display-sized surface.
                # The caller's blit is still unscaled, so keep the logical surface
                # dimensions consistent with the software render target.
                return pygame.display.set_mode(size, flags)

    def toggle_fullscreen(self):
        global FULLSCREEN
        FULLSCREEN = not FULLSCREEN
        self.screen = self._set_display_mode()
        self.notify("Fullscreen: ON" if FULLSCREEN else "Fullscreen: OFF")


        pygame.mouse.set_visible(False)

    # ── Level loading ─────────────────────────────────────────────────────
    def load_chapter(self, chapter_num):
        self.chapter = chapter_num
        self.game_map.load_chapter(chapter_num)
        sx, sy = self.game_map.player_start
        self.player = Player(sx, sy, self.game_map.player_start_angle)
        self.player.current_chapter = chapter_num
        self.player.pages_this_chapter = 0
        self.player.survival_time_left = 7 * 60.0
        self.survival_spawn_timer = 18.0
        self.survival_spawn_count = 0
        self.pages_complete_notified = False
        self.sunrise_missed_notified = False
        self.enemy_manager.spawn_enemies(self.game_map.enemies)
        self.effects = []
        self.level_enemy_total = len(self.enemy_manager.enemies)
        self.renderer.level_enemy_total = self.level_enemy_total
        self.renderer.weather.storm.reset()      # a fresh night: no leftover flash or thunder in flight
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
        # The map, textures and caches are long-lived: move them out of the garbage
        # collector's tracking so gameplay GC passes stay short (fewer frame hitches).
        # While PLAYING the cyclic collector is disabled outright; it re-enables on
        # every transition out of gameplay (see run()), where its cost is invisible.
        try:
            gc.collect()
            gc.freeze()
            gc.set_threshold(10000, 20, 20)
            gc.disable()
        except Exception:
            pass
        if hasattr(self, 'perf'):
            self.perf.reset()

    def max_chapter(self):
        return getattr(self.game_map, 'max_chapters', 2)

    def advance_chapter(self):
        """Go to the next chapter, or show the win screen after the last one."""
        next_ch = self.chapter + 1
        if next_ch <= self.max_chapter():
            print(f"[CHAPTER LOAD] Loading Chapter {next_ch}...")
            try:
                carried = self.player.capture_run_state()  # keep health, ammo, items, wards
                self.load_chapter(next_ch)
                carried.pop('x', None); carried.pop('y', None); carried.pop('angle', None)
                self.player.restore_run_state({**self.player.capture_run_state(), **carried})
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
            elif k == pygame.K_F5:
                self._cycle_quality('next')
            elif k == pygame.K_F6:
                self._cycle_quality('prev')
            elif k == pygame.K_F3:
                # F3 cycles the debug text: compact -> full -> off
                self.renderer.debug_mode = (self.renderer.debug_mode + 1) % 3
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
            elif k == pygame.K_r:
                # Play reload recordings only when the corresponding reload can start.
                can_reload_shotgun = (
                    p.current_weapon == 1 and not p.reloading
                    and p.ammo_shotgun > 0 and p.shotgun_mag < SHOTGUN_MAG_SIZE
                )
                can_reload_revolver = (
                    p.current_weapon == 2 and not p.reloading
                    and p.ammo_revolver > 0 and p.revolver_mag < REVOLVER_MAG_SIZE
                )
                p.start_reload()
                if can_reload_shotgun and p.reloading:
                    audio_mgr.play('shotgun_reload', volume=0.80, headroom=1.0)
                elif can_reload_revolver and p.reloading:
                    audio_mgr.play('revolver_reload', volume=1.0, headroom=1.0)
            elif k == pygame.K_f:
                p.flashlight_on = not p.flashlight_on
            elif k == pygame.K_e:
                self._interact()
            elif k == pygame.K_g:
                self._use_salt()
            elif k == pygame.K_h:
                self._use_garlic()
            elif k == pygame.key.key_code(CONTROLS.get('rosary', 'v')) if CONTROLS.get('rosary') else pygame.K_v:
                self._use_rosary()
            elif k == pygame.key.key_code(CONTROLS.get('cross', 'c')) if CONTROLS.get('cross') else pygame.K_c:
                self._use_cross()
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
            elif k == pygame.K_4:
                p.selected_ward = 3
                self._cast_selected_ward()
            elif k == pygame.K_5:
                p.selected_ward = 4
                self._cast_selected_ward()
            elif k == pygame.K_q:
                self._cast_selected_ward()
            elif k == pygame.K_TAB:
                p.selected_ward = (p.selected_ward + 1) % 5
        if event.type == pygame.MOUSEWHEEL:
            # Route through switch_weapon: it applies the equip delay and cancels
            # any in-progress reload (assigning current_weapon directly bypassed
            # both, letting the player fire a freshly-drawn weapon mid-reload).
            if event.y > 0:
                p.switch_weapon((p.current_weapon - 1) % 3)
            elif event.y < 0:
                p.switch_weapon((p.current_weapon + 1) % 3)
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
            if wi['type'] == 'bolo':
                self.renderer.trigger_bolo_swing()
            else:
                self.renderer.trigger_muzzle_flash()
                if wi['type'] == 'shotgun':
                    self.renderer.trigger_shotgun_fire()
            if wi['type'] in ('shotgun', 'revolver', 'bolo'):
                audio_mgr.play(wi['type'], volume=1.0, headroom=1.0)
                if wi['type'] in ('shotgun', 'revolver'):
                    self.renderer.emit_casing(self.renderer.w // 2 + 60, self.renderer.h - 30, random.uniform(40, 90), random.uniform(-110, -60))
                    self.renderer.emit_smoke(self.renderer.w // 2, self.renderer.h // 2, random.uniform(-10, 10), random.uniform(-30, -10))
                    self.renderer.camera_shake.add(0.3, 0.25)
            # The map lets the hitscan resolve walls: shots no longer punch through cover.
            hits = self.enemy_manager.apply_weapon_hit(p.x, p.y, p.angle, wi, self.game_map)
            if hits:
                self.renderer.trigger_screen_shake(4)
                for enemy in hits:
                    self.renderer.emit_blood(self.renderer.w // 2, self.renderer.h // 2, 10)
                    event = 'death' if not enemy.alive else 'hurt'
                    enemy_audio_mgr.play_spatial(
                        enemy.type,
                        event,
                        p.x,
                        p.y,
                        p.angle,
                        enemy.x,
                        enemy.y,
                        base_volume=0.9,
                        max_dist=20.0,
                    )
    def _use_salt(self):
        if self.player.use_salt():
            self.enemy_manager.add_salt_zone(self.player.x, self.player.y)
            self.notify("Salt circle placed!")

    def _use_garlic(self):
        if self.player.use_garlic():
            self.enemy_manager.add_garlic_zone(self.player.x, self.player.y)
            self.notify("Garlic thrown!")

    def _use_rosary(self):
        p = self.player
        if p.rosary_cooldown <= 0:
            if p.use_rosary():
                try:
                    audio_mgr.play('page_rustle')
                except Exception:
                    pass
                self.notify("Rosary prayed. Sanity restored.")
        else:
            self.notify(f"Rosary not ready! ({p.rosary_cooldown:.1f}s)")

    def _use_cross(self):
        p = self.player
        if p.cross_cooldown <= 0:
            if p.use_cross():
                try:
                    audio_mgr.play('pickup')
                except Exception:
                    pass
                affected = self.enemy_manager.apply_cross(p.x, p.y, radius=6.0)
                self.notify("Cross held high. Radiance restored." + (f" Repelled {len(affected)} creature(s)!" if affected else ""))
        else:
            self.notify(f"Cross not ready! ({p.cross_cooldown:.1f}s)")

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

    def _spawn_survival_enemy(self):
        """Spawn a hunter at a valid point away from the player."""
        p = self.player
        # Keep the active hunt challenging without allowing an unbounded AI crowd.
        if len(self.enemy_manager.get_alive_enemies()) >= 12:
            return False
        enemy_types = ('aswang', 'manananggal', 'multo', 'sigbin', 'white_lady', 'tikbalang', 'kapre')
        for _ in range(40):
            angle = random.uniform(0.0, math.tau)
            distance = random.uniform(13.0, 28.0)
            x = max(2.5, min(self.game_map.width - 2.5, p.x + math.cos(angle) * distance))
            y = max(2.5, min(self.game_map.height - 2.5, p.y + math.sin(angle) * distance))
            if not self.game_map.is_solid(x, y) and math.hypot(x - p.x, y - p.y) >= 10.0:
                from enemies import Enemy
                enemy = Enemy(random.choice(enemy_types), x, y)
                self.enemy_manager.enemies.append(enemy)
                self.survival_spawn_count += 1
                # Keep the debug denominator aligned with the cumulative population:
                # survival hunters are additional chapter spawns, not replacements.
                self.level_enemy_total += 1
                self.renderer.level_enemy_total = self.level_enemy_total
                self.notify('Something is hunting you in the forest...', 2.0)
                return True
        return False

    # ── Update (playing) ──────────────────────────────────────────────────
    def update_playing(self, dt, mouse_dx, mouse_dy):
        p   = self.player
        setattr(p, '_last_mouse_dx', mouse_dx)
        keys = pygame.key.get_pressed()
        p.update(dt, keys, mouse_dx, mouse_dy, self.game_map)
        # Update procedural world chunks around player for infinite exploration
        if hasattr(self.game_map, 'world_engine'):
            self.game_map.world_engine.update_world_chunks(p.x, p.y, self.game_map)


        # Footsteps: one per foot landing in the walk cycle (player.step_event), so the sound
        # is locked to the movement.  Sprinting is loud and wide, crouching is soft and close;
        # the pan alternates a little left/right so the two feet are heard from their own side.
        if p.step_event:
            p.step_event = False
            if p.is_sprinting:
                step_vol, step_pan = 0.75, 0.22
            elif p.is_crouching:
                step_vol, step_pan = 0.16, 0.06
            else:
                step_vol, step_pan = 0.42, 0.14
            audio_mgr.play_footstep(volume=step_vol, pan=p.step_side * step_pan)

        # Enemy AI with stealth sensing and sanity proximity
        self.enemy_manager.update(dt, p.x, p.y, self.game_map, player=self.player)

        # Each living enemy emits its own spatial "tik-tik-tik" stalking call.
        # Independent timers prevent a synchronized chorus; closer enemies call
        # more often and louder, while distance/panning keeps their direction clear.
        for enemy in self.enemy_manager.enemies:
            if not enemy.alive:
                continue

            # Keep the original attack vocalization clear: stalking clicks must
            # never overlap an enemy that has entered its attack animation/state.
            enemy_state = getattr(getattr(enemy, 'state', None), 'value', getattr(enemy, 'state', None))
            scream_pause = getattr(enemy, '_scream_pause_timer', 0.0)
            if scream_pause > 0.0:
                enemy._scream_pause_timer = max(0.0, scream_pause - dt)
                enemy._tiktik_timer = max(getattr(enemy, '_tiktik_timer', 0.0), 0.25)
                continue
            # Suppress Tik-Tik only while a chase scream is queued/playing.
            # The 'attack' AI state also means the enemy is actively chasing, so
            # blocking it here would silence stalking clicks for the whole pursuit.
            if enemy.just_entered_chase:
                enemy._tiktik_timer = max(getattr(enemy, '_tiktik_timer', 0.0), 0.35)
                continue

            dist = enemy.distance_to(p.x, p.y)
            if not hasattr(enemy, '_tiktik_timer'):
                enemy._tiktik_timer = random.uniform(0.25, 2.4)
            enemy._tiktik_timer -= dt
            if dist <= 22.0 and enemy._tiktik_timer <= 0.0:
                proximity = max(0.0, min(1.0, 1.0 - dist / 22.0))
                # Stronger, more readable stalking call; attack sounds are still
                # protected by the attack-state pause above.
                intensity = 0.35 + proximity * 0.65
                try:
                    enemy_audio_mgr.play_spatial(
                        enemy.type, 'tiktik',
                        p.x, p.y, p.angle, enemy.x, enemy.y,
                        base_volume=intensity, max_dist=22.0,
                    )
                except Exception as exc:
                    print(f"[Audio] tiktik sound failed for {enemy.type}: {exc}")
                # A nearby hunter clicks rapidly; distant ones are sparse and unsettling.
                enemy._tiktik_timer = random.uniform(
                    1.05 - proximity * 0.45,
                    2.8 - proximity * 1.05,
                )
            elif dist > 22.0:
                enemy._tiktik_timer = max(enemy._tiktik_timer, 0.15)

        # Loot: enemies that just died may drop a pickup where they fell
        try:
            from enemies import DROP_LABELS
            for drop in self.enemy_manager.collect_drops(self.game_map, self.player):
                label = DROP_LABELS.get(drop['type'], drop['type'].replace('_', ' ').title())
                self.notify(f"{drop['from'].replace('_', ' ').title()} dropped {label}")
        except Exception:
            import traceback
            traceback.print_exc()
        
        # Recurring chase screams: each enemy keeps its own cooldown and voice.
        # Tik-Tik is paused only for the scream plus its short reverb tail.
        for enemy in self.enemy_manager.enemies:
            if not enemy.alive:
                continue
            enemy_state = getattr(getattr(enemy, 'state', None), 'value', getattr(enemy, 'state', None))
            pursuing = enemy_state in ('investigate', 'stalk', 'attack')
            should_scream = False

            if enemy.just_entered_chase:
                enemy.just_entered_chase = False
                should_scream = True
            elif pursuing:
                enemy._chase_scream_timer = max(
                    0.0, getattr(enemy, '_chase_scream_timer', random.uniform(3.0, 4.5)) - dt
                )
                if enemy._chase_scream_timer <= 0.0:
                    should_scream = True
            else:
                enemy._chase_scream_timer = 0.0

            if should_scream:
                try:
                    enemy._scream_pause_timer = enemy_audio_mgr.duration_for(enemy.type, 'scream')
                    enemy_audio_mgr.play_spatial(
                        enemy.type,
                        'scream',
                        p.x,
                        p.y,
                        p.angle,
                        enemy.x,
                        enemy.y,
                        base_volume=1.0,
                        max_dist=enemy.detect_range * 2.4,
                    )
                    enemy._chase_scream_timer = random.uniform(4.5, 6.0)
                except Exception as exc:
                    print(f"[Audio] chase scream failed for {enemy.type}: {exc}")
                    enemy._chase_scream_timer = 2.0

        # Enemy attacks
        dmg = self.enemy_manager.check_attacks(p.x, p.y)
        attackers = self.enemy_manager.last_attackers

        for enemy in attackers:
            try:
                enemy_audio_mgr.play_spatial(
                    enemy.type,
                    'attack',
                    p.x,
                    p.y,
                    p.angle,
                    enemy.x,
                    enemy.y,
                    base_volume=1.0,
                    max_dist=20.0,
                )
            except Exception as e:
                print(f"[Audio] attack sound failed for {enemy.type}: {e}")

        if dmg > 0:
            p.take_damage(dmg)
            
            # Trigger jumpscare if player dies from enemy attack
            if not p.alive:
                try:
                    from jumpscare import get_jumpscare_manager
                    jumpscare_mgr = get_jumpscare_manager()
                    attack_enemy = (
                        min(
                            attackers,
                            key=lambda enemy: enemy.distance_to(p.x, p.y),
                        )
                        if attackers
                        else None
                    )
                    etype = attack_enemy.type if attack_enemy else 'aswang'
                    dist = attack_enemy.distance_to(p.x, p.y) if attack_enemy else 0.0
                    stun_duration = jumpscare_mgr.trigger(enemy_type=etype, distance=dist)
                    if stun_duration:
                        p.stunned = True
                        p.stun_timer = stun_duration
                except Exception:
                    import traceback
                    print("[Jumpscare] trigger failed:")
                    traceback.print_exc()
        
        # Auto-collect pickups
        for pickup in self.game_map.get_nearby_pickups(p.x, p.y):
            if p.pickup_item(pickup):
                pickup['active'] = False
                audio_mgr.play('pickup')
                self.notify(f"Picked up {pickup['type'].replace('_', ' ').title()}")

        # Check level completion: reaching exit with required pages advances chapter
        if getattr(self.game_map, 'exit_pos', None):
            ex, ey = self.game_map.exit_pos
            if math.hypot(ex - p.x, ey - p.y) < 2.0:
                pages_needed = PAGES_REQUIRED_CH1 if self.chapter == 1 else PAGES_REQUIRED_CH2
                pages_have = getattr(p, 'pages_this_chapter', p.bible_pages)
                if pages_have >= pages_needed or pages_have >= 3:
                    self.notify(f"CHAPTER {self.chapter} CLEARED!", 3.0)
                    self.advance_chapter()
                    return
                else:
                    if not getattr(self, '_exit_sealed_notified', False):
                        self._exit_sealed_notified = True
                        self.notify(f"The way is sealed. Find all {pages_needed} Bible pages!", 3.0)
            else:
                self._exit_sealed_notified = False

        # Survival objective: collect all five pages, then endure the night until 7 AM.
        self.player.survival_time_left = max(0.0, self.player.survival_time_left - dt)
        self.survival_spawn_timer -= dt
        if self.survival_spawn_timer <= 0.0:
            self._spawn_survival_enemy()
            # The forest grows more aggressive as sunrise approaches.
            interval = max(10.0, 30.0 - self.survival_spawn_count * 1.2)
            sanity_ratio = max(0.0, min(1.0, p.sanity / SANITY_MAX))
            spawn_multiplier = (SANITY_SPAWN_MIN_INTERVAL_MULTIPLIER
                                + (1.0 - SANITY_SPAWN_MIN_INTERVAL_MULTIPLIER) * sanity_ratio)
            interval *= spawn_multiplier
            self.survival_spawn_timer = max(5.0, interval + random.uniform(-4.0, 5.0))

        if self.player.pages_this_chapter >= 5 and not getattr(self, 'pages_complete_notified', False):
            self.pages_complete_notified = True
            self.notify('All 5 Bible pages found. Survive until 7:00 AM!', 4.0)

        if self.player.survival_time_left <= 0.0:
            if self.player.pages_this_chapter >= 5:
                self.state = STATE_WIN
                safe_set_relative_mouse(False)
                self.notify('The sun has risen. You survived!', 4.0)
                return
            self.player.survival_time_left = 0.0
            if not getattr(self, 'sunrise_missed_notified', False):
                self.sunrise_missed_notified = True
                self.notify('Sunrise came, but you still need all 5 Bible pages!', 4.0)

        # Death check
        if not p.alive:
            self.state = STATE_GAMEOVER
            safe_set_relative_mouse(False)

        # Notification timer
        if self.notif_t > 0:
            self.notif_t -= dt

    # ── Render ────────────────────────────────────────────────────────────
    def render(self, dt):
        overlay = getattr(self.renderer, 'overlay_surface', None)
        if overlay is not None:
            overlay.fill((0, 0, 0, 0))
        alive_enemies = self.enemy_manager.get_alive_enemies()
        # the renderer also draws enemies that are still playing their death animation
        render_enemies = self.enemy_manager.get_renderable_enemies()

        if self.state == STATE_PLAYING:
            sunrise_progress = 1.0 - max(0.0, min(1.0, self.player.survival_time_left / 120.0))
            sunrise_progress = sunrise_progress * sunrise_progress * (3.0 - 2.0 * sunrise_progress)
            # Rain, lightning and thunder only advance while actually playing (not while paused).
            self.renderer.update_weather(self.player, dt, sunrise_progress)
            self.renderer.render_frame(
                self.player, self.game_map, render_enemies, self.effects, dt, sunrise_progress)
            panel_bottom = 4
            if self._hud_visible:
                draw_hud(overlay if overlay is not None else self.internal, self.player, self.font_sm,
                         self.font_hud, self.font_micro)
                panel_bottom = draw_top_hud(overlay if overlay is not None else self.internal, self.player, self.game_map,
                                            self.font_micro, self.page_arrow, pygame.time.get_ticks())
                self.radar.draw(overlay if overlay is not None else self.internal, self.player, alive_enemies, self.game_map,
                                self.font_micro, pygame.time.get_ticks())

            # Notification: centred just under the top panel (the top-left corner is the debug text)
            if self.notif_t > 0:
                nt = self.font_micro.render(self.notif, True, SACRED_GOLD)
                nx = self.internal.get_width() // 2 - nt.get_width() // 2
                nbg = pygame.Surface((nt.get_width() + 8, nt.get_height() + 4), pygame.SRCALPHA)
                nbg.fill((10, 10, 15, 150))
                (overlay if overlay is not None else self.internal).blit(nbg, (nx - 4, panel_bottom + 3))
                (overlay if overlay is not None else self.internal).blit(nt, (nx, panel_bottom + 5))

        elif self.state == STATE_PAUSED:
            sunrise_progress = 1.0 - max(0.0, min(1.0, self.player.survival_time_left / 120.0))
            sunrise_progress = sunrise_progress * sunrise_progress * (3.0 - 2.0 * sunrise_progress)
            self.renderer.render_frame(
                self.player, self.game_map, render_enemies, self.effects, dt, sunrise_progress)
            if self._hud_visible:
                draw_hud(overlay if overlay is not None else self.internal, self.player, self.font_sm,
                         self.font_hud, self.font_micro)
                draw_top_hud(overlay if overlay is not None else self.internal, self.player, self.game_map,
                             self.font_micro, self.page_arrow, pygame.time.get_ticks())
                self.radar.draw(overlay if overlay is not None else self.internal, self.player, alive_enemies, self.game_map,
                                self.font_micro, pygame.time.get_ticks())
            draw_paused(overlay if overlay is not None else self.internal, self.font_lg, self.font_sm)

        elif self.state == STATE_MENU:
            draw_menu(self.internal, self.font_lg, self.font_sm, self.font_tiny)

        elif self.state == STATE_SETTINGS:
            self.settings_menu.draw(self.internal, self.font_lg, self.font_sm, self.font_tiny)

        elif self.state == STATE_INTRO:
            self.cinematic.render()

        elif self.state == STATE_GAMEOVER:
            draw_gameover(self.internal, self.font_lg, self.font_sm)

        elif self.state == STATE_WIN:
            draw_win(self.internal, self.font_lg, self.font_sm, self.chapter, final=True)
        
        # Jumpscare rendering (plays on top of scene during death sequence)
        try:
            from jumpscare import get_jumpscare_manager
            jumpscare_mgr = get_jumpscare_manager()
            if jumpscare_mgr.is_playing():
                jumpscare_mgr.render(overlay if overlay is not None else self.internal)
        except Exception:
            pass

        gp = getattr(self, 'gl_presenter', None)
        if gp is not None:
            # GPU presentation: one upload, then the shader does grade/vignette/fog + upscale.
            # No readback and no software scale (see gl_present.py).
            try:
                playing = self.state in (STATE_PLAYING, STATE_PAUSED)
                fl_on = 1 if (playing and self.player.flashlight_on and self.player.flashlight_battery > 0) else 0
                sup_int = 1.0 if (playing and (self.player.damage_flash > 0 or self.player.sanity < 30)) else 0.0
                gp.present(self.internal, pygame.time.get_ticks() / 1000.0, flashlight_on=fl_on,
                           supernatural=sup_int, fog_density=1.0, post=playing,
                           overlay_surface=overlay)
            except Exception as exc:
                print(f"[GPU] present failed ({type(exc).__name__}: {exc}); falling back to the 2D window.")
                self._fallback_to_2d()
                gp = None
        if gp is None:
            # Opt-in legacy GPU post-processing (ANINO_GPU_POST=1). It runs on the scene
            # surface BEFORE the UI layer is composited so the HUD, viewmodel, crosshair
            # and jumpscare keep their sharpness, mirroring the GPU presenter's shader
            # (which samples the overlay after every grade/bloom/vignette/grain stage).
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
            # Pygame fallback composites the transparent UI/viewmodel layer into the
            # stable internal surface; the existing CPU renderer remains fully usable.
            if overlay is not None:
                self.internal.blit(overlay, (0, 0))

            # The 2D fallback display uses the same logical dimensions as the
            # internal render target. SDL's SCALED display mode performs the final
            # GPU-side upscale to the actual window/monitor; Surface.blit itself
            # does not resize and must use a same-size destination here.
            self.screen.blit(self.internal, (0, 0))
        # Work time excludes the flip, which blocks on vsync and would look like load.
        self._work_ms = (_perf_counter() - self._loop_t0) * 1000.0
        pygame.display.flip()

    # ── Main loop ─────────────────────────────────────────────────────────
    def run(self):
        running   = True
        mouse_dx  = 0
        mouse_dy  = 0

        while running:
            dt = min(self.clock.tick(getattr(self, 'target_fps', FPS)) / 1000.0, 0.05)
            self._loop_t0 = _perf_counter()   # start of this frame's work (after the limiter's wait)
            mouse_dx = 0
            mouse_dy = 0

            try:
                from jumpscare import get_jumpscare_manager
                jumpscare_mgr = get_jumpscare_manager()
                jumpscare_mgr.update(dt)
            except Exception:
                pass

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
                        elif event.key == pygame.K_ESCAPE:
                            running = False
                        elif event.key == pygame.K_s:
                            self._open_settings(STATE_MENU)
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
                        elif event.key == pygame.K_s:
                            self._open_settings(STATE_PAUSED)
                        elif event.key == pygame.K_F11:
                            self.toggle_fullscreen()
                        elif event.key == pygame.K_m:
                            self.state = STATE_MENU
                            safe_set_relative_mouse(False)

                elif self.state == STATE_SETTINGS:
                    if event.type == pygame.MOUSEBUTTONDOWN:
                        if self.gl_presenter is not None:
                            # OpenGL window: undo the letterbox/scale from window pixels.
                            mapped = self.gl_presenter.map_mouse(
                                event.pos, self.internal.get_width(), self.internal.get_height())
                        else:
                            mapped = (int(event.pos[0] * self.internal.get_width() / max(1, self.screen.get_width())),
                                      int(event.pos[1] * self.internal.get_height() / max(1, self.screen.get_height())))
                        scaled_event = pygame.event.Event(event.type, {"pos": mapped, "button": event.button})
                        action = self.settings_menu.handle_event(scaled_event)
                    else:
                        action = self.settings_menu.handle_event(event)
                    if action == "back":
                        self.state = self.settings_return_state
                        if self.state == STATE_PLAYING:
                            safe_set_relative_mouse(True)
                    elif action == "apply":
                        self.settings_menu.apply(self._apply_settings)

                elif self.state == STATE_GAMEOVER:
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_m:
                        self.state = STATE_MENU
                        safe_set_relative_mouse(False)

                elif self.state == STATE_WIN:
                    if event.type == pygame.KEYDOWN:
                        if event.key in (pygame.K_RETURN, pygame.K_m):
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
                        # Give players a clear loading screen when they skip the
                        # cinematic, before the chapter's map and enemies are built.
                        if self.cinematic.skipped:
                            draw_loading_step(
                                self.screen, self.clock, self.font_lg, self.font_sm,
                                "Cinematic skipped. Preparing your journey...", 0.12)
                            draw_loading_step(
                                self.screen, self.clock, self.font_lg, self.font_sm,
                                "Generating the forest and its paths...", 0.38)

                        self.load_chapter(1)

                        if self.cinematic.skipped:
                            draw_loading_step(
                                self.screen, self.clock, self.font_lg, self.font_sm,
                                "Summoning the forest entities...", 0.86)
                            draw_loading_step(
                                self.screen, self.clock, self.font_lg, self.font_sm,
                                "Entering the forest...", 1.0)

                        self.state = STATE_PLAYING
                        safe_set_relative_mouse(True)

            elif self.state == STATE_PLAYING:
                self.update_playing(dt, mouse_dx, mouse_dy)

            # ── GC policy ──
            # load_chapter() primes the collector: collect + gc.freeze() (long-lived map /
            # sprite caches move into the permanent generation) and disable. Here we keep
            # that policy steady-state: the cyclic collector is DISABLED while PLAYING (so
            # no multi-millisecond GC pause ever lands on a gameplay frame - the main 1%
            # low fix on weak CPUs) and re-enabled the instant we leave gameplay, with a
            # periodic collect while idling on menus so the transient graph doesn't grow
            # for minutes.
            want_gc_enabled = (self.state != STATE_PLAYING)
            if want_gc_enabled != self._gc_enabled_now:
                if want_gc_enabled:
                    gc.enable()
                    gc.collect()      # tidy up now; we just came back from a long disabled stretch
                else:
                    gc.disable()
                self._gc_enabled_now = want_gc_enabled
                self._gc_menu_secs = 0.0
            elif want_gc_enabled:
                self._gc_menu_secs += dt
                if self._gc_menu_secs >= 5.0:
                    self._gc_menu_secs = 0.0
                    gc.collect()

            # Forest ambience (wind, crickets, owl, rustling) only while actually playing
            try:
                audio_mgr.set_frenzy_ambience(
                    self.state == STATE_PLAYING
                    and getattr(self.player, 'sanity', SANITY_MAX) < SANITY_FRENZY_THRESHOLD
                    and getattr(_settings_mod, 'RUNTIME_SETTINGS', {}).get('enable_sanity', True))
                audio_mgr.set_ambience_active(self.state == STATE_PLAYING)
                if self.state == STATE_PLAYING:
                    audio_mgr.update_ambience(dt)
            except Exception:
                pass

            # Keep the title soundtrack active on the main menu and its settings screen.
            menu_music_active = (
                self.state == STATE_MENU
                or (self.state == STATE_SETTINGS and self.settings_return_state == STATE_MENU)
            )
            self.menu_music.set_active(menu_music_active)

            self.render(dt)
            self.perf.update(self._work_ms, self.state == STATE_PLAYING)

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

