# 图片工具优化 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 修复豆包 Seedream 图片修改模式 Bug + 全面优化涂抹交互和编辑质量

**架构：**
1. 后端：新增 `_native_edit_ark()` 使用 ARK /api/v3/images/edits 原生编辑；重写 `_crop_edit` → `_llm_crop_edit` 修复 size 参数、增强 prompt、改进边缘融合；重组 `edit_image()` 路由为先原生后回退
2. 前端：改进 ImageToolDialog.vue 的涂抹交互（橡皮擦、Ctrl擦除、mask 预览、视觉效果）
3. 测试：针对 mask 分析、裁剪计算、合成逻辑的单元测试

**技术栈：** Python FastAPI + httpx + Pillow + Vue 3

---

### 任务 1：添加测试依赖 + 创建测试基础设施

**文件：**
- 修改：`requirements.txt`
- 创建：`tests/test_image_edit.py`
- 创建：`tests/conftest.py`

- [ ] **步骤 1：添加 pytest-asyncio 到 requirements.txt**

在 `requirements.txt` 追加一行：
```
pytest-asyncio
```

- [ ] **步骤 2：安装依赖**

运行：
```powershell
.venv\Scripts\pip.exe install pytest-asyncio
```

- [ ] **步骤 3：创建 tests/conftest.py**

```python
"""tests/conftest.py — 共享 fixtures"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import base64
import io
import pytest
from PIL import Image


@pytest.fixture
def sample_image_png() -> bytes:
    """生成 200x200 的纯色测试图片 PNG 字节"""
    img = Image.new("RGBA", (200, 200), (100, 149, 237, 255))  # cornflower blue
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def sample_data_uri(sample_image_png) -> str:
    """返回 data:image/png;base64,..."""
    b64 = base64.b64encode(sample_image_png).decode("utf-8")
    return f"data:image/png;base64,{b64}"


@pytest.fixture
def sample_mask_uri() -> str:
    """生成 200x200 的 mask：中心 50x50 区域为透明（涂抹区域），其余为白色"""
    img = Image.new("RGBA", (200, 200), (255, 255, 255, 255))
    for y in range(75, 125):
        for x in range(75, 125):
            img.putpixel((x, y), (255, 255, 255, 0))  # transparent = edit area
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


@pytest.fixture
def all_white_mask_uri() -> str:
    """全白 mask = 无涂抹区域"""
    img = Image.new("RGBA", (200, 200), (255, 255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"
```

- [ ] **步骤 4：验证测试可以运行**

运行：
```powershell
.venv\Scripts\python.exe -m pytest tests/ -v
```
预期：没有 test_image_edit.py 的测试（还没写），conftest 不应报错

---

### 任务 2：后端 — 提取可测试的同步辅助函数

**文件：**
- 修改：`api/routers/image_gen.py`（在文件末尾新增辅助函数）
- 测试：`tests/test_image_edit.py`

设计说明：将 `_llm_crop_edit` 中的纯计算逻辑提取为同步函数，方便测试。

- [ ] **步骤 1：编写失败的测试 — test_find_mask_region**

在 `tests/test_image_edit.py` 中：

```python
"""tests/test_image_edit.py — 图片编辑模块单元测试"""

import base64
import io
from PIL import Image


def test_find_mask_region_finds_painted_area(sample_mask_uri):
    """验证 find_mask_region 能正确检测涂抹区域边界"""
    from api.routers.image_gen import find_mask_region

    header, b64 = sample_mask_uri.split(",", 1)
    mask_img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGBA")
    x1, y1, x2, y2 = find_mask_region(mask_img)
    # mask 中心 75-124 区域被涂抹，padding 前应该是 (75, 75, 124, 124)
    assert x1 >= 75 and x1 <= 80, f"x1={x1} 预期≈75"
    assert y1 >= 75 and y1 <= 80, f"y1={y1} 预期≈75"
    assert x2 >= 120 and x2 <= 125, f"x2={x2} 预期≈124"
    assert y2 >= 120 and y2 <= 125, f"y2={y2} 预期≈124"


def test_find_mask_region_returns_none_for_empty_mask(all_white_mask_uri):
    """全白 mask 应返回 None"""
    from api.routers.image_gen import find_mask_region

    header, b64 = all_white_mask_uri.split(",", 1)
    mask_img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGBA")
    result = find_mask_region(mask_img)
    assert result is None
```

