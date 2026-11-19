# ANINO SA GUBAT — Godot Visual Frontend

This folder contains the initial Godot 4.x foundation for the full 3D first-person visual migration.

## Current status

- Godot 4 project scaffold and main scene
- Procedural forest blockout for scene and scale testing
- First-person camera and temporary prototype movement
- Flashlight and dark atmospheric environment
- UDP bridge endpoint contract using localhost ports 4243 and 4244

This is a visual prototype, not yet connected to live Python gameplay. The temporary Godot movement controller exists only to validate the 3D scene. Do not remove or bypass the Python Player, EnemyManager, GameMap, combat, inventory, survival, or chapter systems.

## Open the prototype

Open the godot folder in Godot 4.x and run scenes/main.tscn.

Prototype controls:
- WASD: move
- Mouse: look
- Shift: sprint
- Ctrl: crouch
- F: flashlight
- Esc: release mouse; click the viewport to recapture

## Python bridge contract

The bridge uses UDP on loopback only:
- Godot listens on 127.0.0.1:4243 for Python state packets.
- Godot sends input packets to 127.0.0.1:4244.
- JSON datagrams are intended for compact state snapshots, not assets.

Planned Python-to-Godot packet fields:
- type: world_state
- sequence: monotonically increasing packet number
- player: x, y, yaw, pitch
- enemies: compact enemy state list
- events: transient visual events

Planned Godot-to-Python packet fields:
- type: godot_input
- timestamp_usec
- move: two-dimensional movement vector
- sprint and crouch booleans
- flashlight_toggle edge event

The Python adapter is intentionally not wired into main.py in this initial scaffold. The next integration phase must add a non-blocking socket adapter to the existing Pygame loop, define authoritative ownership of player movement/input, and add synchronization tests before switching rendering.

## Migration safety rules

1. Keep all work on godot-migration until the prototype and bridge are tested.
2. Keep the existing Pygame renderer as a fallback during migration.
3. Python remains authoritative for gameplay rules, AI, combat, inventory, sanity, stamina, items, and progression.
4. Godot owns the 3D scene, camera presentation, models, materials, lighting, shadows, fog, animation presentation, and visual UI.
5. Never send large textures, meshes, or audio buffers over the state bridge; load assets locally in Godot.
6. Do not merge this branch into main until the complete game can launch and pass gameplay regression tests.
