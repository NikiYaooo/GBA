# AI 写作全链路优化实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 将 AI 仿写从一次性生成升级为多轮对话式写作工作流，同时支持超长文档流水线生成、项目画像个性化约束、RAG 检索增强和 PRD 自检增强。

**架构：** 后端新增 imitate-iterate 端点 + 大纲→分节→合并流水线 + 项目画像 CRUD；前端新增 TipTap 扩展（节操作/选区操作）+ 右侧对话面板 + 设置页项目画像标签页。

**技术栈：** Python FastAPI + Vue 3 + TipTap/ProseMirror + Element Plus

---

## 文件结构

### 新文件
| 文件 | 职责 |
|------|------|
| `api/routers/project_profile.py` | 项目画像 CRUD 路由 |
| `src/utils/doc-sections.ts` | ProseMirror 文档章节解析 + 替换工具 |
| `src/extensions/AIIteration.ts` | TipTap 自定义扩展：AI 修改命令 + 节操作 UI |
| `src/components/panels/AIIterationPanel.vue` | 右侧 AI 对话折叠面板 |
| `tests/test_ai_service.py` | AI 服务新方法（imitate-iterate、大纲、分节、合并）测试 |

### 修改文件
| 文件 | 职责 |
|------|------|
| `api/ai_service.py` | +imitate_iterate() +_parse_sections() +_generate_outline() +_generate_sections() +_merge_document() +项目画像注入 |
| `api/routers/ai.py` | +POST /api/ai/imitate-iterate |
| `api/kb_project.py` | +_rewrite_query() 查询改写 |
| `api/prd_self_check.py` | +ai_check() +check_consistency() |
| `src/composables/useAI.ts` | +runIteration() +iterationHistory +showIterationPanel |
| `src/components/dialogs/SettingsDialog.vue` | +项目画像标签页 |
| `src/pages/HomePage.vue` | +工具栏 AI 按钮 +右侧面板挂载 +迭代事件绑定 |
| `src/types/index.ts` | +ProjectProfile 接口 |

---

### 任务 1：后端 — 项目画像 CRUD

**文件：**
- 创建：`api/routers/project_profile.py`
- 修改：`api/main.py`（注册新 router）
- 测试：`tests/test_ai_service.py`（在 test_ai_service.py 中写，因为 project_profile 数据最终被 ai_service 使用）

**数据模型：**

```python
# project_profile.py 内部定义
PROFILE_SCHEMA = {
    "game_name": "",
    "genre": "",
    "world_setting": "",
    "target_audience": "",
    "terminology": {},  # {"HP": "气血", ...}
    "template_sections": ["背景", "目标", "规则", "奖励", "限制", "UI"],
    "design_principles": [],  # ["所有数值必须可配置", ...]
}
```

- [ ] **步骤 1：编写失败的测试**

```python
# tests/test_ai_service.py — 先创文件
import os, json, tempfile, shutil, pytest
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

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
```

- [ ] **步骤 2：运行测试验证失败**

运行：`.venv\Scripts\python.exe -m pytest tests/test_ai_service.py::test_project_profile_default -v`
预期：ModuleNotFoundError（文件未创建）

- [ ] **步骤 3：实现 project_profile 路由**

```python
"""api/routers/project_profile.py — 项目画像 CRUD。"""

import os, json
from fastapi import APIRouter, Body, HTTPException
from utils import get_app_data_dir

router = APIRouter(prefix="/api/project-profile", tags=["project-profile"])

DEFAULT_PROFILE = {
    "game_name": "",
    "genre": "",
    "world_setting": "",
    "target_audience": "",
    "terminology": {},
    "template_sections": ["背景", "目标", "规则", "奖励", "限制", "UI"],
    "design_principles": [],
}

def _get_profile_path():
    data_dir = os.environ.get("GB_DATA_DIR", "")
    if not data_dir:
        data_dir = get_app_data_dir()
    return os.path.join(data_dir, "project_profile.json")

def load_profile() -> dict:
    path = _get_profile_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {**DEFAULT_PROFILE, **data}
        except Exception:
            pass
    return dict(DEFAULT_PROFILE)

def save_profile(profile: dict):
    path = _get_profile_path()
    merged = {**DEFAULT_PROFILE, **profile}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

@router.get("")
async def get_profile():
    return {"success": True, "data": load_profile()}

@router.put("")
async def update_profile(payload: dict = Body(...)):
    save_profile(payload)
    return {"success": True, "data": load_profile()}

@router.delete("")
async def reset_profile():
    save_profile(dict(DEFAULT_PROFILE))
    return {"success": True, "data": dict(DEFAULT_PROFILE)}
```

- [ ] **步骤 4：注册到 main.py**

在 `api/main.py` 中，找到 router import 区域，添加：

```python
from routers.project_profile import router as project_profile_router
app.include_router(project_profile_router)
```

- [ ] **步骤 5：运行测试验证通过**

运行：`.venv\Scripts\python.exe -m pytest tests/test_ai_service.py::test_project_profile_default tests/test_ai_service.py::test_project_profile_save_load -v`
预期：PASS

- [ ] **步骤 6：Commit**

```bash
git add api/routers/project_profile.py api/main.py tests/test_ai_service.py
git commit -m "feat: add project profile CRUD"
```

---

### 任务 2：后端 — 章节解析 + imitate-iterate 端点

**文件：**
- 修改：`api/ai_service.py`（+_parse_sections +imitate_iterate +项目画像注入方法）
- 修改：`api/routers/ai.py`（+POST imitate-iterate）
- 测试：`tests/test_ai_service.py`（+test_parse_sections +test_imitate_iterate）

- [ ] **步骤 1：编写失败的测试**

```python
def test_parse_sections_empty():
    from api.ai_service import AIService
    svc = AIService()
    assert svc._parse_sections("") == []

def test_parse_sections_with_headings():
    svc = AIService()
    html = "<h2>背景</h2><p>内容</p><h2>规则</h2><p>规则内容</p><h3>子规则</h3><p>细节</p>"
    sections = svc._parse_sections(html)
    assert len(sections) == 3
    assert sections[0]["title"] == "背景"
    assert sections[1]["title"] == "规则"
    assert sections[2]["title"] == "子规则"

def test_parse_sections_no_headings():
    svc = AIService()
    html = "<p>纯文本内容</p><p>没有标题</p>"
    assert svc._parse_sections(html) == []
```

