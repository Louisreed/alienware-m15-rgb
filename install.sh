#!/usr/bin/env bash
# Installer for alienware-m15-rgb: Python package (user), udev rule (root),
# and optionally the GNOME top-bar extension.
set -euo pipefail
cd "$(dirname "$0")"

echo "==> Installing the Python package (user)…"
python3 -m pip install --user .

echo "==> Installing udev rule (needs sudo)…"
sudo install -m 0644 udev/99-alienware-m15-rgb.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=hidraw || true

if command -v gnome-shell >/dev/null 2>&1; then
    read -r -p "==> Install the GNOME top-bar extension too? [y/N] " ans
    if [[ "${ans,,}" == y* ]]; then
        dest="$HOME/.local/share/gnome-shell/extensions"
        mkdir -p "$dest"
        cp -r gnome-extension/alienware-m15-rgb@local "$dest/"
        echo "    Installed. Enable with: gnome-extensions enable alienware-m15-rgb@local"
        echo "    (log out and back in first)"
    fi
fi

echo
echo "Done. If 'alienware-m15-rgb' isn't found, add ~/.local/bin to PATH."
echo "Log out/in once so the udev uaccess ACL applies, then try:"
echo "    alienware-m15-rgb solid 00AEEF"
