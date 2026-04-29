# Distributed Chatroom

Big-work project for the Distributed Systems course.

A multi-client command-line chatroom built with Python's standard library
(`socket` + `threading`). No third-party packages are required.

---

## Architecture

```
┌────────────┐        TCP        ┌──────────────────────┐
│  client.py │ ◄────────────── ► │     server.py        │
│  (thread)  │                   │  one thread/client   │
└────────────┘                   └──────────────────────┘
                                           │
                                  broadcast to all other
                                  connected clients
```

* The **server** listens on a configurable host/port and spawns one daemon
  thread per connected client.
* The **client** runs two threads: the main thread reads user input and sends
  it to the server; a background thread receives and prints incoming messages.

---

## Quick Start

**Terminal 1 — start the server**

```bash
python server.py
# or specify host/port:
python server.py --host 0.0.0.0 --port 9999
```

**Terminal 2 (and 3, 4 …) — connect clients**

```bash
python client.py
# or specify server address:
python client.py --host 127.0.0.1 --port 9999
```

You will be prompted to choose a nickname. After that, just type and press
Enter to broadcast a message.

---

## Commands

| Command | Description |
|---|---|
| `/list` | Show all currently online users |
| `/msg <nickname> <text>` | Send a private message to `<nickname>` |
| `/quit` | Disconnect from the server |

---

## Running the Tests

```bash
python test_chatroom.py -v
```

The test suite starts an in-process server on port 19999 and exercises:
nickname handshake, broadcast, join/leave notifications, `/list`, `/msg`,
duplicate-nickname rejection, and `/quit`.

---

## Requirements

* Python 3.10 or later (uses `match`-free code; compatible with 3.10+)
* No external dependencies

