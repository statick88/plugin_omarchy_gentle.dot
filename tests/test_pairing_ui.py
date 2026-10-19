"""Public QML pairing behavior against the production controller and synthetic WS."""
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from backend_fixture import FakeServer

ROOT = Path(__file__).resolve().parents[1]
PREVIEW = ROOT / "tests" / "popup_preview" / "run_preview.py"


class PairingUiTests(unittest.TestCase):
    def run_pairing(self, *extra):
        self.scratch = tempfile.TemporaryDirectory(prefix="gentle-dot-pairing-")
        self.addCleanup(self.scratch.cleanup)
        private = Path(self.scratch.name) / "private"
        private.mkdir(mode=0o700)
        token = private / "token"
        token.write_text("synthetic-capability\n")
        token.chmod(0o600)
        server = None if "--bridge-exit" in extra else FakeServer().start()
        if server is not None:
            self.addCleanup(server.close)
        endpoint = f"ws://127.0.0.1:{server.port}/ws" if server else "ws://127.0.0.1:1/ws"
        result = subprocess.run([sys.executable, str(PREVIEW), "--pairing", endpoint, str(token), *extra],
                                text=True, capture_output=True, timeout=15)
        return result, server, token

    def test_explicit_consent_reads_only_synthetic_history_then_cleans_up(self):
        result, server, token = self.run_pairing()
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (0, "T17_RESULT failures=0\n", ""))
        self.assertEqual(server.received, [
            {"type": "hello", "token": server.token, "protocol": 1},
            {"type": "get_history"},
        ])
        self.assertEqual((server.connections, server.messages), (1, 2))
        self.assertEqual(token.read_text(), "synthetic-capability\n")
        self.assertNotIn("synthetic-capability", result.stdout + result.stderr)

    def test_abrupt_owned_bridge_exit_becomes_generic_error(self):
        result, server, token = self.run_pairing("--bridge-exit")
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (0, "T17_RESULT failures=0\n", ""))
        self.assertIsNone(server)
        self.assertEqual(token.read_text(), "synthetic-capability\n")
        self.assertNotIn("synthetic-capability", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
