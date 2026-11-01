"""Generate a directional arrow graphic that points at open Bible pages.

Written asset: assets/sprites/bible_page_arrow.png  (master, glow baked in)
Frames:        assets/sprites/bible_page_arrow_f0..f3.png  (pulsing glow animation)
Also written:  assets/sprites/bible_page_arrow_base.png   (crisp arrow, no glow)

The arrow is golden/amber with a soft radial glow so it reads clearly on
parchment-tone pages in the horror game: it arcs from the top-right and its
head aims down-left into the page text, pulling the viewer's eye toward it.

Run with the project venv:
    .venv\\Scripts\\python tools/make_bible_arrow.py
"""
from __future__ import annotations

import math
from pathlib import Path

import pygame

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / "assets" / "sprites"

# Warm gold/amber palette -- high contrast against parchment & dark horror tones.
GLOW_RGB = (176, 128, 48)
OUTLINE_RGB = (96, 64, 12)
SHAFT_RGB = (247, 210, 112)
HEAD_RGB = (255, 224, 138)
HIGHLIGHT_RGB = (255, 246, 214)

CANVAS = 480

# Quadratic bezier giving the shaft its gentle "guide the eye" sweep.
P0 = (204, 84)     # tail (upper right of the frame)
PC = (244, 268)    # control point (swings toward the right edge)
P2 = (124, 364)    # end of the shaft (lower left)
TIP = (50, 426)    # arrowhead tip: points down-left into the page text
HEAD_WIDTH = 130
SHAFT_WIDTH = 30
BACK_DEPTH = 100


def quad_points(n: int = 48):
    pts = []
    for i in range(n + 1):
        t = i / n
        u = 1.0 - t
        x = u * u * P0[0] + 2 * u * t * PC[0] + t * t * P2[0]
        y = u * u * P0[1] + 2 * u * t * PC[1] + t * t * P2[1]
        pts.append((int(round(x)), int(round(y))))
    return pts


def head_polygon() -> list[tuple[int, int]]:
    """Triangle: back-center + two wings around the tip."""
    dx, dy = P2[0] - PC[0], P2[1] - PC[1]
    length = math.hypot(dx, dy)
    dx, dy = dx / length, dy / length
    px, py = -dy, dx  # unit perpendicular
    bx, by = TIP[0] - dx * BACK_DEPTH, TIP[1] - dy * BACK_DEPTH
    wing = HEAD_WIDTH / 2.0
    return [
        (int(bx + px * wing), int(by + py * wing)),
        TIP,
        (int(bx - px * wing), int(by - py * wing)),
        (int(bx), int(by)),
    ]


def draw_arrow_base(canvas: int) -> pygame.Surface:
    pygame.init()
    base = pygame.Surface((canvas, canvas), pygame.SRCALPHA)
    pts = quad_points()

    # Shaft (slightly rounded ends read cleaner).
    pygame.draw.polygon(base, SHAFT_RGB, pts)
    for c in (pts[0], pts[-1]):
        pygame.draw.circle(base, SHAFT_RGB, c, SHAFT_WIDTH // 2)

    # Arrowhead.
    pygame.draw.polygon(base, HEAD_RGB, head_polygon())

    # Crisp specular streak along the upper edge of the shaft.
    stroke = [
        (int(p[0] - 6), int(p[1]) - SHAFT_WIDTH // 2 + 7)
        for p in pts[2:-2]
    ]
    pygame.draw.polygon(base, (*HIGHLIGHT_RGB, 64), stroke)

    pygame.quit()
    return base


def with_glow(base: pygame.Surface, canvas: int, intensity: float = 1.0) -> pygame.Surface:
    """Compose glow + outlined arrow on a 64-bit (premultiplied) surface.

    Drawing straight-alpha colors onto a 64-bit surface premultiplies them
    automatically, so BLEND_RGBA_ADD compositing stays numerically clean.
    """
    glow = pygame.Surface((canvas, canvas), pygame.SRCALPHA | pygame.DOUBLEBUF)
    pts = quad_points()
    offsets = [
        (26, 26, 8),
        (22, 22, 10),
        (18, 18, 14),
        (12, 12, 22),
        (6, 6, 34),
        (0, 0, 52),
    ]
    for off, w, a in offsets:
        o = int(round(a * intensity))
        if o <= 0:
            continue
        color = (*GLOW_RGB, o)
        pygame.draw.polygon(glow, color, [(p[0] + off, p[1] + off) for p in pts])
        for c in (pts[0], pts[-1]):
            pygame.draw.circle(glow, color, (c[0] + off, c[1] + off), w + off // 2)
        pygame.draw.polygon(glow, color, [(p[0] + off, p[1] + off) for p in head_polygon()])

    outlined = base.copy()
    for off in (13, 9, 6, 4, 2, 0):
        color = (*OUTLINE_RGB, 92 if off < 10 else 48)
        p2 = [(p[0] + off, p[1] + off) for p in pts]
        pygame.draw.polygon(outlined, color, p2)
        for c in (pts[0], pts[-1]):
            pygame.draw.circle(outlined, color, (c[0] + off, c[1] + off), SHAFT_WIDTH // 2 + off // 2)
        pygame.draw.polygon(outlined, color, [(p[0] + off, p[1] + off) for p in head_polygon()])

    canvas_s = pygame.Surface((canvas, canvas), pygame.SRCALPHA | pygame.DOUBLEBUF)
    canvas_s.blit(glow, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
    canvas_s.blit(outlined, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
    return canvas_s


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base = draw_arrow_base(CANVAS)
    master = with_glow(base, CANVAS, intensity=1.0)

    def save(surf: pygame.Surface, name: str) -> None:
        path = OUT_DIR / name
        pygame.image.save(surf, str(path))
        print(f"  wrote {path} ({surf.get_size()[0]}x{surf.get_size()[1]})")

    print("Generating Bible-page arrow assets...")
    save(base, "bible_page_arrow_base.png")
    save(master, "bible_page_arrow.png")

    pygame.init()
    import numpy as np

    for i, (alpha, glow_i) in enumerate(((255, 1.0), (170, 0.66), (110, 0.43), (170, 0.66))):
        frame = with_glow(base, CANVAS, intensity=glow_i)
        if alpha < 255:
            # breathe: dim the whole frame (glow + arrow) on pulse frames.
            # (BLEND_RGBA_MULT corrupts unpremultiplied RGB, so scale manually.)
            w, h = frame.get_size()
            px = np.frombuffer(
                pygame.image.tobytes(frame, "RGBA"), dtype=np.uint8
            ).reshape(h, w, 4).astype(np.uint32)
            px = (px * alpha // 255).astype(np.uint8)
            frame = pygame.image.fromstring(px.tobytes(), (w, h), "RGBA")
        save(frame, f"bible_page_arrow_f{i}.png")
    pygame.quit()
    print("Done.")


if __name__ == "__main__":
    main()
