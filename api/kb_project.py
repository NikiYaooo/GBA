"""api/kb_project.py — 单项目知识库的完整封装。"""

import os
import json
import time
import hashlib
import shutil
import uuid
import re
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
            except Exception as e:
                print(f"[KBProject] 警告: 加载 config.json 失败: {e}")
        if os.path.exists(self.folders_path):
            try:
                with open(self.folders_path, "r", encoding="utf-8") as f:
                    self.folders = json.load(f)
            except Exception as e:
                print(f"[KBProject] 警告: 加载 folders.json 失败: {e}")
                self.folders = []
        if os.path.exists(self.documents_path):
            try:
                with open(self.documents_path, "r", encoding="utf-8") as f:
                    self.documents = json.load(f)
            except Exception as e:
                print(f"[KBProject] 警告: 加载 documents.json 失败: {e}")
                self.documents = []
        if os.path.exists(self.chunks_path):
            try:
                with open(self.chunks_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._chunks = data if isinstance(data, list) else data.get("chunks", [])
            except Exception as e:
                print(f"[KBProject] 警告: 加载 chunks.json 失败: {e}")
                self._chunks = []
        if os.path.exists(self.vectors_path):
            try:
                self._vectors = np.load(self.vectors_path, allow_pickle=False)
            except Exception as e:
                print(f"[KBProject] 警告: 加载 vectors.npy 失败: {e}")
                self._vectors = None
        self._apply_custom_vocab()
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
    # 向量化与 BM25
    # ------------------------------------------------------------------

    def _rebuild_bm25(self):
        """重建 BM25 索引。"""
        import jieba
        from rank_bm25 import BM25Okapi
        if not self._chunks:
            self._bm25 = None
            return
        tokenized = [jieba.lcut(c.get("content", "")) for c in self._chunks]
        self._bm25 = BM25Okapi(tokenized)

    def _ensure_model(self):
        """加载 embedding 模型，失败时回退到 hashing 向量化。"""
        if self._model is not None:
            return
        model_name = self.config.get("embedding_model", "bge-small-zh")
        try:
            from sentence_transformers import SentenceTransformer
            hf_home = os.path.join(os.path.dirname(self.project_dir), "hf_cache")
            os.makedirs(hf_home, exist_ok=True)
            os.environ.setdefault("HF_HOME", hf_home)
            os.environ.setdefault("TRANSFORMERS_CACHE", os.path.join(hf_home, "transformers"))
            os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", os.path.join(hf_home, "sentence_transformers"))
            os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
            model_map = {
                "bge-small-zh": "BAAI/bge-small-zh-v1.5",
                "bge-large-zh": "BAAI/bge-large-zh-v1.5",
                "text2vec-base": "shibing624/text2vec-base-chinese",
            }
            hf_model = model_map.get(model_name, "BAAI/bge-small-zh-v1.5")
            self._model = SentenceTransformer(hf_model)
            self._embedding_backend = "sentence_transformers"
        except Exception:
            from sklearn.feature_extraction.text import HashingVectorizer
            self._model = None
            self._embedding_backend = "hashing"
            self._hash_vectorizer = HashingVectorizer(n_features=2048, alternate_sign=False, norm=None)

    def _apply_custom_vocab(self):
        """向 jieba 添加自定义词汇。"""
        import jieba
        for word in self.config.get("custom_vocab", []):
            jieba.add_word(word)

    def _encode_texts(self, texts: List[str]) -> Any:
        """将文本列表编码为向量 — sentence-transformers 优先，HashingVectorizer 回退。"""
        import numpy as np
        from sklearn.preprocessing import normalize
        if not texts:
            return np.array([], dtype=np.float32)
        self._ensure_model()
        if self._embedding_backend == "sentence_transformers" and self._model is not None:
            vec = self._model.encode(texts, normalize_embeddings=True)
            return np.asarray(vec, dtype=np.float32)
        if self._hash_vectorizer is None:
            from sklearn.feature_extraction.text import HashingVectorizer
            self._hash_vectorizer = HashingVectorizer(n_features=2048, alternate_sign=False, norm=None)
        sparse = self._hash_vectorizer.transform(texts)
        sparse = normalize(sparse, norm="l2", copy=False)
        return sparse.astype(np.float32).toarray()

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
                folder_id=folder_id or None,
                note=note or None,
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

        # 6. 自动切片向量化
        self._chunk_document(doc_id, content)

        # 找到实际生成的块数
        doc_entry = next((d for d in self.documents if d["id"] == doc_id), None)
        chunk_count = doc_entry.get("chunk_count", 0) if doc_entry else 0

        self._save_state()
        return {
            "success": True,
            "message": "文档已添加",
            "doc_id": doc_id,
            "chunks": chunk_count,
        }

    def _chunk_document(self, doc_id: str, content: str):
        """智能切片：标题感知 → 段落合并 → token 回退。"""
        import re, jieba, random
        if not content or not content.strip():
            return

        clean = re.sub(r'<[^>]+>', ' ', content)
        clean = re.sub(r'\s+', ' ', clean).strip()
        if not clean:
            return

        cmin = self.config.get("chunk_size_min", 100)
        cmax = self.config.get("chunk_size_max", 500)
        overlap_ratio = 0.1

        # 找到文档
        doc = next((d for d in self.documents if d["id"] == doc_id), None)
        if not doc:
            return

        # Step 1: 尝试按 Markdown 标题分割
        heading_pattern = re.compile(r'^(#{1,3})\s+(.+)$', re.MULTILINE)
        heading_matches = list(heading_pattern.finditer(clean))

        if heading_matches:
            raw_chunks = self._chunk_by_headings(clean, heading_matches, cmin, cmax)
        else:
            # Step 2: 按段落分割
            paragraphs = re.split(r'\n\s*\n', clean)
            if len(paragraphs) > 1:
                raw_chunks = self._chunk_by_paragraphs(paragraphs, cmin, cmax)
            else:
                # Step 3: token 回退
                raw_chunks = self._chunk_by_tokens(clean, cmin, cmax, overlap_ratio)

        if not raw_chunks:
            return

        # 向量化
        texts = [c["content"] for c in raw_chunks]
        try:
            vectors = self._encode_texts(texts)
        except Exception:
            doc["status"] = "failed"
            return

        # 创建块记录
        new_chunks = []
        for i, ch in enumerate(raw_chunks):
            new_chunks.append({
                "id": f"{doc_id}_{i}",
                "doc_id": doc_id,
                "content": ch["content"],
                "section_title": ch.get("section_title", ""),
                "chunk_index": i,
                "added_at": int(time.time()),
                "metadata": {
                    "doc_id": doc_id,
                    "folder_id": doc.get("folder_id", ""),
                    "filename": doc.get("filename", ""),
                },
            })

        # 合并到总块列表
        if self._vectors is None or len(self._chunks) == 0:
            self._vectors = vectors
            self._chunks = new_chunks
        else:
            import numpy as np
            self._vectors = np.vstack([self._vectors, vectors])
            self._chunks.extend(new_chunks)

        doc["status"] = "ready"
        doc["chunk_count"] = len(new_chunks)
        self._rebuild_bm25()

    def _chunk_by_headings(self, text, heading_matches, cmin, cmax):
        import re
        chunks = []
        for i, match in enumerate(heading_matches):
            start = match.end()
            end = heading_matches[i + 1].start() if i + 1 < len(heading_matches) else len(text)
            section_text = text[start:end].strip()
            if not section_text:
                continue
            title = match.group(2).strip()
            if len(section_text) > cmax:
                sub_paras = [p.strip() for p in re.split(r'\n\s*\n', section_text) if p.strip()]
                current, current_len = [], 0
                for para in sub_paras:
                    if current_len + len(para) > cmax and current:
                        chunks.append({"content": "\n".join(current), "section_title": title})
                        current, current_len = [para], len(para)
                    else:
                        current.append(para)
                        current_len += len(para)
                if current and len("\n".join(current)) >= cmin:
                    chunks.append({"content": "\n".join(current), "section_title": title})
            else:
                if len(section_text) >= cmin:
                    chunks.append({"content": section_text, "section_title": title})
        return chunks

    def _chunk_by_paragraphs(self, paragraphs, cmin, cmax):
        chunks = []
        current, current_len = [], 0
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if current_len + len(para) > cmax and current:
                chunks.append({"content": "\n".join(current), "section_title": ""})
                current, current_len = [para], len(para)
            else:
                current.append(para)
                current_len += len(para)
        if current:
            combined = "\n".join(current)
            if len(combined) >= cmin:
                chunks.append({"content": combined, "section_title": ""})
        return chunks

    def _chunk_by_tokens(self, text, cmin, cmax, overlap_ratio):
        import jieba, random
        chunk_tokens = random.randint(cmin, cmax)
        tokens = [t for t in jieba.lcut(text) if t.strip()]
        if not tokens:
            return []
        overlap = max(1, int(chunk_tokens * overlap_ratio))
        chunks = []
        start = 0
        while start < len(tokens):
            end = min(len(tokens), start + chunk_tokens)
            chunk_text = "".join(tokens[start:end])
            chunks.append({"content": chunk_text, "section_title": ""})
            if end >= len(tokens):
                break
            start = max(0, end - overlap)
        return chunks

    def _update_document(
        self,
        file_hash: str,
        file_path: str,
        filename: str,
        content: str,
        doc_type: str,
        file_size: int,
        folder_id: str = None,
        note: str = None,
    ) -> Dict[str, Any]:
        """覆盖更新已有 hash 的文档，保留原文件夹归属和备注。"""
        existing = self.get_doc_by_hash(file_hash)
        if not existing:
            return {"success": False, "message": "文档不存在", "doc_id": None, "chunks": 0}

        # 保留原有的文件夹和备注（只有传 None 才保留，传 "" 表示清空）
        if folder_id is None:
            folder_id = existing.get("folder_id", "")
        if note is None:
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

        # 重新切片向量化
        self._chunk_document(existing["id"], content)

        # 找到实际生成的块数
        doc_entry = next((d for d in self.documents if d["id"] == existing["id"]), None)
        chunk_count = doc_entry.get("chunk_count", 0) if doc_entry else 0

        self._save_state()
        return {
            "success": True,
            "message": "文档已更新",
            "doc_id": existing["id"],
            "chunks": chunk_count,
        }

    def _remove_doc_vectors(self, file_hash: str):
        """删除文档对应的文本块和向量。"""
        import numpy as np
        doc = self.get_doc_by_hash(file_hash)
        if doc is None:
            return
        doc_id = doc["id"]
        # 找该文档在 chunks 中的索引范围
        remove_idxs = [i for i, c in enumerate(self._chunks) if c.get("doc_id") == doc_id]
        if not remove_idxs:
            return

        old_chunk_count = len(self._chunks)
        # 从 chunks 中删除
        self._chunks = [c for i, c in enumerate(self._chunks) if i not in remove_idxs]

        # 从 vectors 中删除对应行
        if self._vectors is not None:
            if self._vectors.shape[0] == old_chunk_count:
                if sorted(remove_idxs) == list(range(old_chunk_count)):
                    self._vectors = None
                else:
                    self._vectors = np.delete(self._vectors, sorted(remove_idxs), axis=0)
            else:
                # 形状不匹配，安全降级
                self._vectors = None

    def delete_document(self, doc_id: str) -> Dict[str, Any]:
        """删除文档及其所有块。"""
        doc = next((d for d in self.documents if d["id"] == doc_id), None)
        if not doc:
            return {"success": False, "message": "文档不存在"}

        file_hash = doc.get("file_hash", "")

        # 先删除对应的块（必须在移除文档前调用，_remove_doc_vectors 需要查找 doc）
        if file_hash:
            self._remove_doc_vectors(file_hash)

        # 从文档列表移除
        self.documents = [d for d in self.documents if d["id"] != doc_id]

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

    # ------------------------------------------------------------------
    # 检索
    # ------------------------------------------------------------------

    def search(self, query: str, top_k: int = 5, folder_id: str = None) -> List[Dict]:
        """混合检索：向量语义 + BM25 关键词 + RRF 融合排序。"""
        import numpy as np
        import jieba
        if not self._chunks or not query:
            return []

        # 确定需要检索的 chunk 范围
        if folder_id:
            chunk_indices = [i for i, c in enumerate(self._chunks)
                            if c.get("metadata", {}).get("folder_id") == folder_id]
            if not chunk_indices:
                return []
        else:
            chunk_indices = list(range(len(self._chunks)))

        # 向量检索
        q_vec = self._encode_texts([query])
        vec_scores = None
        if self._vectors is not None and self._vectors.shape[0] == len(self._chunks):
            vec_subset = self._vectors[chunk_indices]
            vec_scores = (vec_subset @ q_vec[0]).astype(np.float32)

        # BM25 检索
        bm25_scores = {}
        if self._bm25 is not None:
            tokenized_query = jieba.lcut(query)
            all_scores = self._bm25.get_scores(tokenized_query)
            if all_scores is not None and len(all_scores) == len(self._chunks):
                for idx in chunk_indices:
                    if all_scores[idx] > 0:
                        bm25_scores[self._chunks[idx]["id"]] = float(all_scores[idx])

        # RRF 融合：基于排名而非分数加权
        vec_top_k = max(top_k * 2, 10)

        # 向量检索排名
        vec_ranks = {}
        if vec_scores is not None:
            sorted_vec_idxs = np.argsort(-vec_scores)[:vec_top_k]
            for rank, pos in enumerate(sorted_vec_idxs):
                cid = self._chunks[chunk_indices[pos]]["id"]
                vec_ranks[cid] = rank

        # BM25 检索排名
        bm25_ranks = {}
        if bm25_scores:
            sorted_bm25 = sorted(bm25_scores.items(), key=lambda x: -x[1])[:vec_top_k]
            for rank, (cid, _) in enumerate(sorted_bm25):
                bm25_ranks[cid] = rank

        # RRF 融合
        k = 60
        rrf_scores = {}
        for idx in chunk_indices:
            cid = self._chunks[idx]["id"]
            rank_v = vec_ranks.get(cid, 10000)
            rank_b = bm25_ranks.get(cid, 10000)
            rrf_scores[cid] = 1.0 / (k + rank_v) + 1.0 / (k + rank_b)

        # 按 RRF 分数排序
        sorted_cids = sorted(rrf_scores.items(), key=lambda x: -x[1])[:top_k]

        # 找到对应索引
        cid_to_idx = {self._chunks[i]["id"]: i for i in chunk_indices}
        top_results = [(score, cid_to_idx[cid]) for cid, score in sorted_cids]

        return [
            {
                "content": self._chunks[i].get("content", ""),
                "metadata": self._chunks[i].get("metadata", {}),
                "score": round(float(s), 4),
            }
            for s, i in top_results
        ]

    def fuzzy_search(self, keyword: str, folder_id: str = None) -> List[Dict]:
        """关键词模糊检索：jieba 分词 + 子串匹配。"""
        import jieba
        if not keyword:
            return []
        keyword_lower = keyword.lower()
        tokens = set(jieba.lcut_for_search(keyword))

        matched = []
        seen = set()
        for c in self._chunks:
            if folder_id:
                meta = c.get("metadata", {})
                if meta.get("folder_id") != folder_id:
                    continue
            content = c.get("content", "")
            if not content:
                continue
            # 子串匹配
            if keyword_lower in content.lower():
                if c["id"] not in seen:
                    seen.add(c["id"])
                    matched.append(c)
                    continue
            # token 匹配
            content_tokens = set(jieba.lcut_for_search(content))
            if tokens & content_tokens:
                if c["id"] not in seen:
                    seen.add(c["id"])
                    matched.append(c)

        return [
            {"content": c.get("content", ""), "score": 0.0}
            for c in matched[:20]
        ]

    def search_by_categories(self, query: str, categories: List[str] = None,
                              top_k_per_category: int = 3) -> Dict[str, List[Dict]]:
        """按文件夹分类检索（兼容旧接口，用于 PRD 联动）。"""
        if not categories:
            categories = [f["name"] for f in self.folders]
        if not categories:
            return {"通用": self.search(query, top_k=top_k_per_category)}
        result = {}
        for cat in categories:
            folder = next((f for f in self.folders if f["name"] == cat), None)
            if folder:
                result[cat] = self.search(query, top_k=top_k_per_category, folder_id=folder["id"])
            else:
                result[cat] = []
        return result

    # ------------------------------------------------------------------
    # 备份
    # ------------------------------------------------------------------

    def create_backup(self) -> Dict:
        """将整个项目目录打包为 zip 备份。"""
        import zipfile
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{timestamp}.zip"
        backup_path = os.path.join(self.backups_dir, backup_name)
        self._save_state()
        try:
            with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(self.project_dir):
                    for fn in files:
                        fp = os.path.join(root, fn)
                        # 跳过 backups 目录内的文件（避免嵌套备份）
                        if root.startswith(self.backups_dir + os.sep):
                            continue
                        arcname = os.path.relpath(fp, self.project_dir)
                        zf.write(fp, arcname)
            size = os.path.getsize(backup_path)
            return {"success": True, "filename": backup_name, "size": size}
        except Exception as e:
            return {"success": False, "message": f"备份失败: {e}"}

    def list_backups(self) -> List[Dict]:
        """列出所有备份文件。"""
        if not os.path.isdir(self.backups_dir):
            return []
        backups = []
        for fn in sorted(os.listdir(self.backups_dir), reverse=True):
            if fn.endswith(".zip"):
                fp = os.path.join(self.backups_dir, fn)
                backups.append({
                    "filename": fn,
                    "size": os.path.getsize(fp),
                    "created_at": os.path.getmtime(fp),
                })
        return backups

    def restore_backup(self, filename: str) -> Dict:
        """从备份 zip 恢复项目状态。"""
        import zipfile
        import tempfile
        backup_path = os.path.join(self.backups_dir, filename)
        if not os.path.exists(backup_path):
            return {"success": False, "message": "备份文件不存在"}
        try:
            with zipfile.ZipFile(backup_path, "r") as zf:
                bad = zf.testzip()
                if bad:
                    return {"success": False, "message": f"备份文件损坏: {bad}"}

                # 检查 zip slip 路径穿越
                for entry in zf.namelist():
                    dest = os.path.normpath(os.path.join(self.project_dir, entry))
                    if not dest.startswith(os.path.normpath(self.project_dir) + os.sep):
                        return {"success": False, "message": f"备份文件包含非法路径: {entry}"}

                # 先解压到临时目录
                temp_dir = tempfile.mkdtemp(prefix="kb_restore_")
                try:
                    zf.extractall(temp_dir)
                except Exception:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    return {"success": False, "message": "解压备份文件失败"}

                # 原子替换：清空项目目录（保留 backups），从 temp_dir 复制
                for item in os.listdir(self.project_dir):
                    if item == "backups":
                        continue
                    item_path = os.path.join(self.project_dir, item)
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path, ignore_errors=True)
                    else:
                        try:
                            os.remove(item_path)
                        except Exception:
                            pass

                # 从临时目录复制
                for item in os.listdir(temp_dir):
                    src = os.path.join(temp_dir, item)
                    dst = os.path.join(self.project_dir, item)
                    if os.path.isdir(src):
                        shutil.copytree(src, dst)
                    else:
                        shutil.copy2(src, dst)

                shutil.rmtree(temp_dir, ignore_errors=True)

            self._load_state()
            return {"success": True, "message": f"已从 {filename} 恢复"}
        except zipfile.BadZipFile:
            return {"success": False, "message": "备份文件损坏"}
        except Exception as e:
            return {"success": False, "message": f"恢复失败: {e}"}

    def delete_backup(self, filename: str) -> bool:
        """删除指定备份文件。"""
        backup_path = os.path.join(self.backups_dir, filename)
        if not os.path.exists(backup_path):
            return False
        try:
            os.remove(backup_path)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # 自定义词库
    # ------------------------------------------------------------------

    def add_vocab(self, word: str) -> Dict:
        """添加自定义词汇到 jieba 词典。"""
        import jieba
        if not word:
            return {"success": False, "message": "词汇不能为空"}
        if word in self.config.get("custom_vocab", []):
            return {"success": False, "message": "词汇已存在"}
        self.config.setdefault("custom_vocab", []).append(word)
        jieba.add_word(word)
        self._save_state()
        return {"success": True, "message": f"已添加: {word}"}

    def remove_vocab(self, word: str) -> Dict:
        """从自定义词库中移除词汇。"""
        import jieba
        if word not in self.config.get("custom_vocab", []):
            return {"success": False, "message": "词汇不存在"}
        self.config["custom_vocab"].remove(word)
        jieba.del_word(word)
        self._save_state()
        return {"success": True, "message": f"已删除: {word}"}

    # ------------------------------------------------------------------
    # 模型管理
    # ------------------------------------------------------------------

    def switch_model(self, model_name: str) -> Dict:
        """切换向量模型并触发全量重向量化。"""
        valid_models = {"bge-small-zh", "bge-large-zh", "text2vec-base"}
        if model_name not in valid_models:
            return {"success": False, "message": f"不支持的模型: {model_name}，可选: {valid_models}"}
        if self.config.get("embedding_model") == model_name:
            return {"success": False, "message": "已是当前模型"}
        self.config["embedding_model"] = model_name
        self._model = None  # 强制重新加载
        self._save_state()
        return self.revectorize_all()

    def revectorize_all(self) -> Dict:
        """遍历所有文档，从 raw_docs 重新切片 + 向量化。"""
        import numpy as np
        try:
            from document_parser import DocumentParser
        except ImportError:
            from api.document_parser import DocumentParser

        new_chunks = []
        all_vectors = []

        for doc in self.documents:
            raw_path = doc.get("raw_path", "")
            if not raw_path or not os.path.exists(raw_path):
                # 尝试用 file_hash 查找
                file_hash = doc.get("file_hash", "")
                if file_hash:
                    for ext in [".txt", ".md", ".docx", ".xlsx", ".pdf"]:
                        candidate = os.path.join(self.raw_docs_dir, f"{file_hash}{ext}")
                        if os.path.exists(candidate):
                            raw_path = candidate
                            break
            if not raw_path or not os.path.exists(raw_path):
                doc["status"] = "failed"
                continue

            try:
                content = DocumentParser.parse(raw_path)
                if not content or len(str(content)) < 20:
                    doc["status"] = "failed"
                    continue
                content = str(content)
            except Exception:
                doc["status"] = "failed"
                continue

            # 切片
            cmin = self.config.get("chunk_size_min", 100)
            cmax = self.config.get("chunk_size_max", 500)
            # 用标题感知切片
            import re
            clean = re.sub(r'<[^>]+>', ' ', content)
            clean = re.sub(r'\s+', ' ', clean).strip()
            if not clean:
                continue
            heading_matches = list(re.finditer(r'^(#{1,3})\s+(.+)$', clean, re.MULTILINE))
            if heading_matches:
                raw_chunks = self._chunk_by_headings(clean, heading_matches, cmin, cmax)
            else:
                paragraphs = re.split(r'\n\s*\n', clean)
                if len(paragraphs) > 1:
                    raw_chunks = self._chunk_by_paragraphs(paragraphs, cmin, cmax)
                else:
                    raw_chunks = []

            if not raw_chunks:
                raw_chunks = self._chunk_by_tokens(clean, cmin, cmax, 0.1)

            if not raw_chunks:
                doc["status"] = "failed"
                continue

            texts = [c["content"] for c in raw_chunks]
            try:
                vectors = self._encode_texts(texts)
            except Exception:
                doc["status"] = "failed"
                continue

            doc_id = doc["id"]
            for i, ch in enumerate(raw_chunks):
                new_chunks.append({
                    "id": f"{doc_id}_{i}",
                    "doc_id": doc_id,
                    "content": ch["content"],
                    "section_title": ch.get("section_title", ""),
                    "chunk_index": i,
                    "added_at": int(time.time()),
                    "metadata": {
                        "doc_id": doc_id,
                        "folder_id": doc.get("folder_id", ""),
                        "filename": doc.get("filename", ""),
                    },
                })
            all_vectors.append(vectors)
            doc["status"] = "ready"
            doc["chunk_count"] = len(raw_chunks)

        if not new_chunks:
            return {"success": False, "message": "没有文档需要重向量化"}

        self._chunks = new_chunks
        self._vectors = np.vstack(all_vectors) if all_vectors else None
        self._rebuild_bm25()
        self._save_state()
        return {"success": True, "message": f"重向量化完成，共 {len(new_chunks)} 个文本块"}
