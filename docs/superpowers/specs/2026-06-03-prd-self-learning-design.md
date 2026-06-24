# PRD 知识锚定生成与自学习系统 设计规格

## 概述

在现有的 PRD 智能仿写功能基础上，构建一套"知识锚定生成 + 自我学习"机制，使 AI 在每次仿写中充分吸收知识库内容、生成结果可追溯引用、自动检测矛盾，并将用户确认后的新知识回写到知识库，形成持续优化的闭环。

## 架构

### 扩展现有仿写流程

```
用户需求
  │
  ▼
┌─────────────────────────────────┐
│ ① 知识完整性检查器              │  ← 查询知识库，生成知识清单
│    → 输出: 知识清单（已有点/     │
│      部分有/缺失） + 引用规则    │
└────────────┬────────────────────┘
             │ 知识清单注入提示词
             ▼
┌─────────────────────────────────┐
│ ② 引用增强生成器               │  ← 改造提示词，强制引用溯源
│    → 输出: 含引用标注的AI输出    │
│       + citations 元数据        │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│    PRD自检（已有，保持不变）     │  ← 格式/完整性检查
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│ ③ 一致性检测器                 │  ← 语义比对知识库
│    → 输出: 冲突列表 + 自动修正   │
└────────────┬────────────────────┘
             │ 修正后版本
             ▼
        用户确认/修改
             │
             ▼
┌─────────────────────────────────┐
│ ④ 知识提炼器                   │  ← 提取新知识
│    → 输出: 新知识条目           │
│    → 回写: 知识库 + 项目画像    │
└─────────────────────────────────┘
             │
       下次生成时知识库更丰富 ──→ 闭环
```

### 涉及的文件

| 文件 | 变更类型 | 职责 |
|---|---|---|
| `api/ai_service.py` | 修改 | 仿写流程中集成 4 个新模块的调用 |
| `api/prd_self_check.py` | 修改 | 扩展为包含一致性检测；保持兼容 |
| `api/knowledge_checker.py` | 新建 | 模块①：知识完整性检查器 |
| `api/citation_enhancer.py` | 新建 | 模块②：引用增强提示词构建 |
| `api/consistency_checker.py` | 新建 | 模块③：语义一致性检测 |
| `api/knowledge_extractor.py` | 新建 | 模块④：知识提炼器 |
| `api/routers/ai.py` | 修改 | 新增元数据字段透传到前端 |
| `src/composables/useAI.ts` | 修改 | 处理引用元数据、覆盖率和冲突信息 |
| `src/components/panels/AIIterationPanel.vue` | 修改 | 显示引用来源和冲突标记 |
| `tests/test_knowledge_checker.py` | 新建 | 完整性检查器测试 |
| `tests/test_consistency_checker.py` | 新建 | 一致性检测器测试 |
| `tests/test_knowledge_extractor.py` | 新建 | 知识提炼器测试 |

---

## 模块①：知识完整性检查器

**文件**: `api/knowledge_checker.py`

### 核心类

```python
class KnowledgeChecker:
    def __init__(self, kb_project: KBProject):
        self.kb = kb_project
        self.similarity_thresholds = {
            "existing": 0.7,
            "partial": 0.4,
        }

    def check(self, query: str) -> KnowledgeCheckResult:
        """检查知识库对需求的覆盖程度"""

    def _categorize_entries(self, entries: list) -> dict:
        """将检索结果分为已有/部分/缺失三层"""
```

### 输出数据结构

```python
@dataclass
class KnowledgeCheckResult:
    existing: list[KBCoverageItem]   # 相似度 >= 0.7
    partial: list[KBCoverageItem]    # 0.4 ~ 0.7
    missing: list[MissingTopic]      # < 0.4
    coverage_ratio: float            # 0.0 ~ 1.0（已覆盖/全部需求）

@dataclass
class KBCoverageItem:
    topic: str
    content: str
    source: str          # 文件名
    similarity: float
    category: str        # 世界观/系统/数值/模板/规范/UI

@dataclass
class MissingTopic:
    topic: str
    suggestion: str      # 建议处理方式
```

### 知识清单格式化方法

`format_check_result(result) -> str` 将结果格式化为两个提示词段落：
1. 「本项目已有设定（必须遵守）」— `result.existing` 中的条目
2. 「知识库未覆盖的内容（需自行设计）」— `result.partial` + `result.missing` 摘要

### 错误处理
- 知识库为空（尚未上传文档）→ 返回空结果，不阻塞生成流程
- 检索异常（向量模型加载失败）→ 降级为全量缺失，打印警告日志
- 项目未指定 → 跳过检查

---

## 模块②：引用增强生成器

