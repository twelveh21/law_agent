from typing import List, Optional
from pydantic import BaseModel, Field


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
    message: str
    image_url: Optional[str] = None
    thread_id: str


class ChatResponse(BaseModel):
    """后端返回的对话响应（可选，如果你需要自定义返回格式）"""
    answer: str
    references: List[Reference] = []
    thread_id: str