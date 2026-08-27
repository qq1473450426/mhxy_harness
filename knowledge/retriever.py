# -*- coding: utf-8 -*-
"""知识检索器 (Phase 3: RAG 检索)。

流程(规格书 §17):
    Document Loader -> Chunker -> Embedding -> Vector DB -> Retriever -> LLM

Phase 1: 关键词检索
Phase 3: 向量检索(vector_store) + 关键词混合, 支持引用溯源
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from .chunker import Chunker
from .loader import KnowledgeDoc, KnowledgeLoader
from .vector_store import VectorStore

logger = logging.getLogger(__name__)


class Retriever:
    """知识检索统一入口(RAG)。"""

    def __init__(self, loader: Optional[KnowledgeLoader] = None,
                 chunker: Optional[Chunker] = None,
                 vector_store: Optional[VectorStore] = None,
                 auto_index: bool = True) -> None:
        self.loader = loader or KnowledgeLoader()
        self.chunker = chunker or Chunker(max_chars=500)
        self.store = vector_store or VectorStore()
        self._indexed = False
        if auto_index:
            self.ensure_indexed()

    # ---------------- 索引 ----------------
    def ensure_indexed(self, repo_path: Optional[str] = None) -> int:
        """加载知识库并建索引(幂等)。返回索引块数。"""
        if self._indexed and self.store.size() > 0:
            return self.store.size()
        docs = self.loader.load(repo_path) if repo_path else (self.loader.docs or self.loader.load())
        if not docs:
            logger.warning("知识库为空, 检索不可用")
            return 0
        chunks = self.chunker.chunk_all(docs)
        n = self.store.add_chunks(chunks)
        self._indexed = True
        logger.info("RAG 索引完成: %d 块", n)
        return n

    # ---------------- 检索 ----------------
    def retrieve(self, query: str, top_k: int = 3) -> List[Tuple[Dict[str, Any], float]]:
        """向量检索, 返回 [(chunk_meta, score)] 降序。"""
        if self.store.size() == 0:
            self.ensure_indexed()
        return self.store.search(query, top_k)

    def retrieve_text(self, query: str, top_k: int = 3) -> str:
        """检索并拼接为 LLM 上下文文本。"""
        hits = self.retrieve(query, top_k)
        parts = []
        for i, (meta, score) in enumerate(hits, 1):
            src = meta.get("doc_source", "?")
            text = meta.get("text", "")
            parts.append(f"[知识{i}] (来源: {src}, 相关度 {score:.2f})")
            parts.append(text)
        return "\n".join(parts) if parts else "(知识库无相关条目)"

    # ---------------- 关键词回退 ----------------
    def retrieve_keyword(self, query: str, limit: int = 3) -> List[KnowledgeDoc]:
        """关键词检索(回退方案/补充)。"""
        return self.loader.search(query, limit)

    def stats(self) -> Dict[str, Any]:
        return {
            "docs": len(self.loader.docs),
            "modules": len(self.loader.modules()),
            "chunks": self.store.size(),
            "backend": self.store._backend,
        }
