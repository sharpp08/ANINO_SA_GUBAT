# ANINO SA GUBAT: Update & Compatibility Guide

This guide provides complete instructions for updating the game executable (`ANINO_SA_GUBAT.exe`), patching existing files, verifying file integrity, and managing Python dependencies.

---

## 1. Quick Update Command

To update everything to the latest game version (verify files, update dependencies, rebuild the `.exe`, and update the integrity manifest):

```powershell
python tools/update_game.py update
```

---

## 2. Detailed Tool Operations

The update and compatibility management tool is located at `tools/update_game.py`. Below are all available commands:

### A. Check Status
Inspect the current build version, file integrity status, and executable timestamp:
```powershell
python tools/update_game.py status
```

### B. Verify File Integrity
Check all tracked source and asset files against cryptographic SHA-256 hashes stored in `manifest.json`:
```powershell
python tools/update_game.py verify
```

### C. Apply a Patch File (`.patch`)
If you receive a unified diff patch file (e.g. from the `Patch file/` directory), apply it cleanly without requiring `git` or external patching tools:
```powershell
# Dry-run simulation (does not modify files)
python tools/update_game.py patch Patch_file/arrow_and_compact_hud.patch --dry-run

# Apply patch
python tools/update_game.py patch Patch_file/arrow_and_compact_hud.patch
```

### D. Create Backup Archive
Archive all source code, assets, and configs (excluding temporary caches and build artifacts) into a timestamped zip in the `release/` folder:
```powershell
python tools/update_game.py backup
```

### E. Manage Dependencies
Ensure all required Python packages (`pygame-ce`, `numpy`, `moderngl`, `glcontext`) are installed and up to date:
```powershell
python tools/update_game.py deps
```

### F. Migrate Settings
Ensure user preferences in `settings.json` are fully compatible with the latest game version (adds any new configuration keys with safe defaults):
```powershell
python tools/update_game.py migrate-settings
```

### G. Rebuild Executable (`.exe`)
Rebuild the standalone Windows executable using PyInstaller (`ANINO_SA_GUBAT.spec`):
```powershell
python tools/update_game.py build
```
The resulting updated executable will be placed at:
`dist/ANINO_SA_GUBAT.exe`

---

## 3. Dependency & Configuration Management

- **Python Environment**: The game requires Python 3.12+ and runs within the project's virtual environment (`.venv`).
- **Dependencies**: Listed in `requirements.txt`. Updated automatically via `python tools/update_game.py deps`.
- **Game Saves & Settings**: Saved locally as JSON files (`settings.json` in root, save slots in `saves/`). No Windows registry entries are created or modified by the game or update scripts.

---

## 4. Running Unit Tests

To validate the update system components (manifest verification and patcher):
```powershell
python tests/test_update_system.py
```
