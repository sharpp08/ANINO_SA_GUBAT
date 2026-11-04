"""
GPU presentation path for ANINO SA GUBAT.

The game composes each frame on the CPU into a small surface (640x360). Previously that
frame was (optionally) sent through an offscreen OpenGL pass, READ BACK to the CPU, re-wrapped
as a pygame surface, scaled in software to 1280x720, and then uploaded again by SDL.

This module removes the round trip. The window is an OpenGL window; each frame the CPU
surface is uploaded once (CPU -> GPU, no stall), and a single shader pass on the GPU does the
colour grade, vignette, fog tint, grain and the upscale to the window, then pygame flips.

  * no GPU -> CPU readback (the synchronising stall is gone)
  * no per-frame bytes/surface allocations (the old path allocated ~2 MB/frame)
  * no software 640x360 -> 1280x720 scale
  * letterboxed to the window, so fullscreen at any monitor resolution keeps the aspect

Safety: attach() draws a known colour pattern and reads it back ONCE to verify channel order
and orientation. If anything is off (or no GL 3.3 context), attach() returns False and the game
keeps using the normal 2D window, so a bad driver can't leave you with a black or tinted screen.

Pure helpers (compute_swizzle, letterbox, map_to_surface) avoid pygame/GL so they can be
unit-tested headless.
"""
import sys

VERTEX_SHADER = """#version 330 core
in vec2 in_position;
in vec2 in_uv;
out vec2 v_uv;
void main() { v_uv = in_uv; gl_Position = vec4(in_position, 0.0, 1.0); }
"""

# Same look as the old offscreen shader (grade, flashlight tint, fog, vignette, grain), with
# u_post == 0 giving a plain upscale (menus, loading screens).
FRAGMENT_SHADER = """#version 330 core
uniform sampler2D u_texture;
uniform sampler2D u_overlay;
uniform int u_has_overlay;
uniform float u_time;
uniform int u_flashlight_on;
uniform float u_fog_density;
uniform float u_supernatural_intensity;
uniform int u_post;
uniform float u_bloom_strength;
in vec2 v_uv;
out vec4 fragColor;
float rand(vec2 co) { return fract(sin(dot(co.xy, vec2(12.9898, 78.233))) * 43758.5453); }
vec3 bright_pass(vec3 c) {
    float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
    float knee = max(l - 0.72, 0.0);
    return c * (knee / max(l, 0.001));
}
void main() {
    vec2 uv = v_uv;
    if (u_supernatural_intensity > 0.0 && u_post != 0)
        uv.x += sin(uv.y * 25.0 + u_time * 6.0) * 0.006 * u_supernatural_intensity;
    vec4 col = texture(u_texture, uv);
    // Menus/loading screens skip scene post-processing but still composite UI.
    if (u_post == 0) {
        if (u_has_overlay == 1) {
            vec4 over = texture(u_overlay, v_uv);
            col.rgb = over.rgb * over.a + col.rgb * (1.0 - over.a);
        }
        fragColor = vec4(col.rgb, 1.0);
        return;
    }
    // Five-tap threshold bloom: one inexpensive pass, no framebuffer readback.
    if (u_bloom_strength > 0.0) {
        vec2 px = 1.0 / vec2(textureSize(u_texture, 0));
        vec3 glow = bright_pass(col.rgb) * 0.40;
        glow += bright_pass(texture(u_texture, uv + vec2(px.x, 0.0)).rgb) * 0.15;
        glow += bright_pass(texture(u_texture, uv - vec2(px.x, 0.0)).rgb) * 0.15;
        glow += bright_pass(texture(u_texture, uv + vec2(0.0, px.y)).rgb) * 0.15;
        glow += bright_pass(texture(u_texture, uv - vec2(0.0, px.y)).rgb) * 0.15;
        col.rgb += glow * u_bloom_strength;
    }
    vec3 grade = vec3(0.82, 0.91, 1.0);
    col.rgb = mix(col.rgb, col.rgb * grade, 0.18);
    col.rgb = pow(max(col.rgb, 0.0), vec3(1.12));
    // The scene renderer already computes the real flashlight beam and falloff.
    // Do not add a second screen-centred fake beam or darken the entire scene here.
    // Keep the flag as a subtle neutral exposure adjustment only.
    if (u_flashlight_on == 1) {
        col.rgb *= vec3(1.005, 1.008, 1.012);
    }
    // Screen-space atmospheric tint is deliberately restrained; depth fog is handled
    // by the scene renderer where per-column ray distances are available.
    float fog = smoothstep(0.25, 0.95, distance(uv, vec2(0.5)) * u_fog_density);
    col.rgb = mix(col.rgb, vec3(0.03, 0.06, 0.05), fog * 0.35);
    vec2 cc = uv * 2.0 - 1.0;
    col.rgb *= clamp(1.0 - dot(cc, cc) * 0.38, 0.24, 1.0);
    // Fine grain: keep it subtle to avoid noisy dark gradients.
    col.rgb += vec3((rand(uv * mod(u_time, 100.0)) - 0.5) * 0.018);
    // Composite the UI/viewmodel layer LAST so the HUD, hands, weapon and crosshair stay crisp
    // (no bloom, grade, vignette or grain on them). Sample with the undistorted v_uv so the
    // supernatural ripple only affects the world. Without this, every frame rendered with
    // post == 1 (PLAYING / PAUSED) dropped the overlay layer entirely.
    if (u_has_overlay == 1) {
        vec4 over = texture(u_overlay, v_uv);
        col.rgb = over.rgb * over.a + col.rgb * (1.0 - over.a);
    }
    fragColor = vec4(col.rgb, 1.0);
}
"""


