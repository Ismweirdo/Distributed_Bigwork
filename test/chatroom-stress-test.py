"""
Chatroom 20-Bot Concurrent Chat Stress Test
============================================
Features:
- Register a test account
- Create 20 bots under that account
- Test all bots chatting simultaneously via STOMP WebSocket
- Active mode: bots initiate conversations independently
- Passive mode: user sends messages, bots reply via LLM

Usage:
  python chatroom-stress-test.py --mode passive
  python chatroom-stress-test.py --mode active --interval 10
  python chatroom-stress-test.py --mode both --bots 20 --rounds 3
"""

import asyncio
import json
import uuid
import time
import argparse
import sys
import os
import random
from dataclasses import dataclass, field
from typing import Optional, Callable

# ---------------------------------------------------------------------------
# dependencies check
# ---------------------------------------------------------------------------
try:
    import aiohttp
except ImportError:
    print("Install: pip install aiohttp")
    sys.exit(1)

try:
    import websockets
except ImportError:
    print("Install: pip install websockets")
    sys.exit(1)

# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------
BASE_API = "http://localhost:8080/api"
WS_URL = "ws://localhost:8080/ws/chat"

# DeepSeek config — set via env vars or use server defaults
DEEPSEEK_KEY = os.environ.get("BOT_API_KEY", "sk-6fe13faf47894dbdae05df6dd87f6cf4")
DEEPSEEK_ENDPOINT = os.environ.get("BOT_API_ENDPOINT", "https://api.deepseek.com/v1/chat/completions")
DEEPSEEK_MODEL = os.environ.get("BOT_API_MODEL", "deepseek-chat")

TEST_PASSWORD = "test123456"

# 20 diverse bot personalities
BOT_DEFS = [
    ("sunny_bot_01",    "阳光开朗派",   "你是bot01，阳光开朗。回复自然简短≤80字，喜欢用'哈哈'开头。不透露你是AI。"),
    ("gentle_bot_02",   "温柔知心派",   "你是bot02，温柔体贴。说话轻声细语，用'呢''呀'结尾。回复简短≤80字。"),
    ("humor_bot_03",    "冷幽默吐槽派", "你是bot03，冷幽默吐槽高手。说话简短犀利带黑色幽默。回复≤80字。"),
    ("sister_bot_04",   "热心大姐姐派", "你是bot04，热心大姐姐。关心鼓励对方语气温暖。回复简短≤80字。"),
    ("sharp_bot_05",    "毒舌怼人派",   "你是bot05，毒舌但善良的损友。说话直接不人身攻击。回复简短≤80字。"),
    ("literary_bot_06", "文艺小清新派", "你是bot06，文艺青年。说话带诗意偶尔引经据典。回复简短≤80字。"),
    ("foodie_bot_07",   "吃货聊天派",   "你是bot07，热爱美食的吃货。三句话不离吃的。回复简短≤80字。"),
    ("gamer_bot_08",    "游戏达人派",   "你是bot08，游戏资深玩家。用游戏术语聊天。回复简短≤80字。"),
    ("sporty_bot_09",   "运动健将派",   "你是bot09，运动健身达人。正能量满满。回复简短≤80字。"),
    ("philo_bot_10",    "深夜哲学派",   "你是bot10，深夜哲学家。喜欢思考人生不说教。回复简短≤80字。"),
    ("drama_bot_11",    "追剧狂魔派",   "你是bot11，追剧迷。喜欢安利好剧给大家。回复简短≤80字。"),
    ("pet_bot_12",      "萌宠爱好者派", "你是bot12，猫狗双全铲屎官。喜欢分享宠物趣事。回复简短≤80字。"),
    ("geek_bot_13",     "科技极客派",   "你是bot13，科技极客。聊新技术不用难懂术语。回复简短≤80字。"),
    ("zen_bot_14",      "佛系随缘派",   "你是bot14，佛系随缘。回答云淡风轻不争不抢。回复简短≤80字。"),
    ("flirt_bot_15",    "土味情话派",   "你是bot15，土味情话小能手。见缝插针撩人不油腻。回复简短≤80字。"),
    ("gossip_bot_16",   "八卦吃瓜派",   "你是bot16，吃瓜第一线。反应夸张有趣。回复简短≤80字。"),
    ("health_bot_17",   "养生老干部派", "你是bot17，养生老干部。劝人早睡多喝热水。回复简短≤80字。"),
    ("shy_bot_18",      "社恐碎碎念派", "你是bot18，社恐但真诚。说话有点结巴但很温暖。回复简短≤80字。"),
    ("nerd_bot_19",     "学霸讲题派",   "你是bot19，学霸型。用知识帮人不说教。回复简短≤80字。"),
    ("meme_bot_20",     "沙雕段子手派", "你是bot20，沙雕段子手。无时无刻不想逗对方笑。回复简短≤80字。"),
]

