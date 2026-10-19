#!/usr/bin/env python3
"""Run Panel.qml in an isolated Quickshell process with no real desktop state."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SHELL = ROOT / 'tests' / 'popup_preview' / 'shell.qml'
SDK = Path('/usr/share/omarchy/shell')


def main():
    quickshell = shutil.which('quickshell')
    if quickshell is None:
        print('quickshell is unavailable', file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix='gentle-dot-t11-') as temp:
        runtime = Path(temp)
        home = runtime / 'home'
        theme = home / '.local/state/omarchy/current/theme'
        theme.mkdir(parents=True)
        (theme / 'colors.toml').write_text('foreground = "#e1d1dc"\nbackground = "#201820"\naccent = "#b96a91"\nmuted = "#837481"\n')
        (theme / 'shell.toml').write_text('[font]\nbase-size = 13\n[popups]\nbackground = "background"\ntext = "#e1d1dc"\nborder = "accent"\n')
        private_runtime = runtime / 'runtime'
        private_runtime.mkdir(mode=0o700)
        live_runtime = os.environ.get('XDG_RUNTIME_DIR', '')
        display = os.environ.get('WAYLAND_DISPLAY', '')
        if not display:
            print('WAYLAND_DISPLAY is unavailable', file=sys.stderr)
            return 2
        if not os.path.isabs(display):
            if not live_runtime:
                print('relative WAYLAND_DISPLAY has no runtime directory', file=sys.stderr)
                return 2
            display = os.path.join(live_runtime, display)
        config = runtime / 'preview'
        config.mkdir()
        (config / 'shell.qml').write_bytes(SHELL.read_bytes())
        (config / 'plugin').symlink_to(ROOT, target_is_directory=True)
        qml_root = runtime / 'qml'
        qml_root.mkdir()
        (qml_root / 'qs').symlink_to(SDK, target_is_directory=True)
        env = {
            'HOME': str(home),
            'XDG_CONFIG_HOME': str(runtime / 'config'),
            'XDG_CACHE_HOME': str(runtime / 'cache'),
            'XDG_DATA_HOME': str(runtime / 'data'),
            'QML_IMPORT_PATH': str(qml_root),
            'QML2_IMPORT_PATH': str(qml_root),
            'QT_QPA_PLATFORM': os.environ.get('QT_QPA_PLATFORM', 'wayland'),
            'WAYLAND_DISPLAY': display,
            'XDG_RUNTIME_DIR': str(private_runtime),
        }
        result = subprocess.run([quickshell, '--path', str(config / 'shell.qml'), '--no-color'], env=env,
                                text=True, capture_output=True, timeout=10)
        log_notice = 'Saving logs to "' + str(private_runtime) + '/'
        isolated = (private_runtime.stat().st_mode & 0o777) == 0o700 and log_notice in result.stdout
    marker = next((line for line in result.stdout.splitlines() if 'T11_RESULT' in line), '')
    if not isolated:
        result = subprocess.CompletedProcess(result.args, 1, result.stdout,
            result.stderr + 'preview runtime/log path was not private\n')
    if result.returncode == 0 and marker:
        print('T11_RESULT ' + marker.split('T11_RESULT ', 1)[1])
    else:
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
