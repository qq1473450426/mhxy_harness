# -*- coding: utf-8 -*-
"""Phase 3 测试: RAG + LLM 决策。"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm import LLMClient, parse_json_response, MockBackend
from core.brain import LLMBrain, RuleBrain
from core.game_state import GameState, GameStatus
from knowledge.loader import KnowledgeLoader
from knowledge.chunker import Chunker
from knowledge.vector_store import VectorStore
from knowledge.retriever import Retriever

REPO = "D:/project/python/mhxy_ai/xyq-skills"


def test_chunker_creates_chunks():
    loader = KnowledgeLoader(REPO)
    docs = loader.load()
    assert len(docs) > 0
    chunks = Chunker(max_chars=300).chunk_all(docs)
    assert len(chunks) > 100
    # 每块不超过限制
    for c in chunks[:50]:
        assert len(c.text) <= 400


def test_vector_store_search():
    loader = KnowledgeLoader(REPO)
    docs = loader.load()
    chunks = Chunker().chunk_all(docs)
    vs = VectorStore()
    vs.add_chunks(chunks[:100])
    hits = vs.search("师门任务", top_k=3)
    assert len(hits) == 3
    assert hits[0][1] >= hits[-1][1]  # 降序


def test_retriever_rag():
    if not os.path.isdir(REPO):
        return
    ret = Retriever(KnowledgeLoader(REPO))
    text = ret.retrieve_text("抓鬼队伍怎么配置", top_k=2)
    assert "知识1" in text or "知识库无相关条目" in text
    s = ret.stats()
    assert s["chunks"] > 0


def test_mock_llm_json():
    llm = LLMClient(provider="mock")
    data = llm.chat_json([{"role": "user", "content": "长安城 师门任务 提交"}])
    assert "action" in data
    assert "confidence" in data
    assert data["action"]["type"] == "SUBMIT_TASK"


def test_parse_json_with_codeblock():
    text = "```json\n{\"reason\": \"测试\", \"confidence\": 0.9}\n```"
    data = parse_json_response(text)
    assert data["confidence"] == 0.9


def test_llm_brain_decides():
    llm = LLMClient(provider="mock")
    brain = LLMBrain(llm=llm)
    gs = GameState(account_id="t1", status=GameStatus.CITY, map_name="长安城",
                   task_name="师门任务", task_progress="第2次")
    d = brain.decide(gs, goal="完成师门任务")
    assert d.action in ("SUBMIT_TASK", "OPEN_TASK", "UNKNOWN")
    assert 0 <= d.confidence <= 1


def test_llm_brain_fallback_on_error():
    # 无效 provider 的 llm 会抛错 -> 回退规则
    brain = LLMBrain(llm=None)
    gs = GameState(account_id="t", status=GameStatus.BATTLE, in_battle=True)
    d = brain.decide(gs)
    assert d.action == "BATTLE_AUTO"


def test_llm_brain_with_rag_knowledge():
    if not os.path.isdir(REPO):
        return
    llm = LLMClient(provider="mock")
    ret = Retriever(KnowledgeLoader(REPO))
    brain = LLMBrain(llm=llm, retriever=ret)
    gs = GameState(account_id="t", status=GameStatus.TASK_DIALOG, task_name="师门任务")
    d = brain.decide(gs, goal="师门任务怎么完成")
    # mock 决策不需要知识, 但 RAG 已索引
    assert ret.stats()["chunks"] > 0
