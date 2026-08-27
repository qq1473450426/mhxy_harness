# -*- coding: utf-8 -*-
"""知识库加载器 (Phase 3 扩展)。

从本地 xyq-skills 仓库(14 模块)加载 Markdown 文档, 建立:
- 模块索引: module -> [file paths]
- 文档内容: (source, title, content)

设计原则(规格书 §16):
- 知识库与自动化引擎解耦
- 不把游戏知识硬编码进 Python
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeDoc:
    """一篇知识文档。"""

    source: str       # 相对路径, 如 mhxy-task/SKILL.md
    module: str       # 模块名, 如 mhxy-task
    title: str
    content: str


class KnowledgeLoader:
    """加载本地知识库目录(Markdown)。"""

    def __init__(self, repo_path: str = "") -> None:
        self.repo_path = repo_path
        self.docs: List[KnowledgeDoc] = []
        self.module_index: Dict[str, List[KnowledgeDoc]] = {}

    def load(self, repo_path: Optional[str] = None) -> List[KnowledgeDoc]:
        """扫描并加载所有 .md 文件。返回文档列表。"""
        path = repo_path or self.repo_path
        if not path or not os.path.isdir(path):
            logger.warning("知识库目录不存在: %s", path)
            return []
        self.docs = []
        self.module_index = {}
        for root, _dirs, files in os.walk(path):
            for fname in files:
                if not fname.lower().endswith(".md"):
                    continue
                fpath = os.path.join(root, fname)
                rel = os.path.relpath(fpath, path).replace(os.sep, "/")
                module = rel.split("/")[0] if "/" in rel else "root"
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        content = f.read()
                except Exception as e:
                    logger.warning("读取文档失败 %s: %s", fpath, e)
                    continue
                title = fname[:-3]
                doc = KnowledgeDoc(source=rel, module=module, title=title, content=content)
                self.docs.append(doc)
                self.module_index.setdefault(module, []).append(doc)
        logger.info("知识库加载完成: %d 篇文档, %d 个模块", len(self.docs), len(self.module_index))
        return self.docs

    def modules(self) -> List[str]:
        return sorted(self.module_index.keys())

    def search(self, keyword: str, limit: int = 5) -> List[KnowledgeDoc]:
        """简单关键词检索(Phase 3 替换为向量检索)。"""
        hits = [d for d in self.docs if keyword in d.content]
        return hits[:limit]

    def get_module(self, module: str) -> List[KnowledgeDoc]:
        return self.module_index.get(module, [])
