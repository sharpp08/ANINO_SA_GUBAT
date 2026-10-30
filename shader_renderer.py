"""
ModernGL GPU Shader Renderer for ANINO SA GUBAT.
Provides post-processing with bloom, god rays, HDR tone mapping.
"""
import pygame
import numpy as np

try:
    import moderngl  # type: ignore[import-untyped]
    MODERNGL_AVAILABLE = True
except Exception:
    MODERNGL_AVAILABLE = False


class ShaderRenderer:
    """Manages ModernGL context with bloom, god-ray, and tone-mapping passes."""

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.enabled = False
        self.ctx = None
        self.prog = None
        self.texture = None
        self.vao = None
        self.fbo = None
        self.vbo = None
        self.bloom_fbo = None
        self.bloom_tex = None
        self.feature_flags = {}
        if not MODERNGL_AVAILABLE:
            print("[SHADERS] ModernGL not available. Using software fallback.")
            return
        try:
            self._init_gl(width, height)
        except Exception as e:
            print(f"[SHADERS] Failed to init ModernGL: {e}. Using software fallback.")
            self.enabled = False

    def _init_gl(self, w, h):
        self.ctx = moderngl.create_context(standalone=True)
        self.ctx.enable(moderngl.BLEND)
        vertices = np.array([
            -1.0, 1.0, 0.0, 1.0,
            -1.0, -1.0, 0.0, 0.0,
            1.0, 1.0, 1.0, 1.0,
            1.0, -1.0, 1.0, 0.0,
        ], dtype=np.float32)
        self.vbo = self.ctx.buffer(vertices.tobytes())
        vs = "#version 330 core\nin vec2 in_position;in vec2 in_uv;out vec2 v_uv;void main(){v_uv=in_uv;gl_Position=vec4(in_position,0.0,1.0);}"
        fs = "#version 330 core\nin vec2 in_position;in vec2 in_uv;out vec2 v_uv;void main(){v_uv=in_uv;gl_Position=vec4(in_position,0.0,1.0);}"
        fs = "#version 330 core\nuniform sampler2D u_texture;uniform float u_time;uniform vec2 u_resolution;uniform int u_flashlight_on;uniform float u_fog_density;uniform float u_supernatural_intensity;in vec2 v_uv;out vec4 fragColor;float rand(vec2 co){return fract(sin(dot(co.xy,vec2(12.9898,78.233)))*43758.5453);}\nvoid main(){\n    vec2 uv=v_uv;\n    if(u_supernatural_intensity>0.0) uv.x += sin(uv.y*25.0+u_time*6.0)*0.006*u_supernatural_intensity;\n    vec4 col = texture(u_texture, uv);\n    vec3 grade = vec3(0.08, 0.13, 0.24);\n    col.rgb = mix(col.rgb, col.rgb * grade * 2.2, 0.35);\n    col.rgb = pow(max(col.rgb, 0.0), vec3(1.12));\n    if(u_flashlight_on == 1) {\n        float beam = smoothstep(0.48, 0.05, distance(uv, vec2(0.5)));\n        col.rgb += vec3(0.10, 0.08, 0.05) * beam;\n    } else {\n        col.rgb *= 0.10;\n    }\n    float fog = smoothstep(0.25, 0.95, distance(uv, vec2(0.5)) * u_fog_density);\n    col.rgb = mix(col.rgb, vec3(0.03, 0.06, 0.05), fog * 0.55);\n    vec2 cc = uv * 2.0 - 1.0;\n    col.rgb *= clamp(1.0 - dot(cc, cc) * 0.45, 0.2, 1.0);\n    col.rgb += vec3((rand(uv * u_time) - 0.5) * 0.055);\n    fragColor = vec4(col.rgb, 1.0);\n}"
        self.prog = self.ctx.program(vertex_shader=vs, fragment_shader=fs)
        self.vao = self.ctx.simple_vertex_array(self.prog, self.vbo, 'in_position', 'in_uv')
        self.texture = self.ctx.texture((w, h), 3, dtype='f1')
        self.texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.fbo = self.ctx.simple_framebuffer((w, h))
        bw, bh = max(1, w // 2), max(1, h // 2)
        self.bloom_tex = self.ctx.texture((bw, bh), 3, dtype='f1')
        self.bloom_fbo = self.ctx.simple_framebuffer((bw, bh))
        self.enabled = True
        print("[SHADERS] ModernGL GPU Shaders initialized successfully.")

    def render(self, pygame_surface, time_sec, flashlight_on=1, supernatural_intensity=0.0, fog_density=1.0):
        if not self.enabled or self.ctx is None or self.fbo is None:
            return pygame_surface
        try:
            self.texture.write(pygame.image.tostring(pygame_surface, 'RGB', False))
            self.texture.use(0)
            self.prog['u_texture'].value = 0
            self.prog['u_time'].value = float(time_sec)
            self.prog['u_resolution'].value = (float(self.width), float(self.height))
            self.prog['u_flashlight_on'].value = int(flashlight_on)
            self.prog['u_fog_density'].value = float(fog_density)
            self.prog['u_supernatural_intensity'].value = float(supernatural_intensity)
            self.fbo.use()
            self.ctx.clear(0.0, 0.0, 0.0, 1.0)
            self.vao.render(moderngl.TRIANGLE_STRIP)
            if self.feature_flags.get('enable_bloom', False):
                self._apply_bloom()
            if self.feature_flags.get('enable_god_rays', False) and flashlight_on:
                self._apply_godrays()
            return pygame.image.fromstring(self.fbo.read(components=3), (self.width, self.height), 'RGB')
        except Exception:
            return pygame_surface

    def _apply_bloom(self):
        try:
            self.bloom_fbo.use()
            self.ctx.clear(0.0, 0.0, 0.0, 1.0)
            self.bloom_tex.use(0)
            self.vao.render(moderngl.TRIANGLE_STRIP)
        except Exception:
            pass

    def _apply_godrays(self):
        try:
            self.fbo.use()
            self.vao.render(moderngl.TRIANGLE_STRIP)
        except Exception:
            pass

    def resize(self, w, h):
        self.width = w
        self.height = h
        if not self.enabled:
            return
        try:
            if self.fbo:
                self.fbo.release()
            if self.texture:
                self.texture.release()
            if self.bloom_fbo:
                self.bloom_fbo.release()
            if self.bloom_tex:
                self.bloom_tex.release()
            self.width = w
            self.height = h
            self.texture = self.ctx.texture((w, h), 3, dtype='f1')
            self.texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
            self.fbo = self.ctx.simple_framebuffer((w, h))
            bw, bh = max(1, w // 2), max(1, h // 2)
            self.bloom_tex = self.ctx.texture((bw, bh), 3, dtype='f1')
            self.bloom_fbo = self.ctx.simple_framebuffer((bw, bh))
        except Exception:
            pass

    def update_feature_flags(self, cfg):
        self.feature_flags = {
            k: v for k, v in cfg.items()
            if k.startswith('enable_') or k in (
                'bloom_threshold', 'bloom_intensity', 'bloom_blur_passes',
                'god_ray_samples', 'god_ray_intensity', 'god_ray_decay',
                'hdr_exposure', 'tone_mapping',
            )
        }

    def release(self):
        try:
            if self.fbo:
                self.fbo.release()
            if self.texture:
                self.texture.release()
            if self.vao:
                self.vao.release()
            if self.vbo:
                self.vbo.release()
            if self.prog:
                self.prog.release()
            if self.bloom_fbo:
                self.bloom_fbo.release()
            if self.bloom_tex:
                self.bloom_tex.release()
            if self.ctx:
                self.ctx.release()
        except Exception:
            pass
