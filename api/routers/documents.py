import os
import time
import uuid
import shutil
from urllib.parse import unquote
from fastapi import APIRouter, Body, Request
from fastapi.responses import FileResponse
from document_parser import DocumentParser
from utils import get_app_data_dir, load_json, save_json, generate_docx, generate_xlsx, save_docx_to_path

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _docs_db():
    return os.path.join(get_app_data_dir(), "documents.json")


def _upload_dir():
    d = os.path.join(get_app_data_dir(), "uploads")
    os.makedirs(d, exist_ok=True)
    return d


def _documents_dir():
    """文档本地文件夹存储根目录。"""
    d = os.path.join(get_app_data_dir(), "documents")
    os.makedirs(d, exist_ok=True)
    return d


def _sanitize_folder_name(name: str) -> str:
    """清理文件夹名称中的非法字符。"""
    invalid_chars = r'<>:"/\|?*'
    for c in invalid_chars:
        name = name.replace(c, '_')
    name = name.strip().replace('.', '_')
    if not name:
        name = "未命名文档"
    return name[:100]  # 限制长度


def _get_doc_folder(doc_name: str, doc_id: str) -> str:
    """获取文档对应的本地文件夹路径（基于文档名称创建），如已存在则用 doc_id 避免冲突。"""
    base = _documents_dir()
    safe_name = _sanitize_folder_name(doc_name)
    folder = os.path.join(base, safe_name)
    # 如果文件夹已存在但不是该文档的，则用 id 后缀
    marker = os.path.join(folder, ".doc_id")
    if os.path.exists(folder):
        if os.path.exists(marker):
            try:
                with open(marker, 'r') as f:
                    existing_id = f.read().strip()
                if existing_id == doc_id:
                    return folder
            except Exception:
                pass
        # 冲突：使用 id 作为文件夹名
        folder = os.path.join(base, f"{safe_name}_{doc_id[:8]}")
    os.makedirs(folder, exist_ok=True)
    try:
        with open(os.path.join(folder, ".doc_id"), 'w') as f:
            f.write(doc_id)
    except Exception:
        pass
    return folder


def _save_doc_file(doc: dict) -> str:
    """将文档保存为 .docx 文件到本地文件夹，返回文件路径。"""
    folder = _get_doc_folder(doc.get("name", "未命名"), doc.get("id", ""))
    docx_name = doc.get("name", "文档").replace('.docx', '').replace('.doc', '').strip() + ".docx"
    docx_path = os.path.join(folder, docx_name)
    try:
        content = doc.get("content", "")
        if content:
            save_docx_to_path(content, doc.get("name", ""), docx_path)
        else:
            # 空文档也创建文件
            save_docx_to_path("<p>（空文档）</p>", doc.get("name", ""), docx_path)
    except Exception:
        pass
    return docx_path


@router.post("/upload")
async def upload_document(request: Request):
    filename = request.headers.get("X-Filename", "").strip()
    category = request.headers.get("X-Category", "doc").strip()
    if filename:
        try:
            filename = unquote(filename)
        except Exception:
            pass
    if not filename:
        filename = f"doc_{uuid.uuid4()}.docx"

    ext = os.path.splitext(filename)[1].lower()
    save_filename = f"doc_{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(_upload_dir(), save_filename)

    try:
        raw_bytes = await request.body()
        if not raw_bytes or len(raw_bytes) < 20:
            return {"success": False, "message": "上传内容为空"}

        with open(file_path, "wb") as buffer:
            buffer.write(raw_bytes)

        content = DocumentParser.parse(file_path)

        if ext in ('.xlsx', '.xls'):
            auto_cat = 'excel'
        elif ext in ('.docx', '.doc'):
            auto_cat = 'doc'
        else:
            auto_cat = category if category in ('doc', 'imitation', 'excel', 'draft') else 'doc'

        doc_id = uuid.uuid4().hex
        doc_record = {
            "id": doc_id,
            "name": filename,
            "type": ext.lstrip('.') if ext else 'unknown',
            "category": auto_cat,
            "path": file_path,
            "content": content,
            "created_at": int(time.time())
        }

        # 复制文件到文档本地文件夹
        if auto_cat != 'excel':
            try:
                folder = _get_doc_folder(filename, doc_id)
                dest_path = os.path.join(folder, filename)
                shutil.copy2(file_path, dest_path)
                doc_record["path"] = dest_path
            except Exception:
                pass

        docs = load_json(_docs_db(), [])
        docs.insert(0, doc_record)
        save_json(_docs_db(), docs)

        return {"success": True, "data": doc_record}
    except Exception as e:
        return {"success": False, "message": f"上传失败: {str(e)}"}


@router.get("")
async def get_documents(category: str = ''):
    docs = load_json(_docs_db(), [])
    if category:
        docs = [d for d in docs if d.get('category') == category]
    return {"success": True, "data": docs}


