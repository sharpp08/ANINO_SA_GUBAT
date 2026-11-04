"""Experimental ModernGL wall raycaster for ANINO SA GUBAT.

Renders the existing integer tile grid to an RGBA color texture and a depth
attachment using GLSL 330. Gameplay, map ownership and sprite depth policy stay
in Python. The pass is intentionally opt-in until the scene compositor can
consume GPU wall color/depth without a framebuffer readback.
"""
from __future__ import annotations

import numpy as np

VERTEX_SHADER = "#version 330 core\nin vec2 in_position;\nin vec2 in_uv;\nout vec2 v_uv;\nvoid main() {\n    v_uv = in_uv;\n    gl_Position = vec4(in_position, 0.0, 1.0);\n}\n"
FRAGMENT_SHADER = "#version 330 core\nin vec2 v_uv;\nout vec4 fragColor;\nuniform usampler2D u_map;
uniform sampler2D u_tree_map;\nuniform sampler2DArray u_wall_textures;\nuniform ivec2 u_map_size;\nuniform ivec2 u_view_size;\nuniform int u_tile_layers[16];\nuniform vec2 u_camera_pos;\nuniform float u_camera_angle;\nuniform float u_fov;\nuniform float u_max_depth;\nuniform float u_wall_height_scale;\nuniform float u_tile_size;\nuniform float u_pitch_offset;\nuniform vec2 u_light_dir;\nuniform float u_shadow_strength;\n\nfloat wall_shadow(vec2 world_pos, vec2 surface_normal) {\n    vec2 light_dir = normalize(u_light_dir);\n    vec2 tangent = vec2(-light_dir.y, light_dir.x);\n    float visibility = 0.0;\n    const float offsets[3] = float[3](-0.22, 0.0, 0.22);\n    for (int s = 0; s < 3; ++s) {\n        float ray_visibility = 1.0;\n        vec2 origin = world_pos + surface_normal * 0.035 + tangent * offsets[s];\n        for (int step_i = 1; step_i <= 7; ++step_i) {\n            vec2 sample_pos = origin + light_dir * (float(step_i) * 0.42);\n            ivec2 cell = ivec2(floor(sample_pos));\n            if (cell.x < 0 || cell.y < 0 || cell.x >= u_map_size.x || cell.y >= u_map_size.y) break;\n            if (texelFetch(u_map, cell, 0).r != 0u || texelFetch(u_tree_map, cell, 0).r > 0.5) { ray_visibility = 0.0; break; }\n        }\n        visibility += ray_visibility;\n    }\n    visibility /= 3.0;\n    return mix(1.0, visibility, clamp(u_shadow_strength, 0.0, 1.0));\n}\n\nvoid main() {\n    // Match the game's screen-space ray layout: one ray per horizontal pixel.\n    float screen_x = gl_FragCoord.x / float(u_view_size.x);\n    float screen_y = float(u_view_size.y) - gl_FragCoord.y;\n    float ray_angle = u_camera_angle + (screen_x - 0.5) * u_fov;\n    vec2 ray_dir = vec2(cos(ray_angle), sin(ray_angle));\n    ivec2 cell = ivec2(floor(u_camera_pos));\n    ivec2 step_dir = ivec2(ray_dir.x >= 0.0 ? 1 : -1,\n                           ray_dir.y >= 0.0 ? 1 : -1);\n    vec2 delta = 1.0 / max(abs(ray_dir), vec2(0.00001));\n    vec2 side_dist = vec2(\n        (ray_dir.x >= 0.0 ? float(cell.x + 1) - u_camera_pos.x\n                          : u_camera_pos.x - float(cell.x)) * delta.x,\n        (ray_dir.y >= 0.0 ? float(cell.y + 1) - u_camera_pos.y\n                          : u_camera_pos.y - float(cell.y)) * delta.y\n    );\n\n    int hit_tile = 0;\n    int hit_side = 0;\n    float hit_dist = u_max_depth;\n    bool hit = false;\n    for (int i = 0; i < 160; ++i) {\n        if (min(side_dist.x, side_dist.y) > u_max_depth) break;\n        if (side_dist.x < side_dist.y) {\n            side_dist.x += delta.x;\n            cell.x += step_dir.x;\n            hit_side = 0;\n        } else {\n            side_dist.y += delta.y;\n            cell.y += step_dir.y;\n            hit_side = 1;\n        }\n        if (cell.x < 0 || cell.y < 0 ||\n            cell.x >= u_map_size.x || cell.y >= u_map_size.y) break;\n        int tile_id = int(texelFetch(u_map, cell, 0).r);\n        if (tile_id != 0) {\n            hit_tile = tile_id;\n            hit = true;\n            if (hit_side == 0)\n                hit_dist = (float(cell.x) - u_camera_pos.x +\n                            (1.0 - float(step_dir.x)) * 0.5) / ray_dir.x;\n            else\n                hit_dist = (float(cell.y) - u_camera_pos.y +\n                            (1.0 - float(step_dir.y)) * 0.5) / ray_dir.y;\n            break;\n        }\n    }\n\n    if (!hit || hit_tile < 0 || hit_tile >= 16 || u_tile_layers[hit_tile] < 0) {\n        fragColor = vec4(0.0);\n        gl_FragDepth = 1.0;\n        return;\n    }\n\n    float corrected_dist = max(0.01, hit_dist * cos(ray_angle - u_camera_angle));\n    float wall_h = min(u_wall_height_scale /\n                       (corrected_dist * u_tile_size), float(u_view_size.y) * 3.0);\n    float top = 0.5 * float(u_view_size.y) - 0.5 * wall_h + u_pitch_offset;\n    float local_y = (screen_y - top) / max(wall_h, 0.0001);\n    if (local_y < 0.0 || local_y >= 1.0) {\n        fragColor = vec4(0.0);\n        gl_FragDepth = 1.0;\n        return;\n    }\n\n    float wall_u;\n    if (hit_side == 0) {\n        float wall_y = u_camera_pos.y + hit_dist * ray_dir.y;\n        wall_u = fract(wall_y);\n    } else {\n        float wall_x = u_camera_pos.x + hit_dist * ray_dir.x;\n        wall_u = fract(wall_x);\n    }\n    vec3 texel = texture(u_wall_textures,\n                         vec3(wall_u, 1.0 - local_y,\n                              float(u_tile_layers[hit_tile]))).rgb;\n    float distance_shade = max(0.15, 1.0 - corrected_dist / u_max_depth);\n    float face_shade = hit_side == 1 ? 0.86 : 1.0;\n    vec2 hit_world = u_camera_pos + ray_dir * hit_dist;\n    vec2 surface_normal = hit_side == 0 ? vec2(-float(step_dir.x), 0.0) : vec2(0.0, -float(step_dir.y));\n    float shadow = wall_shadow(hit_world, surface_normal);\n    float shadow_light = max(0.34, shadow);\n    fragColor = vec4(texel * distance_shade * face_shade * shadow_light, 1.0);\n    gl_FragDepth = clamp(corrected_dist / u_max_depth, 0.0, 1.0);\n}\n"

# Existing map tile IDs used by renderer._get_wall_texture().
DEFAULT_WALL_TEXTURE_NAMES = {
    1: "stone",
    2: "wood",
    3: "bamboo",
    4: "balete",
    5: "door",
}


class GPUWallRaycaster:
    """GPU DDA wall pass. Requires an active OpenGL 3.3 context."""

    def __init__(self, ctx, width, height, tile_size=64, max_depth=35.0):
        import moderngl

        self.ctx = ctx
        self.moderngl = moderngl
        self.width = int(width)
        self.height = int(height)
        self.tile_size = float(tile_size)
        self.max_depth = float(max_depth)
        self.program = ctx.program(
            vertex_shader=VERTEX_SHADER,
            fragment_shader=FRAGMENT_SHADER,
        )
        vertices = np.asarray([
            -1.0,  1.0, 0.0, 1.0,
            -1.0, -1.0, 0.0, 0.0,
             1.0,  1.0, 1.0, 1.0,
             1.0, -1.0, 1.0, 0.0,
        ], dtype=np.float32)
        self.vbo = ctx.buffer(vertices.tobytes())
        self.vao = ctx.vertex_array(
            self.program,
            [(self.vbo, "2f 2f", "in_position", "in_uv")],
        )
        self.color = ctx.texture((self.width, self.height), 4, dtype="f1")
        self.color.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self.depth = ctx.depth_texture((self.width, self.height))
        self.fbo = ctx.framebuffer(
            color_attachments=[self.color], depth_attachment=self.depth
        )
        self.map_texture = None
        self.map_key = None
        self.tree_texture = None
        self.tree_key = None
        self.wall_texture_array = None
        self.wall_layers = {}
        self._closed = False

    def upload_map(self, grid, revision=0):
        """Upload a [y, x] integer grid only when its identity/revision changes."""
        array = np.ascontiguousarray(grid, dtype=np.uint32)
        if array.ndim != 2:
            raise ValueError("map grid must be a 2D [y, x] array")
        key = (id(grid), int(revision), array.shape)
        if key == self.map_key:
            return
        if self.map_texture is not None:
            self.map_texture.release()
        h, w = array.shape
        self.map_texture = self.ctx.texture((w, h), 1, array.tobytes(), dtype="u4")
        self.map_texture.filter = (self.moderngl.NEAREST, self.moderngl.NEAREST)
        self.map_texture.repeat_x = False
        self.map_texture.repeat_y = False
        self.map_key = key


    def upload_tree_occluders(self, trees, map_width, map_height, revision=0):
        """Upload coarse world-space tree occupancy for the live GPU wall shadow rays."""
        import numpy as np
        width, height = int(map_width), int(map_height)
        key = (id(trees), len(trees), width, height, int(revision))
        if key == self.tree_key:
            return
        field = np.zeros((height, width), dtype=np.uint8)
        for tree in trees or ():
            try:
                x, y = float(tree["x"]), float(tree["y"])
                radius = max(0.12, float(tree.get("radius", 0.22)))
            except (KeyError, TypeError, ValueError):
                continue
            cx, cy = int(x), int(y)
            for oy in (-1, 0, 1):
                for ox in (-1, 0, 1):
                    tx, ty = cx + ox, cy + oy
                    if 0 <= tx < width and 0 <= ty < height:
                        if (tx + 0.5 - x) ** 2 + (ty + 0.5 - y) ** 2 <= (radius + 0.72) ** 2:
                            field[ty, tx] = 255
        if self.tree_texture is not None:
            self.tree_texture.release()
        self.tree_texture = self.ctx.texture((width, height), 1, field.tobytes(), dtype="f1")
        self.tree_texture.filter = (self.moderngl.NEAREST, self.moderngl.NEAREST)
        self.tree_texture.repeat_x = False
        self.tree_texture.repeat_y = False
        self.tree_key = key

    def upload_wall_textures(self, textures, tile_names=None, size=None):
        """Build a texture-array atlas from pygame wall surfaces, keyed by tile ID."""
        import pygame

        names = tile_names or DEFAULT_WALL_TEXTURE_NAMES
        available = [(tile, textures.get(name)) for tile, name in names.items()]
        available = [(tile, surf) for tile, surf in available if surf is not None]
        if not available:
            raise ValueError("no wall textures supplied")
        if size is None:
            size = max(8, min(512, max(max(s.get_size()) for _, s in available)))
        size = int(size)
        layers = []
        self.wall_layers = {tile: i for i, (tile, _) in enumerate(available)}
        for _, surface in available:
            fitted = pygame.transform.smoothscale(surface, (size, size))
            rgb = pygame.image.tobytes(fitted, "RGB", True)
            layers.append(rgb)
        if self.wall_texture_array is not None:
            self.wall_texture_array.release()
        self.wall_texture_array = self.ctx.texture_array(
            (size, size, len(layers)), 3, b"".join(layers), dtype="f1"
        )
        self.wall_texture_array.filter = (
            self.moderngl.LINEAR, self.moderngl.LINEAR
        )
        self.wall_texture_array.repeat_x = False
        self.wall_texture_array.repeat_y = False
        tile_layers = [-1] * 16
        for tile, layer in self.wall_layers.items():
            if 0 <= int(tile) < len(tile_layers):
                tile_layers[int(tile)] = layer
        self.program["u_tile_layers"].value = tuple(tile_layers)

    def render(self, grid, revision, camera_pos, camera_angle, fov_radians,
               wall_height_scale, tile_size=None, max_depth=None,
               pitch_offset=0.0, trees=None):
        """Render wall color/depth to GPU attachments; returns (color, depth) textures."""
        if self._closed:
            raise RuntimeError("GPUWallRaycaster is closed")
        if self.wall_texture_array is None:
            raise RuntimeError("call upload_wall_textures() before render()")
        self.upload_map(grid, revision)
        self.fbo.use()
        self.fbo.viewport = (0, 0, self.width, self.height)
        self.fbo.clear(0.0, 0.0, 0.0, 0.0, depth=1.0)
        self.upload_tree_occluders(trees or (), grid.shape[1], grid.shape[0], revision)
        if self.tree_texture is None:
            self.tree_texture = self.ctx.texture((grid.shape[1], grid.shape[0]), 1, bytes(grid.shape[1] * grid.shape[0]), dtype='f1')
            self.tree_texture.filter = (self.moderngl.NEAREST, self.moderngl.NEAREST)
        self.map_texture.use(location=0)
        self.tree_texture.use(location=1)
        self.wall_texture_array.use(location=2)
        p = self.program
        p["u_map"].value = 0
        p["u_tree_map"].value = 1
        p["u_wall_textures"].value = 2
        p["u_map_size"].value = (grid.shape[1], grid.shape[0])
        p["u_view_size"].value = (self.width, self.height)
        p["u_camera_pos"].value = (float(camera_pos[0]), float(camera_pos[1]))
        p["u_camera_angle"].value = float(camera_angle)
        p["u_fov"].value = float(fov_radians)
        p["u_max_depth"].value = float(max_depth or self.max_depth)
        p["u_wall_height_scale"].value = float(wall_height_scale)
        p["u_tile_size"].value = float(tile_size or self.tile_size)
        p["u_pitch_offset"].value = float(pitch_offset)
        p["u_light_dir"].value = (-0.42, -0.91)
        p["u_shadow_strength"].value = 0.48
        self.ctx.disable(self.moderngl.BLEND)
        self.ctx.enable(self.moderngl.DEPTH_TEST)
        self.ctx.depth_func = "<="
        self.vao.render(self.moderngl.TRIANGLE_STRIP)
        return self.color, self.depth

    def resize(self, width, height):
        """Resize attachments without recompiling the shader program."""
        width, height = int(width), int(height)
        if (width, height) == (self.width, self.height):
            return
        self.fbo.release()
        self.color.release()
        self.depth.release()
        self.width, self.height = width, height
        self.color = self.ctx.texture((width, height), 4, dtype="f1")
        self.color.filter = (self.moderngl.NEAREST, self.moderngl.NEAREST)
        self.depth = self.ctx.depth_texture((width, height))
        self.fbo = self.ctx.framebuffer(
            color_attachments=[self.color], depth_attachment=self.depth
        )

    def close(self):
        """Release resources owned by this pass; the context remains caller-owned."""
        if self._closed:
            return
        self._closed = True
        for resource in (
            self.fbo, self.color, self.depth, self.map_texture,
            self.wall_texture_array, self.tree_texture, self.vao, self.vbo, self.program,
        ):
            if resource is not None:
                try:
                    resource.release()
                except Exception:
                    pass
        self.fbo = self.color = self.depth = None
        self.map_texture = self.wall_texture_array = self.tree_texture = None
