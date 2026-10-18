import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = "vendor/gentle-dot/apps/desktop/src-tauri/target/release/gentle-dot"


class NativeLauncherTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="gentle native test ")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name) / "project with spaces"
        (self.root / "bin").mkdir(parents=True)
        launcher = ROOT / "bin/gentle-dot"
        if launcher.exists():
            shutil.copyfile(launcher, self.root / "bin/gentle-dot")
        self.env = {
            "PATH": "/usr/bin:/bin", "HOME": "/unwanted/home",
            "GENTLE_DOT_DATA_DIR": "/unwanted/data", "ENGRAM_URL": "http://unwanted",
            "ENGRAM_DATA_DIR": "/unwanted/memory", "ANTHROPIC_API_KEY": "fake-test-value",
            "GENTLE_DOT_AGENT_HOME": "/unwanted/agent", "GNOME_KEYRING_CONTROL": "/unwanted/keyring",
            "DISPLAY": ":99", "WAYLAND_DISPLAY": "wayland-test",
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/test/bus", "XDG_RUNTIME_DIR": "/run/user/test",
        }

    def fake_app(self, code=0):
        app = self.root / ARTIFACT
        app.parent.mkdir(parents=True)
        app.write_text(
            f"#!{sys.executable}\nimport json, os, sys\n"
            "print(json.dumps({'args': sys.argv[1:], 'env': dict(os.environ), 'cwd': os.getcwd()}))\n"
            f"sys.exit({code})\n"
        )
        app.chmod(0o755)

    def run_launcher(self, *args):
        return subprocess.run(
            ["/bin/sh", str(self.root / "bin/gentle-dot"), *args],
            env=self.env, cwd=self.scratch.name, capture_output=True, text=True, timeout=3,
        )

    def test_missing_artifact_is_actionable_and_creates_nothing(self):
        before = sorted(self.root.rglob("*"))
        result = self.run_launcher("--toggle")
        self.assertEqual(result.returncode, 127)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "Gentle Dot native artifact missing. Run scripts/build-native.sh (see its review step).\n")
        self.assertEqual(sorted(self.root.rglob("*")), before)

    def test_arguments_and_native_failure_are_forwarded_once(self):
        self.fake_app(23)
        result = self.run_launcher("--toggle", "two words", "", "*", "--help")
        self.assertEqual(result.returncode, 23)
        self.assertEqual(result.stderr, "")
        self.assertEqual(json.loads(result.stdout)["args"], ["--toggle", "two words", "", "*", "--help"])
        self.assertEqual(len(result.stdout.splitlines()), 1)

    def test_contained_environment_and_persistent_runtime_path(self):
        self.fake_app()
        state = self.root / ".gentle-dot-install"
        state.mkdir()
        (state / "runtime-path").write_text("/retained/node/bin:/usr/bin:/bin\n")
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["args"], [])
        self.assertEqual(payload["cwd"], str(state))
        env = payload["env"]
        self.assertEqual(env["HOME"], self.env["HOME"])
        for key, relative in {
            "XDG_CONFIG_HOME": ".config", "XDG_DATA_HOME": ".local/share",
            "XDG_CACHE_HOME": ".cache", "XDG_STATE_HOME": ".local/state",
        }.items():
            self.assertEqual(env[key], str(Path(self.env["HOME"]) / relative))
        for key, relative in {
            "GENTLE_DOT_DATA_DIR": "data", "TMPDIR": "tmp",
        }.items():
            self.assertEqual(env[key], str(state / relative))
            self.assertTrue((state / relative).is_dir())
        self.assertEqual(env["PATH"], "/retained/node/bin:/usr/bin:/bin")
        self.assertEqual(env["GENTLE_DOT_ENGRAM"], "private")
        self.assertEqual(env["GENTLE_DOT_ENGRAM_PORT"], "17438")
        for key in ("ENGRAM_URL", "ENGRAM_DATA_DIR", "ANTHROPIC_API_KEY", "GENTLE_DOT_AGENT_HOME", "GNOME_KEYRING_CONTROL"):
            self.assertNotIn(key, env)
        for key in ("DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR"):
            self.assertEqual(env[key], self.env[key])

    def test_desktop_environment_reaches_native_app_and_fake_browser(self):
        desktop = Path(self.scratch.name) / "desktop ; literal $HOME"
        desktop.mkdir()
        state = self.root / ".gentle-dot-install"
        (state / "data").mkdir(parents=True)
        sentinels = [desktop / "untouched-fixture", state / "data" / "untouched-fixture"]
        for sentinel in sentinels:
            sentinel.write_bytes(b"fixture-only, preserve exactly\n")
        desktop_env = {
            "HOME": str(desktop),
            "XDG_CONFIG_HOME": str(desktop / "config with spaces"),
            "XDG_DATA_HOME": str(desktop / "share"),
            "XDG_CACHE_HOME": str(desktop / "cache"),
            "XDG_STATE_HOME": str(desktop / "state"),
            "BROWSER": str(desktop / "fake browser"),
            "XDG_CURRENT_DESKTOP": "Hyprland:fixture desktop",
            "XDG_SESSION_TYPE": "wayland",
        }
        self.env.update(desktop_env)
        self.env.update(OPENAI_API_KEY="fixture-only", AWS_SECRET_ACCESS_KEY="fixture-only")
        opener = Path(desktop_env["BROWSER"])
        opener.write_text(
            f"#!{sys.executable}\nimport json, os, sys\n"
            "print(json.dumps({'args': sys.argv[1:], 'env': dict(os.environ)}, sort_keys=True))\n"
        )
        opener.chmod(0o755)
        self.fake_app()
        app = self.root / ARTIFACT
        app.write_text(
            f"#!{sys.executable}\nimport json, os, subprocess, sys\n"
            "print(json.dumps({'args': sys.argv[1:], 'env': dict(os.environ)}, sort_keys=True), flush=True)\n"
            "sys.exit(subprocess.call([os.environ['BROWSER'], 'https://fixture.invalid/no-network']))\n"
        )
        result = self.run_launcher("--toggle", "literal ; $HOME", "")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        expected_env = {
            **desktop_env,
            **{key: self.env[key] for key in (
                "DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR",
            )},
            "PATH": f"{state}/npm/bin:{state}/cargo/bin:/usr/bin:/bin",
            "GENTLE_DOT_DATA_DIR": str(state / "data"),
            "GENTLE_DOT_ENGRAM": "private", "GENTLE_DOT_ENGRAM_PORT": "17438",
            "TMPDIR": str(state / "tmp"),
            # CPython supplies this locale marker when starting from env -i.
            "LC_CTYPE": "C.UTF-8",
        }
        self.assertEqual(result.stdout, "".join(
            json.dumps({"args": args, "env": expected_env}, sort_keys=True) + "\n"
            for args in (["--toggle", "literal ; $HOME", ""], ["https://fixture.invalid/no-network"])
        ))
        for sentinel in sentinels:
            self.assertEqual(sentinel.read_bytes(), b"fixture-only, preserve exactly\n")
        self.assertEqual(sorted(p.name for p in desktop.iterdir()), ["fake browser", "untouched-fixture"])
        self.assertEqual(sorted(p.name for p in (state / "data").iterdir()), ["untouched-fixture"])

    def test_missing_or_empty_home_and_xdg_use_documented_fallbacks(self):
        self.fake_app()
        for missing in (True, False):
            with self.subTest(missing=missing):
                for key in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
                    if missing:
                        self.env.pop(key, None)
                    else:
                        self.env[key] = ""
                result = self.run_launcher()
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stderr, "")
                payload = json.loads(result.stdout)
                self.assertEqual(payload["args"], [])
                home = self.root / ".gentle-dot-install" / "home"
                self.assertEqual(payload["env"]["HOME"], str(home))
                for key, relative in {
                    "XDG_CONFIG_HOME": ".config", "XDG_DATA_HOME": ".local/share",
                    "XDG_CACHE_HOME": ".cache", "XDG_STATE_HOME": ".local/state",
                }.items():
                    self.assertEqual(payload["env"][key], str(home / relative))


if __name__ == "__main__":
    unittest.main()
