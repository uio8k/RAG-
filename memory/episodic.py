"""情景记忆模块：按时间线记录 Agent 完整交互日志"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .base import BaseMemory, Memory


class EpisodicMemory(BaseMemory):
    """
    情景记忆：
    - 按 Agent + 日期分文件存储
    - JSONL 格式，每行一条记录
    - 支持按时间范围检索
    """

    def __init__(self, base_path: str = "./data/episodic"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, agent_id: str, date: Optional[str] = None) -> Path:
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        agent_dir = self.base_path / agent_id
        agent_dir.mkdir(parents=True, exist_ok=True)
        return agent_dir / f"{date}.jsonl"

    # ==================== 写入 ====================

    def add(self, memory: Memory) -> str:
        file_path = self._get_file_path(memory.agent_id)
        record = {
            "id": memory.id,
            "agent_id": memory.agent_id,
            "session_id": memory.session_id,
            "memory_type": memory.memory_type,
            "content": memory.content,
            "metadata": memory.metadata,
            "importance": memory.importance,
            "created_at": memory.created_at.isoformat()
                if isinstance(memory.created_at, datetime)
                else memory.created_at,
        }
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return memory.id

    def log_interaction(self, agent_id: str, session_id: str,
                        role: str, content: str):
        self.add(Memory(
            agent_id=agent_id,
            session_id=session_id,
            memory_type=f"interaction_{role}",
            content=content,
            metadata={"role": role}
        ))

    # ==================== 读取 ====================

    def get(self, memory_id: str) -> Optional[Memory]:
        for i in range(7):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            for agent_dir in self.base_path.iterdir():
                if agent_dir.is_dir():
                    file_path = agent_dir / f"{date}.jsonl"
                    if file_path.exists():
                        with open(file_path, "r", encoding="utf-8") as f:
                            for line in f:
                                record = json.loads(line)
                                if record["id"] == memory_id:
                                    return self._dict_to_memory(record)
        return None

    def get_by_time_range(self, agent_id: str,
                          start: datetime,
                          end: Optional[datetime] = None,
                          limit: int = 100) -> list[Memory]:
        if end is None:
            end = datetime.now()

        memories = []
        current = start
        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            file_path = self._get_file_path(agent_id, date_str)
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        record = json.loads(line)
                        ts = datetime.fromisoformat(record["created_at"])
                        if start <= ts <= end:
                            memories.append(self._dict_to_memory(record))
                            if len(memories) >= limit:
                                break
            current += timedelta(days=1)
            if len(memories) >= limit:
                break

        return sorted(memories, key=lambda m: m.created_at, reverse=True)

    # ==================== 搜索 ====================

    def search(self, query: str, top_k: int = 5, **filters) -> list[Memory]:
        agent_id = filters.get("agent_id", "default")
        results = []
        for i in range(7):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            file_path = self._get_file_path(agent_id, date)
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        record = json.loads(line)
                        if query.lower() in record["content"].lower():
                            results.append(self._dict_to_memory(record))
                            if len(results) >= top_k:
                                break
            if len(results) >= top_k:
                break
        return results

    # ==================== 更新 / 删除 ====================

    def update(self, memory_id: str, content: str, **kwargs) -> bool:
        return False  # 情景记忆只追加不修改

    def delete(self, memory_id: str) -> bool:
        return False  # 情景记忆作为审计日志不允许删除

    def clear(self, agent_id: Optional[str] = None) -> int:
        import shutil
        if agent_id:
            agent_dir = self.base_path / agent_id
            if agent_dir.exists():
                count = sum(
                    1 for _ in agent_dir.rglob("*.jsonl")
                    for _ in open(_, "r", encoding="utf-8")
                )
                shutil.rmtree(agent_dir)
                return count
            return 0
        count = 0
        for agent_dir in self.base_path.iterdir():
            if agent_dir.is_dir():
                count += sum(
                    1 for _ in agent_dir.rglob("*.jsonl")
                    for _ in open(_, "r", encoding="utf-8")
                )
        shutil.rmtree(self.base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        return count

    # ==================== 工具方法 ====================

    def _dict_to_memory(self, record: dict) -> Memory:
        return Memory(
            id=record["id"],
            agent_id=record["agent_id"],
            session_id=record.get("session_id", "default"),
            memory_type=record.get("memory_type", "general"),
            content=record["content"],
            metadata=record.get("metadata", {}),
            importance=record.get("importance", 0.5),
            created_at=datetime.fromisoformat(record["created_at"])
                if isinstance(record["created_at"], str)
                else record["created_at"],
        )
