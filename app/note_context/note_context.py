"""Coordinate project-note retrieval with framework-independent context building."""

from pathlib import Path
from typing import Any, Optional

from app.context import ContextBuilder, ContextConfig, ContextPacket
from app.note import NoteTool


class ProjectContextService:
    """Prepare context from recent conversation and relevant project notes.

    This class stops before calling an LLM. A LangChain adapter can take the
    returned context string and insert it into the agent's input messages.
    """

    def __init__(
        self,
        project_name: str,
        workspace: Optional[str | Path] = None,
        context_config: Optional[ContextConfig] = None,
        note_limit: int = 3,
    ) -> None:
        if not project_name.strip():
            raise ValueError("project_name 不能为空")
        if note_limit <= 0:
            raise ValueError("note_limit 必须大于 0")
        self.project_name = project_name
        self.note_limit = note_limit
        note_workspace = Path(workspace) if workspace else Path("data/notes") / project_name
        self.note_tool = NoteTool(workspace=note_workspace)
        self.context_builder = ContextBuilder(config=context_config or ContextConfig())

    def build_context(
        self,
        user_query: str,
        conversation_history: Optional[list[Any]] = None,
        system_instructions: Optional[str] = None,
        extra_packets: Optional[list[ContextPacket]] = None,
    ) -> str:
        """Retrieve relevant notes, convert them to packets, and build context."""
        note_results = self.note_tool.search_notes(
            query=user_query,
            limit=self.note_limit,
        )
        note_packets = self.context_builder.packets_from_notes(note_results)
        packets = [*note_packets, *(extra_packets or [])]
        return self.context_builder.build(
            user_query=user_query,
            conversation_history=conversation_history,
            system_instructions=system_instructions,
            custom_packets=packets,
        )
