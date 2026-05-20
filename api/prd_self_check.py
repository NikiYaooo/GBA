import os
import json
import time
from typing import List, Dict, Any, Optional


class PRDSelfCheck:
    """PRD 自检校验 + 重写追踪模块。

    职责：
    - 检查生成文档的完整性、逻辑一致性、数值合理性
    - 记录每次不合理原因，后续生成时作为参考
    """

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.log_path = os.path.join(data_dir, "prd_check_log.json")
        self._load_log()

    def _load_log(self):
        if os.path.exists(self.log_path):
            try:
                with open(self.log_path, "r", encoding="utf-8") as f:
                    self.history = json.load(f)
            except Exception:
                self.history = []
        else:
            self.history = []

    def _save_log(self):
        try:
            with open(self.log_path, "w", encoding="utf-8") as f:
                json.dump(self.history[-200:], f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get_warnings(self) -> List[str]:
        """返回最近 20 条历史警告/原因摘要，用于增强提示词。"""
        if not self.history:
            return []
        recent = self.history[-20:]
        warnings = set()
        for entry in recent:
            for r in entry.get("reasons", []):
                if len(r) < 100:
                    warnings.add(r)
        return list(warnings)[-10:]

    def check(self, content: str, kb_contexts: Dict[str, List[Dict]] = None) -> Dict[str, Any]:
        """执行 PRD 自检。

        返回:
        {
            "passed": bool,
            "reasons": List[str],
            "details": { "completeness": [...], "contradictions": [...], "numerical": [...] }
        }
        """
        reasons = []
        details = {"completeness": [], "contradictions": [], "numerical": []}

        # 1. 完整性检查：必备章节
        required_sections = [
            "背景", "目标", "概述",
            "规则", "流程",
            "奖励", "奖励表",
            "限制", "条件",
            "界面", "UI",
        ]
        content_lower = content.lower()
        missing = [s for s in required_sections if s.lower() not in content_lower]
        if missing:
            msg = f"缺少以下标准章节: {'、'.join(missing[:6])}"
            if len(missing) > 6:
                msg += f" 等 {len(missing)} 项"
            reasons.append(msg)
            details["completeness"].append(msg)

        # 2. 检查内容长度是否过短
        word_count = len(content)
        if word_count < 200:
            msg = f"文档内容过短（{word_count} 字），可能不完整"
            reasons.append(msg)
            details["completeness"].append(msg)

        # 3. 与知识库对比检查矛盾
        if kb_contexts:
            for cat, chunks in kb_contexts.items():
                for chunk in chunks:
                    chunk_text = chunk.get("content", "")
                    if not chunk_text or len(chunk_text) < 10:
                        continue
                    # 提取知识库中的关键专有名词/数值
                    kb_terms = self._extract_terms(chunk_text)
                    # 检查文档是否包含了与知识库冲突的内容
                    conflicts = self._find_conflicts(content, chunk_text, kb_terms)
                    if conflicts:
                        for c in conflicts:
                            reasons.append(f"[与{cat}冲突] {c}")
                            details["contradictions"].append(c)

        # 4. 数值合理性检查
        num_issues = self._check_numerical(content)
        if num_issues:
            reasons.extend(num_issues)
            details["numerical"] = num_issues

        return {
            "passed": len(reasons) == 0,
            "reasons": reasons,
            "details": details,
        }

    def _extract_terms(self, text: str) -> set:
        """从知识库文本中提取可能的关键专有名词（连续中文词 >= 2 字）。"""
        import re
        words = set()
        # 提取可能的专有名词：连续中文字符 >= 2
        for match in re.finditer(r'[一-鿿]{2,10}', text):
            word = match.group()
            if len(word) >= 2:
                words.add(word)
        # 提取数字+单位组合
        for match in re.finditer(r'\d+[一-鿿%]', text):
            words.add(match.group())
        return words

    def _find_conflicts(self, doc: str, kb_text: str, kb_terms: set) -> List[str]:
        """检查文档中是否有与知识库矛盾的内容。"""
        conflicts = []
        doc_lower = doc.lower()

        # 检查知识库中的否定式表述（"不包含"、"禁止"、"不能"等）
        import re
        neg_patterns = re.finditer(r'(不能|不可|禁止|不包含|不允许|扣[除减]|减少|上限|下限|最高|最低)\s*[：:]\s*([^\n。]{2,30})', kb_text)
        for m in neg_patterns:
            constraint = m.group(0).strip()
            # 提取关键部分检查文档是否违反
            key_part = m.group(2).strip()
            if key_part and len(key_part) > 2:
                # 检查文档中是否有与约束相反的表述
                opposite_patterns = [
                    f"增加{key_part}", f"添加{key_part}", f"包含{key_part}",
                    f"可以{key_part}", f"允许{key_part}",
                ]
                for opp in opposite_patterns:
                    if opp.lower() in doc_lower:
                        conflicts.append(f"知识库规定「{constraint}」，但文档中提及了「{opp}」")
                        break

        return conflicts

    def _check_numerical(self, content: str) -> List[str]:
        """检查数值相关的合理性问题。"""
        import re
        issues = []

        # 检查异常大的数值
        large_nums = re.finditer(r'(\d{5,})(\s*)(次|个|元|块|金|钻|币|点|分|%)', content)
        for m in large_nums:
            num = int(m.group(1))
            unit = m.group(3)
            if unit in ('次', '个') and num > 100000:
                issues.append(f"数值「{num}{unit}」可能过大，请确认是否合理")
            elif unit in ('元', '块', '金', '钻', '币') and num > 10000000:
                issues.append(f"数值「{num}{unit}」可能过大，请确认是否合理")

        # 检查概率之和
        probs = re.findall(r'(\d+\.?\d*)\s*%', content)
        if len(probs) >= 3:
            try:
                total = sum(float(p) for p in probs)
                if total > 150:
                    issues.append(f"多个概率值之和为 {total:.0f}%，可能超过 100%")
            except ValueError:
                pass

        return issues

    def check_consistency(self, content: str) -> list:
        """轻量级规则一致性检查（不调 AI）。返回问题列表。"""
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

    def log_rewrite(self, reasons: List[str], model: str):
        """记录一次重写的原因，用于后续增强提示词。"""
        entry = {
            "timestamp": int(time.time()),
            "model": model,
            "reasons": reasons,
        }
        self.history.append(entry)
        self._save_log()

    def get_recent_issues(self, limit: int = 5) -> str:
        """获取最近需注意的问题摘要，用于提示词。"""
        warnings = self.get_warnings()
        if not warnings:
            return ""
        return "【近期仿写需注意的问题】\n" + "\n".join(f"- {w}" for w in warnings[:limit])
