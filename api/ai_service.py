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

    async def quality_check(self, model: str, doc_content: str, system_prompt: str = None) -> str:
        if not system_prompt:
            system_prompt = "你是一名资深游戏策划专家，请对用户提供的策划文档进行严格质检。检查逻辑矛盾、信息缺失、边界遗漏、文案模糊、落地性和规范问题。请输出：风险等级、问题原文、分析、修改建议。"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请质检以下文档内容：\n\n{doc_content}"}
        ]
        return await self._call_api(model, messages)

    async def imitate(self, model: str, requirements: str, doc_content: str, use_rag: bool = True, output_format: str = "markdown", template_content: str = "", images: list = None) -> str:
        """增强版智能仿写：多分类 RAG + 知识约束 + 模板强制 + 自检重写 + 优化提示词"""

        # ======== Step 1: 多分类 RAG 检索 ========
        rag_contexts = {}
        if use_rag and self.kb:
            rag_contexts = self.kb.search_by_categories(
                requirements,
                categories=["世界观", "系统", "数值", "模板", "规范", "UI"],
                top_k_per_category=3,
            )

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

        # 3c: 模板参考
        if user_template:
            user_prompt_parts.append(f"【文档模板 - 必须严格按此模板的格式、章节结构、标题层级、样式风格生成】\n{user_template}\n")

        # 3d: 用户需求
        user_prompt_parts.append(f"【用户需求】\n{requirements}\n")

        # 3e: 当前文档参考
        if doc_content:
            user_prompt_parts.append(f"【当前参考的文档内容】\n{doc_content}\n")

        # 3f: 近期历史问题
        if recent_issues:
            user_prompt_parts.append(recent_issues)

        # 3g: 输出指令
        user_prompt_parts.append("请严格按照以上所有约束和模板，输出完整、可执行、逻辑闭环的游戏策划文档。")

        user_text = "\n".join(user_prompt_parts)

        # ======== Step 4: 构建 messages（支持多模态） ========
        messages = [{"role": "system", "content": ENHANCED_SYSTEM_PROMPT}]

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

        # ======== Step 7: 添加标注并格式化 ========
        prefix_parts = []
        if rag_contexts:
            prefix_parts.append("*(已应用 RAG 知识库检索增强)*")
        if has_images:
            prefix_parts.append("*(已参考上传的系统原型图)*")
        if prefix_parts:
            response = " ".join(prefix_parts) + "\n\n" + response

        if output_format == "html":
            response = self._md_to_html(response)

        return response

    async def complete_logic(self, model: str, doc_content: str) -> str:
        system_prompt = "你是一名细节严谨的游戏系统策划。请为用户的半成品/草稿文档补全缺失的标准章节（如背景、目标、流程、规则、奖励、限制、异常等），补齐边界场景、容错逻辑、互斥规则。不要篡改用户原有核心需求，仅做补充和规范化。"

        rag_context = ""
        if self.kb:
            query = doc_content[:200] if len(doc_content) > 200 else doc_content
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
