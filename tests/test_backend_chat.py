import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

from backend_fixture import FakeServer

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "scripts" / "backend_bridge.mjs"


class BackendChatTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="gentle-dot-chat-")
        self.addCleanup(self.scratch.cleanup)
        private = Path(self.scratch.name) / "private"
        private.mkdir(mode=0o700)
        self.token = private / "token"
        self.token.write_text("synthetic-capability\n")
        self.token.chmod(0o600)

    def request(self, server):
        return {"command": "connect", "consent": True,
                "url": f"ws://127.0.0.1:{server.port}/ws", "tokenFile": str(self.token)}

    def bridge(self, lines):
        return subprocess.run(["node", str(BRIDGE)], input="\n".join(map(json.dumps, lines)) + "\n",
                              text=True, capture_output=True, timeout=5)

    def live_bridge(self):
        process = subprocess.Popen(["node", str(BRIDGE)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, bufsize=1)
        self.addCleanup(lambda: process.poll() is None and process.kill())
        self.addCleanup(process.stdout.close)
        self.addCleanup(process.stderr.close)
        return process

    @staticmethod
    def send(process, value):
        process.stdin.write(json.dumps(value) + "\n")
        process.stdin.flush()

    def output(self, result):
        return [json.loads(line) for line in result.stdout.splitlines()]

    def test_granted_send_abort_and_native_stream_are_shared_normalized_events(self):
        events = [
            {"type": "user_message", "messageId": "u2", "text": "shared"},
            {"type": "message_delta", "messageId": "a2", "delta": "hel"},
            {"type": "message_done", "messageId": "a2", "text": "hello", "stopped": False, "error": "secret"},
            {"type": "agent_state", "state": "idle"},
            {"type": "ask", "question": "secret"},
            {"type": "error", "message": "secret"},
        ]
        server = FakeServer(send_events=events).start()
        self.addCleanup(server.close)
        process = self.live_bridge()
        self.send(process, self.request(server))
        self.assertEqual(json.loads(process.stdout.readline()), {"type": "status", "state": "connected", "modelLabel": "safe [redacted]"})
        self.send(process, {"command": "write_access", "enabled": True, "consent": True})
        self.assertEqual(json.loads(process.stdout.readline()), {"type": "write_access", "enabled": True})
        self.send(process, {"command": "send", "text": "hello", "consent": True})
        self.assertEqual([json.loads(process.stdout.readline()) for _ in range(6)], [
            {"type": "stream", "event": "user_message", "messageId": "u2", "text": "shared"},
            {"type": "stream", "event": "message_delta", "messageId": "a2", "delta": "hel"},
            {"type": "stream", "event": "message_done", "messageId": "a2", "text": "hello", "stopped": False, "error": True},
            {"type": "agent_state", "state": "idle"},
            {"type": "action_required", "message": "Use the full Gentle Dot app to respond."},
            {"type": "model_error", "message": "Model request failed."},
        ])
        self.send(process, {"command": "abort", "confirmed": True})
        deadline = time.monotonic() + 1
        while len(server.received) < 3 and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(server.received[-1:], [{"type": "abort"}])
        self.send(process, {"command": "disconnect"})
        self.assertEqual(json.loads(process.stdout.readline()), {"type": "write_access", "enabled": False})
        self.assertEqual(json.loads(process.stdout.readline()), {"type": "status", "state": "disconnected"})
        process.stdin.close()
        process.wait(timeout=5)
        self.assertEqual((process.returncode, process.stderr.read()), (0, ""))
        self.assertEqual(server.received, [
            {"type": "hello", "token": server.token, "protocol": 1},
            {"type": "send", "text": "hello"}, {"type": "abort"},
        ])

    def test_agent_state_allows_only_the_native_protocol_enum(self):
        marker = "SYNTHETIC-provider-secret-not-a-state"
        states = ["starting", "idle", "thinking", "working", "needs_you", "restarting", "error"]
        server = FakeServer(send_events=[{"type": "agent_state", "state": state} for state in [marker, *states]]).start()
        self.addCleanup(server.close)
        before = self.token.read_bytes()
        process = self.live_bridge()
        self.send(process, self.request(server))
        self.assertEqual(json.loads(process.stdout.readline())["state"], "connected")
        self.send(process, {"command": "write_access", "enabled": True, "consent": True})
        self.assertEqual(json.loads(process.stdout.readline()), {"type": "write_access", "enabled": True})
        self.send(process, {"command": "send", "text": "states", "consent": True})
        self.assertEqual([json.loads(process.stdout.readline()) for _ in states], [
            {"type": "agent_state", "state": state} for state in states
        ])
        self.send(process, {"command": "disconnect"})
        self.assertEqual(json.loads(process.stdout.readline()), {"type": "write_access", "enabled": False})
        self.assertEqual(json.loads(process.stdout.readline()), {"type": "status", "state": "disconnected"})
        process.stdin.close()
        process.wait(timeout=5)
        self.assertEqual((process.returncode, process.stderr.read(), self.token.read_bytes()), (0, "", before))
        self.assertEqual(server.received, [
            {"type": "hello", "token": server.token, "protocol": 1}, {"type": "send", "text": "states"},
        ])

    def test_rejected_writes_do_not_change_native_frames_or_token(self):
        server = FakeServer().start()
        self.addCleanup(server.close)
        before = self.token.read_bytes()
        result = self.bridge([self.request(server),
                              {"command": "send", "text": "no", "consent": True},
                              {"command": "write_access", "enabled": True, "consent": False},
                              {"command": "abort", "confirmed": True}])
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertEqual(self.output(result), [
            {"type": "status", "state": "connected", "modelLabel": "safe [redacted]"},
            {"type": "error", "message": "Request refused."},
            {"type": "error", "message": "Request refused."},
            {"type": "error", "message": "Request refused."},
        ])
        self.assertEqual(self.token.read_bytes(), before)
        self.assertEqual(server.received, [{"type": "hello", "token": server.token, "protocol": 1}])

    def test_revocation_invalidates_write_queued_behind_history(self):
        server = FakeServer(history="silent").start()
        self.addCleanup(server.close)
        process = self.live_bridge()
        self.send(process, self.request(server))
        self.assertEqual(json.loads(process.stdout.readline())["state"], "connected")
        self.send(process, {"command": "write_access", "enabled": True, "consent": True})
        self.assertEqual(json.loads(process.stdout.readline()), {"type": "write_access", "enabled": True})
        for request in ({"command": "history", "timeoutMs": 100},
                        {"command": "send", "text": "queued", "consent": True},
                        {"command": "write_access", "enabled": False},
                        {"command": "write_access", "enabled": True, "consent": True},
                        {"command": "abort", "confirmed": True}):
            self.send(process, request)
        self.assertEqual([json.loads(process.stdout.readline()) for _ in range(5)], [
            {"type": "write_access", "enabled": False},
            {"type": "error", "message": "Connection unavailable."},
            {"type": "error", "message": "Request refused."},
            {"type": "error", "message": "Request refused."},
            {"type": "error", "message": "Request refused."},
        ])
        process.stdin.close()
        process.wait(timeout=5)
        self.assertEqual((process.returncode, process.stderr.read()), (0, ""))
        self.assertEqual(server.received, [
            {"type": "hello", "token": server.token, "protocol": 1}, {"type": "get_history"},
        ])

    def test_read_only_connect_history_disconnect_is_unchanged(self):
        server = FakeServer(ready_events=[{"type": "message_delta", "messageId": "a2", "delta": "ignored"}]).start()
        self.addCleanup(server.close)
        result = self.bridge([self.request(server), {"command": "history"}, {"command": "disconnect"}])
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertEqual(self.output(result)[0]["type"], "status")
        self.assertEqual([event["type"] for event in self.output(result)], ["status", "history", "status"])
        self.assertEqual(server.received, [
            {"type": "hello", "token": server.token, "protocol": 1}, {"type": "get_history"},
        ])


if __name__ == "__main__":
    unittest.main()
