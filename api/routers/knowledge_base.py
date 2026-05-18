import os
import uuid
import json
from urllib.parse import unquote
from fastapi import APIRouter, Body, Request, HTTPException
from document_parser import DocumentParser
from utils import get_app_data_dir

router = APIRouter(prefix="/api/kb", tags=["knowledge_base"])

SUPPORTED_EXTS = {'.docx', '.md', '.txt', '.xlsx', '.xls', '.pdf'}


def get_kb():
    return router.kb


def _upload_dir():
    d = os.path.join(get_app_data_dir(), "uploads")
    os.makedirs(d, exist_ok=True)
    return d


# ── 项目管理 ──────────────────────────────────────────────

@router.post("/project")
async def create_project(payload: dict = Body(...)):
    name = payload.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="项目名称不能为空")
    description = payload.get("description", "")
    model = payload.get("embedding_model", "bge-small-zh")
    result = get_kb().create_project(name, description, model)
    return {"success": True, "data": result}


@router.get("/projects")
async def list_projects():
    projects = get_kb().list_projects()
    active_id = get_kb()._active_project_id
    return {"success": True, "data": {"projects": projects, "active_project_id": active_id}}


@router.put("/project/{project_id}")
async def update_project(project_id: str, payload: dict = Body(...)):
    kb = get_kb()
    if not kb.get_project_info(project_id):
        raise HTTPException(status_code=404, detail="项目不存在")
    result = kb.update_project(project_id, payload)
    return {"success": result["success"], "message": result.get("message")}


@router.delete("/project/{project_id}")
async def delete_project(project_id: str):
    result = get_kb().delete_project(project_id)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result.get("message", "项目不存在"))
    return {"success": True}


@router.post("/project/{project_id}/activate")
async def activate_project(project_id: str):
    kb = get_kb()
    if not kb.get_project(project_id):
        raise HTTPException(status_code=404, detail="项目不存在")
    kb._active_project_id = project_id
    kb._save_projects()
    return {"success": True}


@router.post("/project/{project_id}/archive")
async def archive_project(project_id: str):
    kb = get_kb()
    info = kb.get_project_info(project_id)
    if not info:
        raise HTTPException(status_code=404, detail="项目不存在")
    info["archived"] = not info.get("archived", False)
    kb._save_projects()
    return {"success": True, "data": {"archived": info["archived"]}}


# ── 文件夹管理 ────────────────────────────────────────────

@router.post("/project/{project_id}/folder")
async def create_folder(project_id: str, payload: dict = Body(...)):
    name = payload.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="文件夹名称不能为空")
    proj = get_kb().get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    result = proj.create_folder(name)
    return result


@router.put("/project/{project_id}/folder/{folder_id}")
async def rename_folder(project_id: str, folder_id: str, payload: dict = Body(...)):
    new_name = payload.get("name", "").strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="名称不能为空")
    proj = get_kb().get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    result = proj.rename_folder(folder_id, new_name)
    return result


@router.delete("/project/{project_id}/folder/{folder_id}")
async def delete_folder(project_id: str, folder_id: str):
    proj = get_kb().get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    result = proj.delete_folder(folder_id)
    return result


@router.get("/project/{project_id}/folders")
async def list_folders(project_id: str):
    proj = get_kb().get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"success": True, "data": {"folders": proj.folders}}


@router.post("/scan-directory")
async def scan_directory(payload: dict = Body(...)):
    """扫描本地目录，返回受支持的文件列表及其相对路径（用于文件夹分类）。"""
    directory = payload.get("path", "").strip()
    if not directory or not os.path.isdir(directory):
        raise HTTPException(status_code=400, detail="无效的目录路径")
    files = []
    for root, dirs, fnames in os.walk(directory):
        for fname in sorted(fnames):
            ext = os.path.splitext(fname)[1].lower()
            if ext in SUPPORTED_EXTS:
                full_path = os.path.join(root, fname)
                rel_path = os.path.relpath(full_path, directory)
                # 取第一级子目录作为文件夹分类名
                parts = rel_path.replace("\\", "/").split("/")
                folder_name = parts[0] if len(parts) > 1 else ""
                files.append({
                    "filename": fname,
                    "relative_path": rel_path.replace("\\", "/"),
                    "folder_name": folder_name if folder_name != fname else "",
                    "full_path": full_path,
                    "size": os.path.getsize(full_path),
                })
    return {"success": True, "data": {"files": files}}


