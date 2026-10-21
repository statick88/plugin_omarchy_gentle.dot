#!/usr/bin/env python3
"""Omarchy widget installer with an explicit, guided native-source setup mode."""
import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from native_install import NativeRejected, setup as setup_native

PLUGIN = 'statick.gentle-dot'
PAYLOAD = ('manifest.json', 'BarWidget.qml', 'Panel.qml', 'BackendController.qml', 'toggle.sh',
           'assets/rose-glyph.svg', 'scripts/backend_bridge.mjs', 'LICENSE',
           'LICENSES/gentle-dot-MIT.txt', 'THIRD_PARTY_NOTICES.md')
IDENTITY_ERROR = ('Cannot uniquely identify Gentle Dot without an ID collision; '
                  'start the installed app and inspect its tray menu.')
CONFIG_ERROR = 'Invalid shell.json; restore a valid version-1 bar layout first.'
PATH_ERROR = 'Unsafe installation path; remove symlinks or non-directory parents first.'


class Rejected(Exception):
    pass


def regular_path(path, directory=False):
    """Reject symlinks, including parents, before following any package/config path."""
    for parent in reversed(path.parents):
        if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
            raise Rejected(PATH_ERROR)
    if path.is_symlink() or (path.exists() and not (path.is_dir() if directory else path.is_file())):
        raise Rejected(PATH_ERROR)


def command(argv, failure):
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return result.stdout
    except (OSError, subprocess.TimeoutExpired):
        pass
    raise Rejected(failure)


def bus(*args):
    return json.loads(command(['busctl', '--user', '--json=short', *args], IDENTITY_ERROR))


def value(reply, kind):
    if reply['type'] != kind:
        raise ValueError('Unexpected D-Bus type')
    return reply['data']


def menu(service, path):
    layout = value(bus('call', service, path, 'com.canonical.dbusmenu',
                       'GetLayout', 'iias', '0', '1', '1', 'label'), 'u(ia{sv}av)')
    if (not isinstance(layout, list) or len(layout) != 2
            or type(layout[0]) is not int or not isinstance(layout[1], list)
            or len(layout[1]) != 3 or type(layout[1][0]) is not int
            or not isinstance(layout[1][1], dict) or not isinstance(layout[1][2], list)):
        raise ValueError('Invalid menu layout')
    entries = []
    seen_ids = set()
    for child in layout[1][2]:
        node = value(child, '(ia{sv}av)')
        if (not isinstance(node, list) or len(node) != 3 or type(node[0]) is not int
                or not isinstance(node[1], dict) or not isinstance(node[2], list)
                or node[0] in seen_ids):
            raise ValueError('Invalid menu node')
        seen_ids.add(node[0])
        # GetLayout requests only labels: native separators have empty properties.
        if 'label' not in node[1]:
            continue
        label = value(node[1]['label'], 's')
        if not isinstance(label, str):
            raise ValueError('Invalid menu label')
        entries.append((node[0], label))
    visibility = [entry for entry in entries if entry[1] in ('Hide the rose', 'Show the rose')]
    if (sum(label == 'Open' for _, label in entries) != 1
            or sum(label == 'Quit' for _, label in entries) != 1 or len(visibility) != 1):
        raise ValueError('Not the official menu')
    return visibility[0]


def native():
    try:
        registered = value(bus('get-property', 'org.kde.StatusNotifierWatcher',
                               '/StatusNotifierWatcher', 'org.kde.StatusNotifierWatcher',
                               'RegisteredStatusNotifierItems'), 'as')
        if not isinstance(registered, list) or len(set(registered)) != len(registered):
            raise ValueError('Invalid registry')
        items = []
        for address in registered:
            service, separator, suffix = address.partition('/')
            path = '/' + suffix if separator else '/StatusNotifierItem'
            if not service or service.startswith('-'):
                raise ValueError('Invalid service')
            props = {}
            for prop, kind in (('Id', 's'), ('Title', 's'), ('Menu', 'o')):
                props[prop] = value(bus('get-property', service, path,
                                        'org.kde.StatusNotifierItem', prop), kind)
                if not isinstance(props[prop], str) or not props[prop]:
                    raise ValueError('Invalid property')
            items.append((service, props))
        candidates = [(service, props) for service, props in items
                      if props['Title'].strip().casefold() in ('gentle-dot', 'gentle dot')]
        if len(candidates) != 1:
            raise ValueError('Ambiguous title')
        service, props = candidates[0]
        if sum(p['Id'] == props['Id'] for _, p in items) != 1 or not props['Menu'].startswith('/'):
            raise ValueError('Shared identity')
        item_id, label = menu(service, props['Menu'])
        return service, props['Menu'], props['Id'], item_id, label
    except (KeyError, ValueError, TypeError, IndexError, Rejected):
        raise Rejected(IDENTITY_ERROR) from None


