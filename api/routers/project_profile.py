"""api/routers/project_profile.py — 项目画像 CRUD。"""

import os
import json
from fastapi import APIRouter, Body
from utils import get_app_data_dir

router = APIRouter(prefix="/api/project-profile", tags=["project-profile"])

DEFAULT_PROFILE = {
    "game_name": "",
    "genre": "",
    "world_setting": "",
    "target_audience": "",
    "terminology": {},
    "template_sections": ["背景", "目标", "规则", "奖励", "限制", "UI"],
    "design_principles": [],
}


def _get_profile_path(data_dir=None):
    """获取项目画像 JSON 文件的路径。

    Args:
        data_dir: 可选，指定数据目录（用于测试注入）。

    Returns:
        项目画像 JSON 文件的绝对路径。
    """
    if data_dir:
        return os.path.join(data_dir, "project_profile.json")
    env_dir = os.environ.get("GB_DATA_DIR", "")
    if env_dir:
        return os.path.join(env_dir, "project_profile.json")
    return os.path.join(get_app_data_dir(), "project_profile.json")


def load_profile(data_dir=None):
    """加载项目画像数据。

    Args:
        data_dir: 可选，指定数据目录（用于测试注入）。

    Returns:
        包含项目画像数据的字典。
    """
    path = _get_profile_path(data_dir)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {**DEFAULT_PROFILE, **data}
        except Exception:
            pass
    return dict(DEFAULT_PROFILE)


def save_profile(profile: dict, data_dir=None):
    """保存项目画像数据。

    Args:
        profile: 要保存的项目画像数据字典。
        data_dir: 可选，指定数据目录（用于测试注入）。
    """
    path = _get_profile_path(data_dir)
    merged = {**DEFAULT_PROFILE, **profile}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)


@router.get("")
async def get_profile():
    """获取项目画像。"""
    return {"success": True, "data": load_profile()}


@router.put("")
async def update_profile(payload: dict = Body(...)):
    """更新项目画像。"""
    save_profile(payload)
    return {"success": True, "data": load_profile()}


@router.delete("")
async def reset_profile():
    """重置项目画像为默认值。"""
    save_profile(dict(DEFAULT_PROFILE))
    return {"success": True, "data": dict(DEFAULT_PROFILE)}
