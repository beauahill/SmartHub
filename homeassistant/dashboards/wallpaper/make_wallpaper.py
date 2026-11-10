#!/usr/bin/env python3
"""Render the counter dashboard wallpaper: a soft mesh gradient, 1920x1200 (the tablet in landscape).

    python3 homeassistant/dashboards/wallpaper/make_wallpaper.py [out.png]

Nine colours on a 3x3 grid, blended by distance: deep blue on the left where the title sits,
indigo through the middle, plum on the right and a warm glow in the bottom right corner. It stays
dark enough for white type, and colourful enough that the dashboard's glass tiles read as glass.
A faint grain keeps the gradients from banding.

homeassistant/scripts/set_wallpaper.py uploads the result to Home Assistant's image store and
points the dashboard at it; push_dashboard.py then publishes the change. The dock in the Counter
Home app paints the same right-hand edge colours (DOCK_EDGE in Dock.kt), so if you change the
palette here, change it there too.
"""

import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter

W, H = 1920, 1200
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).with_name("counter_wallpaper.png"))

# Mesh points: x, y (fractions of the canvas) and colour.
MESH = [
    (0.0, 0.0, "#0b5a8a"), (0.5, 0.0, "#1f4f9e"), (1.0, 0.0, "#4a3aa0"),
    (0.0, 0.5, "#0a3a6e"), (0.5, 0.5, "#263a86"), (1.0, 0.5, "#7a3f8f"),
    (0.0, 1.0, "#0a1c40"), (0.5, 1.0, "#3a2f6e"), (1.0, 1.0, "#d9775a"),
]
BRIGHTNESS = 0.9   # overall level; lower is darker
SHARPNESS = 2.2    # how tightly each colour holds its corner
GRAIN = 3.0        # sigma of the noise, in 8-bit levels
SCALE = 10         # the mesh is rendered small, then scaled up and blurred


def rgb(colour: str) -> tuple[int, int, int]:
    colour = colour.lstrip("#")
    return tuple(int(colour[i : i + 2], 16) for i in (0, 2, 4))


def mesh() -> Image.Image:
    points = [(x, y, rgb(c)) for x, y, c in MESH]
    w, h = W // SCALE, H // SCALE
    img = Image.new("RGB", (w, h))
    px = img.load()
    aspect = H / W
    for j in range(h):
        for i in range(w):
            u, v = i / (w - 1), j / (h - 1)
            total = 0.0
            acc = [0.0, 0.0, 0.0]
            for x, y, colour in points:
                weight = 1.0 / ((u - x) ** 2 + ((v - y) * aspect) ** 2 + 0.004) ** SHARPNESS
                total += weight
                for k in range(3):
                    acc[k] += weight * colour[k]
            px[i, j] = tuple(int(BRIGHTNESS * acc[k] / total) for k in range(3))
    return img.resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(40))


def grain(img: Image.Image) -> Image.Image:
    """Add faint monochrome noise. effect_noise is centred on 128, so apply both halves around it."""
    noise = Image.effect_noise((W, H), GRAIN).convert("RGB")
    grey = Image.new("RGB", (W, H), (128, 128, 128))
    img = ImageChops.add(img, ImageChops.subtract(noise, grey, 1, 0), 1, 0)
    return ImageChops.subtract(img, ImageChops.subtract(grey, noise, 1, 0), 1, 0)


def main() -> None:
    smooth = mesh()
    grain(smooth).save(OUT, optimize=True)
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")
    # The colours down the right-hand edge, for the dock in the Counter Home app.
    edge = [smooth.getpixel((W - 40, int(t * (H - 1)))) for t in (0, 0.2, 0.4, 0.6, 0.8, 1)]
    print("right edge, top to bottom: " + " ".join("#%02x%02x%02x" % c for c in edge))


if __name__ == "__main__":
    main()