**文件**: `api/citation_enhancer.py`

### 核心类

```python
class CitationEnhancer:
    def enhance_prompt(
        self,
        base_prompt: str,
        check_result: KnowledgeCheckResult,
        kb_only: bool = False,
    ) -> EnhancedPrompt:
        """在系统提示词中注入引用规则和知识清单"""

    def parse_citations_from_response(
        self, response: str
    ) -> tuple[str, list[Citation]]:
        """从 AI 响应中解析引用标注，返回(纯文本, 引用列表)"""
```

### 提示词注入规则

在系统提示词末尾追加：

```
## 引用规则（必须遵守）
1. 涉及项目已有设定的内容，必须标注来源：[参考：文件名]
2. 在已有设定上的合理扩展 → [基于：文件名]
3. AI 自行设计（知识库无此设定）→ [设计：AI自主设计]
4. 每章结束汇总本章引用来源清单
5. 若某设定与知识库不符但你认为应修改，标注 [建议修改] 并说明理由
```

知识清单则注入在 `【用户需求】` 之前。

### 引用解析

`parse_citations_from_response()` 使用正则提取 `[参考：...]`、`[基于：...]`、`[设计：...]`、`[建议修改]` 标注，并将 AI 输出中的标注去除（前端渲染不显示标注，只在元数据中透传）。

### 输出

```python
@dataclass
class Citation:
    claim: str           # 被引用的声明片段
    source: str | None   # 来源文件名，None 表示 AI 设计
    type: Literal["reference", "extension", "ai_design", "suggest_modify"]

@dataclass
class EnhancedPrompt:
    prompt: str          # 注入后的完整提示词
    citation_instruction: str  # 引用规则文本（仅用于记录）
```

### 引用率指标

```python
@dataclass
class CitationMetrics:
    total_claims: int
    referenced: int         # reference + extension
    ai_designed: int        # ai_design
    coverage: float         # referenced / total_claims
```

---

## 模块③：一致性检测器

**文件**: `api/consistency_checker.py`

### 核心类

```python
class ConsistencyChecker:
    def __init__(self, kb_project: KBProject, embedding_fn):
        self.kb = kb_project
        self.embedding_fn = embedding_fn

    def check(self, output: str) -> ConsistencyResult:
        """比对输出与知识库内容，检测矛盾"""

    def _detect_numeric_conflicts(self, para: str) -> list[Conflict]:
        """数值规则检测（正则提取数值 + 知识库比对）"""

    def _detect_constraint_conflicts(self, para: str) -> list[Conflict]:
        """约束关键词检测"""

    def _detect_semantic_conflicts(self, para: str) -> list[Conflict]:
        """语义相似度兜底检测"""

    def auto_fix(self, para: str, conflict: Conflict) -> str:
        """基于知识库自动修正矛盾段落（仅 HIGH 级别）"""
```

### 矛盾分级

| 级别 | 阈值 | 操作 |
|---|---|---|
| HIGH | 语义相似度 < 0.4 或数值直接矛盾 | 自动重写该段落 |
| MEDIUM | 0.4 ~ 0.7 或部分不一致 | 标记冲突位置，前端显示"建议修改" |
| LOW | 0.7 ~ 0.85 | 仅记录日志 |

### 输出

```python
@dataclass
class Conflict:
    level: Literal["high", "medium", "low"]
    paragraph: str
    kb_source: str        # 知识库原文
    source_file: str      # 来源文件名
    conflict_type: Literal["numeric", "constraint", "semantic"]
    fix_suggestion: str | None  # HIGH 级别的修正版本

@dataclass
class ConsistencyResult:
    conflicts: list[Conflict]
    auto_fixed_paragraphs: list[str]  # 被自动修正的段落
    score: float          # 0.0 ~ 1.0，一致性评分
```

### 与 PRDSelfCheck 集成

在 `prd_self_check.py` 中新增一个方法，在现有自检后调用 ConsistencyChecker：

```python
class PRDSelfCheck:
    def check_and_validate(self, response, kb_project) -> CheckResult:
        # 已有的格式检查
        format_result = self.check(response)
        # 新增的语义一致性检查
        if kb_project:
            consistency_result = ConsistencyChecker(kb_project).check(response)
            # 合并结果
        return CombinedResult(...)
```

---

## 模块④：知识提炼器

**文件**: `api/knowledge_extractor.py`

### 核心类

