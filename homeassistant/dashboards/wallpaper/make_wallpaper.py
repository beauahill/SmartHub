#!/usr/bin/env python3
"""Render the counter dashboard wallpaper: a dark mesh gradient, 1920x1200 (the tablet in landscape).

    python3 homeassistant/dashboards/wallpaper/make_wallpaper.py [out.png]

Soft colour glows on a deep blue-black base, with a faint grain so the gradients don't band.
homeassistant/scripts/set_wallpaper.py uploads the result to Home Assistant's image store and
points every view's background at it; push_dashboard.py then publishes the change.
"""

import math
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter

W, H = 1920, 1200
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).with_name("counter_wallpaper.png"))

# Base: very dark navy, a touch brighter at the top where the navigation badges sit.
TOP, BOTTOM = (14, 18, 30), (8, 10, 18)
# Glows: centre x, centre y (fractions of the canvas), radius, colour, strength.
GLOWS = [
    (0.12, 0.18, 0.55, (20, 120, 150), 0.70),  # teal, top-left behind the clock
    (0.88, 0.22, 0.50, (100, 65, 185), 0.60),  # indigo, top-right
    (0.55, 0.95, 0.60, (180, 95, 40), 0.40),  # warm amber, bottom centre
    (0.35, 0.60, 0.45, (30, 65, 130), 0.45),  # blue, centre-left
]
SCALE = 8  # glows are rendered small, blurred, then upscaled


def base_gradient() -> Image.Image:
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        t = y / (H - 1)
        c = tuple(int(TOP[i] * (1 - t) + BOTTOM[i] * t) for i in range(3))
        for x in range(W):
            px[x, y] = c
    return img


def glow_layer() -> Image.Image:
    w, h = W // SCALE, H // SCALE
    layer = Image.new("RGB", (w, h), (0, 0, 0))
    px = layer.load()
    for cx, cy, r, col, k in GLOWS:
        for y in range(h):
            for x in range(w):
                d = math.hypot(x / w - cx, (y / h - cy) * (H / W))
                a = max(0.0, 1 - d / r) ** 2 * k
                if a:
                    o = px[x, y]
                    px[x, y] = tuple(min(255, int(o[i] + col[i] * a)) for i in range(3))
    return layer.filter(ImageFilter.GaussianBlur(14)).resize((W, H), Image.BICUBIC)


def grain(img: Image.Image, sigma: float = 6.0) -> Image.Image:
    """Add faint monochrome noise. effect_noise is centred on 128, so shift it to centre on 0."""
    noise = Image.effect_noise((W, H), sigma).convert("RGB")
    grey = Image.new("RGB", (W, H), (128, 128, 128))
    return ImageChops.add(img, ImageChops.subtract(noise, grey, 1, 0), 1, 0)


def main() -> None:
    img = ImageChops.add(base_gradient(), glow_layer())
    img = grain(img)
    img.save(OUT, optimize=True)
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
