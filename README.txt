项目总览

这是一个面向法律资料问答与文档分析的 Python 项目。主要功能包括：通过 FastAPI 提供接口、调用法律问答 Agent、检索本地法律知识库、管理会话记忆，以及处理输入文档并生成分析报告。

主要目录：
- app：应用源码；Agent、API、RAG、记忆、工具和前端都在这里。
- tests：自动化测试，验证法律 RAG、记忆和工具系统。
- scripts：知识库构建、PDF 转换、文件监控等可单独运行的脚本。
- pdf：法律 PDF 原始资料；data：供检索使用的法律文本资料。
- input：待分析文件；output：生成的分析报告。
- chroma_db、db：本地向量库和 SQLite 持久化数据，内部文件由数据库程序管理。
- docs：项目结构等维护文档；archives：历史 ZIP 快照。
- .env：本地密钥和配置，不要提交或分享。

启动入口是 app/main.py；具体运行命令和配置以 pyproject.toml、langgraph.json 及项目当前环境为准。虚拟环境、Python 缓存和 LangGraph 运行缓存属于自动生成内容，不是源码。