def unique_keys(pairs):
    result = {}
    for key, val in pairs:
        if key in result:
            raise ValueError('Duplicate config key')
        result[key] = val
    return result


def read_config(path):
    regular_path(path)
    try:
        raw = path.read_bytes()
        stamp = path.stat()
        config = json.loads(raw, object_pairs_hook=unique_keys)
        if type(config['version']) is not int or config['version'] != 1:
            raise ValueError('Unknown config version')
        layout = config['bar']['layout']
        for section in ('left', 'center', 'right'):
            if not isinstance(layout[section], list):
                raise ValueError('Invalid section')
            for entry in layout[section]:
                if not isinstance(entry, dict) or not isinstance(entry['id'], str):
                    raise ValueError('Invalid entry')
                if entry['id'] == 'omarchy.tray':
                    for field in ('hidden', 'pinned'):
                        if not isinstance(entry.get(field, []), list) or any(
                                not isinstance(v, str) for v in entry.get(field, [])):
                            raise ValueError('Invalid tray settings')
        return raw, stamp, config
    except (OSError, ValueError, KeyError, TypeError):
        raise Rejected(CONFIG_ERROR) from None


def launcher(explicit, entry):
    configured = explicit if explicit is not None else entry.get('appPath', '')
    if not isinstance(configured, str):
        raise Rejected('Invalid widget appPath; select an existing executable with --app-path.')
    if explicit is not None:
        candidate = Path(configured)
        if not candidate.is_file() or not os.access(candidate, os.X_OK):
            raise Rejected(f'Native launcher is not executable: {candidate}. '
                           'Pass --app-path with an executable file.')
    elif configured:
        candidate = Path(configured)
        if not candidate.is_file() or not os.access(candidate, os.X_OK):
            raise Rejected(f'Configured Gentle Dot appPath is not an executable file: {candidate}. '
                           'Set appPath to the native launcher or clear it for automatic lookup.')
    else:
        local = Path.home() / '.local/bin/gentle-dot'
        candidate = local if local.is_file() and os.access(local, os.X_OK) else Path(shutil.which('gentle-dot') or '')
        if not candidate.is_file() or not os.access(candidate, os.X_OK):
            raise Rejected('Native launcher is not executable; install the app first or pass --app-path /absolute/launcher.')
    return str(candidate.absolute())


def payload(source, target):
    data = {}
    try:
        for name in PAYLOAD:
            path = source / name
            regular_path(path)
            data[name] = path.read_bytes()
    except (OSError, Rejected):
        raise Rejected('Unsafe source payload; use regular package files without symlinks.') from None
    regular_path(target, directory=True)
    present = set()
    if target.exists():
        allowed_dirs = {str(Path(name).parent) for name in PAYLOAD} - {'.'}
        for path in target.rglob('*'):
            name = str(path.relative_to(target))
            regular_path(path, directory=path.is_dir())
            if path.is_dir() and name in allowed_dirs:
                continue
            if name not in data or not path.is_file() or path.read_bytes() != data[name]:
                raise Rejected('Installed payload differs or contains unexpected files; preserve it and remove it manually before reinstalling.')
            present.add(name)
    return data, set(data) - present


def unchanged(path, raw, stamp):
    regular_path(path)
    now = path.stat()
    if (now.st_dev, now.st_ino, now.st_mtime_ns, now.st_size) != (
            stamp.st_dev, stamp.st_ino, stamp.st_mtime_ns, stamp.st_size) or path.read_bytes() != raw:
        raise Rejected('shell.json changed concurrently; inspect it and rerun without overwriting the other writer.')


