# GPU rendering setup

ANINO SA GUBAT includes an optional ModernGL shader post-processing path in
`shader_renderer.py`. The existing Pygame/NumPy raycaster still builds the
scene on the CPU; ModernGL currently applies the final color, flashlight,
fog, vignette, and supernatural distortion shader. This is a hybrid renderer,
not a complete GPU raycaster.

## Install

From the project directory:

```bash
python -m pip install -r requirements.txt
```

The requirements include ModernGL and glcontext. If a usable OpenGL context
cannot be created on the machine, the game logs a shader initialization
warning and continues with the Pygame software-rendering path.

## Verify at startup

Look for this startup message:

```text
[SHADERS] ModernGL GPU Shaders initialized successfully.
```

If you instead see `ModernGL not available` or `Failed to init ModernGL`,
the optional shader path is not active. Update the Intel graphics driver and
check that Windows is using the Intel Iris Xe/UHD graphics device for Python.

## Performance note

The current shader path uploads the CPU-rendered frame to a GPU texture and
reads the processed frame back to a Pygame surface. That readback can be
expensive, especially on integrated graphics. A larger GPU performance gain
requires the next renderer phase: keeping the final frame on the GPU and
presenting it directly through a Pygame OpenGL display/context, then moving
raycasting and floor/lighting passes into GLSL. Do not interpret high GPU
utilization as a goal by itself; stable frame time and higher FPS are the
targets.
