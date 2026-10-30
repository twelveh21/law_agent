ContextBuilder 上下文整理组件说明。

RAG 证据整理：packets_from_rag 将检索结果正文、来源、条款/标题位置和检索分数包装为 rag_result 信息包；build_evidence_context 在预算内挑选完整片段，保留引用与原文，不调用截断压缩。不能容纳任何片段时返回明确提示；不把“未检索到”或服务异常转换成证据。
