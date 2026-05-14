# RAG 向量库功能重构设计文档

> **版本：** v2.6.2  
> **目标：** 将单知识库重构为多项目隔离、文件夹分类、智能切片、多模型切换的完整知识库管理系统  
> **技术栈：** Python 3.10+ / FastAPI / sentence-transformers / jieba / numpy / Vue 3 + Element Plus  
> **构建方式：** 目录隔离式（零新依赖）

---

## 1. 架构总览

### 1.1 目录结构

```
{app_data}/kb/
  projects.json                  # 项目列表索引 [{id, name, type, model, created_at}]
  project_{uuid}/
    config.json                  # 项目配置（chunk 区间、模型名、自定义词库）
    folders.json                 # 文件夹列表 [{id, name, doc_count}]
    documents.json               # 文档元数据 [{id, filename, folder_id, note, size, status}]
    chunks.json                  # 文本块 [{id, doc_id, content, metadata}]
    vectors.npy                  # numpy 向量矩阵
    raw_docs/                    # 原始上传文件（用于重向量化）
      {doc_hash}.ext
    backups/                     # 手动备份 .zip 文件
```

### 1.2 核心类设计

**KnowledgeBase**（原有，保持接口兼容）
- 单例，管理 projects.json 索引
- 代理方法：`search()`, `search_by_categories()` 自动定位到当前活动项目
- 新增：`create_project()`, `delete_project()`, `get_project()`, `list_projects()`

**KBProject**（新增）
- 封装单个项目的所有操作
- 构造时加载项目目录下的所有数据
- 文档管理：upload / delete / rename / set_note / move_folder
- 文件夹管理：create_folder / rename_folder / delete_folder
- 切片管理：chunk / rechunk_doc / rechunk_folder / rechunk_all
- 向量化：encode / revectorize
- 检索：search / search_by_folders / fuzzy_search
- 备份：create_backup / list_backups / restore_backup
- 配置：get_config / update_config / add_vocab / remove_vocab

### 1.3 对比当前架构

| 维度 | 当前 (v2.6.1) | 重构后 (v2.6.2) |
|------|---------------|-----------------|
| 项目数 | 1（硬编码） | 多项目，完全隔离 |
| 文档分类 | type 字段 | 文件夹系统 |
| 切片方式 | 纯 token 随机切 | 按标题/章节智能切 + token 回退 |
| 向量模型 | bge-small-zh-v1.5 固定 | 3 种模型可选，切换自动重向量化 |
| 自定义词库 | 无 | jieba 用户词典 |
| 文档备注 | 无 | 每个文档可加备注文字 |
| 重向量化 | 全库一次 | 单文档/文件夹/全项目 |
| 备份 | 无 | 手动备份/恢复 |
| 检索过滤 | 无 | 按项目+文件夹筛选 |
| 模糊检索 | 无 | 关键词模糊匹配 |
| 与 PRD 联动 | 已有基础 | 增加引用标注、检索片段手动调整 |

---

## 2. API 设计

### 2.1 项目管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/kb/project` | 创建项目 |
| GET | `/api/kb/projects` | 项目列表 |
| PUT | `/api/kb/project/{id}` | 更新项目（名称、描述） |
| DELETE | `/api/kb/project/{id}` | 删除项目（含所有数据） |
| POST | `/api/kb/project/{id}/archive` | 归档项目 |
| POST | `/api/kb/project/{id}/activate` | 切换当前活动项目 |

### 2.2 文件夹管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/kb/project/{id}/folder` | 创建文件夹 |
| PUT | `/api/kb/project/{id}/folder/{fid}` | 重命名文件夹 |
| DELETE | `/api/kb/project/{id}/folder/{fid}` | 删除文件夹（文档移出到根目录） |
| GET | `/api/kb/project/{id}/folders` | 文件夹列表 |

### 2.3 文档管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/kb/project/{id}/upload` | 上传文档（单/多文件） |
| GET | `/api/kb/project/{id}/documents` | 文档列表（支持 folder_id 过滤） |
| PUT | `/api/kb/project/{id}/doc/{doc_id}` | 更新文档（重命名、备注、移动文件夹） |
| DELETE | `/api/kb/project/{id}/doc/{doc_id}` | 删除文档及其向量 |
| POST | `/api/kb/project/{id}/doc/{doc_id}/revectorize` | 单文档重向量化 |

### 2.4 检索

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/kb/project/{id}/search` | 语义检索（支持 folder 过滤、top_k） |
| POST | `/api/kb/project/{id}/fuzzy-search` | 关键词模糊检索 |
| POST | `/api/kb/global-search` | 跨项目检索 |

### 2.5 配置与工具

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/kb/project/{id}/config` | 获取项目配置 |
| PUT | `/api/kb/project/{id}/config` | 更新项目配置（chunk、model） |
| POST | `/api/kb/project/{id}/rechunk` | 按当前配置重新切片全项目 |
| POST | `/api/kb/project/{id}/folder/{fid}/rechunk` | 重切片单个文件夹 |
| POST | `/api/kb/project/{id}/backup` | 创建备份 |
| GET | `/api/kb/project/{id}/backups` | 列出备份 |
| POST | `/api/kb/project/{id}/restore` | 恢复备份 |
| GET | `/api/kb/project/{id}/stats` | 项目统计 |
| GET | `/api/kb/vocab` | 获取自定义词库列表（所有项目） |
| POST | `/api/kb/project/{id}/vocab` | 添加自定义词汇 |
| DELETE | `/api/kb/project/{id}/vocab/{word}` | 删除自定义词汇 |

