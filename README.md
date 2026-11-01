# ANINO SA GUBAT: Mga Bulong ng Dilim
### *Shadows in the Forest: Whispers of the Dark*

> A first-person raycasting horror-shooter set in Philippine folklore, built entirely in Python with **Pygame-CE** and **NumPy**.  
> Survive the haunted forest. Resist the creatures of the night. Trust in faith — and your bolo.

**Current build:** `BUILD 2026.11.02-SURVIVAL-AUDIO` (shown in the F3 debug overlay and the console at startup)

---

## Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Project Structure](#project-structure)
4. [Requirements & Installation](#requirements--installation)
5. [How to Run](#how-to-run)
6. [Standalone Executable Build](#standalone-executable-build)
7. [Controls](#controls)
8. [Gameplay Guide](#gameplay-guide)
9. [Enemy Roster](#enemy-roster)
10. [Map & Tile System](#map--tile-system)
11. [Chapters](#chapters)
12. [Rendering & Atmosphere](#rendering--atmosphere)
13. [Save System](#save-system)
14. [Settings](#settings)
15. [Debug Tools](#debug-tools)
16. [Architecture & Modules](#architecture--modules)
17. [Technical Notes](#technical-notes)
18. [Known Limitations & Recent Optimizations](#known-limitations--recent-optimizations)
19. [Intro Cinematic](#intro-cinematic)
20. [Lore](#lore)

---

## Overview

**ANINO SA GUBAT** is a pseudo-3D first-person game rendered using the classic **raycasting** technique (Wolfenstein-style), reimagined as a Philippine folklore horror game set in an open, moonlit forest. You play as a lone survivor hunted by mythical creatures (*aswang*, *manananggal*, *tikbalang*, *multo*, *sigbin*, and more) straight out of Filipino legend.

The game features:
- 100% procedurally generated pixel-art assets and textures (no external texture files needed)
- An outdoor forest rendered with depth-sorted tree billboards, a starry sky with moon and clouds, exponential fog, an atmospheric depth-fog overlay, and a cached flashlight/darkness overlay
- Glowing enemy eyes and pickup halos that stay visible in the dark
- Horror feedback: pulsing red vignette, heartbeat and screen shake when enemies get close, plus per-enemy jumpscare sequences on player death
- Multiple weapons with reload mechanics (Bolo, Shotgun, Revolver), including a voxel-style revolver viewmodel with firing and reload animation
- A **Sacred Ward** and faith system based on Filipino spiritual traditions
- A **five-page sunrise survival** objective: collect 5 Bible pages, then endure the night until 7:00 AM. A compass arrow and sunrise clock keep you oriented
- Unique procedural creature voices for every enemy, with spatial Tik-Tik stalking calls and recurring chase screams
- Two chapters with carry-over progression, JSON save/load, and a standalone Windows executable build

---

## Features

| Feature | Details |
|---|---|
| 🎮 Raycasting 3D | Pseudo-3D first-person view; internal resolution scales with the quality preset (320×180 on low, 640×360 on medium/high), upscaled to 1280×720 |
| 🌲 Outdoor Forest | 256×256 hybrid forest with biome-tinted terrain, 5,200 / 6,500 procedural trees, handcrafted village, cave, ancient ruins, swamp and shrine, connected trails, and a natural perimeter tree-line |
| 🌿 Legit Forest | 1200 procedural plants (ferns, mushrooms, rocks, bushes, logs, stumps, boulders, saplings) with wind physics and player proximity reactions |
| 🌀 Physics Animation | Spring-driven systems for camera, weapon sway, head bob; NumPy particle physics for casings/smoke/sparks |
| 🌬️ Dynamic Wind | Time-varying wind gusts affecting trees and undergrowth with realistic sway patterns |
| ✨ Particle Effects | Ejected shell casings, muzzle smoke, bullet sparks, blood splatters with gravity and bounce |
| 🌌 Atmospheric Sky | Layered clouds with parallax, subtle aurora borealis effect, twinkling stars, dynamic moon |
| 🌫️ Depth Fog | Atmospheric per-column depth-fog overlay drawn after sprites, cut through by the flashlight beam |
| 👹 7 Enemy Types | Each with unique stats and AI, its own procedural voice, spatial Tik-Tik stalking call, and jumpscare (all 7 spawn across the two chapters, see [Chapters](#chapters)) |
| ⚔️ 3 Weapons | Bolo (melee), Shotgun, Revolver — with ammo, magazines, and reload. Revolver uses a voxel-style viewmodel with firing and reload animation |
| ✝️ 5 Sacred Wards | Light, Shield, Banish, Bind and Final, powered by Faith energy with per-ward cooldowns |
| 🔦 Flashlight | Battery-powered beam with sway, low-battery flicker, and pickups to recharge |
| 🧠 Sanity | Darkness and nearby enemies drain sanity; light restores it |
| 😱 Danger Feedback | Red pulsing vignette, heartbeat and screen shake when an enemy is within 7 tiles |
| 😈 Jumpscares | Each enemy has its own individual jumpscare — a 2.6-second fullscreen horror sequence triggered when it kills you |
| 🔊 Creature Voices | Unique source-filter synthesised voices per enemy (growl, shriek, bray, boom, wail, moan, chitter) with distance panning, air-absorption muffling, and recurring chase screams |
| 🎯 Compass Arrow | Golden HUD arrow that spins like a compass needle to point at the nearest Bible page (or the exit once it opens) |
| 📡 Radar Mini-Map | Rotating radar showing nearby enemies, walls, trees and pickups; toggle with `M` |
| 💰 Loot Drops | Slain enemies may drop health, ammo, battery, faith, salt or garlic; the drop favours items you are running low on |
| 🩸 Hit Reactions | Enemies flinch, tilt and squash on impact; death triggers a squash-and-collapse animation before the body fades |
| 🌅 Survival Mode | Collect all 5 Bible pages, then survive until 7:00 AM. The forest grows more aggressive as sunrise approaches |
| 💾 Save/Load | JSON save file in the `saves/` directory |
| 🎲 Procedural Art | All textures and sprites are generated at runtime; the large ground texture is cached on disk |
| ⏳ Loading Screen | Step-by-step progress bar while assets are generated at startup |
| 🎛️ Animation Controls | Toggle physics, particles, camera shake, enemy animations, environment effects via settings |

---

## Project Structure

```
ANINO_SA_GUBAT/
│
├── main.py              # Game loop, states, HUD drawing, save/load logic, loading screen
├── player.py            # Player class: movement, stamina, sanity, noise, weapons, items, wards
├── enemies.py           # Enemy AI state machine, noise investigation, proximity sanity drain, loot drops, hit/death animation
├── map_system.py        # Forest map generation, cabin, trees, chapter entities, validation, tile queries
├── renderer.py          # Raycasting renderer, sprite pass, flashlight, fog, depth-fog, sky, post-fx, debug overlay
├── asset_generator.py   # Procedural pixel-art generator (textures, sprites, trees, ground)
├── audio_synth.py       # Procedural audio generator (NumPy sound synthesis, spatial mixing, ambience)
├── enemy_audio.py       # Unique per-enemy procedural voices (alert, attack, hurt, death, jumpscare, chase scream, Tik-Tik)
├── jumpscare.py         # Fullscreen per-enemy jumpscare sequences triggered on player death
├── animation_core.py    # Physics & Animation core: springs, easing, NumPy particle system, Verlet ropes, camera shake
├── anim_integration.py  # Realistic enemy animator: squash, flinch, tilt, hover, attack windup/lunge, death animation
├── radar.py             # Rotating enemy radar / mini-map
├── objective.py         # Objective guidance logic (nearest Bible page / exit, heading)
├── page_arrow.py        # Compass arrow HUD pointing at the next Bible page or the exit
├── raycast_fast.py      # Vectorised DDA raycaster and sprite depth-test (pure NumPy)
├── floor_fast.py        # Vectorised perspective floor fill with biome terrain (pure NumPy)
├── cinematic.py         # Intro cinematic
├── settings.py          # All game constants, colors, controls, settings load/save
├── requirements.txt     # Python dependencies
├── ANINO_SA_GUBAT.spec  # PyInstaller build specification
├── settings.json        # User configuration file (optional; created when settings are saved)
│
├── saves/               # (auto-created) JSON save files
├── dist/                # (auto-created) PyInstaller build output
├── tests/               # Headless test suite (smoke tests, raycast equivalence, drops, hit reactions)
├── tools/               # Asset generation scripts (e.g. Bible-page arrow art)
├── enemy_animations_pack/  # Optional 6-frame sprite sheets for animated enemies (auto-discovered)
├── crash.log            # (auto-created) written if the game crashes
└── assets/              # (auto-created) Asset directories
    ├── textures/
    ├── sprites/
    ├── audio/
    ├── fonts/
    └── cache/           # world_ground.npy (baked 1024×1024 ground texture)
```

---

## Requirements & Installation

- **Python:** 3.10 or higher (Python 3.12 recommended)
- **Dependencies:** `pygame-ce` (Community Edition), `numpy`

### Installation Steps

```bash
cd ANINO_SA_GUBAT
python -m venv .venv
.venv\Scripts\Activate
pip install -r requirements.txt
```

*(Note: PyInstaller is required if building the standalone executable and must be installed manually via `pip install pyinstaller`; it is not listed in `requirements.txt`).*

---

## How to Run

```bash
python -B main.py
```

The game launches at **1280×720** (fullscreen by default). The internal raycasting buffer size depends on the quality tier set in `settings.json`: 320×180 on `low`, 640×360 on `medium` and `high` (the default). On first launch the large ground texture is generated and cached in `assets/cache/world_ground.npy`, so the first start takes longer than later ones.

---

## Standalone Executable Build

ANINO SA GUBAT can be packaged as a standalone Windows executable using PyInstaller.

### Building the Executable

```bash
pip install pyinstaller
pyinstaller --clean ANINO_SA_GUBAT.spec
```

The executable will be generated in the `dist/ANINO_SA_GUBAT/` folder. Saves, settings, assets and `crash.log` are stored next to the executable.

---

## Controls

### In-Game

| Key / Input | Action |
|---|---|
| `W`, `A`, `S`, `D` | Move forward, strafe left, move backward, strafe right |
| Mouse | Look around |
| `Shift` (Hold) | Sprint (consumes stamina) |
| `Space` | Jump / Skip Cinematic |
| Left Mouse Click | Attack / Shoot active weapon |
| Mouse Wheel | Cycle weapon (Bolo → Shotgun → Revolver) |
| `R` | Reload active weapon |
| `F` or `1` | Toggle Flashlight (Ward 1: Light) |
| `2` | Cast Ward 2: Shield |
| `3` | Cast Ward 3: Banish |
| `4` | Cast Ward 4: Bind |
| `5` | Cast Ward 5: Final |
| `Tab` | Cycle the selected ward (Light → Shield → Banish → Bind → Final) |
| `Q` | Cast the currently selected ward (alternative to `4` / `5` for **Bind** and **Final**) |
| `G` | Place a Salt circle (repelling/slowing zone) |
| `H` | Throw Garlic (barrier zone against aswang) |
| `E` | Interact (open doors, save checkpoints) |
| `M` | Toggle the radar mini-map on / off |
| `Escape` | Pause |
| `F11` | Toggle Fullscreen |

### Menus

| Screen | Keys |
|---|---|
| Main Menu | `Enter` New Game · `L` Load Game · `I` Replay Intro (hidden shortcut) · `F11` Fullscreen · `Esc` Quit |
| Pause | `Esc` Resume · `S` Save · `F11` Fullscreen · `M` Main Menu |
| Game Over | `R` Respawn at checkpoint · `M` Main Menu |
| Chapter Complete | `Enter` Continue (or return to menu after the last chapter) · `M` Main Menu |

Debug keys (`F3`, `F4`, `F6`, `F7`) are listed under [Debug Tools](#debug-tools).

---

## Gameplay Guide

- **Survival:** Navigate the dark forest, manage your flashlight battery, stamina, and sanity. Darkness and nearby enemies drain sanity; light restores it. Each chapter gives you 7 minutes (until 7:00 AM) to find all **5 Bible pages** and then survive the remaining time. The forest grows more aggressive as sunrise approaches — new hunters spawn on a timer that shortens as the night goes on.
- **Compass Arrow & Clock:** A compact panel at the top-centre of the HUD shows your page count, a sunrise countdown clock, and a golden compass arrow that points at the nearest uncollected Bible page. Once you have all 5 pages the arrow redirects to the exit. Press `M` to toggle the radar mini-map, which shows nearby enemies, walls, trees and pickups as a rotating overlay.
- **Combat:** Use your bolo for silent close-quarters melee, the shotgun for powerful spread damage, or the revolver for precise ranged shots. Firearms are loud and draw enemies. Enemies flinch, tilt and squash when hit, and play a collapse animation when killed.
- **Loot Drops:** When you kill an enemy it may drop a pickup where it fell. Tougher enemies (Kapre, Tikbalang, Manananggal) drop more often. The roll favours items you are running low on, so you are less likely to get ammo you cannot hold.
- **Sacred Wards & Items:** Cast wards using Faith energy to repel, shield, banish or bind creatures. Scatter Salt or throw Garlic to create protective zones. Collect Bible pages for lore and strength.
- **Pickups:** Walk over an item to collect it. Pickups glow softly so you can spot them in the dark. Types: Health, Shotgun Ammo, Revolver Ammo, Salt, Garlic, Flashlight Battery, Faith, Bible Page.
- **Jumpscares:** When an enemy kills you, it triggers its own individual jumpscare — a 2.6-second fullscreen horror sequence with a rushing face, motion streaks, eye flares, impact flash and radial blur, followed by the death screen.
- **Progression:** The exit stays **sealed until you hold all 5 Bible pages** for the chapter (`PAGES_REQUIRED_CH1` / `PAGES_REQUIRED_CH2`, both 5 in `settings.py`); killing every enemy does **not** open it (`ALLOW_ENEMY_CLEAR_EXIT = False`). Each chapter has 5 pages, including one inside the limestone cave (an open archway, not a closed door). The objective line at the top of the screen shows the nearest page (or the exit once you have enough) with the compass arrow and distance. Health, ammo, items and wards carry over to the next chapter. Surviving until 7:00 AM with all 5 pages shows the win screen ("YOU SURVIVED UNTIL 7:00 AM").
- **Checkpoints:** Stand next to the checkpoint inside the cabin and press `E` to save your respawn point.

### Ward Reference

| Slot | Ward | Faith Cost | Cooldown | Visual |
|---|---|---|---|---|
| 1 | Light | – (flashlight toggle) | – | Beam on/off |
| 2 | Shield | 25 | 15 s | Blue screen tint and frame |
| 3 | Banish | 30 | 12 s | Expanding white ring |
| 4 | Bind | 20 | 10 s | Purple concentric rings |
| 5 | Final | 50 | 30 s | Golden flash and ring |

Wards affect enemies within **5 tiles**. The HUD shows each ward slot as locked, ready or on cooldown. Faith regenerates slowly over time (`FAITH_ENERGY_REGEN`) and can be restored with Faith pickups.

### Weapon Reference

| Weapon | Damage | Range | Cooldown | Magazine | Max Reserve | Noise |
|---|---|---|---|---|---|---|
| Bolo | 25 | 1.5 | 0.4 s | – | – | 1.0 (quiet) |
| Shotgun | 40 × 5 pellets | 8 | 0.8 s | 2 | 16 | 8.0 |
| Revolver | 30 | 15 | 0.5 s | 6 | 24 | 6.0 |

Reloading makes noise (`4.0`). Shotgun reload takes 1.5 s, revolver reload 1.2 s.

### Player Stats

| Stat | Value |
|---|---|
| Health | 100 |
| Armor (max) | 50 |
| Stamina | 100 (drains 35/s while sprinting, regenerates 25/s) |
| Sanity | 100 |
| Walk / Sprint speed | 3.0 / 5.0 |
| Flashlight battery | 100% (drains 1.0/s, recharges 0.1/s when off) |
| Salt / Garlic capacity | 10 / 8 |

---

## Enemy Roster

| Enemy | HP | Damage | Speed | Detect Range | Vulnerabilities | Resistances | Spawns In |
|---|---|---|---|---|---|---|---|
| **Aswang** | 80 | 15 | 2.0 | 8 tiles | Repel, Garlic | None | Ch. 1, Ch. 2 |
| **Manananggal** | 100 | 20 | 2.5 | 10 tiles | Repel, Cross | Bind | Ch. 2 |
| **Tikbalang** | 150 | 30 | 1.8 | 7 tiles | Shield | Repel | Ch. 2 |
| **Kapre** | 200 | 35 | 1.2 | 6 tiles | Banish | Bind, Repel | Ch. 2 |
| **White Lady** | 60 | 10 | 1.5 | 12 tiles | Bind | Banish | Ch. 1 |
| **Multo** | 50 | 12 | 2.0 | 8 tiles | Banish | None | Ch. 1, Ch. 2 |
| **Sigbin** | 70 | 18 | 3.5 | 7 tiles | Bind | None | Ch. 1, Ch. 2 |

Enemies are rendered as billboards with a jagged glowing rim, glowing eyes, and an aura for the spectral types. They flash when hit, tint purple while bound, jitter and enlarge when attacking, flinch and squash when struck, and play a collapse-and-fade death animation when killed. Manananggal, White Lady and Multo hover above the ground.

Each creature also has its own **synthesised voice** and **jumpscare**:

| Enemy | Voice |
|---|---|
| Aswang | Rasping vocal-fry growl, chest formants, hard distortion |
| Manananggal | Harsh amplitude-modulated shriek + leathery wing flaps |
| Tikbalang | Donkey/horse "hee-haw" — pitch flips between a high and a low note |
| Kapre | Huge smoky "ho-ho-ho" laugh, each "ho" sinking in pitch |
| White Lady | Breathy, vibrato-rich wail in a long cave-like reverb |
| Multo | Whispered, detuned, fluttering moan |
| Sigbin | Rodent-like chittering with tiny clicks |

Every enemy emits a spatial **Tik-Tik stalking call** (its own signature, closer = more frequent and louder) and, while actively chasing you, a **recurring chase scream**. When an enemy kills you it triggers its **individual jumpscare** — a 2.6-second fullscreen horror sequence. Tougher enemies drop loot more often when slain.

---

## Map & Tile System

- **Grid Size:** 256 × 256 hybrid outdoor forest map (65,536 world cells).
- **Hybrid Layout:** Hand-authored survivor camp, abandoned village (three enterable huts), ancient Balete grove and central ruins/checkpoint, limestone cave entrance, swamp basin, and forgotten shrine exit are connected by winding trails.
- **Procedural Terrain:** Deterministic terrain regions use distinct ground tints for forest, dirt trails, village earth, swamp, ancient grove, limestone and shallow water. The renderer samples the terrain layer during floor projection, so the regions are visible without adding fake wall geometry.
- **Forest Population:** Chapter 1 generates approximately 5,200 regular trees and Chapter 2 approximately 6,500, plus the dense perimeter tree ring and 1,300 undergrowth objects. Species and scale distributions vary by biome.
- **World Generation:** A fixed world seed makes the map repeatable. The legacy chunk loader is intentionally bypassed for this bounded hybrid map so it cannot erase handcrafted POIs or reset their collision data.
- **Tile Types:**
  - `EMPTY`: Walkable forest ground.
  - `WALL_STONE`: Outer boundary wall (edges at `0` and `63`).
  - `WALL_WOOD`: Cabin walls (tiles 28–37 on both axes).
  - `DOOR`: Cabin entryway, two tiles wide at `(32, 37)` and `(33, 37)`. Opened with `E`.
  - `WALL_BAMBOO`, `WALL_BALETE`: Defined with textures but not used by the current maps.
- **Trees:** Not grid tiles. They are billboard objects placed from a fixed seed (`42 + chapter`), so each chapter has the same layout every run. Chapter 1 uses `balete`, `bamboo`, `mahogany`, and `dead` trees; Chapter 2 adds `banana` and `palm`. Trees keep a minimum spacing of 1.6–2.5 tiles (density-dependent), stay out of the cabin area and the start area, and act as circular obstacles for movement.
- **Entity Clearance:** After enemies, pickups, checkpoints, the exit and the player start are placed, any tree overlapping them is removed so nothing spawns inside a trunk. The console reports how many trees were removed.
- **Validation:** Each chapter load checks that entities are not inside walls or trees, then runs a flood-fill from the player start to confirm every entity is reachable. Unreachable entities are relocated to the nearest reachable empty cell, or flagged as unreachable in the F3 overlay if no spot is found.

---

## Chapters

| Chapter | Setting | Player Start | Exit Position | Trees | Initial Enemies | Bible Pages | Time Limit |
|---|---|---|---|---|---|---|---|
| **Chapter 1** | Forgotten Forest & Abandoned Village | (15.5, 128.5) | (242.5, 128.5) | ~5,200 | 2 Aswang, Multo, Sigbin, White Lady | 5 | 7 min |
| **Chapter 2** | Sunken Swamp & Cursed Grove | (15.5, 128.5) | (242.5, 128.5) | ~6,500 | 2 Aswang, Manananggal, Multo, Sigbin, Tikbalang, Kapre | 5 | 7 min |

Both chapters share the hybrid landmark layout and use the central ancient ruins as a checkpoint. The chapter-specific enemy and pickup placements differ. Chapter 1 also places a few supplies (salt, battery, faith) and an Aswang near the start so there is something to see right away. Chapter 2's fifth Bible page is inside the limestone cave, which uses an open archway entrance (3 tiles wide) rather than a closed door so the page is always reachable.

Each chapter runs as a **five-page sunrise survival** round: collect all 5 Bible pages, then survive until the 7:00 AM clock runs out. New hunters spawn on a timer that shortens as the night progresses (the interval floors at 10 seconds). If sunrise arrives before you have all 5 pages, you get a warning but can keep playing. Surviving until 7:00 AM with all 5 pages triggers the win screen ("YOU SURVIVED UNTIL 7:00 AM"). Completing Chapter 1 loads Chapter 2 directly with a "CHAPTER 1 CLEARED!" notification.

---

## Rendering & Atmosphere

The renderer draws each frame in this order:

1. **Sky:** Vertical gradient, 260 twinkling stars, layered clouds with parallax, and a moon at a fixed world direction. An atmospheric aurora borealis effect subtly drifts along the horizon.

2. **Floor:** Per-row gradient with exponential-squared fog and a minimum brightness, rendered in a single vectorised NumPy pass. Enhanced per-biome ground terrain samples a baked terrain atlas so each region (forest, trail, village, swamp, grove, cave, water) has its own distinct ground tint and texture. Dynamic color variation based on distance and time creates a living, breathing forest floor.

3. **Walls:** DDA raycasting (vectorised via `raycast_fast.py`) with a texture column per ray, distance shading, darker side faces, and a per-column z-buffer. Rays that hit nothing draw no wall.

4. **World sprites:** Trees, enemies, undergrowth and pickups are collected, sorted far to near, and drawn together so they overlap correctly. Sprite depth tests run as one vectorised NumPy lookup per screen column.
   - **Trees:** Billboard sprites with wind-based sway. Tree stiffness varies by type (balete trees sway more than rigid mahogany).
   - **Undergrowth:** Procedural ferns, mushrooms, rocks, and bushes react to wind and player proximity. Plants gently push away when the player walks through them.
   - **Enemy animation:** All enemy sprites have spring-based hover, sway, and breathing animations for organic movement. Hits trigger per-hit squash, lateral flinch and tilt; death triggers a collapse animation before the body fades.
   - **Particles:** Physics-driven particles including ejected shell casings, muzzle smoke, bullet sparks, and blood splatters with gravity and bounce.

4b. **Atmospheric depth-fog:** A per-column alpha overlay built from the z-buffer, drawn after sprites so distant trees and walls get hazed, but before the flashlight so the beam cuts through it. Controlled by `ENABLE_FOG` with `FOG_NEAR` / `FOG_FAR` constants.

5. **Darkness and flashlight:** One cached overlay with a soft hole and a warm additive glow. It sways with movement and flickers when the battery is below 20%. With the light off or the battery dead, a flat darker overlay is used.

6. **Emissive pass:** Enemy eyes, auras and pickup halos are drawn after the darkness so they remain visible.

7. **Particles:** Fireflies and dust motes with smooth movement patterns. Physics particles (casings, smoke, sparks, blood) rendered after environmental particles.

8. **Post effects:** Vignette, low-health/low-sanity blood border, danger vignette with heartbeat, ward effects, damage flash, muzzle flash, weapon with bob/recoil/reload animation, crosshair, then screen shake.

### Wind & Environment Physics

The game features a comprehensive wind system that brings the forest to life:
- **Time-varying wind strength:** Wind strength cycles between 0.2 and 0.6, creating natural gusts
- **Gust intervals:** Random gusts every 3-8 seconds add variety
- **Tree-specific stiffness:** Different tree types sway at different rates (balete trees are more flexible)
- **Plant movement:** Undergrowth gently sways in the wind and reacts to player movement

Sprite distance shading only changes colour, never transparency, so sprites no longer appear see-through or surrounded by dark boxes.

---

## Save System

- **Storage:** JSON format saved in the `saves/` directory as `save_0.json` (one slot).
- **How to save:** Pause with `Esc`, then press `S`.
- **How to load:** Press `L` on the main menu.
- **Saved Data:** Current chapter and the player state (position, health, armor, stamina, sanity, weapons, ammunition, items such as salt, garlic and Bible pages, faith energy, and checkpoint). Map pickups and enemies are rebuilt from the chapter on load, so they reset.

---

## Settings

### Constants (`settings.py`)
- Display resolution (`1280×720`), internal raycasting resolution (preset-dependent: 320×180 on low, 640×360 on medium/high), target FPS (`60`), FOV (`60°`), max ray depth (`35` tiles), mouse sensitivity, player movement speeds, weapon, enemy and ward stats, forest settings (map size, tree counts, ground texture size), and UI colors.
- Effect toggles such as `ENABLE_BLOOM`, `ENABLE_FOG`, `ENABLE_PARTICLES`, `ENABLE_SANITY` and `ENABLE_INTRO`.
- `QUALITY_PRESETS` (`low`, `medium`, `high`): chosen with `"quality_tier"` in `settings.json` (default `medium`) and applied at startup by `main.py` before any module imports resolution-dependent values. See [Known Limitations & Recent Optimizations](#known-limitations--recent-optimizations).
- Lighting constants (`AMBIENT`, `AMBIENT_LIGHT_OFF`, `BEAM_RADIUS`, `BEAM_GLOW`, `FOG_DISTANCE`, `ENEMY_EYE_GLOW`, ...) are defined only in `settings.py`.

### Animation & Physics System
The game includes a comprehensive physics and animation system built entirely in Python:

| Setting | Description |
|---|---|
| `ENABLE_ANIMATIONS` | Master toggle for all animation systems |
| `ENABLE_SPRING_PHYSICS` | Spring-based systems for camera, weapon, head bob |
| `ENABLE_PARTICLE_PHYSICS` | NumPy-accelerated particles (casings, smoke, sparks, blood) |
| `ENABLE_VERLET_ROPES` | Verlet chain dynamics for trailing elements |
| `ENABLE_CAMERA_SHAKE` | Coherent noise-based screen shake |
| `ENABLE_WEAPON_INERTIA` | Weapon sway with inertia and spring damping |
| `ENABLE_ENEMIES_ANIM` | Enemy animation springs (hover, sway, breathing) |
| `ENABLE_ENV_ANIM` | Environment animations (wind, undergrowth, aurora) |
| `ENABLE_UI_ANIM` | UI animation effects |
| `ENABLE_GAME_FEEL` | Hit-stop, time scale, impact effects |

The F3 debug overlay displays:
- Animation timing (ms)
- Active particle count
- All standard debug information

### Configuration (`settings.json`)
`load_settings()` merges the file over these defaults:

`screen_width`, `screen_height`, `fullscreen`, `mouse_sensitivity`, `master_volume`, `music_volume`, `sfx_volume`, `enable_bloom`, `enable_film_grain`, `enable_fog`, `enable_particles`, `enable_audio_synth`, `enable_sanity`, `enable_intro`, `debug_overlay`, `quality_tier`, `controls`

- In the code shown, `main.py` reads `enable_intro` when you start a new game (set it to `false` to skip the cinematic).
- `settings.json` is created when `save_settings()` is called; it is not required to run the game.

---

## Debug Tools

| Key | Effect |
|---|---|
| `F3` | Toggle the debug overlay (build, chapter, player position, enemies alive/total and nearest distance, pickups, trees, sprites in view/drawn, danger level, FPS, map validation result) |
| `F4` | Toggle the **raw scene**: darkness overlay off, with markers and distance labels on every enemy and pickup |
| `F6` | Teleport 4 tiles from the nearest living enemy, facing it |
| `F7` | Defeat every enemy (to test chapter progression) |

The debug overlay is on by default (`DEBUG_OVERLAY = True`). The console also prints a spawn report for each chapter and flags any enemy inside a wall.

---

## Architecture & Modules

| Module | Role |
|---|---|
| `main.py` | Game loop, state machine (`MENU` / `INTRO` / `PLAYING` / `PAUSED` / `GAMEOVER` / `WIN`), HUD, loading screen, chapter loading and advancing, audio triggers, save/load, crash logging |
| `player.py` | Movement, collision, stamina, sanity, noise generation, weapons, cancelable reloads, wards, serialization |
| `enemies.py` | AI state machine (`idle`, `patrol`, `investigate`, `stalk`, `attack`, `recover`, `retreat`, `defeated`), noise perception, salt/garlic zones, ward effects, proximity sanity drain, loot drops, hit/death animation tracking |
| `map_system.py` | Boundary and cabin grid, seeded tree placement, per-chapter entities, entity clearance and validation, tile and tree collision queries, doors, pickups |
| `renderer.py` | Raycasting engine, sprite pass with z-buffer, flashlight, sky, depth-fog, fog, particles, danger feedback, post-fx, F3/F4 debug |
| `asset_generator.py` | Procedural pixel art: wall and floor textures (fBm noise with ambient occlusion), weapons, enemies (with horror rim and drips), pickups, tree billboards, undergrowth, cached world ground |
| `audio_synth.py` | Procedural sound synthesis using NumPy arrays & Pygame mixer; spatial panning, air-absorption muffling, mono-to-stereo mixing, mixer format locking, soft-limit + dither, mix headroom, anti-click fade-in |
| `enemy_audio.py` | Unique per-enemy procedural creature voices (alert, attack, hurt, death, jumpscare, chase scream, Tik-Tik) with source-filter synthesis, reverb, formant shaping and spatial playback |
| `jumpscare.py` | Per-enemy fullscreen jumpscare sequences triggered on player death (2.6 s procedural animation: rush, streaks, eye flares, impact flash, radial blur, black fade) |
| `animation_core.py` | Physics & Animation core: springs, easing, NumPy particle system, Verlet ropes, camera shake |
| `anim_integration.py` | Realistic enemy animator: spring-driven squash/rebound, flinch, tilt, hover, attack windup/lunge, death animation — applied on top of sprite frames |
| `radar.py` | Rotating mini-map radar showing enemies, walls, trees and pickups within range; sweep-line glow, alert ring, pulsing hunting blips |
| `objective.py` | Objective guidance logic: nearest uncollected Bible page or the exit, relative bearing, cardinal direction word |
| `page_arrow.py` | HUD compass arrow (golden art with pulsing glow animation) that rotates to point at the next objective from the top-centre panel |
| `raycast_fast.py` | Vectorised DDA raycaster and visible-run lookup — processes all rays in lock-step via NumPy instead of a Python per-ray loop |
| `floor_fast.py` | Vectorised perspective floor fill with per-biome terrain atlas sampling |
| `cinematic.py` | Intro cinematic (75 s, 6 narrative scenes) |
| `settings.py` | Constants: display, physics, weapons, enemies, wards, colors, tiles, controls, settings load/save, quality presets |
| `terrain_gen.py` | Baked 1024×1024 per-biome ground texture and terrain atlas used by the floor renderer |

---

## Asset System

The game generates all textures and sprites procedurally at runtime using Python and NumPy, so no external asset files are required to run the game. However, you can provide custom PNG sprites for enemies if you want to use AI-generated artwork.

### Enemy Sprites

Custom enemy sprites go in `assets/sprites/enemies/` as 64×64 or larger PNGs with transparency:

| Enemy Type | File Name Pattern | States Mapped |
|---|---|---|
| aswang, manananggal, tikbalang, kapre, white_lady, multo, sigbin | `<type>_idle.png` | idle, walk, stalk, crawl, crouch, hover, stagger, death |
| aswang, manananggal, tikbalang, kapre, white_lady, multo, sigbin | `<type>_attack.png` | attack, lunge, run, sprint |

- If a PNG file exists, it will be loaded, scaled to 64×64 (nearest-neighbor for crisp pixel art), and passed through the same horror rim effect as procedural sprites.
- The `death` state uses the idle image flattened (squeezed to ~30% height) and tinted darker.
- If no PNG is found, the game falls back to the procedural generator.
- Toggle with `USE_CUSTOM_ENEMY_SPRITES = True/False` in `settings.py`.
- Custom sprites are cached after first load to avoid repeated I/O.

### Other Assets

All other assets (wall/floor textures, weapons, pickups, trees, undergrowth) remain procedurally generated:

- `assets/textures/` — wall and floor textures (generated per session)
- `assets/sprites/` — weapons and pickups (generated per session)
- `assets/cache/` — cached world ground texture (`world_ground.npy`)

---

## Technical Notes

- **Raycasting:** DDA (Digital Differential Analyzer) algorithm for wall columns, with fish-eye correction. The DDA grid walk and the sprite visible-run test are **vectorised in NumPy** (`raycast_fast.py`) so all rays run in lock-step, and the floor fill is a single vectorised perspective pass (`floor_fast.py`).
- **Z-Buffer:** One entry per ray. Sprites are depth-sorted every frame and drawn in column runs so only closer walls hide them. The depth test is a single NumPy lookup per screen column.
- **GPU-Scaled Display:** The window is created with SDL's `SCALED` flag and vsync, so the 1280×720 surface is stretched to the native monitor resolution on the GPU instead of a CPU blit.
- **Procedural Art:** No external asset files. Everything is generated from Python code at startup, and the 1024×1024 ground texture is saved to `assets/cache/world_ground.npy` after the first run.
- **Creature Voices:** Enemy voices are synthesised per creature type at startup as source-filtered glottal/harmonic waveforms with formant shaping, reverb and saturation. At play time they are panned, distance-attenuated and air-absorbed (progressively muffled cached copies) so each creature has a distinct, spatialised presence.
- **Delta Time Cap:** `dt` is capped at 50 ms per frame to prevent physics tunneling on lag spikes.
- **Upscaling:** Internal buffer (preset-dependent: 320×180 on low, 640×360 on medium/high) upscaled to 1280×720 via `pygame.transform.scale`.
- **Deterministic maps:** Tree layouts use a seeded random generator per chapter.
- **Error handling:** An unhandled exception is written to `crash.log` next to the game (with a message box on Windows).
- **Platform:** Built and tested on Windows with Python 3.10+. Compatible with Linux/macOS given the same dependencies (the crash message box is Windows-only and is skipped elsewhere).

---

## Known Limitations & Recent Optimizations

### Recent changes

- **Five-Page Sunrise Survival:** Gameplay was remade around a survival loop. Each chapter is a 7-minute round: collect all **5 Bible pages** (the exit stays sealed until you have them, `REQUIRE_PAGES_FOR_EXIT = True`), then endure the night. A sunrise countdown clock and page counter appear in a compact top-centre HUD panel. The forest grows more aggressive as sunrise approaches — hunters spawn on a timer whose interval shortens over the night (flooring at 10 s). Surviving until 7:00 AM with all 5 pages triggers the win screen.
- **Compass Arrow & Objective Panel:** A golden compass arrow (`page_arrow.py`, art generated by `tools/make_bible_arrow.py`) spins in the top-centre panel to point at the nearest uncollected Bible page, or at the exit once you have enough pages. The panel also shows the page count and a `SUNRISE HH:MM` countdown. The next-objective logic is headless-testable via `objective.py`.
- **Per-Enemy Jumpscares:** Each of the 7 creatures now has its **own individual jumpscare** sound and a 2.6-second fullscreen procedural sequence (rushing face, motion streaks, eye flares, impact flash, radial blur, black fade) that plays when that enemy kills you. Optional `jumpscare_scream.wav` / `jumpscare.mp4` assets are used when present, with a procedural fallback.
- **Enemy Loot Drops:** Slain enemies can drop a pickup where they fell (`enemies.py`: `DROP_TABLE`, `roll_drop`, `collect_drops`). Tougher enemies drop more often (Kapre/Tikbalang ~85%, Manananggal ~75%, others ~60%), and the drop rolls toward items you are running low on. The player's near-empty stock boosts the weight of that item.
- **Realistic Enemy Hit & Death Animation:** `anim_integration.py` drives per-hit spring impulses (impact squash, rebound overshoot, sideways flinch, tilt-away, hover jolt) scaled by hit strength, plus a collapse-and-fade death animation that plays for `DEATH_ANIM_TIME` seconds. Dead-but-animating enemies still render and block the player.
- **Vectorised Raycaster & Floor:** `raycast_fast.py` runs the DDA grid walk for all rays in lock-step and `floor_fast.py` fills the whole floor in one vectorised NumPy pass (including per-biome terrain atlas sampling). Both are exact drop-in equivalents of the scalar code, verified by `tests/test_raycast_fast.py`. The display is created with SDL's `SCALED` flag + vsync so GPU-side stretching avoids a CPU blit.
- **Atmospheric Depth-Fog Overlay:** A subtle per-column haze built from the z-buffer, drawn after sprites but before the flashlight so the beam cuts through it. Controlled by `ENABLE_FOG` with `FOG_NEAR` / `FOG_FAR`.
- **Enhanced Per-Biome Ground Terrain:** The floor renderer samples a baked terrain atlas so each biome (forest, dirt trail, village earth, swamp, ancient grove, limestone cave, shallow water) shows its own distinct ground tint and texture rather than a single flat colour.
- **Unique Per-Enemy Creature Voices:** `enemy_audio.py` gives every enemy a distinct source-filtered synthesised voice (aswang growl, manananggal shriek, tikbalang bray, kapre "ho-ho-ho" boom, white-lady wail, multo whisper, sigbin chitter) with reverb, formant shaping and saturation. Each living enemy emits its own **spatial "tik-tik" stalking call** (independent timers prevent a synchronised chorus; closer enemies call more often and louder) and a **recurring chase scream** while actively pursuing you; the tik-tik is only paused for the scream's short reverb tail.
- **Audio Pipeline Improvements:** The mixer format is locked, output is soft-limited and dithered with mix headroom, mono sources are up-mixed to stereo cleanly, a diagnostic tool (`tools/check_audio.py`) validates the pipeline, and an anti-click fade-in removes start-of-sound pops. Forest ambience was lowered so gameplay audio (attacks, calls, screams) stays clear.
- **Voxel-Style Revolver:** The revolver viewmodel was remade as a voxel-style model (three-quarter view, shrunk to scale) with an animated firing and reloading sequence driven by the revolver's own reload duration.
- **Cave Entrance Fix:** The limestone cave entrance was widened to a 3-tile **open archway** (not a closed door) so the Chapter 2 cave Bible page placed inside it is always reachable.
- **Quality Presets:** Set `"quality_tier"` to `low`, `medium` or `high` in `settings.json`. The preset is applied at startup, before any resolution-dependent surface exists. `low` renders at 320×180 with fewer trees and particles; `medium` and `high` use 640×360. Press **F5** (next) / **F6** (previous) during gameplay to switch quality tiers at runtime — changes take effect immediately and are saved to `settings.json`. Presets control resolution, bloom, HDR, god rays, SSAO, particles, dynamic lights, tree draw cap, and water movement speed.
- **Towering Tropical Forest:** Tree billboards were upgraded from 64×128 to 64×256 sprites with 7 distinct archetypes — tall tropical hardwoods (balete) with buttress roots, massive trunks with tapered bark and layered canopies, slender bamboo clusters, broken dead trees with sparse branches, banana/palm trees with radiating fronds, and supernatural twisted trees with a dark aura. Trunks feature vertical bark grooves, moss patches, and branches extending in varied directions. Most non-dead, non-bamboo trees also get hanging vines (lianas). Per-tree seeds ensure stable appearance across frames.
- **Organic Terrain:** The world ground texture (1024×1024) now uses 4 layers of multi-octave fBm noise to produce wet soil patches, exposed moss clusters, leaf litter, and subtle root patterns. Stone/pebble spots are scattered across the surface. Undergrowth now includes 8 sprite types: fern, mushroom, rock, bush, fallen log, tree stump, mossy boulder, and sapling — all placed deterministically per chapter.
- **Bloom & Post-Processing:** Bloom is now controlled by the active quality preset (`low` = off, `medium`/`high` = on). The `ShaderRenderer` performs a bloom extraction pass when enabled. Full multi-pass bloom blur requires ModernGL shader compilation; the pipeline gracefully falls back to software rendering if shaders fail.
- **HDR Tone Mapping:** High quality enables HDR exposure (`HDR_EXPOSURE=1.1`) and ACES tone mapping. Medium and low use Reinhard tone mapping at default exposure.
- **God Rays:** High quality enables screen-space god-ray scattering from the flashlight. Low and medium disable this pass.
- **Wall Rendering Performance:** Wall texture columns are pre-sliced once at startup (zero-copy subsurfaces), so the per-ray work is scale + multiply-fill + blit with no per-ray surface allocations.
- **Wards 4 & 5 Direct Keys:** Key `4` casts Bind and key `5` casts Final (alongside the `Tab` + `Q` method).
- **Door Collision:** Closed doors block movement for both player and enemies (`is_solid(x, y, doors_block=True)`); opened doors are passable for both.
- **Enemy Pathfinding:** Enemies now use A* pathfinding via `NavGrid` when chasing the player. Paths are recalculated every 3 seconds or when the player moves more than 5 tiles. Closed doors block pathfinding; opened doors are traversable. Water tiles add a 1.5× movement cost, making enemies prefer land routes.
- **Water Movement Slowdown:** The player moves at 40% normal speed when standing on water tiles (`WATER_SPEED_MULTIPLIER = 0.4`). The slowdown applies smoothly on entry/exit with no frame-rate dependency.
- **Enemy Placement:** White Lady is placed in Chapter 1 and Kapre in Chapter 2. Trees near entities are cleared, and a flood-fill from the player start relocates or flags (in the F3 overlay) anything unreachable.
- **Lighting Constants:** `AMBIENT`, `BEAM_RADIUS`, `FOG_DISTANCE`, `ENEMY_EYE_GLOW` and related constants are defined once in `settings.py`; `renderer.py` and `enemies.py` no longer redefine them.

### Known limitations

- Quality presets do not toggle film grain or chromatic aberration (those remain controlled by `ENABLE_FILM_GRAIN` and `ENABLE_CHROMATIC_ABERRATION`).
- `quality_tier` in `settings.json` is read once at startup; you can also switch at runtime with **F5** / **F6**.
- Enemies path-find using a coarse 1-tile grid; they may clip near thin obstacles. They do not open doors.
- Water tiles slow movement but do not implement swimming or depth variation.
- SSAO is defined in presets but not yet integrated into the renderer (no depth buffer available).
- Tree billboards are 2D sprites; they do not rotate to face the camera (static billboard orientation). Canopy overlap at extreme distances may appear flat.
- Enemy jumpscare MP4 video playback requires `ffmpeg` (not in `requirements.txt`); without it the jumpscare falls back to the procedural rendering.
- Enemy sprite animation pack frames, if present, are uniformly 14 FPS; per-creature animation rate is not yet individually tuned.

---

## Intro Cinematic

ANINO SA GUBAT features an atmospheric 75-second animated **Intro Cinematic** that plays automatically when you select "New Game" from the Main Menu.

- **Content:** 6 narrative scenes (`WARNING`, `FOREST`, `AWAKENING`, `TRAVELER`, `PAGES`, `CLOSING`/`TITLE`) telling the backstory, lore, warning, living forest, awakening spirits, traveler items, Bible pages, and title slam.
- **Skip:** Press `Space`, `Enter`, or `Escape` at any time to instantly skip the cinematic and jump straight into Chapter 1.
- **Replay:** Press `I` on the Main Menu to replay the intro cinematic at any time.
- **Toggle:** Controlled by the `enable_intro` setting in `settings.json` (default: `true`). Set to `false` to jump directly into gameplay on New Game.

---

## Lore

> *"Huwag lumabas ng gabi. Baka abutin ka ng dilim."*  
> *("Don't go out at night. The darkness might catch you.")*

The forest has always been alive. But tonight, the old warnings mean something more. Ancient spirits, stirred by years of disrespect for the land, now roam freely. You are a lone traveler caught in the cursed woods — armed with your grandfather's bolo, a flickering flashlight, and faith passed down through generations. Survive until dawn.

Collect **Bible pages** scattered throughout the forest. They hold prayers, warnings, and the secrets to unlocking the sacred wards that may be your only salvation.

---

*Ingatan mo ang iyong sarili. Ang gubat ay may ibang batas sa gabi.*  
*("Take care of yourself. The forest has different rules at night.")*
