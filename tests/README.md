# Tests Directory

## Running Headless Smoke Tests
To run the automated smoke test suite (headless mode with dummy video and audio drivers):
```bash
python tests/smoke_test.py
```

This test suite covers:
1. Module imports and headless Pygame initialization.
2. Procedural asset generation (< 5s check).
3. Multi-chapter gameplay simulation (600+ frames).
4. Enemy AI state machines and lifecycle.
5. Game state machine transitions.
6. Save & load robust edge cases (round-trip, old format, corrupted JSON, missing file, empty file).
7. Simulated soak test (1800 frames).
