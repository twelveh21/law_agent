本目录实现法律 RAG（检索增强生成）的协调与核心能力。pipeline.py 串起文件解析、切块、来源标注和入库，并提供统一检索入口；simpletool 中的 search_qdrant_knowledge 会把检索结果交给 LangChain 法律 Agent。embeddings.py 管理文本向量化模型及维度；ingestion 负责入库，retrieval 执行查询，storage 管理 Qdrant。典型闭环是：准备资料→解析和切块→向量化并写库→按问题检索→Agent 根据命中的原文回答。

当前 Agent 检索入口已改为 MCP：app/mcp_servers/legal_rag_server.py → service.search_legal_knowledge_text → pipeline.retrieve_knowledge → Qdrant。simpletool.search_qdrant_knowledge 保留为兼容练习入口，未注册到当前 Agent。Qdrant 当前配置的 collection 在接入验证时为 0 个点，需通过现有 ingest_document 流程入库后才能检索到资料。

本地入库进展：已使用 scripts.ingest_qdrant 将 data/劳动合同法.txt 按法条切分为 98 个文本块并写入当前 rag_knowledge_base；通过真实 MCP 查询验证第三十七条及来源可返回。该文档版本未作现行性核验，本地数据不会自动上传到 Render。

RAG → ContextBuilder：service.search_legal_knowledge_text 在 retrieve_knowledge 返回后调用 build_evidence_context，最多返回约 3000 token 的完整证据片段（含来源和条款）。该预算独立于聊天历史/Memory 的 3000 token，不是模型请求总上限。MCP 客户端、工具调用编号和 LangChain ToolMessage 协议不变。
