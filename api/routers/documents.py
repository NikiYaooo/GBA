import os
import time
import uuid
from urllib.parse import unquote
from fastapi import APIRouter, Body, Request
from fastapi.responses import FileResponse
from document_parser import DocumentParser
from utils import get_app_data_dir, load_json, save_json, generate_docx, generate_xlsx

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _docs_db():
    return os.path.join(get_app_data_dir(), "documents.json")


def _upload_dir():
    d = os.path.join(get_app_data_dir(), "uploads")
    os.makedirs(d, exist_ok=True)
    return d


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

        doc_record = {
            "id": uuid.uuid4().hex,
            "name": filename,
            "type": ext.lstrip('.') if ext else 'unknown',
            "category": auto_cat,
            "path": file_path,
            "content": content,
            "created_at": int(time.time())
        }

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
    docs = load_json(_docs_db(), [])
    docs.insert(0, doc_record)
    save_json(_docs_db(), docs)
    return {"success": True, "data": doc_record}


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
        return {"success": True}
    return {"success": False, "message": "文档未找到"}


@router.put("/{doc_id}")
async def update_document(doc_id: str, payload: dict = Body(...)):
    docs = load_json(_docs_db(), [])
    for d in docs:
        if d["id"] == doc_id:
            d["content"] = payload.get("content", d.get("content", ""))
            if "name" in payload:
                d["name"] = payload["name"]
            if "category" in payload:
                d["category"] = payload["category"]
            save_json(_docs_db(), docs)
            return {"success": True}
    return {"success": False, "message": "文档未找到"}
