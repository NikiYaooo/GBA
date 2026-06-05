import os
import json
import re
import markdown
from typing import List, Dict, Optional
import httpx
from knowledge_base import KnowledgeBase
from prd_self_check import PRDSelfCheck


# 各模型的 API 地址映射
MODEL_ENDPOINTS = {
    "DeepSeek": "https://api.deepseek.com/v1/chat/completions",
    "豆包": "https://ark.cn-beijing.volces.com/api/v3/responses",
    "GPT": "https://api.openai.com/v1/chat/completions",
    "Gemini": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
    "Kimi": "https://api.moonshot.cn/v1/chat/completions",
    "GLM": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
    "Ollama (本地)": "http://localhost:11434/v1/chat/completions",
}

# 各模型允许的 temperature 值（None 表示使用默认值）
MODEL_TEMPERATURES = {
    "Kimi": 1.0,
}

# 增强系统提示词：角色定位 + Few-Shot + 约束
ENHANCED_SYSTEM_PROMPT = """你是资深游戏策划专家「张工」，拥有 15 年手游/端游全案策划经验，擅长撰写可落地、逻辑闭环的策划文档。

【角色定位】
- 你是一名严谨的系统策划，只写可落地的文档
- 每次输出前先检查：功能是否明确？数值是否合理？边界是否覆盖？
- 你的文档会被程序、美术、测试直接使用，必须精确、无歧义

【核心规则 - 必须遵守】
1. 禁止自创世界观、职业、玩法、数值体系 —— 必须严格基于知识库和用户需求中的内容生成
2. 如果知识库中有冲突的设定，优先遵循知识库版本，并在文档中标注「✓ 已对齐: XXXX」
3. 数值必须明确、可验证（如「钻石×100，每日限购1次」而非「给一些钻石」）
4. 严格参考提供的【文档模板】格式，包括标题层级、表格样式、条目结构
5. 不准使用模糊表述（大概、可能、若干、适量、一些）
6. 必须包含：背景/目标、规则/流程、奖励/数值、限制/条件、UI/交互 等标准章节

【输出格式要求】
- 使用 Markdown 格式输出
- 章节层级：## 一级标题 → ### 二级标题 → 条目式正文
- 关键数值、规则条件加粗
- 表格用于奖励表、数值表

【Few-Shot 示例】
以下是一个符合要求的策划案片段示例：
```
## 签到活动
### 活动规则
1. 活动持续 7 天，玩家每日登录可签到 1 次；
2. 签到奖励通过邮件发放，有效期 24 小时；
3. 漏签不可补签，但累计签到 7 天可获得额外大奖。

### 奖励表
| 天数 | 奖励内容 | 数量 | 是否可叠加 |
|------|----------|------|-----------|
| 第1天 | 金币 | ×5000 | - |
| 第2天 | 钻石 | ×50 | - |
| 第3天 | 装备强化石 | ×3 | - |
| 第7天 | SSR 角色碎片 | ×10 | - |

### 限制条件
- 每日签到重置时间：05:00（服务器时间）
- 每个角色仅可参与 1 次
- 活动界面入口：主界面 → 活动 → 签到
```
"""


