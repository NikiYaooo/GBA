"""tests/test_citation_enhancer.py"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.citation_enhancer import CitationEnhancer, Citation, CitationMetrics
from api.knowledge_checker import KnowledgeCheckResult, KBCoverageItem, MissingTopic


@pytest.fixture
def enhancer():
    return CitationEnhancer()


@pytest.fixture
def sample_check_result():
    return KnowledgeCheckResult(
        existing=[
            KBCoverageItem(
                excerpt="装备强化上限+15",
                content="装备强化上限为+15，每次强化消耗金币和强化石。",
                source="数值设计规范.docx",
                similarity=0.85,
                category="数值",
            ),
            KBCoverageItem(
                excerpt="强化分为 15 级",
                content="强化系统分为 15 级，每级成功率递减。",
                source="强化系统设计.docx",
                similarity=0.78,
                category="系统",
            ),
        ],
        partial=[
            KBCoverageItem(
                excerpt="玩家等级上限",
                content="玩家等级上限为 100 级。",
                source="角色成长设计.docx",
                similarity=0.55,
                category="数值",
            ),
        ],
        missing=[
            MissingTopic(topic="分解返还", suggestion="需 AI 自行设计"),
        ],
        coverage_ratio=0.72,
    )


def test_enhance_prompt_adds_citation_rules(enhancer, sample_check_result):
    """增强后的提示词应包含引用规则和知识清单。"""
    base_prompt = "你是资深游戏策划专家。"
    enhanced = enhancer.enhance_prompt(base_prompt, sample_check_result)
    assert "引用规则" in enhanced
    assert "数值设计规范.docx" in enhanced
    assert "分解返还" in enhanced
    assert enhanced.startswith(base_prompt)


def test_enhance_prompt_empty_result(enhancer):
    """空检查结果不应添加额外内容。"""
    empty = KnowledgeCheckResult(existing=[], partial=[], missing=[], coverage_ratio=0.0)
    enhanced = enhancer.enhance_prompt("Hello", empty)
    assert enhanced == "Hello"


def test_parse_citations_from_response(enhancer):
    """应正确解析引用标注并返回干净文本和引用列表。"""
    response = """## 强化消耗
每次强化消耗金币和强化石。[参考：数值设计规范.docx]
1-5 级成功率 100%。[参考：强化系统设计.docx]
装备不降级。[设计：AI自主设计]"""
    clean_text, citations, metrics = enhancer.parse_citations_from_response(response)
    assert "[参考：数值设计规范.docx]" not in clean_text
    assert "[设计：AI自主设计]" not in clean_text
    assert any(c.type == "reference" for c in citations)
    assert any(c.type == "ai_design" for c in citations)
    assert metrics.total_claims == 3
    assert metrics.coverage == pytest.approx(2/3, 0.01)


def test_parse_no_citations(enhancer):
    """无引用标注时应返回原文和空列表。"""
    response = "这是没有引用的纯文本。"
    clean, citations, metrics = enhancer.parse_citations_from_response(response)
    assert clean == response
    assert citations == []
    assert metrics.total_claims == 0
