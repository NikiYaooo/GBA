"""api/kb_project.py — 单项目知识库的完整封装。"""

import os
import json
import time
import hashlib
import shutil
import uuid
from typing import List, Dict, Any, Optional


class KBProject:
    """封装单个项目的所有操作：文档、切片、向量、检索、备份、配置。"""

    def __init__(self, project_dir: str, project_config: dict = None):
        self.project_dir = project_dir
        os.makedirs(project_dir, exist_ok=True)

        self.config_path = os.path.join(project_dir, "config.json")
        self.folders_path = os.path.join(project_dir, "folders.json")
        self.documents_path = os.path.join(project_dir, "documents.json")
        self.chunks_path = os.path.join(project_dir, "chunks.json")
        self.vectors_path = os.path.join(project_dir, "vectors.npy")
        self.raw_docs_dir = os.path.join(project_dir, "raw_docs")
        self.backups_dir = os.path.join(project_dir, "backups")
        os.makedirs(self.raw_docs_dir, exist_ok=True)
        os.makedirs(self.backups_dir, exist_ok=True)

        # 默认配置
        self.config = {
            "chunk_size_min": 100,
            "chunk_size_max": 500,
            "embedding_model": "bge-small-zh",
            "custom_vocab": [],
        }
        self.folders: List[Dict] = []
        self.documents: List[Dict] = []
        self._chunks: List[Dict] = []
        self._vectors = None
        self._model = None
        self._hash_vectorizer = None
        self._embedding_backend = "sentence_transformers"
        self._bm25 = None

        if project_config:
            self.config.update(project_config)

        self._load_state()

    # ------------------------------------------------------------------
    # 存储层
    # ------------------------------------------------------------------

    def _load_state(self):
        """从磁盘加载项目状态。"""
        import numpy as np
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.config.update(json.load(f))
            except Exception:
                pass
        if os.path.exists(self.folders_path):
            try:
                with open(self.folders_path, "r", encoding="utf-8") as f:
                    self.folders = json.load(f)
            except Exception:
                self.folders = []
        if os.path.exists(self.documents_path):
            try:
                with open(self.documents_path, "r", encoding="utf-8") as f:
                    self.documents = json.load(f)
            except Exception:
                self.documents = []
        if os.path.exists(self.chunks_path):
            try:
                with open(self.chunks_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._chunks = data if isinstance(data, list) else data.get("chunks", [])
            except Exception:
                self._chunks = []
        if os.path.exists(self.vectors_path):
            try:
                self._vectors = np.load(self.vectors_path)
            except Exception:
                self._vectors = None
        self._rebuild_bm25()

    def _save_state(self):
        """将当前项目状态写入磁盘。"""
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)
        with open(self.folders_path, "w", encoding="utf-8") as f:
            json.dump(self.folders, f, ensure_ascii=False, indent=2)
        with open(self.documents_path, "w", encoding="utf-8") as f:
            json.dump(self.documents, f, ensure_ascii=False, indent=2)
        with open(self.chunks_path, "w", encoding="utf-8") as f:
            json.dump(self._chunks, f, ensure_ascii=False, indent=2)

        if self._vectors is None:
            if os.path.exists(self.vectors_path):
                try:
                    os.remove(self.vectors_path)
                except Exception:
                    pass
        else:
            import numpy as np
            np.save(self.vectors_path, self._vectors)

    # ------------------------------------------------------------------
    # 占位方法（Task 2 实现）
    # ------------------------------------------------------------------

    def _rebuild_bm25(self):
        """重建 BM25 索引 — Task 2 实现。"""
        pass

    def _encode_texts(self, texts: List[str]) -> Any:
        """将文本列表编码为向量 — Task 2 实现。"""
        import numpy as np
        # Task 1 中返回空矩阵作为占位
        if not texts:
            return np.array([], dtype=np.float32)
        return np.zeros((len(texts), 768), dtype=np.float32)

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _compute_file_hash(self, file_path: str) -> str:
        """计算文件 MD5 哈希。"""
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _copy_to_raw_docs(self, file_path: str, file_hash: str) -> str:
        """将文件复制到 raw_docs 目录，返回目标路径。"""
        ext = os.path.splitext(file_path)[1].lower()
        dest = os.path.join(self.raw_docs_dir, f"{file_hash}{ext}")
        shutil.copy2(file_path, dest)
        return dest

    def _resolve_filename_conflict(self, filename: str) -> str:
        """处理文件名冲突：同名但不同 hash 时添加序号后缀。"""
        names_in_use = {d["filename"] for d in self.documents if d.get("filename")}
        if filename not in names_in_use:
            return filename

        base, ext = os.path.splitext(filename)
        counter = 1
        while True:
            candidate = f"{base} ({counter}){ext}"
            if candidate not in names_in_use:
                return candidate
            counter += 1

    def get_doc_by_hash(self, file_hash: str) -> Optional[Dict]:
        """通过文件哈希查找文档。"""
        for doc in self.documents:
            if doc.get("file_hash") == file_hash:
                return doc
        return None

    # ------------------------------------------------------------------
    # 文档管理
    # ------------------------------------------------------------------

    def add_document(
        self,
        file_path: str,
        filename: str,
        content: str,
        doc_type: str,
        file_size: int,
        folder_id: str = "",
        note: str = "",
    ) -> Dict[str, Any]:
        """添加文档：检查 hash 重复，处理文件名冲突，复制到 raw_docs，标记待切片向量化。

        返回格式: {"success": bool, "message": str, "doc_id": str | None, "chunks": int}
        """
        # 1. 计算文件哈希
        try:
            file_hash = self._compute_file_hash(file_path)
        except Exception as e:
            return {"success": False, "message": f"计算文件哈希失败: {e}", "doc_id": None, "chunks": 0}

        # 2. 检查 hash 重复 → 覆盖更新
        existing = self.get_doc_by_hash(file_hash)
        if existing:
            return self._update_document(
                file_hash=file_hash,
                file_path=file_path,
                filename=filename,
                content=content,
                doc_type=doc_type,
                file_size=file_size,
                folder_id=folder_id,
                note=note,
            )

        # 3. 处理文件名冲突
        final_filename = self._resolve_filename_conflict(filename)

        # 4. 复制到 raw_docs
        try:
            raw_path = self._copy_to_raw_docs(file_path, file_hash)
        except Exception as e:
            return {"success": False, "message": f"复制文件失败: {e}", "doc_id": None, "chunks": 0}

        # 5. 创建文档记录
        doc_id = str(uuid.uuid4())
        now = int(time.time())
        doc = {
            "id": doc_id,
            "filename": final_filename,
            "file_hash": file_hash,
            "folder_id": folder_id,
            "note": note,
            "file_size": file_size,
            "doc_type": doc_type,
            "added_at": now,
            "updated_at": now,
            "status": "pending",
            "raw_path": raw_path,
        }
        self.documents.append(doc)

        # 6. 自动切片向量化（占位 — Task 2 实现实际逻辑）
        self._chunk_document(doc_id, content)

        self._save_state()
        return {
            "success": True,
            "message": "文档已添加",
            "doc_id": doc_id,
            "chunks": 0,
        }

    def _chunk_document(self, doc_id: str, content: str):
        """对文档进行切片和向量化（占位 — Task 2 实现）。"""
        # Task 1: 仅创建文档记录，不实际切片
        # 找到文档并标记状态
        for doc in self.documents:
            if doc.get("id") == doc_id:
                doc["status"] = "ready"
                break

    def _update_document(
        self,
        file_hash: str,
        file_path: str,
        filename: str,
        content: str,
        doc_type: str,
        file_size: int,
        folder_id: str = "",
        note: str = "",
    ) -> Dict[str, Any]:
        """覆盖更新已有 hash 的文档，保留原文件夹归属和备注。"""
        existing = self.get_doc_by_hash(file_hash)
        if not existing:
            return {"success": False, "message": "文档不存在", "doc_id": None, "chunks": 0}

        # 保留原有的文件夹和备注
        if not folder_id:
            folder_id = existing.get("folder_id", "")
        if not note:
            note = existing.get("note", "")

        # 删除旧向量块
        self._remove_doc_vectors(file_hash)

        # 复制新文件到 raw_docs
        try:
            raw_path = self._copy_to_raw_docs(file_path, file_hash)
        except Exception as e:
            return {"success": False, "message": f"复制文件失败: {e}", "doc_id": None, "chunks": 0}

        # 更新文档记录
        now = int(time.time())
        existing["filename"] = filename
        existing["folder_id"] = folder_id
        existing["note"] = note
        existing["file_size"] = file_size
        existing["doc_type"] = doc_type
        existing["updated_at"] = now
        existing["status"] = "pending"
        existing["raw_path"] = raw_path

        # 重新切片向量化（占位）
        self._chunk_document(existing["id"], content)

        self._save_state()
        return {
            "success": True,
            "message": "文档已更新",
            "doc_id": existing["id"],
            "chunks": 0,
        }

    def _remove_doc_vectors(self, file_hash: str):
        """删除文档对应的文本块（暂时不操作 vectors numpy 矩阵）。"""
        doc = self.get_doc_by_hash(file_hash)
        if doc is None:
            return
        doc_id = doc["id"]
        self._chunks = [c for c in self._chunks if c.get("doc_id") != doc_id]
        # 注意：vectors.npy 将在 Task 2 中处理

    def delete_document(self, doc_id: str) -> Dict[str, Any]:
        """删除文档及其所有块。"""
        doc = next((d for d in self.documents if d["id"] == doc_id), None)
        if not doc:
            return {"success": False, "message": "文档不存在"}

        file_hash = doc.get("file_hash", "")

        # 从文档列表移除
        self.documents = [d for d in self.documents if d["id"] != doc_id]

        # 删除对应的块
        if file_hash:
            self._remove_doc_vectors(file_hash)

        # 删除 raw_docs 中的文件
        raw_path = doc.get("raw_path", "")
        if raw_path and os.path.exists(raw_path):
            try:
                os.remove(raw_path)
            except Exception:
                pass

        self._rebuild_bm25()
        self._save_state()
        return {"success": True, "message": "文档已删除"}

    def update_document_meta(self, doc_id: str, updates: dict) -> Dict[str, Any]:
        """更新文档元数据（重命名、备注、移动文件夹等）。"""
        doc = next((d for d in self.documents if d["id"] == doc_id), None)
        if not doc:
            return {"success": False, "message": "文档不存在"}

        allowed_keys = {"filename", "folder_id", "note", "doc_type", "status"}
        for key, value in updates.items():
            if key in allowed_keys:
                doc[key] = value

        doc["updated_at"] = int(time.time())
        self._save_state()
        return {"success": True, "message": "文档已更新"}

    # ------------------------------------------------------------------
    # 文件夹管理
    # ------------------------------------------------------------------

    def create_folder(self, name: str) -> Dict[str, Any]:
        """创建文件夹。"""
        folder_id = str(uuid.uuid4())
        folder = {
            "id": folder_id,
            "name": name,
            "created_at": int(time.time()),
        }
        self.folders.append(folder)
        self._save_state()
        return {"success": True, "folder": folder}

    def rename_folder(self, folder_id: str, new_name: str) -> Dict[str, Any]:
        """重命名文件夹。"""
        folder = next((f for f in self.folders if f["id"] == folder_id), None)
        if not folder:
            return {"success": False, "message": "文件夹不存在"}
        folder["name"] = new_name
        self._save_state()
        return {"success": True, "folder": folder}

    def delete_folder(self, folder_id: str) -> Dict[str, Any]:
        """删除文件夹，其中的文档移出到根目录。"""
        folder = next((f for f in self.folders if f["id"] == folder_id), None)
        if not folder:
            return {"success": False, "message": "文件夹不存在"}

        # 文档移出到根目录
        for doc in self.documents:
            if doc.get("folder_id") == folder_id:
                doc["folder_id"] = ""

        self.folders = [f for f in self.folders if f["id"] != folder_id]
        self._save_state()
        return {"success": True, "message": "文件夹已删除"}

    # ------------------------------------------------------------------
    # 统计与列表
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """返回项目统计：总文档数、总块数、总大小、各文件夹文档数。"""
        total_docs = len(self.documents)
        total_chunks = len(self._chunks)
        total_size = sum(d.get("file_size", 0) for d in self.documents)

        # 各文件夹文档数
        folder_counts: Dict[str, int] = {}
        for d in self.documents:
            fid = d.get("folder_id", "")
            folder_counts[fid] = folder_counts.get(fid, 0) + 1

        uncategorized = len([d for d in self.documents if not d.get("folder_id")])

        return {
            "total_documents": total_docs,
            "total_chunks": total_chunks,
            "total_size_bytes": total_size,
            "vector_count": len(self._vectors) if self._vectors is not None else 0,
            "folder_counts": folder_counts,
            "uncategorized_count": uncategorized,
            "config": self.config,
        }

    def get_documents(self, folder_id: Optional[str] = None) -> List[Dict]:
        """获取文档列表，可按文件夹筛选。"""
        if folder_id is None:
            return list(self.documents)
        return [d for d in self.documents if d.get("folder_id") == folder_id]
