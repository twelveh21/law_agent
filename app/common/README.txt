本目录放多个模块共用的基础设施代码。path.py 从项目根目录加载 .env 并集中解析法律数据、PDF、输入输出、SQLite 和 Chroma 的路径；logger.py 配置日志；legal_rag.py 是法律知识检索相关的公共/兼容逻辑。这里应保持通用，具体 Agent 流程放在 agent，RAG 分层实现放在 rag。
