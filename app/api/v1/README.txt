本目录存放当前版本（v1）的 HTTP 接口实现。chat.py 处理对话请求并连接 Agent 服务；oss.py 处理对象存储上传所需的签名 URL 接口；__init__.py 使该目录可作为 Python 包导入。app/main.py 将这里的路由挂载到 /api/v1 前缀下。
