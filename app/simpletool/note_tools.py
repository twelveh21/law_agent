"""LangChain adapters for persistent project notes and context assembly."""

import os
from pathlib import Path
from typing import Literal

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.common.path import DATA_DIR
from app.note_context.note_context import ProjectContextService
from app.simpletool.thread_scope import (
    get_thread_id,
    thread_notes_workspace,
    thread_scoped_notes_enabled,
)


_project_context = ProjectContextService(
    project_name="legal_agent",
    workspace=Path(os.getenv("LAW_NOTES_DIR", str(DATA_DIR / "notes"))) / "legal_agent",
    note_limit=3,
)

NoteType = Literal[
    "task_state",
    "conclusion",
    "blocker",
    "action",
    "reference",
    "general",
]


def _context_for_thread(config: RunnableConfig) -> ProjectContextService | None:
    """Use a separate notes folder per chat when this is a public deployment."""
    if not thread_scoped_notes_enabled():
        return _project_context
    thread_id = get_thread_id(config)
    if thread_id is None:
        return None
    return ProjectContextService(
        project_name="legal_agent",
        workspace=thread_notes_workspace(thread_id),
        note_limit=3,
    )


def delete_project_notes_for_thread(thread_id: str) -> int:
    """Delete notes scoped to a chat; shared local notes are left untouched."""
    from app.simpletool.thread_scope import delete_thread_notes

    return delete_thread_notes(thread_id)


@tool
def save_project_note(
    config: RunnableConfig,
    title: str,
    content: str,
    note_type: NoteType = "general",
    tags: list[str] | None = None,
) -> str:
    """Save a project note only when the user explicitly asks to remember it."""
    context = _context_for_thread(config)
    if context is None:
        return "无法保存笔记：当前调用没有提供 thread_id。"
    note_id = context.note_tool.create_note(
        title=title,
        content=content,
        note_type=note_type,
        tags=tags,
    )
    return f"笔记已保存。标题：{title}；类型：{note_type}；ID：{note_id}"


@tool
def search_project_notes(
    config: RunnableConfig,
    query: str,
    limit: int = 3,
    note_type: NoteType | None = None,
) -> str:
    """Search saved project notes and organize matching notes as answer context."""
    context = _context_for_thread(config)
    if context is None:
        return "无法搜索笔记：当前调用没有提供 thread_id。"
    notes = context.note_tool.search_notes(
        query=query,
        limit=limit,
        note_type=note_type,
    )
    if not notes:
        return f"没有找到与“{query}”相关的已保存笔记。"

    packets = context.context_builder.packets_from_notes(notes)
    return context.context_builder.build(
        user_query=query,
        custom_packets=packets,
    )
