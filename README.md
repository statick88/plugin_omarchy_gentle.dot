# Gentle Dot for Omarchy

An independent Omarchy 4 / Quickshell bar widget. A left click on the bar
rose toggles the **official Gentle Dot desktop panel**; a right click opens the
owned, compact Gentle Dot chat popup. The popup's header can also open or hide
the official panel. Popup pairing and history are opt-in and read-only by default.

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
3. Left-click the bar rose to open or hide the official Gentle Dot panel. A
   right click toggles the owned chat popup instead. Press Escape or the back
   button to dismiss the popup; focus starts in the composer. The popup's
   header **Open Gentle Dot** control also opens the official panel, and a
   failed native launch produces an actionable tooltip.

## Popup pairing and read-only history

The popup uses active bar foreground colors, a Gentle Dot rose accent, and the system
monospace font. It opens disconnected and never starts a helper, reads a file, or
contacts a backend until the user chooses an absolute local `token` file, checks the
explicit consent control, and selects **Connect**. The default endpoint is
`ws://127.0.0.1:4317/ws`; it is loopback-only. The chosen endpoint, file path, and
consent are held only for the current Quickshell session and cleared by **Disconnect**.
The token value is never placed in QML, configuration, argv, or logs.

After connecting, the popup requests normalized plain-text shared-session history. It
does not send messages, abort streams, change models/accounts/conversations, reconnect,
or start the native app; sending is a later unit. Errors do not replace existing history
with an empty success. Node 24+ must already be available on Quickshell's PATH; a missing
runtime fails closed with an actionable message and the native full-app option remains.

The checked-in preview is a finite isolated Quickshell window with synthetic data only;
it loads the production `Panel.qml` and `BackendController.qml` against the installed
Omarchy SDK and never contacts Gentle Dot:

```sh
python3 tests/popup_preview/run_preview.py
```

`BarWidget.chatController` remains an external seam and defaults to the bundled
controller. It exposes normalized plain-text `messages` as `[{id, role, text}]`,
`connectionState`, `statusText`, `modelLabel`, `streaming`, `canSend`, and `canStop`.
Sending and stopping remain disabled in this read-only stage. Message text is rendered
as plain text, not active markup or resources.

The widget installer stages and validates ten plugin runtime files, including
`BackendController.qml` and the private `scripts/backend_bridge.mjs`; native source,
build output, and caches remain private user-managed state, not plugin payload.
The default and `--app-path` paths do not download, build, install, start, stop or log
into the native app.

## Read-only local bridge (T16)

`scripts/backend_bridge.mjs` is a private JSON-lines stdin/stdout helper used only
after the popup's explicit pairing action.
It never starts the native app or discovers credentials. The controller must first
obtain a human pairing decision, then send exactly one line:

```json
{"command":"connect","consent":true,"url":"ws://127.0.0.1:4317/ws","tokenFile":"/chosen/absolute/token"}
```

Only literal `ws://127.0.0.1:<port>/ws` or `ws://[::1]:<port>/ws` endpoints are
accepted. `tokenFile` must be a user-chosen absolute file named `token`, owned by
the current user, private, regular, and directly within a current-user private
0700 or 0711 directory. The helper opens it read-only without following the final
symlink. Invalid input and missing consent do not read the token or connect.

After a `{"type":"status","state":"connected","modelLabel"?}` response,
the controller may send `{"command":"history"}`. Its only request after the
protocol-v1 hello is `get_history`; its response is
`{"type":"history","history":[{"id","role","text"}]}` with plain,
bounded text. The default history wait is 65 seconds to accommodate native startup;
a caller may instead supply an integer `timeoutMs` greater than zero and no greater
than 65000. A timeout, peer close, send failure, or native `error` frame reports
generic `{"type":"error","message":"Connection unavailable."}`, never an
empty history success. `{"command":"disconnect"}` clears the in-memory
connection and emits disconnected status. Errors are generic and capability values are redacted.
There is no automatic reconnect, replay, account, model, or conversation operation.
The native daemon is one shared session: this helper adds a client and never starts
a fresh daemon.

### Shared write-control helper API (T20)

The popup remains read-only until its later UI unit wires these helper commands. A
connected controller may explicitly grant this process temporary write access:

```json
{"command":"write_access","enabled":true,"consent":true}
```

The helper replies `{"type":"write_access","enabled":true}`. Pairing consent
never grants this access. `{"command":"write_access","enabled":false}` revokes
it immediately, including while a history request is pending; disconnect, a new
connection, peer close, and stdin EOF also revoke it. Revocation does **not** send
an abort frame: Stop affects the daemon's shared current turn and needs its own
explicit confirmation each time.

With active access, a controller can issue exactly one deliberate frame per action:
`{"command":"send","text":"...","consent":true}` maps to native
`{"type":"send","text":"..."}`; blank or oversized text is refused.
`{"command":"abort","confirmed":true}` maps to `{"type":"abort"}`. Any
denied, disconnected, revoked, malformed, or unconfirmed request returns generic
`Request refused.` without a native frame, retry, or queued replay. Sending while
busy can steer the shared run; Stop can interrupt a turn started by another client.

While write access is active, normalized shared daemon broadcasts use
`stream` events for `user_message`, `message_delta`, and replacing
`message_done` text (each includes a bounded `messageId` and text/delta; done may
include `stopped` or generic `error:true`). Known `agent_state` is forwarded;
permission asks become `action_required` directing the user to the full app, and
native errors become generic `model_error`. Unknown/malformed events are ignored.
Read-only mode emits none of these unsolicited stream events. The helper never
answers permissions or performs account, model, session, PIN, or tool approvals.

`node scripts/backend_bridge.mjs --help` documents the command names. Development
coverage uses only a Python-stdlib fake loopback WebSocket and temporary synthetic
tokens:

```sh
PYTHONPATH=tests python3 -m unittest test_backend_bridge
```

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
| `manifest.json`, `BarWidget.qml`, `Panel.qml`, `toggle.sh` | Plugin identity, bar widget, popup presentation and literal native toggle |
| `assets/rose-glyph.svg` | Official monochrome rose, tinted by the bar theme |
| `scripts/install.py`, `scripts/native_install.py` | Explicit plugin installer and guided pinned native-source setup |
| `tests/test_install.py`, `tests/test_popup_ui.py`, `tests/popup_preview/`, `tests/test_native_install.py`, `tests/test_toggle.py`, `tests/test_widget_click.py` | Plugin CLI, isolated synthetic Quickshell popup and bar-widget click regression tests |
| `README.md`, `.gitignore` | Plugin documentation and local-state exclusions |
| `LICENSE`, `LICENSES/gentle-dot-MIT.txt`, `THIRD_PARTY_NOTICES.md` | MIT license and preserved upstream attribution |

The rose is unchanged from upstream revision
`8cb20ee888c88be2b359258a65499c20b59e2a86`; see [third-party notices](THIRD_PARTY_NOTICES.md).
This is not an official Gentle Dot or Omarchy product. Names/marks belong to their
owners; the software license does not grant trademark rights or imply endorsement.

References: [Omarchy plugin development](https://plugins.omarchy.org/develop.html),
[publication](https://plugins.omarchy.org/publish.html),
[Gentle Dot source](https://github.com/Gentleman-Programming/gentle-dot).
