本目录负责 RAG 的“查询”阶段。search.py 将用户问题转换为查询向量，按条件搜索向量存储，并处理候选结果、分数、过滤和返回数量等逻辑。它依赖 embeddings 提供向量化能力、storage 提供检索接口；文档解析和建库属于 app/rag/ingestion。
