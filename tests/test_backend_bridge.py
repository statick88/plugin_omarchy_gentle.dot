import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from backend_fixture import FakeServer

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "scripts" / "backend_bridge.mjs"


class BackendBridgeTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="gentle-dot-bridge-")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.private = self.root / "private"
        self.private.mkdir(mode=0o700)
        self.token = self.private / "token"
        self.token.write_text("synthetic-capability\n")
        self.token.chmod(0o600)

    def run_bridge(self, lines, timeout=8):
        return subprocess.run(["node", str(BRIDGE)], input="\n".join(map(json.dumps, lines)) + "\n",
                              text=True, capture_output=True, timeout=timeout)

    def connect(self, server):
        return {"command": "connect", "consent": True,
                "url": f"ws://127.0.0.1:{server.port}/ws", "tokenFile": str(self.token)}

    def output(self, result):
        return [json.loads(line) for line in result.stdout.splitlines()]

    def test_protocol_hello_ready_and_read_only_history_are_normalized(self):
        server = FakeServer().start()
        self.addCleanup(server.close)
        result = self.run_bridge([self.connect(server), {"command": "history"}, {"command": "disconnect"}])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(self.output(result), [
            {"type": "status", "state": "connected", "modelLabel": "safe [redacted]"},
            {"type": "history", "history": [{"id": "u1", "role": "user", "text": "hello [redacted]"}, {"id": "a1", "role": "assistant", "text": "world"}]},
            {"type": "status", "state": "disconnected"},
        ])
        self.assertEqual(server.received, [{"type": "hello", "token": server.token, "protocol": 1}, {"type": "get_history"}])

    def test_denial_and_invalid_endpoint_have_no_file_or_network_effect(self):
        server = FakeServer().start()
        self.addCleanup(server.close)
        before = self.token.read_bytes()
        for request in (
            {**self.connect(server), "consent": False},
            {**self.connect(server), "url": "ws://localhost:1234/ws"},
            {"command": "connect", "consent": True, "url": "ws://127.0.0.1:9/ws?x=1", "tokenFile": str(self.token)},
        ):
            with self.subTest(request=request):
                result = self.run_bridge([request])
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '{"type":"error","message":"Request refused."}\n', ""))
                self.assertEqual(self.token.read_bytes(), before)
                self.assertEqual((server.connections, server.messages), (0, 0))

    def test_unsafe_files_and_invalid_json_never_connect_or_leak(self):
        server = FakeServer().start()
        self.addCleanup(server.close)
        link = self.private / "linked-token"
        link.symlink_to(self.token)
        bad = self.run_bridge([{**self.connect(server), "tokenFile": str(link)}])
        malformed = subprocess.run(["node", str(BRIDGE)], input="{bad}\n", text=True, capture_output=True, timeout=5)
        self.assertEqual((bad.returncode, bad.stdout, bad.stderr), (0, '{"type":"error","message":"Request refused."}\n', ""))
        self.assertEqual((malformed.returncode, malformed.stdout, malformed.stderr), (0, '{"type":"error","message":"Request refused."}\n', ""))
        self.assertEqual(server.connections, 0)
        self.assertNotIn("synthetic-capability", bad.stdout + bad.stderr + malformed.stdout + malformed.stderr)

    def test_failure_closes_and_does_not_retry_or_send_history_early(self):
        server = FakeServer(ready=False).start()
        self.addCleanup(server.close)
        result = self.run_bridge([self.connect(server), {"command": "history"}])
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '{"type":"error","message":"Connection unavailable."}\n{"type":"error","message":"Not connected."}\n', ""))
        self.assertEqual(server.messages, 1)

    def test_help_is_static_and_private_file_requirements_are_enforced(self):
        self.private.chmod(0o755)
        result = self.run_bridge([{**self.connect(FakeServer())}])
        help_result = subprocess.run(["node", str(BRIDGE), "--help"], text=True, capture_output=True, timeout=5)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '{"type":"error","message":"Request refused."}\n', ""))
        self.assertEqual(help_result.returncode, 0)
        self.assertIn("connect", help_result.stdout)
        self.assertEqual(help_result.stderr, "")


class BackendBridgeHistoryFailureTests(BackendBridgeTests):
    def assert_history_failure(self, server, request):
        before = self.token.read_bytes()
        result = self.run_bridge([self.connect(server), request])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(self.output(result)[0], {"type": "status", "state": "connected", "modelLabel": "safe [redacted]"})
        self.assertEqual(self.output(result)[-1], {"type": "error", "message": "Connection unavailable."})
        self.assertNotIn("history", [event["type"] for event in self.output(result)])
        self.assertNotIn(server.token, result.stdout + result.stderr)
        self.assertEqual(self.token.read_bytes(), before)
        self.assertEqual(server.received, [{"type": "hello", "token": server.token, "protocol": 1}, {"type": "get_history"}])

    def test_history_native_error_is_generic_not_empty_history(self):
        server = FakeServer(history="error").start()
        self.addCleanup(server.close)
        self.assert_history_failure(server, {"command": "history"})

    def test_history_peer_close_is_generic_not_empty_history(self):
        server = FakeServer(history="close").start()
        self.addCleanup(server.close)
        self.assert_history_failure(server, {"command": "history"})

    def test_history_short_timeout_is_generic_not_empty_history(self):
        server = FakeServer(history="silent").start()
        self.addCleanup(server.close)
        self.assert_history_failure(server, {"command": "history", "timeoutMs": 100})

    def test_empty_history_is_a_success_and_default_waits_past_old_deadline(self):
        empty = FakeServer(history="empty").start()
        self.addCleanup(empty.close)
        empty_result = self.run_bridge([self.connect(empty), {"command": "history"}])
        self.assertEqual((empty_result.returncode, empty_result.stderr), (0, ""))
        self.assertEqual(self.output(empty_result)[-1], {"type": "history", "history": []})
        delayed = FakeServer(delay=1.7).start()
        self.addCleanup(delayed.close)
        delayed_result = self.run_bridge([self.connect(delayed), {"command": "history"}])
        self.assertEqual((delayed_result.returncode, delayed_result.stderr), (0, ""))
        self.assertEqual(self.output(delayed_result)[-1]["type"], "history")

    def test_invalid_history_timeout_sends_no_history_request(self):
        server = FakeServer().start()
        self.addCleanup(server.close)
        before = self.token.read_bytes()
        result = self.run_bridge([self.connect(server), {"command": "history", "timeoutMs": 0}])
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertEqual(self.output(result)[-1], {"type": "error", "message": "Request refused."})
        self.assertEqual(self.token.read_bytes(), before)
        self.assertEqual(server.received, [{"type": "hello", "token": server.token, "protocol": 1}])

    def test_numeric_loopback_alias_is_refused_before_token_or_network(self):
        server = FakeServer().start()
        self.addCleanup(server.close)
        before = self.token.read_bytes()
        request = {**self.connect(server), "url": f"ws://2130706433:{server.port}/ws"}
        result = self.run_bridge([request])
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '{"type":"error","message":"Request refused."}\n', ""))
        self.assertEqual(self.token.read_bytes(), before)
        self.assertEqual((server.connections, server.messages), (0, 0))


if __name__ == "__main__":
    unittest.main()
