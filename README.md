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

By default the plugin uses an executable `$HOME/.local/bin/gentle-dot` first, then `gentle-dot` from the shell's `PATH` (including packaged installations at `/usr/bin` in a normal session). It passes only `--toggle` and preserves the app's exit status. A missing or broken launcher produces an error; it does not install software or start a browser fallback.

### Select the prepared native launcher

Set `appPath` inline on the existing `statick.gentle-dot` entry in
`bar.layout.right` (or whichever section contains it) in
`~/.config/omarchy/shell.json`. Back up the file before changing it; preserve
all other entries. For this project's prepared installation:

```json
{
  "id": "statick.gentle-dot",
  "appPath": "/home/statick/Projects/plugin_omarchy_gentle.dot/bin/gentle-dot"
}
```

Use your actual absolute executable launcher path if the project moves. The
setting is one literal argv value, not a shell command: spaces are supported;
`~`, variables and shell expressions are not expanded. Empty or omitted
`appPath` keeps automatic lookup. A configured missing, non-executable or
directory path fails with exit 127 and an actionable tooltip, never a fallback.
A configured app's own failure is also propagated without retry. Direct usage:

```sh
/bin/sh toggle.sh /absolute/path/to/bin/gentle-dot
```

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

## Prepare a persistent native app in this project

The official source is retained at `vendor/gentle-dot`, pinned to commit `8cb20ee888c88be2b359258a65499c20b59e2a86`. Generated tools, dependencies, caches and app data are ignored by Git. Keep both that checkout and `.gentle-dot-install`; the source-built app records its Node and daemon paths.

For a fresh checkout, prepare the pinned official source first (skip cloning if
`vendor/gentle-dot` already exists; preserve that checkout):

```sh
mkdir -p vendor
git clone https://github.com/Gentleman-Programming/gentle-dot.git vendor/gentle-dot
git -C vendor/gentle-dot checkout --detach 8cb20ee888c88be2b359258a65499c20b59e2a86
```

```sh
# Downloads the official Rust installer into this project, without executing it.
/bin/sh scripts/build-native.sh
# Inspect .gentle-dot-install/rustup-init.sh before this build step:
/bin/sh scripts/build-native.sh --build-reviewed-installer
# Only after the native build succeeds:
/bin/sh bin/gentle-dot --toggle
```

The build prepares local Rust and pnpm 11.5.0, then runs the upstream UI and Tauri native build without installing a system package or modifying shell profiles. It requires Node 24+ and the Arch development libraries listed by upstream `scripts/linux/setup-arch.sh`. Do not run that upstream installer unchanged: it writes outside this project.

The prepared launcher keeps app data explicitly at `.gentle-dot-install/data`, uses the recorded runtime PATH, drops inherited provider credentials and agent overrides, and selects private Engram on port 17438. That port must be free. The native app and its browser opener retain the desktop's HOME and XDG config/data/cache/state directories, BROWSER, XDG_CURRENT_DESKTOP and XDG_SESSION_TYPE, plus display and D-Bus transport variables. Values are passed as literal environment arguments, not evaluated by a shell; the rest of the caller's environment is not inherited.

Missing or empty XDG directory values default to `$HOME/.config`, `$HOME/.local/share`, `$HOME/.cache` and `$HOME/.local/state`. If HOME is missing or empty, the launcher uses `.gentle-dot-install/home` as its fallback (without consulting account databases); absent browser/desktop markers remain empty. The launcher does not copy credentials or populate desktop configuration directories.

Engine isolation remains upstream's responsibility: `packages/daemon/src/isolation.ts` sets the engine's HOME and XDG directories under `.gentle-dot-install/data/home`, with private Engram there. Account storage remains explicitly under the app's data directory (`data/agent/auth.json`), not the desktop HOME. No existing account, conversation or session data is moved or removed. This is **not a sandbox**: the native app still has desktop D-Bus/Secret Service access. Restoring desktop browser resolution corrects a launcher divergence; it does not prove account linking succeeds. Login requires a separate human action and has not been tested automatically.

Autostart is not configured. The existing broken launcher in `~/.local/bin` is not replaced, and the installed bar button now selects this project-local launcher with `appPath`. Plugin files and configuration were backed up under `.gentle-dot-install/backups/1792320775407342062` before updating.

The desktop/browser environment correction has regression coverage: the fake native app and fake opener receive the expected desktop variables, provider-secret canaries are absent, fixture data remains unchanged, and all 14 local tests pass. Independent source review found no blocker; executable probes were parent-run because the verifier's scratch requirements conflicted with project-only testing. The user subsequently confirmed OpenAI/Codex account linking succeeds; this is human acceptance, not an automated browser/OAuth test.

The native release build completed successfully at the pinned revision using Node 26.8.2, pnpm 11.5.0 and Rust/Cargo 1.99.1. Independent verification confirmed the executable artifact, retained paths and isolated launcher behavior; the preparation's 9 local tests passed. An initial npm configuration collision was reproduced and fixed with regression coverage.

