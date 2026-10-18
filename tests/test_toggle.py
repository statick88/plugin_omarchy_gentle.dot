import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "toggle.sh"


class ToggleTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="gentle-dot-test-")
        self.addCleanup(self.scratch.cleanup)
        self.home = Path(self.scratch.name) / "home with spaces"
        self.bin = Path(self.scratch.name) / "bin"
        self.home.mkdir()
        self.bin.mkdir()
        self.env = {"HOME": str(self.home), "PATH": str(self.bin)}

    def executable(self, path, output="--toggle", code=0):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '#!/bin/sh\nprintf "%s\\n" "$*"\n'
            f'printf "%s\\n" "{output}" >&2\nexit {code}\n'
        )
        path.chmod(0o755)

    def run_toggle(self, *args):
        return subprocess.run(
            ["/bin/sh", str(LAUNCHER), *args], env=self.env,
            text=True, capture_output=True, timeout=3,
        )

    def assert_result(self, result, code, stdout, stderr):
        self.assertEqual(result.returncode, code)
        self.assertEqual(result.stdout, stdout)
        self.assertEqual(result.stderr, stderr)

    def test_explicit_launcher_is_literal_and_takes_precedence(self):
        app = Path(self.scratch.name) / "prepared app ; $(literal)" / "gentle-dot"
        self.executable(app, "explicit", 23)
        self.executable(self.home / ".local/bin/gentle-dot", "local")
        self.executable(self.bin / "gentle-dot", "path")
        before = sorted(Path(self.scratch.name).rglob("*"))
        self.assert_result(self.run_toggle(str(app)), 23, "--toggle\n", "explicit\n")
        self.assertEqual(sorted(Path(self.scratch.name).rglob("*")), before)

    def test_invalid_explicit_launcher_never_falls_back(self):
        self.executable(self.home / ".local/bin/gentle-dot", "local")
        self.executable(self.bin / "gentle-dot", "path")
        missing = Path(self.scratch.name) / "missing app"
        nonexecutable = Path(self.scratch.name) / "not executable"
        nonexecutable.write_text("not a launcher\n")
        directory = Path(self.scratch.name) / "directory"
        directory.mkdir()
        for app in (missing, nonexecutable, directory):
            with self.subTest(app=app):
                before = {p: p.read_bytes() for p in Path(self.scratch.name).rglob("*")
                          if p.is_file()}
                entries = sorted(Path(self.scratch.name).rglob("*"))
                self.assert_result(
                    self.run_toggle(str(app)), 127, "",
                    f"Configured Gentle Dot appPath is not an executable file: {app}. "
                    "Set appPath to the native launcher or clear it for automatic lookup.\n",
                )
                self.assertEqual(sorted(Path(self.scratch.name).rglob("*")), entries)
                self.assertEqual({p: p.read_bytes() for p in entries if p.is_file()}, before)

    def test_empty_app_path_preserves_automatic_lookup(self):
        self.executable(self.home / ".local/bin/gentle-dot", "local")
        self.executable(self.bin / "gentle-dot", "path")
        self.assert_result(self.run_toggle(""), 0, "--toggle\n", "local\n")

    def test_click_uses_local_app_even_without_local_bin_in_path(self):
        self.executable(self.home / ".local/bin/gentle-dot", "local")
        self.executable(self.bin / "gentle-dot", "path")
        self.assert_result(self.run_toggle(), 0, "--toggle\n", "local\n")

    def test_click_uses_app_from_path_when_local_launcher_is_broken(self):
        local = self.home / ".local/bin/gentle-dot"
        local.parent.mkdir(parents=True)
        local.symlink_to(self.home / "missing-app")
        self.executable(self.bin / "gentle-dot", "path")
        self.assert_result(self.run_toggle(), 0, "--toggle\n", "path\n")

    def test_missing_app_reports_action_without_creating_files(self):
        before = sorted(Path(self.scratch.name).rglob("*"))
        self.assert_result(
            self.run_toggle(), 127, "",
            "Gentle Dot is not installed or executable. Install the official app first.\n",
        )
        self.assertEqual(sorted(Path(self.scratch.name).rglob("*")), before)

    def test_app_failure_is_not_hidden_or_retried(self):
        self.executable(self.bin / "gentle-dot", "startup failed", 23)
        self.assert_result(self.run_toggle(), 23, "--toggle\n", "startup failed\n")


if __name__ == "__main__":
    unittest.main()
