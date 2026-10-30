"""LangChain adapters that scope persistent memories to the active chat thread."""

from typing import Literal

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.context import ContextPacket
from app.memory.memory_act import MemoryTool
from app.memory.memory_base import MemoryConfig
from app.simpletool.thread_scope import get_thread_id


# These memory types use SQLite, so creating an adapter for each tool call does
# not lose the saved data. Working memory is in-process and is intentionally
# excluded because a new adapter is created for every call.
PersistentMemoryType = Literal["episodic", "semantic"]
_MEMORY_TYPES = ["episodic", "semantic"]


def _build_memory_tool(thread_id: str) -> MemoryTool:
    """Build a MemoryTool whose SQLite owner key is this conversation ID."""
    return MemoryTool(
        user_id=thread_id,
        session_id=thread_id,
        memory_config=MemoryConfig(),
        memory_types=_MEMORY_TYPES,
    )


def retrieve_memory_packets(thread_id: str, query: str, limit: int = 3) -> list[ContextPacket]:
    """Read this thread's saved memories as structured context candidates."""
    if not thread_id or not thread_id.strip() or not query.strip():
        return []
    memory_tool = _build_memory_tool(thread_id)
    memories = memory_tool.memory_manager.retrieve_memories(
        query=query,
        limit=limit,
        memory_types=_MEMORY_TYPES,
        min_importance=0.1,
    )
    return [
        ContextPacket(
            content=f"[用户曾保存的记忆｜{item.memory_type}｜{item.timestamp.isoformat()}]\n{item.content}",
            timestamp=item.timestamp,
            relevance_score=item.score,
            metadata={"type": "memory", "memory_id": item.id},
        )
        for item in memories
    ]


@tool
def save_conversation_memory(
    config: RunnableConfig,
    content: str,
    memory_type: PersistentMemoryType = "episodic",
    importance: float = 0.7,
) -> str:
    """Save a user-approved fact or event in this conversation's memory."""
    thread_id = get_thread_id(config)
    if thread_id is None:
        return "无法保存记忆：当前调用没有提供 thread_id。"

    memory_tool = _build_memory_tool(thread_id)
    return memory_tool.run(
        {
            "action": "add",
            "content": content,
            "memory_type": memory_type,
            "importance": importance,
        }
    )


@tool
def search_conversation_memory(
    config: RunnableConfig,
    query: str,
    limit: int = 5,
    memory_type: PersistentMemoryType | None = None,
) -> str:
    """Search only the persistent memories belonging to this conversation."""
    thread_id = get_thread_id(config)
    if thread_id is None:
        return "无法搜索记忆：当前调用没有提供 thread_id。"

    memory_tool = _build_memory_tool(thread_id)
    parameters: dict[str, object] = {
        "action": "search",
        "query": query,
        "limit": limit,
        "memory_types": [memory_type] if memory_type else _MEMORY_TYPES,
    }
    return memory_tool.run(parameters)
