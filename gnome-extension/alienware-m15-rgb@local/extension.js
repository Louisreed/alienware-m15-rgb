// SPDX-License-Identifier: GPL-3.0-or-later
import GObject from 'gi://GObject';
import St from 'gi://St';
import GLib from 'gi://GLib';
import Gio from 'gi://Gio';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import {Slider} from 'resource:///org/gnome/shell/ui/slider.js';

const CLI = 'alienware-m15-rgb';

const Indicator = GObject.registerClass(
class Indicator extends PanelMenu.Button {
    _init() {
        super._init(0.0, 'Alienware m15 RGB');
        this._briTimer = 0;
        this.add_child(new St.Icon({
            icon_name: 'keyboard-brightness-symbolic',
            style_class: 'system-status-icon',
        }));

        this._item('🎨  Match Wallpaper', ['wallpaper']);
        this._item('🌊  Wave', ['effect', 'wave']);
        this._item('💓  Breathing', ['effect', 'breathing']);
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        const presets = new PopupMenu.PopupSubMenuMenuItem('🎨  Solid Colour');
        for (const [name, hex] of [
            ['Alienware Blue', '00AEEF'], ['Red', 'FF1414'], ['Green', '15FF15'],
            ['Purple', 'A020F0'], ['Cyan', '00FFD5'], ['Amber', 'FF9500'], ['White', 'FFFFFF'],
        ]) {
            const it = new PopupMenu.PopupMenuItem(name);
            it.connect('activate', () => this._run(['solid', hex]));
            presets.menu.addMenuItem(it);
        }
        this.menu.addMenuItem(presets);

        const bri = new PopupMenu.PopupBaseMenuItem({activate: false});
        bri.add_child(new St.Icon({icon_name: 'display-brightness-symbolic', style_class: 'popup-menu-icon'}));
        this._slider = new Slider(1.0);
        this._slider.connect('notify::value', () => this._onBrightness());
        bri.add_child(this._slider);
        this.menu.addMenuItem(bri);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this._item('⏻  Off', ['off']);
    }

    _item(label, args) {
        const it = new PopupMenu.PopupMenuItem(label);
        it.connect('activate', () => this._run(args));
        this.menu.addMenuItem(it);
    }

    _onBrightness() {
        if (this._briTimer) GLib.source_remove(this._briTimer);
        this._briTimer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 350, () => {
            this._run(['brightness', String(Math.round(this._slider.value * 100))]);
            this._briTimer = 0;
            return GLib.SOURCE_REMOVE;
        });
    }

    _run(args) {
        // /usr/bin/env resolves the CLI on PATH regardless of install location.
        try {
            Gio.Subprocess.new(['/usr/bin/env', CLI, ...args],
                Gio.SubprocessFlags.STDOUT_SILENCE | Gio.SubprocessFlags.STDERR_SILENCE);
        } catch (e) {
            Main.notify('Alienware m15 RGB', `Failed to run ${CLI}: ${e.message}`);
        }
    }

    destroy() {
        if (this._briTimer) GLib.source_remove(this._briTimer);
        super.destroy();
    }
});

export default class AlienwareRGBExtension extends Extension {
    enable() {
        this._indicator = new Indicator();
        Main.panel.addToStatusArea('alienware-m15-rgb', this._indicator);
    }
    disable() {
        this._indicator?.destroy();
        this._indicator = null;
    }
}
