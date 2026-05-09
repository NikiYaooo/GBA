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

    if not requirements:
        raise HTTPException(status_code=400, detail="需求不能为空")

    try:
        result = await get_ai_service().imitate(model, requirements, context, use_rag=use_rag)
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
