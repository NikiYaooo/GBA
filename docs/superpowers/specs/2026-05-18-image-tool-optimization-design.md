# 图片工具优化设计文档

## 概述

优化图片工具的图片修改模式，修复豆包 Seedream 模型在修改模式下的 Bug，并全面改进涂抹交互体验和编辑质量。

## 问题分析

### Bug: 豆包 Seedream 修改模式 HTTP 400

`api/routers/image_gen.py` 中 `_crop_edit()` 函数在调用豆包 ARK 生图 API 时使用 `"size": "1024x1024"`（第 179 行）。豆包 Seedream 要求图片 `size >= 3,686,400` 像素（即 `1920x1920`），导致接口返回 400 错误。

### 设计问题: Crop-Edit 方案质量有限

对于不支持原生 mask 编辑的模型，当前的裁剪合成方案存在以下问题：
- 用 text2image 独立生成裁剪区域，缺少原图上下文，风格不匹配
- prompt 硬编码，缺乏针对具体图片的分析
- 边缘融合算法简单，可能存在接缝

### 前端交互

- 画笔光标定位可能存在 canvas 坐标与 CSS 坐标混用问题
- 缺少橡皮擦功能
- 掩码覆盖层不够醒目
- 提交前缺少 mask 预览

## 方案设计

### 架构

采用混合方案（Hybrid Approach）：优先使用每个模型的原生编辑 API，不支持时回退到改进版 LLM 增强的 Crop-Edit。

```
用户涂抹区域 → 输入修改需求 → POST /api/image/edit →
  ├─ GPT-Image 2 → DALL-E 2 edits API（不变）
  ├─ 豆包 Seedream → 优先 ARK /api/v3/images/edits
  │                    └─ 失败回退 → LLM 增强 Crop-Edit
  ├─ Qwen-Image 2 → LLM 增强 Crop-Edit（DashScope 无公开编辑接口）
  └─ 其他模型 → LLM 增强 Crop-Edit
```

### 详细设计

#### 1. 前端：ImageToolDialog.vue

##### 画笔交互改进

- 统一 mousePos 坐标系，解决 CSS 定位偏移问题
- 增加橡皮擦模式：toggle 按钮切换涂抹/擦除，擦除使用 `globalCompositeOperation = 'destination-out'`
- 右键擦除：在 `onMouseDown` 中检测 `e.button === 2` 切换为擦除

##### 覆盖层视觉改进

- 涂抹区域使用 `rgba(255, 0, 0, 0.5)` 半透明红色，更加醒目
- 提交前 mask 预览：在确认弹窗中展示当前 mask 效果
- 显示涂抹进度：画布角落展示"已涂抹 X% 区域"

##### 交互细节

- Ctrl 键按住时临时切换为擦除模式（`onMouseDown` 中检测 `e.ctrlKey`）
- 提交按钮增加禁用状态：mask 全白（未涂抹）时置灰
- brush cursor preview 圆圈适配 canvas 缩放比例

##### UI 布局调整

```
修改模式界面：
  标题区域: "在图片上涂抹要修改的区域（左键涂抹 / 右键擦除 / Ctrl 擦除）"
  工具栏: 画笔大小 [slider] 20px | [橡皮擦按钮] | [清除涂抹]
  画布区域: 原图 + 红色半透明覆盖层
  状态栏: "已涂抹 3.2% 区域"
  输入区: [修改需求输入框] [确认修改] [返回]
```

#### 2. 后端：image_gen.py

##### `_native_edit_ark()` — 豆包 Seedream 原生编辑

```
_native_edit_ark(prompt: str, data_uri: str, mask_uri: str,
                  api_key: str, model_id: str) -> str
```

- 将原图和 mask 解析为二进制
- 对齐 mask 尺寸到原图尺寸
- POST `https://ark.cn-beijing.volces.com/api/v3/images/edits`
  - multipart/form-data: image, mask, prompt, n=1, size=原图尺寸
- 解析返回的 `b64_json` 或 `url`
- 返回 `data:image/png;base64,...`

##### `_llm_crop_edit()` — LLM 增强的裁剪合成方案

替代原有的 `_crop_edit()`，核心变化：

1. **LLM 分析原图**：如果配置了多模态 LLM（doubao-vision、GPT-4V），将原图发送给 LLM 分析风格、色调、构图；否则使用 PIL 提取图片主色调、亮度等基本信息

2. **增强 prompt**：基于 LLM 分析结果 + mask 区域描述 + 用户需求 → 生成高质量的编辑提示

3. **修复 size 参数**：豆包模型使用 `"size": "1920x1920"`（满足最低像素要求）

4. **增加 crop padding**：从 15% 增加到 25%，提供更多上下文

5. **改进边缘融合**：双阶段高斯羽化（粗羽化半径 10 + 精羽化半径 3）

##### edit_image() 路由重组

```python
@router.post("/api/image/edit")
async def edit_image(payload):
    model_name = ...
    prompt = ...
    data_uri = ...
    mask_uri = ...

    # 获取配置
    config = _get_config()
    model_configs = config.get("models", {})

    if model_name == "GPT-Image 2":
        # 使用 DALL-E 2 edits（现有逻辑）
        ...

    elif model_name == "豆包Seedream":
        # 优先原生编辑
        try:
            result = await _native_edit_ark(...)
            return {"success": True, "data": {"data_uri": result}}
        except Exception as e:
            # 回退 LLM 增强 Crop-Edit
            logger.warning(f"原生编辑失败，回退 Crop-Edit: {e}")
            result = await _llm_crop_edit(...)
            return {"success": True, "data": {"data_uri": result}}

    elif model_name == "Qwen-Image 2":
        result = await _llm_crop_edit(...)
        return {"success": True, "data": {"data_uri": result}}

    else:
        return {"success": False, "message": f"{model_name} 修改功能暂未实现"}
```

#### 3. 错误处理

| 场景 | 处理方式 |
|---|---|
| 豆包原生编辑返回 400 | 捕获异常，自动回退到 `_llm_crop_edit` |
| 用户选择不支持编辑的模型 | 前端在"确认修改"按钮旁显示提示 |
| 未涂抹区域提交 | 前端检测 mask 全白，禁用确认按钮 |
| mask 尺寸不匹配 | 后端使用 `LANCZOS` 缩放到原图尺寸 |
| LLM 分析超时/失败 | 跳过 LLM 分析，使用原始 prompt + 默认参数 |

### 文件变更清单

| 文件 | 改动内容 |
|---|---|
| `src/components/dialogs/ImageToolDialog.vue` | 修复画笔交互、增加橡皮擦、mask 预览、交互优化 |
| `api/routers/image_gen.py` | 新增 `_native_edit_ark()`、重写 `_crop_edit` → `_llm_crop_edit`、重构 edit_image 路由 |
| `tests/test_image_edit.py` | 新增测试（mask 检测、裁剪逻辑、合成逻辑） |
