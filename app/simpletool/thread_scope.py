"""Helpers for deriving private storage paths from LangGraph thread IDs."""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

from langchain_core.runnables import RunnableConfig

from app.common.path import DATA_DIR, PROJECT_ROOT


def get_thread_id(config: RunnableConfig | None) -> str | None:
    """Extract a non-empty thread ID from LangChain's runtime configuration."""
    configurable = (config or {}).get("configurable", {})
    thread_id = configurable.get("thread_id") if isinstance(configurable, dict) else None
    if not isinstance(thread_id, str) or not thread_id.strip():
        return None
    return thread_id.strip()


def thread_scoped_notes_enabled() -> bool:
    """Enable per-thread note folders for public multi-chat deployments."""
    return os.getenv("THREAD_SCOPED_NOTES", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }


def thread_notes_workspace(thread_id: str) -> Path:
    """Hash the client-provided ID so it can never become a filesystem path."""
    configured_root = os.getenv("LAW_NOTES_DIR")
    root = Path(configured_root).expanduser() if configured_root else DATA_DIR / "notes"
    if not root.is_absolute():
        root = PROJECT_ROOT / root
    thread_key = hashlib.sha256(thread_id.encode("utf-8")).hexdigest()
    return (root / "threads" / thread_key).resolve()


def delete_thread_notes(thread_id: str) -> int:
    """Remove one thread's note folder, refusing any path outside the notes root."""
    if not thread_scoped_notes_enabled():
        return 0

    target = thread_notes_workspace(thread_id)
    configured_root = os.getenv("LAW_NOTES_DIR")
    notes_root = Path(configured_root).expanduser() if configured_root else DATA_DIR / "notes"
    if not notes_root.is_absolute():
        notes_root = PROJECT_ROOT / notes_root
    expected_parent = (notes_root / "threads").resolve()
    if target.parent != expected_parent or target.is_symlink():
        raise ValueError("线程笔记目录越界，已拒绝删除")
    if not target.exists():
        return 0

    deleted_files = sum(1 for path in target.rglob("*") if path.is_file())
    shutil.rmtree(target)
    return deleted_files
