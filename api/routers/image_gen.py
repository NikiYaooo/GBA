"""图片生成 API 路由（生图、修改、提示增强）"""

import asyncio
import json
import httpx
from fastapi import APIRouter, Body
from typing import Optional
from PIL import Image

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
    "豆包Seedream": "",
    "Stable Diffusion（本地）": "",
}

# Qwen-Image 2 — 直接使用 DashScope SDK，无需 URL 映射

QWEN_MODEL = "qwen-image-2.0"


async def _qwen_generate(prompt: str, api_key: str, size: str = "1024x1024") -> dict:
    """通过 DashScope SDK 调用 qwen-image-2.0 生图（异步提交 + 轮询结果）"""
    from dashscope.aigc.image_synthesis import AioImageSynthesis

    try:
        response = await AioImageSynthesis.call(
            model=QWEN_MODEL,
            prompt=prompt,
            api_key=api_key,
            n=1,
            size=size,
        )
    except Exception as e:
        raise Exception(f"请求异常: {str(e)}")

    if response.status_code != 200:
        msg = response.message or "未知错误"
        raise Exception(f"API 错误 ({response.status_code}): {msg}")

    if not response.output:
        raise Exception("API 返回为空")

    task_status = getattr(response.output, 'task_status', None)
    if task_status and task_status != 'SUCCEEDED':
        raise Exception(f"生图任务失败: {task_status}")

    results = getattr(response.output, 'results', [])
    if not results:
        raise Exception("生图未返回图片结果")

    url = results[0].url if hasattr(results[0], 'url') else ''
    if not url:
        raise Exception("生图结果中无图片 URL")

    return {"url": url, "revised_prompt": prompt}


