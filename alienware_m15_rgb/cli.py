# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Louis Reed
"""Command-line interface: ``alienware-m15-rgb``.

Drives both lighting controllers — the per-key keyboard (V5) and the chassis
power button / lid head / rear strip (V4) — keeping them in sync with the chosen
colour. Use --target to limit to one.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

from .driver import Keyboard, Chassis, KeyboardNotFound
from . import colors

STATE = os.path.join(
    os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")),
    "alienware-m15-rgb", "state.json",
)

EFFECTS = {
    "wave":        (0x03, (255, 0, 0), (0, 0, 255)),
    "dual-wave":   (0x04, (255, 0, 255), (0, 255, 255)),
    "breathing":   (0x02, (255, 0, 0), (0, 0, 0)),
    "pulse":       (0x08, (255, 0, 0), (0, 0, 255)),
    "night-rider": (0x0A, (255, 0, 0), (0, 0, 0)),
}


def _hex(s):
    s = s.lstrip("#")
    return tuple(int(s[i : i + 2], 16) for i in (0, 2, 4))


def _hx(c):
    return "%02X%02X%02X" % tuple(c)


def _save_state(d):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(d, open(STATE, "w"))


def _load_state():
    try:
        return json.load(open(STATE))
    except (OSError, ValueError):
        return {}


def _current_wallpaper():
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


def _scale(c, pct):
    p = max(0, min(100, pct)) / 100.0
    return tuple(int(x * p) for x in c)


def _open(target):
    """Open the requested controllers that are actually present.

    Returns (keyboard_or_None, chassis_or_None). Missing/denied devices are
    skipped with a warning rather than aborting — so the tool still works if you
    only have one of the two controllers.
    """
    kb = ch = None
    if target in ("both", "keyboard"):
        try:
            kb = Keyboard()
        except (KeyboardNotFound, PermissionError) as exc:
            if target == "keyboard":
                print(f"error: {exc}", file=sys.stderr)
            else:
                print(f"note: keyboard unavailable ({exc})", file=sys.stderr)
    if target in ("both", "chassis"):
        try:
            ch = Chassis()
        except (KeyboardNotFound, PermissionError) as exc:
            if target == "chassis":
                print(f"error: {exc}", file=sys.stderr)
            else:
                print(f"note: chassis unavailable ({exc})", file=sys.stderr)
    return kb, ch


def main(argv=None):
    p = argparse.ArgumentParser(prog="alienware-m15-rgb",
                                description="Control Alienware m15 R2 RGB (keyboard + chassis).")
    p.add_argument("--target", choices=["both", "keyboard", "chassis"], default="both",
                   help="which controller(s) to drive (default: both)")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("solid"); s.add_argument("color")
    sub.add_parser("off")
    g = sub.add_parser("grid"); g.add_argument("colors")
    w = sub.add_parser("wallpaper")
    w.add_argument("--mode", choices=["gradient", "dominant"], default="gradient")
    w.add_argument("--image")
    e = sub.add_parser("effect"); e.add_argument("name", choices=sorted(EFFECTS)); e.add_argument("--tempo", type=int, default=4)
    b = sub.add_parser("brightness"); b.add_argument("percent", type=int)
    sub.add_parser("detect")
    args = p.parse_args(argv)

    if args.cmd == "detect":
        from .driver import find_keyboard, find_chassis
        print("keyboard:", find_keyboard() or "not found")
        print("chassis: ", find_chassis() or "not found")
        return 0

    kb, ch = _open(args.target)
    if kb is None and ch is None:
        return 2

    if args.cmd == "solid":
        c = _hex(args.color)
        if kb: kb.set_solid(*c)
        if ch: ch.set_solid(*c)
        _save_state({"mode": "solid", "colors": [_hx(c)], "brightness": 100})

    elif args.cmd == "off":
        if kb: kb.off()
        if ch: ch.off()

    elif args.cmd == "grid":
        cols = [_hex(x) for x in args.colors.split(",")]
        if kb: kb.set_grid(cols)
        if ch: ch.set_solid(*cols[0])           # chassis: lead colour
        _save_state({"mode": "grid", "colors": [_hx(c) for c in cols], "brightness": 100})

    elif args.cmd == "wallpaper":
        img = args.image or _current_wallpaper()
        if not img or not os.path.exists(img):
            print(f"error: wallpaper image not found: {img}", file=sys.stderr)
            return 1
        if args.mode == "dominant":
            c = colors.dominant_color(img)
            if kb: kb.set_solid(*c)
            if ch: ch.set_solid(*c)
            _save_state({"mode": "solid", "colors": [_hx(c)], "brightness": 100})
        else:
            cols = colors.theme_colors(img, 4)
            if kb: kb.set_grid(cols)
            if ch: ch.set_solid(*cols[0])       # chassis tracks the dominant theme colour
            _save_state({"mode": "grid", "colors": [_hx(c) for c in cols], "brightness": 100})
        print("matched:", img)

    elif args.cmd == "effect":
        et, c1, c2 = EFFECTS[args.name]
        if kb: kb.set_effect(et, args.tempo, c1, c2)
        if ch:
            # The chassis controller has no firmware animations, so during an
            # effect we set it to the current theme's lead colour (the last
            # wallpaper/solid choice) rather than leaving it stuck.
            lead = _load_state().get("colors") or ["00AEEF"]   # fallback: Alienware blue
            ch.set_solid(*_hex(lead[0]))

    elif args.cmd == "brightness":
        st = _load_state()
        cols = [_scale(_hex(c), args.percent) for c in st.get("colors", [])]
        if cols:
            if st.get("mode") == "grid":
                if kb: kb.set_grid(cols)
            else:
                if kb: kb.set_solid(*cols[0])
            if ch: ch.set_solid(*cols[0])
        st["brightness"] = args.percent
        _save_state(st)

    return 0


if __name__ == "__main__":
    sys.exit(main())
