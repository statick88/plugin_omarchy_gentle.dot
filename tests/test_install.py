"""Public CLI tests: every desktop command is a fixture executable."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ('manifest.json', 'BarWidget.qml', 'Panel.qml', 'BackendController.qml', 'toggle.sh',
           'assets/rose-glyph.svg', 'scripts/backend_bridge.mjs', 'LICENSE',
           'LICENSES/gentle-dot-MIT.txt', 'THIRD_PARTY_NOTICES.md')
PLUGIN = 'statick.gentle-dot'
NATIVE_ID = 'tray-icon tray app main'
NATIVE_MENU = [
    {'type': '(ia{sv}av)', 'data': [item_id, {} if label is None else
     {'label': {'type': 's', 'data': label}}, []]}
    for item_id, label in ((2, 'Open'), (3, 'Open in browser'), (4, 'Hide the rose'),
                           (5, None), (6, 'Restart assistant'), (7, 'Launch at login'),
                           (8, None), (9, 'Quit'))
]
# Loaded only by the fixture installer subprocess, never imported by these tests.
FILESYSTEM_FAULTS = r'''
import io, os, pathlib, sys
root = pathlib.Path(os.environ['FIXTURE'])
if sys.argv[0] == str(root / 'package/scripts/install.py'):
    config_dir = root / 'home/.config/omarchy'
    target = config_dir / 'plugins/statick.gentle-dot'
    fault = os.environ.get('FILESYSTEM_FAULT', '')
    original_open = io.open
    original_os_open = os.open
    backup_fds = set()

    def is_backup(path):
        return (path.parent == config_dir and
                path.name.startswith('shell.json.bak.gentle-dot.'))

    class BackupStream:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            return self

        def write(self, data):
            if fault == 'backup-write':
                raise OSError('injected backup write failure')
            return self.stream.write(data)

        def __exit__(self, *args):
            self.stream.close()
            if fault == 'backup-close':
                raise OSError('injected backup close failure')

    def open_fd(path, flags, mode=0o777, *, dir_fd=None):
        fd = original_os_open(path, flags, mode, dir_fd=dir_fd)
        if not isinstance(path, int) and is_backup(pathlib.Path(path)):
            backup_fds.add(fd)
        return fd

    def open_stream(file, mode='r', *args, **kwargs):
        path = None if isinstance(file, int) else pathlib.Path(file)
        if (fault == 'payload-open' and path is not None and
                path.parent == target and 'x' in mode):
            raise OSError('injected payload open failure')
        stream = original_open(file, mode, *args, **kwargs)
        backup = file in backup_fds if isinstance(file, int) else is_backup(path)
        if backup and fault in ('backup-write', 'backup-close'):
            return BackupStream(stream)
        return stream

    os.open = open_fd
    io.open = open_stream
'''
FAKE = r'''
import json, os, pathlib, sys
root = pathlib.Path(os.environ['FIXTURE'])
args = sys.argv[1:]
name = pathlib.Path(sys.argv[0]).name
state = json.loads((root / 'state').read_text())
def emit(kind, data):
    print(json.dumps({'type': kind, 'data': data}))
def record():
    with (root / 'events').open('a') as f:
        f.write(json.dumps([name, sys.argv[1:]]) + '\n')
if name == 'native app ; literal':
    record()
    sys.exit(99)
if name == 'omarchy':
    assert args[:2] == ['plugin', 'validate']
    stage = pathlib.Path(args[2])
    assert sorted(str(p.relative_to(stage)) for p in stage.rglob('*') if p.is_file()) == sorted(state['payload'])
    if state.get('concurrent_config'):
        (pathlib.Path(os.environ['HOME']) / '.config/omarchy/shell.json').write_text(state['concurrent_config'])
    sys.exit(1 if state.get('invalid_package') else 0)
if name == 'omarchy-shell':
    assert args in [['shell', 'rescanPlugins'], ['shell', 'reloadConfig']]
    record()
    failure = state.get('shell_failure')
    sys.exit(1 if failure is True or failure == args[1] else 0)
assert args[:2] == ['--user', '--json=short']
args = args[2:]
if args[0] == 'get-property':
    prop = args[-1]
    if prop == 'RegisteredStatusNotifierItems':
        emit('as', [item['service'] + '/StatusNotifierItem' for item in state['items']])
    else:
        item = next(i for i in state['items'] if i['service'] == args[1])
        emit('o' if prop == 'Menu' else 's', item[prop])
elif args[-6:] == ['GetLayout', 'iias', '0', '1', '1', 'label']:
    item = next(i for i in state['items'] if i['service'] == args[1])
    children = item.get('nodes', state['menu'])
    if state['hidden']:
        for child in children:
            label = child['data'][1].get('label')
            if label == {'type': 's', 'data': 'Hide the rose'}:
                label['data'] = 'Show the rose'
    emit('u(ia{sv}av)', [1, [0, {}, children]])
else:
    assert args[3:] == ['com.canonical.dbusmenu', 'Event', 'isvu', '4', 'clicked', 'i', '0', '0']
    record()
    if not state.get('stuck'):
        state['hidden'] = True
        (root / 'state').write_text(json.dumps(state))
'''


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='install-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / 'home'
        self.source = self.root / 'package'
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.source.mkdir()
        for name in PAYLOAD:
            dest = self.source / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, dest)
        (self.source / 'scripts').mkdir(exist_ok=True)
        for script in ('install.py', 'native_install.py', 'backend_bridge.mjs'):
            if (ROOT / 'scripts' / script).exists():
                shutil.copyfile(ROOT / 'scripts' / script, self.source / 'scripts' / script)
        self.config = self.home / '.config/omarchy/shell.json'
        self.config.parent.mkdir(parents=True)
        self.original = {'version': 1, 'bar': {'layout': {
            'left': [{'id': 'peer', 'custom': 42}], 'center': [],
            'right': [{'id': 'omarchy.tray', 'pinned': ['mail'], 'hidden': ['other'], 'custom': 9}]}},
            'plugins': [{'id': 'peer.service'}], 'idle': {'lock': 333}}
        self.config.write_text(json.dumps(self.original))
        self.target = self.config.parent / 'plugins' / PLUGIN
        self.account = self.home / 'surrogate-account'
        self.account.write_text('account sentinel')
        self.app = self.bin / 'native app ; literal'
        for name in ('busctl', 'omarchy', 'omarchy-shell', self.app.name):
            path = self.bin / name
            path.write_text('#!' + sys.executable + '\n' + FAKE)
            path.chmod(0o755)
        self.state = {'items': [{'service': ':1.23', 'Title': 'gentle-dot',
                       'Id': NATIVE_ID, 'Menu': '/Menu'},
                       {'service': ':1.99', 'Title': 'Mail', 'Id': 'mail', 'Menu': '/PeerMenu'}],
                      'hidden': False, 'payload': PAYLOAD, 'menu': NATIVE_MENU}
        self.save_state()
        self.env = {'HOME': str(self.home), 'PATH': str(self.bin), 'FIXTURE': str(self.root),
                    'TMPDIR': str(self.root), 'PYTHONDONTWRITEBYTECODE': '1'}

    def save_state(self):
        (self.root / 'state').write_text(json.dumps(self.state))

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(self.source / 'scripts/install.py'), *args],
                              env=self.env, capture_output=True, text=True, timeout=15,
                              umask=0o022)

    def filesystem_fault(self, name):
        hooks = self.root / 'subprocess-hooks'
        hooks.mkdir(exist_ok=True)
        (hooks / 'sitecustomize.py').write_text(FILESYSTEM_FAULTS)
        self.env.update(PYTHONPATH=str(hooks), FILESYSTEM_FAULT=name)

    def result(self, result, code, out='', err=''):
        self.assertEqual((result.returncode, result.stdout, result.stderr), (code, out, err))

    def events(self):
        path = self.root / 'events'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def snapshot(self):
        return {str(p.relative_to(self.home)): p.read_bytes()
                for p in self.home.rglob('*') if p.is_file()}

    def success(self, *args):
        result = self.run_cli(*args)
        backups = list(self.config.parent.glob('shell.json.bak.gentle-dot.*'))
        self.assertEqual(len(backups), 1)
        self.result(result, 0, f'Installed: one Gentle Dot rose configured.\nBackup: {backups[0]}\n')
        self.assertEqual(json.loads(backups[0].read_text()), self.original)

    def test_real_menu_with_extra_actions_and_separators_hides_only_native(self):
        self.success('--app-path', str(self.app))
        expected = json.loads(json.dumps(self.original))
        expected['bar']['layout']['right'][0]['hidden'].append(NATIVE_ID)
        expected['bar']['layout']['right'].append({'id': PLUGIN, 'appPath': str(self.app)})
        self.assertEqual(json.loads(self.config.read_text()), expected)
        self.assertEqual(self.account.read_text(), 'account sentinel')
        self.assertEqual(sorted(str(p.relative_to(self.target)) for p in self.target.rglob('*') if p.is_file()), sorted(PAYLOAD))
        for name in PAYLOAD:
            self.assertEqual((self.target / name).read_bytes(), (self.source / name).read_bytes())
        self.assertEqual(self.events(), [
            ['omarchy-shell', ['shell', 'rescanPlugins']],
            ['omarchy-shell', ['shell', 'reloadConfig']],
            ['busctl', ['--user', '--json=short', 'call', ':1.23', '/Menu',
                        'com.canonical.dbusmenu', 'Event', 'isvu', '4', 'clicked', 'i', '0', '0']]])
        self.assertEqual(json.loads((self.root / 'state').read_text())['items'], self.state['items'])

    def test_repeat_run_is_same_state_without_events_backups_or_writes(self):
        self.success('--app-path', str(self.app))
        before = self.snapshot()
        mtimes = {p: p.stat().st_mtime_ns for p in self.home.rglob('*')}
        events = self.events()
        self.result(self.run_cli(), 0, 'Unchanged: one Gentle Dot rose already configured.\n')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual({p: p.stat().st_mtime_ns for p in self.home.rglob('*')}, mtimes)
        self.assertEqual(self.events(), events)

    def test_existing_location_settings_and_path_preserved_without_tray(self):
        self.original['bar']['layout']['right'] = []
        entry = {'id': PLUGIN, 'appPath': str(self.app), 'custom': 'keep'}
        self.original['bar']['layout']['left'].append(entry)
        self.config.write_text(json.dumps(self.original))
        self.state['hidden'] = True
        self.state['items'][0]['Title'] = 'Gentle Dot'
        self.save_state()
        self.result(self.run_cli(), 0, 'Installed: one Gentle Dot rose configured.\n')
        self.assertEqual(json.loads(self.config.read_text()), self.original)
        self.assertEqual(self.events(), [['omarchy-shell', ['shell', 'rescanPlugins']]])
        replacement = self.bin / 'replacement'
        replacement.write_text('never execute')
        replacement.chmod(0o755)
        self.success('--app-path', str(replacement))
        entry['appPath'] = str(replacement)
        self.assertEqual(json.loads(self.config.read_text()), self.original)

    def reject(self, message):
        before = self.snapshot()
        events = self.events()
        self.result(self.run_cli('--app-path', str(self.app)), 1, '', f'Preflight rejected: {message}\n')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.events(), events)

    def test_identity_collision_and_native_absent_fail_closed(self):
        for items in ([], [dict(self.state['items'][0], Title='Not Gentle Dot')],
                      [dict(self.state['items'][0], nodes=[NATIVE_MENU[0], NATIVE_MENU[-1]])],
                      [dict(self.state['items'][0], Menu='invalid-object-path')],
                      self.state['items'] + [dict(self.state['items'][0], service=':1.24', Title='Peer')]):
            with self.subTest(items=items):
                self.state['items'] = items
                self.save_state()
                self.reject('Cannot uniquely identify Gentle Dot without an ID collision; start the installed app and inspect its tray menu.')

    def test_ambiguous_or_malformed_menu_rejects_before_writes_or_events(self):
        variants = []
        for index in (0, 2, 7):  # Duplicate Open, Hide or Quit is ambiguous.
            nodes = json.loads(json.dumps(NATIVE_MENU))
            duplicate = json.loads(json.dumps(nodes[index]))
            duplicate['data'][0] = 10
            nodes.append(duplicate)
            variants.append(nodes)
        both_visibility = json.loads(json.dumps(NATIVE_MENU))
        both_visibility.append({'type': '(ia{sv}av)', 'data': [10,
                               {'label': {'type': 's', 'data': 'Show the rose'}}, []]})
        variants.append(both_visibility)
        for field, bad in ((0, '4'), (0, True), (1, []), (2, {})):
            nodes = json.loads(json.dumps(NATIVE_MENU))
            nodes[2]['data'][field] = bad
            variants.append(nodes)
        for bad_label in ({'type': 'i', 'data': 4}, {'type': 's', 'data': 4}):
            nodes = json.loads(json.dumps(NATIVE_MENU))
            nodes[2]['data'][1]['label'] = bad_label
            variants.append(nodes)
        duplicate_id = json.loads(json.dumps(NATIVE_MENU))
        duplicate_id[0]['data'][0] = 4  # Must not alias Open's action ID.
        variants.append(duplicate_id)
        for nodes in variants:
            with self.subTest(nodes=nodes):
                self.state['items'][0]['nodes'] = nodes
                self.save_state()
                self.reject('Cannot uniquely identify Gentle Dot without an ID collision; start the installed app and inspect its tray menu.')

    def test_invalid_config_and_unsafe_paths_fail_closed(self):
        self.config.write_text('{broken')
        self.reject('Invalid shell.json; restore a valid version-1 bar layout first.')
        self.config.write_text(json.dumps(self.original))
        outside = self.root / 'outside'
        outside.write_text('do not touch')
        asset = self.source / 'assets/rose-glyph.svg'
        asset.unlink()
        asset.symlink_to(outside)
        self.reject('Unsafe source payload; use regular package files without symlinks.')
        asset.unlink()
        shutil.copyfile(ROOT / 'assets/rose-glyph.svg', asset)
        self.target.parent.mkdir()
        self.target.symlink_to(self.source, target_is_directory=True)
        self.reject('Unsafe installation path; remove symlinks or non-directory parents first.')
        self.assertEqual(outside.read_text(), 'do not touch')

    def test_unexpected_installed_edits_and_package_validation_fail_closed(self):
        shutil.copytree(self.source, self.target, ignore=shutil.ignore_patterns('scripts'))
        (self.target / 'BarWidget.qml').write_text('user edited')
        self.reject('Installed payload differs or contains unexpected files; preserve it and remove it manually before reinstalling.')
        (self.target / 'BarWidget.qml').write_bytes((self.source / 'BarWidget.qml').read_bytes())
        self.state['invalid_package'] = True
        self.save_state()
        self.reject('Plugin validation failed; run omarchy plugin validate on the plugin-only payload.')

    def test_post_commit_failure_is_honest_and_retains_backup(self):
        self.state['shell_failure'] = True
        self.save_state()
        result = self.run_cli('--app-path', str(self.app))
        backup, = self.config.parent.glob('shell.json.bak.gentle-dot.*')
        self.result(result, 2, '', 'Partial installation: shell rescanPlugins failed; restore shell availability and rerun this installer.\n' + f'Backup: {backup}\n')
        self.assertTrue(self.target.exists())
        self.assertNotEqual(json.loads(self.config.read_text()), self.original)
        self.assertEqual(self.account.read_text(), 'account sentinel')
        self.assertFalse(any(event[0] == 'busctl' for event in self.events()))

    def assert_shell_failure_recovers(self, operation):
        self.state['shell_failure'] = operation
        self.save_state()
        message = f'shell {operation} failed; restore shell availability and rerun this installer.'
        first = self.run_cli('--app-path', str(self.app))
        backup, = self.config.parent.glob('shell.json.bak.gentle-dot.*')
        self.result(first, 2, '', f'Partial installation: {message}\nBackup: {backup}\n')
        calls = [['omarchy-shell', ['shell', 'rescanPlugins']]]
        if operation == 'reloadConfig':
            calls.append(['omarchy-shell', ['shell', 'reloadConfig']])
        self.assertEqual(self.events(), calls)
        partial = self.snapshot()
        self.assertEqual((self.config.parent / '.gentle-dot-pending').stat().st_mode & 0o777, 0o600)
        self.result(self.run_cli(), 2, '', f'Partial installation: {message}\n')
        self.assertEqual(self.snapshot(), partial)
        self.assertEqual(self.events(), calls * 2)
        self.assertFalse(json.loads((self.root / 'state').read_text())['hidden'])
        self.state['shell_failure'] = False
        self.save_state()
        self.result(self.run_cli(), 0, 'Installed: one Gentle Dot rose configured.\n')
        self.assertEqual(self.events(), calls * 2 + [
            ['omarchy-shell', ['shell', 'rescanPlugins']],
            ['omarchy-shell', ['shell', 'reloadConfig']],
            ['busctl', ['--user', '--json=short', 'call', ':1.23', '/Menu',
                        'com.canonical.dbusmenu', 'Event', 'isvu', '4', 'clicked', 'i', '0', '0']]])
        partial.pop('.config/omarchy/.gentle-dot-pending')
        self.assertEqual(self.snapshot(), partial)
        self.assertEqual(backup.read_bytes(), json.dumps(self.original).encode())
        self.assertEqual(self.account.read_text(), 'account sentinel')
        self.assertTrue(json.loads((self.root / 'state').read_text())['hidden'])
        complete, events = self.snapshot(), self.events()
        self.result(self.run_cli(), 0, 'Unchanged: one Gentle Dot rose already configured.\n')
        self.assertEqual(self.snapshot(), complete)
        self.assertEqual(self.events(), events)

    def test_rescan_failure_retry_recovers_before_hiding(self):
        self.assert_shell_failure_recovers('rescanPlugins')

    def test_reload_failure_retry_recovers_before_hiding(self):
        self.assert_shell_failure_recovers('reloadConfig')

    def test_invalid_or_symlinked_recovery_marker_rejects_without_effects(self):
        marker = self.config.parent / '.gentle-dot-pending'
        marker.write_text('false')
        self.reject('Invalid recovery marker; inspect ~/.config/omarchy/.gentle-dot-pending before retrying.')
        marker.unlink()
        peer = self.root / 'peer'
        peer.write_text('[true, true]')
        marker.symlink_to(peer)
        self.reject('Unsafe installation path; remove symlinks or non-directory parents first.')
        self.assertEqual(peer.read_text(), '[true, true]')

    def test_private_config_backup_is_private_under_permissive_child_umask(self):
        self.config.chmod(0o600)
        self.success('--app-path', str(self.app))
        backup, = self.config.parent.glob('shell.json.bak.gentle-dot.*')
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.account.read_text(), 'account sentinel')
        self.assertEqual([event[0] for event in self.events()],
                         ['omarchy-shell', 'omarchy-shell', 'busctl'])

    def test_created_backup_write_or_close_failure_is_partial(self):
        self.config.chmod(0o600)
        for operation in ('write', 'close'):
            with self.subTest(operation=operation):
                before = self.snapshot()
                existing = set(self.config.parent.glob('shell.json.bak.gentle-dot.*'))
                self.filesystem_fault('backup-' + operation)
                result = self.run_cli('--app-path', str(self.app))
                backup, = set(self.config.parent.glob('shell.json.bak.gentle-dot.*')) - existing
                self.result(result, 2, '',
                            f'Partial installation: injected backup {operation} failure\nBackup: {backup}\n')
                expected = dict(before)
                expected[str(backup.relative_to(self.home))] = (
                    b'' if operation == 'write' else self.config.read_bytes())
                self.assertEqual(self.snapshot(), expected)
                self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
                self.assertFalse(self.target.exists())
                self.assertEqual(self.events(), [])

    def test_payload_directory_created_then_open_failure_is_partial(self):
        self.original['bar']['layout']['right'][0]['hidden'].append(NATIVE_ID)
        self.original['bar']['layout']['right'].append({'id': PLUGIN, 'appPath': str(self.app)})
        self.config.write_text(json.dumps(self.original))
        self.state['hidden'] = True
        self.save_state()
        before = self.snapshot()
        self.filesystem_fault('payload-open')
        result = self.run_cli()
        self.result(result, 2, '', 'Partial installation: injected payload open failure\n')
        self.assertTrue(self.target.is_dir())
        self.assertEqual(list(self.target.iterdir()), [])
        expected = dict(before)
        expected['.config/omarchy/.gentle-dot-pending'] = b'[true, false]'
        self.assertEqual(self.snapshot(), expected)
        self.assertEqual(list(self.config.parent.glob('shell.json.bak.gentle-dot.*')), [])
        self.assertEqual(self.events(), [])

    def test_lookup_uses_local_then_path_without_executing_either(self):
        local = self.home / '.local/bin/gentle-dot'
        local.parent.mkdir(parents=True)
        shutil.copyfile(self.app, local)
        local.chmod(0o755)
        self.success()
        self.assertEqual(json.loads(self.config.read_text())['bar']['layout']['right'][-1]['appPath'], str(local))
        self.assertFalse(any(e[0] == self.app.name for e in self.events()))
        # Empty saved appPath keeps automatic lookup rather than being rewritten.
        current = json.loads(self.config.read_text())
        current['bar']['layout']['right'][-1]['appPath'] = ''
        self.config.write_text(json.dumps(current))
        local.unlink()
        fallback = self.bin / 'gentle-dot'
        shutil.copyfile(self.app, fallback)
        fallback.chmod(0o755)
        before = self.snapshot()
        events = self.events()
        self.result(self.run_cli(), 0, 'Unchanged: one Gentle Dot rose already configured.\n')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.events(), events)

    def test_missing_or_symlinked_config_and_invalid_launcher_reject(self):
        self.config.unlink()
        self.reject('Invalid shell.json; restore a valid version-1 bar layout first.')
        external = self.root / 'external-config'
        external.write_text(json.dumps(self.original))
        self.config.symlink_to(external)
        self.reject('Unsafe installation path; remove symlinks or non-directory parents first.')
        self.config.unlink()
        self.config.write_text(json.dumps(self.original))
        self.app.chmod(0o644)
        self.reject(f'Native launcher is not executable: {self.app}. '
                    'Pass --app-path with an executable file.')
        self.assertEqual(json.loads(external.read_text()), self.original)

    def configured_app_path(self, path):
        current = json.loads(json.dumps(self.original))
        current['bar']['layout']['right'].append({'id': PLUGIN, 'appPath': str(path)})
        self.config.write_text(json.dumps(current))

    def test_stale_configured_app_path_is_named_with_the_widget_recovery(self):
        self.configured_app_path(self.app)
        self.app.unlink()
        before = self.snapshot()
        events = self.events()
        self.result(self.run_cli(), 1, '',
                    'Preflight rejected: Configured Gentle Dot appPath is not an executable file: '
                    f'{self.app}. Set appPath to the native launcher or clear it for automatic lookup. '
                    'Install the official app first if it is not installed.\n')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.events(), events)

    def test_configured_app_path_that_lost_its_execute_bit_is_named(self):
        self.configured_app_path(self.app)
        self.app.chmod(0o644)
        self.result(self.run_cli(), 1, '',
                    'Preflight rejected: Configured Gentle Dot appPath is not an executable file: '
                    f'{self.app}. Set appPath to the native launcher or clear it for automatic lookup. '
                    'Install the official app first if it is not installed.\n')

    def test_missing_launcher_reports_that_the_app_is_not_installed(self):
        self.result(self.run_cli(), 1, '',
                    'Preflight rejected: Native launcher is not executable; install the app first '
                    'or pass --app-path /absolute/launcher.\n')

    def test_empty_app_path_argument_is_reported_as_empty(self):
        self.result(self.run_cli('--app-path', ''), 1, '',
                    'Preflight rejected: Native launcher is not executable: the --app-path value is empty. '
                    'Pass --app-path with an executable file.\n')

    def test_configured_app_path_recovery_matches_the_widget_message(self):
        sentence = ('Configured Gentle Dot appPath is not an executable file: %s. '
                    'Set appPath to the native launcher or clear it for automatic lookup.')
        widget = (ROOT / 'toggle.sh').read_text()
        self.assertIn(sentence.replace('%s', '$1'), widget)
        self.configured_app_path(self.app)
        self.app.unlink()
        result = self.run_cli()
        self.assertTrue(result.stderr.startswith('Preflight rejected: ' + sentence.replace('%s', str(self.app))),
                        result.stderr)

    def test_concurrent_config_writer_is_not_overwritten(self):
        other = json.dumps(dict(self.original, other_writer='preserve'))
        self.state['concurrent_config'] = other
        self.save_state()
        self.result(self.run_cli('--app-path', str(self.app)), 1, '',
                    'Preflight rejected: shell.json changed concurrently; inspect it and rerun without overwriting the other writer.\n')
        self.assertEqual(self.config.read_text(), other)
        self.assertFalse(self.target.exists())
        self.assertEqual(list(self.config.parent.glob('shell.json.bak.*')), [])
        self.assertEqual(self.events(), [])
        self.assertEqual(self.account.read_text(), 'account sentinel')

    def test_unconfirmed_hide_is_partial_not_success(self):
        self.state['stuck'] = True
        self.save_state()
        result = self.run_cli('--app-path', str(self.app))
        backup, = self.config.parent.glob('shell.json.bak.gentle-dot.*')
        self.result(result, 2, '', 'Partial installation: Native rose hiding was not confirmed; inspect its tray menu and retry.\n' + f'Backup: {backup}\n')
        self.assertEqual([e[0] for e in self.events()], ['omarchy-shell', 'omarchy-shell', 'busctl'])
        self.assertEqual(json.loads(backup.read_text()), self.original)
        self.assertEqual(self.account.read_text(), 'account sentinel')

    def test_help_has_no_desktop_effects(self):
        before = self.snapshot()
        result = self.run_cli('--help')
        self.result(result, 0, '''usage: install.py [-h] [--app-path EXECUTABLE] [--install-native]
                  [--no-launch]

Install the Omarchy widget; --install-native explicitly builds the pinned
official native source first.

options:
  -h, --help            show this help message and exit
  --app-path EXECUTABLE
                        existing native launcher (one literal path); otherwise
                        preserve widget appPath, then try ~/.local/bin/gentle-
                        dot and PATH
  --install-native      guided build of the pinned official Gentle Dot source
                        before widget integration
  --no-launch           with --install-native, build only; do not start the
                        native app or modify Omarchy configuration

Native source setup is Omarchy-only, retains its source/runtime directory, and
asks before installing missing Arch build packages.
''')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.events(), [])


if __name__ == '__main__':
    unittest.main()