- [ ] **步骤 2：运行测试验证失败**

运行：`.venv\Scripts\python.exe -m pytest tests/test_ai_service.py::test_parse_sections_empty -v`
预期：FAIL（方法不存在）

- [ ] **步骤 3：实现 _parse_sections**

```python
# 在 AIService 类中添加：
def _parse_sections(self, html: str) -> list:
    """将 HTML 文档按 h2/h3 标题解析为章节列表。
    返回: [{title, level, content_html, content_text}, ...]
    """
    import re
    if not html:
        return []
    # 只匹配 <h2> 和 <h3>（章节级标题）
    pattern = r'<h([23])(?:\s+[^>]*)?>(.*?)</h\1>'
    matches = list(re.finditer(pattern, html, re.IGNORECASE))
    if not matches:
        return []
    sections = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(html)
        title = re.sub(r'<[^>]+>', '', m.group(2)).strip()
        content_html = html[start:end].strip()
        sections.append({
            "title": title,
            "level": int(m.group(1)),
            "content_html": content_html,
            "content_text": re.sub(r'<[^>]+>', '', content_html).strip(),
        })
    return sections
```

- [ ] **步骤 4：运行测试验证通过**

- [ ] **步骤 5：实现 imitate_iterate 方法**

```python
# 在 AIService 类中添加：
async def imitate_iterate(
    self, model: str, full_doc: str, instruction: str,
    mode: str = "section", target_section: str = "",
    selection_context: dict = None,
    project_id: str = "",
    template_content: str = "",
) -> str:
    """多轮迭代修改。返回替换内容（HTML）。"""

    # 1. 解析章节
    sections = self._parse_sections(full_doc)
    if not sections:
        mode = "full"

    # 2. 构建修订 Prompt
    system_prompt = "你是资深游戏策划「张工」，正在修订一份 PRD 文档。你只输出修改后的目标内容，不输出其他内容。保持与原文一致的格式和风格。严格遵循项目已有的设定，不自创。"

    # 注入项目画像
    profile = self._load_project_profile()
    if profile and profile.get("game_name"):
        profile_text = self._build_profile_constraint(profile)
        system_prompt += f"\n\n【项目画像 - 必须遵守】\n{profile_text}"

    user_parts = []
    context_before = ""
    context_after = ""
    target_content = ""

    if mode == "section" and target_section:
        for i, sec in enumerate(sections):
            if sec["title"] == target_section:
                target_content = sec["content_text"]
                if i > 0:
                    prev = sections[i-1]
                    context_before = f"[前节: {prev['title']}] {prev['content_text'][:100]}"
                if i + 1 < len(sections):
                    nxt = sections[i+1]
                    context_after = f"[后节: {nxt['title']}] {nxt['content_text'][:100]}"
                break

        if not target_content:
            mode = "full"

    if mode == "section" and target_content:
        if context_before:
            user_parts.append(f"【前节参考】\n{context_before}\n")
        user_parts.append(f"【需要修改的章节：{target_section}】\n{target_content}\n")
        if context_after:
            user_parts.append(f"【后节参考】\n{context_after}\n")
        user_parts.append(f"【修改要求】\n{instruction}")
        user_parts.append("\n请只输出修改后的章节内容（不含标题），保持格式与原文一致。")
    elif mode == "selection" and selection_context:
        user_parts.append(f"【选中文本之前的内容】\n{selection_context.get('before', '')}\n")
        user_parts.append(f"【选中的文本】\n{selection_context.get('selected', '')}\n")
        user_parts.append(f"【选中文本之后的内容】\n{selection_context.get('after', '')}\n")
        user_parts.append(f"【修改要求】\n{instruction}")
        user_parts.append("\n请只输出修改后的选中文本内容。")
    else:
        user_parts.append(f"【当前文档全文】\n{full_doc}\n")
        user_parts.append(f"【修改要求】\n{instruction}")

    # RAG 上下文（如有关联项目）
    rag_context = ""
    if project_id and self.kb:
        proj = self.kb.get_project(project_id)
        if proj:
            results = proj.search(instruction, top_k=3)
            if results:
                rag_context = "\n".join(f"[来源: {r['metadata'].get('filename', '')}] {r['content']}" for r in results)
                user_parts.append(f"【知识库参考】\n{rag_context}")

    user_text = "\n".join(user_parts)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]

    response = await self._call_api(model, messages)

    if not response or len(response.strip()) < 10:
        raise ValueError("AI 未能生成有效修改内容")

    return response.strip()

def _load_project_profile(self) -> dict:
    """加载项目画像配置。"""
    try:
        from routers.project_profile import load_profile
        return load_profile()
    except Exception:
        return {}

def _build_profile_constraint(self, profile: dict) -> str:
    """将项目画像格式化为约束文本。"""
    lines = []
    if profile.get("game_name"):
        lines.append(f"项目名称: {profile['game_name']}")
    if profile.get("genre"):
        lines.append(f"游戏类型: {profile['genre']}")
    if profile.get("world_setting"):
        lines.append(f"世界观: {profile['world_setting']}")
    if profile.get("terminology"):
        lines.append("\n术语映射（使用以下术语，不得混用）:")
        for k, v in profile["terminology"].items():
            lines.append(f"  {k} → {v}")
    if profile.get("design_principles"):
        lines.append("\n设计原则:")
        for p in profile["design_principles"]:
            lines.append(f"  - {p}")
    return "\n".join(lines)
```

- [ ] **步骤 6：添加 imitate-iterate 路由**

在 `api/routers/ai.py` 中添加：

