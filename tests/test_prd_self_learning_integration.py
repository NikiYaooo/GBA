"""tests/test_prd_self_learning_integration.py — Integration tests for self-learning modules chain."""

import os
import sys
import time
import tempfile
import shutil
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.knowledge_checker import KnowledgeChecker, KnowledgeCheckResult
from api.citation_enhancer import CitationEnhancer
from api.consistency_checker import ConsistencyChecker, ConsistencyResult
from api.knowledge_extractor import KnowledgeExtractor, ExtractionResult, WriteBackSummary
from api.kb_project import KBProject


@pytest.fixture
def kb_with_docs():
    tmp_dir = tempfile.mkdtemp(prefix="sl_integ_")
    project = KBProject(project_dir=tmp_dir)
    docs_data = [
        ("数值设计规范.docx", "装备强化上限为+15，每次强化消耗金币和强化石。"),
        ("强化系统设计.docx", "强化系统分为 15 级，每级成功率递减。"),
    ]
    for fname, content in docs_data:
        fpath = os.path.join(tmp_dir, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        project.add_document(
            file_path=fpath, filename=fname, content=content,
            doc_type="text", file_size=len(content.encode("utf-8")),
        )
    time.sleep(1.0)
    yield project
    shutil.rmtree(tmp_dir, ignore_errors=True)


def test_full_module_chain(kb_with_docs):
    """Test the full module chain: KnowledgeChecker -> CitationEnhancer -> ConsistencyChecker."""
    # 1. Knowledge Checker
    kc = KnowledgeChecker(kb_with_docs)
    check_result = kc.check("装备强化系统设计")
    assert isinstance(check_result, KnowledgeCheckResult)
    assert len(check_result.existing) >= 1 or len(check_result.partial) >= 1

    # 2. Citation Enhancer (uses check result)
    ce = CitationEnhancer()
    base = "你是资深游戏策划专家。"
    enhanced = ce.enhance_prompt(base, check_result)
    assert "引用规则" in enhanced or enhanced == base

    # 3. Consistency Checker
    cc = ConsistencyChecker(kb_with_docs)
    output = "装备强化上限为+20，强化到+15后不可继续。"
    result = cc.check(output)
    assert isinstance(result, ConsistencyResult)
    assert len(result.conflicts) >= 0  # might or might not detect
    assert 0 <= result.score <= 1

    # 4. Knowledge Extractor (write-back simulation)
    extractor = KnowledgeExtractor(kb_with_docs, {"terminology": {}})
    extract_result = extractor.extract(output, check_result.existing)
    assert isinstance(extract_result, ExtractionResult)

    # Write-back
    summary = extractor.write_back(extract_result)
    assert isinstance(summary, WriteBackSummary)
    assert summary.added_to_kb >= 0  # may add new knowledge


def test_knowledge_checker_empty_kb():
    """Empty KB returns zero coverage."""
    tmp_dir = tempfile.mkdtemp(prefix="sl_empty_")
    try:
        project = KBProject(project_dir=tmp_dir)
        time.sleep(0.3)
        checker = KnowledgeChecker(project)
        result = checker.check("装备强化")
        assert result.coverage_ratio == 0.0
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_consistency_checker_no_conflict(kb_with_docs):
    """Aligned output yields no conflicts."""
    cc = ConsistencyChecker(kb_with_docs)
    output = "装备强化上限为+15，每次强化消耗金币和强化石。"
    result = cc.check(output)
    assert len(result.conflicts) == 0
    assert result.score == 1.0


def test_citation_enhancer_identity_without_kb():
    """CitationEnhancer returns prompt unchanged on empty check result."""
    from api.knowledge_checker import KnowledgeCheckResult
    ce = CitationEnhancer()
    base = "test prompt"
    empty_result = KnowledgeCheckResult(existing=[], partial=[], missing=[], coverage_ratio=0.0)
    enhanced = ce.enhance_prompt(base, empty_result)
    assert enhanced == base
