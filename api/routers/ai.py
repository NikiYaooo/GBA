from fastapi import APIRouter, HTTPException, Body
from ai_service import AIService

router = APIRouter(prefix="/api/ai", tags=["ai"])


def get_ai_service() -> AIService:
    return router.ai_service


@router.post("/quality-check")
async def quality_check(payload: dict = Body(...)):
    model = payload.get("model", "DeepSeek")
    content = payload.get("content", "")
    system_prompt = payload.get("system_prompt", "")

    if not content:
        raise HTTPException(status_code=400, detail="内容不能为空")

    try:
        result = await get_ai_service().quality_check(model, content, system_prompt=system_prompt or None)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "message": f"AI 服务调用失败: {str(e)}"}


@router.post("/imitate")
async def imitate(payload: dict = Body(...)):
    model = payload.get("model", "DeepSeek")
    requirements = payload.get("requirements", "")
    context = payload.get("context", "")
    use_rag = payload.get("use_rag", True)
    output_format = payload.get("format", "html")  # 默认输出 HTML（适配 TipTap）
    template_content = payload.get("template_content", "")
    images = payload.get("images", [])  # base64 data URI 数组

    if not requirements:
        raise HTTPException(status_code=400, detail="需求不能为空")

    try:
        result = await get_ai_service().imitate(model, requirements, context, use_rag=use_rag, output_format=output_format, template_content=template_content, images=images)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "message": f"AI 服务调用失败: {str(e)}"}


@router.post("/complete-logic")
async def complete_logic(payload: dict = Body(...)):
    model = payload.get("model", "DeepSeek")
    content = payload.get("content", "")

    if not content:
        raise HTTPException(status_code=400, detail="内容不能为空")

    try:
        result = await get_ai_service().complete_logic(model, content)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "message": f"AI 服务调用失败: {str(e)}"}


@router.post("/generate-ui")
async def generate_ui(payload: dict = Body(...)):
    """根据文档内容生成 UI 原型图。"""
    model = payload.get("model", "GPT")
    content = payload.get("content", "")
    design_prompt = payload.get("design_prompt", "")
    count = min(int(payload.get("count", 4)), 8)

    if not content:
        raise HTTPException(status_code=400, detail="文档内容不能为空")

    if not design_prompt:
        design_prompt = "手游UI，系统界面原型图，简洁风格，轻质感，柔和阴影，圆角控件，适当效果，浅蓝白配色，专业游戏UI设计，符合交互逻辑，高清，高细节，原型图+标题描述"

    try:
        result = await get_ai_service().generate_ui_images(model, content, design_prompt, n=count)
        return result
    except Exception as e:
        return {"success": False, "message": f"图片生成失败: {str(e)}"}
