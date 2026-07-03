"""记忆模块抽象基类"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4


@dataclass
class Memory:
    """统一的记忆数据结构"""
    id: str = field(default_factory=lambda: uuid4().hex)
    agent_id: str = "default"
    session_id: str = "default"
    memory_type: str = "general"
    content: str = ""
    metadata: dict = field(default_factory=dict)
    importance: float = 0.5
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    ttl: Optional[int] = None


class BaseMemory(ABC):
    """所有记忆模块的抽象基类"""

    @abstractmethod
    def add(self, memory: Memory) -> str:
        """添加一条记忆，返回记忆 ID"""
        pass

    @abstractmethod
    def get(self, memory_id: str) -> Optional[Memory]:
        """根据 ID 获取记忆"""
        pass

    @abstractmethod
    def update(self, memory_id: str, content: str, **kwargs) -> bool:
        """更新记忆内容"""
        pass

    @abstractmethod
    def delete(self, memory_id: str) -> bool:
        """删除一条记忆"""
        pass

    @abstractmethod
    def search(self, query: str, top_k: int = 5, **filters) -> list[Memory]:
        """搜索记忆"""
        pass

    @abstractmethod
    def clear(self, agent_id: Optional[str] = None) -> int:
        """清除记忆，返回清除数量"""
        pass
