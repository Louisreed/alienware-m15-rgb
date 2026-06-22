# alienware-m15-rgb

**Native Linux per-key RGB control for the Alienware m15 R2 keyboard** — no
Windows, no Alienware Command Center, no proprietary daemon.

The m15 R2's per-key keyboard is driven by a Darfon controller (`0d62:0a1c`)
that **OpenRGB, AlienFX, and AKBL do not control** — OpenRGB only sees the
separate chassis controller (`187c:0550`). This project speaks the keyboard's
actual protocol directly over `hidraw`, so you can finally set its colours from
Linux.

> Protocol reverse-engineered from the device's own HID report descriptor and
> the open-source [T-Troll/AlienFX-SDK](https://github.com/T-Troll/AlienFX-SDK)
> (AlienFX "API_V5"). Full write-up in [`docs/PROTOCOL.md`](docs/PROTOCOL.md).

## Features

- Control **both** lighting controllers, kept in sync:
  - **Per-key keyboard** (Darfon, API_V5)
  - **Chassis** — power button, lid alien-head, rear light strip (AW-ELC, API_V4)
- Solid colour, palette across the keyboard, or **match your desktop wallpaper**
- Firmware effects (wave, breathing, pulse, …)
- Brightness scaling
- `--target keyboard|chassis|both` to scope commands
- Optional **GNOME top-bar menu** to drive it all
- Pure stdlib Python + `hidraw` — no C, no daemon, no external libs

## Supported hardware

| Device | USB ID | Status |
|---|---|---|
| Alienware m15 R2 per-key keyboard (Darfon) | `0d62:0a1c` | ✅ tested |
| Alienware m15 R2 chassis lights (AW-ELC) | `187c:0550` | ✅ tested |

Other Alienware notebooks using the same Darfon "API_V5" keyboard (vendor HID
Usage `0xCC`, Report ID `0xCC`) are likely compatible — please open an issue
with the output of `alienware-m15-rgb detect` and `lsusb` if you try one.

## Install

### From PyPI
```bash
pip install --user alienware-m15-rgb
# then install the udev rule for non-root access (see below)
```

### From source / git
```bash
git clone https://github.com/Louisreed/alienware-m15-rgb
cd alienware-m15-rgb
./install.sh
```

### udev rule (for non-root access)
```bash
sudo cp udev/99-alienware-m15-rgb.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
# log out and back in once so the uaccess ACL applies
```

`wallpaper` matching needs **ImageMagick** (`magick`/`convert`) for image
decoding (handles JPEG-XL, PNG, JPG, …).

## Usage

```bash
alienware-m15-rgb solid 00AEEF           # whole keyboard Alienware-blue
alienware-m15-rgb grid FF0000,00FF00,0000FF,FFFF00
alienware-m15-rgb wallpaper              # match the desktop wallpaper (gradient)
alienware-m15-rgb wallpaper --mode dominant
alienware-m15-rgb effect wave            # firmware wave animation
alienware-m15-rgb brightness 40          # dim the current colours to 40%
alienware-m15-rgb off
alienware-m15-rgb detect                 # print the keyboard's hidraw node
```

As a library:
```python
from alienware_m15_rgb import Keyboard
with Keyboard() as kb:
    kb.set_solid(0xFF, 0x14, 0x14)
```

## GNOME top-bar menu (optional)

```bash
cp -r gnome-extension/alienware-m15-rgb@local \
   ~/.local/share/gnome-shell/extensions/
gnome-extensions enable alienware-m15-rgb@local   # then log out/in
```

## How it works (short version)

The keyboard exposes a vendor HID collection (Usage Page `0xFF89`, Usage `0xCC`)
with a 63-byte **feature** report (Report ID `0xCC`). Colours are set by issuing
a sequence of `HIDIOCSFEATURE` reports:

```
Reset        cc 94
Custom mode  cc 80 01 fe 00 00 01 01 01     ← required, or colours are ignored
ColorSet     cc 8c 02 00  [keyID+1, R, G, B] × up to 15
Loop         cc 8c 13
Update       cc 8b 01 ff
```

See [`docs/PROTOCOL.md`](docs/PROTOCOL.md) for the complete reverse-engineering.

## Credits

- [T-Troll/AlienFX-SDK](https://github.com/T-Troll/AlienFX-SDK) and the wider
  AlienFX-Tools project — the protocol reference that made this possible.
- [OpenRGB](https://openrgb.org) — for the broader Alienware/Dell device map.

## License

[GPL-3.0-or-later](LICENSE). This is an independent interoperability
implementation; it ships no proprietary code.

## Disclaimer

Not affiliated with or endorsed by Dell/Alienware. Use at your own risk.
