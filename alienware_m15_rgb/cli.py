# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Louis Reed
"""Command-line interface: ``alienware-m15-rgb``."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

from .driver import Keyboard, KeyboardNotFound
from . import colors

STATE = os.path.join(
    os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")),
    "alienware-m15-rgb", "state.json",
)

# Named firmware effects -> (eff_type, default colours). Best-effort; see PROTOCOL.md.
EFFECTS = {
    "wave":       (0x03, (255, 0, 0), (0, 0, 255)),
    "dual-wave":  (0x04, (255, 0, 255), (0, 255, 255)),
    "breathing":  (0x02, (255, 0, 0), (0, 0, 0)),
    "pulse":      (0x08, (255, 0, 0), (0, 0, 255)),
    "night-rider":(0x0A, (255, 0, 0), (0, 0, 0)),
}


def _hex(s: str) -> tuple[int, int, int]:
    s = s.lstrip("#")
    return tuple(int(s[i : i + 2], 16) for i in (0, 2, 4))


def _save_state(d: dict) -> None:
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(d, open(STATE, "w"))


def _load_state() -> dict:
    try:
        return json.load(open(STATE))
    except (OSError, ValueError):
        return {}


def _current_wallpaper() -> str | None:
    for key in ("picture-uri-dark", "picture-uri"):
        try:
            uri = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.background", key],
                capture_output=True, text=True,
            ).stdout.strip().strip("'")
        except FileNotFoundError:
            return None
        if uri and uri != "''":
            return uri[7:] if uri.startswith("file://") else uri
    return None


def _scale(c: tuple[int, int, int], pct: int) -> tuple[int, int, int]:
    p = max(0, min(100, pct)) / 100.0
    return tuple(int(x * p) for x in c)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="alienware-m15-rgb",
                                description="Control the Alienware m15 R2 per-key RGB keyboard.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("solid", help="set all keys to one colour")
    s.add_argument("color", help="hex, e.g. FF0000")
    sub.add_parser("off", help="turn keys off")
    g = sub.add_parser("grid", help="spread colours across the keyboard in bands")
    g.add_argument("colors", help="comma-separated hex list, e.g. FF0000,00FF00,0000FF")
    w = sub.add_parser("wallpaper", help="match the current desktop wallpaper")
    w.add_argument("--mode", choices=["gradient", "dominant"], default="gradient")
    w.add_argument("--image", help="use this image instead of the live wallpaper")
    e = sub.add_parser("effect", help="run a firmware effect")
    e.add_argument("name", choices=sorted(EFFECTS))
    e.add_argument("--tempo", type=int, default=4)
    b = sub.add_parser("brightness", help="scale the last colour(s) by a percentage")
    b.add_argument("percent", type=int)
    sub.add_parser("detect", help="print the keyboard's hidraw device path")

    args = p.parse_args(argv)

    try:
        if args.cmd == "detect":
            from .driver import find_keyboard
            dev = find_keyboard()
            print(dev or "not found")
            return 0 if dev else 1

        kb = Keyboard()
    except KeyboardNotFound as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except PermissionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 13

    if args.cmd == "solid":
        c = _hex(args.color)
        kb.set_solid(*c)
        _save_state({"mode": "solid", "colors": ["%02X%02X%02X" % c], "brightness": 100})
    elif args.cmd == "off":
        kb.off()
    elif args.cmd == "grid":
        cols = [_hex(x) for x in args.colors.split(",")]
        kb.set_grid(cols)
        _save_state({"mode": "grid", "colors": ["%02X%02X%02X" % c for c in cols], "brightness": 100})
    elif args.cmd == "wallpaper":
        img = args.image or _current_wallpaper()
        if not img or not os.path.exists(img):
            print(f"error: wallpaper image not found: {img}", file=sys.stderr)
            return 1
        if args.mode == "dominant":
            c = colors.dominant_color(img)
            kb.set_solid(*c)
            _save_state({"mode": "solid", "colors": ["%02X%02X%02X" % c], "brightness": 100})
        else:
            cols = colors.theme_colors(img, 4)
            kb.set_grid(cols)
            _save_state({"mode": "grid", "colors": ["%02X%02X%02X" % c for c in cols], "brightness": 100})
        print("matched:", img)
    elif args.cmd == "effect":
        et, c1, c2 = EFFECTS[args.name]
        kb.set_effect(et, args.tempo, c1, c2)
    elif args.cmd == "brightness":
        st = _load_state()
        cols = [_scale(_hex(c), args.percent) for c in st.get("colors", [])]
        if st.get("mode") == "solid" and cols:
            kb.set_solid(*cols[0])
        elif st.get("mode") == "grid" and cols:
            kb.set_grid(cols)
        st["brightness"] = args.percent
        _save_state(st)

    return 0


if __name__ == "__main__":
    sys.exit(main())