```python
@router.post("/imitate-iterate")
async def imitate_iterate(payload: dict = Body(...)):
    model = payload.get("model", "DeepSeek")
    full_doc = payload.get("full_doc", "")
    instruction = payload.get("instruction", "")
    mode = payload.get("mode", "section")
    target_section = payload.get("target_section", "")
    selection_context = payload.get("selection_context", None)
    project_id = payload.get("project_id", "")
    template_content = payload.get("template_content", "")

    if not full_doc:
        raise HTTPException(status_code=400, detail="文档内容不能为空")
    if not instruction:
        raise HTTPException(status_code=400, detail="修改指令不能为空")
    if mode == "section" and not target_section:
        raise HTTPException(status_code=400, detail="章节模式下必须指定目标章节")
    if mode == "selection" and not selection_context:
        raise HTTPException(status_code=400, detail="选区模式下必须提供选中上下文")

    try:
        result = await get_ai_service().imitate_iterate(
            model, full_doc, instruction, mode=mode,
            target_section=target_section,
            selection_context=selection_context,
            project_id=project_id,
            template_content=template_content,
        )
        return {"success": True, "data": {
            "replacement": result,
            "section_title": target_section,
            "mode": mode,
        }}
    except ValueError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        return {"success": False, "message": f"AI 服务调用失败: {str(e)}"}
```

- [ ] **步骤 7：运行测试验证通过**

- [ ] **步骤 8：Commit**

```bash
git add api/ai_service.py api/routers/ai.py tests/test_ai_service.py
git commit -m "feat: add imitate-iterate endpoint with section parsing"
```

---

### 任务 3：后端 — 超长文档生成流水线

**文件：**
- 修改：`api/ai_service.py`（+_generate_outline +_generate_sections +_merge_document，修改 imitate）
- 测试：`tests/test_ai_service.py`

- [ ] **步骤 1：编写失败的测试**

```python
@pytest.mark.asyncio
async def test_generate_outline():
    """测试大纲生成（mock AI 调用）。"""
    from api.ai_service import AIService
    svc = AIService()
    # 模拟 _call_api 返回 JSON
    async def mock_call(model, messages):
        return '{"sections": [{"title": "活动背景", "desc": "活动目的"}, {"title": "活动规则", "desc": "签到规则"}]}'
    svc._call_api = mock_call

    outline = await svc._generate_outline("春节签到活动")
    assert len(outline) == 2
    assert outline[0]["title"] == "活动背景"

@pytest.mark.asyncio
async def test_merge_document():
    svc = AIService()
    outline = [{"title": "背景"}, {"title": "规则"}]
    sections_html = ["<p>背景内容</p>", "<p>规则内容</p>"]
    merged = await svc._merge_document(outline, sections_html)
    assert "<h2>背景</h2>" in merged
    assert "<h2>规则</h2>" in merged
    assert "背景内容" in merged
    assert "规则内容" in merged
```

- [ ] **步骤 2：运行测试验证失败**

- [ ] **步骤 3：实现 _generate_outline**

```python
async def _generate_outline(self, requirements: str, model: str = "DeepSeek", project_id: str = "") -> list:
    """生成文档大纲。返回 [{title, desc}, ...]"""
    # 构建大纲 Prompt
    profile = self._load_project_profile()
    profile_note = ""
    if profile and profile.get("template_sections"):
        profile_note = f"\n项目常用章节: {', '.join(profile['template_sections'])}"

    prompt = f"""你是一名资深游戏策划架构师。请为用户需求规划 PRD 文档大纲。

需求：{requirements}{profile_note}

要求：
- 输出 4-8 个章节
- 每个章节给出标题和一句话说明
- 标准章节参考：背景/目标、规则/流程、奖励/数值、限制/条件、UI/交互

请只输出 JSON 格式：{{"sections": [{{"title": "章节标题", "desc": "说明"}}]}}
不要输出其他内容。"""

    messages = [
        {"role": "system", "content": "你是一位严格输出 JSON 的文档架构师。"},
        {"role": "user", "content": prompt},
    ]

    response = await self._call_api(model, messages)  # 大纲用用户选择的模型
    import json, re
    json_match = re.search(r'\{[\s\S]*\}', response)
    if json_match:
        try:
            data = json.loads(json_match.group())
            return data.get("sections", [])
        except json.JSONDecodeError:
            pass
    # 回退：按空行分割
    return [{"title": "概述", "desc": ""}, {"title": "规则", "desc": ""}, {"title": "奖励", "desc": ""}]
```

- [ ] **步骤 4：实现 _generate_sections**

```python
async def _generate_sections(
    self, outline: list, requirements: str,
    model: str, project_id: str = "", template_content: str = ""
) -> list:
    """逐节生成（可并行）。返回 [html_string, ...]"""
    import asyncio
    profile = self._load_project_profile()
    profile_text = self._build_profile_constraint(profile) if profile.get("game_name") else ""

    async def gen_section(sec: dict) -> str:
        title = sec["title"]
        user_parts = []

        # RAG 上下文
        rag_context = ""
        if project_id and self.kb:
            proj = self.kb.get_project(project_id)
            if proj:
                results = proj.search(f"{requirements} {title}", top_k=3)
                if results:
                    rag_context = "\n".join(
                        f"[来源: {r['metadata'].get('filename', '')}] {r['content']}"
                        for r in results
                    )
                    user_parts.append(f"【{title} 相关的知识库参考】\n{rag_context}\n")

        user_parts.append(f"【用户需求】\n{requirements}\n")
        user_parts.append(f"【当前章节】\n{title}\n")
        user_parts.append(f"【章节说明】\n{sec.get('desc', '')}\n")

        if template_content:
            user_parts.append(f"【文档模板参考】\n{template_content}\n")

        user_parts.append(f"请生成「{title}」章节的内容，使用 Markdown 格式。只输出该章节内容，不要输出标题。")

        system = ENHANCED_SYSTEM_PROMPT
        if profile_text:
            system += f"\n\n【项目画像 - 必须遵守】\n{profile_text}"

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": "\n".join(user_parts)},
        ]
        return await self._call_api(model, messages)

    # 并行生成所有章节
    tasks = [gen_section(sec) for sec in outline]
    sections_html = await asyncio.gather(*tasks)
    return sections_html
```

- [ ] **步骤 5：实现 _merge_document**

```python
async def _merge_document(self, outline: list, sections_html: list) -> str:
    """合并章节为完整文档。"""
    parts = []
    for sec, html in zip(outline, sections_html):
        if not html or len(html.strip()) < 20:
            continue
        parts.append(f"<h2>{sec['title']}</h2>\n{html}")
    full_doc = "\n".join(parts)

    # 一致性检查
    if self.checker:
        try:
            issues = self.checker.check_consistency(full_doc)
            if issues:
                notes = "\n".join(f"- {issue}" for issue in issues[:5])
                full_doc += f"\n\n<hr><p><strong>⚠️ 一致性检查提醒</strong></p><ul>{notes}</ul>"
        except Exception:
            pass

    return full_doc
```