- [ ] **步骤 2：实现 find_mask_region**

在 `api/routers/image_gen.py` 末尾（`edit_image` 函数之前或之后），新增：

```python
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
```

- [ ] **步骤 3：运行测试验证通过**

运行：
```powershell
.venv\Scripts\python.exe -m pytest tests/test_image_edit.py::test_find_mask_region_finds_painted_area tests/test_image_edit.py::test_find_mask_region_returns_none_for_empty_mask -v
```
预期：PASS

- [ ] **步骤 4：编写测试 — compute_crop_region**

```python
def test_compute_crop_region():
    """验证 compute_crop_region 正确计算 padding 后的裁剪区域"""
    from api.routers.image_gen import compute_crop_region

    # mask 区域为 (50, 50, 150, 150)，原图 200x200，padding 0.25
    result = compute_crop_region(50, 50, 150, 150, img_w=200, img_h=200, padding=0.25)
    # padding = (150-50) * 0.25 = 25
    # x1 = max(0, 50-25) = 25
    # y1 = max(0, 50-25) = 25
    # x2 = min(200, 150+25) = 175
    # y2 = min(200, 150+25) = 175
    assert result == (25, 25, 175, 175), f"结果={result}"


def test_compute_crop_region_clamps_to_image_bounds():
    """验证裁剪区域不会超出图片边界"""
    from api.routers.image_gen import compute_crop_region

    # mask 紧贴边缘 (0, 0, 10, 10)，原图 100x100
    result = compute_crop_region(0, 0, 10, 10, img_w=100, img_h=100, padding=0.5)
    # padding = 5，x1 = 0, y1 = 0, x2 = 15, y2 = 15
    assert result == (0, 0, 15, 15)
```

- [ ] **步骤 5：实现 compute_crop_region**

```python
def compute_crop_region(x1, y1, x2, y2, img_w, img_h, padding=0.25):
    """根据涂抹区域计算四周 padding 后的裁剪范围

    参数：
        x1, y1, x2, y2: 涂抹区域边界（像素坐标）
        img_w, img_h: 原图宽高
        padding: 扩展比例（基于涂抹区域尺寸）
    返回：
        (cx1, cy1, cx2, cy2)
    """
    ew, eh = x2 - x1 + 1, y2 - y1 + 1
    pad = int(max(20, min(ew, eh) * padding))
    cx1 = max(0, x1 - pad)
    cy1 = max(0, y1 - pad)
    cx2 = min(img_w, x2 + pad)
    cy2 = min(img_h, y2 + pad)
    return (cx1, cy1, cx2, cy2)
```

- [ ] **步骤 6：运行测试验证通过**

运行：
```powershell
.venv\Scripts\python.exe -m pytest tests/test_image_edit.py -v
```
预期：4 个测试全部 PASS

---

### 任务 3：后端 — 实现 _llm_crop_edit（改进版裁剪合成）

**文件：**
- 修改：`api/routers/image_gen.py`
- 测试：`tests/test_image_edit.py`

设计说明：
- 基于原 `_crop_edit`，但修复 size 参数、增加 padding、改进融合
- 使用 PIL 分析图片基本信息辅助 prompt 生成（无需 LLM 调用即可改进）
- 保留原有的 crop-edit 核心流程

- [ ] **步骤 1：实现 `_analyze_image_basic()` — PIL 图片分析**

