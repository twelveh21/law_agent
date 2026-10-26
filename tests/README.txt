本目录保存自动化测试，而非应用源码。test_legal_rag.py 验证法律 RAG 行为；test_memory_system.py 验证记忆逻辑；test_tool_system.py 验证工具接口或注册/执行逻辑。测试应使用隔离的临时数据或假对象，避免意外修改真实法律知识库、SQLite 数据或调用外部模型；运行方式以 pyproject.toml 中的测试配置为准。