def install(explicit, native_committed=False):
    backup = None
    committed = native_committed
    try:
        config_path = Path.home() / '.config/omarchy/shell.json'
        raw, stamp, original = read_config(config_path)
        pending = config_path.with_name('.gentle-dot-pending')
        regular_path(pending)
        recovery = [False, False]
        if pending.exists():
            try:
                recovery = json.loads(pending.read_bytes())
                if (not isinstance(recovery, list) or len(recovery) != 2
                        or any(type(flag) is not bool for flag in recovery) or not any(recovery)):
                    raise ValueError('Invalid pending operations')
            except (OSError, ValueError):
                raise Rejected('Invalid recovery marker; inspect ~/.config/omarchy/.gentle-dot-pending before retrying.') from None
        config = copy.deepcopy(original)
        layout = config['bar']['layout']
        entries = [entry for section in ('left', 'center', 'right') for entry in layout[section]]
        widgets = [entry for entry in entries if entry['id'] == PLUGIN]
        if len(widgets) > 1:
            raise Rejected(CONFIG_ERROR)
        widget = widgets[0] if widgets else {'id': PLUGIN}
        app = launcher(explicit, widget)
        if not widgets:
            layout['right'].append(widget)
        if explicit is not None or not widgets:
            widget['appPath'] = app
        source = Path(__file__).absolute().parent.parent
        target = config_path.parent / 'plugins' / PLUGIN
        data, missing = payload(source, target)
        service, menu_path, native_id, item_id, label = native()
        for entry in entries:
            if entry['id'] == 'omarchy.tray' and native_id not in entry.get('hidden', []):
                entry.setdefault('hidden', []).append(native_id)
        changed = config != original
        rescan, reload_config = bool(missing) or recovery[0], changed or recovery[1]
        # The repository may contain vendor symlinks: validate only the ten runtime files.
        with tempfile.TemporaryDirectory(prefix='gentle-dot-payload-') as temp:
            stage = Path(temp) / PLUGIN
            for name, content in data.items():
                path = stage / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            command(['omarchy', 'plugin', 'validate', str(stage)],
                    'Plugin validation failed; run omarchy plugin validate on the plugin-only payload.')
            unchanged(config_path, raw, stamp)
            # Recheck the destination after external validation, before any writes.
            _, current_missing = payload(source, target)
            if current_missing != missing:
                raise Rejected('Installation target changed concurrently; inspect it and rerun.')
            if changed:
                backup = config_path.with_name(config_path.name + '.bak.gentle-dot.' + str(time.time_ns()))
                # Creation/write/close can leave state even when they raise.
                committed = True
                fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(raw)
            if rescan or reload_config:
                # Persist intent before payload/config changes; retries must not infer
                # shell activation from the files already being present on disk.
                committed = True
                temp_pending = None
                try:
                    with tempfile.NamedTemporaryFile(dir=config_path.parent, prefix='.gentle-dot-pending-', delete=False) as stream:
                        temp_pending = Path(stream.name)
                        stream.write(json.dumps([rescan, reload_config]).encode())
                        stream.flush()
                        os.fsync(stream.fileno())
                    regular_path(pending)
                    os.replace(temp_pending, pending)
                finally:
                    if temp_pending is not None and temp_pending.exists():
                        temp_pending.unlink()
            for name in sorted(missing):
                path = target / name
                regular_path(path)
                # Parent creation may partially succeed before mkdir/open fails.
                committed = True
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open('xb') as stream:
                    stream.write(data[name])
            if changed:
                temp_path = None
                try:
                    with tempfile.NamedTemporaryFile(dir=config_path.parent, prefix='.gentle-dot-', delete=False) as stream:
                        temp_path = Path(stream.name)
                        stream.write((json.dumps(config, indent=2) + '\n').encode())
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.chmod(temp_path, stamp.st_mode & 0o777)
                    unchanged(config_path, raw, stamp)
                    os.replace(temp_path, config_path)
                finally:
                    if temp_path is not None and temp_path.exists():
                        temp_path.unlink()
        if rescan:
            command(['omarchy-shell', 'shell', 'rescanPlugins'],
                    'shell rescanPlugins failed; restore shell availability and rerun this installer.')
        if reload_config:
            command(['omarchy-shell', 'shell', 'reloadConfig'],
                    'shell reloadConfig failed; restore shell availability and rerun this installer.')
        if rescan or reload_config:
            pending.unlink()
        # Reconfirm public identity after commit; never click a stale menu item.
        fresh = native()
        if fresh[:3] != (service, menu_path, native_id):
            raise Rejected(IDENTITY_ERROR)
        item_id, label = fresh[3:]
        hidden_now = label == 'Show the rose'
        if not hidden_now:
            committed = True  # An Event can succeed even if its reply is lost.
            command(['busctl', '--user', '--json=short', 'call', service, menu_path,
                     'com.canonical.dbusmenu', 'Event', 'isvu', str(item_id), 'clicked', 'i', '0', '0'],
                    'Native Hide the rose event failed; inspect the native tray menu before retrying.')
            for _ in range(10):
                if menu(service, menu_path)[1] == 'Show the rose':
                    break
                time.sleep(0.1)
            else:
                raise Rejected('Native rose hiding was not confirmed; inspect its tray menu and retry.')
        action = 'Installed: one Gentle Dot rose configured.' if missing or changed or any(recovery) or not hidden_now else 'Unchanged: one Gentle Dot rose already configured.'
        print(action)
        if backup:
            print(f'Backup: {backup}')
        return 0
    except (Rejected, OSError, ValueError, KeyError, TypeError, IndexError) as error:
        prefix = 'Partial installation' if committed else 'Preflight rejected'
        print(f'{prefix}: {error}', file=sys.stderr)
        if backup:
            print(f'Backup: {backup}', file=sys.stderr)
        return 2 if committed else 1


