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
12. [Save System](#save-system)
13. [Settings](#settings)
14. [Architecture & Modules](#architecture--modules)
15. [Technical Notes](#technical-notes)
16. [Intro Cinematic](#intro-cinematic)
17. [Lore](#lore)

---

## Overview

**ANINO SA GUBAT** is a pseudo-3D first-person game rendered using the classic **raycasting** technique (Wolfenstein-style), reimagined in a Philippine horror setting. You play as a lone survivor navigating cursed forests and ruins, hunted by mythical creatures (*aswang*, *manananggal*, *kapre*, *multo*, *sigbin*, *tikbalang*, *white_lady*) straight out of Filipino legend.

The game features:
- 100% procedurally generated pixel-art assets and textures (no external texture files needed)
- An atmospheric raycasting renderer with colored fog, vignette, particle systems, and flashlight effects
- Multiple weapons with reload mechanics (Bolo, Shotgun, Revolver)
- A unique **Sacred Ward** and faith system based on Filipino spiritual traditions
- Multi-chapter progression with JSON save/load support and standalone Windows executable build

---

## Features

| Feature | Details |
|---|---|
| 🎮 Raycasting 3D | Pseudo-3D first-person view at 640×360 internal resolution, scaled to 1280×720 |
| 👹 7 Enemy Types | Each with unique AI states, stats, vulnerabilities, and resistances |
| ⚔️ 3 Weapons | Bolo (melee), Shotgun, Revolver — with ammo, magazines, and reload |
| ✝️ 5 Sacred Wards | Special faith-powered abilities to repel, shield, banish, bind, and purge |
| 🔦 Flashlight | Battery-powered; drains over time |
| 🗺️ 2 Chapters | Hand-crafted outdoor forest maps with trees, debris, checkpoints, and exits |
| 💾 Save/Load | JSON-based save files stored in a `saves/` directory |
| 🎲 Procedural Art | All textures and sprites are generated at runtime — no asset files required |

---
## Project Structure

```
ANINO_SA_GUBAT/
│
├── main.py              # Game loop, states, HUD drawing, save/load logic
├── player.py            # Player class: movement, stamina, sanity, noise, weapons, items
├── enemies.py           # Enemy AI state machine, noise investigation, proximity sanity drain
├── map_system.py        # Map grid data for Chapter 1 & 2, tile queries, pickups
├── renderer.py          # Raycasting renderer, colored fog, parallax sky, particles, post-fx
├── asset_generator.py   # Procedural pixel-art generator (fBm noise textures, sprites)
├── audio_synth.py       # Procedural audio generator (NumPy sound synthesis)
├── settings.py          # All game constants, colors, controls, save/load settings
├── requirements.txt     # Python dependencies
├── ANINO_SA_GUBAT.spec  # PyInstaller build specification
├── settings.json        # User configuration file (auto-created/updated)
│
├── saves/               # (auto-created) JSON save files
├── dist/                # (auto-created) PyInstaller build output
└── assets/              # (auto-created) Cached asset directories
    ├── textures/
    └── sprites/
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

The game launches at **1280×720** (windowed by default, with an internal 640×360 raycasting buffer).

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
| `Space` | Jump / Skip Cinematic |
| Left Mouse Click | Attack / Shoot active weapon |
| Right Mouse Click | Alt Fire / Secondary Weapon Action (Unused) |
| `R` | Reload active weapon |
| `1`, `2`, `3` | Switch Weapon (1: Bolo, 2: Shotgun, 3: Revolver) |
| `4`, `5`, `6`, `7`, `8` | Cast Sacred Wards (1: Light/Repel, 2: Shield, 3: Banish, 4: Bind, 5: Purge) |
| `E` | Interact (pickups, doors, checkpoints, exits) |
| `F` | Toggle Flashlight |
| `Q` | Throw Salt (creates repelling/slowing zone) |
| `C` | Place Garlic (creates barrier zone against vampires/aswang) |
| `S` | Save Game (when paused) |
| `L` | Load Game (from main menu) |
| `I` | Replay Intro Cinematic (from main menu) |
| `F3` | Toggle Debug Overlay |
| `F4` | Snap camera toward moon azimuth |
| `F11` | Toggle Fullscreen |
| `Escape` | Pause Game / Return to Main Menu / Quit |

---

## Gameplay Guide

- **Survival:** Navigate the dark forest, manage your flashlight battery, stamina, and sanity. Darkness and nearby enemies drain sanity.
- **Combat:** Use your bolo for silent close-quarters melee, the shotgun for powerful spread damage, or the revolver for precise ranged shots.
- **Sacred Wards & Items:** Cast wards using Faith energy to repel or bind creatures. Scatter Salt or place Garlic to create protective zones. Collect Bible pages for lore and strength.
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

## Save System

- **Storage:** JSON format saved in the `saves/` directory (`save_0.json`, etc.).
- **Saved Data:** Current chapter, player position, health, armor, stamina, sanity, weapons, ammunition, inventory items (salt, garlic, Bible pages), faith energy, and active checkpoint.

---

## Settings

### Constants (`settings.py`)
- Display resolution (`1280×720`), internal raycasting resolution (`640×360`), target FPS (`60`), FOV (`60°`), max ray depth (`25 tiles`), player movement speeds, weapon damage/cooldown/ammo stats, enemy stats, and UI colors.

### Configuration (`settings.json`)
- User preferences (`fullscreen`, `quality_tier`, `enable_intro`, volume levels, etc.).
- `settings.json` is auto-created or updated upon saving game state or modifying settings.

---

## Architecture & Modules

| Module | Role |
|---|---|
| `main.py` | Game loop, state machine (`MENU` / `PLAYING` / `PAUSED` / `GAMEOVER` / `WIN`), HUD, audio triggers, save/load |
| `player.py` | Movement, collision, stamina, sanity, noise generation, weapons, cancelable reloads, serialization |
| `enemies.py` | AI state machine (`idle`, `patrol`, `investigate`, `stalk`, `attack`, `recover`, `retreat`, `defeated`), noise perception, proximity sanity drain |
| `map_system.py` | Map grids, tile queries, doors, pickups, checkpoints |
| `renderer.py` | Raycasting engine, colored fog, parallax sky, particles, post-fx (vignette, blood), F3 debug overlay |
| `asset_generator.py` | 100% procedural pixel art & fBm noise textures with ambient occlusion |
| `audio_synth.py` | Procedural sound synthesis using NumPy arrays & Pygame mixer |
| `settings.py` | All constants: display, physics, weapons, enemies, wards, colors, tiles, controls |

---

## Technical Notes

- **Raycasting:** DDA (Digital Differential Analyzer) algorithm for fast, accurate wall columns.
- **Z-Buffer:** Sprites depth-sorted per frame; prevented from drawing in front of closer walls.
- **Procedural Art:** Zero external asset dependencies — everything generated from Python code at startup.
- **Delta Time Cap:** `dt` capped at 50ms per frame to prevent physics tunneling on lag spikes.
- **Upscaling:** Internal 640×360 upscaled to 1280×720 via `pygame.transform.scale` for a retro CRT aesthetic.
- **Platform:** Built and tested on Windows with Python 3.10+. Compatible with Linux/macOS given same dependencies.

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
