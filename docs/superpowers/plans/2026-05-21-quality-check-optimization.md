# 配置表文档质检优化 实现计划

> **面向 AI 代理的工作者：** 此计划在单次会话中执行。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在文档右键菜单"文档质检"和执行质检之间增加弹窗，支持上传系统策划案和输入配置表描述，使质检更精准。

**架构：** 前端新增 QualityCheckDialog.vue 弹窗组件，修改 HomePage.vue 右键菜单流程，修改 useAI.ts 传递额外参数；后端扩展 quality-check API 接受 reference_content 和 config_description 字段。

**技术栈：** Vue 3 + Element Plus 弹窗、Axios、FastAPI、python-docx

---

### 任务 1：新增 QualityCheckDialog.vue 组件

**文件：**
- 创建：`src/components/dialogs/QualityCheckDialog.vue`

- [x] **步骤 1：创建 QualityCheckDialog.vue**

参照 ImitateDialog.vue 的 pattern，创建质检弹窗组件，包含：
- 文件上传区（支持 .txt/.docx）
- 文本输入区（配置表描述）
- 取消/确定按钮

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Upload, FileText, X } from 'lucide-vue-next'

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  submit: [referenceContent: string, configDescription: string]
}>()

interface UploadedFile {
  name: string
  content: string
}

const uploadedFile = ref<UploadedFile | null>(null)
const configDescription = ref('')

const fileToText = async (file: File): Promise<string> => {
  if (file.name.endsWith('.txt')) {
    return await file.text()
  }
  // .docx 文件通过后端解析
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch('/api/parse-docx', { method: 'POST', body: formData })
  if (!res.ok) throw new Error('解析失败')
  const data = await res.json()
  return data.text
}

const handleFileUpload = () => {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.txt,.docx'
  input.onchange = async (e: any) => {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      const content = await fileToText(file)
      uploadedFile.value = { name: file.name, content }
    } catch {
      ElMessage.error('文件解析失败')
    }
  }
  input.click()
}

const removeFile = () => {
  uploadedFile.value = null
}

const handleSubmit = () => {
  visible.value = false
  emit('submit', uploadedFile.value?.content || '', configDescription.value)
  // 重置状态
  uploadedFile.value = null
  configDescription.value = ''
}
</script>

<template>
  <el-dialog :model-value="visible" @update:model-value="visible = $event" title="配置表文档质检" width="480px" :close-on-click-modal="false" destroy-on-close>
    <div class="space-y-4">
      <!-- 系统策划案上传 -->
      <div>
        <label class="text-sm font-medium block mb-1">上传系统策划案（可选）</label>
        <div v-if="!uploadedFile" class="border-2 border-dashed border-app-light rounded-lg p-6 text-center cursor-pointer hover:border-blue-400 transition-colors" @click="handleFileUpload">
          <Upload class="w-6 h-6 mx-auto mb-2 text-app-muted" />
          <p class="text-sm text-app-muted">点击上传 .txt 或 .docx 文件</p>
        </div>
        <div v-else class="flex items-center gap-2 p-3 bg-surface border border-app rounded-lg">
          <FileText class="w-4 h-4 text-blue-500 shrink-0" />
          <span class="text-sm truncate flex-1">{{ uploadedFile.name }}</span>
          <button class="text-red-400 hover:text-red-600" @click="removeFile"><X class="w-4 h-4" /></button>
        </div>
      </div>
      <!-- 配置表描述 -->
      <div>
        <label class="text-sm font-medium block mb-1">配置表介绍（可选）</label>
        <textarea
          v-model="configDescription"
          class="w-full h-24 px-3 py-2 text-sm border border-app rounded-lg bg-surface resize-none outline-none focus:border-blue-400 transition-colors"
          placeholder="描述该配置表的用途、设计思路、涉及的数值类型等..."
        ></textarea>
      </div>
    </div>
    <template #footer>
      <div class="flex justify-end gap-2">
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定质检</el-button>
      </div>
    </template>
  </el-dialog>
