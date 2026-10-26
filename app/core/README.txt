本目录是自建 Agent 框架的核心抽象层：agent.py 定义 Agent 基础接口或公共行为，config.py 管理配置，llm.py 封装大模型客户端调用，message.py 定义消息数据结构。它提供可复用的框架零件；具体法律 Agent 的业务组装在 app/agent，Reflection 等专门范式在 app/refagent。
