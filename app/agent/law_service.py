"""Application-level conversation operations for the legal agent."""

import asyncio

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage

from app.common.logger import logger
from app.memory.memory_act import MemoryTool
from app.refagent.evidence_review import answer_with_review
from app.simpletool.note_tools import delete_project_notes_for_thread


async def search_recipes(
    agent, prompt: str, image: str, thread_id: str,
    review_answer: bool = False, reviewer=None,
):
    """Stream a response from the legal agent for one chat request."""
    # Never put user content or signed image URLs in hosted service logs.
    logger.info(
        "收到对话请求 thread_id=%s has_image=%s",
        thread_id,
        bool(image and image.strip()),
    )
    try:
        if not image or image.strip() == "":
            message = HumanMessage(content=prompt)
        else:
            message = HumanMessage(
                content=[
                    {"type": "image", "url": image},
                    {"type": "text", "text": prompt},
                ]
            )

        if review_answer:
            if reviewer is None:
                raise RuntimeError("回答复核组件未初始化")
            yield await answer_with_review(
                agent, reviewer, message,
                {"configurable": {"thread_id": thread_id}},
            )
            return

        async for chunk, metadata in agent.astream(
            {"messages": [message]},
            {"configurable": {"thread_id": thread_id}},
            stream_mode="messages",
        ):
            if isinstance(chunk, AIMessageChunk) and chunk.content:
                yield chunk.content
    except Exception as exc:
        # SDK exceptions can contain request details; log only the exception type.
        logger.error("对话处理失败 error_type=%s", type(exc).__name__)
        yield "信息检索失败，请稍后重试。"


async def clear_messages(checkpointer, thread_id: str) -> int:
    """Delete one thread's checkpoint history and its thread-scoped memories."""
    logger.info(f"清空历史消息，thread_id: {thread_id}")
    await checkpointer.adelete_thread(thread_id)
    # Memory/note deletion uses synchronous file/database operations.
    return await asyncio.to_thread(_clear_thread_storage, thread_id)


def _clear_thread_storage(thread_id: str) -> int:
    memory_tool = MemoryTool(
        user_id=thread_id,
        session_id=thread_id,
        memory_types=["episodic", "semantic"],
    )
    deleted_memories = memory_tool.memory_manager.clear_memories()
    deleted_notes = delete_project_notes_for_thread(thread_id)
    logger.info(f"已删除 thread_id={thread_id} 的 {deleted_memories} 条记忆")
    logger.info(f"已删除 thread_id={thread_id} 的 {deleted_notes} 个笔记文件")
    return deleted_memories


async def get_messages(checkpointer, thread_id: str) -> list[dict[str, str]]:
    """Return user and assistant messages saved for one conversation thread."""
    logger.info(f"获取历史消息，thread_id: {thread_id}")
    checkpoint = await checkpointer.aget({"configurable": {"thread_id": thread_id}})
    if not checkpoint:
        return []

    channel_values = checkpoint.get("channel_values")
    if not channel_values:
        return []

    messages = channel_values.get("messages", [])
    result = []
    for message in messages:
        if not message.content:
            continue
        if isinstance(message, HumanMessage):
            result.append({"role": "user", "content": message.content})
        elif isinstance(message, AIMessage):
            result.append({"role": "assistant", "content": message.content})
    return result
