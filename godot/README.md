# ANINO SA GUBAT — Godot visual frontend

This branch is an incremental renderer migration, **not a rewrite of the game rules**.

## Runtime ownership

- **Python/Pygame is authoritative:** player movement and collision, stamina, health and sanity, weapons, ammunition, reloads, enemy AI and damage, pickups, map progression, objectives, items/wards, weather/gameplay timers, and the existing audio systems.
- **Godot 4 is the visual frontend:** 3D camera, forest geometry, lighting, fog, shadows, enemy/pickup visuals, and the presentation HUD.
- **The original Python project and gameplay modules remain intact.** Godot no longer instantiates the standalone `survival_game.gd` prototype from the active main scene.

The bridge is local-only UDP on loopback:
- Godot input -> Python: `127.0.0.1:4244`
- Python state -> Godot: `127.0.0.1:4243`
- Protocol version: `1`
- Input packets: up to 30 Hz; state snapshots: up to 20 Hz.
- Player and enemy transforms are interpolated on the Godot side. Python remains the source of truth.

## Run the integrated build

The Python simulation and Godot renderer are two separate processes. Start Python first so it can receive the first start-game command.

### 1. Start the Python gameplay process

Open PowerShell in the repository root (the folder containing `main.py`):

```powershell
Set-Location "D:\PhyGame\GODOT"
$env:ANINO_GODOT_BRIDGE = "1"
$env:ANINO_GPU_PRESENT = "0"
python main.py
```

In bridge mode, Pygame uses SDL's dummy video driver so it does not open a second visible game window. Python gameplay and the original Python audio systems continue running. Keep this terminal open.

Use the Python environment that already has the project's Pygame and other dependencies installed. If `python` points to a different interpreter, activate the project's virtual environment first.

### 2. Start Godot

1. Open Godot 4.7.2 (or a compatible Godot 4.x standard build).
2. Import/open `D:\PhyGame\GODOT\godot\project.godot`.
3. Press **F5**.
4. Wait for the HUD to show **PYTHON CONNECTED**.
5. Select **ENTER THE FOREST**. Python starts the original intro/chapter flow; Godot displays the received player, map, and enemy state.

If Godot is started before Python, it will keep waiting for the Python process. Start Python and then run the Godot project again if the initial start command was sent before Python was listening.

## Controls

The Godot window forwards input to the original Python event handlers:

| Input | Original Python action |
|---|---|
| WASD | Move |
| Mouse | Look |
| Shift | Sprint |
| Ctrl | Crouch |
| F | Toggle flashlight |
| Left mouse | Fire current weapon |
| Mouse wheel | Switch weapon |
| R | Reload |
| E | Interact |
| G / H | Salt / garlic |
| V / C | Rosary / cross |
| Q, 2–5, Tab | Original ward controls |
| Esc | Pause / resume |

The exact behavior remains governed by the original Python settings and gameplay code.

## Current implementation boundaries

Implemented:
- Two-way versioned JSON UDP transport on localhost.
- Godot input is converted into Pygame key, mouse-motion, mouse-button, and mouse-wheel events and routed through the existing Python handlers.
- Python sends authoritative player stats/transforms, enemy state, notifications, and nearby map-tree data.
- Godot renders a Python-driven first-person camera, flashlight, forest blockout, enemy blockout visuals, pickup placeholders, and a basic HUD.
- Nearby tree visuals are refreshed periodically; player and enemy transforms are smoothed between snapshots.
- Python's Pygame display is hidden in bridge mode; original Python gameplay/audio remain active.

Still required:
- Validate the bridge on the target Windows PC with the installed Python environment and Godot 4.7.2.
- Improve reliability/acknowledgement for one-shot commands and add connection timeout/reconnect UI.
- Stream all relevant map geometry, terrain, water, doors, shrines, and chapter-specific landmarks instead of only nearby tree blockout geometry.
- Replace procedural blockout visuals with the original art/animation assets and properly rigged 3D models.
- Add visual representations for all original projectiles, ward effects, weather, cinematic events, and jumpscares.
- Tune coordinate mapping, camera pitch, movement interpolation, and latency in a live play test.
- Build and test a distributable launcher that starts the Python simulation and Godot frontend together.

## Migration safety

- Continue on `godot-migration`; do not merge into `main` yet.
- Keep the original `D:\PhyGame\ANINO_SA_GUBAT` working copy untouched.
- `godot/scripts/main.gd` and `godot/scripts/survival_game.gd` are retained as prototype/reference files, but the active scene uses `python_frontend.gd`.
- Do not treat this build as fully parity-complete or runtime-verified until the Windows two-process test has passed.
