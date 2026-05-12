import os
import json
from fastapi import APIRouter, Body, Request
from utils import get_app_data_dir, load_json, save_json


def get_launcher_config_path():
    """固定路径的启动配置，用于跨版本持久化存储数据目录等设置。"""
    if os.name == 'nt':
        app_data = os.environ.get('APPDATA')
        if not app_data:
            app_data = os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming')
        config_dir = os.path.join(app_data, 'GameBuilderAIHelper')
    else:
        config_dir = os.path.join(os.path.expanduser('~'), '.gamebuilder_aihelper')
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, 'launcher-config.json')

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


@router.get("/api/config/data-path")
async def get_data_path():
    config_path = get_launcher_config_path()
    config = load_json(config_path, {})
    return {"success": True, "data": {"path": config.get("dataPath", "")}}


@router.post("/api/config/data-path")
async def save_data_path(payload: dict = Body(...)):
    path = payload.get("path", "").strip()
    config_path = get_launcher_config_path()
    config = load_json(config_path, {})
    config["dataPath"] = path
    save_json(config_path, config)
    return {"success": True, "message": "保存成功，重启应用后生效"}


@router.get("/api/models/available")
async def get_available_models():
    return {
        "success": True,
        "data": {
            "models": [
                {"name": "豆包", "type": "cloud", "available": True},
                {"name": "DeepSeek", "type": "cloud", "available": True},
                {"name": "GPT", "type": "cloud", "available": True},
                {"name": "Gemini", "type": "cloud", "available": True},
                {"name": "Kimi", "type": "cloud", "available": True},
                {"name": "GLM", "type": "cloud", "available": True},
                {"name": "Ollama (本地)", "type": "local", "available": True}
            ]
        }
    }