# ── 文档管理 ──────────────────────────────────────────────

@router.post("/project/{project_id}/upload")
async def upload_document(project_id: str, request: Request):
    proj = get_kb().get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")

    filename = request.headers.get("X-Filename", "").strip()
    if filename:
        try:
            filename = unquote(filename)
        except Exception:
            pass
    folder_id = request.headers.get("X-Folder-Id", "")
    note = request.headers.get("X-Note", "")

    if not filename:
        form = await request.form()
        file = form.get("file")
        if not file:
            raise HTTPException(status_code=400, detail="缺少文件")
        filename = file.filename or "unknown"
        folder_id = form.get("folder_id", "")
        note = form.get("note", "")
        raw_bytes = await file.read()
    else:
        raw_bytes = await request.body()

    if not raw_bytes or len(raw_bytes) < 20:
        raise HTTPException(status_code=400, detail="文件内容为空")

    safe_filename = os.path.basename(filename)
    ext = os.path.splitext(safe_filename)[1].lower()
    file_id = str(uuid.uuid4())
    save_name = f"doc_{file_id}{ext}"
    file_path = os.path.join(_upload_dir(), save_name)
    with open(file_path, "wb") as f:
        f.write(raw_bytes)

    content = DocumentParser.parse(file_path)
    if isinstance(content, str) and "解析错误" in content[:50]:
        if os.path.exists(file_path):
            os.remove(file_path)
        return {"success": False, "message": content}

    doc_type = ext.lstrip(".") or "unknown"
    result = proj.add_document(
        file_path=file_path, filename=safe_filename,
        content=str(content), doc_type=doc_type,
        file_size=len(raw_bytes), folder_id=folder_id, note=note,
    )
    if os.path.exists(file_path):
        os.remove(file_path)
    return result


@router.post("/project/{project_id}/upload-multi")
async def upload_multiple(project_id: str, request: Request):
    proj = get_kb().get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    form = await request.form()
    results = []
    for key in form.keys():
        field = form.get(key)
        if hasattr(field, "filename") and field.filename:
            raw_bytes = await field.read()
            if not raw_bytes or len(raw_bytes) < 20:
                continue
            safe_name = os.path.basename(field.filename)
            ext = os.path.splitext(safe_name)[1].lower()
            if ext not in SUPPORTED_EXTS and ext not in {'.csv'}:
                continue
            file_id = str(uuid.uuid4())
            file_path = os.path.join(_upload_dir(), f"doc_{file_id}{ext}")
            with open(file_path, "wb") as f:
                f.write(raw_bytes)
            content = DocumentParser.parse(file_path)
            doc_type = ext.lstrip(".") or "unknown"
            result = proj.add_document(
                file_path=file_path, filename=safe_name,
                content=str(content) if content else "",
                doc_type=doc_type, file_size=len(raw_bytes),
            )
            results.append({"filename": safe_name, **result})
            if os.path.exists(file_path):
                os.remove(file_path)
    return {"success": True, "data": {"results": results, "total": len(results)}}


@router.post("/project/{project_id}/import-files")
async def import_files(project_id: str, payload: dict = Body(...)):
    """批量导入本地文件。files: [{path, folder_id?}]"""
    proj = get_kb().get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    files = payload.get("files", [])
    if not files:
        raise HTTPException(status_code=400, detail="文件列表不能为空")
    results = []
    for item in files:
        file_path = item.get("path", "")
        folder_id = item.get("folder_id", "")
        if not file_path or not os.path.isfile(file_path):
            results.append({"filename": os.path.basename(file_path), "success": False, "message": "文件不存在"})
            continue
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in SUPPORTED_EXTS:
            continue
        content = DocumentParser.parse(file_path)
        if isinstance(content, str) and "解析错误" in content[:50]:
            results.append({"filename": os.path.basename(file_path), "success": False, "message": content})
            continue
        safe_name = os.path.basename(file_path)
        doc_type = ext.lstrip(".") or "unknown"
        file_size = os.path.getsize(file_path)
        result = proj.add_document(
            file_path=file_path, filename=safe_name,
            content=str(content), doc_type=doc_type,
            file_size=file_size, folder_id=folder_id or None,
        )
        results.append({"filename": safe_name, **result})
    return {"success": True, "data": {"results": results, "total": len(results), "succeeded": sum(1 for r in results if r.get("success"))}}


