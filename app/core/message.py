from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# 限制消息角色类型
MessageRole = Literal["user", "assistant", "system", "tool"]


class Message(BaseModel):
    """框架内部统一使用的消息结构。"""

    content: str
    role: MessageRole
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, str]:
        """转换为模型聊天接口使用的 role/content 格式。"""
        return {"role": self.role, "content": self.content}

    def __str__(self) -> str:
        return f"[{self.role}] {self.content}"
