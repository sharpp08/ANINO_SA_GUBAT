# GLSL shadow-depth shader pair

This folder contains the first reusable geometry shadow-map shader pair for the
ModernGL / OpenGL 3.3 renderer.

## Files

- `shadow_depth.vert`: transforms caster vertices from model space into light
  clip space and forwards UV coordinates.
- `shadow_depth.frag`: writes depth into the currently bound depth attachment.
  Optional alpha testing preserves transparent gaps in leaf and foliage textures.

## Vertex layout

The vertex shader expects:
- location 0: `vec3` position
- location 1: `vec2` texture coordinate

Configure the VAO to match this layout. Supply `u_model` and
`u_lightSpaceMatrix` for each caster. Bind the caster's diffuse texture to
`u_diffuseTexture`; set `u_useAlphaTest` and `u_alphaThreshold` for foliage.

## Current integration status

These shaders are committed as the shadow-map depth-pass foundation. They are
not yet connected to live gameplay geometry. The current world renderer uses
2D/Pygame billboards for trees, plants, enemies and pickups, plus a GPU wall
raycaster; those objects do not currently provide the 3D vertex buffers and
model transforms this shader requires. The shader pair alone therefore does
not make visible shadows appear in the game.

The next integration stage must submit supported world casters to a depth
framebuffer, then update the scene's receiving shader to sample that depth
texture (with bias and PCF filtering). Tree billboards need alpha-tested
shadow geometry; GPU-native terrain/receiver rendering is also required for
shadows to appear on the ground. Keep the CPU renderer as fallback.

Baseline: GLSL 330 Core. Suggested initial alpha threshold: 0.5. Shadow-map
resolution and PCF kernel should be benchmarked on the target Intel UHD GPU
before enabling by default.
