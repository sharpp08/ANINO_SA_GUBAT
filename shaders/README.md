# Live GPU tree-shadow occlusion

The opt-in ModernGL wall raycaster now uploads a coarse tree-occupancy texture
alongside the integer map. Its wall fragment shader samples both textures while
tracing directional light visibility, so tree positions can occlude moonlight
on GPU-rendered wall faces. Three offset visibility taps soften the shadow
edge. The CPU renderer continues to draw projected tree shadows on the ground.

## Coverage and limits

- GPU wall pixels: wall-grid and tree-cell occlusion for the existing directional
  moonlight shader.
- Ground: existing CPU-projected moonlight and flashlight tree shadows.
- Trees, plants, enemies and pickups: still Pygame billboards, not GPU depth-map
  casters or receivers. The depth shader files are not yet connected to those
  objects. This is not full scene-wide shadow mapping.
- The GPU wall pass remains opt-in and automatically falls back to CPU walls
  when the ModernGL pass fails.

The tree occupancy field uses map-cell resolution and is an approximation of
tree trunks/canopies, not alpha-tested foliage silhouettes.
