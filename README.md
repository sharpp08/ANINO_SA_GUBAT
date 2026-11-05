# ANINO SA GUBAT: Mga Bulong ng Dilim
### *Shadows in the Forest: Whispers of the Dark*

A first-person, pseudo-3D horror-survival game inspired by Philippine folklore. Explore a haunted forest, gather sacred pages, manage your sanity and supplies, and survive until sunrise.

**Current build:** `BUILD 2026.11.05-HITSCAN-HUD`

---

## At a glance

- **Genre:** First-person horror / survival
- **Setting:** A supernatural forest inspired by Filipino folklore
- **Engine:** Python, Pygame-CE and NumPy
- **Rendering:** CPU-side vectorised raycasting with an optional ModernGL shader post-processing path
- **Display:** 1280 × 720 window; internal rendering resolution depends on the quality preset
- **Objective:** Find all five Bible pages in a chapter, then survive until 7:00 AM

## Features

### Settings menu
- Open Settings from the main menu or pause menu with `S`.
- The atmospheric settings screen includes Video, Audio, Controls, Gameplay and Accessibility categories.
- Use arrow keys to navigate and change values, Enter to edit, Tab to switch categories, and Escape to return.
- Select **Apply** to save preferences to `settings.json`; **Reset** restores defaults.
- Graphics quality, display mode, FPS cap, mouse sensitivity and mixer volume are applied at runtime. Other options are saved as preferences for supported systems.


### Survival and exploration
- Two chapters with carry-over progression.
- A large, seeded forest with trails, village structures, a limestone cave, swamp, ruins and shrine.
- Five Bible pages per chapter, a sealed exit, sunrise countdown and compass guidance.
- Flashlight battery, stamina, health, armor, Faith and sanity management.
- Permanent death: dying ends the run; there are no checkpoints, respawns, or save/load persistence.
- A rotating radar mini-map for nearby enemies, obstacles and pickups.

### Sanity and Frenzy
Darkness and nearby enemies reduce sanity; light and certain restorative actions help recover it. When sanity falls below **30**, enemies enter **Frenzy**:
- Living enemies become aggressive and pursue the player.
- Frenzy increases enemy movement speed by 45% and damage by 25%.
- Enemy attack cooldowns are shortened.
- Survival-mode enemy spawn intervals become shorter as sanity falls, reaching 55% of the normal interval at zero sanity.
- Frenzy uses a recovery threshold of 36 sanity to prevent rapid toggling around the activation threshold.
- A quiet, looping background ambience fades in when Frenzy activates and fades out when it ends or gameplay is paused/exited.

Keep your flashlight charged, use protective items and wards, and avoid letting sanity collapse.

### Combat
Three weapons are available:
- **Bolo:** quiet close-range melee.
- **Shotgun:** powerful multi-pellet attack with a small magazine.
- **Revolver:** precise ranged firearm.

Weapons have ammunition, reloads, firing feedback and first-person viewmodel animations. Reloading makes noise; firing firearms can attract enemies. Reloads can be interrupted by combat or weapon switching.

### Sacred wards and items
Five Faith-powered wards provide light, shielding and supernatural crowd control:
1. Light
2. Shield
3. Banish
4. Bind
5. Final

Salt creates a protective zone and garlic can be thrown to create a barrier against aswang. Pickups include health, ammunition, flashlight battery, Faith, salt, garlic and Bible pages.

### Enemies and atmosphere
Seven folklore-inspired enemy types appear across the chapters: **Aswang, Manananggal, Tikbalang, Kapre, White Lady, Multo and Sigbin**. Enemies have distinct stats, AI behaviours, hit reactions, death animations, procedural creature voices, stalking calls and individual jumpscare sequences.

Other effects include dynamic wind, rain and lightning, fog, glowing eyes and pickups, particle effects, screen shake, heartbeat feedback and a layered night sky.

---

## Changelog

### BUILD 2026.11.05-HITSCAN-HUD (November 5, 2026)

