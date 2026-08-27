# -*- coding: utf-8 -*-
"""知识库加载/检索测试。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge.loader import KnowledgeLoader

REPO = "D:/project/python/mhxy_ai/xyq-skills"


def test_load_local_repo():
    if not os.path.isdir(REPO):
        return  # 无知识库时跳过
    loader = KnowledgeLoader(REPO)
    docs = loader.load()
    assert len(docs) > 0
    assert len(loader.modules()) >= 14
    assert any(d.module == "mhxy-task" for d in docs)


def test_keyword_search():
    if not os.path.isdir(REPO):
        return
    loader = KnowledgeLoader(REPO)
    loader.load()
    hits = loader.search("师门")
    assert len(hits) > 0
