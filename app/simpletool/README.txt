本目录保存面向 LangChain Agent 的工具适配函数。这里的函数负责把项目已有的业务能力转换成 LangChain 能识别的工具；不在这里重复实现法律检索、笔记存储等业务逻辑。

law_tools.py：包装 Qdrant/Chroma 法律知识检索和网页读取能力。联网搜索由 app/agent/mcp_tools.py 连接 Tavily MCP 提供，不再在这里直接调用 Tavily API。
note_tools.py：包装 app/note/NoteTool 与 app/context/ContextBuilder。save_project_note 仅在用户明确要求保存时创建笔记；search_project_notes 搜索笔记，并用 ContextBuilder 整理成上下文返回给 Agent。笔记保存在项目的 data/notes/legal_agent 目录中。
memory_tools.py：把 app/memory/MemoryTool 包装成 save_conversation_memory 和 search_conversation_memory 两个 LangChain 工具。工具从 LangChain 注入的 RunnableConfig 读取 configurable.thread_id，并将其同时作为 MemoryTool 的 user_id 和 session_id；SQLite 中因此按当前对话隔离持久记忆。仅启用 episodic（事件/经历）和 semantic（稳定事实/偏好）两类持久记忆；不启用每次创建工具都会重置的 working memory。保存必须由用户明确要求，搜索只覆盖当前 thread_id。
__init__.py：统一导出工具，供 app/agent/law.py 注册到 create_agent。

本地默认笔记仍保存在项目级目录。部署配置开启 THREAD_SCOPED_NOTES=true 后，笔记会按 LangGraph thread_id 哈希到独立目录；删除会话时同步清除该目录。thread_id 由浏览器提供，只能实现不同会话的基本隔离，不等于用户身份认证，也不能用于存放真实案件中的敏感信息。

MemoryTool 的 thread_id 隔离只区分不同聊天线程，不等同于真实用户身份认证。当前前端生成并提交 thread_id，因此不能把它当作安全凭证；如果部署为多用户服务，应从已认证的服务端身份中取得 user_id，并与 thread_id 一起做权限校验。删除会话时，后端会同时清除该 thread 的 LangGraph checkpoint、SQLite 持久记忆和（部署启用时）独立笔记目录。

本目录适合放轻量 LangChain 适配器；自定义 Tool 基类和参数 Schema 位于 app/tool。

更新：法律 Agent 的 Qdrant 查询已改为 search_legal_knowledge MCP 工具。law_tools.search_qdrant_knowledge 仅保留兼容入口，复用 app/rag/service.py，不再注册给 law.py。
