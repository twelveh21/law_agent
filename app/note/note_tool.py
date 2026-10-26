"""Markdown/YAML note storage for long-running project tasks."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import yaml

from app.tool.tool_base import Tool, ToolParameter
from app.common.path import PROJECT_ROOT


class NoteTool(Tool):
    """Create, read, search, update, list, and delete project notes.

    Notes are human-readable Markdown files. A JSON index stores lightweight
    metadata so list/search do not need to parse every note file first.
    """

    NOTE_TYPES = {"task_state", "conclusion", "blocker", "action", "reference", "general"}

    def __init__(self, workspace: str | Path = "data/notes") -> None:
        super().__init__(name="notes", description="管理项目进度、结论、阻塞和行动笔记")
        workspace_path = Path(workspace).expanduser()
        if not workspace_path.is_absolute():
            workspace_path = PROJECT_ROOT / workspace_path
        self.workspace = workspace_path.resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.index_path = self.workspace / "notes_index.json"
        self.index: dict[str, dict[str, Any]] = self._load_index()

    def _load_index(self) -> dict[str, dict[str, Any]]:
        """Load the JSON index; create an empty one on first use."""
        if not self.index_path.exists():
            return {}
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"笔记索引无法读取: {self.index_path}") from exc
        if not isinstance(data, dict):
            raise ValueError("笔记索引格式错误：顶层必须是 JSON 对象")
        return data

    def _save_index(self) -> None:
        """Persist the in-memory index as readable UTF-8 JSON."""
        self.index_path.write_text(
            json.dumps(self.index, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _note_path(self, note_id: str) -> Path:
        """Build a path from a validated ID instead of trusting index paths."""
        if note_id not in self.index:
            raise ValueError(f"笔记不存在: {note_id}")
        if not re.fullmatch(r"note_\d{8}_\d{6}_[a-f0-9]{8}", note_id):
            raise ValueError("笔记 ID 格式不合法")
        return self.workspace / f"{note_id}.md"

    @staticmethod
    def _build_markdown(metadata: dict[str, Any], content: str) -> str:
        """Serialize metadata into YAML front matter followed by Markdown body."""
        yaml_header = yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False)
        return f"---\n{yaml_header}---\n\n{content.rstrip()}\n"

    @staticmethod
    def _parse_markdown(raw_content: str) -> tuple[dict[str, Any], str]:
        """Split a note's YAML front matter from its Markdown body."""
        lines = raw_content.splitlines()
        if not lines or lines[0].strip() != "---":
            return {}, raw_content.strip()
        try:
            closing_index = next(
                index for index in range(1, len(lines)) if lines[index].strip() == "---"
            )
        except StopIteration:
            return {}, raw_content.strip()
        metadata = yaml.safe_load("\n".join(lines[1:closing_index])) or {}
        if not isinstance(metadata, dict):
            raise ValueError("笔记 YAML 元数据必须是字典")
        body = "\n".join(lines[closing_index + 1:]).strip()
        return metadata, body

    def create_note(
        self,
        title: str,
        content: str,
        note_type: str = "general",
        tags: Optional[list[str]] = None,
    ) -> str:
        """Create a note and return its unique ID."""
        if not title.strip() or not content.strip():
            raise ValueError("title 和 content 不能为空")
        if note_type not in self.NOTE_TYPES:
            raise ValueError(f"note_type 必须是: {', '.join(sorted(self.NOTE_TYPES))}")
        now = datetime.now().isoformat(timespec="seconds")
        note_id = f"note_{datetime.now():%Y%m%d_%H%M%S}_{uuid4().hex[:8]}"
        metadata: dict[str, Any] = {
            "id": note_id,
            "title": title.strip(),
            "type": note_type,
            "tags": list(tags or []),
            "created_at": now,
            "updated_at": now,
        }
        note_path = self.workspace / f"{note_id}.md"
        note_path.write_text(self._build_markdown(metadata, content), encoding="utf-8")
        self.index[note_id] = metadata
        try:
            self._save_index()
        except Exception:
            note_path.unlink(missing_ok=True)
            self.index.pop(note_id, None)
            raise
        return note_id

    def read_note(self, note_id: str) -> dict[str, Any]:
        """Read one note and return {note_id, metadata, content}."""
        note_path = self._note_path(note_id)
        raw_content = note_path.read_text(encoding="utf-8")
        metadata, content = self._parse_markdown(raw_content)
        return {"note_id": note_id, "metadata": metadata or self.index[note_id], "content": content}

    def search_notes(
        self,
        query: str,
        limit: int = 10,
        note_type: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """Find notes by simple case-insensitive substring matching."""
        if limit <= 0:
            raise ValueError("limit 必须大于 0")
        query_lower = query.strip().lower()
        if not query_lower:
            raise ValueError("query 不能为空")
        scored_results: list[tuple[int, dict[str, Any]]] = []
        query_terms = self._search_terms(query_lower)
        for note_id, metadata in self.index.items():
            if note_type and metadata.get("type") != note_type:
                continue
            note_tags = set(metadata.get("tags", []))
            if tags and not note_tags.intersection(tags):
                continue
            try:
                note = self.read_note(note_id)
            except (OSError, ValueError, yaml.YAMLError):
                continue
            title = str(metadata.get("title", ""))
            searchable_text = f"{title} {note['content']}".lower()
            matched_terms = len(query_terms.intersection(self._search_terms(searchable_text)))
            if query_lower in searchable_text or matched_terms >= min(2, len(query_terms)):
                scored_results.append((matched_terms, self._result_record(note_id, metadata, note["content"])))
        scored_results.sort(
            key=lambda pair: (pair[0], pair[1]["updated_at"]), reverse=True
        )
        return [record for _, record in scored_results[:limit]]

    @staticmethod
    def _search_terms(text: str) -> set[str]:
        """Extract English words and Chinese character bigrams for simple search."""
        import re

        terms = set(re.findall(r"[a-z0-9_]+", text.lower()))
        chinese_runs = re.findall(r"[\u4e00-\u9fff]+", text)
        for run in chinese_runs:
            if len(run) == 1:
                terms.add(run)
            else:
                terms.update(run[index:index + 2] for index in range(len(run) - 1))
        return terms

    def list_notes(
        self,
        note_type: Optional[str] = None,
        tags: Optional[list[str]] = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """List note metadata, optionally filtered by type and tags."""
        if limit <= 0:
            raise ValueError("limit 必须大于 0")
        results = []
        for note_id, metadata in self.index.items():
            if note_type and metadata.get("type") != note_type:
                continue
            if tags and not set(metadata.get("tags", [])).intersection(tags):
                continue
            results.append(self._result_record(note_id, metadata))
        results.sort(key=lambda item: item["updated_at"], reverse=True)
        return results[:limit]

    def update_note(
        self,
        note_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        note_type: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> str:
        """Update only supplied fields; tags=[] intentionally clears all tags."""
        note = self.read_note(note_id)
        metadata = dict(note["metadata"])
        if title is not None:
            if not title.strip():
                raise ValueError("title 不能为空")
            metadata["title"] = title.strip()
        if note_type is not None:
            if note_type not in self.NOTE_TYPES:
                raise ValueError(f"不支持的 note_type: {note_type}")
            metadata["type"] = note_type
        if tags is not None:
            metadata["tags"] = list(tags)
        body = note["content"] if content is None else content
        metadata["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self._note_path(note_id).write_text(self._build_markdown(metadata, body), encoding="utf-8")
        self.index[note_id] = metadata
        self._save_index()
        return f"笔记已更新：{metadata['title']}"

    def delete_note(self, note_id: str) -> str:
        """Delete the Markdown file and remove its index record."""
        note_path = self._note_path(note_id)
        metadata = self.index[note_id]
        note_path.unlink(missing_ok=True)
        del self.index[note_id]
        self._save_index()
        return f"笔记已删除：{metadata.get('title', note_id)}"

    def summary(self) -> dict[str, Any]:
        """Return total count, counts per note type, and five latest notes."""
        type_counts: dict[str, int] = {}
        for metadata in self.index.values():
            note_type = metadata.get("type", "general")
            type_counts[note_type] = type_counts.get(note_type, 0) + 1
        recent = self.list_notes(limit=5)
        return {"total_notes": len(self.index), "type_distribution": type_counts, "recent_notes": recent}

    @staticmethod
    def _result_record(
        note_id: str, metadata: dict[str, Any], content: Optional[str] = None
    ) -> dict[str, Any]:
        """Create a stable result shape for callers and tests."""
        result = {
            "note_id": note_id,
            "title": metadata.get("title", ""),
            "type": metadata.get("type", "general"),
            "tags": metadata.get("tags", []),
            "created_at": metadata.get("created_at", ""),
            "updated_at": metadata.get("updated_at", ""),
        }
        if content is not None:
            result["content"] = content
        return result

    def get_parameters(self) -> list[ToolParameter]:
        """Describe the dictionary arguments accepted by run()."""
        return [
            ToolParameter(name="action", type="string", description="create/read/search/list/update/delete/summary"),
            ToolParameter(name="note_id", type="string", description="笔记 ID", required=False),
            ToolParameter(name="title", type="string", description="笔记标题", required=False),
            ToolParameter(name="content", type="string", description="Markdown 正文", required=False),
            ToolParameter(name="note_type", type="string", description="task_state/conclusion/blocker/action/reference/general", required=False),
            ToolParameter(name="tags", type="array", description="标签列表", required=False),
            ToolParameter(name="query", type="string", description="搜索关键词", required=False),
            ToolParameter(name="limit", type="integer", description="最多返回数量", required=False, default=10),
        ]

    def run(self, parameters: dict[str, Any]) -> str:
        """Execute one note operation and return JSON text for tool callers."""
        if not isinstance(parameters, dict):
            raise TypeError("NoteTool.run 的参数必须是字典")
        action = parameters.get("action")
        if action == "create":
            result: Any = {"note_id": self.create_note(
                title=parameters.get("title", ""), content=parameters.get("content", ""),
                note_type=parameters.get("note_type", "general"), tags=parameters.get("tags"),
            )}
        elif action == "read":
            result = self.read_note(parameters["note_id"])
        elif action == "search":
            result = self.search_notes(
                query=parameters.get("query", ""), limit=parameters.get("limit", 10),
                note_type=parameters.get("note_type"), tags=parameters.get("tags"),
            )
        elif action == "list":
            result = self.list_notes(
                note_type=parameters.get("note_type"), tags=parameters.get("tags"),
                limit=parameters.get("limit", 20),
            )
        elif action == "update":
            result = {"message": self.update_note(
                note_id=parameters["note_id"], title=parameters.get("title"),
                content=parameters.get("content"), note_type=parameters.get("note_type"),
                tags=parameters.get("tags"),
            )}
        elif action == "delete":
            result = {"message": self.delete_note(parameters["note_id"])}
        elif action == "summary":
            result = self.summary()
        else:
            raise ValueError("action 必须是 create/read/search/list/update/delete/summary")
        return json.dumps(result, ensure_ascii=False, indent=2)
