# ANINO SA GUBAT: Mga Bulong ng Dilim
### *Shadows in the Forest: Whispers of the Dark*

> A first-person raycasting horror-shooter set in Philippine folklore, built entirely in Python with **Pygame-CE** and **NumPy**.  
> Survive the haunted forest. Resist the creatures of the night. Trust in faith — and your bolo.

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
12. [Settings](#settings)
13. [Architecture & Modules](#architecture--modules)
14. [Technical Notes](#technical-notes)
15. [Performance & Scaling](#performance--scaling)
16. [Testing](#testing)
17. [Intro Cinematic](#intro-cinematic)
18. [Lore](#lore)

---

## Overview

**ANINO SA GUBAT** is a pseudo-3D first-person game rendered using the classic **raycasting** technique (Wolfenstein-style), reimagined in a Philippine horror setting. You play as a lone survivor navigating cursed forests and ruins, hunted by mythical creatures (*aswang*, *manananggal*, *kapre*, *multo*, *sigbin*, *tikbalang*, *white_lady*) straight out of Filipino legend.

The game features:
- 100% procedurally generated pixel-art assets and textures (no external texture files needed)
- An atmospheric raycasting renderer with colored fog, vignette, particle systems, and flashlight effects
- A readback-free **GPU compositor** that uploads the scene once and runs post-processing (bloom, grade, fog, grain) in-shader, keeping the HUD/UI on a separate always-sharp layer
- **Performance monitoring** that measures sustained frame work and reports bottlenecks without silently disabling visual effects or reducing forest density
- Multiple weapons with reload mechanics (Bolo, Shotgun, Revolver), switched with the scroll wheel
- A unique **Sacred Ward** and faith system based on Filipino spiritual traditions (5 wards)
- Multi-chapter progression with a standalone Windows executable build

---

## Features

| Feature | Details |
|---|---|
| 🎮 Raycasting 3D | Pseudo-3D first-person view at 640×360 internal resolution, presented on a SCALED 1280×720 window |
| 🖥️ GPU Compositor | Scene is uploaded to the GPU once per frame; post-FX (bloom, color grade, depth fog, film grain) run in-shader — no CPU/GPU readback, HUD stays pixel-sharp |
| ⚡ Performance Monitor | Measures sustained frame work and reports over-budget frames; it never disables shaders, particles, wind, fog, trees, or grading automatically |
| 👹 7 Enemy Types | Each with unique AI states, stats, vulnerabilities, and resistances |
| ⚔️ 3 Weapons | Bolo (melee), Shotgun, Revolver — with ammo, magazines, and reload; cycled with the mouse wheel |
| ✝️ 5 Sacred Wards | Faith-powered abilities: repel, shield, banish, bind, and a final ultimate (The Final Benediction) |
| 🧭 Compass & Radar | A page-arrow compass points toward your objective and a top-right radar shows nearby enemies |
| 🔦 Flashlight | Battery-powered; drains over time |
| 🧠 Sanity / Frenzy | Darkness and nearby enemies drain sanity; low sanity triggers a high-aggression frenzy |
| 🎬 Intro Cinematic | A skippable animated title sequence with menu music |
| 🗺️ 2 Chapters | Hand-crafted outdoor forest maps with trees, debris, checkpoints, and exits |
| 🎲 Procedural Art & Audio | All textures, sprites, and most SFX are synthesized at runtime — no asset files required |

---
## Project Structure

```
ANINO_SA_GUBAT/
│
├── main.py                # Game loop, states, HUD drawing, input, present hook
├── player.py              # Player class: movement, stamina, sanity, noise, weapons, items, wards
├── enemies.py             # Enemy AI state machine, noise investigation, sanity drain, hitscan resolution
├── map_system.py          # Map grid data, tile queries, pickups, checkpoints, doors
├── renderer.py            # Raycasting renderer, sky, particles, depth fog, viewmodel, sprite billboards
├── gl_present.py          # Readback-free GPU presenter: single texture upload + in-shader post-FX
├── graphics_manager.py    # Quality-tier presets, window/display setup, GPU feature negotiation
├── shader_renderer.py     # Legacy (readback) shader path, used only when ANINO_GPU_POST=1
├── photorealistic.py      # CPU photo-grade pass (vignette / mist / floor glints) for the 2D fallback
├── perf_governor.py       # Quality-preserving performance monitor
├── radar.py               # Top-right enemy radar widget
├── page_arrow.py          # Compass page-arrow pointing at the active objective
├── cinematic.py           # Intro cinematic scenes
├── jumpscare.py           # Jumpscare presentation layer (renders into the UI overlay)
├── animation_core.py      # Sprite-sheet prescaling + enemy animation frames
├── anim_integration.py    # Ties enemy animator frames into the sprite renderer
├── asset_generator.py     # Procedural pixel-art generator (fBm noise textures, sprites)
├── audio_synth.py         # Procedural audio generator (NumPy sound synthesis)
├── enemy_audio.py         # Spatial enemy audio (per-enemy panned/attenuated SFX)
├── menu_music.py          # Menu/title soundtrack player
├── floor_fast.py          # Vectorised floor-texture mapping helper
├── settings.py            # All game constants, colors, controls, quality tiers
├── requirements.txt       # Python dependencies
├── ANINO_SA_GUBAT.spec    # PyInstaller build specification
├── settings.json          # User configuration file (auto-created/updated)
│
├── tests/                 # Headless unit + integration tests and performance benchmarks
├── docs/                  # Design notes (GPU compositor migration, model/sprite prompts)
├── dist/                  # (auto-created) PyInstaller build output
└── assets/                # (auto-created) Cached asset directories
    ├── textures/
    └── sprites/
```

---

## Requirements & Installation

- **Python:** 3.10 or higher (Python 3.12 recommended)
- **Dependencies:** `pygame-ce` (Community Edition), `numpy`, `moderngl`, `glcontext` (the latter two power the readback-free GPU compositor; if they can't initialize, the game falls back to a pure-2D software path automatically)

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

The game renders at an internal **640×360** raycasting buffer and presents it on a SCALED **1280×720** window (fullscreen by default; toggle with `F11`).

**Display back-end selection:**
- **Default (GPU compositor):** the scene is drawn to a small CPU buffer, uploaded to the GPU once, and post-processed (bloom / grade / fog / grain) in-shader via `moderngl`. The HUD/UI is composited last on a separate layer so it stays pixel-sharp — no CPU↔GPU readback.
- **2D fallback:** if the GPU can't initialize, or you force it with `ANINO_GPU_POST=1`, the game uses a software/legacy path and keeps the same look.
- **Headless (CI / self-test):** `SDL_VIDEODRIVER=dummy python _hud_verify.py` (or the tests in `tests/`) run the full render pipeline without a display.

---
## Standalone Executable Build

ANINO SA GUBAT can be packaged as a standalone Windows executable using PyInstaller.

### Building the Executable

```bash
pip install pyinstaller
pyinstaller --clean ANINO_SA_GUBAT.spec
```

The executable will be generated in the `dist/ANINO_SA_GUBAT/` folder.

---

## Controls

| Key / Input | Action |
|---|---|
| `W`, `A`, `S`, `D` / Arrow Keys | Move Forward, Strafe Left, Move Backward, Strafe Right |
| `Shift` (Hold) | Sprint (consumes stamina) |
| `Space` | Skip Cinematic |
| `Left Mouse Click` | Fire the active weapon |
| `Mouse Wheel` | Cycle weapon: Bolo → Shotgun → Revolver (applies the equip delay, cancels an in-progress reload) |
| `R` | Reload active weapon |
| `E` | Interact (pickups, doors, checkpoints, exits) |
| `F` / `1` | Toggle flashlight (`1` checks the battery first) |
| `G` | Place Salt — a repelling / slowing circle |
| `H` | Throw Garlic — a barrier zone vs. aswang & vampires |
| `V` | Pray with the Rosary — restores sanity |
| `C` | Hold the Cross — a radiance pulse that repels nearby creatures |
| `2` | Cast Ward — Shield of Faith |
| `3` | Cast Ward — Banishment of Darkness |
| `4` | Cast Ward — Binding of the Shadow |
| `5` | Cast Ward — The Final Benediction (ultimate) |
| `Tab` | Cycle the selected Sacred Ward |
| `Q` | Cast the currently selected Sacred Ward |
| `I` | Replay Intro Cinematic (from main menu) |
| `F3` | Toggle Debug Overlay |
| `F11` | Toggle Fullscreen |
| `Escape` | Pause Game / Return to Main Menu / Quit |

> Note: the base repel ward *Light of the Almighty* is reached by cycling with `Tab` (it is ward index 0; `2`–`5` map to the remaining four wards). All bindings live under `settings.json → controls`, though a few keys (number-ward hotkeys, `Tab`, `Q`, `F`/`1`) are fixed in code.

---

## Gameplay Guide

- **Survival:** Navigate the dark forest, manage your flashlight battery, stamina, and sanity. Darkness and nearby enemies drain sanity.
- **Combat:** Use your bolo for silent close-quarters melee, the shotgun for powerful spread damage, or the revolver for precise ranged shots.
- **Sacred Wards & Items:** Cast the five wards — *Light of the Almighty* (repel), *Shield of Faith*, *Banishment of Darkness*, *Binding of the Shadow*, and the ultimate *The Final Benediction* — using Faith energy to repel or bind creatures. Scatter Salt (`G`) or place Garlic (`H`) for protective zones, pray with the Rosary (`V`) to restore sanity, and hold the Cross (`C`) for a repelling radiance pulse. Collect Bible pages for lore and strength.
- **Progression:** Reach checkpoints and find the exit portal/door to advance through chapters.

---

## Enemy Roster

| Enemy | HP | Damage | Speed | Detect Range | Vulnerabilities | Resistances |
|---|---|---|---|---|---|---|
| **Aswang** | 80 | 15 | 2.0 | 8 tiles | Repel, Garlic | None |
| **Manananggal** | 100 | 20 | 2.5 | 10 tiles | Repel, Cross | Bind |
| **Tikbalang** | 150 | 30 | 1.8 | 7 tiles | Shield | Repel |
| **Kapre** | 200 | 35 | 1.2 | 6 tiles | Banish | Bind, Repel |
| **White Lady** | 60 | 10 | 1.5 | 12 tiles | Bind | Banish |
| **Multo** | 50 | 12 | 2.0 | 8 tiles | Banish | None |
| **Sigbin** | 70 | 18 | 3.5 | 7 tiles | Bind | None |

---
## Map & Tile System

- **Grid Size:** 64 × 64 outdoor forest map.
- **Tile Types:**
  - `EMPTY`: Walkable forest ground.
  - `WALL_STONE`: Outer boundary wall (`0` and `63` edges).
  - `WALL_WOOD`: Cabin / ruins interior structure.
  - `DOOR`: Cabin entryway door.
- **Environment:** Procedurally seeded trees (`balete`, `bamboo`, `mahogany`, `dead`), undergrowth, pickups, checkpoints, and enemy spawns.

---

## Chapters

| Chapter | Setting | Player Start | Exit Position | Key Enemies |
|---|---|---|---|---|
| **Chapter 1** | Outer Forest & Abandoned Cabin | (4.5, 4.5) | (58.5, 58.5) | Aswang, Multo, Sigbin |
| **Chapter 2** | Deep Forest & Cursed Ruins | (4.5, 4.5) | (58.5, 58.5) | Aswang, Manananggal, Tikbalang, Kapre, Multo, Sigbin |

---

## Settings

### Constants (`settings.py`)
- Display resolution (`1280×720`), internal raycasting resolution (`640×360`), target FPS (`60`), FOV, max ray depth, player movement speeds, weapon damage/cooldown/ammo stats, enemy stats, UI colors, and the **quality-tier presets** (`low` / `medium` / `high`) that are the single source of truth for all renderer feature flags.

### Configuration (`settings.json`)
Auto-created and updated when settings change. Notable keys:

| Group | Keys |
|---|---|
| Display & audio | `fullscreen`, `screen_width`/`screen_height`, `mouse_sensitivity`, `invert_mouse_y`, `master_volume`, `music_volume`, `sfx_volume`, `ambient_volume`, `enemy_volume`, `vsync` |
| Graphics | `quality_tier`, `brightness`, `fov`, `enable_bloom`, `enable_film_grain`, `enable_fog`, `enable_particles`, `enable_camera_shake`, `reduce_camera_shake`, `reduce_flashing`, `gpu_world_rendering` |
| Accessibility & UI | `ui_scale` (e.g. `100%`), `high_contrast_ui`, `hud_visible` |
| Gameplay | `difficulty`, `enemy_aggression`, `enemy_spawn_rate`, `enable_sanity`, `enable_intro`, `fps_limit` |
| Performance | `adaptive_perf` (enables performance monitoring; it never changes visual quality) |
| Controls | `controls` (per-action bindings) |

- `settings.json` is auto-created or updated when you modify settings.

---

## Architecture & Modules

| Module | Role |
|---|---|
| `main.py` | Game loop, state machine (`MENU` / `PLAYING` / `PAUSED` / `GAMEOVER` / `WIN` / `INTRO`), input, HUD, audio triggers, present hook, GC policy |
| `player.py` | Movement, collision, stamina, sanity, noise generation, weapons, cancelable reloads, ward casting |
| `enemies.py` | AI state machine (`idle`, `patrol`, `investigate`, `stalk`, `attack`, `recover`, `retreat`, `defeated`), noise perception, proximity sanity drain, **hitscan resolution** (wall-aware, deterministic shotgun spread, distance falloff) |
| `map_system.py` | Map grids, tile queries, doors, pickups, checkpoints |
| `renderer.py` | Raycasting engine, parallax sky, particles, depth fog, billboard sprites, first-person viewmodel + equip animations, F3 debug overlay |
| `gl_present.py` | Readback-free GPU presenter — uploads the scene texture and runs post-FX in-shader; keeps the UI layer un-distorted |
| `graphics_manager.py` | Quality-tier presets, display/window setup, GPU feature negotiation |
| `shader_renderer.py` | Legacy readback shader path (opt-in via `ANINO_GPU_POST=1`) |
| `photorealistic.py` | CPU photo-grade pass (vignette / mist / floor glints) for the 2D fallback |
| `perf_governor.py` | Monitor-only performance tracking; preserves configured visual quality |
| `radar.py` / `page_arrow.py` | Enemy radar and objective compass widgets |
| `cinematic.py` / `jumpscare.py` | Intro cinematic and jumpscare presentation |
| `asset_generator.py` | 100% procedural pixel art & fBm noise textures with ambient occlusion |
| `audio_synth.py` / `enemy_audio.py` | Procedural sound synthesis + spatialized per-enemy audio |
| `settings.py` | All constants: display, physics, weapons, enemies, wards, colors, tiles, controls, quality tiers |

---

## Technical Notes

- **Raycasting:** DDA (Digital Differential Analyzer) algorithm for fast, accurate wall columns.
- **Z-Buffer:** Sprites depth-sorted per frame; prevented from drawing in front of closer walls.
- **Procedural Art:** Zero external asset dependencies — everything generated from Python code at startup.
- **Delta Time Cap:** `dt` capped at 50ms per frame to prevent physics tunneling on lag spikes.
- **Upscaling:** Internal 640×360 is presented on a SCALED 1280×720 window. By default the **GPU compositor** (`gl_present.py`) uploads the small buffer once and lets a fullscreen shader do the upscale + post-FX with **no CPU↔GPU readback**; the UI layer is composited last on its own texture so it stays crisp. The 2D fallback blits the buffer to the window with SDL's accelerated blit rather than a per-frame CPU `pygame.transform.scale`.
- **GC policy:** long-lived map/sprite caches are frozen into the permanent generation and the cyclic collector is disabled while playing, so multi-millisecond GC pauses never land on a gameplay frame.
- **Platform:** Built and tested on Windows with Python 3.10+. Compatible with Linux/macOS given the same dependencies.

---

## Performance & Scaling

The scene contains substantial CPU-side rendering work, while the GPU compositor handles presentation and post-processing. Use the F3 stage timings on the target machine to identify whether a slowdown comes from CPU rendering, uploads, or GPU work.

- **Performance monitor (`perf_governor.py`):** when enabled (`adaptive_perf`), it measures gameplay frame work over rolling ~1.5 s windows, ignores warmup and long hitches, and reports sustained over-budget work. It is deliberately monitor-only: it never disables shaders, particles, stars, wind, fog, trees, or photo grading. Use the F3 stage timings to identify the actual bottleneck.
- **Quality tiers (`graphics_manager.py` / `settings.py`):** `low` / `medium` / `high` presets remain the source of configured renderer feature flags. The performance monitor never overrides them.
- **Cross-hardware targets (at 60 FPS):**

  The monitor does not apply automatic device tiers or tree caps. Choose the desired quality tier explicitly in settings, then use F3 timings to profile performance. Do not infer GPU headroom from the presence of an OpenGL context alone.

- **Spikes are guarded:** the cyclic GC is frozen during play, the redundant CPU upscale in the 2D fallback is gone, and the biggest load-time spikes (map generation, sprite-sheet prescaling, audio preparation) are the main remaining targets for lazy/cached loading.

---

## Testing

The project ships a headless test + benchmark suite in `tests/` (no display required). A few highlights:

| Script | Purpose |
|---|---|
| `smoke_test.py` | End-to-end "does it run" sanity checks |
| `test_gl_present.py` | GPU presenter: texture upload, shader post, **HUD layer never distorted** |
| `test_weapon_hitscan.py` | Wall-aware hitscan, deterministic shotgun spread, distance falloff |
| `test_perf_governor.py` | Confirms performance monitoring never changes configured visual effects |
| `test_enemy_hit_reactions.py` / `test_enemy_drops.py` / `test_collision.py` | Combat, loot, and collision behavior |
| `benchmark_profile.py` | Per-stage frame-time export for the F3 debug overlay |

Run any of them with:

```bash
python tests/test_gl_present.py
python tests/smoke_test.py
# full headless HUD render check:
$env:SDL_VIDEODRIVER='dummy'; python _hud_verify.py
```

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
