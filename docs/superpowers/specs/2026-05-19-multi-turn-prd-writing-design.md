# 多轮对话式 PRD 写作 + 全链路优化设计

## 目标

将 AI 仿写从"一次性生成"升级为完整写作工作流：多轮迭代 + 超长文档流水线 + 项目画像 + RAG 增强 + PRD 自检增强。

## 架构概览

```
ImitateDialog (需求输入) → 生成流水线 → 完整 PRD → TipTap 编辑器中打开
                              ├─ 大纲生成
                              ├─ 逐节生成（并行）
                              ├─ 合并 + 一致性检查
                              └─ 项目画像注入

用户迭代修改 → imitate-iterate() → 局部替换
                ├─ section 模式（整节）
                ├─ selection 模式（选中）
                └─ full 模式（全文）

生成和迭代全流程：
  ├─ RAG 检索增强（查询改写 + 重排序）
  ├─ 项目画像约束（术语/风格/原则注入）
  └─ PRD 自检（结构检查 + AI 逻辑检查 + 画像对齐）
```

---

## 1. 多轮对话式迭代（原设计保留）

### 端点: POST /api/ai/imitate-iterate

**请求参数:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `full_doc` | string | 是 | 当前完整文档 HTML |
| `instruction` | string | 是 | 用户修改指令 |
| `mode` | string | 是 | `"section"` / `"selection"` / `"full"` |
| `target_section` | string | 否 | 目标章节标题（mode=section 时必填） |
| `selection_context` | object | 否 | `{selected, before, after}`（mode=selection 时必填） |
| `model` | string | 否 | 默认为当前活跃模型 |
| `project_id` | string | 否 | 用于 RAG 检索 |
| `template_content` | string | 否 | 文档模板参考 |

**返回:**

```json
{
  "success": true,
  "data": {
    "replacement": "<替换后的 HTML 内容>",
    "section_title": "目标章节标题",
    "mode": "section"
  }
}
```

### AIService.imitate_iterate()

**流程:**

1. **解析文档结构** — 将 full_doc 按 `<h2>` `<h3>` 标题解析为章节列表
2. **定位目标** — 根据 mode 确定要修改的内容范围
3. **构建修订 Prompt**:
   - System: "你是资深游戏策划，正在修订一份 PRD 文档。你只输出修改后的目标内容，不输出其他内容。保持格式一致。"
   - 注入项目画像约束（如果已配置）
   - User prompt: 目标节原文 + 前后节摘要 + 修改指令 + RAG 上下文(如有)
4. **调用 AI** — `_call_api()`，temperature=0.3
5. **返回替换内容** — 空/异常长时返回错误

**章节解析:**
```python
import re
pattern = r'<h([23])(?:\s+[^>]*)?>(.*?)</h\1>'
# 返回 [{title, level, content_html, content_text}, ...]
```

**上下文摘要:** 前后各一节，仅传标题和纯文本前 100 字。

---

## 2. 超长文档生成流水线（大纲→分节→合并）

### 改进 imitate() 方法

当前 `imitate()` 是一次生成。改为流水线模式：

```
用户需求 → 判断复杂度（字数 > 200 或 明确要求分节）
           ├─ 简单 → 原有一次生成路径（保持兼容）
           └─ 复杂 → 流水线模式
```

### 流水线步骤

**Step 1: 生成大纲**

```python
async def _generate_outline(self, requirements: str, project_id: str = "") -> List[Dict]:
    """
    调 AI 生成文档大纲。
    返回: [{title: "活动规则", description: "签到规则和参与条件"}, ...]
    """
    prompt = f"""你是一名资深游戏策划架构师。请为用户需求规划 PRD 文档大纲。

需求：{requirements}

要求：
- 输出 4-8 个章节
- 每个章节给出标题和一句话说明
- 标准章节参考：背景/目标、规则/流程、奖励/数值、限制/条件、UI/交互

请输出 JSON 格式：{{"sections": [{{"title": "章节标题", "desc": "说明"}}]}}
"""
    # 调 AI → 解析 JSON
```

**Step 2: 逐节生成（可并行）**

