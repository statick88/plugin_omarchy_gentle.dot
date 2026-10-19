# Gentle Dot for Omarchy

An independent Omarchy 4 / Quickshell bar widget with an owned, compact Gentle
Dot chat popup. The popup is presentation-only for now: it does not implement an
assistant, contact a backend, or read account credentials. Its header can still open
or hide the **official Gentle Dot desktop panel** for the existing full app.

## Install

1. Clone the plugin:

   ```sh
   git clone https://github.com/statick88/plugin_omarchy_gentle.dot.git
   cd plugin_omarchy_gentle.dot
   ```

2. Either build the official native app through the guided Omarchy-only path, or use an existing launcher:

   ```sh
   # Shows missing Arch build dependencies and asks before installing them.
   python3 scripts/install.py --install-native
   # Build the exact source revision without starting it or changing shell.json.
   python3 scripts/install.py --install-native --no-launch
   # Existing native launcher:
   python3 scripts/install.py --app-path /absolute/path/to/gentle-dot
   ```

   Native setup retains the official `https://github.com/Gentleman-Programming/gentle-dot.git`
   checkout at revision `8cb20ee888c88be2b359258a65499c20b59e2a86` under
   `~/.local/share/gentle-dot-omarchy/<revision>/source`; it does not copy a binary
   then discard runtime resources. It verifies origin, the full commit and a clean
   source tree, then uses `pnpm install --frozen-lockfile`, `pnpm build`, and
   `pnpm --filter @gentle-dot/desktop tauri build --no-bundle`.
   It lists only missing Arch libraries/build tools before asking permission for
   `sudo pacman -S --needed`. Node >=24 and Rust >=1.90 are required; pnpm 11.5.0 is
   installed under the private setup directory, not globally. Approved Arch packages
   may be added, but setup never performs a full/partial system upgrade, executes
   `curl | sh`, runs rustup or edits shell profiles. `--no-launch` builds only;
   it does not start the app or integrate the widget.

   A native setup lock rejects concurrent runs. A private successful-build record
   verifies the executable digest before reuse; retries retain source/resources and
   do not rebuild a completed artifact. Do not delete this source directory while
   its launcher is configured. Lock and partial-state errors require inspection,
   not automatic deletion or a force reinstall.

   Full setup first preserves a valid existing configured/automatic launcher; it
   does not replace that installation or its account locations. It starts the chosen
   app only when explicitly requested and not already publicly ready, waits for its
   tray identity, then integrates the plugin. Desktop HOME/XDG/browser locations are
   preserved; only allowlisted desktop variables reach the launched app, not inherited
   token/auth/agent overrides. Build caches/configuration use the managed setup area. Requires Python 3
   (stdlib only), `busctl`, `omarchy`, a running `omarchy-shell`,
   and a valid version-1 `~/.config/omarchy/shell.json` with all three layout sections.
   Use `python3 scripts/install.py --help` for options. Marketplace installation
   does not run this setup command or arbitrary hooks.
3. Left-click the bar rose to toggle the chat popup. Press Escape or the back button
   to dismiss it; focus starts in the composer. The header's **Open Gentle Dot**
   control preserves the native-panel toggle, and a failed native launch produces an
   actionable tooltip.

## Popup state and next backend unit

The popup uses active bar foreground colors, a Gentle Dot rose accent, and the system
monospace font. It intentionally contains no production conversation data while
connection is unavailable. The checked-in preview is a finite isolated Quickshell window with synthetic data only;
it loads the production `Panel.qml` against the installed Omarchy SDK and never contacts
Gentle Dot:

```sh
python3 tests/popup_preview/run_preview.py
```

T12 may inject one small controller object into `BarWidget.chatController` (and the
popup's `chatController`) with these properties: `messages` as normalized plain-text
`[{id, role, text}]`, `connectionState`, `statusText`, `modelLabel`, `streaming`,
`canSend`, and `canStop`. It provides `send(text)` and `abort()`. Missing or
disconnected controllers disable send/stop and retain the explanatory status; no
session, model, account, retry, or message is created by this UI. Message text is
rendered as plain text, not active markup or resources.

The widget installer stages and validates only eight plugin runtime files: manifest,
the bar and popup QML, toggle script, rose SVG and three license/notice files. Native
source, build output, and caches remain private user-managed state, not plugin payload.
The default and `--app-path` paths do not download, build, install, start, stop or log
into the native app.

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
| `0` | Installed/already configured, or native build-only completed with `--no-launch` |
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
| `manifest.json`, `BarWidget.qml`, `Panel.qml`, `toggle.sh` | Plugin identity, popup-enabled bar widget, popup presentation and literal native toggle |
| `assets/rose-glyph.svg` | Official monochrome rose, tinted by the bar theme |
| `scripts/install.py`, `scripts/native_install.py` | Explicit plugin installer and guided pinned native-source setup |
| `tests/test_install.py`, `tests/test_popup_ui.py`, `tests/popup_preview/`, `tests/test_native_install.py`, `tests/test_toggle.py` | Plugin CLI and isolated synthetic Quickshell popup regression tests |
| `README.md`, `.gitignore` | Plugin documentation and local-state exclusions |
| `LICENSE`, `LICENSES/gentle-dot-MIT.txt`, `THIRD_PARTY_NOTICES.md` | MIT license and preserved upstream attribution |

The rose is unchanged from upstream revision
`8cb20ee888c88be2b359258a65499c20b59e2a86`; see [third-party notices](THIRD_PARTY_NOTICES.md).
This is not an official Gentle Dot or Omarchy product. Names/marks belong to their
owners; the software license does not grant trademark rights or imply endorsement.

References: [Omarchy plugin development](https://plugins.omarchy.org/develop.html),
[publication](https://plugins.omarchy.org/publish.html),
[Gentle Dot source](https://github.com/Gentleman-Programming/gentle-dot).