@router.post("/create")
async def create_document(payload: dict = Body(...)):
    name = payload.get("name", "未命名文档")
    content = payload.get("content", "")
    category = payload.get("category", "draft")
    doc_id = uuid.uuid4().hex
    doc_record = {
        "id": doc_id,
        "name": name,
        "type": "",
        "category": category,
        "path": "",
        "content": content,
        "created_at": int(time.time())
    }

    # 保存到本地文件夹
    if category != 'excel':
        try:
            docx_path = _save_doc_file(doc_record)
            doc_record["path"] = docx_path
        except Exception:
            pass

    docs = load_json(_docs_db(), [])
    docs.insert(0, doc_record)
    save_json(_docs_db(), docs)
    return {"success": True, "data": doc_record}


@router.post("/save-file/{doc_id}")
async def save_document_file(doc_id: str, payload: dict = Body(...)):
    """保存文档内容到本地 .docx 文件（不改变 JSON 中的 path）。"""
    docs = load_json(_docs_db(), [])
    for d in docs:
        if d["id"] == doc_id:
            content = payload.get("content", d.get("content", ""))
            d["content"] = content
            # 更新 JSON
            save_json(_docs_db(), docs)
            # 保存到本地文件
            try:
                docx_path = _save_doc_file(d)
                if not d.get("path"):
                    d["path"] = docx_path
                    save_json(_docs_db(), docs)
            except Exception:
                pass
            return {"success": True, "message": "文档已保存"}
    return {"success": False, "message": "文档未找到"}


@router.post("/generate-file")
async def generate_document_file(payload: dict = Body(...)):
    name = payload.get("name", "文档")
    content = payload.get("content", "")
    file_type = payload.get("type", "docx")
    try:
        ext = file_type.lower()
        if ext in ('xlsx', 'xls'):
            return generate_xlsx(content, name)
        else:
            return generate_docx(content, name)
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/file/{doc_id}")
async def get_document_file(doc_id: str):
    docs = load_json(_docs_db(), [])
    doc = next((d for d in docs if d["id"] == doc_id), None)
    if not doc or not doc.get("path") or not os.path.exists(doc["path"]):
        return {"success": False, "message": "文件未找到"}
    return FileResponse(doc["path"], filename=doc.get("name", "file"), media_type="application/octet-stream")


@router.get("/{doc_id}")
async def get_document(doc_id: str):
    docs = load_json(_docs_db(), [])
    doc = next((d for d in docs if d["id"] == doc_id), None)
    if doc:
        return {"success": True, "data": doc}
    return {"success": False, "message": "文档未找到"}


@router.delete("/{doc_id}")
async def delete_document(doc_id: str):
    docs = load_json(_docs_db(), [])
    doc_to_delete = next((d for d in docs if d["id"] == doc_id), None)
    if doc_to_delete:
        docs = [d for d in docs if d["id"] != doc_id]
        save_json(_docs_db(), docs)
        if os.path.exists(doc_to_delete.get("path", "")):
            try:
                os.remove(doc_to_delete["path"])
            except Exception:
                pass
        # 删除文件夹
        try:
            folder = _get_doc_folder(doc_to_delete.get("name", ""), doc_id)
            if os.path.isdir(folder):
                shutil.rmtree(folder, ignore_errors=True)
        except Exception:
            pass
        return {"success": True}
    return {"success": False, "message": "文档未找到"}


@router.put("/{doc_id}")
async def update_document(doc_id: str, payload: dict = Body(...)):
    docs = load_json(_docs_db(), [])
    for d in docs:
        if d["id"] == doc_id:
            old_name = d.get("name", "")
            d["content"] = payload.get("content", d.get("content", ""))
            if "name" in payload:
                d["name"] = payload["name"]
            if "category" in payload:
                d["category"] = payload["category"]
            save_json(_docs_db(), docs)

            # 如果名称改变，重新保存文件并处理文件夹重命名
            new_name = d.get("name", "")
            if new_name and new_name != old_name:
                try:
                    # 删除旧文件夹
                    old_folder = _get_doc_folder(old_name, doc_id)
                    if os.path.isdir(old_folder) and os.path.exists(os.path.join(old_folder, ".doc_id")):
                        try:
                            with open(os.path.join(old_folder, ".doc_id"), 'r') as f:
                                if f.read().strip() == doc_id:
                                    shutil.rmtree(old_folder, ignore_errors=True)
                        except Exception:
                            pass
                    # 保存到新文件夹
                    docx_path = _save_doc_file(d)
                    d["path"] = docx_path
                    save_json(_docs_db(), docs)
                except Exception:
                    pass

            return {"success": True}
    return {"success": False, "message": "文档未找到"}
