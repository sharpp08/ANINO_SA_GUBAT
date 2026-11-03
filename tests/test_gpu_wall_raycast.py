"""Headless contract tests for the GLSL 330 GPU wall raycaster."""
import os
import sys
import inspect

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gpu_wall_raycast import (
    DEFAULT_WALL_TEXTURE_NAMES,
    FRAGMENT_SHADER,
    VERTEX_SHADER,
    GPUWallRaycaster,
)


def test_shader_contract():
    assert VERTEX_SHADER.startswith("#version 330 core")
    assert FRAGMENT_SHADER.startswith("#version 330 core")
    for uniform in (
        "u_map", "u_wall_textures", "u_map_size", "u_view_size",
        "u_tile_layers", "u_camera_pos", "u_camera_angle", "u_fov",
        "u_max_depth", "u_wall_height_scale", "u_tile_size", "u_pitch_offset",
    ):
        assert uniform in FRAGMENT_SHADER
    assert "usampler2D" in FRAGMENT_SHADER
    assert "sampler2DArray" in FRAGMENT_SHADER
    assert "gl_FragDepth" in FRAGMENT_SHADER
    assert "texelFetch" in FRAGMENT_SHADER


def test_render_api_exposes_pitch_offset():
    params = inspect.signature(GPUWallRaycaster.render).parameters
    assert "pitch_offset" in params
    assert params["pitch_offset"].default == 0.0


def test_existing_wall_tile_mapping():
    assert DEFAULT_WALL_TEXTURE_NAMES == {
        1: "stone", 2: "wood", 3: "bamboo", 4: "balete", 5: "door"
    }


if __name__ == "__main__":
    test_shader_contract()
    test_render_api_exposes_pitch_offset()
    test_existing_wall_tile_mapping()
    print("[PASS] GPU wall raycaster shader contract")