- [ ] **步骤 6：修改 imitate() 使用流水线**

在 `ai_service.py` 的 `imitate()` 方法中，在 Step 1 之后添加判断：

```python
# 在原有 imitate() 方法的开始处，判断是否启用流水线模式
# 条件：requirements 长度 > 200 或 包含"分节"关键字
use_pipeline = len(requirements) > 200 or "分节" in requirements or "大纲" in requirements

if use_pipeline:
    outline = await self._generate_outline(requirements, model, project_id)
    if outline and len(outline) >= 3:
        sections_html = await self._generate_sections(
            outline, model, requirements, project_id, template_content
        )
        response = await self._merge_document(outline, sections_html)
        # 跳过原有的 RAG + 生成 + 自检步骤，直接到 Step 7（标注）
        # 但在标注前需要先赋值 response
```

注意：这个改动需要小心整合到现有的 `imitate()` 方法中。推荐做法是将现有 `imitate()` 中 Step 1-5 包裹在一个条件分支中：

```python
# 在 imitate() 中原有 Step 1 的位置：
use_pipeline = len(requirements) > 200 or "分节" in requirements

if use_pipeline:
    # 流水线模式
    outline = await self._generate_outline(requirements, model, project_id)
    if outline and len(outline) >= 3:
        sections_html = await self._generate_sections(outline, model, requirements, project_id, template_content)
        response = await self._merge_document(outline, sections_html)
    else:
        use_pipeline = False  # 大纲生成失败，回退

if not use_pipeline:
    # 原有的 Step 1-5 代码...
    pass
```

- [ ] **步骤 7：运行测试验证通过**

- [ ] **步骤 8：Commit**

```bash
git add api/ai_service.py tests/test_ai_service.py
git commit -m "feat: add long document pipeline (outline → sections → merge)"
```

---

### 任务 4：后端 — RAG 查询改写 + PRD 自检增强

**文件：**
- 修改：`api/kb_project.py`（+_rewrite_query 在 search 中）
- 修改：`api/prd_self_check.py`（+ai_check +check_consistency）
- 测试：`tests/test_ai_service.py`（+test_query_rewriting +test_ai_check）

- [ ] **步骤 1：编写失败的测试**

```python
def test_query_rewriting():
    from api.kb_project import KBProject
    import tempfile
    tmp = tempfile.mkdtemp()
    try:
        proj = KBProject(tmp)
        rewritten = proj._rewrite_query("做一个春节签到活动，持续7天")
        # 应该提取核心词
        assert "签到" in rewritten or "春节" in rewritten or "活动" in rewritten
        # 应该去掉语气词
        assert "做一个" not in rewritten
    finally:
        import shutil
        shutil.rmtree(tmp)

@pytest.mark.asyncio
async def test_check_consistency():
    from api.prd_self_check import PRDSelfCheck
    import tempfile
    tmp = tempfile.mkdtemp()
    try:
        checker = PRDSelfCheck(tmp)
        # 内容有矛盾："不限次数" vs "每日限购1次"
        content = "<h2>规则</h2><p>本活动不限参与次数</p><h2>限制</h2><p>每日限购1次</p>"
        issues = checker.check_consistency(content)
        assert len(issues) > 0
        assert any("限" in issue for issue in issues)
    finally:
        import shutil
        shutil.rmtree(tmp)
```

- [ ] **步骤 2：运行测试验证失败**

- [ ] **步骤 3：实现 KBProject._rewrite_query**

```python
def _rewrite_query(self, query: str) -> str:
    """将用户需求改写为更好的搜索查询。
    规则改写：去语气词 + 提取核心名词短语。
    """
    import re
    # 1. 去掉常见语气词和指令前缀
    cleaned = re.sub(
        r'^(请|帮我|做一个|设计一个|写一个|生成一个|需要|我要|我想)',
        '', query.strip()
    )
    # 2. 去掉句末语气词
    cleaned = re.sub(r'[。！？，、；：]', ' ', cleaned)
    # 3. 保留中英文、数字
    cleaned = re.sub(r'[^\w一-鿿\s]', ' ', cleaned)
    # 4. 去掉单字
    tokens = [w for w in cleaned.split() if len(w) >= 2]
    # 5. 如果太短，用原文
    if len(' '.join(tokens)) < 4:
        return query
    return ' '.join(tokens)
```

同时在 `search()` 方法开头添加调用：

```python
def search(self, query: str, top_k: int = 5, folder_id: str = None) -> List[Dict]:
    query = self._rewrite_query(query)  # ← 新增
    # 原有代码保持不变...
```

- [ ] **步骤 4：实现 PRDSelfCheck.check_consistency + ai_check**