# ── pure helpers (no pygame / GL) ────────────────────────────────────────────
def compute_swizzle(shifts, preserve_alpha=False):
    """Texture swizzle that maps a little-endian 32-bit surface to RGB.

    ``shifts`` is pygame's (r, g, b, a) bit shifts. Byte i of a pixel lives at bits 8*i, and
    a 4-component texture exposes byte i as component 'RGBA'[i]. A default pygame surface
    (R shift 16, G 8, B 0) is stored B,G,R,X, which needs 'BGR1'.
    """
    r, g, b = (shifts[0] // 8, shifts[1] // 8, shifts[2] // 8)
    if len({r, g, b}) != 3 or max(r, g, b) > 3 or any(sh % 8 for sh in shifts[:3]):
        raise ValueError(f"unsupported pixel layout {shifts}")
    alpha = '1'
    if preserve_alpha:
        a = shifts[3] // 8
        if shifts[3] % 8 or a < 0 or a > 3:
            raise ValueError(f"surface has no usable alpha byte: {shifts}")
        alpha = 'RGBA'[a]
    return 'RGBA'[r] + 'RGBA'[g] + 'RGBA'[b] + alpha


def letterbox(win_w, win_h, src_w, src_h):
    """Largest aspect-correct rectangle (x, y, w, h) of the source inside the window."""
    scale = min(win_w / float(src_w), win_h / float(src_h))
    rw, rh = max(1, int(src_w * scale)), max(1, int(src_h * scale))
    return (win_w - rw) // 2, (win_h - rh) // 2, rw, rh


def map_to_surface(pos, win_w, win_h, src_w, src_h):
    """Window pixel position -> position in the presented surface's own pixels."""
    scale = min(win_w / float(src_w), win_h / float(src_h))
    x0 = (win_w - src_w * scale) / 2.0
    y0 = (win_h - src_h * scale) / 2.0
    return int((pos[0] - x0) / scale), int((pos[1] - y0) / scale)


class GLPresenter:
    """Uploads a pygame surface and presents it on an OpenGL window via one shader pass."""

    def __init__(self):
        self.ctx = None
        self.prog = None
        self.vbo = None
        self.vao = None
        self.tex = None
        self.overlay_tex = None
        self.scene_depth = None
        self.scene_fbo = None
        self._tex_key = None
        self._overlay_key = None
        self._overlay_key = None
        self._rect = None
        self._moderngl = None

    # ── window ───────────────────────────────────────────────────────────
    @staticmethod
    def open_window(size, fullscreen, vsync):
        """Create the OpenGL window (3.3 core). Returns pygame's display surface."""
        import pygame
        for attr, val in ((pygame.GL_CONTEXT_MAJOR_VERSION, 3),
                          (pygame.GL_CONTEXT_MINOR_VERSION, 3),
                          (pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE),
                          (pygame.GL_DOUBLEBUFFER, 1)):
            try:
                pygame.display.gl_set_attribute(attr, val)
            except Exception:
                pass
        flags = pygame.OPENGL | pygame.DOUBLEBUF
        if fullscreen:
            flags |= pygame.FULLSCREEN
            size = (0, 0)                      # native desktop resolution; we letterbox
        try:
            return pygame.display.set_mode(size, flags, vsync=vsync)
        except TypeError:
            return pygame.display.set_mode(size, flags)

    # ── GL setup + self-test ─────────────────────────────────────────────
    def attach(self, ref_surface):
        """Create GL objects and verify output. ``ref_surface`` gives the pixel format to test.

        Returns True only if the verification pattern came out with correct colours and
        orientation; otherwise releases everything and returns False.
        """
        try:
            import numpy as np
            import moderngl
            self._moderngl = moderngl
            self.ctx = moderngl.create_context()
            self.prog = self.ctx.program(vertex_shader=VERTEX_SHADER, fragment_shader=FRAGMENT_SHADER)
            # Row 0 of the surface is the top of the image; texture row 0 is v = 0.
            verts = np.array([-1.0, 1.0, 0.0, 0.0,
                              -1.0, -1.0, 0.0, 1.0,
                              1.0, 1.0, 1.0, 0.0,
                              1.0, -1.0, 1.0, 1.0], dtype=np.float32)
            self.vbo = self.ctx.buffer(verts.tobytes())
            self.vao = self.ctx.vertex_array(self.prog, [(self.vbo, '2f 2f', 'in_position', 'in_uv')])
            info = self.ctx.info
            print(f"[GPU] GL_RENDERER={info.get('GL_RENDERER')} | GL_VENDOR={info.get('GL_VENDOR')} "
                  f"| GL_VERSION={info.get('GL_VERSION')}")
            if not self._self_test(ref_surface):
                print("[GPU] output verification failed - using the normal 2D window instead.")
                self.close()
                return False
            print("[GPU] GPU presentation active (no readback, GPU upscale + post-process).")
            return True
        except Exception as exc:
            print(f"[GPU] OpenGL presentation unavailable ({type(exc).__name__}: {exc}); "
                  f"using the normal 2D window.")
            self.close()
            return False

    def _self_test(self, ref_surface):
        import pygame
        test = pygame.Surface((64, 36), 0, ref_surface)
        w, h = test.get_size()
        quads = {
            'TL': ((0.25, 0.75), (255, 0, 0), (0, 0, w // 2, h // 2)),
            'TR': ((0.75, 0.75), (0, 255, 0), (w // 2, 0, w - w // 2, h // 2)),
            'BL': ((0.25, 0.25), (0, 0, 255), (0, h // 2, w // 2, h - h // 2)),
            'BR': ((0.75, 0.25), (255, 255, 255), (w // 2, h // 2, w - w // 2, h - h // 2)),
        }
        for _, (_, color, rect) in quads.items():
            test.fill(color, rect)
        self.present(test, post=False)
        x0, y0, rw, rh = self._rect[:4]
        for name, ((fx, fy), want, _) in quads.items():
            px, py = int(x0 + rw * fx), int(y0 + rh * fy)    # GL origin is bottom-left
            got = tuple(self.ctx.screen.read(viewport=(px, py, 1, 1), components=3)[:3])
            if any(abs(int(a) - int(b)) > 8 for a, b in zip(got, want)):
                print(f"[GPU] self-test {name}: expected {want}, got {got}")
                return False
        return True

    # ── per-frame ────────────────────────────────────────────────────────
    def _ensure_texture(self, surface):
        if sys.byteorder != 'little':
            raise ValueError("big-endian pixel layout unsupported")
        w, h = surface.get_size()
        if surface.get_bitsize() != 32 or surface.get_pitch() != w * 4:
            raise ValueError(f"need a tightly packed 32-bit surface (bits={surface.get_bitsize()}, "
                             f"pitch={surface.get_pitch()}, width={w})")
        key = (w, h, tuple(surface.get_shifts()))
        if key == self._tex_key:
            return
        # Release the old framebuffer before its attachments when the render size
        # or source pixel layout changes.
        for resource_name in ("scene_fbo", "scene_depth", "tex"):
            resource = getattr(self, resource_name, None)
            if resource is not None:
                resource.release()
                setattr(self, resource_name, None)
        mgl = self._moderngl
        self.tex = self.ctx.texture((w, h), 4, dtype='f1')
        self.tex.filter = (mgl.NEAREST, mgl.NEAREST)
        self.tex.repeat_x = False
        self.tex.repeat_y = False
        self.tex.swizzle = compute_swizzle(surface.get_shifts())
        # Persistent scene color/depth attachments. Until each world pass is migrated,
        # the legacy renderer uploads its color into this GPU-owned target. Native passes
        # can progressively render into this FBO and share its depth attachment.
        self.scene_depth = self.ctx.depth_texture((w, h))
        self.scene_fbo = self.ctx.framebuffer(
            color_attachments=[self.tex], depth_attachment=self.scene_depth)
        self.scene_fbo.clear(0.0, 0.0, 0.0, 0.0, depth=1.0)
        self._tex_key = key

    def _ensure_overlay_texture(self, surface):
        if sys.byteorder != 'little':
            raise ValueError("big-endian pixel layout unsupported")
        w, h = surface.get_size()
        if surface.get_bitsize() != 32 or surface.get_pitch() != w * 4:
            raise ValueError(f"overlay needs tightly packed 32-bit pixels (bits={surface.get_bitsize()}, "
                             f"pitch={surface.get_pitch()}, width={w})")
        key = (w, h, tuple(surface.get_shifts()))
        if key != self._overlay_key:
            if self.overlay_tex is not None:
                self.overlay_tex.release()
            self.overlay_tex = self.ctx.texture((w, h), 4, dtype='f1')
            self.overlay_tex.filter = (self._moderngl.NEAREST, self._moderngl.NEAREST)
            self.overlay_tex.repeat_x = False
            self.overlay_tex.repeat_y = False
            self.overlay_tex.swizzle = compute_swizzle(surface.get_shifts(), preserve_alpha=True)
            self._overlay_key = key

    def begin_scene(self, surface, clear_color=(0.0, 0.0, 0.0, 0.0)):
        """Bind and clear the persistent GPU scene target for native world passes.

        Call after the presenter has been attached and while its GL context is current.
        The returned framebuffer shares the presenter's color and depth attachments.
        """
        self._ensure_texture(surface)
        self.scene_fbo.use()
        self.scene_fbo.viewport = (0, 0, *surface.get_size())
        self.scene_fbo.clear(*clear_color, depth=1.0)
        return self.scene_fbo

    @staticmethod
    def _upload_surface(texture, surface):
        buf = surface.get_buffer()
        try:
            try:
                texture.write(memoryview(buf))
            except Exception:
                texture.write(buf.raw)
        finally:
            del buf

    def present(self, surface, time_sec=0.0, flashlight_on=1, supernatural=0.0,
                fog_density=1.0, post=True, bloom_strength=0.12, overlay_surface=None,
                scene_is_gpu=False):
        """Present a GPU scene or upload the legacy Pygame scene during migration.

        Set scene_is_gpu=True after native world passes have rendered into begin_scene().
        """
        import pygame
        self._ensure_texture(surface)
        if not scene_is_gpu:
            self._upload_surface(self.tex, surface)
        has_overlay = overlay_surface is not None
        if has_overlay:
            self._ensure_overlay_texture(overlay_surface)
            self._upload_surface(self.overlay_tex, overlay_surface)
        ww, wh = pygame.display.get_window_size()
        sw, sh = surface.get_size()
        x, y, rw, rh = letterbox(ww, wh, sw, sh)
        self._rect = (x, y, rw, rh, ww, wh)
        screen = self.ctx.screen
        screen.use()
        screen.viewport = (0, 0, ww, wh)
        screen.clear(0.0, 0.0, 0.0, 1.0)
        screen.viewport = (x, y, rw, rh)
        self.tex.use(0)
        if has_overlay:
            self.overlay_tex.use(1)
        prog = self.prog
        prog['u_texture'].value = 0
        prog['u_overlay'].value = 1
        prog['u_has_overlay'].value = 1 if has_overlay else 0
        prog['u_post'].value = 1 if post else 0
        prog['u_time'].value = float(time_sec)
        prog['u_flashlight_on'].value = int(flashlight_on)
        prog['u_fog_density'].value = float(fog_density)
        prog['u_supernatural_intensity'].value = float(supernatural)
        prog['u_bloom_strength'].value = float(bloom_strength) if post else 0.0
        self.vao.render(self._moderngl.TRIANGLE_STRIP)

    def map_mouse(self, pos, src_w, src_h):
        """Window mouse position -> pixel position in a ``src_w`` x ``src_h`` presented surface."""
        import pygame
        ww, wh = pygame.display.get_window_size()
        return map_to_surface(pos, ww, wh, src_w, src_h)

    def close(self):
        for name in ('vao', 'vbo', 'scene_fbo', 'scene_depth', 'tex', 'overlay_tex', 'prog'):
            obj = getattr(self, name, None)
            if obj is not None:
                try:
                    obj.release()
                except Exception:
                    pass
                setattr(self, name, None)
        if self.ctx is not None:
            try:
                self.ctx.release()
            except Exception:
                pass
        self.ctx = None
        self._tex_key = None
        self._overlay_key = None
