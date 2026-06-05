"""tests/test_knowledge_extractor.py"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_extract_knowledge_with_numeric():
    """含数值的段落应被识别为知识。"""
    from api.knowledge_extractor import KnowledgeExtractor
    ext = KnowledgeExtractor(None, {"terminology": {}, "template_sections": []})
    output = "暴击率为15%，冷却时间30秒。玩家每日可购买体力3次。"
    result = ext.extract(output, [])
    assert any("暴击率" in e.content for e in result.entries)
    assert any("冷却" in e.content for e in result.entries)
    assert any("购买体力" in e.content for e in result.entries)


def test_extract_terminology():
    """术语定义应被正确提取。"""
    from api.knowledge_extractor import KnowledgeExtractor
    ext = KnowledgeExtractor(None, {"terminology": {}})
    output = "以下将「金币」简称为「G」，VIP等级达到3以上可购买月卡。"
    result = ext.extract(output, [])
    assert "G" in result.terminology_updates


def test_skip_generic_description():
    """通用描述不应被提取为知识。"""
    from api.knowledge_extractor import KnowledgeExtractor
    ext = KnowledgeExtractor(None, {"terminology": {}})
    output = "这是一个有趣的系统。玩家可以体验到丰富的游戏内容。"
    result = ext.extract(output, [])
    assert len(result.entries) == 0


def test_write_back_adds_to_kb():
    """write_back 应将新知识添加到知识库并更新画像。"""
    import tempfile, shutil
    tmp_dir = tempfile.mkdtemp(prefix="ke_wb_")
    try:
        from api.kb_project import KBProject
        project = KBProject(project_dir=tmp_dir)
        profile = {"terminology": {}}
        from api.knowledge_extractor import KnowledgeExtractor, KnowledgeEntry, ExtractionResult
        ext = KnowledgeExtractor(project, profile)
        result = ExtractionResult(
            entries=[
                KnowledgeEntry(content="暴击率为15%", category="数值", confidence=0.8),
                KnowledgeEntry(content="VIP3可购买月卡", category="规则", confidence=0.7),
            ],
            terminology_updates={"VIP": "VIP等级", "G": "金币"},
        )
        summary = ext.write_back(result)
        assert summary.added_to_kb == 2
        assert "VIP" in summary.updated_profile
        assert summary.drafts == 0
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
