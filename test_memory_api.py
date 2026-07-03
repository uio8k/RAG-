"""测试 Agent Memory Hub 的 FastAPI 路由（需要先启动 main.py）"""
import httpx
import asyncio

BASE_URL = "http://127.0.0.1:8000"


async def test_all():
    agent_id = "test_api_user"
    session_id = "test_session"

    async with httpx.AsyncClient(timeout=10) as client:
        # 0. 健康检查
        print("=" * 50)
        print("[0] 健康检查...")
        resp = await client.get(f"{BASE_URL}/")
        print(f"  状态: {resp.status_code}, 内容: {resp.json()}")

        # 1. 记住一些对话
        print("\n[1] POST /api/memory/remember")
        conversations = [
            ("user", "你好，我叫小红"),
            ("assistant", "你好小红！"),
            ("user", "我喜欢投资科技股"),
            ("assistant", "科技股确实是不错的选择"),
            ("user", "我持有 AAPL 和 MSFT"),
        ]
        for role, content in conversations:
            resp = await client.post(f"{BASE_URL}/api/memory/remember", json={
                "agent_id": agent_id,
                "session_id": session_id,
                "role": role,
                "content": content,
            })
            data = resp.json()
            print(f"  [{role}] '{content}' → ok={data.get('ok')}, id={data.get('memory_id', '')[:8]}")

        # 2. 检索
        print("\n[2] POST /api/memory/recall")
        queries = ["科技股", "AAPL", "投资"]
        for q in queries:
            resp = await client.post(f"{BASE_URL}/api/memory/recall", json={
                "agent_id": agent_id,
                "query": q,
                "top_k": 3,
            })
            data = resp.json()
            print(f"  查询 '{q}': 返回 {data.get('count', 0)} 条")
            for m in data.get("memories", []):
                print(f"    [{m.get('memory_type')}] {m.get('content', '')[:50]}...")

        # 3. LLM 上下文
        print("\n[3] GET /api/memory/context/{agent_id}")
        resp = await client.get(
            f"{BASE_URL}/api/memory/context/{agent_id}",
            params={"query": "科技股投资"}
        )
        data = resp.json()
        ctx = data.get("context", "")
        print(f"  上下文长度: {len(ctx)} 字符")
        print(f"  前 200 字符: {ctx[:200]}...")

        # 4. 工作记忆
        print("\n[4] POST /api/memory/working/set + GET /api/memory/working/{agent_id}/{key}")
        await client.post(f"{BASE_URL}/api/memory/working/set", json={
            "agent_id": agent_id,
            "key": "target_return",
            "value": "15%",
        })
        resp = await client.get(f"{BASE_URL}/api/memory/working/{agent_id}/target_return")
        data = resp.json()
        print(f"  target_return = {data.get('value')}")

        # 5. 统计
        print("\n[5] GET /api/memory/stats/{agent_id}")
        resp = await client.get(f"{BASE_URL}/api/memory/stats/{agent_id}")
        data = resp.json()
        print(f"  统计: {data.get('stats')}")

        # 6. 遗忘
        print("\n[6] POST /api/memory/forget")
        resp = await client.post(f"{BASE_URL}/api/memory/forget", json={
            "agent_id": agent_id,
        })
        data = resp.json()
        print(f"  已清除 {data.get('deleted_count', 0)} 条记忆")

        print("\n" + "=" * 50)
        print("API 测试完成！")
        print("=" * 50)


if __name__ == "__main__":
    asyncio.run(test_all())
