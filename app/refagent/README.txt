本目录放 Reflection（反思式）Agent 的实验实现。reflection_agent.py 负责尝试、收集反馈并进行下一轮改进；refmemory.py 保存该流程需要的历史结果或反馈。它是 Agent 范式练习模块，不等同于法律 Agent 主入口；只有在主 Agent 明确接入后，API 才会实际使用它。

evidence_review.py：网页可选的一次异步回答复核。初稿由现有 Agent（含 MCP）生成，取当前轮成功的本地法条工具结果，由无业务工具的模型输出结构化 ReviewDecision。跳过无证据/超预算情况，异常保留初稿并明确标记；使用相同 AIMessage ID 替换已保存初稿，内部复核提示不进入聊天。默认关闭；开启时等待最终结果，通常额外调用一次模型。不保证事实正确，不代替资料版本核验；第一版仅复核本地法条材料，不纳入 Tavily、Memory、笔记或图片证据。
