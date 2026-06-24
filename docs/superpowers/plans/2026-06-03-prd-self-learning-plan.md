# PRD 知识锚定生成与自学习系统 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）逐任务实现。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在现有 PRD 智能仿写流程中插入 4 个新模块（知识完整性检查、引用增强生成、一致性检测、知识提炼），使 AI 输出充分锚定知识库内容并可追溯引用，同时将用户确认后的新知识自动回写知识库，形成持续学习闭环。

**架构：** 在 `ai_service.py` 的 `imitate()` 流程中——RAG 检索之后、AI 调用之前注入知识清单和引用规则；AI 返回后先经 PRD 自检、再经一致性检测；用户确认后通过新端点触发知识提炼回写。4 个新模块各自独立成文件，通过明确的 dataclass 接口通信。

**技术栈：** Python 3.10+, FastAPI, pytest, re, dataclasses, typing

---

### 文件结构

| 操作 | 文件 | 职责 |
|---|---|---|
| 新建 | `api/knowledge_checker.py` | 模块①：知识完整性检查器 |
| 新建 | `api/citation_enhancer.py` | 模块②：引用增强生成器 |
| 新建 | `api/consistency_checker.py` | 模块③：语义一致性检测 |
| 新建 | `api/knowledge_extractor.py` | 模块④：知识提炼器 |
| 修改 | `api/prd_self_check.py` | 集成一致性检测 |
| 修改 | `api/ai_service.py` | 仿写流程接入模块①②③ |
| 修改 | `api/routers/ai.py` | 新增 confirm-generation 端点、imitate 返回扩展元数据 |
| 修改 | `src/composables/useAI.ts` | 扩展类型、处理引用/冲突元数据、调用确认端点 |
| 修改 | `src/components/panels/AIIterationPanel.vue` | 显示引用来源、冲突标记、覆盖率 |
| 新建 | `tests/test_knowledge_checker.py` | 知识完整性检查器测试 |
| 新建 | `tests/test_citation_enhancer.py` | 引用增强测试 |
| 新建 | `tests/test_consistency_checker.py` | 一致性检测测试 |
| 新建 | `tests/test_knowledge_extractor.py` | 知识提炼器测试 |

### 依赖关系

```
Task 1 (KnowledgeChecker) ───┐
Task 2 (CitationEnhancer) ───┼──→ Task 5 (PRDSelfCheck集成) ──→ Task 6 (AIService集成)
Task 3 (ConsistencyChecker) ─┘                                    │
Task 4 (KnowledgeExtractor) ───────────────────────────────────────┘
                                                                   │
                                             Task 7 (Router API) ──┘
                                             Task 8 (useAI.ts)
                                             Task 9 (AIIterationPanel.vue)
```

Task 1-4 可并行执行。Task 5-6 依赖 1-3。Task 7 依赖 6。Task 8-9 依赖 7。

---

### 任务 1：知识完整性检查器 (KnowledgeChecker)

**文件：**
- 创建：`api/knowledge_checker.py`
- 测试：`tests/test_knowledge_checker.py`

- [ ] **步骤 1：编写失败的测试**

```python
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
    """查询"装备强化"应返回 existing 中包含数值/系统条目，missing 包含查询中提到但未覆盖的主题。"""
    checker = KnowledgeChecker(kb_with_docs)
    result = checker.check("装备强化系统设计，包含强化消耗和概率")
    assert isinstance(result, KnowledgeCheckResult)
    assert len(result.existing) >= 1  # 至少命中数值或系统
    assert any("强化" in item.topic or "15" in item.content for item in result.existing)
    assert hasattr(result, "coverage_ratio")
    assert 0 <= result.coverage_ratio <= 1


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
        assert result.coverage_ratio == 0.0
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_format_check_result(kb_with_docs):
    """format_check_result 应生成包含"已有设定"和"未覆盖"两个区块的文本。"""
    checker = KnowledgeChecker(kb_with_docs)
    result = checker.check("装备强化")
    text = checker.format_check_result(result)
    assert "已有设定" in text or "知识库" in text
    assert isinstance(text, str)
    assert len(text) > 0
```

- [ ] **步骤 2：运行测试验证失败**

```bash
.venv\Scripts\python.exe -m pytest tests/test_knowledge_checker.py -v
```
预期：FAIL，`ModuleNotFoundError: No module named 'api.knowledge_checker'`

- [ ] **步骤 3：编写实现代码**