```python
async def _generate_sections(self, outline: List[Dict], requirements: str,
                              project_id: str = "", template_content: str = "") -> List[str]:
    """
    为每节独立生成内容。
    每节注入该节相关的 RAG 上下文 + 项目画像约束。
    各节可并行调用 AI。
    """
    sections_html = []
    for sec in outline:
        # 为该节做定向 RAG 检索
        rag = self._rag_for_section(sec["title"], requirements, project_id)

        prompt = f"...使用 {sec['title']} 相关的知识库内容..."
        # + 项目画像约束
        # + 模板格式参考

        html = await self._call_api(model, messages)
        sections_html.append(html)
    return sections_html
```

**Step 3: 合并**

```python
async def _merge_document(self, outline: List[Dict], sections_html: List[str]) -> str:
    """
    拼接为完整文档。每节加 <h2> 标题。
    如果启用了自检，进行一次全文档一致性检查。
    """
    parts = []
    for sec, html in zip(outline, sections_html):
        parts.append(f"<h2>{sec['title']}</h2>\n{html}")
    full_doc = "\n".join(parts)

    # 一致性检查（调用 PRD 自检增强模块）
    if self.checker:
        issues = await self.checker.check_consistency(full_doc)
        # 如果有问题，在文档末尾加备注

    return full_doc
```

### 与多轮迭代的衔接

生成时就是分节的，每节有 `<h2>` 边界，后续 iterate 直接定位到对应节。

---

## 3. 项目画像

### 数据模型

```json
{
  "game_name": "我的游戏",
  "genre": "MMORPG",
  "world_setting": "东方玄幻",
  "target_audience": "18-35岁",
  "terminology": {
    "HP": "气血",
    "gold": "银两"
  },
  "template_sections": ["背景", "目标", "规则", "奖励", "限制", "UI"],
  "design_principles": [
    "所有数值必须在策划配置表中可调",
    "每个系统必须有产出消耗闭环"
  ]
}
```

### 后端: 新增路由器 api/routers/project_profile.py

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/project-profile` | GET | 获取当前项目画像 |
| `/api/project-profile` | PUT | 更新项目画像 |
| `/api/project-profile` | DELETE | 重置为默认 |

存储在 `data_dir/project_profile.json`。

### Prompt 注入

在 `AIService._call_api()` 或 `imitate()` 中，检测是否有 project_profile：
- 如果有，在 system prompt 末尾追加：

```
【项目画像 - 必须遵守】
项目名称：{game_name}
游戏类型：{genre}
世界观：{world_setting}
目标用户：{target_audience}

术语映射（使用以下术语，不得混用）：
{terminology 表}

设计原则：
{design_principles 列表}
```

### 前端: SettingsDialog 新标签页

在设置对话框新增"项目画像"标签页：

```
┌─────────────────────────┐
│ [基本设置] [模型配置] [项目画像] ← 新标签 │
├─────────────────────────┤
│ 游戏名称: [___________] │
│ 游戏类型: [▼ MMORPG]   │
│ 世界观:   [东方玄幻...] │
│ 目标用户: [18-35岁  ]  │
│                         │
│ 术语映射:               │
│ ┌───────────────────┐   │
│ │ HP → 气血         │   │
│ │ MP → 法力         │   │
│ │ + 添加术语        │   │
│ └───────────────────┘   │
│                         │
│ 设计原则:               │
│ ┌───────────────────┐   │
│ │ 所有数值必须可配  │   │
│ │ 每个系统必须有闭环│   │
│ │ + 添加原则        │   │
│ └───────────────────┘   │
│                         │
│ [保存]                  │
└─────────────────────────┘
```

---

## 4. RAG 检索增强

### 4.1 查询改写（Query Rewriting）

在 `KBProject.search()` 前加改写层：

```python
def _rewrite_query(self, query: str) -> str:
    """将用户需求改写为更好的搜索查询。"""
    # 规则改写（轻量，不调 AI）
    # 1. 去掉语气词和修饰词
    # 2. 提取核心名词短语
    # 3. 补充同义术语

    # 例如:
    # "做一个春节签到活动，持续7天，奖励要有吸引力"
    # → "春节 签到 活动 7天 奖励"
    return rewritten
```

如果规则改写不够，可扩展为用轻量模型改写（后续阶段）。

### 4.2 Cross-encoder 重排序

在 `search()` 的 RRF 融合后增加重排序：

```python
def search(self, query: str, top_k: int = 5) -> List[Dict]:
    # 1. 查询改写
    rewritten = self._rewrite_query(query)

    # 2. 向量 + BM25 混合检索（现有 RRF 逻辑）
    candidates = self._hybrid_search(rewritten, top_k=top_k * 4)

    # 3. Cross-encoder 重排序
    if self._cross_encoder is not None:
        candidates = self._rerank(rewritten, candidates)

    return candidates[:top_k]
