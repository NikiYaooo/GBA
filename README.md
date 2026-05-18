# 游戏策划AI文档助手

> 一款面向游戏策划人员的桌面端 AI 文档辅助工具。集成文档管理、AI 智能仿写、质检、知识库检索增强(RAG)、Excel 表格编辑、AI 图片生成与修改等能力，帮助策划人员高效撰写和管理策划案。

**当前版本**: 2.6.10

---

## 目录

- [快速开始](#快速开始)
- [技术架构](#技术架构)
- [功能详解](#功能详解)
- [开发指南](#开发指南)
- [数据存储](#数据存储)
- [常见问题](#常见问题)

---

## 快速开始

### 下载使用

从 `release28/` 目录下载最新的 `游戏策划AI文档助手.exe`，双击运行即可。

### 环境要求

- Windows 10+
- 建议 8GB 以上内存
- 无需安装 Python（已内置于打包中）

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
│                            │  ImageGen (豆包Seedream)  │ │
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
- **Lucide Vue Next** 图标库
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

输入需求描述，AI 自动生成完整策划案。采用**五步增强流程**：

1. **多分类 RAG 检索** — 自动从知识库检索世界观、系统设定、数值规则、PRD 模板、UI 规范等分类，确保生成内容贴合项目
2. **知识约束检查** — 禁止 AI 自创世界观/职业/玩法/数值，必须基于知识库内容生成
3. **模板强制输出** — 参考上传的文档模板，严格保持格式一致
4. **自检 + 自动重写** — 生成后自动检查完整性、逻辑、数值合理性，不合格自动重写
5. **优化提示词** — 角色定位、Few-Shot 示例、输出约束等

**辅助输入**：
- 脑图/思维导图（xmind, mm, png, jpg, txt, md）
- 系统原型图（PNG 多张，支持 vision 的模型可看图理解需求）
- .docx 模板文件

#### 文档质检

对文档内容进行 AI 质量检测，支持自定义质检角色和提示词。
检查维度：逻辑矛盾、信息缺失、边界遗漏、文案模糊、落地性、规范问题。

#### 逻辑补完

对草稿/半成品文档，AI 自动补全缺失的章节和边界逻辑，不篡改原有核心需求。

#### AI 图片生成与修改

集成**豆包 Seedream** 图片生成模型，支持：
- **文生图**：输入描述生成图片
- **参考图生成**：上传参考图片（最多 4 张），AI 参考风格/构图生成
- **图片修改**：对已有图片进行修改编辑（包括 AI 增强 Crop-Edit）
- **图片库管理**：左侧图片列表，支持重命名、删除、另存为
- **画板编辑**：在图片上绘制遮罩，指定修改区域

#### 迭代修改

对 AI 生成的结果进行多轮迭代优化。

#### RAG 增强

所有 AI 功能均可结合本地知识库进行检索增强生成。

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

#### 多项目支持

支持创建多个知识库项目，每个项目独立管理文档和向量索引。

#### 工作流程

```
用户上传文档 → 自动解析 → jieba 中文分词
  → 按配置大小切块（100-500 字符，10% 重叠）
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
- 拖拽或点击上传（支持多文件批量上传）
- 文件夹分类管理
- 批量导入：扫描文件夹路径，批量选择文件导入
- 查看入库文档列表（文件名、块数、大小）
- 删除单个文档或清空全部
- 切片大小可配置（100-500 字符）
- 备份管理：创建和恢复知识库快照
- 自定义词库：添加分词词汇提高切分质量

### 4. Excel 表格编辑

- **多 Sheet 标签**：切换不同工作表
- **行号列号**：左侧灰色行号，顶部灰色列字母
- **单元格编辑**：点击直接编辑，Enter 完成
- **公式保留**：原始公式以蓝色显示，鼠标悬停查看公式原文
- **单元格填充色**：hover 显示颜色选择器
- **新增行列**：一键添加行或列
- **复制/粘贴单元格**
- **另存为**：编辑后保存为 .xlsx 文件

### 5. 快捷工具

#### SVN 更新

配置多个 SVN 工作目录路径，一键更新。
- **TortoiseSVN**：使用 GUI 更新
- **原生 svn 命令行**：自动回退

#### 快捷导航

配置常用文件夹路径或网址，一键打开。

### 6. 设置

- **通用设置**：开机自启、TortoiseSVN 路径
- **AI 模型配置**：为每个模型配置 API Key 和 Model ID（支持测试连接）
- **职业角色管理**：管理质检角色和仿写 Prompt 模板

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
npm run dev        # 启动 Vite 开发服务器 (端口 5173)
python api/main.py # 单独启动 Python 后端（另一终端，端口 8000）
```

### 构建打包

```bash
npm run build
```

构建流程：vue-tsc 类型检查 → Vite 构建 → electron-builder 打包。
产物输出到 `release28/` 目录。

### 项目结构

```
game_builder/
├── api/                    # Python 后端
│   ├── main.py             # FastAPI 入口
│   ├── ai_service.py       # AI 模型调用
│   ├── kb_project.py       # 知识库项目引擎（向量+BM25）
│   ├── knowledge_base.py   # 知识库管理器（多项目）
│   ├── document_parser.py  # 文档解析
│   └── routers/            # API 路由模块
│       ├── image_gen.py    # 图片生成 API
│       ├── knowledge_base.py # 知识库 API
│       └── template.py     # 文档模板 API
├── electron/               # Electron 主进程
│   ├── main.ts             # 主进程代码
│   └── preload.ts          # 预加载脚本
├── src/                    # Vue 前端
│   ├── pages/
│   │   └── HomePage.vue    # 主页面（SPA）
│   ├── components/
│   │   └── dialogs/        # 对话框组件
│   │       ├── ImageToolDialog.vue  # AI 图片工具
│   │       ├── KBDialog.vue         # 知识库管理
│   │       ├── KBBatchImportDialog.vue # 批量导入
│   │       ├── PromptDialog.vue     # 提示词管理
│   │       └── ...                   # 其他 12+ 对话框
│   ├── composables/        # Vue 组合式函数
│   │   ├── useKnowledgeBase.ts  # 知识库逻辑
│   │   ├── useImageLibrary.ts   # 图片库逻辑
│   │   └── ...
│   └── types/              # TypeScript 类型定义
├── tests/                  # Python 测试
├── docs/                   # 设计文档和计划
├── release28/              # 打包产物
├── package.json
└── vite.config.ts
```

### 技术栈

**前端**：Vue 3 + TypeScript + Tiptap + Element Plus + Lucide Vue Next + Vite

**后端**：Python 3.10+ + FastAPI + Uvicorn + python-docx + openpyxl

**AI/向量**：sentence-transformers + jieba + rank-bm25 + scikit-learn + httpx

**图片生成**：豆包 Seedream (ARK API) + Canvas 2D 画板

**桌面壳**：Electron 27 + electron-builder

---

## 数据存储

### 存储位置

用户数据默认存储在 `%APPDATA%\GameBuilderAIHelper\`（Windows）。
可通过 `GB_DATA_DIR` 环境变量覆盖。

### 文件结构

```
GameBuilderAIHelper/
├── documents.json   # 文档库数据
├── config.json      # 应用配置（模型密钥、SVN、设置）
├── prompts.json     # 质检角色和仿写 Prompt
├── image_library.json # 图片库记录
├── uploads/         # 上传的原始文件
├── images/          # 生成的图片文件
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

### 图片生成失败

- 检查豆包 Seedream 的 API Key 是否正确配置
- 参考图片最多支持 4 张
- 图片修改需要上传原图后使用

### 文档保存为 Word 打不开

确保使用「右键 → 另存为」功能保存，后端会自动生成真正的 `.docx` 文件。

### SVN 更新失败

1. 如未安装 TortoiseSVN，确保安装了 `svn` 命令行工具
2. 在 **设置 → 通用设置** 中配置 TortoiseSVN 路径
3. 确认文件夹路径是有效的 SVN 工作副本

### 知识库相关

- 每个项目独立管理文档和向量索引
- 切片大小（100-500）可在知识库管理界面调整
- 支持创建备份用于恢复
- 自定义词库可提高中文分词准确度
