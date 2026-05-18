import os
import uuid
from fastapi import APIRouter, Body, Request
from document_parser import DocumentParser
from utils import get_app_data_dir, load_json, save_json

router = APIRouter(prefix="/api/template", tags=["template"])


def _template_dir():
    d = os.path.join(get_app_data_dir(), "template")
    os.makedirs(d, exist_ok=True)
    return d


def _template_meta_path():
    return os.path.join(get_app_data_dir(), "template.json")


def _get_template_meta() -> dict:
    return load_json(_template_meta_path(), {})


def _save_template_meta(meta: dict):
    save_json(_template_meta_path(), meta)


@router.post("/upload")
async def upload_template(request: Request):
    """上传文档模板（.docx），替换已有模板。"""
    filename = request.headers.get("X-Filename", "").strip()
    if not filename:
        return {"success": False, "message": "缺少文件名"}

    ext = os.path.splitext(filename)[1].lower()
    if ext != '.docx':
        return {"success": False, "message": "仅支持 .docx 格式模板"}

    try:
        raw_bytes = await request.body()
        if not raw_bytes or len(raw_bytes) < 20:
            return {"success": False, "message": "文件内容为空"}

        # 删除旧模板
        old_meta = _get_template_meta()
        old_path = old_meta.get("path", "")
        if old_path and os.path.exists(old_path):
            try:
                os.remove(old_path)
            except Exception:
                pass

        # 保存新模板
        file_id = uuid.uuid4().hex
        save_path = os.path.join(_template_dir(), f"template_{file_id}{ext}")
        with open(save_path, "wb") as f:
            f.write(raw_bytes)

        # 解析模板内容
        content = DocumentParser.parse(save_path)

        meta = {
            "id": file_id,
            "name": filename,
            "path": save_path,
            "uploaded_at": __import__('time').time(),
        }
        _save_template_meta(meta)

        return {
            "success": True,
            "data": {
                "id": file_id,
                "name": filename,
                "content": content,
            }
        }
    except Exception as e:
        return {"success": False, "message": f"模板上传失败: {str(e)}"}


@router.get("")
async def get_template():
    """获取当前模板信息。"""
    meta = _get_template_meta()
    if not meta.get("path") or not os.path.exists(meta.get("path", "")):
        return {"success": True, "data": {"exists": False}}
    return {
        "success": True,
        "data": {
            "exists": True,
            "id": meta.get("id", ""),
            "name": meta.get("name", ""),
            "uploaded_at": meta.get("uploaded_at", 0),
        }
    }


@router.get("/content")
async def get_template_content():
    """获取模板的解析内容（HTML）。"""
    meta = _get_template_meta()
    if not meta.get("path") or not os.path.exists(meta.get("path", "")):
        return {"success": False, "message": "未上传模板"}
    try:
        content = DocumentParser.parse(meta["path"])
        return {"success": True, "data": {"content": content}}
    except Exception as e:
        return {"success": False, "message": f"模板解析失败: {str(e)}"}


@router.delete("")
async def delete_template():
    """删除当前模板。"""
    meta = _get_template_meta()
    old_path = meta.get("path", "")
    if old_path and os.path.exists(old_path):
        try:
            os.remove(old_path)
        except Exception:
            pass
    _save_template_meta({})
    return {"success": True, "message": "模板已删除"}
