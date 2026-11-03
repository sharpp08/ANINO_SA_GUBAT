# GPU rendering migration

## Current status

The project currently uses a **hybrid renderer**, not a fully GPU-rendered world:

- `renderer.py` composes the scene on the CPU.
- `raycast_fast.py` performs vectorized NumPy DDA wall raycasting.
- `floor_fast.py` performs vectorized CPU floor mapping.
- `gl_present.py` can upload the completed CPU frame and present/upscale it with an OpenGL shader.
- `shader_renderer.py` contains an older offscreen post-process path that reads the processed framebuffer back into a Pygame surface.

The GPU migration below is a roadmap. It is **not implemented yet** and must not be described as complete until the world, sprites, and final presentation are actually rendered on the GPU.

## Target architecture

Keep Python/Pygame as the game runtime and use OpenGL 3.3 core / ModernGL with GLSL 330 for scene rendering.

**Keep in Python:** player movement, enemy AI, collision and physics, objectives, weapons and gameplay state, animation selection, audio, save/settings handling, and game rules.

**Move to the GPU incrementally:** wall raycasting and depth, floor/ceiling and terrain sampling, texture sampling, flashlight and dynamic lighting, depth fog and atmosphere, billboard sprites, particles/weather, and compatible weapon/HUD presentation.

## Compatibility requirements

- Do not migrate the project to Godot or Unity.
- Preserve existing maps, assets, save/settings formats, and gameplay behavior.
- Keep an automatic software-renderer fallback for unsupported or unstable graphics drivers.
- Use OpenGL 3.3 core / GLSL 330 as the baseline; do not require compute shaders or newer APIs.
- Avoid GPU-to-CPU framebuffer readback in the normal GPU path.
- Preserve the current restrained flashlight brightness and dark flashlight-off atmosphere.
- Do not claim FPS gains until measured on the target Intel UHD laptop against the same scene, resolution, and quality settings.

## Implementation sequence

### 1. Baseline and renderer contract

Document the current render entry points, map/grid encoding, wall texture IDs, terrain data, camera projection, sprite depth rules, and post-process inputs. Add a repeatable benchmark scene and deterministic renderer tests. Keep the CPU renderer as the reference implementation.

**Acceptance:** existing gameplay and renderer tests pass; the benchmark reports frame-time statistics and which renderer path is active.

### 2. GPU wall raycasting and depth

Upload the map as a GPU texture. Implement per-column DDA in a GLSL 330 fragment shader and sample wall textures from an atlas. Produce depth data for later sprite occlusion. Match the existing FOV, wall hit-side shading, texture coordinates, distance fog, and clipping. Keep a feature flag and CPU fallback until image comparisons pass.

**Acceptance:** GPU output matches reference scenes within a documented pixel tolerance; doors, walls, boundaries, texture orientation, and occlusion are correct.

### 3. GPU floor and ceiling

Move perspective floor/ceiling mapping to GLSL using camera position, direction, pitch, and terrain textures. Preserve terrain variation, horizon alignment, mist, and the current dark ambient balance. Use texture atlases or texture arrays compatible with GL 3.3.

**Acceptance:** no floor holes, seams, texture shifts, or horizon changes across supported resolutions.

### 4. GPU lighting and atmosphere

Port depth-aware flashlight falloff, ambient light, fog, mist, and supported dynamic lights into shader passes. Preserve flashlight intensity; do not brighten the scene to hide rendering differences. Add shadows only where the scene representation supports stable results.

**Acceptance:** flashlight beam and flashlight-off visibility remain balanced; depth fog is visually compared against the reference renderer.

### 5. GPU sprites and world objects

Render enemies, pickups, trees, and other billboards as GPU batches/instanced quads where practical. Sample the GPU wall depth for occlusion. Keep animation selection, facing, hitboxes, and gameplay collision in Python.

**Acceptance:** sprite ordering and wall occlusion match the current renderer; AI, collision, and hit detection are unchanged.

### 6. GPU effects and final presentation

Move particles, weather, weapon presentation, and compatible HUD/effects to GPU batches incrementally. Keep simpler UI in Pygame until a validated replacement exists. Keep the final frame in GPU framebuffers through presentation and eliminate avoidable readbacks and redundant uploads.

**Acceptance:** normal GPU mode has no per-frame framebuffer readback; software fallback remains usable.

### 7. Benchmark and rollout

Benchmark repeatable scenes at the same resolution and quality settings. Report average FPS and frame-time percentiles, and record CPU/GPU path selection. Make GPU world rendering the default only if it is visually correct and stable on the Intel UHD driver. Retain an override to force the CPU renderer.

**Acceptance:** automated tests and a manual gameplay smoke test pass; performance results are documented. If GPU rendering is slower or unstable on Intel UHD, keep the CPU path as default.

## Install and verify the existing optional GPU path

Install dependencies from the project directory:

```powershell
python -m pip install -r requirements.txt
```

The current optional shader initialization message is:

```text
[SHADERS] ModernGL GPU Shaders initialized successfully.
```

This message only confirms the existing shader/post-processing path, not GPU world rendering. If ModernGL cannot create a usable context, the game should continue through its software fallback.

## Rollout rule

Implement, test, and commit each stage separately. A roadmap/documentation commit is not an implementation commit. Do not label the game fully GPU-rendered until the scene, sprites, and presentation are all GPU-rendered without a per-frame framebuffer readback.
