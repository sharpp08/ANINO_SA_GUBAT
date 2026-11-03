# GPU wall raycasting — Stage 1

## What this stage adds

- `gpu_wall_raycast.py`: an opt-in ModernGL 3.3 pass that uploads the existing
  integer tile grid, runs DDA per output fragment, samples the game's five wall
  texture types from a texture array, and writes both wall color and normalized
  depth to GPU attachments.
- `tests/test_gpu_wall_raycast.py`: headless shader/interface and tile mapping
  contract checks.

## Current rollout status

The pass is now connected to the live gameplay render sequence as an **opt-in migration bridge**.
When enabled, GLSL draws the wall pixels between the CPU floor and the existing Python sprite pass.
The CPU raycaster still builds the authoritative z-buffer so current sprite occlusion, trees,
enemies, pickups, fog and gameplay behavior remain unchanged. The GPU wall color attachment is
read back into a reusable Pygame surface for this first integration; this is a transitional bridge,
not the final no-readback architecture and may be slower than the CPU renderer. It is disabled by
default until shader output and performance are validated on the target Intel UHD system.

Enable for a local test with PowerShell:

```powershell
$env:ANINO_GPU_WALLS = "1"
python -B main.py
```

Set it to `0` to force CPU walls. The GPU pass requires the OpenGL presenter to have created a
working ModernGL context. If initialization or a frame fails, the renderer immediately returns
to CPU wall drawing.

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

- The opt-in live wall bridge uses GPU-to-CPU color readback; a GPU-native scene compositor and GPU sprite/depth composition are still required.
- No GPU floor/ceiling, sprite batching, flashlight lighting, or shadow mapping.
- Texture array uses a common square resolution; the CPU renderer remains the
  visual reference and automatic fallback.
- The CPU raycaster remains active for the Python sprite z-buffer. The GPU wall pass replaces the wall pixels only when explicitly enabled; its color readback is temporary migration scaffolding.
- Run the shader contract tests on any machine; compile/render validation still
  requires a working OpenGL 3.3 context and should be performed on the target
  Intel UHD laptop before enabling this pass in gameplay.
