"""图片生成 API 路由（生图、修改、提示增强）"""

import json
import httpx
from fastapi import APIRouter, Body
from typing import Optional

router = APIRouter(tags=["image_gen"])

# Global reference set by api/main.py
router.ai_service = None


def _get_config():
    svc = router.ai_service
    if svc and hasattr(svc, '_get_config'):
        return svc._get_config()
    return {"models": {}}


IMAGE_MODEL_ENDPOINTS = {
    "GPT-Image 2": "https://api.openai.com/v1/images/generations",
    "Midjourney": "",
    "Google Banana": "",
    "豆包Seedream": "",
    "Stable Diffusion（本地）": "",
}


@router.post("/api/image/enhance-prompt")
async def enhance_prompt(payload: dict = Body(...)):
    """将自然语言提示词增强为专业生图 prompt"""
    text = payload.get("text", "").strip()
    if not text:
        return {"success": False, "message": "请输入提示内容"}
    system_prompt = (
        "你是一名专业AI绘画提示词工程师。将用户输入的简单描述扩展为详细、专业的英文生图提示词。"
        "请直接输出优化后的prompt，不要加解释和前缀。包含：主体描述、环境、光照、风格、构图、画质关键词。"
    )
    svc = router.ai_service
    if not svc or not hasattr(svc, '_call_api'):
        return {"success": False, "message": "AI服务不可用", "enhanced": text}

    # Use the first configured model
    config = _get_config()
    model_configs = config.get("models", {})
    preferred = ["DeepSeek", "GPT", "Kimi", "豆包", "GLM"]
    target_model = None
    for name in preferred:
        if name in model_configs and model_configs[name].get("apiKey"):
            target_model = name
            break
    if not target_model:
        # fallback: just return the original
        return {"success": True, "data": {"enhanced": text}}

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text},
    ]
    try:
        result = await svc._call_api(target_model, messages)
        enhanced = result.strip().strip('"\'')
        return {"success": True, "data": {"enhanced": enhanced}}
    except Exception as e:
        return {"success": False, "message": f"增强失败: {str(e)}", "enhanced": text}


