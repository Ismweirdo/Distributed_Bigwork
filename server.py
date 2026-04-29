"""
Distributed Chatroom - Server
------------------------------
Multi-client TCP chat server using Python's threading module.

Usage:
    python server.py [--host HOST] [--port PORT]

Defaults: host=0.0.0.0, port=9999
"""

import socket
import threading
import argparse
import sys
import time

# ── globals ──────────────────────────────────────────────────────────────────
clients: dict[socket.socket, str] = {}   # socket → nickname
clients_lock = threading.Lock()


# ── helpers ───────────────────────────────────────────────────────────────────

def broadcast(message: str, exclude: socket.socket | None = None) -> None:
    """Send *message* to every connected client except *exclude*."""
    encoded = message.encode()
    with clients_lock:
        dead = []
        for client_sock in clients:
            if client_sock is exclude:
                continue
            try:
                client_sock.sendall(encoded)
            except OSError:
                dead.append(client_sock)
        for sock in dead:
            _remove_client(sock)


def _remove_client(sock: socket.socket) -> None:
    """Remove *sock* from the clients dict (must hold clients_lock)."""
    clients.pop(sock, None)
    try:
        sock.close()
    except OSError:
        pass


def _send(sock: socket.socket, message: str) -> None:
    """Send *message* to a single socket.

    OSError is silently swallowed because the caller does not need to take
    any action when a single send fails (the client will be cleaned up the
    next time the receive loop notices the broken connection).
    """
    try:
        sock.sendall(message.encode())
    except OSError:
        pass


# ── per-client thread ─────────────────────────────────────────────────────────

def handle_client(conn: socket.socket, addr: tuple) -> None:
    """Negotiate a nickname then relay messages until the client disconnects."""
    print(f"[+] New connection from {addr}")

    # ── nickname handshake ────────────────────────────────────────────────────
    _send(conn, "NICK")
    try:
        nickname = conn.recv(1024).decode("utf-8", errors="replace").strip()
    except OSError:
        conn.close()
        return

    if not nickname or len(nickname) > 32:
        _send(conn, "ERROR Invalid nickname")
        conn.close()
        return

    with clients_lock:
        # Ensure nickname is unique
        taken = nickname in clients.values()
        if taken:
            _send(conn, f"ERROR Nickname '{nickname}' is already taken")
            conn.close()
            return
        clients[conn] = nickname

    print(f"[+] {nickname!r} joined from {addr}")
    broadcast(f"[Server] {nickname} has joined the chat!\n", exclude=conn)
    _send(conn, f"[Server] Welcome, {nickname}! Type /quit to leave.\n")

    # ── message relay loop ────────────────────────────────────────────────────
    try:
        while True:
            try:
                data = conn.recv(4096)
            except OSError:
                break

            if not data:
                break

            text = data.decode("utf-8", errors="replace").strip()

            if not text:
                continue

            # ── built-in commands ─────────────────────────────────────────────
            if text == "/quit":
                break

            if text == "/list":
                with clients_lock:
                    names = list(clients.values())
                _send(conn, "[Server] Online: " + ", ".join(names) + "\n")
                continue

            if text.startswith("/msg "):
                # Private message: /msg <target> <message>
                parts = text.split(" ", 2)
                if len(parts) < 3:
                    _send(conn, "[Server] Usage: /msg <nickname> <message>\n")
                    continue
                target_name = parts[1]
                pm_text = parts[2]
                with clients_lock:
                    target_sock = next(
                        (s for s, n in clients.items() if n == target_name), None
                    )
                    sender_name = clients.get(conn, "Unknown")
                if target_sock is None:
                    _send(conn, f"[Server] User '{target_name}' not found.\n")
                else:
                    _send(target_sock, f"[PM from {sender_name}] {pm_text}\n")
                    _send(conn, f"[PM to {target_name}] {pm_text}\n")
                continue

            # ── normal broadcast ──────────────────────────────────────────────
            with clients_lock:
                sender = clients.get(conn, "Unknown")
            timestamp = time.strftime("%H:%M:%S")
            broadcast(f"[{timestamp}] {sender}: {text}\n", exclude=conn)
            # Echo back so the sender sees the formatted message too
            _send(conn, f"[{timestamp}] {sender}: {text}\n")

    finally:
        with clients_lock:
            nickname = clients.get(conn, "Unknown")
            _remove_client(conn)
        print(f"[-] {nickname!r} disconnected")
        broadcast(f"[Server] {nickname} has left the chat.\n")


# ── server entry-point ────────────────────────────────────────────────────────

def start_server(host: str, port: int) -> None:
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((host, port))
    server_sock.listen(50)
    print(f"[Server] Listening on {host}:{port}  (Ctrl-C to stop)")

    try:
        while True:
            conn, addr = server_sock.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("\n[Server] Shutting down…")
    finally:
        broadcast("[Server] The server is shutting down. Goodbye!\n")
        server_sock.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Distributed Chatroom Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=9999, help="Port number (default: 9999)")
    args = parser.parse_args()
    start_server(args.host, args.port)


if __name__ == "__main__":
    main()
