"""tests/test_ai_service.py — 项目画像 CRUD + 章节解析 + imitate-iterate 测试。"""

import os
import json
import tempfile
import shutil
import pytest

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
# 添加 api/ 目录到路径，使 routers 中的 from utils import ... 可工作
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

from api.routers.project_profile import load_profile, save_profile, DEFAULT_PROFILE


def test_project_profile_default():
    """默认项目画像返回空值。"""
    tmp_dir = tempfile.mkdtemp()
    try:
        profile = load_profile(tmp_dir)
        assert profile == DEFAULT_PROFILE
    finally:
        shutil.rmtree(tmp_dir)


def test_project_profile_save_and_load():
    """保存后加载返回相同值。"""
    tmp_dir = tempfile.mkdtemp()
    try:
        data = {"game_name": "梦幻西游", "genre": "MMORPG"}
        save_profile(data, tmp_dir)
        loaded = load_profile(tmp_dir)
        assert loaded["game_name"] == "梦幻西游"
        assert loaded["genre"] == "MMORPG"
    finally:
        shutil.rmtree(tmp_dir)


def test_parse_sections_empty():
    """解析空 HTML 返回空列表。"""
    from api.ai_service import AIService
    svc = AIService()
    assert svc._parse_sections("") == []


def test_parse_sections_with_headings():
    """解析含 h2/h3 标题的 HTML，返回章节列表。"""
    from api.ai_service import AIService
    svc = AIService()
    html = "<h2>背景</h2><p>内容</p><h2>规则</h2><p>规则内容</p><h3>子规则</h3><p>细节</p>"
    sections = svc._parse_sections(html)
    assert len(sections) == 3
    assert sections[0]["title"] == "背景"
    assert sections[1]["title"] == "规则"
    assert sections[2]["title"] == "子规则"


def test_parse_sections_no_headings():
    """解析无标题的 HTML 返回空列表。"""
    from api.ai_service import AIService
    svc = AIService()
    html = "<p>纯文本内容</p><p>没有标题</p>"
    assert svc._parse_sections(html) == []


@pytest.mark.asyncio
async def test_generate_outline():
    """测试大纲生成（mock AI 调用）。"""
    from api.ai_service import AIService
    svc = AIService()
    async def mock_call(model, messages):
        return '{"sections": [{"title": "活动背景", "desc": "活动目的"}, {"title": "活动规则", "desc": "签到规则"}]}'
    svc._call_api = mock_call

    outline = await svc._generate_outline("春节签到活动")
    assert len(outline) == 2
    assert outline[0]["title"] == "活动背景"


@pytest.mark.asyncio
async def test_merge_document():
    """测试文档合并。"""
    from api.ai_service import AIService
    svc = AIService()
    outline = [{"title": "背景"}, {"title": "规则"}]
    sections_html = ["<p>背景内容</p>", "<p>规则内容</p>"]
    merged = await svc._merge_document(outline, sections_html)
    assert "<h2>背景</h2>" in merged
    assert "<h2>规则</h2>" in merged
    assert "背景内容" in merged
    assert "规则内容" in merged


def test_query_rewriting():
    """测试查询改写。"""
    from api.kb_project import KBProject
    tmp = tempfile.mkdtemp()
    try:
        proj = KBProject(tmp)
        rewritten = proj._rewrite_query("做一个春节签到活动，持续7天")
        assert "签到" in rewritten or "春节" in rewritten or "活动" in rewritten
        assert "做一个" not in rewritten
    finally:
        shutil.rmtree(tmp)


@pytest.mark.asyncio
async def test_check_consistency():
    """测试一致性检查。"""
    from api.prd_self_check import PRDSelfCheck
    tmp = tempfile.mkdtemp()
    try:
        checker = PRDSelfCheck(tmp)
        content = "<h2>规则</h2><p>本活动不限次数</p><h2>限制</h2><p>每日限购1次</p>"
        issues = checker.check_consistency(content)
        assert len(issues) > 0
        assert any("限" in issue for issue in issues)
    finally:
        shutil.rmtree(tmp)
