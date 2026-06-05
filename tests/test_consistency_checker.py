"""tests/test_consistency_checker.py"""

import os
import sys
import time
import tempfile
import shutil
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.consistency_checker import ConsistencyChecker, Conflict, ConsistencyResult
from api.kb_project import KBProject
from api.prd_self_check import PRDSelfCheck


@pytest.fixture
def kb_with_numeric_rules():
    """知识库含明确数值约束。"""
    tmp_dir = tempfile.mkdtemp(prefix="cc_test_")
    project = KBProject(project_dir=tmp_dir)

    docs_data = [
        ("数值设计规范.docx", "装备强化上限为+15，强化到+15后不可继续强化。"),
        ("战斗数值.docx", "暴击率上限为 50%，超过部分无效。"),
        ("系统规则.docx", "玩家每日可购买体力 3 次，每次消耗钻石 50。"),
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


def test_detect_numeric_conflict(kb_with_numeric_rules):
    """输出中的"强化上限+20"与知识库"上限+15"冲突，应检测为 HIGH。"""
    checker = ConsistencyChecker(kb_with_numeric_rules)
    output = "装备强化上限为+20，达到后不可继续。"
    result = checker.check(output)
    high_conflicts = [c for c in result.conflicts if c.level == "high"]
    assert len(high_conflicts) >= 1


def test_no_conflict_on_consistent_output(kb_with_numeric_rules):
    """与知识库一致的输出不应产生冲突。"""
    checker = ConsistencyChecker(kb_with_numeric_rules)
    output = "装备强化上限为+15，强化到+15后不可继续强化。"
    result = checker.check(output)
    high_conflicts = [c for c in result.conflicts if c.level == "high"]
    assert len(high_conflicts) == 0


def test_empty_output_returns_empty_result(kb_with_numeric_rules):
    """空输出应返回空结果。"""
    checker = ConsistencyChecker(kb_with_numeric_rules)
    result = checker.check("")
    assert len(result.conflicts) == 0
    assert result.score == 1.0


def test_check_and_validate_integration(kb_with_numeric_rules):
    """Test PRDSelfCheck.check_and_validate with both format and consistency checks."""
    from api.prd_self_check import PRDSelfCheck

    checker = PRDSelfCheck(data_dir=tempfile.mkdtemp())
    content = "装备强化上限为+20，达到后不可继续。"
    result = checker.check_and_validate(content, kb_with_numeric_rules)

    assert "passed" in result
    assert "format_issues" in result
    assert "consistency_issues" in result
    assert "consistency_score" in result
    assert "all_reasons" in result
    # Should have consistency issues (上限+20 vs +15)
    # imported tempfile and shutil used for cleanup
