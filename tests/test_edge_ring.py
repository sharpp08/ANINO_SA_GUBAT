"""
Verify the dense perimeter tree-line (invisible wall):
 - ring trees exist on all four sides
 - ring survives chunk rebuilds (update_world_chunks)
 - clamp_position keeps a player hugging each wall inside the map
"""
import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

import sys
import math
import pygame

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from settings import *
from map_system import GameMap
from player import Player


class _FakeKeys:
    def __init__(self):
        self._keys = {}
    def __setitem__(self, k, v):
        self._keys[k] = v
    def __getitem__(self, k):
        return self._keys.get(k, False)
    def __contains__(self, k):
        return k in self._keys


def _fake_keys(forward=False):
    keys = _FakeKeys()
    if forward:
        keys[pygame.K_w] = True
    return keys

gmap = GameMap(1)
w, h = gmap.width, gmap.height
ring = gmap._edge_ring
print(f"Ring trees: {len(ring)} (total trees: {len(gmap.trees)})")
assert len(ring) > 0

# 1. All four sides populated
def side_count(pred):
    return sum(1 for t in ring if pred(t))
assert side_count(lambda t: t['y'] < 6.0) > 100, "top side"
assert side_count(lambda t: t['y'] > h - 6.0) > 100, "bottom side"
assert side_count(lambda t: t['x'] < 6.0) > 80, "left side"
assert side_count(lambda t: t['x'] > w - 6.0) > 80, "right side"
print("[PASS] Ring present on all four sides")

# 2. Ring is part of self.trees and the spatial hash
assert all(t in gmap.trees for t in ring[:50])
near_left = gmap.spatial_hash.query(2.0, 64.0, radius=1.0)
assert any(t['biome'] == 'edge_ring' for t in near_left), "left wall missing from spatial hash"
print("[PASS] Ring trees in self.trees and spatial hash")

# 3. Ring survives a chunk rebuild
gmap.world_engine.update_world_chunks(gmap.player_start[0], gmap.player_start[1], gmap)
assert any(t['biome'] == 'edge_ring' for t in gmap.trees), "ring lost on chunk rebuild"
near_left2 = gmap.spatial_hash.query(2.0, 64.0, radius=1.0)
assert any(t['biome'] == 'edge_ring' for t in near_left2), "ring lost from hash on chunk rebuild"
print("[PASS] Ring survives chunk rebuilds")

# 4. Clamp backstop: walk into every wall
for (x0, y0, ang, label) in [
    (8.0, 64.0, math.pi, "left"),
    (w - 8.0, 64.0, 0.0, "right"),
    (64.0, 8.0, -math.pi / 2, "top"),
    (64.0, h - 8.0, math.pi / 2, "bottom"),
]:
    p = Player(x0, y0, ang)
    for i in range(600):
        p.update(1 / 60, _fake_keys(forward=True), 0.0, 0.0, gmap)
    m = EDGE_RING_PLAYABLE_MARGIN + PLAYER_SIZE
    assert m - 0.01 <= p.x <= w - m + 0.01, f"{label}: x={p.x:.2f} out of [{m:.1f},{w-m:.1f}]"
    assert m - 0.01 <= p.y <= h - m + 0.01, f"{label}: y={p.y:.2f} out of [{m:.1f},{h-m:.1f}]"
    print(f"[PASS] {label} wall holds player at ({p.x:.2f}, {p.y:.2f})")


print("=== EDGE RING TESTS COMPLETE: ALL PASSED ===")
