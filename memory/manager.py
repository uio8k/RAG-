"""统一记忆管理器：对外提供一站式记忆服务"""
from typing import Any, Callable, Optional

from .base import Memory
from .short_term import ShortTermMemory
from .long_term import LongTermMemory
from .working import WorkingMemory
from .episodic import EpisodicMemory
from .consolidation import MemoryConsolidator


class MemoryManager:
    """
    统一记忆管理器

    使用示例：
        manager = MemoryManager(
            short_term=ShortTermMemory(max_messages=50),
            long_term=LongTermMemory(chroma_path="./data/chroma"),
            working=WorkingMemory(),
            episodic=EpisodicMemory(base_path="./data/episodic"),
        )

        # 记住一条对话
        manager.remember("user_123", "session_1", "user", "我喜欢 Python")

        # 检索相关记忆
        memories = manager.recall("user_123", "Python 编程")

        # 获取对话上下文（给 LLM）
        context = manager.get_llm_context("user_123")
    """

    def __init__(self,
                 short_term: Optional[ShortTermMemory] = None,
                 long_term: Optional[LongTermMemory] = None,
                 working: Optional[WorkingMemory] = None,
                 episodic: Optional[EpisodicMemory] = None):

        self.short_term = short_term or ShortTermMemory()
        self.long_term = long_term or LongTermMemory()
        self.working = working or WorkingMemory()
        self.episodic = episodic or EpisodicMemory()

        self.consolidator = MemoryConsolidator(
            short_term=self.short_term,
            long_term=self.long_term,
            episodic=self.episodic,
        )

    # ==================== 便捷 API ====================

    def remember(self, agent_id: str, session_id: str,
                 role: str, content: str,
                 memory_type: str = "conversation",
                 importance: float = 0.5) -> str:
        """记住一条信息（同时写入短期 + 长期 + 情景记忆）"""
        memory = Memory(
            agent_id=agent_id,
            session_id=session_id,
            memory_type=memory_type,
            content=content,
            importance=importance,
            metadata={"role": role, "session_id": session_id}
        )

        self.short_term.add(memory)
        memory_id = self.long_term.add(memory)
        self.episodic.add(memory)
        return memory_id

    def recall(self, agent_id: str, query: str,
               top_k: int = 5,
               include_short_term: bool = True,
               include_long_term: bool = True) -> list[Memory]:
        """检索记忆（混合检索）"""
        results = []

        if include_long_term:
            long_results = self.long_term.search(
                query, top_k=top_k, agent_id=agent_id
            )
            results.extend(long_results)

        if include_short_term:
            short_results = self.short_term.search(
                query, top_k=top_k, agent_id=agent_id
            )
            existing_ids = {m.id for m in results}
            for m in short_results:
                if m.id not in existing_ids:
                    results.append(m)

        results.sort(
            key=lambda m: (
                m.metadata.get("_similarity", 0) * 0.7 +
                m.importance * 0.3
            ),
            reverse=True
        )
        return results[:top_k]

    def recall_facts(self, agent_id: str, limit: int = 20) -> list[Memory]:
        """获取已存储的事实/偏好"""
        return self.long_term.get_by_agent(agent_id, limit=limit)

    def get_llm_context(self, agent_id: str,
                        query: Optional[str] = None,
                        short_term_limit: int = 20,
                        long_term_top_k: int = 3) -> str:
        """获取 LLM 可用的上下文字符串"""
        parts = []

        short_context = self.short_term.get_context_for_llm(
            agent_id, limit=short_term_limit
        )
        if short_context:
            parts.append(f"## 对话历史\n{short_context}")

        if query:
            long_memories = self.long_term.search(
                query, top_k=long_term_top_k, agent_id=agent_id
            )
            if long_memories:
                facts = "\n".join([f"- {m.content}" for m in long_memories])
                parts.append(f"## 相关长期记忆\n{facts}")

        working = self.working.get_all(agent_id)
        if working:
            items = "\n".join([f"- {k}: {v}" for k, v in working.items()])
            parts.append(f"## 当前任务状态\n{items}")

        return "\n\n".join(parts)

    def forget(self, agent_id: str, memory_id: Optional[str] = None) -> int:
        """遗忘"""
        if memory_id:
            self.short_term.delete(memory_id)
            self.long_term.delete(memory_id)
            return 1
        else:
            count = 0
            count += self.short_term.clear(agent_id)
            count += self.long_term.forget_by_agent(agent_id)
            count += self.working.clear(agent_id)
            return count

    def set_working(self, agent_id: str, key: str, value: Any) -> str:
        """设置工作记忆"""
        return self.working.set(agent_id, key, value)

    def get_working(self, agent_id: str, key: str) -> Optional[str]:
        """获取工作记忆"""
        return self.working.get_value(agent_id, key)

    def consolidate(self, agent_id: str, llm_call: Callable,
                    clear_after: bool = False) -> Optional[str]:
        """手动触发记忆整合"""
        return self.consolidator.consolidate_sync(
            agent_id, llm_call, clear_after
        )

    # ==================== 统计 ====================

    def stats(self, agent_id: Optional[str] = None) -> dict:
        return {
            "short_term_count": (
                len(self.short_term._stores.get(agent_id, []))
                if agent_id else sum(
                    len(dq) for dq in self.short_term._stores.values()
                )
            ),
            "long_term_count": self.long_term.count(agent_id),
            "working_count": (
                len(self.working._stores.get(agent_id, {}))
                if agent_id else sum(
                    len(s) for s in self.working._stores.values()
                )
            ),
        }
