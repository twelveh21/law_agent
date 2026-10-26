from uuid import uuid4

from .refmemory import (
    INITIAL_PROMPT_TEMPLATE,
    REFLECT_PROMPT_TEMPLATE,
    REFINE_PROMPT_TEMPLATE,
    Memory,
)


class ReflectionAgent:
    """Wrap an existing LangChain/LangGraph agent with a reflect-and-refine loop."""

    def __init__(self, agent, max_iterations: int = 3):
        if max_iterations < 0:
            raise ValueError("max_iterations 必须大于等于 0")

        self.agent = agent
        self.max_iterations = max_iterations
        self.memory = Memory()

    def run(self, task: str) -> str:
        """Generate an answer, review it, and refine it up to max_iterations times."""
        if not task.strip():
            raise ValueError("task 不能为空")

        # 每个任务单独保存记忆，避免多次 run() 时串入上一个任务的记录。
        self.memory = Memory()

        print(f"\n--- 开始处理任务：{task} ---")
        print("\n--- 正在进行初次尝试 ---")

        initial_prompt = INITIAL_PROMPT_TEMPLATE.format(task=task)
        initial_answer = self._get_llm_response(initial_prompt)
        self.memory.add_records("execution", initial_answer)

        for iteration in range(self.max_iterations):
            print(f"\n--- 正在进行第 {iteration + 1} 次反思 ---")

            last_answer = self.memory.get_last_execution()
            if last_answer is None:
                raise RuntimeError("Memory 中没有可供反思的初始答案")

            reflect_prompt = REFLECT_PROMPT_TEMPLATE.format(
                task=task,
                law_answer=last_answer,
            )
            feedback = self._get_llm_response(reflect_prompt)
            self.memory.add_records("reflection", feedback)

            if "无需改进" in feedback:
                print("\n评审认为答案无需改进，结束反思。")
                break

            refine_prompt = REFINE_PROMPT_TEMPLATE.format(
                task=task,
                last_ans_attempt=last_answer,
                feedback=feedback,
            )
            refined_answer = self._get_llm_response(refine_prompt)
            self.memory.add_records("execution", refined_answer)

        final_answer = self.memory.get_last_execution()
        if final_answer is None:
            raise RuntimeError("Memory 中没有最终答案")

        print(f"\n--- 任务完成 ---\n最终生成的法律分析：\n{final_answer}")
        return final_answer

    def _get_llm_response(self, prompt: str) -> str:
        """Invoke the configured agent and extract the final assistant message text."""
        result = self.agent.invoke(
            {"messages": [{"role": "user", "content": prompt}]},
            # 每次调用使用独立 thread，避免 Reflection 的内部提示污染普通聊天历史。
            config={"configurable": {"thread_id": f"reflection-{uuid4().hex}"}},
        )

        messages = result.get("messages", [])
        if not messages:
            raise RuntimeError("Agent.invoke() 返回结果中没有 messages")

        content = messages[-1].content
        if isinstance(content, str):
            return content

        # 某些模型会用文本块列表表示 content；这里只拼接其中的文本块。
        if isinstance(content, list):
            text_parts = [
                block["text"]
                for block in content
                if isinstance(block, dict) and isinstance(block.get("text"), str)
            ]
            if text_parts:
                return "\n".join(text_parts)

        raise TypeError(f"Agent 最后一条消息的 content 不是可识别的文本：{type(content).__name__}")
