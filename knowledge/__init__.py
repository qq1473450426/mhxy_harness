"""knowledge 包: 游戏知识库(解耦, 规格书 §16/§17/§18)。

Phase 3 完整实现: loader -> chunker -> embedding -> vector store -> retriever -> LLM
Phase 1 先提供 loader(扫描本地 xyq-skills) + 简单关键词检索。
"""
from .loader import KnowledgeLoader  # noqa: F401
