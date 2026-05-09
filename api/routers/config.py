import os
from fastapi import APIRouter, Body, Request
from utils import get_app_data_dir, load_json, save_json

router = APIRouter(tags=["config"])


def _config_db():
    return os.path.join(get_app_data_dir(), "config.json")


@router.get("/api/config")
async def get_config():
    config = load_json(_config_db(), {"models": {}})
    return {"success": True, "data": config}


@router.post("/api/config")
async def save_config(payload: dict = Body(...)):
    existing = load_json(_config_db(), {})
    existing.update(payload)
    save_json(_config_db(), existing)
    return {"success": True}


@router.get("/api/tools/config")
async def get_tools_config():
    config = load_json(_config_db(), {})
    tools = config.get("tools", {})
    return {"success": True, "data": {"svn": tools.get("svn", []), "nav": tools.get("nav", [])}}


@router.put("/api/tools/config")
async def save_tools_config(payload: dict = Body(...)):
    config = load_json(_config_db(), {})
    tools = config.get("tools", {})
    if "svn" in payload:
        tools["svn"] = payload["svn"]
    if "nav" in payload:
        tools["nav"] = payload["nav"]
    config["tools"] = tools
    save_json(_config_db(), config)
    return {"success": True}


@router.get("/api/models/available")
async def get_available_models():
    return {
        "success": True,
        "data": {
            "models": [
                {"name": "豆包", "type": "cloud", "available": True},
                {"name": "DeepSeek", "type": "cloud", "available": True},
                {"name": "GPT-4o", "type": "cloud", "available": True},
                {"name": "Gemini", "type": "cloud", "available": True},
                {"name": "Kimi", "type": "cloud", "available": True},
                {"name": "GLM", "type": "cloud", "available": True},
                {"name": "Ollama (本地)", "type": "local", "available": True}
            ]
        }
    }