```python
def check_consistency(self, content: str) -> list:
    """轻量级规则一致性检查（不调 AI）。
    返回问题列表。
    """
    import re
    issues = []

    # 1. 检查矛盾关键词组合
    contradiction_pairs = [
        (r'不限次数', r'限.*次'),
        (r'永久', r'限时'),
        (r'免费', r'付费'),
        (r'所有玩家', r'仅.*VIP|仅.*会员'),
    ]
    for pos_pattern, neg_pattern in contradiction_pairs:
        if re.search(pos_pattern, content) and re.search(neg_pattern, content):
            pos_match = re.search(pos_pattern, content)
            neg_match = re.search(neg_pattern, content)
            # 检查它们是否在合理的上下文中共存
            # 如果不是"免费玩家"和"付费玩家"这种合理并列
            issues.append(f"可能存在矛盾: 「{pos_pattern}」和「{neg_pattern}」同时出现")

    # 2. 检查模糊词
    fuzzy_terms = ['若干', '适量', '一些', '大概', '可能', '左右', '适当']
    for term in fuzzy_terms:
        if term in content:
            issues.append(f"存在不明确表述: 「{term}」")

    # 3. 检查缺失结束时间
    if any(word in content for word in ['活动', '签到', '限时']):
        if not re.search(r'结束|截止|到期|持续时间?|下线', content):
            issues.append("活动类文档缺少结束时间/持续时间说明")

    return issues

async def ai_check(self, model: str, content: str) -> dict:
    """调 AI 做深度逻辑审查。"""
    prompt = f"""你是一名资深游戏策划架构师，请对以下 PRD 文档进行逻辑审查。

检查以下问题：
1. 规则内部矛盾（如"不限次数"和"每日限购1次"冲突）
2. 跨节冲突（规则节和奖励节的数值/条件不一致）
3. 边界遗漏（活动没写结束时间、数值没写上限）
4. 不明确表述（"适量""若干""可能"等模糊词）

文档内容：
{content[:4000]}

按以下 JSON 格式输出检查结果：
{{"issues": [{{"type": "contradiction|missing|ambiguity", "description": "...", "severity": "high|medium|low"}}]}}

如果没有问题，输出：{{"issues": []}}
"""
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": "你是严谨的游戏策划审核专家，只输出JSON。"},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 1024,
                },
                headers={"Authorization": "Bearer ..."},  # 从配置获取
                timeout=60,
            )
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            import json as _json
            result = _json.loads(text)
            return result
    except Exception:
        return {"issues": []}

    # 简化版（不强依赖 DeepSeek API）:
    return {"issues": []}  # 如果 API 不可用，静默跳过
```

注意：ai_check 中的 API key 需要从配置获取。简化实现中，可以先做规则检查（check_consistency），AI 检查作为可选增强。

- [ ] **步骤 5：运行测试验证通过**

- [ ] **步骤 6：Commit**

```bash
git add api/kb_project.py api/prd_self_check.py tests/test_ai_service.py
git commit -m "feat: add query rewriting and PRD self-check enhancement"
```

---

### 任务 5：前端 — doc-sections.ts 章节解析工具 + 测试

**文件：**
- 创建：`src/utils/doc-sections.ts`
- 测试：`src/utils/doc-sections.test.ts`

- [ ] **步骤 1：编写失败的测试**

```typescript
// src/utils/doc-sections.test.ts
import { describe, it, expect } from 'vitest'
import { parseHtmlSections } from './doc-sections'

describe('parseHtmlSections', () => {
  it('空文档返回空数组', () => {
    expect(parseHtmlSections('')).toEqual([])
  })

  it('解析 h2/h3 章节', () => {
    const html = '<h2>背景</h2><p>内容</p><h2>规则</h2><p>规则内容</p><h3>子规则</h3><p>细节</p>'
    const sections = parseHtmlSections(html)
    expect(sections).toHaveLength(3)
    expect(sections[0].title).toBe('背景')
    expect(sections[1].title).toBe('规则')
    expect(sections[2].title).toBe('子规则')
  })

  it('无标题返回空数组', () => {
    expect(parseHtmlSections('<p>纯文本</p>')).toEqual([])
  })
})
```

- [ ] **步骤 2：运行测试验证失败**

运行：`npx vitest run src/utils/doc-sections.test.ts`
预期：FAIL（文件未找到）

- [ ] **步骤 3：实现 parseHtmlSections**

```typescript
// src/utils/doc-sections.ts
export interface DocSection {
  title: string
  level: number
  contentHtml: string
  contentText: string
}

/**
 * 将 HTML 文档按 h2/h3 标题解析为章节列表。
 */
export function parseHtmlSections(html: string): DocSection[] {
  if (!html) return []
  const pattern = /<h([23])(?:\s+[^>]*)?>(.*?)<\/h\1>/gi
  const matches: { level: number; title: string; start: number; end: number }[] = []
  let match
  while ((match = pattern.exec(html)) !== null) {
    const title = match[2].replace(/<[^>]+>/g, '').trim()
    matches.push({
      level: parseInt(match[1]),
      title,
      start: match.index + match[0].length,
      end: match.index + match[0].length,
    })
  }
  if (matches.length === 0) return []
  // 设置每个章节的结束位置（到下一个标题或文档末尾）
  for (let i = 0; i < matches.length; i++) {
    if (i + 1 < matches.length) {
      matches[i].end = matches[i + 1].start
    } else {
      matches[i].end = html.length
    }
  }
  return matches.map(m => {
    const contentHtml = html.slice(m.start, m.end).trim()
    return {
      title: m.title,
      level: m.level,
      contentHtml,
      contentText: contentHtml.replace(/<[^>]+>/g, '').trim(),
    }
  })
}

/**
 * 在 TipTap 编辑器中替换指定章节内容。
 * editor: TipTap Editor 实例
 * section: 要替换的章节
 * newHtml: 新内容（纯 HTML，不含标题）
 */
export function replaceSectionInEditor(editor: any, section: DocSection, newHtml: string): void {
  // ProseMirror 中查找 h2/h3 标题节点
  let found = false
  editor.state.doc.forEach((node: any, offset: number) => {
    if (found) return false
    if (node.type.name === 'heading' && node.textContent.trim() === section.title) {
      found = true
      // 找到下一章节或文档末尾作为结束位置
      let endPos = offset + node.nodeSize
      let nextFound = false
      editor.state.doc.forEach((n: any, pos: number) => {
        if (nextFound) return false
        if (pos > offset && n.type.name === 'heading' && (n.attrs.level === 2 || n.attrs.level === 3)) {
          endPos = pos
          nextFound = true
          return false
        }
        return true
      })
      // 替换整个章节范围（标题 + 内容）
      editor.chain().focus().deleteRange({ from: offset, to: endPos }).insertContentAt(offset, `<h2>${section.title}</h2>${newHtml}`).run()
    }
  })
}

/**
 * 获取光标所在的当前章节。
 */
export function getCurrentSection(editor: any, sections: DocSection[], html: string): DocSection | null {
  if (!editor || sections.length === 0) return null
  const { from } = editor.state.selection
  let currentSection: DocSection | null = null
  editor.state.doc.forEach((node: any, pos: number) => {
    if (node.type.name === 'heading' && (node.attrs.level === 2 || node.attrs.level === 3)) {
      const s = sections.find(s => s.title === node.textContent.trim())
      if (s && pos <= from) {
        currentSection = s
      }
    }
  })
  return currentSection
}
```

