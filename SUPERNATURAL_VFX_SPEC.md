# ANINO SA GUBAT — Supernatural VFX Technical Specification

Cohesive supernatural aesthetic for the three ward/ritual effects: **Salt Circle** (G),
**Garlic Toss** (H), and **Cross Manifestation** (C). This spec is normative for the
current pseudo-3D raycaster pipeline and maps every requirement to the code that
implements it, so spec and engine cannot drift apart.

## 0. Design Pillars (apply to all three effects)

| Pillar | Rule |
|---|---|
| Palette discipline | Salt = spectral blue-silver; Garlic = earthy ivory/pungent green; Cross = sacred gold. Each effect owns ONE hue family; neutrals are tinted, never pure white/black. |
| Glow after darkness | All supernatural light is drawn **after** the darkness/flashlight pass so wards stay visible in the dark (the `_emissive` pass, `renderer.py:_draw_emissive`). |
| Unlit, additive treatment | Effect surfaces are treated as *unlit emissive* — they ignore scene lighting (the renderer has no per-pixel lit shading for sprites), so "shader" work happens as cached SRCALPHA / `BLEND_RGB_ADD` surfaces, never per-frame allocations. |
| Easing grammar | *Manifest* (coming into being): easeOut* pop with overshoot allowed. *Sustain*: 1.5 Hz sine breathing. *Dissipate*: linear alpha over the final 0.5 s. |
| Fail-safe | Every VFX path is wrapped so a glitching effect can never crash a frame (zone pass, toss draw, ward branch). |
| Audio pairing | Every effect has a paired synthetic cue (`audio_synth.py`): salt_pour, garlic_throw / garlic_impact, ward_bless. |

---

## 1. Salt Circle (ground-based ritual effect)

**Purpose:** a consecrated ground ward (radius 2.0 tiles, 8.0 s life) that slows and
repels aswang/multo/white-lady/sigbin. Zone state lives in
`EnemyManager.active_effects` (`enemies.py:add_salt_zone`) and is drawn by the
zone pass (`zone_fx.py:ZoneFX`, called from `renderer.render_frame` step 5a).

### 1.1 Visual properties

