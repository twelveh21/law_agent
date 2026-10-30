本目录放可单独运行的项目运维/数据处理脚本。build_knowledge_base.py 构建本地法律知识库；convert_pdf.py 批量提取 PDF 文本；watchdog_service.py 监控 input 并处理新文件；__init__.py 使脚本目录也可作为 Python 包导入。运行脚本前确认虚拟环境、.env、输入路径和目标数据库正确，避免覆盖不该改的数据。

ingest_qdrant.py：将指定 TXT 法律资料按法条切块，保留来源和条款编号，调用现有 index_chunks 向量化并 upsert 到 MCP 使用的 Qdrant collection。示例：uv run python -m scripts.ingest_qdrant data/劳动合同法.txt。支持多个文件；默认每批 16 条。不会更新旧法律版本，也不会自动删除已修改文件留下的旧切片。Qdrant 本地目录不能与另一进程同时打开，入库后关闭客户端。
