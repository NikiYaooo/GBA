<!-- superpowers-zh:begin (do not edit between these markers) -->
# Superpowers-ZH 中文增强版

本项目已安装 superpowers-zh 技能框架（20 个 skills）。

## 核心规则

1. **收到任务时，先检查是否有匹配的 skill** — 哪怕只有 1% 的可能性也要检查
2. **设计先于编码** — 收到功能需求时，先用 brainstorming skill 做需求分析
3. **测试先于实现** — 写代码前先写测试（TDD）
4. **验证先于完成** — 声称完成前必须运行验证命令

## 可用 Skills

Skills 位于 `.claude/skills/` 目录，每个 skill 有独立的 `SKILL.md` 文件。

- **brainstorming**: 在任何创造性工作之前必须使用此技能——创建功能、构建组件、添加功能或修改行为。在实现之前先探索用户意图、需求和设计。
- **chinese-code-review**: 中文代码审查规范——在保持专业严谨的同时，用符合国内团队文化的方式给出有效反馈
- **chinese-commit-conventions**: 中文 Git 提交规范 — 适配国内团队的 commit message 规范和 changelog 自动化
- **chinese-documentation**: 中文技术文档写作规范——排版、术语、结构一步到位，告别机翻味
- **chinese-git-workflow**: 适配国内 Git 平台和团队习惯的工作流规范——Gitee、Coding、极狐 GitLab、CNB 全覆盖
- **dispatching-parallel-agents**: 当面对 2 个以上可以独立进行、无共享状态或顺序依赖的任务时使用
- **executing-plans**: 当你有一份书面实现计划需要在单独的会话中执行，并设有审查检查点时使用
- **finishing-a-development-branch**: 当实现完成、所有测试通过、需要决定如何集成工作时使用——通过提供合并、PR 或清理等结构化选项来引导开发工作的收尾
- **mcp-builder**: MCP 服务器构建方法论 — 系统化构建生产级 MCP 工具，让 AI 助手连接外部能力
- **receiving-code-review**: 收到代码审查反馈后、实施建议之前使用，尤其当反馈不明确或技术上有疑问时——需要技术严谨性和验证，而非敷衍附和或盲目执行
- **requesting-code-review**: 完成任务、实现重要功能或合并前使用，用于验证工作成果是否符合要求
- **subagent-driven-development**: 当在当前会话中执行包含独立任务的实现计划时使用
- **systematic-debugging**: 遇到任何 bug、测试失败或异常行为时使用，在提出修复方案之前执行
- **test-driven-development**: 在实现任何功能或修复 bug 时使用，在编写实现代码之前
- **using-git-worktrees**: 当需要开始与当前工作区隔离的功能开发或执行实现计划之前使用——创建具有智能目录选择和安全验证的隔离 git 工作树
- **using-superpowers**: 在开始任何对话时使用——确立如何查找和使用技能，要求在任何响应（包括澄清性问题）之前调用 Skill 工具
- **verification-before-completion**: 在宣称工作完成、已修复或测试通过之前使用，在提交或创建 PR 之前——必须运行验证命令并确认输出后才能声称成功；始终用证据支撑断言
- **workflow-runner**: 在 Claude Code / OpenClaw / Cursor 中直接运行 agency-orchestrator YAML 工作流——无需 API key，使用当前会话的 LLM 作为执行引擎。当用户提供 .yaml 工作流文件或要求多角色协作完成任务时触发。
- **writing-plans**: 当你有规格说明或需求用于多步骤任务时使用，在动手写代码之前
- **writing-skills**: 当创建新技能、编辑现有技能或在部署前验证技能是否有效时使用

## 如何使用

当任务匹配某个 skill 时，使用 `Skill` 工具加载对应 skill 并严格遵循其流程。绝不要用 Read 工具读取 SKILL.md 文件。

如果你认为哪怕只有 1% 的可能性某个 skill 适用于你正在做的事情，你必须调用该 skill 检查。
<!-- superpowers-zh:end -->