def main():
    parser = argparse.ArgumentParser(description='Install the Omarchy widget; --install-native explicitly builds the pinned official native source first.', epilog='Native source setup is Omarchy-only, retains its source/runtime directory, and asks before installing missing Arch build packages.')
    parser.add_argument('--app-path', metavar='EXECUTABLE', help='existing native launcher (one literal path); otherwise preserve widget appPath, then try ~/.local/bin/gentle-dot and PATH')
    parser.add_argument('--install-native', action='store_true', help='guided build of the pinned official Gentle Dot source before widget integration')
    parser.add_argument('--no-launch', action='store_true', help='with --install-native, build only; do not start the native app or modify Omarchy configuration')
    args = parser.parse_args()
    if args.no_launch and not args.install_native:
        parser.error('--no-launch requires --install-native')
    if not args.install_native:
        return install(args.app_path)
    if args.app_path is not None:
        parser.error('--app-path cannot be combined with --install-native')
    try:
        existing = None
        if not args.no_launch:
            config_path = Path.home() / '.config/omarchy/shell.json'
            _, _, config = read_config(config_path)
            widgets = [entry for section in ('left', 'center', 'right')
                       for entry in config['bar']['layout'][section] if entry['id'] == PLUGIN]
            if len(widgets) > 1:
                raise Rejected(CONFIG_ERROR)
            widget = widgets[0] if widgets else {}
            try:
                existing = launcher(None, widget)
            except Rejected:
                if widget.get('appPath') or not isinstance(widget.get('appPath', ''), str):
                    raise
            # Reject an unsafe/edited widget destination before provisioning native code.
            payload(Path(__file__).absolute().parent.parent, config_path.parent / 'plugins' / PLUGIN)
        app_path, native_changed = setup_native(no_launch=args.no_launch, ready=native, existing=existing)
    except Rejected as error:
        print(f'Preflight rejected: {error}', file=sys.stderr)
        return 1
    except NativeRejected as error:
        prefix = 'Partial installation' if error.args[1] else 'Preflight rejected'
        print(f'{prefix}: {error.args[0]}', file=sys.stderr)
        return 2 if error.args[1] else 1
    if args.no_launch:
        return 0
    # Keep a configured existing path literal; a new managed build supplies its path.
    return install(None if existing else app_path, native_committed=native_changed)


if __name__ == '__main__':
    sys.exit(main())
