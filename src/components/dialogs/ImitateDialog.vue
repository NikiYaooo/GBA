<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { apiUrl, getErrMsg } from '@/utils/api'

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  submit: [requirements: string, mindmapContent: string, templateContent: string, images: string[]]
}>()

const requirements = ref('')
const mindmapFileName = ref('')
let mindmapFile: File | null = null

// 原型图上传
const uploadedImages = ref<{ dataUri: string; name: string }[]>([])

const handleImageUpload = () => {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.png'
  input.multiple = true
  input.onchange = async (e: any) => {
    const files = e.target.files
    if (!files || files.length === 0) return
    for (const file of files) {
      if (file.size > 10 * 1024 * 1024) {
        ElMessage.warning(`"${file.name}" 超过 10MB 限制，已跳过`)
        continue
      }
      const dataUri = await fileToBase64(file)
      uploadedImages.value.push({ dataUri, name: file.name })
    }
  }
  input.click()
}

const removeImage = (index: number) => {
  uploadedImages.value.splice(index, 1)
}

const fileToBase64 = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

// 模板状态
const templateInfo = ref<{ exists: boolean; name?: string; id?: string }>({ exists: false })
const isTemplateLoading = ref(false)
const isTemplateUploading = ref(false)

const handleMindmapSelect = () => {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.xmind,.mm,.png,.jpg,.jpeg,.txt,.md'
  input.onchange = (e: any) => {
    if (e.target.files[0]) {
      mindmapFile = e.target.files[0]
      mindmapFileName.value = e.target.files[0].name
    }
  }
  input.click()
}

// 加载模板信息
const loadTemplateInfo = async () => {
  isTemplateLoading.value = true
  try {
    const r = await axios.get(apiUrl('/api/template'))
    if (r.data.success && r.data.data) {
      templateInfo.value = r.data.data
    }
  } catch { /* */ }
  finally { isTemplateLoading.value = false }
}

// 上传模板
const handleTemplateUpload = () => {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.docx'
  input.onchange = async (e: any) => {
    const file = e.target.files?.[0]
    if (!file) return
    isTemplateUploading.value = true
    try {
      const r = await axios.post(apiUrl('/api/template/upload'), file, {
        headers: { 'Content-Type': 'application/octet-stream', 'X-Filename': encodeURIComponent(file.name) },
        timeout: 30000
      })
      if (r.data.success) {
        ElMessage.success(`模板 "${file.name}" 上传成功`)
        await loadTemplateInfo()
      } else {
        ElMessage.warning(r.data.message || '上传失败')
      }
    } catch (e: any) {
      ElMessage.error('上传失败: ' + getErrMsg(e))
    } finally { isTemplateUploading.value = false }
  }
  input.click()
}

// 删除模板
const handleTemplateDelete = async () => {
  try {
    const r = await axios.delete(apiUrl('/api/template'))
    if (r.data.success) {
      ElMessage.success('模板已删除')
      templateInfo.value = { exists: false }
    }
  } catch { ElMessage.error('删除失败') }
}

// 获取模板内容
const getTemplateContent = async (): Promise<string> => {
  if (!templateInfo.value.exists) return ''
  try {
    const r = await axios.get(apiUrl('/api/template/content'))
    if (r.data.success && r.data.data?.content) {
      return r.data.data.content
    }
  } catch { /* */ }
  return ''
}

// 对话框打开时，刷新模板状态
watch(visible, (v) => {
  if (v) loadTemplateInfo()
})

const submit = async () => {
  if (!requirements.value.trim()) { ElMessage.warning('请输入需求描述'); return }

  let mindmapContext = ''
  if (mindmapFile) {
    try {
      const formData = new FormData()
      formData.append('file', mindmapFile)
      const r = await axios.post(apiUrl('/api/mindmap/parse'), formData, { timeout: 60000 })
      if (r.data.success && r.data.content) mindmapContext = r.data.content
    } catch { /* 脑图解析失败不影响主流程 */ }
  }

  // 如果有模板，获取模板内容
  const templateContent = templateInfo.value.exists ? await getTemplateContent() : ''

  const images = uploadedImages.value.map(img => img.dataUri)

  emit('submit', requirements.value.trim(), mindmapContext, templateContent, images)
  requirements.value = ''
  mindmapFile = null
  mindmapFileName.value = ''
  uploadedImages.value = []
  visible.value = false
}
</script>

<template>
  <el-dialog v-model="visible" title="智能PRD" width="550px" top="8vh">
    <div class="space-y-4">
      <div>
        <label class="text-sm font-medium text-app block mb-2">需求描述</label>
        <el-input
          v-model="requirements" type="textarea" :rows="6"
          placeholder="描述需求，例如：设计一个春节签到活动，持续7天，每日签到可获得不同奖励..."
          @keyup.ctrl.enter="submit"
        />
      </div>
      <div class="flex items-center gap-2">
        <span class="text-xs text-app-muted">辅助脑图（可选）：</span>
        <el-button size="small" @click="handleMindmapSelect">选择脑图文件</el-button>
        <span v-if="mindmapFileName" class="text-xs text-green-600">{{ mindmapFileName }}</span>
      </div>

      <!-- 系统原型图 -->
      <div class="border border-app rounded-lg p-3">
        <div class="flex items-center justify-between mb-2">
          <label class="text-sm font-medium text-app">系统原型图（可选）</label>
          <el-button size="small" @click="handleImageUpload">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="mr-1"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
            上传 PNG 图片
          </el-button>
        </div>
        <div v-if="uploadedImages.length > 0" class="grid grid-cols-3 gap-2">
          <div v-for="(img, idx) in uploadedImages" :key="idx" class="relative group border rounded-md overflow-hidden">
            <img :src="img.dataUri" class="w-full h-20 object-cover" alt="原型图" />
            <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
              <el-button size="small" circle @click.stop="removeImage(idx)">
                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </el-button>
            </div>
            <div class="text-[10px] text-app-muted truncate px-1">{{ img.name }}</div>
          </div>
        </div>
        <div v-else class="text-xs text-app-muted">上传系统原型图 PNG，让 AI 更了解系统需求（支持多张，每张最大 10MB）</div>
      </div>

      <!-- 文档模板 -->
      <div class="border border-app rounded-lg p-3">
        <div class="flex items-center justify-between mb-2">
          <label class="text-sm font-medium text-app">文档模板</label>
          <div class="flex gap-1">
            <el-button v-if="!templateInfo.exists" size="small" :loading="isTemplateUploading" @click="handleTemplateUpload">
              上传模板
            </el-button>
            <template v-if="templateInfo.exists">
              <el-button size="small" :loading="isTemplateUploading" @click="handleTemplateUpload">
                更换模板
              </el-button>
              <el-button size="small" type="danger" plain @click="handleTemplateDelete">
                删除模板
              </el-button>
            </template>
          </div>
        </div>
        <div v-if="isTemplateLoading" class="text-xs text-app-muted">加载中...</div>
        <div v-else-if="templateInfo.exists" class="flex items-center gap-2 text-xs text-green-600">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
          <span>当前模板：{{ templateInfo.name }}</span>
          <span class="text-app-muted">（仿写时将按此模板格式生成）</span>
        </div>
        <div v-else class="text-xs text-app-muted">
          上传 .docx 模板文件，仿写时将按模板的格式生成文档
        </div>
      </div>
    </div>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="submit" :disabled="!requirements.trim()">开始生成</el-button>
    </template>
  </el-dialog>
</template>
