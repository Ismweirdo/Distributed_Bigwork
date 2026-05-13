"""
Chatroom 极限并发压测 v3
— 正确的 STOMP 协议握手
— 逐级提升找到最高并发
"""
import asyncio, json, uuid, time, argparse, sys, statistics
from dataclasses import dataclass, field

try:
    import aiohttp
except ImportError:
    print("pip install aiohttp"); sys.exit(1)
try:
    import websockets
except ImportError:
    print("pip install websockets"); sys.exit(1)

BASE = "http://localhost:8080/api"
WS   = "ws://localhost:8080/ws/chat"
PASS = "test123456"

# ===================== helpers =====================
def stomp_connect(token):
    return f"CONNECT\naccept-version:1.1,1.2\nhost:localhost\nlogin:{token}\n\n\0"

def stomp_sub(dest, sid="0"):
    return f"SUBSCRIBE\nid:{sid}\ndestination:{dest}\n\n\0"

def stomp_send(dest, body_dict):
    body = json.dumps(body_dict, ensure_ascii=False)
    return f"SEND\ndestination:{dest}\ncontent-type:application/json\ncontent-length:{len(body.encode())}\n\n{body}\0"

async def api(session, method, path, data=None, token=None, timeout=15):
    headers = {"Content-Type": "application/json"}
    if token: headers["Authorization"] = f"Bearer {token}"
    try:
        async with asyncio.timeout(timeout):
            if method == "POST":
                async with session.post(f"{BASE}{path}", json=data, headers=headers) as r:
                    return await r.json(), r.status
            else:
                async with session.get(f"{BASE}{path}", headers=headers) as r:
                    return await r.json(), r.status
    except Exception as e:
        return {"error": str(e)}, 0

