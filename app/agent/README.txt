本目录负责法律 Agent 的组装和面向业务的调用服务。law.py 创建模型、提示词、检查点，并异步加载 MCP 工具后组装 Agent；mcp_tools.py 连接 Tavily 远程 MCP 服务并把服务端工具转换成 LangChain 工具；law_service.py 使用异步流式调用 Agent，供 API 层使用。FastAPI 在启动阶段创建 Agent，因此 Tavily MCP 工具在应用启动时发现，而不是每条用户消息都重新发现。

context_middleware.py：在每次模型调用前接入 ContextBuilder。最多考察最近 8 个旧对话轮次，在约 3000 token 的历史预算内挑选完整轮次，并按原时间顺序作为用户级参考消息传入；当前问题、图片、本轮工具调用及工具结果完整保留，系统提示词也保留。仅修改本次模型请求，不删除 checkpointer 中的聊天记录。预算仅覆盖选中的历史与记忆正文，不是整次请求的总上限；没有自动摘要，不自动检索笔记或 RAG。同步与异步模型调用都支持。

Memory 上下文接入：context_middleware 每次模型调用前从运行配置获取 thread_id，调用 memory_tools.retrieve_memory_packets 搜索此会话的 semantic/episodic 记忆（最多 3 条），与最近 8 轮历史共同交给 build_history_context 挑选，共享约 3000 token 正文预算。首次提问也能读取已保存的记忆；没有 thread_id 时跳过。异步路径在线程中检索 SQLite，失败仅记录错误类型并继续对话；不自动保存新记忆，不把记忆视为已核实的法律证据。

法律 RAG MCP：mcp_tools.load_legal_rag_mcp_tools 用当前 Python 启动 app/mcp_servers/legal_rag_server.py；main.lifespan 通过 AsyncExitStack 管理连接与子进程。law.py 注册 search_legal_knowledge 替代直接 Qdrant 工具，失败则按提示使用本地 Chroma。发现工具成功不代表 Qdrant 数据或 embedding 凭据可用，需实际检索验证。

异步会话存储：main.lifespan 创建 AsyncSqliteSaver 并 setup，通过参数传给 create_law_agent；law.py 不在导入时创建全局数据库连接。law_service.get_messages/clear_messages 使用 aget/adelete_thread，API 从 app.state 取得保存器并 await。关闭时 AsyncExitStack 清理 MCP 和 SQLite；沿用原 LAW_DATABASE_PATH，不迁移或清空历史数据库。