```python
"""api/knowledge_checker.py — 知识完整性检查器。"""

import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class KBCoverageItem:
    topic: str
    content: str
    source: str
    similarity: float
    category: str


@dataclass
class MissingTopic:
    topic: str
    suggestion: str


@dataclass
class KnowledgeCheckResult:
    existing: List[KBCoverageItem]
    partial: List[KBCoverageItem]
    missing: List[MissingTopic]
    coverage_ratio: float


class KnowledgeChecker:
    """检查知识库对需求的覆盖程度，输出三层知识清单。"""

    def __init__(self, kb_project):
        self.kb = kb_project
        self.thresholds = {"existing": 0.7, "partial": 0.4}

    def check(self, query: str) -> KnowledgeCheckResult:
        """检索知识库，将结果按相似度阈值分为已有/部分/缺失三层。"""
        if not self.kb:
            return KnowledgeCheckResult(existing=[], partial=[], missing=[], coverage_ratio=0.0)

        try:
            all_results = self.kb.search(query, top_k=10)
        except Exception:
            return KnowledgeCheckResult(existing=[], partial=[], missing=[], coverage_ratio=0.0)

        existing = []
        partial = []
        known_texts = []

        for item in all_results:
            content = item.get("text", "")
            similarity = item.get("score", 0.0)
            meta = item.get("metadata", {}) or {}
            source = meta.get("filename", "") if isinstance(meta, dict) else ""
            category = meta.get("category", "通用") if isinstance(meta, dict) else "通用"

            # 从内容提取简短主题（前 20 字）
            topic = content[:20].strip().rstrip("，。；")

            if similarity >= self.thresholds["existing"]:
                existing.append(KBCoverageItem(
                    topic=topic, content=content, source=source,
                    similarity=similarity, category=category,
                ))
                known_texts.append(content)
            elif similarity >= self.thresholds["partial"]:
                partial.append(KBCoverageItem(
                    topic=topic, content=content, source=source,
                    similarity=similarity, category=category,
                ))
                known_texts.append(content)

        # 从查询中提取未被覆盖的主题作为 missing
        missing_topics = self._extract_missing_topics(query, known_texts)

        total = len(existing) + len(partial) + len(missing_topics)
        coverage_ratio = (len(existing) + len(partial) * 0.5) / max(total, 1)

        return KnowledgeCheckResult(
            existing=existing,
            partial=partial,
            missing=missing_topics,
            coverage_ratio=round(coverage_ratio, 2),
        )

    def _extract_missing_topics(self, query: str, known_texts: List[str]) -> List[MissingTopic]:
        """从查询中提取知识库未覆盖的主题词。"""
        known_combined = " ".join(known_texts)

        # 简单名词短语提取：去掉语气词、动词，取 2-4 字片段
        tokens = re.findall(r'[一-鿿]{2,6}', query)
        stop_words = {"设计", "系统", "功能", "实现", "制作", "开发", "需求", "文档",
                       "策划", "方案", "规划", "流程", "规则", "配置", "一个"}

        missing = []
        seen = set()
        for token in tokens:
            if token in stop_words or len(token) < 2:
                continue
            if token not in known_combined and token not in seen:
                seen.add(token)
                missing.append(MissingTopic(
                    topic=token,
                    suggestion=f"知识库中无「{token}」相关设定，需 AI 自行设计或用户补充",
                ))

        return missing[:5]  # 最多返回 5 个缺失主题

    def format_check_result(self, result: KnowledgeCheckResult) -> str:
        """将检查结果格式化为提示词中的两个区块。"""
        parts = []

        # 区块 1：已有设定
        if result.existing:
            parts.append("## 本项目已有设定（必须遵守）")
            for item in result.existing:
                parts.append(f"- {item.content} [来源：{item.source or '知识库'}]")
            parts.append("")

        # 区块 2：部分覆盖
        if result.partial:
            parts.append("## 本项目已有部分相关内容（可作为参考）")
            for item in result.partial:
                parts.append(f"- {item.content} [来源：{item.source or '知识库'}，相似度：{item.similarity:.1%}]")
            parts.append("")

        # 区块 3：缺失项
        if result.missing:
            parts.append("## 知识库未覆盖的内容（需自行设计）")
            for item in result.missing:
                parts.append(f"- {item.topic}：{item.suggestion}")
            parts.append("")

        return "\n".join(parts)
```

- [ ] **步骤 4：运行测试验证通过**