@router.get("/project/{project_id}/documents")
async def list_documents(project_id: str, folder_id: str = ""):
    proj = get_kb().get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    docs = proj.get_documents(folder_id=folder_id or None)
    return {"success": True, "data": {"documents": docs, "total": len(docs)}}


@router.put("/project/{project_id}/doc/{doc_id}")
async def update_document(project_id: str, doc_id: str, payload: dict = Body(...)):
    proj = get_kb().get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    result = proj.update_document_meta(doc_id, payload)
    return result


@router.delete("/project/{project_id}/doc/{doc_id}")
async def delete_document(project_id: str, doc_id: str):
    proj = get_kb().get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    result = proj.delete_document(doc_id)
    return result


@router.delete("/project/{project_id}/documents")
async def clear_documents(project_id: str, folder_id: str = None):
    """批量删除项目下所有文档，可选按 folder_id 过滤。"""
    proj = get_kb().get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    docs = proj.get_documents(folder_id=folder_id or None)
    deleted = 0
    for doc in docs:
        result = proj.delete_document(doc["id"])
        if result.get("success"):
            deleted += 1
    return {"success": True, "data": {"deleted": deleted, "total": len(docs)}}


@router.post("/project/{project_id}/doc/{doc_id}/revectorize")
async def revectorize_document(project_id: str, doc_id: str):
    proj = get_kb().get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    doc = next((d for d in proj.documents if d["id"] == doc_id), None)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    file_hash = doc.get("file_hash", doc_id)
    ext = "." + doc.get("doc_type", "txt")
    raw_path = os.path.join(proj.raw_docs_dir, f"{file_hash}{ext}")
    if not os.path.exists(raw_path):
        raw_path = os.path.join(proj.raw_docs_dir, doc["filename"])
    if not os.path.exists(raw_path):
        return {"success": False, "message": "原始文件不存在，无法重向量化"}
    content = DocumentParser.parse(raw_path)
    if not content:
        return {"success": False, "message": "文档解析失败"}
    # 删除旧向量后重新添加
    proj._remove_doc_vectors(file_hash)
    result = proj.add_document(raw_path, doc["filename"], str(content),
                                doc["doc_type"], doc["file_size"],
                                doc.get("folder_id", ""), doc.get("note", ""))
    return result


# ── 检索 ──────────────────────────────────────────────────

@router.post("/project/{project_id}/search")
async def search_kb(project_id: str, payload: dict = Body(...)):
    query = payload.get("query", "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="查询内容不能为空")
    top_k = int(payload.get("top_k", 5))
    folder_id = payload.get("folder_id", "")
    proj = get_kb().get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    results = proj.search(query, top_k=top_k, folder_id=folder_id or None)
    return {"success": True, "data": {"results": results, "total": len(results)}}


@router.post("/project/{project_id}/fuzzy-search")
async def fuzzy_search_kb(project_id: str, payload: dict = Body(...)):
    keyword = payload.get("keyword", "").strip()
    if not keyword:
        raise HTTPException(status_code=400, detail="关键词不能为空")
    folder_id = payload.get("folder_id", "")
    proj = get_kb().get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    results = proj.fuzzy_search(keyword, folder_id=folder_id or None)
    return {"success": True, "data": {"results": results, "total": len(results)}}


@router.post("/global-search")
async def global_search(payload: dict = Body(...)):
    query = payload.get("query", "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="查询内容不能为空")
    top_k = int(payload.get("top_k", 3))
    results = []
    for pinfo in get_kb()._projects:
        if pinfo.get("archived"):
            continue
        proj = get_kb().get_project(pinfo["id"])
        if not proj:
            continue
        res = proj.search(query, top_k=top_k)
        for r in res:
            r["project_name"] = pinfo["name"]
            r["project_id"] = pinfo["id"]
        results.extend(res)
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return {"success": True, "data": {"results": results, "total": len(results)}}


# ── 配置 ──────────────────────────────────────────────────

@router.get("/project/{project_id}/config")
async def get_project_config(project_id: str):
    proj = get_kb().get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"success": True, "data": proj.config}


@router.put("/project/{project_id}/config")
async def update_project_config(project_id: str, payload: dict = Body(...)):
    proj = get_kb().get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    for key in ["chunk_size_min", "chunk_size_max", "embedding_model"]:
        if key in payload:
            proj.config[key] = payload[key]
    proj._save_state()
    return {"success": True}


@router.post("/project/{project_id}/rechunk")
async def rechunk_project(project_id: str):
    proj = get_kb().get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    result = proj.revectorize_all()
    return result


@router.post("/project/{project_id}/folder/{folder_id}/rechunk")
async def rechunk_folder(project_id: str, folder_id: str):
    proj = get_kb().get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    doc_ids = [d["id"] for d in proj.documents if d.get("folder_id") == folder_id]
    count = 0
    for doc_id in doc_ids:
        file_hash = next((d.get("file_hash") for d in proj.documents if d["id"] == doc_id), doc_id)
        proj._remove_doc_vectors(file_hash)
        doc = next((d for d in proj.documents if d["id"] == doc_id), None)
        if not doc:
            continue
        ext = "." + doc.get("doc_type", "txt")
        raw_path = os.path.join(proj.raw_docs_dir, f"{file_hash}{ext}")
        if not os.path.exists(raw_path):
            raw_path = os.path.join(proj.raw_docs_dir, doc["filename"])
        if not os.path.exists(raw_path):
            continue
        try:
            content = DocumentParser.parse(raw_path)
            if content and len(str(content)) >= 20:
                r = proj.add_document(raw_path, doc["filename"], str(content),
                                       doc["doc_type"], doc["file_size"],
                                       doc.get("folder_id", ""), doc.get("note", ""))
                if r.get("success"):
                    count += 1
        except Exception:
            continue
    return {"success": True, "message": f"已重新分块 {count}/{len(doc_ids)} 个文档"}


@router.post("/project/{project_id}/switch-model")
async def switch_model(project_id: str, payload: dict = Body(...)):
    model_name = payload.get("model", "").strip()
    if not model_name:
        raise HTTPException(status_code=400, detail="模型名称不能为空")
    proj = get_kb().get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    result = proj.switch_model(model_name)
    return result


# ── 备份 ──────────────────────────────────────────────────

@router.post("/project/{project_id}/backup")
async def create_backup(project_id: str):
    proj = get_kb().get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    result = proj.create_backup()
    return result


@router.get("/project/{project_id}/backups")
async def list_backups(project_id: str):
    proj = get_kb().get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"success": True, "data": {"backups": proj.list_backups()}}


