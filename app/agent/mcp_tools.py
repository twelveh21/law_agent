"""Connections to remote MCP servers used by the legal agent."""

import os
import sys
from contextlib import AsyncExitStack
from typing import Any

from fastmcp import Client
from fastmcp.client.transports import PythonStdioTransport

from app.common.path import PROJECT_ROOT
from langchain.mcp import MCPAdapter


DEFAULT_TAVILY_MCP_URL = "https://mcp.tavily.com/mcp/"


async def load_tavily_mcp_tools() -> list[Any]:
    """Connect to Tavily MCP and return its tools as LangChain tools."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise RuntimeError("缺少 TAVILY_API_KEY，无法连接 Tavily MCP")

    mcp_url = os.getenv("TAVILY_MCP_URL", DEFAULT_TAVILY_MCP_URL)
    client = Client(mcp_url, auth=api_key)

    # list_tools() asks the MCP server what tools it offers and adapts them
    # into LangChain-compatible tools. The returned tools retain the client.
    async with MCPAdapter(client) as adapter:
        tools = await adapter.list_tools()

    if not tools:
        raise RuntimeError("Tavily MCP 已连接，但没有返回可用工具")

    return tools


async def load_legal_rag_mcp_tools(stack: AsyncExitStack) -> list[Any]:
    """Keep one local MCP process connected until the app lifespan ends."""
    transport = PythonStdioTransport(
        script_path=PROJECT_ROOT / "app" / "mcp_servers" / "legal_rag_server.py",
        python_cmd=sys.executable,
        cwd=str(PROJECT_ROOT),
        env=os.environ.copy(),
        keep_alive=False,
    )
    adapter = await stack.enter_async_context(MCPAdapter(Client(transport, timeout=60)))
    tools = await adapter.list_tools()
    if {tool.name for tool in tools} != {"search_legal_knowledge"}:
        raise RuntimeError("法律 RAG MCP 返回的工具列表不符合预期")
    return tools
