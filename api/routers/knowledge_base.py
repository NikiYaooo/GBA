import os
import uuid
from urllib.parse import unquote
from fastapi import APIRouter, Body, Request
from document_parser import DocumentParser
from utils import get_app_data_dir, load_json, save_json

router = APIRouter(prefix="/api/kb", tags=["knowledge_base"])


def get_kb():
    return router.kb


def _upload_dir():
    d = os.path.join(get_app_data_dir(), "uploads")
    os.makedirs(d, exist_ok=True)
    return d


@router.post("/upload")
async def kb_upload_raw(request: Request):
    filename = request.headers.get("X-Filename", "").strip()
    if filename:
        try:
            filename = unquote(filename)
        except Exception:
            pass
    if not filename:
        return {"success": False, "message": "缺少文件名 (X-Filename header)"}

    safe_filename = os.path.basename(filename)
    if not safe_filename:
        return {"success": False, "message": "文件名无效"}

    file_id = str(uuid.uuid4())
    ext = os.path.splitext(safe_filename)[1]
    save_filename = f"kb_{file_id}{ext}"
    file_path = os.path.join(_upload_dir(), save_filename)

    try:
        raw_bytes = await request.body()
        if not raw_bytes or len(raw_bytes) < 20:
            return {"success": False, "message": "上传内容为空或文件过小"}

        with open(file_path, "wb") as buffer:
            buffer.write(raw_bytes)

        content = DocumentParser.parse(file_path)
        if isinstance(content, str) and content.startswith("DOCX 解析错误"):
            return {"success": False, "message": content}

        ext = os.path.splitext(safe_filename)[1].lower().lstrip('.')
        if not ext:
            ext = "unknown"

        result = get_kb().add_document(
            file_path=file_path, filename=safe_filename,
            content=str(content), doc_type=ext, file_size=len(raw_bytes)
        )
        return {"success": bool(result.get("success")), "message": result.get("message", "")}
    except Exception as e:
        return {"success": False, "message": f"入库失败: {str(e)}"}


@router.get("/stats")
async def kb_stats():
    try:
        stats = get_kb().get_stats()
        config = load_json(os.path.join(get_app_data_dir(), "config.json"), {})
        stats["chunk_size_min"] = config.get("chunk_size_min", 100)
        stats["chunk_size_max"] = config.get("chunk_size_max", 500)
        return {"success": True, "data": stats}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/chunk-size")
async def set_kb_chunk_size(payload: dict = Body(...)):
    cmin = int(payload.get("min", 100))
    cmax = int(payload.get("max", 500))
    if cmin < 50: cmin = 50
    if cmax > 1000: cmax = 1000
    if cmin >= cmax: cmax = cmin + 50

    config_path = os.path.join(get_app_data_dir(), "config.json")
    config = load_json(config_path, {})
    config["chunk_size_min"] = cmin
    config["chunk_size_max"] = cmax
    save_json(config_path, config)

    get_kb()._chunk_size_min = cmin
    get_kb()._chunk_size_max = cmax
    return {"success": True, "data": {"chunk_size_min": cmin, "chunk_size_max": cmax}}


@router.post("/rechunk")
async def kb_rechunk():
    try:
        result = get_kb().rechunk_all()
        return result
    except Exception as e:
        return {"success": False, "message": f"重新分块失败: {str(e)}"}


@router.delete("/document/{file_hash}")
async def kb_delete_doc(file_hash: str):
    try:
        result = get_kb().delete_document(file_hash)
        return {"success": result.get("success", False)}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/clear")
async def kb_clear():
    try:
        result = get_kb().clear_all()
        return {"success": result.get("success", False)}
    except Exception as e:
        return {"success": False, "message": str(e)}