```python
def _analyze_image_basic(img: Image.Image, mask_region: tuple) -> dict:
    """分析图片基本信息用于 prompt 增强

    返回：
        dict 包含：dominant_colors, brightness, has_text, region_ratio 等
    """
    from collections import Counter

    # 转 RGB 缩略图加速
    thumb = img.copy()
    thumb.thumbnail((64, 64))
    thumb_rgb = thumb.convert("RGB")

    # 提取主色调（降采样到 16 色后取 top 3）
    pixels = list(thumb_rgb.getdata())
    # 量化到 32 级每通道
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
```

- [ ] **步骤 2：测试 `_analyze_image_basic`**

```python
def test_analyze_image_basic(sample_data_uri):
    from api.routers.image_gen import _analyze_image_basic, find_mask_region
    import base64, io
    from PIL import Image

    header, b64 = sample_data_uri.split(",", 1)
    img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGBA")

    # 创建一个已知的 mask region
    result = _analyze_image_basic(img, (75, 75, 124, 124))
    assert "dominant_colors" in result
    assert "brightness" in result
    assert result["region_ratio"] > 0
```

- [ ] **步骤 3：运行测试**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_image_edit.py::test_analyze_image_basic -v
```
预期：PASS

- [ ] **步骤 4：重写 `_llm_crop_edit` 函数**

用以下代码完全替代原有的 `_crop_edit` 函数（从 `async def _crop_edit` 到函数结束）：

```python
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
    2. PIL 分析图片基本信息（主色调、亮度等）
    3. 基于分析结果生成增强 prompt
    4. 裁剪涂抹区域 + padding
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

    # 3. PIL 分析图片
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
        # 修复：使用 1920x1920 满足最低像素要求
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
```

- [ ] **步骤 5：验证现有测试仍然通过**

运行：
```powershell
.venv\Scripts\python.exe -m pytest tests/ -v
```
预期：所有测试 PASS（包括原有的 test_kb_project.py）

---

### 任务 4：后端 — 实现 _native_edit_ark（豆包 Seedream 原生编辑）

**文件：**
- 修改：`api/routers/image_gen.py`

设计说明：ARL `/api/v3/images/edits` 端点与 OpenAI edits 格式相同（multipart/form-data）。

- [ ] **步骤 1：在 image_gen.py 中新增 `_native_edit_ark` 函数**

添加到 `_llm_crop_edit` 函数之后：

```python
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
    # 使用原图尺寸作为 size 参数（ARL edits API 要求）
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
```

- [ ] **步骤 2：添加 import logging 到文件顶部（如果还没有）**

确认 `image_gen.py` 顶部已有 `import logging`（用于 `logger.warning` 回退日志）。

---

### 任务 5：后端 — 重组 edit_image() 路由

**文件：**
- 修改：`api/routers/image_gen.py`（`edit_image` 函数）

- [ ] **步骤 1：重写 edit_image 函数**

将 `edit_image` 函数（第 506 行起）重写为：

```python
@router.post("/api/image/edit")
async def edit_image(payload: dict = Body(...)):
    """修改图片（inpaint）
    
    策略：优先使用模型的原生编辑 API，不支持或失败时回退到 LLM 增强的 Crop-Edit。
    """
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

    # ========== GPT-Image 2（DALL-E 2 edits） ==========
    if model_name == "GPT-Image 2":
        cfg = model_configs.get("GPT-Image 2") or model_configs.get("GPT", {})
        api_key = cfg.get("apiKey", "")
        if not api_key:
            return {"success": False, "message": "GPT 未配置 API Key"}
        # ...（保持现有 DALL-E 2 edit 代码不变，第 522-595 行）...

    # ========== 豆包 Seedream ==========
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
            logger = logging.getLogger(__name__)
            logger.warning(f"豆包原生编辑失败，回退 Crop-Edit: {e}")
            # 回退到 LLM 增强 Crop-Edit
            try:
                data_uri_result = await _llm_crop_edit(prompt, data_uri, mask_uri, model_name, api_key, model_configs)
                return {"success": True, "data": {"data_uri": data_uri_result}}
            except Exception as e2:
                return {"success": False, "message": str(e2)}

    # ========== Qwen-Image 2 ==========
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
```

**注意：** 保留 GPT-Image 2 分支的原有代码不变（第 522-595 行代码块不动，仅将分支结构改为上述 if/elif 模式）。

实际修改方式：用编辑工具将现有的 `edit_image` 中豆包和 Qwen 的分支替换。

具体来说需要：
1. 保留 GPT-Image 2 分支代码
2. 将豆包分支（当前第 597-607 行 `if model_name == "豆包Seedream": → _crop_edit`）替换为 try native → fallback _llm_crop_edit
3. 将 Qwen 分支（当前第 609-619 行 `if model_name == "Qwen-Image 2": → _crop_edit`）替换为直接调用 _llm_crop_edit
4. 删除原 `_crop_edit` 函数（已被 `_llm_crop_edit` 替代）

---

### 任务 6：前端 — 改进 ImageToolDialog.vue 涂抹交互

**文件：**
- 修改：`src/components/dialogs/ImageToolDialog.vue`

- [ ] **步骤 1：增加橡皮擦模式状态和 toggle**

在 `<script setup>` 的 `const isModifyMode` 附近增加：

```typescript
const isErasing = ref(false)
const toggleErase = () => { isErasing.value = !isErasing.value }
```

- [ ] **步骤 2：修改 mouse 事件处理支持橡皮擦**

更新 `drawBrush` 函数：

```typescript
const drawBrush = (e: MouseEvent) => {
  if (!editCtx || !editCanvasRef.value) return
  const rect = editCanvasRef.value.getBoundingClientRect()
  const scaleX = editCanvasRef.value.width / rect.width
  const scaleY = editCanvasRef.value.height / rect.height
  const x = (e.clientX - rect.left) * scaleX
  const y = (e.clientY - rect.top) * scaleY

  const erasing = isErasing.value || e.ctrlKey || e.button === 2
  if (erasing) {
    // 橡皮擦模式：清除涂抹
    editCtx.globalCompositeOperation = 'destination-out'
    editCtx.fillStyle = 'rgba(0, 0, 0, 1)'
  } else {
    // 涂抹模式
    editCtx.globalCompositeOperation = 'source-over'
    editCtx.fillStyle = 'rgba(255, 0, 0, 0.5)'
  }
  editCtx.beginPath()
  editCtx.arc(x, y, brushSize.value, 0, Math.PI * 2)
  editCtx.fill()
}
```

更新 `onMouseDown` 阻止右键菜单：

```typescript
const onMouseDown = (e: MouseEvent) => {
  if (e.button === 2) e.preventDefault()  // 阻止右键菜单
  if (!editCtx || !editCanvasRef.value) return
  isDrawing = true
  const rect = editCanvasRef.value.getBoundingClientRect()
  // ... 原有逻辑 ...
}
```

在模板的 canvas 上增加 `@contextmenu.prevent`：

```html
<canvas
  ref="editCanvasRef"
  @contextmenu.prevent
  ...
