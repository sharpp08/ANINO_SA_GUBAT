# GPU compositor migration status

## Implemented foundation

- `GLPresenter` owns the existing OpenGL context and a persistent scene color/depth framebuffer.
- `GLPresenter.begin_scene(surface)` binds and clears the shared scene framebuffer for future native GPU passes.
- `GLPresenter.present(..., scene_is_gpu=True)` can present the framebuffer's color texture without uploading a CPU scene image. The default remains the compatibility path.
- The compositor accepts a separate transparent Pygame overlay texture and blends it after scene post-processing, keeping HUD/viewmodel elements crisp.
- The overlay texture preserves its alpha channel. Scene and overlay textures are reused and recreated only when dimensions or pixel layout change.
- The renderer retains its original Pygame world surface. The first-person viewmodel and crosshair are rendered to a separate transparent layer; gameplay HUD, radar, notifications, pause UI, and jumpscare output are routed to that layer.
- The software fallback composites the overlay onto the existing internal surface and continues to use the legacy Pygame renderer.

## Important migration boundary

This is the compositor and layer-separation foundation, not yet a fully GPU-rendered world. At present, the legacy Pygame renderer still produces the world color image and uploads it to the GPU scene color texture each frame. The new `scene_is_gpu` path is available for native passes, but the main game loop must not enable it until those passes actually render into `begin_scene()`.

The experimental GPU wall raycaster remains separate from the shared scene framebuffer and retains its legacy readback integration. Keep `gpu_world_rendering` disabled until the wall pass is migrated to the shared color/depth attachments and its readback is removed.

## Next native rendering stages

1. Port floor/terrain reconstruction to a GLSL pass writing directly into the shared scene framebuffer.
2. Port wall DDA and texture sampling into the same framebuffer, sharing its depth attachment with terrain.
3. Port tree/vegetation billboards or instanced geometry with alpha testing and depth writes for visible foliage only.
4. Port enemies and pickups as depth-aware GPU billboards.
5. Add depth-aware fog, lighting, shadow maps, and GPU particles after unified depth is validated.
6. Keep the CPU renderer as a selectable fallback until visual parity and stability are demonstrated.

## Frame contract

Update gameplay once, construct one immutable camera/world snapshot, render the GPU scene from that snapshot, draw the Pygame overlay from the same snapshot, upload only the overlay in native-GPU mode, composite, and present. Keep all GL calls on the presenter's owning thread/context. Avoid framebuffer readbacks and blocking synchronization in the normal frame path.

## Validation

The headless helper tests in `tests/test_gl_present.py` cover pixel swizzles, overlay alpha mapping, letterboxing, mouse mapping, and the GLSL 3.3 shader contract. Runtime validation is still required on the target Intel UHD system: verify weapon/HUD alpha, lightning flashes, resizing, fallback, frame pacing, and absence of GPU readback in native-scene mode.
