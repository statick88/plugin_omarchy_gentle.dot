"""Explicit Omarchy source setup; source/runtime remain outside the widget payload."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

SOURCE_URL = 'https://github.com/Gentleman-Programming/gentle-dot.git'
REVISION = '8cb20ee888c88be2b359258a65499c20b59e2a86'
LIBRARIES = ('webkit2gtk-4.1', 'base-devel', 'curl', 'wget', 'file', 'openssl',
             'appmenu-gtk-module', 'libayatana-appindicator', 'librsvg', 'xdotool', 'xz', 'pkgconf')


class NativeRejected(Exception):
    """Message and whether native setup may already have changed persistent state."""


def private_root():
    return Path.home() / '.local/share/gentle-dot-omarchy'


def source_root():
    return private_root() / REVISION / 'source'


def tools_root():
    return private_root() / 'tools'


def binary(source):
    return source / 'apps/desktop/src-tauri/target/release/gentle-dot'


def marker_path():
    return source_root().parent / 'native-build.json'


def launcher_path():
    """Where the plugin's automatic lookup looks for the native launcher."""
    return Path.home() / '.local/bin/gentle-dot'


def safe_launcher_path(launcher):
    for parent in reversed(launcher.parents):
        if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
            raise NativeRejected('Unsafe native launcher path; inspect it before retrying.', False)


def publish_launcher(executable, partial=False):
    """Expose the managed build at the path the plugin looks up.

    A working launcher that points somewhere else belongs to the user and is kept.
    A broken link is replaced, so a launcher left over from a deleted temporary
    build stops shadowing the managed one.
    """
    launcher = launcher_path()
    safe_launcher_path(launcher)
    if launcher.is_symlink():
        try:
            if launcher.resolve() == executable.resolve():
                return str(launcher), 'published'
        except OSError:
            pass
        if launcher.exists():
            return str(launcher), 'kept'
    elif launcher.exists():
        if launcher.is_file() and os.access(launcher, os.X_OK):
            return str(launcher), 'kept'
        raise NativeRejected('Unsafe native launcher path; inspect it before retrying.', partial)
    launcher.parent.mkdir(parents=True, exist_ok=True)
    temporary = launcher.parent / ('.gentle-dot-launcher-' + os.urandom(8).hex())
    try:
        os.symlink(str(executable), str(temporary))
        os.replace(str(temporary), str(launcher))
    except OSError as error:
        if temporary.is_symlink():
            temporary.unlink()
        raise NativeRejected('Native launcher publication failed; inspect it before retrying.', partial) from error
    return str(launcher), 'published'


def safe_path(path, directory=True):
    for parent in reversed(path.parents):
        if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
            raise NativeRejected('Unsafe native installation path; inspect it before retrying.', False)
    if path.is_symlink() or (path.exists() and not (path.is_dir() if directory else path.is_file())):
        raise NativeRejected('Unsafe native installation path; inspect it before retrying.', False)


def env_for(*, build=False):
    allowed = ('HOME', 'PATH', 'BROWSER', 'DISPLAY', 'WAYLAND_DISPLAY', 'XDG_RUNTIME_DIR',
               'XDG_SESSION_TYPE', 'XDG_CURRENT_DESKTOP', 'XDG_SESSION_DESKTOP',
               'XDG_DATA_HOME', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_STATE_HOME',
               'DBUS_SESSION_BUS_ADDRESS', 'LANG', 'LC_ALL', 'TERM', 'TMPDIR', 'TMP', 'TEMP')
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    if build:
        env.update(PATH=str(tools_root() / 'node_modules/.bin') + os.pathsep + env.get('PATH', ''),
                   GIT_TERMINAL_PROMPT='0', GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1',
                   CARGO_HOME=str(private_root() / 'cargo-cache'),
                   NPM_CONFIG_USERCONFIG=str(private_root() / '.npm-user.rc'),
                   NPM_CONFIG_GLOBALCONFIG=str(private_root() / '.npm-global.rc'),
                   npm_config_manage_package_manager_versions='false')
    return env


