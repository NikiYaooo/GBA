<script setup lang="ts">
import { Database } from 'lucide-vue-next'
import type { KBStats } from '@/types'

const visible = defineModel<boolean>('visible', { default: false })

defineProps<{
  kbStats: KBStats
  isUploadingKB: boolean
  chunkSizeMin: number
  chunkSizeMax: number
  showChunkSizeDialog: boolean
}>()

const emit = defineEmits<{
  'update:chunkSizeMin': [val: number]
  'update:chunkSizeMax': [val: number]
  uploadFile: [file: File]
  deleteDocument: [fileHash: string]
  clearAll: []
  saveChunkSize: []
  'update:showChunkSizeDialog': [val: boolean]
}>()

const formatSize = (bytes: number) => {
  if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + ' MB'
  if (bytes >= 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return bytes + ' B'
}

const handleDrop = (e: DragEvent) => {
  const files = e.dataTransfer?.files
  if (!files) return
  for (let i = 0; i < files.length; i++) {
    const ext = files[i].name.split('.').pop()?.toLowerCase()
    if (!['docx', 'md', 'txt'].includes(ext || '')) continue
    emit('uploadFile', files[i])
  }
}

const handleUploadClick = () => {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.docx,.md,.txt'
  input.multiple = true
  input.onchange = (e: any) => {
    for (let i = 0; i < e.target.files.length; i++) {
      emit('uploadFile', e.target.files[i])
    }
  }
  input.click()
}
</script>

<template>
  <el-dialog v-model="visible" title="知识库管理" width="650px" top="5vh">
    <div class="bg-primary-light border border-app rounded-lg p-4 mb-4 flex items-center gap-4">
      <Database class="w-8 h-8 text-app-primary" />
      <div class="grid grid-cols-3 gap-6 flex-1 text-sm">
        <div><span class="text-app-muted">文档数</span><p class="font-semibold text-lg">{{ kbStats.total_documents }}</p></div>
        <div><span class="text-app-muted">文本块</span><p class="font-semibold text-lg">{{ kbStats.total_chunks }}</p></div>
        <div><span class="text-app-muted">总大小</span><p class="font-semibold text-lg">{{ formatSize(kbStats.total_size_bytes) }}</p></div>
      </div>
    </div>

    <div class="flex items-center justify-between mb-3">
      <div class="flex gap-2">
        <el-button size="small" @click="handleUploadClick" :loading="isUploadingKB">上传文档</el-button>
        <el-button size="small" @click="emit('update:showChunkSizeDialog', true)">
          向量块大小：{{ chunkSizeMin }} ~ {{ chunkSizeMax }}
        </el-button>
        <el-dialog
          :model-value="showChunkSizeDialog" width="320px" top="20vh"
          @update:model-value="(v: boolean) => emit('update:showChunkSizeDialog', v)"
        >
          <template #header><span class="text-sm font-semibold">设置向量块大小</span></template>
          <div class="space-y-4">
            <div>
              <label class="text-xs text-app-secondary block mb-1">最小值（字符数）</label>
              <el-input-number
                :model-value="chunkSizeMin" :min="50" :max="500" :step="50"
                @update:model-value="(v: number|null) => v && emit('update:chunkSizeMin', v)"
              />
            </div>
            <div>
              <label class="text-xs text-app-secondary block mb-1">最大值（字符数）</label>
              <el-input-number
                :model-value="chunkSizeMax" :min="100" :max="1000" :step="50"
                @update:model-value="(v: number|null) => v && emit('update:chunkSizeMax', v)"
              />
            </div>
            <p class="text-xs text-app-muted">保存后将对知识库中已有文档重新分块</p>
          </div>
          <template #footer>
            <el-button size="small" @click="emit('update:showChunkSizeDialog', false)">取消</el-button>
            <el-button size="small" type="primary" @click="emit('saveChunkSize')">保存并重新分块</el-button>
          </template>
        </el-dialog>
      </div>
      <el-button
        v-if="kbStats.total_documents > 0" size="small" type="danger" plain
        @click="emit('clearAll')"
      >
        清空
      </el-button>
    </div>

    <div
      class="border-2 border-dashed border-app rounded-lg p-6 text-center mb-4 text-xs text-app-muted"
      @dragover.prevent @drop.prevent="handleDrop"
    >
      拖拽 .docx / .md / .txt 文件到此处入库
    </div>

    <div class="max-h-[240px] overflow-y-auto">
      <div
        v-for="doc in kbStats.documents" :key="doc.file_hash"
        class="flex items-center gap-3 p-2 border-b border-app-light text-sm hover:bg-app-hover"
      >
        <span class="flex-1 truncate">{{ doc.filename }}</span>
        <span class="text-xs text-app-muted">{{ doc.type }}</span>
        <span class="text-xs text-app-muted">{{ doc.chunks_count }} 块</span>
        <span class="text-xs text-app-muted">{{ formatSize(doc.file_size) }}</span>
        <el-button link size="small" type="danger" @click="emit('deleteDocument', doc.file_hash)">删除</el-button>
      </div>
      <div v-if="kbStats.total_documents === 0" class="text-center py-8 text-app-muted text-sm">
        暂无文档，上传文档到知识库以增强 AI 检索
      </div>
    </div>
  </el-dialog>
</template>
