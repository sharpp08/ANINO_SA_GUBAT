"""Experimental ModernGL wall raycaster for ANINO SA GUBAT.

Renders the existing integer tile grid to an RGBA color texture and a depth
attachment using GLSL 330. Gameplay, map ownership and sprite depth policy stay
in Python. The pass is intentionally opt-in until the scene compositor can
consume GPU wall color/depth without a framebuffer readback.
"""
from __future__ import annotations

import numpy as np

VERTEX_SHADER = "#version 330 core\nin vec2 in_position;\nin vec2 in_uv;\nout vec2 v_uv;\nvoid main() {\n    v_uv = in_uv;\n    gl_Position = vec4(in_position, 0.0, 1.0);\n}\n"
FRAGMENT_SHADER = "#version 330 core\nin vec2 v_uv; out vec4 fragColor;\nuniform usampler2D u_map; uniform sampler2D u_tree_map; uniform sampler2DArray u_wall_textures;\nuniform ivec2 u_map_size; uniform ivec2 u_view_size; uniform int u_tile_layers[16];\nuniform vec2 u_camera_pos; uniform float u_camera_angle; uniform float u_fov; uniform float u_max_depth;\nuniform float u_wall_height_scale; uniform float u_tile_size; uniform float u_pitch_offset;\nuniform vec2 u_light_dir; uniform float u_shadow_strength;\nfloat wall_shadow(vec2 world_pos, vec2 surface_normal, vec2 ray_dir, float hit_dist) {\n vec2 light_dir=normalize(u_light_dir), tangent=vec2(-u_light_dir.y,u_light_dir.x);\n float visibility=0.0; const float offsets[3]=float[3](-0.22,0.0,0.22);\n for(int tap=0;tap<3;tap++){float ray_visibility=1.0;\n  vec2 origin=world_pos+surface_normal*0.055+tangent*offsets[tap];\n  for(int step_i=1;step_i<=12;step_i++){vec2 sample_pos=origin+light_dir*(float(step_i)*0.32);\n   ivec2 cell=ivec2(floor(sample_pos));\n   if(cell.x<0||cell.y<0||cell.x>=u_map_size.x||cell.y>=u_map_size.y)break;\n   if(texelFetch(u_map,cell,0).r!=0u||texelFetch(u_tree_map,cell,0).r>0.5){ray_visibility=0.0;break;}}\n  visibility+=ray_visibility;}\n return mix(1.0,visibility/3.0,clamp(u_shadow_strength,0.0,1.0));\n}\nvoid main(){\n float sx=gl_FragCoord.x/float(u_view_size.x),sy=float(u_view_size.y)-gl_FragCoord.y;\n float angle=u_camera_angle+(sx-0.5)*u_fov;vec2 rd=vec2(cos(angle),sin(angle));\n ivec2 cell=ivec2(floor(u_camera_pos));ivec2 sd=ivec2(rd.x>=0.0?1:-1,rd.y>=0.0?1:-1);\n vec2 delta=1.0/max(abs(rd),vec2(0.00001));\n vec2 side=vec2((rd.x>=0.0?float(cell.x+1)-u_camera_pos.x:u_camera_pos.x-float(cell.x))*delta.x,\n (rd.y>=0.0?float(cell.y+1)-u_camera_pos.y:u_camera_pos.y-float(cell.y))*delta.y);\n int tile=0,hs=0;float hd=u_max_depth;bool hit=false;\n for(int i=0;i<160;i++){if(min(side.x,side.y)>u_max_depth)break;\n  if(side.x<side.y){side.x+=delta.x;cell.x+=sd.x;hs=0;}else{side.y+=delta.y;cell.y+=sd.y;hs=1;}\n  if(cell.x<0||cell.y<0||cell.x>=u_map_size.x||cell.y>=u_map_size.y)break;\n  int id=int(texelFetch(u_map,cell,0).r);if(id!=0){tile=id;hit=true;\n   if(hs==0)hd=(float(cell.x)-u_camera_pos.x+(1.0-float(sd.x))*0.5)/rd.x;\n   else hd=(float(cell.y)-u_camera_pos.y+(1.0-float(sd.y))*0.5)/rd.y;break;}}\n if(!hit||tile<0||tile>=16||u_tile_layers[tile]<0){fragColor=vec4(0.0);gl_FragDepth=1.0;return;}\n float corrected=max(0.01,hd*cos(angle-u_camera_angle));float wh=min(u_wall_height_scale/(corrected*u_tile_size),float(u_view_size.y)*3.0);\n float top=0.5*float(u_view_size.y)-0.5*wh+u_pitch_offset;float ly=(sy-top)/max(wh,0.0001);\n if(ly<0.0||ly>=1.0){fragColor=vec4(0.0);gl_FragDepth=1.0;return;}\n float wu=hs==0?fract(u_camera_pos.y+hd*rd.y):fract(u_camera_pos.x+hd*rd.x);\n vec3 texel=texture(u_wall_textures,vec3(wu,1.0-ly,float(u_tile_layers[tile]))).rgb;\n float ds=max(0.15,1.0-corrected/u_max_depth),face=hs==1?0.86:1.0;\n vec2 wp=u_camera_pos+rd*hd;vec2 normal=hs==0?vec2(-float(sd.x),0.0):vec2(0.0,-float(sd.y));\n float shadow=max(0.34,wall_shadow(wp,normal));\n fragColor=vec4(texel*ds*face*shadow,1.0);gl_FragDepth=clamp(corrected/u_max_depth,0.0,1.0);\n}"

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
               pitch_offset=0.0, trees=None, sunrise_progress=0.0,
               flashlight_on=False, flashlight_range=12.0):
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
        p["u_light_dir"].value = (0.82, 0.57)
        p["u_shadow_strength"].value = 0.48
        angle = float(camera_angle)
        p["u_camera_forward"].value = (float(np.cos(angle)), float(np.sin(angle)))
        p["u_flashlight_on"].value = 1 if flashlight_on else 0
        p["u_flashlight_range"].value = max(1.0, float(flashlight_range))
        p["u_moon_strength"].value = max(0.0, min(1.0, 1.0 - float(sunrise_progress)))
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
