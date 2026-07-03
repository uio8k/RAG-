"""短期记忆模块：基于滑动窗口的对话上下文管理"""
from collections import deque
from datetime import datetime
from typing import Optional
from uuid import uuid4

from .base import BaseMemory, Memory


class ShortTermMemory(BaseMemory):
    """
    短期记忆：
    - 内存中的双端队列，重启后丢失
    - 按 agent_id 隔离
    - 滑动窗口，超出容量自动淘汰最旧的
    """

    def __init__(self, max_messages: int = 50, max_tokens: int = 4000):
        self.max_messages = max_messages
        self.max_tokens = max_tokens
        self._stores: dict[str, deque[Memory]] = {}

    def _get_or_create_deque(self, agent_id: str) -> deque:
        if agent_id not in self._stores:
            self._stores[agent_id] = deque(maxlen=self.max_messages)
        return self._stores[agent_id]

    def add(self, memory: Memory) -> str:
        if not memory.id:
            memory.id = uuid4().hex
        dq = self._get_or_create_deque(memory.agent_id)
        dq.append(memory)
        self._trim_by_tokens(memory.agent_id)
        return memory.id

    def get(self, memory_id: str) -> Optional[Memory]:
        for dq in self._stores.values():
            for m in dq:
                if m.id == memory_id:
                    m.access_count += 1
                    return m
        return None

    def get_recent(self, agent_id: str, limit: int = 20) -> list[Memory]:
        dq = self._get_or_create_deque(agent_id)
        return list(dq)[-limit:]

    def get_context_for_llm(self, agent_id: str, limit: int = 20) -> str:
        memories = self.get_recent(agent_id, limit)
        lines = []
        for m in memories:
            role = m.metadata.get("role", "unknown")
            lines.append(f"[{role}]: {m.content}")
        return "\n".join(lines)

    def update(self, memory_id: str, content: str, **kwargs) -> bool:
        for dq in self._stores.values():
            for i, m in enumerate(dq):
                if m.id == memory_id:
                    m.content = content
                    m.updated_at = datetime.now()
                    return True
        return False

    def delete(self, memory_id: str) -> bool:
        for dq in self._stores.values():
            for i, m in enumerate(dq):
                if m.id == memory_id:
                    del dq[i]
                    return True
        return False

    def search(self, query: str, top_k: int = 5, **filters) -> list[Memory]:
        agent_id = filters.get("agent_id", "default")
        results = []
        for m in self.get_recent(agent_id, limit=self.max_messages):
            if query.lower() in m.content.lower():
                results.append(m)
        return results[:top_k]

    def clear(self, agent_id: Optional[str] = None) -> int:
        if agent_id:
            count = len(self._stores.get(agent_id, deque()))
            self._stores.pop(agent_id, None)
            return count
        total = sum(len(dq) for dq in self._stores.values())
        self._stores.clear()
        return total

    def _trim_by_tokens(self, agent_id: str):
        dq = self._get_or_create_deque(agent_id)
        while True:
            total_chars = sum(len(m.content) for m in dq)
            estimated_tokens = total_chars // 2
            if estimated_tokens <= self.max_tokens or len(dq) <= 1:
                break
            dq.popleft()
