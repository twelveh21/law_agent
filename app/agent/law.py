"""Core assembly for the legal agent: model, checkpoint storage, prompt, and tools."""

from contextlib import AsyncExitStack
import logging
import os

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.agent.context_middleware import LegalContextMiddleware
from app.agent.mcp_tools import load_legal_rag_mcp_tools, load_tavily_mcp_tools
from app.simpletool import (
    save_conversation_memory,
    save_project_note,
    search_local_knowledge,
    search_project_notes,
    search_conversation_memory,
    web_crawler,
)

logger = logging.getLogger(__name__)


base_url = os.getenv("DASHSCOPE_BASE_URL")
api_key = os.getenv("DASHSCOPE_API_KEY")

# Configure the model client. DashScope exposes an OpenAI-compatible API here.
model = init_chat_model(
    model="qwen3.5-plus",
    model_provider="openai",
    base_url=base_url,
    api_key=api_key,
)

def _build_system_prompt(tavily_tools, legal_tools) -> str:
    """Build instructions that name the MCP tools actually discovered at startup."""
    if tavily_tools:
        tavily_tool_list = "\n".join(
            f"- {tool.name}: {tool.description}" for tool in tavily_tools
        )
        web_search_instructions = f"""联网工具（Tavily MCP）：
{tavily_tool_list}
法律问题需要联网核实时，按工具说明选择搜索工具；拿到官方网页后可继续用网页提取/爬取工具读取正文。优先查询 gov.cn、法院或其他官方来源。"""
    else:
        web_search_instructions = "联网搜索工具当前不可用；只能依据本地检索材料回答，并明确说明无法联网核实。"

    legal_instructions = (
        "用户询问法律问题时，先调用 search_legal_knowledge 通过 MCP 检索 Qdrant 法律知识库。"
        if legal_tools else "法律知识库 MCP 当前不可用，使用 search_local_knowledge 检索本地 Chroma 知识库。"
    )
    return f"""你是法律信息助理。回答时使用清晰、谨慎的中文。

【工具选择】
1. {legal_instructions}
2. 如果 Qdrant 没有结果或材料不足，再调用 search_local_knowledge 检索旧的本地 Chroma 知识库。
3. {web_search_instructions}
4. 用户明确要求读取或提取某个网址时，优先使用 Tavily MCP 中适合的网页提取/爬取工具；若其不可用，再调用 web_crawler。
5. 用户提到之前保存的项目笔记、结论或待办时，调用 search_project_notes 查询。
6. 只有用户明确说“记下来”“保存为笔记”等要求时，才调用 save_project_note；不要擅自保存普通对话、个人隐私或未经核实的法律结论。
7. 用户明确要求“记住”“保存到记忆”时，调用 save_conversation_memory；稳定偏好或事实可存为 semantic，某次经历、决定或事件存为 episodic。不得自动保存普通对话、身份证号、联系方式、密码等敏感信息或未经核实的法律结论。
8. 用户要求回忆之前对话中的个人偏好、事实或事件时，调用 search_conversation_memory；它只会搜索当前对话 thread_id 对应的记忆。项目级笔记仍使用 search_project_notes。
9. 不要调用工具列表之外的工具。

【回答要求】
1. 法律结论必须依据工具返回的材料，不得编造法条、案例或来源。
2. 引用法条时注明法律名称和条款编号；无法确认时明确说明。
3. 检索结果不足以支持结论时，说明缺少什么信息，不要假装已经查到。
4. 用户提供图片时，结合图片中能识别的内容分析；无法识别的部分要明确说明。
5. 区分检索到的事实、基于材料的分析和仍需核实的内容。
"""


async def create_law_agent(
    mcp_stack: AsyncExitStack, checkpointer: AsyncSqliteSaver,
):
    """Load Tavily MCP tools, then assemble the application agent."""
    try:
        tavily_tools = await load_tavily_mcp_tools()
        logger.info(
            "Tavily MCP connected; discovered tools=%s",
            [tool.name for tool in tavily_tools],
        )
    except Exception as exc:
        # Keep local legal RAG and chat available during a Tavily outage.
        logger.warning(
            "Tavily MCP unavailable; online search disabled error_type=%s",
            type(exc).__name__,
        )
        tavily_tools = []

    try:
        legal_tools = await load_legal_rag_mcp_tools(mcp_stack)
        logger.info("Legal RAG MCP connected; discovered tools=%s", [tool.name for tool in legal_tools])
    except Exception as exc:
        logger.warning("Legal RAG MCP unavailable error_type=%s", type(exc).__name__)
        legal_tools = []

    return create_agent(
        model=model,
        system_prompt=_build_system_prompt(tavily_tools, legal_tools),
        tools=[
            search_local_knowledge,
            web_crawler,
            search_project_notes,
            save_project_note,
            search_conversation_memory,
            save_conversation_memory,
            *legal_tools,
            *tavily_tools,
        ],
        middleware=[LegalContextMiddleware()],
        checkpointer=checkpointer,
    )