| Property | Specification | Where |
|---|---|---|
| Ground decal | Perspective-squished ellipse, `h = w × 0.32` (same squish as shadow/pickup decals). Ring color `(220,240,255)`; inner speckle ring at 82 % radius in dimmed color `(154,168,179)` when `unit > 0.35` reads as scattered grains up close. | `zone_fx.py:draw` |
| Grain texture | No texture asset: grain is *procedural* — outer solid ring + inner faint ring + inner speckle; salt granules are conveyed by the particle motes, not a tile texture. | `zone_fx.py` |
| Emissive ring | Cached SRCALPHA elliptical glow, `renderer._zone_ring()` (LRU, 64 entries; radius quantized //8, alpha //16). Glow color `(90,100,125)` (= `PICKUP_GLOW['salt']`). | `renderer.py:_zone_ring/_draw_emissive` |
| Shimmer | Breathing radius pulse: `r ×(1 + 0.05·sin(t·3 + seed))`, seed = `7x + 13y` so neighboring circles don't sync. | `zone_fx.py:draw` |
| Particles (motes) | Screen-space `ParticleSystem(400)` (`animation_core.py`): 2 motes / 0.35 s per visible zone; `vy = −(8..22)` px/s, `vx = ±7`, life 0.8 s, size 1 px, color `(210,230,255)`, `gravity_scale = 0.0`, `drag_scale = 0.9` (drift up, never fall). | `zone_fx.py:draw` |
| Particles (burst) | One formation crackle on zone spawn: `burst(24, speed 30–110, life 0.9, size 2, up_bias 30, gravity_scale 1.2)` at screen (w/2, 0.72h). | `zone_fx.py:on_zone_appeared` |

### 1.2 Animation sequence (timing & easing)

| Phase | Time | Behavior | Easing / curve |
|---|---|---|---|
| **Deposition** | 0.0 → 0.5 s | Ring radius scales 0 → full; formation burst fires on frame 0; `salt_pour` SFX (granule crackle, 0.45 s). | `easeOutQuad(t) = 1 − (1−t)²` |
| **Glow buildup** | 0.0 → 0.5 s | Emissive alpha rises with the same envelope: `α = 190 · scale · fade`. | same `easeOutQuad` |
| **Sustained ward** | 0.5 → 7.5 s | Full-alpha ring, 1.5 Hz breathing pulse, mote emission every 0.35 s; enemies in zone take the `apply_salt()` slow/repel. | `sin(t·3)` |
| **Dissipation** | 7.5 → 8.0 s | Ring alpha ramps linearly to 0 (grain "scatters" — the shrinking emissive ring reads as the salt going inert). Zone dict is popped by `EnemyManager.update`. | linear fade, `α · (timer/0.5)` |

Known geometric note: a circle placed **under** the camera projects below the screen
bottom (correct for a ring surrounding you — you see it as you step into it). This is
documented and asserted in `tests/test_vfx_zones.py`.

---

## 2. Garlic (projectile mechanic)

**Purpose:** a thrown pungent ward. The zone (radius 2.5 tiles, 6.0 s) forms where the
bulb **lands** — ~4.5 tiles ahead of the thrower — not under the player
(`garlic_toss.py`, wired in `main.py:_use_garlic` / `update_playing`).

### 2.1 Aesthetics

| Property | Specification | Where |
|---|---|---|
| Sprite style | Procedural pixel sprite (32×32, `asset_generator.py:generate_pickup_sprite` 'garlic'): ivory bulb `(230,220,200)` with darker clove shading `(210,200,180)`, vertical septum line `(180,170,150)`, sage-green stem arc `(100,140,60)`. Stylized, not realistic — matches the game's pixel-art pickup family. | `asset_generator.py` |
| In-flight scale | Depth-scaled exactly like pickups: `sw = unit × 0.32` (`_unit_h` from `renderer.py`), lifted `z·unit` px above the floor contact point. | `garlic_toss.py:_draw_flight` |
| Tumble | 720°/s rotation faked by **mirroring** the bulb each half-spin (cached `pygame.transform.flip`, 64-entry LRU) — avoids per-frame `transform.rot` cost. | `garlic_toss.py:_flip_h` |
| Glow | Earthy warm aura `(120,110,80)` (= `PICKUP_GLOW['garlic']`): flight uses the vapor trail below; the landed zone uses the emissive ring pass with these colors. | `zone_fx.py:ZONE_STYLE` |

### 2.2 Toss mechanic (animation & physics)

Three phases in `garlic_toss.GarlicToss`; `update(dt)` returns True on the exact
landing frame, which is when `main.py` creates the zone + plays the impact SFX.

| Phase | Duration | Logic | Easing / curve |
|---|---|---|---|
| **charge** | 0.15 s | Viewmodel bulb pops in from the lower-right of the view. | `easeOutBack` (c1 = 1.70158, c3 = 2.70158) |
| **flight** | 0.50 s | World-space parabolic arc. Horizontal: `x = lerp(x0, x1, easeOutCubic(t))` (decelerates into the landing point, no bounce); vertical: pseudo-Z parabola `z(t) = 4·Z_MAX·t(1−t)`, `Z_MAX = 0.45` tiles (peak at t = 0.5, total flight = 0.5 s — no free-fall constant needed because the arc is time-normalized). | `easeOutCubic(t) = 1 − (1−t)³` + parabola |
| **impact** | frame of landing | Zone forms at `(land_x, land_y)`; clove-shatter burst; lingering pungent haze = the zone's emissive ring decaying over its 6 s life; `garlic_impact` SFX (90 Hz thump + vapor puff). | n/a (event) |

**Gravity influence:** deliberately *absent* in the classic sense — the arc is a
time-normalized parabola so impact timing is deterministic regardless of
`settings` quality tier; the `easeOutCubic` horizontal term is what gives the
"heaviness" of the throw.

### 2.3 Impact VFX

| Element | Config | Where |
|---|---|---|
| Clove shatter | `burst(count 24, speed 30–110, life 0.9, size 2, color (190,185,160), up_bias 30, gravity_scale 1.2)` — fragments arc out and settle (ParticleSystem has built-in ground bounce at `ground_y = 350`). | `zone_fx.py:on_zone_appeared` |
| Vapor trail (flight) | 1 mote/frame in flight: `(190,185,160)`, life 0.5 s, size 1, `gravity_scale 0.0`, `drag_scale 0.9`, slight upward drift. | `garlic_toss.py:_draw_flight` |
| Lingering scent cloud | The zone emissive ring at `(120,110,80)` with 1.5 Hz breathing for the full 6 s zone life. | `zone_fx.py` |
| SFX | `garlic_throw` (0.3 s whoosh, shimmer sweep) on charge; `garlic_impact` (thump + puff) on landing. | `audio_synth.py` |


---

## 3. Cross (manifestation / activation effect)

**Purpose:** `main.py:_use_cross` → `apply_cross()` (repel radius 6.0, sanity restore)
+ `renderer.trigger_ward_effect('cross', 1.5)` + screen-shake(2) + `ward_bless` SFX.

### 3.1 Visual design & light interaction

| Property | Specification | Where |
|---|---|---|
| Material | **Ethereal sacred gold, unlit.** No metallic PBR — the renderer is unlit pseudo-3D, so the cross is drawn as a line-art crucifix on the cached full-screen ward scratch surface (`_ward_fx`, SRCALPHA, no per-frame allocation): gold `(255,215,0)` bars with a thin white-hot core `(255,250,220)` over the 360p internal canvas. | `renderer.py:_draw_ward_effect` ('cross' branch) |
| Light interaction | It *is* the light: the effect layer blits over the darkness pass, and the expanding rings double as the "radiance" the player sees. The optional GPU bloom path (`gl_present.py`) already exposes `u_supernatural_intensity` — the guard comment notes the current GLSL doesn't consume it; a future enhancement can route a `supernatural` intensity into that uniform **without touching** the CPU path. | `gl_present.py` (future) |
| Symbol proportions | Vertical bar `sym` px tall (16→38 px via the rise curve), horizontal bar at `0.15·sym` below center, crossbar half-length `0.55·sym`. Stroke widths clamp to ≥2 px at 360p. | 'cross' branch |

### 3.2 Manifestation, pulse & rotation (active-state behavior)

All timing driven by `ward_effect_timer` (1.5 s; note `renderer.py` clamps `t ≥ 0` so
the one frame that slips past the `timer > 0` guard can't produce negative alphas).

| Style | Time | Logic | Easing / curve |
|---|---|---|---|
| **Manifest (raise)** | 0.0 → 0.75 s | Crucifix symbol springs up from `0.80h` to `0.50h` (the "arm raise") while scaling 16 → 38 px; overshoots ~10 % mid-rise. | `easeOutBack(min(1, u·2))` (u = elapsed/1.5) |
| **Pulse (radiance)** | 0.0 → 1.5 s | Expanding golden rings from screen center: `r = u · w·0.45`, 2 px outer + 1 px inner ring. | linear expansion, alpha envelope below |
| **Rotate (holy aura)** | 0.0 → 1.5 s | Six rune ticks orbit the cross: `θ_i = u·0.6 + i·π/3`, on a 1.5:0.7 (x:y) ellipse at 1.5·/0.7·sym. Slow 0.6 rad total — a "blessing" drift, not a spin. | linear rotation |
| **Envelope** | 0.0 → 1.5 s | Brightness ramps in over 0.2 s, holds, fades out over the last 0.4 s: `fade = min(1, t/0.2, (1.5−t)/0.4)` → α = 210·fade (bars), 150·fade (rings), halved (ticks/core). | smooth in / smooth out |
| **Power beat** | frame 0 | Golden spark cascade: `burst(24, speed 60–220, life 0.7, size 1, color (255,220,90), gravity_scale 0.6)` at screen center + `trigger_screen_shake(2)` (trauma² falloff via `animation_core.CameraShake`). | n/a (event) |
| SFX | frame 0 → 1.6 s | `ward_bless`: ascending four-tone holy chime (523/659/784/1046 Hz, staggered decay). | n/a |

**Active-state presence:** while any ward is casting, the HUD chip and the expanding
ring both read as "power out" — the cross is the only ward with a *symbol* raise,
which is what sells "manifestation" vs the others (repel = ring, shield = tint,
banish = white ring, bind = purple rings — all in `_draw_ward_effect`).


---

## 4. Technical deliverables summary

### 4.1 Particle system configuration (all screen-space, `ParticleSystem(400)`)

| Effect | Type | Count / rate | Life | Size | Color gradient | Physics |
|---|---|---|---|---|---|---|
| Salt formation burst | `burst` | 24 | 0.9 s | 2 px | `(210,230,255)` → system fades color to black over life | up_bias 30, gravity 1.2, drag 1.0 |
| Salt motes | `emit` | 2 / 0.35 s per visible zone | 0.8 s | 1 px | `(210,230,255)` steady | gravity 0, drag 0.9 (pure drift up) |
| Garlic trail | `emit` | 1/frame while in flight | 0.5 s | 1 px | `(190,185,160)` | gravity 0, drag 0.9 |
| Garlic shatter | `burst` | 24 | 0.9 s | 2 px | `(190,185,160)` | up_bias 30, gravity 1.2 (ground bounce at y=350) |
| Cross sparks | `burst` | 24 | 0.7 s | 1 px | `(255,220,90)` | gravity 0.6 (fall slowly, "holy rain") |

Note: `ParticleSystem` v2 applies per-frame drag/gravity from the *emitted* values
with dt-corrected integration (`animation_core.py` — v1 had a per-frame decay bug;
do **not** re-add manual decay on top).

### 4.2 Shader / surface specifications

| Effect | Model | Key parameters | Implementation |
|---|---|---|---|
| Salt/garlic ground decal | Unlit decal, normal blend | ring RGB `(220,240,255)` / `(230,220,200)`; squish 0.32; ring width `1.5 + 0.4·unit` px | `zone_fx.draw` on the world surface (before darkness) |
| Zone glow ring | Unlit emissive, per-pixel alpha (SRCALPHA) | color `(90,100,125)` / `(120,110,80)`; α baked per (radius//8, α//16) LRU bucket; outer + inner ring | `renderer._zone_ring` + `'ring'` branch of `_draw_emissive` |
| Pickup/eye halos (context) | Unlit, `BLEND_RGB_ADD` | radial `f = clip(1−d)²` falloff, cached `_glow_sprite` | `renderer._glow_sprite` |
| Cross symbol + rings | Unlit emissive on cached scratch surface | gold `(255,215,0)`, core `(255,250,220)`, tick `(255,230,150)`; stroke ≥2 px; ring 2 px + 1 px | `renderer._draw_ward_effect` ('cross') |
| Future GPU pass | GLSL bloom/god-ray (optional) | `u_supernatural_intensity` uniform (currently *not* consumed by the fragment shader — keep the `if 'u_…' in prog` guard so Intel drivers can't crash) | `gl_present.py` |

Fresnel is intentionally out of scope: with no lit material model, the "Fresnel rim"
look is achieved by the two-ring emissive ellipse (bright rim + dim inner ring),
which reads as fresnel falloff at this pixel density.

### 4.3 Animation & timing coherence rules

1. **Manifest = easeOut***: anything *appearing* (zone ring, toss charge, cross raise)
   uses an easeOut family; only the cross gets overshoot (`easeOutBack`) because it is
   the "divine" beat. `zone_fx.py` exports `ease_out_quad/cubic/back` — reuse them,
   don't hand-roll new curves.
2. **One breath frequency**: all sustained supernatural states pulse at
   `sin(t·3)` (≈1.5 Hz) — zone breathing uses it, so any new ward sustain must too.
3. **Dissipation is always the final 0.5 s, linear**: zones fade `timer/0.5`; the
   cross envelope fades `(1.5−t)/0.4`. Never exponential — exponential fades read as
   "tech", not "ritual".
4. **Events fire on frame 0**: bursts/SFX/shake are single-frame triggers keyed to
   the action (`on_zone_appeared`, `trigger_ward_effect`), never per-frame emissions,
   except the explicitly sustained mote/vapor emitters above.
5. **All VFX dt-independent**: envelopes are functions of elapsed time, not frame
   counts; the one frame that slips past a `timer > 0` guard is clamped
   (`t = max(0.0, …)` in `_draw_ward_effect`).

### 4.4 Implementation map

| File | Responsibility |
|---|---|
| `zone_fx.py` | Zone projection, lifecycle envelopes, decal + emissive ring + motes, spawn bursts |
| `garlic_toss.py` | 3-phase toss object (charge/flight/land), world-position kinematics, in-flight draw |
| `renderer.py` | zone pass hook (step 5a), `_emissive` 'ring' kind, `_zone_ring` cache, 'cross' ward branch, cross spark burst |
| `main.py` | `render_frame` now receives `enemy_manager.active_effects`; `_use_salt/_use_garlic/_use_cross` wiring; toss update in `update_playing` |
| `enemies.py` | zone state (`add_salt_zone` r=2.0/8 s, `add_garlic_zone` r=2.5/6 s, timer bookkeeping) |
| `audio_synth.py` | `salt_pour`, `garlic_throw`, `garlic_impact`, `ward_bless` synthesized cues |
| `tests/test_vfx_zones.py` | 4 headless tests: ring emissive + cache, toss→zone landing, cross ward frames, smoke render |

**Verification:** `python tests/test_vfx_zones.py` (4/4), `python tests/smoke_test.py`
(12/12, includes the frames that fire salt/garlic through the new paths),
`python tests/test_gameplay_fixes.py` (ALL PASSED — cooldown semantics untouched).