## 全局规则

以下规则对本项目的所有 Claude Code 对话生效：

1. **版本号规则** — 版本号从 `package.json` 的 `version` 字段读取。格式为 `大版本.小版本.bug修复`（例如 `2.6.12`）。每次开发完成时迭代版本号。
2. **自动编译** — 每次开发完成后自动执行 `npm run build`（vue-tsc → vite → electron-builder），确保构建通过。
3. **自动推送** — 每个版本开发完成、编译通过后，自动将代码 push 到 GitHub (`git@github.com:NikiYaooo/GBA.git`)。
4. **中文输出** — 每次对话都用中文回答，权限询问也翻译为中文。

# Codebase Overview

## Architecture

Electron desktop app with Vue 3 frontend (renderer) communicating via HTTP to a Python FastAPI backend (spawned as child process):

```
Electron main.ts                       Python backend (api/main.py)
  └─ spawns Python on port 8000           ├─ FastAPI + Uvicorn + SwitchMiddleware
  └─ IPC handlers:                        ├─ routers/ (12 modules)
       file dialogs, SVN,                    image_gen.py  — 豆包Seedream生图/修改
       auto-start, port mgmt                 knowledge_base.py — KB CRUD
       backend lifecycle                     ai.py — 智能仿写/质检/逻辑补完
                                             documents.py — 文档CRUD
Vue 3 SPA (src/pages/HomePage.vue)           config.py, excel.py, prompts.py
  ├─ 17 dialogs in components/dialogs/       image_library.py, reminders.py
  ├─ 10 composables (useAI, useKnowledgeBase,  mindmap.py, template.py
  │   useDocuments, useImageLibrary, ...)   ├─ ai_service.py (多模型调用)
  ├─ Axios → apiUrl() → FastAPI             ├─ kb_project.py (RAG引擎)
  └─ electronAPI (IPC bridge)               ├─ knowledge_base.py (多项目)
  └─ switch interceptor (403 / X-Switch-Status) ├─ document_parser.py (docx→HTML)
                                            └─ project_profile.py (项目画像)
                                            └─ switch_checker.py (远程开关)
```

## Key Directories

| Directory | Purpose |
|---|---|
| `api/` | Python FastAPI backend — main.py (entry), routers/ (12 routers), service modules, switch_checker |
| `api/routers/` | API 路由模块 — image_gen.py, knowledge_base.py, ai.py, documents.py, 等 |
| `src/` | Vue 3 frontend — SPA in pages/, dialogs in components/dialogs/ |
| `src/composables/` | Vue composables — useKnowledgeBase.ts, useAI.ts, useDocuments.ts, 等 |
| `electron/` | Electron main.ts (Python lifecycle, IPC handlers) + preload.ts |
| `src/types/index.ts` | TypeScript 类型定义（共享给所有组件和composables） |
| `src/utils/api.ts` | API 工具 — apiUrl(), getErrMsg(), scanPorts() |
| `tests/` | Python pytest 测试 (44 tests: KB项目 + AI服务 + 图片编辑) |
| `docs/superpowers/` | 设计规格文档 (specs/) 和实现计划 (plans/) |

## Key Commands

| Command | Description |
|---|---|
| `npm run check` | TypeScript 类型检查 (vue-tsc -b) |
| `npm run build` | 完整构建: vue-tsc → vite → electron-builder → release28/ |
| `npx vite build` | 仅 Vite 构建（跳过类型检查） |
| `npm run dev` | 开发模式 — Vite HMR + Electron |
| `.venv\Scripts\python.exe -m pytest tests/ -v` | 运行 Python 测试（44个） |
| `.venv\Scripts\python.exe -m pytest tests/test_kb_project.py::test_name -v` | 单个测试 |
| `.venv\Scripts\python.exe api/main.py` | 单独启动 Python 后端（端口8000） |

## Architecture Details