</template>
```

- [x] **步骤 2：Commit**

```bash
git add src/components/dialogs/QualityCheckDialog.vue
git commit -m "feat: 新增质检弹窗组件 QualityCheckDialog"
```

### 任务 2：修改 useAI.ts — runQualityCheck 支持额外参数

**文件：**
- 修改：`src/composables/useAI.ts`

- [x] **步骤 1：修改 runQualityCheck 方法签名和 API 调用**

```typescript
  const runQualityCheck = async (content: string, systemPrompt?: string, referenceContent?: string, configDescription?: string): Promise<string | null> => {
    const r = await axios.post<ApiResponse<string>>(apiUrl('/api/ai/quality-check'), {
      model: activeModel.value, content, system_prompt: systemPrompt || '',
      reference_content: referenceContent || '',
      config_description: configDescription || ''
    })
    if (r.data.success) return r.data.data || null
    return null
  }
```

- [x] **步骤 2：Commit**

```bash
git add src/composables/useAI.ts
git commit -m "feat: runQualityCheck 支持 referenceContent 和 configDescription 参数"
```

### 任务 3：修改后端 API — 扩展 quality-check 接口

**文件：**
- 修改：`api/routers/ai.py`（第 11-24 行）
- 修改：`api/ai_service.py`（第 267-274 行）

- [x] **步骤 1：修改 api/routers/ai.py — 接收新字段**

```python
@router.post("/quality-check")
async def quality_check(payload: dict = Body(...)):
    model = payload.get("model", "DeepSeek")
    content = payload.get("content", "")
    system_prompt = payload.get("system_prompt", "")
    reference_content = payload.get("reference_content", "")
    config_description = payload.get("config_description", "")

    if not content:
        raise HTTPException(status_code=400, detail="内容不能为空")

    try:
        result = await get_ai_service().quality_check(
            model, content, system_prompt=system_prompt or None,
            reference_content=reference_content or None,
            config_description=config_description or None
        )
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "message": f"AI 服务调用失败: {str(e)}"}
```

- [x] **步骤 2：修改 api/ai_service.py — quality_check 方法扩展**

```python
    async def quality_check(self, model: str, doc_content: str, system_prompt: str = None,
                           reference_content: str = None, config_description: str = None) -> str:
        if not system_prompt:
            system_prompt = "你是一名资深游戏策划专家，请对用户提供的策划文档进行严格质检。检查逻辑矛盾、信息缺失、边界遗漏、文案模糊、落地性和规范问题。请输出：风险等级、问题原文、分析、修改建议。"
        
        messages = [{"role": "system", "content": system_prompt}]
        
        # 构建用户消息
        user_parts = []
        if reference_content:
            user_parts.append(f"【参考系统策划案】\n{reference_content}\n")
        if config_description:
            user_parts.append(f"【配置表说明】\n{config_description}\n")
        user_parts.append(f"【待质检文档内容】\n\n{doc_content}")
        
        messages.append({"role": "user", "content": "\n---\n".join(user_parts)})
        return await self._call_api(model, messages)
```

- [x] **步骤 3：添加 docx 解析路由（可选增强）**

如果前端需要解析 .docx 文件，在 `api/routers/ai.py` 中添加：

```python
@router.post("/parse-docx")
async def parse_docx(file: UploadFile = File(...)):
    if not file.filename.endswith('.docx'):
        raise HTTPException(status_code=400, detail="仅支持 .docx 文件")
    try:
        content = await file.read()
        import io
        from docx import Document
        doc = Document(io.BytesIO(content))
        text = "\n".join(p.text for p in doc.paragraphs)
        return {"text": text}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"解析失败: {str(e)}")
