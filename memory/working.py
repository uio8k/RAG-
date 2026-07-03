"""工作记忆模块：存储当前任务状态和中间结果"""
from typing import Any, Optional

from .base import BaseMemory, Memory


class WorkingMemory(BaseMemory):
    """
    工作记忆：
    - 键值对存储
    - 用于存放当前任务状态、中间计算结果
    - 内存存储，重启后丢失
    """

    def __init__(self):
        self._stores: dict[str, dict[str, Memory]] = {}

    def _get_store(self, agent_id: str) -> dict:
        if agent_id not in self._stores:
            self._stores[agent_id] = {}
        return self._stores[agent_id]

    def set(self, agent_id: str, key: str, value: Any) -> str:
        store = self._get_store(agent_id)
        memory = Memory(
            agent_id=agent_id,
            memory_type="working",
            content=str(value),
            metadata={"key": key, "raw_type": type(value).__name__}
        )
        store[key] = memory
        return memory.id

    def get_value(self, agent_id: str, key: str) -> Any:
        store = self._get_store(agent_id)
        memory = store.get(key)
        if memory:
            memory.access_count += 1
            raw_type = memory.metadata.get("raw_type", "str")
            if raw_type == "int":
                return int(memory.content)
            elif raw_type == "float":
                return float(memory.content)
            elif raw_type == "bool":
                return memory.content.lower() == "true"
            return memory.content
        return None

    def get_all(self, agent_id: str) -> dict[str, str]:
        store = self._get_store(agent_id)
        return {k: m.content for k, m in store.items()}

    def delete_key(self, agent_id: str, key: str) -> bool:
        store = self._get_store(agent_id)
        if key in store:
            del store[key]
            return True
        return False

    # ==================== 抽象方法实现 ====================

    def add(self, memory: Memory) -> str:
        key = memory.metadata.get("key", memory.id)
        self.set(memory.agent_id, key, memory.content)
        return memory.id

    def get(self, memory_id: str) -> Optional[Memory]:
        for store in self._stores.values():
            for m in store.values():
                if m.id == memory_id:
                    return m
        return None

    def update(self, memory_id: str, content: str, **kwargs) -> bool:
        for store in self._stores.values():
            for key, m in store.items():
                if m.id == memory_id:
                    m.content = content
                    return True
        return False

    def delete(self, memory_id: str) -> bool:
        for agent_id, store in self._stores.items():
            for key, m in list(store.items()):
                if m.id == memory_id:
                    del store[key]
                    return True
        return False

    def search(self, query: str, top_k: int = 5, **filters) -> list[Memory]:
        agent_id = filters.get("agent_id", "default")
        store = self._get_store(agent_id)
        results = [m for m in store.values() if query.lower() in m.content.lower()]
        return results[:top_k]

    def clear(self, agent_id: Optional[str] = None) -> int:
        if agent_id:
            count = len(self._stores.get(agent_id, {}))
            self._stores.pop(agent_id, None)
            return count
        total = sum(len(s) for s in self._stores.values())
        self._stores.clear()
        return total