- [ ] **步骤 4：运行测试验证通过**

运行：`npx vitest run src/utils/doc-sections.test.ts`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add src/utils/doc-sections.ts src/utils/doc-sections.test.ts
git commit -m "feat: add doc section parsing utility"
```

---

### 任务 6：前端 — useAI.ts 扩展

**文件：**
- 修改：`src/composables/useAI.ts`

- [ ] **步骤 1：添加迭代方法和状态**

```typescript
// 在 useAI() 函数中添加：

// 迭代历史
const iterationHistory = ref<{
  instruction: string
  targetSection: string
  replacement: string
  timestamp: number
}[]>([])

// 对话面板状态
const showIterationPanel = ref(false)
const iterationInput = ref('')
const isIterating = ref(false)

// 运行迭代修改
const runIteration = async (
  fullDoc: string,
  instruction: string,
  mode: 'section' | 'selection' | 'full' = 'section',
  targetSection?: string,
  selectionContext?: { selected: string; before: string; after: string },
  projectId?: string
): Promise<string | null> => {
  isIterating.value = true
  try {
    const r = await axios.post(apiUrl('/api/ai/imitate-iterate'), {
      model: activeModel.value,
      full_doc: fullDoc,
      instruction,
      mode,
      target_section: targetSection || '',
      selection_context: selectionContext || null,
      project_id: projectId || undefined,
    })
    if (r.data.success && r.data.data?.replacement) {
      iterationHistory.value.push({
        instruction,
        targetSection: targetSection || '',
        replacement: r.data.data.replacement,
        timestamp: Date.now(),
      })
      return r.data.data.replacement
    }
    return null
  } catch (e: any) {
    console.error('迭代修改失败:', e)
    return null
  } finally {
    isIterating.value = false
  }
}
```

- [ ] **步骤 2：在 return 中添加新暴露的属性**

```typescript
return {
  activeModel, models, aiResult, isProcessing,
  iterativePrompt,
  runQualityCheck, runImitation, runLogicCompletion, iterate, generateDocTitle,
  // 新增:
  runIteration, iterationHistory,
  showIterationPanel, iterationInput, isIterating,
}
```

- [ ] **步骤 3：Commit**

```bash
git add src/composables/useAI.ts
git commit -m "feat: add runIteration and iterationHistory to useAI"
```

---

### 任务 7：前端 — AIIteration TipTap 扩展

**文件：**
- 创建：`src/extensions/AIIteration.ts`

- [ ] **步骤 1：实现 TipTap 扩展**

```typescript
// src/extensions/AIIteration.ts
import { Extension } from '@tiptap/core'
import { Plugin, PluginKey } from '@tiptap/pm/state'

export interface AIExtensionOptions {
  onModifySection: (title: string) => void
}

/**
 * AI 迭代修改的 TipTap 扩展。
 * 提供 commands: aiModifySection, aiModifySelection
 * 并在每个 h2/h3 标题旁注入修改按钮。
 */
export const AIExtension = Extension.create<AIExtensionOptions>({
  name: 'aiIteration',

  addOptions() {
    return {
      onModifySection: () => {},
    }
  },

  addCommands() {
    return {
      aiModifySection:
        (title: string) =>
        ({ editor }: any) => {
          this.options.onModifySection(title)
          return true
        },
      aiModifySelection:
        () =>
        ({ editor }: any) => {
          const { from, to } = editor.state.selection
          if (from === to) return false
          const selected = editor.state.doc.textBetween(from, to)
          const before = editor.state.doc.textBetween(Math.max(0, from - 200), from)
          const after = editor.state.doc.textBetween(to, Math.min(editor.state.doc.content.size, to + 200))
          // 触发自定义事件
          window.dispatchEvent(new CustomEvent('ai-modify-selection', {
            detail: { selected, before, after },
          }))
          return true
        },
    }
  },

  // 添加 ProseMirror Plugin 用于检测选区变化
  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: new PluginKey('aiIteration'),
        props: {
          handleClickOn: (view: any, pos: number, node: any) => {
            // 点击标题时不做特殊处理（由 NodeView 渲染按钮）
            return false
          },
        },
      }),
    ]
  },
})
```

- [ ] **步骤 2：Commit**

```bash
git add src/extensions/AIIteration.ts
git commit -m "feat: add AI iteration TipTap extension"
```

---

### 任务 8：前端 — AIIterationPanel 对话面板

**文件：**
- 创建：`src/components/panels/AIIterationPanel.vue`

- [ ] **步骤 1：实现组件**

```vue
<script setup lang="ts">
import { ref, watch } from 'vue'
import type { DocSection } from '@/utils/doc-sections'

const props = defineProps<{
  visible: boolean
  currentSection: DocSection | null
  history: { instruction: string; targetSection: string; timestamp: number }[]
  isIterating: boolean
}>()

const emit = defineEmits<{
  submit: [instruction: string]
  close: []
}>()

const inputText = ref('')

const handleSubmit = () => {
  if (!inputText.value.trim() || props.isIterating) return
  emit('submit', inputText.value.trim())
  inputText.value = ''
}

const formatTime = (ts: number) => {
  const d = new Date(ts)
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}
</script>

<template>
  <div v-if="visible" class="border-t border-app bg-surface">
    <div class="flex items-center justify-between px-3 py-2">
      <span class="text-xs font-bold text-app-muted uppercase tracking-wider">AI 对话</span>
      <button class="text-xs text-app-muted hover:text-app" @click="emit('close')">关闭</button>
    </div>

    <div class="h-48 overflow-y-auto px-3 space-y-2" v-if="history.length > 0">
      <div v-for="(item, i) in history" :key="i" class="text-xs">
        <div class="flex items-start gap-1">
          <span class="text-purple-600 font-medium shrink-0">你:</span>
          <span class="text-app">{{ item.instruction }}</span>
        </div>
        <div class="flex items-start gap-1 mt-0.5">
          <span class="text-green-600 font-medium shrink-0">AI:</span>
          <span class="text-app-muted">
            已修改「{{ item.targetSection || '文档' }}」
            <span class="text-[10px] text-zinc-300">{{ formatTime(item.timestamp) }}</span>
          </span>
        </div>
      </div>
    </div>
    <div v-else class="h-48 flex items-center justify-center text-xs text-app-muted px-3">
      在文档中选中章节或文字，然后输入修改指令
    </div>

    <div class="p-3 border-t border-app-light flex gap-2">
      <el-input
        v-model="inputText"
        :placeholder="currentSection ? `修改「${currentSection.title}」...` : '输入修改指令...'"
        size="small"
        @keyup.enter="handleSubmit"
        :disabled="isIterating"
      />
      <el-button
        size="small"
        type="primary"
        @click="handleSubmit"
        :loading="isIterating"
        :disabled="!inputText.trim()"
      >发送</el-button>
    </div>

    <div v-if="currentSection" class="px-3 pb-2">
      <span class="text-[10px] text-app-muted">当前章节: {{ currentSection.title }}</span>
    </div>
  </div>
