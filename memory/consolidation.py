"""记忆整合模块：定期将短期记忆总结压缩到长期记忆"""
import asyncio
from typing import Callable, Optional

from .base import Memory
from .short_term import ShortTermMemory
from .long_term import LongTermMemory
from .episodic import EpisodicMemory


class MemoryConsolidator:
    """
    记忆整合器：
    - 当短期记忆积累到一定量时，调用 LLM 总结
    - 将总结写入长期记忆
    """

    def __init__(self,
                 short_term: ShortTermMemory,
                 long_term: Optional[LongTermMemory] = None,
                 episodic: Optional[EpisodicMemory] = None,
                 trigger_count: int = 20,
                 summary_prompt: Optional[str] = None):
        self.short_term = short_term
        self.long_term = long_term
        self.episodic = episodic
        self.trigger_count = trigger_count
        self.summary_prompt = summary_prompt or (
            "请将以下对话历史提炼为 3-5 条关键事实和用户偏好，用简洁的中文列出：\n"
            "{conversation}"
        )
        self._counters: dict[str, int] = {}

    def should_consolidate(self, agent_id: str) -> bool:
        current = len(self.short_term._stores.get(agent_id, []))
        last_count = self._counters.get(agent_id, 0)
        return (current - last_count) >= self.trigger_count

    def consolidate_sync(self, agent_id: str, llm_call: Callable,
                         clear_after: bool = False) -> Optional[str]:
        """
        执行记忆整合（同步版本）

        Args:
            agent_id: Agent ID
            llm_call: LLM 调用函数，接收 prompt，返回响应字符串
            clear_after: 是否在整合后清空短期记忆
        """
        recent = self.short_term.get_recent(agent_id, limit=self.trigger_count)
        if not recent:
            return None

        conversation = "\n".join([
            f"[{m.metadata.get('role', 'unknown')}]: {m.content}"
            for m in recent
        ])

        prompt = self.summary_prompt.format(conversation=conversation)
        summary = llm_call(prompt)

        if self.long_term:
            memory = Memory(
                agent_id=agent_id,
                memory_type="consolidation",
                content=summary,
                importance=0.8,
                metadata={
                    "source": "consolidation",
                    "original_count": len(recent),
                }
            )
            self.long_term.add(memory)

        if self.episodic:
            self.episodic.log_interaction(
                agent_id, "system",
                "consolidation",
                f"记忆整合完成：将 {len(recent)} 条短期记忆压缩为 1 条长期记忆"
            )

        self._counters[agent_id] = len(
            self.short_term._stores.get(agent_id, [])
        )

        if clear_after:
            self.short_term.clear(agent_id)
            self._counters[agent_id] = 0

        return summary

    async def consolidate(self, agent_id: str, llm_call: Callable,
                          clear_after: bool = False) -> Optional[str]:
        """异步版本（如果 LLM 调用是异步的）"""
        recent = self.short_term.get_recent(agent_id, limit=self.trigger_count)
        if not recent:
            return None

        conversation = "\n".join([
            f"[{m.metadata.get('role', 'unknown')}]: {m.content}"
            for m in recent
        ])

        prompt = self.summary_prompt.format(conversation=conversation)

        # 检测 llm_call 是否为协程函数，分别处理
        if asyncio.iscoroutinefunction(llm_call):
            summary = await llm_call(prompt)
        else:
            summary = llm_call(prompt)

        if self.long_term:
            memory = Memory(
                agent_id=agent_id,
                memory_type="consolidation",
                content=summary,
                importance=0.8,
                metadata={
                    "source": "consolidation",
                    "original_count": len(recent),
                }
            )
            self.long_term.add(memory)

        if self.episodic:
            self.episodic.log_interaction(
                agent_id, "system",
                "consolidation",
                f"记忆整合完成：将 {len(recent)} 条短期记忆压缩为 1 条长期记忆"
            )

        self._counters[agent_id] = len(
            self.short_term._stores.get(agent_id, [])
        )

        if clear_after:
            self.short_term.clear(agent_id)
            self._counters[agent_id] = 0

        return summary