### 后端路由架构
- `api/main.py` 初始化 FastAPI app、知识库、AI 服务，然后导入并注册所有 router 模块
- 每个 router 独立处理一个 API 域，通过 `router.ai_service` 全局引用共享 AI 服务实例
- 知识库多项目架构: `KnowledgeBase` (管理器) → `KBProject` (单个项目引擎，含向量检索+BM25)

### 前端 Composables 模式
- 每个功能域对应一个 composable，返回响应式状态和方法
- HomePage.vue 导入所有 composable 实例，模板中通过 `kb.xxx`、`ai.xxx`、`docs.xxx` 等方式调用
- `useExcel.ts` — 自定义表格编辑引擎：公式计算（calcFormula + 5遍收敛重算）、选区管理（多选/Shift扩展）、格式操作（加粗/字体/颜色/对齐）、撤销栈（15层深）、复制粘贴（公式引用偏移）、Sheet切换、行列操作。Excel 模式工具栏通过上下文分发调用此 composable
- `useKnowledgeBase.ts` — 管理 KB 对话框状态：项目/文件夹/文档CRUD、搜索、备份、词库、切片配置
- `useAI.ts` — 管理智能仿写/质检/逻辑补完 + PRD 多轮迭代 (`iterationHistory`, `runIteration`)
- `useDocuments.ts` — 文档CRUD、上传（含扩展名自动分类、上传后立即插入列表）、筛选搜索
- `useTools.ts` — 管理工具栏组件状态（图片工具、模板、SVN、提醒等）
- `useTheme.ts` — 界面亮暗主题切换

### Electron IPC 通道
- `window.electronAPI` 通过 preload.ts 暴露
- 关键通道: `toggle-auto-start`, `show-item-in-folder`, `save-file-as`, `select-local-image`, `run-svn-update`, `open-path`, `select-folder`, `restart-backend`, `test-ai-model`

### 图片生成 (image_gen.py)
- 支持三种模式: 文生图 (generate)、图片修改 (edit with mask) + 原生编辑 (_native_edit_ark)
- 模型: 豆包 Seedream (ARK API), Qwen-Image 2 (DashScope), GPT-Image 2 (OpenAI)
- 参考图限制: 最多 4 张，data URI 格式需去除前缀后传给 ARK API
- 前端画板: Canvas 2D 遮罩绘制 (画笔/橡皮擦)

### 远程开关 (switch_checker.py)
- 启动时和执行每个功能前/后检查 `https://github.com/NikiYaooo/GBA-switch/blob/main/switch.txt`
- 后端 SwitchMiddleware: 403 阻断 + X-Switch-Status 响应头
- Electron main.ts: `checkSwitch()` IPC guard 拦截功能调用
- 前端 Axios 拦截器: 检测 403 和 X-Switch-Status: off，提示后退出

### 项目画像 (project_profile.py)
- 存储游戏项目的核心设定（游戏名、类型、世界观、系统、数值等）
- AI 生成时作为约束注入提示词，防止自创设定

### 数据存储
- 所有运行时数据存储在 `%APPDATA%\GameBuilderAIHelper\`（或 `GB_DATA_DIR` 覆盖）
- 存储为 JSON 文件 + numpy 向量 (.npy)
- 构建时 `api/` 目录打包到 `resources/api/` 中

## Build Details

- `electron-builder` 配置在 `package.json` → `build` 字段
- 输出: `release28/游戏策划AI文档助手.exe` (Win portable，~300MB)
- 打包内容: `dist/`, `dist-electron/`, `api/` (resources/api/)
- Electron 27.3.11, 需安装 `python-3.10+` 和 `pip install -r requirements.txt`

## Testing Notes

- **只有 Python 后端测试**，无前端测试
- 测试文件: `tests/test_kb_project.py` (KBProject), `tests/test_ai_service.py` (AI服务), `tests/test_image_edit.py` (图片编辑遮罩)
- 共 44 个测试
- KBProject 测试使用 `tempfile.mkdtemp` 创建临时项目目录，测试后 `shutil.rmtree` 清理
- 测试需要从项目根目录运行（Python path 包含 api/ 目录）