- **Geometric hitscan weapon damage:** `apply_weapon_hit` now uses precise ray-casting instead of random circle checks, respecting 3D line-of-sight and solid map tiles. Enemy hits only register when forward of the aim and within the enemy's physical body radius. Shotgun spread is deterministic even-fan instead of random. Melee bolts respect wall-blocking.
- **HUD readability improvements:** panel opacity and text alignment are updated for better legibility, dedicated HUD fonts replace dynamic parameters, fixed-width item columns for inventory, and increased spacing between objective lines and weapon slots.
- **Outlined text helper:** `_outlined()` in `main.py` renders text with a subtle dark alpha-blended outline so UI remains readable over post-processing effects such as muzzle flashes, color grade, and bloom. Used in the survival stats, inventory, weapon chips, and pause menu.
- **Frenzy background audio fallback:** if `frenzy_mode_ambience.mp3` is missing or cannot be loaded, procedural audio provides a silent-safe fallback so the Frenzy layer does not break startup.
- **Windows executable rebuilt:** `ANINO_SA_GUBAT.exe` was recompiled from the PyInstaller spec so the shipped binary includes the geometric hitscan damage, HUD readability, and outlined-text changes.

### BUILD 2026.11.02-SURVIVAL-AUDIO (November 2, 2026)

- **Frenzy Mode ambience (new audio layer):** a quiet looping background track plays only while Frenzy is active during gameplay. It loops on a dedicated mixer channel with fade-in/fade-out and stops on Frenzy end, pause or exit. The track `assets/audio/frenzy_mode_ambience.mp3` now ships with the repository; if it is missing or cannot be loaded, the game continues silently without affecting other audio.
- **Frenzy ambience volume fix:** the source MP3 was attenuated but the playback level had been dropped to 5%, making the layer inaudible. Playback was restored to the intended 10% channel volume (`FRENZY_AMBIENCE_VOLUME`).
- **Frenzy audiovisual feedback:** the old Frenzy camera-waving feedback is replaced with a strong inhale/exhale zoom and a separate red heartbeat pulse. The pulse follows transient peaks detected from the decoded heartbeat recording and the live playback position, rather than a guessed BPM. Place the supplied recordings at `assets/audio/heartbeat.mp3` and `assets/audio/heavy-breathing-sound.mp3`; the heartbeat and breathing loops start and fade out with Frenzy Mode. If either optional recording is absent or cannot load, the game remains playable.
- **ModernGL hybrid GPU post-processing:** optional fragment-shader pass for color grading, flashlight treatment, fog, vignette and supernatural distortion, with a Pygame fallback when no OpenGL context is available. `moderngl` and `glcontext` were added to `requirements.txt`; see [GPU_RENDERING.md](GPU_RENDERING.md).
- **Sanity HUD and spawn scaling:** the sanity bar is now displayed in the HUD, and survival-mode enemy spawn intervals scale with sanity (down to 55% of the normal interval at zero sanity).
- **Frenzy AI fixes:** enemy AI is restored when the sanity Frenzy ends, and a per-frame pathfinding spike that occurred during Frenzy was fixed.
- **Recorded SFX and storm audio:** optional custom recordings in `assets/audio/` for revolver/shotgun fire and reload, walk-cycle footsteps, near/far thunder and the intro cinematic score, with procedural fallbacks for every missing file.
- **Windows executable rebuilt:** the bundled `ANINO_SA_GUBAT.exe` was recompiled from the PyInstaller spec so the shipped binary includes all of the above audio and rendering changes.

---

## Requirements

- Python 3.10 or newer
- Windows is the primary documented platform; Linux and macOS may work with compatible dependencies and graphics drivers.

Install dependencies from the project directory:

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The requirements include:
- `pygame-ce`
- `numpy`
- `moderngl`
- `glcontext`

ModernGL is optional at runtime: if a usable OpenGL context cannot be created, the game falls back to its Pygame rendering path.

## Run the game

```bash
python -B main.py
```

The game starts at 1280 × 720. On first launch, procedural assets and the cached world-ground texture may take extra time to generate. Later launches can reuse the cache.

## Controls

| Input | Action |
|---|---|
| `W` / `A` / `S` / `D` | Move |
| Mouse | Look around |
| Hold `Shift` | Sprint |
| `Space` | Jump / skip intro cinematic |
| Left mouse button | Attack or fire |
| Mouse wheel | Cycle Bolo → Shotgun → Revolver |
| `R` | Reload |
| `F` or `1` | Toggle flashlight / Light |
| `2` | Shield ward |
| `3` | Banish ward |
| `4` | Bind ward |
| `5` | Final ward |
| `Tab` | Cycle selected ward |
| `Q` | Cast selected ward |
| `G` | Place salt |
| `H` | Throw garlic |
| `E` | Interact with doors |
| `M` | Toggle radar |
| `Esc` | Pause |
| `F11` | Toggle fullscreen |

