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
        self.thresholds = {"existing": 0.03, "partial": 0.01}

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
            content = item.get("content", "")
            similarity = item.get("score", 0.0)
            meta = item.get("metadata", {}) or {}
            source = meta.get("filename", "") if isinstance(meta, dict) else ""
            category = meta.get("category", "通用") if isinstance(meta, dict) else "通用"

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

        return missing[:5]

    def format_check_result(self, result: KnowledgeCheckResult) -> str:
        """将检查结果格式化为提示词中的两个区块。"""
        parts = []

        if result.existing:
            parts.append("## 本项目已有设定（必须遵守）")
            for item in result.existing:
                parts.append(f"- {item.content} [来源：{item.source or '知识库'}]")
            parts.append("")

        if result.partial:
            parts.append("## 本项目已有部分相关内容（可作为参考）")
            for item in result.partial:
                parts.append(f"- {item.content} [来源：{item.source or '知识库'}，相似度：{item.similarity:.1%}]")
            parts.append("")

        if result.missing:
            parts.append("## 知识库未覆盖的内容（需自行设计）")
            for item in result.missing:
                parts.append(f"- {item.topic}：{item.suggestion}")
            parts.append("")

        return "\n".join(parts)