### 2.6 与智能 PRD 联动（AI 服务接口更新）

`POST /api/ai/imitate` 新增可选参数：
- `project_id`: 指定使用哪个项目库做 RAG 检索（不传则不使用 RAG）
- `kb_only`: boolean，为 true 时强制仅基于知识库内容生成
- `cite_sources`: boolean，为 true 时在生成内容中标注引用来源（文档名+章节）

`POST /api/ai/complete-logic` 同理新增 `project_id` 参数。



### 2.7 活跃项目机制

- 前端维护当前活跃项目 ID（localStorage 持久化）
- 所有前端 KB 操作默认指向活跃项目
- AI 仿写/逻辑补完时，前端将 `project_id` 传入 `POST /api/ai/imitate`
- 后端不维护"默认项目"状态，完全由前端指定

---

## 3. 智能切片算法

### 3.1 标题感知切片

```
输入: 文档原始文本
1. 尝试按 Markdown 标题分割（# / ## / ### 正则匹配）
2. 如果是 DOCX，尝试读取 heading 样式段落
3. 如果检测到标题结构：
   a. 以每个一级/二级标题作为章节起点
   b. 该标题到下一标题之间内容作为一节
   c. 如该节超过 max_chars（默认500），按段落二次分割
4. 如果无标题结构（纯文本）：
   a. 回退到现有 token 切分算法
5. 每段不得少于 min_chars（默认100）
```

### 3.2 切片配置

- 区间：100-1000 字符（用户可调）
- 重叠：10%（固定，防止边界截断语义）

---

## 4. 向量模型管理

### 4.1 内置模型

| 模型名称 | 标识符 | 大小 | 特点 |
|----------|--------|------|------|
| BAAI/bge-small-zh-v1.5 | bge-small-zh | ~33MB | 轻量，默认 |
| BAAI/bge-large-zh-v1.5 | bge-large-zh | ~1.3GB | 高精度 |
| text2vec-base-chinese | text2vec-base | ~390MB | 国产中文优化 |

### 4.2 模型切换流程

1. 用户选择新模型 → 保存到 config.json
2. 触发全量重向量化
3. 进度通过 `GET /api/kb/project/{id}/vector-status` 轮询
4. 切换期间检索功能暂用旧模型，完成后原子切换

---

## 5. 自定义词库

- 存储在 `project_{uuid}/config.json` 的 `custom_vocab` 字段
- 每次添加/删除后调用 `jieba.add_word(word)` / `jieba.del_word(word)`
- 分词前加载用户词典
- 词库变更后提示用户重跑向量化以生效

---

## 6. 前端组件设计

### 6.1 组件拆分

| 组件 | 说明 |
|------|------|
| `KBDialog.vue` | 主弹窗，左侧项目列表 + 右侧内容区（重构已有） |
| `KBProjectPanel.vue` | 左侧项目切换面板 + 新建项目按钮 |
| `KBFolderTabs.vue` | 文件夹标签页 |
| `KBDocList.vue` | 文档列表（备注图标/搜索/筛选） |
| `KBSearchPanel.vue` | 检索面板（独立弹窗，Ctrl+F 触发） |
| `KBProjectDialog.vue` | 新建/编辑项目对话框 |
| `KBDocNoteDialog.vue` | 文档备注编辑对话框 |
| `KBBackupDialog.vue` | 备份管理对话框 |
| `KBVocabDialog.vue` | 自定义词库管理对话框 |

### 6.2 检索面板与 PRD 联动

ImitateDialog 新增区域：
- 当前知识库状态标签：`已关联项目: 项目A（128 文档）`
- 复选框：[ ] 仅基于知识库内容生成
- 复选框：[ ] 引用标注（在生成内容中标明文档来源）
- 检索片段列表：展示已命中的片段，支持手动移除/添加

---

## 7. 数据兼容与迁移

### 7.1 升级路径

首次启动 v2.6.2 时自动检测：
1. 如果 `kb/chunks.json` 存在且有数据 → 自动创建默认项目"默认项目库"
2. 将旧 chunks / raw_docs / vectors 完整迁移到 `project_default/` 目录
3. 标记迁移完成，删除旧 `kb/chunks.json` 的临时标记（保留旧数据作为回退）

### 7.2 回退策略

- 旧 `kb/` 目录数据不会立即删除，仅标记为已迁移
- 如新版本启动异常，可手动移走 `kb/projects.json` 恢复旧版行为

---

## 8. 边界场景处理

| 场景 | 处理方式 |
|------|---------|
| 上传已存在文档（同名同hash） | 自动覆盖旧文档及其向量，保留备注和文件夹归属 |
| 上传同名但不同内容 | 视为新文档（hash不同），文件名为 "xxx (1).ext" |
| 删除文件夹时内部有文档 | 文档移出到根目录（folder_id = null），不删除文档 |
| 切换模型时检索 | 旧模型服务到重向量化完成，原子切换 |
| 向量化失败 | 标记文档 status = "failed"，提供重试按钮 |
| 备份文件损坏 | 恢复时校验 zip 完整性，提示重新备份 |
| 全局搜索无结果 | 提示"未找到相关内容"，建议扩大范围 |
