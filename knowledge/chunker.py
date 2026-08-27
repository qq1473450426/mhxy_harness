# -*- coding: utf-8 -*-
"""知识文档分块器 (Phase 3, 规格书 §17)。

Document Loader -> Chunker -> Embedding -> Vector DB -> Retriever -> LLM

中文 Markdown 分块策略:
- 按标题(##/###)切分为语义块
- 块大小上限(字符数), 超长再按段落/句号切分
- 保留来源信息(模块/文件/标题)用于引用溯源
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import List

from .loader import KnowledgeDoc

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """一个可检索的知识块。"""

    doc_source: str
    module: str
    doc_title: str
    heading: str
    text: str

    def to_dict(self) -> dict:
        return {"doc_source": self.doc_source, "module": self.module,
                "doc_title": self.doc_title, "heading": self.heading,
                "text": self.text}


class Chunker:
    """Markdown 分块器。"""

    def __init__(self, max_chars: int = 500, overlap: int = 50) -> None:
        self.max_chars = max_chars
        self.overlap = overlap

    def chunk_doc(self, doc: KnowledgeDoc) -> List[Chunk]:
        """把一篇文档切成多个 Chunk。"""
        chunks: List[Chunk] = []
        lines = doc.content.split("\n")
        current_heading = ""
        buffer: List[str] = []
        buffer_len = 0

        def flush():
            nonlocal buffer, buffer_len
            if not buffer:
                return
            text = "\n".join(buffer).strip()
            if text:
                chunks.append(Chunk(doc.source, doc.module, doc.title,
                                    current_heading, text))
            buffer = []
            buffer_len = 0

        for line in lines:
            stripped = line.strip()
            # 标题行 -> 新块
            if re.match(r"^#{1,4}\s+", line):
                flush()
                current_heading = re.sub(r"^#{1,4}\s*", "", line).strip()
                continue
            if not stripped:
                continue  # 空行跳过(节省空间)
            # 累积到 buffer, 超长则切分
            if buffer_len + len(stripped) > self.max_chars and buffer:
                flush()
            buffer.append(stripped)
            buffer_len += len(stripped) + 1
        flush()

        # 兜底: 无标题文档也应有块
        if not chunks:
            text = doc.content.strip()
            if text:
                chunks.append(Chunk(doc.source, doc.module, doc.title, "", text[:self.max_chars]))
        return chunks

    def chunk_all(self, docs: List[KnowledgeDoc]) -> List[Chunk]:
        all_chunks: List[Chunk] = []
        for d in docs:
            all_chunks.extend(self.chunk_doc(d))
        return all_chunks
