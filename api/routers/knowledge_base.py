import os
import uuid
import time
import asyncio
import concurrent.futures
from typing import Dict
from urllib.parse import unquote
from fastapi import APIRouter, Body, Request
from document_parser import DocumentParser
from utils import get_app_data_dir, load_json, save_json

router = APIRouter(prefix="/api/kb", tags=["knowledge_base"])

# 后台导入进度跟踪
_import_tasks: Dict[str, Dict] = {}
_thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)

SUPPORTED_EXTS = {'.docx', '.md', '.txt', '.xlsx', '.xls'}


def get_kb():
    return router.kb


def _upload_dir():
    d = os.path.join(get_app_data_dir(), "uploads")
    os.makedirs(d, exist_ok=True)
    return d


def _scan_folder(path: str) -> list:
    """扫描文件夹下所有支持的文档，返回文件信息列表。"""
    if not os.path.isdir(path):
        return []
    files = []
    for root, dirs, names in os.walk(path):
        for name in sorted(names):
            ext = os.path.splitext(name)[1].lower()
            if ext in SUPPORTED_EXTS:
                full = os.path.join(root, name)
                files.append({
                    "name": name,
                    "path": full,
                    "size": os.path.getsize(full),
                    "ext": ext.lstrip('.'),
                })
    return files


def _run_folder_import(task_id: str, folder_path: str, kb, file_paths: list = None) -> None:
    """在后台线程中执行文件夹导入。"""
    import numpy as np
    try:
        _import_tasks[task_id]["status"] = "scanning"
        _import_tasks[task_id]["message"] = "扫描文件夹中..."

        if file_paths:
            # 使用前端指定的文件列表
            files = []
            for fp in file_paths:
                if not os.path.isfile(fp):
                    continue
                ext = os.path.splitext(fp)[1].lower()
                files.append({
                    "name": os.path.basename(fp),
                    "path": fp,
                    "size": os.path.getsize(fp),
                    "ext": ext.lstrip('.'),
                })
        else:
            files = _scan_folder(folder_path)
        if not files:
            _import_tasks[task_id]["status"] = "error"
            _import_tasks[task_id]["message"] = "文件夹中没有找到支持的文档"
            return

        total = len(files)
        _import_tasks[task_id]["total_files"] = total
        _import_tasks[task_id]["succeeded_files"] = 0
        _import_tasks[task_id]["skipped_files"] = 0
        _import_tasks[task_id]["message"] = f"找到 {total} 个文档，开始导入..."

        succeeded = 0
        skipped = 0
        for idx, f in enumerate(files):
            if _import_tasks.get(task_id, {}).get("cancelled"):
                _import_tasks[task_id]["status"] = "cancelled"
                _import_tasks[task_id]["message"] = "已取消"
                _import_tasks[task_id]["succeeded_files"] = succeeded
                _import_tasks[task_id]["skipped_files"] = skipped
                return

            # 暂停检测
            while _import_tasks.get(task_id, {}).get("paused"):
                if _import_tasks.get(task_id, {}).get("cancelled"):
                    _import_tasks[task_id]["status"] = "cancelled"
                    _import_tasks[task_id]["message"] = "已取消"
                    _import_tasks[task_id]["succeeded_files"] = succeeded
                    _import_tasks[task_id]["skipped_files"] = skipped
                    return
                time.sleep(0.5)

            _import_tasks[task_id]["status"] = "importing"
            _import_tasks[task_id]["current_file"] = f["name"]
            _import_tasks[task_id]["processed_files"] = idx + 1
            _import_tasks[task_id]["progress"] = int((idx + 1) / total * 100)
            _import_tasks[task_id]["succeeded_files"] = succeeded
            _import_tasks[task_id]["skipped_files"] = skipped

            try:
                content = DocumentParser.parse(f["path"])
                if isinstance(content, str) and ("解析错误" in content[:50] or "不支持" in content[:50]):
                    skipped += 1
                    continue

                result = kb.add_document(
                    file_path=f["path"],
                    filename=f["name"],
                    content=str(content),
                    doc_type=f["ext"],
                    file_size=f["size"],
                )
                if result.get("success"):
                    succeeded += 1
                else:
                    skipped += 1
            except Exception:
                skipped += 1
                continue

        _import_tasks[task_id]["status"] = "done"
        _import_tasks[task_id]["processed_files"] = total
        _import_tasks[task_id]["succeeded_files"] = succeeded
        _import_tasks[task_id]["skipped_files"] = skipped
        _import_tasks[task_id]["progress"] = 100
        parts = [f"导入完成，成功 {succeeded} 个"]
        if skipped > 0:
            parts.append(f"，跳过 {skipped} 个")
        _import_tasks[task_id]["message"] = "".join(parts)
    except Exception as e:
        _import_tasks[task_id]["status"] = "error"
        _import_tasks[task_id]["message"] = f"导入失败: {str(e)}"


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


@router.post("/scan-folder")
async def kb_scan_folder(payload: dict = Body(...)):
    """扫描文件夹，返回支持的文档列表。"""
    folder_path = payload.get("path", "").strip()
    if not folder_path:
        return {"success": False, "message": "请提供文件夹路径"}
    if not os.path.isdir(folder_path):
        return {"success": False, "message": "路径不存在或不是文件夹"}
    files = _scan_folder(folder_path)
    return {"success": True, "data": {"files": files, "total": len(files)}}


@router.post("/import-folder")
async def kb_import_folder(payload: dict = Body(...)):
    """异步导入文件夹中所有文档，返回 task_id 用于轮询进度。"""
    folder_path = payload.get("path", "").strip()
    if not folder_path:
        return {"success": False, "message": "请提供文件夹路径"}
    if not os.path.isdir(folder_path):
        return {"success": False, "message": "路径不存在或不是文件夹"}

    task_id = str(uuid.uuid4())
    _import_tasks[task_id] = {
        "status": "pending",
        "progress": 0,
        "message": "等待开始...",
        "total_files": 0,
        "processed_files": 0,
        "current_file": "",
    }
    file_paths = payload.get("files")
    loop = asyncio.get_event_loop()
    loop.run_in_executor(_thread_pool, _run_folder_import, task_id, folder_path, get_kb(), file_paths)
    return {"success": True, "data": {"task_id": task_id}}


@router.get("/import-progress/{task_id}")
async def kb_import_progress(task_id: str):
    """查询导入进度。"""
    task = _import_tasks.get(task_id)
    if not task:
        return {"success": False, "message": "任务不存在"}
    return {"success": True, "data": dict(task)}


@router.post("/import-pause/{task_id}")
async def kb_import_pause(task_id: str):
    """暂停导入任务。"""
    task = _import_tasks.get(task_id)
    if not task:
        return {"success": False, "message": "任务不存在"}
    task["paused"] = True
    task["status"] = "paused"
    task["message"] = "已暂停"
    return {"success": True}


@router.post("/import-resume/{task_id}")
async def kb_import_resume(task_id: str):
    """继续导入任务。"""
    task = _import_tasks.get(task_id)
    if not task:
        return {"success": False, "message": "任务不存在"}
    task["paused"] = False
    task["status"] = "importing"
    task["message"] = "继续导入中..."
    return {"success": True}


@router.post("/import-stop/{task_id}")
async def kb_import_stop(task_id: str):
    """停止（取消）导入任务。"""
    task = _import_tasks.get(task_id)
    if not task:
        return {"success": False, "message": "任务不存在"}
    task["cancelled"] = True
    task["status"] = "cancelled"
    task["message"] = "已停止"
    return {"success": True}


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
