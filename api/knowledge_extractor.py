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

            term_result = self._extract_terminology(para)
            if term_result:
                term, meaning = term_result
                terminology[term] = meaning

        return ExtractionResult(entries=entries, terminology_updates=terminology)

    def _is_project_knowledge(self, paragraph: str) -> bool:
        if len(paragraph) < 6 or len(paragraph) > 300:
            return False

        generic = re.compile(
            r'^(这是一个|这是一款|玩家可以|游戏将|我们设计了|综上所述|总之|以下是一些|以下是关于|以下内容)',
        )
        if generic.match(paragraph):
            return False

        for pattern, _ in KNOWLEDGE_PATTERNS:
            if pattern.search(paragraph):
                return True

        return False

    def _is_duplicate(self, paragraph: str, kb_entries: list) -> bool:
        for entry in kb_entries:
            existing = entry.get("text", "") if isinstance(entry, dict) else str(entry)
            if len(existing) > 5 and paragraph[:20] in existing:
                return True
        return False

    def _classify_paragraph(self, paragraph: str) -> str:
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
        score = 0.7

        if re.search(r'\d+', paragraph):
            score += 0.1
        if re.search(r'(上限|下限|不能|必须|禁止)', paragraph):
            score += 0.1
        if len(paragraph) > 150:
            score -= 0.1
        if len(paragraph) < 15:
            score -= 0.1

        return max(0.3, min(1.0, round(score, 2)))

    def _extract_terminology(self, paragraph: str) -> Optional[Tuple[str, str]]:
        # 先尝试具体的 "以下将X简称为Y" 模式（更精确）
        alt = re.search(r'以下将[「""]?([^」""\s]+)[」""]?简称为[「""]?([^」""\s]+)[」""]?', paragraph)
        if alt:
            return (alt.group(2), alt.group(1))

        # 再尝试带括号的通用模式: ...称为「术语」
        match = TERMINOLOGY_PATTERN.search(paragraph)
        if match:
            term = match.group(1).strip()
            before = paragraph[:match.start()].strip()
            words = re.findall(r'[一-鿿]+', before)
            meaning = words[-1] if words else ""
            return (term, meaning)

        return None

    def write_back(self, result: ExtractionResult) -> WriteBackSummary:
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
