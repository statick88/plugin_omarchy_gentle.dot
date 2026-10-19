#!/usr/bin/env python3
"""Run Panel.qml in an isolated Quickshell process with no real desktop state."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SHELL = ROOT / "tests" / "popup_preview" / "shell.qml"
SDK = Path("/usr/share/omarchy/shell")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pairing",
        nargs=2,
        metavar=("LOOPBACK_URL", "TOKEN_FILE"),
        help="run the synthetic explicit-pairing preview",
    )
    parser.add_argument(
        "--write-controls",
        nargs=2,
        metavar=("LOOPBACK_URL", "TOKEN_FILE"),
        help="run the synthetic write-controls preview",
    )
    parser.add_argument(
        "--bridge-exit",
        action="store_true",
        help="make the private synthetic node bridge exit after connected",
    )
    args = parser.parse_args()
    quickshell = shutil.which("quickshell")
    if quickshell is None:
        print("quickshell is unavailable", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="gentle-dot-t11-") as temp:
        runtime = Path(temp)
        home = runtime / "home"
        theme = home / ".local/state/omarchy/current/theme"
        theme.mkdir(parents=True)
        (theme / "colors.toml").write_text(
            'foreground = "#e1d1dc"\nbackground = "#201820"\naccent = "#b96a91"\nmuted = "#837481"\n'
        )
        (theme / "shell.toml").write_text(
            '[font]\nbase-size = 13\n[popups]\nbackground = "background"\ntext = "#e1d1dc"\nborder = "accent"\n'
        )
        private_runtime = runtime / "runtime"
        private_runtime.mkdir(mode=0o700)
        live_runtime = os.environ.get("XDG_RUNTIME_DIR", "")
        display = os.environ.get("WAYLAND_DISPLAY", "")
        if not display:
            print("WAYLAND_DISPLAY is unavailable", file=sys.stderr)
            return 2
        if not os.path.isabs(display):
            if not live_runtime:
                print(
                    "relative WAYLAND_DISPLAY has no runtime directory", file=sys.stderr
                )
                return 2
            display = os.path.join(live_runtime, display)
        config = runtime / "preview"
        config.mkdir()
        shell_source = (
            ROOT
            / "tests"
            / "popup_preview"
            / (
                "write_controls.qml"
                if args.write_controls
                else ("pairing.qml" if args.pairing else "shell.qml")
            )
        )
        (config / "shell.qml").write_bytes(shell_source.read_bytes())
        plugin = config / "plugin"
        if args.pairing or args.write_controls:
            plugin.mkdir()
            for name in ("BackendController.qml", "Panel.qml"):
                shutil.copyfile(ROOT / name, plugin / name)
            (plugin / "scripts").mkdir()
            shutil.copyfile(
                ROOT / "scripts" / "backend_bridge.mjs",
                plugin / "scripts" / "backend_bridge.mjs",
            )
            panel = plugin / "Panel.qml"
            source = panel.read_text()
            replacements = (
                (
                    "    property var chatController: null",
                    "    property var chatController: null\n    readonly property var verificationPairing: pairing",
                ),
                (
                    "        property bool accepted: false",
                    "        property bool accepted: false\n        readonly property var verificationEndpoint: endpointInput\n        readonly property var verificationToken: tokenInput\n        readonly property var verificationToggle: consentToggle\n        readonly property var verificationConnect: connectButton\n        readonly property var verificationDisconnect: disconnectButton\n        readonly property var verificationWriteConsent: writeConsent\n        readonly property var verificationConfirmStop: confirmStopButton\n        readonly property var verificationCancelStop: cancelStopButton",
                ),
                (
                    '            Ui.Toggle {\n                width: parent.width\n                label: "I consent to read-only history"',
                    '            Ui.Toggle {\n                id: consentToggle\n                width: parent.width\n                label: "I consent to read-only history"',
                ),
                (
                    'Ui.Button { text: "Connect"',
                    'Ui.Button { id: connectButton; text: "Connect"',
                ),
                (
                    'Ui.Button { text: "Disconnect"',
                    'Ui.Button { id: disconnectButton; text: "Disconnect"',
                ),
                (
                    "                Ui.Toggle {\n                    id: writeConsent",
                    "                Ui.Toggle {\n                    id: writeConsent",
                ),
                (
                    '                    Ui.Button { text: "Confirm Stop"',
                    '                    Ui.Button { id: confirmStopButton; text: "Confirm Stop"',
                ),
                (
                    '                    Ui.Button { text: "Cancel"',
                    '                    Ui.Button { id: cancelStopButton; text: "Cancel"',
                ),
            )
            for old, new in replacements:
                if source.count(old) != 1:
                    raise RuntimeError("pairing probe injection target changed")
                source = source.replace(old, new)
            panel.write_text(source)
        else:
            plugin.symlink_to(ROOT, target_is_directory=True)
        qml_root = runtime / "qml"
        qml_root.mkdir()
        (qml_root / "qs").symlink_to(SDK, target_is_directory=True)
        env = {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(runtime / "config"),
            "XDG_CACHE_HOME": str(runtime / "cache"),
            "XDG_DATA_HOME": str(runtime / "data"),
            "QML_IMPORT_PATH": str(qml_root),
            "QML2_IMPORT_PATH": str(qml_root),
            "QT_QPA_PLATFORM": os.environ.get("QT_QPA_PLATFORM", "wayland"),
            "WAYLAND_DISPLAY": display,
            "XDG_RUNTIME_DIR": str(private_runtime),
        }
        if args.pairing or args.write_controls:
            pair_args = args.pairing or args.write_controls
            env.update(
                {
                    "GENTLE_PAIR_URL": pair_args[0],
                    "GENTLE_PAIR_TOKEN": pair_args[1],
                }
            )
        if args.bridge_exit:
            bin_dir = runtime / "bin"
            bin_dir.mkdir()
            node = bin_dir / "node"
            node.write_text(
                '#!/bin/sh\nif [ "$1" = "--version" ]; then echo v24.0.0; exit 0; fi\nprintf \'{"type":"status","state":"connected"}\\n\'\nexit 0\n'
            )
            node.chmod(0o700)
            env["PATH"] = str(bin_dir)
            env["GENTLE_BRIDGE_EXIT"] = "1"
        result = subprocess.run(
            [quickshell, "--path", str(config / "shell.qml"), "--no-color"],
            env=env,
            text=True,
            capture_output=True,
            timeout=10,
        )
        log_notice = 'Saving logs to "' + str(private_runtime) + "/"
        isolated = (
            private_runtime.stat().st_mode & 0o777
        ) == 0o700 and log_notice in result.stdout
    marker_name = (
        "T18_RESULT"
        if args.write_controls
        else ("T17_RESULT" if args.pairing else "T11_RESULT")
    )
    marker = next(
        (line for line in result.stdout.splitlines() if marker_name in line), ""
    )
    if not isolated:
        result = subprocess.CompletedProcess(
            result.args,
            1,
            result.stdout,
            result.stderr + "preview runtime/log path was not private\n",
        )
    if result.returncode == 0 and marker:
        print(marker_name + " " + marker.split(marker_name + " ", 1)[1])
    else:
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
