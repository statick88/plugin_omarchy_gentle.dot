import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
REVISION = "8cb20ee888c88be2b359258a65499c20b59e2a86"


class BuildNativeTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="gentle build test ")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name) / "project with spaces"
        (self.root / "scripts").mkdir(parents=True)
        shutil.copyfile(ROOT / "scripts/build-native.sh", self.root / "scripts/build-native.sh")
        self.state = self.root / ".gentle-dot-install"
        self.state.mkdir()
        self.installer = self.state / "rustup-init.sh"
        self.installer.write_text("#!/bin/sh\nexit 99 # Retained installer must not run.\n")
        (self.root / "vendor/gentle-dot").mkdir(parents=True)
        self.tools = self.root / "fake-tools"
        self.tools.mkdir()
        self.log = self.tools / "calls.jsonl"
        dispatcher = self.tools / "dispatch"
        dispatcher.write_text(
            f"#!{sys.executable}\n"
            "import json, os, pathlib, sys\n"
            "tool = pathlib.Path(sys.argv[0]).name\n"
            "tools = pathlib.Path(__file__).resolve().parent\n"
            "state = tools.parent / '.gentle-dot-install'\n"
            "with (tools / 'calls.jsonl').open('a') as log:\n"
            "    log.write(json.dumps([tool, sys.argv[1:]]) + '\\n')\n"
            f"if tool == 'git': print('{REVISION}')\n"
            "elif tool == 'node':\n"
            "    if sys.argv[1:] == ['--version']: print('v26.8.2')\n"
            "elif tool == 'rustc': print('rustc 1.99.1 (fake)')\n"
            "elif tool == 'cargo': print('cargo 1.99.1 (fake)')\n"
            "elif tool == 'npm':\n"
            "    user = pathlib.Path(os.environ['npm_config_userconfig'])\n"
            "    glob = pathlib.Path(os.environ['npm_config_globalconfig'])\n"
            "    if user.resolve() == glob.resolve():\n"
            "        sys.stderr.write('Exit prior to config file resolving\\ncause\\n'\n"
            "                         f'double-loading config \"{glob}\" as \"global\", previously loaded as \"user\"\\n')\n"
            "        sys.exit(1)\n"
            "    for config in (user, glob):\n"
            "        assert config.is_absolute() and config.resolve().is_relative_to(state.resolve())\n"
            "        assert config.is_file() and config.read_bytes() == b''\n"
            "    pnpm = state / 'npm/bin/pnpm'\n"
            "    pnpm.parent.mkdir(parents=True)\n"
            "    pnpm.symlink_to(tools / 'dispatch')\n"
            "elif tool == 'pnpm':\n"
            "    if sys.argv[1:] == ['--version']: print('11.5.0')\n"
            "    elif sys.argv[1:] == ['--filter', '@gentle-dot/desktop', 'tauri', 'build', '--no-bundle']:\n"
            "        app = pathlib.Path(os.environ['CARGO_TARGET_DIR']) / 'release/gentle-dot'\n"
            "        app.parent.mkdir(parents=True)\n"
            "        app.write_text('#!/bin/sh\\nexit 0\\n')\n"
            "        app.chmod(0o755)\n"
            "elif tool == 'curl': sys.exit('Network access forbidden in this test')\n"
            "else: sys.exit('Unexpected command: ' + tool)\n"
        )
        dispatcher.chmod(0o755)
        for tool in ("git", "node", "npm", "pnpm", "rustc", "cargo", "curl"):
            (self.tools / tool).symlink_to(dispatcher)
        rustc = self.state / "cargo/bin/rustc"
        rustc.parent.mkdir(parents=True)
        rustc.symlink_to(dispatcher)

    def run_build(self, *args):
        return subprocess.run(
            ["/bin/sh", str(self.root / "scripts/build-native.sh"), *args],
            cwd=self.scratch.name, env={"PATH": f"{self.tools}:/usr/bin:/bin"},
            capture_output=True, text=True, timeout=5,
        )

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_reviewed_build_uses_distinct_empty_contained_npm_configs(self):
        retained = self.installer.read_bytes()
        result = self.run_build("--build-reviewed-installer")
        self.assertEqual((result.returncode, result.stdout, result.stderr), (
            0, "Native build ready. Retain vendor/gentle-dot and .gentle-dot-install; app not launched.\n", "",
        ))
        self.assertEqual(self.installer.read_bytes(), retained)
        self.assertEqual(self.calls(), [
            ["git", ["-C", str(self.root / "vendor/gentle-dot"), "rev-parse", "HEAD"]],
            ["node", ["-e", 'if (+process.versions.node.split(".")[0] < 24) process.exit(1)']],
            ["rustc", ["--version"]],
            ["npm", ["install", "--global", "--prefix", str(self.state / "npm"),
                     "--registry=https://registry.npmjs.org", "pnpm@11.5.0"]],
            ["pnpm", ["--version"]],
            ["pnpm", ["install", "--frozen-lockfile"]],
            ["pnpm", ["build"]],
            ["pnpm", ["--filter", "@gentle-dot/desktop", "tauri", "build", "--no-bundle"]],
            ["node", ["--version"]], ["pnpm", ["--version"]],
            ["rustc", ["--version"]], ["cargo", ["--version"]],
        ])
        self.assertEqual((self.state / "toolchain-versions").read_text(),
                         "v26.8.2\n11.5.0\nrustc 1.99.1 (fake)\ncargo 1.99.1 (fake)\n")
        self.assertEqual((self.state / "runtime-path").read_text(),
                         f"{self.state}/npm/bin:{self.state}/cargo/bin:{self.tools}:/usr/bin:/bin\n")

    def test_no_arguments_retains_installer_and_only_prepares(self):
        retained = self.installer.read_bytes()
        result = self.run_build()
        digest = hashlib.sha256(retained).hexdigest()
        self.assertEqual((result.returncode, result.stdout, result.stderr), (
            0, f'{digest}  {self.installer}\nInspect {self.installer}, then run:\n'
               f'/bin/sh "{self.root}/scripts/build-native.sh" --build-reviewed-installer\n', "",
        ))
        self.assertEqual(self.installer.read_bytes(), retained)
        self.assertEqual([tool for tool, args in self.calls()], ["git", "node"])
        for artifact in ("npm", "runtime-path", "toolchain-versions"):
            self.assertFalse((self.state / artifact).exists())


if __name__ == "__main__":
    unittest.main()
