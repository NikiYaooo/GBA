import os
import time
from fastapi import APIRouter, Body
from utils import get_app_data_dir, load_json, save_json
from default_prompts import DEFAULT_PROMPTS

router = APIRouter(prefix="/api/prompts", tags=["prompts"])


def _prompts_db():
    return os.path.join(get_app_data_dir(), "prompts.json")


def _load_prompts():
    try:
        data = load_json(_prompts_db(), None)
        if isinstance(data, dict) and data.get("professions"):
            return data
    except Exception:
        pass
    return DEFAULT_PROMPTS


@router.get("/professions")
async def get_professions():
    prompts = _load_prompts()
    result = []
    for p in prompts.get("professions", []):
        result.append({
            "id": p["id"], "name": p["name"],
            "role_count": len(p.get("roles", [])),
            "prompts": p.get("prompts", [])
        })
    return {"success": True, "data": result}


@router.get("/professions/{profession_id}")
async def get_roles(profession_id: str):
    prompts = _load_prompts()
    for p in prompts.get("professions", []):
        if p["id"] == profession_id:
            return {"success": True, "data": p.get("roles", [])}
    return {"success": False, "message": "未找到该职业"}


@router.post("/roles")
async def add_or_update_role(payload: dict = Body(...)):
    profession_id = payload.get("profession_id", "")
    role = payload.get("role", {})
    if not profession_id or not role:
        return {"success": False, "message": "参数不完整"}

    prompts = _load_prompts()
    for p in prompts.get("professions", []):
        if p["id"] == profession_id:
            existing = [r for r in p.get("roles", []) if r["id"] == role.get("id")]
            if existing:
                for r in p["roles"]:
                    if r["id"] == role["id"]:
                        r.update(role)
            else:
                p.setdefault("roles", []).append(role)
            save_json(_prompts_db(), prompts)
            return {"success": True}
    return {"success": False, "message": "未找到该职业"}


@router.delete("/roles/{role_id}")
async def delete_role(role_id: str, profession_id: str = ""):
    prompts = _load_prompts()
    for p in prompts.get("professions", []):
        if not profession_id or p["id"] == profession_id:
            p["roles"] = [r for r in p.get("roles", []) if r["id"] != role_id]
            save_json(_prompts_db(), prompts)
            return {"success": True}
    return {"success": False, "message": "未找到该角色"}


@router.post("/init-defaults")
async def init_default_prompts():
    save_json(_prompts_db(), DEFAULT_PROMPTS)
    return {"success": True}


@router.put("/profession/{profession_id}")
async def update_profession_prompt(profession_id: str, payload: dict = Body(...)):
    prompts = _load_prompts()
    for p in prompts.get("professions", []):
        if p["id"] == profession_id:
            if "prompts" in payload:
                p["prompts"] = payload["prompts"]
            save_json(_prompts_db(), prompts)
            return {"success": True}
    return {"success": False, "message": "未找到该职业"}


@router.put("/profession/{profession_id}/add-prompt")
async def add_profession_prompt(profession_id: str, payload: dict = Body(...)):
    prompt_name = payload.get("name", "新Prompt")
    prompt_content = payload.get("content", "")
    if not prompt_content.strip():
        return {"success": False, "message": "内容不能为空"}
    prompts = _load_prompts()
    for p in prompts.get("professions", []):
        if p["id"] == profession_id:
            pid = "p_" + str(int(time.time()))
            p.setdefault("prompts", []).append({
                "id": pid, "name": prompt_name, "content": prompt_content
            })
            save_json(_prompts_db(), prompts)
            return {"success": True, "data": {"id": pid, "name": prompt_name, "content": prompt_content}}
    return {"success": False, "message": "未找到该职业"}


@router.delete("/profession/{profession_id}/prompt/{prompt_id}")
async def delete_profession_prompt(profession_id: str, prompt_id: str):
    prompts = _load_prompts()
    for p in prompts.get("professions", []):
        if p["id"] == profession_id:
            p["prompts"] = [pp for pp in p.get("prompts", []) if pp.get("id") != prompt_id]
            save_json(_prompts_db(), prompts)
            return {"success": True}
    return {"success": False, "message": "未找到该职业"}
