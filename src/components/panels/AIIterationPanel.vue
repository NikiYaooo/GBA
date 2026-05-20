<script setup lang="ts">
import { ref } from 'vue'
import type { DocSection } from '@/utils/doc-sections'

const props = withDefaults(defineProps<{
  visible?: boolean
  embedded?: boolean
  currentSection: DocSection | null
  history: { instruction: string; targetSection: string; timestamp: number; replacement?: string }[]
  isIterating: boolean
}>(), {
  visible: false,
  embedded: false,
})

const emit = defineEmits<{
  submit: [instruction: string]
  close: []
}>()

const inputText = ref('')

const handleSubmit = () => {
  if (!inputText.value.trim() || props.isIterating) return
  emit('submit', inputText.value.trim())
  inputText.value = ''
}

const formatTime = (ts: number) => {
  const d = new Date(ts)
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}
</script>

<template>
  <!-- Embedded mode (inside tabs) → no header/close, fills parent -->
  <div v-if="embedded" class="flex flex-col min-h-0 h-full">
    <div class="flex-1 overflow-y-auto space-y-2 px-1">
      <div v-if="history.length === 0" class="h-full flex items-center justify-center text-xs text-app-muted px-3">
        在文档中选中章节或文字，然后输入修改指令
      </div>
      <div v-for="(item, i) in history" :key="i" class="text-xs">
        <div class="flex items-start gap-1">
          <span class="text-purple-600 font-medium shrink-0">你:</span>
          <span class="text-app">{{ item.instruction }}</span>
        </div>
        <div class="flex items-start gap-1 mt-0.5">
          <span class="text-green-600 font-medium shrink-0">AI:</span>
          <span class="text-app-muted">
            已修改「{{ item.targetSection || '文档' }}」
            <span class="text-[10px] text-zinc-300">{{ formatTime(item.timestamp) }}</span>
          </span>
        </div>
      </div>
    </div>

    <div class="flex gap-2 pt-2 border-t border-app-light mt-2">
      <el-input
        v-model="inputText"
        :placeholder="currentSection ? `修改「${currentSection.title}」...` : '输入修改指令...'"
        size="small"
        @keyup.enter="handleSubmit"
        :disabled="isIterating"
      />
      <el-button
        size="small"
        type="primary"
        @click="handleSubmit"
        :loading="isIterating"
        :disabled="!inputText.trim()"
      >发送</el-button>
    </div>

    <div v-if="currentSection" class="mt-1">
      <span class="text-[10px] text-app-muted">当前章节: {{ currentSection.title }}</span>
    </div>
  </div>

  <!-- Non-embedded mode (standalone panel) → original layout with header -->
  <div v-else-if="visible" class="border-t border-app bg-surface">
    <div class="flex items-center justify-between px-3 py-2">
      <span class="text-xs font-bold text-app-muted uppercase tracking-wider">AI 对话</span>
      <button class="text-xs text-app-muted hover:text-app" @click="emit('close')">关闭</button>
    </div>

    <div class="h-48 overflow-y-auto px-3 space-y-2" v-if="history.length > 0">
      <div v-for="(item, i) in history" :key="i" class="text-xs">
        <div class="flex items-start gap-1">
          <span class="text-purple-600 font-medium shrink-0">你:</span>
          <span class="text-app">{{ item.instruction }}</span>
        </div>
        <div class="flex items-start gap-1 mt-0.5">
          <span class="text-green-600 font-medium shrink-0">AI:</span>
          <span class="text-app-muted">
            已修改「{{ item.targetSection || '文档' }}」
            <span class="text-[10px] text-zinc-300">{{ formatTime(item.timestamp) }}</span>
          </span>
        </div>
      </div>
    </div>
    <div v-else class="h-48 flex items-center justify-center text-xs text-app-muted px-3">
      在文档中选中章节或文字，然后输入修改指令
    </div>

    <div class="p-3 border-t border-app-light flex gap-2">
      <el-input
        v-model="inputText"
        :placeholder="currentSection ? `修改「${currentSection.title}」...` : '输入修改指令...'"
        size="small"
        @keyup.enter="handleSubmit"
        :disabled="isIterating"
      />
      <el-button
        size="small"
        type="primary"
        @click="handleSubmit"
        :loading="isIterating"
        :disabled="!inputText.trim()"
      >发送</el-button>
    </div>

    <div v-if="currentSection" class="px-3 pb-2">
      <span class="text-[10px] text-app-muted">当前章节: {{ currentSection.title }}</span>
    </div>
  </div>
</template>