def run(argv, *, cwd=None, env=None, failure, partial=False, timeout=1800, interactive=False):
    try:
        result = subprocess.run(argv, cwd=cwd, env=env if env is not None else env_for(build=True),
                                text=True, capture_output=not interactive, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise NativeRejected(failure, partial) from error
    if result.returncode:
        raise NativeRejected(failure, partial)
    return (result.stdout or '').strip()


def version(name, args, minimum, exact=False):
    try:
        result = subprocess.run([name, *args], env=env_for(build=True), text=True,
                                capture_output=True, timeout=5)
        if result.returncode:
            return False
        token = next(word.lstrip('v') for word in result.stdout.split() if word.lstrip('v')[:1].isdigit())
        found = tuple(int(part) for part in token.split('.') if part.isdigit())
        return found == minimum if exact else found >= minimum
    except (OSError, ValueError, StopIteration, subprocess.TimeoutExpired):
        return False


def missing_dependencies():
    missing = []
    for package in LIBRARIES:
        try:
            result = subprocess.run(['pacman', '-Q', package], env=env_for(),
                                    capture_output=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise NativeRejected('Cannot inspect Arch packages; run this setup on Omarchy.', False) from error
        if result.returncode:
            missing.append(package)
    for executable, package, args, minimum in (
            ('git', 'git', [], ()), ('node', 'nodejs', ['--version'], (24,)),
            ('npm', 'npm', [], ()), ('rustc', 'rust', ['--version'], (1, 90)),
            ('cargo', 'rust', [], ())):
        present = bool(shutil.which(executable)) and (not args or version(executable, args, minimum))
        if not present and package not in missing:
            missing.append(package)
    return missing


def digest(path):
    safe_path(path, directory=False)
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def verify_source(source, partial):
    safe_path(source)
    safe_path(source / '.git')
    if not (source / '.git').is_dir():
        raise NativeRejected('Unsafe native source path; inspect it before retrying.', partial)
    remote = run(['git', '-C', str(source), 'config', '--get', 'remote.origin.url'],
                 failure='Official source revision verification failed.', partial=partial, timeout=10)
    revision = run(['git', '-C', str(source), 'rev-parse', 'HEAD'],
                   failure='Official source revision verification failed.', partial=partial, timeout=10)
    dirty = run(['git', '-C', str(source), 'status', '--porcelain', '--untracked-files=all'],
                failure='Native source integrity check failed.', partial=partial, timeout=10)
    if remote != SOURCE_URL or revision != REVISION:
        raise NativeRejected('Official source revision verification failed.', partial)
    if dirty:
        raise NativeRejected('Native source contains tracked or unexpected files; inspect it before retrying.', partial)


def prepare_source(source):
    if source.exists():
        verify_source(source, False)
        return False
    safe_path(source)
    source.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    run(['git', 'clone', '--no-checkout', SOURCE_URL, str(source)],
        failure='Official source download failed.', partial=True)
    run(['git', '-C', str(source), 'fetch', '--depth', '1', 'origin', REVISION],
        failure='Official source download failed.', partial=True)
    run(['git', '-C', str(source), 'checkout', '--detach', REVISION],
        failure='Official source checkout failed.', partial=True)
    verify_source(source, True)
    return True


def private_pnpm():
    return tools_root() / 'node_modules/.bin/pnpm'


def ensure_pnpm():
    safe_path(tools_root())
    for name in ('.npm-user.rc', '.npm-global.rc'):
        path = private_root() / name
        safe_path(path, directory=False)
        if not path.exists():
            with path.open('x'):
                pass
        elif path.read_bytes():
            raise NativeRejected('Private build configuration changed; inspect it before retrying.', True)
    pnpm = private_pnpm()
    if pnpm.is_file() and os.access(pnpm, os.X_OK) and version(str(pnpm), ['--version'], (11, 5, 0), exact=True):
        return pnpm
    run(['npm', 'install', '--prefix', str(tools_root()), '--ignore-scripts', '--no-audit',
         '--no-fund', '--registry=https://registry.npmjs.org', 'pnpm@11.5.0'],
        failure='Private pnpm 11.5.0 bootstrap failed.', partial=True)
    if not pnpm.is_file() or not os.access(pnpm, os.X_OK) or not version(str(pnpm), ['--version'], (11, 5, 0), exact=True):
        raise NativeRejected('Private pnpm 11.5.0 verification failed.', True)
    return pnpm


def read_marker(source, executable, pnpm):
    path = marker_path()
    safe_path(path, directory=False)
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return False
    return data == {'revision': REVISION, 'source': str(source), 'binary': str(executable),
                    'binary_sha256': digest(executable), 'pnpm': str(pnpm), 'pnpm_version': '11.5.0'}


def write_marker(source, executable, pnpm):
    path = marker_path()
    safe_path(path, directory=False)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix='.native-build-', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump({'revision': REVISION, 'source': str(source), 'binary': str(executable),
                       'binary_sha256': digest(executable), 'pnpm': str(pnpm), 'pnpm_version': '11.5.0'}, stream)
            stream.flush(); os.fsync(stream.fileno())
        safe_path(path, directory=False)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def acquire_lock():
    safe_path(private_root())
    private_root().mkdir(parents=True, exist_ok=True, mode=0o700)
    path = private_root() / '.install.lock'
    safe_path(path)
    try:
        path.mkdir(mode=0o700)
    except FileExistsError:
        raise NativeRejected('Another native installation is in progress; wait for it to finish and retry.', False) from None
    return path, path.stat().st_ino


def start_if_needed(executable, ready):
    if ready is not None:
        try:
            ready()
            return False
        except Exception:
            pass
    try:
        subprocess.Popen([str(executable)], env=env_for(), stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError as error:
        raise NativeRejected('Native launch failed.', True) from error
    if ready is not None:
        for _ in range(100):
            try:
                ready()
                return True
            except Exception:
                time.sleep(.1)
        raise NativeRejected('Native launch was not ready through its public tray identity.', True)
    return True


def setup(no_launch=False, ready=None, existing=None):
    if sys.platform != 'linux' or not os.environ.get('OMARCHY_PATH') or not shutil.which('omarchy'):
        raise NativeRejected('Native setup is supported only on Omarchy.', False)
    if existing is not None and not no_launch:
        changed = start_if_needed(existing, ready)
        print(f'Native build ready: {existing}')
        return str(existing), changed
    safe_path(private_root())
    missing = missing_dependencies()
    if missing:
        print('Missing build dependencies: ' + ' '.join(missing))
        try:
            answer = input('Install these Arch packages now? [y/N] ')
        except EOFError:
            answer = ''
        if answer.strip().casefold() not in ('y', 'yes'):
            raise NativeRejected('dependency installation declined.', False)
    old_mask = os.umask(0o077)
    lock = None
    partial = False
    try:
        lock, inode = acquire_lock()
        if missing:
            partial = True
            run(['sudo', 'pacman', '-S', '--needed', *missing], env=env_for(), interactive=True,
                failure='dependency installation failed.', partial=True)
            if missing_dependencies():
                raise NativeRejected('Required build dependencies are still unavailable after package installation.', True)
        source, executable = source_root(), binary(source_root())
        partial = prepare_source(source) or partial
        pnpm = ensure_pnpm()
        safe_path(executable, directory=False)
        if not (executable.is_file() and os.access(executable, os.X_OK) and read_marker(source, executable, pnpm)):
            partial = True
            run([str(pnpm), 'install', '--frozen-lockfile'], cwd=source,
                failure='Native dependency build failed.', partial=True)
            run([str(pnpm), 'build'], cwd=source, failure='Native frontend build failed.', partial=True)
            run([str(pnpm), '--filter', '@gentle-dot/desktop', 'tauri', 'build', '--no-bundle'], cwd=source,
                failure='Native desktop build failed; the bounded build phase exceeded its limit or failed.', partial=True)
            safe_path(executable, directory=False)
            if not executable.is_file() or not os.access(executable, os.X_OK):
                raise NativeRejected('Native desktop build did not produce its launcher.', True)
            write_marker(source, executable, pnpm)
        launcher, state = publish_launcher(executable, partial)
        if not no_launch:
            partial = start_if_needed(executable, ready) or partial
        print(f'Native build ready: {executable}')
        print(f'Native launcher {state}: {launcher}')
        return str(executable), partial
    except OSError as error:
        raise NativeRejected('Native filesystem operation failed; inspect retained files before retrying.', True) from error
    finally:
        if lock is not None:
            try:
                if not lock.is_symlink() and lock.stat().st_ino == inode:
                    lock.rmdir()
            except OSError:
                pass
        os.umask(old_mask)
