"""
Distributed Chatroom - Client
------------------------------
Interactive command-line chat client.

Usage:
    python client.py [--host HOST] [--port PORT]

Defaults: host=127.0.0.1, port=9999

Commands once connected:
    /list          — show all online users
    /msg <name> <text>  — send a private message
    /quit          — disconnect
"""

import socket
import threading
import argparse
import sys


# ── receive thread ────────────────────────────────────────────────────────────

_stop_event = threading.Event()


def receive_messages(sock: socket.socket) -> None:
    """Continuously read from *sock* and print messages to stdout."""
    while not _stop_event.is_set():
        try:
            data = sock.recv(4096)
        except OSError:
            break

        if not data:
            print("\n[Client] Connection closed by server.")
            _stop_event.set()
            break

        # Print on its own line without clobbering the input prompt
        sys.stdout.write("\r" + data.decode("utf-8", errors="replace"))
        sys.stdout.flush()

    _stop_event.set()


# ── client entry-point ────────────────────────────────────────────────────────

def start_client(host: str, port: int) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((host, port))
    except ConnectionRefusedError:
        print(f"[Client] Could not connect to {host}:{port}. Is the server running?")
        sys.exit(1)

    print(f"[Client] Connected to {host}:{port}")

    # ── nickname handshake ────────────────────────────────────────────────────
    try:
        prompt = sock.recv(1024).decode().strip()
    except OSError as exc:
        print(f"[Client] Handshake error: {exc}")
        sock.close()
        sys.exit(1)

    if prompt != "NICK":
        # Server sent an error instead of the nickname prompt
        print(f"[Client] Unexpected server response: {prompt}")
        sock.close()
        sys.exit(1)

    nickname = input("Choose a nickname: ").strip()
    if not nickname:
        print("[Client] Nickname cannot be empty.")
        sock.close()
        sys.exit(1)

    sock.sendall(nickname.encode())

    # Check if the server accepted the nickname
    try:
        response = sock.recv(1024).decode()
    except OSError as exc:
        print(f"[Client] Error receiving server response: {exc}")
        sock.close()
        sys.exit(1)

    if response.startswith("ERROR"):
        print(f"[Client] {response.strip()}")
        sock.close()
        sys.exit(1)

    # The welcome message from the server
    sys.stdout.write(response)
    sys.stdout.flush()

    # ── start background receive thread ───────────────────────────────────────
    recv_thread = threading.Thread(target=receive_messages, args=(sock,), daemon=True)
    recv_thread.start()

    # ── send loop (main thread) ───────────────────────────────────────────────
    print("[Client] Type a message and press Enter. Use /quit to exit.\n")
    try:
        while not _stop_event.is_set():
            try:
                text = input()
            except EOFError:
                break

            if not text.strip():
                continue

            try:
                sock.sendall(text.encode())
            except OSError:
                print("[Client] Lost connection to server.")
                break

            if text.strip() == "/quit":
                break

    except KeyboardInterrupt:
        pass
    finally:
        _stop_event.set()
        sock.close()
        print("\n[Client] Disconnected. Goodbye!")


def main() -> None:
    parser = argparse.ArgumentParser(description="Distributed Chatroom Client")
    parser.add_argument(
        "--host", default="127.0.0.1", help="Server address (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", type=int, default=9999, help="Server port (default: 9999)"
    )
    args = parser.parse_args()
    start_client(args.host, args.port)


if __name__ == "__main__":
    main()
