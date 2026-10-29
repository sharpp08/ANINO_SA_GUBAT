"""
Navigation pathfinding for enemy AI. Uses A* on a grid derived from the map.
"""
import math
import heapq
from settings import EMPTY, DOOR, WALL_STONE, WATER


class NavGrid:
    """A* pathfinding on a grid mapped from the game map."""

    def __init__(self, game_map, cell_size=1.0):
        self.gm = game_map
        self.cell_size = cell_size
        self.width = game_map.width
        self.height = game_map.height

    def _cell(self, x, y):
        return int(x / self.cell_size), int(y / self.cell_size)

    def _world(self, cx, cy):
        return (cx + 0.5) * self.cell_size, (cy + 0.5) * self.cell_size

    def is_walkable(self, wx, wy, radius=0.3):
        cx, cy = self._cell(wx, wy)
        if not (0 <= cx < self.width and 0 <= cy < self.height):
            return False
        tile = self.gm.grid[cy][cx]
        if tile == WALL_STONE:
            return False
        if tile == DOOR:
            return False
        if tile == WATER:
            return True
        return not self.gm.is_tree_solid(wx, wy, radius=radius)

    def heuristic(self, a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def find_path(self, start, end, max_steps=500):
        sc = self._cell(*start)
        ec = self._cell(*end)
        if not (0 <= sc[0] < self.width and 0 <= sc[1] < self.height):
            return None
        if not (0 <= ec[0] < self.width and 0 <= ec[1] < self.height):
            return None
        if not self.is_walkable(*start) or not self.is_walkable(*end):
            return None

        open_set = [(0, sc)]
        came_from = {}
        g_score = {sc: 0}
        visited = set()

        while open_set:
            f, cur = heapq.heappop(open_set)
            if cur in visited:
                continue
            visited.add(cur)

            if cur == ec:
                path = []
                while cur in came_from:
                    path.append(self._world(*cur))
                    cur = came_from[cur]
                path.append(start)
                path.reverse()
                return path

            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nb = (cur[0] + dx, cur[1] + dy)
                if nb in visited:
                    continue
                if not (0 <= nb[0] < self.width and 0 <= nb[1] < self.height):
                    continue
                nx, ny = self._world(*nb)
                if not self.is_walkable(nx, ny):
                    continue
                cost = 1.5 if self.gm.grid[nb[1]][nb[0]] == WATER else 1.0
                tg = g_score[cur] + cost
                if tg < g_score.get(nb, float('inf')):
                    came_from[nb] = cur
                    g_score[nb] = tg
                    heapq.heappush(open_set, (tg + self.heuristic(nb, ec), nb))

            if len(visited) > max_steps:
                break
        return None

    def get_tile_at(self, x, y):
        cx, cy = self._cell(x, y)
        if 0 <= cx < self.width and 0 <= cy < self.height:
            return self.gm.grid[cy][cx]
        return EMPTY