### Menu controls
- **Main menu:** `Enter` starts a fresh run, `I` replays the intro, `Esc` quits.
- **Pause menu:** `Esc` resumes, `M` returns to the main menu. Saving and loading runs are disabled for competitive fairness.
- **Game over:** death is permanent for that run; `M` returns to the main menu.
- **Chapter complete:** `Enter` continues; `M` returns to the main menu.

### Debug overlay
- `F3`: Cycle the debug overlay (compact -> full -> off), including build information and FPS.

Quality tier switching is handled by `F5` (next tier) and `F6` (previous tier); see Quality settings below.

---

## Gameplay tips

1. Follow the compass and collect all **five Bible pages** before trying to leave the chapter.
2. Watch the sunrise clock. You must survive until **7:00 AM** after completing the page objective.
3. Conserve flashlight battery and stay in lit areas when possible to protect sanity.
4. Keep distance from enemies when your sanity is low: Frenzy makes them faster and more dangerous.
5. Use the bolo when you need a quieter option. Gunfire and reloads can attract attention.
6. Avoid dying: there are no checkpoints or respawns, and progress is not saved between sessions.
7. Use salt, garlic and Faith-powered wards to control dangerous encounters.

---

## Project layout

```text
ANINO_SA_GUBAT/
├── main.py              # Game loop, states, HUD and objectives
├── player.py            # Player movement, stats, weapons, items and wards
├── enemies.py           # Enemy AI, Frenzy, loot and combat reactions
├── map_system.py        # Forest generation, world entities and collision
├── renderer.py          # Raycasting renderer, sprites, lighting and effects
├── shader_renderer.py   # Optional ModernGL post-processing renderer
├── raycast_fast.py      # Vectorised NumPy raycasting
├── floor_fast.py        # Vectorised floor and terrain rendering
├── pathfinder.py        # Enemy pathfinding
├── asset_generator.py   # Procedural textures, sprites and viewmodels
├── audio_synth.py       # Procedural audio and optional recorded sound loading
├── enemy_audio.py       # Creature voices and spatial enemy audio
├── jumpscare.py         # Enemy-specific jumpscare sequences
├── animation_core.py    # Springs, particles and animation utilities
├── anim_integration.py  # Enemy animation integration
├── radar.py             # Radar / mini-map
├── objective.py         # Objective and direction calculations
├── page_arrow.py        # Compass-arrow HUD
├── weather_fx.py        # Rain, lightning and weather effects
├── cinematic.py         # Intro cinematic
├── settings.py          # Gameplay constants, quality presets and configuration
├── requirements.txt     # Python dependencies
├── GPU_RENDERING.md     # ModernGL setup and current renderer limitations
├── ANINO_SA_GUBAT.spec  # PyInstaller build specification
├── assets/              # Optional audio/art and generated caches
│   └── audio/frenzy_mode_ambience.mp3  # Bundled Frenzy Mode background ambience (recorded SFX optional)
└── tools/               # Development and asset utilities
```

## Rendering and performance notes

The world is still drawn primarily by the **CPU-side Pygame/NumPy raycaster**. The vectorised DDA raycaster and floor renderer reduce Python per-pixel/per-ray work.

The optional ModernGL path applies a fragment shader for post-processing effects such as color grading, flashlight treatment, fog, vignette and supernatural distortion. It currently:
1. Uploads the CPU-rendered frame to a GPU texture.
2. Applies the shader.
3. Reads the processed frame back into a Pygame surface.

This is a **hybrid renderer**, not a full GPU raycaster. Frame upload and readback can limit performance, particularly on integrated graphics. A full GPU pipeline that keeps the rendered frame on the GPU is future work. See [GPU_RENDERING.md](GPU_RENDERING.md) for setup and troubleshooting.

### Quality settings

The quality presets are `low`, `medium` and `high`. They control internal resolution and selected rendering effects and workload limits. The active tier can be configured through `quality_tier` in `settings.json`; the game also supports runtime quality switching with `F5` and `F6`.

If performance is poor, try the low preset first and compare stable frame rate and frame time. High CPU or GPU utilisation is not itself the goal.

## Audio

The game combines procedural ambience and creature sounds with optional recorded sound assets in `assets/audio/`. When supported custom recordings are missing or cannot be loaded, procedural sounds provide a fallback. The audio engine uses the Pygame mixer and NumPy-generated sound.

