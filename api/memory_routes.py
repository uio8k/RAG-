"""记忆管理 API 路由（FastAPI）

使用方法：在 main.py 中导入
    from api.memory_routes import router as memory_router
    app.include_router(memory_router)
"""
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


router = APIRouter(prefix="/api/memory", tags=["Memory"])


# ==================== 请求/响应模型 ====================

class RememberRequest(BaseModel):
    agent_id: str = Field(..., description="Agent/用户 ID")
    session_id: str = Field(default="default", description="会话 ID")
    role: str = Field(default="user", description="角色: user/assistant/system")
    content: str = Field(..., description="记忆内容")
    memory_type: str = Field(default="conversation", description="记忆类型")
    importance: float = Field(default=0.5, ge=0.0, le=1.0, description="重要性评分")


class RecallRequest(BaseModel):
    agent_id: str = Field(..., description="Agent/用户 ID")
    query: str = Field(..., description="检索查询")
    top_k: int = Field(default=5, ge=1, le=50, description="返回数量")


class WorkingMemoryRequest(BaseModel):
    agent_id: str = Field(..., description="Agent/用户 ID")
    key: str = Field(..., description="键")
    value: Optional[str] = Field(default=None, description="值")


class ForgetRequest(BaseModel):
    agent_id: str = Field(..., description="Agent/用户 ID")
    memory_id: Optional[str] = Field(default=None, description="记忆 ID（不传则清除全部）")


# ==================== 路由 ====================

@router.post("/remember")
async def api_remember(req: RememberRequest):
    """记住一条信息"""
    try:
        from main import memory_manager
        memory_id = memory_manager.remember(
            agent_id=req.agent_id,
            session_id=req.session_id,
            role=req.role,
            content=req.content,
            memory_type=req.memory_type,
            importance=req.importance,
        )
        return {"ok": True, "memory_id": memory_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recall")
async def api_recall(req: RecallRequest):
    """检索相关记忆"""
    try:
        from main import memory_manager
        memories = memory_manager.recall(
            agent_id=req.agent_id,
            query=req.query,
            top_k=req.top_k,
        )
        return {
            "ok": True,
            "count": len(memories),
            "memories": [
                {
                    "id": m.id,
                    "content": m.content,
                    "memory_type": m.memory_type,
                    "importance": m.importance,
                    "similarity": m.metadata.get("_similarity"),
                    "created_at": m.created_at.isoformat(),
                }
                for m in memories
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/forget")
async def api_forget(req: ForgetRequest):
    """遗忘记忆"""
    try:
        from main import memory_manager
        count = memory_manager.forget(
            agent_id=req.agent_id,
            memory_id=req.memory_id,
        )
        return {"ok": True, "deleted_count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/context/{agent_id}")
async def api_get_context(agent_id: str, query: Optional[str] = None):
    """获取 LLM 可用上下文"""
    try:
        from main import memory_manager
        context = memory_manager.get_llm_context(
            agent_id=agent_id,
            query=query,
        )
        return {"ok": True, "context": context}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/working/set")
async def api_set_working(req: WorkingMemoryRequest):
    """设置工作记忆"""
    try:
        from main import memory_manager
        memory_manager.set_working(req.agent_id, req.key, req.value)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/working/{agent_id}/{key}")
async def api_get_working(agent_id: str, key: str):
    """获取工作记忆"""
    try:
        from main import memory_manager
        value = memory_manager.get_working(agent_id, key)
        if value is None:
            raise HTTPException(status_code=404, detail="Key not found")
        return {"ok": True, "key": key, "value": value}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/{agent_id}")
async def api_stats(agent_id: str):
    """获取记忆统计"""
    try:
        from main import memory_manager
        stats = memory_manager.stats(agent_id)
        return {"ok": True, "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
