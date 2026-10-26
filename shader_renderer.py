"""
ModernGL GPU Shader Renderer for ANINO SA GUBAT: Mga Bulong ng Dilim.
Provides GPU-accelerated horror lighting, distance fog, color grading, and supernatural post-processing,
with automatic fallback to software rendering if OpenGL context creation or shader compilation fails.
"""

import pygame
import numpy as np

try:
    import moderngl  # type: ignore
    MODERNGL_AVAILABLE = True
except Exception:
    MODERNGL_AVAILABLE = False


class ShaderRenderer:
    """Manages ModernGL context, textures, full-screen quad, and horror post-processing shaders."""

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

        if not MODERNGL_AVAILABLE:
            print("[SHADERS] ModernGL not available. Using software fallback renderer.")
            return

        try:
            self.ctx = moderngl.create_context(standalone=True)
            self.ctx.enable(moderngl.BLEND)

            vertices = np.array([
                -1.0,  1.0, 0.0, 1.0,
                -1.0, -1.0, 0.0, 0.0,
                 1.0,  1.0, 1.0, 1.0,
                 1.0, -1.0, 1.0, 0.0,
            ], dtype=np.float32)

            self.vbo = self.ctx.buffer(vertices.tobytes())

            vert_shader = """
            #version 330 core
            in vec2 in_position;
            in vec2 in_uv;
            out vec2 v_uv;
            void main() {
                v_uv = in_uv;
                gl_Position = vec4(in_position, 0.0, 1.0);
            }
            """

            frag_shader = """
            #version 330 core
            uniform sampler2D u_texture;
            uniform float u_time;
            uniform vec2 u_resolution;
            uniform int u_flashlight_on;
            uniform float u_fog_density;
            uniform float u_supernatural_intensity;
            in vec2 v_uv;
            out vec4 fragColor;

            float rand(vec2 co){
                return fract(sin(dot(co.xy ,vec2(12.9898,78.233))) * 43758.5453);
            }

            void main() {
                vec2 uv = v_uv;
                if (u_supernatural_intensity > 0.0) {
                    uv.x += sin(uv.y * 25.0 + u_time * 6.0) * 0.006 * u_supernatural_intensity;
                }
                vec4 col = texture(u_texture, uv);

                // Horror Color Grading & Darkness
                vec3 grade = vec3(0.08, 0.13, 0.24);
                col.rgb = mix(col.rgb, col.rgb * grade * 2.2, 0.35);
                col.rgb = pow(max(col.rgb, 0.0), vec3(1.12));

                if (u_flashlight_on == 1) {
                    float beam = smoothstep(0.48, 0.05, distance(uv, vec2(0.5, 0.5)));
                    col.rgb += vec3(0.18, 0.14, 0.09) * beam;
                }

                float fog = smoothstep(0.25, 0.95, distance(uv, vec2(0.5, 0.5)) * u_fog_density);
                col.rgb = mix(col.rgb, vec3(0.03, 0.06, 0.05), fog * 0.55);

                vec2 cc = uv * 2.0 - 1.0;
                col.rgb *= clamp(1.0 - dot(cc, cc) * 0.45, 0.2, 1.0);
                col.rgb += vec3((rand(uv * u_time) - 0.5) * 0.055);

                fragColor = vec4(col.rgb, 1.0);
            }
            """

            self.prog = self.ctx.program(vertex_shader=vert_shader, fragment_shader=frag_shader)
            self.vao = self.ctx.simple_vertex_array(self.prog, self.vbo, 'in_position', 'in_uv')
            self.texture = self.ctx.texture((width, height), 3, dtype='f1')
            self.texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
            self.fbo = self.ctx.simple_framebuffer((width, height))

            self.enabled = True
            print("[SHADERS] ModernGL GPU Shaders initialized successfully.")
        except Exception as e:
            print(f"[SHADERS] Failed to initialize ModernGL: {e}. Falling back to software renderer.")
            self.enabled = False

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

            return pygame.image.fromstring(self.fbo.read(components=3), (self.width, self.height), 'RGB')
        except Exception:
            return pygame_surface

    def release(self):
        try:
            if self.fbo: self.fbo.release()
            if self.texture: self.texture.release()
            if self.vao: self.vao.release()
            if self.vbo: self.vbo.release()
            if self.prog: self.prog.release()
            if self.ctx: self.ctx.release()
        except Exception:
            pass
