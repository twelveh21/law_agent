from typing import Any, Optional


class Memory:
    """
    短期记忆模块用于存储智能体行动和反思
    """

    def __init__(self):
        """初始化空列表储存记录"""
        self.records: list[dict[str, Any]] = []

    def add_records(self, record_type: str, content: str) -> None:
        """向记忆增加记录"""
        self.records.append({"type": record_type, "content": content})

    def get_trajectory(self) -> str:
        """
        将所有记忆格式变成连贯文本，用于构建提示词
        """
        trajectory_parts = []
        for record in self.records:
            if record["type"] == "execution":
                trajectory_parts.append(f"上一轮答案：\n{record['content']}")
            elif record["type"] == "reflection":
                trajectory_parts.append(f"上一轮反思：\n{record['content']}")

        return "\n\n".join(trajectory_parts)

    def get_last_execution(self) -> Optional[str]:
        """
        获取最近一次执行结果
        """
        for record in reversed(self.records):
            if record["type"] == "execution":
                return record["content"]
        return None


INITIAL_PROMPT_TEMPLATE = """
你是一位资深法律助手，你要根据用户的要求，进行法律分析，法律分析要具备专业性和严谨性，
要根据法条和法律数据库以及权威网站的内容搜索结果回答。

要求: {task}

请直接输出回答。
"""
REFLECT_PROMPT_TEMPLATE = """
你是一位极其严格的法律评审专家和律师，对法律报道有严格的要求。
你的任务是审查以下法律报告，并专注于找出其在法律专业性严谨性和逻辑性的问题。

# 原始任务:
{task}

# 待审查的代码:
```
{law_answer}
```

请分析该法律回答的严谨性，专业性，逻辑性，完整性。
分析该法律回答是否查找了足够多的法条法规作为依据，是否前后逻辑通顺合理，是否直接解决了用户的需求，是否有补充。
如果不够完善，请提改进意见。如果无需改进，请必须明确输出“无需改进”。

请直接输出你的反馈，不要包含任何额外的解释。
"""

REFINE_PROMPT_TEMPLATE = """
你是一位资深的法律助手。你正在根据一位法律评审专家的反馈来优化你的法律报告。

# 原始任务:
{task}

# 你上一轮尝试的代码:
{last_ans_attempt}
评审员的反馈：
{feedback}

请根据评审员的反馈，生成一个优化后的新法律报告。
你的法律报告必须包含完整的法律引用索引，案例分析，证据分析。
请直接输出优化后的法律报告，不要包含任何额外的解释。
"""


