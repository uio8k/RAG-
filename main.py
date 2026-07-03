"""Agent Memory Hub + RAG 主入口"""
from fastapi import FastAPI
from memory.manager import MemoryManager
from memory.short_term import ShortTermMemory
from memory.long_term import LongTermMemory
from memory.working import WorkingMemory
from memory.episodic import EpisodicMemory
from api.memory_routes import router as memory_router
from config import memory_config

# 初始化记忆管理器（全局单例，带自动降级）
try:
    memory_manager = MemoryManager(
        short_term=ShortTermMemory(
            max_messages=memory_config.short_term_max_messages,
            max_tokens=memory_config.short_term_max_tokens,
        ),
        long_term=LongTermMemory(
            chroma_path=memory_config.chroma_path,
            sqlite_path=memory_config.sqlite_path,
            embedding_model=memory_config.embedding_model,
        ),
        working=WorkingMemory(),
        episodic=EpisodicMemory(base_path=memory_config.episodic_path),
    )
    # 触发嵌入模型加载检测
    memory_manager.long_term._get_embedder()
    print("--- [MemoryHub] 完整模式 (短期 + 长期 + 工作 + 情景) ---")
except Exception as e:
    print(f"--- [MemoryHub] 长期记忆不可用 ({e})，降级为纯短期模式 ---")
    memory_manager = MemoryManager(
        short_term=ShortTermMemory(
            max_messages=memory_config.short_term_max_messages,
            max_tokens=memory_config.short_term_max_tokens,
        ),
        long_term=None,
        working=WorkingMemory(),
        episodic=EpisodicMemory(base_path=memory_config.episodic_path),
    )

app = FastAPI(title="RAG + Agent Memory Hub")

# 挂载记忆管理路由
app.include_router(memory_router)


@app.get("/")
async def root():
    return {"message": "RAG + Agent Memory Hub is running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
