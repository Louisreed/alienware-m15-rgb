# Alienware m15 R2 keyboard RGB — protocol notes

Reverse-engineered from the device's HID report descriptor and the open-source
[T-Troll/AlienFX-SDK](https://github.com/T-Troll/AlienFX-SDK) ("API_V5" path).

## Two separate lighting controllers

The m15 R2 splits lighting across **two** USB devices:

| Function | USB ID | Notes |
|---|---|---|
| **Per-key keyboard** | `0d62:0a1c` (Darfon) | API_V5, vendor HID **feature** reports. |
| **Chassis**: power button, lid alien-head, rear strip | `187c:0550` (Alienware AW-ELC) | API_V4, **output** reports. |

Both are supported by this project. OpenRGB/AlienFX only ever bind the AW-ELC
(and unreliably), which is why the keys never changed for anyone — the keys are
on the *other* controller entirely.

## Chassis controller (AW-ELC `187c:0550`, API_V4)

Report descriptor: Usage Page `0xFF00`, a 33-byte **OUTPUT** report, no report
id → on Linux send 34-byte `write()`s (`buf[0]=0` report id). Determined as
API_V4 by the SDK's 34-byte output-length rule.

| Step | Bytes (after report id 0) |
|---|---|
| Reset | `03 21 00 04 00 ff` then `03 21 00 01 00 ff` |
| Set colour | `03 27` + `[r, g, b, 00, count, id0, id1, …]` |
| Update | `03 21 00 03 00 ff` |

Light ids `0..15` cover the lid alien-head and rear strip via `setOneColor`.

### The power button is special

The front power-button light is a **power-state light** (id **2** on the m15 R2)
— its colour is stored per power state, and the normal `setOneColor` does *not*
change it. It must be programmed with the `setPower` command (`03 22`) for each
state id `0x5b..0x60` (AC/battery × sleep/power, charge, critical):

```
setPower  03 22 00 04 00 <cid>     # init state
setPower  03 22 00 01 00 <cid>
colorSel  03 23 01 00 01 <lightid>
colorSet  03 24 00 <type 0> 00 d0 00 fa <r> <g> <b>
setPower  03 22 00 02 00 <cid>     # end state
...repeat per cid...
commit    03 21 00 05 00 ff
```

This driver programs the awake states (`0x5c` AC, `0x5d` charge, `0x5f` battery)
so the button tracks the chosen colour whenever the machine is in use.

## The keyboard's HID interface

From `/sys/class/hidraw/hidrawN/device/report_descriptor`:

```
06 89 ff    Usage Page (Vendor 0xFF89)
09 cc       Usage (0xCC)            ← RGB control collection
a1 01       Collection (Application)
85 cc         Report ID (0xCC)
75 08 95 3f   Report Size 8, Report Count 0x3f (63)
b1 00         Feature (Data,Var,Abs)
c0          End Collection
```

So: a **FEATURE report**, Report ID `0xCC`, 63 data bytes → 64 bytes total on
the wire. On Linux this is sent with the `HIDIOCSFEATURE` ioctl on the matching
`hidraw` node (status is read back with `HIDIOCGFEATURE`).

There is also a small `09 10` / Report ID `0x5a` vendor collection and the
standard boot-keyboard collection on the same interface; ignore those.

## Report framing

Every report is 64 bytes: `[0xCC] [payload …] [0x00 padding …]`. Byte 0 is the
HID report id (`0xCC`); the command starts at byte 1.

## Command set (API_V5)

| Name | Bytes (after report id) | Purpose |
|---|---|---|
| Reset | `94` | begin a command sequence / stop the running effect |
| Status | `93` | query; readback byte[2] is the device state |
| Custom mode | `80 01 fe 00 00 01 01 01` | select custom-colour theme (**required**) |
| ColorSet | `8c 02 00` + `[id+1, R, G, B]…` | colour blocks, start at byte 4, step 4 (≤15/report) |
| Loop | `8c 13` | end of a colour batch |
| Update | `8b 01 ff` | commit / latch |
| Effect | `80 <type> <tempo> 00 00 01 01 01 <nc-1> <r1 g1 b1> <r2 g2 b2>` | firmware animation |

### Setting per-key colours

```
Reset                                   cc 94
Custom mode                             cc 80 01 fe 00 00 01 01 01
Update                                  cc 8b 01 ff
Reset                                   cc 94
ColorSet (repeat for >15 keys)          cc 8c 02 00  [id+1,R,G,B] × n
Loop                                    cc 8c 13
Update                                  cc 8b 01 ff
```

**The "Custom mode" step is essential.** Without it, `Reset` merely freezes the
firmware rainbow and the per-key colour buffer is never displayed. With it, the
keys obey `ColorSet`.

Light IDs are sent as `id + 1`. Keys appear to occupy a contiguous low ID range;
this driver simply writes ids `0..159` (unused ids are ignored by the firmware).
A physical key-id → position map is still TODO (PRs welcome) — until then,
`grid` spreads colours by id order, which approximates left-to-right.

### Effect types (`80 <type> …`)

`0` color · `2` breathing · `3` single-colour wave · `4` dual-colour wave ·
`8` pulse · `9` mix pulse · `a` night-rider · `b` laser. (From AlienFX-SDK
comments; treat as best-effort.)

## Transport reference (Linux)

```python
import fcntl
def _ioc(d,t,nr,sz): return (d<<30)|(sz<<16)|(t<<8)|nr
HIDIOCSFEATURE = lambda n: _ioc(3, ord('H'), 0x06, n)   # write|read
buf = bytearray(64); buf[0] = 0xCC; buf[1] = 0x94       # Reset
fcntl.ioctl(fd, HIDIOCSFEATURE(64), buf, True)
```