/>
```

- [ ] **步骤 3：增加涂抹进度显示**

在 `generateMaskDataUrl` 函数旁新增计算函数：

```typescript
const paintedPercent = computed(() => {
  const canvas = editCanvasRef.value
  if (!canvas) return 0
  const ctx = canvas.getContext('2d')
  if (!ctx) return 0
  const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data
  let painted = 0
  for (let i = 3; i < data.length; i += 4) {
    if (data[i] > 10) painted++
  }
  const total = data.length / 4
  return Math.round((painted / total) * 1000) / 10
})

const hasMask = computed(() => paintedPercent.value > 0)
```

- [ ] **步骤 4：修改模板 — 工具栏区域**

将修改模式下的 UI 改为：

```html
<!-- Modify mode: canvas with brush -->
<div v-else class="space-y-3">
  <div class="flex items-center justify-between">
    <span class="text-sm font-medium">
      在图片上涂抹要修改的区域（<span class="text-blue-400">左键涂抹</span> / <span class="text-yellow-400">右键/ Ctrl 擦除</span>）
    </span>
    <div class="flex items-center gap-2">
      <el-button
        size="small"
        :type="isErasing ? 'warning' : 'default'"
        @click="toggleErase"
      >
        {{ isErasing ? '擦除中' : '橡皮擦' }}
      </el-button>
      <span class="text-xs text-app-muted">画笔:</span>
      <el-slider v-model="brushSize" :min="5" :max="80" class="!w-20" />
      <span class="text-xs text-app-muted w-8">{{ brushSize }}px</span>
    </div>
  </div>

  <!-- Canvas stack -->
  <div class="relative border rounded-lg overflow-hidden" :style="canvasContainerStyle">
    <canvas ref="canvasRef" class="absolute inset-0" />
    <canvas
      ref="editCanvasRef"
      class="absolute inset-0 cursor-crosshair"
      @mousedown="onMouseDown"
      @mousemove="onMouseMove"
      @mouseup="onMouseUp"
      @mouseleave="onMouseLeave"
      @contextmenu.prevent
    />
    <!-- Brush cursor preview -->
    <div
      v-if="mousePos.x >= 0"
      class="absolute pointer-events-none rounded-full border-2"
      :class="isErasing ? 'border-yellow-400' : 'border-white'"
      :style="{
        width: brushSize * 2 + 'px',
        height: brushSize * 2 + 'px',
        left: mousePos.x - brushSize + 'px',
        top: mousePos.y - brushSize + 'px',
      }"
    />
  </div>

  <!-- Status bar -->
  <div class="flex items-center justify-between">
    <div class="flex gap-2 items-center">
      <span class="text-xs" :class="hasMask ? 'text-green-500' : 'text-app-muted'">
        已涂抹 {{ paintedPercent }}% 区域
      </span>
      <el-button v-if="hasMask" size="small" text @click="clearMask">清除涂抹</el-button>
    </div>
    <div class="flex gap-2 flex-1 ml-4">
      <el-input
        v-model="modifyPrompt"
        size="small"
        placeholder="输入修改需求（如：把背景换成森林）"
        class="flex-1"
        @keyup.enter="submitEdit"
      />
      <el-button
        size="small"
        type="primary"
        :loading="isEditing"
        :disabled="!hasMask || !modifyPrompt.trim()"
        @click="submitEdit"
      >确认修改</el-button>
      <el-button size="small" @click="exitModifyMode">返回</el-button>
    </div>
  </div>
</div>
```

- [ ] **步骤 5：确保 `onMouseLeave` 重置鼠标状态时不影响绘制状态**

```typescript
const onMouseLeave = () => {
  isDrawing = false
  mousePos.value = { x: -1, y: -1 }
}
```

- [ ] **步骤 6：验证前端 TypeScript 类型**

```powershell
npm run check
```
预期：vue-tsc 类型检查通过

---

### 任务 7：全量编译测试

**文件：**
- （无代码变更）

- [ ] **步骤 1：运行 pytest 验证所有后端测试通过**

```powershell
.venv\Scripts\python.exe -m pytest tests/ -v
```
预期：全部 PASS

- [ ] **步骤 2：运行 TypeScript 类型检查**

```powershell
npm run check
```
预期：vue-tsc 通过

- [ ] **步骤 3：运行 Vite 构建**

```powershell
npx vite build
```
预期：构建成功，dist/ 目录输出

- [ ] **步骤 4：运行完整构建**

```powershell
npm run build
```
预期：electron-builder 输出到 release28/
