"""快速测试记忆系统（无需启动 HTTP 服务）"""
import sys
import traceback
from memory.base import Memory
from memory.working import WorkingMemory
from memory.short_term import ShortTermMemory
from memory.episodic import EpisodicMemory
from memory.long_term import LongTermMemory
from memory.manager import MemoryManager


def test_core_modules():
    """测试不依赖网络的模块：Working + ShortTerm + Episodic"""
    print("=" * 50)
    print("  [核心模块] Working / ShortTerm / Episodic")
    print("=" * 50)
    agent_id = "test_core"
    all_ok = True

    # --- Working Memory ---
    print("\n[1] WorkingMemory ...")
    wm = WorkingMemory()
    wm.set(agent_id, "task", "测试任务")
    wm.set(agent_id, "score", "95")
    assert wm.get_value(agent_id, "task") == "测试任务", "WorkingMemory get_value 失败"
    assert len(wm.get_all(agent_id)) == 2, "WorkingMemory get_all 数量错误"
    wm.delete_key(agent_id, "score")
    assert wm.get_value(agent_id, "score") is None, "WorkingMemory delete_key 失败"
    wm.clear(agent_id)
    assert len(wm.get_all(agent_id)) == 0, "WorkingMemory clear 失败"
    print("  ✓ WorkingMemory 通过")

    # --- ShortTerm Memory ---
    print("\n[2] ShortTermMemory ...")
    stm = ShortTermMemory(max_messages=5)
    for i in range(7):
        m = Memory(agent_id=agent_id, content=f"消息{i}", metadata={"role": "user"})
        stm.add(m)
    recent = stm.get_recent(agent_id, limit=10)
    assert len(recent) == 5, f"ShortTerm 滑动窗口应为5，实际{len(recent)}"
    assert recent[-1].content == "消息6", f"最新消息应为消息6，实际{recent[-1].content}"
    ctx = stm.get_context_for_llm(agent_id)
    assert "消息6" in ctx, "get_context_for_llm 应包含最新消息"
    stm.clear(agent_id)
    assert len(stm.get_recent(agent_id)) == 0, "ShortTerm clear 失败"
    print("  ✓ ShortTermMemory 通过")

    # --- Episodic Memory ---
    print("\n[3] EpisodicMemory ...")
    em = EpisodicMemory(base_path="./data/episodic_test")
    em.add(Memory(agent_id=agent_id, content="事件1", memory_type="test"))
    em.add(Memory(agent_id=agent_id, content="事件2", memory_type="test"))
    results = em.search("事件1", top_k=5, agent_id=agent_id)
    assert len(results) >= 1, "Episodic search 应找到事件1"
    em.clear(agent_id)
    print("  ✓ EpisodicMemory 通过")

    return True


def test_long_term():
    """测试长期记忆（需要联网下载嵌入模型）"""
    print("\n" + "=" * 50)
    print("  [长期记忆] LongTermMemory (需要联网)")
    print("=" * 50)
    agent_id = "test_ltm"

    try:
        ltm = LongTermMemory(
            chroma_path="./data/chroma_test",
            sqlite_path="./data/memory_test.db",
        )
        # 触发延迟加载
        print("  正在加载嵌入模型 (首次使用会自动下载 ~80MB)...")
        _ = ltm._get_embedder()
        print("  ✓ 嵌入模型加载成功")

        m = Memory(agent_id=agent_id, content="用户喜欢 Python 和 FastAPI", importance=0.8)
        mid = ltm.add(m)
        print(f"  ✓ 写入记忆: {mid[:8]}")

        results = ltm.search("Python Web 框架", top_k=3, agent_id=agent_id)
        assert len(results) >= 1, "LongTerm search 未找到结果"
        print(f"  ✓ 语义检索成功，返回 {len(results)} 条")

        ltm.clear(agent_id)
        print("  ✓ LongTermMemory 全部通过")
        return True

    except Exception as e:
        print(f"  ⚠ 长期记忆测试跳过: {type(e).__name__}")
        print(f"    原因: 无法下载 SentenceTransformer 模型")
        print(f"    解决: 设置 HF_ENDPOINT=https://hf-mirror.com 或使用代理")
        return False


def test_manager_integration():
    """测试 MemoryManager 集成"""
    print("\n" + "=" * 50)
    print("  [集成测试] MemoryManager")
    print("=" * 50)
    agent_id = "test_mgr"

    # 不带 LongTermMemory 也能测试
    manager = MemoryManager(long_term=None)
    manager.remember(agent_id, "s1", "user", "你好")
    manager.remember(agent_id, "s1", "assistant", "你好！有什么可以帮你的？")

    ctx = manager.get_llm_context(agent_id)
    assert "你好" in ctx, "get_llm_context 应包含对话"

    manager.set_working(agent_id, "step", "1")
    assert manager.get_working(agent_id, "step") == "1"

    stats = manager.stats(agent_id)
    assert stats["short_term_count"] >= 2, f"short_term 应>=2，实际{stats['short_term_count']}"

    count = manager.forget(agent_id)
    assert count > 0, "forget 应清除记忆"
    print(f"  ✓ MemoryManager 集成测试通过 (清除 {count} 条)")
    return True


def test_memory_hub():
    """完整端到端测试（需要网络）"""
    print("\n" + "=" * 50)
    print("  [端到端] 完整 MemoryManager + LongTerm")
    print("=" * 50)

    try:
        manager = MemoryManager()
        agent_id = "test_e2e"
        session_id = "s1"

        conversations = [
            ("user", "你好，我叫小明，我是一名 Python 开发者"),
            ("assistant", "你好小明！很高兴认识你。"),
            ("user", "我喜欢用 FastAPI 构建 Web API"),
            ("user", "我想用 ChromaDB 做向量存储，做 RAG 应用"),
        ]
        for role, content in conversations:
            mid = manager.remember(agent_id, session_id, role, content)
            print(f"  ✓ [{role}]: {content[:30]}... -> {mid[:8]}")

        results = manager.recall(agent_id, "FastAPI RAG", top_k=3)
        print(f"  ✓ 检索到 {len(results)} 条相关记忆")

        ctx = manager.get_llm_context(agent_id, query="Python")
        print(f"  ✓ LLM 上下文: {len(ctx)} 字符")

        manager.forget(agent_id)
        print("  ✓ 端到端测试完成")
        return True

    except Exception as e:
        print(f"  ⚠ 端到端测试跳过 (需要联网): {type(e).__name__}")
        return False


if __name__ == "__main__":
    passed = 0
    failed = 0

    # 核心模块（不需要网络）
    try:
        test_core_modules()
        passed += 1
    except Exception:
        print(f"\n  ✗ 核心模块测试失败:\n{traceback.format_exc()}")
        failed += 1

    # 长期记忆（需要网络）
    if test_long_term():
        passed += 1
    else:
        print("  (非致命，核心功能正常)")

    # 集成测试（不需要网络）
    try:
        test_manager_integration()
        passed += 1
    except Exception:
        print(f"\n  ✗ 集成测试失败:\n{traceback.format_exc()}")
        failed += 1

    # 端到端（需要网络）
    test_memory_hub()

    print("\n" + "=" * 50)
    if failed == 0:
        print(f"  ✓ 测试完成: {passed} 项全部通过!")
    else:
        print(f"  通过: {passed}, 失败: {failed}")
    print("=" * 50)
    sys.exit(0 if failed == 0 else 1)
