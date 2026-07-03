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
    # 本地模型路径（优先使用，ModelScope 下载后自动检测）
    local_model_path: str = ""

    def _find_local_model(self) -> str | None:
        """自动查找本地已下载的模型"""
        candidates = [
            self.local_model_path,
            os.environ.get("EMBEDDING_MODEL_PATH", ""),
            os.path.expanduser(
                "~/.cache/modelscope/sentence-transformers/all-MiniLM-L6-v2"
            ),
            os.path.expanduser(
                "~/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2"
            ),
        ]
        for p in candidates:
            if p and Path(p).is_dir():
                return p
        return None

    def get_embedding_model(self) -> str:
        """返回可用的嵌入模型路径或名称"""
        local = self._find_local_model()
        if local:
            print(f"--- [Config] 使用本地嵌入模型: {local} ---")
            return local
        print(f"--- [Config] 使用远程嵌入模型: {self.embedding_model} ---")
        return self.embedding_model

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