@router.post("/api/image/generate")
async def generate_image(payload: dict = Body(...)):
    """生图"""
    prompt = payload.get("prompt", "").strip()
    model_name = payload.get("model", "GPT-Image 2")
    if not prompt:
        return {"success": False, "message": "请输入生图提示词"}

    config = _get_config()
    model_configs = config.get("models", {})

    # GPT-Image 2 → use OpenAI /v1/images/generations
    if model_name == "GPT-Image 2":
        cfg = model_configs.get("GPT-Image 2") or model_configs.get("GPT", {})
        api_key = cfg.get("apiKey", "")
        if not api_key:
            return {"success": False, "message": "GPT 未配置 API Key，请先在设置中配置"}
        endpoint = IMAGE_MODEL_ENDPOINTS["GPT-Image 2"]
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": "dall-e-3",
            "prompt": prompt,
            "n": 1,
            "size": "1024x1024",
        }
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(endpoint, json=body, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    url = data.get("data", [{}])[0].get("url", "")
                    revised = data.get("data", [{}])[0].get("revised_prompt", "")
                    if url:
                        # Download the image and return as base64
                        img_resp = await client.get(url, timeout=30)
                        if img_resp.status_code == 200:
                            import base64
                            b64 = base64.b64encode(img_resp.content).decode("utf-8")
                            return {
                                "success": True,
                                "data": {
                                    "data_uri": f"data:image/png;base64,{b64}",
                                    "revised_prompt": revised,
                                }
                            }
                return {"success": False, "message": f"生图失败 (HTTP {resp.status_code})"}
        except Exception as e:
            return {"success": False, "message": f"请求异常: {str(e)}"}

    # 豆包Seedream
    if model_name == "豆包Seedream":
        # 优先查生图模型名，再 fallback 到 AI 模型名
        cfg = model_configs.get("豆包Seedream") or model_configs.get("豆包", {})
        api_key = cfg.get("apiKey", "")
        if not api_key:
            return {"success": False, "message": "豆包Seedream 未配置 API Key，请先在设置中配置"}
        endpoint = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        model_id = cfg.get("modelId", "seedream-2-0")
        body = {
            "model": model_id,
            "prompt": prompt,
            "n": 1,
            "size": "1920x1920",
        }
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(endpoint, json=body, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    b64_json = data.get("data", [{}])[0].get("b64_json", "")
                    if b64_json:
                        return {
                            "success": True,
                            "data": {
                                "data_uri": f"data:image/png;base64,{b64_json}",
                                "revised_prompt": prompt,
                            }
                        }
                    url = data.get("data", [{}])[0].get("url", "")
                    if url:
                        async with httpx.AsyncClient(timeout=30) as client2:
                            img_resp = await client2.get(url)
                            if img_resp.status_code == 200:
                                import base64
                                b64 = base64.b64encode(img_resp.content).decode("utf-8")
                                return {
                                    "success": True,
                                    "data": {
                                        "data_uri": f"data:image/png;base64,{b64}",
                                        "revised_prompt": prompt,
                                    }
                                }
                detail = ""
                try: detail = resp.text[:200]
                except: pass
                return {"success": False, "message": f"生图失败 (HTTP {resp.status_code}) {detail}".strip()}
        except Exception as e:
            return {"success": False, "message": f"请求异常: {str(e)}"}

    # Stable Diffusion（本地）
    if model_name == "Stable Diffusion（本地）":
        cfg = model_configs.get("Stable Diffusion（本地）", {})
        base_url = cfg.get("modelId", "http://127.0.0.1:7860").rstrip("/")
        endpoint = f"{base_url}/sdapi/v1/txt2img"
        body = {
            "prompt": prompt,
            "negative_prompt": "",
            "steps": 20,
            "width": 1024,
            "height": 1024,
        }
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                resp = await client.post(endpoint, json=body)
                if resp.status_code == 200:
                    data = resp.json()
                    b64 = data.get("images", [""])[0]
                    if b64:
                        return {
                            "success": True,
                            "data": {
                                "data_uri": f"data:image/png;base64,{b64}",
                                "revised_prompt": prompt,
                            }
                        }
                return {"success": False, "message": f"生图失败 (HTTP {resp.status_code})"}
        except Exception as e:
            return {"success": False, "message": f"连接失败: {str(e)}"}

    # Midjourney / Google Banana — not yet implemented
    return {"success": False, "message": f"{model_name} 暂未实现，敬请期待"}


@router.post("/api/image/test-model")
async def test_image_model(payload: dict = Body(...)):
    """测试生图模型连接是否可用"""
    model_name = payload.get("model", "")
    api_key = payload.get("apiKey", "")
    model_id = payload.get("modelId", "")

    if not model_name:
        return {"success": False, "message": "未指定模型"}

    if model_name == "GPT-Image 2":
        if not api_key:
            return {"success": False, "message": "缺少 API Key"}
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        body = {"model": "dall-e-3", "prompt": "test", "n": 1, "size": "1024x1024"}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post("https://api.openai.com/v1/images/generations", json=body, headers=headers)
                if resp.status_code == 200:
                    return {"success": True, "message": "连接成功"}
                detail = ""
                try: detail = resp.text[:200]
                except: pass
                return {"success": False, "message": f"连接失败 (HTTP {resp.status_code}) {detail}".strip()}
        except Exception as e:
            return {"success": False, "message": f"连接异常: {str(e)}"}

    if model_name == "豆包Seedream":
        if not api_key:
            return {"success": False, "message": "缺少 API Key"}
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        body = {"model": model_id or "seedream-2-0", "prompt": "test", "n": 1, "size": "1920x1920"}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post("https://ark.cn-beijing.volces.com/api/v3/images/generations", json=body, headers=headers)
                if resp.status_code == 200:
                    return {"success": True, "message": "连接成功"}
                detail = ""
                try: detail = resp.text[:200]
                except: pass
                return {"success": False, "message": f"连接失败 (HTTP {resp.status_code}) {detail}".strip()}
        except Exception as e:
            return {"success": False, "message": f"连接异常: {str(e)}"}

    if model_name == "Stable Diffusion（本地）":
        base_url = (model_id or "http://127.0.0.1:7860").rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{base_url}/sdapi/v1/options", timeout=5)
                if resp.status_code == 200:
                    return {"success": True, "message": "连接成功"}
                return {"success": False, "message": f"连接失败 (HTTP {resp.status_code})"}
        except Exception as e:
            return {"success": False, "message": f"连接异常: {str(e)}"}

    # Midjourney / Google Banana
    return {"success": False, "message": f"{model_name} 暂不支持连接测试"}


@router.post("/api/image/edit")
async def edit_image(payload: dict = Body(...)):
    """修改图片（inpaint）"""
    model_name = payload.get("model", "GPT-Image 2")
    prompt = payload.get("prompt", "").strip()
    data_uri = payload.get("data_uri", "")
    mask_uri = payload.get("mask_uri", "")

    if not prompt:
        return {"success": False, "message": "请输入修改需求"}
    if not data_uri:
        return {"success": False, "message": "缺少原图"}

    config = _get_config()
    model_configs = config.get("models", {})

    if model_name == "GPT-Image 2":
        cfg = model_configs.get("GPT-Image 2") or model_configs.get("GPT", {})
        api_key = cfg.get("apiKey", "")
        if not api_key:
            return {"success": False, "message": "GPT 未配置 API Key"}

        body = {
            "model": "dall-e-2",
            "prompt": prompt,
            "n": 1,
            "size": "1024x1024",
        }

        if mask_uri:
            import base64, io
            from PIL import Image
            header, b64data = data_uri.split(",", 1)
            mask_header, mask_b64 = mask_uri.split(",", 1)
            body["image"] = b64data
            body["mask"] = mask_b64

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                if mask_uri:
                    import base64 as b64mod
                    img_bytes = b64mod.b64decode(body.pop("image"))
                    mask_bytes = b64mod.b64decode(body.pop("mask"))
                    files = {
                        "image": ("image.png", img_bytes, "image/png"),
                        "mask": ("mask.png", mask_bytes, "image/png"),
                        "prompt": (None, prompt),
                        "n": (None, "1"),
                        "size": (None, "1024x1024"),
                    }
                    resp = await client.post(
                        "https://api.openai.com/v1/images/edits",
                        files=files,
                        headers={"Authorization": f"Bearer {api_key}"},
                    )
                else:
                    resp = await client.post(
                        IMAGE_MODEL_ENDPOINTS.get("GPT-Image 2", ""),
                        json=body,
                        headers=headers,
                    )
                if resp.status_code == 200:
                    data = resp.json()
                    url = data.get("data", [{}])[0].get("url", "")
                    if url:
                        img_resp = await client.get(url, timeout=30)
                        if img_resp.status_code == 200:
                            import base64 as b64mod2
                            b64 = b64mod2.b64encode(img_resp.content).decode("utf-8")
                            return {
                                "success": True,
                                "data": {"data_uri": f"data:image/png;base64,{b64}"}
                            }
                return {"success": False, "message": f"修改失败 (HTTP {resp.status_code})"}
        except Exception as e:
            return {"success": False, "message": f"请求异常: {str(e)}"}

    # 豆包Seedream 修改
    if model_name == "豆包Seedream":
        cfg = model_configs.get("豆包Seedream") or model_configs.get("豆包", {})
        api_key = cfg.get("apiKey", "")
        if not api_key:
            return {"success": False, "message": "豆包Seedream 未配置 API Key"}
        import base64 as b64mod
        header, b64data = data_uri.split(",", 1)
        img_bytes = b64mod.b64decode(b64data)
        files = {
            "image": ("image.png", img_bytes, "image/png"),
            "prompt": (None, prompt),
            "n": (None, "1"),
            "size": (None, "1920x1920"),
        }
        if mask_uri:
            mask_header, mask_b64 = mask_uri.split(",", 1)
            mask_bytes = b64mod.b64decode(mask_b64)
            files["mask"] = ("mask.png", mask_bytes, "image/png")
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                resp = await client.post(
                    "https://ark.cn-beijing.volces.com/api/v3/images/edits",
                    files=files,
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                # 如果 edits 端点不存在（404），回退到 generation
                if resp.status_code == 404:
                    # 分析 mask 确定涂抹区域的位置和范围
                    region_desc = "指定区域"
                    if mask_uri:
                        try:
                            from PIL import Image as PILImage
                            import io
                            m_bytes = b64mod.b64decode(mask_b64)
                            m_img = PILImage.open(io.BytesIO(m_bytes)).convert("RGBA")
                            m_w, m_h = m_img.size
                            m_pixels = m_img.load()
                            # Find bounding box of transparent pixels (edit area)
                            min_x, min_y = m_w, m_h
                            max_x, max_y = 0, 0
                            for y in range(m_h):
                                for x in range(m_w):
                                    if m_pixels[x, y][3] < 250:  # transparent = edit
                                        min_x = min(min_x, x)
                                        min_y = min(min_y, y)
                                        max_x = max(max_x, x)
                                        max_y = max(max_y, y)
                            if max_x > min_x and max_y > min_y:
                                cx = (min_x + max_x) / 2 / m_w
                                cy = (min_y + max_y) / 2 / m_h
                                # Position description
                                vpos = "顶部" if cy < 0.33 else "底部" if cy > 0.67 else "中间"
                                hpos = "左侧" if cx < 0.33 else "右侧" if cx > 0.67 else "中间"
                                pos_parts = []
                                if vpos != "中间": pos_parts.append(vpos)
                                if hpos != "中间": pos_parts.append(hpos)
                                if not pos_parts: pos_parts.append("正中央")
                                area_ratio = ((max_x - min_x) * (max_y - min_y)) / (m_w * m_h)
                                size_desc = "小部分" if area_ratio < 0.15 else "约一半" if area_ratio < 0.4 else "大部分"
                                region_desc = f"图片的{'的'.join(pos_parts)}{size_desc}区域"
                        except Exception:
                            pass
                    gen_prompt = f"对{region_desc}进行修改：{prompt}。请保持图片其他所有内容与原始图片完全一致，只修改{region_desc}。"
                    gen_body = {
                        "model": cfg.get("modelId", "seedream-2-0"),
                        "prompt": gen_prompt,
                        "n": 1,
                        "size": "1920x1920",
                    }
                    resp = await client.post(
                        "https://ark.cn-beijing.volces.com/api/v3/images/generations",
                        json=gen_body,
                        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    )
                if resp.status_code == 200:
                    data = resp.json()
                    b64 = data.get("data", [{}])[0].get("b64_json", "") or ""
                    if not b64:
                        url = data.get("data", [{}])[0].get("url", "")
                        if url:
                            img_resp = await client.get(url, timeout=30)
                            if img_resp.status_code == 200:
                                b64 = b64mod.b64encode(img_resp.content).decode("utf-8")
                    if b64:
                        return {"success": True, "data": {"data_uri": f"data:image/png;base64,{b64}"}}
                detail = ""
                try: detail = resp.text[:200]
                except: pass
                return {"success": False, "message": f"修改失败 (HTTP {resp.status_code}) {detail}".strip()}
        except Exception as e:
            return {"success": False, "message": f"请求异常: {str(e)}"}
