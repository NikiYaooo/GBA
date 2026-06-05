"""api/citation_enhancer.py — 引用增强生成器。"""

import re
from dataclasses import dataclass
from typing import List, Tuple, Optional, Literal

from api.knowledge_checker import KnowledgeChecker, KnowledgeCheckResult


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
    r'\[(参考|基于|设计|建议修改)(?:[：:]\s*(.*?))?\]'
)


class CitationEnhancer:
    """在生成前增强提示词，生成后解析引用标注。"""

    def enhance_prompt(
        self, base_prompt: str, check_result: KnowledgeCheckResult, kb_only: bool = False
    ) -> str:
        """在 base_prompt 末尾注入引用规则，在知识清单不为空时追加知识清单。"""
        if not check_result.existing and not check_result.partial and not check_result.missing:
            return base_prompt

        extra_parts = [CITATION_RULES]

        knowledge_section = KnowledgeChecker.format_check_result(check_result)

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
            claim_start = max(0, start - 60)
            claim = response[claim_start:start].strip().split("\n")[-1][:30]

            tag_type = match.group(1)
            source = match.group(2).strip() if match.group(2) else None

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

            clean_parts.append(response[last_end:start])
            last_end = end

        clean_parts.append(response[last_end:])
        clean_text = "".join(clean_parts).strip()

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