```python
class KnowledgeExtractor:
    def __init__(self, kb_project: KBProject, project_profile: dict):
        self.kb = kb_project
        self.profile = project_profile

    def extract(self, final_output: str, kb_entries: list) -> ExtractionResult:
        """从用户最终确认的版本中提取新知识"""

    def _is_project_knowledge(self, paragraph: str) -> bool:
        """判断段落是否包含有价值的项目设定"""
        # 规则: 包含数值、约束词、定义性陈述、术语定义
        # 排除: 通用描述、用户故事、AI 推理过程

    def _classify_paragraph(self, paragraph: str) -> str:
        """分类: 世界观/系统/数值/术语/规则"""

    def _extract_terminology(self, paragraph: str) -> tuple[str, str] | None:
        """提取术语定义，返回 (术语, 含义) 或 None"""

    def write_back(self, result: ExtractionResult) -> WriteBackSummary:
        """将新知识回写到知识库和项目画像"""
```

### 知识判据（什么算是"有价值的项目设定"）

```python
KNOWLEDGE_PATTERNS = [
    r"\d+%",                        # 百分比数值
    r"上限.*\d+|.*上限为\d+",      # 数值上限
    r"[不能禁止不可必须只能不得].+",  # 约束性陈述
    r"(?:指|定义为|称为|包括|分为|包含|由)",  # 定义性陈述
    r"简称.*|.*以下简称为",         # 术语定义
    r"等级[0-9]+.*|.*[0-9]+级时",  # 等级相关
]
```

### 输出

```python
@dataclass
class KnowledgeEntry:
    content: str
    category: str
    source: str = "AI生成提炼"
    confidence: float = 0.7
    is_draft: bool = False      # True 表示待确认

@dataclass
class ExtractionResult:
    entries: list[KnowledgeEntry]
    terminology_updates: dict[str, str]  # 目标项目画像

@dataclass
class WriteBackSummary:
    added_to_kb: int
    updated_profile: list[str]
    drafts: int               # 作为草稿的数量
```

### 写回策略

- 置信度 >= 0.7 且分类明确的 → 直接添加到知识库对应分类，以「【AI提炼】分类名」为文档标题
- 置信度 < 0.7 → 存为草稿（知识库内标记 pending_review），后续生成时作为参考但标注「待确认」
- 术语 → 合并到项目画像的 `terminology` 字段
- 去重 → 写回前用向量相似度检测是否与已有知识库条目重复，相似度 > 0.85 则跳过

---

## 前端适配

### useAI.ts 扩展

```typescript
interface CitationMeta {
  citations: Citation[]
  coverage: number
}

interface ConflictInfo {
  level: 'high' | 'medium' | 'low'
  paragraph: string
  fixSuggestion?: string
}

// imitation 和 iterate 的返回结果扩展
interface ImitationResult {
  content: string
  citations?: CitationMeta
  conflicts?: ConflictInfo[]
  consistencyScore?: number
}

// 新增 API：获取知识覆盖统计
async getKnowledgeCoverageStats(): Promise<{
  knowledgeCount: number       // 知识库条目数
  citationRate: number         // 引用率（近10次均值）
  consistencyScore: number     // 一致性评分
  missingTopics: string[]      // 常见的缺失主题
}>
```

### AIIterationPanel.vue 扩展

- 引用来源折叠面板：在输出下方显示「引用来源 N 条」，展开后列出每条声明的来源文件
- 冲突标记：MEDIUM 级别的冲突在对应段落旁显示 ⚠️ 图标，hover 显示知识库原文和建议
- 知识覆盖指标：在面板顶部显示引用率（如「引用知识库覆盖 67%」）

---

## 测试策略

### 单元测试

| 测试文件 | 测试内容 |
|---|---|
| `tests/test_knowledge_checker.py` | 知识分类正确性、空知识库、边缘阈值 |
| `tests/test_consistency_checker.py` | 数值冲突检测、约束关键词检测、语义冲突检测、自动修正 |
| `tests/test_knowledge_extractor.py` | 知识判据模式匹配、分类准确率、术语提取、去重检测 |
| `tests/test_citation_enhancer.py` | 提示词注入、引用解析、引用率计算 |

### 集成测试

在 `tests/test_ai_service.py` 中扩展：
- 带知识锚定的完整仿写流程测试
- 知识库为空时的降级行为
- 一致性检测与自检的集成

### 测试数据

- 模拟知识库：3~5 个已知条目覆盖各分类
- 模拟输出：含一致/冲突/缺失三种场景的 AI 输出
- 空知识库边界

---

## 不需要实现的内容（YAGNI）

- 用户行为偏好建模（如"用户喜欢多详细的输出"）—— 可后续方案 C 实现
- 多轮对话中的上下文压缩学习
- 跨项目的知识迁移（项目 A 学到的用到项目 B）
- 前端拖拽式引用编辑
- 知识图谱可视化
