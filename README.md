# Gentle Dot for Omarchy

An independent Omarchy 4 / Quickshell bar widget that opens or hides the
**official Gentle Dot desktop panel**. Chat and settings remain in the native app.
The plugin does not implement another assistant or read account credentials.

## Install

1. Install a working [Gentle Dot desktop app](https://github.com/Gentleman-Programming/gentle-dot/blob/main/docs/install.md).
   Native installation/build is an external prerequisite, not part of this plugin.
2. Clone the plugin:

   ```sh
   git clone https://github.com/statick88/plugin_omarchy_gentle.dot.git
   cd plugin_omarchy_gentle.dot
   ```

3. With Gentle Dot **already running** and its tray menu available, explicitly install:

   ```sh
   python3 scripts/install.py --app-path /absolute/path/to/gentle-dot
   # Or preserve an existing appPath / use local-bin then PATH lookup:
   python3 scripts/install.py
   ```

   Requires Python 3 (stdlib only), `busctl`, `omarchy`, a running `omarchy-shell`,
   and a valid version-1 `~/.config/omarchy/shell.json` with all three layout sections.
   Use `python3 scripts/install.py --help` for options. Marketplace installation
   does not run this setup command or arbitrary hooks.
4. Left-click the bar rose to toggle the native panel. A failed launcher produces
   an actionable tooltip; repeated clicks are ignored while launch is running.

The explicit installer stages and validates only seven runtime files: manifest,
QML, toggle script, rose SVG and three license/notice files. It does not download,
build, install, start, stop or log into the native application, and requires no sudo.

## One visible rose, safely

The installer preserves existing widget placement/settings and `appPath` unless
explicitly overridden; a new widget is added on the right. It identifies the native
app by exact title and menu shape, rejects shared IDs, invokes only its official
**Hide the rose** action and verifies **Show the rose**. It adds only that native ID
to existing tray widgets' `hidden` arrays, preserving peers/pins; it never adds a tray.
The native ID is generic: current collision checks cannot prevent a future app
from reusing it. Inspect the hidden list if another icon later disappears.

Changed config is backed up to a unique `shell.json.bak.gentle-dot.*` beside the
original, with owner-only permissions. Existing identical plugin files are untouched;
edited/unexpected files and unsafe symlinks are rejected instead of overwritten.
Concurrent config changes are checked before replacement; this is not a shared lock,
so avoid simultaneous settings edits. Account and conversation data is untouched.

Pending shell synchronization is stored privately beside `shell.json` in
`.gentle-dot-pending` before payload/config writes. After a rescan/reload failure,
restore shell availability and rerun: pending operations run before native hiding,
without rewriting completed files/backups. The marker is removed only after
successful synchronization. Invalid/symlinked markers are rejected for inspection.
A repeat after successful installation makes no writes, backups, reloads or clicks.

| Exit | Meaning |
| --- | --- |
| `0` | Installed or already configured |
| `1` | Preflight rejection; inspect the reported prerequisite |
| `2` | Partial installation/external failure; inspect error and backup, then retry/reconcile |

Automatic rollback is not promised, including when failed creation/write/close
attempts may already have left files or directories.

## Choose the native launcher

Set `appPath` on the existing `statick.gentle-dot` entry in any bar section of
`~/.config/omarchy/shell.json`, preserving other settings:

```json
{"id": "statick.gentle-dot", "appPath": "/absolute/path/to/gentle-dot"}
```

This is one literal argv path, not a shell expression. Spaces are supported;
`~` and variables are not expanded. Empty/omitted `appPath` tries the executable
`~/.local/bin/gentle-dot`, then `gentle-dot` on PATH. Only `--toggle` is passed.
Missing/broken configured paths fail with exit 127; app failures are propagated
without fallback or retry. Direct use: `/bin/sh toggle.sh /absolute/native/launcher`.

## Disable or remove

```sh
omarchy plugin disable statick.gentle-dot
omarchy plugin remove statick.gentle-dot
```

These commands do not restore native visibility. Remove **only** Gentle Dot's ID
from existing tray `hidden` arrays (compare the installer backup), preserving peer
IDs/pins/layout; never replace the whole config with an old backup. Choose **Show
the rose** in the native tray menu if wanted. If no tray was present, use the native
app's supported controls. Leave native accounts and app data intact.

## Verify the plugin

```sh
python3 -m unittest discover -s tests -v
omarchy plugin validate .
```

Tests use isolated fake desktop/native commands; they do not initiate login,
send model messages or install on the live desktop. Plugin validation is not a
security audit: community plugins run unsandboxed and require source inspection.

## Files and license

| Files | Purpose |
| --- | --- |
| `manifest.json`, `BarWidget.qml`, `toggle.sh` | Plugin identity, bar widget and literal native toggle |
| `assets/rose-glyph.svg` | Official monochrome rose, tinted by the bar theme |
| `scripts/install.py` | Explicit plugin-only single-rose installer |
| `tests/test_install.py`, `tests/test_toggle.py` | Plugin CLI regression tests |
| `README.md`, `.gitignore` | Plugin documentation and local-state exclusions |
| `LICENSE`, `LICENSES/gentle-dot-MIT.txt`, `THIRD_PARTY_NOTICES.md` | MIT license and preserved upstream attribution |

The rose is unchanged from upstream revision
`8cb20ee888c88be2b359258a65499c20b59e2a86`; see [third-party notices](THIRD_PARTY_NOTICES.md).
This is not an official Gentle Dot or Omarchy product. Names/marks belong to their
owners; the software license does not grant trademark rights or imply endorsement.

References: [Omarchy plugin development](https://plugins.omarchy.org/develop.html),
[publication](https://plugins.omarchy.org/publish.html),
[Gentle Dot source](https://github.com/Gentleman-Programming/gentle-dot).
