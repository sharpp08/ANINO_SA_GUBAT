# Performance audit — 2026-11-03

Repository: `sharpp08/ANINO_SA_GUBAT`

## Scope and evidence

This is a source-code audit of the current `main` branch. No executable was run and no hardware benchmark or frame-time trace was available, so the findings below are code-path diagnoses rather than measured millisecond costs.

## Findings

### 1. High-confidence systemic cost: hybrid renderer readback

`shader_renderer.py::ShaderRenderer.render` serializes the Pygame frame to RGB bytes, uploads it to a ModernGL texture, renders a full-screen shader pass, reads the framebuffer back to CPU bytes, and constructs a new Pygame surface with `pygame.image.fromstring`. This forces CPU↔GPU transfers and per-frame allocation. The README and GPU_RENDERING.md correctly describe this as a hybrid renderer, not a GPU-resident pipeline. On integrated graphics, synchronization/readback can erase much of the shader's benefit.

**Recommendation:** keep the software renderer as the baseline; make the shader path opt-in for low/medium presets or bypass it when frame time exceeds budget. The durable fix is a GPU-resident presentation path that avoids readback.

### 2. Frenzy-specific CPU workload: enemy count and AI

Frenzy raises enemy movement speed by 45%, damage by 25%, and shortens attack cooldowns. Survival-mode spawn intervals also shrink with sanity, reaching 55% of normal at zero sanity. This increases the number of active enemy updates and the frequency of collision, animation, distance, and path-following work at exactly the point the game enters Frenzy.

**Recommendation:** enforce a hard active-enemy cap, pause distant/irrelevant AI updates, and use cheaper steering for enemies far from the player. Keep the higher movement speed as a gameplay effect without multiplying expensive work.

### 3. A* pathfinding bursts

Each pursuing enemy recalculates a path on a timer. Previously every enemy started with a zero timer, so enemies entering a pursuing state together could request A* work in the same frame. That creates periodic frame-time spikes even if average CPU usage remains low.

**Change made:** initial path-recalculation timers are now staggered randomly over a three-second window. The existing three-second repath cadence remains intact.

### 4. Tree rendering is bounded, but candidate processing grows with density

The renderer spatially buckets trees and draws only the nearest `MAX_RENDER_TREES` visible billboards. This protects the draw count, but more trees still increase nearby candidate checks and selection work.

**Change made:** the authored map target increased from 5,200 to 6,000 trees in Chapter 1 and from 6,500 to 7,400 in Chapter 2 (+15%). The renderer's existing per-quality billboard cap was intentionally left unchanged, so the increase improves forest fullness without increasing the maximum number of tree billboards drawn per frame.

### 5. CPU raycasting and floor mapping remain the baseline cost

The world is primarily built on the CPU with vectorised NumPy raycasting and floor mapping, followed by Pygame sprite composition, fog, flashlight, weather, and particles. The debug overlay already reports ray timing and sprite counts, but it does not provide a complete per-stage frame-time breakdown.

**Recommendation:** profile raycast, floor, world-sprite, shader, and enemy-update stages separately. Use frame time (milliseconds) and 1% low FPS, not average FPS alone. At 60 FPS the frame budget is 16.67 ms.

## Validation checklist

1. Start a fresh run in both chapters and confirm the forest is visibly denser while trails, clearings, buildings, pickups, and enemy spawn points remain reachable.
2. Compare Low and Medium quality from the same player position and camera direction.
3. Record FPS and frame-time behavior before Frenzy, immediately after Frenzy begins, and at low sanity when spawn intervals are shortest.
4. Repeat with the ModernGL shader path disabled and enabled. A large improvement with it disabled points to transfer/readback overhead.
5. Check for periodic spikes at roughly three-second intervals; the pathfinding stagger should reduce synchronized spikes.
6. Confirm tree collisions and map reachability after the density increase.

## Limitations

No FPS improvement is claimed until the updated build is run on the target laptop. The repository's tracked Windows executable has not been rebuilt by this source-only audit.
