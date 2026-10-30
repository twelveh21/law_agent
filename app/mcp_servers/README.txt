法律检索 MCP 服务：legal_rag_server.py 用 FastMCP 提供 search_legal_knowledge(query, top_k=5) 工具。内部调用 app/rag/service.py，再使用既有 pipeline.retrieve_knowledge 查询 Qdrant。仅暴露查询，不暴露入库或删除。Agent 在 lifespan 中维持一个 stdio 子进程，关闭时清理；API 不再注册直接的 search_qdrant_knowledge。其他支持 stdio 的 MCP 客户端也可使用同一个 Python 脚本，需配置自己的运行环境、Qdrant 和向量模型密钥。
手动启动：项目虚拟环境 Python -m app.mcp_servers.legal_rag_server（stdio 模式不会打开网页，而是等待 MCP 客户端通信）。stdout 留给协议，普通输出转到 stderr。
Qdrant 本地目录不能由独立进程同时打开；服务运行时不要用另一个入库脚本同时访问该目录。需要并行入库或多个 Web worker 时应使用远程 Qdrant，设置 QDRANT_URL 等原有环境变量。