```bash
.venv\Scripts\python.exe -m pytest tests/test_knowledge_checker.py -v
```
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add api/knowledge_checker.py tests/test_knowledge_checker.py
git commit -m "feat: 新增知识完整性检查器模块"
```

---

### 任务 2：引用增强生成器 (CitationEnhancer)

**文件：**
- 创建：`api/citation_enhancer.py`
- 测试：`tests/test_citation_enhancer.py`

- [ ] **步骤 1：编写失败的测试**

```python
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
                topic="装备强化上限+15",
                content="装备强化上限为+15，每次强化消耗金币和强化石。",
                source="数值设计规范.docx",
                similarity=0.85,
                category="数值",
            ),
            KBCoverageItem(
                topic="强化分为 15 级",
                content="强化系统分为 15 级，每级成功率递减。",
                source="强化系统设计.docx",
                similarity=0.78,
                category="系统",
            ),
        ],
        partial=[
            KBCoverageItem(
                topic="玩家等级上限",
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
    assert enhanced.startswith(base_prompt)  # base_prompt 保持不变


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
```

- [ ] **步骤 2：运行测试验证失败**

```bash
.venv\Scripts\python.exe -m pytest tests/test_citation_enhancer.py -v
```
预期：FAIL

- [ ] **步骤 3：编写实现代码**

```python
"""api/citation_enhancer.py — 引用增强生成器。"""

import re
from dataclasses import dataclass
from typing import List, Tuple, Optional, Literal


@dataclass
class Citation:
    claim: str
    source: Optional[str]
    type: Literal["reference", "extension", "ai_design", "suggest_modify"]


@dataclass
class CitationMetrics:
    total_claims: int
    referenced: int
    ai_designed: int
    coverage: float


CITATION_RULES = """
## 引用规则（必须遵守）
1. 涉及项目已有设定的内容，必须标注来源：[参考：文件名]
2. 在已有设定上的合理扩展 → [基于：文件名]
3. AI 自行设计（知识库无此设定）→ [设计：AI自主设计]
4. 每章结束汇总本章引用来源清单
5. 若某设定与知识库不符但你认为应修改，标注 [建议修改] 并说明理由
"""

CITATION_PATTERN = re.compile(
    r'\[(参考|基于|设计|建议修改)[：:]\s*(.*?)\]'
)


class CitationEnhancer:
    """在生成前增强提示词，生成后解析引用标注。"""

    def enhance_prompt(self, base_prompt: str, check_result, kb_only: bool = False) -> str:
        """在 base_prompt 末尾注入引用规则，在知识清单不为空时追加知识清单。"""
        if not check_result.existing and not check_result.partial and not check_result.missing:
            return base_prompt

        extra_parts = [CITATION_RULES]

        from api.knowledge_checker import KnowledgeChecker
        checker = KnowledgeChecker.__new__(KnowledgeChecker)
        knowledge_section = checker.format_check_result(check_result)

        if knowledge_section:
            extra_parts.append(knowledge_section)

        if kb_only:
            extra_parts.append(
                "\n【额外约束 - 仅基于知识库】\n"
                "你只能使用上面提供的「项目已有设定」内容来生成文档。"
                "如果知识库中没有相关信息，请明确说明「知识库中无此设定，无法生成」。"
                "严禁编造任何知识库中没有的世界观、系统、数值、角色、玩法等内容。"
            )

        return base_prompt + "\n" + "\n".join(extra_parts)

    def parse_citations_from_response(
        self, response: str
    ) -> Tuple[str, List[Citation], CitationMetrics]:
        """从 AI 响应中解析引用标注，返回(干净文本, 引用列表, 指标)。"""
        citations = []
        clean_parts = []
        last_end = 0

        for match in CITATION_PATTERN.finditer(response):
            start, end = match.start(), match.end()
            # 标注前面的文本（被引用的声明）
            claim_start = max(0, start - 60)
            claim = response[claim_start:start].strip().split("\n")[-1][:30]

            tag_type = match.group(1)
            source = match.group(2).strip() or None

            type_map = {
                "参考": "reference",
                "基于": "extension",
                "设计": "ai_design",
                "建议修改": "suggest_modify",
            }

            citations.append(Citation(
                claim=claim,
                source=source,
                type=type_map.get(tag_type, "ai_design"),
            ))

            # 保留标注前的文本，去掉标注本身
            clean_parts.append(response[last_end:start])
            last_end = end

        clean_parts.append(response[last_end:])
        clean_text = "".join(clean_parts).strip()

        # 计算指标
        total = len(citations)
        referenced = sum(1 for c in citations if c.type in ("reference", "extension"))
        ai_designed = sum(1 for c in citations if c.type == "ai_design")
        coverage = referenced / total if total > 0 else 0.0

        metrics = CitationMetrics(
            total_claims=total,
            referenced=referenced,
            ai_designed=ai_designed,
            coverage=round(coverage, 2),
        )

        return clean_text, citations, metrics
```

- [ ] **步骤 4：运行测试验证通过**

```bash
.venv\Scripts\python.exe -m pytest tests/test_citation_enhancer.py -v
```
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add api/citation_enhancer.py tests/test_citation_enhancer.py
git commit -m "feat: 新增引用增强生成器模块"
```

---

### 任务 3：一致性检测器 (ConsistencyChecker)

**文件：**
- 创建：`api/consistency_checker.py`
- 测试：`tests/test_consistency_checker.py`

- [ ] **步骤 1：编写失败的测试**

```python
"""tests/test_consistency_checker.py"""

import os
import sys
import tempfile
import shutil
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.consistency_checker import ConsistencyChecker, Conflict, ConsistencyResult
from api.kb_project import KBProject


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

    import time
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
    assert any("上限" in c.paragraph or "+15" in c.kb_source for c in high_conflicts)


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
```

- [ ] **步骤 2：运行测试验证失败**

```bash
.venv\Scripts\python.exe -m pytest tests/test_consistency_checker.py -v
```
预期：FAIL

- [ ] **步骤 3：编写实现代码**

```python
"""api/consistency_checker.py — 语义一致性检测器。"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Literal


@dataclass
class Conflict:
    level: Literal["high", "medium", "low"]
    paragraph: str
    kb_source: str
    source_file: str
    conflict_type: Literal["numeric", "constraint", "semantic"]
    fix_suggestion: Optional[str] = None


@dataclass
class ConsistencyResult:
    conflicts: List[Conflict] = field(default_factory=list)
    auto_fixed_paragraphs: List[str] = field(default_factory=list)
    score: float = 1.0


# 数值模式：提取数值加上下文前缀，如 "上限+15" "消耗50" "50%"
NUMERIC_PATTERN = re.compile(r'(上限为|下限为|上限|下限|消耗|为|)(\d{1,6})([%+]?)')

# 约束关键词
CONSTRAINT_KEYWORDS = ["不能", "禁止", "不可", "必须", "只能", "不得", "上限", "下限"]


class ConsistencyChecker:
    """比对输出与知识库内容，检测数值/约束/语义矛盾。"""

    def __init__(self, kb_project):
        self.kb = kb_project

    def check(self, output: str) -> ConsistencyResult:
        if not output or not self.kb:
            return ConsistencyResult()

        conflicts = []
        paragraphs = [p.strip() for p in output.split("\n") if p.strip()]

        for para in paragraphs:
            # 1. 数值冲突检测
            conflicts.extend(self._detect_numeric_conflicts(para))
            # 2. 约束关键词检测
            conflicts.extend(self._detect_constraint_conflicts(para))

        # 计算一致性评分
        if not conflicts:
            score = 1.0
        else:
            high = sum(1 for c in conflicts if c.level == "high")
            medium = sum(1 for c in conflicts if c.level == "medium")
            score = max(0.0, 1.0 - (high * 0.4 + medium * 0.15))

        return ConsistencyResult(conflicts=conflicts, score=round(score, 2))

    def _detect_numeric_conflicts(self, para: str) -> List[Conflict]:
        """检测段落中与知识库矛盾的数值。"""
        conflicts = []
        numbers = NUMERIC_PATTERN.findall(para)
        if not numbers:
            return conflicts

        # 从 KB 搜索相关条目
        try:
            kb_results = self.kb.search(para[:80], top_k=3)
        except Exception:
            return conflicts

        for prefix, value, suffix in numbers:
            for kb_item in kb_results:
                kb_text = kb_item.get("text", "")
                kb_score = kb_item.get("score", 0)
                meta = kb_item.get("metadata", {}) or {}
                source_file = meta.get("filename", "") if isinstance(meta, dict) else ""

                # 找知识库中同一个维度的数值进行比较
                if prefix and prefix in kb_text:
                    kb_numbers = NUMERIC_PATTERN.findall(kb_text)
                    for kb_prefix, kb_value, kb_suffix in kb_numbers:
                        if kb_prefix == prefix and value != kb_value:
                            level = "high"
                            conflicts.append(Conflict(
                                level=level,
                                paragraph=para,
                                kb_source=kb_text,
                                source_file=source_file,
                                conflict_type="numeric",
                                fix_suggestion=f"知识库中该值为 {kb_value}{kb_suffix}，建议统一",
                            ))

        return conflicts

    def _detect_constraint_conflicts(self, para: str) -> List[Conflict]:
        """检测段落中与知识库矛盾的约束表述。"""
        conflicts = []
        has_keyword = any(kw in para for kw in CONSTRAINT_KEYWORDS)
        if not has_keyword:
            return conflicts

        try:
            kb_results = self.kb.search(para[:100], top_k=3)
        except Exception:
            return conflicts

        for kb_item in kb_results:
            kb_text = kb_item.get("text", "")
            kb_score = kb_item.get("score", 0)
            meta = kb_item.get("metadata", {}) or {}
            source_file = meta.get("filename", "") if isinstance(meta, dict) else ""

            # 如果 KB 中有相反的约束
            for kw in CONSTRAINT_KEYWORDS:
                if kw in kb_text:
                    # 简单矛盾检测：段落说"不能X"而知识库说"可以X"，反之亦然
                    para_after_kw = para[para.find(kw):para.find(kw) + 20] if kw in para else ""
                    kb_after_kw = kb_text[kb_text.find(kw):kb_text.find(kw) + 20] if kw in kb_text else ""
                    if para_after_kw and kb_after_kw and self._is_contradictory(para_after_kw, kb_after_kw):
                        conflicts.append(Conflict(
                            level="medium",
                            paragraph=para,
                            kb_source=kb_text,
                            source_file=source_file,
                            conflict_type="constraint",
                        ))

        return conflicts

    def _is_contradictory(self, text_a: str, text_b: str) -> bool:
        """简单判断两段文本是否语义矛盾。"""
        negations = ["不", "禁止", "不能", "不可", "不得"]
        a_neg = any(n in text_a for n in negations)
        b_neg = any(n in text_b for n in negations)
        return a_neg != b_neg  # 一个有否定另一个没有 → 可能矛盾
```

- [ ] **步骤 4：运行测试验证通过**

```bash
.venv\Scripts\python.exe -m pytest tests/test_consistency_checker.py -v
```
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add api/consistency_checker.py tests/test_consistency_checker.py
git commit -m "feat: 新增一致性检测器模块"
```

---

### 任务 4：知识提炼器 (KnowledgeExtractor) + KBProject 扩展

**文件：**
- 创建：`api/knowledge_extractor.py`
- 修改：`api/kb_project.py`（追加 `add_text_knowledge` 方法）
- 测试：`tests/test_knowledge_extractor.py`

- [ ] **步骤 1：在 `api/kb_project.py` 末尾（`_load_projects` 之前或之后）追加 `add_text_knowledge` 方法**

```python
def add_text_knowledge(self, text: str, category: str = "通用", source: str = "AI生成") -> bool:
    """添加一段纯文本知识到知识库（不经过文件系统），用于程序化知识回写。"""
    import uuid, time
    doc_id = f"ai_{uuid.uuid4().hex[:12]}"

    doc = {
        "id": doc_id,
        "filename": f"{source}_{category}.md",
        "content": text,
        "doc_type": "text",
        "file_size": len(text.encode("utf-8")),
        "folder_id": category,
        "status": "pending",
        "created_at": time.time(),
    }
    self.documents.append(doc)

    self._chunk_document(doc_id, text)
    self._save_all()
    return True
```

- [ ] **步骤 1：编写失败的测试**

```python
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
```

- [ ] **步骤 2：运行测试验证失败**

```bash
.venv\Scripts\python.exe -m pytest tests/test_knowledge_extractor.py -v
```
预期：FAIL

- [ ] **步骤 3：编写实现代码**

```python
"""api/knowledge_extractor.py — 知识提炼器。"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple


KNOWLEDGE_PATTERNS = [
    (re.compile(r'[\d.]+\%'), "数值"),                    # 百分比数值
    (re.compile(r'(上限|下限).*\d+'), "数值"),           # 数值上限/下限
    (re.compile(r'(不能|禁止|不可|必须|只能|不得).+'), "规则"),  # 约束性陈述
    (re.compile(r'(?:指|定义为|称为|包括|分为|包含|由|包括)'), "系统"),  # 定义性陈述
    (re.compile(r'(简称.*|.*以下简称为)'), "术语"),       # 术语定义
    (re.compile(r'(等级|级)\s*[\d]+\s*[级时]'), "数值"),  # 等级相关
    (re.compile(r'\[数值\]|\[规则\]|\[系统\]'), "通用"),  # 显式标记
]

TERMINOLOGY_PATTERN = re.compile(r'(?:简称|以下简称为|以下称为|叫作|称之为)\s*[「""]?([^」""\s]+)[」""]?\s*')


@dataclass
class KnowledgeEntry:
    content: str
    category: str
    source: str = "AI生成提炼"
    confidence: float = 0.7
    is_draft: bool = False


@dataclass
class ExtractionResult:
    entries: List[KnowledgeEntry] = field(default_factory=list)
    terminology_updates: Dict[str, str] = field(default_factory=dict)


@dataclass
class WriteBackSummary:
    added_to_kb: int = 0
    updated_profile: List[str] = field(default_factory=list)
    drafts: int = 0


class KnowledgeExtractor:
    """从用户确认后的最终文档提取新知识，回写到知识库和项目画像。"""

    def __init__(self, kb_project, project_profile: dict):
        self.kb = kb_project
        self.profile = project_profile

    def extract(self, final_output: str, kb_entries: list) -> ExtractionResult:
        """从输出中提取新知识条目和术语更新。"""
        entries = []
        terminology = {}

        paragraphs = [p.strip() for p in final_output.split("\n") if p.strip()]

        for para in paragraphs:
            if not self._is_project_knowledge(para):
                continue

            # 检查是否与已有知识库重复
            if self._is_duplicate(para, kb_entries):
                continue

            category = self._classify_paragraph(para)
            confidence = self._calc_confidence(para)
            entries.append(KnowledgeEntry(
                content=para,
                category=category,
                confidence=confidence,
                is_draft=confidence < 0.7,
            ))

            # 提取术语
            term_result = self._extract_terminology(para)
            if term_result:
                term, meaning = term_result
                terminology[term] = meaning

        return ExtractionResult(entries=entries, terminology_updates=terminology)

    def _is_project_knowledge(self, paragraph: str) -> bool:
        """判断段落是否包含有价值的项目设定。"""
        if len(paragraph) < 6 or len(paragraph) > 300:
            return False

        # 通用描述排除
        generic = re.compile(
            r'^(这是一个|这是一款|玩家可以|游戏将|我们设计了|综上所述|总之|以下)',
        )
        if generic.match(paragraph):
            return False

        for pattern, _ in KNOWLEDGE_PATTERNS:
            if pattern.search(paragraph):
                return True

        return False

    def _is_duplicate(self, paragraph: str, kb_entries: list) -> bool:
        """简单去重：检查是否与已有知识库条目高度相似。"""
        for entry in kb_entries:
            existing = entry.get("text", "") if isinstance(entry, dict) else str(entry)
            if len(existing) > 5 and paragraph[:20] in existing:
                return True
        return False

    def _classify_paragraph(self, paragraph: str) -> str:
        """对段落进行分类。"""
        best_cat = "通用"
        best_score = 0

        category_scores = {
            "数值": len(re.findall(r'[\d]', paragraph)) / max(len(paragraph), 1),
            "规则": 0.8 if re.search(r'(不能|禁止|必须|只能|不得|条件|限制)', paragraph) else 0,
            "系统": 0.8 if re.search(r'(系统|分为|包括|包含|由.*组成)', paragraph) else 0,
            "术语": 0.9 if re.search(r'(简称|定义为|称为)', paragraph) else 0,
            "世界观": 0.8 if re.search(r'(世界观|背景|年代|大陆|世界)', paragraph) else 0,
        }

        for cat, score in category_scores.items():
            if score > best_score:
                best_score = score
                best_cat = cat

        return best_cat if best_score > 0 else "通用"

    def _calc_confidence(self, paragraph: str) -> float:
        """计算知识置信度。"""
        score = 0.7  # 基准

        # 含数值 → 加分
        if re.search(r'\d+', paragraph):
            score += 0.1
        # 含约束词 → 加分
        if re.search(r'(上限|下限|不能|必须|禁止)', paragraph):
            score += 0.1
        # 超过 100 字 → 减分（太泛）
        if len(paragraph) > 150:
            score -= 0.1
        # 非常短 → 减分
        if len(paragraph) < 15:
            score -= 0.1

        return max(0.3, min(1.0, round(score, 2)))

    def _extract_terminology(self, paragraph: str) -> Optional[Tuple[str, str]]:
        """提取术语定义。"""
        match = TERMINOLOGY_PATTERN.search(paragraph)
        if match:
            term = match.group(1).strip()
            # 术语含义通常是术语前面最近的名词短语
            before = paragraph[:match.start()].strip()
            words = re.findall(r'[一-鿿]+', before)
            meaning = words[-1] if words else ""
            return (term, meaning)

        # 也匹配「以下将X简称为Y」模式
        alt = re.search(r'以下将[「""]?([^」""\s]+)[」""]?简称为[「""]?([^」""\s]+)[」""]?', paragraph)
        if alt:
            return (alt.group(2), alt.group(1))

        return None

    def write_back(self, result: ExtractionResult) -> WriteBackSummary:
        """将新知识回写到知识库和项目画像。"""
        added = 0
        drafts = 0

        for entry in result.entries:
            content = entry.content
            if entry.is_draft:
                content = f"[待确认] {content}"
                drafts += 1

            try:
                if self.kb and hasattr(self.kb, 'add_text_knowledge'):
                    self.kb.add_text_knowledge(content, entry.category, entry.source)
                    added += 1
            except Exception:
                pass

        # 更新项目画像术语
        profile_updates = []
        if self.profile and result.terminology_updates:
            terms = self.profile.setdefault("terminology", {})
            for term, meaning in result.terminology_updates.items():
                if term not in terms:
                    terms[term] = meaning
                    profile_updates.append(term)

        return WriteBackSummary(
            added_to_kb=added,
            updated_profile=profile_updates,
            drafts=drafts,
        )
```

- [ ] **步骤 4：运行测试验证通过**

```bash
.venv\Scripts\python.exe -m pytest tests/test_knowledge_extractor.py -v
```
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add api/knowledge_extractor.py tests/test_knowledge_extractor.py
git commit -m "feat: 新增知识提炼器模块"
```

---

### 任务 5：PRDSelfCheck 集成一致性检测

**文件：**
- 修改：`api/prd_self_check.py`

- [ ] **步骤 1：编写失败的测试**

先确认现有测试能通过：

```bash
.venv\Scripts\python.exe -m pytest tests/ -v -k "self_check or prd"
```

然后编写新测试（追加到 `tests/test_consistency_checker.py` 或独立的集成测试文件）：

```python
# 追加到 tests/test_consistency_checker.py 末尾

def test_check_and_validate_integration(kb_with_numeric_rules):
    """check_and_validate 应同时返回格式检查和一致性检查结果。"""
    from api.prd_self_check import PRDSelfCheck
    import tempfile

    tmp_dir = tempfile.mkdtemp(prefix="pci_")
    try:
        checker = PRDSelfCheck(tmp_dir)
        # 模拟一个同时包含格式问题和一致性问题的输出
        output = "装备强化上限为+20。"
        result = checker.check_and_validate(output, kb_with_numeric_rules)
        assert "consistency" in result
        assert "format" in result
        assert len(result["consistency"].conflicts) >= 1
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)
```

- [ ] **步骤 2：运行测试验证失败**

```bash
.venv\Scripts\python.exe -m pytest tests/test_consistency_checker.py::test_check_and_validate_integration -v
```
预期：FAIL（PRDSelfCheck 尚无 check_and_validate 方法）

- [ ] **步骤 3：修改 `api/prd_self_check.py`——追加 `check_and_validate` 方法**

在 `PRDSelfCheck` 类的末尾（`_save_log` 方法之后）追加：

```python
def check_and_validate(self, content: str, kb_project=None) -> dict:
    """合并格式检查 + 语义一致性检查。

    返回:
    {
        "passed": bool,
        "reasons": list[str],
        "format": dict,           # 原有格式检查结果
        "consistency": object,    # ConsistencyResult
    }
    """
    format_result = self.check(content)

    # 带引用标注的文本在检查前去掉标注
    import re
    clean_content = re.sub(r'\[(参考|基于|设计|建议修改)[：:].*?\]', '', content)

    consistency_result = None
    if kb_project:
        try:
            from consistency_checker import ConsistencyChecker
            cc = ConsistencyChecker(kb_project)
            consistency_result = cc.check(clean_content)
        except Exception:
            consistency_result = None

    # 合并通过状态
    format_passed = format_result.get("passed", True)
    consistency_passed = consistency_result.score >= 0.6 if consistency_result else True
    passed = format_passed and consistency_passed

    reasons = list(format_result.get("reasons", []))
    if consistency_result and consistency_result.conflicts:
        high_count = sum(1 for c in consistency_result.conflicts if c.level == "high")
        if high_count > 0:
            reasons.append(f"与知识库存在 {high_count} 处严重冲突，建议修正")

    return {
        "passed": passed,
        "reasons": reasons,
        "format": format_result,
        "consistency": consistency_result,
    }
```

- [ ] **步骤 4：运行测试验证通过**

```bash
.venv\Scripts\python.exe -m pytest tests/test_consistency_checker.py::test_check_and_validate_integration -v
```
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add api/prd_self_check.py tests/test_consistency_checker.py
git commit -m "feat: PRDSelfCheck 集成一致性检测"
```

---

### 任务 6：AIService 集成全部模块

**文件：**
- 修改：`api/ai_service.py`
- 测试：`tests/test_ai_service.py`（追加）

- [ ] **步骤 1：在 `imitate()` 方法中——RAG 检索后插入 KnowledgeChecker**

找到 `ai_service.py:299-320`（RAG 检索后、prompt 构建前），在 `rag_contexts` 获取之后、`knowledge_sections` 构建之前，插入：

```python
# ======== Step 1.5: 知识完整性检查 (新增) ========
knowledge_check = None
if use_rag and self.kb and project_id:
    try:
        from knowledge_checker import KnowledgeChecker
        proj = self.kb.get_project(project_id) if self.kb else None
        if proj:
            kc = KnowledgeChecker(proj)
            knowledge_check = kc.check(requirements)
    except Exception:
        knowledge_check = None
```

- [ ] **步骤 2：在 prompt 构建前插入引用规则增强（修改 Step 3）**

在 `user_prompt_parts` 构建之前（`ai_service.py:349` 处），插入 KnowledgeCheck 结果格式化和 CitationEnhancer 调用：

```python
# ======== Step 2.5: 引用增强 (新增) ========
citation_enhanced_system = ENHANCED_SYSTEM_PROMPT
template_is_html = bool(user_template and re.search(r'</?(h[1-6]|p|div|table|tr|td|th|ul|ol|li|br|span|strong|em)>', user_template))

if knowledge_check and (knowledge_check.existing or knowledge_check.partial):
    try:
        from citation_enhancer import CitationEnhancer
        ce = CitationEnhancer()
        citation_enhanced_system = ce.enhance_prompt(
            ENHANCED_SYSTEM_PROMPT, knowledge_check, kb_only=kb_only,
        )
    except Exception:
        citation_enhanced_system = ENHANCED_SYSTEM_PROMPT
```

然后将后续代码中的 `system_prompt = ENHANCED_SYSTEM_PROMPT` 替换为使用 `citation_enhanced_system`。

- [ ] **步骤 3：在输出格式化前插入一致性检测（修改 Step 6）**

在 `ai_service.py:436` 的自检 + 重写循环之后，格式化之前插入：

```python
# ======== Step 6.5: 一致性检测 (新增) ========
consistency_data = None
if self.checker and response and len(response) > 50 and project_id and self.kb:
    try:
        proj = self.kb.get_project(project_id) if self.kb else None
        if proj:
            combined = self.checker.check_and_validate(response, proj)
            consistency_data = combined.get("consistency")
            # 如果格式 + 一致性都通过，但原有自检标记了重写但未触发（因为 max=1），
            # 这里不再触发额外重写，仅在返回数据中附带一致性信息
    except Exception:
        consistency_data = None
```

- [ ] **步骤 4：修改 `imitate()` 的返回值，附带元数据**

将返回从 `return response` 改为：

```python
# 构建返回元数据
result_data = {
    "content": response,
}
if knowledge_check:
    from knowledge_checker import KnowledgeChecker as _KC
    result_data["knowledge_coverage"] = knowledge_check.coverage_ratio
    result_data["existing_topics"] = [item.topic[:20] for item in knowledge_check.existing[:5]]
    result_data["missing_topics"] = [item.topic for item in knowledge_check.missing[:5]]

if consistency_data:
    result_data["consistency_score"] = consistency_data.score
    result_data["conflicts"] = [
        {"level": c.level, "paragraph": c.paragraph[:100],
         "source_file": c.source_file, "fix_suggestion": c.fix_suggestion}
        for c in consistency_data.conflicts[:10]
    ]

if cite_sources and rag_contexts:
    # 已有的引用来源处理
    sources = set()
    for cat_items in rag_contexts.values():
        for item in cat_items:
            meta = item.get("metadata", {})
            fname = meta.get("filename", "") if isinstance(meta, dict) else ""
            if fname:
                sources.add(fname)
    result_data["sources"] = list(sources)

# 引用解析
if knowledge_check and (knowledge_check.existing or knowledge_check.partial):
    try:
        from citation_enhancer import CitationEnhancer
        ce = CitationEnhancer()
        clean_text, citations, metrics = ce.parse_citations_from_response(response)
        if citations:
            result_data["citations"] = [
                {"claim": c.claim[:30], "source": c.source, "type": c.type}
                for c in citations
            ]
            result_data["citation_coverage"] = metrics.coverage
    except Exception:
        pass

return result_data
```

- [ ] **步骤 5：更新 `ai.py` 路由层适配新返回值**

修改 `api/routers/ai.py:48-72` 的 `imitate` 端点：

```python
@router.post("/imitate")
async def imitate(payload: dict = Body(...)):
    # ... 参数解析保持不变 ...
    try:
        result = await get_ai_service().imitate(
            model, requirements, context, use_rag=use_rag,
            output_format=output_format, template_content=template_content,
            images=images, project_id=project_id,
            kb_only=kb_only, cite_sources=cite_sources,
        )
        if isinstance(result, dict):
            return {"success": True, "data": result.get("content", ""), "meta": result}
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "message": f"AI 服务调用失败: {str(e)}"}
```

- [ ] **步骤 6：运行现有测试确保不破坏已有逻辑**

```bash
.venv\Scripts\python.exe -m pytest tests/ -v
```
预期：44 个测试全部 PASS（原有测试不变）

- [ ] **步骤 7：Commit**

```bash
git add api/ai_service.py api/routers/ai.py
git commit -m "feat: AIService 集成知识锚定四个模块"
```

---

### 任务 7：新增 confirm-generation API 端点

**文件：**
- 修改：`api/routers/ai.py`

- [ ] **步骤 1：在 `api/routers/ai.py` 末尾新增端点**

```python
@router.post("/confirm-generation")
async def confirm_generation(payload: dict = Body(...)):
    """用户确认了 AI 生成的内容，触发知识提炼回写。"""
    content = payload.get("content", "")
    project_id = payload.get("project_id", "")
    rag_sources = payload.get("rag_sources", [])

    if not content or not project_id:
        return {"success": False, "message": "内容或项目ID不能为空"}

    try:
        svc = get_ai_service()
        # 获取知识库项目实例
        if not svc.kb:
            return {"success": False, "message": "知识库未初始化"}

        proj = svc.kb.get_project(project_id)
        if not proj:
            return {"success": False, "message": "项目不存在"}

        # 加载项目画像
        import os, json
        data_dir = os.environ.get("GB_DATA_DIR", "")
        if not data_dir:
            app_data = os.environ.get("APPDATA", "")
            data_dir = os.path.join(app_data, "GameBuilderAIHelper") if app_data else ""
        profile_path = os.path.join(data_dir, "project_profile.json")
        profile = {}
        if os.path.exists(profile_path):
            with open(profile_path, "r", encoding="utf-8") as f:
                profile = json.load(f)

        from api.knowledge_extractor import KnowledgeExtractor
        extractor = KnowledgeExtractor(proj, profile)
        result = extractor.extract(content, rag_sources)
        summary = extractor.write_back(result)

        # 保存更新后的项目画像
        if summary.updated_profile and profile:
            try:
                with open(profile_path, "w", encoding="utf-8") as f:
                    json.dump(profile, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

        return {
            "success": True,
            "data": {
                "added_to_kb": summary.added_to_kb,
                "updated_profile": summary.updated_profile,
                "drafts": summary.drafts,
            }
        }
    except Exception as e:
        return {"success": False, "message": f"知识提炼失败: {str(e)}"}
```

- [ ] **步骤 2：测试新端点**

```bash
# 启动后端后
curl -X POST http://127.0.0.1:8000/api/ai/confirm-generation \
  -H "Content-Type: application/json" \
  -d "{\"content\":\"暴击率为15%，冷却时间30秒。\",\"project_id\":\"test\"}"
```

预期：返回 `{"success": true, "data": { "added_to_kb": N, "updated_profile": [], "drafts": M }}`

- [ ] **步骤 3：Commit**

```bash
git add api/routers/ai.py
git commit -m "feat: 新增 confirm-generation 知识提炼端点"
```

---

### 任务 8：前端 useAI.ts 适配

**文件：**
- 修改：`src/composables/useAI.ts`

- [ ] **步骤 1：扩展现有类型和请求逻辑**

在文件顶部附近（import 之后）添加新接口：

```typescript
interface CitationData {
  claim: string
  source: string | null
  type: 'reference' | 'extension' | 'ai_design' | 'suggest_modify'
}

interface ConflictData {
  level: 'high' | 'medium' | 'low'
  paragraph: string
  source_file?: string
  fix_suggestion?: string
}

interface ImitationMeta {
  knowledge_coverage?: number
  consistency_score?: number
  citation_coverage?: number
  existing_topics?: string[]
  missing_topics?: string[]
  sources?: string[]
  citations?: CitationData[]
  conflicts?: ConflictData[]
}
```

在 `useAI` 的返回值中添加响应式和确认方法：

```typescript
const imitationMeta = ref<ImitationMeta | null>(null)
const projectId = ref('')

const runImitation = async (
  requirements: string, context = '', useRag = true, format = 'html',
  templateContent = '', images: string[] = [], pid = '', kbOnly = false, citeSources = false
): Promise<string | null> => {
  projectId.value = pid
  const r = await axios.post<ApiResponse<string> & { meta?: ImitationMeta }>(
    apiUrl('/api/ai/imitate'), {
      model: activeModel.value, requirements, context, use_rag: useRag,
      format, template_content: templateContent, images,
      project_id: pid || undefined, kb_only: kbOnly, cite_sources: citeSources,
    },
  )
  if (r.data.success) {
    if (r.data.meta) imitationMeta.value = r.data.meta
    return r.data.data || null
  }
  return null
}

const confirmGeneration = async (content: string): Promise<{ addedToKb: number; drafts: number } | null> => {
  if (!projectId.value) return null
  try {
    const r = await axios.post(apiUrl('/api/ai/confirm-generation'), {
      content,
      project_id: projectId.value,
      rag_sources: imitationMeta.value?.sources || [],
    })
    if (r.data.success) return r.data.data || null
    return null
  } catch {
    return null
  }
}

const resetMeta = () => { imitationMeta.value = null }
```

在 `return` 语句中添加：

```typescript
return {
  // ... 原有返回值 ...
  imitationMeta,
  confirmGeneration,
  resetMeta,
}
```

- [ ] **步骤 2：运行 TypeScript 检查**

```bash
npm run check
```
预期：PASS

- [ ] **步骤 3：Commit**

```bash
git add src/composables/useAI.ts
git commit -m "feat: useAI 适配知识锚定元数据和确认端点"
```

---

### 任务 9：前端 AIIterationPanel.vue 显示引用来源和冲突

**文件：**
- 修改：`src/components/panels/AIIterationPanel.vue`

- [ ] **步骤 1：在面板顶部添加知识覆盖指标**

在模板中适当位置（如输出区域上方）插入：

```vue
<template v-if="imitationMeta">
  <div class="knowledge-metrics">
    <span v-if="imitationMeta.citation_coverage !== undefined"
          :class="['metric-badge', coverageClass(imitationMeta.citation_coverage)]">
      引用覆盖 {{ (imitationMeta.citation_coverage * 100).toFixed(0) }}%
    </span>
    <span v-if="imitationMeta.consistency_score !== undefined"
          :class="['metric-badge', scoreClass(imitationMeta.consistency_score)]">
      一致性 {{ (imitationMeta.consistency_score * 100).toFixed(0) }}%
    </span>
    <span v-if="imitationMeta.knowledge_coverage !== undefined"
          class="metric-badge metric-neutral">
      知识覆盖 {{ (imitationMeta.knowledge_coverage * 100).toFixed(0) }}%
    </span>
  </div>
</template>
```

添加样式：

```vue
<style scoped>
.knowledge-metrics {
  display: flex;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-secondary);
  border-radius: 6px;
  margin-bottom: 8px;
}
.metric-badge {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
}
.metric-good { background: #e6f7e6; color: #1a7a1a; }
.metric-warn { background: #fff3e0; color: #b76e00; }
.metric-poor { background: #ffeaea; color: #c0392b; }
.metric-neutral { background: #e8e8e8; color: #666; }
</style>
```

方法：

```typescript
const coverageClass = (rate: number) =>
  rate >= 0.7 ? 'metric-good' : rate >= 0.4 ? 'metric-warn' : 'metric-poor'
const scoreClass = (score: number) =>
  score >= 0.8 ? 'metric-good' : score >= 0.6 ? 'metric-warn' : 'metric-poor'
```

- [ ] **步骤 2：添加引用来源折叠面板**

在输出内容下方插入：

```vue
<template v-if="imitationMeta?.citations?.length">
  <div class="citation-panel">
    <div class="citation-header" @click="showCitations = !showCitations">
      <span>📎 引用来源 {{ imitationMeta.citations.length }} 条</span>
      <span :class="['arrow', { open: showCitations }]">▶</span>
    </div>
    <div v-if="showCitations" class="citation-list">
      <div v-for="(cite, i) in imitationMeta.citations" :key="i" class="citation-item">
        <span class="cite-type" :class="cite.type">[{{ typeLabel(cite.type) }}]</span>
        <span class="cite-claim">{{ cite.claim }}</span>
        <span v-if="cite.source" class="cite-source">{{ cite.source }}</span>
      </div>
    </div>
  </div>
</template>
```

```typescript
const showCitations = ref(false)
const typeLabel = (t: string) =>
  ({ reference: '参考', extension: '基于', ai_design: '设计', suggest_modify: '建议' })[t] || t
```

- [ ] **步骤 3：添加冲突标记**

在输出内容中渲染冲突标记（需要遍历 `imitationMeta.conflicts`）：

```vue
<template v-if="imitationMeta?.conflicts?.length">
  <div class="conflict-panel">
    <div class="conflict-header">
      <span>⚠️ 检测到 {{ imitationMeta.conflicts.filter(c => c.level==='medium'||c.level==='high').length }} 处潜在冲突</span>
    </div>
    <div v-for="(conflict, i) in highAndMediumConflicts" :key="i" class="conflict-item">
      <span :class="['conflict-level', conflict.level]">{{ levelBadge(conflict.level) }}</span>
      <span class="conflict-text">{{ conflict.paragraph.substring(0, 60) }}...</span>
      <div v-if="conflict.fix_suggestion" class="conflict-fix">建议：{{ conflict.fix_suggestion }}</div>
    </div>
  </div>
</template>
```

```typescript
const highAndMediumConflicts = computed(() =>
  (imitationMeta.value?.conflicts || []).filter(c => c.level === 'high' || c.level === 'medium')
)
const levelBadge = (level: string) =>
  ({ high: '严重', medium: '建议修改', low: '轻微' })[level] || level
```

- [ ] **步骤 4：添加「确认并学习」按钮**

在操作栏中添加：

```vue
<template v-if="projectId">
  <button class="btn btn-primary" @click="onConfirmGeneration" :disabled="isConfirming">
    {{ isConfirming ? '保存中...' : '确认并学习' }}
  </button>
</template>
```

```typescript
const isConfirming = ref(false)
const onConfirmGeneration = async () => {
  if (!aiResult.value) return
  isConfirming.value = true
  try {
    const result = await confirmGeneration(aiResult.value)
    if (result) {
      // 显示成功提示
      showToast(`已学习 ${result.addedToKb} 条新知识`)
      resetMeta()
    }
  } finally {
    isConfirming.value = false
  }
}
```

- [ ] **步骤 5：运行 TypeScript 检查**

```bash
npm run check
```
预期：PASS

- [ ] **步骤 6：Commit**

```bash
git add src/components/panels/AIIterationPanel.vue
git commit -m "feat: AIIterationPanel 展示引用来源和冲突信息"
```

---

### 集成验证

所有任务完成后运行完整测试套件：

```bash
.venv\Scripts\python.exe -m pytest tests/ -v
npm run check
```

预期：所有 44+ 个原有测试和新测试全部 PASS，TypeScript 检查通过。

---

### 未纳入范围（YAGNI）

- 用户行为偏好建模（如"喜欢多详细的输出"）
- 多轮对话中的上下文压缩学习
- 跨项目的知识迁移
- 前端拖拽式引用编辑
- 知识图谱可视化
- 前端深度引用标注渲染（仅在元数据/折叠面板中展示）

---

## 执行方式

计划已完成并保存到 `docs/superpowers/plans/2026-06-03-prd-self-learning-plan.md`。两种执行方式：

**1. 子代理驱动（推荐）** - 每个任务调度一个新的子代理，任务间进行审查，快速迭代

**2. 内联执行** - 在当前会话中使用 executing-plans 执行任务，批量执行并设有检查点

**选哪种方式？**
