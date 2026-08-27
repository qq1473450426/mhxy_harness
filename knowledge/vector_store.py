# -*- coding: utf-8 -*-
"""向量库 (Phase 3, 规格书 §17)。

优先选择: FAISS / Chroma / LanceDB(一种即可)。
本实现:
- 内置: numpy 词袋向量 + 余弦相似度(零额外依赖, 完全离线)
- 预留: FAISS 插槽(set_backend("faiss") 可切换)

Embedding 策略(内置):
- 中文文本按字符 bigram + 词 建立特征
- 适合小规模知识库(几千块), 避免下载嵌入模型
- 如需高质量语义检索, 可配置 bge-m3 (requirements-rag.txt)
"""
from __future__ import annotations

import hashlib
import logging
import math
import os
import pickle
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 中文停用词(最小集)
_STOP = set("的了是在和与及或我等你他她它们这那一个上有也对于把被到要会能可很都只不师门任务抓鬼长安")


class VectorStore:
    """本地向量库: 索引 Chunk 并支持相似度检索。"""

    def __init__(self, dim: int = 512, persist_path: str = "") -> None:
        self.dim = dim
        self.persist_path = persist_path
        self._items: List[dict] = []          # [{id, text, meta, vec}]
        self._idf: Dict[str, float] = {}      # 词 -> IDF
        self._docs: Dict[str, dict] = {}      # id -> chunk 元数据
        self._backend = "numpy"

    # ---------------- 特征提取 ----------------
    def _features(self, text: str) -> Dict[str, int]:
        """提取文本特征: 词 + 字符bigram。"""
        feats: Dict[str, int] = {}
        # 中文词(2-4字连续片段) + 英文词
        tokens = re.findall(r"[\u4e00-\u9fff]{1,4}|[a-zA-Z0-9]+", text)
        for tok in tokens:
            if tok in _STOP or len(tok) < 1:
                continue
            feats[tok] = feats.get(tok, 0) + 1
        # 字符 bigram 覆盖更细粒度
        chars = [c for c in text if "\u4e00" <= c <= "\u9fff"]
        for i in range(len(chars) - 1):
            bigram = chars[i] + chars[i + 1]
            feats[bigram] = feats.get(bigram, 0) + 1
        return feats

    def _hash_feat(self, feat: str) -> int:
        """特征 -> 稳定哈希索引(0..dim-1)。"""
        return int(hashlib.md5(feat.encode("utf-8")).hexdigest(), 16) % self.dim

    def embed(self, text: str) -> List[float]:
        """文本 -> 稀疏特征向量(归一化)。"""
        vec = [0.0] * self.dim
        feats = self._features(text)
        norm = 0.0
        entries = []
        for feat, cnt in feats.items():
            idx = self._hash_feat(feat)
            weight = (1.0 + math.log(cnt)) * self._idf.get(feat, 1.0)
            entries.append((idx, weight))
            norm += weight * weight
        norm = math.sqrt(norm) or 1.0
        for idx, weight in entries:
            vec[idx] = weight / norm
        return vec

    # ---------------- 索引 ----------------
    def add_chunks(self, chunks: List[Any]) -> int:
        """索引一批 Chunk。返回成功数。"""
        # 先算 IDF
        doc_freq: Dict[str, int] = {}
        for c in chunks:
            for feat in self._features(c.text):
                doc_freq[feat] = doc_freq.get(feat, 0) + 1
        n = max(1, len(chunks))
        self._idf = {f: math.log(n / (1 + df)) + 1 for f, df in doc_freq.items()}

        for c in chunks:
            cid = hashlib.md5(c.text.encode("utf-8")).hexdigest()[:16]
            if cid in self._docs:
                continue
            vec = self.embed(c.text)
            self._items.append({"id": cid, "text": c.text, "meta": c.to_dict(), "vec": vec})
            self._docs[cid] = c.to_dict()
        logger.info("向量库索引 %d 块", len(self._items))
        return len(self._items)

    def add_chunk(self, chunk: Any) -> None:
        self.add_chunks([chunk])

    # ---------------- 检索 ----------------
    def search(self, query: str, top_k: int = 3) -> List[Tuple[dict, float]]:
        """余弦相似度检索, 返回 [(chunk_meta, score)] 降序。"""
        if not self._items:
            return []
        qvec = self.embed(query)
        scored = []
        for item in self._items:
            s = sum(a * b for a, b in zip(qvec, item["vec"]))
            scored.append((item["meta"], s))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def size(self) -> int:
        return len(self._items)

    # ---------------- 持久化 ----------------
    def save(self, path: str = "") -> bool:
        p = path or self.persist_path
        if not p:
            return False
        try:
            os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
            with open(p, "wb") as f:
                pickle.dump({"items": self._items, "idf": self._idf,
                             "docs": self._docs, "dim": self.dim}, f)
            return True
        except Exception as e:
            logger.warning("向量库保存失败: %s", e)
            return False

    def load(self, path: str = "") -> bool:
        p = path or self.persist_path
        if not p or not os.path.exists(p):
            return False
        try:
            with open(p, "rb") as f:
                data = pickle.load(f)
            self._items = data["items"]
            self._idf = data["idf"]
            self._docs = data["docs"]
            self.dim = data["dim"]
            return True
        except Exception as e:
            logger.warning("向量库加载失败: %s", e)
            return False

    # ---------------- FAISS 插槽(Phase 3+) ----------------
    def set_backend(self, backend: str) -> None:
        """切换后端: numpy | faiss(需安装 faiss-cpu)。"""
        if backend == "faiss":
            try:
                import faiss  # type: ignore  # noqa: F401
                self._backend = "faiss"
                logger.info("向量库后端: FAISS")
            except Exception as e:
                logger.warning("faiss 未安装, 保持 numpy: %s", e)
        else:
            self._backend = "numpy"
