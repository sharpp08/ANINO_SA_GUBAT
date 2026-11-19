# ANINO SA GUBAT — Godot 4.x standalone migration

This project is being ported from Python/Pygame to a standalone Godot 4.x first-person survival game. The original Python project remains unchanged and is retained as the reference implementation.

## Implemented in this migration build

- First-person controller: mouse look, WASD movement, sprint/stamina, crouch, flashlight
- Procedural forest blockout, ground collision, moonlight, fog, shadows
- Seven folklore enemy archetypes: Aswang, Kapre, Manananggal, White Lady, Sigbin, Tikbalang, and Multo
- Basic enemy pursuit and melee damage
- Two selectable firearms (service pistol and hunting shotgun), ammunition, hitscan firing, reload timers
- Salt ward placement with temporary enemy damage
- Pickups for torn pages, ammunition, first aid, and herbal sanity tonics
- Health and sanity meters, frenzy state, page collection objective, win/death feedback
- Main menu, pause/resume, and return-to-menu flow
- Original rain/frenzy ambience and firearm/reload sound hooks (after asset import)

These are first-pass Godot implementations and procedural placeholders. They are not yet exact feature parity with the original Python systems or final art/animation quality.

## Import the original audio and sprite assets

The Godot project folder is nested under the repository root, while the original assets live in the repository's top-level `assets` folder. Copy them into the Godot resource root before opening the project:

Open PowerShell and run:

```powershell
powershell -ExecutionPolicy Bypass -File "D:\PhyGame\GODOT\godot\import_original_assets.ps1"
```

The script copies only `assets/audio` and `assets/sprites` into `godot/assets`; it does not delete or modify the originals. The Godot editor will import the copied files when the project is opened.

## Open and run

1. Install Godot 4.x standard edition (no .NET version required).
2. In Godot Project Manager choose **Import**.
3. Select `D:\PhyGame\GODOT\godot\project.godot`.
4. Open the project and press **F5**.
5. Choose **ENTER THE FOREST**.

## Controls

| Input | Action |
|---|---|
| WASD | Move |
| Mouse | Look |
| Shift | Sprint (uses stamina) |
| Ctrl | Crouch |
| F | Toggle flashlight |
| Left mouse | Fire |
| R | Reload |
| 1 / 2 | Select pistol / shotgun |
| Q | Place salt ward |
| E | Interact with the exit after finding all five pages |
| Esc | Pause / resume |
| Click viewport | Recapture mouse after releasing it |

Walk over the colored pickups to collect them. Recover all five torn pages, then press E to complete the current prototype objective.

## Still required for full original-game parity

- Port the complete original chapter/map layouts and progression, rather than the current procedural forest test area
- Replace placeholder enemy geometry with the original enemy sprite/model assets and animation sets; implement their distinct attack, movement, hit reaction, and spawn logic
- Implement the complete original weapon roster, melee/throwable weapons, ammo economy, and weapon viewmodels
- Port the full inventory and all sacred items (garlic, rosary, cross, salt, etc.)
- Rebuild the original cinematic, lore, chapter objectives, radar, compass, jumpscares, and complete settings/options screens
- Connect all original ambience, footsteps, heartbeat, breathing, thunder, enemy vocalizations, and cinematic audio
- Add save/load, difficulty, accessibility, rebinding, resolution/fullscreen options, and automated gameplay regression tests

## Migration safety

- Continue working on `godot-migration`; do not merge into `main` yet.
- Keep `D:\PhyGame\ANINO_SA_GUBAT` untouched.
- Python files are source references, not executable Godot gameplay. Their behavior must be ported to GDScript or native Godot systems.
- Run the project in the installed Godot version and check the first error in the Debugger before treating a commit as runtime-verified.
