import os
import json
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

        body = {
            "model": model_id or model_name.lower(),
            "messages": messages,
            "temperature": 0.3,
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

    async def quality_check(self, model: str, doc_content: str, system_prompt: str = None) -> str:
        """文档质检：不使用 RAG。可传入自定义 system_prompt"""
        if not system_prompt:
            system_prompt = "你是一名资深游戏策划专家，请对用户提供的策划文档进行严格质检。检查逻辑矛盾、信息缺失、边界遗漏、文案模糊、落地性和规范问题。请输出：风险等级、问题原文、分析、修改建议。"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请质检以下文档内容：\n\n{doc_content}"}
        ]
        return await self._call_api(model, messages)

    async def imitate(self, model: str, requirements: str, doc_content: str, use_rag: bool = True) -> str:
        """智能仿写：首次使用 RAG，后续可不使用"""
        system_prompt = "你是一名资深游戏主策划，请根据用户的新需求撰写游戏策划案。要求结构严谨，逻辑清晰，可以直接落地。"
        
        rag_context = ""
        if use_rag and self.kb:
            search_results = self.kb.search(requirements, top_k=3)
            if search_results:
                rag_context = "【以下是知识库中检索到的同类型历史策划案片段，请参考其格式、术语和结构风格进行仿写】：\n\n"
                for i, res in enumerate(search_results):
                    rag_context += f"--- 参考片段 {i+1} (来源: {res['metadata'].get('filename', '未知')}) ---\n"
                    rag_context += res['content'] + "\n\n"
                    
        user_prompt = ""
        if rag_context:
            user_prompt += rag_context
            
        user_prompt += f"【当前参考的文档内容（如有）】：\n{doc_content}\n\n"
        user_prompt += f"【新需求】：\n{requirements}\n\n请开始撰写："
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = await self._call_api(model, messages)
        
        if rag_context:
            response = "*(已应用 RAG 知识库检索增强)*\n\n" + response
            
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
