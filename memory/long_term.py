"""长期记忆模块：基于 ChromaDB 向量存储的持久化记忆"""
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

import chromadb
from sentence_transformers import SentenceTransformer

from .base import BaseMemory, Memory


class LongTermMemory(BaseMemory):
    """
    长期记忆：
    - ChromaDB 存储向量（语义检索）
    - SQLite 存储完整元数据（结构化查询）
    - 支持 TTL 过期和重要性评分
    """

    def __init__(self, chroma_path: str = "./data/chroma",
                 sqlite_path: str = "./data/memory.db",
                 embedding_model: str = "all-MiniLM-L6-v2"):
        self.chroma_client = chromadb.PersistentClient(path=chroma_path)
        self.collection = self.chroma_client.get_or_create_collection(
            name="long_term_memory",
            metadata={"hnsw:space": "cosine"}
        )
        self.embedder = SentenceTransformer(embedding_model)
        self.sqlite_path = sqlite_path
        self._init_sqlite()

    def _init_sqlite(self):
        conn = sqlite3.connect(self.sqlite_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                session_id TEXT DEFAULT 'default',
                memory_type TEXT DEFAULT 'general',
                content TEXT NOT NULL,
                metadata_json TEXT DEFAULT '{}',
                importance REAL DEFAULT 0.5,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                access_count INTEGER DEFAULT 0,
                ttl INTEGER
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_id ON memories(agent_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_type ON memories(memory_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON memories(created_at)")
        conn.commit()
        conn.close()

    # ==================== 写入 ====================

    def add(self, memory: Memory) -> str:
        if not memory.id:
            from uuid import uuid4
            memory.id = uuid4().hex

        now = datetime.now().isoformat()
        if not memory.created_at:
            memory.created_at = datetime.now()
        memory.updated_at = datetime.now()

        # 写入 ChromaDB
        embedding = self.embedder.encode(memory.content).tolist()
        self.collection.add(
            ids=[memory.id],
            embeddings=[embedding],
            documents=[memory.content],
            metadatas=[{
                "agent_id": memory.agent_id,
                "session_id": memory.session_id,
                "memory_type": memory.memory_type,
                "importance": memory.importance,
                "created_at": memory.created_at.isoformat(),
            }]
        )

        # 写入 SQLite
        conn = sqlite3.connect(self.sqlite_path)
        conn.execute("""
            INSERT OR REPLACE INTO memories
            (id, agent_id, session_id, memory_type, content, metadata_json,
             importance, created_at, updated_at, access_count, ttl)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            memory.id, memory.agent_id, memory.session_id,
            memory.memory_type, memory.content,
            json.dumps(memory.metadata, ensure_ascii=False),
            memory.importance,
            memory.created_at.isoformat(), now, 0, memory.ttl
        ))
        conn.commit()
        conn.close()
        return memory.id

    def batch_add(self, memories: list[Memory]) -> list[str]:
        return [self.add(m) for m in memories]

    # ==================== 读取 ====================

    def get(self, memory_id: str) -> Optional[Memory]:
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM memories WHERE id = ?", (memory_id,)
        ).fetchone()
        conn.close()

        if row is None:
            return None
        self._increment_access(memory_id)
        return self._row_to_memory(row)

    def get_by_agent(self, agent_id: str, limit: int = 50) -> list[Memory]:
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM memories WHERE agent_id = ? ORDER BY created_at DESC LIMIT ?",
            (agent_id, limit)
        ).fetchall()
        conn.close()
        return [self._row_to_memory(r) for r in rows]

    # ==================== 检索（核心） ====================

    def search(self, query: str, top_k: int = 5, **filters) -> list[Memory]:
        agent_id = filters.get("agent_id")
        memory_type = filters.get("memory_type")
        min_importance = filters.get("min_importance", 0.0)

        where = {}
        if agent_id:
            where["agent_id"] = agent_id
        if memory_type:
            where["memory_type"] = memory_type

        embedding = self.embedder.encode(query).tolist()
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where=where if where else None,
            include=["documents", "metadatas", "distances"]
        )

        memories = []
        if results["ids"] and results["ids"][0]:
            for i, mem_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i] if results["distances"] else 1.0
                similarity = 1 - distance

                full_memory = self.get(mem_id)
                if full_memory:
                    full_memory.metadata["_similarity"] = round(similarity, 4)
                    if full_memory.importance >= min_importance:
                        memories.append(full_memory)

        return memories

    def search_keyword(self, keyword: str, agent_id: Optional[str] = None,
                       limit: int = 10) -> list[Memory]:
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        if agent_id:
            rows = conn.execute(
                "SELECT * FROM memories WHERE agent_id = ? AND content LIKE ? "
                "ORDER BY created_at DESC LIMIT ?",
                (agent_id, f"%{keyword}%", limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM memories WHERE content LIKE ? "
                "ORDER BY created_at DESC LIMIT ?",
                (f"%{keyword}%", limit)
            ).fetchall()
        conn.close()
        return [self._row_to_memory(r) for r in rows]

    # ==================== 更新 / 删除 ====================

    def update(self, memory_id: str, content: str, **kwargs) -> bool:
        existing = self.get(memory_id)
        if not existing:
            return False

        existing.content = content
        existing.updated_at = datetime.now()
        for key, val in kwargs.items():
            if hasattr(existing, key):
                setattr(existing, key, val)

        self.add(existing)
        return True

    def delete(self, memory_id: str) -> bool:
        try:
            self.collection.delete(ids=[memory_id])
        except Exception:
            pass
        conn = sqlite3.connect(self.sqlite_path)
        conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        conn.commit()
        conn.close()
        return True

    def forget_by_agent(self, agent_id: str) -> int:
        memories = self.get_by_agent(agent_id, limit=10000)
        ids = [m.id for m in memories]
        if ids:
            try:
                self.collection.delete(ids=ids)
            except Exception:
                pass

        conn = sqlite3.connect(self.sqlite_path)
        cursor = conn.execute("DELETE FROM memories WHERE agent_id = ?", (agent_id,))
        count = cursor.rowcount
        conn.commit()
        conn.close()
        return count

    def clear(self, agent_id: Optional[str] = None) -> int:
        if agent_id:
            return self.forget_by_agent(agent_id)
        conn = sqlite3.connect(self.sqlite_path)
        cursor = conn.execute("SELECT COUNT(*) FROM memories")
        count = cursor.fetchone()[0]
        conn.execute("DELETE FROM memories")
        conn.commit()
        conn.close()
        try:
            self.chroma_client.delete_collection("long_term_memory")
            self.collection = self.chroma_client.get_or_create_collection(
                name="long_term_memory",
                metadata={"hnsw:space": "cosine"}
            )
        except Exception:
            pass
        return count

    # ==================== 过期清理 ====================

    def expire_old(self, days: int = 30) -> int:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        conn = sqlite3.connect(self.sqlite_path)
        rows = conn.execute(
            "SELECT id FROM memories WHERE created_at < ?", (cutoff,)
        ).fetchall()
        ids = [r[0] for r in rows]
        conn.execute("DELETE FROM memories WHERE created_at < ?", (cutoff,))
        conn.commit()
        conn.close()
        if ids:
            try:
                self.collection.delete(ids=ids)
            except Exception:
                pass
        return len(ids)

    # ==================== 统计 ====================

    def count(self, agent_id: Optional[str] = None) -> int:
        conn = sqlite3.connect(self.sqlite_path)
        if agent_id:
            row = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE agent_id = ?", (agent_id,)
            ).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) FROM memories").fetchone()
        conn.close()
        return row[0] if row else 0

    # ==================== 工具方法 ====================

    def _row_to_memory(self, row) -> Memory:
        row_dict = dict(row)
        return Memory(
            id=row_dict["id"],
            agent_id=row_dict["agent_id"],
            session_id=row_dict.get("session_id", "default"),
            memory_type=row_dict.get("memory_type", "general"),
            content=row_dict["content"],
            metadata=json.loads(row_dict.get("metadata_json", "{}")),
            importance=row_dict.get("importance", 0.5),
            created_at=datetime.fromisoformat(row_dict["created_at"])
                if row_dict["created_at"] else datetime.now(),
            updated_at=datetime.fromisoformat(row_dict["updated_at"])
                if row_dict["updated_at"] else datetime.now(),
            access_count=row_dict.get("access_count", 0),
            ttl=row_dict.get("ttl"),
        )

    def _increment_access(self, memory_id: str):
        conn = sqlite3.connect(self.sqlite_path)
        conn.execute(
            "UPDATE memories SET access_count = access_count + 1 WHERE id = ?",
            (memory_id,)
        )
        conn.commit()
        conn.close()