ACTIVE_OPENERS = [
    "嗨！今天天气真不错，你在干嘛呢？",
    "嘿，我刚刚看到一个超好笑的事情，想听吗？",
    "在吗？我突然想到一个问题想问你！",
    "我今天心情特别好，想找你聊聊天～",
    "你相信星座吗？我最近在研究这个，好有意思！",
    "我刚刚看完一部超好看的剧，强烈推荐给你！",
    "今天有什么新鲜事吗？跟我说说呗～",
    "嘿！好久没聊天了，最近过得怎么样？",
    "我今天学了一个新技能，好想分享给你！",
    "你在忙吗？不忙的话来聊五块钱的～",
]


# ---------------------------------------------------------------------------
# data classes
# ---------------------------------------------------------------------------
@dataclass
class Stats:
    sent: int = 0
    received: int = 0
    bot_replies: int = 0
    active_sent: int = 0
    errors: int = 0
    latencies: list = field(default_factory=list)
    connect_failures: int = 0


stats = Stats()
stats_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
async def api_post(session, path, data, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with session.post(f"{BASE_API}{path}", json=data, headers=headers) as resp:
        return await resp.json()


async def api_get(session, path, token=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with session.get(f"{BASE_API}{path}", headers=headers) as resp:
        return await resp.json()


async def api_delete(session, path, token=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with session.delete(f"{BASE_API}{path}", headers=headers) as resp:
        return await resp.json()


async def login(session, username, password):
    data = await api_post(session, "/auth/login", {
        "username": username, "password": password
    })
    if data.get("code") == 200:
        return data["data"]["token"]
    return None


async def register_user(session, username, password, nickname):
    data = await api_post(session, "/auth/register", {
        "username": username,
        "password": password,
        "nickname": nickname
    })
    if data.get("code") == 200:
        token = data["data"]["token"]
        actual_username = data["data"].get("user", {}).get("username", "unknown")
        return token, actual_username
    return None, None


# ---------------------------------------------------------------------------
# STOMP frame helpers
# ---------------------------------------------------------------------------
def stomp_connect_frame(token):
    """Build a STOMP CONNECT frame."""
    body = f"CONNECT\naccept-version:1.1,1.2\nhost:localhost\nlogin:{token}\n\n\0"
    return body


def stomp_subscribe_frame(destination, sub_id="sub-0"):
    return f"SUBSCRIBE\nid:{sub_id}\ndestination:{destination}\n\n\0"


def stomp_send_frame(destination, body_json):
    body_str = json.dumps(body_json, ensure_ascii=False)
    return f"SEND\ndestination:{destination}\ncontent-type:application/json\ncontent-length:{len(body_str.encode('utf-8'))}\n\n{body_str}\0"


def stomp_disconnect_frame():
    return "DISCONNECT\nreceipt:disconnect-1\n\n\0"


def parse_stomp_frame(raw):
    """Parse raw STOMP frame text into (command, headers_dict, body_str)."""
    if not raw or raw == "\n":
        return None
    parts = raw.split("\n\n", 1) if "\n\n" in raw else (raw.split("\n\0", 1) if "\n\0" in raw else (raw, ""))
    if len(parts) < 1:
        return None
    header_block = parts[0]
    body = parts[1] if len(parts) > 1 else ""
    body = body.rstrip("\0")
    lines = header_block.split("\n")
    command = lines[0].strip() if lines else ""
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip()] = v.strip()
    return command, headers, body


# ---------------------------------------------------------------------------
# WebSocket + STOMP client
# ---------------------------------------------------------------------------
class StompClient:
    """Minimal async STOMP-over-WebSocket client for Spring Boot."""

    def __init__(self, token, name="unknown"):
        self.token = token
        self.name = name
        self.ws = None
        self.connected = False
        self._recv_task = None
        self._handlers: dict[str, list[Callable]] = {}  # destination -> [callbacks]
        self._pending = {}  # sub_id -> destination

    async def connect(self, max_retries=3):
        url = f"{WS_URL}?token={self.token}"
        for attempt in range(max_retries):
            try:
                self.ws = await websockets.connect(
                    url,
                    additional_headers={"Origin": "http://localhost:3000"},
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5,
                )
                # Send STOMP CONNECT
                await self.ws.send(stomp_connect_frame(self.token))
                raw = await asyncio.wait_for(self.ws.recv(), timeout=10)
                cmd, headers, body = parse_stomp_frame(raw)
                if cmd == "CONNECTED":
                    self.connected = True
                    self._recv_task = asyncio.create_task(self._recv_loop())
                    return True
                else:
                    await self.ws.close()
            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(1 * (attempt + 1))
                else:
                    raise e
        return False

    async def _recv_loop(self):
        buf = ""
        try:
            while self.connected and self.ws:
                raw = await self.ws.recv()
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                buf += raw
                # STOMP frames end with \0 — some frames may be bundled
                while "\0" in buf:
                    idx = buf.index("\0")
                    frame_text = buf[:idx + 1]
                    buf = buf[idx + 1:]
                    parsed = parse_stomp_frame(frame_text)
                    if parsed:
                        cmd, headers, body = parsed
                        dest = headers.get("destination", "")
                        if dest in self._handlers:
                            for cb in self._handlers[dest]:
                                try:
                                    await cb(cmd, headers, body)
                                except Exception:
                                    pass
        except websockets.exceptions.ConnectionClosed:
            self.connected = False
        except Exception:
            self.connected = False

    async def subscribe(self, destination, callback):
        sub_id = f"sub-{uuid.uuid4().hex[:8]}"
        self._pending[sub_id] = destination
        if destination not in self._handlers:
            self._handlers[destination] = []
        self._handlers[destination].append(callback)
        await self.ws.send(stomp_subscribe_frame(destination, sub_id))
        return sub_id

    async def send(self, destination, body):
        frame = stomp_send_frame(destination, body)
        await self.ws.send(frame)

    async def disconnect(self):
        self.connected = False
        if self._recv_task:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass
        if self.ws:
            try:
                await self.ws.send(stomp_disconnect_frame())
            except Exception:
                pass
            await self.ws.close()


# ---------------------------------------------------------------------------
# Bot registration
# ---------------------------------------------------------------------------
async def cleanup_old_bots(session, token, bots_to_keep=()):
    """Delete bots from previous test runs. Uses user API to check usernames."""
    bots = await api_get(session, "/bots/", token)
    deleted = 0
    for b in bots.get("data", []):
        bot_user_id = b.get("botUserId")
        if not bot_user_id or bot_user_id in bots_to_keep:
            continue
        # Fetch user info to get the username
        user_data = await api_get(session, f"/users/{bot_user_id}", token)
        username = user_data.get("data", {}).get("username", "")
        test_prefixes = ("stress_", "sunny_", "gentle_", "humor_",
                "sister_", "sharp_", "literary_", "foodie_", "gamer_", "sporty_",
                "philo_", "drama_", "pet_", "geek_", "zen_", "flirt_", "gossip_",
                "health_", "shy_", "nerd_", "meme_", "demo_bot_", "deepseek_bot_",
                "load_bot_", "imp_")
        if username and any(username.startswith(p) for p in test_prefixes):
            await api_delete(session, f"/bots/{bot_user_id}", token)
            deleted += 1
    if deleted:
        print(f"  Cleaned {deleted} old test bots")


async def register_bots(session, token, count=20):
    """Register `count` bots and return list of {userId, username, password, nickname}."""
    bots = []
    for i in range(min(count, len(BOT_DEFS))):
        username, skill_name, system_prompt = BOT_DEFS[i]
        nickname = f"{skill_name[:4]}_{i+1:02d}"
        data = await api_post(session, "/bots/register", {
            "username": username,
            "nickname": nickname,
            "skillName": skill_name,
            "systemPrompt": system_prompt,
            "fewShotExamples": "[]",
            "emotionProfile": "{}",
            "languageStyle": "{}",
            "apiEndpoint": DEEPSEEK_ENDPOINT,
            "apiKey": DEEPSEEK_KEY,
            "model": DEEPSEEK_MODEL,
            "password": TEST_PASSWORD,
        }, token)
        if data.get("code") == 200:
            inner = data["data"]
            bot_info = {
                "userId": inner.get("botUserId") or inner.get("skill", {}).get("botUserId"),
                "username": username,
                "nickname": nickname,
                "password": inner.get("botPassword", TEST_PASSWORD),
            }
            bots.append(bot_info)
            print(f"  [{i+1:2d}/20] {nickname:20s}  userId={bot_info['userId']}")
        else:
            print(f"  [{i+1:2d}/20] FAILED: {data.get('message', data)}")
    print(f"  Registered: {len(bots)}/{count} bots")
    return bots


async def add_friends(session, token, bot_ids):
    """Add all bots as friends. Accept any pending reverse requests first."""
    added = 0
    for bid in bot_ids:
        # Add bot as friend
        data = await api_post(session, "/friends/add", {
            "friendId": bid, "message": "Hello bot!"
        }, token)
        if data.get("code") == 200:
            added += 1
        else:
            # Try accepting existing request
            await api_post(session, f"/friends/{bid}/accept", {}, token)
    print(f"  Friends added: {added}/{len(bot_ids)}")


# ---------------------------------------------------------------------------
# Passive mode — user sends, bots reply
# ---------------------------------------------------------------------------
PASSIVE_MESSAGES = [
    "你好呀！最近怎么样？",
    "今天天气真好，适合出去走走～",
    "你有什么兴趣爱好吗？",
    "给我讲个笑话吧！",
    "你喜欢吃什么美食？",
    "推荐一部好看的电影吧～",
    "你相信缘分吗？",
    "周末打算做什么？",
    "最近有看什么好书吗？",
    "你觉得AI会取代人类吗？",
    "说一句鼓励我的话吧！",
    "你最喜欢什么季节？",
    "晚上吃什么好呢？",
    "给我推荐一首歌吧～",
    "如果中彩票了你会干嘛？",
]


async def passive_chat_round(user_client: StompClient, bot_ids: list[int],
                             round_num: int, session: aiohttp.ClientSession):
    """One round: send 1 message to each bot, wait for reply."""
    reply_count = 0
    bot_reply_received = {}  # bot_id -> bool

    async def on_message(cmd, headers, body):
        nonlocal reply_count
        if cmd == "MESSAGE":
            try:
                data = json.loads(body)
                if data.get("type") == "CHAT":
                    sender_id = data.get("senderId")
                    if sender_id in bot_ids:
                        bot_reply_received[sender_id] = True
                    async with stats_lock:
                        stats.received += 1
                        stats.bot_replies += 1
                    reply_count += 1
            except json.JSONDecodeError:
                pass

    await user_client.subscribe("/user/queue/private/chat", on_message)

    # Mark round start time
    round_start = time.time()
    for bid in bot_ids:
        msg_text = random.choice(PASSIVE_MESSAGES)
        chat_msg = {
            "content": msg_text,
            "messageType": 0,
            "targetId": bid,
            "contentType": 0,
            "clientMessageId": f"passive_{uuid.uuid4().hex[:16]}",
        }
        start = time.time()
        await user_client.send("/app/chat.send", chat_msg)
        async with stats_lock:
            stats.sent += 1
        latency = (time.time() - start) * 1000
        async with stats_lock:
            stats.latencies.append(latency)

    # Wait for bot replies (give them time to call LLM)
    wait_time = min(15, len(bot_ids) * 2)
    await asyncio.sleep(wait_time)

    # Count how many responded
    responded = sum(1 for v in bot_reply_received.values() if v)
    print(f"  Round {round_num}: sent={len(bot_ids)}, replied={responded}/{len(bot_ids)} "
          f"({time.time() - round_start:.1f}s)")


# ---------------------------------------------------------------------------
# Active mode — bots initiate conversations
# ---------------------------------------------------------------------------
async def active_bot_loop(bot_info: dict, target_user_id: int, interval: float,
                          active_events: dict):
    """Connect as the bot, periodically send messages to the target user."""
    try:
        # Login as bot
        async with aiohttp.ClientSession() as session:
            token = await login(session, bot_info["username"], bot_info["password"])
            if not token:
                async with stats_lock:
                    stats.connect_failures += 1
                print(f"  [ACTIVE] {bot_info['nickname']}: login failed")
                return

        # Connect WebSocket
        client = StompClient(token, bot_info["nickname"])
        await client.connect()
        print(f"  [ACTIVE] {bot_info['nickname']} connected")

        # Subscribe to receive messages from user (for acknowledgment)
        msg_from_target = {}
        async def on_user_msg(cmd, headers, body):
            if cmd == "MESSAGE":
                try:
                    data = json.loads(body)
                    if data.get("type") == "CHAT" and data.get("senderId") == target_user_id:
                        msg_from_target["last"] = time.time()
                        async with stats_lock:
                            stats.received += 1
                except json.JSONDecodeError:
                    pass

        await client.subscribe("/user/queue/private/chat", on_user_msg)

        # Periodically send messages
        while client.connected:
            await asyncio.sleep(interval + random.uniform(-2, 2))

            if not client.connected:
                break

            opener = random.choice(ACTIVE_OPENERS)
            chat_msg = {
                "content": opener,
                "messageType": 0,
                "targetId": target_user_id,
                "contentType": 0,
                "clientMessageId": f"active_{uuid.uuid4().hex[:16]}",
            }
            try:
                start = time.time()
                await client.send("/app/chat.send", chat_msg)
                async with stats_lock:
                    stats.active_sent += 1
                    stats.sent += 1
                latency = (time.time() - start) * 1000
                async with stats_lock:
                    stats.latencies.append(latency)
                active_events[bot_info["nickname"]] = active_events.get(bot_info["nickname"], 0) + 1
            except Exception:
                async with stats_lock:
                    stats.errors += 1
                break

        await client.disconnect()
    except Exception as e:
        async with stats_lock:
            stats.errors += 1
            stats.connect_failures += 1
        print(f"  [ACTIVE] {bot_info['nickname']}: error - {e}")


async def run_active_mode(bots: list[dict], target_user_id: int, interval: float,
                          duration: float):
    """Run all bots in active mode: each bot connects and sends messages independently."""
    print(f"\n{'='*60}")
    print(f"  ACTIVE MODE: {len(bots)} bots initiating conversations")
    print(f"  Interval: {interval}s, Duration: {duration}s")
    print(f"{'='*60}")

    active_events = {}
    tasks = [asyncio.create_task(active_bot_loop(b, target_user_id, interval, active_events))
             for b in bots]

    # Wait for duration or until all tasks complete
    try:
        await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=duration)
    except asyncio.TimeoutError:
        pass

    # Cancel remaining tasks
    for t in tasks:
        if not t.done():
            t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

    active_total = sum(active_events.values())
    print(f"\n  Active messages sent: {active_total}")
    for name, count in sorted(active_events.items()):
        print(f"    {name}: {count} messages")


# ---------------------------------------------------------------------------
# Passive mode — user client sends messages to all bots in rounds
# ---------------------------------------------------------------------------
async def run_passive_mode(token: str, bots: list[dict], rounds: int):
    """Connect as the main user and send messages to each bot for N rounds."""
    print(f"\n{'='*60}")
    print(f"  PASSIVE MODE: user -> {len(bots)} bots x {rounds} rounds")
    print(f"{'='*60}")

    user_client = StompClient(token, "main_user")
    await user_client.connect()
    print("  Main user connected via WebSocket")

    bot_ids = [b["userId"] for b in bots]

    async with aiohttp.ClientSession() as session:
        for r in range(1, rounds + 1):
            await passive_chat_round(user_client, bot_ids, r, session)
            if r < rounds:
                await asyncio.sleep(2)

    await user_client.disconnect()


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------
def print_report(start_time: float):
    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"  STRESS TEST RESULTS")
    print(f"{'='*60}")
    print(f"  Duration:            {elapsed:.1f}s")
    print(f"  Messages sent:       {stats.sent}")
    print(f"  Active (bot→user):   {stats.active_sent}")
    print(f"  Messages received:   {stats.received}")
    print(f"  Bot replies:         {stats.bot_replies}")
    print(f"  Errors:              {stats.errors}")
    print(f"  Connect failures:    {stats.connect_failures}")

    if stats.latencies:
        lats = sorted(stats.latencies)
        print(f"  Latency P50:         {lats[len(lats)//2]:.1f}ms")
        print(f"  Latency P95:         {lats[int(len(lats)*0.95)]:.1f}ms")
        print(f"  Latency P99:         {lats[int(len(lats)*0.99)]:.1f}ms")
        print(f"  Latency Max:         {max(lats):.1f}ms")

    total = max(stats.sent, 1)
    error_rate = (stats.errors / total) * 100
    reply_rate = (stats.bot_replies / max(stats.sent - stats.active_sent, 1)) * 100
    print(f"  Error rate:          {error_rate:.2f}%")
    print(f"  Bot reply rate:      {reply_rate:.1f}%")
    print()

    if error_rate < 5.0 and stats.connect_failures == 0:
        print("  [PASS] All bots chatting stably!")
    elif error_rate < 20.0:
        print("  [WARN] Some errors but system is functional")
    else:
        print("  [FAIL] High error rate — check server and API keys")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
