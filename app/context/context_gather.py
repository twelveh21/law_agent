from datetime import datetime
from typing import Optional, List

from app.core.message import Message
from app.context.context_builder import ContextPacket


def _gather(
        self,
        user_query: str,
        conversation_history: Optional[List[Message]] = None,
        system_instructions: Optional[str] = None,
        custom_packets: Optional[List[ContextPacket]] = None
) -> List[ContextPacket]:
    """汇集所有候选信息

    Args:
        user_query: 用户查询
        conversation_history: 对话历史
        system_instructions: 系统指令
        custom_packets: 自定义信息包

    Returns:
        List[ContextPacket]: 候选信息列表
    """
    packets = []
    # 1.添加系统指令(最高优先级，不参与评分）
    if system_instructions:
        packets.append(ContextPacket(
            content=system_instructions,
            timestamp=datetime.now(),
            token_count=self._count_tokens(system_instructions),
            relevance_score=1.0,
            matadata={"type": "system_instruction", "priority": "high"}
        ))
    # 2.从记忆系统检索相关记忆
    if self.memory_tool:
        try:
            memory_results = self.memory_tool.run({
                "action": "search",
                "query": user_query,
                "limit": 10,
                "min_importance": 0.3
            })
            # 解析记忆结果并转换为ContextPacket
            memory_packets = self._parse_memory_results(memory_results, user_query)
            packets.append(memory_packets)
        except Exception as e:
            print(f"[WARNING]记忆检索失败{e}")

    # 3.从rag系统检索相关知识
    if self.rag_tool:
        try:
            rag_results = self.tag_tool.run({
                "action": "search",
                "query": user_query,
                "limit": 5,
                "min_importance": 0.3
            })
            # 解析rag结果并转换为ContextPacket
            rag_packets = self._parse_rag_results(rag_results, user_query)
            packets.extend(rag_packets)
        except Exception as e:
            print(f"[WARNING] RAG 检索失败: {e}")

    # 4.添加对话历史（仅保留最近的N条）
    if conversation_history:
        recent_history = conversation_history[-5:]  # 默认保留最近 5 条
        for msg in recent_history:
            packets.append(ContextPacket(
                content=f"{msg.role}: {msg.content}",
                timestamp=msg.timestamp if hasattr(msg, 'timestamp') else datetime.now(),
                token_count=self._count_tokens(msg.content),
                relevance_score=0.6,  # 历史消息的基础相关性
                metadata={"type": "conversation_history", "role": msg.role}
            ))

        # 5. 添加自定义信息包
        if custom_packets:
            packets.extend(custom_packets)

        print(f"[ContextBuilder] 汇集了 {len(packets)} 个候选信息包")
        return packets
