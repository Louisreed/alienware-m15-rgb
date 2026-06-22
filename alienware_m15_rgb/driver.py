# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Louis Reed
"""
Native Linux driver for the Alienware m15 R2 per-key RGB keyboard.

Hardware: Darfon keyboard controller, USB ``0d62:0a1c``, exposing a vendor HID
collection (Usage Page 0xFF89, Usage 0xCC) with Report ID 0xCC and a 63-byte
FEATURE report.

The control protocol is "AlienFX API_V5", reverse-engineered from the device's
own HID report descriptor and the open-source T-Troll/AlienFX-SDK. See
``docs/PROTOCOL.md`` for the full write-up. Transport is a HID SET_FEATURE
report (64 bytes including the report id) issued via the Linux ``hidraw``
``HIDIOCSFEATURE`` ioctl, so no external daemon or library is required.
"""
from __future__ import annotations

import fcntl
import glob
import os
import sys
import time

REPORT_ID = 0xCC
REPORT_LEN = 64          # 1 report-id byte + 63 data bytes
DEFAULT_VID = 0x0D62
DEFAULT_PID = 0x0A1C
MAX_LIGHT_ID = 160       # blast the whole plausible key-id range


# --- hidraw ioctl numbers (asm-generic encoding) ---
def _ioc(direction: int, typ: int, nr: int, size: int) -> int:
    return (direction << 30) | (size << 16) | (typ << 8) | nr


def _HIDIOCSFEATURE(size: int) -> int:
    return _ioc(3, ord("H"), 0x06, size)   # dir = write|read


def _HIDIOCGFEATURE(size: int) -> int:
    return _ioc(3, ord("H"), 0x07, size)


def find_keyboard(vid: int = DEFAULT_VID, pid: int = DEFAULT_PID) -> str | None:
    """Return the /dev/hidrawN node for the keyboard's RGB collection.

    Matches the vendor/product id *and* verifies the report descriptor contains
    the vendor RGB collection (Usage 0xCC, Report ID 0xCC), so we never grab the
    plain keyboard-input interface by mistake.
    """
    for path in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        try:
            uevent = open(os.path.join(path, "device", "uevent")).read().upper()
        except OSError:
            continue
        if f"{vid:04X}" not in uevent or f"{pid:04X}" not in uevent:
            continue
        try:
            rdesc = open(os.path.join(path, "device", "report_descriptor"), "rb").read()
        except OSError:
            continue
        if b"\x09\xcc" in rdesc and b"\x85\xcc" in rdesc:  # Usage 0xCC + Report ID 0xCC
            return "/dev/" + os.path.basename(path)
    return None


class KeyboardNotFound(RuntimeError):
    pass


