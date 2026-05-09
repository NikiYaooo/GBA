<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { apiUrl } from '@/utils/api'
import type { Profession, PromptTemplate } from '@/types'

const visible = defineModel<boolean>('visible', { default: false })
const props = defineProps<{
  professions: Profession[]
  selectedProfessionId: string
  selectedPrompt: PromptTemplate | null
}>()

const emit = defineEmits<{
  'update:selectedProfessionId': [val: string]
  'update:selectedPrompt': [val: PromptTemplate | null]
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

const onProfessionChange = (profId: string) => {
  emit('update:selectedProfessionId', profId)
  const pro = props.professions.find(p => p.id === profId)
  const prompts = pro?.prompts || []
  emit('update:selectedPrompt', prompts.length > 0 ? prompts[0] : null)
}
</script>

<template>
  <el-dialog v-model="visible" title="智能仿写 / 智能PRD" width="550px" top="8vh">
    <div class="space-y-4">
      <div>
        <label class="text-sm font-medium text-app block mb-2">仿写职业</label>
        <el-select
          :model-value="selectedProfessionId"
          class="w-full"
          @change="onProfessionChange"
        >
          <el-option v-for="p in professions" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
      </div>
      <div v-if="(professions.find(p=>p.id===selectedProfessionId)?.prompts?.length||0) > 1">
        <label class="text-sm font-medium text-app block mb-2">仿写 Prompt</label>
        <el-select
          :model-value="selectedPrompt?.id"
          class="w-full"
          @change="(val:string) => emit('update:selectedPrompt', professions.find(p=>p.id===selectedProfessionId)?.prompts?.find(pp=>pp.id===val)||null)"
        >
          <el-option
            v-for="pp in (professions.find(p=>p.id===selectedProfessionId)?.prompts||[])"
            :key="pp.id" :label="pp.name" :value="pp.id"
          />
        </el-select>
      </div>
      <div>
        <label class="text-sm font-medium text-app block mb-2">需求描述</label>
        <el-input
          v-model="requirements" type="textarea" :rows="5"
          placeholder="描述需求，例如：设计一个春节签到活动..." @keyup.ctrl.enter="submit"
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
