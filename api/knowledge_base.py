from __future__ import annotations
import os
import json
import time
import hashlib
import traceback
import sys
import random
from typing import List, Dict, Any, Optional


class KnowledgeBase:
    """本地知识库：向量检索（本地 Embedding）+ BM25 关键词检索 + RRF 融合。"""

    def __init__(self, data_dir: str):
        """初始化知识库（不在启动时加载大模型，避免阻塞后端启动）。"""
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

        self.kb_dir = os.path.join(self.data_dir, "kb")
        os.makedirs(self.kb_dir, exist_ok=True)

        self.vectors_path = os.path.join(self.kb_dir, "vectors.npy")
        self.chunks_path = os.path.join(self.kb_dir, "chunks.json")

        self._model = None  # type: ignore
        self._hash_vectorizer = None  # type: ignore
        self._embedding_backend: str = "sentence_transformers"
        self._vectors = None  # type: ignore
        self._chunks: List[Dict[str, Any]] = []
        self._raw_docs: List[Dict[str, Any]] = []
        self._chunk_size_min = 100
        self._chunk_size_max = 500
        self._bm25 = None  # type: ignore

        self._load_state()

    def _ensure_model(self):
        """按需加载本地 Embedding 模型（首次使用会下载权重，后续走缓存）。"""
        if self._model is not None:
            return

        try:
            from sentence_transformers import SentenceTransformer
            hf_home = os.path.join(self.kb_dir, "hf_cache")
            os.makedirs(hf_home, exist_ok=True)
            os.environ.setdefault("HF_HOME", hf_home)
            os.environ.setdefault("TRANSFORMERS_CACHE", os.path.join(hf_home, "transformers"))
            os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", os.path.join(hf_home, "sentence_transformers"))
            os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

            self._model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
            self._embedding_backend = "sentence_transformers"
        except Exception as e:
            from sklearn.feature_extraction.text import HashingVectorizer
            self._model = None
            self._embedding_backend = "hashing"
            self._hash_vectorizer = HashingVectorizer(
                n_features=2048,
                alternate_sign=False,
                norm=None,
            )

    def _encode_texts(self, texts: List[str]) -> np.ndarray:
        """将文本列表编码为向量（优先 sentence-transformers，失败则回退 hashing）。"""
        import numpy as np
        from sklearn.preprocessing import normalize
        self._ensure_model()

        if self._embedding_backend == "sentence_transformers" and self._model is not None:
            vec = self._model.encode(texts, normalize_embeddings=True)
            return np.asarray(vec, dtype=np.float32)

        if self._hash_vectorizer is None:
            from sklearn.feature_extraction.text import HashingVectorizer
            self._hash_vectorizer = HashingVectorizer(n_features=2048, alternate_sign=False, norm=None)

        sparse = self._hash_vectorizer.transform(texts)
        sparse = normalize(sparse, norm="l2", copy=False)
        dense = sparse.astype(np.float32).toarray()
        return dense

    def _load_state(self):
        """从本地磁盘加载向量与分块数据。"""
        import numpy as np
        if os.path.exists(self.chunks_path):
            try:
                with open(self.chunks_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._chunks = data.get("chunks", [])
                    self._raw_docs = data.get("raw_docs", [])
                else:
                    # 兼容旧格式（纯数组）
                    self._chunks = data
                    self._raw_docs = []
            except Exception:
                self._chunks = []
                self._raw_docs = []

        if os.path.exists(self.vectors_path):
            try:
                self._vectors = np.load(self.vectors_path)
            except Exception:
                self._vectors = None

        self._rebuild_bm25()

    def _save_state(self):
        """将当前知识库状态写入磁盘（向量 + 分块元数据 + 原始文档）。"""
        data = {
            "chunks": self._chunks,
            "raw_docs": getattr(self, '_raw_docs', [])
        }
        with open(self.chunks_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        if self._vectors is None:
            if os.path.exists(self.vectors_path):
                try:
                    os.remove(self.vectors_path)
                except Exception:
                    pass
        else:
            np.save(self.vectors_path, self._vectors)

    def _rebuild_bm25(self):
        """重建 BM25 索引（轻量，数据量不大时足够快）。"""
        import jieba
        from rank_bm25 import BM25Okapi
        if not self._chunks:
            self._bm25 = None
            return

        tokenized = [jieba.lcut(c.get("content", "")) for c in self._chunks]
        self._bm25 = BM25Okapi(tokenized)

    def get_file_hash(self, file_path: str) -> str:
        """计算文件哈希用于去重（MD5）。"""
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _chunk_text_tokens(self, text: str, chunk_tokens: int = None, overlap_ratio: float = 0.1) -> List[str]:
        """按中文分词后的 token 数切块（区间随机值，10% 重叠）。"""
        import jieba
        import random
        if chunk_tokens is not None:
            pass  # 使用传入的固定值
        else:
            cmin = getattr(self, '_chunk_size_min', 100)
            cmax = getattr(self, '_chunk_size_max', 500)
            if cmin >= cmax:
                cmax = cmin + 50
            chunk_tokens = random.randint(cmin, cmax)
        # 去掉 HTML 标签再分词，防止 <table>/style= 等被当成 token 产生海量无意义分块
        import re
        clean = re.sub(r'<[^>]+>', ' ', text)
        clean = re.sub(r'\s+', ' ', clean).strip()
        if not clean:
            return []
        tokens = [t for t in jieba.lcut(clean) if t.strip()]
        if not tokens:
            return []

        overlap = max(1, int(chunk_tokens * overlap_ratio))
        chunks: List[str] = []
        start = 0
        while start < len(tokens):
            end = min(len(tokens), start + chunk_tokens)
            chunks.append("".join(tokens[start:end]))
            if end >= len(tokens):
                break
            start = max(0, end - overlap)
        return chunks

    def add_document(self, file_path: str, filename: str, content: str, doc_type: str = "unknown", version: str = "v1.0", file_size: int = 0) -> Dict[str, Any]:
        """将文档解析内容写入知识库（去重、分块、向量化、入库）。"""
        import numpy as np
        try:
            file_hash = self.get_file_hash(file_path)
        except Exception as e:
            return {"success": False, "message": f"计算文件哈希失败: {str(e)}"}

        if any(c.get("metadata", {}).get("file_hash") == file_hash for c in self._chunks):
            return {"success": False, "message": "文件已存在，跳过导入"}

        # 保存原始文档内容
        raw_doc = {
            "file_hash": file_hash,
            "filename": filename,
            "content": content,
            "doc_type": doc_type,
            "file_size": file_size,
            "added_at": int(time.time()),
        }
        # 去重
        self._raw_docs = [d for d in getattr(self, '_raw_docs', []) if d.get("file_hash") != file_hash]
        self._raw_docs.append(raw_doc)

        chunks = self._chunk_text_tokens(content)
        if not chunks:
            return {"success": False, "message": "文档内容为空"}

        try:
            vectors = self._encode_texts(chunks)
        except Exception as e:
            return {"success": False, "message": f"向量化失败: {str(e)}"}

        created_at = int(time.time())
        new_chunk_records: List[Dict[str, Any]] = []
        for i, chunk in enumerate(chunks):
            new_chunk_records.append(
                {
                    "id": f"{file_hash}_{i}",
                    "content": chunk,
                    "metadata": {
                        "filename": filename,
                        "type": doc_type,
                        "version": version,
                        "file_hash": file_hash,
                        "file_size": file_size,
                        "chunk_index": i,
                        "added_at": created_at,
                    },
                }
            )

        if self._vectors is None or len(self._chunks) == 0:
            self._vectors = vectors
            self._chunks = new_chunk_records
        else:
            self._vectors = np.vstack([self._vectors, vectors])
            self._chunks.extend(new_chunk_records)

        self._rebuild_bm25()
        self._save_state()

        return {"success": True, "message": f"成功导入 {len(chunks)} 个文本块", "chunks": len(chunks)}

    def rechunk_all(self) -> Dict[str, Any]:
        """根据当前 chunk_size_min/max 重新分块所有已有文档。"""
        import numpy as np
        raw_docs = getattr(self, '_raw_docs', [])
        if not raw_docs:
            return {"success": False, "message": "没有原始文档数据，无法重新分块"}

        new_chunks: List[Dict[str, Any]] = []
        all_vectors: List[np.ndarray] = []

        for raw in raw_docs:
            content = raw.get("content", "")
            if not content:
                continue
            chunks = self._chunk_text_tokens(content)
            if not chunks:
                continue

            file_hash = raw.get("file_hash", "unknown")
            filename = raw.get("filename", "unknown")
            doc_type = raw.get("doc_type", "unknown")
            file_size = raw.get("file_size", 0)

            try:
                vectors = self._encode_texts(chunks)
            except Exception:
                continue

            for i, chunk in enumerate(chunks):
                new_chunks.append({
                    "id": f"{file_hash}_{i}",
                    "content": chunk,
                    "metadata": {
                        "filename": filename,
                        "type": doc_type,
                        "file_hash": file_hash,
                        "file_size": file_size,
                        "chunk_index": i,
                        "added_at": int(time.time()),
                    },
                })
            all_vectors.append(vectors)

        if not new_chunks:
            return {"success": False, "message": "重新分块后没有生成任何文本块"}

        self._chunks = new_chunks
        self._vectors = np.vstack(all_vectors) if len(all_vectors) > 0 else None
        self._rebuild_bm25()
        self._save_state()

        return {"success": True, "message": f"已重新分块，共 {len(new_chunks)} 个文本块"}

    def search(self, query: str, top_k: int = 6) -> List[Dict[str, Any]]:
        """混合检索：向量（语义）+ BM25（关键词），用 RRF 融合返回 TopK。"""
        import numpy as np
        import jieba
        if not self._chunks:
            return []

        # 向量检索
        q_vec = self._encode_texts([query])

        vec_scores = None
        if self._vectors is not None and self._vectors.shape[0] == len(self._chunks):
            vec_scores = (self._vectors @ q_vec[0]).astype(np.float32)

        # 取向量 TopN
        vec_rank: Dict[str, float] = {}
        if vec_scores is not None:
            top_n = min(len(self._chunks), max(top_k * 2, 10))
            idxs = np.argpartition(-vec_scores, top_n - 1)[:top_n]
            idxs = idxs[np.argsort(-vec_scores[idxs])]
            for rank, idx in enumerate(idxs.tolist()):
                chunk_id = self._chunks[idx]["id"]
                vec_rank[chunk_id] = 1.0 / (rank + 1)

        # BM25 检索
        bm25_rank: Dict[str, float] = {}
        if self._bm25 is not None:
            tokenized_query = jieba.lcut(query)
            scores = self._bm25.get_scores(tokenized_query)
            scores = np.asarray(scores, dtype=np.float32)
            top_n = min(len(self._chunks), max(top_k * 2, 10))
            idxs = np.argpartition(-scores, top_n - 1)[:top_n]
            idxs = idxs[np.argsort(-scores[idxs])]
            for rank, idx in enumerate(idxs.tolist()):
                if scores[idx] <= 0:
                    continue
                chunk_id = self._chunks[idx]["id"]
                bm25_rank[chunk_id] = 1.0 / (rank + 1)

        # RRF 融合
        combined: Dict[str, float] = {}
        for cid in set(vec_rank.keys()).union(bm25_rank.keys()):
            combined[cid] = vec_rank.get(cid, 0) + bm25_rank.get(cid, 0)

        sorted_ids = sorted(combined.keys(), key=lambda x: combined[x], reverse=True)[:top_k]

        results: List[Dict[str, Any]] = []
        id_to_idx = {c["id"]: i for i, c in enumerate(self._chunks)}
        for cid in sorted_ids:
            idx = id_to_idx.get(cid)
            if idx is None:
                continue
            results.append(
                {
                    "content": self._chunks[idx].get("content", ""),
                    "metadata": self._chunks[idx].get("metadata", {}),
                    "score": float(combined.get(cid, 0)),
                }
            )

        return results

    def get_stats(self) -> Dict[str, Any]:
        """返回知识库概览：文档数、向量块数、文档列表、库大小。"""
        if not self._chunks:
            return {"total_documents": 0, "total_chunks": 0, "documents": [], "total_size_bytes": 0, "vector_count": 0}

        docs: Dict[str, Dict[str, Any]] = {}
        for c in self._chunks:
            meta = c.get("metadata", {})
            fh = meta.get("file_hash")
            if not fh:
                continue
            if fh not in docs:
                docs[fh] = {
                    "file_hash": fh,
                    "filename": meta.get("filename", ""),
                    "type": meta.get("type", "unknown"),
                    "version": meta.get("version", "v1.0"),
                    "added_at": meta.get("added_at", 0),
                    "file_size": meta.get("file_size", 0),
                    "chunks_count": 0,
                }
            docs[fh]["chunks_count"] += 1

        documents = sorted(docs.values(), key=lambda x: x.get("added_at", 0), reverse=True)
        total_size = sum(d.get("file_size", 0) for d in documents)
        return {
            "total_documents": len(documents),
            "total_chunks": len(self._chunks),
            "total_size_bytes": total_size,
            "vector_count": len(self._vectors) if self._vectors is not None else 0,
            "documents": documents,
        }

    def delete_document(self, file_hash: str) -> Dict[str, Any]:
        """删除某个文档的所有分块（含向量）。"""
        keep_idxs = [i for i, c in enumerate(self._chunks) if c.get("metadata", {}).get("file_hash") != file_hash]
        if len(keep_idxs) == len(self._chunks):
            return {"success": False, "message": "未找到该文档"}

        self._chunks = [self._chunks[i] for i in keep_idxs]
        # 同时删除 raw_docs 中对应的文档
        self._raw_docs = [d for d in getattr(self, '_raw_docs', []) if d.get("file_hash") != file_hash]
        if self._vectors is not None and self._vectors.shape[0] >= len(keep_idxs):
            self._vectors = self._vectors[keep_idxs]
        else:
            self._vectors = None

        self._rebuild_bm25()
        self._save_state()
        return {"success": True}

    def clear_all(self) -> Dict[str, Any]:
        """清空知识库。"""
        self._chunks = []
        self._raw_docs = []
        self._vectors = None
        self._bm25 = None
        self._save_state()
        return {"success": True}
