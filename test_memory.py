"""快速测试记忆系统（无需启动 HTTP 服务）"""
from memory.manager import MemoryManager


def test_memory_hub():
    """端到端测试"""
    print("=" * 50)
    print("Agent Memory Hub 测试")
    print("=" * 50)

    # 初始化
    manager = MemoryManager()
    agent_id = "test_user_001"
    session_id = "session_001"

    # 1. 记住对话
    print("\n[1] 写入记忆...")
    conversations = [
        ("user", "你好，我叫小明，我是一名 Python 开发者"),
        ("assistant", "你好小明！很高兴认识你。有什么我可以帮助你的吗？"),
        ("user", "我喜欢用 FastAPI 构建 Web API"),
        ("assistant", "FastAPI 是个很棒的选择！它性能高，文档完善。"),
        ("user", "我最近在学习机器学习，对 NLP 特别感兴趣"),
        ("assistant", "NLP 是非常有前景的领域！你是想从哪个方向入门？"),
        ("user", "我想用 ChromaDB 做向量存储，做 RAG 应用"),
        ("assistant", "ChromaDB 非常适合 RAG 场景，轻量且易用。"),
    ]

    for role, content in conversations:
        mid = manager.remember(agent_id, session_id, role, content)
        print(f"  ✓ [{role}]: {content[:40]}... -> {mid[:8]}")

    # 2. 检索记忆
    print("\n[2] 检索相关记忆...")
    queries = ["Python 开发", "FastAPI", "机器学习和 NLP", "ChromaDB RAG"]
    for q in queries:
        results = manager.recall(agent_id, q, top_k=3)
        print(f"\n  查询: '{q}'")
        for r in results:
            sim = r.metadata.get("_similarity", "N/A")
            print(f"    [{r.memory_type}] {r.content[:60]}... (相似度: {sim})")

    # 3. 获取 LLM 上下文
    print("\n[3] LLM 上下文...")
    context = manager.get_llm_context(agent_id, query="FastAPI RAG")
    print(f"  上下文长度: {len(context)} 字符")
    print(f"  前 200 字符: {context[:200]}...")

    # 4. 工作记忆
    print("\n[4] 工作记忆...")
    manager.set_working(agent_id, "current_task", "构建 RAG 系统")
    manager.set_working(agent_id, "progress", "60%")
    task = manager.get_working(agent_id, "current_task")
    progress = manager.get_working(agent_id, "progress")
    print(f"  当前任务: {task}")
    print(f"  进度: {progress}")

    # 5. 统计
    print("\n[5] 记忆统计...")
    stats = manager.stats(agent_id)
    for k, v in stats.items():
        print(f"  {k}: {v}")

    # 6. 遗忘
    print("\n[6] 测试遗忘...")
    count = manager.forget(agent_id)
    print(f"  已清除 {count} 条记忆")
    stats_after = manager.stats(agent_id)
    for k, v in stats_after.items():
        print(f"  {k}: {v}")

    print("\n" + "=" * 50)
    print("测试完成！")
    print("=" * 50)


if __name__ == "__main__":
    test_memory_hub()
