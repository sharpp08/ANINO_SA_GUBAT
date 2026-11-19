# ANINO SA GUBAT — Godot 4.x standalone prototype

This folder contains a runnable Godot 4.x first-person forest prototype. The original Python/Pygame project remains unchanged in the repository root.

## What currently runs in Godot

- Procedurally generated 3D forest blockout with ground collision, trunks, and canopy meshes
- First-person camera and collision body
- WASD movement, sprint with stamina drain/recovery, crouching with capsule resizing
- Toggleable flashlight (F)
- Dark forest sky, ambient lighting, directional moonlight, fog, and shadows
- Main menu, start button, quit button, stamina HUD, and pause/resume/main-menu flow
- Compatibility renderer selected for broad hardware support

## Open and run

1. Install **Godot 4.x** (standard build; no .NET version required).
2. In Godot Project Manager choose **Import**.
3. Select this file: `godot/project.godot` (not the repository-root README or Python project).
4. Open the project and press **F6** only if you want to run the current scene; use **F5** to run the project.
5. Select **ENTER THE FOREST** to begin.

If Godot reports a parse or resource error, open the **Debugger** panel and inspect the first error. The project should be tested in the installed Godot 4.x version before packaging.

## Controls

- WASD — move
- Mouse — look
- Shift — sprint (uses stamina)
- Ctrl — crouch
- F — toggle flashlight
- Esc — pause / release mouse; click the viewport to recapture mouse

## Important migration status

This is **not yet a complete Godot port of the original game**. The original Python README describes procedural assets and systems implemented in Python modules. Python source files cannot simply be copied into a Godot project and executed as GDScript.

Not yet ported into this standalone Godot build:
- Original title cinematic, chapters, map/tile data, pickups, and progression
- Original weapons, ammunition, reloads, sacred wards, salt/garlic/rosary/cross items
- All seven enemy types and their AI/combat behavior
- Sanity/frenzy, inventory, objective progression, save/settings, and original audio systems
- Original HUD, radar, compass, jumpscares, and full menu/settings flow

The initial Godot UDP bridge was only a contract prototype; it is not enabled as a required dependency for this standalone scene. Do not launch Python expecting the Godot build to automatically receive its gameplay state.

## Migration safety

- Keep all work on `godot-migration` until the Godot build has feature parity and regression tests.
- Keep the original Python/Pygame game as the authoritative reference during porting.
- Reuse compatible original assets when they exist; the original README describes most visuals/audio as generated procedurally at runtime, so those generators and gameplay systems must be ported or replaced deliberately.
- Do not merge this branch into `main` until the Godot version is independently playable and tested.
