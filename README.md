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
15. [Technical Notes & Screenshots](#technical-notes--screenshots)

---

## Overview

**ANINO SA GUBAT** is a pseudo-3D first-person game rendered using the classic **raycasting** technique (Wolfenstein-style), reimagined in a Philippine horror setting. You play as a lone survivor navigating cursed forests and ruins, hunted by mythical creatures (*aswang*, *manananggal*, *kapre*, *multo*, *sigbin*, *tikbalang*, *tiyanak*) straight out of Filipino legend.

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
| 🗺️ 2 Chapters | Hand-crafted maps with enemies, pickups, checkpoints, and exits |
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
│
├── saves/               # (auto-created) JSON save files
└── assets/              # (auto-created) Cached asset directories
    ├── textures/
    ├── sprites/
    ├── audio/
    └── fonts/
```

---

## Requirements & Installation

### Prerequisites
- **Python 3.10+**
- **pip**

### Install Dependencies

```bash
pip install -r requirements.txt
```

`requirements.txt` contains:
```
pygame-ce>=2.4.0
numpy>=1.24.0
```

> ⚠️ This project uses **`pygame-ce`** (Community Edition), not the standard `pygame`. Make sure you install `pygame-ce` specifically, as the APIs differ slightly and `pygame-ce` offers better performance.

---

## How to Run

```bash
cd d:\PhyGame\ANINO_SA_GUBAT
python main.py
```

The game opens at **1280×720** (windowed by default). It automatically sets its working directory to its own folder on startup.

---
---

## Standalone Executable Build

ANINO SA GUBAT can be packaged as a standalone Windows executable using PyInstaller.

### Running the Executable
Once built, the standalone executable is located at:
```bash
dist\ANINO_SA_GUBAT.exe
```

### Building via PyInstaller
To rebuild the executable from source:
```bash
pyinstaller ANINO_SA_GUBAT.spec
```
The spec file (`ANINO_SA_GUBAT.spec`) bundles all procedural asset generators, audio synthesis modules, and dependencies into a self-contained distribution folder/binary.

---


## Controls

### In-Game

| Action | Key / Mouse |
|---|---|
| Move Forward | `W` |
| Move Backward | `S` |
| Strafe Left | `A` |
| Strafe Right | `D` |
| Look / Turn | Mouse Movement |
| Fire / Attack | `Left Mouse Button` |
| Alt Fire | `Right Mouse Button` |
| Reload | `R` |
| Toggle Flashlight | `F` |
| Interact (doors, etc.) | `E` |
| Sprint | `Left Shift` |
| Crouch | `Left Ctrl` |
| Jump | `Space` |
| Open Ward Menu | `Q` |
| Select Ward 1–5 | `1` `2` `3` `4` `5` |
| Throw Salt | `G` |
| Throw Garlic | `H` |
| Use Rosary | `V` |
| Use Cross | `C` |
| Pause | `Escape` |

### Menus

| Screen | Action | Key |
|---|---|---|
| Main Menu | Start New Game | `Enter` |
| Main Menu | Load Saved Game | `L` |
| Main Menu | Quit | `Escape` |
| Pause | Resume | `Escape` |
| Pause | Save Game | `S` |
| Pause | Main Menu | `M` |
| Game Over | Respawn at Checkpoint | `R` |
| Game Over | Main Menu | `M` |

---

## Gameplay Guide

### HUD Explained

The HUD overlays critical information at all times during gameplay:

| HUD Element | Color | Description |
|---|---|---|
| HP Bar | 🟢 Green | Current health (max 100) |
| AP Bar | 🔵 Blue | Armor points — absorbs damage before HP |
| Battery Bar | 🟡/🔴 | Flashlight charge — turns red below 30% |
| Faith Bar | 💙 Blue | Sacred ward energy; regenerates passively |
| Ward Slots | Bottom-center | Cooldown timers for wards 1–5 |
| Weapon Name | 🟡 Gold | BOLO / SHOTGUN / REVOLVER |
| Ammo Counter | Yellow | `Magazine / Reserve` (Bolo shows `---`) |
| Items Line | Gray | SALT count · GARLIC count · PAGES count |

---

### Weapons

| Weapon | Type | Damage | Range | Cooldown | Magazine | Reserve |
|---|---|---|---|---|---|---|
| **Bolo** | Melee | 25 | 1.5 tiles | 0.4 s | Unlimited | — |
| **Shotgun** | Spread (5 pellets) | Up to 40 | 8 tiles | 0.8 s | 2 shells | 50 max |
| **Revolver** | Precision shot | 30 | 15 tiles | 0.5 s | 6 rounds | 36 max |

- **Shotgun reload time:** 1.5 s — damage falls off with distance.
- **Revolver reload time:** 1.2 s — slight falloff at very long range.
- **Reload:** press `R` at any time while using a ranged weapon.

---

### Sacred Wards

Open the ward menu with `Q`, select with `1`–`5`. Consumes Faith Energy and triggers a cooldown.

| Ward | Key | Faith Cost | Cooldown | Effect |
|---|---|---|---|---|
| **Holy Light (Repel)** | `1` | 20 | 8 s | Sacred ring — repels vulnerable enemies |
| **Spirit Shield** | `2` | 25 | 15 s | Barrier — reduces incoming damage |
| **Banishment** | `3` | 30 | 12 s | Banishes spectral enemies |
| **Binding Chains** | `4` | 20 | 10 s | Immobilizes nearby enemies |
| **Final Rite** | `5` | 50 | 30 s | Ultimate purge — damages all nearby creatures |

> Faith regenerates at **0.5/sec**. Ward 1 is unlocked from the start.

---

### Sacred Items & Flashlight

| Item / Tool | Key | Effect |
|---|---|---|
| **Salt** | `G` | Drops a salt protection zone (repels enemies, 8 s, max 10) |
| **Garlic** | `H` | Drops a garlic zone (weakens enemies, 6 s, max 8) |
| **Rosary** | `V` | Rosary prayer (8 s cooldown) |
| **Cross** | `C` | Cross radiance burst (6 s cooldown) |
| **Flashlight** | `F` | Toggle on/off — drains 2/sec, recharges 0.5/sec when off |

---

### Pickups

Walk into pickups to collect automatically.

| Pickup | Effect |
|---|---|
| Health Pack | Restores HP |
| Ammo (Shotgun) | Adds shells to reserve |
| Ammo (Revolver) | Adds rounds to reserve |
| Salt | +1 (max 10) |
| Garlic | +1 (max 8) |
| Battery | Restores flashlight battery |
| Faith Orb | Restores Faith Energy |
| Bible Page | Lore collectible; may unlock wards |

---



## Enemy Roster

Seven mythical creatures from **Philippine folklore** stalk the forest.

| Enemy | HP | Damage | Speed | Detect Range | Vulnerabilities | Resistances |
|---|---|---|---|---|---|---|
| **Aswang** | 80 | 15 | 2.0 | 8 tiles | Repel, Garlic | — |
| **Manananggal** | 100 | 20 | 2.5 | 10 tiles | Repel, Cross | Bind |
| **Tikbalang** | 150 | 30 | 1.8 | 7 tiles | Shield | Repel |
| **Kapre** | 200 | 35 | 1.2 | 6 tiles | Banish | Bind, Repel |
| **White Lady** | 60 | 10 | 1.5 | 12 tiles | Bind | Banish |
| **Multo** | 50 | 12 | 2.0 | 8 tiles | Banish | — |
| **Sigbin** | 70 | 18 | 3.5 | 7 tiles | Bind | — |

> **Vulnerable** = 2× damage. **Resistant** = 0.5× damage.

### AI State Machine
```
IDLE → PATROL → INVESTIGATE → STALK → ATTACK → RECOVER → RETREAT → DEFEATED
```
Active status effects on enemies: `Bound` (immobilized), `Repelled` (fleeing), `Shield Debuff` (takes extra damage).

---

## Map & Tile System

Maps are 2D integer grids. Key tile values:

| Range | Meaning |
|---|---|
| `0` | EMPTY — walkable floor |
| `1–4` | Walls: Stone, Wood, Bamboo, Balete |
| `5` | Door — open with `E` |
| `10–17` | Pickups: Health, Shotgun ammo, Revolver ammo, Salt, Garlic, Battery, Faith, Bible Page |
| `20–26` | Enemy spawns: Aswang, Manananggal, Tikbalang, Kapre, White Lady, Multo, Sigbin |
| `30` | Player Start |
| `31` | Checkpoint |
| `32` | Level Exit |
| `33` | Interactable Object |

---

## Chapters

| Chapter | Map Size | Enemies | Setting |
|---|---|---|---|
| **1 — Dark Forest Trail** | 24 × 24 | Aswang ×2, Multo ×1, Sigbin ×1 | Dense forest, bamboo/balete walls, cabin interior |
| **2 — The Cursed Ruins** | 32 × 16 | Aswang ×2, Manananggal ×1, Multo ×1, Sigbin ×1, Tikbalang ×1 | Complex ruins, tougher encounters |

After Chapter 2, the game returns to the main menu.

---

## Save System

| Action | How |
|---|---|
| **Save** | Pause (`Escape`) → press `S` |
| **Load** | Main Menu → press `L` |

Saves are JSON files in `saves/` and include: position, health/armor, weapons & ammo, flashlight battery, faith energy, sacred items, ward unlocks, journal, relics, chapter, and checkpoint.

---

## Settings

`settings.json` is auto-created on first save. Edit manually or via future settings menu.

| Key Constant | Default | Description |
|---|---|---|
| `SCREEN_WIDTH/HEIGHT` | 1280 × 720 | Output display resolution |
| `INTERNAL_WIDTH/HEIGHT` | 640 × 360 | Raycasting render resolution |
| `FPS` | 60 | Target framerate |
| `FOV` | 60° | Field of view |
| `MAX_DEPTH` | 20 tiles | Max ray distance |
| `PLAYER_SPEED` | 3.0 | Walk speed |
| `PLAYER_SPRINT_SPEED` | 5.0 | Sprint speed |
| `FULLSCREEN` | False | Fullscreen toggle |

---

## Architecture & Modules

| Module | Role |
|---|---|
| `main.py` | Game loop, state machine (MENU/PLAYING/PAUSED/GAMEOVER/WIN), HUD, audio triggers, save/load |
| `player.py` | Movement, collision, stamina, sanity, noise generation, weapons, cancelable reloads, serialization |
| `enemies.py` | AI state machine (Idle/Patrol/Investigate/Chase/Attack), noise perception, proximity sanity drain |
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

## Lore

> *"Huwag lumabas ng gabi. Baka abutin ka ng dilim."*  
> *("Don't go out at night. The darkness might catch you.")*

The forest has always been alive. But tonight, the old warnings mean something more. Ancient spirits, stirred by years of disrespect for the land, now roam freely. You are a lone traveler caught in the cursed woods — armed with your grandfather's bolo, a flickering flashlight, and faith passed down through generations. Survive until dawn.

Collect **Bible pages** scattered throughout the forest. They hold prayers, warnings, and the secrets to unlocking the sacred wards that may be your only salvation.

---

*Ingatan mo ang iyong sarili. Ang gubat ay may ibang batas sa gabi.*  
*("Take care of yourself. The forest has different rules at night.")*
