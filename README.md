# Gentle Dot for Omarchy

A small Omarchy 4 / Quickshell plugin that opens or hides the **official Gentle Dot desktop panel**. Chat and settings stay in the native application; this plugin does not implement another assistant, read credentials, or connect to the daemon.

This is an independent integration, not an official Gentle Dot plugin.

## Use it

1. Install a working [Gentle Dot desktop app](https://github.com/Gentleman-Programming/gentle-dot/blob/main/docs/install.md). The upstream README currently says there are no published releases; follow its source-build instructions if a package is unavailable. Do not run a second daemon for this plugin.
2. From this project's root, run the launcher tests:

   ```sh
   python3 -m unittest discover -s tests -v
   ```

   Validate the plugin-only destination in step 3. Do not validate this whole working tree after a native build: `vendor/` contains dependency symlinks that Omarchy correctly rejects in distributable plugins.

3. With the native app **already running** and its tray menu available, explicitly install one visible rose:

   ```sh
   python3 scripts/install.py --app-path /absolute/path/to/gentle-dot
   # Or preserve an existing appPath / use local-bin then PATH lookup:
   python3 scripts/install.py
   ```

   Requires Python 3 (stdlib only), `busctl`, `omarchy`, a running `omarchy-shell`,
   and a valid version-1 `~/.config/omarchy/shell.json` with all three layout sections.
   Use `--help` for options. Quote launcher paths containing spaces; they are literal
   paths, not shell commands. The installer never executes the launcher.

   This is a separate explicit command: Omarchy marketplace installation does not
   run hooks. Only seven plugin files (manifest, QML, toggle script, rose SVG and
   three license/notice files) are staged, validated and installed. No native app,
   vendor dependencies, runtime or account data is installed or modified. Nothing
   is downloaded, started, stopped or logged into; no sudo or restart is used.

   The installer preserves existing widget placement/settings and `appPath` unless
   explicitly overridden. Otherwise it adds the widget on the right. It uses the
   official native **Hide the rose** menu event and verifies **Show the rose**, and
   adds only the identified native ID to existing tray widgets' `hidden` arrays.
   Peers, pins and other hidden IDs remain unchanged; an absent tray is not added.
   Exact title + official menu checks must identify one native item, with no other
   item sharing its ID. The menu must contain one Open, one Quit and one Hide/Show
   action; other native actions and unlabeled separators are allowed, never clicked.
   A generic ID alone is never trusted; collisions or missing
   metadata reject installation before changes. This check cannot prevent a future
   app from reusing that ID: inspect the tray's hidden list if other icons disappear.

   After a completed installation, repeating the command in the same state does
   not copy, back up, reload or click again. Pending shell synchronization is saved
   privately beside `shell.json` in `.gentle-dot-pending` before payload/config writes.
   If rescan/reload fails, restore shell availability and rerun: pending operations
   run again before native hiding, without rewriting installed files or backups.
   The marker is removed only after successful synchronization; malformed or
   symlinked markers are rejected for inspection, never followed or silently reset.
   Changed config is backed up beside `shell.json` to a unique
   `shell.json.bak.gentle-dot.*` path, printed by the command and created with
   owner-only permissions (0600, further restricted by umask). Identical installed
   files are untouched; edited or unexpected destination files are refused, not
   silently updated (preserve/remove that copy yourself before reinstalling).
   Unsafe symlinks and invalid config are rejected. Concurrent config changes are
   checked before atomic replacement, but this is not a lock shared by other writers;
   avoid simultaneous settings edits. Exit 1 means preflight rejection; exit 2 means
   a partial installation/external failure, including failed creation/write/close
   attempts that may leave files or directories: inspect the printed error and backup,
   then retry or reconcile the related settings. No automatic rollback is promised.

4. Left-click the **rose** in the bar. The official app's `--toggle` shows or hides its panel. Open chat and configuration within that panel. If launch fails, hover over the button for the error. The button ignores additional clicks while its launch process is running.

### Configure the native launcher

## Brand and license

The bar uses the official monochrome Gentle Dot rose, unchanged from the pinned
upstream revision, tinted with the SDK bar foreground rather than a fixed
palette or font. See [third-party attribution](THIRD_PARTY_NOTICES.md) and the
[preserved upstream MIT notice](LICENSES/gentle-dot-MIT.txt). This independent
integration is MIT licensed under [Copyright 2026 statick](LICENSE); use of the
rose does not imply official affiliation or trademark permission.

For floating/pinned placement on Hyprland, use the [official Lua rules](https://github.com/Gentleman-Programming/gentle-dot/blob/main/scripts/linux/hyprland/gentle-dot.lua). Match the shortcut command to your actual app location. This plugin does not edit window rules or keyboard shortcuts.

### Disable or remove safely

```sh
omarchy plugin disable statick.gentle-dot
# Optionally remove plugin files using the public command:
omarchy plugin remove statick.gentle-dot
```

These commands do not restore native visibility. To return to the native controls,
remove **only** Gentle Dot's ID from each existing `omarchy.tray` entry's `hidden`
array in `~/.config/omarchy/shell.json` (compare the printed installer backup).
Preserve peer IDs, pins and all other settings; do not replace the entire config
with an old backup. Then choose **Show the rose** in the native tray menu if wanted.
Leave the app and its account data intact. If the tray was already absent, use the
native app's supported controls to restore visibility; the installer never adds a tray.

## Files

| File | Purpose |
| --- | --- |
| `manifest.json` | Omarchy plugin identity and bar entrypoint |
| `BarWidget.qml` | Theme-aware bar button, launch process, error tooltip |
| `toggle.sh` | Resolve the official app and execute `--toggle` |
| `tests/test_toggle.py` | Isolated plugin launcher tests with fake executables; no account or real daemon |
| `scripts/install.py` | Explicit plugin-only, single-rose installer with config backup |
| `tests/test_install.py` | Isolated installer CLI checks; no real desktop or account calls |

## Official references

- [Official Omarchy plugin authoring guide](https://plugins.omarchy.org/develop.html)
- [Official Omarchy plugin publishing guide](https://plugins.omarchy.org/publish.html)
- [Gentle Dot README](https://github.com/Gentleman-Programming/gentle-dot)
- [Installation and Linux security limits](https://github.com/Gentleman-Programming/gentle-dot/blob/main/docs/install.md)
- [Linux / Omarchy testing checklist](https://github.com/Gentleman-Programming/gentle-dot/blob/main/docs/linux-testing.md)
- Local SDK: `/usr/share/omarchy/shell/README.md` and `/usr/share/omarchy/shell/Ui/` (read-only).
