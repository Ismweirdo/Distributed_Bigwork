"""
Distributed Chatroom — automated tests
---------------------------------------
Run with:
    python -m pytest test_chatroom.py -v
or:
    python test_chatroom.py
"""

import socket
import threading
import time
import unittest

# Import server helpers directly so we can spin up a real server in-process.
from server import start_server


def _run_server(host: str, port: int) -> threading.Thread:
    """Start a chat server in a daemon thread and wait until it is accepting connections."""
    t = threading.Thread(target=start_server, args=(host, port), daemon=True)
    t.start()
    # Poll until the server is actually accepting connections (up to 5 s).
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            probe = socket.create_connection((host, port), timeout=0.1)
            probe.close()
            return t
        except OSError:
            time.sleep(0.05)
    raise RuntimeError(f"Server on {host}:{port} did not start in time")


def _connect_client(host: str, port: int, nickname: str) -> socket.socket:
    """Connect a raw socket, complete the nickname handshake, and return it."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    sock.connect((host, port))

    # Expect NICK prompt
    prompt = sock.recv(1024).decode()
    assert "NICK" in prompt, f"Expected NICK prompt, got: {prompt!r}"
    sock.sendall(nickname.encode())

    # Expect welcome or error
    response = sock.recv(1024).decode()
    return sock, response


HOST = "127.0.0.1"


class TestChatroom(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.port = 19999   # use a high port to avoid conflicts
        _run_server(HOST, cls.port)

    def _client(self, nickname: str) -> tuple[socket.socket, str]:
        return _connect_client(HOST, self.port, nickname)

    # ── basic connectivity ────────────────────────────────────────────────────

    def test_welcome_message(self):
        sock, welcome = self._client("Alice")
        self.assertIn("Welcome", welcome)
        sock.close()

    def test_join_notification(self):
        """Second client should see a join notice when a third client connects."""
        s1, _ = self._client("Bob")
        s2, _ = self._client("Carol")
        try:
            # s1 should have received Carol's join notification
            s1.settimeout(3)
            data = s1.recv(1024).decode()
            self.assertIn("Carol", data)
        finally:
            s1.close()
            s2.close()

    # ── /list command ─────────────────────────────────────────────────────────

    def test_list_command(self):
        s, _ = self._client("Dave")
        s.sendall(b"/list")
        data = s.recv(1024).decode()
        self.assertIn("Dave", data)
        s.close()

    # ── /msg private messaging ────────────────────────────────────────────────

    def test_private_message(self):
        s1, _ = self._client("Eve")
        s2, _ = self._client("Frank")
        try:
            s1.sendall(b"/msg Frank Hello Frank!")
            s2.settimeout(3)
            data = s2.recv(1024).decode()
            self.assertIn("Hello Frank!", data)
            self.assertIn("Eve", data)
        finally:
            s1.close()
            s2.close()

    # ── duplicate nickname ────────────────────────────────────────────────────

    def test_duplicate_nickname_rejected(self):
        s1, _ = self._client("Grace")
        s2 = None
        try:
            s2, response = _connect_client(HOST, self.port, "Grace")
            self.assertIn("ERROR", response)
        finally:
            s1.close()
            if s2 is not None:
                s2.close()

    # ── broadcast ─────────────────────────────────────────────────────────────

    def test_broadcast(self):
        s1, _ = self._client("Heidi")
        s2, _ = self._client("Ivan")
        try:
            s1.sendall(b"Hello everyone!")
            s2.settimeout(3)
            data = s2.recv(1024).decode()
            self.assertIn("Hello everyone!", data)
        finally:
            s1.close()
            s2.close()

    # ── /quit ─────────────────────────────────────────────────────────────────

    def test_quit_removes_client(self):
        s1, _ = self._client("Judy")
        s2, _ = self._client("Karl")
        try:
            s1.sendall(b"/quit")
            time.sleep(0.5)
            # Karl should see the leave notification
            s2.settimeout(3)
            data = s2.recv(1024).decode()
            self.assertIn("Judy", data)
        finally:
            s1.close()
            s2.close()


if __name__ == "__main__":
    unittest.main()
