# GPU wall raycasting — Stage 1

## What this stage adds

- `gpu_wall_raycast.py`: an opt-in ModernGL 3.3 pass that uploads the existing
  integer tile grid, runs DDA per output fragment, samples the game's five wall
  texture types from a texture array, and writes both wall color and normalized
  depth to GPU attachments.
- `tests/test_gpu_wall_raycast.py`: headless shader/interface and tile mapping
  contract checks.

## Current rollout status

This is the first GPU world-rendering pass, but it is **not yet the default game
renderer**. The existing scene is composed in Pygame: floor, walls, sprites,
flashlight overlays, weather, weapon and HUD. Replacing only the wall draw call
would break sprite occlusion and render order. The GPU pass therefore exposes
color/depth textures without reading them back; the next integration step is a
GPU scene compositor that can combine these attachments with GPU sprite batches
and preserve the current Python z-buffer behavior during migration.

## API sketch

```python
wall_pass = GPUWallRaycaster(ctx, width, height)
wall_pass.upload_wall_textures(renderer.textures)
color_tex, depth_tex = wall_pass.render(
    np.asarray(game_map.grid, dtype=np.uint32),
    game_map.grid_rev,
    (player.x, player.y),
    player.angle,
    math.radians(FOV),
    WALL_HEIGHT_SCALE,
    tile_size=TILE_SIZE,
    pitch_offset=int(player.pitch * INTERNAL_HEIGHT),
)
# Bind color_tex/depth_tex in a later GPU composition pass.
```

The context is caller-owned. Call `wall_pass.close()` before destroying it.
Map uploads are cached by grid identity, revision and dimensions. Texture-array
layers are built once per wall-texture set.

## Known limits in Stage 1

- No GPU scene compositor or game-loop activation yet.
- No GPU floor/ceiling, sprite batching, flashlight lighting, or shadow mapping.
- Texture array uses a common square resolution; the CPU renderer remains the
  visual reference and automatic fallback.
- The CPU renderer remains active until GPU color/depth can be composited with
  sprites without per-frame GPU-to-CPU readback.
- Run the shader contract tests on any machine; compile/render validation still
  requires a working OpenGL 3.3 context and should be performed on the target
  Intel UHD laptop before enabling this pass in gameplay.
