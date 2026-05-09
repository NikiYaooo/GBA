<script setup lang="ts">
import { Database } from 'lucide-vue-next'
import type { KBStats } from '@/types'

const visible = defineModel<boolean>('visible', { default: false })

defineProps<{
  kbStats: KBStats
  isUploadingKB: boolean
  chunkSize: number
  showChunkSizeDialog: boolean
}>()

const emit = defineEmits<{
  'update:chunkSize': [val: number]
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
    <div class="bg-zinc-50 border border-zinc-200 rounded-lg p-4 mb-4 flex items-center gap-4">
      <Database class="w-8 h-8 text-blue-500" />
      <div class="grid grid-cols-3 gap-6 flex-1 text-sm">
        <div><span class="text-zinc-400">文档数</span><p class="font-semibold text-lg">{{ kbStats.total_documents }}</p></div>
        <div><span class="text-zinc-400">文本块</span><p class="font-semibold text-lg">{{ kbStats.total_chunks }}</p></div>
        <div><span class="text-zinc-400">总大小</span><p class="font-semibold text-lg">{{ formatSize(kbStats.total_size_bytes) }}</p></div>
      </div>
    </div>

    <div class="flex items-center justify-between mb-3">
      <div class="flex gap-2">
        <el-button size="small" @click="handleUploadClick" :loading="isUploadingKB">上传文档</el-button>
        <el-button size="small" @click="emit('update:showChunkSizeDialog', true)">
          向量块大小：{{ chunkSize }}
        </el-button>
        <el-dialog
          :model-value="showChunkSizeDialog" width="280px" top="20vh"
          @update:model-value="(v: boolean) => emit('update:showChunkSizeDialog', v)"
        >
          <template #header><span class="text-sm font-semibold">设置向量块大小</span></template>
          <div>
            <el-input-number
              :model-value="chunkSize" :min="100" :max="500" :step="50"
              @update:model-value="(v: number|null) => v && emit('update:chunkSize', v)"
            />
            <p class="text-xs text-zinc-400 mt-2">范围 100-500 字符，修改后仅对新入库文档生效</p>
          </div>
          <template #footer>
            <el-button size="small" @click="emit('update:showChunkSizeDialog', false)">取消</el-button>
            <el-button size="small" type="primary" @click="emit('saveChunkSize')">确定</el-button>
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
      class="border-2 border-dashed border-zinc-200 rounded-lg p-6 text-center mb-4 text-xs text-zinc-400"
      @dragover.prevent @drop.prevent="handleDrop"
    >
      拖拽 .docx / .md / .txt 文件到此处入库
    </div>

    <div class="max-h-[240px] overflow-y-auto">
      <div
        v-for="doc in kbStats.documents" :key="doc.file_hash"
        class="flex items-center gap-3 p-2 border-b border-zinc-100 text-sm hover:bg-zinc-50"
      >
        <span class="flex-1 truncate">{{ doc.filename }}</span>
        <span class="text-xs text-zinc-400">{{ doc.type }}</span>
        <span class="text-xs text-zinc-400">{{ doc.chunks_count }} 块</span>
        <span class="text-xs text-zinc-400">{{ formatSize(doc.file_size) }}</span>
        <el-button link size="small" type="danger" @click="emit('deleteDocument', doc.file_hash)">删除</el-button>
      </div>
      <div v-if="kbStats.total_documents === 0" class="text-center py-8 text-zinc-400 text-sm">
        暂无文档，上传文档到知识库以增强 AI 检索
      </div>
    </div>
  </el-dialog>
</template>
