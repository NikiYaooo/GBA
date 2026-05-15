"""图片库 API 路由（保存、列表、删除、重命名）"""

import os
import uuid
import base64
from datetime import datetime
from fastapi import APIRouter, Body, HTTPException
from utils import get_app_data_dir, ensure_dir, load_json, save_json

router = APIRouter(tags=["image_library"])

DATA_DIR = get_app_data_dir()
LIBRARY_DB = os.path.join(DATA_DIR, "image_library.json")
IMAGES_DIR = os.path.join(DATA_DIR, "images")
ensure_dir(IMAGES_DIR)


def _load_library():
    data = load_json(LIBRARY_DB)
    if not data or "images" not in data:
        return {"images": []}
    return data


def _save_library(data: dict):
    save_json(LIBRARY_DB, data)


@router.get("/api/images/library")
async def list_images():
    """获取图片库列表"""
    lib = _load_library()
    return {"success": True, "data": lib}


@router.post("/api/images/library")
async def save_image(payload: dict = Body(...)):
    """保存图片到图片库"""
    data_uri = payload.get("data_uri", "")
    name = payload.get("name", "").strip() or "未命名图片"
    if not data_uri:
        return {"success": False, "message": "缺少图片数据"}

    # Decode and save image file
    try:
        header, b64data = data_uri.split(",", 1)
    except ValueError:
        return {"success": False, "message": "图片数据格式错误"}

    img_id = uuid.uuid4().hex[:12]
    ext = "png"
    filename = f"{img_id}.{ext}"
    filepath = os.path.join(IMAGES_DIR, filename)

    try:
        img_bytes = base64.b64decode(b64data)
        with open(filepath, "wb") as f:
            f.write(img_bytes)
    except Exception as e:
        return {"success": False, "message": f"保存文件失败: {str(e)}"}

    # Add to library index
    lib = _load_library()
    lib["images"].insert(0, {
        "id": img_id,
        "name": name,
        "filename": filename,
        "created_at": datetime.now().isoformat(),
    })
    _save_library(lib)

    return {"success": True, "message": "已保存到图片库", "data": {"id": img_id}}


@router.get("/api/images/library/{image_id}/data")
async def get_image_data(image_id: str):
    """获取图片的 base64 数据"""
    filepath = os.path.join(IMAGES_DIR, f"{image_id}.png")
    if not os.path.exists(filepath):
        # Try to find by checking all files (in case ext differs)
        lib = _load_library()
        entry = next((img for img in lib.get("images", []) if img["id"] == image_id), None)
        if not entry:
            raise HTTPException(status_code=404, detail="图片不存在")
        filepath = os.path.join(IMAGES_DIR, entry["filename"])
        if not os.path.exists(filepath):
            raise HTTPException(status_code=404, detail="图片文件不存在")

    try:
        with open(filepath, "rb") as f:
            img_bytes = f.read()
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        return {"success": True, "data": {"data_uri": f"data:image/png;base64,{b64}"}}
    except Exception as e:
        return {"success": False, "message": f"读取图片失败: {str(e)}"}


@router.put("/api/images/library/{image_id}")
async def rename_image(image_id: str, payload: dict = Body(...)):
    """重命名图片"""
    name = payload.get("name", "").strip()
    if not name:
        return {"success": False, "message": "名称不能为空"}

    lib = _load_library()
    entry = next((img for img in lib.get("images", []) if img["id"] == image_id), None)
    if not entry:
        return {"success": False, "message": "图片不存在"}

    entry["name"] = name
    _save_library(lib)
    return {"success": True, "message": "已重命名"}


@router.delete("/api/images/library/{image_id}")
async def delete_image(image_id: str):
    """删除图片"""
    lib = _load_library()
    entry = next((img for img in lib.get("images", []) if img["id"] == image_id), None)
    if not entry:
        return {"success": False, "message": "图片不存在"}

    # Delete file
    filepath = os.path.join(IMAGES_DIR, entry["filename"])
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
    except Exception:
        pass

    lib["images"] = [img for img in lib["images"] if img["id"] != image_id]
    _save_library(lib)
    return {"success": True, "message": "已删除"}
