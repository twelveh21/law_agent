from typing import List, Optional
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator, model_validator


# ===== 法律 Agent 专用数据结构 =====

class Reference(BaseModel):
    """搜索结果中引用的网页"""
    title: str = Field(description="The title of the web page cited in the answer")
    url: str = Field(description="The url of the web page cited in the answer")


class AnswerInfo(BaseModel):
    """法律 Agent 的最终回答"""
    answer: str = Field(description="The final answer for user")
    reference: List[Reference] = Field(description="The web page cited in the answer")


# ===== API 请求/响应模型（如果你用教程的对话接口，这个保留）=====

class ChatRequest(BaseModel):
    """前端发来的对话请求"""
    message: str = Field(max_length=8000)
    image_url: Optional[str] = Field(default=None, max_length=4096)
    thread_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9_-]+$",
    )

    @field_validator("image_url")
    @classmethod
    def validate_image_url(cls, value: Optional[str]) -> Optional[str]:
        """Accept only web URLs; the app forwards this URL to the vision model."""
        if value is None or not value.strip():
            return None
        value = value.strip()
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("image_url 必须是有效的 HTTP 或 HTTPS 地址")
        return value

    @model_validator(mode="after")
    def require_message_or_image(self) -> "ChatRequest":
        """Allow image-only questions, but reject an empty request."""
        if not self.message.strip() and not self.image_url:
            raise ValueError("message 和 image_url 不能同时为空")
        return self


class ChatResponse(BaseModel):
    """后端返回的对话响应（可选，如果你需要自定义返回格式）"""
    answer: str
    references: List[Reference] = []
    thread_id: str
