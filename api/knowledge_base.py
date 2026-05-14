"""api/knowledge_base.py — KBManager 多项目管理器 + 旧数据迁移。"""

import os
import json
import time
import uuid
from typing import List, Dict, Any, Optional

from kb_project import KBProject


class KnowledgeBase:
    """多项目管理器（兼容旧 KnowledgeBase 接口）。"""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.kb_dir = os.path.join(data_dir, "kb")
        os.makedirs(self.kb_dir, exist_ok=True)

        self.projects_path = os.path.join(self.kb_dir, "projects.json")
        self._projects: List[Dict] = []
        self._project_instances: Dict[str, KBProject] = {}
        self._active_project_id: Optional[str] = None

        # 兼容旧接口的 chunk_size 属性（路由器直接赋值）
        self._chunk_size_min = 100
        self._chunk_size_max = 500

        self._load_projects()
        self._migrate_old_data()

    def _load_projects(self):
        if os.path.exists(self.projects_path):
            try:
                with open(self.projects_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._projects = data.get("projects", [])
                    self._active_project_id = data.get("active_project_id")
            except Exception as e:
                print(f"[KB] 加载 projects.json 失败: {e}")
                self._projects = []
        if self._projects:
            for p in self._projects:
                pid = p["id"]
                pdir = os.path.join(self.kb_dir, f"project_{pid}")
                if os.path.isdir(pdir):
                    self._project_instances[pid] = KBProject(pdir, {
                        "chunk_size_min": p.get("chunk_size_min", 100),
                        "chunk_size_max": p.get("chunk_size_max", 500),
                        "embedding_model": p.get("embedding_model", "bge-small-zh"),
                    })

    def _save_projects(self):
        data = {
            "projects": self._projects,
            "active_project_id": self._active_project_id,
        }
        with open(self.projects_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _get_project_dir(self, project_id: str) -> str:
        return os.path.join(self.kb_dir, f"project_{project_id}")

    def _migrate_old_data(self):
        """检测旧单库格式并迁移到多项目格式。"""
        migration_flag = os.path.join(self.kb_dir, ".migrated_v2.6.2")
        if os.path.exists(migration_flag):
            return

        old_chunks_path = os.path.join(self.kb_dir, "chunks.json")
        old_vectors_path = os.path.join(self.kb_dir, "vectors.npy")
        if not os.path.exists(old_chunks_path):
            # 无旧数据，创建默认项目
            if not self._projects:
                self.create_project("默认项目库", "自动创建的默认项目")
            try:
                open(migration_flag, "w").close()
            except Exception:
                pass
            return

        # 有旧数据 → 迁移到默认项目
        import shutil
        try:
            p = self.create_project("默认项目库", "从旧版知识库自动迁移")
            pdir = self._get_project_dir(p["id"])

            # 复制旧数据
            if os.path.exists(old_chunks_path):
                shutil.copy2(old_chunks_path, os.path.join(pdir, "chunks.json"))
            if os.path.exists(old_vectors_path):
                shutil.copy2(old_vectors_path, os.path.join(pdir, "vectors.npy"))

            # 从旧 chunks 中提取文档信息
            with open(old_chunks_path, "r", encoding="utf-8") as f:
                old_data = json.load(f)
            old_chunks = old_data if isinstance(old_data, list) else old_data.get("chunks", [])

            docs_seen = {}
            for c in old_chunks:
                meta = c.get("metadata", {})
                fh = meta.get("file_hash", "unknown")
                if fh not in docs_seen:
                    docs_seen[fh] = {
                        "id": fh,
                        "file_hash": fh,
                        "filename": meta.get("filename", "unknown"),
                        "doc_type": meta.get("type", meta.get("doc_type", "unknown")),
                        "file_size": meta.get("file_size", 0),
                        "folder_id": "",
                        "note": "",
                        "added_at": meta.get("added_at", int(time.time())),
                        "updated_at": int(time.time()),
                        "chunk_count": 0,
                        "vector_status": "vectorized",
                    }
                docs_seen[fh]["chunk_count"] += 1

            # 加载到 KBProject
            proj = self.get_project(p["id"])
            if proj:
                proj._chunks = old_chunks
                proj.documents = list(docs_seen.values())
                proj._rebuild_bm25()
                proj._save_state()

            try:
                open(migration_flag, "w").close()
            except Exception:
                pass
        except Exception as e:
            print(f"[KB] 数据迁移失败: {e}")

    # ============ 项目管理 ============

    def create_project(self, name: str, description: str = "",
                       embedding_model: str = "bge-small-zh") -> Dict:
        pid = uuid.uuid4().hex[:12]
        now = int(time.time())
        project = {
            "id": pid,
            "name": name,
            "description": description,
            "type": "personal",
            "embedding_model": embedding_model,
            "chunk_size_min": 100,
            "chunk_size_max": 500,
            "created_at": now,
            "updated_at": now,
            "archived": False,
        }
        self._projects.append(project)

        pdir = self._get_project_dir(pid)
        os.makedirs(pdir, exist_ok=True)
        proj = KBProject(pdir, {
            "chunk_size_min": 100,
            "chunk_size_max": 500,
            "embedding_model": embedding_model,
        })
        self._project_instances[pid] = proj

        if not self._active_project_id:
            self._active_project_id = pid
        self._save_projects()
        return project

    def list_projects(self) -> List[Dict]:
        result = []
        for p in self._projects:
            proj = self._project_instances.get(p["id"])
            doc_count = len(proj.documents) if proj else 0
            result.append({**p, "doc_count": doc_count})
        return result

    def get_project(self, project_id: str) -> Optional[KBProject]:
        return self._project_instances.get(project_id)

    def get_project_info(self, project_id: str) -> Optional[Dict]:
        for p in self._projects:
            if p["id"] == project_id:
                return p
        return None

    def update_project(self, project_id: str, updates: dict) -> Dict:
        proj_info = self.get_project_info(project_id)
        if not proj_info:
            return {"success": False, "message": "项目不存在"}
        for key in ["name", "description"]:
            if key in updates:
                proj_info[key] = updates[key]
        proj_info["updated_at"] = int(time.time())
        self._save_projects()
        return {"success": True}

    def delete_project(self, project_id: str) -> Dict:
        if project_id not in [p["id"] for p in self._projects]:
            return {"success": False, "message": "项目不存在"}
        self._projects = [p for p in self._projects if p["id"] != project_id]
        self._project_instances.pop(project_id, None)
        pdir = self._get_project_dir(project_id)
        if os.path.isdir(pdir):
            import shutil
            shutil.rmtree(pdir, ignore_errors=True)
        if self._active_project_id == project_id:
            self._active_project_id = self._projects[0]["id"] if self._projects else None
        self._save_projects()
        return {"success": True}

    # ============ 兼容旧接口 ============

    def get_stats(self) -> Dict:
        if not self._active_project_id:
            return {"total_documents": 0, "total_chunks": 0, "total_size_bytes": 0,
                    "vector_count": 0, "documents": []}
        proj = self.get_project(self._active_project_id)
        if not proj:
            return {"total_documents": 0, "total_chunks": 0, "total_size_bytes": 0,
                    "vector_count": 0, "documents": []}
        stats = proj.get_stats()
        docs_list = []
        for d in proj.documents:
            docs_list.append({
                "file_hash": d.get("file_hash", d["id"]),
                "filename": d["filename"],
                "type": d.get("doc_type", "unknown"),
                "chunks_count": d.get("chunk_count", 0),
                "file_size": d.get("file_size", 0),
                "added_at": d.get("added_at", 0),
            })
        stats["documents"] = docs_list
        return stats

    def add_document(self, file_path, filename, content, doc_type="unknown",
                     version="v1.0", file_size=0) -> Dict:
        if not self._active_project_id:
            return {"success": False, "message": "没有活跃项目"}
        proj = self.get_project(self._active_project_id)
        if not proj:
            return {"success": False, "message": "项目不存在"}
        return proj.add_document(file_path, filename, content, doc_type, file_size)

    def search(self, query, top_k=5):
        if not self._active_project_id:
            return []
        proj = self.get_project(self._active_project_id)
        if not proj:
            return []
        return proj.search(query, top_k=top_k)

    def search_by_categories(self, query, categories=None, top_k_per_category=3):
        if not self._active_project_id:
            return {}
        proj = self.get_project(self._active_project_id)
        if not proj:
            return {}
        return proj.search_by_categories(query, categories, top_k_per_category)

    def delete_document(self, file_hash: str) -> Dict:
        """通过 file_hash 删除文档（兼容旧接口）。"""
        if not self._active_project_id:
            return {"success": False, "message": "没有活跃项目"}
        proj = self.get_project(self._active_project_id)
        if not proj:
            return {"success": False, "message": "项目不存在"}
        # KBProject.delete_document 接受 doc_id，需要通过 file_hash 查找
        doc = proj.get_doc_by_hash(file_hash)
        if not doc:
            return {"success": False, "message": "未找到该文档"}
        return proj.delete_document(doc["id"])

    def clear_all(self) -> Dict:
        if not self._active_project_id:
            return {"success": False, "message": "没有活跃项目"}
        proj = self.get_project(self._active_project_id)
        if not proj:
            return {"success": False, "message": "项目不存在"}
        proj.documents = []
        proj._chunks = []
        proj._vectors = None
        proj._save_state()
        return {"success": True}

    # ============ 路由器兼容属性与方法 ============

    @property
    def _chunks(self) -> List[Dict]:
        """兼容旧接口：获取当前活跃项目的 chunks。"""
        proj = self.get_project(self._active_project_id)
        if proj:
            return proj._chunks
        return []

    def rechunk_all(self) -> Dict:
        """兼容旧接口：对当前活跃项目执行重新分块+向量化。"""
        if not self._active_project_id:
            return {"success": False, "message": "没有活跃项目"}
        proj = self.get_project(self._active_project_id)
        if not proj:
            return {"success": False, "message": "项目不存在"}
        return proj.revectorize_all()
