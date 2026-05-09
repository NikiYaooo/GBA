<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { apiUrl } from '@/utils/api'

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  submit: [requirements: string, mindmapContent: string]
}>()

const requirements = ref('')
const mindmapFileName = ref('')
let mindmapFile: File | null = null

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

  emit('submit', requirements.value.trim(), mindmapContext)
  requirements.value = ''
  mindmapFile = null
  mindmapFileName.value = ''
  visible.value = false
}
</script>

<template>
  <el-dialog v-model="visible" title="智能仿写 / 智能PRD" width="550px" top="8vh">
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
    </div>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="submit" :disabled="!requirements.trim()">开始生成</el-button>
    </template>
  </el-dialog>
</template>