@router.post("/project/{project_id}/restore")
async def restore_backup(project_id: str, payload: dict = Body(...)):
    filename = payload.get("filename", "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="备份文件名不能为空")
    proj = get_kb().get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    result = proj.restore_backup(filename)
    return result


@router.delete("/project/{project_id}/backup/{filename:path}")
async def delete_backup(project_id: str, filename: str):
    proj = get_kb().get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    ok = proj.delete_backup(filename)
    return {"success": ok, "message": "已删除" if ok else "删除失败"}


# ── 统计 ──────────────────────────────────────────────────

@router.get("/project/{project_id}/stats")
async def project_stats(project_id: str):
    proj = get_kb().get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"success": True, "data": proj.get_stats()}


@router.get("/overall-stats")
async def overall_stats():
    projects = get_kb().list_projects()
    total_docs = sum(p.get("doc_count", 0) for p in projects)
    total_projects = len(projects)
    return {"success": True, "data": {
        "total_projects": total_projects,
        "total_documents": total_docs,
        "projects": projects,
    }}


# ── 自定义词库 ────────────────────────────────────────────

@router.get("/project/{project_id}/vocab")
async def list_vocab(project_id: str):
    proj = get_kb().get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"success": True, "data": {"vocab": proj.config.get("custom_vocab", [])}}


@router.post("/project/{project_id}/vocab")
async def add_vocab(project_id: str, payload: dict = Body(...)):
    word = payload.get("word", "").strip()
    if not word:
        raise HTTPException(status_code=400, detail="词汇不能为空")
    proj = get_kb().get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    return proj.add_vocab(word)


@router.delete("/project/{project_id}/vocab/{word}")
async def remove_vocab(project_id: str, word: str):
    word = unquote(word)
    proj = get_kb().get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    return proj.remove_vocab(word)


# ── 兼容旧接口（保留前端旧调用）───────────────────────────

@router.get("/stats")
async def stats_compat():
    kb = get_kb()
    pid = kb._active_project_id
    if not pid:
        return {"success": True, "data": {"total_documents": 0, "total_chunks": 0, "documents": []}}
    return await project_stats(pid)


@router.post("/upload")
async def upload_compat(request: Request):
    kb = get_kb()
    pid = kb._active_project_id
    if not pid:
        return {"success": False, "message": "没有活跃项目"}
    return await upload_document(pid, request)