The Frenzy Mode background layer ships with the repository at `assets/audio/frenzy_mode_ambience.mp3`. It loops on a dedicated mixer channel at 10% volume with fade-in/fade-out, and only plays while Frenzy is active during gameplay. The source MP3 is intentionally attenuated and the playback level was restored to an audible 10% (see changelog). If the file is absent or cannot be loaded, the game continues silently without interrupting other audio.

## Configuration and local data

- User settings are stored in `settings.json`; the file is created when settings are saved.
- Generated ground/cache data is stored under `assets/cache/`.
- Crash details are written to `crash.log` when an unhandled error is captured.
- Gameplay progress is never written to disk; every new run begins at Chapter 1.

## Build a Windows executable

The spec builds a standalone one-file executable (hidden console; UPX compression when available). From the project directory:

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

python -m pip install -r requirements.txt
python -m pip install pyinstaller

# Build (clean discards stale PyInstaller caches; rebuild after any code, audio or rendering change)
python -m PyInstaller --clean ANINO_SA_GUBAT.spec
```

Steps to produce the latest binary:

1. Run the command above; PyInstaller writes `dist/ANINO_SA_GUBAT/ANINO_SA_GUBAT.exe`.
2. Copy it to the project root (the location tracked in git) and optionally to `release/` for distribution:

   ```bash
   copy dist\ANINO_SA_GUBAT\ANINO_SA_GUBAT.exe ANINO_SA_GUBAT.exe
   copy dist\ANINO_SA_GUBAT\ANINO_SA_GUBAT.exe release\
   ```

3. Keep the `assets/` folder next to the executable: the game resolves `assets/` and `settings.json` relative to the folder the exe lives in. The bundled recorded SFX (including `assets/audio/frenzy_mode_ambience.mp3`) must live under `assets/audio/` for custom sound to play; without them the procedural audio fallbacks are used and the Frenzy layer stays silent.
4. Commit the updated root `ANINO_SA_GUBAT.exe` alongside the source changes so the shipped binary always matches the code.

## Current technical caveats

- ModernGL post-processing is optional and may fall back to Pygame if context creation fails.
- The ModernGL path currently performs CPU-to-GPU upload and GPU-to-CPU readback; it is not yet a fully GPU-resident renderer.
- Enemy pathfinding uses a coarse grid and may not navigate every narrow obstacle perfectly.
- Some visual and audio features depend on optional assets or graphics-driver support; procedural/software fallbacks are provided where implemented.
- Performance and gameplay should be profiled on the target machine; documentation updates do not imply a runtime benchmark has been performed.

---

## Lore

> *"Huwag lumabas ng gabi. Baka abutin ka ng dilim."*  
> *(Don't go out at night. The darkness might catch you.)*

The forest has always been alive. Tonight, the old warnings mean something more. Ancient spirits roam the cursed woods. You are a lone traveler with a bolo, a flickering flashlight and faith passed down through generations. Find the pages. Hold on until dawn.

*Ingatan mo ang iyong sarili. Ang gubat ay may ibang batas sa gabi.*

## Adaptive 60 FPS governor

The game measures its own per-frame work time (excluding the vsync wait). If the average stays above ~14.5 ms it sheds optional effects one level at a time, and restores them after ~10 s of headroom:

1. GPU post-process pass off
2. Floating particles, physics particles and stars off
3. Tree wind sway off and ~40% fewer billboard trees
4. Depth fog off and a further tree cut

Changes are logged to the console as `[PERF] ... -> level N`. Disable it with `"adaptive_perf": false` in `settings.json` or `ANINO_ADAPTIVE=0`. The GPU post-process pass can also be turned off alone with `"enable_gpu_post": false` or `ANINO_GPU_POST=0`. Tests: `python tests/test_perf_governor.py`.

## GPU presentation path (OpenGL window)

The CPU still draws the scene, but the finished 640x360 frame is now uploaded to the GPU once and a single shader pass does the colour grade, vignette, fog tint, grain and the upscale to the window. This replaces the old offscreen shader that read the frame back to the CPU, the software 640x360 -> 1280x720 scale, and ~2 MB/frame of allocations. Fullscreen uses the monitor's native resolution with letterboxing.

On startup it draws a test pattern and reads four pixels back once to verify colours and orientation; if that fails (or no OpenGL 3.3 context exists) the game silently keeps the normal 2D window. Look for `[GPU]` lines in the console (`GL_RENDERER=...` shows which GPU is used).

Turn it off with `"gpu_present": false` in `settings.json` or `ANINO_GPU_PRESENT=0`. Tests: `python tests/test_gl_present.py`.
