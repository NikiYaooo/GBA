import os
import json
import re
import markdown
from typing import List, Dict, Optional
import httpx
from knowledge_base import KnowledgeBase


# 各模型的 API 地址映射
MODEL_ENDPOINTS = {
    "DeepSeek": "https://api.deepseek.com/v1/chat/completions",
    "豆包": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
    "GPT-4o": "https://api.openai.com/v1/chat/completions",
    "Gemini": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
    "Kimi": "https://api.moonshot.cn/v1/chat/completions",
    "GLM": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
}

# 各模型允许的 temperature 值（None 表示使用默认值）
MODEL_TEMPERATURES = {
    "Kimi": 1.0,
}


class AIService:
    """
    负责集成多个 AI 模型，并处理 RAG 逻辑
    """

    def __init__(self, kb: KnowledgeBase = None):
        self.kb = kb

    def _get_config(self) -> dict:
        # 优先使用 GB_DATA_DIR 环境变量
        data_dir = os.environ.get("GB_DATA_DIR", "")
        if data_dir:
            config_path = os.path.join(data_dir, "config.json")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    return json.load(f)

        # 兜底：使用 AppData
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
        """将 AI 输出的 Markdown 文本转换为 HTML，适配 TipTap 编辑器。"""
        # 检测是否已经是 HTML（包含完整标签）
        if re.search(r'<(h[1-6]|p|div|table|ul|ol|strong|em)[^>]*>', text):
            return text

        # 预处理：移除多余的空行（保留段落分隔）
        text = re.sub(r'\n{4,}', '\n\n', text)

        # 使用 markdown 库转换（extra 扩展支持表格、围栏代码等）
        html = markdown.markdown(text, extensions=['extra', 'tables', 'fenced_code', 'codehilite'])

        # 后处理：清理多余的空白
        html = re.sub(r'<p>\s+', '<p>', html)
        html = re.sub(r'\s+</p>', '</p>', html)
        html = re.sub(r'<br\s*/?>\s*<br\s*/?>', '<br>', html)
        return html.strip()

    async def quality_check(self, model: str, doc_content: str, system_prompt: str = None) -> str:
        """文档质检：不使用 RAG。可传入自定义 system_prompt"""
        if not system_prompt:
            system_prompt = "你是一名资深游戏策划专家，请对用户提供的策划文档进行严格质检。检查逻辑矛盾、信息缺失、边界遗漏、文案模糊、落地性和规范问题。请输出：风险等级、问题原文、分析、修改建议。"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请质检以下文档内容：\n\n{doc_content}"}
        ]
        return await self._call_api(model, messages)

    async def imitate(self, model: str, requirements: str, doc_content: str, use_rag: bool = True, output_format: str = "markdown", template_content: str = "", images: list = None) -> str:
        """智能仿写：使用 RAG 知识库 + 文档模板增强风格和系统关联"""
        system_prompt = """你是资深游戏策划师，精通各类游戏（手游/端游）的策划文档撰写规范，擅长结合参考文档的风格、结构、术语，仿写符合要求的策划内容，全程贴合以下规则，不偏离用户需求：

1.仿写核心原则：严格参考用户提供的【文档模板】和【本地 RAG 知识库检索结果】（用户提供的历史策划文档、模板、术语库），保持一致的文档结构（标题层级、条目格式）、专业术语、表述风格，不添加无关内容，不改变用户要求的核心逻辑。如果用户提供了【文档模板】，必须严格按照模板的格式、章节结构、排版风格来生成文档。

2.内容要求：仿写内容需具备可执行性、逻辑闭环，符合游戏策划行业规范——比如数值规则明确、流程步骤清晰、模块划分合理，避免口语化、模糊化表述（例：不说"大概给100钻石"，说"活动奖励：钻石×100，每日可领取1次"）。

3.逻辑补完适配：若用户提供的仿写需求不完整（缺少流程、数值、条件等），需结合 RAG 检索到的同类策划案例，补充合理内容，保证策划文档的完整性和可落地性，补充部分需标注"【补充】"，不强行添加无关功能。

4.术语规范：严格沿用 RAG 知识库中已有的项目专属术语（如奖励命名、系统名称、角色称谓等），不随意创造术语，若有新增术语，需标注说明。

5.格式要求：如果用户提供了【文档模板】，必须严格按模板的格式输出（标题层级、表格样式、条目结构等）；如果没有模板，则按"章节标题→子标题→条目式描述"排版，关键信息（数值、规则、条件）加粗，符合游戏策划文档（GDD/活动策划/系统策划）的标准格式，可直接导出为Word文档。

6.如果用户上传了系统原型图（UI 设计图），请仔细观察图像中界面布局、控件、功能模块，理解系统需求，将其融入生成的文档中。"""

        rag_context = ""
        if use_rag and self.kb:
            search_results = self.kb.search(requirements, top_k=5)
            if search_results:
                rag_context = "【以下是知识库中检索到的同类型历史策划案片段，请严格参考其格式、术语和结构风格进行仿写】：\n\n"
                for i, res in enumerate(search_results):
                    rag_context += f"--- 参考文档 {i+1}：《{res['metadata'].get('filename', '未知')}》---\n"
                    rag_context += res['content'] + "\n\n"

        user_text = ""
        if rag_context:
            user_text += rag_context

        if template_content:
            user_text += f"【文档模板 - 请严格按照以下模板的格式、结构、样式风格生成文档】：\n{template_content}\n\n"

        user_text += f"【用户需求】：\n{requirements}\n\n"
        if doc_content:
            user_text += f"【当前参考的文档内容】：\n{doc_content}\n\n"
        user_text += "请输出：完整、可执行、风格统一的游戏策划内容。"

        # 构建 messages - 支持多模态（图片）
        messages = [{"role": "system", "content": system_prompt}]

        if images and len(images) > 0:
            # 对于支持 vision 的模型，使用多模态消息格式
            # GPT-4o 和 Gemini 支持图片理解
            vision_content = []
            # 文本放在前面
            vision_content.append({"type": "text", "text": user_text})
            # 添加图片（限制最多 6 张以避免 token 过多）
            max_images = min(len(images), 6)
            for i in range(max_images):
                data_uri = images[i]
                # data_uri 格式: "data:image/png;base64,..."
                vision_content.append({
                    "type": "image_url",
                    "image_url": {"url": data_uri, "detail": "high"}
                })
            if len(images) > 6:
                vision_content.append({"type": "text", "text": f"\n（注：用户还上传了 {len(images) - 6} 张原型图未展示）"})
            messages.append({"role": "user", "content": vision_content})
        else:
            messages.append({"role": "user", "content": user_text})

        response = await self._call_api(model, messages)

        if rag_context:
            response = "*(已应用 RAG 知识库检索增强)*\n\n" + response

        if images:
            response = "*(已参考上传的系统原型图)*\n\n" + response

        if output_format == "html":
            response = self._md_to_html(response)

        return response

    async def complete_logic(self, model: str, doc_content: str) -> str:
        """逻辑补完：使用 RAG 补充标准模块"""
        system_prompt = "你是一名细节严谨的游戏系统策划。请为用户的半成品/草稿文档补全缺失的标准章节（如背景、目标、流程、规则、奖励、限制、异常等），补齐边界场景、容错逻辑、互斥规则。不要篡改用户原有核心需求，仅做补充和规范化。"
        
        rag_context = ""
        if self.kb:
            # 用文档前几百个字去检索相关系统模板
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
        """根据文档描述生成 UI 原型图（使用 DALL-E 3）。"""
        config = self._get_config()
        model_config = config.get("models", {}).get(model, {})
        api_key = model_config.get("apiKey", "")

        if not api_key:
            # 尝试从 GPT-4o 的配置中获取 key
            model_config = config.get("models", {}).get("GPT-4o", {})
            api_key = model_config.get("apiKey", "")

        if not api_key:
            return {"success": False, "message": f"{model} 未配置 API Key，无法生成图片"}

        # 从文档中提取关键描述（取前 1500 字）
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
