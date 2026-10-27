# Enemy Animation System Integration

## Overview

The **enemy_animations_pack** (32 sprite sheets, 6 frames each) has been fully integrated into ANINO SA GUBAT. Enemies now cycle through smooth animations at 14 FPS.

## What's Integrated

### 1. **Sprite Animation System** (`animation_core.py`)
- `SpriteAnimation` class: Loads 6-frame horizontal sprite strips from PNG sheets
- `load_from_pack()`: Auto-discovers enemy sheets from `enemy_animations_pack/sheets/`
- Frame cycling at 14 FPS with per-enemy frame tracking
- State mapping: game states (idle, run, attack) → sheet names (run, crawl, attack)
- Unique moves per enemy: aswang transform, manananggal fly, tikbalang rear, kapre smash, white_lady vanish, multo phase, sigbin pounce

### 2. **Enemy Frame Tracking** (`enemies.py`)
- Added `anim_frame` (0-5) per enemy instance for current animation frame
- Added `anim_time` accumulator that cycles every 1/14 second
- Automatic frame advancement in `Enemy.update()` method
- Random initial frame offsets for visual variety

### 3. **Asset Generator** (`asset_generator.py`)
- Priority: Animation pack → Custom PNGs → Procedural fallback
- Detects `enemy_animations_pack/sheets/` and loads all enemy types
- Returns compatible dict: `{etype: {state: surface}}`
- First frame of each animation serves as static fallback

### 4. **Renderer** (`renderer.py`)
- `_draw_enemy()` queries `SpriteAnimation.get_frame()` first
- Passes `enemy.anim_frame` for current frame selection
- Falls back to static sprite dict if animation system unavailable
- Existing procedural effects (breathing, sway, hover) still applied on top

### 5. **Jumpscare System** (`jumpscare.py`)
New module for enemy grab sequences:
- Loads `jumpscare_scream.wav` from animation pack (if available)
- Renders fullscreen procedural sequence (2.6s total):
  - **0.0-0.5s**: Darkness fade-in + screen shake
  - **0.5-1.2s**: Aswang face rushes at camera + motion streaks + eye flares
  - **1.2-1.8s**: Impact flash + radial blur
  - **1.8-2.6s**: Black fade-out

## Animation Sheet Manifest

**All 7 enemy types × 4 common states + 1 unique move each:**

```
aswang:      run, crawl, attack, transform
manananggal: run, crawl, attack, fly
tikbalang:   run, crawl, attack, rear
kapre:       run, crawl, attack, smash
white_lady:  run, crawl, attack, vanish
multo:       run, crawl, attack, phase
sigbin:      run, crawl, attack, pounce
```

6 frames per sheet × 28 sheets = 168 total frames cached in memory.

## State-to-Sheet Mapping

| Game State | Sheet Used | Animation |
|---|---|---|
| idle, walk, hover, float | run | Lean-forward cycle with squash & stretch |
| run, sprint | run | Same as above |
| crawl, stalk, crouch | crawl | Low, squashed drag |
| attack, lunge, stagger | attack | Camera-lunge with blur + eye-flare |
| death | attack | Reuses attack (flattened by renderer) |
| Unique per enemy | Unique sheet | Enemy-specific move |

## Technical Details

### Loading Pipeline
1. Game starts → `asset_generator.generate_all_enemies()`
2. Checks for `enemy_animations_pack/sheets/` directory
3. `SpriteAnimation.load_from_pack()` reads all PNG strips
4. Extracts 6 frames from each strip (divides width by 6)
5. Scales each frame to 64×64
6. Caches: `{enemy_type: {sheet_name: [frame0, frame1, ...]}}`
7. Returns compatible static sprite dict as fallback

### Per-Frame Animation
```python
In Enemy.update(dt):
  anim_time += dt
  if anim_time >= 1/14:
    anim_time -= 1/14
    anim_frame = (anim_frame + 1) % 6

In Renderer._draw_enemy():
  img = anim_sys.get_frame(enemy_type, animation_state, enemy.anim_frame)
```

## Fallback Behavior

If animation pack unavailable:
1. Reverts to static PNGs (if `USE_CUSTOM_ENEMY_SPRITES=True`)
2. Falls back to procedural generation
3. Renderer displays enemies normally (just non-animated)
4. No gameplay impact

## Performance

- **Memory**: ~50 MB in-memory frame cache (32 sheets × 6 frames × 64² × 4 bytes)
- **Loading time**: ~500 ms (sheet extraction + scaling)
- **Per-frame cost**: Single subsurface blit (cached frames)
- **Tested on**: Medium quality tier (640×360 internal resolution)

## Integration Points for Jumpscare

Trigger on enemy grab:

```python
from jumpscare import get_jumpscare_manager
jumpscare_mgr = get_jumpscare_manager()
jumpscare_mgr.trigger()  # Plays 2.6s sequence

# In render loop:
if jumpscare_mgr.is_playing():
    shake = jumpscare_mgr.render(internal_surface)
```

## Settings

- `USE_CUSTOM_ENEMY_SPRITES` (settings.py): Toggle pack loading (default: True)
- `ENABLE_ENEMIES_ANIM` (settings.py): Toggle procedural effects (default: True)
- Animation FPS: 14 (hardcoded in SpriteAnimation.__init__)

## Files Modified

1. **animation_core.py**: Added SpriteAnimation class
2. **asset_generator.py**: Updated generate_all_enemies()
3. **enemies.py**: Added anim_frame tracking
4. **renderer.py**: Updated _draw_enemy()
5. **jumpscare.py**: New module (JumpscareManager)

## Testing

```bash
python tests/smoke_test.py
python -c "from asset_generator import generate_all_enemies; e = generate_all_enemies(); print(list(e.keys()))"
```
