"""
Enemy radar / mini-map.

A round radar in the top-right corner. The player is in the centre and the radar
ROTATES with the player, so "up" is always the direction you are facing.
  * red / orange dots = enemies inside RADAR_RANGE (red + pulsing = hunting you)
  * a rotating sweep line makes each dot flash when the sweep passes it
  * nearby walls (grey), trees (green) and pickups (yellow) give you a rough map
  * the ring flashes red when an enemy is closer than ALERT_DIST
  * press M to turn the radar on / off
Enemies outside RADAR_RANGE are NOT shown.
"""
import math
import pygame
from settings import FOV, EMPTY

RADAR_RANGE = 14.0      # tiles: enemies farther away than this are not detected
RADAR_RADIUS = 52       # radar radius in pixels (on the 640x360 internal screen)
RADAR_MARGIN = 12       # distance from the screen edge
ALERT_DIST = 5.0        # ring flashes red when an enemy is this close
HUNTING_STATES = ('stalk', 'attack', 'investigate')


def world_to_radar(dx, dy, angle, rng=RADAR_RANGE, radius=RADAR_RADIUS):
    """World offset (dx, dy) from the player -> radar pixels (x right, y down) from the centre.

    The player faces `angle`; forward is drawn as UP. In this game's raycaster the
    right-hand side of the screen is angle + 90 degrees.
    """
    fx, fy = math.cos(angle), math.sin(angle)
    rx, ry = -math.sin(angle), math.cos(angle)
    forward = dx * fx + dy * fy
    right = dx * rx + dy * ry
    k = radius / rng
    return right * k, -forward * k


