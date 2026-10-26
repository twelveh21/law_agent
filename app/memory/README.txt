本目录实现 Agent 记忆的基础数据结构和管理逻辑。memory_base.py 定义记忆条目/存储抽象，memory_act.py 实现记忆的添加、检索、过期或遗忘等行为。RAG 文档向量索引与会话记忆是不同用途：前者在 app/rag，后者在这里；通过工具暴露给 Agent 的适配代码位于 app/tool 或 app/simpletool。

MemoryManager.clear_memories() 会删除当前 manager 所属 user_id 下已启用类型的全部记忆；删除会话时，服务层以 thread_id 作为 user_id 调用此方法，清除该会话对应的持久记忆。
