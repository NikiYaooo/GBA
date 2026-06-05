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
# 注意：前缀后可选的空格和 + 号（如 "上限为+15"、"上限为 50%"）
NUMERIC_PATTERN = re.compile(r'(上限为|下限为|上限|下限|消耗|为|)\s*\+?(\d{1,6})([%+]?)')

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
            conflicts.extend(self._detect_numeric_conflicts(para))
            conflicts.extend(self._detect_constraint_conflicts(para))

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

        try:
            kb_results = self.kb.search(para[:80], top_k=3)
        except Exception:
            return conflicts

        for prefix, value, suffix in numbers:
            if not prefix:
                continue
            for kb_item in kb_results:
                kb_text = kb_item.get("content", "")
                meta = kb_item.get("metadata", {}) or {}
                source_file = meta.get("filename", "") if isinstance(meta, dict) else ""

                if prefix not in kb_text:
                    continue
                # 确保上下文重叠：输出段落和知识库文本共享主题词
                if not self._has_context_overlap(para, kb_text):
                    continue

                kb_numbers = NUMERIC_PATTERN.findall(kb_text)
                for kb_prefix, kb_value, kb_suffix in kb_numbers:
                    if kb_prefix == prefix and value != kb_value:
                        conflicts.append(Conflict(
                            level="high",
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
            kb_text = kb_item.get("content", "")
            meta = kb_item.get("metadata", {}) or {}
            source_file = meta.get("filename", "") if isinstance(meta, dict) else ""

            for kw in CONSTRAINT_KEYWORDS:
                if kw in kb_text:
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
        return a_neg != b_neg

    def _has_context_overlap(self, para: str, kb_text: str) -> bool:
        """检查输出段落与知识库文本是否有主题词重叠，避免跨概念误报。"""
        # 提取有意义的上下文词（2+ 中文字符的词）
        para_words = set(re.findall(r'[一-鿿]{2,}', para))
        kb_words = set(re.findall(r'[一-鿿]{2,}', kb_text))
        # 排除通用的数值前缀词，这些词本身不能代表主题
        generic_prefixes = {"上限", "下限", "上限为", "下限为", "消耗", "为"}
        meaningful = (para_words & kb_words) - generic_prefixes
        return len(meaningful) >= 1
