<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Upload, FileText, X } from 'lucide-vue-next'
import axios from 'axios'
import { apiUrl, getErrMsg } from '@/utils/api'

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
  // .docx 通过后端解析
  const formData = new FormData()
  formData.append('file', file)
  const res = await axios.post(apiUrl('/api/ai/parse-docx'), formData)
  if (!res.data?.text) throw new Error('解析失败')
  return res.data.text
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
      ElMessage.success(`已上传：${file.name}`)
    } catch (err) {
      ElMessage.error('文件解析失败: ' + getErrMsg(err))
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
