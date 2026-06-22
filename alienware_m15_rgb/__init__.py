# SPDX-License-Identifier: GPL-3.0-or-later
"""Native Linux per-key RGB control for the Alienware m15 R2 keyboard."""
from .driver import Keyboard, KeyboardNotFound, find_keyboard

__version__ = "0.1.0"
__all__ = ["Keyboard", "KeyboardNotFound", "find_keyboard"]
