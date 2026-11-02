# ANINO SA GUBAT: Mga Bulong ng Dilim
### *Shadows in the Forest: Whispers of the Dark*

A first-person, pseudo-3D horror-survival game inspired by Philippine folklore. Explore a haunted forest, gather sacred pages, manage your sanity and supplies, and survive until sunrise.

**Current build:** `BUILD 2026.11.02-SURVIVAL-AUDIO`

---

## At a glance

- **Genre:** First-person horror / survival
- **Setting:** A supernatural forest inspired by Filipino folklore
- **Engine:** Python, Pygame-CE and NumPy
- **Rendering:** CPU-side vectorised raycasting with an optional ModernGL shader post-processing path
- **Display:** 1280 × 720 window; internal rendering resolution depends on the quality preset
- **Objective:** Find all five Bible pages in a chapter, then survive until 7:00 AM

## Features

### Survival and exploration
- Two chapters with carry-over progression.
- A large, seeded forest with trails, village structures, a limestone cave, swamp, ruins and shrine.
- Five Bible pages per chapter, a sealed exit, sunrise countdown and compass guidance.
- Flashlight battery, stamina, health, armor, Faith and sanity management.
- Checkpoints and JSON save/load support.
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
| `E` | Interact with doors and checkpoints |
| `M` | Toggle radar |
| `Esc` | Pause |
| `F11` | Toggle fullscreen |

### Menu controls
- **Main menu:** `Enter` starts a new game, `L` loads a save, `I` replays the intro, `Esc` quits.
- **Pause menu:** `Esc` resumes, `S` saves, `M` returns to the main menu.
- **Game over:** `R` respawns at a checkpoint; `M` returns to the main menu.
- **Chapter complete:** `Enter` continues; `M` returns to the main menu.

### Debug keys
- `F3`: Toggle the debug overlay, including build information and FPS.
- `F4`: Toggle the raw-scene diagnostic view.
- `F6`: Teleport near the nearest living enemy.
- `F7`: Defeat all enemies (chapter-progression testing).

---

## Gameplay tips

1. Follow the compass and collect all **five Bible pages** before trying to leave the chapter.
2. Watch the sunrise clock. You must survive until **7:00 AM** after completing the page objective.
3. Conserve flashlight battery and stay in lit areas when possible to protect sanity.
4. Keep distance from enemies when your sanity is low: Frenzy makes them faster and more dangerous.
5. Use the bolo when you need a quieter option. Gunfire and reloads can attract attention.
6. Save at the cabin checkpoint when available.
7. Use salt, garlic and Faith-powered wards to control dangerous encounters.

---

## Project layout

```text
ANINO_SA_GUBAT/
├── main.py              # Game loop, states, HUD, objectives and save/load
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
│   └── audio/frenzy_mode_ambience.mp3  # Optional Frenzy Mode background ambience
├── saves/               # JSON save files (created as needed)
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

For the Frenzy Mode background layer, place the supplied track at `assets/audio/frenzy_mode_ambience.mp3`. It loops on a dedicated mixer channel at 10% volume with fade-in/fade-out, and only plays while Frenzy is active during gameplay. If the file is absent or cannot be loaded, the game continues silently without interrupting other audio.

## Save data and configuration

- Save data is stored as JSON under `saves/`.
- User settings are stored in `settings.json`; the file is created when settings are saved.
- Generated ground/cache data is stored under `assets/cache/`.
- Crash details are written to `crash.log` when an unhandled error is captured.

## Build a Windows executable

Install PyInstaller, then run:

```bash
python -m pip install pyinstaller
pyinstaller --clean ANINO_SA_GUBAT.spec
```

The packaged output is written under `dist/`.

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
