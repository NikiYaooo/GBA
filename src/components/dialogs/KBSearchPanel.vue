<script setup lang="ts">
import { ref } from 'vue'
import { Search } from 'lucide-vue-next'
import type { KBSearchResult, KBProject, KBFolder } from '@/types'

const visible = defineModel<boolean>('visible', { default: false })

const props = defineProps<{
  projects: KBProject[]
  activeProjectId: string
  folders: KBFolder[]
  searchResults: KBSearchResult[]
  searchLoading: boolean
}>()

const emit = defineEmits<{
  search: [query: string, topK?: number, folderId?: string]
  fuzzySearch: [keyword: string, folderId?: string]
  switchProject: [id: string]
}>()

const query = ref('')
const isFuzzy = ref(false)
const filterFolder = ref('')

const onSearch = () => {
  if (!query.value.trim()) return
  if (isFuzzy.value) {
    emit('fuzzySearch', query.value.trim(), filterFolder.value || undefined)
  } else {
    emit('search', query.value.trim(), 10, filterFolder.value || undefined)
  }
}

const truncate = (text: string, max: number) => {
  return text.length > max ? text.slice(0, max) + '...' : text
}
</script>

<template>
  <el-dialog
    v-model="visible"
    title="知识库检索"
    width="650px"
    top="10vh"
  >
    <!-- Search controls -->
    <div class="space-y-3 mb-4">
      <div class="flex gap-2">
        <el-input
          v-model="query"
          size="default"
          placeholder="输入搜索关键词..."
          clearable
          @keyup.enter="onSearch"
        >
          <template #prefix>
            <Search class="w-4 h-4" />
          </template>
        </el-input>
        <el-button type="primary" :loading="searchLoading" @click="onSearch">检索</el-button>
      </div>

      <div class="flex items-center gap-4">
        <div v-if="projects.length > 1" class="flex items-center gap-2 text-sm">
          <span class="text-app-muted">项目:</span>
          <el-select v-model="filterFolder" size="small" placeholder="全部项目" disabled class="!w-36">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </div>
        <div class="flex items-center gap-2 text-sm">
          <span class="text-app-muted">文件夹:</span>
          <el-select v-model="filterFolder" size="small" clearable placeholder="全部" class="!w-32">
            <el-option v-for="f in folders" :key="f.id" :label="f.name" :value="f.id" />
          </el-select>
        </div>
        <el-checkbox v-model="isFuzzy" size="small">模糊匹配</el-checkbox>
      </div>
    </div>

    <!-- Results -->
    <div v-if="searchLoading" class="text-center py-8 text-app-muted text-sm">检索中...</div>

    <div v-else-if="searchResults.length === 0 && query" class="text-center py-8 text-app-muted text-sm">
      未找到匹配结果
    </div>

    <div v-else-if="searchResults.length > 0" class="max-h-[400px] overflow-y-auto space-y-2">
      <div
        v-for="(r, i) in searchResults" :key="i"
        class="p-3 border rounded text-sm hover:bg-app-hover"
      >
        <div class="text-xs text-app-muted mb-1">
          {{ r.metadata?.filename || '未知来源' }}
          <span class="ml-2">相似度: {{ (r.score * 100).toFixed(0) }}%</span>
        </div>
        <div class="text-sm whitespace-pre-wrap line-clamp-4">{{ truncate(r.content, 300) }}</div>
      </div>
    </div>

    <div v-else class="text-center py-8 text-app-muted text-sm">
      输入关键词开始检索
    </div>
  </el-dialog>
</template>
