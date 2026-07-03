"""全局配置管理"""
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class MemoryConfig:
    """记忆系统配置"""

    # --- 存储路径 ---
    chroma_path: str = "./data/chroma"           # 向量数据库路径
    sqlite_path: str = "./data/memory.db"        # SQLite 元数据路径
    episodic_path: str = "./data/episodic"       # 情景记忆日志路径

    # --- 短期记忆 ---
    short_term_max_messages: int = 50
    short_term_max_tokens: int = 4000

    # --- 长期记忆 ---
    long_term_top_k: int = 5
    long_term_similarity_threshold: float = 0.5

    # --- 嵌入模型 ---
    embedding_model: str = "all-MiniLM-L6-v2"

    # --- 记忆整合 ---
    consolidation_trigger_count: int = 20

    # --- 遗忘 ---
    memory_ttl_days: int = 30

    def __post_init__(self):
        Path(self.chroma_path).mkdir(parents=True, exist_ok=True)
        Path(self.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.episodic_path).mkdir(parents=True, exist_ok=True)


# 全局单例
memory_config = MemoryConfig()
