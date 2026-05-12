<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { apiUrl, getErrMsg } from '@/utils/api'

const props = defineProps<{
  visible: boolean
  docContent: string
  docName: string
  docId: string
}>()

const emit = defineEmits<{
  'update:visible': [val: boolean]
}>()

const modelOptions = ref<{ name: string; configured: boolean }[]>([])
const selectedModel = ref('GPT')
const isGenerating = ref(false)
const generatedImages = ref<{ index: number; data_uri: string; selected: boolean }[]>([])
const isSaving = ref(false)

// 默认设计 prompt（不在界面显示）
const designPrompt = "手游UI，系统界面原型图，简洁风格，轻质感，柔和阴影，圆角控件，适当效果，浅蓝白配色，专业游戏UI设计，符合交互逻辑，高清，高细节，原型图+标题描述"

// 加载可选模型列表
const loadModels = async () => {
  try {
    const r = await axios.get(apiUrl('/api/config'))
    if (r.data.success && r.data.data?.models) {
      const modelConfigs = r.data.data.models
      // 支持生图的模型列表
      const imageModels = ['GPT']
      modelOptions.value = imageModels.map(name => ({
        name,
        configured: !!(modelConfigs[name]?.apiKey)
      }))
      const firstConfigured = modelOptions.value.find(m => m.configured)
      if (firstConfigured) selectedModel.value = firstConfigured.name
    }
  } catch { /* */ }
}

const generate = async () => {
  if (!props.docContent) { ElMessage.warning('文档内容为空'); return }
  if (!selectedModel.value) { ElMessage.warning('请选择AI模型'); return }

  const modelOpt = modelOptions.value.find(m => m.name === selectedModel.value)
  if (!modelOpt?.configured) {
    ElMessage.warning('所选模型未配置 API Key，请先在设置中配置')
    return
  }

  isGenerating.value = true
  generatedImages.value = []
  try {
    const r = await axios.post(apiUrl('/api/ai/generate-ui'), {
      model: selectedModel.value,
      content: props.docContent,
      design_prompt: designPrompt,
      count: 4
    })
    if (r.data.success && r.data.data?.images) {
      generatedImages.value = r.data.data.images.map((img: any) => ({
        ...img,
        selected: true  // 默认选中
      }))
      if (generatedImages.value.length === 0) {
        ElMessage.warning('未生成任何图片')
      }
    } else {
      ElMessage.warning(r.data.message || '生成失败')
    }
  } catch (e: any) {
    ElMessage.error('生成失败: ' + getErrMsg(e))
  } finally { isGenerating.value = false }
}

const toggleImage = (index: number) => {
  const img = generatedImages.value.find(i => i.index === index)
  if (img) img.selected = !img.selected
}

const toggleAll = () => {
  const allSelected = generatedImages.value.every(i => i.selected)
  generatedImages.value.forEach(i => { i.selected = !allSelected })
}

const saveSelected = async () => {
  const selected = generatedImages.value.filter(i => i.selected)
  if (selected.length === 0) { ElMessage.warning('请至少选择一张图片'); return }

  isSaving.value = true
  try {
    // 通过 Electron API 保存到文档所在文件夹
    const api = (window as any).electronAPI
    if (!api?.saveFileAs) {
      // 非桌面环境：下载到本地
      for (const img of selected) {
        const link = document.createElement('a')
        link.href = img.data_uri
        link.download = `${props.docName}_UI_${img.index + 1}.png`
        link.click()
      }
      ElMessage.success(`已下载 ${selected.length} 张图片`)
      isSaving.value = false
      return
    }

    // 桌面环境：保存到文档所在文件夹或用户选择的位置
    for (const img of selected) {
      const defaultName = `${props.docName.replace(/\.[^/.]+$/, '')}_UI_${img.index + 1}.png`
      const result = await api.saveFileAs(img.data_uri, defaultName)
      if (!result?.success && result?.error !== 'Canceled') {
        ElMessage.warning(`图片 ${img.index + 1} 保存失败`)
      }
    }
    ElMessage.success(`已保存 ${selected.length} 张图片`)
  } catch (e: any) {
    ElMessage.error('保存失败: ' + getErrMsg(e))
  } finally { isSaving.value = false }
}

watch(() => props.visible, (v) => {
  if (v) {
    generatedImages.value = []
    loadModels()
  }
})
</script>

<template>
  <el-dialog :model-value="visible" title="界面生成" width="750px" top="5vh"
    @update:model-value="(v: boolean) => emit('update:visible', v)">
    <div class="space-y-4">
      <!-- 模型选择 -->
      <div class="flex items-center gap-3">
        <label class="text-sm font-medium shrink-0">AI 模型</label>
        <el-select v-model="selectedModel" size="small" class="w-48">
          <el-option v-for="m in modelOptions" :key="m.name" :label="m.name + (m.configured ? '' : '（未配置）')"
            :value="m.name" :disabled="!m.configured" />
        </el-select>
        <el-button type="primary" size="small" :loading="isGenerating" :disabled="!docContent" @click="generate">
          生成原型图
        </el-button>
      </div>

      <!-- 提示信息 -->
      <div v-if="!docContent" class="text-sm text-orange-500">当前文档内容为空，请先编辑文档内容再生成</div>

      <!-- 图片预览 -->
      <div v-if="generatedImages.length > 0">
        <div class="flex items-center justify-between mb-2">
          <span class="text-sm text-app-muted">共生成 {{ generatedImages.length }} 张图片</span>
          <div class="flex gap-2">
            <el-button size="small" link @click="toggleAll">全选/取消</el-button>
            <el-button size="small" type="primary" :loading="isSaving" :disabled="generatedImages.filter(i => i.selected).length === 0" @click="saveSelected">
              保存选中 ({{ generatedImages.filter(i => i.selected).length }})
            </el-button>
          </div>
        </div>
        <div class="grid grid-cols-2 gap-4 max-h-[480px] overflow-y-auto">
          <div v-for="img in generatedImages" :key="img.index"
            class="relative border rounded-lg overflow-hidden cursor-pointer group"
            :class="img.selected ? 'ring-2 ring-blue-500' : 'opacity-70'"
            @click="toggleImage(img.index)">
            <img :src="img.data_uri" :alt="`原型图 ${img.index + 1}`" class="w-full h-auto" />
            <div class="absolute top-2 left-2 bg-black/50 text-white text-xs px-2 py-0.5 rounded">
              {{ img.index + 1 }}
            </div>
            <div v-if="img.selected"
              class="absolute top-2 right-2 bg-blue-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs">
              ✓
            </div>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else-if="!isGenerating" class="text-center py-12 text-app-muted text-sm">
        点击「生成原型图」按钮，根据文档描述生成 UI 原型预览
      </div>

      <!-- 加载状态 -->
      <div v-if="isGenerating" class="text-center py-12 text-sm text-blue-500">
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="animate-spin inline-block mr-2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
        AI 正在生成中...
      </div>
    </div>
  </el-dialog>
</template>