class Keyboard:
    """Control object for the per-key RGB keyboard."""

    def __init__(self, device: str | None = None):
        self.device = device or find_keyboard()
        if not self.device:
            raise KeyboardNotFound(
                "Alienware RGB keyboard (Darfon 0d62:0a1c, HID Usage 0xCC) not found"
            )
        try:
            self.fd = os.open(self.device, os.O_RDWR)
        except PermissionError as exc:
            raise PermissionError(
                f"{self.device}: permission denied. Install the udev rule "
                f"(udev/99-alienware-m15-rgb.rules) and re-login, or run as root."
            ) from exc

    def close(self) -> None:
        if getattr(self, "fd", None) is not None:
            os.close(self.fd)
            self.fd = None

    def __enter__(self) -> "Keyboard":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # --- raw protocol primitives -------------------------------------------
    def _set_feature(self, *data: int) -> None:
        buf = bytearray(REPORT_LEN)
        buf[0] = REPORT_ID
        buf[1 : 1 + len(data)] = bytes(data)
        fcntl.ioctl(self.fd, _HIDIOCSFEATURE(REPORT_LEN), buf, True)

    def _get_status(self) -> int | None:
        self._set_feature(0x93)                       # COMMV5_status
        buf = bytearray(REPORT_LEN)
        buf[0] = REPORT_ID
        try:
            fcntl.ioctl(self.fd, _HIDIOCGFEATURE(REPORT_LEN), buf, True)
            return buf[2]
        except OSError:
            return None

    def _reset(self) -> None:
        self._set_feature(0x94)                       # COMMV5_reset
        self._get_status()
        time.sleep(0.005)

    def _custom_mode(self) -> None:
        """Switch the keyboard to custom-colour theme.

        Essential: without this the reset merely freezes the firmware animation
        and per-key colours are ignored.
        """
        self._reset()
        self._set_feature(0x80, 0x01, 0xFE, 0x00, 0x00, 0x01, 0x01, 0x01)
        self._set_feature(0x8B, 0x01, 0xFF)           # update
        time.sleep(0.02)

    def _color_blocks(self, items) -> None:
        """items: iterable of (light_id, r, g, b). 15 blocks per ColorSet."""
        items = list(items)
        for i in range(0, len(items), 15):
            payload = [0x8C, 0x02, 0x00]              # COMMV5_colorSet (+pad)
            for lid, r, g, b in items[i : i + 15]:
                payload += [(lid + 1) & 0xFF, r, g, b]
            self._set_feature(*payload)

    def _loop(self) -> None:
        self._set_feature(0x8C, 0x13)                 # COMMV5_loop

    def _update(self) -> None:
        self._set_feature(0x8B, 0x01, 0xFF)           # COMMV5_update

    # --- high-level API -----------------------------------------------------
    def set_solid(self, r: int, g: int, b: int, max_id: int = MAX_LIGHT_ID) -> None:
        """Set every key to a single colour."""
        self._custom_mode()
        self._reset()
        self._color_blocks((i, r, g, b) for i in range(max_id))
        self._loop()
        self._update()

    def off(self) -> None:
        self.set_solid(0, 0, 0)

    def set_grid(self, colors, max_id: int = MAX_LIGHT_ID) -> None:
        """Spread a list of (r, g, b) tuples across the keys in equal bands."""
        colors = list(colors)
        if not colors:
            return
        self._custom_mode()
        self._reset()
        band = max(1, max_id // len(colors))
        items = []
        for i in range(max_id):
            r, g, b = colors[min(i // band, len(colors) - 1)]
            items.append((i, r, g, b))
        self._color_blocks(items)
        self._loop()
        self._update()

    def set_effect(self, eff_type: int, tempo: int, c1, c2, n_colors: int = 2) -> None:
        """Run a firmware effect (wave/pulse/etc). eff_type per docs/PROTOCOL.md."""
        self._reset()
        self._set_feature(
            0x80, eff_type, tempo, 0x00, 0x00, 0x01, 0x01, 0x01,
            (n_colors - 1) & 0xFF, c1[0], c1[1], c1[2], c2[0], c2[1], c2[2],
        )
        self._update()


# ---------------------------------------------------------------------------
# Chassis controller: power button, lid alien-head, rear light strip.
# Alienware AW-ELC, USB 187c:0550, AlienFX "API_V4". 34-byte OUTPUT reports
# (report id 0) sent via write(). See docs/PROTOCOL.md.
# ---------------------------------------------------------------------------
CHASSIS_VID = 0x187C
CHASSIS_PID = 0x0550
CHASSIS_REPORT_LEN = 34
CHASSIS_LIGHT_IDS = tuple(range(16))   # covers power button, lid head, strip


def find_chassis(vid: int = CHASSIS_VID, pid: int = CHASSIS_PID) -> str | None:
    for path in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        try:
            uevent = open(os.path.join(path, "device", "uevent")).read().upper()
        except OSError:
            continue
        if f"{vid:04X}" in uevent and f"{pid:04X}" in uevent:
            return "/dev/" + os.path.basename(path)
    return None


class Chassis:
    """Control object for the AW-ELC chassis lighting (API_V4)."""

    def __init__(self, device: str | None = None):
        self.device = device or find_chassis()
        if not self.device:
            raise KeyboardNotFound("Alienware chassis controller (187c:0550) not found")
        try:
            self.fd = os.open(self.device, os.O_RDWR)
        except PermissionError as exc:
            raise PermissionError(
                f"{self.device}: permission denied. Install the udev rule and re-login."
            ) from exc

    def close(self) -> None:
        if getattr(self, "fd", None) is not None:
            os.close(self.fd)
            self.fd = None

    def __enter__(self) -> "Chassis":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _out(self, payload, mods=None) -> None:
        buf = bytearray(CHASSIS_REPORT_LEN)        # buf[0] = 0 (report id)
        buf[1 : 1 + len(payload)] = bytes(payload)
        if mods:
            for off, vals in mods:
                buf[off : off + len(vals)] = bytes(vals)
        os.write(self.fd, bytes(buf))
        time.sleep(0.005)

    def _reset(self) -> None:
        self._out([0x03, 0x21, 0x00, 0x03, 0x00, 0xFF], [(4, [4])])  # COMMV4_control
        self._out([0x03, 0x21, 0x00, 0x03, 0x00, 0xFF], [(4, [1])])

    def _update(self) -> None:
        self._out([0x03, 0x21, 0x00, 0x03, 0x00, 0xFF])

    def set_lights(self, ids, r: int, g: int, b: int) -> None:
        ids = list(ids)
        self._reset()
        self._out([0x03, 0x27], [(3, [r, g, b, 0, len(ids)] + ids)])  # COMMV4_setOneColor
        self._update()

    def set_solid(self, r: int, g: int, b: int) -> None:
        self.set_lights(CHASSIS_LIGHT_IDS, r, g, b)

    def off(self) -> None:
        self.set_solid(0, 0, 0)
