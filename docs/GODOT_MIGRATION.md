# Godot 4.x Full 3D First-Person Migration

## Goal

Move visual rendering from the existing Pygame raycasting renderer to Godot 4.x while retaining Python as the authoritative gameplay backend.

## Existing Python systems to preserve

- Player: health, stamina, sanity, noise, weapons, ammo, reloads, wards, inventory and progression
- EnemyManager and enemy state machines: AI, perception, attacks, vulnerabilities and damage
- GameMap: map data, collision queries, pickups, checkpoints, doors and chapter flow
- Existing audio synthesis, spatial enemy audio, music, events and settings unless a separately tested replacement is approved

## Ownership model

| Concern | Authority |
|---|---|
| Game rules, stats, combat outcomes, enemy AI, inventory, chapters | Python |
| 3D world, camera rendering, lighting, fog, shadows, materials, animation presentation | Godot |
| Input capture and translation | Godot captures; Python adapter translates into existing gameplay actions |
| Position/state | Python authoritative; Godot interpolates presentation snapshots |
| HUD and menus | Godot presentation driven by Python state |

Avoid two independent player controllers after integration. The current Godot controller is only a visual prototype and must be replaced with a presentation controller driven by Python snapshots and translated input.

## Bridge

Initial local-only UDP contract:
- Godot binds 127.0.0.1:4243 and receives compact JSON world snapshots from Python.
- Godot sends compact input JSON to Python at 127.0.0.1:4244.
- Target 30–60 state updates per second, with sequence numbers and timestamps.
- No blocking socket operations in either frame loop.
- Validate packet type, schema, bounds and stale sequence numbers.
- Add interpolation/extrapolation limits and a safe timeout/fallback.
- UDP is suitable for frequent snapshots; reliable one-off commands should use an acknowledged message channel or a TCP control channel.

## Phases and exit criteria

1. Godot visual blockout — project opens, first-person camera works, forest blockout renders, flashlight and collision work.
2. Bridge adapter — Python non-blocking networking is integrated without changing game rules; protocol tests cover malformed, stale, missing and burst packets.
3. Player synchronization — movement, yaw/pitch, crouch and sprint have one authoritative simulation; no double movement or duplicate input.
4. World and collision — translate map geometry and traversable areas; validate spawn, doors, pickups, boundaries and chapter transitions.
5. Enemy presentation — all seven folklore enemy types receive 3D presentation while Python retains AI and combat authority.
6. Items, weapons and effects — weapons, reloads, sacred wards, pickups, projectiles and hit feedback are driven by Python events/state.
7. HUD, menus and audio — reproduce all current UI states and preserve existing audio behavior unless replacements are explicitly tested.
8. Regression and packaging — run Python tests, protocol tests, chapter playthrough checks, performance profiling and Windows packaging.

## Performance target

The target is a stable 60 FPS on the project's documented Intel UHD laptop class where practical. Use conservative real-time shadow distance, occlusion culling, LODs, instancing or MultiMesh foliage, baked/static lighting where appropriate, and scalable fog/post-processing. Do not assume the prototype forest is final art or final performance.

## Safety

- All changes stay on godot-migration until reviewed.
- Do not delete existing Python modules, assets, audio, tests, build specs, or the current executable.
- Do not change main or merge without explicit approval.
- Keep a working Pygame fallback until Godot parity and regression tests are demonstrated.