async def _qwen_test_connect(api_key: str) -> bool:
    """测试 DashScope API Key 是否有效（提交最小任务，不等待完成）"""
    import httpx
    import json

    endpoint = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
    }
    body = {
        "model": QWEN_MODEL,
        "input": {"prompt": "test"},
        "parameters": {"n": 1, "size": "1024x1024"},
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(endpoint, json=body, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("output", {}).get("task_id"):
                    return True
            detail = ""
            try:
                detail = resp.text[:200]
            except Exception:
                pass
            raise Exception(f"连接失败 (HTTP {resp.status_code}) {detail}".strip())
    except httpx.TimeoutException:
        raise Exception("连接超时")
    except Exception as e:
        if "连接失败" in str(e):
            raise
        raise Exception(f"连接异常: {str(e)}")


async def _llm_crop_edit(
    prompt: str,
    data_uri: str,
    mask_uri: str,
    model_name: str,
    api_key: str,
    model_configs: dict,
) -> str:
    """LLM 增强的裁剪合成方案 — 修复 size 参数 + 改进融合

    流程：
    1. 解码原图 + mask
    2. 使用 find_mask_region / compute_crop_region 辅助函数
    3. PIL 分析图片基本信息（主色调、亮度等）
    4. 基于分析结果生成增强 prompt
    5. text2image 生成新内容（修复 size 参数）
    6. 双阶段高斯羽化合成回原图
    """
    import base64 as b64mod
    import io
    from PIL import Image, ImageFilter

    # 1. 解码原图
    _, b64data = data_uri.split(",", 1)
    orig_img = Image.open(io.BytesIO(b64mod.b64decode(b64data))).convert("RGBA")
    ow, oh = orig_img.size

    # 2. 解码 mask，找出涂抹区域
    _, mb64 = mask_uri.split(",", 1)
    mask_img = Image.open(io.BytesIO(b64mod.b64decode(mb64))).convert("RGBA")
    if mask_img.size != (ow, oh):
        mask_img = mask_img.resize((ow, oh), Image.LANCZOS)

    region = find_mask_region(mask_img)
    if region is None:
        raise Exception("未检测到涂抹区域，请在图片上涂抹后再提交修改")
    x1, y1, x2, y2 = region

    # 3. PIL 分析图片基本信息
    img_info = _analyze_image_basic(orig_img, (x1, y1, x2, y2))

    # 4. 计算裁剪区域（padding 25%）
    cx1, cy1, cx2, cy2 = compute_crop_region(x1, y1, x2, y2, ow, oh, padding=0.25)
    cw, ch = cx2 - cx1, cy2 - cy1

    # 5. 生成增强 prompt
    style_hint = f"主色调: {', '.join(img_info['dominant_colors'])}, 整体亮度: {img_info['brightness']}"
    gen_prompt = (
        f"【图片局部编辑任务】\n"
        f"原始图片特征：{style_hint}\n"
        f"编辑要求：{prompt}\n"
        f"请根据编辑要求生成该区域的新内容，确保风格、光照和色调与原始图片保持一致。"
    )

    # 6. 用 text2image 生成涂抹区域的新内容
    generated_bytes = None
    if model_name == "Qwen-Image 2":
        result = await _qwen_generate(gen_prompt, api_key, size="1024x1024")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(result["url"])
            if resp.status_code != 200:
                raise Exception("下载生成图片失败")
            generated_bytes = resp.content
    elif model_name == "豆包Seedream":
        model_id = (model_configs.get("豆包Seedream") or model_configs.get("豆包", {})).get("modelId", "seedream-2-0")
        endpoint = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        # 修复：使用 1920x1920 满足最低像素要求 (>= 3686400)
        body = {"model": model_id, "prompt": gen_prompt, "n": 1, "size": "1920x1920"}
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(endpoint, json=body, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                b64 = data.get("data", [{}])[0].get("b64_json", "") or ""
                if b64:
                    generated_bytes = b64mod.b64decode(b64)
                else:
                    url = data.get("data", [{}])[0].get("url", "")
                    if url:
                        img_resp = await client.get(url, timeout=30)
                        if img_resp.status_code == 200:
                            generated_bytes = img_resp.content
            if not generated_bytes:
                detail = ""
                try:
                    detail = resp.text[:200]
                except Exception:
                    pass
                raise Exception(f"生成失败 (HTTP {resp.status_code}) {detail}".strip())
    else:
        raise Exception(f"{model_name} 不支持此编辑方式")

    # 7. 将生成结果 resize 到裁剪区域大小
    gen_img = Image.open(io.BytesIO(generated_bytes)).convert("RGBA")
    gen_img = gen_img.resize((cw, ch), Image.LANCZOS)

    # 8. 创建羽化合成 mask
    edit_region = mask_img.crop((cx1, cy1, cx2, cy2))
    composite = Image.new("L", (cw, ch), 0)
    cp = composite.load()
    ep = edit_region.load()
    for y in range(ch):
        for x in range(cw):
            a = ep[x, y][3]
            if a < 250:
                cp[x, y] = 255
            elif a < 255:
                cp[x, y] = max(0, 255 - a)

    # 改进：双阶段高斯羽化
    feather_coarse = max(10, (cx2 - cx1) // 20)
    feather_fine = max(3, feather_coarse // 3)
    composite = composite.filter(ImageFilter.GaussianBlur(radius=feather_coarse))
    composite = composite.filter(ImageFilter.GaussianBlur(radius=feather_fine))

    # 9. 合成回原图
    result = orig_img.copy()
    result.paste(gen_img, (cx1, cy1), composite)

    # 10. 转为 base64
    buf = io.BytesIO()
    result.save(buf, format="PNG")
    return f"data:image/png;base64,{b64mod.b64encode(buf.getvalue()).decode('utf-8')}"


async def _native_edit_ark(
    prompt: str,
    data_uri: str,
    mask_uri: str,
    api_key: str,
    model_id: str,
) -> str:
    """通过 ARK /api/v3/images/edits 调用豆包 Seedream 原生图片编辑

    参数：
        prompt: 修改需求
        data_uri: 原图 data URI
        mask_uri: mask data URI（白=保留，透明=修改）
        api_key: ARK API Key
        model_id: 模型 ID（如 seedream-3-0）
    返回：
        编辑后的 data URI
    """
    import base64 as b64mod
    import io
    from PIL import Image as PILImage

    # 1. 解析原图和 mask
    _, img_b64 = data_uri.split(",", 1)
    img_bytes = b64mod.b64decode(img_b64)
    _, mask_b64 = mask_uri.split(",", 1)
    mask_bytes = b64mod.b64decode(mask_b64)

    # 2. 对齐 mask 尺寸到原图
    img_pil = PILImage.open(io.BytesIO(img_bytes))
    mask_pil = PILImage.open(io.BytesIO(mask_bytes)).convert("RGBA")
    if mask_pil.size != img_pil.size:
        mask_pil = mask_pil.resize(img_pil.size, PILImage.LANCZOS)

    mask_buf = io.BytesIO()
    mask_pil.save(mask_buf, format="PNG")
    mask_bytes_aligned = mask_buf.getvalue()

    # 3. 准备 multipart 请求
    size_str = f"{img_pil.width}x{img_pil.height}"

    endpoint = "https://ark.cn-beijing.volces.com/api/v3/images/edits"
    files = {
        "image": ("image.png", img_bytes, "image/png"),
        "mask": ("mask.png", mask_bytes_aligned, "image/png"),
        "prompt": (None, prompt),
        "n": (None, "1"),
        "size": (None, size_str),
        "model": (None, model_id),
    }
    headers = {"Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(endpoint, files=files, headers=headers)
        if resp.status_code != 200:
            detail = ""
            try:
                detail = resp.text[:300]
            except Exception:
                pass
            raise Exception(f"原生编辑失败 (HTTP {resp.status_code}) {detail}".strip())

        data = resp.json()
        b64_json = data.get("data", [{}])[0].get("b64_json", "")
        if b64_json:
            return f"data:image/png;base64,{b64_json}"

        url = data.get("data", [{}])[0].get("url", "")
        if url:
            img_resp = await client.get(url, timeout=30)
            if img_resp.status_code == 200:
                result_b64 = b64mod.b64encode(img_resp.content).decode("utf-8")
                return f"data:image/png;base64,{result_b64}"

        raise Exception("原生编辑返回中无图片数据")


@router.post("/api/image/enhance-prompt")
async def enhance_prompt(payload: dict = Body(...)):
    """将自然语言提示词增强为专业生图 prompt"""
    text = payload.get("text", "").strip()
    if not text:
        return {"success": False, "message": "请输入提示内容"}
    system_prompt = (
        "你是一名专业AI绘画提示词工程师。请将用户输入的简单描述扩展为详细、专业的中文生图提示词。"
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
    reference_images = payload.get("reference_images") or []
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
        if reference_images:
            # ARK API 需要 raw base64（去掉 data:image/...;base64, 前缀）
            # 参考图作为顶层 image + strength 参数传递
            ref = reference_images[0]
            if isinstance(ref, str):
                raw = ref
                if raw.startswith('data:'):
                    raw = raw.split(',', 1)[-1] if ',' in raw else raw
                body["image"] = raw
                body["strength"] = 0.9
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

    # Qwen-Image 2 — 使用 DashScope SDK（异步任务 + OSS 结果）
    if model_name == "Qwen-Image 2":
        cfg = model_configs.get("Qwen-Image 2", {})
        api_key = cfg.get("apiKey", "")
        if not api_key:
            return {"success": False, "message": "Qwen-Image 2 未配置 API Key，请先在设置中配置"}
        try:
            result = await _qwen_generate(prompt, api_key)
            # Download image from URL and convert to base64
            async with httpx.AsyncClient(timeout=30) as client:
                img_resp = await client.get(result["url"])
                if img_resp.status_code == 200:
                    import base64
                    b64 = base64.b64encode(img_resp.content).decode("utf-8")
                    return {
                        "success": True,
                        "data": {
                            "data_uri": f"data:image/png;base64,{b64}",
                            "revised_prompt": result["revised_prompt"],
                        }
                    }
                return {"success": False, "message": "下载生成图片失败"}
        except Exception as e:
            return {"success": False, "message": str(e)}

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

    return {"success": False, "message": f"不支持的图片模型: {model_name}"}


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

    if model_name == "Qwen-Image 2":
        if not api_key:
            return {"success": False, "message": "缺少 API Key"}
        try:
            await _qwen_test_connect(api_key)
            return {"success": True, "message": "连接成功"}
        except Exception as e:
            return {"success": False, "message": str(e)}

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

    return {"success": False, "message": f"不支持的图片模型: {model_name}"}


# ========== 图片编辑辅助函数 ==========

def _analyze_image_basic(img: Image.Image, mask_region: tuple) -> dict:
    """分析图片基本信息用于 prompt 增强

    返回：
        dict 包含：dominant_colors, brightness, region_ratio
    """
    from collections import Counter

    # 转 RGB 缩略图加速
    thumb = img.copy()
    thumb.thumbnail((64, 64))
    thumb_rgb = thumb.convert("RGB")

    # 提取主色调（降采样到 32 级每通道后取 top 3）
    pixels = list(thumb_rgb.getdata())
    quantized = [(r // 32 * 32, g // 32 * 32, b // 32 * 32) for r, g, b in pixels]
    top3 = [f"rgb{c}" for c, _ in Counter(quantized).most_common(3)]

    # 平均亮度
    gray = thumb_rgb.convert("L")
    avg_brightness = sum(gray.getdata()) / len(list(gray.getdata()))

    # 涂抹区域占比
    x1, y1, x2, y2 = mask_region
    mask_area = (x2 - x1 + 1) * (y2 - y1 + 1)
    total_area = img.width * img.height
    region_ratio = mask_area / total_area

    return {
        "dominant_colors": top3,
        "brightness": "bright" if avg_brightness > 170 else "dark" if avg_brightness < 85 else "medium",
        "region_ratio": round(region_ratio, 3),
    }


def find_mask_region(mask_img: Image.Image, alpha_threshold: int = 250) -> tuple | None:
    """从 mask 图片中找出涂抹区域（alpha < threshold 的像素范围）

    参数：
        mask_img: RGBA 模式的 PIL Image
        alpha_threshold: alpha 低于此值视为涂抹区域
    返回：
        (x1, y1, x2, y2) 或 None（未检测到涂抹）
    """
    w, h = mask_img.size
    mpx = mask_img.load()
    x1, y1, x2, y2 = w, h, 0, 0
    found = False
    for y in range(h):
        for x in range(w):
            if mpx[x, y][3] < alpha_threshold:
                found = True
                if x < x1: x1 = x
                if y < y1: y1 = y
                if x > x2: x2 = x
                if y > y2: y2 = y
    if not found:
        return None
    return (x1, y1, x2, y2)


def compute_crop_region(x1: int, y1: int, x2: int, y2: int, img_w: int, img_h: int, padding: float = 0.25) -> tuple[int, int, int, int]:
    """根据涂抹区域计算四周 padding 后的裁剪范围"""
    ew, eh = x2 - x1 + 1, y2 - y1 + 1
    pad = int(max(20, min(ew, eh) * padding))
    cx1 = max(0, x1 - pad)
    cy1 = max(0, y1 - pad)
    cx2 = min(img_w, x2 + pad)
    cy2 = min(img_h, y2 + pad)
    return (cx1, cy1, cx2, cy2)


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
                    from PIL import Image as PILImage2
                    import io
                    img_bytes = b64mod.b64decode(body.pop("image"))
                    mask_bytes = b64mod.b64decode(body.pop("mask"))
                    # Resize mask to match original image dimensions
                    img_pil = PILImage2.open(io.BytesIO(img_bytes))
                    mask_pil = PILImage2.open(io.BytesIO(mask_bytes)).convert("RGBA")
                    if mask_pil.size != img_pil.size:
                        mask_pil = mask_pil.resize(img_pil.size, PILImage2.NEAREST)
                    mask_buf = io.BytesIO()
                    mask_pil.save(mask_buf, format="PNG")
                    mask_bytes = mask_buf.getvalue()
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

    # 豆包Seedream 修改 — 优先原生编辑，回退 Crop-Edit
    if model_name == "豆包Seedream":
        cfg = model_configs.get("豆包Seedream") or model_configs.get("豆包", {})
        api_key = cfg.get("apiKey", "")
        if not api_key:
            return {"success": False, "message": "豆包Seedream 未配置 API Key"}
        model_id = cfg.get("modelId", "seedream-2-0")
        # 优先原生编辑
        try:
            data_uri_result = await _native_edit_ark(prompt, data_uri, mask_uri, api_key, model_id)
            return {"success": True, "data": {"data_uri": data_uri_result}}
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"豆包原生编辑失败，回退 Crop-Edit: {e}")
            # 回退到 LLM 增强 Crop-Edit
            try:
                data_uri_result = await _llm_crop_edit(prompt, data_uri, mask_uri, model_name, api_key, model_configs)
                return {"success": True, "data": {"data_uri": data_uri_result}}
            except Exception as e2:
                return {"success": False, "message": str(e2)}

    # Qwen-Image 2 修改 — 使用裁剪合成方案（crop→generate→composite）
    if model_name == "Qwen-Image 2":
        cfg = model_configs.get("Qwen-Image 2", {})
        api_key = cfg.get("apiKey", "")
        if not api_key:
            return {"success": False, "message": "Qwen-Image 2 未配置 API Key"}
        try:
            data_uri_result = await _llm_crop_edit(prompt, data_uri, mask_uri, model_name, api_key, model_configs)
            return {"success": True, "data": {"data_uri": data_uri_result}}
        except Exception as e:
            return {"success": False, "message": str(e)}

    return {"success": False, "message": f"{model_name} 修改功能暂未实现"}
