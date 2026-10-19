"""Synthetic protocol-v1 WebSocket fixture; never a Gentle Dot daemon."""
import base64
import hashlib
import json
import socket
import threading
import time


class FakeServer:
    def __init__(self, token="synthetic-capability", ready=True, history="normal", delay=0, send_events=None, ready_events=None):
        self.token, self.ready = token, ready
        self.history, self.delay = history, delay
        self.send_events = send_events or []
        self.ready_events = ready_events or []
        self.connections = self.messages = 0
        self.received = []
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        self.thread = threading.Thread(target=self._serve, daemon=True)

    def start(self):
        self.thread.start()
        return self

    def close(self):
        self.sock.close()
        self.thread.join(1)

    def _serve(self):
        try:
            conn, _ = self.sock.accept()
            self.connections += 1
            with conn:
                request = conn.recv(8192).decode("ascii")
                headers = dict(line.split(": ", 1) for line in request.split("\r\n") if ": " in line)
                key = headers["sec-websocket-key"]
                accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
                conn.sendall(f"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: {accept}\r\n\r\n".encode())
                while True:
                    message = self._read(conn)
                    if message is None:
                        return
                    self.messages += 1
                    self.received.append(message)
                    if message.get("type") == "hello" and self.ready:
                        self._send(conn, {"type": "ready", "agentState": "idle", "model": "safe " + self.token})
                        for event in self.ready_events:
                            self._send(conn, event)
                    elif message.get("type") == "get_history":
                        self._history(conn)
                    elif message.get("type") == "send":
                        for event in self.send_events:
                            self._send(conn, event)
        except OSError:
            pass

    def _history(self, conn):
        if self.history == "close":
            conn.close()
            return
        if self.history == "silent":
            return
        if self.delay:
            time.sleep(self.delay)
        if self.history == "error":
            self._send(conn, {"type": "error", "code": "test", "message": "leak " + self.token})
        elif self.history == "empty":
            self._send(conn, {"type": "history", "messages": []})
        else:
            self._send(conn, {"type": "history", "messages": [
                {"id": "u1", "role": "user", "text": "hello " + self.token, "activities": []},
                {"id": "a1", "role": "assistant", "text": "world", "activities": []},
                {"id": "tool", "role": "assistant", "content": [{"type": "image", "url": "ignored"}]},
            ]})

    @staticmethod
    def _exact(conn, count):
        data = bytearray()
        while len(data) < count:
            part = conn.recv(count - len(data))
            if not part:
                return None
            data.extend(part)
        return bytes(data)

    @classmethod
    def _read(cls, conn):
        head = cls._exact(conn, 2)
        if not head:
            return None
        opcode, length = head[0] & 15, head[1] & 127
        if length == 126:
            length = int.from_bytes(cls._exact(conn, 2), "big")
        if opcode == 8:
            return None
        mask, data = cls._exact(conn, 4), cls._exact(conn, length)
        return json.loads(bytes(v ^ mask[i % 4] for i, v in enumerate(data)).decode())

    @staticmethod
    def _send(conn, value):
        data = json.dumps(value).encode()
        header = bytes([129, len(data)]) if len(data) < 126 else bytes([129, 126]) + len(data).to_bytes(2, "big")
        conn.sendall(header + data)
