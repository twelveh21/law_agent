from datetime import datetime
from typing import List

from app.context.context_builder import ContextPacket


def _select(
    self,
    packets: List[ContextPacket],
    user_query: str,
    available_tokens: int
) -> List[ContextPacket]:
    """选择最相关的信息包

    Args:
        packets: 候选信息包列表
        user_query: 用户查询(用于计算相关性)
        available_tokens: 可用的 token 数量

    Returns:
        List[ContextPacket]: 选中的信息包列表
    """
    # 1. 分离系统指令和其他信息
    system_packets = [p for p in packets if p.metadata.get("type") == "system_instruction"]
    other_packets = [p for p in packets if p.metadata.get("type") != "system_instruction"]

    # 2. 计算系统指令占用的 token
    system_tokens = sum(p.token_count for p in system_packets)
    remaining_tokens = available_tokens - system_tokens

    if remaining_tokens <= 0:
        print("[WARNING] 系统指令已占满所有 token 预算")
        return system_packets

        # 3. 为其他信息计算综合分数
        scored_packets = []
        for packet in other_packets:
            # 计算相关性分数(如果尚未计算)
            if packet.relevance_score == 0.5:  # 默认值,需要重新计算
                relevance = self._calculate_relevance(packet.content, user_query)
                packet.relevance_score = relevance

            # 计算新近性分数
            recency = self._calculate_recency(packet.timestamp)

            # 综合分数 = 相关性权重 × 相关性 + 新近性权重 × 新近性
            combined_score = (
                    self.config.relevance_weight * packet.relevance_score +
                    self.config.recency_weight * recency
            )

            # 过滤低于最小相关性阈值的信息
            if packet.relevance_score >= self.config.min_relevance:
                scored_packets.append((combined_score, packet))

        # 4. 按分数降序排序
        scored_packets.sort(key=lambda x: x[0], reverse=True)

        # 5. 贪心选择:按分数从高到低填充,直到达到 token 上限
        selected = system_packets.copy()
        current_tokens = system_tokens

        for score, packet in scored_packets:
            if current_tokens + packet.token_count <= available_tokens:
                selected.append(packet)
                current_tokens += packet.token_count
            else:
                # Token 预算已满,停止选择
                break

        print(f"[ContextBuilder] 选择了 {len(selected)} 个信息包,共 {current_tokens} tokens")
        return selected

def calculate_relevance(self, content: str, query: str) -> float:
    """计算内容与查询的相关性

        使用简单的关键词重叠算法。在生产环境中,可以替换为向量相似度计算。

        Args:
            content: 内容文本
            query: 查询文本

        Returns:
            float: 相关性分数(0.0-1.0)
        """
        #分词
    content_words=set(content.lower().split())
    query_words=set(query.lower().split())

    if not query_words:
        return 0.0

    #Jaccard 相似度 并集除以交集
    intersection = content_words&query_words
    union=content_words|query_words

    return len(intersection)/len(union) if union else 0.0

def _calculate_recency(self, timestamp:datetime)-> float:
    """计算时间近因性分数

    使用指数衰减模型,24小时内保持高分,之后逐渐衰减。

    Args:
        timestamp: 信息的时间戳

    Returns:
        float: 新近性分数(0.0-1.0)
    """
    import math

    age_hours = (datetime.now() - timestamp).total_seconds() / 3600

    # 指数衰减:24小时内保持高分,之后逐渐衰减
    decay_factor = 0.1  # 衰减系数
    recency_score = math.exp(-decay_factor * age_hours / 24)

    return max(0.1, min(1.0, recency_score))  # 限制在 [0.1, 1.0] 范围内