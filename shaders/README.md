# GPU tree occlusion shadows

The opt-in ModernGL wall raycaster uploads a coarse tree-occupancy texture
alongside the integer map. The GLSL fragment shader samples both textures
while tracing directional moonlight visibility. Tree cells can therefore
occlude moonlight on GPU-rendered wall faces, with three offset taps to soften
the shadow edge.

## Coverage and limits

- GPU wall surfaces: directional moonlight shadowing from map walls and tree
  occupancy cells.
- Ground: existing CPU-projected tree shadows respond to both moonlight and
  the player's flashlight.
- Trees, plants, enemies and pickups remain Pygame billboards, not GPU
  depth-map casters or receivers. The generic depth shader pair is not yet
  connected to those objects. This is not full scene-wide shadow mapping.
- The GPU wall pass remains opt-in and automatically falls back to CPU walls
  when the ModernGL pass fails.

The tree occupancy field uses map-cell resolution. It approximates tree
trunks/canopies; it is not alpha-tested foliage geometry.
