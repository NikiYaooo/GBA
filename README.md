# 游戏策划AI文档助手

> 一款面向游戏策划人员的桌面端 AI 文档辅助工具。集成文档管理、AI 智能仿写、质检、知识库检索增强、Excel 表格编辑等能力，帮助策划人员高效撰写和管理策划案。

---

## 目录

- [快速开始](#快速开始)
- [技术架构](#技术架构)
- [功能详解](#功能详解)
- [API 参考](#api-参考)
- [开发指南](#开发指南)
- [数据存储](#数据存储)
- [常见问题](#常见问题)

---

## 快速开始

### 下载使用

从 [release12/](file:///e:/game_builder/release12/) 目录下载最新的 `游戏策划AI文档助手 x.x.x.exe`，双击运行即可。

### 环境要求

- Windows 7+
- Python 3.10+（用于后端服务）
- 建议 8GB 以上内存（AI 功能可能需加载本地模型）

### 首次启动

1. 双击 exe 启动应用
2. 左下角状态灯变为绿色后，表示后端服务已连接
3. 前往左下角 **设置 → AI 模型配置** 填写 API Key（至少配置一个模型）
4. 开始使用

---

## 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                    Electron Shell                        │
│  ┌──────────────────┐       ┌─────────────────────────┐ │
│  │  前端 (Renderer)   │       │  后端 (Python FastAPI)   │ │
│  │  Vue 3 + Tiptap   │ HTTP  │  FastAPI + Uvicorn      │ │
│  │  Element Plus     │◄────►│  KnowledgeBase (RAG)    │ │
│  │  Axios            │       │  AIService (多模型)      │ │
│  └──────────────────┘       │  DocumentParser         │ │
│                            └─────────────────────────┘ │
│         IPC Bridge (electronAPI)                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │  main.ts: 窗口管理、文件对话框、SVN、端口管理     │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 前端

- **Vue 3** + **TypeScript** 单页应用
- **Tiptap** 富文本编辑器（15+ 扩展）
- **Element Plus** UI 组件库
- **Tailwind CSS** 样式框架
- **Axios** HTTP 客户端
- **Vite** 构建工具

### 后端

- **Python 3.10+** + **FastAPI** + **Uvicorn**
- 默认监听 `127.0.0.1:8000`，端口可由 `GB_PORT` 环境变量覆盖
- CORS 全开放

### 通信方式

| 方式 | 用途 | 实现 |
|------|------|------|
| HTTP | 前端 ↔ 后端数据交互 | Axios → FastAPI |
| IPC | 前端 ↔ Electron 主进程 | `window.electronAPI` → ipcMain.handle |

---

## 功能详解

### 1. 文档管理

#### 文档分类系统

分为四个分类标签页：

| 分类 | 说明 | 典型用途 |
|------|------|----------|
| **文档库** (doc) | 正式文档 | 策划案、设计文档等 Word 文档 |
| **仿写库** (imitation) | AI 生成文档 | 智能仿写/PRD 产出的文档 |
| **配置表** (excel) | 表格数据 | 数值配置、Excel 表格 |
| **草稿** (draft) | 未完成的文档 | 编辑中未归类的文档 |

#### 支持的文件格式

| 格式 | 上传 | 编辑 | 导出 |
|------|------|------|------|
| .docx | ✅ | ✅ (富文本) | ✅ (.docx) |
| .doc | ✅ | ✅ (富文本) | ✅ (.docx) |
| .md | ✅ | ✅ (富文本) | ✅ (.docx) |
| .txt | ✅ | ✅ (富文本) | ✅ (.docx) |
| .xlsx | ✅ | ✅ (表格编辑) | ✅ (.xlsx) |
| .xls | ✅ | ✅ (表格编辑) | ✅ (.xlsx) |

#### 文档操作

- **上传**：拖拽文件到编辑区，或点击左上角上传按钮
- **右键菜单**：右击文档 → 另存为、文档质检、重命名、删除
- **搜索过滤**：右上角搜索框按名称过滤
- **自动保存**：编辑后 1.5 秒自动保存

#### 新建草稿

点击「+ 新建草稿」可选择两种类型：

- **文档 (.docx)**：使用富文本编辑器，保存后归入文档库
- **表格 (.xlsx)**：使用 Excel 编辑器，保存后归入配置表

草稿只有点击右上角「保存到分类」按钮后才会归入正式分类。

### 2. AI 功能

#### 智能仿写 / 智能 PRD

输入需求描述，AI 自动生成完整策划案。

**流程**：
1. 输入需求描述（必填）
2. 可选上传脑图/思维导图辅助
3. AI 首轮生成（RAG 增强，参考知识库同类文档）
4. 自动质检反馈
5. 根据质检反馈优化文档
6. 创建文档保存到仿写库

**支持上传的脑图格式**：xmind, mind, xmind, mind, mmap, mm, md

#### 文档质检

对文档内容进行 AI 质量检测。

- 可自定义质检角色（策划、开发、设计、测试等）
- 每个角色可配置专属质检提示词
- 检查维度：逻辑矛盾、信息缺失、边界遗漏、文案模糊、落地性、规范问题

#### 逻辑补完

对草稿/半成品文档，AI 自动补全缺失的章节和边界逻辑。

- 背景、目标、流程、规则、奖励、限制、异常等标准章节
- 边界场景、容错逻辑、互斥规则
- 不篡改原有核心需求

#### 迭代修改

对 AI 生成的结果进行多轮迭代优化，输入新的需求或修改意见继续生成。

#### RAG 增强

所有 AI 功能均可结合本地知识库进行检索增强生成，让 AI 参考同类型文档的格式和风格。

#### 支持的 AI 模型

| 模型 | 类型 | 需要 API Key |
|------|------|-------------|
| DeepSeek | 云端 | ✅ |
| 豆包 (火山引擎) | 云端 | ✅ |
| GPT-4o | 云端 | ✅ |
| Gemini | 云端 | ✅ |
| Kimi (月之暗面) | 云端 | ✅ |
| GLM (智谱) | 云端 | ✅ |
| Ollama (本地) | 本地 | ❌ |

### 3. 知识库 (RAG)

本地知识库用于 AI 检索增强，提高生成内容的准确性。

#### 工作流程

```
用户上传文档 → 自动解析 → jieba 中文分词
  → 按配置大小切块（默认 512 tokens，10% 重叠）
  → 向量化（sentence-transformers 或 hashing 回退）
  → 存储到本地磁盘
```

#### 检索流程

```
用户查询 → 向量语义检索 (余弦相似度)
  + BM25 关键词检索 (jieba 分词)
  → RRF 融合排序 → 返回 TopK 结果
```

#### 知识库管理

- 支持格式：docx、md、txt
- 拖拽或点击上传
- 查看入库文档列表（文件名、类型、块数、大小、时间）
- 删除单个文档或清空全部
- **向量块大小可调**（100-500 字符，通过知识库管理界面调整）

### 4. Excel 表格编辑

#### 支持功能

- **多 Sheet 标签**：切换不同工作表
- **行号列号**：左侧灰色行号，顶部灰色列字母（A B C...）
- **单元格编辑**：点击直接编辑，Enter 完成
- **公式保留**：原始公式以蓝色显示，鼠标悬停查看公式原文
- **单元格填充色**：hover 单元格显示颜色选择器
- **新增行列**：一键添加行或列
- **另存为**：编辑后保存为 .xlsx 文件

### 5. 快捷工具

#### SVN 更新

配置多个 SVN 工作目录路径，一键更新。

支持两种方式：
- **TortoiseSVN**（推荐）：配置 TortoiseProc.exe 路径后，使用 GUI 更新
- **原生 svn 命令行**：未配置 TortoiseSVN 时自动回退

**更新成功后自动打开文件夹**。

#### 快捷导航

配置常用文件夹路径或网址，一键打开。

### 6. 设置

#### 通用设置

- **开机自动启动**：应用随系统自启
- **TortoiseSVN 路径**：TortoiseSVN 程序的完整路径

#### AI 模型配置

为每个云端模型配置 API Key 和 Model ID，支持「测试连接」验证配置有效性。

#### 职业角色管理

管理不同职业（策划、开发、设计、测试等）的质检角色和仿写 Prompt。

- 每个职业可添加多个自定义质检角色
- 每个职业可配置多个仿写 Prompt 模板
- 支持恢复默认 Prompt
- 质检和仿写时可选择不同角色/Prompt

---

## API 参考

### 文档 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 健康检查 |
| POST | `/api/documents/upload` | 上传文档（二进制流） |
| GET | `/api/documents` | 获取文档列表 |
| POST | `/api/documents/create` | 创建文档记录 |
| POST | `/api/documents/generate-file` | 生成 docx/xlsx 文件 |
| GET | `/api/documents/file/{doc_id}` | 获取原始文件 |
| GET | `/api/documents/{doc_id}` | 获取单个文档 |
| DELETE | `/api/documents/{doc_id}` | 删除文档 |
| PUT | `/api/documents/{doc_id}` | 更新文档 |

### AI API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/ai/quality-check` | 文档质检 |
| POST | `/api/ai/imitate` | 智能仿写 |
| POST | `/api/ai/complete-logic` | 逻辑补完 |
| GET | `/api/models/available` | 获取可用模型列表 |

### 知识库 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/kb/upload` | 上传文档到知识库 |
| GET | `/api/kb/stats` | 知识库统计 |
| POST | `/api/kb/chunk-size` | 设置向量块大小 |
| DELETE | `/api/kb/document/{file_hash}` | 删除知识库文档 |
| POST | `/api/kb/clear` | 清空知识库 |

### 配置 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/config` | 获取应用配置 |
| POST | `/api/config` | 保存应用配置 |
| GET | `/api/tools/config` | 获取快捷工具配置 |
| PUT | `/api/tools/config` | 保存快捷工具配置 |

### Excel API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/excel/parse` | 解析 Excel 文件 |
| POST | `/api/excel/save` | 保存 Excel 文件 |

### Prompt 管理 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/prompts/professions` | 获取职业列表 |
| GET | `/api/prompts/professions/{id}` | 获取职业下的质检角色 |
| POST | `/api/prompts/roles` | 新增/更新质检角色 |
| DELETE | `/api/prompts/roles/{id}` | 删除质检角色 |
| POST | `/api/prompts/init-defaults` | 重置默认提示词 |
| PUT | `/api/prompts/profession/{id}` | 更新职业仿写 Prompt |
| PUT | `/api/prompts/profession/{id}/add-prompt` | 新增仿写 Prompt |
| DELETE | `/api/prompts/profession/{id}/prompt/{id}` | 删除仿写 Prompt |

### 其他 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/mindmap/parse` | 解析脑图文件 |

### Electron IPC

| 通道名 | 参数 | 说明 |
|--------|------|------|
| `toggle-auto-start` | `enable: boolean` | 切换开机自启 |
| `get-auto-start-status` | 无 | 获取开机自启状态 |
| `show-item-in-folder` | `filePath: string` | 在资源管理器中显示文件 |
| `save-file-as` | `content, defaultName` | 弹出保存对话框 |
| `select-local-image` | 无 | 选择本地图片 |
| `test-ai-model` | `modelName, apiKey, modelId` | 测试 AI 模型连通性 |
| `get-backend-base-url` | 无 | 获取后端地址 |
| `run-svn-update` | `folderPath, tortoisePath?` | SVN 更新 |
| `open-path` | `targetPath: string` | 打开路径/网址 |
| `select-folder` | 无 | 选择文件夹 |
| `restart-backend` | 无 | 重启后端 |

---

## 开发指南

### 环境搭建

```bash
# 克隆项目
cd game_builder

# 安装前端依赖
npm install

# 创建 Python 虚拟环境并安装后端依赖
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 启动开发环境
npm run dev        # 启动 Vite 开发服务器
python api/main.py # 单独启动 Python 后端（另一终端）
```

### 构建打包

```bash
npm run electron:build
```

构建产物输出到 `release12/` 目录。

### 项目结构

```
game_builder/
├── api/                  # Python 后端
│   ├── main.py           # FastAPI 入口 + 所有路由
│   ├── ai_service.py     # AI 模型调用
│   ├── knowledge_base.py # 知识库（向量检索+BM25）
│   └── document_parser.py# 文档解析
├── electron/             # Electron 主进程
│   ├── main.ts           # 主进程代码
│   └── preload.ts        # 预加载脚本
├── src/                  # Vue 前端
│   ├── pages/
│   │   └── HomePage.vue  # 主页面（所有功能）
│   ├── App.vue
│   └── main.ts
├── dist/                 # 构建输出
├── dist-electron/        # Electron 构建输出
├── release12/            # 打包产物
├── package.json
├── vite.config.ts
└── README.md
```

### 技术栈

**前端**：Vue 3 + TypeScript + Tiptap + Element Plus + Tailwind CSS + Vite

**后端**：Python 3.10+ + FastAPI + Uvicorn + python-docx + openpyxl

**AI/向量**：sentence-transformers + jieba + rank-bm25 + scikit-learn + httpx

**桌面壳**：Electron 27 + electron-builder

---

## 数据存储

### 存储位置

用户数据默认存储在 `%APPDATA%\GameBuilderAIHelper\`（Windows）
可通过 `GB_DATA_DIR` 环境变量覆盖。

### 文件结构

```
GameBuilderAIHelper/
├── documents.json   # 文档库数据
├── config.json      # 应用配置（模型密钥、SVN 配置、设置）
├── prompts.json     # 质检角色和仿写 Prompt
├── uploads/         # 上传的原始文件
├── kb/              # 知识库
│   ├── chunks.json  # 文本块数据
│   ├── vectors.npy  # 向量数据
│   └── hf_cache/    # HuggingFace 模型缓存
└── logs/            # 日志
    ├── api.log      # API 运行日志
    ├── python.log   # Python 进程日志
    └── main.log     # Electron 主进程日志
```

---

## 常见问题

### 后端服务连接失败

1. 重启应用
2. 检查 8000 端口是否被占用：`netstat -ano | findstr :8000`
3. 查看日志文件 `%APPDATA%\GameBuilderAIHelper\logs\python.log` 排查错误

### AI 模型调用失败

1. 前往 **设置 → AI 模型配置** 检查 API Key 是否正确
2. 点击「测试连接」验证
3. 检查网络连通性

### 文档保存为 Word 打不开

确保使用「右键 → 另存为」功能保存，后端会自动生成真正的 `.docx` 文件。如果生成失败会显示具体错误信息。

### SVN 更新失败

1. 如果没有安装 TortoiseSVN，确保安装了 `svn` 命令行工具
2. 在 **设置 → 通用设置** 中配置 TortoiseSVN 路径
3. 确认文件夹路径是有效的 SVN 工作副本

### 知识库相关

- **向量块大小**：知识库管理界面可调整（100-500），修改后新入库的文档按新大小切块
- **显示 "unknown" 类型**：之前版本的 bug，1.13.3+ 已修复为显示实际文件扩展名
