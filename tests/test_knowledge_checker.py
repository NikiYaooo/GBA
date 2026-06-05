"""tests/test_knowledge_checker.py"""

import os
import sys
import tempfile
import shutil
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.knowledge_checker import KnowledgeChecker, KnowledgeCheckResult, KBCoverageItem, MissingTopic
from api.kb_project import KBProject


@pytest.fixture
def kb_with_docs():
    """创建含 3 条文档的临时知识库（通过文件路径导入）。"""
    tmp_dir = tempfile.mkdtemp(prefix="kc_test_")
    project = KBProject(project_dir=tmp_dir)

    docs_data = [
        ("数值设计规范.docx", "装备强化上限为+15，每次强化消耗金币和强化石。"),
        ("强化系统设计.docx", "强化系统分为 15 级，每级成功率递减。1-5 级 100%，6-10 级 80%，11-15 级 50%。"),
        ("角色成长设计.docx", "玩家等级上限为 100 级，每升一级获得 5 属性点。"),
    ]
    for fname, content in docs_data:
        fpath = os.path.join(tmp_dir, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        project.add_document(
            file_path=fpath, filename=fname, content=content,
            doc_type="text", file_size=len(content.encode("utf-8")),
        )

    import time
    time.sleep(1.0)  # 等待索引构建和向量化
    yield project
    shutil.rmtree(tmp_dir, ignore_errors=True)


def test_check_returns_correct_categories(kb_with_docs):
    """查询"装备强化"应返回 existing 中包含数值/系统条目。"""
    checker = KnowledgeChecker(kb_with_docs)
    result = checker.check("装备强化系统设计，包含强化消耗和概率")
    assert isinstance(result, KnowledgeCheckResult)
    assert len(result.existing) >= 1
    assert hasattr(result, "coverage_ratio")
    assert 0 <= result.coverage_ratio <= 1
    assert len(result.existing) + len(result.partial) >= 1


def test_check_empty_kb():
    """空知识库应返回全缺失。"""
    tmp_dir = tempfile.mkdtemp(prefix="kc_empty_")
    try:
        project = KBProject(project_dir=tmp_dir)
        import time
        time.sleep(0.3)
        checker = KnowledgeChecker(project)
        result = checker.check("设计签到系统")
        assert len(result.existing) == 0
        assert len(result.partial) == 0
        assert len(result.missing) > 0  # 应检测到未覆盖的主题
        assert result.coverage_ratio == 0.0
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_format_check_result(kb_with_docs):
    """format_check_result 应生成包含'已有设定'和'未覆盖'两个区块的文本。"""
    checker = KnowledgeChecker(kb_with_docs)
    result = checker.check("装备强化签到")
    text = checker.format_check_result(result)
    assert "已有设定" in text
    assert "未覆盖" in text or "自行设计" in text
    assert isinstance(text, str)
    assert len(text) > 0
