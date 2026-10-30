"""Serve the existing legal RAG over MCP stdio."""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager, redirect_stdout
from pathlib import Path
from typing import Annotated

# Support direct script execution by a client from any working directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from app.rag.service import search_legal_knowledge_text

@asynccontextmanager
async def server_lifespan(server):
    try:
        yield {}
    finally:
        # Close only if a tool call actually loaded the Qdrant module.
        storage = sys.modules.get("app.rag.storage.qdrant")
        if storage is not None:
            storage.close_cached_pipelines()


mcp = FastMCP("法律知识库", lifespan=server_lifespan)
_retrieval_lock = asyncio.Lock()
logger = logging.getLogger(__name__)


def _search(query: str, top_k: int) -> str:
    # Protocol messages use stdout. Send existing RAG print output to stderr.
    with redirect_stdout(sys.stderr):
        return search_legal_knowledge_text(query, top_k)


@mcp.tool
async def search_legal_knowledge(
    query: Annotated[str, Field(min_length=1, description="需要检索的法律问题")],
    top_k: Annotated[int, Field(ge=1, le=20, description="最多返回的文本块数量")] = 5,
) -> str:
    """检索本项目 Qdrant 法律知识库，返回原文、可用的来源和条款/标题位置。"""
    # Serialize local Qdrant access and stdout redirection in this subprocess.
    async with _retrieval_lock:
        try:
            return await asyncio.to_thread(_search, query, top_k)
        except Exception as exc:
            logger.warning("Legal RAG retrieval failed error_type=%s", type(exc).__name__)
            raise ToolError("法律知识库检索失败，请检查 Qdrant 与向量模型配置，或使用其他检索工具。") from None


if __name__ == "__main__":
    mcp.run(transport="stdio", show_banner=False)