class Radar:
    def __init__(self):
        self.enabled = True
        r = RADAR_RADIUS
        self.size = r * 2 + 6
        self.c = self.size // 2
        c = self.c

        # static background (drawn once)
        self.bg = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
        pygame.draw.circle(self.bg, (6, 14, 10, 175), (c, c), r)
        for f in (1 / 3, 2 / 3):
            pygame.draw.circle(self.bg, (40, 95, 62, 130), (c, c), int(r * f), 1)
        pygame.draw.line(self.bg, (40, 95, 62, 110), (c - r, c), (c + r, c), 1)
        pygame.draw.line(self.bg, (40, 95, 62, 110), (c, c - r), (c, c + r), 1)
        half = math.radians(FOV) / 2.0           # field-of-view cone
        for sgn in (-1, 1):
            ex = c + int(math.sin(half) * r * sgn)
            ey = c - int(math.cos(half) * r)
            pygame.draw.line(self.bg, (70, 120, 90, 110), (c, c), (ex, ey), 1)
        pygame.draw.circle(self.bg, (90, 175, 125, 235), (c, c), r, 2)

        self.layer = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
        self.sweep = 0.0
        self.last_count = 0
        self.last_nearest = None

    def toggle(self):
        self.enabled = not self.enabled
        return self.enabled

    def draw(self, surf, player, enemies, game_map, font, t_ms):
        if not self.enabled:
            return
        r, c = RADAR_RADIUS, self.c
        px, py, ang = player.x, player.y, player.angle
        layer = self.layer
        layer.fill((0, 0, 0, 0))
        self.sweep = (t_ms * 0.0022) % (2 * math.pi)
        edge2 = (r - 2) ** 2

        # nearby walls (grey) - cheap: only cells inside the radar square
        x_lo = max(0, int(px - RADAR_RANGE))
        x_hi = min(game_map.width, int(px + RADAR_RANGE) + 2)
        y_lo = max(0, int(py - RADAR_RANGE))
        y_hi = min(game_map.height, int(py + RADAR_RANGE) + 2)
        for gy in range(y_lo, y_hi):
            row = game_map.grid[gy]
            for gx in range(x_lo, x_hi):
                if row[gx] != EMPTY:
                    ox, oy = world_to_radar(gx + 0.5 - px, gy + 0.5 - py, ang)
                    if ox * ox + oy * oy <= edge2:
                        pygame.draw.rect(layer, (95, 110, 100, 190),
                                         (c + int(ox) - 1, c + int(oy) - 1, 2, 2))

        # trees (dark green dots)
        for t in game_map.trees_near(px, py, RADAR_RANGE):
            dx, dy = t['x'] - px, t['y'] - py
            if dx * dx + dy * dy > RADAR_RANGE * RADAR_RANGE:
                continue
            ox, oy = world_to_radar(dx, dy, ang)
            if ox * ox + oy * oy <= edge2:
                layer.set_at((c + int(ox), c + int(oy)), (50, 140, 70, 230))

        # pickups (yellow dots)
        for p in getattr(game_map, 'pickups', []):
            if not p.get('active', True):
                continue
            dx, dy = p['x'] - px, p['y'] - py
            if dx * dx + dy * dy > RADAR_RANGE * RADAR_RANGE:
                continue
            ox, oy = world_to_radar(dx, dy, ang)
            pygame.draw.circle(layer, (235, 205, 70, 230), (c + int(ox), c + int(oy)), 1)

        # sweep line with a fading trail
        for i in range(7):
            a = self.sweep - i * 0.07
            ex = c + int(math.sin(a) * r)
            ey = c - int(math.cos(a) * r)
            pygame.draw.line(layer, (80, 230, 130, max(0, 150 - i * 22)), (c, c), (ex, ey), 1)

        # enemies inside the detection range
        count = 0
        nearest = None
        for e in enemies:
            if not getattr(e, 'alive', True):
                continue
            dx, dy = e.x - px, e.y - py
            dist = math.hypot(dx, dy)
            if dist > RADAR_RANGE:
                continue
            count += 1
            if nearest is None or dist < nearest:
                nearest = dist
            ox, oy = world_to_radar(dx, dy, ang)
            blip_angle = math.atan2(ox, -oy)                    # clockwise from "up"
            since_sweep = (self.sweep - blip_angle) % (2 * math.pi)
            glow = max(0.0, 1.0 - since_sweep / (math.pi * 1.4))
            pulse = 0.5 + 0.5 * math.sin(t_ms * 0.009 + (id(e) % 17))
            hunting = getattr(e, 'state', '') in HUNTING_STATES
            base = (255, 45, 45) if hunting else (235, 140, 45)
            k = 0.5 + 0.5 * glow
            col = (int(base[0] * k), int(base[1] * k), int(base[2] * k), 255)
            rad = 3 if dist > ALERT_DIST else 4
            if hunting:
                rad += int(pulse * 1.5)
            pos = (c + int(ox), c + int(oy))
            pygame.draw.circle(layer, (base[0], base[1], base[2], int(70 + 90 * glow)), pos, rad + 3, 1)
            pygame.draw.circle(layer, col, pos, rad)

        # player marker (triangle pointing up)
        pygame.draw.polygon(layer, (235, 235, 255, 255), [(c, c - 5), (c - 4, c + 4), (c + 4, c + 4)])

        # alert ring when an enemy is very close
        if nearest is not None and nearest < ALERT_DIST:
            pulse = 0.5 + 0.5 * math.sin(t_ms * 0.012)
            pygame.draw.circle(layer, (255, 40, 40, int(110 + 130 * pulse)), (c, c), r, 3)

        self.last_count = count
        self.last_nearest = nearest

        x = surf.get_width() - self.size - RADAR_MARGIN
        y = RADAR_MARGIN
        surf.blit(self.bg, (x, y))
        surf.blit(layer, (x, y))

        label = f"ENEMIES {count}"
        if nearest is not None:
            label += f"  NEAR {nearest:.0f}m"
            col = (255, 90, 90) if nearest < ALERT_DIST else (230, 200, 160)
        else:
            col = (140, 200, 160)
        txt = font.render(label, True, col)
        surf.blit(txt, (x + self.size // 2 - txt.get_width() // 2, y + self.size + 2))
