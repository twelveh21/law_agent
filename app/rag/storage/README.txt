本目录封装 RAG 向量数据的持久化后端。qdrant.py 负责创建或连接 Qdrant collection，并提供向量及元数据的写入、查询等适配能力。上层 ingestion/retrieval 通过该层访问存储，不应各自重复创建客户端或硬编码数据库路径。项目配置可使用本地持久化目录或 Qdrant 服务，具体以配置为准。
