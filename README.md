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

### Choose the native executable

Automatic lookup prefers executable `$HOME/.local/bin/gentle-dot`, then
`gentle-dot` on the shell's PATH. A broken local link allows PATH lookup.
To override it, back up `~/.config/omarchy/shell.json` and set `appPath` on the
existing widget entry in its current `bar.layout` section, preserving peers:

```json
{"id": "statick.gentle-dot", "appPath": "/absolute/path/to/gentle-dot"}
```

This is one literal executable path: spaces work, but `~`, variables and shell
expressions are not expanded. Empty or omitted `appPath` keeps automatic lookup.
A configured missing, non-executable or directory path fails closed with exit 127
and a tooltip, never falling back. Native failures propagate without retry.
For a direct diagnostic, from the project root:

```sh
/bin/sh toggle.sh /absolute/path/to/gentle-dot
```

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

## Optional project-local native build

For a fresh checkout, prepare official sources manually from the project root
before running the build script (network and build steps are opt-in):

```sh
mkdir -p vendor
git clone https://github.com/Gentleman-Programming/gentle-dot.git vendor/gentle-dot
git -C vendor/gentle-dot checkout --detach 8cb20ee888c88be2b359258a65499c20b59e2a86
# Retain the Rust installer for review; do not execute it yet:
/bin/sh scripts/build-native.sh
# Inspect .gentle-dot-install/rustup-init.sh before explicitly approving execution:
/bin/sh scripts/build-native.sh --build-reviewed-installer
```

If sources already exist, preserve them; do not clone over them. The script
refuses any HEAD other than the pinned revision. It requires Node 24+ and Arch
development libraries listed in upstream `scripts/linux/setup-arch.sh`; do not
run that upstream installer unchanged, because it writes outside this project.
The script prepares local Rust (upstream requires 1.90+) and pnpm 11.5.0, builds
the UI and Tauri artifact with `--no-bundle`, and records runtime/toolchain paths.
It does not install a system package, change shell profiles or launch the app.
Retain both ignored directories, `vendor/gentle-dot` and `.gentle-dot-install`:
the artifact records Node and daemon source paths. The resulting executable is
`vendor/gentle-dot/apps/desktop/src-tauri/target/release/gentle-dot`.
Do not copy vendor dependencies, caches or app data into the plugin folder;
whole-tree validation after a build can reject dependency symlinks.

### Use the prepared launcher

Only after a successful build, explicitly launch with:

```sh
/bin/sh bin/gentle-dot --toggle
```

For bar use, select the executable launcher with your actual absolute project path:

```json
{"id": "statick.gentle-dot", "appPath": "/absolute/path/to/plugin_omarchy_gentle.dot/bin/gentle-dot"}
```

The launcher forwards literal arguments and native exit status; a missing artifact
fails with exit 127 before creating state. It keeps app data at
`.gentle-dot-install/data`, uses recorded `runtime-path` (or local tool paths),
and selects private Engram on port **17438**, which must be free. It does not
replace a global launcher or configure autostart.

The native app/browser retain desktop HOME, XDG config/data/cache/state,
BROWSER, XDG_CURRENT_DESKTOP, XDG_SESSION_TYPE, display and D-Bus variables.
Missing/empty XDG directories default beneath HOME; missing/empty HOME falls
back to `.gentle-dot-install/home` without account-database lookups. Absent
browser/desktop markers stay empty. Values are literal environment arguments.
The allowlist drops inherited provider credentials and agent overrides; it does
not copy credentials or populate desktop configuration directories.

Engine isolation is upstream's responsibility: `packages/daemon/src/isolation.ts`
in the retained source sets engine HOME/XDG under `.gentle-dot-install/data/home`.
Account storage stays under the app data directory (`data/agent/auth.json`).
No accounts, conversations or sessions are moved or deleted. This is **not a
sandbox**: the native app retains desktop D-Bus/Secret Service access. Environment
fixture coverage does not establish OAuth success; login is a separate human action.
See [the historical preparation record](odd/tasks/persistent-gentle-dot.md) for
prior work and its acceptance limits, not additional installation automation.

## Checks and limits

```sh
python3 -m unittest discover -s tests -p 'test_toggle.py' -v
python3 -m unittest discover -s tests -p 'test_build_native.py' -v
python3 -m unittest discover -s tests -p 'test_native_launcher.py' -v
```

Seven isolated fake-executable tests cover literal paths, fail-closed errors,
empty-path lookup, local precedence, broken-link PATH fallback, missing-app
no-mutation and app failure propagation. Two build-script tests check retained
installer preparation and distinct contained npm configs using fake tools.
Five native-launcher tests cover missing-artifact no-mutation, arguments/failure,
recorded PATH/private Engram, desktop variables reaching a fake browser with
credential canaries absent and fixture data unchanged, and HOME/XDG fallbacks
(14 tests total). They do not prove downloads, real builds or automated OAuth.
Prior manual rose open/close passed; a human confirmed OpenAI/Codex linking.
Settings navigation timed out and model replies remain untested. Manually check
theme/orientation and workspace placement separately; do not enter credentials here.

## Official references

- [Omarchy plugin authoring](https://plugins.omarchy.org/develop.html)
- [Omarchy plugin publishing](https://plugins.omarchy.org/publish.html)
- [Gentle Dot source](https://github.com/Gentleman-Programming/gentle-dot)
- [Installation and Linux security limits](https://github.com/Gentleman-Programming/gentle-dot/blob/main/docs/install.md)
- [Linux testing checklist](https://github.com/Gentleman-Programming/gentle-dot/blob/main/docs/linux-testing.md)