A successful build does not prove chat, settings or graphical behavior. The app was launched through the prepared native launcher and Hyprland reports a mapped, floating, pinned 420×640 `Gentle Dot Panel`. The rendered bar rose and actual rose-button open/close were verified. Settings navigation timed out; settings interaction and model replies remain unverified. Run local checks with `python3 -m unittest discover -s tests -v`.

## Files

| File | Purpose |
| --- | --- |
| `manifest.json` | Omarchy plugin identity and bar entrypoint |
| `BarWidget.qml` | Theme-aware bar button, launch process, error tooltip |
| `toggle.sh` | Resolve the official app and execute `--toggle` |
| `tests/test_toggle.py` | Isolated plugin launcher tests with fake executables; no account or real daemon |
| `scripts/install.py` | Explicit plugin-only, single-rose installer with config backup |
| `tests/test_install.py` | Isolated installer CLI checks; no real desktop or account calls |
| `scripts/build-native.sh` | Retained-installer review step and project-local native build |
| `tests/test_build_native.py` | Isolated retained-installer and contained npm configuration checks |
| `bin/gentle-dot` | Prepared launcher for the persistent native artifact |
| `tests/test_native_launcher.py` | Argument, failure and environment checks against an isolated fake app |

## Verified on this machine

- Omarchy **4.0.5-1**, Hyprland **0.56.2-4**, Quickshell **0.3.2.r7.g2b4501a-1**.
- Installed Omarchy SDK supports `bar-widget`, `Ui.BarWidget`, `Ui.BarIconButton`, and plugin validation.
- Existing Hyprland configuration loads Gentle Dot's rules but points its shortcut at `/usr/bin/gentle-dot`.
- Neither `/usr/bin/gentle-dot` nor `$HOME/.local/bin/gentle-dot` is currently executable. The local launcher is a broken symlink to `/tmp/gentle-dot/apps/desktop/src-tauri/target/release/gentle-dot`; authorized inspection confirmed `/tmp/gentle-dot` no longer exists. A new persistent native artifact is now built inside this project; the global launcher remains unchanged.
- Launcher coverage includes literal explicit paths, fail-closed errors, local paths with spaces, PATH fallback, a broken local link, missing-app diagnostics without file creation, and app failure propagation. These are mock-process checks, not GUI proof.
- With user approval, installed the three plugin files under `$HOME/.config/omarchy/plugins/statick.gentle-dot` and enabled the plugin. Independent verification confirmed byte-identical installed files and that the only semantic change to `shell.json` is the new right-bar entry. Backup: `shell.json.bak.gentle-dot.20261018052638` next to that file.
- Installed manifest validation passes, shell IPC returns `ok`, and the registry reports `enabled: true`. Its `active: false` field is only meaningful for full `bar` plugins, not this `bar-widget`.
- Deployed the rose icon and notices, configured the existing widget's `appPath`, and validated the installed plugin-only folder. Native launch produced mapped `Gentle Dot` and `Gentle Dot Panel` windows with the existing placement rules.
- After the official shell restart, a tight bar capture confirmed the rose replaced the legacy G. Actual pointer clicks opened and closed the native panel successfully. The settings-navigation probe timed out before reaching settings; no retry or success is claimed. Chat replies remain unverified; the user later confirmed OpenAI/Codex linking succeeds. That confirmation is human acceptance, not automated OAuth coverage; the pointer/settings probes entered no credentials or model messages.
- **Configuration reconciliation required:** after deployment, the live right-bar layout no longer contains `hed1ad.cve-search` and `resn3t.pomodoro`, which exist in the deployment backup. Initial write readback matched the intended appPath-only change, but subsequent drift has unknown ownership. The user chose to preserve the current layout; those unrelated widgets were not restored. No further layout edits are required for the launcher correction.

## Desktop acceptance check

After installing the app and enabling the plugin:

- Click the rose: one native panel opens, without duplicate app instances.
- Click again: the panel hides. Open again: the conversation is retained.
- Open settings and return to chat; confirm both are usable.
- Switch workspace and check the official Hyprland placement rules.
- Check the button in your current theme and bar orientation.

Do not enter account keys in this plugin or commit them to this project. Configure accounts directly in Gentle Dot. Linux computer control is not provided by this integration; upstream documents computer control as macOS-only.

## Official references

- [Official Omarchy plugin authoring guide](https://plugins.omarchy.org/develop.html)
- [Official Omarchy plugin publishing guide](https://plugins.omarchy.org/publish.html)
- [Gentle Dot README](https://github.com/Gentleman-Programming/gentle-dot)
- [Installation and Linux security limits](https://github.com/Gentleman-Programming/gentle-dot/blob/main/docs/install.md)
- [Linux / Omarchy testing checklist](https://github.com/Gentleman-Programming/gentle-dot/blob/main/docs/linux-testing.md)
- Local SDK: `/usr/share/omarchy/shell/README.md` and `/usr/share/omarchy/shell/Ui/` (read-only).
