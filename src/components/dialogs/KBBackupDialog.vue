<script setup lang="ts">
import type { KBBackup } from '@/types'

const visible = defineModel<boolean>('visible', { default: false })

const props = defineProps<{
  backups: KBBackup[]
  loading: boolean
}>()

const emit = defineEmits<{
  loadBackups: []
  createBackup: []
  restoreBackup: [filename: string]
  deleteBackup: [filename: string]
}>()

const formatDate = (ts: number) => {
  return new Date(ts * 1000).toLocaleString()
}

const formatSize = (bytes: number) => {
  if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + ' MB'
  if (bytes >= 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return bytes + ' B'
}

const onOpen = () => {
  emit('loadBackups')
}

const onRestore = (filename: string) => {
  emit('restoreBackup', filename)
}

const onDelete = (filename: string) => {
  emit('deleteBackup', filename)
}
</script>

<template>
  <el-dialog
    v-model="visible"
    title="备份管理"
    width="600px"
    top="15vh"
    @open="onOpen"
  >
    <div class="flex justify-end mb-3">
      <el-button size="small" type="primary" :loading="loading" @click="emit('createBackup')">
        创建备份
      </el-button>
    </div>

    <div v-if="backups.length === 0" class="text-center py-8 text-app-muted text-sm">
      暂无备份
    </div>

    <div v-else class="space-y-2">
      <div
        v-for="b in backups" :key="b.filename"
        class="flex items-center gap-3 p-2 border rounded text-sm"
      >
        <span class="flex-1 truncate">{{ b.filename }}</span>
        <span class="text-xs text-app-muted">{{ formatDate(b.created_at) }}</span>
        <span class="text-xs text-app-muted">{{ formatSize(b.size) }}</span>
        <el-button size="small" type="primary" link @click="onRestore(b.filename)">恢复</el-button>
        <el-button size="small" type="danger" link @click="onDelete(b.filename)">删除</el-button>
      </div>
    </div>
  </el-dialog>
</template>
