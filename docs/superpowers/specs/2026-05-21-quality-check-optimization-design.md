# 配置表文档质检优化设计

## 概述

在文档列表右键菜单"文档质检"功能中，增加弹窗让用户可选择上传系统策划案（参考文档）和填写配置表描述，使 AI 质检更加精准。质检结果仍展示在程序主界面右下角的"质检结果"区域。

## 变更清单

### 1. 新增 `QualityCheckDialog.vue`

位置：`src/components/dialogs/QualityCheckDialog.vue`

组件结构：
- `defineModel('visible')` 控制显示
- Props: 无（独立弹窗）
- Emits: `submit` — 携带 `{ referenceContent: string, configDescription: string }`
- 内部状态：
  - `uploadedFile: { name: string, content: string } | null` — 上传的系统策划案
  - `configDescription: string` — 配置表描述输入

UI 布局：
- 标题："配置表文档质检"
- 文件上传区：拖拽或点击上传 .docx/.txt 文件，显示文件名，可移除
- 文本输入区：textarea，placeholder "可选，描述该配置表的用途、设计思路等..."
- 底部按钮：取消 / 确定质检

### 2. 修改 `HomePage.vue`

右键菜单流程变更：
- `handleDocCommand('qualityCheck', doc)` → 打开 `QualityCheckDialog` 弹窗
- 弹窗确认后 → 调用 `ai.runQualityCheck(content, systemPrompt, referenceContent, configDescription)`
- 将额外上下文拼入 prompt，使 AI 质检更有针对性

新增状态和模板：
- `showQualityCheckDialog: ref(false)` — 控制弹窗显示
- 引入 `QualityCheckDialog` 组件并绑定

### 3. 修改 `useAI.ts`

`runQualityCheck` 方法签名扩展：
- 新增可选参数 `referenceContent?: string` 和 `configDescription?: string`
- 调用 API 时传入新字段

### 4. 修改后端 `api/routers/ai.py` 和 `api/ai_service.py`

API 扩展：
- `POST /api/ai/quality-check` 新增可选请求体字段：
  - `reference_content: str` — 系统策划案文本内容
  - `config_description: str` — 配置表描述

AI 服务 `quality_check` 方法扩展：
- 如果有 `reference_content`：将参考文档内容作为上下文注入 prompt，要求 AI 结合参考文档的设定和规范进行质检
- 如果有 `config_description`：在 prompt 中加入配置表描述信息，让 AI 理解该配置表的业务背景
- 如果两者都未提供：行为与现有完全一致（向后兼容）

### 5. 文档解析

上传的 .docx 文件使用 `python-docx` 解析为纯文本（后端已有该依赖）。
上传时前端将文件内容发送到临时解析接口，或直接在前端读取 .txt 内容，.docx 由后端解析。

简化方案：前端只接受 .txt 文件，或使用已有的 `document_parser.py` 解析上传文档。

## 数据流

```
右键文档 → 质检 → 显示 QualityCheckDialog
  └─ 用户可选上传策划案 + 输入描述
  └─ 点击确定 →
     POST /api/ai/quality-check {
       content: docText,
       reference_content: uploadedDocText,
       config_description: inputText,
       system_prompt: ...
     }
  └─ 返回结果 → aiResult.value = text → 右下角质检结果面板展示
```

## 向后兼容

所有新增字段均为可选。不传额外参数时，行为与当前版本完全一致。