```

**注意：** Cross-encoder 需要额外模型（如 `BAAI/bge-reranker-v2-m3`），约 500MB。如果用户环境受限，可以不加，仅用 RRF 也够用。**做成可选配置**，默认关闭。

---

## 5. PRD 自检增强

### 分层自检架构

在 `prd_self_check.py` 中扩展，增加第二层 AI 驱动检查：

**第一层：规则检查（现有，保留）**
- 章节完整性检查
- 字数阈值
- 数值异常检查

**第二层：AI 逻辑一致性检查（新增）**

```python
async def ai_check(self, model: str, content: str, kb_contexts: dict = None) -> dict:
    """调 AI 模型做深度逻辑审查。

    返回: {passed: bool, issues: [{severity, type, description}]}
    """
    prompt = f"""你是一名资深游戏策划架构师，请对以下 PRD 文档进行逻辑审查。

请检查：
1. 规则内部矛盾（如"不限次数"和"每日限购1次"冲突）
2. 跨节冲突（规则节和奖励节的数值/条件不一致）
3. 边界遗漏（活动没写结束时间、数值没写上限）
4. 不明确表述（"适量""若干""可能"等模糊词）

文档内容：
{content[:4000]}

按以下 JSON 格式输出检查结果：
{{"issues": [{{"type": "contradiction|missing|ambiguity", "description": "...", "severity": "high|medium|low"}}]}}
"""
    result = await self._lightweight_check(model, prompt)
    return result
```

**第三层：画像对齐检查（依赖项目画像）**
- 检查术语是否与项目画像一致
- 如画像是"气血"但文档用了"HP"，标注提示

### 自检触发时机

- 首次生成后（已有逻辑，增强 AI 检查）
- 每次 iterate 修改后（新增：增量检查被修改的节）
- 用户可以手动触发"自检"按钮

---

## 前端改动汇总

| 改动 | 文件 | 说明 |
|------|------|------|
| 章节解析工具 | `src/utils/doc-sections.ts` | ProseMirror 章节解析 + 替换 |
| TipTap 扩展 | `src/extensions/AIIteration.ts` | 节操作按钮 + AI 命令 |
| 对话面板 | `src/components/panels/AIIterationPanel.vue` | 右侧折叠面板 |
| useAI 扩展 | `src/composables/useAI.ts` | runIteration + 对话历史 |
| HomePage 集成 | `src/pages/HomePage.vue` | 面板挂载 + 入口绑定 |
| Settings 新标签页 | `src/components/dialogs/SettingsDialog.vue` | 项目画像标签页 |

## 测试策略

### 后端测试（新增）

- `test_parse_sections` — 章节解析：空文档/纯文本/多级标题
- `test_imitate_iterate_section` — 迭代：修改整节
- `test_imitate_iterate_selection` — 迭代：修改选中文字
- `test_generate_outline` — 大纲生成
- `test_generate_sections` — 逐节生成
- `test_merge_document` — 合并 + 一致性检查
- `test_project_profile_crud` — 画像 CRUD
- `test_query_rewriting` — 查询改写
- `test_ai_self_check` — AI 逻辑检查
- `test_ai_check_consistency` — 跨节一致性

### 前端测试（新增）

- `test_parse_doc_sections` — 章节解析
- `test_get_current_section` — 光标 → 章节
- `test_replace_section` — 替换后内容正确
- `test_ai_iteration_api` — 迭代请求/响应

## 实施阶段

| 阶段 | 内容 | 涉及文件 | 预计改动量 |
|------|------|---------|-----------|
| **P0** | 多轮迭代后端 + 前端 | `ai_service.py`, `ai.py`, `doc-sections.ts`, `AIIteration.ts`, `AIIterationPanel.vue`, `useAI.ts`, `HomePage.vue` | 大 |
| **P1** | 超长文档流水线 | `ai_service.py` imitate() 方法重构 | 中 |
| **P1** | 项目画像 | `project_profile.py`, `SettingsDialog.vue` | 中 |
| **P2** | RAG 增强 | `kb_project.py` search() 方法增强 | 小 |
| **P2** | PRD 自检增强 | `prd_self_check.py` 新增 ai_check() | 中 |

P0+P1 是本次核心交付。P2 可选，看编译后空间。
