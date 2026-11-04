# Live GPU tree-shadow occlusion

The opt-in ModernGL wall raycaster uploads a coarse tree-occupancy texture
alongside the integer map. Its GLSL fragment shader traces visibility toward
directional moonlight and back toward the player-mounted flashlight. Wall cells
and tree cells can block either light. Three lateral taps soften silhouettes;
moonlight fades with the sunrise value, and flashlight shadows use the live
player direction, battery state, and range.

## Coverage and limits

- GPU raycast wall surfaces receive tree-occlusion shadows from moonlight and
  the player's flashlight.
- Ground shadows remain the existing CPU-projected tree shadows.
- Trees, plants, enemies and pickups remain Pygame billboards, not GPU
  depth-map casters or receivers. The generic depth shader pair is still not
  connected to those objects. This is not full scene-wide shadow mapping.
- The GPU wall pass remains opt-in and automatically falls back to CPU walls
  when the ModernGL pass fails.

The tree occupancy field uses map-cell resolution. It approximates trunks and
canopies; it is not yet alpha-tested foliage geometry or per-pixel tree depth.
