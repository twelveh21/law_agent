"""Application-level conversation operations for the legal agent."""

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage

from app.agent.law import agent, checkpointer
from app.common.logger import logger
from app.memory.memory_act import MemoryTool
from app.simpletool.note_tools import delete_project_notes_for_thread


def search_recipes(prompt: str, image: str, thread_id: str):
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

        for chunk, metadata in agent.stream(
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


def clear_messages(thread_id: str) -> int:
    """Delete one thread's checkpoint history and its thread-scoped memories."""
    logger.info(f"清空历史消息，thread_id: {thread_id}")
    checkpointer.delete_thread(thread_id)
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


def get_messages(thread_id: str) -> list[dict[str, str]]:
    """Return user and assistant messages saved for one conversation thread."""
    logger.info(f"获取历史消息，thread_id: {thread_id}")
    checkpoint = checkpointer.get({"configurable": {"thread_id": thread_id}})
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
