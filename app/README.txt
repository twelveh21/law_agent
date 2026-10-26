本目录是应用主体源码包。main.py 创建 FastAPI 应用、挂载 app/api/v1 下的 HTTP 路由，并将 static 目录作为前端资源提供；agent、core、memory、rag 和 tool 等子包分别承担 Agent 组装、模型接口、记忆、检索增强生成和工具功能。项目根目录配置及数据路径集中在 common/path.py。
