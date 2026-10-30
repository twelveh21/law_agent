from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from ...models.schemas import ChatRequest
from ...agent.law_service import search_recipes, get_messages, clear_messages
from ...common.rate_limit import enforce_rate_limit

router = APIRouter()


@router.post("/chat/stream")
async def chat_endpoint(request: Request, payload: ChatRequest):
    """流式对话"""
    enforce_rate_limit(request, "chat", "CHAT_RATE_LIMIT_PER_MINUTE")
    return StreamingResponse(
        search_recipes(
            request.app.state.agent,
            payload.message,
            payload.image_url or "",
            payload.thread_id,
            review_answer=payload.review_answer,
            reviewer=request.app.state.reviewer,
        ),
        media_type="text/event-stream"
    )


@router.get("/chat/messages")
async def get_chat_messages(request: Request, thread_id: str):
    """获取历史消息"""
    return await get_messages(request.app.state.checkpointer, thread_id)


@router.delete("/chat/messages")
async def clear_chat_messages(request: Request, thread_id: str):
    """删除指定会话及其对应的持久记忆。"""
    deleted_memories = await clear_messages(request.app.state.checkpointer, thread_id)
    return {"status": "ok", "deleted_memories": deleted_memories}
