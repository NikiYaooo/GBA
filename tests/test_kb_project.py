"""tests/test_kb_project.py — KBProject 单元测试。"""

import os
import json
import time
import tempfile
import shutil
import pytest

# 将被测试对象加入路径
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.kb_project import KBProject


# ======================================================================
# Fixtures
# ======================================================================

@pytest.fixture
def tmp_project():
    """创建临时项目目录并返回 KBProject 实例，测试后自动清理。"""
    tmp_dir = tempfile.mkdtemp(prefix="kb_test_")
    project = KBProject(project_dir=tmp_dir)
    yield project
    shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.fixture
def tmp_project_dir():
    """仅返回临时目录路径，不创建 KBProject 实例。"""
    tmp_dir = tempfile.mkdtemp(prefix="kb_test_")
    yield tmp_dir
    shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.fixture
def sample_txt(tmp_project_dir):
    """创建示例文本文件并返回路径。"""
    path = os.path.join(tmp_project_dir, "sample.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("这是示例文档内容。")
    return path


# ======================================================================
# 初始化测试
# ======================================================================

class TestInit:
    def test_creates_directories(self, tmp_project_dir):
        """初始化时应创建所有必需目录。"""
        project = KBProject(project_dir=tmp_project_dir)
        assert os.path.isdir(project.project_dir)
        assert os.path.isdir(project.raw_docs_dir)
        assert os.path.isdir(project.backups_dir)

    def test_default_config(self, tmp_project_dir):
        """默认配置应包含正确默认值。"""
        project = KBProject(project_dir=tmp_project_dir)
        assert project.config["chunk_size_min"] == 100
        assert project.config["chunk_size_max"] == 500
        assert project.config["embedding_model"] == "bge-small-zh"
        assert project.config["custom_vocab"] == []

    def test_custom_config_overrides_defaults(self, tmp_project_dir):
        """传入的 project_config 应覆盖默认配置。"""
        custom = {"chunk_size_min": 200, "embedding_model": "bge-large-zh"}
        project = KBProject(project_dir=tmp_project_dir, project_config=custom)
        assert project.config["chunk_size_min"] == 200
        assert project.config["embedding_model"] == "bge-large-zh"
        # 未被覆盖的配置项保留默认值
        assert project.config["chunk_size_max"] == 500

    def test_loads_existing_state(self, tmp_project_dir):
        """应从磁盘加载已有状态。"""
        # 先创建项目并写入数据
        project1 = KBProject(project_dir=tmp_project_dir)
        folder = project1.create_folder("测试文件夹")["folder"]
        doc_id = project1.add_document(
            file_path=__file__,  # 用当前文件作为测试文件
            filename="test.py",
            content="test",
            doc_type="py",
            file_size=100,
        )["doc_id"]

        # 重新创建 KBProject 实例，应加载之前的数据
        project2 = KBProject(project_dir=tmp_project_dir)
        assert len(project2.folders) == 1
        assert project2.folders[0]["name"] == "测试文件夹"
        assert len(project2.documents) == 1
        assert project2.documents[0]["id"] == doc_id

    def test_loads_existing_empty_files(self, tmp_project_dir):
        """空的或不存在的文件不应导致错误。"""
        project = KBProject(project_dir=tmp_project_dir)
        # 创建空文件来模拟损坏的场景
        for fname in ["config.json", "folders.json", "documents.json", "chunks.json"]:
            path = os.path.join(tmp_project_dir, fname)
            with open(path, "w", encoding="utf-8") as f:
                f.write("invalid json{")
        # 重新加载不应崩溃
        project2 = KBProject(project_dir=tmp_project_dir)
        assert project2.folders == []
        assert project2.documents == []
        assert project2._chunks == []

    def test_initial_state_is_empty(self, tmp_project_dir):
        """新项目应无文档、无文件夹、无块。"""
        project = KBProject(project_dir=tmp_project_dir)
        assert project.folders == []
        assert project.documents == []
        assert project._chunks == []
        assert project._vectors is None


# ======================================================================
# 文件夹管理测试
# ======================================================================

class TestFolderManagement:
    def test_create_folder(self, tmp_project):
        """创建文件夹应返回包含 id 的文件夹对象。"""
        result = tmp_project.create_folder("世界观")
        assert result["success"] is True
        folder = result["folder"]
        assert folder["name"] == "世界观"
        assert "id" in folder
        assert "created_at" in folder

    def test_create_folder_stores_in_list(self, tmp_project):
        """创建文件夹后应出现在文件夹列表中。"""
        tmp_project.create_folder("系统")
        assert len(tmp_project.folders) == 1
        assert tmp_project.folders[0]["name"] == "系统"

    def test_rename_folder(self, tmp_project):
        """重命名文件夹应更新名称。"""
        f = tmp_project.create_folder("旧名称")["folder"]
        result = tmp_project.rename_folder(f["id"], "新名称")
        assert result["success"] is True
        updated = result["folder"]
        assert updated["name"] == "新名称"
        # 验证持久化
        reloaded = KBProject(project_dir=tmp_project.project_dir)
        assert reloaded.folders[0]["name"] == "新名称"

    def test_rename_nonexistent_folder(self, tmp_project):
        """重命名不存在的文件夹应返回错误。"""
        result = tmp_project.rename_folder("no-such-id", "新名称")
        assert result["success"] is False

    def test_delete_folder(self, tmp_project):
        """删除文件夹后列表应不再包含它。"""
        f = tmp_project.create_folder("数值")["folder"]
        result = tmp_project.delete_folder(f["id"])
        assert result["success"] is True
        assert len(tmp_project.folders) == 0

    def test_delete_folder_moves_docs_to_root(self, tmp_project, sample_txt):
        """删除文件夹时其中的文档应移出到根目录。"""
        folder = tmp_project.create_folder("待删")["folder"]
        tmp_project.add_document(
            file_path=sample_txt,
            filename="doc1.txt",
            content="内容",
            doc_type="txt",
            file_size=10,
            folder_id=folder["id"],
        )
        # 确认文档在文件夹中
        docs_in_folder = tmp_project.get_documents(folder_id=folder["id"])
        assert len(docs_in_folder) == 1

        # 删除文件夹
        tmp_project.delete_folder(folder["id"])

        # 文档应在根目录
        root_docs = tmp_project.get_documents(folder_id="")
        assert len(root_docs) == 1
        assert root_docs[0]["filename"] == "doc1.txt"

    def test_delete_nonexistent_folder(self, tmp_project):
        """删除不存在的文件夹应返回错误。"""
        result = tmp_project.delete_folder("no-such-id")
        assert result["success"] is False


# ======================================================================
# 文档管理测试
# ======================================================================

class TestDocumentManagement:
    def test_add_document_creates_record(self, tmp_project, sample_txt):
        """add_document 应创建文档记录并复制文件到 raw_docs。"""
        result = tmp_project.add_document(
            file_path=sample_txt,
            filename="示例.txt",
            content="这是示例文档内容。",
            doc_type="txt",
            file_size=os.path.getsize(sample_txt),
        )
        assert result["success"] is True
        assert result["doc_id"] is not None
        assert len(tmp_project.documents) == 1

        doc = tmp_project.documents[0]
        assert doc["filename"] == "示例.txt"
        assert doc["doc_type"] == "txt"
        assert doc["status"] == "ready"
        assert doc["folder_id"] == ""

        # 文件应复制到 raw_docs
        assert os.path.exists(doc["raw_path"])

    def test_add_document_with_folder(self, tmp_project, sample_txt):
        """add_document 应支持指定文件夹。"""
        folder = tmp_project.create_folder("测试")["folder"]
        result = tmp_project.add_document(
            file_path=sample_txt,
            filename="doc.txt",
            content="内容",
            doc_type="txt",
            file_size=10,
            folder_id=folder["id"],
        )
        assert result["success"] is True
        doc = tmp_project.documents[0]
        assert doc["folder_id"] == folder["id"]

    def test_add_document_with_note(self, tmp_project, sample_txt):
        """add_document 应支持指定备注。"""
        tmp_project.add_document(
            file_path=sample_txt,
            filename="备注测试.txt",
            content="内容",
            doc_type="txt",
            file_size=10,
            note="这是一个重要文档",
        )
        assert tmp_project.documents[0]["note"] == "这是一个重要文档"

    def test_add_document_hash_dedup_updates(self, tmp_project, sample_txt):
        """相同 hash 的文档应触发覆盖更新而非新建。"""
        # 第一次添加
        result1 = tmp_project.add_document(
            file_path=sample_txt,
            filename="original.txt",
            content="原始内容",
            doc_type="txt",
            file_size=10,
            note="原始备注",
            folder_id="",
        )
        # 第二次添加相同文件（相同 hash）
        result2 = tmp_project.add_document(
            file_path=sample_txt,
            filename="updated.txt",
            content="更新后的内容",
            doc_type="txt",
            file_size=20,
        )
        assert result2["success"] is True
        # 文档数应仍为 1（覆盖而非新增）
        assert len(tmp_project.documents) == 1
        doc = tmp_project.documents[0]
        # 文件名应更新
        assert doc["filename"] == "updated.txt"
        # 备注应保留（_update_document 中传入空字符串时不覆盖）
        assert doc["note"] == "原始备注"

    def test_add_document_filename_conflict(self, tmp_project, sample_txt):
        """同名但不同 hash 的文档应自动添加序号后缀。"""
        # 添加第一个文档
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as f:
            f.write("content A")
            path_a = f.name
        try:
            result1 = tmp_project.add_document(
                file_path=path_a,
                filename="同名.txt",
                content="A",
                doc_type="txt",
                file_size=10,
            )
            assert result1["success"] is True

            # 创建另一个内容不同的文件
            with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as f:
                f.write("content B")
                path_b = f.name
            try:
                result2 = tmp_project.add_document(
                    file_path=path_b,
                    filename="同名.txt",
                    content="B",
                    doc_type="txt",
                    file_size=10,
                )
                assert result2["success"] is True
                # 第二个文档应自动重命名
                assert len(tmp_project.documents) == 2
                assert tmp_project.documents[0]["filename"] == "同名.txt"
                assert tmp_project.documents[1]["filename"] == "同名 (1).txt"
            finally:
                os.unlink(path_b)
        finally:
            os.unlink(path_a)

    def test_delete_document(self, tmp_project, sample_txt):
        """删除文档应移除记录和块。"""
        result = tmp_project.add_document(
            file_path=sample_txt,
            filename="待删.txt",
            content="将被删除",
            doc_type="txt",
            file_size=10,
        )
        doc_id = result["doc_id"]

        delete_result = tmp_project.delete_document(doc_id)
        assert delete_result["success"] is True
        assert len(tmp_project.documents) == 0

    def test_delete_nonexistent_document(self, tmp_project):
        """删除不存在的文档应返回错误。"""
        result = tmp_project.delete_document("no-such-id")
        assert result["success"] is False

    def test_get_doc_by_hash(self, tmp_project, sample_txt):
        """get_doc_by_hash 应通过哈希查找文档。"""
        result = tmp_project.add_document(
            file_path=sample_txt,
            filename="哈希测试.txt",
            content="内容",
            doc_type="txt",
            file_size=10,
        )
        doc = tmp_project.documents[0]
        file_hash = doc["file_hash"]

        found = tmp_project.get_doc_by_hash(file_hash)
        assert found is not None
        assert found["id"] == doc["id"]

        not_found = tmp_project.get_doc_by_hash("ffffffffffffffffffffffffffffffff")
        assert not_found is None

    def test_update_document_meta(self, tmp_project, sample_txt):
        """update_document_meta 应更新允许的字段。"""
        result = tmp_project.add_document(
            file_path=sample_txt,
            filename="原名称.txt",
            content="内容",
            doc_type="txt",
            file_size=10,
        )
        doc_id = result["doc_id"]

        # 更新名称和备注
        update_result = tmp_project.update_document_meta(doc_id, {
            "filename": "新名称.txt",
            "note": "新增备注",
            "folder_id": "some-folder",
        })
        assert update_result["success"] is True

        doc = tmp_project.documents[0]
        assert doc["filename"] == "新名称.txt"
        assert doc["note"] == "新增备注"
        assert doc["folder_id"] == "some-folder"

    def test_update_document_meta_rejects_invalid_keys(self, tmp_project, sample_txt):
        """update_document_meta 应拒绝修改不允许的字段。"""
        result = tmp_project.add_document(
            file_path=sample_txt,
            filename="安全测试.txt",
            content="内容",
            doc_type="txt",
            file_size=10,
        )
        doc_id = result["doc_id"]
        original_id = tmp_project.documents[0]["id"]

        tmp_project.update_document_meta(doc_id, {"id": "should-not-change", "file_hash": "hack"})
        doc = tmp_project.documents[0]
        assert doc["id"] == original_id  # 不应被修改

    def test_update_document_meta_nonexistent(self, tmp_project):
        """update_document_meta 对不存在的文档应返回错误。"""
        result = tmp_project.update_document_meta("no-such-id", {"filename": "新名称"})
        assert result["success"] is False

    def test_remove_doc_vectors(self, tmp_project, sample_txt):
        """_remove_doc_vectors 应只移除指定文档的块。"""
        # 添加一个文档用于获取真实的 doc_id
        result = tmp_project.add_document(
            file_path=sample_txt,
            filename="remove_test.txt",
            content="test",
            doc_type="txt",
            file_size=10,
        )
        doc_a = tmp_project.documents[0]
        file_hash_a = doc_a["file_hash"]
        doc_id_a = doc_a["id"]

        # 创建另一个文档用于对照
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as f:
            f.write("other content")
            other_path = f.name
        try:
            result2 = tmp_project.add_document(
                file_path=other_path,
                filename="other.txt",
                content="other",
                doc_type="txt",
                file_size=10,
            )
            doc_b = tmp_project.documents[1]
            doc_id_b = doc_b["id"]

            # 手动设置 chunks，使用真实的 doc_id（UUID）
            tmp_project._chunks = [
                {"id": "c1", "doc_id": doc_id_a, "content": "chunk from A"},
                {"id": "c2", "doc_id": doc_id_b, "content": "chunk from B"},
                {"id": "c3", "doc_id": doc_id_a, "content": "another chunk from A"},
            ]

            # 通过 file_hash 移除文档 A 的块
            tmp_project._remove_doc_vectors(file_hash_a)
            assert len(tmp_project._chunks) == 1
            assert tmp_project._chunks[0]["doc_id"] == doc_id_b
        finally:
            os.unlink(other_path)


# ======================================================================
# 统计与列表测试
# ======================================================================

class TestStatsAndListing:
    def test_get_stats_empty(self, tmp_project):
        """空项目统计应全为零。"""
        stats = tmp_project.get_stats()
        assert stats["total_documents"] == 0
        assert stats["total_chunks"] == 0
        assert stats["total_size_bytes"] == 0
        assert stats["folder_counts"] == {}
        assert stats["uncategorized_count"] == 0
        assert "config" in stats

    def test_get_stats_with_data(self, tmp_project, sample_txt):
        """有数据时统计应正确。"""
        f1 = tmp_project.create_folder("世界观")["folder"]
        f2 = tmp_project.create_folder("系统")["folder"]

        # 添加两个文档到不同文件夹
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as f:
            f.write("hello")
            p1 = f.name
        try:
            tmp_project.add_document(
                file_path=p1, filename="doc1.txt", content="hello",
                doc_type="txt", file_size=5, folder_id=f1["id"],
            )
        finally:
            os.unlink(p1)

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as f:
            f.write("world")
            p2 = f.name
        try:
            tmp_project.add_document(
                file_path=p2, filename="doc2.txt", content="world",
                doc_type="txt", file_size=5, folder_id=f2["id"],
            )
        finally:
            os.unlink(p2)

        # 手动创建一个块来测试 chunks 计数
        tmp_project._chunks = [{"id": "c1", "doc_id": "h1", "content": "hello"}]

        stats = tmp_project.get_stats()
        assert stats["total_documents"] == 2
        assert stats["total_chunks"] == 1
        assert stats["total_size_bytes"] == 10
        assert stats["folder_counts"].get(f1["id"]) == 1
        assert stats["folder_counts"].get(f2["id"]) == 1
        assert stats["uncategorized_count"] == 0
        assert stats["config"]["embedding_model"] == "bge-small-zh"

    def test_get_documents_all(self, tmp_project, sample_txt):
        """get_documents 无参数应返回所有文档。"""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as f:
            f.write("a")
            p1 = f.name
        try:
            tmp_project.add_document(file_path=p1, filename="a.txt", content="a", doc_type="txt", file_size=1)
        finally:
            os.unlink(p1)

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as f:
            f.write("b")
            p2 = f.name
        try:
            tmp_project.add_document(file_path=p2, filename="b.txt", content="b", doc_type="txt", file_size=1)
        finally:
            os.unlink(p2)

        all_docs = tmp_project.get_documents()
        assert len(all_docs) == 2

    def test_get_documents_by_folder(self, tmp_project, sample_txt):
        """get_documents 带 folder_id 应过滤。"""
        folder = tmp_project.create_folder("测试")["folder"]

        tmp_project.add_document(
            file_path=sample_txt, filename="根目录文档.txt",
            content="根", doc_type="txt", file_size=10,
        )

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as f:
            f.write("folder doc")
            p = f.name
        try:
            tmp_project.add_document(
                file_path=p, filename="文件夹文档.txt",
                content="文件夹", doc_type="txt", file_size=10,
                folder_id=folder["id"],
            )
        finally:
            os.unlink(p)

        folder_docs = tmp_project.get_documents(folder_id=folder["id"])
        assert len(folder_docs) == 1
        assert folder_docs[0]["filename"] == "文件夹文档.txt"

        root_docs = tmp_project.get_documents(folder_id="")
        assert len(root_docs) == 1
        assert root_docs[0]["filename"] == "根目录文档.txt"