# ==================== L1: REST API 登录压测 ====================
async def test_rest_qps(concurrency: int):
    """并发登录 + 查询用户信息"""
    print(f"\n{'='*60}")
    print(f"  L1: REST API 并发测试 (并发={concurrency})")
    print(f"{'='*60}")

    # 预注册用户
    users = []
    async with aiohttp.ClientSession() as s:
        for i in range(concurrency):
            d, c = await api(s, "POST", "/auth/register",
                {"username": f"qpstest_{uuid.uuid4().hex[:8]}", "password": PASS, "nickname": f"Q{i}"})
            if c == 200 and d.get("code") == 200:
                users.append(d["data"]["token"])
        print(f"  预注册: {len(users)}/{concurrency}")

    if len(users) < 5:
        print("  [FAIL] 用户不足")
        return

    # 并发登录
    conn = aiohttp.TCPConnector(limit=concurrency, force_close=True)
    t0 = time.time()
    lats = []
    ok = 0
    fail = 0

    async def login_one(token):
        t1 = time.time()
        d, c = await api(s, "GET", "/auth/me", token=token)
        lat = (time.time() - t1) * 1000
        return (c == 200 and d.get("code") == 200), lat

    # 分批发送避免本地连接耗尽
    batch = 20
    async with aiohttp.ClientSession(connector=conn) as s:
        for offset in range(0, len(users), batch):
            chunk = users[offset:offset+batch]
            results = await asyncio.gather(*[login_one(t) for t in chunk])
            for is_ok, lat in results:
                if is_ok: ok += 1
                else: fail += 1
                lats.append(lat)

    wall = time.time() - t0
    lats.sort()
    p50 = lats[len(lats)//2] if lats else 0
    p95 = lats[int(len(lats)*0.95)] if lats else 0
    p99 = lats[int(len(lats)*0.99)] if lats else 0
    qps = ok / max(wall, 0.001)
    err = fail / max(ok+fail, 1) * 100

    print(f"  OK={ok} FAIL={fail} ERR={err:.1f}% WALL={wall:.1f}s QPS={qps:.0f}")
    print(f"  Lat(ms): avg={statistics.mean(lats):.0f} p50={p50:.0f} p95={p95:.0f} p99={p99:.0f} max={max(lats):.0f}")
    return {"qps": qps, "p95": p95, "err": err, "ok": ok}

# ==================== L2: WebSocket 连接压测 ====================
async def test_ws_connections(max_concurrency: int, token: str):
    """逐级提升 WebSocket 并发连接数，找到断裂点"""
    print(f"\n{'='*60}")
    print(f"  L2: WebSocket 连接上限测试 (最大尝试={max_concurrency})")
    print(f"{'='*60}")

    if not token:
        print("  [SKIP] 需要 token")
        return

    async def ws_connect(idx, sem):
        async with sem:
            try:
                async with asyncio.timeout(8):
                    ws = await websockets.connect(
                        f"{WS}?token={token}",
                        ping_interval=None, close_timeout=2,
                    )
                    # Send STOMP CONNECT
                    await ws.send(stomp_connect(token))
                    raw = await asyncio.wait_for(ws.recv(), timeout=5)
                    if isinstance(raw, bytes): raw = raw.decode()
                    if "CONNECTED" in raw:
                        return ws
                    try: await ws.close()
                    except: pass
            except Exception:
                pass
        return None

    levels = [10, 20, 50, 100, 200, 500, 1000, 2000, 3000, 5000]
    peak = (0, 0)
    for level in levels:
        if level > max_concurrency: break
        print(f"  -> 尝试 {level} 并发连接...", end=" ", flush=True)
        sem = asyncio.Semaphore(level)
        tasks = [ws_connect(i, sem) for i in range(level)]
        sockets = await asyncio.gather(*tasks)
        count = sum(1 for s in sockets if s is not None)
        print(f"成功: {count}/{level}")
        peak = max(peak, (level, count), key=lambda x: x[1])

        # Close all
        for ws in sockets:
            if ws:
                try: await ws.close()
                except: pass

        if count < level * 0.85:
            print(f"  [!] 成功率 < 85%，停止")
            break
        await asyncio.sleep(1)

    print(f"\n  WS 峰值: {peak[1]} / {peak[0]}")
    return peak

# ==================== L3: 消息吞吐压测 ====================
async def test_msg_throughput(conn_count: int, msgs_per_conn: int, token: str):
    """N 条连接同时发送消息"""
    print(f"\n{'='*60}")
    print(f"  L3: 消息吞吐测试 (连接={conn_count}, 每连接={msgs_per_conn}条)")
    print(f"{'='*60}")

    if not token:
        print("  [SKIP] 需要 token")
        return

    # Get a bot to target (so bot replies don't slow things down)
    async with aiohttp.ClientSession() as s:
        d, _ = await api(s, "GET", "/auth/me", token=token)
        my_id = d.get("data", {}).get("id")

    async def sender(idx, sem):
        sent = 0
        lats = []
        ws = None
        async with sem:
            try:
                async with asyncio.timeout(20):
                    ws = await websockets.connect(
                        f"{WS}?token={token}",
                        ping_interval=None, close_timeout=2,
                    )
                    await ws.send(stomp_connect(token))
                    raw = await asyncio.wait_for(ws.recv(), timeout=5)
                    if b"CONNECTED" not in (raw if isinstance(raw, bytes) else raw.encode()):
                        return 0, []

                    # Subscribe to private messages
                    await ws.send(stomp_sub("/user/queue/private/chat", f"s{idx}"))
                    await asyncio.sleep(0.1)

                    for i in range(msgs_per_conn):
                        msg = {
                            "content": f"p_{idx}_{i}",
                            "messageType": 0, "targetId": my_id,
                            "contentType": 0,
                            "clientMessageId": f"t_{uuid.uuid4().hex[:12]}",
                        }
                        t1 = time.time()
                        await ws.send(stomp_send("/app/chat.send", msg))
                        lats.append((time.time() - t1) * 1000)
                        sent += 1
            except Exception:
                pass
            finally:
                if ws:
                    try: await ws.close()
                    except: pass
        return sent, lats

    t0 = time.time()
    sem = asyncio.Semaphore(conn_count)
    tasks = [sender(i, sem) for i in range(conn_count)]
    results = await asyncio.gather(*tasks)
    wall = time.time() - t0

    total = conn_count * msgs_per_conn
    ok = sum(r[0] for r in results)
    all_lats = []
    for r in results: all_lats.extend(r[1])
    all_lats.sort()

    err = (total - ok) / max(total, 1) * 100
    qps = ok / max(wall, 0.001)
    p50 = all_lats[len(all_lats)//2] if all_lats else 0
    p95 = all_lats[int(len(all_lats)*0.95)] if all_lats else 0

    print(f"  OK={ok}/{total} ERR={err:.1f}% WALL={wall:.1f}s MSG/s={qps:.0f}")
    print(f"  Lat(ms): avg={statistics.mean(all_lats):.0f}" if all_lats else "  No data",
          f"p50={p50:.0f} p95={p95:.0f} max={max(all_lats):.0f}" if all_lats else "")
    return {"qps": qps, "p95": p95, "err": err, "ok": ok}

# ==================== L4: 极限并发梯度 ====================
async def test_ramp(token: str, start=10, step=10, max_level=200):
    """逐级增加并发直到错误率超过阈值 (注册新用户 + 登录)"""
    print(f"\n{'='*60}")
    print(f"  L4: 极限并发梯度 (start={start} step={step} max={max_level})")
    print(f"{'='*60}")

    results = []
    for level in range(start, max_level + 1, step):
        t0 = time.time()
        ok = 0
        fail = 0
        lats = []

        async def register_and_login(idx):
            async with aiohttp.ClientSession() as s:
                t1 = time.time()
                d, c = await api(s, "POST", "/auth/register",
                    {"username": f"ramptest_{uuid.uuid4().hex[:8]}", "password": PASS, "nickname": f"R{idx}"})
                lat = (time.time() - t1) * 1000
                return (c == 200 and d.get("code") == 200), lat

        # 分批发送避免本地瓶颈
        batch = min(level, 50)
        for offset in range(0, level, batch):
            chunk_size = min(batch, level - offset)
            tasks = [register_and_login(offset + i) for i in range(chunk_size)]
            batch_results = await asyncio.gather(*tasks)
            for is_ok, lat in batch_results:
                if is_ok: ok += 1
                else: fail += 1
                lats.append(lat)

        wall = time.time() - t0
        err = fail / max(level, 1) * 100
        qps = ok / max(wall, 0.001)
        p95 = sorted(lats)[int(len(lats)*0.95)] if lats else 0

        bar = "█" * (ok // max(level//20, 1))
        print(f"  并发={level:4d} │{bar:<20s}│ QPS={qps:6.0f} ERR={err:5.1f}% p95={p95:5.0f}ms")

        results.append({"level": level, "qps": qps, "err": err, "p95": p95, "wall": wall})

        if err > 20:
            print(f"  [!] 错误率 {err:.1f}% > 20%，停止")
            break
        await asyncio.sleep(0.3)

    if results:
        best = max(results, key=lambda x: x["qps"])
        stable = [x for x in results if x["err"] < 5]
        max_stable = max(stable, key=lambda x: x["level"]) if stable else results[0]
        print(f"\n  ★ 最大 QPS: {best['qps']:.0f} (并发={best['level']})")
        print(f"  ★ 稳定最大并发: {max_stable['level']} (错误率={max_stable['err']:.1f}%)")
    return results

# ==================== main ====================
async def main():
    parser = argparse.ArgumentParser(description="Chatroom 极限并发压测 v3")
    parser.add_argument("--quick", action="store_true", help="快速模式")
    parser.add_argument("--full", action="store_true", help="全量模式")
    parser.add_argument("--ws-max", type=int, default=1000, help="WS 最大连接尝试")
    parser.add_argument("--ramp-max", type=int, default=300, help="极限梯度最大并发")
    args = parser.parse_args()

    print("=" * 60)
    print("  Chatroom 极限并发压测 v3")
    print(f"  API: {BASE}  |  WS: {WS}")
    print("=" * 60)

    total_t0 = time.time()

    # 1. 创建测试账号
    print("\n── 准备: 创建测试账号 ──")
    async with aiohttp.ClientSession() as s:
        uname = f"stresstest_{uuid.uuid4().hex[:6]}"
        d, _ = await api(s, "POST", "/auth/register",
            {"username": uname, "password": PASS, "nickname": "StressTester"})
        if d.get("code") != 200:
            print(f"  [FAIL] 注册失败: {d}")
            return
        token = d["data"]["token"]
        d2, _ = await api(s, "GET", "/auth/me", token=token)
        uid = d2.get("data", {}).get("id")
        print(f"  账号: {uname}  ID={uid}")

    # 2. L1: REST API 登录压测
    if args.quick:
        l1 = await test_rest_qps(20)
    else:
        l1 = await test_rest_qps(50)

    # 3. L2: WebSocket 连接上限
    if args.quick:
        l2 = await test_ws_connections(50, token)
    else:
        l2 = await test_ws_connections(args.ws_max, token)

    # 4. L3: 消息吞吐
    if args.quick:
        l3 = await test_msg_throughput(10, 10, token)
    else:
        l3 = await test_msg_throughput(30, 20, token)

    # 5. L4: 极限并发梯度
    if not args.quick:
        await test_ramp(token, start=10, step=20, max_level=args.ramp_max)

    # 总结
    elapsed = time.time() - total_t0
    print(f"\n{'='*60}")
    print(f"  压测总结 (总耗时 {elapsed:.0f}s)")
    print(f"{'='*60}")
    if l1:
        print(f"  REST QPS: {l1['qps']:.0f} | p95={l1['p95']:.0f}ms | 错误={l1['err']:.1f}%")
    if l2:
        print(f"  WS 最大并发: {l2[1]}/{l2[0]}")
    if l3:
        print(f"  消息吞吐: {l3['qps']:.0f} msg/s | p95={l3['p95']:.0f}ms | 错误={l3['err']:.1f}%")
    print()

if __name__ == "__main__":
    asyncio.run(main())