async def main():
    parser = argparse.ArgumentParser(description="Chatroom 20-Bot Concurrent Chat Stress Test")
    parser.add_argument("--mode", choices=["passive", "active", "both"],
                        default="both", help="Chat mode (default: both)")
    parser.add_argument("--bots", type=int, default=20,
                        help="Number of bots to test (default: 20)")
    parser.add_argument("--rounds", type=int, default=3,
                        help="Rounds of messages in passive mode (default: 3)")
    parser.add_argument("--interval", type=float, default=15,
                        help="Seconds between active bot messages (default: 15)")
    parser.add_argument("--duration", type=float, default=60,
                        help="Duration in seconds for active mode (default: 60)")
    parser.add_argument("--clean", action="store_true", default=True,
                        help="Clean up old test bots before starting")
    parser.add_argument("--no-clean", dest="clean", action="store_false",
                        help="Skip cleaning old test bots")
    parser.add_argument("--user", type=str, default=None,
                        help="Existing username (skip registration)")
    args = parser.parse_args()

    print("=" * 60)
    print("  Chatroom 20-Bot Concurrent Chat Stress Test")
    print("=" * 60)
    print(f"  Mode: {args.mode}, Bots: {args.bots}, Rounds: {args.rounds}")
    print(f"  Active interval: {args.interval}s, Duration: {args.duration}s")
    print()

    test_start = time.time()

    async with aiohttp.ClientSession() as session:
        # ---- Step 1: Account ----
        print("--- Step 1: Account ---")
        username = args.user or f"stress_test_{uuid.uuid4().hex[:6]}"
        token = await login(session, username, TEST_PASSWORD)
        actual_username = username
        if not token:
            print(f"  Registering new user: {username}")
            token, actual_username = await register_user(session, username, TEST_PASSWORD, f"StressTester_{username[:6]}")
            if not token:
                print("[FAIL] Cannot register or login. Is the server running?")
                return
        print(f"  Login account: {actual_username} / {TEST_PASSWORD}")
        print(f"  Token obtained: {token[:30]}...")

        # ---- Step 2: Clean old bots ----
        if args.clean:
            print("\n--- Step 2: Clean Old Bots ---")
            await cleanup_old_bots(session, token)

        # ---- Step 3: Register bots ----
        print(f"\n--- Step 3: Register {args.bots} Bots ---")
        bots = await register_bots(session, token, args.bots)
        if not bots:
            print("[FAIL] No bots registered. Check API key and server.")
            return

        # ---- Step 4: Add friends ----
        print(f"\n--- Step 4: Add Bots as Friends ---")
        bot_ids = [b["userId"] for b in bots]
        await add_friends(session, token, bot_ids)

        # Get main user's userId
        me_data = await api_get(session, "/auth/me", token)
        my_user_id = me_data.get("data", {}).get("id")

        if not my_user_id:
            # Parse from token or use login info
            my_user_id = None

        # ---- Step 5: Run Tests ----
        if args.mode in ("passive", "both"):
            await run_passive_mode(token, bots, args.rounds)

        if args.mode in ("active", "both"):
            if my_user_id:
                # Brief pause between modes
                if args.mode == "both":
                    await asyncio.sleep(3)
                await run_active_mode(bots, my_user_id, args.interval, args.duration)
            else:
                print("\n  [SKIP] Active mode requires user ID — check /auth/me endpoint")

    # ---- Report ----
    print_report(test_start)


if __name__ == "__main__":
    asyncio.run(main())