class AIService:
    """
    负责集成多个 AI 模型，并处理 RAG + PRD 自检逻辑
    """

    def __init__(self, kb: KnowledgeBase = None, data_dir: str = None):
        self.kb = kb
        self.checker = PRDSelfCheck(data_dir) if data_dir else None

    def _get_config(self) -> dict:
        data_dir = os.environ.get("GB_DATA_DIR", "")
        if data_dir:
            config_path = os.path.join(data_dir, "config.json")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    return json.load(f)

        app_data = os.environ.get("APPDATA")
        if not app_data:
            app_data = os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
        target_dir = os.path.join(app_data, "GameBuilderAIHelper")
        config_path = os.path.join(target_dir, "config.json")

        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"models": {}}

    async def _call_api(self, model_name: str, messages: List[Dict[str, str]]) -> str:
        config = self._get_config()
        model_config = config.get("models", {}).get(model_name, {})

        api_key = model_config.get("apiKey", "")
        model_id = model_config.get("modelId", "")

        # Ollama：本地调用
        if model_name == "Ollama (本地)":
            base_url = model_id.strip() or "http://localhost:11434"
            ollama_url = f"{base_url.rstrip('/')}/api/chat"
            ollama_messages = [{"role": m["role"], "content": m["content"]} for m in messages]
            try:
                async with httpx.AsyncClient(timeout=180) as client:
                    resp = await client.post(
                        ollama_url,
                        json={"model": "llama3", "messages": ollama_messages, "stream": False},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        return data.get("message", {}).get("content", "") or data.get("response", "")
                    return f"Ollama 请求失败 (HTTP {resp.status_code}): {resp.text[:200]}"
            except Exception as e:
                return f"Ollama 调用失败: {str(e)}"

        # 云模型：需要 API Key
        if not api_key:
            return (
                f"【{model_name}】未配置 API Key\n"
                f"请前往左下角「设置」→「AI 模型配置」中填写 {model_name} 的 API Key。"
            )

        endpoint = MODEL_ENDPOINTS.get(model_name, "")
        if not endpoint:
            return f"不支持的模型: {model_name}"

        temperature = MODEL_TEMPERATURES.get(model_name, 0.3)

        # 豆包使用 Responses API（与 OpenAI 标准格式不同）
        if model_name == "豆包":
            body = {
                "model": model_id or model_name.lower(),
                "input": [],
            }
            for msg in messages:
                role = msg["role"]
                content = msg["content"]
                if isinstance(content, str):
                    input_item = {
                        "role": role,
                        "content": [{"type": "input_text", "text": content}]
                    }
                elif isinstance(content, list):
                    converted_parts = []
                    for part in content:
                        if part.get("type") == "text":
                            converted_parts.append({"type": "input_text", "text": part["text"]})
                        elif part.get("type") == "image_url":
                            converted_parts.append({
                                "type": "input_image",
                                "image_url": part["image_url"]["url"]
                            })
                        else:
                            converted_parts.append(part)
                    input_item = {"role": role, "content": converted_parts}
                else:
                    input_item = {"role": role, "content": [{"type": "input_text", "text": str(content)}]}
                body["input"].append(input_item)

            if temperature is not None:
                body["temperature"] = temperature
            body["max_output_tokens"] = 4096

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            try:
                async with httpx.AsyncClient(timeout=300) as client:
                    resp = await client.post(endpoint, json=body, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        output = data.get("output", [])
                        if output:
                            for out_msg in reversed(output):
                                if out_msg.get("role") == "assistant":
                                    content_parts = out_msg.get("content", [])
                                    texts = [p.get("text", "") for p in content_parts if p.get("type") == "output_text" or p.get("text")]
                                    if texts:
                                        return "".join(texts)
                        return str(data)
                    return f"API 请求失败 (HTTP {resp.status_code}): {resp.text[:300]}"
            except httpx.ConnectError:
                return f"无法连接到 {model_name} 的 API 服务器，请检查网络连接和 API 地址配置"
            except httpx.TimeoutException:
                return f"{model_name} API 请求超时，请稍后重试"
            except Exception as e:
                return f"API 调用异常: {str(e)}"

        # 其他模型使用 OpenAI 标准格式
        body = {
            "model": model_id or model_name.lower(),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 4096,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=300) as client:
                resp = await client.post(endpoint, json=body, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "")
                    return str(data)
                return f"API 请求失败 (HTTP {resp.status_code}): {resp.text[:300]}"
        except httpx.ConnectError:
            return f"无法连接到 {model_name} 的 API 服务器，请检查网络连接和 API 地址配置"
        except httpx.TimeoutException:
            return f"{model_name} API 请求超时，请稍后重试"
        except Exception as e:
            return f"API 调用异常: {str(e)}"

    def _md_to_html(self, text: str) -> str:
        if re.search(r'<(h[1-6]|p|div|table|ul|ol|strong|em)[^>]*>', text):
            return text
        text = re.sub(r'\n{4,}', '\n\n', text)
        html = markdown.markdown(text, extensions=['extra', 'tables', 'fenced_code', 'codehilite'])
        html = re.sub(r'<p>\s+', '<p>', html)
        html = re.sub(r'\s+</p>', '</p>', html)
        html = re.sub(r'<br\s*/?>\s*<br\s*/?>', '<br>', html)
        return html.strip()

    def _parse_sections(self, html: str) -> list:
        """将 HTML 文档按 h2/h3 标题解析为章节列表。
        返回: [{title, level, content_html, content_text}, ...]
        """
        import re
        if not html:
            return []
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

    async def quality_check(self, model: str, doc_content: str, system_prompt: str = None) -> str:
        if not system_prompt:
            system_prompt = "你是一名资深游戏策划专家，请对用户提供的策划文档进行严格质检。检查逻辑矛盾、信息缺失、边界遗漏、文案模糊、落地性和规范问题。请输出：风险等级、问题原文、分析、修改建议。"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请质检以下文档内容：\n\n{doc_content}"}
        ]
        return await self._call_api(model, messages)

    async def imitate(self, model: str, requirements: str, doc_content: str, use_rag: bool = True, output_format: str = "markdown", template_content: str = "", images: list = None, project_id: str = "", kb_only: bool = False, cite_sources: bool = False) -> dict:
        """增强版智能仿写：多分类 RAG + 知识约束 + 模板强制 + 自检重写 + 优化提示词"""

        # ======== Step 0: 判断是否启用流水线模式 ========
        use_pipeline = len(requirements) > 200 or "分节" in requirements or "大纲" in requirements
        knowledge_check_result = None
        kb_project = None
        consistency_result = None

        if use_pipeline:
            outline = await self._generate_outline(requirements, model, project_id)
            if outline and len(outline) >= 3:
                sections_html = await self._generate_sections(
                    outline, model, requirements, project_id, template_content
                )
                response = await self._merge_document(outline, sections_html)
            else:
                use_pipeline = False

        # ======== 非流水线模式：原有流程 ========
        if not use_pipeline:
            # ======== Step 1: 多分类 RAG 检索 ========
            rag_contexts = {}
            if use_rag and self.kb:
                if project_id:
                    proj = self.kb.get_project(project_id)
                    if proj:
                        rag_contexts = proj.search_by_categories(
                            requirements,
                            categories=["世界观", "系统", "数值", "模板", "规范", "UI"],
                            top_k_per_category=3,
                        )
                else:
                    rag_contexts = self.kb.search_by_categories(
                        requirements,
                        categories=["世界观", "系统", "数值", "模板", "规范", "UI"],
                        top_k_per_category=3,
                    )

            # ======== Knowledge Check ========
            if project_id and self.kb:
                kb_project = self.kb.get_project(project_id)
            if kb_project:
                from api.knowledge_checker import KnowledgeChecker
                kc = KnowledgeChecker(kb_project)
                knowledge_check_result = kc.check(requirements)

            # ======== Step 2: 构建知识约束和 RAG 上下文 ========
            knowledge_sections = []
            constraint_notes = []

            if rag_contexts:
                for cat in ["世界观", "系统", "数值", "规范"]:
                    items = rag_contexts.get(cat, [])
                    if items:
                        section = f"【{cat} - 项目已有设定（必须遵守，不得自创）】\n"
                        for i, item in enumerate(items):
                            meta = item.get("metadata", {})
                            source = meta.get("filename", "未知")
                            section += f"[来源: {source}]\n{item.get('content', '')}\n\n"
                        knowledge_sections.append(section)
                        constraint_notes.append(f"- 本项目的{cat}已有明确设定，必须在这些设定范围内生成，不得自创新设定")

                # PRD 模板类别的检索结果用于格式参考
                template_items = rag_contexts.get("模板", [])
                ui_items = rag_contexts.get("UI", [])

            # 如果用户提供了文档模板，优先使用
            user_template = template_content

            # 近期历史问题提醒
            recent_issues = ""
            if self.checker:
                recent_issues = self.checker.get_recent_issues()

            # ======== Step 3: 构建用户提示词 ========
            user_prompt_parts = []

            # 3a: 知识约束
            if constraint_notes:
                user_prompt_parts.append("【项目已有设定约束 - 必须遵守】")
                user_prompt_parts.extend(constraint_notes)
                user_prompt_parts.append("")

            # 3b: 插入分类 RAG 知识
            for sec in knowledge_sections:
                user_prompt_parts.append(sec)

            # 3c: 模板参考 — 检测是否为 HTML 模板
            template_is_html = bool(user_template and re.search(r'</?(h[1-6]|p|div|table|tr|td|th|ul|ol|li|br|span|strong|em)>', user_template))
            if user_template:
                fmt = "HTML" if template_is_html else "Markdown"
                user_prompt_parts.append(f"【文档模板 - 必须严格按此模板的格式、章节结构、标题层级、样式风格生成】\n{user_template}\n")
                user_prompt_parts.append(f"【格式要求】模板为 {fmt} 格式，请使用相同的 {fmt} 格式输出，严格遵循模板的标签层级和样式。\n")

            # 3d: 用户需求
            user_prompt_parts.append(f"【用户需求】\n{requirements}\n")

            # 3e: 当前文档参考
            if doc_content:
                user_prompt_parts.append(f"【当前参考的文档内容】\n{doc_content}\n")

            # 3f: 近期历史问题
            if recent_issues:
                user_prompt_parts.append(recent_issues)

            # 3g: 输出指令
            fmt_name = "HTML" if template_is_html else "Markdown"
            user_prompt_parts.append(f"请严格按照以上所有约束和模板，输出完整、可执行、逻辑闭环的游戏策划文档（{fmt_name} 格式）。")

            user_text = "\n".join(user_prompt_parts)

            # ======== Step 4: 构建 messages（支持多模态） ========
            system_prompt = ENHANCED_SYSTEM_PROMPT
            if template_is_html:
                system_prompt = system_prompt.replace(
                    "【输出格式要求】\n- 使用 Markdown 格式输出",
                    "【输出格式要求】\n- 使用 HTML 格式输出，严格遵循提供的 HTML 模板中的标签结构"
                )
            if kb_only:
                system_prompt += """

        【额外约束 - 仅基于知识库】
        你只能使用上面提供的「项目已有设定」内容来生成文档。如果知识库中没有相关信息，请明确说明「知识库中无此设定，无法生成」。严禁编造任何知识库中没有的世界观、系统、数值、角色、玩法等内容。"""

            # ======== Citation Enhancement ========
            if knowledge_check_result:
                from api.citation_enhancer import CitationEnhancer
                ce = CitationEnhancer()
                system_prompt = ce.enhance_prompt(system_prompt, knowledge_check_result, kb_only)

            messages = [{"role": "system", "content": system_prompt}]

            vision_models = {"GPT", "Gemini"}
            has_images = images and len(images) > 0

            if has_images and model in vision_models:
                vision_content = []
                vision_content.append({"type": "text", "text": user_text})
                max_images = min(len(images), 6)
                for i in range(max_images):
                    vision_content.append({
                        "type": "image_url",
                        "image_url": {"url": images[i]}
                    })
                if len(images) > 6:
                    vision_content.append({"type": "text", "text": f"\n（注：用户还上传了 {len(images) - 6} 张原型图未展示）"})
                messages.append({"role": "user", "content": vision_content})
            else:
                if has_images:
                    user_text += f"\n\n（用户上传了 {len(images)} 张系统原型图。当前模型不支持直接看图，请根据需求描述和原型图标题推测需求。）"
                messages.append({"role": "user", "content": user_text})

            # ======== Step 5: 首次生成 ========
            response = await self._call_api(model, messages)

            # 检查是否生成了有效内容
            if not response or len(response.strip()) < 50:
                # 生成失败，尝试简化重试
                retry_msg = [
                    {"role": "system", "content": "你是资深游戏策划专家。请根据用户需求生成游戏策划文档。"},
                    {"role": "user", "content": f"请为以下需求生成一份完整的游戏策划文档：\n{requirements}\n\n要求：结构完整，包含背景、规则、奖励、限制等标准章节。"}
                ]
                response = await self._call_api(model, retry_msg)

            if not response:
                response = ""

            # ======== Step 6: 自检 + 重写循环 ========
            if self.checker and response and len(response) > 50:
                check_result = self.checker.check(response, rag_contexts)
                max_rewrite_attempts = 1  # 最多重写 1 次
                rewrite_attempt = 0

                while not check_result["passed"] and rewrite_attempt < max_rewrite_attempts:
                    rewrite_attempt += 1
                    # 记录失败原因
                    self.checker.log_rewrite(check_result["reasons"], model)

                    # 构建改写提示
                    feedback_text = "【PRD 自检未通过，需要进行修订。以下是需要修正的问题】\n"
                    for reason in check_result["reasons"]:
                        feedback_text += f"- {reason}\n"
                    feedback_text += "\n请根据以上反馈修正文档，保留原有正确内容，仅修正问题。输出修正后的完整文档。\n"

                    rewrite_messages = [
                        {"role": "system", "content": "你是资深游戏策划专家，正在修订一份 PRD 文档。请根据反馈修正问题，输出完整修订版。"},
                        {"role": "user", "content": f"【原始文档】\n{response}\n\n{feedback_text}"}
                    ]
                    new_response = await self._call_api(model, rewrite_messages)

                    if new_response and len(new_response) > 50:
                        response = new_response
                        # 重写后再次检查
                        check_result = self.checker.check(response, rag_contexts)
                    else:
                        break  # 重写失败，保留原版

            # ======== Consistency Check ========
            if kb_project and response:
                from api.consistency_checker import ConsistencyChecker
                cc = ConsistencyChecker(kb_project)
                consistency_result = cc.check(response)
                if consistency_result.score < 0.6 and self.checker:
                    self.checker.log_rewrite(
                        [f"一致性评分{consistency_result.score}，发现{len(consistency_result.conflicts)}处冲突"],
                        model
                    )

        # ======== Step 7: 添加标注并格式化 ========
        rag_contexts = rag_contexts if not use_pipeline else {}
        has_images = images and len(images) > 0

        prefix_parts = []
        if rag_contexts:
            prefix_parts.append("*(已应用 RAG 知识库检索增强)*")
        if has_images:
            prefix_parts.append("*(已参考上传的系统原型图)*")
        if prefix_parts:
            response = " ".join(prefix_parts) + "\n\n" + response

        if cite_sources and rag_contexts:
            # 收集所有引用的文档来源
            sources = set()
            for cat_items in rag_contexts.values():
                for item in cat_items:
                    meta = item.get("metadata", {})
                    fname = meta.get("filename", "") if isinstance(meta, dict) else ""
                    if fname:
                        sources.add(fname)
            if sources:
                citation_section = "\n\n---\n**引用来源：**\n"
                for s in sorted(sources):
                    citation_section += f"- {s}\n"
                response += citation_section

        if output_format == "html":
            response = self._md_to_html(response)

        return {
            "content": response,
            "knowledge_coverage": round(knowledge_check_result.coverage_ratio, 2) if knowledge_check_result else None,
            "consistency_score": consistency_result.score if consistency_result is not None else None,
            "conflicts": [
                {
                    "level": c.level,
                    "paragraph": c.paragraph[:100],
                    "suggestion": c.fix_suggestion or "",
                    "source_file": c.source_file,
                }
                for c in (consistency_result.conflicts if consistency_result else [])
            ],
        }

    async def imitate_iterate(
        self, model: str, full_doc: str, instruction: str,
        mode: str = "section", target_section: str = "",
        selection_context: dict = None,
        project_id: str = "",
        template_content: str = "",
    ) -> str:
        """多轮迭代修改。返回替换内容（HTML）。"""
        sections = self._parse_sections(full_doc)
        if not sections:
            mode = "full"

        system_prompt = "你是资深游戏策划「张工」，正在修订一份 PRD 文档。你只输出修改后的目标内容，不输出其他内容。保持与原文一致的格式和风格。严格遵循项目已有的设定，不自创。"

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

        rag_context = ""
        if project_id and self.kb:
            proj = self.kb.get_project(project_id)
            if proj:
                results = proj.search(instruction, top_k=3)
                if results:
                    rag_context = "\n".join(
                        f"[来源: {r['metadata'].get('filename', '')}] {r['content']}"
                        for r in results
                    )
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

    async def _generate_outline(self, requirements: str, model: str = "DeepSeek", project_id: str = "") -> list:
        """生成文档大纲。返回 [{title, desc}, ...]"""
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

        response = await self._call_api(model, messages)
        import json, re
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                data = json.loads(json_match.group())
                return data.get("sections", [])
            except json.JSONDecodeError:
                pass
        return [{"title": "概述", "desc": ""}, {"title": "规则", "desc": ""}, {"title": "奖励", "desc": ""}]

    async def _generate_sections(
        self, outline: list, model: str, requirements: str,
        project_id: str = "", template_content: str = ""
    ) -> list:
        """逐节生成（并行）。返回 [html_string, ...]"""
        import asyncio
        profile = self._load_project_profile()
        profile_text = self._build_profile_constraint(profile) if profile.get("game_name") else ""

        async def gen_section(sec: dict) -> str:
            title = sec["title"]
            user_parts = []

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

            template_is_html = bool(template_content and re.search(r'</?(h[1-6]|p|div|table|tr|td|th|ul|ol|li|br|span|strong|em)>', template_content))

            if template_content:
                user_parts.append(f"【文档模板参考】\n{template_content}\n")

            fmt_name = "HTML" if template_is_html else "Markdown"
            user_parts.append(f"请生成「{title}」章节的内容，使用 {fmt_name} 格式。只输出该章节内容，不要输出标题。")

            system = ENHANCED_SYSTEM_PROMPT
            if template_is_html:
                system = system.replace(
                    "【输出格式要求】\n- 使用 Markdown 格式输出",
                    "【输出格式要求】\n- 使用 HTML 格式输出，严格遵循提供的 HTML 模板中的标签结构"
                )
            if profile_text:
                system += f"\n\n【项目画像 - 必须遵守】\n{profile_text}"

            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": "\n".join(user_parts)},
            ]
            return await self._call_api(model, messages)

        tasks = [gen_section(sec) for sec in outline]
        sections_html = await asyncio.gather(*tasks)
        return sections_html

    async def _merge_document(self, outline: list, sections_html: list) -> str:
        """合并章节为完整文档。"""
        parts = []
        for sec, html in zip(outline, sections_html):
            if not html or len(html.strip()) < 5:
                continue
            parts.append(f"<h2>{sec['title']}</h2>\n{html}")
        full_doc = "\n".join(parts)

        if self.checker:
            try:
                issues = self.checker.check_consistency(full_doc)
                if issues:
                    notes = "\n".join(f"- {issue}" for issue in issues[:5])
                    full_doc += f"\n\n<hr><p><strong>⚠️ 一致性检查提醒</strong></p><ul>{notes}</ul>"
            except Exception:
                pass

        return full_doc

    async def complete_logic(self, model: str, doc_content: str, project_id: str = "") -> str:
        system_prompt = "你是一名细节严谨的游戏系统策划。请为用户的半成品/草稿文档补全缺失的标准章节（如背景、目标、流程、规则、奖励、限制、异常等），补齐边界场景、容错逻辑、互斥规则。不要篡改用户原有核心需求，仅做补充和规范化。"

        rag_context = ""
        if self.kb:
            query = doc_content[:200] if len(doc_content) > 200 else doc_content
            search_results = []
            if project_id:
                proj = self.kb.get_project(project_id)
                if proj:
                    search_results = proj.search(query, top_k=2)
            else:
                search_results = self.kb.search(query, top_k=2)
            if search_results:
                rag_context = "【参考的历史项目标准模板/边界规则】：\n"
                for res in search_results:
                    rag_context += res['content'] + "\n\n"

        user_prompt = ""
        if rag_context:
            user_prompt += rag_context

        user_prompt += f"【需要补完的草稿文档】：\n{doc_content}\n\n请输出补完后的完整文档，并在补充的部分做出标记（如加粗或引用）："

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response = await self._call_api(model, messages)

        if rag_context:
            response = "*(已应用 RAG 参考项目标准模板补完)*\n\n" + response

        return response

    async def generate_ui_images(self, model: str, doc_content: str, design_prompt: str, n: int = 4) -> dict:
        config = self._get_config()
        model_config = config.get("models", {}).get(model, {})
        api_key = model_config.get("apiKey", "")

        if not api_key:
            model_config = config.get("models", {}).get("GPT", {})
            api_key = model_config.get("apiKey", "")

        if not api_key:
            return {"success": False, "message": f"{model} 未配置 API Key，无法生成图片"}

        import re as _re
        clean_content = _re.sub(r'<[^>]+>', ' ', doc_content)
        clean_content = _re.sub(r'\s+', ' ', clean_content).strip()
        doc_excerpt = clean_content[:1500]

        prompt = f"{design_prompt}\n\n文档描述：{doc_excerpt}"

        endpoint = "https://api.openai.com/v1/images/generations"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": "dall-e-3",
            "prompt": prompt,
            "n": 1,
            "size": "1024x1024",
            "response_format": "b64_json",
        }

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                images = []
                for i in range(n):
                    try:
                        resp = await client.post(endpoint, json=body, headers=headers)
                        if resp.status_code == 200:
                            data = resp.json()
                            for item in data.get("data", []):
                                b64 = item.get("b64_json", "")
                                if b64:
                                    images.append({
                                        "index": len(images),
                                        "data_uri": f"data:image/png;base64,{b64}",
                                        "revised_prompt": item.get("revised_prompt", ""),
                                    })
                        else:
                            err_msg = resp.text[:200]
                            if i == 0:
                                return {"success": False, "message": f"图片生成失败 (HTTP {resp.status_code}): {err_msg}"}
                    except Exception as e:
                        if i == 0:
                            return {"success": False, "message": f"图片生成请求失败: {str(e)}"}

                if not images:
                    return {"success": False, "message": "图片生成失败，未返回有效数据"}

                return {"success": True, "data": {"images": images}}
        except Exception as e:
            return {"success": False, "message": f"图片生成失败: {str(e)}"}