</template>
```

- [ ] **步骤 2：Commit**

```bash
git add src/components/panels/AIIterationPanel.vue
git commit -m "feat: add AI iteration panel component"
```

---

### 任务 9：前端 — SettingsDialog 项目画像标签页

**文件：**
- 修改：`src/components/dialogs/SettingsDialog.vue`
- 修改：`src/types/index.ts`（+ProjectProfile 接口）

- [ ] **步骤 1：添加 ProjectProfile 类型**

```typescript
// src/types/index.ts 中添加：
export interface ProjectProfile {
  game_name: string
  genre: string
  world_setting: string
  target_audience: string
  terminology: Record<string, string>
  template_sections: string[]
  design_principles: string[]
}
```

- [ ] **步骤 2：实现项目画像标签页**

在 `SettingsDialog.vue` 的 `<script>` 中添加：

```typescript
// 项目画像
const profile = ref<ProjectProfile>({
  game_name: '', genre: '', world_setting: '', target_audience: '',
  terminology: {}, template_sections: ['背景', '目标', '规则', '奖励', '限制', 'UI'],
  design_principles: [],
})
const profileLoading = ref(false)
const profileSaving = ref(false)
const newTermKey = ref('')
const newTermVal = ref('')
const newPrinciple = ref('')

const loadProfile = async () => {
  profileLoading.value = true
  try {
    const r = await axios.get(apiUrl('/api/project-profile'))
    if (r.data.success && r.data.data) profile.value = r.data.data
  } catch { /* */ }
  finally { profileLoading.value = false }
}

const saveProfile = async () => {
  profileSaving.value = true
  try {
    await axios.put(apiUrl('/api/project-profile'), profile.value)
    ElMessage.success('项目画像已保存')
  } catch { ElMessage.error('保存失败') }
  finally { profileSaving.value = false }
}

const addTerm = () => {
  if (!newTermKey.value.trim() || !newTermVal.value.trim()) return
  profile.value.terminology[newTermKey.value.trim()] = newTermVal.value.trim()
  newTermKey.value = ''; newTermVal.value = ''
}

const removeTerm = (key: string) => { delete profile.value.terminology[key] }

const addPrinciple = () => {
  if (!newPrinciple.value.trim()) return
  profile.value.design_principles.push(newPrinciple.value.trim())
  newPrinciple.value = ''
}

const removePrinciple = (idx: number) => { profile.value.design_principles.splice(idx, 1) }

// 对话框打开时加载
watch(visible, (v) => { if (v) loadProfile() })
```

在 `<template>` 中添加 `<el-tab-pane label="项目画像">` (在 "职业角色" 之后)：

```vue
<el-tab-pane label="项目画像">
  <div class="py-4 space-y-4 max-h-[400px] overflow-y-auto pr-2">
    <p class="text-xs text-app-muted mb-2">填写项目基本信息，AI 仿写时将自动遵守项目设定和术语。</p>

    <div class="grid grid-cols-2 gap-3">
      <div>
        <label class="text-xs text-app-secondary block mb-1">游戏名称</label>
        <el-input v-model="profile.game_name" size="small" placeholder="例如：梦幻西游" />
      </div>
      <div>
        <label class="text-xs text-app-secondary block mb-1">游戏类型</label>
        <el-select v-model="profile.genre" size="small" class="w-full">
          <el-option label="MMORPG" value="MMORPG" />
          <el-option label="卡牌" value="卡牌" />
          <el-option label="SLG" value="SLG" />
          <el-option label="ACT" value="ACT" />
          <el-option label="休闲" value="休闲" />
          <el-option label="其他" value="其他" />
        </el-select>
      </div>
    </div>
    <div>
      <label class="text-xs text-app-secondary block mb-1">世界观设定</label>
      <el-input v-model="profile.world_setting" size="small" placeholder="例如：东方玄幻，仙侠世界" />
    </div>
    <div>
      <label class="text-xs text-app-secondary block mb-1">目标用户</label>
      <el-input v-model="profile.target_audience" size="small" placeholder="例如：18-35岁男性玩家" />
    </div>

    <div>
      <label class="text-xs text-app-secondary block mb-1">术语映射</label>
      <div class="space-y-1">
        <div v-for="(v, k) in profile.terminology" :key="k" class="flex items-center gap-2 text-xs">
          <span class="font-mono bg-app-hover px-1 rounded">{{ k }}</span>
          <span>→</span>
          <span class="text-green-600">{{ v }}</span>
          <el-button link size="small" type="danger" @click="removeTerm(k)">删除</el-button>
        </div>
      </div>
      <div class="flex gap-1 mt-1">
        <el-input v-model="newTermKey" size="small" placeholder="原文（如 HP）" class="!w-28" />
        <el-input v-model="newTermVal" size="small" placeholder="映射（如 气血）" class="!w-28" />
        <el-button size="small" @click="addTerm" :disabled="!newTermKey.trim() || !newTermVal.trim()">添加</el-button>
      </div>
    </div>

    <div>
      <label class="text-xs text-app-secondary block mb-1">设计原则</label>
      <div class="space-y-1">
        <div v-for="(p, i) in profile.design_principles" :key="i" class="flex items-center gap-2 text-xs">
          <span class="text-green-600">•</span>
          <span>{{ p }}</span>
          <el-button link size="small" type="danger" @click="removePrinciple(i)">删除</el-button>
        </div>
      </div>
      <div class="flex gap-1 mt-1">
        <el-input v-model="newPrinciple" size="small" placeholder="例如：所有数值必须可配置" @keyup.enter="addPrinciple" />
        <el-button size="small" @click="addPrinciple" :disabled="!newPrinciple.trim()">添加</el-button>
      </div>
    </div>

    <div class="flex justify-end">
      <el-button type="primary" :loading="profileSaving" @click="saveProfile">保存画像</el-button>
    </div>
  </div>
