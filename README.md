# Gentle Dot for Omarchy

An independent Omarchy 4 / Quickshell integration that toggles the **official
Gentle Dot desktop panel**. Chat and settings belong to the native app; this
plugin does not implement an assistant, read credentials or connect to a daemon.
It is not an official Gentle Dot or Omarchy product.

## Install the bar widget

Install a working [official native app](https://github.com/Gentleman-Programming/gentle-dot/blob/main/docs/install.md)
first; follow upstream's source-build guide if no package is available. Do not
start a second daemon for this plugin. Requires Omarchy's bar-widget SDK.

From this project's root, copy only these seven files into a **new** plugin
folder. If that destination exists, preserve it and reconcile it before copying;
these commands are not an updater or a backup mechanism.

```sh
mkdir -p "$HOME/.config/omarchy/plugins/statick.gentle-dot/assets" \
  "$HOME/.config/omarchy/plugins/statick.gentle-dot/LICENSES"
cp manifest.json BarWidget.qml toggle.sh LICENSE THIRD_PARTY_NOTICES.md \
  "$HOME/.config/omarchy/plugins/statick.gentle-dot/"
cp assets/rose-glyph.svg "$HOME/.config/omarchy/plugins/statick.gentle-dot/assets/"
cp LICENSES/gentle-dot-MIT.txt "$HOME/.config/omarchy/plugins/statick.gentle-dot/LICENSES/"
omarchy plugin validate "$HOME/.config/omarchy/plugins/statick.gentle-dot"
omarchy plugin enable statick.gentle-dot
```

Use Omarchy's bar settings to place `statick.gentle-dot` on the right if absent;
preserve existing entries. Validate the plugin-only folder, not unrelated sources.
Left-click the rose to pass `--toggle` to the native app. Further clicks are
ignored while its launch process runs. Hover for launch errors; there is no
installation or browser fallback. Chat, settings and accounts stay in Gentle Dot.

### Configure the native launcher

## Brand, license and removal

The unchanged official monochrome rose at pinned upstream revision `8cb20ee` is
tinted with the SDK bar foreground. See [attribution](THIRD_PARTY_NOTICES.md),
[upstream MIT notice](LICENSES/gentle-dot-MIT.txt) and this project's
[MIT license, Copyright 2026 statick](LICENSE). No trademark permission or
endorsement is implied. For placement, use the [official Hyprland rules](https://github.com/Gentleman-Programming/gentle-dot/blob/main/scripts/linux/hyprland/gentle-dot.lua);
this plugin edits neither window rules nor shortcuts.

```sh
omarchy plugin disable statick.gentle-dot
# Optional plugin-file removal:
omarchy plugin remove statick.gentle-dot
```

Removal leaves the native app and all account data intact. This widget does not
hide or alter native tray/floating controls.

## Official references

- [Omarchy plugin authoring](https://plugins.omarchy.org/develop.html)
- [Omarchy plugin publishing](https://plugins.omarchy.org/publish.html)
- [Gentle Dot source](https://github.com/Gentleman-Programming/gentle-dot)
- [Installation and Linux security limits](https://github.com/Gentleman-Programming/gentle-dot/blob/main/docs/install.md)
- [Linux testing checklist](https://github.com/Gentleman-Programming/gentle-dot/blob/main/docs/linux-testing.md)
