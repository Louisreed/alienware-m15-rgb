# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Louis Reed
"""Extract a vibrant theme palette from an image (e.g. the desktop wallpaper).

Decoding is delegated to ImageMagick (``magick``/``convert``), which handles
JPEG-XL, PNG, JPG, WebP, etc., so there is no hard dependency on Pillow.
"""
from __future__ import annotations

import colorsys
import re
import shutil
import subprocess

Color = tuple[int, int, int]


def _magick() -> str | None:
    return shutil.which("magick") or shutil.which("convert")


def extract_palette(path: str, n_colors: int = 14) -> list[dict]:
    binary = _magick()
    if not binary:
        raise RuntimeError("ImageMagick not found (install 'ImageMagick')")
    out = subprocess.run(
        [binary, path, "-resize", "200x200", "-depth", "8",
         "-colors", str(n_colors), "-format", "%c", "histogram:info:-"],
        capture_output=True, text=True,
    ).stdout
    rows = []
    for line in out.splitlines():
        m = re.search(r"\s*(\d+):.*#([0-9A-Fa-f]{6})", line)
        if not m:
            continue
        count, hexc = int(m.group(1)), m.group(2).upper()
        r, g, b = (int(hexc[i : i + 2], 16) for i in (0, 2, 4))
        _, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        rows.append({"count": count, "rgb": (r, g, b), "s": s, "v": v})
    return rows


def _dist(a: Color, b: Color) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def theme_colors(path: str, n: int = 4) -> list[Color]:
    """Pick ``n`` distinct, vibrant colours (frequency x saturation x value)."""
    rows = extract_palette(path)
    if not rows:
        return [(255, 255, 255)] * n
    rows.sort(key=lambda c: c["count"] * (0.25 + c["s"]) * (0.25 + c["v"]), reverse=True)
    picked: list[Color] = []
    for c in rows:
        if all(_dist(c["rgb"], p) > 60 for p in picked):
            picked.append(c["rgb"])
        if len(picked) == n:
            break
    i = 0
    while len(picked) < n and rows:
        picked.append(rows[i % len(rows)]["rgb"])
        i += 1
    return picked


def dominant_color(path: str) -> Color:
    return theme_colors(path, 1)[0]