</el-tab-pane>
```

- [ ] **步骤 3：Commit**

```bash
git add src/components/dialogs/SettingsDialog.vue src/types/index.ts
git commit -m "feat: add project profile tab to settings"
```

---

### 任务 10：前端 — HomePage.vue 集成

**文件：**
- 修改：`src/pages/HomePage.vue`

- [ ] **步骤 1：注册新的 TipTap 扩展**

在 `tiptapEditor = useEditor({...})` 的 extensions 数组中添加：

```typescript
import { AIExtension } from '@/extensions/AIIteration'

// ... 在 extensions 数组中添加:
AIExtension.configure({
  onModifySection: (title: string) => {
    showAIInput.value = true
    aiTargetSection.value = title
  },
}),
```

- [ ] **步骤 2：添加 AI 工具栏按钮**

在第 2 个工具栏区域（第 942-959 行）的末尾、`</div>` 之前添加：

```html
<div class="w-px h-5 bg-app-hover mx-1" />
<button
  class="p-1.5 rounded hover:bg-app-hover text-purple-600"
  :class="{ 'bg-purple-100': showIterationPanel }"
  @click="showIterationPanel = !showIterationPanel"
  title="AI 修改"
>
  <Sparkles class="w-4 h-4" />
</button>
<button
  class="px-2 py-1 rounded hover:bg-app-hover text-xs text-purple-600"
  @click="handleAIExpand"
  :disabled="!hasSelection"
  title="扩写选中内容"
>
  扩写
</button>
<button
  class="px-2 py-1 rounded hover:bg-app-hover text-xs text-purple-600"
  @click="handleAIShorten"
  :disabled="!hasSelection"
  title="缩写选中内容"
>
  缩写
</button>
```

- [ ] **步骤 3：添加迭代相关状态和方法**

在 `<script>` 中添加状态变量：

```typescript
const showIterationPanel = ref(false)
const aiTargetSection = ref('')
const showAIInput = ref(false)
const aiInstruction = ref('')
const hasSelection = ref(false)

// 监听选区变化
watch(() => tiptapEditor.value?.state.selection, () => {
  if (!tiptapEditor.value) return
  const { from, to } = tiptapEditor.value.state.selection
  hasSelection.value = from !== to
}, { deep: true })

// 处理 AI 修改请求
const handleAIModify = async (instruction: string) => {
  if (!tiptapEditor.value || !instruction.trim()) return
  const fullDoc = tiptapEditor.value.getHTML()
  const { from, to } = tiptapEditor.value.state.selection
  const isSelection = from !== to

  let mode: 'section' | 'selection' | 'full' = 'full'
  let targetSection = ''
  let selectionContext = undefined

  if (isSelection) {
    mode = 'selection'
    const selected = tiptapEditor.value.state.doc.textBetween(from, to)
    const before = tiptapEditor.value.state.doc.textBetween(Math.max(0, from - 200), from)
    const after = tiptapEditor.value.state.doc.textBetween(to, Math.min(tiptapEditor.value.state.doc.content.size, to + 200))
    selectionContext = { selected, before, after }
  } else if (aiTargetSection.value) {
    mode = 'section'
    targetSection = aiTargetSection.value
  }

  const result = await ai.runIteration(fullDoc, instruction, mode, targetSection, selectionContext, kb.activeProjectId.value)
  if (result) {
    if (mode === 'selection' && selectionContext) {
      // 替换选中内容
      tiptapEditor.value.chain().focus().deleteSelection().insertContent(result).run()
    } else if (mode === 'section' && targetSection) {
      // 替换整节
      const { parseHtmlSections, replaceSectionInEditor } = await import('@/utils/doc-sections')
      const sections = parseHtmlSections(fullDoc)
      const sec = sections.find(s => s.title === targetSection)
      if (sec) replaceSectionInEditor(tiptapEditor.value, sec, result)
    } else {
      // 全文替换
      tiptapEditor.value.commands.setContent(result)
    }
    ElMessage.success('修改完成')
  } else {
    ElMessage.warning('修改失败，请重试')
  }
  aiTargetSection.value = ''
  showAIInput.value = false
}

// 预设指令
const handleAIExpand = () => handleAIModify('扩写这段内容')
const handleAIShorten = () => handleAIModify('缩写这段内容')
```

- [ ] **步骤 4：在底部挂载对话面板**

在模板末尾、`</template>` 之前，挂载对话面板：

```vue
<AIIterationPanel
  :visible="showIterationPanel"
  :current-section="currentDocSection"
  :history="ai.iterationHistory.value"
  :is-iterating="ai.isIterating.value"
  @submit="handleAIModify"
  @close="showIterationPanel = false"
/>
```

- [ ] **步骤 5：在右侧面板中集成对话面板**

将现有的 AI 执行结果区域（第 1094-1112 行）替换为包含折叠面板的布局。或者直接将对话面板放在右侧面板底部（在"AI 执行结果"后面）。

- [ ] **步骤 6：Commit**

```bash
git add src/pages/HomePage.vue
git commit -m "feat: integrate AI iteration into editor"
```

---

### 任务 11：构建 + 测试验证

**文件：**
- 不需要修改代码

- [ ] **步骤 1：运行所有 Python 测试**

运行：`.venv\Scripts\python.exe -m pytest tests/ -v`
预期：原有 35 个测试 + 新增测试全部 PASS

- [ ] **步骤 2：运行所有前端测试**

运行：`npx vitest run`
预期：所有测试 PASS

- [ ] **步骤 3：TypeScript 类型检查**

运行：`npx vue-tsc -b`
预期：无类型错误

- [ ] **步骤 4：Vite 构建**

运行：`npx vite build`
预期：构建成功

- [ ] **步骤 5：完整 electron-builder 构建**

运行：`npm run build`
预期：构建成功，输出到 release 目录
