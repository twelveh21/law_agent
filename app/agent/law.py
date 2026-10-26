"""Core assembly for the legal agent: model, checkpoint storage, prompt, and tools."""

import os
import sqlite3

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.sqlite import SqliteSaver

from app.common.path import DATABASE_PATH
from app.simpletool import (
    save_conversation_memory,
    save_project_note,
    search_law,
    search_local_knowledge,
    search_project_notes,
    search_conversation_memory,
    search_qdrant_knowledge,
    web_crawler,
)


base_url = os.getenv("DASHSCOPE_BASE_URL")
api_key = os.getenv("DASHSCOPE_API_KEY")

# Configure the model client. DashScope exposes an OpenAI-compatible API here.
model = init_chat_model(
    model="qwen3.5-plus",
    model_provider="openai",
    base_url=base_url,
    api_key=api_key,
)

# Keep conversation checkpoints in SQLite so threads can be resumed across requests.
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
connection = sqlite3.connect(str(DATABASE_PATH), check_same_thread=False)
checkpointer = SqliteSaver(connection)
checkpointer.setup()

system_prompt = """你是法律信息助理。回答时使用清晰、谨慎的中文。

【工具选择】
1. 用户询问法律问题时，先调用 search_qdrant_knowledge 检索 Qdrant 法律知识库。
2. 如果 Qdrant 没有结果或材料不足，再调用 search_local_knowledge 检索旧的本地 Chroma 知识库。
3. 如果本地材料仍不足，或问题涉及可能变化的法律信息，再调用 search_law 联网搜索。
4. 用户明确要求读取或提取某个网址时，调用 web_crawler。
5. 用户提到之前保存的项目笔记、结论或待办时，调用 search_project_notes 查询。
6. 只有用户明确说“记下来”“保存为笔记”等要求时，才调用 save_project_note；不要擅自保存普通对话、个人隐私或未经核实的法律结论。
7. 用户明确要求“记住”“保存到记忆”时，调用 save_conversation_memory；稳定偏好或事实可存为 semantic，某次经历、决定或事件存为 episodic。不得自动保存普通对话、身份证号、联系方式、密码等敏感信息或未经核实的法律结论。
8. 用户要求回忆之前对话中的个人偏好、事实或事件时，调用 search_conversation_memory；它只会搜索当前对话 thread_id 对应的记忆。项目级笔记仍使用 search_project_notes。
9. 不要调用不存在的工具；当前可用工具有 search_qdrant_knowledge、search_local_knowledge、search_law、web_crawler、search_project_notes、save_project_note、search_conversation_memory、save_conversation_memory。

【回答要求】
1. 法律结论必须依据工具返回的材料，不得编造法条、案例或来源。
2. 引用法条时注明法律名称和条款编号；无法确认时明确说明。
3. 检索结果不足以支持结论时，说明缺少什么信息，不要假装已经查到。
4. 用户提供图片时，结合图片中能识别的内容分析；无法识别的部分要明确说明。
5. 区分检索到的事实、基于材料的分析和仍需核实的内容。
"""

agent = create_agent(
    model=model,
    system_prompt=system_prompt,
    tools=[
        search_qdrant_knowledge,
        search_local_knowledge,
        search_law,
        web_crawler,
        search_project_notes,
        save_project_note,
        search_conversation_memory,
        save_conversation_memory,
    ],
    checkpointer=checkpointer,
)
