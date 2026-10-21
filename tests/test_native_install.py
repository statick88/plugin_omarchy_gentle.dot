"""Public installer CLI tests; all desktop/build/package commands are fixtures."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
REVISION = '8cb20ee888c88be2b359258a65499c20b59e2a86'
URL = 'https://github.com/Gentleman-Programming/gentle-dot.git'
LIBRARIES = ('webkit2gtk-4.1', 'base-devel', 'curl', 'wget', 'file', 'openssl',
             'appmenu-gtk-module', 'libayatana-appindicator', 'librsvg', 'xdotool', 'xz', 'pkgconf')
MISSING = (*LIBRARIES, 'nodejs', 'rust')
PROMPT = 'Install these Arch packages now? [y/N] '
FAKE = r'''import json, os, pathlib, sys, time
root = pathlib.Path(ROOT_LITERAL)
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with (root / 'events').open('a') as f: f.write(json.dumps([name, args]) + '\n')
def option(key, default=''):
    p = root / key
    return p.read_text() if p.exists() else default
def emit(kind, data): print(json.dumps({'type': kind, 'data': data}))
if name == 'pacman':
    missing = json.loads(option('missing-packages', 'null'))
    sys.exit(0 if (root / 'dependencies').exists() or missing is not None and args[-1] not in missing else 1)
if name in ('node', 'rustc'):
    if (root / 'dependencies').exists() or (root / 'tools-ready').exists():
        print('v24.0.0' if name == 'node' else 'rustc 1.90.0')
    sys.exit(0)
if name == 'sudo':
    (root / 'dependencies').write_text('installed'); sys.exit(0)
if name == 'git':
    if args[:2] == ['clone', '--no-checkout']:
        target = pathlib.Path(args[-1]); target.mkdir(parents=True); (target / '.git').mkdir()
    elif args[-1] == 'remote.origin.url': print(option('remote', 'https://github.com/Gentleman-Programming/gentle-dot.git'))
    elif args[-2:] == ['rev-parse', 'HEAD']: print(option('revision', '8cb20ee888c88be2b359258a65499c20b59e2a86'))
    elif 'status' in args: print(option('dirty'))
    sys.exit(0)
if name == 'npm':
    target = pathlib.Path(args[args.index('--prefix') + 1]) / 'node_modules/.bin/pnpm'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(pathlib.Path(sys.argv[0]).read_text()); target.chmod(0o755); sys.exit(0)
if name == 'pnpm':
    if args == ['--version']: print(option('pnpm-version', '11.5.0')); sys.exit(0)
    if args == ['build']:
        if option('mode') == 'fail-build': sys.exit(1)
        if option('mode') == 'block-build':
            (root / 'build-entered').touch()
            deadline = time.monotonic() + 5
            while not (root / 'release-build').exists() and time.monotonic() < deadline: time.sleep(.02)
    if args == ['--filter', '@gentle-dot/desktop', 'tauri', 'build', '--no-bundle']:
        target = pathlib.Path.cwd() / 'apps/desktop/src-tauri/target/release/gentle-dot'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('#!/missing' if option('mode') == 'broken-launch' else pathlib.Path(sys.argv[0]).read_text())
        target.chmod(0o755)
    sys.exit(0)
if name in ('gentle-dot', 'native-existing'):
    (root / 'native-env').write_text(json.dumps(dict(os.environ)))
    (root / 'native-ready').touch(); sys.exit(0)
if name in ('omarchy', 'omarchy-shell'): sys.exit(0)
if name == 'busctl':
    args = args[2:]
    if args[0] == 'get-property':
        prop = args[-1]
        if prop == 'RegisteredStatusNotifierItems': emit('as', [':1.23/StatusNotifierItem'] if (root / 'native-ready').exists() else [])
        else: emit('o' if prop == 'Menu' else 's', {'Id':'tray-icon tray app main','Title':'gentle-dot','Menu':'/Menu'}[prop])
    elif 'GetLayout' in args:
        label = 'Show the rose' if (root / 'hidden').exists() else 'Hide the rose'
        children = [{'type':'(ia{sv}av)','data':[i,{'label':{'type':'s','data':text}},[]]} for i,text in ((2,'Open'),(4,label),(9,'Quit'))]
        emit('u(ia{sv}av)', [1,[0,{},children]])
    else: (root / 'hidden').touch()
    sys.exit(0)
'''


class NativeInstallTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / '.gentle-dot-install'
        scratch.mkdir(mode=0o700, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix='native-test-', dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home, self.bin = self.root / 'home', self.root / 'bin'
        self.home.mkdir(); self.bin.mkdir()
        script = '#!' + sys.executable + '\n' + FAKE.replace('ROOT_LITERAL', repr(str(self.root)))
        for name in ('git', 'npm', 'pnpm', 'sudo', 'node', 'rustc', 'cargo', 'pacman', 'busctl', 'omarchy', 'omarchy-shell', 'native-existing'):
            p = self.bin / name; p.write_text(script); p.chmod(0o755)
        self.env = {'HOME': str(self.home), 'TMPDIR': str(self.root), 'PATH': str(self.bin),
                    'OMARCHY_PATH': '/usr/share/omarchy', 'PYTHONDONTWRITEBYTECODE': '1'}
        self.account = self.home / 'account.sentinel'; self.account.write_text('unchanged account')
        self.source = self.home / '.local/share/gentle-dot-omarchy' / REVISION / 'source'
        self.launcher = self.source / 'apps/desktop/src-tauri/target/release/gentle-dot'
        self.published = self.home / '.local/bin/gentle-dot'
        self.plan = 'Missing build dependencies: ' + ' '.join(MISSING) + '\n' + PROMPT

    def cli(self, *args, answer=''):
        return subprocess.run([sys.executable, str(ROOT / 'scripts/install.py'), *args], input=answer,
                              env=self.env, capture_output=True, text=True, timeout=15)

    def assert_result(self, result, code, out='', err=''):
        self.assertEqual((result.returncode, result.stdout, result.stderr), (code, out, err))
        self.assertEqual(self.account.read_text(), 'unchanged account')

    def events(self):
        p = self.root / 'events'
        return [json.loads(line) for line in p.read_text().splitlines()] if p.exists() else []

    def configured(self, app=None):
        p = self.home / '.config/omarchy/shell.json'; p.parent.mkdir(parents=True, exist_ok=True)
        right = [{'id':'omarchy.tray','hidden':['peer'],'pinned':['mail']}]
        if app: right.append({'id':'statick.gentle-dot','appPath':str(app)})
        p.write_text(json.dumps({'version':1,'bar':{'layout':{'left':[],'center':[],'right':right}}}))
        return p

    def build(self):
        result = self.cli('--install-native', '--no-launch', answer='y\n')
        self.assert_result(result, 0, self.plan + f'Native build ready: {self.launcher}\n'
                         + f'Native launcher published: {self.published}\n')

    def test_decline_and_eof_leave_home_and_package_counters_unchanged(self):
        for answer in ('n\n', ''):
            before = {str(p):p.read_bytes() for p in self.home.rglob('*') if p.is_file()}
            self.assert_result(self.cli('--install-native','--no-launch',answer=answer), 1, self.plan,
                               'Preflight rejected: dependency installation declined.\n')
            self.assertEqual(before, {str(p):p.read_bytes() for p in self.home.rglob('*') if p.is_file()})
        self.assertFalse(any(name in ('sudo','git','npm','pnpm') for name,_ in self.events()))

    def test_only_missing_packages_are_proposed(self):
        (self.root / 'tools-ready').touch(); (self.root / 'missing-packages').write_text('["librsvg"]')
        self.assert_result(self.cli('--install-native','--no-launch',answer='n\n'), 1,
                           'Missing build dependencies: librsvg\n' + PROMPT,
                           'Preflight rejected: dependency installation declined.\n')
        self.assertFalse(any(name in ('sudo','git','npm','pnpm') for name,_ in self.events()))

    def test_official_layout_and_completed_retry_do_not_rebuild_or_launch(self):
        self.build(); before = len(self.events())
        self.assertTrue(self.launcher.is_file())
        self.assertIn(['git',['-C',str(self.source),'checkout','--detach',REVISION]], self.events())
        self.assertIn(['pnpm',['--filter','@gentle-dot/desktop','tauri','build','--no-bundle']], self.events())
        self.assertIn(['sudo',['pacman','-S','--needed',*MISSING]], self.events())
        self.assertFalse((self.root / 'native-ready').exists())
        self.assert_result(self.cli('--install-native','--no-launch'),0,
                           f'Native build ready: {self.launcher}\n'
                           f'Native launcher published: {self.published}\n')
        self.assertFalse(any(name=='sudo' or name=='pnpm' and args!=['--version'] or name=='npm'
                             for name,args in self.events()[before:]))

    def test_build_failure_does_not_configure_or_launch(self):
        (self.root / 'mode').write_text('fail-build')
        self.assert_result(self.cli('--install-native','--no-launch',answer='y\n'),2,self.plan,
                           'Partial installation: Native frontend build failed.\n')
        self.assertFalse((self.home / '.config').exists())
        self.assertFalse((self.root / 'native-ready').exists())

    def test_wrong_pin_does_not_build_configure_or_launch(self):
        (self.root / 'revision').write_text('wrong')
        self.assert_result(self.cli('--install-native','--no-launch',answer='y\n'),2,self.plan,
                           'Partial installation: Official source revision verification failed.\n')
        self.assertFalse((self.home / '.config').exists())
        self.assertFalse((self.root / 'native-ready').exists())
        self.assertFalse(any(name in ('npm','pnpm') for name,_ in self.events()))

    def test_dirty_source_is_rejected_without_rebuild(self):
        self.build(); before = len(self.events()); (self.root / 'dirty').write_text(' M package.json')
        self.assert_result(self.cli('--install-native','--no-launch'),1,'',
                           'Preflight rejected: Native source contains tracked or unexpected files; inspect it before retrying.\n')
        self.assertFalse(any(name in ('npm','sudo') or name=='pnpm' and args!=['--version'] for name,args in self.events()[before:]))

    def test_symlinked_parent_is_rejected_without_touching_destination(self):
        outside=self.root/'outside'; outside.mkdir(); (self.home/'.local').symlink_to(outside)
        (self.root/'dependencies').touch()
        self.assert_result(self.cli('--install-native','--no-launch'),1,'',
                           'Preflight rejected: Unsafe native installation path; inspect it before retrying.\n')
        self.assertEqual(list(outside.iterdir()),[])
        self.assertFalse(any(name in ('sudo','git','npm','pnpm') for name,_ in self.events()))

    def test_wrong_private_pnpm_never_executes_build(self):
        (self.root/'pnpm-version').write_text('11.6.0')
        self.assert_result(self.cli('--install-native','--no-launch',answer='y\n'),2,self.plan,
                           'Partial installation: Private pnpm 11.5.0 verification failed.\n')
        self.assertFalse(any(name=='pnpm' and args!=['--version'] for name,args in self.events()))
        self.assertFalse((self.home/'.config').exists())

    def test_no_launch_then_launch_retry_preserves_desktop_environment(self):
        self.build(); config=self.configured(); before=len(self.events())
        self.env.update(BROWSER='browser --new-window', XDG_CACHE_HOME=str(self.home/'cache'),
                        XDG_STATE_HOME=str(self.home/'state'), GENTLE_DOT_DATA_DIR='/wrong',
                        OPENAI_API_KEY='secret-canary', NODE_OPTIONS='--bad-option')
        result=self.cli('--install-native')
        backups=list(config.parent.glob('shell.json.bak.gentle-dot.*'))
        self.assertEqual(len(backups),1)
        self.assert_result(result,0,f'Native build ready: {self.published}\n'
                         f'Installed: one Gentle Dot rose configured.\nBackup: {backups[0]}\n')
        env=json.loads((self.root/'native-env').read_text())
        for key in ('HOME','BROWSER','XDG_CACHE_HOME','XDG_STATE_HOME'): self.assertEqual(env[key],self.env[key])
        for key in ('GENTLE_DOT_DATA_DIR','OPENAI_API_KEY','NODE_OPTIONS'): self.assertNotIn(key,env)
        self.assertFalse(any(name in ('sudo','npm') or name=='pnpm' and args!=['--version'] for name,args in self.events()[before:]))

    def test_valid_existing_installation_is_not_rebuilt_or_replaced(self):
        app=self.bin/'native-existing'; config=self.configured(app); (self.root/'native-ready').touch()
        result=self.cli('--install-native'); backups=list(config.parent.glob('shell.json.bak.gentle-dot.*'))
        self.assertEqual(len(backups),1)
        self.assert_result(result,0,f'Native build ready: {app}\nInstalled: one Gentle Dot rose configured.\nBackup: {backups[0]}\n')
        self.assertFalse(any(name in ('git','npm','pnpm','pacman','sudo','native-existing') for name,_ in self.events()))
        self.assertEqual(json.loads(config.read_text())['bar']['layout']['right'][1]['appPath'],str(app))

    def test_other_omarchy_environment_is_rejected_before_commands(self):
        self.env.pop('OMARCHY_PATH')
        self.assert_result(self.cli('--install-native','--no-launch'),1,'',
                           'Preflight rejected: Native setup is supported only on Omarchy.\n')
        self.assertEqual(self.events(),[])

    def test_concurrent_installer_is_refused_through_public_cli(self):
        (self.root/'dependencies').touch(); (self.root/'mode').write_text('block-build')
        first=subprocess.Popen([sys.executable,str(ROOT/'scripts/install.py'),'--install-native','--no-launch'],
                               env=self.env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            deadline=time.monotonic()+5
            while not (self.root/'build-entered').exists() and time.monotonic()<deadline: time.sleep(.02)
            self.assertTrue((self.root/'build-entered').exists())
            self.assert_result(self.cli('--install-native','--no-launch'),1,'',
                               'Preflight rejected: Another native installation is in progress; wait for it to finish and retry.\n')
        finally:
            (self.root/'release-build').touch()
            out,err=first.communicate(timeout=10)
        self.assertEqual((first.returncode,out,err),
                         (0,f'Native build ready: {self.launcher}\n'
                          f'Native launcher published: {self.published}\n',''))

    def test_managed_setup_publishes_a_stable_launcher(self):
        self.build()
        self.assertTrue(self.published.is_symlink())
        self.assertEqual(self.published.resolve(), self.launcher.resolve())
        self.assertTrue(os.access(self.published, os.X_OK))
        # The published link points at the managed private root, never a temporary tree.
        self.assertTrue(str(self.published.resolve()).startswith(str(self.source)))

    def test_broken_launcher_link_is_replaced_by_the_managed_build(self):
        self.published.parent.mkdir(parents=True)
        self.published.symlink_to(self.root / 'deleted-build')
        self.build()
        self.assertEqual(self.published.resolve(), self.launcher.resolve())

    def test_working_foreign_launcher_is_preserved(self):
        self.published.parent.mkdir(parents=True)
        self.published.write_text('#!/bin/sh\nexit 0\n')
        self.published.chmod(0o755)
        result = self.cli('--install-native', '--no-launch', answer='y\n')
        self.assertEqual(result.returncode, 0)
        self.assertIn(f'Native launcher kept: {self.published}', result.stdout)
        self.assertFalse(self.published.is_symlink())
        self.assertEqual(self.published.read_text(), '#!/bin/sh\nexit 0\n')

    def test_symlinked_launcher_directory_is_rejected_without_writing_outside(self):
        (self.home / '.local/share').mkdir(parents=True)
        outside = self.root / 'outside'
        outside.mkdir()
        (self.home / '.local/bin').symlink_to(outside)
        result = self.cli('--install-native', '--no-launch', answer='y\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Unsafe native launcher path', result.stderr)
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