```

- [ ] **步骤 4：Commit**

```bash
git add api/routers/ai.py api/ai_service.py
git commit -m "feat: quality-check API 支持参考文档和配置表描述上下文"
```

### 任务 4：修改 HomePage.vue — 右键菜单接入质检弹窗

**文件：**
- 修改：`src/pages/HomePage.vue`

- [x] **步骤 1：导入组件并添加状态**

在 import 区域添加：
```typescript
import QualityCheckDialog from '@/components/dialogs/QualityCheckDialog.vue'
```

在 data/ref 区域添加：
```typescript
const showQualityCheckDialog = ref(false)
// 临时存储右键点击时的文档
const pendingQCDoc = ref<DocRecord | null>(null)
```

- [x] **步骤 2：修改 handleDocCommand 中的 qualityCheck 分支**

将：
```typescript
  } else if (command === 'qualityCheck') {
    ai.aiResult.value = ''; ai.isProcessing.value = true
    const text = tiptapEditor.value?.getText() || docs.currentDoc.value.content || ''
    const pro = prompts.professionsFull.value.find(p => p.id === prompts.selectedImitationProfession.value)
    const qcPrompt = pro?.qualityCheckPrompt || ''
    const result = await ai.runQualityCheck(text, qcPrompt)
    if (result) ai.aiResult.value = `【质检职业：${pro?.name || '默认'}】\n\n${result}`
    else ElMessage.error('质检失败')
    ai.isProcessing.value = false
  }
```

改为：
```typescript
  } else if (command === 'qualityCheck') {
    pendingQCDoc.value = doc
    showQualityCheckDialog.value = true
    return
  }
```

- [x] **步骤 3：添加弹窗确认回调方法**

在 `handleDocCommand` 附近添加：
```typescript
const handleQualityCheckSubmit = async (referenceContent: string, configDescription: string) => {
  const doc = pendingQCDoc.value
  if (!doc) return
  pendingQCDoc.value = null

  // 优先使用编辑器中的内容，其次使用文档存储的内容
  const text = tiptapEditor.value?.getText() || docs.currentDoc.value.content || ''
  // 如果当前选中的文档不是右键的那个，尝试获取该文档内容
  const targetContent = docs.currentDoc.value?.id === doc.id ? text : doc.content || text
  
  const pro = prompts.professionsFull.value.find(p => p.id === prompts.selectedImitationProfession.value)
  const qcPrompt = pro?.qualityCheckPrompt || ''

  ai.aiResult.value = ''
  ai.isProcessing.value = true
  
  // 构建显示标题
  let title = `【质检文档：${doc.name}】`
  if (referenceContent) title += `\n【参考文档：已上传】`
  if (configDescription) title += `\n【配置表说明：${configDescription.slice(0, 50)}${configDescription.length > 50 ? '...' : ''}】`
  
  const result = await ai.runQualityCheck(targetContent, qcPrompt, referenceContent, configDescription)
  if (result) {
    ai.aiResult.value = `${title}\n\n${result}`
    // 切换到质检结果 tab
    aiResultTab.value = 'result'
  } else {
    ElMessage.error('质检失败')
  }
  ai.isProcessing.value = false
}
```

- [x] **步骤 4：在模板中添加 QualityCheckDialog 组件**

在模板末尾（其他 dialog 附近）添加：
```vue
<QualityCheckDialog v-model:visible="showQualityCheckDialog" @submit="handleQualityCheckSubmit" />
```

- [ ] **步骤 5：Commit**

```bash
git add src/pages/HomePage.vue
git commit -m "feat: 质检右键菜单接入弹窗，支持上传参考文档和配置表描述"
```

### 任务 5：编译构建并输出

**文件：**
- 无代码变更

- [ ] **步骤 1：运行 TypeScript 类型检查**

运行：`npm run check`
预期：Type check 通过

- [ ] **步骤 2：完整构建**

运行：`npm run build`
预期：构建成功，输出到 `GBA/` 目录

- [ ] **步骤 3：验证输出文件**

运行：`ls "GBA/"`
预期：包含 exe 文件、setup_env.bat、requirements.txt 等
